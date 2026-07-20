# -*- coding: utf-8 -*-
"""
Configuración central de P&A. En producción, TODO por variables de entorno.
Nunca subir llaves reales al repositorio (usar .env local + gestor de secretos).
"""
import os

# --- Entorno ---
# development | production  (controla seed, CORS estricto, cookies seguras)
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ES_PRODUCCION = ENVIRONMENT == "production"

# DEBUG estrictamente apagado en producción (no hay trazas al cliente;
# los docs interactivos /docs y /redoc también se desactivan).
DEBUG = (os.getenv("DEBUG", "false").lower() == "true") and not ES_PRODUCCION

# URL pública base (para links cortos de confirmación)
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# --- Seguridad / JWT ---
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if ES_PRODUCCION:
        raise RuntimeError("SECRET_KEY es obligatoria en producción "
                           "(generar con: openssl rand -hex 32)")
    SECRET_KEY = "solo-desarrollo-no-usar-en-produccion"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))  # máx 2 h

# --- Cifrado de archivos en reposo (SEGURIDAD 1) ---
# Generar: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
MASTER_ENCRYPTION_KEY = os.getenv("MASTER_ENCRYPTION_KEY", "")
if ES_PRODUCCION and not MASTER_ENCRYPTION_KEY:
    raise RuntimeError("MASTER_ENCRYPTION_KEY es obligatoria en producción: "
                       "los archivos fiscales no pueden guardarse sin cifrar.")

# --- CORS / Subdominios (SEGURIDAD 4) ---
# La app se divide visualmente en dos frontends bajo el dominio propio:
#   clientes.tudominio.com -> Portal VIP (rol CLIENTE)
#   equipo.tudominio.com   -> Director, Contadores y Secretaria
# Definir en producción, separados por coma:
#   ALLOWED_ORIGINS=https://clientes.pya.mx,https://equipo.pya.mx
_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if _origins_env:
    ALLOWED_ORIGINS = [o.strip() for o in _origins_env.split(",") if o.strip()]
elif ES_PRODUCCION:
    raise RuntimeError("ALLOWED_ORIGINS es obligatoria en producción "
                       "(ej. https://clientes.pya.mx,https://equipo.pya.mx)")
else:
    ALLOWED_ORIGINS = ["http://localhost:8000", "http://localhost:5173"]

# Hosts válidos que puede atender este servidor (anti Host-header injection)
_hosts_env = os.getenv("ALLOWED_HOSTS", "")
ALLOWED_HOSTS = ([h.strip() for h in _hosts_env.split(",") if h.strip()]
                 if _hosts_env else
                 (["clientes.pya.mx", "equipo.pya.mx", "api.pya.mx"]
                  if ES_PRODUCCION else ["*"]))

# --- Almacenamiento de documentos ---
# "s3" (OBLIGATORIO en producción: bucket privado + URLs firmadas 5 min)
# "local" (solo desarrollo: Fernet en reposo)
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
if ES_PRODUCCION and STORAGE_BACKEND == "local":
    raise RuntimeError("En producción el almacenamiento local está prohibido: "
                       "configurar STORAGE_BACKEND=s3 con bucket privado.")
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")  # R2/MinIO opcional
URL_FIRMADA_EXPIRACION_SEGUNDOS = 300  # 5 minutos exactos

UPLOADS_DIR = os.getenv("UPLOADS_DIR", "uploads")  # solo backend local

# --- 2FA ---
TOTP_OBLIGATORIO_INTERNO = os.getenv("TOTP_OBLIGATORIO_INTERNO", "true").lower() == "true"

# --- Tareas asíncronas (Celery) ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- Correo (Esquema A) ---
SMTP_HOST = os.getenv("SMTP_HOST", "")   # vacío = modo simulado
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "notificaciones@pya.mx")

# --- WhatsApp Business API (Twilio / Meta Cloud API) ---
WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "simulado")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+5218100000000")

# --- IA de Voz: asistente "Sofía" ---
# Voz en pruebas con ElevenLabs; orquestador telefónico: Vapi o Retell AI.
# LLAVES A DEFINIR EN .env CUANDO SE CONTRATE EL SERVICIO:
#   ELEVENLABS_API_KEY   -> API key de ElevenLabs (síntesis de la voz de Sofía)
#   VOICE_WEBHOOK_API_KEY-> secreto compartido con el orquestador: TODA petición
#                           entrante a /api/voice/* debe traerlo en el header
#                           X-Voice-Api-Key (generar: openssl rand -hex 24)
#   VOZ_API_KEY          -> API key del orquestador (Vapi/Retell)
#   VOZ_AGENT_ID         -> id del agente Sofía configurado en la plataforma
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
VOICE_WEBHOOK_API_KEY = os.getenv("VOICE_WEBHOOK_API_KEY", "")
if ES_PRODUCCION and not VOICE_WEBHOOK_API_KEY:
    # sin secreto, los endpoints de voz quedan APAGADOS (401 siempre)
    pass
NOMBRE_ASISTENTE_VOZ = os.getenv("NOMBRE_ASISTENTE_VOZ", "Sofía")

# --- IA de Voz (Vapi / Retell) ---
VOZ_PROVIDER = os.getenv("VOZ_PROVIDER", "simulado")
VOZ_API_KEY = os.getenv("VOZ_API_KEY", "")
VOZ_AGENT_ID = os.getenv("VOZ_AGENT_ID", "")

# --- Identidad del asistente virtual ---
NOMBRE_ASISTENTE = "Regina"
FIRMA_ASISTENTE = "Regina · Asistente Digital de P&A"

# --- Reglas de cartera vencida (Módulo 2) ---
DIAS_ALERTA_AMARILLA = 30
DIAS_ALERTA_ROJA = 60
DIAS_ALERTA_ROJA_PARPADEANTE = 90
