# -*- coding: utf-8 -*-
"""
Esquema A (Servicio Primero): entrega también por CORREO.
Backend SMTP configurable; en desarrollo, modo 'simulado' loguea a consola.
"""
import logging
import smtplib
from email.message import EmailMessage

import config

logger = logging.getLogger("pya.correo")


def enviar_correo(destinatario: str, asunto: str, cuerpo: str,
                  adjunto: bytes | None = None,
                  nombre_adjunto: str | None = None) -> None:
    if not destinatario:
        return
    if config.SMTP_HOST == "":
        logger.info("[SIMULADO] Correo -> %s | %s | adjunto=%s",
                    destinatario, asunto, nombre_adjunto)
        return

    msg = EmailMessage()
    msg["From"] = config.SMTP_FROM
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.set_content(cuerpo)
    if adjunto and nombre_adjunto:
        msg.add_attachment(adjunto, maintype="application", subtype="pdf",
                           filename=nombre_adjunto)

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as s:
        s.starttls()
        if config.SMTP_USER:
            s.login(config.SMTP_USER, config.SMTP_PASSWORD)
        s.send_message(msg)
