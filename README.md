# P&A · Sistema de Gestión del Despacho Contable

Backend FastAPI + SQLAlchemy que implementa los 7 módulos del sistema,
subordinado a la **Regla de Oro: Modo Humano Primero**.

## Estructura del proyecto

```
pa_despacho/
├── app.py                  # Inicialización FastAPI (punto de entrada)
├── config.py               # Configuración central (env vars)
├── database.py             # SQLite dev / PostgreSQL prod
├── seed.py                 # Datos de prueba
├── requirements.txt
├── models/
│   └── models.py           # MÓDULO 1: 6 tablas + enums de negocio
├── routers/
│   ├── auth.py             # Login JWT por rol
│   ├── obligaciones.py     # MÓDULO 2: contadores + tablero director + semáforo
│   ├── cobranza.py         # MÓDULOS 3 y 5: panel de Pao + efectivo/OXXO/folios
│   ├── webhooks.py         # MÓDULOS 4 y 6: WhatsApp entrante/estatus + post-llamada voz
│   └── portal.py           # MÓDULO 7: Portal VIP (dashboard, bóveda, tickets)
├── services/
│   ├── reglas_negocio.py   # ⭐ REGLA DE ORO (único punto de decisión)
│   ├── whatsapp.py         # Regina: plantillas, envío, bitácora legal
│   ├── voz.py              # Prompt de identidad Regina + llamadas rezagados
│   └── auth.py             # Hash bcrypt + JWT + requiere_rol()
├── static/                 # Frontend (Tailwind CDN + Chart.js) — siguiente fase
└── uploads/                # PDFs SAT, comprobantes, bóveda documental
```

## Cómo correr el entorno local (paso a paso)

1. **Requisitos:** Python 3.11+ instalado (`python --version`).

2. **Crear entorno virtual** (aísla las dependencias del proyecto):
   ```bash
   cd pa_despacho
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS / Linux:
   source venv/bin/activate
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Cargar datos de prueba** (crea la base SQLite `pa_despacho.db` y usuarios):
   ```bash
   python seed.py
   ```

5. **Levantar el servidor:**
   ```bash
   uvicorn app:app --reload --port 8000
   ```

6. **Probar:** abre `http://localhost:8000/docs` — FastAPI genera una interfaz
   interactiva de todos los endpoints. Haz clic en "Authorize" e ingresa
   cualquiera de los usuarios del seed (ej. `luis@pya.mx` / `cambiar123`).

## Flujo de prueba sugerido

1. Login como **contador** → `POST /api/obligaciones/{id}/subir-linea-captura`
   con un PDF → observa en la consola el WhatsApp simulado de Regina.
2. Login como **director** → `GET /api/obligaciones/semaforo-cartera` →
   verás a "Ferretería Don Juan" (70 días) en rojo y "Compadre Ramírez" (95
   días) en rojo parpadeante.
3. Login como **Pao** → pestañas roja/amarilla/verde en `/api/cobranza/...`,
   prueba `solicitar-recoleccion` (genera folio PA-1001) y `confirmar-pago`.
4. Simula webhooks: `POST /api/webhooks/whatsapp/estatus` con `estatus=read`
   dos veces → el cliente aparecerá como "visto sin respuesta" en el semáforo.

## Regla de Oro (verificación)

`services/reglas_negocio.puede_automatizar_cobranza()` es el **único** punto
del código que decide si se permite cobranza automática. "Compadre Ramírez"
(Confianza_Especial) nunca recibirá recordatorios de honorarios ni llamadas
de IA — solo su línea de captura del SAT, informativa. Puedes verificarlo
llamando al disparador de voz y viendo la lista `omitidas_por_regla_de_oro`.

## Pasar a producción (siguientes pasos)

- `DATABASE_URL=postgresql+psycopg2://...` + Alembic para migraciones.
- Credenciales reales de Twilio/Meta en `.env` y `WHATSAPP_PROVIDER=twilio`.
- Configurar agente en Vapi/Retell con `PROMPT_IDENTIDAD_REGINA`.
- Servir tras HTTPS (nginx/Caddy) y cambiar `SECRET_KEY`.

## Blindaje de seguridad (v0.2)

| Control | Implementación | Verificación |
|---|---|---|
| Cifrado en reposo | `services/cifrado.py` (Fernet/AES). Todo PDF y comprobante se cifra antes de tocar disco (`.enc`); descifrado solo en memoria | Archivo en disco ilegible; descarga íntegra ✓ |
| Auditoría inmutable | Tabla `logs_auditoria` + `services/auditoria.py`. Descargas, cambios de saldo y accesos al portal quedan con usuario, IP y hora | 3 logs generados en prueba ✓ |
| JWT endurecido | Expiración techo 2 h, firma HMAC-SHA256, rol validado contra BD en cada request | Token expira en 120 min ✓ |
| Aislamiento rol Cliente | `cliente_autenticado()`: imposible consultar datos ajenos; rutas del despacho retornan 403 | 3 rutas internas bloqueadas ✓ |
| Subdominios | CORS + TrustedHost desde env (`clientes.` / `equipo.` / `api.`) | Configurable en `.env` |
| Candado producción | `seed.py` aborta si `ENVIRONMENT=production` | exit 1 ✓ |

**Antes del primer deploy:** generar `SECRET_KEY` y `MASTER_ENCRYPTION_KEY`,
respaldar la llave de cifrado en un gestor de secretos, y en PostgreSQL:
`REVOKE UPDATE, DELETE ON logs_auditoria FROM app_user;`

## v0.3 — Producción extrema

Nuevo en esta versión: cifrado a nivel de campo (RFC, montos, secretos TOTP
con Fernet + rfc_hash HMAC para búsquedas), 2FA TOTP obligatorio para el
personal interno, almacenamiento S3 privado con URLs firmadas de 5 minutos
(local prohibido en producción), cabeceras HSTS/CSP/X-Frame-Options,
HTTPS forzado, /docs desactivado en producción, panel Super-Admin/CFO
(ingresos, auditoría de solo lectura, altas/bajas, botón Trato Especial),
Celery+Redis con recordatorios anclados al vencimiento del SAT que
revalidan la Regla de Oro al ejecutarse, entrega por correo con link corto
de confirmación (/c/{token}).

Arranque completo local:
    redis-server &
    celery -A services.tareas worker -l info &
    celery -A services.tareas beat -l info &
    uvicorn app:app --reload

## v0.4 — Frontend completo

- `/equipo` (equipo.tudominio.com): login con 2FA integrado y tres vistas por rol.
  Director: KPIs, semáforo de cartera (rojo parpadeante), ingresos Chart.js,
  auditoría en vivo. Contador: lista de trabajo, carga de línea de captura con
  envío automático, trámites de clientes. Pao: menú de 3 botones gigantes
  rojo/ámbar/verde, tipografía de 22-34px, switch de automatizaciones y
  acciones de un toque (confirmar pago, código OXXO, recolección).
- `/clientes` (clientes.tudominio.com): portal VIP con sello fiscal circular
  (elemento firma), dona Chart.js del desglose de impuestos, descarga de línea
  de captura, bóveda por año y buzón de trámites.
- Identidad visual: verde tinta #16382B / papel #F1F2ED / dorado sello #A57A1F,
  tipografías Fraunces + Archivo. Accesibilidad: focus visible,
  prefers-reduced-motion respetado, roles ARIA en switches.
- En producción, apunta cada subdominio a su HTML (o usa un reverse proxy
  que sirva /static/equipo y /static/clientes según el Host).

## v0.5 — Identidad de marca real

- Logo recreado en vectorial (`static/marca/monograma.svg`) y en alta
  resolución 3200px (`logotipo.png`): óvalo azul #053EE8 con monograma PA
  en serif itálica, fiel al original del despacho.
- Rediseño completo de ambos frontends sobre la marca: azul #053EE8 +
  marino #0A1747, tipografías Source Serif 4 + Archivo, login de pantalla
  dividida con el lockup completo, cabecera con monograma.
- Cero emojis: set de íconos SVG minimalistas de trazo (check, descarga,
  clip, código de barras, camión de recolección, sobre, reloj, documento).
- El sello fiscal del portal ahora lleva el monograma PA al centro con el
  anillo de estatus 32D alrededor: marca y semáforo en una sola pieza.

## v0.8 — Rediseño UX de primer nivel

Portal VIP: Semáforo Fiscal central tri-estado (verde=32D positiva /
amarillo=línea de captura vigente por pagar / rojo=requerimiento urgente,
conmutables desde admin), Zona Express (línea de captura + estado de cuenta
de honorarios en PDF generado al vuelo con reportlab), repositorio por
carpetas anuales plegables.

Equipo: login con campo 2FA nativo (Google Authenticator); kiosco de Pao
con Buscador Universal (nombre o RFC exacto vía rfc_hash sobre datos
cifrados) y botón [Enviar Recordatorio Amable vía Regina] de un toque
—bloqueado por la Regla de Oro para trato especial—; vista de contadores
con filtros rápidos por estatus + texto y zona Drag & Drop para carga
masiva de PDFs del SAT (cola con cliente/monto/vencimiento por archivo).

Verificado: cero lógica ajena al despacho en todo el código.

## v0.9 — Diseño premium + módulo de nómina y contabilidad

- Frontend reemplazado por el diseño premium (Claude Design): CSS propio sin
  Tailwind CDN, app.js externo (compatible con la CSP estricta: nuestros
  scripts inline anteriores habrían sido bloqueados por el navegador en
  producción), landing pública en /inicio, dona de impuestos en SVG puro.
- Nuevos conceptos fiscales: el desglose del mes ahora acepta IVA, ISR,
  retenciones, ISN (impuesto sobre nómina), cuotas patronales IMSS e
  INFONAVIT — el contador los captura por archivo en la cola de carga y la
  gráfica del portal los muestra automáticamente.
- Bóveda extendida: nuevas categorías balanza_comprobacion, cedula_isn,
  propuesta_sipare y aviso_infonavit, con mes opcional para documentos
  mensuales; tarjeta "Subir a la bóveda" en la vista del contador; y
  endpoint POST /api/obligaciones/{cliente_id}/subir-documento (cifrado +
  auditoría).

## v1.0 — Agenda de asesorías (Citas)

- Nuevo modelo `Cita` + `Cliente.contador_asignado_id` (asignable desde
  admin: POST /api/admin/clientes/{id}/asignar-contador).
- Portal del cliente: sección "¿Necesita una asesoría?" — elige con quién
  (titular, su contador(a) asignado(a) destacado, o el resto del equipo),
  fecha deseada, modalidad y motivo; ve sus citas con estatus.
- Kiosco de Pao: cuarto botón gigante CITAS — confirma solicitudes (puede
  ajustar la hora), agenda directas por teléfono y cancela.
- Notificaciones: al confirmar, Regina avisa al cliente por WhatsApp y la
  persona con quien es la cita recibe correo + la ve en "Mis próximas
  citas" dentro de su panel (contador y director).
- Migración aplicada también en Supabase producción (tabla citas + RLS).
- Seed: se agregó la contadora Artemisa (artemisa@pya.mx) asignada a
  Grupo Norte para pruebas.

## v1.1 — Administración 100% visual (cero código para operar)

- Vista del Director con pestañas Tablero | Administración: alta de clientes
  y personal por formulario; por cada cliente, con un clic: asignar
  contador(a), trato especial, requerimiento urgente, suspender/reactivar;
  baja de personal e indicador de quién ya activó su 2FA.
- 2FA sin pasos técnicos: en el login, "configurar mi código 2FA" muestra el
  QR en pantalla (generado por el backend); se escanea con Google
  Authenticator y se activa capturando los 6 dígitos.
- Corrección importante: se restauraron 4 bloques de funciones del frontend
  (citas de Pao, agenda del personal, 2FA visual y panel admin) que parches
  anteriores no insertaron por anclas inexistentes; ahora con verificación
  estricta de definición+uso y auditoría de referencias huérfanas.

## v1.2 — Determinación de impuestos, Supervisora y canal de voz (Sofía)

**Rol SUPERVISOR (C.P. Artemisa):** acceso completo al trabajo contable +
autoridad para autorizar cálculos (igual que el Director; cualquiera de los
dos). 2FA obligatorio. Vista propia con chips Autorizaciones | Trabajo |
Cálculos.

**Motor fiscal (services/fiscal.py):** tarifa ISR mensual Art. 96 elevada al
periodo (límite inferior, cuota fija y tasa marginal AUTO-RELLENADOS, como
la página del SAT), persona moral por coeficiente de utilidad × 30%, IVA
16%, ISN Zacatecas 3%. Verificado contra cálculo a mano al centavo.
⚠ Verificar TARIFA_ISR_MENSUAL y TASA_ISN_ZACATECAS cada ejercicio
(expuestas en GET /api/calculos/tarifa para transparencia).

**Flujo de autorización:** contador captura datos de la balanza (CONTPAQ) →
BORRADOR → enviar (correo a Director Y Supervisora) → AUTORIZADO (con
segregación: el elaborador no puede autorizar su propio cálculo) o
RECHAZADO con correcciones puntuales por campo → corregir y reenviar →
candado: la línea de captura NO puede subirse sin cálculo AUTORIZADO
(409); al subirse, el ciclo cierra en DECLARADO.

**Canal de voz Sofía (/api/voice/):** caller-id (identifica al cliente por
número indexado y entrega nombre, título, montos frescos del mes y bandera
de Regla de Oro), update-contact (contacto alternativo del número) y
book-appointment (agenda en vivo con verificación de traslapes, escribe en
la MISMA agenda de Pao). Autenticación server-to-server por header
X-Voice-Api-Key (VOICE_WEBHOOK_API_KEY). Decisiones de diseño: los montos
NO se duplican en columnas (se leen de las tablas fuente para no
desfasarse) y no se creó tabla CitasAsesoria aparte (misma tabla citas).
Llaves .env: ELEVENLABS_API_KEY, VOICE_WEBHOOK_API_KEY, NOMBRE_ASISTENTE_VOZ.

Migraciones aplicadas a Supabase producción: supervisor_rol y
determinacion_impuestos_y_voz (tabla calculos_impuestos + RLS, campos de
telefonía, índice de Caller ID).

## v1.3 — IMSS (IDSE/SUA/SIPARE), nóminas, certificados blindados

- Ciclo patronal por cliente/mes: 3 pasos rastreables con documento de
  respaldo cada uno (emisión IDSE, cálculo SUA, propuesta SIPARE) guardados
  a perpetuidad en la bóveda; desglose de cuotas por concepto (captura
  manual, total autosumado); el FORMATO DE PAGO final se envía al cliente
  al presentarse. Sofía recibe total + desglose + ISN en caller-id.
- ISN: presentación mensual con importe y formato; aviso individual.
- Nóminas: tareas recurrentes generadas por Celery beat según periodicidad
  del cliente (semanal=viernes, quincenal=15 y último, mensual=último);
  solo se completan entregando el PDF; vencidas se marcan en rojo.
- Esquema de cobro: cada pago se informa individualmente al presentarse;
  el estado de cuenta de honorarios va con el ÚLTIMO del periodo
  (services/pagos_periodo.py), respetando la Regla de Oro.
- Tablero de supervisión (Supervisora/Director): semáforo SAT/IMSS/ISN por
  cliente, paso exacto del IMSS, responsable y nóminas pendientes.
- Certificados digitales (e.firma, CSD, sellos IMSS/estatales): cifrados,
  con vigilancia diaria de vencimientos (aviso a 30 días), solicitud de
  renovación con aviso a jefaturas, reemplazo versionado; descarga del
  personal con código TOTP tecleado al momento (step-up) y del cliente
  reconfirmando contraseña; todo auditado. Las contraseñas de las llaves
  privadas NUNCA se almacenan.
- Admin: toggles IMSS/Nómina + periodicidad por cliente.
- DESPLIEGUE_FACIL.md: guía en lenguaje llano.
- Migraciones aplicadas a Supabase producción: categorias_patronales y
  patronal_y_certificados (4 tablas nuevas + RLS).


## v1.4 — Despliegue de un solo servicio ($7/mes)

Celery+Redis sustituidos por un programador interno (APScheduler) dentro
del propio servicio web: las 3 rutinas diarias (tareas de nómina 6:00,
vigilancia de certificados 6:30, recordatorios SAT 9:30, hora de
Zacatecas) corren en el proceso, sin worker ni Redis. Reversible con
USAR_PROGRAMADOR_INTERNO=false. La raíz (/) sirve la landing para
www.pafirma.com; el chequeo técnico vive en /salud.

## v2.0 — Motor fiscal por régimen, pantalla dividida, portal completo, modo oscuro

**Motor fiscal v2 (services/fiscal_v2.py):** réplica de los papeles de trabajo
del despacho, verificada al centavo contra los Excel reales:
- pf_actividad_empresarial · pf_resico · rif (bimestral) · pm_general · pm_resico
- Tarifa Art. 96 elevada al periodo; tasa RESICO Art. 113-E automática por
  ingresos; RIF con factor de acreditamiento de IVA, IVA de público en general
  y reducción por años; PM con coeficiente de utilidad Art. 14 y PTU.
- La BD acumula como las hojas: el contador captura SOLO el mes; el sistema
  suma meses anteriores, arrastra saldo a favor de IVA y sugiere pagos
  provisionales (fiscal_v2.contexto_desde_bd).
- ⚠ Verificar cada ejercicio: TARIFA_ISR_MENSUAL, TASAS_RESICO_PF, TASA_ISR_PM.

**Régimen en el cliente:** tipo_persona (fisica|moral) + regimen_fiscal definen
la calculadora. Alta con cuenta de portal opcional (contraseña de una vez) y
EDICIÓN completa (PUT /api/admin/clientes/{id}) con auditoría campo por campo
(antes → ahora). Los logs de auditoría siguen siendo lo único inmutable.

**Pantalla dividida (must):** en autorización, hoja de cálculo | balanza de
comprobación embebida lado a lado; en captura, botón "Balanza a un lado". Al
autorizar, la balanza queda VINCULADA al cálculo (huella permanente).

**Autoregistro del portal:** el cliente escribe correo/teléfono ya dados de
alta → código de 6 dígitos por WhatsApp (15 min) → crea su contraseña.
Respuesta neutra ante desconocidos (no revela quién es cliente).

**Portal del cliente:** los tres pagos del mes a primera vista con desglose y
descarga; descargas frecuentes (constancia de situación fiscal, 32D, estado de
cuenta); certificados; buzón de solicitudes; y citas eligiendo entre los
HORARIOS REALMENTE LIBRES (GET /api/citas/disponibilidad, 9-18h, sin fines de
semana) del contador asignado, la Supervisora o el Director.

**Respaldos CONTPAQ:** subida con ROTACIÓN automática (conserva los N más
recientes por cliente, N=3 configurable con RESPALDOS_CONTPAQ_A_CONSERVAR);
avisa si el archivo es muy pesado (ojo con el 1 GB del plan gratuito).

**Diseño:** modo oscuro (azul profundo, no gris) en equipo y portal, con toggle
persistente y respeto a la preferencia del sistema; paleta azul institucional
rectora; superficies por variables CSS (sin blancos fijos).

Migraciones aplicadas a producción: perfil_fiscal_clientes, autoregistro_portal,
categoria_respaldo_contpaq.

## v2.1 — Regímenes completos, saldos a favor, dos documentos por declaración

### Motor fiscal: 21 regímenes (services/fiscal_v2.py + fiscal_catalogo.py)
- **PF (12):** sueldos y salarios · actividad empresarial y profesional · RESICO
  (tasa Art. 113-E automática) · RIF (bimestral, factor de acreditamiento de IVA,
  reducción por años) · plataformas tecnológicas (Art. 113-A: 2.1/4/1%) ·
  arrendamiento (deducción ciega 35%) · AGAPE (exención PRORRATEADA al periodo) ·
  enajenación (ganancia ÷ años) · adquisición · intereses · dividendos
  (piramidación 1.4286) · demás ingresos
- **PM (5):** general (coeficiente Art. 14) · RESICO · no lucrativas ·
  coordinados · AGAPE
- **ANUALES (4):** PF general (aplica solo el tope de deducciones personales =
  el MENOR entre 5 UMA anuales y 15% del ingreso; detecta SALDO A FAVOR) ·
  RESICO PF (Art. 113-F) · PM general (resultado fiscal, PTU, pérdidas) · PM RESICO
- ⚠ VERIFICAR CADA EJERCICIO: TARIFA_ISR_MENSUAL, TARIFA_ISR_ANUAL,
  TASAS_RESICO_PF, TASA_ISR_PM, UMA_DIARIA (en fiscal_v2 y fiscal_catalogo).

### Dos documentos por declaración (routers/obligaciones.py)
Al presentar, el contador sube LOS DOS archivos que genera el SAT:
- `archivo_pdf` = **ACUSE / línea de captura** (formato de pago) → es el que se
  le envía al cliente por WhatsApp/portal.
- `comprobante_pdf` = **COMPROBANTE de la declaración** (la declaración en sí)
  → se guarda en el expediente. Indispensable si hay saldo a favor.
Más `numero_operacion`, `saldo_a_favor` e `impuesto_saldo_favor`.

### Inventario de saldos a favor (routers/saldos_favor.py)
Si la declaración arroja saldo a favor, entra SOLO al inventario, ligado a su
comprobante y número de operación. Lleva: **monto original, aplicado y
REMANENTE**; el historial de cada aplicación (cuánto, contra qué impuesto, en
qué declaración, con qué número de operación); y avisa de la **prescripción a
5 años** (Art. 22 CFF). Candados: no se puede aplicar sobre un saldo agotado ni
más de lo que queda. Estatus: disponible / agotado / en_devolucion / devuelto /
prescrito.

### Contraseña temporal (no hay canal de mensajería todavía)
WhatsApp y correo están SIMULADOS (solo log), así que el autoregistro por código
quedó APAGADO (variable `AUTOREGISTRO_ACTIVO`). En su lugar: al dar de alta, el
sistema genera una contraseña temporal LEGIBLE (ej. "Balanza-6312-CM", dictable
por teléfono) que se muestra UNA vez; el cliente DEBE cambiarla en su primer
acceso (`debe_cambiar_password`). Botón "Contraseña" por cliente para reponerla.

### Bug resuelto: la calculadora no abría
`/api/citas/clientes-agendables` tenía permiso solo para Pao → daba 403 al
contador y, como la vista carga varios endpoints juntos, tumbaba toda la
pantalla. Nuevo guardián `todo_el_personal` en services/auth.py. El mismo bug
afectaba en silencio a Certificados, Respaldos e IMSS.

### Administración (el hueco que faltaba)
Alta con tipo de persona, régimen fiscal (selector filtrado), IMSS/nómina y
cuenta de portal. Botones **Editar** (todo corregible, con auditoría campo por
campo: antes → ahora) y **Contraseña** por cliente. Los clientes sin régimen se
marcan en ámbar: la calculadora no funciona sin él.

Migraciones aplicadas a producción: perfil_fiscal_clientes, autoregistro_portal,
categoria_respaldo_contpaq, categorias_declaracion,
saldos_favor_y_password_temporal, obligaciones_comprobante_declaracion.

## v2.2 — Roles reales del despacho

**Cinco perfiles internos** (models/models.py → RolUsuario):

| Perfil | Quién | Qué puede |
|---|---|---|
| ADMINISTRADOR | Luis | **TODO**: las 11 secciones + administración. Acceso técnico total. |
| DIRECTOR | Papá | **TODO** el despacho: las mismas 11 secciones. |
| SUPERVISOR | Artemisa | 9 secciones. Es **supervisora Y contadora**: elabora cálculos, hace el ciclo IMSS, y **autoriza — incluidos los suyos**. |
| ADMIN_SECRETARIA | Pao | 7 secciones. Kiosco de cobranza (su pantalla de inicio) **+ contabilidades**: elabora cálculos, IMSS, saldos. NO autoriza. |
| CONTADOR | Equipo | 6 secciones. Elabora; **nunca autoriza sus propios cálculos**. |

### Autofirma de la Supervisora (decisión del despacho)
Artemisa puede autorizar lo que ella misma elaboró: quien revisa a los demás
responde por lo suyo. Pero **queda registrado**:
- La bitácora usa la acción `autoautorizacion_calculo` (no `autorizacion_calculo`).
- El resultado del cálculo lleva `auto_autorizado: true`.
- El **tablero del Director lista las autofirmas del periodo**, para que las vea
  sin buscarlas. No es una alarma: es visibilidad.
El CONTADOR sigue impedido de autofirmar (candado por PERSONA, `elaborado_por_id`).

### Navegación unificada
Una sola barra de secciones (`SECCIONES` en static/equipo/app.js), filtrada por
rol. Ya no hay pantallas duplicadas por perfil: agregar una sección nueva es una
línea en ese arreglo. Pao conserva su kiosco de botones gigantes como sección de
inicio, y ahora puede navegar a lo contable.

### Asignación de contador a cliente
Ahora aceptan CONTADOR, SUPERVISOR (Artemisa), ADMIN_SECRETARIA (Pao), DIRECTOR
y ADMINISTRADOR — porque todos ellos llevan contabilidades.

Migración aplicada a producción: rol_administrador (enum ADMINISTRADOR).
Seed: admin@pya.mx (Administrador) y luis@pya.mx (Director).

## v2.3 — Alta masiva por Excel (routers/importacion.py)

Para arrancar con toda la cartera de un jalón, en tres pasos:

1. **Plantilla** (`GET /api/importacion/plantilla`): Excel con tres hojas —
   INSTRUCCIONES (con la lista EXACTA de los 17 regímenes válidos y los 5
   roles), CLIENTES y PERSONAL. Cada hoja trae encabezados y una fila de
   ejemplo en amarillo.
2. **Revisión** (`POST /api/importacion/revisar`): valida TODO **sin guardar
   nada** y devuelve renglón por renglón qué está mal y por qué.
3. **Confirmación** (`POST /api/importacion/confirmar`): da de alta y devuelve
   las **contraseñas temporales** de todos (personal y clientes con portal),
   para entregarlas. Se muestran UNA vez.

**Regla de oro: todo o nada.** Si un solo renglón tiene error, no se da de alta
nada. Es preferible corregir el Excel a quedarse con media cartera cargada.

**Validaciones:** RFC (formato y duplicados, dentro del archivo y contra la
base) · régimen válido Y coherente con el tipo de persona (un `pf_arrendamiento`
marcado como "moral" se rechaza) · correos duplicados o ya existentes · portal
sin correo · contador asignado inexistente (acepta a los que vienen en la misma
hoja PERSONAL) · roles y periodicidades válidos.

**Detalle de implementación:** la fila de ejemplo se detecta por POSICIÓN
(renglón 2), no por contenido: si se comparara por texto, un cliente real cuyos
datos coincidieran con el ejemplo se perdería en silencio.

Dependencia nueva: `openpyxl==3.1.5` (ya en requirements.txt).
Permiso: solo DIRECTOR y ADMINISTRADOR.

## v2.6 — Integración CONTPAQ (agente local, solo lectura)

El SQL Server de CONTPAQi NUNCA se expone a internet: un **agente local**
(carpeta `/agente`, con sus instrucciones) lee las bases en la PC del despacho
—usuario db_datareader + DENY de escritura + conexión ReadOnly— y **empuja**
resúmenes por HTTPS con el token `AGENTE_CONTPAQ_TOKEN` (variable en Render;
sin ella, la integración responde 503: apagada por defecto).

**Tres flujos** (routers/integracion_contpaq.py → snapshots_contpaq, upsert
por cliente+tipo+periodo):
1. **Resultados visuales**: ingresos/costos/gastos por mes y rubro nivel 1,
   clasificados por Código Agrupador SAT (4xx/5xx/6-7xx) — no depende de cómo
   numere sus cuentas cada empresa.
2. **Carga social proyectada** (services/carga_social.py): ISN estatal (3%
   Zacatecas, configurable) + cuotas patronales IMSS ramo por ramo + Infonavit,
   desde la plantilla activa (SDI topado a 25 UMA). ⚠ CEAV en transición
   2023–2030: capturar TABLA_CEAV_PATRON cada ejercicio.
3. **Predicción fiscal híbrida** (services/prediccion_fiscal.py): corrige el
   sesgo de la factura global — factor de cierre histórico (% del ingreso en
   los últimos 3 días) + promedio móvil de gastos → ingreso estimado al
   cierre → ISR/IVA con **fiscal_v2 y el régimen del cliente** (la misma hoja
   del despacho, sin fórmulas paralelas). Confianza por desviación estándar
   (CV) con escenarios pesimista/central/optimista.

Frontend: la predicción aparece en la calculadora al elegir cliente; la carga
social, en IMSS y nóminas. Verificado al centavo contra cálculo manual.

## v2.7 — Predicción de TRES FUENTES + solicitud de facturas

### El motor ya no tiene "una única verdad" (services/prediccion_fiscal.py)
Tres perspectivas lado a lado, y una síntesis:
1. **Timbrado (XML tal cual)**, del ADD de CONTPAQi: lo facturado real a la
   fecha. ⚠ A mitad de mes suele mostrar una "pérdida brutal" que NO es real
   (los gastos fluyen todo el mes; la GLOBAL del público se emite al cierre):
   el motor lo advierte con todas sus letras.
2. **XML + global esperada**: proyecta el ritmo timbrado y repone la global
   con el factor histórico (si la global YA se emitió, proyecta por avance
   natural). Es la fuente que "voltea" la pérdida aparente.
3. **Histórico CONTPAQi**: la híbrida/estacional de pólizas.
La SÍNTESIS pondera (default 50/50 XML corregida/histórico, `PESO_XML_SINTESIS`)
y sobre ella corren los escenarios con su confianza. El contador ve las tres
en la calculadora y decide cuál pesa (XML que sabe que se cancelarán, etc.).
Agente: nueva fuente `bd_add` en config.ini (query al ADD con CAMPOS_ADD
ajustables vía --descubrir); detecta la global por el receptor XAXX010101000.

### Solicitud de facturas (routers/facturas.py + solicitudes_factura)
El cliente pide su factura desde el portal como la necesita (RFC, razón
social, CP, régimen del receptor, uso de CFDI, forma y método de pago,
concepto, monto opcional). El equipo la ve en su sección **Facturas** (chip
con contador de pendientes), la toma, y al timbrarla sube el PDF (+XML
opcional) → queda en la BÓVEDA del cliente (categoría factura_emitida) y la
solicitud pasa a "emitida". Rechazo solo con motivo, visible al cliente.
Migraciones aplicadas: categoria_factura_emitida (enum, separada) y
solicitudes_factura (tabla con RLS).

## v2.8 — La calculadora ANALÍTICA (petición del Director)

"No me digas cuánto: enséñame de dónde." Cuatro piezas, con regresión
verificada (los totales de los 21 regímenes NO cambiaron):

1. **Captura desglosada** (fiscal_v2.DESGLOSE_CAMPOS + CAMPOS_CAPTURA): el
   formulario ya no pide un solo "total de gastos" — pide gastos de venta,
   de administración y otros de operación (más lo que cada régimen ya
   desglosaba: ingresos 16/0/otros, compras, financieros, NO DEDUCIBLES,
   inversiones, pérdidas…). El sistema suma; el contador no trae sumadora.
2. **La hoja se lee sola**: nueva sección "Captura del periodo · papel de
   trabajo" con TODO lo tecleado renglón por renglón antes de los totales,
   y **cédulas desplegables** en los valores AUTO (la fila del total de
   gastos enseña su suma; la tasa RESICO enseña la tabla del 113-E con el
   rango aplicado marcado; las tarifas ya venían desplegadas en renglones).
3. **La predicción como punto de partida**: botón "Usar como punto de
   partida en la hoja" en la tarjeta de predicción — precarga los renglones
   (en azul) con el escenario central (`precarga_calculadora`, mapeada por
   régimen; el gasto cae en "Otros gastos de operación" para repartirse) y
   el contador le mueve desde ahí.
4. **Predicción vs autorizado**: al autorizar, el cálculo real sustituye a
   la predicción y la comparación queda en AMBOS lados — en la hoja (bloque
   "Predicción vs autorizado": predicho, rango, real, diferencia y
   PRECISIÓN %) y en el snapshot (la tarjeta de predicción muestra "ya fue
   autorizado en $X · precisión Y%"). Historial de precisión por cliente.

## v2.9 — Correcciones de producción y autorizaciones por contador

### 🔴 BUG CRÍTICO: ningún documento se podía descargar en producción
`services/almacenamiento.py` creaba el cliente boto3 SIN `signature_version`.
Contra proveedores compatibles (Supabase Storage, R2, MinIO) eso genera una
URL "firmada" **sin el parámetro X-Amz-Signature** → `AccessDenied ·
Missing signature`. No afectaba solo la balanza: tampoco abrían certificados,
líneas de captura ni nada del portal del cliente. Corregido con
`signature_version="s3v4"` + `addressing_style="path"`, **verificado
subiendo y descargando contra el Supabase real (200 OK)**.

### Otras correcciones
- **La balanza mostraba el documento equivocado**: `_balanza_del_periodo`
  tenía un fallback que devolvía CUALQUIER documento del periodo si no había
  balanza (llegó a mostrarse el PDF del IDSE rotulado como balanza).
  Eliminado: si no hay balanza, el panel lo dice con letras y ofrece subirla.
- **Se perdía el regreso al panel** (Director → Trabajo → IMSS): se pasaba
  `vistaPatronal(vistaContador)` sin su propio `volverA`. Reparadas las 4
  rutas de regreso.
- **Faltaba dónde subir la balanza**: ahora se sube desde la calculadora
  misma (botón siempre visible) y va a la bóveda del cliente.
- **IMSS, el explorador no dejaba escoger el archivo**: el `accept` era
  solo PDF, pero el SUA entrega `.sua` y varios archivos. Ahora acepta
  múltiples archivos (`.sua .pdf .txt .zip .xls…`), conserva la extensión
  real, los numera `_1/_2/_3`, y el paso 3 se llama "Pago en SIPARE".
- **Fallos silenciosos**: 4 handlers hacían `if (r.ok) recargar()` y ante un
  error no mostraban NADA (parecía que el archivo "no cargaba"). Todos
  muestran ya el motivo.

### Autorizaciones en tres niveles (`/api/calculos/por-contador`)
1. **Contadores** con su avance x/xx y barra de progreso; píldoras de
   "espera su firma" / "le faltan"; los que están **al corriente se van al
   fondo** (plegados) para no estorbar.
2. **Clientes de ese contador** con su punto exacto: sin elaborar,
   elaborado, espera autorización, regresado, autorizado o declarado.
3. **La pantalla de autorización de siempre**, ahora con la hoja centrada y
   ancha; al desplegar la balanza se parte en dos con **scroll
   independiente** en cada lado.

## v3.0 — Diagnóstico visible, Regina, visor PDF y obligaciones en dos vistas

### Consola de errores (lo que pidió el Director: "que mande mensajes de error")
Antes, cuando algo fallaba, la app **simplemente no hacía nada**. Ahora:
- `api()` reporta TODA respuesta de error del servidor con su motivo y la ruta.
- `window.onerror` y `unhandledrejection` capturan cualquier error de JS.
- Aparece una **consola roja abajo a la derecha** con el detalle, botón de
  copiar (para reportarlo) y las últimas 25 fallas.
- En el portal del cliente, el equivalente discreto: aviso en su idioma.
- **Ninguna pantalla puede quedar muerta**: `abrirCompletaSegura` envuelve
  IMSS, calculadora, kiosco y trabajo; si truenan, muestran el motivo y un
  botón para regresar al panel, en vez de dejar la pantalla congelada.

### Visor de PDF corregido
La URL firmada de Supabase se sirve como DESCARGA, y por eso el navegador se
negaba a mostrarla dentro de la página ("no muestra PDF embebido"). Ahora el
documento se trae y se muestra **desde memoria (blob)**, que sí se incrusta:
la pantalla dividida balanza/papel de trabajo funciona de verdad.

### Regina (antes Victoria)
Renombrada la asistente en TODO el proyecto (código, prompts de voz, mensajes
de WhatsApp, config, documentación). Cero referencias a Victoria.

### Obligaciones con dos miradas
- **Por cliente**: cada uno con sus puntos SAT/IMSS/ISN y nóminas; al tocarlo
  se despliega QUÉ falta exactamente ("IMSS: falta cálculo SUA, pago en
  SIPARE") y quién es el responsable. Detalle a un clic, sin abrumar.
- **Por contador responsable**: avance x/xx con barra, los que van al
  corriente al fondo, y bajo cada uno la lista de sus clientes con pendientes
  y el detalle de lo que falta a cada quien.

## v3.1 — Cobranza real, semáforo con criterio y expediente completo

### El semáforo lo pone una PERSONA (routers/situaciones.py)
El sistema no puede adivinar un requerimiento ni una auditoría. Ahora se
registran como *situaciones*, con **dos textos**: el detalle interno (solo
equipo) y el mensaje que leería el cliente. Y con una regla del despacho:
**el contador registra, pero encender el rojo del portal lo autoriza la
Supervisora o el Director.** Si no se marca visible, el cliente no ve nada:
los asuntos graves se avisan hablando, no con un foquito. Verificado que el
detalle interno JAMÁS se filtra al portal.

### ¿Ya se pagó? (comprobantes y complementarias)
- El **cliente sube su comprobante** desde su portal (PDF o foto) con la
  referencia del banco. El semáforo pasa a verde y el equipo lo ve al momento.
- El **equipo también puede registrarlo** desde el panel del contador.
- **Declaraciones complementarias**: como la obligación es única por
  cliente+mes+año, la complementaria SUSTITUYE a la vigente y **archiva la
  anterior** (montos, acuse, comprobante y pago) en `historial_complementarias`.
  El expediente conserva las dos.

### Cobranza con datos reales
- Alta de cliente (formulario Y plantilla Excel): **honorario, periodicidad,
  día de corte y adeudo previo con su concepto**. Sin esto la cobranza estaba
  de adorno.
- **Adeudos previos** con abonos y saldo (`AdeudoPrevio`).
- **Estado de cuenta en PDF** con el membrete del despacho: honorarios del
  ejercicio con su estatus, adeudos anteriores, totales y SALDO POR PAGAR,
  formas de pago y nota legal. Lo descarga el equipo **y el cliente**
  (Entrega Transparente: se entrega siempre, deba o no deba).

### Expediente del cliente (nuevo módulo)
- **Para el equipo**: TODO su rastro documental agrupado por ejercicio, con
  visor integrado, sus situaciones, sus adeudos, sus balances y su estado de
  cuenta — todo en una pantalla. Se abre desde Administración.
- **Para el cliente**: su bóveda ya NO tiene paja. Solo ve lo suyo
  (constancias, formatos de pago, facturas, recibos, sus comprobantes). El
  papel de trabajo interno (balanzas, SUA, respaldos) se conserva pero no se
  le muestra. Si pide verlo todo, se enciende `boveda_completa`.

### Resumen financiero honesto
Activo / pasivo / capital en el portal **solo si el despacho emitió un estado
financiero**. Si no existe, el módulo no aparece: cero cifras inventadas. Al
capturarlo se valida que el balance cuadre (activo = pasivo + capital).

### Otros
- Bases de CONTPAQi capturables por cliente desde Administración y el Excel.
- **Nóminas pendientes en el panel del contador** (con las vencidas en rojo),
  para no enterarse hasta cerrar el mes.

## v3.2 — Los huecos que quedaban

Auditoría contra la lista completa. Lo que faltaba de verdad:

- **Los campos de cobranza solo existían en el ALTA.** Los clientes ya dados
  de alta (incluidos los de producción) no tenían honorario y NO había forma
  de ponérselo: la cobranza seguía sin datos para ellos. Ahora el expediente
  trae una tarjeta **"Cobranza y CONTPAQ" editable** (honorario, periodicidad,
  día de corte, las tres bases de CONTPAQi, coeficiente de utilidad y el
  acceso ampliado a la bóveda). Solo la edita el Director/Administrador; los
  demás la ven en modo lectura.
- **El historial de complementarias no se veía en ningún lado.** El expediente
  ahora lista cada periodo corregido con su motivo, el monto vigente y **las
  versiones anteriores** (monto, si estaba pagada, quién la archivó).
- **Descarga directa** en el expediente (antes solo se podían ver): botón
  "bajar" que trae el archivo real, además del visor.

## v3.3 — Los errores reportados en producción

### 🔴 "Failed to fetch" en TODOS los documentos: era CORS
El servidor devolvía la URL firmada de Supabase y el navegador la bloqueaba
por ser **otro dominio** (por eso "abrir en otra pestaña" sí funcionaba y el
visor no). Ahora el archivo **lo sirve el backend** (`respuesta_archivo`),
mismo origen: se incrusta, se descarga y la pantalla dividida funciona.
Corregido en los 6 endpoints de descarga.

### 🔴 IMSS no abría: `ETQ_CUOTAS is not defined`
Al rediseñar el caminito de pasos borré la tabla de conceptos del desglose
patronal. Restituida (los mismos ramos que calcula `carga_social.py`).

### 🔴 "Not authenticated" en el estado de cuenta
`window.open` no manda el token. Ahora se descarga con la sesión
(`descargarConSesion`) y se abre desde memoria.

### 🔴 "Cannot set properties of null" (Tablero)
Era una carrera: si navegas mientras una pantalla carga, el elemento ya no
existe cuando llega la respuesta. Añadido un **nodo fantasma** que absorbe
esas escrituras sin romper nada, en ambos frontends.

### 🔴 La cobranza salía vacía: NADIE generaba los cobros
Se capturaba el honorario pero nada creaba el cargo del mes.
`POST /api/cobranza/generar` los crea desde el honorario contratado
(idempotente, respeta periodicidad y día de corte) y `GET /api/cobranza/resumen`
muestra facturado, por cobrar, adeudos anteriores y **quién no tiene
honorario capturado**. Con su botón en el kiosco.

### 🔴 La contraseña de un solo uso no servía
Al corregir el correo del cliente **no se actualizaba el de su cuenta de
acceso**: el cliente quedaba entrando con un correo que la cuenta no tenía.
Ahora (1) el correo se **valida** al alta y a la edición, (2) corregirlo
**arrastra la cuenta**, (3) `regenerar-password` dice con qué correo entrar y
avisa si están desemparejados, y (4) hay `/api/admin/cuentas-desincronizadas`
+ `emparejar-correo` para reparar los casos viejos.
*(En producción se encontró `matiasfelix@gmail,com` —con coma— y se corrigió.)*

### Dar fe del trabajo hecho fuera del sistema
Si la app falla o no hay internet, el contador sigue trabajando (manda la
línea por WhatsApp, entrega en mano). Un **mando** (Supervisor/Director/Admin)
verifica que sí se hizo, con su nombre y su motivo, y marca si faltan
documentos — que se suben después y **apagan solos** el aviso. El cliente no
se preocupa de balde ni el contador aparece incumplido.

### Saldos a favor: personales, editables y en la calculadora
- **Ya no se suman entre clientes**: el saldo a favor es personal e
  intransferible. Sin filtro se agrupa por cliente; con `cliente_id` se
  totaliza solo el suyo.
- **Editables** (`PUT /api/saldos-favor/{id}`) para errores de dedo, con
  candado: no se puede bajar el monto por debajo de lo ya aplicado.
- **Anexados a la calculadora**: al elegir cliente aparecen SUS saldos, con
  "aplicar aquí" y "corregir" sin salir de la hoja.

## v3.4 — Prueba de humo del frontend (y el bug que encontró)

### La prueba que faltaba: `pruebas/humo_frontend.js`
`node --check` valida sintaxis y la auditoría revisa identificadores del HTML,
pero **ninguna de las dos ejecuta las pantallas**. Por eso
`ETQ_CUOTAS is not defined` llegó a producción y dejó el IMSS sin abrir.

Ahora hay una prueba que monta un navegador simulado (DOM y `fetch` con las
respuestas EXACTAS de cada endpoint) y **llama a cada pantalla** del panel y
del portal, reportando referencias rotas y errores en tiempo de ejecución.

```
node pruebas/humo_frontend.js     # sale con código 1 si algo truena
```

### 🔴 Lo que encontró de inmediato: `$$` no existía en el portal
Cinco funciones del portal del cliente usaban `$$(...)` —que nunca se
definió— y tronaban **en silencio**, porque el error caía dentro de una
promesa. Estaban rotos, sin que nadie lo notara:
- los botones de pago de **IMSS e ISN** (`.btn-pago`),
- la **descarga rápida** de constancias (`.btn-frec`),
- la descarga de **certificados** (`.cert-bajar`),
- los **horarios de cita** seleccionables (`.slot`).

Corregido. Las 19 pantallas (14 del panel + 5 del portal) corren limpias.
