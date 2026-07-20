# -*- coding: utf-8 -*-
"""
Link corto de confirmación del Esquema A: /c/{token}
El cliente toca el link del WhatsApp/correo y confirma que programará su
pago. No requiere login (el token de 64 hex ES la credencial de un solo
propósito) y solo puede cambiar UN honorario a POR_CONFIRMAR — nada más.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from database import get_db
from models.models import EstatusPago, HonorarioCobranza
from services import auditoria, whatsapp

router = APIRouter(tags=["Confirmación (link corto)"])


@router.get("/c/{token}", response_class=HTMLResponse)
def confirmar_pago_link(token: str, request: Request,
                        db: Session = Depends(get_db)):
    h = (db.query(HonorarioCobranza)
         .filter(HonorarioCobranza.token_confirmacion == token).first())
    if not h:
        raise HTTPException(404, "Link inválido o expirado")

    if h.estatus_pago == EstatusPago.PENDIENTE:
        h.confirmado_por_cliente_en = datetime.utcnow()
        whatsapp.registrar_evento_bitacora(h, "confirmacion_link",
                                           canal="link_corto")
        auditoria.registrar(db, usuario_id=None, accion="confirmacion_cliente_link",
                            tabla_afectada="honorarios_cobranza",
                            registro_id=h.id, request=request)
        db.commit()

    return f"""<html><body style="font-family:sans-serif;text-align:center;padding:3em">
    <h2>¡Gracias, {h.cliente.nombre_comercial}!</h2>
    <p>Hemos registrado su confirmación. Su asesor de P&A queda atento.</p>
    </body></html>"""
