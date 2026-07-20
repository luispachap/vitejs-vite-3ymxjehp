# -*- coding: utf-8 -*-
"""
SITUACIONES DEL CLIENTE — el semáforo lo pone una PERSONA
==========================================================
El sistema no puede adivinar un requerimiento del SAT ni una auditoría: eso
lo sabe el contador o el supervisor. Antes el semáforo rojo dependía de un
booleano suelto (`requerimiento_urgente`) que nadie tenía cómo activar.

Criterio del despacho (decisión del Director, documentada a propósito):
  - El semáforo sirve para lo COTIDIANO: una línea de captura por pagar,
    honorarios pendientes. Eso sí se muestra.
  - Los asuntos GRAVES (requerimientos, auditorías, discrepancias) se avisan
    HABLANDO, no con un foquito rojo que asuste al cliente. Por eso cada
    situación se registra con dos textos: el `detalle_interno` (solo equipo)
    y un `mensaje_al_cliente` OPCIONAL. Si `visible_para_cliente` es falso,
    el cliente no ve nada: el despacho decide cuándo y cómo se lo dice.
  - Quién puede marcar visible algo ROJO: supervisor, director o admin.
    El contador puede registrar la situación y proponerla, pero no
    "encender" el rojo del portal por su cuenta.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.models import Cliente, RolUsuario, SituacionCliente, Usuario
from services import auditoria
from services.auth import solo_equipo_contable

router = APIRouter(prefix="/api/situaciones", tags=["Situaciones del cliente"])

TIPOS = ("requerimiento", "auditoria", "aclaracion", "discrepancia", "otro")
SEVERIDADES = ("roja", "ambar", "informativa")
ROLES_QUE_ENCIENDEN_ROJO = (RolUsuario.SUPERVISOR, RolUsuario.DIRECTOR,
                            RolUsuario.ADMINISTRADOR)


def _serializar(s: SituacionCliente, para_cliente: bool = False) -> dict:
    base = {"id": s.id, "cliente_id": s.cliente_id,
            "tipo": s.tipo, "severidad": s.severidad, "titulo": s.titulo,
            "abierta": s.abierta,
            "visible_para_cliente": s.visible_para_cliente,
            "mensaje_al_cliente": s.mensaje_al_cliente,
            "creada_en": s.creada_en.isoformat() if s.creada_en else None}
    if para_cliente:
        # El cliente JAMÁS ve el detalle interno ni quién lo escribió.
        return {k: base[k] for k in ("id", "tipo", "severidad", "titulo",
                                     "mensaje_al_cliente", "creada_en")}
    base.update({
        "cliente": s.cliente.nombre_comercial if s.cliente else None,
        "detalle_interno": s.detalle_interno,
        "creada_por": s.creada_por.nombre if s.creada_por else None,
        "cerrada_por": s.cerrada_por.nombre if s.cerrada_por else None,
        "cerrada_en": s.cerrada_en.isoformat() if s.cerrada_en else None})
    return base


class NuevaSituacion(BaseModel):
    cliente_id: int
    tipo: str = "requerimiento"
    severidad: str = "ambar"
    titulo: str
    detalle_interno: str | None = None
    mensaje_al_cliente: str | None = None
    visible_para_cliente: bool = False


@router.get("")
def listar(cliente_id: int | None = None, abiertas: bool = True,
           u: Usuario = Depends(solo_equipo_contable),
           db: Session = Depends(get_db)):
    q = db.query(SituacionCliente)
    if cliente_id:
        q = q.filter_by(cliente_id=cliente_id)
    if abiertas:
        q = q.filter_by(abierta=True)
    return [_serializar(s)
            for s in q.order_by(SituacionCliente.id.desc()).limit(120).all()]


@router.post("")
def registrar(payload: NuevaSituacion, request: Request,
              u: Usuario = Depends(solo_equipo_contable),
              db: Session = Depends(get_db)):
    if payload.tipo not in TIPOS:
        raise HTTPException(400, f"Tipo no válido. Use: {', '.join(TIPOS)}")
    if payload.severidad not in SEVERIDADES:
        raise HTTPException(400, "Severidad no válida (roja, ambar o informativa)")
    if not db.query(Cliente).get(payload.cliente_id):
        raise HTTPException(404, "Cliente no encontrado")
    if not payload.titulo.strip():
        raise HTTPException(400, "Escriba un título para la situación")

    visible = payload.visible_para_cliente
    aviso = None
    if visible and payload.severidad == "roja" and u.rol not in ROLES_QUE_ENCIENDEN_ROJO:
        # El contador registra, pero encender el rojo del portal del cliente
        # es decisión de la Supervisora o el Director.
        visible = False
        aviso = ("Registrada, pero NO se encendió el semáforo rojo del "
                 "cliente: eso lo autoriza la Supervisora o el Director. "
                 "Ellos la verán en su tablero.")
    if visible and not (payload.mensaje_al_cliente or "").strip():
        raise HTTPException(400, "Si el cliente va a verlo, escriba el mensaje "
                                 "que leerá (con sus palabras, sin tecnicismos)")

    s = SituacionCliente(
        cliente_id=payload.cliente_id, tipo=payload.tipo,
        severidad=payload.severidad, titulo=payload.titulo.strip()[:160],
        detalle_interno=(payload.detalle_interno or "").strip()[:600] or None,
        mensaje_al_cliente=(payload.mensaje_al_cliente or "").strip()[:400] or None,
        visible_para_cliente=visible, creada_por_id=u.id)
    db.add(s)
    db.flush()
    auditoria.registrar(db, usuario_id=u.id, accion="situacion_registrada",
                        tabla_afectada="situaciones_cliente", registro_id=s.id,
                        request=request, tipo=s.tipo, severidad=s.severidad,
                        visible_cliente=visible)
    db.commit()
    return {"ok": True, "situacion": _serializar(s), "aviso": aviso}


class CambioVisibilidad(BaseModel):
    visible_para_cliente: bool
    mensaje_al_cliente: str | None = None


@router.post("/{situacion_id}/visibilidad")
def cambiar_visibilidad(situacion_id: int, payload: CambioVisibilidad,
                        request: Request,
                        u: Usuario = Depends(solo_equipo_contable),
                        db: Session = Depends(get_db)):
    """Encender o apagar lo que el cliente ve. Solo mandos."""
    if u.rol not in ROLES_QUE_ENCIENDEN_ROJO:
        raise HTTPException(403, "Mostrar u ocultar una situación al cliente "
                                 "lo decide la Supervisora o el Director")
    s = db.query(SituacionCliente).get(situacion_id)
    if not s:
        raise HTTPException(404, "Situación no encontrada")
    if payload.mensaje_al_cliente is not None:
        s.mensaje_al_cliente = payload.mensaje_al_cliente.strip()[:400] or None
    if payload.visible_para_cliente and not s.mensaje_al_cliente:
        raise HTTPException(400, "Escriba primero el mensaje que leerá el cliente")
    s.visible_para_cliente = payload.visible_para_cliente
    auditoria.registrar(db, usuario_id=u.id, accion="situacion_visibilidad",
                        tabla_afectada="situaciones_cliente", registro_id=s.id,
                        request=request, visible=s.visible_para_cliente)
    db.commit()
    return _serializar(s)


@router.post("/{situacion_id}/cerrar")
def cerrar(situacion_id: int, request: Request,
           u: Usuario = Depends(solo_equipo_contable),
           db: Session = Depends(get_db)):
    s = db.query(SituacionCliente).get(situacion_id)
    if not s:
        raise HTTPException(404, "Situación no encontrada")
    s.abierta = False
    s.visible_para_cliente = False
    s.cerrada_por_id = u.id
    s.cerrada_en = datetime.utcnow()
    auditoria.registrar(db, usuario_id=u.id, accion="situacion_cerrada",
                        tabla_afectada="situaciones_cliente", registro_id=s.id,
                        request=request, titulo=s.titulo)
    db.commit()
    return _serializar(s)


# ---------------------------------------------------------------------------
# Utilidad para el portal: qué situación manda en el semáforo del cliente
# ---------------------------------------------------------------------------
def situacion_dominante(db: Session, cliente_id: int):
    """La situación abierta VISIBLE más grave, o None."""
    abiertas = (db.query(SituacionCliente)
                .filter_by(cliente_id=cliente_id, abierta=True,
                           visible_para_cliente=True).all())
    if not abiertas:
        return None
    orden = {"roja": 0, "ambar": 1, "informativa": 2}
    return sorted(abiertas, key=lambda s: (orden.get(s.severidad, 9), -s.id))[0]
