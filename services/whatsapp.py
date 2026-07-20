# -*- coding: utf-8 -*-
"""
MÓDULO 4: Asistente Virtual de WhatsApp "Regina"
==================================================
Capa de abstracción sobre el proveedor de mensajería (Twilio / Meta Cloud API).
En modo 'simulado' imprime a consola y registra en la bitácora JSON, lo que
permite desarrollar todo el flujo localmente sin credenciales.
"""
import logging
from datetime import datetime

import config
from models.models import HonorarioCobranza

logger = logging.getLogger("regina.whatsapp")


# ---------------------------------------------------------------------------
# PLANTILLAS OFICIALES
# ---------------------------------------------------------------------------

def plantilla_entrega_impuesto(nombre_comercial: str, monto_honorario: float) -> str:
    """Mensaje de Entrega Transparente (se envía en cuanto el contador sube el PDF)."""
    return (
        f"Hola {nombre_comercial}, buenas tardes. Le comparto que ya quedó lista "
        f"su declaración de este mes. Aquí le dejo su formato oficial del SAT "
        f"para que pueda pagarlo con calma antes del vencimiento. Por separado, "
        f"le adjuntamos el estado de cuenta de sus honorarios del mes por "
        f"${monto_honorario:,.2f} por si gusta programar su movimiento. "
        f"¡Excelente semana!"
    )


def plantilla_entrega_solo_informativa(nombre_comercial: str) -> str:
    """Variante para clientes CONFIANZA_ESPECIAL: solo el SAT, sin mencionar honorarios."""
    return (
        f"Hola {nombre_comercial}, buenas tardes. Le comparto que ya quedó lista "
        f"su declaración de este mes. Aquí le dejo su formato oficial del SAT "
        f"para que pueda pagarlo con calma antes del vencimiento. ¡Excelente semana!"
    )


def plantilla_referencia_oxxo(nombre_comercial: str, referencia: str) -> str:
    return (
        f"Para su comodidad y seguridad, {nombre_comercial}, puede realizar el "
        f"depósito de sus honorarios con este código de barras en cualquier "
        f"OXXO comercial. Referencia: {referencia}"
    )


def plantilla_folio_recoleccion(folio: str) -> str:
    return (
        f"Su folio de recepción de efectivo es el #{folio}, favor de entregar "
        f"el sobre cerrado a mensajería. Le confirmaremos por este medio en "
        f"cuanto lo tengamos en oficina."
    )


# ---------------------------------------------------------------------------
# ENVÍO Y BITÁCORA
# ---------------------------------------------------------------------------

def _enviar(telefono: str, mensaje: str, adjunto_ruta: str | None = None) -> dict:
    """Punto único de salida hacia el proveedor. Retorna metadata del envío."""
    if config.WHATSAPP_PROVIDER == "twilio":
        # from twilio.rest import Client
        # client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        # msg = client.messages.create(from_=config.TWILIO_WHATSAPP_FROM,
        #                              to=f"whatsapp:{telefono}", body=mensaje,
        #                              media_url=[url_publica_del_adjunto])
        # return {"proveedor": "twilio", "sid": msg.sid}
        raise NotImplementedError("Configura credenciales de Twilio en .env")

    # Modo simulado (desarrollo local)
    logger.info("[SIMULADO] WhatsApp -> %s | adjunto=%s | %s", telefono, adjunto_ruta, mensaje)
    return {"proveedor": "simulado", "sid": f"SIM-{datetime.utcnow().timestamp()}"}


def registrar_evento_bitacora(honorario: HonorarioCobranza, evento: str, **detalle):
    """
    Agrega un evento a la bitácora cronológica de deslinde legal.
    Eventos típicos: enviado, entregado, leido, respuesta_cliente,
    llamada_ia, comprobante_recibido.
    """
    historial = list(honorario.historial_notificaciones or [])
    historial.append({
        "evento": evento,
        "ts": datetime.utcnow().isoformat() + "Z",
        **detalle,
    })
    honorario.historial_notificaciones = historial


def enviar_entrega_impuesto(cliente, honorario: HonorarioCobranza | None,
                            ruta_pdf: str, incluir_honorarios: bool) -> dict:
    """
    Envía la línea de captura del SAT vía Regina.
    `incluir_honorarios=False` para clientes Confianza_Especial / switch apagado.
    """
    if incluir_honorarios and honorario:
        mensaje = plantilla_entrega_impuesto(cliente.nombre_comercial, honorario.monto_honorario)
    else:
        mensaje = plantilla_entrega_solo_informativa(cliente.nombre_comercial)

    meta = _enviar(cliente.telefono_whatsapp, mensaje, adjunto_ruta=ruta_pdf)

    if honorario is not None:
        registrar_evento_bitacora(
            honorario, "enviado", canal="whatsapp",
            tipo="entrega_impuesto", incluyo_honorarios=incluir_honorarios,
            proveedor_sid=meta.get("sid"),
        )
    return meta
