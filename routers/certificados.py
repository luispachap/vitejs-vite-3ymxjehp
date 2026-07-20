# -*- coding: utf-8 -*-
"""
CERTIFICADOS DIGITALES Y FIRMAS ELECTRÓNICAS
============================================
e.firma (FIEL), CSD (sellos digitales del SAT), certificados estatales y
del IMSS: los documentos MÁS delicados del despacho.

PROTECCIONES (adicionales a las del resto del sistema):
1. Cifrados en reposo (Fernet) como todos los archivos, y en producción en
   bucket S3 privado.
2. DESCARGA CON PASO EXTRA ("step-up"):
   - Personal: además de su sesión con 2FA, debe teclear un código TOTP
     VIGENTE de su app en el momento de descargar.
   - Clientes: deben reconfirmar su CONTRASEÑA en el momento de descargar.
3. Cada descarga queda en la bitácora inmutable con quién, qué y cuándo.
4. Vencimientos vigilados: tarea diaria (Celery beat) avisa a Supervisora y
   Director 30 días antes; "en renovación" y "renovado por" hacen que nadie
   ande buscando quién tiene la versión nueva: siempre está aquí.

NOTA DE SEGURIDAD: el sistema guarda los ARCHIVOS (.cer/.key/.pfx en ZIP o
PDF), pero NUNCA las contraseñas de las llaves privadas. Esas viajan por
otro canal, de persona a persona.
"""
from datetime import date, datetime

import pyotp
from fastapi import (APIRouter, Depends, File, Form, HTTPException, Request,
                     UploadFile)
from sqlalchemy.orm import Session

import config
from database import get_db
from models.models import CertificadoDigital, Cliente, RolUsuario, Usuario
from services import almacenamiento, auditoria
from services.auth import (cliente_autenticado, solo_equipo_contable,
                           usuario_actual, verificar_password)

router = APIRouter(prefix="/api/certificados", tags=["Certificados y firmas"])

TIPOS_VALIDOS = ("efirma", "csd", "sello_imss", "certificado_estatal", "otro")
EXTENSIONES = (".zip", ".pdf", ".cer", ".key", ".pfx", ".p12")
NOMBRE_TIPO = {"efirma": "e.firma (FIEL)", "csd": "CSD (sello digital SAT)",
               "sello_imss": "Certificado IMSS",
               "certificado_estatal": "Certificado estatal", "otro": "Otro"}


def _serializar(c: CertificadoDigital) -> dict:
    return {"id": c.id, "cliente_id": c.cliente_id,
            "cliente": c.cliente.nombre_comercial if c.cliente else "Despacho P&A",
            "tipo": c.tipo, "tipo_nombre": NOMBRE_TIPO.get(c.tipo, c.tipo),
            "descripcion": c.descripcion,
            "fecha_vencimiento": str(c.fecha_vencimiento),
            "estatus": c.estatus, "en_renovacion": c.en_renovacion,
            "dias_restantes": (c.fecha_vencimiento - date.today()).days}


def _entregar_archivo(c: CertificadoDigital):
    # El certificado SIEMPRE se descarga (nunca se muestra incrustado)
    return almacenamiento.respuesta_archivo(c.ruta_archivo, inline=False)


# ---------------------------------------------------------------------------
# EQUIPO: subir, listar, renovar
# ---------------------------------------------------------------------------

@router.get("")
def listar_certificados(u: Usuario = Depends(solo_equipo_contable),
                        db: Session = Depends(get_db)):
    """Todos los certificados vigentes/por vencer/vencidos (no reemplazados)."""
    certs = (db.query(CertificadoDigital)
             .filter(CertificadoDigital.reemplazado_por_id.is_(None))
             .order_by(CertificadoDigital.fecha_vencimiento.asc()).all())
    return [_serializar(c) for c in certs]


@router.post("")
def subir_certificado(request: Request,
                      tipo: str = Form(...),
                      descripcion: str = Form(...),
                      fecha_vencimiento: date = Form(...),
                      cliente_id: int = Form(None),
                      reemplaza_a: int = Form(None),
                      archivo: UploadFile = File(...),
                      u: Usuario = Depends(solo_equipo_contable),
                      db: Session = Depends(get_db)):
    """
    Sube un certificado (o su RENOVACIÓN con `reemplaza_a`): el anterior
    queda marcado como reemplazado y todos descargan siempre el vigente.
    """
    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(400, "Tipo no válido")
    nombre = (archivo.filename or "").lower()
    if not any(nombre.endswith(e) for e in EXTENSIONES):
        raise HTTPException(400, f"Extensión no permitida ({', '.join(EXTENSIONES)})")
    if cliente_id and not db.query(Cliente).get(cliente_id):
        raise HTTPException(404, "Cliente no encontrado")

    carpeta = (f"certificados/cliente{cliente_id}" if cliente_id
               else "certificados/despacho")
    ruta = almacenamiento.guardar_documento(
        archivo.file.read(), carpeta,
        f"{tipo}_{fecha_vencimiento.isoformat()}_{nombre.replace(' ', '_')}")

    cert = CertificadoDigital(cliente_id=cliente_id, tipo=tipo,
                              descripcion=descripcion.strip()[:200],
                              ruta_archivo=ruta,
                              fecha_vencimiento=fecha_vencimiento,
                              subido_por_id=u.id)
    db.add(cert)
    db.flush()

    if reemplaza_a:
        anterior = db.query(CertificadoDigital).get(reemplaza_a)
        if anterior:
            anterior.reemplazado_por_id = cert.id
            anterior.en_renovacion = False

    auditoria.registrar(db, usuario_id=u.id, accion="carga_certificado",
                        tabla_afectada="certificados_digitales",
                        registro_id=cert.id, request=request, tipo=tipo,
                        renovacion=bool(reemplaza_a))
    db.commit()
    return _serializar(cert)


@router.post("/{cert_id}/solicitar-renovacion")
def solicitar_renovacion(cert_id: int, request: Request,
                         u: Usuario = Depends(solo_equipo_contable),
                         db: Session = Depends(get_db)):
    """Marca 'en renovación' y avisa por correo a Supervisora y Director."""
    from services import correo
    cert = db.query(CertificadoDigital).get(cert_id)
    if not cert:
        raise HTTPException(404, "Certificado no encontrado")
    cert.en_renovacion = True
    for a in (db.query(Usuario)
              .filter(Usuario.rol.in_([RolUsuario.DIRECTOR, RolUsuario.SUPERVISOR]),
                      Usuario.activo).all()):
        correo.enviar_correo(
            a.email, f"Renovación solicitada: {NOMBRE_TIPO.get(cert.tipo)}",
            f"{u.nombre} solicitó renovar '{cert.descripcion}' "
            f"({cert.cliente.nombre_comercial if cert.cliente else 'del despacho'}), "
            f"vence el {cert.fecha_vencimiento}. Cuando esté renovado, súbanlo "
            f"al sistema con 'reemplaza a' para que todos lo encuentren ahí.")
    auditoria.registrar(db, usuario_id=u.id, accion="solicitud_renovacion",
                        tabla_afectada="certificados_digitales",
                        registro_id=cert.id, request=request)
    db.commit()
    return {"ok": True}


@router.post("/{cert_id}/descargar")
def descargar_staff(cert_id: int, request: Request,
                    codigo_totp: str = Form(...),
                    u: Usuario = Depends(solo_equipo_contable),
                    db: Session = Depends(get_db)):
    """
    Descarga del personal con STEP-UP: exige un código TOTP vigente tecleado
    en el momento, además de la sesión. Sin 2FA enrolado no hay descarga.
    """
    cert = db.query(CertificadoDigital).get(cert_id)
    if not cert:
        raise HTTPException(404, "Certificado no encontrado")
    if not (u.totp_habilitado and u.totp_secret):
        raise HTTPException(403, "Active su 2FA para poder descargar certificados")
    if not pyotp.TOTP(u.totp_secret).verify(codigo_totp.strip(), valid_window=1):
        auditoria.registrar(db, usuario_id=u.id, accion="descarga_certificado_denegada",
                            tabla_afectada="certificados_digitales",
                            registro_id=cert.id, request=request, motivo="totp_invalido")
        db.commit()
        raise HTTPException(403, "Código 2FA incorrecto")

    auditoria.registrar(db, usuario_id=u.id, accion="descarga_certificado",
                        tabla_afectada="certificados_digitales",
                        registro_id=cert.id, request=request, tipo=cert.tipo)
    db.commit()
    return _entregar_archivo(cert)


# ---------------------------------------------------------------------------
# PORTAL DEL CLIENTE: sus certificados, cuando los necesite
# ---------------------------------------------------------------------------

@router.get("/mios")
def certificados_del_cliente(cliente: Cliente = Depends(cliente_autenticado),
                             db: Session = Depends(get_db)):
    certs = (db.query(CertificadoDigital)
             .filter(CertificadoDigital.cliente_id == cliente.id,
                     CertificadoDigital.reemplazado_por_id.is_(None))
             .order_by(CertificadoDigital.fecha_vencimiento.asc()).all())
    return [_serializar(c) for c in certs]


@router.post("/mios/{cert_id}/descargar")
def descargar_cliente(cert_id: int, request: Request,
                      password: str = Form(...),
                      cliente: Cliente = Depends(cliente_autenticado),
                      usuario: Usuario = Depends(usuario_actual),
                      db: Session = Depends(get_db)):
    """
    Descarga del cliente con STEP-UP: reconfirma su contraseña en el momento
    (aunque ya tenga sesión iniciada). Solo sus propios certificados.
    """
    cert = db.query(CertificadoDigital).get(cert_id)
    if not cert or cert.cliente_id != cliente.id:
        raise HTTPException(404, "Certificado no encontrado")
    if not verificar_password(password, usuario.password_hash):
        auditoria.registrar(db, usuario_id=usuario.id,
                            accion="descarga_certificado_denegada",
                            tabla_afectada="certificados_digitales",
                            registro_id=cert.id, request=request,
                            motivo="password_invalida")
        db.commit()
        raise HTTPException(403, "Contraseña incorrecta")

    auditoria.registrar(db, usuario_id=usuario.id, accion="descarga_certificado",
                        tabla_afectada="certificados_digitales",
                        registro_id=cert.id, request=request,
                        tipo=cert.tipo, canal="portal_cliente")
    db.commit()
    return _entregar_archivo(cert)
