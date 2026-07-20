# Guía de despliegue a producción — P&A

Arquitectura final: **Supabase** (PostgreSQL + Storage S3) + **Render**
(API FastAPI + worker Celery + Redis) + **tu dominio** apuntando ahí.
Costo aproximado: Supabase gratis para empezar + Render ~$14 USD/mes
(web + worker) + dominio ~$12 USD/año.

## Paso 1 — Base de datos y archivos: Supabase (15 min)
1. Crea el proyecto en https://supabase.com (región `us-east-1` o la más
   cercana a Zacatecas disponible). Guarda la contraseña de la base.
2. **Cadena de conexión**: Project Settings → Database → Connection string
   → pestaña **Session pooler** (puerto 5432). Se ve así:
   `postgresql://postgres.abcdef:[PASSWORD]@aws-0-us-east-1.pooler.supabase.com:5432/postgres`
   → esa es tu `DATABASE_URL` (agrega el prefijo `postgresql+psycopg2://`).
3. **Storage**: Storage → New bucket → nombre `documentos`, **Private**.
4. **Llaves S3**: Project Settings → Storage → S3 Access Keys → New access
   key. Anota: endpoint (`https://TU-REF.supabase.co/storage/v1/s3`),
   region, access key y secret → van a `S3_*` en Render.

## Paso 2 — Genera tus dos llaves maestras (2 min)
```bash
openssl rand -hex 32        # SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # MASTER_ENCRYPTION_KEY
```
⚠ Respalda MASTER_ENCRYPTION_KEY en un gestor de contraseñas. Si se
pierde, los RFC y montos cifrados en la base son IRRECUPERABLES.

## Paso 3 — Sube el código a GitHub (10 min)
Repositorio **privado** con el contenido de esta carpeta. Nunca subas un
archivo `.env` con valores reales (el `.gitignore` ya lo excluye).

## Paso 4 — Render (20 min)
1. https://render.com → New → **Blueprint** → conecta tu repo. Render lee
   `render.yaml` y crea los tres servicios (api, celery, redis).
2. Pega los valores de las variables marcadas `sync: false` (paso 1 y 2).
3. Al terminar el deploy, abre la **Shell** del servicio `pya-api` y crea
   tu usuario:
   ```bash
   python crear_director.py "Luis" luis@pacheco-aparicio.com
   ```
4. Enrola tu 2FA (obligatorio en producción): manda un POST a
   `/api/auth/2fa/enrolar` con tu correo y contraseña, escanea el QR de la
   `provisioning_uri` con Google Authenticator y verifica en
   `/api/auth/2fa/verificar`. Desde el panel Super-Admin podrás dar de
   alta a Pao, contadores y clientes.

## Paso 5 — Tu dominio (10 min + propagación DNS)
1. Compra el dominio (Namecheap, Cloudflare o GoDaddy).
2. DNS → registro **CNAME**: `despacho` → `pya-api.onrender.com`.
3. En Render: Settings del servicio web → Custom Domains → agrega
   `despacho.pacheco-aparicio.com`. Render emite el certificado HTTPS solo.
4. Listo: `despacho.tudominio.com/equipo` y `.../clientes`.
   Cuando quieras separar en `equipo.` y `clientes.` como subdominios
   independientes, se agregan igual (más CNAMEs) y se actualizan
   `ALLOWED_ORIGINS`/`ALLOWED_HOSTS`; los roles JWT ya aíslan los datos
   sin importar el subdominio.

## Paso 6 — Encender los canales reales (cuando toque)
- WhatsApp: cuenta de Twilio → `WHATSAPP_PROVIDER=twilio` + credenciales,
  y apunta los webhooks de Twilio a `/api/webhooks/whatsapp/...`.
- Voz: crea el agente en Vapi/Retell con el prompt de `services/voz.py`
  y apunta su webhook post-llamada a `/api/webhooks/voz/post-llamada`.
- Correo: credenciales SMTP (el correo de tu dominio o SendGrid).
Mientras tanto todo opera en modo simulado sin romper nada.

## Verificación final
- `https://despacho.tudominio.com/` responde `{"estatus": "operando"}`.
- `/docs` NO abre (bloqueado en producción). ✓ esperado
- Login sin 2FA de un usuario interno → rechazado. ✓ esperado
- En Supabase → Table Editor: la columna `rfc` de `clientes` se ve como
  blob cifrado ilegible. ✓ esperado
