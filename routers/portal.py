# -*- coding: utf-8 -*-
"""
MÓDULO 7: Portal VIP de clientes — BLINDADO.
- Aislamiento total: toda ruta usa `cliente_autenticado` (jamás un cliente_id
  manipulable). El rol CLIENTE solo existe en este router.
- Descargas: descifrado EN MEMORIA (services/cifrado) + log de auditoría.
- Accesos al dashboard quedan auditados con IP de origen.
"""
from fastapi import (APIRouter, Depends, File, Form, HTTPException,
                     Request, UploadFile)
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from datetime import datetime

from models.models import (CategoriaDocumento, Cliente, DocumentoClave,
                           ObligacionMensual, RolUsuario, TicketTramite,
                           Usuario)
from services.auth import cliente_autenticado, usuario_actual
import config
from services import almacenamiento, auditoria

router = APIRouter(prefix="/api/portal", tags=["Portal VIP (Clientes)"])


@router.get("/dashboard")
def dashboard(mes: int, anio: int, request: Request,
              cliente: Cliente = Depends(cliente_autenticado),
              usuario: Usuario = Depends(usuario_actual),
              db: Session = Depends(get_db)):
    """Semáforo SAT + progreso + desglose Chart.js. Acceso auditado."""
    from datetime import date as _date
    obligacion = (db.query(ObligacionMensual)
                  .filter_by(cliente_id=cliente.id, mes=mes, anio=anio).first())

    auditoria.registrar(db, usuario_id=usuario.id, accion="acceso_portal",
                        tabla_afectada="clientes", registro_id=cliente.id,
                        request=request, seccion="dashboard",
                        periodo=f"{anio}-{mes:02d}")
    db.commit()

    # SEMÁFORO FISCAL tri-estado:
    #  ROJO    = requerimiento urgente u Opinión 32D negativa
    #  AMARILLO= línea de captura del mes emitida y aún dentro del plazo de pago
    #  VERDE   = al corriente
    # EL SEMÁFORO LO PONE UNA PERSONA cuando se trata de algo serio.
    # El sistema solo sabe de lo cotidiano (una línea de captura por pagar);
    # un requerimiento o una auditoría los registra el contador o el
    # supervisor, y ELLOS deciden si el cliente debe verlo aquí o si es de
    # esas cosas que se avisan hablando. Ver routers/situaciones.py.
    from routers.situaciones import situacion_dominante
    situacion = situacion_dominante(db, cliente.id)
    ya_pagada = bool(obligacion and obligacion.pagado_en)

    if situacion and situacion.severidad == "roja":
        semaforo = {"estado": "rojo", "mensaje": situacion.mensaje_al_cliente,
                    "titulo": situacion.titulo}
    elif not cliente.opinion_32d_positiva:
        semaforo = {"estado": "rojo",
                    "mensaje": "Su opinión de cumplimiento salió negativa: "
                               "su contador ya está trabajando en ello."}
    elif situacion and situacion.severidad == "ambar":
        semaforo = {"estado": "amarillo", "mensaje": situacion.mensaje_al_cliente,
                    "titulo": situacion.titulo}
    elif (obligacion and obligacion.ruta_archivo_linea_captura and not ya_pagada
          and obligacion.fecha_vencimiento_sat
          and obligacion.fecha_vencimiento_sat >= _date.today()):
        semaforo = {"estado": "amarillo",
                    "mensaje": "Tiene una línea de captura vigente por pagar"}
    elif ya_pagada:
        semaforo = {"estado": "verde",
                    "mensaje": "Su pago del mes quedó registrado. Todo en orden."}
    else:
        semaforo = {"estado": "verde",
                    "mensaje": "Su empresa está al corriente con el SAT (Opinión 32D Positiva)"}

    progreso = {"pendiente": 10, "en_proceso": 55, "terminado": 100}
    estatus = obligacion.estatus_contabilidad.value if obligacion else "pendiente"

    # LOS TRES PAGOS DEL MES, a primera vista y con su descarga lista
    from models.models import PagoIMSS, PagoISN
    pagos = []
    if obligacion and obligacion.ruta_archivo_linea_captura:
        pagos.append({
            "concepto": "Impuestos federales (SAT)",
            "monto": obligacion.monto_impuesto_sat,
            "vence": (str(obligacion.fecha_vencimiento_sat)
                      if obligacion.fecha_vencimiento_sat else None),
            "descarga": f"/api/portal/linea-captura/{anio}/{mes}/descargar",
            "desglose": obligacion.desglose_impuestos,
            # Para que el cliente pueda comprobar que YA pagó
            "obligacion_id": obligacion.id,
            "pagado": bool(obligacion.pagado_en),
            "pagado_en": (obligacion.pagado_en.isoformat()
                          if obligacion.pagado_en else None),
            "referencia_pago": obligacion.referencia_pago,
            "es_complementaria": obligacion.es_complementaria,
            "numero_complementaria": obligacion.numero_complementaria})
    if cliente.tiene_imss:
        p = (db.query(PagoIMSS)
             .filter_by(cliente_id=cliente.id, mes=mes, anio=anio).first())
        if p and p.formato_pago_documento_id:
            pagos.append({
                "concepto": "Cuotas patronales (IMSS)",
                "monto": p.total_a_pagar, "vence": None,
                "descarga": f"/api/portal/boveda/{p.formato_pago_documento_id}/descargar",
                "desglose": p.desglose_cuotas})
    if cliente.tiene_nomina:
        i = (db.query(PagoISN)
             .filter_by(cliente_id=cliente.id, mes=mes, anio=anio).first())
        if i and i.documento_id:
            pagos.append({
                "concepto": "Impuesto sobre nómina (estatal)",
                "monto": i.importe, "vence": None,
                "descarga": f"/api/portal/boveda/{i.documento_id}/descargar",
                "desglose": None})

    # DESCARGAS FRECUENTES: lo que el cliente busca siempre
    def _ultimo(cat):
        d = (db.query(DocumentoClave)
             .filter_by(cliente_id=cliente.id, categoria=cat)
             .order_by(DocumentoClave.anio.desc(), DocumentoClave.mes.desc(),
                       DocumentoClave.id.desc()).first())
        return ({"documento_id": d.id, "periodo": f"{d.mes:02d}/{d.anio}"}
                if d else None)

    frecuentes = {
        "constancia_situacion_fiscal": _ultimo(CategoriaDocumento.CONSTANCIA_SITUACION_FISCAL),
        "opinion_32d": _ultimo(CategoriaDocumento.OPINION_32D),
        "estado_cuenta_honorarios": f"/api/portal/estado-cuenta/{anio}/{mes}/descargar",
    }

    return {
        "empresa": cliente.nombre_comercial,
        "semaforo_sat": semaforo,
        "progreso_contabilidad": {"estatus": estatus,
                                  "porcentaje": progreso.get(estatus, 0)},
        "desglose_impuestos": (obligacion.desglose_impuestos if obligacion else None),
        "monto_total_impuesto": (obligacion.monto_impuesto_sat if obligacion else None),
        "pagos_del_mes": pagos,
        "descargas_frecuentes": frecuentes,
        "contador_asignado": (cliente.contador_asignado.nombre
                              if cliente.contador_asignado else None),
    }


@router.post("/obligaciones/{obligacion_id}/comprobante-pago")
def cliente_sube_comprobante(obligacion_id: int, request: Request,
                             referencia: str = Form(None),
                             archivo_pdf: UploadFile = File(...),
                             cliente: Cliente = Depends(cliente_autenticado),
                             db: Session = Depends(get_db)):
    """
    El cliente comprueba que YA PAGÓ su línea de captura. Con esto el
    despacho deja de perseguir pagos ya hechos y el semáforo se pone verde.
    """
    from models.models import ObligacionMensual
    from routers.obligaciones import _guardar_comprobante
    o = (db.query(ObligacionMensual)
         .filter_by(id=obligacion_id, cliente_id=cliente.id).first())
    if not o:
        raise HTTPException(404, "No encontramos ese pago en su expediente")
    doc = _guardar_comprobante(db, o, archivo_pdf)
    o.comprobante_pago_documento_id = doc.id
    o.pagado_en = datetime.utcnow()
    o.pagado_registrado_por = "cliente"
    o.referencia_pago = (referencia or "").strip()[:60] or None
    auditoria.registrar(db, usuario_id=None, accion="comprobante_pago_cliente",
                        tabla_afectada="obligaciones_mensuales", registro_id=o.id,
                        request=request, documento_id=doc.id,
                        cliente=cliente.nombre_comercial)
    db.commit()
    return {"ok": True,
            "mensaje": "Recibimos su comprobante. Queda registrado en su "
                       "expediente y su contador ya lo ve."}


@router.get("/boveda")
def boveda_documentos(cliente: Cliente = Depends(cliente_autenticado),
                      db: Session = Depends(get_db)):
    """
    SIN PAJA: al cliente no le sirve ver el respaldo de CONTPAQ, la balanza
    ni la emisión del IDSE — eso es papel de trabajo del despacho, que se
    conserva siempre pero no se le enseña. Aquí solo van sus documentos
    útiles. Si algún cliente pide ver TODO, se le enciende el acceso
    ampliado (boveda_completa) desde Administración.
    """
    from routers.expediente import CATEGORIAS_DEL_CLIENTE, NOMBRES
    docs = (db.query(DocumentoClave)
            .filter_by(cliente_id=cliente.id)
            .order_by(DocumentoClave.anio.desc()).all())
    completo = bool(getattr(cliente, "boveda_completa", False))
    por_anio: dict[int, list] = {}
    for d in docs:
        if not completo and d.categoria not in CATEGORIAS_DEL_CLIENTE:
            continue
        por_anio.setdefault(d.anio, []).append(
            {"id": d.id, "categoria": d.categoria.value,
             "nombre": NOMBRES.get(d.categoria, d.categoria.value.replace("_", " ")),
             "mes": d.mes, "subido_en": d.subido_en})
    return por_anio


@router.get("/boveda/{documento_id}/descargar")
def descargar_documento(documento_id: int, request: Request,
                        cliente: Cliente = Depends(cliente_autenticado),
                        usuario: Usuario = Depends(usuario_actual),
                        db: Session = Depends(get_db)):
    """
    Descarga blindada:
    1. El filtro cliente_id=cliente.id garantiza que SOLO puede descargar
       documentos de SU empresa (un ID ajeno retorna 404, no 403, para no
       revelar existencia).
    2. El archivo se descifra en memoria y se sirve directo; nunca se
       escribe descifrado al disco.
    3. Queda registrado quién, qué documento, desde qué IP y a qué hora,
       ANTES de retornar la respuesta.
    """
    doc = (db.query(DocumentoClave)
           .filter_by(id=documento_id, cliente_id=cliente.id).first())
    if not doc:
        raise HTTPException(404, "Documento no encontrado")

    auditoria.registrar(db, usuario_id=usuario.id, accion="descarga_documento",
                        tabla_afectada="documentos_clave", registro_id=doc.id,
                        request=request, categoria=doc.categoria.value,
                        anio=doc.anio)
    db.commit()

    return almacenamiento.respuesta_archivo(doc.ruta_archivo)


@router.get("/linea-captura/{anio}/{mes}/descargar")
def descargar_linea_captura(anio: int, mes: int, request: Request,
                            cliente: Cliente = Depends(cliente_autenticado),
                            usuario: Usuario = Depends(usuario_actual),
                            db: Session = Depends(get_db)):
    """La línea de captura del SAT del periodo, descifrada al vuelo y auditada."""
    obligacion = (db.query(ObligacionMensual)
                  .filter_by(cliente_id=cliente.id, mes=mes, anio=anio).first())
    if not obligacion or not obligacion.ruta_archivo_linea_captura:
        raise HTTPException(404, "Aún no hay línea de captura para este periodo")

    ruta = obligacion.ruta_archivo_linea_captura
    auditoria.registrar(db, usuario_id=usuario.id,
                        accion="descarga_linea_captura",
                        tabla_afectada="obligaciones_mensuales",
                        registro_id=obligacion.id, request=request,
                        periodo=f"{anio}-{mes:02d}")
    db.commit()

    return almacenamiento.respuesta_archivo(ruta)


@router.get("/estado-cuenta/{anio}/{mes}/descargar")
def descargar_estado_cuenta(anio: int, mes: int, request: Request,
                            cliente: Cliente = Depends(cliente_autenticado),
                            usuario: Usuario = Depends(usuario_actual),
                            db: Session = Depends(get_db)):
    """Zona Express: estado de cuenta de honorarios del mes, PDF al vuelo."""
    import io as _io
    from models.models import HonorarioCobranza
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas as _canvas

    h = (db.query(HonorarioCobranza)
         .filter_by(cliente_id=cliente.id, mes=mes, anio=anio).first())
    if not h:
        raise HTTPException(404, "Aún no hay estado de cuenta para este periodo")

    buf = _io.BytesIO()
    c = _canvas.Canvas(buf, pagesize=letter)
    ancho, alto = letter
    azul = (10/255, 90/255, 160/255)

    c.setFillColorRGB(*azul)
    c.rect(0, alto-90, ancho, 90, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Times-Bold", 20)
    c.drawString(50, alto-50, "Pacheco & Aparicio")
    c.setFont("Times-Roman", 11)
    c.drawString(50, alto-70, "Consultoría Jurídica Fiscal · C.P. y Lic. Rodolfo Pacheco Ortega")

    c.setFillColorRGB(0.08, 0.11, 0.2)
    c.setFont("Times-Bold", 16)
    c.drawString(50, alto-140, "Estado de cuenta de honorarios")
    c.setFont("Times-Roman", 12)
    y = alto-180
    filas = [("Cliente", cliente.nombre_comercial),
             ("Razón social", cliente.razon_social),
             ("Periodo", f"{mes:02d}/{anio}"),
             ("Honorarios del mes", f"${h.monto_honorario:,.2f} MXN"),
             ("Estatus", h.estatus_pago.value.replace("_", " ").title()),
             ("Fecha límite de pago", str(h.fecha_limite_pago or "—"))]
    for etiqueta, valor in filas:
        c.setFont("Times-Bold", 12); c.drawString(50, y, etiqueta + ":")
        c.setFont("Times-Roman", 12); c.drawString(210, y, str(valor))
        y -= 24
    c.setFont("Times-Italic", 10)
    c.setFillColorRGB(0.4, 0.44, 0.52)
    c.drawString(50, 60, "Documento informativo generado por el portal seguro de P&A. "
                         "Cada descarga queda registrada.")
    c.save()

    auditoria.registrar(db, usuario_id=usuario.id, accion="descarga_estado_cuenta",
                        tabla_afectada="honorarios_cobranza", registro_id=h.id,
                        request=request, periodo=f"{anio}-{mes:02d}")
    db.commit()

    return Response(content=buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition":
                             f'attachment; filename="estado_cuenta_{anio}-{mes:02d}.pdf"'})


class SolicitudTramite(BaseModel):
    tipo_tramite: str
    descripcion: str | None = None


@router.post("/solicitar-tramite")
def solicitar_tramite(payload: SolicitudTramite, request: Request,
                      cliente: Cliente = Depends(cliente_autenticado),
                      usuario: Usuario = Depends(usuario_actual),
                      db: Session = Depends(get_db)):
    ticket = TicketTramite(cliente_id=cliente.id,
                           tipo_tramite=payload.tipo_tramite,
                           descripcion=payload.descripcion)
    db.add(ticket)
    db.flush()
    auditoria.registrar(db, usuario_id=usuario.id, accion="creacion_ticket",
                        tabla_afectada="tickets_tramites", registro_id=ticket.id,
                        request=request, tipo_tramite=payload.tipo_tramite)
    db.commit()
    return {"ok": True, "ticket_id": ticket.id,
            "mensaje": "Su solicitud fue registrada. Le avisaremos por WhatsApp."}


# ---------------------------------------------------------------------------
# AUTOREGISTRO: el cliente crea su propia contraseña desde el login
# ---------------------------------------------------------------------------
import hashlib
import secrets as _secrets
from datetime import timedelta

from pydantic import BaseModel as _BaseModel


def _hash_codigo(codigo: str) -> str:
    return hashlib.sha256(codigo.encode()).hexdigest()


def _buscar_cliente_por_contacto(db, contacto: str):
    from services.voice import _normalizar_telefono
    contacto = (contacto or "").strip()
    c = (db.query(Cliente)
         .filter(Cliente.email == contacto.lower()).first())
    if not c and any(ch.isdigit() for ch in contacto):
        c = (db.query(Cliente)
             .filter(Cliente.telefono_whatsapp == _normalizar_telefono(contacto))
             .first())
    return c


class SolicitudCodigo(_BaseModel):
    contacto: str  # correo o teléfono YA dados de alta en Administración


@router.post("/autoregistro/solicitar-codigo")
def autoregistro_solicitar_codigo(payload: SolicitudCodigo, request: Request,
                                  db: Session = Depends(get_db)):
    """
    Paso 1: el cliente escribe su correo o teléfono. Si está dado de alta y
    aún no tiene cuenta, Regina le manda un código de 6 dígitos por
    WhatsApp (15 min de vigencia). La respuesta es NEUTRA a propósito: no
    revela a extraños si un contacto existe o no en el despacho.
    """
    from services import whatsapp
    # ⚠ MIENTRAS NO HAYA CANAL REAL (WhatsApp Business API o correo SMTP),
    # el código NO puede llegarle al cliente: los envíos están simulados.
    # Por eso este flujo queda APAGADO y el portal indica al cliente que
    # pida su contraseña al despacho (el Director se la genera desde
    # Administración y se la entrega). Al conectar el canal, basta poner
    # AUTOREGISTRO_ACTIVO=true.
    import os
    if os.getenv("AUTOREGISTRO_ACTIVO", "false").lower() != "true":
        return {"ok": False, "canal_no_disponible": True, "mensaje":
                "Por ahora las contraseñas las entrega el despacho. "
                "Comuníquese con nosotros y con gusto le damos su acceso."}

    respuesta_neutra = {"ok": True, "mensaje":
                        "Si sus datos están registrados con el despacho, en un "
                        "momento recibirá un código por WhatsApp."}
    cliente = _buscar_cliente_por_contacto(db, payload.contacto)
    if not cliente or cliente.usuario_portal_id:
        return respuesta_neutra

    codigo = f"{_secrets.randbelow(1000000):06d}"
    cliente.codigo_verificacion_hash = _hash_codigo(codigo)
    cliente.codigo_verificacion_expira = datetime.utcnow() + timedelta(minutes=15)
    whatsapp._enviar(
        cliente.telefono_whatsapp,
        f"Hola {cliente.nombre_comercial}, le saluda Regina de Pacheco & "
        f"Aparicio. Su código para crear la contraseña de su portal es: "
        f"{codigo} (vigente 15 minutos). Si usted no lo solicitó, ignore "
        f"este mensaje.")
    auditoria.registrar(db, usuario_id=None, accion="autoregistro_codigo",
                        tabla_afectada="clientes", registro_id=cliente.id,
                        request=request)
    db.commit()
    return respuesta_neutra


class CrearContrasena(_BaseModel):
    contacto: str
    codigo: str
    password: str


@router.post("/autoregistro/crear-contrasena")
def autoregistro_crear_contrasena(payload: CrearContrasena, request: Request,
                                  db: Session = Depends(get_db)):
    """
    Paso 2: con el código vigente, el cliente define su contraseña y su
    cuenta del portal queda creada y ligada a su expediente.
    """
    from services.auth import hash_password
    cliente = _buscar_cliente_por_contacto(db, payload.contacto)
    if (not cliente or cliente.usuario_portal_id
            or not cliente.codigo_verificacion_hash
            or not cliente.codigo_verificacion_expira
            or cliente.codigo_verificacion_expira < datetime.utcnow()
            or cliente.codigo_verificacion_hash != _hash_codigo(payload.codigo.strip())):
        raise HTTPException(403, "Código incorrecto o vencido. Solicite uno nuevo.")
    if len(payload.password) < 10:
        raise HTTPException(400, "La contraseña debe tener al menos 10 caracteres.")
    if not cliente.email:
        raise HTTPException(400, "Su expediente no tiene correo registrado: "
                                 "llame al despacho para completarlo.")

    usuario = Usuario(nombre=cliente.nombre_comercial, email=cliente.email,
                      rol=RolUsuario.CLIENTE,
                      password_hash=hash_password(payload.password))
    db.add(usuario)
    db.flush()
    cliente.usuario_portal_id = usuario.id
    cliente.codigo_verificacion_hash = None
    cliente.codigo_verificacion_expira = None
    auditoria.registrar(db, usuario_id=usuario.id, accion="autoregistro_completado",
                        tabla_afectada="clientes", registro_id=cliente.id,
                        request=request)
    db.commit()
    return {"ok": True, "mensaje": "Cuenta creada. Ya puede iniciar sesión."}
