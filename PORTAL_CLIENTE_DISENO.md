# Portal del cliente — P&A Despacho Contable
### Documento de referencia para el diseño (pafirma.com/clientes)

Extraído del código en funcionamiento. Archivos:
`static/clientes/index.html` + `static/clientes/app.js`

---

## Quién lo usa y en qué estado mental llega

El cliente **no es contador**. Es el dueño de una ferretería, un médico con
consultorio, un ranchero. Entra al portal con una de tres preguntas en la cabeza:

1. **"¿Cuánto tengo que pagar y dónde está el papel para pagarlo?"** ← la más
   frecuente, con diferencia.
2. **"¿Ya está lista mi contabilidad o voy tarde con el SAT?"**
3. **"Necesito mi constancia / mi 32-D / mi e.firma."**

Todo lo demás es secundario. **El diseño debe responder la pregunta 1 antes de
que el cliente tenga que buscar nada.**

---

## ⚠ Tres problemas actuales que el rediseño debería resolver

### 1. El orden de las secciones está mal
Hoy el portal se lee así, de arriba abajo:

1. Semáforo fiscal (sello grande)
2. Zona Express (2 botones)
3. Impuestos (gráfica de dona)
4. Bóveda de documentos
5. **Sus pagos del mes** ← *lo que el cliente vino a buscar, en quinto lugar*
6. Descarga rápida
7. Certificados
8. Citas
9. Buzón de solicitudes

**Los pagos del mes deberían ir primero o segundo.** El código incluso lleva un
comentario que dice *"lo primero que el cliente quiere ver"*, pero quedó pintado
abajo.

### 2. Hay tres bloques que hacen casi lo mismo
- **Zona Express** (botones `btn-linea`, `btn-estado`): línea de captura del SAT
  + estado de cuenta de honorarios.
- **Sus pagos del mes** (`seccion-pagos`): tarjeta por cada pago (SAT, IMSS, ISN)
  con su botón de descarga.
- **Descarga rápida** (`seccion-frecuentes`): constancia, 32-D, estado de cuenta.

La línea de captura y el estado de cuenta aparecen **dos veces**. Conviene
consolidar: **un solo bloque de "sus pagos"** (con los formatos de pago) y **un
solo bloque de "sus documentos"** (constancia, 32-D, estado de cuenta).

### 3. Copy que promete algo que hoy no ocurre
Dos mensajes dicen que la asistente avisará **por WhatsApp**:
- Al agendar cita: *"Nuestra asistente le confirmará el horario por WhatsApp"*.
- Al pedir un trámite: *"Le avisaremos por WhatsApp en cuanto esté lista"*.

**El canal de WhatsApp todavía no existe** (los envíos están simulados en el
código: solo escriben en un log). Hay que suavizar el copy —*"el despacho se
pondrá en contacto con usted"*— hasta que se conecte de verdad.

---

## Lo que NO se puede romper

La lógica está atada a los `id` y las clases. El diseño puede cambiar por
completo alrededor de ellos, pero **si desaparecen, el portal deja de funcionar**.

**Clases del sistema de diseño** (reestilizar sí, renombrar no):
`.btn` · `.btn-azul` · `.campo` · `.etiqueta` · `.micro` · `.serif` · `.tnum` ·
`.oculto` · `.seccion` · `.portal` · `.login`

**Variables CSS** (cambiar los valores es seguro; quitarlas no):
`--azul` `--azul-h` `--azul-suave` `--marino` `--papel` `--tarjeta` `--borde`
`--tinta` `--gris` `--gris2` `--rojo` `--ambar` `--verde`

**Sin modo oscuro.** Se probó y se descartó.

**Tipografías:** `Public Sans` (interfaz) · `Libre Caslon Text` (títulos, `.serif`)

---

# PANTALLA 1 — Entrada (`id="vista-login"`)

## Formulario de acceso (`id="form-login"`)
- Correo (`id="email"`) y contraseña (`id="password"`)
- Botón "Entrar a mi portal"
- Mensaje de error (`id="login-error"`)
- Nota al pie: *"¿Aún no tiene acceso? Comuníquese con el despacho y con gusto le
  entregamos su contraseña."*

> **Contexto:** el cliente **no se registra solo**. El despacho le genera una
> contraseña temporal legible (ej. `Balanza-6312-CM`, pensada para dictarse por
> teléfono) y se la entrega. El autoregistro por WhatsApp está construido pero
> **apagado** hasta que exista el canal.

## Cambio de contraseña obligatorio (`id="form-cambio"`)
Si entró con la contraseña temporal, el sistema **lo lleva directo aquí** y no lo
deja pasar sin cambiarla.

- Título: "Cree su contraseña"
- Texto: *"Entró con la contraseña temporal que le dio el despacho. Por su
  seguridad, defina ahora una propia."*
- Campos: `cp-nueva` y `cp-nueva2` (mínimo 10 caracteres)
- Mensaje: `cp-msj` · Botón: `btn-cambiar` ("Guardar y entrar")

**Es la primera impresión del cliente con el sistema.** Debe sentirse cuidadosa,
no burocrática.

---

# PANTALLA 2 — El portal (`id="vista-portal"`)

## Cabecera
- Nombre de la empresa (`id="cab-empresa"`)
- Periodo actual (`id="cab-periodo"`)
- Botón de salir (`id="btn-salir"`)

---

## Sección A — Semáforo fiscal

El sello grande de estado (`id="sello"`, 216×216 px). **Tri-estado:**

| Estado | Significa |
|---|---|
| Verde | Al corriente con el SAT |
| Ámbar | Hay algo pendiente por resolver |
| Rojo | Requerimiento urgente del SAT |

- Título grande (`id="semaforo-titulo"`) y subtítulo (`id="semaforo-sub"`)
- **Barra de avance de la contabilidad del mes** (`id="progreso-barra"` +
  `id="progreso-texto"`): pendiente (10%) → en proceso (55%) → terminado (100%)

Es el "¿estoy bien o estoy mal?" de un vistazo. Debe leerse desde el otro lado
del escritorio.

---

## Sección B — **Sus pagos del mes** (`id="seccion-pagos"`) ★ LA MÁS IMPORTANTE

Se oculta si no hay pagos cargados. Contenedor: `id="lista-pagos"`.

Una tarjeta por cada pago, **con el monto en grande**:

| Concepto | Qué trae |
|---|---|
| **Impuestos federales (SAT)** | Monto · fecha de vencimiento · desglose por concepto (IVA, ISR, retenciones…) · botón de descarga |
| **Cuotas patronales (IMSS)** | Monto · desglose (cuota fija, retiro, INFONAVIT…) · botón de descarga |
| **Impuesto sobre nómina (ISN)** | Monto · botón de descarga |

- El desglose va en un desplegable ("Ver desglose").
- Botón por tarjeta: **"Descargar formato de pago"** (clase `.btn-pago`).
- La fecha de vencimiento se marca en ámbar.

> ### Entrega Transparente — regla inviolable del despacho
> **El formato de pago del impuesto se le entrega al cliente SIEMPRE**, aunque
> deba honorarios al despacho. El impuesto **nunca** se retiene como palanca de
> cobro. El diseño no debe insinuar lo contrario en ningún estado (nada de
> "desbloquee su documento", "pague para continuar", candados, etc.).

---

## Sección C — Sus impuestos (gráfica)

- Monto total del mes en grande (`id="impuesto-total"`, con `id="impuesto-periodo"`)
- **Gráfica de dona** (`id="dona"`) con el total al centro (`id="dona-total"`) y
  su leyenda (`id="leyenda"`)
- Si aún no hay desglose: `id="sin-desglose"` → *"El desglose aparecerá aquí
  cuando su contador cierre el mes."*

**Nota:** esta sección se traslapa con la anterior. Considerar fusionarlas: la
dona podría vivir *dentro* de la tarjeta del pago del SAT.

---

## Sección D — Zona Express

Bloque azul marino, alto contraste. Dos botones:
- **Línea de captura del SAT** (`id="btn-linea"`)
- **Estado de cuenta de honorarios** (`id="btn-estado"`)
- Aviso: `id="aviso-express"`

**Nota:** duplica funciones de las secciones B y E. Candidata a desaparecer o a
fundirse con ellas.

---

## Sección E — Descarga rápida (`id="seccion-frecuentes"`)

Contenedor: `id="lista-frecuentes"`. Los documentos que **siempre le piden** al
cliente, cada uno como botón (clase `.btn-frec`):

- **Constancia de situación fiscal**
- **Opinión de cumplimiento (32-D)**
- **Estado de cuenta de honorarios**

Cada botón muestra el nombre y el periodo del documento. Si no hay ninguno:
*"Su despacho aún no ha cargado estos documentos. Puede solicitarlos en el buzón."*

---

## Sección F — Bóveda de documentos (`id="boveda"`)

*"Su expediente, siempre a un clic."* Documentos por categoría y periodo:
acta constitutiva, balanzas, acuses del SAT, comprobantes de declaración,
estados financieros… Vacía: `id="boveda-vacia"`.

---

## Sección G — Certificados (`id="seccion-certificados"`)

*"Sus certificados y firmas."* Lista: `id="lista-certificados"`.

Su **e.firma** y **sellos digitales (CSD)**, con sus vigencias.

> **Seguridad:** cada descarga **le vuelve a pedir la contraseña**. El diseño debe
> comunicar esa protección como un cuidado del despacho hacia él, no como un
> estorbo. Copy actual: *"Por su seguridad, cada descarga le pedirá reconfirmar su
> contraseña."*

Los certificados por vencer deben verse. Es el documento más delicado que existe:
con la e.firma se puede firmar en nombre de la empresa.

---

## Sección H — Citas (`id="form-cita"`)

*"¿Necesita una asesoría?"*

- **Sus citas ya agendadas** (`id="mis-citas-lista"`)
- **¿Con quién?** (`id="cita-con"`): su contador asignado, la Supervisora o el
  Director
- **Día** (`id="cita-dia"`)
- **Modalidad** (`id="cita-modalidad"`): en la oficina · videollamada · por teléfono
- **★ Horarios disponibles** (`id="cita-slots"`): al elegir persona y día, el
  sistema muestra **las horas realmente libres** de esa persona (botones `.slot`,
  jornada 9–18 h, sin fines de semana). Las ya tomadas **no aparecen**. El
  horario elegido se marca en azul.
- Motivo (`id="cita-motivo"`, opcional)
- Confirmación: `id="cita-ok"` + `id="cita-ok-titulo"` + botón `id="btn-otra-cita"`

Esto es de lo mejor que tiene el portal: el cliente **agenda viendo**, no a
ciegas. Merece un diseño que lo luzca.

---

## Sección I — Buzón de solicitudes (`id="form-tramite"`)

*"¿Necesita un trámite?"*

- Tipo (`id="tipo-tramite"`): constancia de situación fiscal · opinión 32-D ·
  copia certificada del acta constitutiva · estado financiero del ejercicio · otro
- Detalles (`id="detalle-tramite"`, opcional)
- Confirmación: `id="tramite-ok"` + `id="tramite-ok-titulo"` + botón
  `id="btn-otro-tramite"`

---

## Endpoints que consume el portal

| Endpoint | Para qué |
|---|---|
| `POST /api/auth/login` | Entrar (devuelve `debe_cambiar_password`) |
| `POST /api/auth/cambiar-password` | Cambio obligatorio en el primer acceso |
| `GET /api/portal/dashboard` | Semáforo, avance, pagos del mes, descargas frecuentes |
| `GET /api/portal/boveda` | Expediente completo |
| `GET /api/portal/boveda/{id}/descargar` | Bajar un documento |
| `GET /api/portal/linea-captura/{año}/{mes}/descargar` | Formato de pago del SAT |
| `GET /api/portal/estado-cuenta/{año}/{mes}/descargar` | Estado de cuenta de honorarios |
| `POST /api/portal/solicitar-tramite` | Buzón |
| `GET /api/certificados/mios` | Sus certificados |
| `GET /api/certificados/mios/{id}/descargar` | Descarga con contraseña |
| `GET /api/citas/opciones` | Con quién puede agendar |
| `GET /api/citas/disponibilidad` | **Horarios realmente libres** |
| `POST /api/citas/solicitar` | Agendar |
| `GET /api/citas/mis-citas` | Sus citas |

---

## Orden propuesto para el rediseño

1. **Semáforo fiscal** — ¿estoy bien o mal?
2. **Sus pagos del mes** — cuánto y dónde está el papel *(con la dona integrada)*
3. **Descarga rápida** — constancia, 32-D, estado de cuenta
4. **Certificados** — e.firma y sellos
5. **Bóveda** — el expediente completo
6. **Citas** — con horarios reales
7. **Buzón** — pedir un trámite

*(La Zona Express desaparece: sus dos botones ya viven en 2 y 3.)*

---

## El criterio

El cliente de este despacho recibe hoy sus impuestos **por WhatsApp, en un PDF
suelto**, y le pregunta a su contador por teléfono si ya está lista su
contabilidad. El portal existe para que deje de tener que preguntar.

Si el cliente entra, **ve su monto y su botón de descarga sin desplazarse**, y se
sale tranquilo: el diseño funcionó. Si tiene que buscar, no.
