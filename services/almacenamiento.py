# -*- coding: utf-8 -*-
"""
SEGURIDAD: Almacenamiento de documentos en la nube.
===================================================
Abstracción de storage con dos backends (config.STORAGE_BACKEND):

- "s3" (PRODUCCIÓN): bucket privado en AWS S3 (o compatible: Cloudflare R2,
  GCS en modo interoperable). Los objetos se suben con cifrado del lado del
  servidor (SSE) y bucket 100% privado. Las descargas se entregan mediante
  URLs FIRMADAS TEMPORALES que expiran en 5 minutos: nadie sin una URL
  recién firmada por la app puede tocar un archivo, y la URL caduca sola.

- "local" (SOLO DESARROLLO): disco local con cifrado Fernet en reposo
  (services/cifrado.py) y descifrado en memoria. En producción, config.py
  aborta el arranque si STORAGE_BACKEND=local.

DECISIÓN DE DISEÑO (documentada a propósito): en el backend S3 el cifrado
en reposo lo aplica el proveedor (SSE-S3/KMS) en lugar de Fernet a nivel
de aplicación. Motivo: las URLs firmadas entregan el objeto directamente
desde S3 al navegador del cliente, sin pasar por nuestra app; si el objeto
estuviera cifrado con Fernet, el cliente recibiría bytes ilegibles. SSE +
bucket privado + URL de 5 minutos + auditoría de cada firma es el patrón
estándar de la industria para documentos confidenciales.
"""
import os
import uuid

import config
from services import cifrado as cifrado_local


def _cliente_s3():
    """
    ⚠ SigV4 + path-style NO SON OPCIONALES en proveedores compatibles
    (Supabase Storage, R2, MinIO). Sin signature_version="s3v4", boto3
    genera la URL "firmada" SIN el parámetro X-Amz-Signature y el proveedor
    responde <Code>AccessDenied</Code><Message>Missing signature</Message>:
    ningún documento se puede descargar. Verificado contra Supabase real.
    """
    import boto3  # import diferido: solo se requiere en producción
    from botocore.config import Config as ConfigBoto
    return boto3.client(
        "s3",
        region_name=config.S3_REGION,
        aws_access_key_id=config.S3_ACCESS_KEY or None,
        aws_secret_access_key=config.S3_SECRET_KEY or None,
        endpoint_url=config.S3_ENDPOINT_URL or None,  # R2/MinIO/Supabase
        config=ConfigBoto(signature_version="s3v4",
                          s3={"addressing_style": "path"}),
    )


def guardar_documento(contenido: bytes, carpeta: str, nombre: str) -> str:
    """
    Guarda el documento y retorna la CLAVE que debe persistirse en BD.
    Nombres de objeto sin datos sensibles (jamás el RFC): carpeta lógica +
    uuid + nombre saneado.
    """
    nombre_seguro = os.path.basename(nombre).replace(" ", "_")
    clave = f"{carpeta}/{uuid.uuid4().hex}_{nombre_seguro}"

    if config.STORAGE_BACKEND == "s3":
        _cliente_s3().put_object(
            Bucket=config.S3_BUCKET,
            Key=clave,
            Body=contenido,
            ServerSideEncryption="AES256",   # cifrado en reposo del proveedor
            ContentType="application/pdf" if nombre_seguro.lower().endswith(".pdf")
                        else "application/octet-stream",
        )
        return f"s3://{clave}"

    # Backend local (desarrollo): Fernet en reposo
    return cifrado_local.guardar_cifrado(
        contenido, os.path.join(config.UPLOADS_DIR, clave))


def es_s3(ruta: str) -> bool:
    return ruta.startswith("s3://")


def url_firmada_temporal(ruta: str) -> str:
    """
    URL firmada que EXPIRA EN 5 MINUTOS (300 s) para descarga directa
    del bucket privado. Solo válida para backend s3.
    """
    if not es_s3(ruta):
        raise ValueError("url_firmada_temporal solo aplica al backend s3")
    return _cliente_s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": config.S3_BUCKET, "Key": ruta[len("s3://"):]},
        ExpiresIn=config.URL_FIRMADA_EXPIRACION_SEGUNDOS,  # 300 s
    )


def leer_bytes(ruta: str) -> bytes:
    """Lectura en memoria (backend local descifra Fernet al vuelo)."""
    if es_s3(ruta):
        obj = _cliente_s3().get_object(Bucket=config.S3_BUCKET,
                                       Key=ruta[len("s3://"):])
        return obj["Body"].read()
    return cifrado_local.leer_descifrado(ruta)


def respuesta_archivo(ruta: str, nombre: str | None = None,
                      inline: bool = True):
    """
    Devuelve el archivo SERVIDO POR NOSOTROS (mismo origen).
    ⚠ No devolver la URL firmada de S3 al navegador: al ser otro dominio, el
    fetch() del visor falla por CORS ("Failed to fetch"). Servirlo aquí
    permite incrustarlo, descargarlo y verlo en la pantalla dividida.
    """
    from fastapi.responses import Response
    datos = leer_bytes(ruta)
    nombre = nombre or nombre_descarga(ruta)
    tipos = {".pdf": "application/pdf", ".png": "image/png",
             ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".xml": "text/xml",
             ".zip": "application/zip", ".txt": "text/plain"}
    ext = os.path.splitext(nombre)[1].lower()
    disposicion = "inline" if inline else "attachment"
    return Response(content=datos,
                    media_type=tipos.get(ext, "application/octet-stream"),
                    headers={"Content-Disposition":
                             f'{disposicion}; filename="{nombre}"'})


def nombre_descarga(ruta: str) -> str:
    base = os.path.basename(ruta)
    if base.endswith(cifrado_local.EXTENSION_CIFRADO):
        base = base[:-len(cifrado_local.EXTENSION_CIFRADO)]
    # quitar el prefijo uuid_
    return base.split("_", 1)[1] if "_" in base else base


def eliminar_documento(ruta: str) -> None:
    """
    Borra un archivo (usado por la rotación de respaldos CONTPAQ).
    Funciona igual en local y en S3; si el archivo ya no existe, no falla.
    """
    if es_s3(ruta):
        _cliente_s3().delete_object(Bucket=config.S3_BUCKET,
                                    Key=ruta[len("s3://"):])
    elif os.path.exists(ruta):
        os.remove(ruta)
