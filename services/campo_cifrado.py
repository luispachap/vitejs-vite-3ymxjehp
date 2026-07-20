# -*- coding: utf-8 -*-
"""
SEGURIDAD: Cifrado a Nivel de Campo (Field-Level Encryption).
=============================================================
Tipos de columna SQLAlchemy que cifran/descifran transparentemente con
Fernet (AES-128-CBC + HMAC-SHA256). En la base de datos solo existen
blobs cifrados; el código Python siempre ve el valor real.

Se aplica a: RFC, montos de honorarios e impuestos, secretos TOTP y
tokens de API.

NOTA DE INGENIERÍA (importante):
- Las CONTRASEÑAS NO se cifran: se HASHEAN con bcrypt (services/auth.py).
  Hashear es estrictamente más seguro que cifrar para contraseñas —
  un hash no puede revertirse ni con la llave maestra. Cifrarlas sería
  un retroceso de seguridad.
- Fernet es no-determinista (el mismo RFC produce blobs distintos), por lo
  que NO se puede buscar ni imponer UNIQUE sobre la columna cifrada.
  Para búsquedas/unicidad se usa una columna paralela `rfc_hash`
  (HMAC-SHA256 con la llave maestra): permite encontrar por RFC exacto
  sin revelar el RFC.
- Los campos numéricos cifrados no pueden sumarse con SQL (SUM); las
  agregaciones se hacen en Python, como ya ocurre en los tableros.
"""
import hashlib
import hmac

from sqlalchemy import Text, TypeDecorator

import config
from services.cifrado import _fernet


class TextoCifrado(TypeDecorator):
    """Cadena cifrada en reposo (RFC, secretos TOTP, tokens de API)."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _fernet().encrypt(str(value).encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return _fernet().decrypt(value.encode()).decode()


class NumeroCifrado(TypeDecorator):
    """Monto (float) cifrado en reposo. Agregaciones: en Python."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _fernet().encrypt(repr(float(value)).encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return float(_fernet().decrypt(value.encode()).decode())


def hash_busqueda(valor: str) -> str:
    """
    HMAC-SHA256 determinista para índices de búsqueda sobre datos cifrados
    (ej. rfc_hash). Usa la llave maestra como clave del HMAC, de modo que
    el hash no es calculable sin ella (a diferencia de un SHA simple).
    """
    llave = (config.MASTER_ENCRYPTION_KEY or "dev").encode()
    return hmac.new(llave, valor.strip().upper().encode(),
                    hashlib.sha256).hexdigest()
