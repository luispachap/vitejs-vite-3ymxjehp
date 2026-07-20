# -*- coding: utf-8 -*-
"""
AGENDA DE ASESORÍAS (Citas)
===========================
Flujo:
1. El CLIENTE solicita desde su portal: elige con quién (el titular, su
   contador(a) asignado(a) u otro miembro del equipo contable), fecha
   deseada, modalidad y motivo. Queda SOLICITADA.
2. PAO gestiona: ve las solicitadas, ajusta fecha/hora si hace falta y
   CONFIRMA con un toque (o crea citas directas por teléfono).
3. Al confirmar: la persona con quien es la cita recibe CORREO y la ve en
   "Mis próximas citas" de su panel; el cliente recibe WhatsApp de Regina.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.models import (Cita, Cliente, EstatusCita, RolUsuario, Usuario)
from services import auditoria, correo, whatsapp
from services.auth import (cliente_autenticado, requiere_rol,
                           solo_secretaria_o_director, todo_el_personal,
                           usuario_actual)

router = APIRouter(prefix="/api/citas", tags=["Citas (Agenda)"])

ROLES_EQUIPO = (RolUsuario.DIRECTOR, RolUsuario.SUPERVISOR,
                RolUsuario.ADMIN_SECRETARIA, RolUsuario.CONTADOR)


def _formato(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y a las %H:%M")


def _serializar(c: Cita) -> dict:
    return {"id": c.id, "cliente": c.cliente.nombre_comercial,
            "cliente_id": c.cliente_id,
            "con": c.con_usuario.nombre, "con_usuario_id": c.con_usuario_id,
            "fecha_hora": c.fecha_hora, "duracion_minutos": c.duracion_minutos,
            "modalidad": c.modalidad, "motivo": c.motivo,
            "estatus": c.estatus.value, "notas_internas": c.notas_internas}


def _notificar_confirmacion(cita: Cita):
    """Aviso a AMBAS partes al confirmar."""
    whatsapp._enviar(
        cita.cliente.telefono_whatsapp,
        f"Hola {cita.cliente.nombre_comercial}, le confirma Regina de "
        f"Pacheco & Aparicio: su cita de asesoría con {cita.con_usuario.nombre} "
        f"quedó agendada para el {_formato(cita.fecha_hora)} "
        f"({cita.modalidad}). Si necesita moverla, respóndanos por aquí "
        f"con confianza. ¡Le esperamos!")
    correo.enviar_correo(
        cita.con_usuario.email,
        f"Cita confirmada: {cita.cliente.nombre_comercial} · {_formato(cita.fecha_hora)}",
        f"Se confirmó una cita de asesoría.\n\n"
        f"Cliente: {cita.cliente.nombre_comercial}\n"
        f"Fecha: {_formato(cita.fecha_hora)} ({cita.duracion_minutos} min)\n"
        f"Modalidad: {cita.modalidad}\n"
        f"Motivo: {cita.motivo or 'Sin especificar'}\n\n"
        f"También aparece en su panel del sistema.")


# ---------------------------------------------------------------------------
# PORTAL DEL CLIENTE
# ---------------------------------------------------------------------------

@router.get("/opciones")
def opciones_de_cita(cliente: Cliente = Depends(cliente_autenticado),
                     db: Session = Depends(get_db)):
    """
    Con quién puede agendar el cliente:
    el titular (Director), su contador(a) asignado(a) —destacado— y el
    resto del equipo contable.
    """
    opciones = []
    for u in (db.query(Usuario)
              .filter(Usuario.rol == RolUsuario.DIRECTOR, Usuario.activo).all()):
        opciones.append({"usuario_id": u.id, "nombre": u.nombre,
                         "etiqueta": "Titular del despacho"})
    if cliente.contador_asignado and cliente.contador_asignado.activo:
        opciones.append({"usuario_id": cliente.contador_asignado.id,
                         "nombre": cliente.contador_asignado.nombre,
                         "etiqueta": "Lleva su contabilidad"})
    for rol, etq in ((RolUsuario.SUPERVISOR, "Supervisora del despacho"),
                     (RolUsuario.CONTADOR, "Equipo contable")):
        for u in (db.query(Usuario)
                  .filter(Usuario.rol == rol, Usuario.activo).all()):
            if not any(o["usuario_id"] == u.id for o in opciones):
                opciones.append({"usuario_id": u.id, "nombre": u.nombre,
                                 "etiqueta": etq})
    return opciones


HORA_INICIO, HORA_FIN = 9, 18          # jornada del despacho
DURACION_MIN = 60


@router.get("/disponibilidad")
def disponibilidad(usuario_id: int, fecha: str,
                   cliente: Cliente = Depends(cliente_autenticado),
                   db: Session = Depends(get_db)):
    """
    Horarios libres de esa persona ese día (el cliente agenda VIENDO, no a
    ciegas). Jornada 9:00–18:00 en bloques de una hora; se descartan los ya
    tomados (solicitados o confirmados) y las horas ya pasadas de hoy.
    """
    from datetime import date as _date, time as _time, timedelta
    try:
        dia = _date.fromisoformat(fecha)
    except ValueError:
        raise HTTPException(400, "Fecha inválida (use AAAA-MM-DD)")
    if dia.weekday() >= 5:
        return {"fecha": fecha, "slots": [], "nota": "El despacho no atiende en fin de semana."}

    inicio = datetime.combine(dia, _time(HORA_INICIO))
    fin = datetime.combine(dia, _time(HORA_FIN))
    ocupadas = {c.fecha_hora.replace(minute=0, second=0, microsecond=0)
                for c in db.query(Cita)
                .filter(Cita.con_usuario_id == usuario_id,
                        Cita.estatus.in_([EstatusCita.SOLICITADA,
                                          EstatusCita.CONFIRMADA]),
                        Cita.fecha_hora >= inicio, Cita.fecha_hora < fin).all()}
    ahora = datetime.utcnow()
    slots = []
    h = inicio
    while h < fin:
        if h not in ocupadas and h > ahora:
            slots.append(h.strftime("%H:%M"))
        h += timedelta(minutes=DURACION_MIN)
    return {"fecha": fecha, "slots": slots}


class SolicitudCita(BaseModel):
    con_usuario_id: int
    fecha_hora: datetime
    modalidad: str = "presencial"
    motivo: str | None = None


@router.post("/solicitar")
def solicitar_cita(payload: SolicitudCita, request: Request,
                   cliente: Cliente = Depends(cliente_autenticado),
                   usuario: Usuario = Depends(usuario_actual),
                   db: Session = Depends(get_db)):
    destino = db.query(Usuario).get(payload.con_usuario_id)
    if not destino or destino.rol not in (RolUsuario.DIRECTOR, RolUsuario.SUPERVISOR,
                                          RolUsuario.CONTADOR):
        raise HTTPException(400, "Persona no válida para citas")
    if payload.fecha_hora <= datetime.utcnow():
        raise HTTPException(400, "La fecha debe ser futura")
    if payload.modalidad not in ("presencial", "videollamada", "llamada"):
        raise HTTPException(400, "Modalidad no válida")

    cita = Cita(cliente_id=cliente.id, con_usuario_id=destino.id,
                fecha_hora=payload.fecha_hora, modalidad=payload.modalidad,
                motivo=payload.motivo, creada_por_usuario_id=usuario.id)
    db.add(cita)
    db.flush()

    # Aviso inmediato a la persona destino; Pao la ve en su panel para confirmar
    correo.enviar_correo(
        destino.email,
        f"Solicitud de cita: {cliente.nombre_comercial}",
        f"{cliente.nombre_comercial} solicitó una asesoría con usted.\n\n"
        f"Fecha propuesta: {_formato(payload.fecha_hora)}\n"
        f"Modalidad: {payload.modalidad}\n"
        f"Motivo: {payload.motivo or 'Sin especificar'}\n\n"
        f"Pao la confirmará en el sistema.")
    auditoria.registrar(db, usuario_id=usuario.id, accion="solicitud_cita",
                        tabla_afectada="citas", registro_id=cita.id,
                        request=request, con=destino.nombre)
    db.commit()
    return {"ok": True, "cita_id": cita.id,
            "mensaje": f"Solicitud enviada. Le confirmaremos por WhatsApp "
                       f"su cita con {destino.nombre}."}


@router.get("/mis-citas")
def mis_citas_cliente(cliente: Cliente = Depends(cliente_autenticado),
                      db: Session = Depends(get_db)):
    citas = (db.query(Cita)
             .filter(Cita.cliente_id == cliente.id,
                     Cita.estatus != EstatusCita.CANCELADA,
                     Cita.fecha_hora >= datetime.utcnow())
             .order_by(Cita.fecha_hora.asc()).all())
    return [{"con": c.con_usuario.nombre, "fecha_hora": c.fecha_hora,
             "modalidad": c.modalidad, "estatus": c.estatus.value}
            for c in citas]


# ---------------------------------------------------------------------------
# GESTIÓN DE PAO (y Director)
# ---------------------------------------------------------------------------

@router.get("/clientes-agendables")
def clientes_agendables(u: Usuario = Depends(todo_el_personal),
                        db: Session = Depends(get_db)):
    """
    Lista mínima de clientes (id, nombre, régimen) para los selectores de
    TODO el personal: citas de Pao, calculadora del contador, certificados,
    respaldos. Antes era solo de Pao y eso tumbaba la calculadora (403).
    """
    return [{"cliente_id": c.id, "cliente": c.nombre_comercial,
             "regimen_fiscal": c.regimen_fiscal,
             "tipo_persona": c.tipo_persona}
            for c in db.query(Cliente)
                       .filter(Cliente.estatus == "activo")
                       .order_by(Cliente.nombre_comercial).all()]


@router.get("/equipo-agendable")
def equipo_agendable(u: Usuario = Depends(solo_secretaria_o_director),
                     db: Session = Depends(get_db)):
    """Personas con quienes se puede agendar: titular y equipo contable."""
    salida = []
    for rol, etiqueta in ((RolUsuario.DIRECTOR, "Titular del despacho"),
                          (RolUsuario.SUPERVISOR, "Supervisora del despacho"),
                          (RolUsuario.CONTADOR, "Equipo contable")):
        for p in db.query(Usuario).filter(Usuario.rol == rol, Usuario.activo).all():
            salida.append({"usuario_id": p.id, "nombre": p.nombre,
                           "etiqueta": etiqueta})
    return salida


@router.get("")
def listar_citas(u: Usuario = Depends(solo_secretaria_o_director),
                 db: Session = Depends(get_db)):
    """Solicitadas primero (requieren acción), luego próximas confirmadas."""
    citas = (db.query(Cita)
             .filter(Cita.estatus.in_([EstatusCita.SOLICITADA, EstatusCita.CONFIRMADA]),
                     Cita.fecha_hora >= datetime.utcnow())
             .order_by(Cita.fecha_hora.asc()).all())
    citas.sort(key=lambda c: c.estatus != EstatusCita.SOLICITADA)
    return [_serializar(c) for c in citas]


class CitaDirecta(BaseModel):
    cliente_id: int
    con_usuario_id: int
    fecha_hora: datetime
    modalidad: str = "presencial"
    motivo: str | None = None


@router.post("")
def crear_cita_directa(payload: CitaDirecta, request: Request,
                       u: Usuario = Depends(solo_secretaria_o_director),
                       db: Session = Depends(get_db)):
    """Pao agenda directo (el cliente llamó por teléfono): nace CONFIRMADA."""
    cliente = db.query(Cliente).get(payload.cliente_id)
    destino = db.query(Usuario).get(payload.con_usuario_id)
    if not cliente or not destino:
        raise HTTPException(404, "Cliente o persona no encontrados")

    cita = Cita(cliente_id=cliente.id, con_usuario_id=destino.id,
                fecha_hora=payload.fecha_hora, modalidad=payload.modalidad,
                motivo=payload.motivo, estatus=EstatusCita.CONFIRMADA,
                creada_por_usuario_id=u.id)
    db.add(cita)
    db.flush()
    _notificar_confirmacion(cita)
    whatsapp_ok = True
    auditoria.registrar(db, usuario_id=u.id, accion="cita_creada",
                        tabla_afectada="citas", registro_id=cita.id,
                        request=request, con=destino.nombre,
                        cliente=cliente.nombre_comercial)
    db.commit()
    return {"ok": whatsapp_ok, "cita_id": cita.id,
            "mensaje": f"Cita confirmada. Regina ya avisó a {cliente.nombre_comercial}."}


class ConfirmarCita(BaseModel):
    fecha_hora: datetime | None = None  # Pao puede ajustar el horario
    notas_internas: str | None = None


@router.post("/{cita_id}/confirmar")
def confirmar_cita(cita_id: int, payload: ConfirmarCita, request: Request,
                   u: Usuario = Depends(solo_secretaria_o_director),
                   db: Session = Depends(get_db)):
    cita = db.query(Cita).get(cita_id)
    if not cita:
        raise HTTPException(404, "Cita no encontrada")
    if payload.fecha_hora:
        cita.fecha_hora = payload.fecha_hora
    if payload.notas_internas:
        cita.notas_internas = payload.notas_internas
    cita.estatus = EstatusCita.CONFIRMADA
    _notificar_confirmacion(cita)
    auditoria.registrar(db, usuario_id=u.id, accion="cita_confirmada",
                        tabla_afectada="citas", registro_id=cita.id,
                        request=request)
    db.commit()
    return {"ok": True,
            "mensaje": f"Confirmada. Regina avisó a {cita.cliente.nombre_comercial} "
                       f"y {cita.con_usuario.nombre} recibió el aviso."}


@router.post("/{cita_id}/cancelar")
def cancelar_cita(cita_id: int, request: Request,
                  u: Usuario = Depends(solo_secretaria_o_director),
                  db: Session = Depends(get_db)):
    cita = db.query(Cita).get(cita_id)
    if not cita:
        raise HTTPException(404, "Cita no encontrada")
    cita.estatus = EstatusCita.CANCELADA
    whatsapp._enviar(cita.cliente.telefono_whatsapp,
                     f"Hola {cita.cliente.nombre_comercial}, le informa Regina: "
                     f"su cita del {_formato(cita.fecha_hora)} con "
                     f"{cita.con_usuario.nombre} fue cancelada. Con gusto le "
                     f"buscamos otro horario cuando nos indique.")
    correo.enviar_correo(cita.con_usuario.email,
                         f"Cita cancelada: {cita.cliente.nombre_comercial}",
                         f"La cita del {_formato(cita.fecha_hora)} fue cancelada.")
    auditoria.registrar(db, usuario_id=u.id, accion="cita_cancelada",
                        tabla_afectada="citas", registro_id=cita.id,
                        request=request)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# AGENDA PERSONAL (contadores y director)
# ---------------------------------------------------------------------------

@router.get("/mias")
def mis_citas_staff(u: Usuario = Depends(requiere_rol(*ROLES_EQUIPO)),
                    db: Session = Depends(get_db)):
    """Las citas de la persona autenticada: lo que ve en 'Mis próximas citas'."""
    citas = (db.query(Cita)
             .filter(Cita.con_usuario_id == u.id,
                     Cita.estatus.in_([EstatusCita.SOLICITADA, EstatusCita.CONFIRMADA]),
                     Cita.fecha_hora >= datetime.utcnow())
             .order_by(Cita.fecha_hora.asc()).limit(10).all())
    return [_serializar(c) for c in citas]
