# GUÍA DE DESPLIEGUE EN CRISTIANO 🙂

Piénsalo así: tu sistema es como abrir una sucursal del despacho en
internet. Necesitas 3 cosas, y 2 ya están:

1. **La bodega** (donde viven los datos y archivos) = **Supabase** ✅ YA ESTÁ.
   Yo ya creé el proyecto, las tablas y el candado de seguridad.
2. **El local** (la computadora que está prendida 24/7 sirviendo la página)
   = **Render**. ESTO es lo que falta.
3. **La dirección** (lo que la gente escribe en el navegador) = tu dominio.

---

## ANTES QUE NADA: ¿qué es la famosa "master key" y DÓNDE va?

La `MASTER_ENCRYPTION_KEY` es **la llave de la caja fuerte**. Con ella el
sistema cifra los RFC, los montos y los archivos. Es un texto largo tipo:
`kX9mP2vQ...=`

**¿Dónde la generas?** Si tienes una computadora con Python, corres:
```
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Si no, dímelo y yo te genero una aquí mismo en el chat.

**¿Dónde la guardas?** En DOS lugares:
1. En un lugar TUYO y seguro: una nota en tu gestor de contraseñas
   (1Password, Bitwarden) o hasta una nota protegida en tu teléfono.
   ⚠ Si esta llave se pierde, los datos cifrados NO se pueden recuperar.
   Ni yo, ni Supabase, ni nadie. Por eso el respaldo.
2. En Render, cuando te pida las "variables de entorno" (paso 3 de abajo).
   Es literalmente copiar y pegar en una casilla. NO va en ningún archivo
   del código, NO se sube a GitHub, NO se la mandas a nadie.

Lo mismo aplica para la `SECRET_KEY` (otra llave, para las sesiones):
```
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## PASO A PASO (total: una tarde tranquila)

### PASO 1 — Junta tus 6 datos de Supabase (ya casi los tienes)
Entra a https://supabase.com/dashboard/project/efaumphgxxpdlttppcgv y apunta:

| Qué | Dónde está | Se pega en Render como |
|---|---|---|
| Contraseña de la base | Settings → Database → Reset database password | (parte de DATABASE_URL) |
| Cadena de conexión | Settings → Database → Connection string → pestaña **Session pooler** | DATABASE_URL |
| Endpoint S3 | Settings → Storage → S3 Access Keys | S3_ENDPOINT_URL |
| Región S3 | ahí mismo | S3_REGION |
| Access key | ahí mismo → New access key | S3_ACCESS_KEY |
| Secret key | ahí mismo (solo se muestra UNA vez, cópiala ya) | S3_SECRET_KEY |

Ojo con la cadena de conexión: donde dice `[YOUR-PASSWORD]` pones la
contraseña que reseteaste, y al inicio cámbiale `postgresql://` por
`postgresql+psycopg2://`. Queda algo así:
`postgresql+psycopg2://postgres.efaumphgxxpdlttppcgv:TUCONTRASEÑA@aws-0-us-west-1.pooler.supabase.com:5432/postgres`

### PASO 2 — Sube el código a GitHub (10 min)
1. Crea cuenta en https://github.com si no tienes.
2. Botón verde "New" → nombre `pa-despacho` → marca **Private** → Create.
3. En la página del repo vacío: "uploading an existing file" → arrastra
   TODO el contenido del ZIP que te di (descomprimido) → Commit.
   Así de simple, sin comandos.

### PASO 3 — Render: prende el local (20 min)
1. Crea cuenta en https://render.com (puedes entrar con tu GitHub).
2. New → **Blueprint** → conecta tu repositorio `pa-despacho`.
3. Render lee el archivo `render.yaml` que ya viene en el código y te
   muestra UN solo servicio (la página; los recordatorios viven adentro).
   Dale crear.
4. Te va a pedir llenar unas casillas (las variables). AQUÍ es donde pegas:
   - `MASTER_ENCRYPTION_KEY` → tu llave de la caja fuerte
   - `SECRET_KEY` → la otra llave
   - `DATABASE_URL` → la cadena del paso 1
   - `S3_ENDPOINT_URL`, `S3_REGION`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` → del paso 1
   - Las demás ya vienen prellenadas.
5. Espera a que diga "Live" (5-10 min la primera vez).

### PASO 4 — Crea tu usuario Director (2 min)
En Render, en el servicio `pya-api` hay una pestaña **Shell** (una
pantallita negra). Escribes UNA sola línea y Enter:
```
python crear_director.py "Rodolfo Pacheco" rodolfo@tucorreo.com
```
Te pide inventar una contraseña (no se ve mientras la escribes, es normal).

### PASO 5 — Tu 2FA (2 min, ya es visual)
Abres `https://pya-api.onrender.com/equipo` (Render te da esa dirección),
tocas "configurar mi código 2FA", escaneas el QR con Google Authenticator
y listo. Ya dentro, desde Administración das de alta a Artemisa, Pao,
los contadores y los clientes CON PUROS CLICS.

### PASO 6 — El dominio bonito (cuando quieras, 10 min + espera)
1. Compra el dominio (Namecheap ~$12 USD/año).
2. En el panel del dominio: agregar registro **CNAME**: nombre `despacho`,
   valor `pya-api.onrender.com`.
3. En Render: Settings → Custom Domains → agregas
   `despacho.tudominio.com`. El candadito HTTPS sale solo.
Mientras tanto, la dirección de Render funciona perfectamente.

---

## ¿Puedo probar sin pagar? SÍ
El `render.yaml` viene en **plan free**: $0. El único inconveniente es que
el servicio se duerme si nadie lo usa 15 minutos y tarda ~50 segundos en
despertar la próxima vez. Suficiente para afinar todo con calma.
Cuando ya lo vayas a abrir a los clientes: Render → tu servicio → Settings
→ Instance Type → **Starter ($7/mes)**. Un clic, sin perder datos ni
volver a configurar nada.

## ¿Cuánto cuesta al mes?
- Supabase: $0 (plan gratuito alcanza para arrancar)
- Render: $7 USD (un solo servicio; los recordatorios corren adentro)
- Dominio: ~$1 USD prorrateado
**Total: ~$8 USD/mes.**

## Si algo truena
Cópiame el mensaje de error tal cual (o captura de pantalla) y lo
resolvemos juntos aquí. Los tropiezos típicos son: contraseña de la base
con caracteres raros (resétala a una sin símbolos), o una variable pegada
con un espacio de más al final.
