# -*- coding: utf-8 -*-
"""
P&A Despacho Contable - Sistema de Gestión Institucional
========================================================
Archivo principal de inicialización (FastAPI).

Arranque local:
    uvicorn app:app --reload --port 8000

Documentación interactiva automática:
    http://localhost:8000/docs
"""
import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from database import Base, engine
from models import models  # noqa: F401  (registra las tablas en el metadata)
from routers import (admin, auth, calculos, certificados, citas, cobranza,
                     confirmacion, facturas, importacion, instalacion,
                     expediente, integracion_contpaq, obligaciones, patronal,
                     portal, respaldos, saldos_favor, situaciones, tickets,
                     voice, webhooks)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(name)s | %(message)s")

# Crear tablas en desarrollo. En producción usar migraciones (Alembic).
Base.metadata.create_all(bind=engine)

# Carpeta local solo si el backend de storage es local (desarrollo)
if config.STORAGE_BACKEND == "local":
    os.makedirs(config.UPLOADS_DIR, exist_ok=True)

app = FastAPI(
    title="P&A · Sistema de Gestión del Despacho",
    description=(
        "Backend modular: obligaciones fiscales, cobranza asistida, "
        "asistente virtual Regina (WhatsApp + voz) y Portal VIP de clientes. "
        "Regla de Oro: Modo Humano Primero."
    ),
    version="0.3.0",
    # DEBUG=False en producción: sin documentación interactiva expuesta
    docs_url="/docs" if config.DEBUG or not config.ES_PRODUCCION else None,
    redoc_url=None if config.ES_PRODUCCION else "/redoc",
    debug=config.DEBUG,
)

# SEGURIDAD: HTTPS de extremo a extremo en producción.
# (El TLS lo termina nginx/Caddy/el balanceador; este middleware redirige
# cualquier petición http:// residual a https://.)
if config.ES_PRODUCCION:
    app.add_middleware(HTTPSRedirectMiddleware)


@app.middleware("http")
async def cabeceras_de_seguridad(request: Request, call_next):
    """Cabeceras estrictas en TODA respuesta (HSTS, CSP, anti-framing)."""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com "
        "https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; frame-ancestors 'none'")
    if config.ES_PRODUCCION:
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload")
    return response

# SEGURIDAD 4: CORS y hosts confiables para el despliegue por subdominios.
# El backend (api.tudominio.com) servirá a DOS frontends bajo tu dominio:
#   - clientes.tudominio.com -> Portal VIP (solo rutas /api/portal + /api/auth)
#   - equipo.tudominio.com   -> Director, Contadores y panel de Pao
# En producción definir:
#   ALLOWED_ORIGINS=https://clientes.tudominio.com,https://equipo.tudominio.com
#   ALLOWED_HOSTS=api.tudominio.com
# Nota: la separación por subdominio es visual/organizativa; la seguridad
# real de datos la garantizan los roles JWT (un cliente que apunte al
# subdominio del equipo recibirá 403 igualmente).
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.ALLOWED_HOSTS)

# Routers (módulos del sistema)
app.include_router(auth.router)          # Módulo 1: roles y acceso
app.include_router(obligaciones.router)  # Módulo 2 + disparo Módulo 4
app.include_router(cobranza.router)      # Módulos 3 y 5: panel de Pao + efectivo
app.include_router(webhooks.router)      # Módulos 4 y 6: WhatsApp y voz
app.include_router(portal.router)        # Módulo 7: Portal VIP
app.include_router(admin.router)         # Vista Super-Admin/CFO (Director)
app.include_router(confirmacion.router)  # Link corto /c/{token}
app.include_router(tickets.router)       # Buzón de trámites (equipo)
app.include_router(citas.router)         # Agenda de asesorías
app.include_router(calculos.router)      # Determinación y autorización de impuestos
app.include_router(voice.router)         # Canal de voz de Sofía (orquestador)
app.include_router(patronal.router)      # IMSS (IDSE/SUA/SIPARE), ISN y nóminas
app.include_router(certificados.router)  # Bóveda blindada de firmas y sellos
app.include_router(instalacion.router)   # /instalar: primer Director sin Shell
app.include_router(respaldos.router)     # Respaldos CONTPAQ con rotación
app.include_router(saldos_favor.router)  # Inventario de saldos a favor
app.include_router(importacion.router)   # Alta masiva por Excel
app.include_router(integracion_contpaq.router)  # Agente CONTPAQ (solo lectura)
app.include_router(facturas.router)      # Solicitud de facturas del cliente
app.include_router(situaciones.router)   # Semáforo con criterio humano
app.include_router(expediente.router)    # Expediente, adeudos, estado de cuenta

# Frontend estático (Tailwind + Chart.js se sirven desde /static)
app.mount("/static", StaticFiles(directory="static"), name="static")


# En producción, cada subdominio (clientes./equipo.) apunta su raíz a su app;
# en desarrollo se sirven en rutas locales:
@app.get("/equipo", include_in_schema=False)
def app_equipo():
    return FileResponse("static/equipo/index.html")


@app.get("/clientes", include_in_schema=False)
def app_clientes():
    return FileResponse("static/clientes/index.html")


@app.get("/inicio", include_in_schema=False)
def landing():
    return FileResponse("static/landing/index.html")


@app.on_event("startup")
def _arrancar_programador():
    """Rutinas diarias dentro del propio servicio (sin Redis ni worker).
    Se apaga con USAR_PROGRAMADOR_INTERNO=false si algún día se vuelve
    al esquema de Celery+Redis dedicados."""
    import os
    if os.getenv("USAR_PROGRAMADOR_INTERNO", "true").lower() != "false":
        from services import programador
        programador.iniciar()


@app.get("/", include_in_schema=False)
def raiz():
    """www.pafirma.com muestra la página institucional, no un JSON técnico."""
    return FileResponse("static/landing/index.html")


@app.get("/salud", tags=["Salud"])
def salud():
    return {"sistema": "P&A Despacho", "estatus": "operando",
            "regla_de_oro": "Modo Humano Primero"}
