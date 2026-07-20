# -*- coding: utf-8 -*-
"""
MÓDULO 6: Asistente telefónico con IA de voz (arquitectura Vapi / Retell AI).
Incluye el Prompt de Identidad del agente "Regina" y el disparador de
llamadas salientes a clientes rezagados, SIEMPRE filtrado por la Regla de Oro.
"""
import logging
from sqlalchemy.orm import Session

import config
from models.models import EstatusPago, HonorarioCobranza
from services.reglas_negocio import puede_automatizar_cobranza
from services import whatsapp

logger = logging.getLogger("regina.voz")

# ---------------------------------------------------------------------------
# PROMPT DE IDENTIDAD DEL AGENTE (se configura en Vapi/Retell)
# ---------------------------------------------------------------------------

PROMPT_IDENTIDAD_REGINA = """
Eres Regina, la Asistente Digital del despacho contable P&A.

IDENTIDAD Y VOZ:
- Voz femenina, pausada, profesional, con calidez regional norteña: amable
  pero firme. Usas cortesías naturales ("don", "con gusto", "para servirle").
- Te presentas SIEMPRE como asistente digital de P&A. Nunca finges ser una
  persona real ni la secretaria del despacho. Si te preguntan si eres robot,
  lo confirmas con naturalidad y sigues ayudando.
- PROHIBIDO imitar o clonar la voz de personal real del despacho.

OBJETIVO DE LA LLAMADA:
- Recordar con cortesía la fecha de vencimiento del impuesto ante el SAT
  ("Le recuerdo que su IVA vence mañana, don {nombre}, para evitar recargos").
- De forma secundaria y sutil, mencionar el saldo de honorarios pendiente y
  ofrecer facilidades de pago.

MANEJO DE OBJECIONES:
- Si el cliente dice estar en el rancho, sin señal, o pide pagar en efectivo:
  empatiza con buen humor y canaliza a la referencia OXXO:
  "No se preocupe por dar la vuelta, don {nombre}, saliendo del rancho le
  dejo el código OXXO en su WhatsApp, le queda más rápido. ¿Le parece bien?"
- Si el cliente pide hablar con una persona, agenda el pendiente y despídete
  cordialmente; NUNCA presiones ni discutas.
- Si el cliente hace plática personal, responde breve y amable sin inventar
  recuerdos ni información del despacho.

AL FINALIZAR:
- Resume el acuerdo alcanzado y confirma el siguiente paso.
- El sistema enviará tu resumen al panel de la secretaria.
"""


def disparar_llamadas_rezagados(db: Session, mes: int, anio: int) -> dict:
    """
    Recorre honorarios pendientes del periodo y agenda llamadas de Regina
    SOLO para clientes donde la Regla de Oro lo permite.
    """
    pendientes = (db.query(HonorarioCobranza)
                  .filter_by(mes=mes, anio=anio, estatus_pago=EstatusPago.PENDIENTE)
                  .all())

    agendadas, omitidas = [], []
    for h in pendientes:
        # --- REGLA DE ORO: MODO HUMANO PRIMERO ---
        if not puede_automatizar_cobranza(h.cliente):
            omitidas.append(h.cliente.nombre_comercial)
            continue
        if h.dias_vencido <= 0:
            continue  # solo rezagados

        _agendar_llamada(h)
        whatsapp.registrar_evento_bitacora(h, "llamada_ia_agendada")
        agendadas.append(h.cliente.nombre_comercial)

    db.commit()
    return {"agendadas": agendadas, "omitidas_por_regla_de_oro": omitidas}


def _agendar_llamada(h: HonorarioCobranza):
    """POST saliente a la plataforma de voz. Simulado en desarrollo."""
    if config.VOZ_PROVIDER == "simulado":
        logger.info("[SIMULADO] Llamada Regina -> %s (%s) | saldo $%.2f",
                    h.cliente.nombre_comercial, h.cliente.telefono_whatsapp,
                    h.monto_honorario)
        return
    # Producción (ejemplo Vapi):
    # requests.post("https://api.vapi.ai/call", headers={...}, json={
    #     "assistantId": config.VOZ_AGENT_ID,
    #     "customer": {"number": h.cliente.telefono_whatsapp},
    #     "assistantOverrides": {"variableValues": {
    #         "nombre": h.cliente.nombre_comercial,
    #         "monto": h.monto_honorario,
    #         "vence": str(h.fecha_limite_pago)}},
    # })
