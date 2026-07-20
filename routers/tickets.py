# -*- coding: utf-8 -*-
"""Tickets del Buzón de Solicitudes: lista de trabajo del equipo y cierre con aviso."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from models.models import EstatusTicket, TicketTramite, Usuario
from services import auditoria, whatsapp
from services.auth import solo_equipo_contable

router = APIRouter(prefix="/api/tickets", tags=["Tickets (Equipo)"])


@router.get("")
def listar_tickets(u: Usuario = Depends(solo_equipo_contable),
                   db: Session = Depends(get_db)):
    tickets = (db.query(TicketTramite)
               .filter(TicketTramite.estatus != EstatusTicket.CERRADO)
               .order_by(TicketTramite.timestamp_creado.asc()).all())
    return [{"id": t.id, "cliente": t.cliente.nombre_comercial,
             "tipo_tramite": t.tipo_tramite, "descripcion": t.descripcion,
             "estatus": t.estatus.value, "creado": t.timestamp_creado}
            for t in tickets]


@router.post("/{ticket_id}/cerrar")
def cerrar_ticket(ticket_id: int, request: Request,
                  u: Usuario = Depends(solo_equipo_contable),
                  db: Session = Depends(get_db)):
    """Cierra el trámite y Regina avisa al cliente por WhatsApp."""
    t = db.get(TicketTramite, ticket_id)
    if not t:
        raise HTTPException(404, "Ticket no encontrado")
    t.estatus = EstatusTicket.CERRADO
    t.timestamp_cerrado = datetime.utcnow()
    t.asignado_a = u.id
    whatsapp._enviar(t.cliente.telefono_whatsapp,
                     f"Hola {t.cliente.nombre_comercial}, le informa Regina de P&A: "
                     f"su trámite \"{t.tipo_tramite}\" quedó listo. Ya puede "
                     f"consultarlo en su portal. ¡Buen día!")
    auditoria.registrar(db, usuario_id=u.id, accion="cierre_ticket",
                        tabla_afectada="tickets_tramites", registro_id=t.id,
                        request=request, tipo=t.tipo_tramite)
    db.commit()
    return {"ok": True}
