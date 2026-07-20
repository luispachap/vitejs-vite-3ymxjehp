# -*- coding: utf-8 -*-
"""
SERVICIO DE LA ASISTENTE DE VOZ "SOFÍA"
=======================================
Capa centralizada para las interacciones telefónicas. La voz se sintetiza
en ElevenLabs y las llamadas las orquesta Vapi o Retell AI; este servicio
alimenta a Sofía con datos frescos de la base durante la llamada.

DISEÑO PARA BAJA LATENCIA (una llamada no puede quedarse en silencio):
- Búsqueda por Caller ID sobre columna INDEXADA (telefono_whatsapp).
- Una sola sesión de base de datos por petición; sin joins pesados:
  los montos del mes se resuelven con dos consultas puntuales por índice
  (cliente_id, mes, anio son índices/constraint únicos).
- Cero llamadas a servicios externos dentro del request.

PROTECCIÓN DE DATOS SENSIBLES:
- Los montos (SAT y honorarios) viven CIFRADOS en la base y solo se
  descifran en memoria para responder al orquestador autenticado.
- Autenticación: header X-Voice-Api-Key == VOICE_WEBHOOK_API_KEY (.env).
  Sin llave válida, /api/voice/* responde 401 y no revela nada.
- Regla de Oro respetada: la respuesta incluye `permite_cobranza_automatica`
  para que el prompt de Sofía NO mencione honorarios a clientes de trato
  especial o con el switch apagado (la llamada entrante se atiende igual,
  pero sin gestión de cobro).

LLAVES EN .env (ver config.py): ELEVENLABS_API_KEY, VOICE_WEBHOOK_API_KEY,
VOZ_API_KEY, VOZ_AGENT_ID, NOMBRE_ASISTENTE_VOZ.
"""
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from models.models import (Cita, Cliente, EstatusCita, EstatusPago,
                           HonorarioCobranza, ObligacionMensual, PagoIMSS,
                           PagoISN, RolUsuario, TipoCliente, Usuario)
from services.reglas_negocio import puede_automatizar_cobranza

DURACION_CITA_MINUTOS = 60


def _normalizar_telefono(telefono: str) -> str:
    """'+52 492 123 4567' -> '+524921234567' (formato E.164 compacto)."""
    limpio = "".join(ch for ch in (telefono or "") if ch.isdigit() or ch == "+")
    if limpio and not limpio.startswith("+"):
        # números nacionales de 10 dígitos -> prefijo México
        limpio = "+52" + limpio[-10:] if len(limpio) >= 10 else limpio
    return limpio


def buscar_por_caller_id(db: Session, telefono: str) -> dict:
    """
    Identifica al cliente que llama y arma el paquete de datos dinámicos
    que Sofía usa para saludar y contextualizar la conversación.
    """
    tel = _normalizar_telefono(telefono)
    cliente = (db.query(Cliente)
               .filter(Cliente.telefono_whatsapp == tel).first())
    if not cliente:
        return {"estatus": "desconocido", "telefono": tel}

    hoy = date.today()
    obligacion = (db.query(ObligacionMensual)
                  .filter_by(cliente_id=cliente.id, mes=hoy.month,
                             anio=hoy.year).first())
    honorario = (db.query(HonorarioCobranza)
                 .filter_by(cliente_id=cliente.id, mes=hoy.month,
                            anio=hoy.year).first())

    # Fuente de verdad: los montos SIEMPRE salen de las tablas del mes
    # (no de columnas duplicadas que pudieran quedarse desfasadas).
    return {
        "estatus": "identificado",
        "cliente_id": cliente.id,
        "cliente_nombre": cliente.nombre_comercial,
        # Título de cortesía para el saludo norteño de Sofía
        "cliente_titulo": ("estimado cliente preferente"
                           if cliente.tipo_cliente == TipoCliente.VIP
                           else "estimado cliente"),
        "nombre_alternativo": cliente.nombre_alternativo_telefono,
        "numero_compartido": cliente.numero_compartido,
        "monto_sat": (obligacion.monto_impuesto_sat if obligacion else None),
        "vencimiento_sat": (str(obligacion.fecha_vencimiento_sat)
                            if obligacion and obligacion.fecha_vencimiento_sat
                            else None),
        "monto_honorarios": (honorario.monto_honorario if honorario else None),
        "honorarios_pagados": (honorario.estatus_pago == EstatusPago.PAGADO
                               if honorario else None),
        # Detalle patronal: total del IMSS y desglose por concepto, más el
        # ISN, para que Sofía pueda responder "cuánto corresponde a qué"
        # si el cliente pregunta durante la llamada.
        "imss": _detalle_imss(db, cliente, hoy),
        "isn": _detalle_isn(db, cliente, hoy),
        # Bandera para el prompt: si es False, Sofía NO gestiona cobro
        "permite_cobranza_automatica": puede_automatizar_cobranza(cliente),
        "contador_asignado": (cliente.contador_asignado.nombre
                              if cliente.contador_asignado else None),
    }


def _detalle_imss(db: Session, cliente: Cliente, hoy) -> dict | None:
    """Total y desglose de cuotas patronales del mes (None si no aplica)."""
    if not cliente.tiene_imss:
        return None
    pago = (db.query(PagoIMSS)
            .filter_by(cliente_id=cliente.id, mes=hoy.month, anio=hoy.year)
            .first())
    if not pago:
        return {"presentado": False}
    return {"presentado": bool(pago.sipare_presentado
                               and pago.formato_pago_documento_id),
            "total": pago.total_a_pagar,
            "desglose": pago.desglose_cuotas or {}}


def _detalle_isn(db: Session, cliente: Cliente, hoy) -> dict | None:
    """Importe del impuesto sobre nómina del mes (None si no aplica)."""
    if not cliente.tiene_nomina:
        return None
    pago = (db.query(PagoISN)
            .filter_by(cliente_id=cliente.id, mes=hoy.month, anio=hoy.year)
            .first())
    if not pago or not pago.documento_id:
        return {"presentado": False}
    return {"presentado": True, "importe": pago.importe}


def registrar_contacto_alternativo(db: Session, telefono: str,
                                   nuevo_nombre: str) -> dict:
    """
    El titular indicó que otra persona atiende habitualmente este número
    (familiar o administrador): se registra para que Sofía salude bien
    en la próxima llamada.
    """
    tel = _normalizar_telefono(telefono)
    cliente = db.query(Cliente).filter(Cliente.telefono_whatsapp == tel).first()
    if not cliente:
        return {"estatus": "desconocido"}

    cliente.nombre_alternativo_telefono = (nuevo_nombre or "").strip()[:120]
    cliente.numero_compartido = True
    db.commit()
    return {"estatus": "actualizado", "cliente_id": cliente.id,
            "nombre_alternativo": cliente.nombre_alternativo_telefono,
            "numero_compartido": True}


def _espacio_libre(db: Session, con_usuario_id: int,
                   fecha_hora: datetime) -> bool:
    """
    Verificación de disponibilidad (lógica local; cuando se conecte un
    calendario externo, este es el único punto a sustituir): no debe haber
    otra cita del mismo miembro del equipo que se traslape ±duración.
    """
    margen = timedelta(minutes=DURACION_CITA_MINUTOS)
    choque = (db.query(Cita)
              .filter(Cita.con_usuario_id == con_usuario_id,
                      Cita.estatus.in_([EstatusCita.SOLICITADA,
                                        EstatusCita.CONFIRMADA]),
                      Cita.fecha_hora > fecha_hora - margen,
                      Cita.fecha_hora < fecha_hora + margen)
              .first())
    return choque is None


def agendar_cita_por_voz(db: Session, cliente_id: int, fecha_hora: datetime,
                         motivo: str | None,
                         con_usuario_id: int | None = None) -> dict:
    """
    Sofía agenda en vivo durante la llamada. Escribe en la MISMA tabla de
    citas del sistema (la que gestiona Pao y ve el personal en su agenda),
    con estatus CONFIRMADA. Por omisión, con el contador(a) asignado(a) del
    cliente; si no tiene, con la Supervisora; en última instancia el Director.
    """
    cliente = db.query(Cliente).get(cliente_id)
    if not cliente:
        return {"estatus": "error", "detalle": "cliente no encontrado"}
    if fecha_hora <= datetime.utcnow():
        return {"estatus": "error", "detalle": "la fecha debe ser futura"}

    destino_id = con_usuario_id or cliente.contador_asignado_id
    if not destino_id:
        respaldo = (db.query(Usuario)
                    .filter(Usuario.rol.in_([RolUsuario.SUPERVISOR,
                                             RolUsuario.DIRECTOR]),
                            Usuario.activo)
                    .order_by(Usuario.rol.desc()).first())
        destino_id = respaldo.id if respaldo else None
    if not destino_id:
        return {"estatus": "error", "detalle": "sin personal disponible"}

    if not _espacio_libre(db, destino_id, fecha_hora):
        return {"estatus": "ocupado",
                "detalle": "ese horario ya está tomado; proponer otro"}

    cita = Cita(cliente_id=cliente.id, con_usuario_id=destino_id,
                fecha_hora=fecha_hora, motivo=(motivo or "").strip()[:500] or None,
                modalidad="llamada", estatus=EstatusCita.CONFIRMADA)
    db.add(cita)
    db.flush()
    destino = db.query(Usuario).get(destino_id)
    db.commit()
    return {"estatus": "confirmada", "cita_id": cita.id,
            "con": destino.nombre,
            "fecha_hora": cita.fecha_hora.isoformat(),
            "mensaje_para_sofia": f"Su cita quedó confirmada con "
                                  f"{destino.nombre} el "
                                  f"{cita.fecha_hora.strftime('%d/%m a las %H:%M')}"}
