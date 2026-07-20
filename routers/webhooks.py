# -*- coding: utf-8 -*-
"""
MÓDULOS 4 y 6: Webhooks entrantes.
- /whatsapp/estatus : entregado / leído (bitácora de deslinde legal)
- /whatsapp/entrante: triage de respuestas (comprobantes, texto)
- /voz/post-llamada : JSON de la plataforma de voz (Vapi/Retell) -> tarjetita
                      de notas para el panel de Pao.
"""
import os
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

import config
from database import get_db
from models.models import Cliente, EstatusPago, HonorarioCobranza
from services import almacenamiento, whatsapp

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks (WhatsApp / Voz)"])


def _honorario_pendiente_por_telefono(db: Session, telefono: str):
    cliente = (db.query(Cliente)
               .filter(Cliente.telefono_whatsapp == telefono).first())
    if not cliente:
        return None, None
    h = (db.query(HonorarioCobranza)
         .filter(HonorarioCobranza.cliente_id == cliente.id,
                 HonorarioCobranza.estatus_pago != EstatusPago.PAGADO)
         .order_by(HonorarioCobranza.anio.desc(), HonorarioCobranza.mes.desc())
         .first())
    return cliente, h


# ---------------------------------------------------------------------------
# ESTATUS DE ENTREGA (Twilio: MessageStatus | Meta: statuses[])
# ---------------------------------------------------------------------------

class WebhookEstatus(BaseModel):
    telefono: str          # número del cliente
    estatus: str           # delivered | read
    mensaje_sid: str | None = None


@router.post("/whatsapp/estatus")
def webhook_estatus(payload: WebhookEstatus, db: Session = Depends(get_db)):
    """Registra 'entregado'/'leído' en la bitácora cronológica del honorario."""
    _, h = _honorario_pendiente_por_telefono(db, payload.telefono)
    if not h:
        return {"ok": True, "detalle": "sin honorario activo asociado"}

    evento = "leido" if payload.estatus == "read" else "entregado"
    whatsapp.registrar_evento_bitacora(h, evento, proveedor_sid=payload.mensaje_sid)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# MENSAJES ENTRANTES (triage inteligente)
# ---------------------------------------------------------------------------

@router.post("/whatsapp/entrante")
async def webhook_entrante(
    telefono: str = Form(...),
    texto: str | None = Form(None),
    adjunto: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    """
    Triage:
    - Adjunto (foto/PDF) => se asume comprobante: se guarda en la carpeta del
      cliente y el honorario pasa a POR_CONFIRMAR (aparece en la pestaña roja
      de Pao con bandera de validación).
    - Texto => se registra en bitácora como respuesta del cliente.
    """
    cliente, h = _honorario_pendiente_por_telefono(db, telefono)
    if not cliente:
        return {"ok": True, "detalle": "número no registrado"}

    if adjunto is not None and h is not None:
        # SEGURIDAD: el comprobante va al almacenamiento cifrado.
        # Carpeta por id de cliente (nunca el RFC en la ruta).
        nombre = f"{h.anio}-{h.mes:02d}_{datetime.utcnow():%Y%m%d%H%M%S}_{adjunto.filename}"
        ruta = almacenamiento.guardar_documento(
            adjunto.file.read(), f"comprobantes/cliente{cliente.id}", nombre)

        h.ruta_comprobante = ruta
        h.estatus_pago = EstatusPago.POR_CONFIRMAR
        whatsapp.registrar_evento_bitacora(h, "comprobante_recibido", archivo=ruta)
        # TODO producción: pasar la imagen por OCR/visión para pre-validar
        # monto y referencia antes de notificar a Pao.
        db.commit()
        return {"ok": True, "accion": "comprobante_guardado_por_confirmar"}

    if texto and h is not None:
        whatsapp.registrar_evento_bitacora(h, "respuesta_cliente", texto=texto[:500])
        db.commit()
    return {"ok": True, "accion": "texto_registrado"}


# ---------------------------------------------------------------------------
# MÓDULO 6: POST-LLAMADA DE LA IA DE VOZ (Regina)
# ---------------------------------------------------------------------------

class WebhookPostLlamada(BaseModel):
    telefono: str
    estatus: str                    # completada | sin_respuesta | buzon
    resultado: str | None = None    # promesa_pago | pedira_efectivo | objecion | otro
    resumen: str | None = None      # resumen de texto formateado de la llamada
    duracion_segundos: int | None = None


@router.post("/voz/post-llamada")
def webhook_post_llamada(payload: WebhookPostLlamada, db: Session = Depends(get_db)):
    """
    Al colgar, la plataforma de voz envía este JSON. El resumen se inyecta a
    la bitácora y queda visible como tarjetita de notas en el panel de Pao,
    incluyendo cualquier comentario personal del cliente.
    """
    _, h = _honorario_pendiente_por_telefono(db, payload.telefono)
    if not h:
        return {"ok": True, "detalle": "sin honorario activo asociado"}

    whatsapp.registrar_evento_bitacora(
        h, "llamada_ia",
        estatus=payload.estatus,
        resultado=payload.resultado,
        resumen=payload.resumen,
        duracion_segundos=payload.duracion_segundos,
    )
    # Si el cliente pidió efectivo en la llamada, Regina ya canalizó a la
    # Opción A; aquí solo reflejamos la intención para la pestaña amarilla.
    if payload.resultado == "pedira_efectivo":
        h.estatus_pago = EstatusPago.EN_EFECTIVO
    db.commit()
    return {"ok": True}
