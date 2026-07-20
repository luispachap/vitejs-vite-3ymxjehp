# -*- coding: utf-8 -*-
"""
SEGURIDAD 1: Cifrado de archivos en reposo.
===========================================
TODO archivo (PDF del SAT, comprobantes, documentos de la bóveda) se cifra
con Fernet (AES-128-CBC + HMAC-SHA256, de la librería `cryptography`) ANTES
de tocar el disco. Los archivos guardados llevan extensión adicional `.enc`
y son ilegibles sin la llave maestra.

El descifrado ocurre SIEMPRE en memoria: nunca se escribe una copia
descifrada al disco. La llave maestra vive exclusivamente en la variable
de entorno MASTER_ENCRYPTION_KEY (ver config.py).

Generar una llave nueva (una sola vez, guardarla en el gestor de secretos):
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

ADVERTENCIA: si se pierde la llave, los archivos son IRRECUPERABLES.
Respaldar la llave en un gestor de secretos (no en el repositorio).
"""
import os

from cryptography.fernet import Fernet, InvalidToken

import config

EXTENSION_CIFRADO = ".enc"


def _fernet() -> Fernet:
    llave = config.MASTER_ENCRYPTION_KEY
    if not llave:
        raise RuntimeError(
            "MASTER_ENCRYPTION_KEY no está definida en las variables de entorno. "
            "El sistema NO guardará archivos sin cifrado configurado."
        )
    return Fernet(llave.encode() if isinstance(llave, str) else llave)


def guardar_cifrado(contenido: bytes, ruta_destino: str) -> str:
    """
    Cifra `contenido` y lo escribe en disco como `ruta_destino + .enc`.
    Retorna la ruta final (la que debe guardarse en la base de datos).
    """
    ruta_final = ruta_destino + EXTENSION_CIFRADO
    os.makedirs(os.path.dirname(ruta_final), exist_ok=True)
    cifrado = _fernet().encrypt(contenido)
    # Escritura atómica: primero temporal, luego rename
    tmp = ruta_final + ".tmp"
    with open(tmp, "wb") as f:
        f.write(cifrado)
    os.replace(tmp, ruta_final)
    return ruta_final


def leer_descifrado(ruta_archivo: str) -> bytes:
    """
    Lee el archivo cifrado y retorna los bytes ORIGINALES en memoria.
    Nunca escribe la versión descifrada al disco.
    Lanza ValueError si el archivo fue alterado o la llave no corresponde.
    """
    with open(ruta_archivo, "rb") as f:
        datos = f.read()
    try:
        return _fernet().decrypt(datos)
    except InvalidToken as exc:
        raise ValueError(
            "No fue posible descifrar el archivo: llave incorrecta o "
            "archivo alterado (posible manipulación)."
        ) from exc


def nombre_original(ruta_cifrada: str) -> str:
    """Nombre de descarga sin la extensión .enc (ej. 'GNO_2026-07.pdf')."""
    base = os.path.basename(ruta_cifrada)
    return base[:-len(EXTENSION_CIFRADO)] if base.endswith(EXTENSION_CIFRADO) else base
