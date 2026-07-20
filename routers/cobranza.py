# -*- coding: utf-8 -*-
"""
MÓDULOS 3 y 5: Panel de la Secretaria (Pao) + Gestión de efectivo.
Endpoints diseñados para una interfaz de 3 pestañas (Roja/Amarilla/Verde)
con acciones de un solo botón.
"""
import random
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from models.models import (Cliente, EstatusPago, HonorarioCobranza,
                           RolUsuario, Usuario)
from services.auth import requiere_rol, solo_equipo_contable
from services import auditoria, whatsapp
from services.campo_cifrado import hash_busqueda
from services.reglas_negocio import puede_automatizar_cobranza

router = APIRouter(prefix="/api/cobranza", tags=["Cobranza (Panel de Pao)"])

# El kiosco de cobranza lo usan Pao, el Director, la Supervisora (jefa del
# despacho) y el Administrador (acceso total).
ROLES_PAO = (RolUsuario.ADMIN_SECRETARIA, RolUsuario.DIRECTOR,
             RolUsuario.SUPERVISOR, RolUsuario.ADMINISTRADOR)


# ---------------------------------------------------------------------------
# BUSCADOR UNIVERSAL (Pao): por nombre comercial o RFC exacto
# ---------------------------------------------------------------------------

@router.get("/buscar")
def buscar_cliente(q: str,
                   u: Usuario = Depends(requiere_rol(*ROLES_PAO)),
                   db: Session = Depends(get_db)):
    """
    Busca por nombre (contiene) o por RFC exacto. El RFC está cifrado en la
    base, así que la coincidencia exacta se hace vía rfc_hash (HMAC), sin
    exponer ni recorrer valores descifrados en SQL.
    """
    q = q.strip()
    if len(q) < 2:
        return []
    resultados = (db.query(Cliente)
                  .filter(Cliente.nombre_comercial.ilike(f"%{q}%")).limit(8).all())
    por_rfc = (db.query(Cliente)
               .filter(Cliente.rfc_hash == hash_busqueda(q)).first())
    if por_rfc and por_rfc.id not in {c.id for c in resultados}:
        resultados.insert(0, por_rfc)

    salida = []
    for c in resultados:
        h = next((x for x in sorted(c.honorarios, key=lambda y: (y.anio, y.mes),
                                    reverse=True)
                  if x.estatus_pago != EstatusPago.PAGADO), None)
        salida.append({
            "cliente_id": c.id, "cliente": c.nombre_comercial, "rfc": c.rfc,
            "tipo_cliente": c.tipo_cliente.value,
            "automatizaciones_activas": c.automatizaciones_activas,
            "saldo_pendiente": ({"honorario_id": h.id, "monto": h.monto_honorario,
                                 "dias_vencido": h.dias_vencido,
                                 "estatus": h.estatus_pago.value} if h else None),
        })
    return salida


# ---------------------------------------------------------------------------
# RECORDATORIO AMABLE VÍA REGINA (un toque, sin redactar)
# ---------------------------------------------------------------------------

@router.post("/{honorario_id}/recordatorio-regina")
def recordatorio_regina(honorario_id: int, request: Request,
                          u: Usuario = Depends(requiere_rol(*ROLES_PAO)),
                          db: Session = Depends(get_db)):
    """
    Botón [Enviar Recordatorio Amable vía Regina] del panel de Pao.
    La REGLA DE ORO se valida aquí también: si el cliente es de trato
    especial o el switch está apagado, el sistema se niega con un mensaje
    claro para Pao, aunque ella haya tocado el botón.
    """
    h = db.query(HonorarioCobranza).get(honorario_id)
    if not h:
        raise HTTPException(404, "Honorario no encontrado")
    if h.estatus_pago == EstatusPago.PAGADO:
        raise HTTPException(409, "Este cliente ya pagó este mes")
    if not puede_automatizar_cobranza(h.cliente):
        raise HTTPException(403, "Cliente de trato especial: su cobranza la "
                                 "lleva personalmente el Director")

    mensaje = (f"Hola {h.cliente.nombre_comercial}, le saluda Regina de "
               f"Pacheco & Aparicio. Solo un recordatorio amable: su estado de "
               f"cuenta del mes por ${h.monto_honorario:,.2f} sigue disponible "
               f"para cuando guste programar su movimiento. Cualquier duda, "
               f"aquí estamos para servirle. ¡Excelente día!")
    whatsapp._enviar(h.cliente.telefono_whatsapp, mensaje)
    whatsapp.registrar_evento_bitacora(h, "recordatorio_manual_regina",
                                       disparado_por=u.nombre)
    auditoria.registrar(db, usuario_id=u.id, accion="recordatorio_regina",
                        tabla_afectada="honorarios_cobranza", registro_id=h.id,
                        request=request, cliente=h.cliente.nombre_comercial)
    db.commit()
    return {"ok": True, "mensaje": f"Regina ya le escribió a {h.cliente.nombre_comercial}"}


# ---------------------------------------------------------------------------
# LAS 3 PESTAÑAS
# ---------------------------------------------------------------------------

@router.post("/generar")
def generar_honorarios(request: Request, mes: int, anio: int,
                       u: Usuario = Depends(solo_equipo_contable),
                       db: Session = Depends(get_db)):
    """
    Genera los cobros del periodo a partir del honorario contratado de cada
    cliente. ANTES ESTO NO EXISTÍA: se capturaba el honorario pero nadie
    creaba el cargo, así que la cobranza salía vacía.

    Reglas:
      · Solo clientes ACTIVOS con honorario capturado.
      · Periodicidad: mensual (todos los meses), bimestral (meses impares)
        y anual (solo enero).
      · La fecha límite es el día de corte del cliente.
      · Es IDEMPOTENTE: si el cobro del periodo ya existe, no lo duplica ni
        lo pisa (por si ya se pagó o se editó a mano).
      · REGLA DE ORO: a los de CONFIANZA_ESPECIAL sí se les genera el cargo
        (el despacho necesita saber cuánto se les debe cobrar), pero su
        cobranza sigue siendo 100% humana: ninguna automatización los toca.
    """
    from calendar import monthrange
    from models.models import EstatusCliente, TipoCliente

    creados, omitidos, ya_estaban = [], [], 0
    for c in db.query(Cliente).filter(Cliente.estatus == EstatusCliente.ACTIVO).all():
        monto = c.honorario_mensual
        if not monto or float(monto) <= 0:
            omitidos.append({"cliente": c.nombre_comercial,
                             "motivo": "sin honorario capturado"})
            continue
        periodicidad = (c.periodicidad_honorario or "mensual").lower()
        if periodicidad == "bimestral" and mes % 2 == 0:
            continue                      # el bimestral cae en meses impares
        if periodicidad == "anual" and mes != 1:
            continue
        existente = (db.query(HonorarioCobranza)
                     .filter_by(cliente_id=c.id, mes=mes, anio=anio).first())
        if existente:
            ya_estaban += 1
            continue
        dia = min(int(c.dia_corte_honorario or 1), monthrange(anio, mes)[1])
        h = HonorarioCobranza(
            cliente_id=c.id, mes=mes, anio=anio,
            monto_honorario=round(float(monto), 2),
            estatus_pago=EstatusPago.PENDIENTE,
            fecha_limite_pago=date(anio, mes, dia))
        db.add(h)
        creados.append({"cliente": c.nombre_comercial, "monto": float(monto),
                        "vence": str(h.fecha_limite_pago),
                        "confianza_especial": c.tipo_cliente == TipoCliente.CONFIANZA_ESPECIAL})
    db.flush()
    auditoria.registrar(db, usuario_id=u.id, accion="generar_honorarios_periodo",
                        tabla_afectada="honorarios_cobranza", registro_id=None,
                        request=request, mes=mes, anio=anio,
                        creados=len(creados), ya_estaban=ya_estaban)
    db.commit()
    return {"creados": creados, "ya_estaban": ya_estaban,
            "sin_honorario": omitidos,
            "mensaje": (f"{len(creados)} cobro(s) generado(s) para {mes:02d}/{anio}."
                        + (f" {ya_estaban} ya existían." if ya_estaban else "")
                        + (f" {len(omitidos)} cliente(s) sin honorario capturado: "
                           f"póngaselo en su expediente." if omitidos else ""))}


@router.get("/resumen")
def resumen_cobranza(mes: int, anio: int,
                     u: Usuario = Depends(solo_equipo_contable),
                     db: Session = Depends(get_db)):
    """Lo que hay que cobrar este periodo, con los adeudos anteriores."""
    from models.models import AdeudoPrevio, EstatusCliente

    honorarios = (db.query(HonorarioCobranza)
                  .filter_by(mes=mes, anio=anio).all())
    activos = db.query(Cliente).filter(Cliente.estatus == EstatusCliente.ACTIVO).all()
    sin_honorario = [c.nombre_comercial for c in activos
                     if not c.honorario_mensual or float(c.honorario_mensual) <= 0]
    adeudos = db.query(AdeudoPrevio).filter_by(liquidado=False).all()
    saldo_adeudos = sum(float(a.monto_original or 0) - float(a.monto_pagado or 0)
                        for a in adeudos)
    cobrado = sum(float(h.monto_honorario or 0) for h in honorarios
                  if h.estatus_pago == EstatusPago.PAGADO)
    facturado = sum(float(h.monto_honorario or 0) for h in honorarios)
    return {
        "mes": mes, "anio": anio,
        "clientes_activos": len(activos),
        "honorarios_generados": len(honorarios),
        "sin_honorario_capturado": sin_honorario,
        "facturado": round(facturado, 2),
        "cobrado": round(cobrado, 2),
        "por_cobrar": round(facturado - cobrado, 2),
        "adeudos_anteriores": round(saldo_adeudos, 2),
        "adeudos_detalle": [
            {"id": a.id, "cliente": a.cliente.nombre_comercial if a.cliente else "—",
             "cliente_id": a.cliente_id, "concepto": a.concepto,
             "saldo": round(float(a.monto_original or 0) - float(a.monto_pagado or 0), 2)}
            for a in adeudos],
    }


@router.get("/pestana-roja")
def pestana_por_cobrar(mes: int, anio: int,
                       u: Usuario = Depends(requiere_rol(*ROLES_PAO)),
                       db: Session = Depends(get_db)):
    """Pestaña Roja: saldos pendientes con estado del switch de automatizaciones."""
    filas = (db.query(HonorarioCobranza)
             .filter_by(mes=mes, anio=anio)
             .filter(HonorarioCobranza.estatus_pago.in_(
                 [EstatusPago.PENDIENTE, EstatusPago.POR_CONFIRMAR])).all())
    return [{
        "honorario_id": h.id,
        "cliente_id": h.cliente_id,
        "cliente": h.cliente.nombre_comercial,
        "monto": h.monto_honorario,
        "estatus": h.estatus_pago.value,
        "dias_vencido": h.dias_vencido,
        "automatizaciones_activas": h.cliente.automatizaciones_activas,
        "tipo_cliente": h.cliente.tipo_cliente.value,
        "comprobante_pendiente_validar": h.estatus_pago == EstatusPago.POR_CONFIRMAR,
    } for h in filas]


@router.get("/pestana-amarilla")
def pestana_efectivo(mes: int, anio: int,
                     u: Usuario = Depends(requiere_rol(*ROLES_PAO)),
                     db: Session = Depends(get_db)):
    """Pestaña Amarilla: pagos en efectivo en camino, con folio y recolección."""
    filas = (db.query(HonorarioCobranza)
             .filter_by(mes=mes, anio=anio, estatus_pago=EstatusPago.EN_EFECTIVO).all())
    return [{
        "honorario_id": h.id,
        "cliente": h.cliente.nombre_comercial,
        "monto": h.monto_honorario,
        "folio_recepcion": h.folio_recepcion_efectivo,
        "referencia_oxxo": h.referencia_oxxo,
        "estatus_recoleccion": h.estatus_recoleccion,
    } for h in filas]


@router.get("/pestana-verde")
def pestana_pagado(mes: int, anio: int,
                   u: Usuario = Depends(requiere_rol(*ROLES_PAO)),
                   db: Session = Depends(get_db)):
    """Pestaña Verde: historial de cobros conciliados del mes."""
    filas = (db.query(HonorarioCobranza)
             .filter_by(mes=mes, anio=anio, estatus_pago=EstatusPago.PAGADO).all())
    return [{
        "cliente": h.cliente.nombre_comercial,
        "monto": h.monto_honorario,
        "fecha_pago": h.fecha_pago,
    } for h in filas]


# ---------------------------------------------------------------------------
# ACCIONES DE UN BOTÓN
# ---------------------------------------------------------------------------

@router.post("/{honorario_id}/confirmar-pago")
def confirmar_pago(honorario_id: int, request: Request,
                   u: Usuario = Depends(requiere_rol(*ROLES_PAO)),
                   db: Session = Depends(get_db)):
    """Botón verde grande: Pao confirma el pago (transferencia, ticket o sobre)."""
    h = db.query(HonorarioCobranza).get(honorario_id)
    if not h:
        raise HTTPException(404, "Honorario no encontrado")
    estatus_anterior = h.estatus_pago.value
    h.estatus_pago = EstatusPago.PAGADO
    h.fecha_pago = datetime.utcnow()
    whatsapp.registrar_evento_bitacora(h, "pago_confirmado", confirmado_por=u.nombre)
    auditoria.registrar(db, usuario_id=u.id, accion="modificacion_saldo",
                        tabla_afectada="honorarios_cobranza", registro_id=h.id,
                        request=request, cambio=f"{estatus_anterior} -> pagado",
                        monto=h.monto_honorario,
                        cliente=h.cliente.nombre_comercial)
    db.commit()
    return {"ok": True, "mensaje": f"Pago de {h.cliente.nombre_comercial} confirmado ✓"}


@router.post("/cliente/{cliente_id}/switch-automatizaciones")
def switch_automatizaciones(cliente_id: int, activar: bool, request: Request,
                            u: Usuario = Depends(requiere_rol(*ROLES_PAO)),
                            db: Session = Depends(get_db)):
    """Switch manual de la pestaña roja: apaga/enciende recordatorios y llamadas IA."""
    c = db.query(Cliente).get(cliente_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    c.automatizaciones_activas = activar
    auditoria.registrar(db, usuario_id=u.id, accion="switch_automatizaciones",
                        tabla_afectada="clientes", registro_id=c.id,
                        request=request, nuevo_estado=activar,
                        cliente=c.nombre_comercial)
    db.commit()
    return {"ok": True, "automatizaciones_activas": c.automatizaciones_activas}


# ---------------------------------------------------------------------------
# MÓDULO 5: SUB-FLUJO DE EFECTIVO
# ---------------------------------------------------------------------------

@router.post("/{honorario_id}/activar-efectivo-oxxo")
def opcion_a_oxxo(honorario_id: int, request: Request,
                  u: Usuario = Depends(requiere_rol(*ROLES_PAO)),
                  db: Session = Depends(get_db)):
    """
    Opción A: genera referencia OXXO Pay / corresponsal y la envía por WhatsApp.
    (En producción: integrar API de OXXO Pay / Conekta / STP para la referencia real.)
    """
    h = db.query(HonorarioCobranza).get(honorario_id)
    if not h:
        raise HTTPException(404, "Honorario no encontrado")

    h.estatus_pago = EstatusPago.EN_EFECTIVO
    h.referencia_oxxo = f"9300{random.randint(10**9, 10**10 - 1)}"  # simulada

    mensaje = whatsapp.plantilla_referencia_oxxo(h.cliente.nombre_comercial, h.referencia_oxxo)
    whatsapp._enviar(h.cliente.telefono_whatsapp, mensaje)
    whatsapp.registrar_evento_bitacora(h, "referencia_oxxo_enviada",
                                       referencia=h.referencia_oxxo)
    auditoria.registrar(db, usuario_id=u.id, accion="activacion_flujo_efectivo",
                        tabla_afectada="honorarios_cobranza", registro_id=h.id,
                        request=request, via="oxxo",
                        referencia=h.referencia_oxxo)
    db.commit()
    return {"ok": True, "referencia": h.referencia_oxxo}


@router.post("/{honorario_id}/solicitar-recoleccion")
def opcion_b_recoleccion(honorario_id: int, request: Request,
                         u: Usuario = Depends(requiere_rol(*ROLES_PAO)),
                         db: Session = Depends(get_db)):
    """
    Opción B: botón "Solicitar Recolección". Genera folio único, avisa al
    cliente y dispara la alerta a la mensajería de confianza — la secretaria
    nunca sale de la oficina a recoger efectivo.
    """
    h = db.query(HonorarioCobranza).get(honorario_id)
    if not h:
        raise HTTPException(404, "Honorario no encontrado")

    ultimo = db.query(HonorarioCobranza).filter(
        HonorarioCobranza.folio_recepcion_efectivo.isnot(None)).count()
    h.folio_recepcion_efectivo = f"PA-{1000 + ultimo + 1}"
    h.estatus_pago = EstatusPago.EN_EFECTIVO
    h.estatus_recoleccion = "solicitada"

    whatsapp._enviar(h.cliente.telefono_whatsapp,
                     whatsapp.plantilla_folio_recoleccion(h.folio_recepcion_efectivo))
    whatsapp.registrar_evento_bitacora(h, "recoleccion_solicitada",
                                       folio=h.folio_recepcion_efectivo)
    auditoria.registrar(db, usuario_id=u.id, accion="solicitud_recoleccion",
                        tabla_afectada="honorarios_cobranza", registro_id=h.id,
                        request=request, folio=h.folio_recepcion_efectivo)
    # TODO producción: POST a API de mensajería/delivery de confianza con
    # dirección del cliente y folio.
    db.commit()
    return {"ok": True, "folio": h.folio_recepcion_efectivo}
