# -*- coding: utf-8 -*-
"""
Autenticación con 2FA TOTP obligatorio para personal interno.
=============================================================
Flujo:
1. POST /login con email+password.
   - Rol CLIENTE: token directo (el portal puede adoptar 2FA después).
   - Roles internos SIN 2FA configurado:
       * producción -> login BLOQUEADO hasta enrolar 2FA (obligatorio).
       * desarrollo -> se permite, con aviso.
   - Roles internos CON 2FA: deben incluir `codigo_totp` en el form.
2. POST /2fa/enrolar (autenticado con password vía /login-enrolamiento):
   genera el secreto y la URI de aprovisionamiento para el QR
   (Google Authenticator, Authy, 1Password...). Se activa al verificar
   el primer código.
"""
import pyotp
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import config
from database import get_db
from models.models import RolUsuario, Usuario
from services import auditoria
from pydantic import BaseModel

from services.auth import (crear_token, hash_password, usuario_actual,
                           verificar_password)

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])

ROLES_INTERNOS = (RolUsuario.ADMINISTRADOR, RolUsuario.DIRECTOR, RolUsuario.SUPERVISOR,
                  RolUsuario.ADMIN_SECRETARIA, RolUsuario.CONTADOR)


def _validar_credenciales(email: str, password: str, db: Session) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario or not verificar_password(password, usuario.password_hash):
        raise HTTPException(401, "Correo o contraseña incorrectos")
    if not usuario.activo:
        raise HTTPException(403, "Usuario desactivado")
    return usuario


@router.post("/login")
def login(request: Request,
          form: OAuth2PasswordRequestForm = Depends(),
          codigo_totp: str | None = Form(None),
          db: Session = Depends(get_db)):
    usuario = _validar_credenciales(form.username, form.password, db)

    if usuario.rol in ROLES_INTERNOS:
        if usuario.totp_habilitado:
            if not codigo_totp:
                # Señal al frontend de que debe pedir el código de 6 dígitos
                raise HTTPException(401, "totp_requerido")
            if not pyotp.TOTP(usuario.totp_secret).verify(codigo_totp,
                                                          valid_window=1):
                auditoria.registrar(db, usuario_id=usuario.id,
                                    accion="totp_fallido",
                                    tabla_afectada="usuarios",
                                    registro_id=usuario.id, request=request)
                db.commit()
                raise HTTPException(401, "Código 2FA inválido")
        elif config.ES_PRODUCCION and config.TOTP_OBLIGATORIO_INTERNO:
            raise HTTPException(
                403, "2FA obligatorio: enrole su autenticador en "
                     "/api/auth/2fa/enrolar antes de iniciar sesión")

    auditoria.registrar(db, usuario_id=usuario.id, accion="inicio_sesion",
                        tabla_afectada="usuarios", registro_id=usuario.id,
                        request=request, rol=usuario.rol.value)
    db.commit()
    return {"access_token": crear_token(usuario), "token_type": "bearer",
            "rol": usuario.rol.value, "nombre": usuario.nombre,
            "totp_habilitado": usuario.totp_habilitado,
            # Si entró con una contraseña temporal entregada en mano, el
            # frontend lo manda directo a cambiarla.
            "debe_cambiar_password": usuario.debe_cambiar_password}


@router.post("/2fa/enrolar")
def enrolar_2fa(request: Request, email: str = Form(...),
                password: str = Form(...), db: Session = Depends(get_db)):
    """
    Genera el secreto TOTP (se guarda CIFRADO) y la URI para el código QR.
    Requiere credenciales válidas; el 2FA queda activo tras verificar.
    """
    usuario = _validar_credenciales(email, password, db)
    if usuario.totp_habilitado:
        raise HTTPException(409, "2FA ya está activo para esta cuenta")

    usuario.totp_secret = pyotp.random_base32()
    uri = pyotp.TOTP(usuario.totp_secret).provisioning_uri(
        name=usuario.email, issuer_name="P&A Despacho")

    # QR listo para mostrarse en pantalla (data URI): cero pasos técnicos
    import base64, io
    import qrcode
    buf = io.BytesIO()
    qrcode.make(uri).save(buf, format="PNG")
    qr_data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    auditoria.registrar(db, usuario_id=usuario.id, accion="enrolamiento_2fa",
                        tabla_afectada="usuarios", registro_id=usuario.id,
                        request=request)
    db.commit()
    return {"provisioning_uri": uri, "qr": qr_data_uri,
            "instrucciones": "Escanee el QR con Google Authenticator y "
                             "capture el código de 6 dígitos"}


@router.post("/2fa/verificar")
def verificar_2fa(request: Request, email: str = Form(...),
                  password: str = Form(...), codigo_totp: str = Form(...),
                  db: Session = Depends(get_db)):
    usuario = _validar_credenciales(email, password, db)
    if not usuario.totp_secret:
        raise HTTPException(400, "Primero debe enrolarse en /2fa/enrolar")
    if not pyotp.TOTP(usuario.totp_secret).verify(codigo_totp, valid_window=1):
        raise HTTPException(401, "Código 2FA inválido")

    usuario.totp_habilitado = True
    auditoria.registrar(db, usuario_id=usuario.id, accion="activacion_2fa",
                        tabla_afectada="usuarios", registro_id=usuario.id,
                        request=request)
    db.commit()
    return {"ok": True, "mensaje": "2FA activado correctamente"}


class CambioPassword(BaseModel):
    password_actual: str
    password_nueva: str


@router.post("/cambiar-password")
def cambiar_password(payload: CambioPassword, request: Request,
                     usuario: Usuario = Depends(usuario_actual),
                     db: Session = Depends(get_db)):
    """
    Cambio de contraseña propio. Obligatorio en el primer acceso cuando se
    entregó una temporal (debe_cambiar_password), y disponible siempre desde
    el portal para quien quiera cambiarla.
    """
    if not verificar_password(payload.password_actual, usuario.password_hash):
        raise HTTPException(403, "Su contraseña actual no es correcta")
    if len(payload.password_nueva) < 10:
        raise HTTPException(400, "La nueva contraseña debe tener al menos "
                                 "10 caracteres")
    if payload.password_nueva == payload.password_actual:
        raise HTTPException(400, "La nueva contraseña debe ser distinta de "
                                 "la temporal")

    usuario.password_hash = hash_password(payload.password_nueva)
    usuario.debe_cambiar_password = False
    auditoria.registrar(db, usuario_id=usuario.id, accion="cambio_password",
                        tabla_afectada="usuarios", registro_id=usuario.id,
                        request=request)
    db.commit()
    return {"ok": True, "mensaje": "Contraseña actualizada."}
