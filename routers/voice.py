# -*- coding: utf-8 -*-
"""
ENDPOINTS DEL CANAL DE VOZ (Sofía) — /api/voice/*
=================================================
Los consume el orquestador telefónico (Vapi / Retell AI) DURANTE la llamada,
por eso están optimizados para latencia mínima (ver services/voice.py).

SEGURIDAD: server-to-server. Toda petición debe traer el header
    X-Voice-Api-Key: <VOICE_WEBHOOK_API_KEY del .env>
Sin llave configurada o incorrecta -> 401 sin filtrar información.
Cada identificación por Caller ID queda en la bitácora de auditoría.
"""
import hmac
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

import config
from database import get_db
from services import auditoria, voice

router = APIRouter(prefix="/api/voice", tags=["Voz (Sofía / orquestador)"])


def _validar_llave(x_voice_api_key: str = Header(default="")):
    """Dependencia de autenticación del orquestador (comparación en tiempo constante)."""
    llave = config.VOICE_WEBHOOK_API_KEY
    if not llave or not hmac.compare_digest(x_voice_api_key, llave):
        raise HTTPException(401, "Llave de voz inválida")
    return True


class PeticionCallerId(BaseModel):
    telefono: str


@router.post("/caller-id")
def caller_id(payload: PeticionCallerId, request: Request,
              _: bool = Depends(_validar_llave),
              db: Session = Depends(get_db)):
    """
    Identifica al cliente por su número entrante y retorna los datos
    dinámicos para el saludo y contexto de Sofía: nombre, título, monto SAT
    del mes, honorarios y banderas de la Regla de Oro.
    """
    resultado = voice.buscar_por_caller_id(db, payload.telefono)
    if resultado["estatus"] == "identificado":
        auditoria.registrar(db, usuario_id=None, accion="voz_caller_id",
                            tabla_afectada="clientes",
                            registro_id=resultado["cliente_id"],
                            request=request, canal="telefono")
        db.commit()
    return resultado


class PeticionActualizarContacto(BaseModel):
    telefono: str
    nuevo_nombre: str


@router.post("/update-contact")
def update_contact(payload: PeticionActualizarContacto, request: Request,
                   _: bool = Depends(_validar_llave),
                   db: Session = Depends(get_db)):
    """
    El titular avisó que ese número lo atiende habitualmente otra persona:
    guarda `nombre_alternativo_telefono` y marca `numero_compartido = True`.
    """
    resultado = voice.registrar_contacto_alternativo(
        db, payload.telefono, payload.nuevo_nombre)
    if resultado["estatus"] == "actualizado":
        auditoria.registrar(db, usuario_id=None, accion="voz_contacto_alternativo",
                            tabla_afectada="clientes",
                            registro_id=resultado["cliente_id"],
                            request=request,
                            nombre=resultado["nombre_alternativo"])
        db.commit()
    return resultado


class PeticionAgendarCita(BaseModel):
    cliente_id: int
    fecha_hora: datetime
    motivo: str | None = None
    con_usuario_id: int | None = None  # opcional; por omisión su contador(a)


@router.post("/book-appointment")
def book_appointment(payload: PeticionAgendarCita, request: Request,
                     _: bool = Depends(_validar_llave),
                     db: Session = Depends(get_db)):
    """
    Agenda la cita EN VIVO durante la llamada: verifica disponibilidad y la
    registra CONFIRMADA en la misma agenda que gestiona Pao y que el
    personal ve en su panel. Si el horario está ocupado, retorna 'ocupado'
    para que Sofía proponga otro sin colgar.
    """
    resultado = voice.agendar_cita_por_voz(
        db, payload.cliente_id, payload.fecha_hora,
        payload.motivo, payload.con_usuario_id)
    if resultado["estatus"] == "confirmada":
        auditoria.registrar(db, usuario_id=None, accion="voz_cita_agendada",
                            tabla_afectada="citas",
                            registro_id=resultado["cita_id"],
                            request=request, canal="telefono")
        db.commit()
    return resultado
