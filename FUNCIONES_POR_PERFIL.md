# P&A Despacho Contable — Funciones por perfil
### Documento de referencia para el diseño (pafirma.com)

Este documento lista **todo lo que cada perfil puede hacer**, extraído del código
en funcionamiento. Sirve para verificar que ninguna función se pierda al
rediseñar la interfaz.

---

## ⚠ Antes de tocar el HTML: lo que NO se puede romper

La lógica está atada a los **identificadores (`id`) y clases** de los elementos.
Si el rediseño reescribe el HTML sin conservarlos, los botones dejan de
funcionar (ya nos pasó: un botón que "no hacía nada" resultó ser un endpoint con
el permiso equivocado).

**Reglas para el rediseño:**
1. **Conservar todos los `id` y las clases que aparecen en este documento.** El
   diseño puede cambiar por completo alrededor de ellos.
2. Los `id` que empiezan con `nav-`, `sub-vista`, `contenido` sostienen la
   navegación entera.
3. Las clases `.chip`, `.carta`, `.campo`, `.btn`, `.btn-azul`, `.btn-linea`,
   `.micro`, `.tnum`, `.oculto`, `.etiqueta`, `.kpi`, `.fila` son el sistema de
   diseño: se pueden reestilizar libremente, pero **no renombrar**.
4. La paleta vive en variables CSS (`--azul`, `--marino`, `--papel`, `--tarjeta`,
   `--borde`, `--tinta`, `--gris`, `--gris2`, `--rojo`, `--ambar`, `--verde`, y
   sus variantes `-suave` / `-borde`). Cambiar los valores es seguro; quitar las
   variables no.
5. **Sin modo oscuro.** Se probó y se descartó.
6. Tipografías actuales: `Public Sans` (interfaz) y `Libre Caslon Text` (títulos,
   clase `.serif`).

---

## Los seis perfiles

| Perfil | Persona | Rol técnico | Pantalla de inicio |
|---|---|---|---|
| **Administrador** | Luis | `administrador` | Panel (todas las secciones) |
| **Director** | C.P. Rodolfo Pacheco | `director` | Panel → Tablero |
| **Supervisora** | Artemisa | `supervisor` | Panel → Kiosco |
| **Contador** | Carlos y equipo | `contador` | Trabajo del despacho |
| **Secretaria** | Pao | `admin_secretaria` | Kiosco de cobranza |
| **Cliente** | Grupo Norte, etc. | `cliente` | Portal (`/clientes`) |

Los cinco perfiles internos entran por `/equipo`. El cliente, por `/clientes`.

---

## Navegación: una sola barra, filtrada por rol

El panel interno (`panelPrincipal`) pinta una barra de secciones. **Cada rol ve
solo las suyas.** Agregar una sección es una línea en el arreglo `SECCIONES`.

| Sección | `id` del botón | Administrador | Director | Supervisora | Contador | Secretaria |
|---|---|:--:|:--:|:--:|:--:|:--:|
| Kiosco de cobranza | `nav-kiosco` | ✓ | ✓ | ✓ | — | ✓ |
| Tablero | `nav-tablero` | ✓ | ✓ | — | — | — |
| Trabajo del despacho | `nav-trabajo` | ✓ | ✓ | ✓ | ✓ | ✓ |
| Autorizaciones | `nav-autoriza` | ✓ | ✓ | ✓ | — | — |
| Cálculo de impuestos | `nav-calculos` | ✓ | ✓ | ✓ | ✓ | ✓ |
| IMSS y nóminas | `nav-patronal` | ✓ | ✓ | ✓ | ✓ | ✓ |
| Obligaciones | `nav-obligaciones` | ✓ | ✓ | ✓ | — | — |
| Saldos a favor | `nav-saldos` | ✓ | ✓ | ✓ | ✓ | ✓ |
| Certificados | `nav-certs` | ✓ | ✓ | ✓ | ✓ | ✓ |
| Respaldos | `nav-respaldos` | ✓ | ✓ | ✓ | ✓ | ✓ |
| Administración | `nav-admin` | ✓ | ✓ | — | — | — |
| **Total** | | **11** | **11** | **9** | **6** | **7** |

El chip de Autorizaciones lleva un contador de pendientes (`id="n-autoriza"`).

---

# ADMINISTRADOR (Luis) — 11 secciones

Acceso técnico total. Ve y hace **todo** lo que hace cualquier otro perfil, más
la administración del sistema. No tiene pantallas exclusivas: su valor es que
nada le queda cerrado.

---

# DIRECTOR (Papá) — 11 secciones

Acceso completo al despacho. Las mismas 11 secciones que el Administrador.

## Tablero (`subTablero`) — exclusivo de Director y Administrador

- **Tres indicadores grandes** (clase `.kpi`, contenedor `id="kpis"`):
  - Contabilidades cerradas (% y "X de Y clientes")
  - Impuestos enviados (X/Y, "línea de captura ya con el cliente")
  - Eficiencia de entrega (minutos del cierre contable al envío)
- **Aviso de autofirmas** (`id="autofirmas"`): lista los cálculos que su propio
  autor autorizó (la Supervisora puede hacerlo). Franja ámbar a la izquierda.
  Texto: *"no pasaron por un segundo par de ojos, aquí están por si quiere
  revisarlos"*. **No es una alarma, es visibilidad.**
- **Semáforo de cartera vencida**: clientes con adeudos, por antigüedad.

## Administración (`subAdmin`) — exclusivo de Director y Administrador

### Alta de cliente (formulario, `id="nc2-*"`)
Campos: nombre comercial, razón social, RFC, WhatsApp, correo · **tipo de
persona** (`nc2-persona`) y **régimen fiscal** (`nc2-regimen`, se filtra solo
según física/moral) · tipo de cliente (estándar / VIP / **confianza especial**)
· IMSS (`nc2-imss`), nómina (`nc2-nomina`) y su periodicidad · crear cuenta de
portal (`nc2-cuenta`), con contraseña opcional (`nc2-pass`).

Al crear con portal, **se muestra una vez** la contraseña temporal generada
(ej. `Balanza-6312-CM`), en un recuadro azul para copiarla.

### Alta masiva por Excel (`abrirAltaMasiva`, botón `id="btn-alta-masiva"`)
Modal de tres pasos:
1. **Descargar plantilla** (`id="am-plantilla"`): Excel con hojas CLIENTES,
   PERSONAL e INSTRUCCIONES (lista exacta de los 17 regímenes y los 5 roles).
2. **Revisar** (`id="am-revisar"`): valida **sin guardar nada**; muestra los
   errores renglón por renglón, en tarjetas rojas.
3. **Confirmar** (`id="am-confirmar"`): da de alta. Regla **todo o nada**: si un
   solo renglón falla, no entra nada.
4. **Tabla de contraseñas** (`mostrarCredenciales`): todas las temporales
   generadas, con botón "Copiar todas" (`id="am-copiar"`). Se muestran una vez.

### Lista de clientes
Cada fila muestra el **régimen fiscal**; si falta, sale en ámbar:
*"⚠ Sin régimen fiscal — la calculadora no funcionará"*. Botones por fila:
- **Editar** (`.adm-editar` → `abrirEdicionCliente`): modal con todos los campos
  corregibles. Cada cambio se guarda en la bitácora con su valor anterior
  (antes → ahora).
- **Contraseña** (`.adm-password`): genera una temporal nueva y la muestra
  (`mostrarPasswordTemporal`), con botón de copiar.
- **Suspender / Reactivar** (`.adm-estatus`).

### Alta de personal (`id="np-*"`)
Nombre, correo y **rol** (`np-rol`): contador · secretaria · supervisora ·
director · administrador. Con nota explicativa de qué puede cada uno.

### Bitácora de auditoría
Registro inmutable: quién, qué, cuándo, desde qué IP. Distingue
`autorizacion_calculo` de `autoautorizacion_calculo`.

---

# SUPERVISORA (Artemisa) — 9 secciones

**Es supervisora Y contadora.** Elabora cálculos y hace el ciclo patronal, además
de autorizar los de los demás.

## Autorizaciones (`vistaAutorizaciones`) — pantalla dividida

La función más importante del sistema. Por cada cálculo pendiente:

- **Izquierda**: la hoja de cálculo, pintada **como el papel de trabajo** —
  secciones, renglones y operadores (−, ×, =) al margen. Lo que el sistema
  calculó solo va **en azul con la etiqueta AUTO**.
- **Derecha**: la **balanza de comprobación en PDF, embebida** (`visorPDF`), para
  cotejar sin salir de la pantalla.
- **Correcciones puntuales** (`.corr-campo`, `.corr-texto`, `.corr-agregar`):
  señalar un campo específico y escribir por qué está mal.
- **AUTORIZAR** (`.btn-autorizar`, verde) — al autorizar, **la balanza queda
  vinculada al cálculo para siempre**.
- **Regresar con correcciones** (`.btn-rechazar`, rojo) — exige al menos una
  corrección puntual.

**Autofirma:** Artemisa puede autorizar lo que ella misma elaboró. Queda marcado
como `autoautorizacion_calculo` en la bitácora y aparece en el tablero del
Director. Los cálculos autofirmados se marcan con la etiqueta **AUTOFIRMADO** en
ámbar.

## Obligaciones (`vistaTableroObligaciones`)
Tabla de estatus por cliente y periodo (puntos verdes/rojos) para tomar medidas
a tiempo.

## Además: todo lo del Contador (ver abajo) y el Kiosco de Pao.

---

# CONTADOR (Carlos y equipo) — 6 secciones

**No puede autorizar sus propios cálculos** (candado por persona, no por rol).

## Trabajo del despacho (`vistaContador`)
Pantalla de inicio. Lista de sus clientes y el estado del mes. Botones:
`ir-calculos`, `ir-patronal`, `ir-saldos`, `ir-citas`. Cola de subida de
declaraciones (`btn-enviar-todo`, `bov-enviar`).

## Cálculo de impuestos (`vistaCalculos`) — el corazón del sistema

- **Selector de cliente** (`calc-cliente`). El **régimen viene del cliente**, no
  se elige aquí. Si falta, avisa en ámbar.
- **Formulario dinámico** (`id="campos-v2"`): los campos cambian según el régimen.
  Son **21 regímenes**, cada uno con su propia calculadora.
- **Hoja de cálculo** (`hojaHTML`, `id="calc-resultado"`): réplica del papel de
  trabajo del despacho. Renglones con operador al margen, totales en negrita, y
  lo automático **en azul con etiqueta AUTO**: tarifas, tasas, acumulados del
  ejercicio, saldos a favor de IVA arrastrados del mes anterior, pagos
  provisionales sugeridos.
- **"◫ Balanza a un lado"** (`calc-split`): abre la balanza de comprobación
  embebida junto a la hoja (`id="panel-balanza"`).
- **Calcular y guardar** (`calc-guardar`) · **Enviar a autorización**
  (`calc-enviar`).
- **Correcciones recibidas** (`id="calc-correcciones"`): si le regresaron el
  cálculo, aquí ve exactamente qué campo y por qué, en tarjetas rojas.

### Los 21 regímenes
**Personas físicas (12):** sueldos y salarios · actividad empresarial y
profesional · RESICO (tasa Art. 113-E automática) · RIF (bimestral, con factor de
acreditamiento de IVA) · plataformas tecnológicas (Art. 113-A) · arrendamiento
(deducción ciega 35%) · AGAPE · enajenación de bienes · adquisición de bienes ·
intereses · dividendos (piramidación 1.4286) · demás ingresos.

**Personas morales (5):** régimen general (coeficiente Art. 14) · RESICO · fines
no lucrativos · coordinados · AGAPE.

**Declaraciones anuales (4):** PF general (aplica solo el tope de deducciones
personales; detecta saldo a favor) · RESICO PF · PM general (resultado fiscal,
PTU, pérdidas) · PM RESICO.

## IMSS y nóminas (`vistaPatronal`)
Ciclo patronal completo **IDSE → SUA → SIPARE** en tres pasos con su PDF cada
uno. Desglose por concepto (cuota fija, retiro, INFONAVIT...) que se autosuma
(`btn-guardar-desglose`). Impuesto sobre nómina estatal (ISN). Nóminas
recurrentes por periodicidad.

## Saldos a favor (`vistaSaldosFavor`)

- **Remanente total disponible** del despacho, en grande y en verde.
- Por cada saldo: **monto original · aplicado · REMANENTE** (los tres visibles a
  la vez), la declaración que lo originó (número de operación + botón **ver
  comprobante**), y la fecha de prescripción.
- **Alerta de prescripción** en ámbar cuando faltan menos de 180 días (los saldos
  prescriben a los 5 años, Art. 22 CFF).
- **Aplicar saldo** (`.sf-aplicar`): monto, contra qué impuesto, en qué periodo y
  con qué número de operación. **No deja aplicar más del remanente.**
- **Historial de aplicaciones** por saldo (desplegable).
- **Registrar saldo histórico** (`sf-nuevo`) para los anteriores al sistema.

## Certificados (`vistaCertificados`)
Bóveda blindada de e.firma y CSD. Subir (`cert-subir`), descargar
(`cert-descargar`) con doble autenticación, renovar (`cert-renovar`), y vigilancia
de vencimientos.

## Respaldos (`vistaRespaldos`)
Respaldos de CONTPAQ con **rotación automática**: conserva los 3 más recientes por
cliente; al subir uno nuevo, el más viejo se borra solo. Avisa si el archivo pesa
demasiado.

## Declaración con DOS archivos (en la cola de subida)
Al presentar una declaración se suben **los dos archivos que genera el SAT**:
- **Acuse / línea de captura** (`archivo_pdf`): el formato de pago → **este es el
  que se le envía al cliente**.
- **Comprobante de la declaración** (`.cola-comprobante`): la declaración en sí →
  se guarda en el expediente.
- Más: número de operación (`.cola-operacion`) y, si hubo **saldo a favor**
  (`.cola-saldo` + `.cola-saldo-imp`), entra solo al inventario ligado a esa
  declaración.

---

# SECRETARIA (Pao) — 7 secciones

**Además de la cobranza, lleva contabilidades.** Puede elaborar cálculos, hacer el
ciclo IMSS y manejar saldos. **No autoriza.**

## Kiosco de cobranza (`vistaPao`) — su pantalla de inicio

Diseñada para operarse **sin saber de computación**: botones gigantes
(`.pao-gigante`), texto grande, un color por estado.

- **POR COBRAR** (rojo, `ir-roja`) · **EN CAMINO / EFECTIVO** (ámbar,
  `ir-amarilla`) · **PAGADO** (verde, `ir-verde`) · **CITAS** (azul, `ir-citas`).
  Cada botón lleva su contador de pendientes.
- **Buscador de clientes** por nombre.
- Acciones por cliente: **confirmar pago** (`.btn-confirmar`), **recordatorio de
  Regina** (`.btn-reco`), **activar efectivo/OXXO** (`.btn-oxxo`), **solicitar
  recolección** (`.btn-recordar`), **switch de automatizaciones** (`.btn-switch`).

> **Regla de Oro (no negociable):** los clientes marcados
> **`confianza_especial`** NUNCA reciben cobranza automática. El switch de
> automatizaciones debe respetarlo siempre.

## Citas (`vistaCitasPao`)
Agenda del despacho: confirmar (`.btn-cita-confirmar`), cancelar
(`.btn-cita-cancelar`), crear cita (`nc-crear`). Incluye el enrolamiento de 2FA
(`btn-generar-qr`, `btn-verificar-totp`).

## Además: cálculos, IMSS/nóminas, saldos, certificados y respaldos.

---

# CLIENTE (portal en `/clientes`)

Entra con su correo y la **contraseña temporal** que le entregó el despacho.

## Primer acceso: cambio obligatorio (`id="form-cambio"`)
Si entró con la temporal, el sistema lo lleva **directo** a crear la suya
(mínimo 10 caracteres). No puede usar el portal sin cambiarla.

> **Nota para el diseño:** el autoregistro por WhatsApp **está apagado** (los
> envíos son simulados; no hay canal real todavía). El login dice: *"¿Aún no tiene
> acceso? Comuníquese con el despacho y con gusto le entregamos su contraseña."*

## Portal (secciones, en orden)

### 1. Semáforo del SAT y avance de su contabilidad
Sello tri-estado y barra de progreso (pendiente / en proceso / terminado).

### 2. Sus pagos del mes (`id="seccion-pagos"`) — **lo primero que quiere ver**
Una tarjeta por cada pago, con el monto en grande:
- **Impuestos federales (SAT)** — con fecha de vencimiento y **desglose por
  concepto** desplegable (IVA, ISR, retenciones...).
- **Cuotas patronales (IMSS)** — con su desglose (cuota fija, retiro, INFONAVIT).
- **Impuesto sobre nómina (ISN)**.

Cada uno con su botón **Descargar formato de pago** (`.btn-pago`).

> **Entrega Transparente (regla del despacho):** el formato de pago del impuesto
> se le entrega al cliente **siempre**, aunque deba honorarios. El impuesto nunca
> se retiene como palanca de cobro.

### 3. Descarga rápida (`id="seccion-frecuentes"`)
Los documentos que siempre le piden: **constancia de situación fiscal**,
**opinión de cumplimiento (32-D)** y **estado de cuenta de honorarios**
(`.btn-frec`).

### 4. Certificados (`id="seccion-certificados"`)
Su e.firma y CSD, con vigencias. Descarga protegida por contraseña.

### 5. Bóveda de documentos
Su expediente completo, por categoría y periodo.

### 6. Buzón de solicitudes
Pedirle un trámite o documento al despacho (`/api/portal/solicitar-tramite`).

### 7. Citas — **viendo horarios reales**
Elige con quién (su contador, la Supervisora o el Director), qué día
(`id="cita-dia"`), y el sistema muestra **los horarios realmente libres** de esa
persona (`id="cita-slots"`, botones `.slot`, jornada 9–18 h, sin fines de semana).
Los que ya están tomados no aparecen.

---

## Resumen de pantallas a diseñar

| # | Pantalla | Quién la ve |
|---|---|---|
| 1 | Landing pública (`/`) | Todos |
| 2 | Login del equipo (`/equipo`) | Los 5 internos |
| 3 | Panel con barra de secciones | Los 5 internos |
| 4 | Tablero | Director, Administrador |
| 5 | Trabajo del despacho | Todos menos cliente |
| 6 | **Calculadora + hoja de trabajo + balanza al lado** | Contador, Pao, Artemisa, Director, Admin |
| 7 | **Autorizaciones (pantalla dividida)** | Artemisa, Director, Admin |
| 8 | IMSS y nóminas (ciclo de 3 pasos) | Todos menos cliente |
| 9 | Saldos a favor (inventario) | Todos menos cliente |
| 10 | Certificados | Todos menos cliente |
| 11 | Respaldos | Todos menos cliente |
| 12 | Obligaciones | Artemisa, Director, Admin |
| 13 | **Kiosco de Pao (botones gigantes)** | Pao, Artemisa, Director, Admin |
| 14 | Citas del despacho | Pao y superiores |
| 15 | Administración (alta, edición, personal, bitácora) | Director, Admin |
| 16 | **Alta masiva por Excel** (modal de 3 pasos) | Director, Admin |
| 17 | Login del cliente (`/clientes`) | Cliente |
| 18 | Cambio de contraseña obligatorio | Cliente |
| 19 | **Portal del cliente** (7 secciones) | Cliente |

---

## Las tres pantallas donde el diseño más importa

1. **La calculadora con su hoja de trabajo.** Debe *sentirse* como el papel de
   trabajo de toda la vida: renglones, operadores al margen, totales
   subrayados. Lo automático en azul es lo que le da confianza al contador de que
   el sistema no se inventó nada.
2. **La autorización en pantalla dividida.** Hoja de cálculo | balanza en PDF.
   Es donde el Director y Artemisa deciden. Necesita respirar.
3. **El kiosco de Pao.** Botones enormes, un color por estado, cero jerga. Si Pao
   duda un segundo, el diseño falló.
