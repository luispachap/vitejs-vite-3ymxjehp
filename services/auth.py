# -*- coding: utf-8 -*-
"""
SEGURIDAD 3: Autenticación JWT endurecida + control estricto de roles.
======================================================================
- Tokens de vida corta (máx. 2 horas, configurable a la baja).
- El token está FIRMADO con HMAC-SHA256: cualquier alteración del rol o del
  usuario invalida la firma y el acceso se rechaza. (Nota técnica honesta:
  un JWT firmado es a prueba de manipulación pero su contenido es legible;
  como el rol no es un dato secreto, la firma es la protección correcta.
  Si algún día se requiere ocultar el contenido, el estándar es JWE.)
- `requiere_rol(...)` es la ÚNICA puerta de entrada a rutas protegidas.
- `cliente_autenticado()` implementa el aislamiento del rol CLIENTE:
  solo puede consumir rutas de routers/portal.py y únicamente ve los datos
  de SU propia empresa. Jamás puede tocar rutas del despacho.
"""
import uuid
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

import config
from database import get_db
from models.models import Cliente, Usuario, RolUsuario

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Techo duro de 2 horas: aunque la variable de entorno pida más, se recorta.
MAX_MINUTOS_TOKEN = 120


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verificar_password(plano: str, hashed: str) -> bool:
    return pwd_context.verify(plano, hashed)


def crear_token(usuario: Usuario) -> str:
    minutos = min(config.ACCESS_TOKEN_EXPIRE_MINUTES, MAX_MINUTOS_TOKEN)
    ahora = datetime.utcnow()
    payload = {
        "sub": str(usuario.id),
        "rol": usuario.rol.value,
        "iat": ahora,                               # emitido en
        "exp": ahora + timedelta(minutes=minutos),  # expira (<= 2 h)
        "jti": str(uuid.uuid4()),                   # id único del token
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.ALGORITHM)


def usuario_actual(token: str = Depends(oauth2_scheme),
                   db: Session = Depends(get_db)) -> Usuario:
    excepcion = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión inválida o expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.SECRET_KEY,
                             algorithms=[config.ALGORITHM])
        usuario_id = int(payload["sub"])
        rol_token = payload["rol"]
    except (JWTError, KeyError, TypeError, ValueError):
        raise excepcion

    usuario = db.query(Usuario).filter(Usuario.id == usuario_id,
                                       Usuario.activo).first()
    if not usuario:
        raise excepcion

    # Defensa en profundidad: el rol vigente en base de datos manda.
    # Si el rol del token no coincide (p. ej. fue degradado tras emitirse),
    # la sesión se invalida.
    if usuario.rol.value != rol_token:
        raise excepcion
    return usuario


def requiere_rol(*roles: RolUsuario):
    """
    Dependencia parametrizable de control de acceso:
        Depends(requiere_rol(RolUsuario.DIRECTOR))
    Rechaza con 403 cualquier rol no listado explícitamente.
    """
    def _verificar(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para esta sección",
            )
        return usuario
    return _verificar


# --- Alias semánticos para lectura clara en los routers -------------------
# El rol CLIENTE no aparece en ninguno de estos alias: las rutas internas
# del despacho le quedan prohibidas por construcción.
# El ADMINISTRADOR (Luis) entra a TODO: se agrega a cada guardián.
# El DIRECTOR (Papá) también tiene acceso completo al despacho.
# La SUPERVISORA (Artemisa) es además CONTADORA: elabora cálculos y hace el
# ciclo patronal, aparte de autorizar (nunca sus propios cálculos: eso lo
# impide un candado por PERSONA, no por rol).
solo_director = requiere_rol(RolUsuario.DIRECTOR, RolUsuario.ADMINISTRADOR)
# Pao no solo lleva la cobranza: también hace contabilidades. Por eso entra al
# equipo contable (elabora cálculos, ciclo IMSS, saldos a favor...). Conserva
# además su kiosco simplificado, que sigue siendo su pantalla de inicio.
solo_equipo_contable = requiere_rol(RolUsuario.CONTADOR, RolUsuario.SUPERVISOR,
                                    RolUsuario.DIRECTOR, RolUsuario.ADMINISTRADOR,
                                    RolUsuario.ADMIN_SECRETARIA)
solo_secretaria_o_director = requiere_rol(RolUsuario.ADMIN_SECRETARIA,
                                          RolUsuario.SUPERVISOR,
                                          RolUsuario.DIRECTOR,
                                          RolUsuario.ADMINISTRADOR)
# Autorización de cálculos: SOLO el Director (Papá) o la Supervisora (Artemisa)
solo_autorizadores = requiere_rol(RolUsuario.DIRECTOR, RolUsuario.SUPERVISOR,
                                  RolUsuario.ADMINISTRADOR)
# Todo el personal interno: para listados básicos que TODOS necesitan
# (selector de clientes en calculadora, certificados, respaldos, citas...)
todo_el_personal = requiere_rol(RolUsuario.DIRECTOR, RolUsuario.SUPERVISOR,
                                RolUsuario.CONTADOR, RolUsuario.ADMIN_SECRETARIA,
                                RolUsuario.ADMINISTRADOR)


def cliente_autenticado(usuario: Usuario = Depends(requiere_rol(RolUsuario.CLIENTE)),
                        db: Session = Depends(get_db)) -> Cliente:
    """
    AISLAMIENTO DE DATOS DEL ROL CLIENTE (multi-tenant a nivel de fila):
    resuelve la empresa vinculada al usuario autenticado. Todas las rutas de
    portal.py consultan EXCLUSIVAMENTE a través del objeto retornado aquí,
    de modo que es estructuralmente imposible pedir datos de otra empresa
    (no existe ningún parámetro cliente_id que el usuario pueda manipular).
    """
    cliente = db.query(Cliente).filter(
        Cliente.usuario_portal_id == usuario.id).first()
    if not cliente:
        raise HTTPException(status_code=403,
                            detail="Su cuenta no está vinculada a una empresa")
    return cliente
