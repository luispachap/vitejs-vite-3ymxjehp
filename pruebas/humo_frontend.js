/* ============================================================================
   PRUEBA DE HUMO DEL FRONTEND
   ============================================================================
   Por qué existe: el bug "ETQ_CUOTAS is not defined" dejó la pantalla del
   IMSS SIN ABRIR en producción. Ni `node --check` (que solo valida sintaxis)
   ni la auditoría de identificadores del HTML lo detectaron, porque el error
   solo aparece cuando la función SE EJECUTA.

   Qué hace: monta un navegador de mentiras (DOM y fetch simulados), llama a
   CADA pantalla del panel y del portal, y reporta cualquier referencia rota,
   propiedad de null o error en tiempo de ejecución.

   Uso:  node pruebas/humo_frontend.js
   Sale con código 1 si alguna pantalla truena (para poder encadenarlo).
   ========================================================================= */
const fs = require("fs");
const path = require("path");

const RAIZ = path.join(__dirname, "..");
const fallos = [];

/* --- Navegador de mentiras -------------------------------------------- */
function construirEntorno(datosPorRuta) {
  const registro = {};
  function nodo(id) {
    if (!registro[id]) {
      registro[id] = {
        id, _html: "", textContent: "", value: "", checked: false,
        disabled: false, files: [], onclick: null, onchange: null,
        style: {}, dataset: {},
        get innerHTML() { return this._html; },
        set innerHTML(v) { this._html = String(v); },
        classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
        addEventListener() {}, removeEventListener() {},
        querySelector: () => nodo("hijo"), querySelectorAll: () => [],
        closest: () => nodo("padre"), insertAdjacentHTML() {},
        appendChild() {}, remove() {}, reset() {}, click() {}, focus() {},
        setAttribute() {}, getAttribute: () => null,
        firstElementChild: null, children: [],
      };
    }
    return registro[id];
  }
  const g = {
    document: {
      querySelector: (s) => nodo(String(s).replace(/^#/, "")),
      querySelectorAll: () => [],
      getElementById: (id) => nodo(id),
      createElement: () => nodo("creado_" + Math.random()),
      body: { appendChild() {} },
      addEventListener() {},
    },
    window: { location: { pathname: "/equipo", href: "" }, scrollTo() {},
              addEventListener() {}, open() {} },
    navigator: { clipboard: { writeText() {} } },
    sessionStorage: {
      getItem: (k) => ({ pya_equipo_token: "T", pya_equipo_rol: "director",
                         pya_equipo_nombre: "Prueba", pya_token: "T" }[k] || null),
      setItem() {}, removeItem() {},
    },
    setTimeout: (f) => { try { f(); } catch (e) {} return 0; },
    clearTimeout() {}, alert() {}, confirm: () => false, prompt: () => null,
    URL: { createObjectURL: () => "blob:x", revokeObjectURL() {} },
    FormData: class { append() {} },
    Blob: class { constructor() {} },
    fetch: async (ruta) => {
      let datos = [];
      for (const clave in datosPorRuta) {
        if (String(ruta).includes(clave)) { datos = datosPorRuta[clave]; break; }
      }
      return {
        ok: true, status: 200,
        headers: { get: () => "application/json" },
        json: async () => datos,
        blob: async () => ({}),
        clone() { return this; },
      };
    },
    // OJO: NO se sustituye console — si no, la propia prueba enmudece.
  };
  g.localStorage = g.sessionStorage;
  return { global: g, registro };
}

/* --- Respuestas realistas para cada endpoint -------------------------- */
const RESPUESTAS_EQUIPO = {
  "/api/patronal/imss": [{
    cliente_id: 1, cliente: "Grupo Norte", emision_idse_hecha: true,
    calculo_sua_hecho: true, sipare_presentado: true, notificado_cliente: false,
    total_a_pagar: 6800, desglose_cuotas: { cuota_fija: 3500, retiro: 1200 },
  }],
  "/api/patronal/nominas": [{ id: 1, cliente: "Grupo Norte", cliente_id: 1,
    etiqueta: "Quincena 1", fecha_objetivo: "2026-07-15", estatus: "pendiente" }],
  "/api/patronal/tablero": [{ cliente_id: 1, cliente: "Grupo Norte",
    contador_id: 2, contador: "C.P. Artemisa", tipo_cliente: "vip",
    obligaciones: { sat: false, imss: true, isn: true }, faltantes: ["Declaración del SAT sin presentar"],
    completo: false, nominas_pendientes: 1, imss_pasos: { idse: true, sua: true, sipare: false } }],
  // Forma EXACTA que devuelve routers/obligaciones.py:tablero_director
  "/api/obligaciones/tablero-director": {
    progreso_contabilidades: { terminadas: 3, total: 5, porcentaje: 60.0 },
    impuestos_enviados: { enviados: 2, total: 5 },
    eficiencia_promedio_minutos: 45.0,
    autoautorizaciones: [{ cliente: "Grupo Norte", quien: "C.P. Artemisa",
                           total: 45000 }] },
  "/api/obligaciones/semaforo-cartera": { cartera_en_riesgo: [], monto_total: 0 },
  "/api/obligaciones/panel-contador": [{ cliente_id: 1, cliente: "Grupo Norte",
    tipo_cliente: "vip", estatus: "pendiente", monto_impuesto: 45000, enviado: false,
    obligacion_id: 1, pagado: false, pagado_por: null, referencia_pago: null,
    presentada: true, es_complementaria: false, numero_complementaria: 0,
    verificado_manualmente: false, verificado_por: null, motivo_verificacion: null,
    documentos_pendientes: false }],
  "/api/calculos/por-contador": [{ contador_id: 2, contador: "C.P. Artemisa",
    total_clientes: 3, esperando_firma: 1, pendiente_contador: 1, cerrados: 1,
    avance_pct: 33, conteo: {}, todo_listo: false,
    clientes: [{ cliente_id: 1, cliente: "Grupo Norte", tipo_cliente: "vip",
      calculo_id: 1, estatus: "en_autorizacion", total_a_pagar: 45000,
      elaborado_por: "Carlos", enviado_en: null }] }],
  "/api/calculos/pendientes": [],
  "/api/calculos/regimenes": { regimenes: { pm_general: "PM Régimen General" },
    campos: { pm_general: [["ingresos_nominales", "Ingresos nominales"]] } },
  "/api/calculos/mios": [],
  "/api/calculos/balanza-periodo": { documento_id: null, hay_balanza: false },
  "/api/saldos-favor": { saldos: [], por_cliente: [], nota: "x" },
  "/api/facturas": [],
  "/api/admin/clientes": [{ id: 1, nombre_comercial: "Grupo Norte",
    razon_social: "Grupo Norte SA", rfc: "GNO120101AB1", telefono: "+521",
    email: "a@b.mx", tipo_cliente: "vip", estatus: "activo",
    automatizaciones_activas: true, requerimiento_urgente: false,
    contador_asignado_id: 2, contador_asignado: "C.P. Artemisa",
    tiene_imss: true, tiene_nomina: true, periodicidad_nomina: "quincenal",
    tipo_persona: "moral", regimen_fiscal: "pm_general", tiene_cuenta_portal: true,
    honorario_mensual: 3500, periodicidad_honorario: "mensual",
    dia_corte_honorario: 5, bd_contpaq_contabilidad: null, bd_contpaq_nomina: null,
    bd_contpaq_add: null, coeficiente_utilidad: null, boveda_completa: false,
    opinion_32d_positiva: true }],
  "/api/admin/personal": [],
  "/api/admin/auditoria": [],
  // Forma EXACTA de routers/admin.py:ingresos_generales
  "/api/admin/ingresos": { anio: 2026,
    por_mes: Object.fromEntries([...Array(12)].map((_, i) =>
      [i + 1, { facturado: 10000 + i * 500, cobrado: 8000 + i * 400 }])),
    total_facturado: 153000, total_cobrado: 122400 },
  "/api/clientes/1/expediente": { cliente: "Grupo Norte", cliente_id: 1,
    ficha: { razon_social: "Grupo Norte SA", rfc: "GNO120101AB1",
      honorario_mensual: 3500, periodicidad_honorario: "mensual",
      dia_corte_honorario: 5, bd_contpaq_contabilidad: null,
      bd_contpaq_nomina: null, bd_contpaq_add: null, coeficiente_utilidad: null,
      boveda_completa: false, regimen_fiscal: "pm_general" },
    total_documentos: 1, complementarias: [],
    ejercicios: [{ anio: 2026, documentos: [{ id: 1, categoria: "balanza_comprobacion",
      nombre: "Balanza de comprobación", anio: 2026, mes: 7,
      para_el_cliente: false, subido_en: "2026-07-01" }] }] },
  "/api/situaciones": [],
  "/api/clientes/1/adeudos": [],
  "/api/clientes/1/estados-financieros": [],
  "/api/cobranza/resumen": { mes: 7, anio: 2026, clientes_activos: 3,
    honorarios_generados: 3, sin_honorario_capturado: [], facturado: 10500,
    cobrado: 3500, por_cobrar: 7000, adeudos_anteriores: 12000,
    adeudos_detalle: [{ id: 1, cliente: "Grupo Norte", cliente_id: 1,
      concepto: "2025", saldo: 12000 }] },
  "/api/cobranza/pestana": [],
  "/api/cobranza/buscar": [],
  "/api/tickets": [],
  "/api/certificados": [],
  "/api/respaldos": { respaldos: [], conservados_por_cliente: 3 },
  "/api/integracion/contpaq": {},
  "/api/importacion": {},
};

const RESPUESTAS_PORTAL = {
  "/api/portal/dashboard": {
    semaforo_sat: { estado: "verde", mensaje: "Todo en orden" },
    monto_total_impuesto: 45000, desglose_impuestos: { isr: 20000, iva: 25000 },
    pagos_del_mes: [{ concepto: "Impuestos federales (SAT)", monto: 45000,
      vence: "2026-07-17", descarga: "/x", desglose: null, obligacion_id: 1,
      pagado: false, pagado_en: null, referencia_pago: null,
      es_complementaria: false, numero_complementaria: 0 }],
    descargas_frecuentes: {}, progreso_contabilidad: { porcentaje: 80 },
  },
  "/api/portal/boveda": { 2026: [{ id: 1, categoria: "acuse_declaracion",
    nombre: "Formato de pago", mes: 7, subido_en: "2026-07-01" }] },
  "/api/portal/facturas": [],
  "/api/portal/resumen-financiero": { hay_estado_financiero: false },
  "/api/certificados/mios": [],
  "/api/citas/opciones": [{ usuario_id: 2, nombre: "C.P. Rodolfo", etiqueta: "Titular" }],
  "/api/citas": [],
};

/* --- Ejecutar cada pantalla ------------------------------------------- */
function probarApp(rutaJs, nombresVistas, respuestas, etiqueta) {
  const fuente = fs.readFileSync(path.join(RAIZ, rutaJs), "utf8");
  const inyeccion = `\n  globalThis.__vistas = { ${nombresVistas.join(", ")} };\n`;
  // Exponer las funciones justo antes de que el IIFE se cierre
  const marcas = ["  if (token && ROL) arrancar();", "  if (token) cargarPortal();"];
  let instrumentado = null;
  for (const marca of marcas) {
    if (fuente.includes(marca)) {
      instrumentado = fuente.replace(marca, inyeccion + marca);
      break;
    }
  }
  if (!instrumentado) instrumentado = fuente.replace(/\}\)\(\);\s*$/, inyeccion + "})();");

  const { global: entorno, registro } = construirEntorno(respuestas);
  // navigator y otros son de solo lectura en Node: se definen con descriptor
  for (const clave of Object.keys(entorno)) {
    try { globalThis[clave] = entorno[clave]; }
    catch (e) {
      try { Object.defineProperty(globalThis, clave,
        { value: entorno[clave], configurable: true, writable: true }); }
      catch (e2) { /* si tampoco se puede, se ignora */ }
    }
  }

  let vistas;
  try {
    vistas = new Function(instrumentado + "\n; return globalThis.__vistas;")();
  } catch (e) {
    fallos.push(`${etiqueta}: el archivo no carga → ${e.message}`);
    return;
  }
  if (!vistas) {
    fallos.push(`${etiqueta}: no se pudieron exponer las pantallas`);
    return;
  }

  return { vistas, registro };
}

async function correr() {
  console.log("═══ PRUEBA DE HUMO DEL FRONTEND ═══\n");

  /* ---- Panel del equipo ---- */
  const VISTAS_EQUIPO = [
    "vistaContador", "vistaPatronal", "vistaCalculos", "vistaAutorizaciones",
    "vistaFacturas", "vistaSaldosFavor", "vistaExpediente", "vistaPao",
    "subTablero", "subAdmin", "vistaTableroObligaciones", "vistaCertificados",
    "vistaRespaldos", "panelPrincipal",
  ];
  const equipo = probarApp("static/equipo/app.js", VISTAS_EQUIPO,
                           RESPUESTAS_EQUIPO, "equipo");
  if (equipo) {
    for (const nombre of VISTAS_EQUIPO) {
      const fn = equipo.vistas[nombre];
      if (typeof fn !== "function") {
        console.log(`  ⚠ ${nombre}: no existe (¿se renombró?)`);
        continue;
      }
      try {
        // Argumentos tolerantes: zona/volverA/cliente según la firma
        const args = nombre === "vistaExpediente"
          ? [1, "Grupo Norte", () => {}]
          : [equipo.registro["sub-vista"] || {}, () => {}];
        await Promise.resolve(fn.apply(null, args));
        console.log(`  ✓ ${nombre}`);
      } catch (e) {
        console.log(`  ✗ ${nombre}: ${e.message}`);
        fallos.push(`equipo/${nombre}: ${e.message}`);
      }
    }
  }

  /* ---- Portal del cliente ---- */
  console.log("");
  const VISTAS_PORTAL = ["cargarPortal", "cargarMisFacturas",
                         "cargarResumenFinanciero", "cargarCertificados",
                         "cargarCitas"];
  // Se fusionan las respuestas del equipo: alguna petición suya puede
  // resolverse tarde, ya con el entorno del portal montado, y no debe
  // ensuciar el resultado con ruido que no es un fallo real.
  const portal = probarApp("static/clientes/app.js", VISTAS_PORTAL,
                           { ...RESPUESTAS_EQUIPO, ...RESPUESTAS_PORTAL },
                           "portal");
  if (portal) {
    for (const nombre of VISTAS_PORTAL) {
      const fn = portal.vistas[nombre];
      if (typeof fn !== "function") {
        console.log(`  ⚠ ${nombre}: no existe`);
        continue;
      }
      try {
        await Promise.resolve(fn());
        console.log(`  ✓ ${nombre}`);
      } catch (e) {
        console.log(`  ✗ ${nombre}: ${e.message}`);
        fallos.push(`portal/${nombre}: ${e.message}`);
      }
    }
  }

  console.log("\n" + "─".repeat(48));
  if (fallos.length) {
    console.log(`PANTALLAS ROTAS (${fallos.length}):`);
    fallos.forEach((f) => console.log("  · " + f));
    process.exit(1);
  }
  console.log("TODAS LAS PANTALLAS CORREN SIN ERROR ✓");
}

correr();
