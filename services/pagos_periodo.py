# -*- coding: utf-8 -*-
"""
PAGOS DEL PERIODO Y COBRO DE HONORARIOS
=======================================
Regla implementada (esquema recomendado y confirmable con el Director):

1. CADA PAGO SE INFORMA INDIVIDUALMENTE al presentarse (SAT, IMSS, ISN),
   para que el cliente tenga el máximo de días para pagar cada uno.
2. El ESTADO DE CUENTA DE HONORARIOS se envía UNA sola vez: cuando se
   completa la ÚLTIMA obligación habilitada del cliente en el periodo
   (SAT siempre; IMSS solo si tiene_imss; ISN solo si tiene_nomina).

Los mensajes salen por la asistente (Regina en WhatsApp hoy; la voz de
Sofía usa estos mismos datos), siempre respetando la Regla de Oro.
"""
from sqlalchemy.orm import Session

from models.models import (Cliente, HonorarioCobranza, ObligacionMensual,
                           PagoIMSS, PagoISN)
from services import whatsapp
from services.reglas_negocio import puede_automatizar_cobranza


def estado_obligaciones(db: Session, cliente: Cliente, mes: int, anio: int) -> dict:
    """Estatus de las tres obligaciones del periodo (solo las habilitadas)."""
    obligacion = (db.query(ObligacionMensual)
                  .filter_by(cliente_id=cliente.id, mes=mes, anio=anio).first())
    estado = {"sat": bool(obligacion and obligacion.ruta_archivo_linea_captura)}
    if cliente.tiene_imss:
        pago = (db.query(PagoIMSS)
                .filter_by(cliente_id=cliente.id, mes=mes, anio=anio).first())
        estado["imss"] = bool(pago and pago.sipare_presentado
                              and pago.formato_pago_documento_id)
    if cliente.tiene_nomina:
        isn = (db.query(PagoISN)
               .filter_by(cliente_id=cliente.id, mes=mes, anio=anio).first())
        estado["isn"] = bool(isn and isn.documento_id)
    return estado


def periodo_completo(db: Session, cliente: Cliente, mes: int, anio: int) -> bool:
    return all(estado_obligaciones(db, cliente, mes, anio).values())


def notificar_honorarios_si_completo(db: Session, cliente: Cliente,
                                     mes: int, anio: int) -> bool:
    """
    Si TODAS las obligaciones habilitadas del periodo ya se presentaron,
    envía el estado de cuenta de honorarios (una sola vez). Respeta la
    Regla de Oro: clientes de trato especial jamás reciben cobro automático.
    """
    if not periodo_completo(db, cliente, mes, anio):
        return False
    if not puede_automatizar_cobranza(cliente):
        return False
    honorario = (db.query(HonorarioCobranza)
                 .filter_by(cliente_id=cliente.id, mes=mes, anio=anio).first())
    if not honorario or honorario.historial_notificaciones and any(
            e.get("evento") == "estado_cuenta_honorarios"
            for e in honorario.historial_notificaciones):
        return False

    whatsapp._enviar(
        cliente.telefono_whatsapp,
        f"Hola {cliente.nombre_comercial}, le saluda Regina de Pacheco & "
        f"Aparicio. Todas sus obligaciones del mes ya quedaron presentadas. "
        f"Le compartimos también su estado de cuenta de honorarios por "
        f"${honorario.monto_honorario:,.2f}, para cuando guste programar su "
        f"movimiento. ¡Gracias por su confianza!")
    whatsapp.registrar_evento_bitacora(honorario, "estado_cuenta_honorarios",
                                       disparado_por="cierre_de_periodo")
    return True
