/* Pacheco & Aparicio · App del equipo — conectada a la API FastAPI.
   Servir desde /static/equipo/app.js (CSP: script-src 'self'). */
(function () {
  "use strict";

  /* Si el usuario navega mientras una pantalla está cargando, el elemento al
     que iba a escribir la respuesta YA NO EXISTE y todo tronaba con
     "Cannot set properties of null". Ahora esas escrituras caen en un nodo
     fantasma que las absorbe sin romper nada (los IDs mal escritos se cazan
     en la verificación automática, no en producción). */
  const NODO_FANTASMA = new Proxy({ _fantasma: true }, {
    get(_, k) {
      if (k === "classList") return { add() {}, remove() {}, toggle() {}, contains: () => false };
      if (k === "style" || k === "dataset") return {};
      if (k === "files") return [];
      if (k === "value" || k === "textContent" || k === "innerHTML") return "";
      if (k === "checked") return false;
      if (k === "children" || k === "options") return [];
      if (k === "firstElementChild" || k === "closest" || k === "querySelector") return () => NODO_FANTASMA;
      if (k === "querySelectorAll") return () => [];
      return typeof k === "string" ? () => {} : undefined;
    },
    set() { return true; },
  });
  const $ = (s) => document.querySelector(s) || NODO_FANTASMA;
  const $$ = (s) => [...document.querySelectorAll(s)];

  let token = sessionStorage.getItem("pya_equipo_token");
  let ROL = sessionStorage.getItem("pya_equipo_rol");
  let NOMBRE = sessionStorage.getItem("pya_equipo_nombre");

  const hoy = new Date();
  const MES = hoy.getMonth() + 1;
  const ANIO = hoy.getFullYear();
  const NOMBRE_MES = hoy.toLocaleDateString("es-MX", { month: "long", year: "numeric" });
  const dinero = (n) => n == null ? "—" :
    Number(n).toLocaleString("es-MX", { style: "currency", currency: "MXN", maximumFractionDigits: 0 });
  const fecha = (t) => t ? new Date(t).toLocaleString("es-MX",
    { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";

  /* ---------- Íconos (trazo, sin emojis) ---------- */
  const I = (p, t = 18) => `<svg width="${t}" height="${t}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
  const ICO = {
    check: (t) => I('<path d="M20 6 9 17l-5-5"/>', t),
    circuloCheck: (t) => I('<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>', t),
    clip: (t) => I('<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>', t),
    atras: (t) => I('<path d="M19 12H5"/><path d="m12 19-7-7 7-7"/>', t),
    codigo: (t) => I('<path d="M3 5v14"/><path d="M8 5v14"/><path d="M12 5v14"/><path d="M17 5v14"/><path d="M21 5v14"/>', t),
    camion: (t) => I('<path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.62l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/>', t),
    reloj: (t) => I('<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>', t),
    sobre: (t) => I('<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>', t),
    doc: (t) => I('<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v5h5"/><path d="M16 13H8"/><path d="M16 17H8"/>', t),
    enviar: (t) => I('<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>', t),
    buscar: (t) => I('<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>', t),
    subir: (t) => I('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>', t),
    calendario: (t) => I('<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>', t),
  };

  /* ---------- API ---------- */
  /* =====================================================================
     CONSOLA DE ERRORES VISIBLE
     Antes, cuando algo fallaba, la app simplemente NO HACÍA NADA y no
     respondía: imposible saber qué pasó. Ahora todo error —de red, de
     servidor o de JavaScript— aparece abajo a la derecha, con la ruta que
     falló y el motivo, y se puede copiar para reportarlo.
     ===================================================================== */
  const BITACORA = [];
  function reportarError(donde, detalle, ruta) {
    const marca = new Date().toLocaleTimeString("es-MX");
    BITACORA.unshift({ marca, donde, detalle: String(detalle || ""), ruta: ruta || "" });
    if (BITACORA.length > 25) BITACORA.pop();
    try { console.error(`[P&A] ${donde}`, detalle, ruta || ""); } catch (e) {}
    pintarConsolaErrores();
  }
  function pintarConsolaErrores() {
    let caja = document.getElementById("consola-errores");
    if (!caja) {
      caja = document.createElement("div");
      caja.id = "consola-errores";
      caja.style.cssText = "position:fixed;right:14px;bottom:14px;z-index:9999;max-width:min(92vw,420px);" +
        "background:#2A0E0A;color:#FFE9E4;border:1px solid #B4362A;border-radius:12px;" +
        "box-shadow:0 16px 40px -12px rgba(0,0,0,.5);font-size:12px;overflow:hidden";
      document.body.appendChild(caja);
    }
    const u = BITACORA[0];
    caja.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;padding:9px 12px;background:#B4362A">
        <strong style="flex:1;font-size:12px">Algo falló (${BITACORA.length})</strong>
        <button id="err-copiar" style="border:1px solid rgba(255,255,255,.5);background:none;color:#fff;border-radius:6px;font-size:10.5px;padding:2px 7px;cursor:pointer">copiar</button>
        <button id="err-cerrar" style="border:none;background:none;color:#fff;font-size:16px;line-height:1;cursor:pointer;padding:0 2px">×</button>
      </div>
      <div style="padding:10px 12px;max-height:200px;overflow:auto">
        <p style="margin:0;font-weight:700">${u.donde}</p>
        <p style="margin:4px 0 0;opacity:.9;word-break:break-word">${u.detalle}</p>
        ${u.ruta ? `<p style="margin:4px 0 0;opacity:.7;font-size:11px">${u.ruta}</p>` : ""}
        <p style="margin:6px 0 0;opacity:.6;font-size:10.5px">${u.marca}</p>
      </div>`;
    const cerrar = document.getElementById("err-cerrar");
    if (cerrar) cerrar.onclick = () => caja.remove();
    const copiar = document.getElementById("err-copiar");
    if (copiar) copiar.onclick = () => {
      const texto = BITACORA.map((b) => `[${b.marca}] ${b.donde}: ${b.detalle} ${b.ruta}`).join("\n");
      if (navigator.clipboard) navigator.clipboard.writeText(texto);
      copiar.textContent = "copiado";
    };
  }
  window.addEventListener("error", (e) =>
    reportarError("Error de JavaScript", e.message + (e.lineno ? ` (línea ${e.lineno})` : "")));
  window.addEventListener("unhandledrejection", (e) =>
    reportarError("Operación fallida", (e.reason && e.reason.message) || e.reason));

  async function api(ruta, opciones = {}) {
    let r;
    try {
      r = await fetch(ruta, {
        ...opciones,
        headers: { ...(opciones.headers || {}), ...(token ? { Authorization: "Bearer " + token } : {}) },
      });
    } catch (e) {
      reportarError("Sin conexión con el servidor", e.message, ruta);
      throw e;
    }
    if (r.status === 401) { salir(); throw new Error("sesión expirada"); }
    if (!r.ok) {
      // El servidor respondió con error: se avisa SIEMPRE, aunque quien
      // llamó decida además mostrar su propio mensaje.
      let motivo = `HTTP ${r.status}`;
      try {
        const copia = r.clone();
        const j = await copia.json();
        if (j && j.detail) motivo = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      } catch (e) {}
      reportarError(`El servidor rechazó la petición (${r.status})`, motivo, ruta);
    }
    return r;
  }
  function salir() {
    sessionStorage.removeItem("pya_equipo_token");
    sessionStorage.removeItem("pya_equipo_rol");
    sessionStorage.removeItem("pya_equipo_nombre");
    token = null;
    $("#vista-app").classList.add("oculto");
    $("#vista-login").classList.remove("oculto");
  }
  $("#btn-salir").addEventListener("click", salir);

  /* ---------- Login con 2FA ---------- */
  $("#form-login").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = $("#login-error");
    err.classList.add("oculto");
    const datos = new URLSearchParams({ username: $("#email").value, password: $("#password").value });
    const totp = $("#codigo-totp").value.trim();
    if (totp) datos.append("codigo_totp", totp);
    let r, j;
    try {
      r = await fetch("/api/auth/login", { method: "POST", body: datos });
      j = await r.json();
    } catch {
      err.textContent = "No se pudo conectar con el servidor. Intente de nuevo.";
      err.classList.remove("oculto");
      return;
    }
    if (!r.ok) {
      if (j.detail === "totp_requerido") {
        $("#codigo-totp").focus();
        err.textContent = "Ingrese el código de 6 dígitos de su app autenticadora.";
      } else {
        err.textContent = typeof j.detail === "string" ? j.detail : "Correo o contraseña incorrectos.";
      }
      err.classList.remove("oculto");
      return;
    }
    if (j.rol === "cliente") {
      err.textContent = "Esta es la entrada del equipo. Los clientes entran por su portal.";
      err.classList.remove("oculto");
      return;
    }
    token = j.access_token; ROL = j.rol; NOMBRE = j.nombre;
    sessionStorage.setItem("pya_equipo_token", token);
    sessionStorage.setItem("pya_equipo_rol", ROL);
    sessionStorage.setItem("pya_equipo_nombre", NOMBRE);
    arrancar();
  });

  function arrancar() {
    $("#vista-login").classList.add("oculto");
    $("#vista-app").classList.remove("oculto");
    $("#cab-nombre").textContent = NOMBRE;
    const titulos = { administrador: "Administración del sistema",
      director: "Dirección", supervisor: "Supervisión y contaduría",
      contador: "Contaduría", admin_secretaria: "Cobranza" };
    $("#cab-rol").textContent = (titulos[ROL] || ROL) + " · " + NOMBRE_MES;
    window.scrollTo(0, 0);
    // Todos entran al panel unificado; cada quien ve las secciones de su rol
    // y ARRANCA en su pantalla de siempre (INICIO_POR_ROL). Regresar al panel
    // siempre lleva al carril de secciones.
    panelPrincipal(INICIO_POR_ROL[ROL]);
  }

  /* ==================== DIRECTOR / CFO ==================== */
  /* =========================================================================
     PANEL UNIFICADO — las secciones dependen del ROL, no de pantallas
     duplicadas. El DIRECTOR (Papá) y el ADMINISTRADOR (Luis) ven TODO.
     Artemisa es supervisora Y contadora: elabora cálculos y hace el ciclo
     patronal, además de autorizar (nunca sus propios cálculos).
     ========================================================================= */
  const SECCIONES = [
    { id: "kiosco",       etq: "Kiosco de cobranza",   roles: ["admin_secretaria", "supervisor", "director", "administrador"],
      completa: true },
    { id: "tablero",      etq: "Tablero",              roles: ["director", "administrador"],
      abrir: () => subTablero() },
    { id: "trabajo",      etq: "Trabajo del despacho", roles: ["contador", "admin_secretaria", "supervisor", "director", "administrador"],
      completa: true },
    { id: "autoriza",     etq: "Autorizaciones",       roles: ["supervisor", "director", "administrador"],
      abrir: (z) => vistaAutorizaciones(z), contador: true },
    { id: "calculos",     etq: "Cálculo de impuestos", roles: ["contador", "admin_secretaria", "supervisor", "director", "administrador"],
      completa: true },
    { id: "patronal",     etq: "IMSS y nóminas",       roles: ["contador", "admin_secretaria", "supervisor", "director", "administrador"],
      completa: true },
    { id: "obligaciones", etq: "Obligaciones",         roles: ["supervisor", "director", "administrador"],
      abrir: (z) => vistaTableroObligaciones(z) },
    { id: "saldos",       etq: "Saldos a favor",       roles: ["contador", "admin_secretaria", "supervisor", "director", "administrador"],
      abrir: (z) => vistaSaldosFavor(z) },
    { id: "facturas",     etq: "Facturas",             roles: ["contador", "admin_secretaria", "supervisor", "director", "administrador"],
      abrir: (z) => vistaFacturas(z), contador: true },
    { id: "certs",        etq: "Certificados",         roles: ["contador", "admin_secretaria", "supervisor", "director", "administrador"],
      abrir: (z) => vistaCertificados(z) },
    { id: "respaldos",    etq: "Respaldos",            roles: ["contador", "admin_secretaria", "supervisor", "director", "administrador"],
      abrir: (z) => vistaRespaldos(z) },
    { id: "admin",        etq: "Administración",       roles: ["director", "administrador"],
      abrir: () => subAdmin() },
  ];

  // Pantallas COMPLETAS (toman todo el ancho: balanza, ciclo IMSS, kiosco)
  const ABRIR_COMPLETA = {
    kiosco:   (volver) => vistaPao(volver),
    trabajo:  (volver) => vistaContador(volver),
    calculos: (volver) => vistaCalculos(volver),
    patronal: (volver) => vistaPatronal(volver),
  };

  function seccionesDeMiRol() {
    return SECCIONES.filter((s) => s.roles.includes(ROL));
  }

  // Dónde abre cada rol AL INICIAR SESIÓN (su pantalla de trabajo de siempre).
  // OJO: "Regresar al panel" desde una pantalla completa vuelve al CARRIL
  // (la primera sección normal del rol), nunca a la misma pantalla completa:
  // eso era el bucle que dejaba al Director atascado en el kiosco de cobranza.
  const INICIO_POR_ROL = {
    admin_secretaria: "kiosco",     // Pao: su kiosco de siempre
    contador: "trabajo",            // Carlos: el trabajo del mes
    supervisor: "autoriza",         // Artemisa: lo que espera su firma
    director: "tablero",            // Papá: el despacho de un vistazo
    administrador: "tablero",       // Luis
  };

  // Si una vista truena (datos raros de producción, red, etc.), el panel NO
  // se muere en silencio: se muestra el error y el carril sigue vivo.
  function abrirSeguro(seccion, zona) {
    try {
      Promise.resolve(seccion.abrir(zona)).catch((e) => errorDeVista(zona, seccion, e));
    } catch (e) { errorDeVista(zona, seccion, e); }
  }
  // Igual para las pantallas COMPLETAS (IMSS, calculadora, kiosco, trabajo):
  // si truenan, ya no dejan una pantalla muerta sin salida.
  function abrirCompletaSegura(id, volver) {
    const etq = (SECCIONES.find((s) => s.id === id) || {}).etq || id;
    try {
      Promise.resolve(ABRIR_COMPLETA[id](volver)).catch((e) => falloPantalla(id, etq, e, volver));
    } catch (e) { falloPantalla(id, etq, e, volver); }
  }
  function falloPantalla(id, etq, e, volver) {
    reportarError(`No se pudo abrir «${etq}»`, (e && e.message) || e);
    $("#contenido").innerHTML = `
      <div class="carta" style="padding:24px;border-left:3px solid var(--rojo);max-width:640px">
        <p style="margin:0;font-size:15px;font-weight:800;color:var(--marino)">No se pudo abrir «${etq}»</p>
        <p style="margin:8px 0 0;font-size:13px;color:var(--gris);line-height:1.6">${(e && e.message) || e}</p>
        <p style="margin:8px 0 0;font-size:12.5px;color:var(--gris2)">Las demás secciones siguen funcionando.</p>
        <button id="fallo-volver" class="btn btn-linea" style="margin-top:14px;min-height:42px">${ICO.atras(15)} Regresar al panel</button>
      </div>`;
    const b = $("#fallo-volver");
    if (b) b.onclick = () => (volver ? volver() : panelPrincipal());
  }
  function errorDeVista(zona, seccion, e) {
    reportarError(`Sección «${seccion.etq || seccion.id}»`, (e && e.message) || e);
    if (zona) zona.innerHTML = `
      <div class="carta" style="padding:20px;border-left:3px solid var(--rojo)">
        <p style="margin:0;font-size:13.5px;font-weight:800;color:var(--marino)">Esta sección no pudo cargar</p>
        <p style="margin:6px 0 0;font-size:12.5px;color:var(--gris)">${(e && e.message) || e || "Error desconocido"}. Las demás secciones siguen funcionando; intente de nuevo o recargue la página.</p>
      </div>`;
  }

  async function panelPrincipal(seccionInicial) {
    const mias = seccionesDeMiRol();
    const normal = mias.find((x) => !x.completa) || mias[0];
    const activa = seccionInicial || normal.id;
    $("#contenido").innerHTML = `
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:22px">
        ${mias.map((s) => `<button id="nav-${s.id}" class="chip ${s.id === activa ? "activo" : ""}">${s.etq}${s.contador ? ` <span id="n-${s.id}"></span>` : ""}</button>`).join("")}
      </div>
      <div id="sub-vista"></div>`;

    mias.forEach((s) => {
      $(`#nav-${s.id}`).onclick = () => {
        if (s.completa) return abrirCompletaSegura(s.id, () => panelPrincipal());
        $$(".chip").forEach((c) => c.classList.toggle("activo", c.id === `nav-${s.id}`));
        abrirSeguro(s, $("#sub-vista"));
      };
    });

    // Contadores de pendientes en los chips
    if (mias.some((s) => s.id === "autoriza")) {
      api("/api/calculos/pendientes").then((r) => r.json()).then((p) => {
        const e = $("#n-autoriza");
        if (e && p.length) e.textContent = `(${p.length})`;
      }).catch(() => {});
    }
    if (mias.some((s) => s.id === "facturas")) {
      api("/api/facturas?estatus=abiertas").then((r) => r.json()).then((p) => {
        const e = $("#n-facturas");
        if (e && p.length) e.textContent = `(${p.length})`;
      }).catch(() => {});
    }

    const sec = mias.find((s) => s.id === activa) || normal;
    if (sec && sec.completa) return abrirCompletaSegura(sec.id, () => panelPrincipal());
    if (sec && sec.abrir) abrirSeguro(sec, $("#sub-vista"));
  }

  async function subTablero() {
    $("#sub-vista").innerHTML = `
      <div style="animation:aparecer .35s ease">
      <h1 class="h1">El despacho, de un vistazo</h1>
      <div id="kpis" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-bottom:34px"></div>
      <div id="autofirmas"></div>
      <div style="display:flex;flex-wrap:wrap;gap:clamp(20px,3vw,32px);align-items:flex-start">
        <div style="flex:1.5;min-width:min(100%,340px)">
          <p class="micro" style="margin:0 0 12px;color:var(--rojo)">Semáforo de cartera vencida</p>
          <div id="cartera" class="carta" style="overflow:hidden"></div>
          <p id="riesgo-total" class="tnum" style="margin:12px 0 0;font-size:14px;font-weight:700;color:var(--marino)"></p>
        </div>
        <div style="flex:1;min-width:min(100%,300px);display:flex;flex-direction:column;gap:28px">
          <div>
            <p class="micro" style="margin:0 0 12px">Ingresos ${ANIO} · facturado vs cobrado</p>
            <div class="carta" style="padding:20px 18px 14px">
              <div id="barras" style="display:flex;align-items:flex-end;gap:6px;height:150px"></div>
              <div id="barras-meses" style="display:flex;gap:6px;margin-top:8px"></div>
              <div style="display:flex;gap:16px;margin-top:12px;padding-top:12px;border-top:1px solid #EEF0F4">
                <span style="display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--gris)"><span style="width:10px;height:10px;border-radius:3px;background:#C9D8EA"></span>Facturado</span>
                <span style="display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--gris)"><span style="width:10px;height:10px;border-radius:3px;background:#0A5AA1"></span>Cobrado</span>
              </div>
            </div>
          </div>
          <div>
            <p class="micro" style="margin:0 0 12px">Auditoría reciente</p>
            <div id="auditoria" class="carta" style="padding:6px 18px;max-height:280px;overflow-y:auto"></div>
          </div>
        </div>
      </div></div>`;

    const t = await (await api(`/api/obligaciones/tablero-director?mes=${MES}&anio=${ANIO}`)).json();
    const kpi = (etq, val, sub) => `<div class="kpi">
      <p class="micro" style="margin:0">${etq}</p>
      <p class="serif tnum" style="margin:8px 0 0;font-weight:700;font-size:36px;color:var(--marino)">${val}</p>
      <p style="margin:4px 0 0;font-size:13px;color:var(--gris2)">${sub}</p></div>`;
    $("#kpis").innerHTML =
      kpi("Contabilidades cerradas", t.progreso_contabilidades.porcentaje + "%",
        `${t.progreso_contabilidades.terminadas} de ${t.progreso_contabilidades.total} clientes`) +
      kpi("Impuestos enviados", `${t.impuestos_enviados.enviados}/${t.impuestos_enviados.total}`,
        "línea de captura ya con el cliente") +
      kpi("Eficiencia de entrega",
        t.eficiencia_promedio_minutos != null ? t.eficiencia_promedio_minutos + " min" : "—",
        "del cierre contable al envío de Regina");

    // Autofirmas del periodo: cálculos que su propio autor autorizó.
    // No es una alarma, es visibilidad: usted decide si quiere revisarlos.
    const af = t.autoautorizaciones || [];
    $("#autofirmas").innerHTML = af.length ? `
      <div class="carta" style="padding:18px 22px;margin-bottom:30px;border-left:3px solid var(--ambar)">
        <p style="margin:0 0 4px;font-size:13px;font-weight:800;color:var(--marino)">
          ${af.length} cálculo${af.length > 1 ? "s" : ""} autorizado${af.length > 1 ? "s" : ""} por quien mismo lo${af.length > 1 ? "s" : ""} elaboró</p>
        <p style="margin:0 0 10px;font-size:12px;color:var(--gris2);line-height:1.5">
          No pasaron por un segundo par de ojos. Aquí están, por si quiere revisarlos.</p>
        ${af.map((x) => `
          <div style="display:flex;justify-content:space-between;gap:10px;padding:5px 0;border-bottom:1px solid var(--borde-suave);font-size:12.5px">
            <span><strong>${x.cliente}</strong> · ${x.quien}</span>
            <span class="tnum" style="font-weight:700">${dinero(x.total)}</span></div>`).join("")}
      </div>` : "";

    const s = await (await api("/api/obligaciones/semaforo-cartera")).json();
    if (!s.cartera_en_riesgo.length) {
      $("#cartera").innerHTML = `<p style="margin:0;padding:20px;display:flex;align-items:center;gap:10px;font-size:14px;font-weight:600;color:var(--verde)">${ICO.circuloCheck(18)} Cartera sana: nadie rebasa los ${30} días.</p>`;
    } else {
      $("#cartera").innerHTML = s.cartera_en_riesgo.map((c) => {
        const colorDias = c.nivel.startsWith("rojo") ? "var(--rojo)" : "var(--ambar)";
        const lectura = c.estatus_lectura === "visto_sin_respuesta"
          ? `<span style="color:var(--rojo);font-weight:600">visto, sin respuesta</span>`
          : c.estatus_lectura.replaceAll("_", " ");
        return `<div class="fila ${c.nivel === "rojo_parpadeante" ? "rojo-parpadeante" : ""}" style="padding:15px 18px">
          <div style="flex:1;min-width:170px">
            <p style="margin:0;font-size:14.5px;font-weight:700">${c.cliente}
              ${c.tipo_cliente === "confianza_especial" ? `<span style="margin-left:6px;font-size:10.5px;font-weight:700;letter-spacing:.06em;padding:2.5px 7px;border-radius:99px;background:#EAF2F9;color:var(--azul);text-transform:uppercase">trato especial</span>` : ""}</p>
            <p style="margin:3px 0 0;font-size:12px;color:var(--gris2)">${lectura} · últ. aviso ${fecha(c.ultima_notificacion)}</p>
          </div>
          <p class="tnum" style="margin:0;font-size:13px;font-weight:700;color:${colorDias}">${c.dias_vencido} días</p>
          <p class="tnum" style="margin:0;font-size:14.5px;font-weight:700;color:var(--marino);min-width:84px;text-align:right">${dinero(c.monto_adeudado)}</p>
        </div>`;
      }).join("");
      $("#riesgo-total").textContent = "Monto total en riesgo: " +
        dinero(s.monto_total_riesgo).replace("MXN", "").trim();
    }

    const ing = await (await api(`/api/admin/ingresos?anio=${ANIO}`)).json();
    const meses = "EFMAMJJASOND".split("");
    const maximo = Math.max(1, ...Object.values(ing.por_mes).map((m) => m.facturado));
    $("#barras").innerHTML = Object.keys(ing.por_mes).map((m) => {
      const d = ing.por_mes[m];
      const hf = Math.max(2, Math.round(d.facturado / maximo * 100));
      const hc = Math.max(2, Math.round(d.cobrado / maximo * 100));
      const vacio = d.facturado === 0;
      return `<div style="flex:1;display:flex;align-items:flex-end;gap:2px;height:100%">
        <span style="flex:1;height:${vacio ? "3px" : hf + "%"};background:${vacio ? "#E4E7ED" : "#C9D8EA"};border-radius:3px 3px 0 0"></span>
        <span style="flex:1;height:${vacio ? "3px" : hc + "%"};background:${vacio ? "#E4E7ED" : "#0A5AA1"};border-radius:3px 3px 0 0"></span>
      </div>`;
    }).join("");
    $("#barras-meses").innerHTML = meses.map((m, i) =>
      `<span style="flex:1;text-align:center;font-size:10px;font-weight:${i + 1 === MES ? 700 : 600};color:${i + 1 === MES ? "var(--azul)" : "var(--gris2)"}">${m}</span>`).join("");

    pintarMisCitas();
    const logs = await (await api("/api/admin/auditoria?limite=40")).json();
    $("#auditoria").innerHTML = logs.map((l) =>
      `<p style="margin:13px 0;font-size:12.5px;line-height:1.55;color:#43506B;border-bottom:1px solid #F1F2F5;padding-bottom:13px">
        <span class="tnum" style="color:var(--gris2)">${fecha(l.timestamp)}</span> ·
        <strong>${l.accion.replaceAll("_", " ")}</strong>
        <span style="color:var(--gris2)"> ${(l.detalles && (l.detalles.cliente || l.detalles.nombre)) || ""} · IP ${l.ip || "—"}</span></p>`
    ).join("") || `<p style="margin:13px 0;font-size:12.5px;color:var(--gris2)">Sin movimientos aún.</p>`;
  }

  /* ==================== CONTADOR ==================== */
  async function vistaContador(volverA) {
    $("#contenido").innerHTML = `
      <div style="animation:aparecer .35s ease">
      ${volverA ? `<button id="volver-panel-c" class="btn btn-linea" style="margin-bottom:16px;min-height:40px">${ICO.atras(15)} Regresar al panel</button>` : ""}
      <div id="aviso-nominas"></div>
      <div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px">
        <h1 class="h1" style="margin:0">Trabajo del mes</h1>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button id="ir-calculos" class="btn btn-azul" style="min-height:42px;font-size:13.5px">Cálculo de impuestos</button>
          <button id="ir-patronal" class="btn btn-linea" style="min-height:42px;font-size:13.5px">IMSS y Nóminas</button>
          <button id="ir-saldos" class="btn btn-linea" style="min-height:42px;font-size:13.5px">Saldos a favor</button>
        </div>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:clamp(20px,3vw,32px);align-items:flex-start">
        <div style="flex:1.5;min-width:min(100%,340px)">
          <div style="display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:14px">
            <input id="filtro-texto" placeholder="Filtrar por cliente…" aria-label="Filtrar por cliente"
                   class="campo" style="flex:1;min-width:180px;max-width:260px;padding:10px 12px;font-size:13.5px">
            <div role="group" aria-label="Filtrar por estatus" style="display:flex;gap:6px;flex-wrap:wrap">
              <button data-f="todos" class="chip">Todos</button>
              <button data-f="pendiente" class="chip">Pendientes</button>
              <button data-f="en_proceso" class="chip">En proceso</button>
              <button data-f="terminado" class="chip">Terminados</button>
            </div>
          </div>
          <div id="tabla" class="carta" style="overflow:hidden"></div>
          <p class="micro" style="margin:34px 0 12px">Trámites solicitados por clientes</p>
          <div id="tickets" style="display:flex;flex-direction:column;gap:10px"></div>
          <p class="micro" style="margin:30px 0 12px">Mis próximas citas</p>
          <div id="mis-citas" style="display:flex;flex-direction:column;gap:9px"></div>
        </div>
        <div style="flex:1;min-width:min(100%,300px)">
          <div class="carta" style="padding:22px">
            <h2 class="serif" style="margin:0;font-weight:700;font-size:19px;color:var(--marino)">Cargar líneas de captura</h2>
            <p style="margin:8px 0 16px;font-size:13px;line-height:1.6;color:var(--gris)">Arrastre uno o varios PDF del SAT. El sistema los cifra, los guarda y Regina los entrega al instante por WhatsApp.</p>
            <div id="zona-drop" class="zona-drop" tabindex="0" role="button" aria-label="Cargar PDF del SAT">
              <span style="pointer-events:none">
                <span style="display:inline-block;margin-bottom:8px;color:var(--azul)">${ICO.subir(30)}</span>
                <span style="display:block;font-size:13.5px;font-weight:700;color:var(--marino)">Suelte aquí los PDF del SAT</span>
                <span style="display:block;font-size:12px;margin-top:3px;color:var(--gris2)">o toque para elegirlos</span>
              </span>
            </div>
            <input id="pdfs" type="file" accept="application/pdf" multiple class="oculto">
            <div id="cola" style="display:flex;flex-direction:column;gap:12px;margin-top:16px"></div>
            <button id="btn-enviar-todo" class="btn btn-azul oculto" style="margin-top:14px;width:100%;min-height:48px;font-weight:700">Enviar todo</button>
          </div>
          <div class="carta" style="padding:22px;margin-top:18px">
            <h2 class="serif" style="margin:0;font-weight:700;font-size:19px;color:var(--marino)">Subir a la bóveda del cliente</h2>
            <p style="margin:8px 0 14px;font-size:13px;line-height:1.6;color:var(--gris)">Balanza de comprobación, cédula de ISN, cuotas patronales (SIPARE), acuses y demás documentos del expediente.</p>
            <div style="display:flex;flex-direction:column;gap:10px">
              <select id="bov-cliente" class="campo" aria-label="Cliente" style="padding:10px;font-size:13.5px"></select>
              <select id="bov-categoria" class="campo" aria-label="Categoría" style="padding:10px;font-size:13.5px">
                <option value="balanza_comprobacion">Balanza de comprobación</option>
                <option value="cedula_isn">Impuesto sobre nómina (cédula ISN)</option>
                <option value="propuesta_sipare">Cuotas patronales IMSS (SIPARE)</option>
                <option value="aviso_infonavit">Aportaciones INFONAVIT</option>
                <option value="acuse_sat">Acuse de pago SAT</option>
                <option value="constancia_situacion_fiscal">Constancia de Situación Fiscal</option>
                <option value="opinion_32d">Opinión de cumplimiento 32D</option>
                <option value="estado_financiero_dictaminado">Estado financiero dictaminado</option>
                <option value="acta_constitutiva">Acta Constitutiva</option>
              </select>
              <div style="display:flex;gap:8px">
                <input id="bov-anio" type="number" class="campo" aria-label="Año" style="flex:1;padding:10px;font-size:13.5px">
                <select id="bov-mes" class="campo" aria-label="Mes (opcional)" style="flex:1;padding:10px;font-size:13.5px">
                  <option value="">Mes (opcional)</option>
                </select>
              </div>
              <input id="bov-pdf" type="file" accept="application/pdf" style="font-size:12.5px">
              <button id="bov-enviar" class="btn btn-azul" style="width:100%;min-height:46px">Subir a la bóveda</button>
              <p id="bov-msj" class="oculto" style="margin:0;font-size:12.5px;font-weight:600"></p>
            </div>
          </div>
        </div>
      </div></div>`;

    let FILAS = [], filtroEstatus = "todos";
    const puntos = { pendiente: "var(--rojo)", en_proceso: "var(--ambar)", terminado: "var(--verde)" };

    function pintarTabla() {
      const q = ($("#filtro-texto").value || "").toLowerCase();
      const visibles = FILAS.filter((f) =>
        (filtroEstatus === "todos" || f.estatus === filtroEstatus) &&
        f.cliente.toLowerCase().includes(q));
      $("#tabla").innerHTML = visibles.map((f) => `
        <div class="fila">
          <p style="margin:0;flex:1.4;min-width:150px;font-size:14.5px;font-weight:700">${f.cliente}</p>
          <p style="margin:0;flex:1;min-width:105px;display:flex;align-items:center;gap:8px;font-size:13px;color:#43506B">
            <span style="width:8px;height:8px;border-radius:50%;background:${puntos[f.estatus]};flex:none"></span>${f.estatus.replace("_", " ")}</p>
          <p class="tnum" style="margin:0;min-width:82px;font-size:13.5px;color:#43506B;text-align:right">${f.monto_impuesto != null ? dinero(f.monto_impuesto) : "—"}</p>
          <p style="margin:0;min-width:96px;font-size:12.5px;font-weight:600;text-align:right;color:${f.enviado ? "var(--verde)" : "#C0C7D4"}">${f.enviado ? "✓ entregado" : "—"}</p>
          <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;min-width:190px;justify-content:flex-end">
            ${f.es_complementaria ? `<span class="pildora ambar">complementaria #${f.numero_complementaria}</span>` : ""}
            ${f.pagado ? `<span class="pildora verde" title="${f.referencia_pago || ""}">pagado${f.pagado_por === "cliente" ? " por el cliente" : ""}</span>`
              : f.presentada ? `<label class="chip" style="cursor:pointer">registrar pago
                  <input type="file" accept="application/pdf,image/jpeg,image/png" class="ob-comprobante" data-ob="${f.obligacion_id}" style="display:none"></label>` : ""}
            ${f.presentada ? `<button class="chip ob-complementaria" data-ob="${f.obligacion_id}" data-n="${f.cliente}">complementaria</button>` : ""}
            ${f.verificado_manualmente
              ? `<span class="pildora verde" title="${f.motivo_verificacion || ""}">verificado por ${(f.verificado_por || "").split(" ").slice(-1)[0]}</span>
                 ${f.documentos_pendientes ? `<span class="pildora ambar">faltan papeles</span>` : ""}`
              : (ROL === "supervisor" || ROL === "director" || ROL === "administrador") && f.obligacion_id
                ? `<button class="chip ob-verificar" data-ob="${f.obligacion_id}" data-n="${f.cliente}">dar fe</button>` : ""}
          </div>
        </div>`).join("")
        || `<p style="margin:0;padding:20px;text-align:center;font-size:13.5px;color:var(--gris2)">Sin clientes con ese filtro.</p>`;
    }
    $("#filtro-texto").addEventListener("input", pintarTabla);

    /* NÓMINAS A LA VISTA: antes solo se veían dentro de IMSS y nóminas, o
       sea que el contador se enteraba hasta cerrar el mes. Aquí arriba, con
       las vencidas en rojo, para que no se le pasen. */
    (async () => {
      const zona = $("#aviso-nominas");
      if (!zona) return;
      const nominas = await (await api("/api/patronal/nominas")).json();
      const pendientes = nominas.filter((n) => n.estatus !== "terminada");
      if (!pendientes.length) return;
      const hoyISO = new Date().toISOString().slice(0, 10);
      const vencidas = pendientes.filter((n) => n.fecha_objetivo && n.fecha_objetivo < hoyISO);
      zona.innerHTML = `
        <div class="carta" style="padding:16px 20px;margin-bottom:18px;border-left:3px solid ${vencidas.length ? "var(--rojo)" : "var(--ambar)"}">
          <div style="display:flex;flex-wrap:wrap;gap:8px 14px;align-items:baseline">
            <p style="margin:0;flex:1;font-size:14px;font-weight:800;color:var(--marino)">
              ${pendientes.length} nómina${pendientes.length > 1 ? "s" : ""} por entregar</p>
            ${vencidas.length ? `<span class="pildora roja">${vencidas.length} vencida${vencidas.length > 1 ? "s" : ""}</span>` : ""}
            <button id="nom-ir" class="chip">Ir a nóminas ›</button>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:8px">
            ${pendientes.slice(0, 6).map((n) => `
              <span style="font-size:12px;color:${n.fecha_objetivo < hoyISO ? "var(--rojo)" : "var(--gris)"}">
                <strong>${n.cliente}</strong> · ${n.etiqueta}${n.fecha_objetivo ? ` · ${n.fecha_objetivo}` : ""}</span>`).join("")}
            ${pendientes.length > 6 ? `<span style="font-size:12px;color:var(--gris2)">y ${pendientes.length - 6} más…</span>` : ""}
          </div>
        </div>`;
      const b = $("#nom-ir");
      if (b) b.onclick = () => vistaPatronal(() => vistaContador(volverA));
    })();

    // Registrar el pago de la línea de captura y presentar complementarias.
    // (pintarTabla se redibuja seguido, por eso los handlers van delegados)
    $("#tabla").addEventListener("change", async (e) => {
      const inp = e.target.closest(".ob-comprobante");
      if (!inp || !inp.files.length) return;
      const referencia = prompt("Referencia del pago (opcional):") || "";
      const fd = new FormData();
      fd.append("archivo_pdf", inp.files[0]);
      fd.append("referencia", referencia);
      const r = await api(`/api/obligaciones/${inp.dataset.ob}/comprobante-pago`,
        { method: "POST", body: fd });
      if (r.ok) return recargar();
      const j = await r.json().catch(() => ({}));
      alert(j.detail || "No se pudo registrar el pago.");
    });
    // DAR FE: cuando el sistema falló y el trabajo SÍ se hizo (por WhatsApp,
    // en mano...). Un mando lo verifica para que el cliente no se preocupe
    // de balde ni el contador aparezca incumplido.
    $("#tabla").addEventListener("click", async (e) => {
      const v = e.target.closest(".ob-verificar");
      if (!v) return;
      const motivo = prompt(`Dar fe del trabajo de ${v.dataset.n}\n\n` +
        `¿Qué pasó y cómo se entregó? (queda en la bitácora con su nombre)`);
      if (!motivo) return;
      const faltan = confirm("¿Quedan documentos por subir?\n\n" +
        "Aceptar = sí, se subirán después (se marca 'faltan papeles').\n" +
        "Cancelar = no, todo está en el sistema.");
      const r = await api(`/api/obligaciones/${v.dataset.ob}/verificacion-manual`,
        { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ motivo, documentos_pendientes: faltan,
                                 marcar_entregado: true }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) return alert(j.detail || "No se pudo verificar.");
      alert(j.mensaje);
      recargar();
    });
    $("#tabla").addEventListener("click", async (e) => {
      const b = e.target.closest(".ob-complementaria");
      if (!b) return;
      const motivo = prompt(`Complementaria de ${b.dataset.n}\n\n¿Por qué se presenta?`);
      if (!motivo) return;
      const r = await api(`/api/obligaciones/${b.dataset.ob}/complementaria`,
        { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ motivo }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) return alert(j.detail || "No se pudo iniciar la complementaria.");
      alert(j.mensaje);
      recargar();
    });
    function marcarChips() {
      $$(".chip").forEach((c) => c.classList.toggle("activo", c.dataset.f === filtroEstatus));
    }
    $$(".chip").forEach((c) => c.onclick = () => { filtroEstatus = c.dataset.f; marcarChips(); pintarTabla(); });
    marcarChips();

    async function recargar() {
      FILAS = await (await api(`/api/obligaciones/panel-contador?mes=${MES}&anio=${ANIO}`)).json();
      pintarTabla();
      const tk = await (await api("/api/tickets")).json();
      $("#tickets").innerHTML = tk.map((t) => `
        <div class="carta" style="border-radius:12px;padding:14px 16px;display:flex;flex-wrap:wrap;align-items:center;gap:10px 14px">
          <span style="flex:none;color:var(--azul)">${ICO.doc(19)}</span>
          <div style="flex:1;min-width:170px">
            <p style="margin:0;font-size:14px;font-weight:700">${t.tipo_tramite}</p>
            <p style="margin:2px 0 0;font-size:12px;color:var(--gris2)">${t.cliente} · folio #${t.id} · ${fecha(t.creado)}</p>
          </div>
          <button data-ticket="${t.id}" class="btn-cerrar btn" style="min-height:40px;padding:0 14px;border-radius:8px;background:var(--verde);color:#fff;font-size:13px;font-weight:700">${ICO.check(14)} Listo</button>
        </div>`).join("")
        || `<p style="margin:0;font-size:13.5px;color:var(--gris2)">Sin trámites pendientes. Buen trabajo.</p>`;
      $$(".btn-cerrar").forEach((b) => b.addEventListener("click", async () => {
        b.disabled = true;
        await api(`/api/tickets/${b.dataset.ticket}/cerrar`, { method: "POST" });
        recargar();
      }));
    }
    await recargar();
    pintarMisCitas();
    if (volverA) $("#volver-panel-c").onclick = () => volverA();
    $("#ir-calculos").onclick = () => vistaCalculos(() => vistaContador(volverA));
    $("#ir-patronal").onclick = () => vistaPatronal(() => vistaContador(volverA));
    $("#ir-saldos").onclick = () => { $("#contenido").innerHTML = `<button id="volver-sf" class="btn btn-linea" style="margin-bottom:16px;min-height:40px">${ICO.atras(15)} Regresar</button><h1 class="h1" style="margin-top:0">Saldos a favor</h1><div id="zona-sf"></div>`; $("#volver-sf").onclick = () => vistaContador(volverA); vistaSaldosFavor($("#zona-sf")); };

    /* -------- Carga masiva drag & drop -------- */
    let cola = [];
    const zona = $("#zona-drop"), inputPdfs = $("#pdfs");
    zona.onclick = () => inputPdfs.click();
    zona.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") inputPdfs.click(); };
    ["dragover", "dragenter"].forEach((ev) => zona.addEventListener(ev, (e) => {
      e.preventDefault(); zona.classList.add("encima");
    }));
    ["dragleave", "drop"].forEach((ev) => zona.addEventListener(ev, (e) => {
      e.preventDefault(); zona.classList.remove("encima");
    }));
    zona.addEventListener("drop", (e) => agregarArchivos(e.dataTransfer.files));
    inputPdfs.addEventListener("change", () => { agregarArchivos(inputPdfs.files); inputPdfs.value = ""; });

    function agregarArchivos(lista) {
      [...lista].filter((f) => f.type === "application/pdf")
        .forEach((f) => cola.push({ archivo: f, estado: "listo", detalle: "" }));
      pintarCola();
    }
    const opcionesClientes = () => FILAS.filter((f) => f.estatus !== "terminado")
      .map((f) => `<option value="${f.cliente_id}">${f.cliente}</option>`).join("");

    function pintarCola() {
      $("#btn-enviar-todo").classList.toggle("oculto", !cola.some((c) => c.estado !== "ok"));
      $("#cola").innerHTML = cola.map((c, i) => `
        <div data-i="${i}" style="border:1px solid var(--borde);border-radius:10px;padding:12px 14px">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
            <p style="margin:0;font-size:12.5px;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:flex;align-items:center;gap:6px">${ICO.doc(14)} ${c.archivo.name}</p>
            <span style="flex:none;font-size:12px;font-weight:700;color:${c.estado === "ok" ? "var(--verde)" : c.estado === "error" ? "var(--rojo)" : "var(--gris2)"}">${c.estado === "ok" ? (c.detalle ? `enviado ✓ · ${c.detalle}` : "enviado ✓") : c.estado === "error" ? (c.detalle || "error") : ""}</span>
          </div>
          ${c.estado === "ok" ? "" : `
          <div style="display:flex;flex-direction:column;gap:8px;margin-top:10px">
            <select class="campo cola-cliente" aria-label="Cliente del PDF" style="padding:9px 10px;font-size:13px">${opcionesClientes()}</select>
            <div style="display:flex;gap:8px">
              <input type="number" placeholder="Monto SAT" min="0" step="0.01" aria-label="Monto SAT" class="campo cola-monto" style="flex:1;min-width:0;padding:9px 10px;font-size:13px">
              <input type="date" aria-label="Vencimiento SAT" class="campo cola-vence" style="flex:1;min-width:0;padding:8px 10px;font-size:13px;color:#43506B">
            </div>
            <input placeholder="Número de operación (SAT)" class="campo cola-operacion" style="padding:9px 10px;font-size:13px">

            <div style="border:1px dashed var(--azul-borde);border-radius:10px;padding:10px 12px;background:var(--azul-suave)">
              <p style="margin:0 0 6px;font-size:11.5px;font-weight:700;color:var(--marino)">
                Comprobante de la declaración <span style="font-weight:500;color:var(--gris2)">(el otro archivo: la declaración en sí)</span></p>
              <input type="file" accept="application/pdf" class="cola-comprobante" style="font-size:12px;width:100%">
              <p style="margin:6px 0 0;font-size:11px;color:var(--gris2);line-height:1.5">
                El PDF de arriba es el <strong>acuse / línea de captura</strong> (formato de pago) y es el que se le envía al cliente. Este es el comprobante, que se guarda en el expediente.</p>
            </div>

            <details>
              <summary style="font-size:12px;font-weight:600;color:var(--azul);cursor:pointer">¿La declaración arrojó SALDO A FAVOR?</summary>
              <div style="display:flex;gap:6px;margin-top:8px;align-items:center">
                <input type="number" placeholder="Monto del saldo a favor" min="0" step="0.01" class="campo cola-saldo" style="flex:1;padding:8px 10px;font-size:12.5px">
                <select class="campo cola-saldo-imp" style="width:92px;padding:8px;font-size:12.5px">
                  <option value="isr">ISR</option><option value="iva">IVA</option>
                  <option value="ieps">IEPS</option><option value="otro">Otro</option></select>
              </div>
              <p style="margin:6px 0 0;font-size:11px;color:var(--gris2);line-height:1.5">
                Entrará solo al <strong>inventario de saldos a favor</strong>, ligado a esta declaración y su comprobante, para poder aplicarlo después.</p>
            </details>

            <details>
              <summary style="font-size:12px;font-weight:600;color:var(--azul);cursor:pointer">Desglose por concepto (opcional, alimenta la gráfica del cliente)</summary>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:8px">
                <input type="number" placeholder="IVA" min="0" step="0.01" class="campo cola-iva" style="padding:8px 10px;font-size:12.5px">
                <input type="number" placeholder="ISR" min="0" step="0.01" class="campo cola-isr" style="padding:8px 10px;font-size:12.5px">
                <input type="number" placeholder="Retenciones" min="0" step="0.01" class="campo cola-ret" style="padding:8px 10px;font-size:12.5px">
                <input type="number" placeholder="ISN (nómina)" min="0" step="0.01" class="campo cola-isn" style="padding:8px 10px;font-size:12.5px">
                <input type="number" placeholder="Cuotas IMSS" min="0" step="0.01" class="campo cola-imss" style="padding:8px 10px;font-size:12.5px">
                <input type="number" placeholder="INFONAVIT" min="0" step="0.01" class="campo cola-infonavit" style="padding:8px 10px;font-size:12.5px">
              </div>
            </details>
          </div>`}
        </div>`).join("");
    }

    $("#btn-enviar-todo").onclick = async () => {
      for (const [i, c] of cola.entries()) {
        if (c.estado === "ok") continue;
        const caja = document.querySelector(`[data-i="${i}"]`);
        const cliente = caja.querySelector(".cola-cliente")?.value;
        const monto = caja.querySelector(".cola-monto")?.value;
        const vence = caja.querySelector(".cola-vence")?.value;
        if (!cliente || !monto || !vence) { c.estado = "error"; c.detalle = "faltan datos"; continue; }
        const fd = new FormData();
        fd.append("mes", MES); fd.append("anio", ANIO);
        fd.append("monto_impuesto", monto); fd.append("fecha_vencimiento", vence);
        // Archivo 1: ACUSE / línea de captura (el formato de pago del cliente)
        fd.append("archivo_pdf", c.archivo);
        // Archivo 2: COMPROBANTE de la declaración (para el expediente)
        const comp = caja.querySelector(".cola-comprobante")?.files[0];
        if (comp) fd.append("comprobante_pdf", comp);
        const operacion = caja.querySelector(".cola-operacion")?.value;
        if (operacion) fd.append("numero_operacion", operacion);
        // Saldo a favor -> entra al inventario ligado a esta declaración
        const saldo = caja.querySelector(".cola-saldo")?.value;
        if (saldo && +saldo > 0) {
          fd.append("saldo_a_favor", saldo);
          fd.append("impuesto_saldo_favor", caja.querySelector(".cola-saldo-imp").value);
        }
        [["iva",".cola-iva"],["isr",".cola-isr"],["retenciones",".cola-ret"],
         ["isn",".cola-isn"],["cuotas_imss",".cola-imss"],["infonavit",".cola-infonavit"]]
          .forEach(([campo, sel]) => {
            const v = caja.querySelector(sel)?.value;
            if (v) fd.append(campo, v);
          });
        const r = await api(`/api/obligaciones/${cliente}/subir-linea-captura`, { method: "POST", body: fd });
        if (r.ok) {
          const j = await r.json();
          c.estado = "ok";
          c.detalle = j.saldo_favor_registrado
            ? `saldo a favor de ${dinero(j.saldo_favor_registrado.monto)} registrado`
            : null;
        } else { c.estado = "error"; c.detalle = (await r.json()).detail || "error"; }
        pintarCola();
      }
      pintarCola();
      recargar();
    };

    /* -------- Subir a la bóveda -------- */
    const MESES_N = ["enero","febrero","marzo","abril","mayo","junio","julio",
      "agosto","septiembre","octubre","noviembre","diciembre"];
    $("#bov-mes").innerHTML += MESES_N.map((m, i) =>
      `<option value="${i + 1}">${m.charAt(0).toUpperCase() + m.slice(1)}</option>`).join("");
    $("#bov-anio").value = ANIO;
    function pintarBovClientes() {
      $("#bov-cliente").innerHTML = FILAS.map((f) =>
        `<option value="${f.cliente_id}">${f.cliente}</option>`).join("");
    }
    const _recargarOriginal = recargar;
    $("#bov-enviar").onclick = async () => {
      const msj = $("#bov-msj");
      const pdf = $("#bov-pdf").files[0];
      if (!pdf) { msj.textContent = "Elija el PDF primero."; msj.style.color = "var(--rojo)";
        msj.classList.remove("oculto"); return; }
      const fd = new FormData();
      fd.append("categoria", $("#bov-categoria").value);
      fd.append("anio", $("#bov-anio").value);
      if ($("#bov-mes").value) fd.append("mes", $("#bov-mes").value);
      fd.append("archivo_pdf", pdf);
      $("#bov-enviar").disabled = true;
      const r = await api(`/api/obligaciones/${$("#bov-cliente").value}/subir-documento`,
        { method: "POST", body: fd });
      $("#bov-enviar").disabled = false;
      const j = await r.json();
      msj.textContent = r.ok ? "Documento en la bóveda del cliente." : (j.detail || "No se pudo subir.");
      msj.style.color = r.ok ? "var(--verde)" : "var(--rojo)";
      msj.classList.remove("oculto");
      if (r.ok) $("#bov-pdf").value = "";
    };
    // poblar el select de clientes cuando la tabla carga
    const _obs = setInterval(() => { if (FILAS.length) { pintarBovClientes(); clearInterval(_obs); } }, 400);
  }

  /* ==================== PAO (kiosco) ==================== */
  async function vistaPao(volverA) {
    const cont = $("#contenido");
    // Botón de regreso al panel (Pao también lo tiene: ya no solo hace cobranza)
    const barraVolver = volverA
      ? `<button id="volver-panel-p" class="btn btn-linea" style="margin-bottom:16px;min-height:40px">${ICO.atras(15)} Regresar al panel</button>`
      : "";

    /* RESUMEN DE COBRANZA: qué hay que cobrar este mes y los adeudos
       anteriores. Antes la pantalla salía vacía porque NADIE generaba los
       cobros a partir del honorario contratado; ahora se generan aquí. */
    async function pintarResumenCobranza() {
      const zona = $("#cob-resumen");
      if (!zona || zona._fantasma) return;
      const r = await api(`/api/cobranza/resumen?mes=${MES}&anio=${ANIO}`);
      if (!r.ok) return;
      const j = await r.json();
      zona.innerHTML = `
        <div class="carta" style="padding:18px 22px;margin-bottom:22px">
          <div style="display:flex;flex-wrap:wrap;gap:10px 26px;align-items:baseline">
            <div style="flex:1;min-width:150px">
              <p class="micro" style="margin:0">Honorarios de ${NOMBRE_MES}</p>
              <p class="tnum serif" style="margin:4px 0 0;font-size:26px;font-weight:700;color:var(--marino)">${dinero(j.facturado)}</p>
              <p style="margin:2px 0 0;font-size:12px;color:var(--gris2)">${j.honorarios_generados} cobro(s) · por cobrar ${dinero(j.por_cobrar)}</p>
            </div>
            ${j.adeudos_anteriores ? `
            <div style="min-width:140px">
              <p class="micro" style="margin:0">Adeudos anteriores</p>
              <p class="tnum serif" style="margin:4px 0 0;font-size:22px;font-weight:700;color:var(--rojo)">${dinero(j.adeudos_anteriores)}</p>
              <p style="margin:2px 0 0;font-size:12px;color:var(--gris2)">${j.adeudos_detalle.length} pendiente(s)</p>
            </div>` : ""}
            <button id="cob-generar" class="btn btn-linea" style="min-height:42px;font-size:12.5px">Generar cobros del mes</button>
          </div>
          ${j.sin_honorario_capturado.length ? `
          <p style="margin:10px 0 0;font-size:12px;color:var(--ambar);font-weight:600">
            ⚠ ${j.sin_honorario_capturado.length} cliente(s) sin honorario capturado (${j.sin_honorario_capturado.slice(0,4).join(", ")}${j.sin_honorario_capturado.length > 4 ? "…" : ""}): pónganselo en su expediente para poder cobrarles.</p>` : ""}
          ${j.adeudos_detalle.length ? `
          <details style="margin-top:10px">
            <summary style="font-size:12.5px;font-weight:700;color:var(--azul);cursor:pointer">Ver adeudos anteriores</summary>
            ${j.adeudos_detalle.map((a) => `
            <div style="display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-bottom:1px solid var(--borde-suave);font-size:12.5px">
              <span><strong>${a.cliente}</strong> · ${a.concepto}</span>
              <span class="tnum" style="font-weight:700">${dinero(a.saldo)}</span></div>`).join("")}
          </details>` : ""}
          <p id="cob-msj" class="oculto" style="margin:8px 0 0;font-size:12px;font-weight:700"></p>
        </div>`;
      const b = $("#cob-generar");
      if (b && !b._fantasma) b.onclick = async () => {
        b.disabled = true;
        const r2 = await api(`/api/cobranza/generar?mes=${MES}&anio=${ANIO}`, { method: "POST" });
        const j2 = await r2.json().catch(() => ({}));
        const m = $("#cob-msj");
        m.classList.remove("oculto");
        m.style.color = r2.ok ? "var(--verde)" : "var(--rojo)";
        m.textContent = r2.ok ? j2.mensaje : (j2.detail || "No se pudieron generar.");
        b.disabled = false;
        if (r2.ok) setTimeout(pintarResumenCobranza, 1200);
      };
    }

    function conectarRecordatorios() {
      $$(".btn-recordar").forEach((b) => b.onclick = async () => {
        b.disabled = true; b.style.opacity = .75;
        b.innerHTML = "Enviando…";
        const r = await api(`/api/cobranza/${b.dataset.h}/recordatorio-regina`, { method: "POST" });
        const j = await r.json();
        b.innerHTML = r.ok ? ICO.check(22) + " " + j.mensaje : (j.detail || "No se pudo enviar");
        b.style.background = r.ok ? "var(--verde)" : "var(--gris)";
      });
    }

    function menu() {
      cont.innerHTML = `
        <div style="animation:aparecer .35s ease;max-width:760px">
        ${barraVolver}
        <h1 style="margin:0 0 6px;font-size:clamp(28px,4.4vw,32px);font-weight:800;color:var(--marino)">Hola, ${NOMBRE}</h1>
        <p style="margin:0 0 22px;font-size:20px;color:var(--gris)">Toque un botón, o busque a un cliente.</p>
        <div id="cob-resumen"></div>
        <div style="position:relative;margin-bottom:26px">
          <div style="display:flex;align-items:center;gap:12px;background:#fff;border:2px solid #D4D9E2;border-radius:14px;padding:0 18px">
            <span style="flex:none;color:var(--gris2)">${ICO.buscar(24)}</span>
            <input id="buscador" placeholder="Buscar cliente por nombre o RFC…" autocomplete="off"
                   aria-label="Buscar cliente por nombre o RFC"
                   style="width:100%;border:none;outline:none;padding:17px 0;font-size:20px;background:none;color:var(--tinta)">
          </div>
          <div id="resultados" class="oculto" style="position:absolute;z-index:20;left:0;right:0;margin-top:8px;background:#fff;border:1px solid var(--borde);border-radius:14px;overflow:hidden;box-shadow:0 18px 40px -12px rgba(10,28,51,.25)"></div>
        </div>
        <div style="display:flex;flex-direction:column;gap:16px">
          <button id="ir-roja" class="pao-gigante" style="background:var(--rojo)"><span>POR COBRAR</span><span id="n-roja" class="pao-contador">…</span></button>
          <button id="ir-amarilla" class="pao-gigante" style="background:var(--ambar)"><span>EN CAMINO / EFECTIVO</span><span id="n-amarilla" class="pao-contador">…</span></button>
          <button id="ir-verde" class="pao-gigante" style="background:var(--verde)"><span>PAGADO</span><span id="n-verde" class="pao-contador">…</span></button>
          <button id="ir-citas" class="pao-gigante" style="background:var(--azul)"><span>CITAS</span><span id="n-citas" class="pao-contador">…</span></button>
        </div></div>`;
      pintarResumenCobranza();
      if (volverA) { const b = $("#volver-panel-p"); if (b) b.onclick = () => volverA(); }
      $("#ir-citas").onclick = vistaCitasPao;
      api("/api/citas").then((r) => r.json()).then((cs) => { $("#n-citas").textContent = cs.length; });
      $("#ir-roja").onclick = () => pestana("roja");
      $("#ir-amarilla").onclick = () => pestana("amarilla");
      $("#ir-verde").onclick = () => pestana("verde");
      ["roja", "amarilla", "verde"].forEach(async (p) => {
        const d = await (await api(`/api/cobranza/pestana-${p}?mes=${MES}&anio=${ANIO}`)).json();
        $(`#n-${p}`).textContent = d.length;
      });

      let temporizador;
      $("#buscador").addEventListener("input", (e) => {
        clearTimeout(temporizador);
        const q = e.target.value.trim();
        if (q.length < 2) { $("#resultados").classList.add("oculto"); return; }
        temporizador = setTimeout(async () => {
          const r = await (await api(`/api/cobranza/buscar?q=${encodeURIComponent(q)}`)).json();
          const caja = $("#resultados");
          caja.innerHTML = r.length ? r.map((c) => `
            <div style="padding:16px 18px;border-bottom:1px solid #EEF0F4">
              <div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:6px 14px">
                <div>
                  <p style="margin:0;font-size:20px;font-weight:700">${c.cliente}</p>
                  <p class="tnum" style="margin:2px 0 0;font-size:14px;color:var(--gris2)">RFC ${c.rfc}${c.tipo_cliente === "confianza_especial" ? ' · <strong style="color:var(--azul)">trato especial</strong>' : ""}</p>
                </div>
                ${c.saldo_pendiente
                  ? `<p class="tnum" style="margin:0;font-size:20px;font-weight:800;color:var(--rojo)">Debe ${dinero(c.saldo_pendiente.monto)}</p>`
                  : `<p style="margin:0;display:flex;align-items:center;gap:7px;font-size:18px;font-weight:700;color:var(--verde)">${ICO.check(19)} Al corriente</p>`}
              </div>
              ${c.saldo_pendiente && c.automatizaciones_activas && c.tipo_cliente !== "confianza_especial" ? `
                <button data-h="${c.saldo_pendiente.honorario_id}" class="btn-recordar pao-accion" style="width:100%;margin-top:12px;min-height:54px;font-size:18px;background:var(--azul)">${ICO.enviar(20)} Enviar Recordatorio Amable vía Regina</button>` : ""}
              ${c.saldo_pendiente && (!c.automatizaciones_activas || c.tipo_cliente === "confianza_especial") ? `
                <p style="margin:12px 0 0;font-size:16px;color:var(--gris)">La cobranza de este cliente la lleva personalmente el Director.</p>` : ""}
            </div>`).join("")
            : `<p style="margin:0;padding:16px 18px;font-size:18px;color:var(--gris)">No encontré a nadie con ese nombre o RFC.</p>`;
          caja.classList.remove("oculto");
          conectarRecordatorios();
        }, 350);
      });
    }

    async function pestana(cual) {
      const colores = { roja: "var(--rojo)", amarilla: "var(--ambar)", verde: "var(--verde)" };
      const titulos = { roja: "POR COBRAR", amarilla: "EN CAMINO / EFECTIVO", verde: "PAGADO" };
      const filas = await (await api(`/api/cobranza/pestana-${cual}?mes=${MES}&anio=${ANIO}`)).json();

      let cuerpo;
      if (cual === "roja") {
        cuerpo = filas.map((f) => `
          <div class="carta" style="border-radius:16px;padding:24px;display:flex;flex-direction:column;gap:16px">
            <div style="display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:6px 14px">
              <p style="margin:0;font-size:23px;font-weight:700">${f.cliente}</p>
              <p class="tnum" style="margin:0;font-size:23px;font-weight:800;color:var(--rojo)">${dinero(f.monto)}</p>
            </div>
            ${f.comprobante_pendiente_validar ? `
              <p style="margin:0;display:flex;align-items:center;gap:10px;background:#FBF3E2;color:var(--ambar);font-size:18px;font-weight:700;border-radius:10px;padding:13px 16px">${ICO.clip(21)} Mandó su comprobante: revíselo y confirme.</p>` : ""}
            ${f.dias_vencido > 0 ? `
              <p style="margin:0;display:flex;align-items:center;gap:9px;color:var(--rojo);font-size:17px">${ICO.reloj(19)} Debe desde hace ${f.dias_vencido} días</p>` : ""}
            <button data-h="${f.honorario_id}" class="btn-confirmar pao-accion" style="width:100%;min-height:60px;font-size:20px;background:var(--verde)">${ICO.check(23)} CONFIRMAR PAGO</button>
            ${f.automatizaciones_activas && f.tipo_cliente !== "confianza_especial" ? `
              <button data-h="${f.honorario_id}" class="btn-recordar pao-accion" style="width:100%;min-height:60px;font-size:19px;background:var(--azul)">${ICO.enviar(20)} Enviar Recordatorio Amable vía Regina</button>`
            : `<p style="margin:0;font-size:16px;color:var(--gris)">La cobranza de este cliente la lleva personalmente el Director.</p>`}
            <div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:14px;padding-top:14px;border-top:1px solid #EEF0F4">
              <div style="display:flex;align-items:center;gap:13px">
                <span style="font-size:16.5px">Mensajes automáticos</span>
                <button role="switch" aria-checked="${f.automatizaciones_activas}" data-c="${f.cliente_id}"
                        class="switch btn-switch" aria-label="Mensajes automáticos para ${f.cliente}"></button>
              </div>
              <details>
                <summary style="font-size:16.5px;cursor:pointer;color:var(--azul);font-weight:700;user-select:none">¿Pagará en efectivo?</summary>
                <div style="display:flex;flex-wrap:wrap;gap:10px;padding-top:14px">
                  <button data-h="${f.honorario_id}" class="btn-oxxo pao-accion" style="min-height:54px;padding:0 18px;font-size:17px;background:var(--ambar)">${ICO.codigo(20)} Mandar código OXXO</button>
                  <button data-h="${f.honorario_id}" class="btn-reco pao-accion" style="min-height:54px;padding:0 18px;font-size:17px;background:var(--marino)">${ICO.camion(20)} Pedir que lo recojan</button>
                </div>
              </details>
            </div>
          </div>`).join("") || `
          <div class="carta" style="border-radius:16px;padding:30px;display:flex;align-items:center;gap:16px;color:var(--verde)">
            ${ICO.circuloCheck(36)}<p style="margin:0;font-size:22px;font-weight:700">Nadie debe este mes.</p></div>`;
      } else if (cual === "amarilla") {
        cuerpo = filas.map((f) => `
          <div class="carta" style="border-radius:16px;padding:24px">
            <div style="display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:6px 14px">
              <p style="margin:0;font-size:23px;font-weight:700">${f.cliente}</p>
              <p class="tnum" style="margin:0;font-size:23px;font-weight:800;color:var(--ambar)">${dinero(f.monto)}</p>
            </div>
            ${f.folio_recepcion ? `
              <p style="margin:14px 0 0;display:flex;align-items:center;gap:10px;font-size:19px"><span style="color:var(--azul)">${ICO.sobre(23)}</span> Sobre con folio <strong style="color:var(--azul)">#${f.folio_recepcion}</strong> · ${f.estatus_recoleccion || "esperando"}</p>` : ""}
            ${f.referencia_oxxo ? `
              <p style="margin:12px 0 0;display:flex;align-items:center;gap:10px;font-size:17px;color:var(--gris)">${ICO.codigo(21)} Código OXXO enviado: <span class="tnum">${f.referencia_oxxo}</span></p>` : ""}
            <button data-h="${f.honorario_id}" class="btn-confirmar pao-accion" style="width:100%;margin-top:18px;min-height:60px;font-size:20px;background:var(--verde)">${ICO.check(23)} YA LLEGÓ EL DINERO</button>
          </div>`).join("") || `
          <div class="carta" style="border-radius:16px;padding:30px"><p style="margin:0;font-size:20px;color:var(--gris)">Nadie ha avisado que pagará en efectivo.</p></div>`;
      } else {
        cuerpo = filas.map((f) => `
          <div class="carta" style="border-radius:16px;padding:22px 24px;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 14px">
            <p style="margin:0;display:flex;align-items:center;gap:12px;font-size:21px;font-weight:700"><span style="color:var(--verde)">${ICO.circuloCheck(26)}</span>${f.cliente}</p>
            <p class="tnum" style="margin:0;font-size:21px;font-weight:700;color:var(--verde)">${dinero(f.monto)}</p>
          </div>`).join("") || `
          <div class="carta" style="border-radius:16px;padding:30px"><p style="margin:0;font-size:20px;color:var(--gris)">Todavía no hay pagos este mes.</p></div>`;
      }

      cont.innerHTML = `
        <div style="animation:aparecer .35s ease;max-width:760px">
        <button id="volver" class="pao-accion" style="min-height:56px;padding:0 22px;font-size:19px;background:var(--marino);margin-bottom:24px">${ICO.atras(22)} Regresar al menú</button>
        <h1 style="margin:0 0 20px;font-size:clamp(26px,4.2vw,32px);font-weight:800;color:${colores[cual]}">${titulos[cual]}</h1>
        <div style="display:flex;flex-direction:column;gap:18px">${cuerpo}</div></div>`;
      $("#volver").onclick = menu;

      conectarRecordatorios();
      $$(".btn-confirmar").forEach((b) => b.onclick = async () => {
        b.disabled = true; b.textContent = "Guardando…";
        await api(`/api/cobranza/${b.dataset.h}/confirmar-pago`, { method: "POST" });
        pestana(cual);
      });
      $$(".btn-switch").forEach((b) => b.onclick = async () => {
        const nuevo = b.getAttribute("aria-checked") !== "true";
        await api(`/api/cobranza/cliente/${b.dataset.c}/switch-automatizaciones?activar=${nuevo}`, { method: "POST" });
        b.setAttribute("aria-checked", String(nuevo));
      });
      $$(".btn-oxxo").forEach((b) => b.onclick = async () => {
        b.disabled = true; b.textContent = "Enviando…";
        await api(`/api/cobranza/${b.dataset.h}/activar-efectivo-oxxo`, { method: "POST" });
        pestana("amarilla");
      });
      $$(".btn-reco").forEach((b) => b.onclick = async () => {
        b.disabled = true; b.textContent = "Pidiendo…";
        await api(`/api/cobranza/${b.dataset.h}/solicitar-recoleccion`, { method: "POST" });
        pestana("amarilla");
      });
    }

    menu();
  }

  /* ==================== BLOQUES RESTAURADOS v1.1 ==================== */

  /* ---------- Agenda personal (contador y director) ---------- */
  async function pintarMisCitas() {
    const caja = $("#mis-citas");
    if (!caja) return;
    const citas = await (await api("/api/citas/mias")).json();
    caja.innerHTML = citas.map((c) => {
      const f = new Date(c.fecha_hora);
      return `<div class="carta" style="padding:13px 16px;display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px">
        <span style="color:var(--azul)">${ICO.calendario(17)}</span>
        <span class="tnum" style="font-size:13px;font-weight:700;color:var(--marino)">
          ${f.toLocaleDateString("es-MX", { day: "2-digit", month: "short" })} ·
          ${f.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" })}</span>
        <span style="font-size:13.5px;font-weight:600;flex:1;min-width:120px">${c.cliente}</span>
        <span style="font-size:11.5px;color:${c.estatus === "solicitada" ? "var(--ambar)" : "var(--verde)"};font-weight:700;text-transform:uppercase;letter-spacing:.06em">
          ${c.estatus === "solicitada" ? "por confirmar" : c.modalidad}</span>
      </div>`;
    }).join("") ||
      `<p style="margin:0;font-size:13px;color:var(--gris2)">Sin citas próximas.</p>`;
  }

  /* ---------- Citas (kiosco de Pao) ---------- */
  async function vistaCitasPao() {
    const cont = $("#contenido");
    const [citas, buscables, equipo] = await Promise.all([
      (await api("/api/citas")).json(),
      (await api("/api/citas/clientes-agendables")).json(),
      (await api("/api/citas/equipo-agendable")).json(),
    ]);
    const fmtLocal = (d) => { const x = new Date(d); x.setMinutes(x.getMinutes() - x.getTimezoneOffset()); return x.toISOString().slice(0, 16); };

    const filas = citas.map((c) => `
      <div class="carta" style="padding:20px 22px;display:flex;flex-direction:column;gap:12px">
        <div style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;align-items:baseline">
          <p style="margin:0;font-size:22px;font-weight:800">${c.cliente}</p>
          <span style="font-size:15px;font-weight:800;color:${c.estatus === "solicitada" ? "var(--ambar)" : "var(--verde)"}">
            ${c.estatus === "solicitada" ? "POR CONFIRMAR" : "CONFIRMADA"}</span>
        </div>
        <p style="margin:0;font-size:18px;color:#43506B;display:flex;align-items:center;gap:9px">
          ${ICO.calendario(20)} Con <strong>${c.con}</strong> · ${c.modalidad}</p>
        ${c.motivo ? `<p style="margin:0;font-size:16px;color:var(--gris)">Motivo: ${c.motivo}</p>` : ""}
        <input type="datetime-local" class="campo cita-fecha" data-id="${c.id}"
               value="${fmtLocal(c.fecha_hora)}" style="font-size:17px;max-width:280px">
        <div style="display:flex;flex-wrap:wrap;gap:10px">
          ${c.estatus === "solicitada" ? `
          <button class="pao-accion btn-cita-confirmar" data-id="${c.id}" style="background:var(--verde);flex:1;min-width:200px">
            ${ICO.check(22)} CONFIRMAR</button>` : `
          <button class="pao-accion btn-cita-confirmar" data-id="${c.id}" style="background:var(--azul);flex:1;min-width:200px">
            ${ICO.check(22)} GUARDAR CAMBIO DE HORA</button>`}
          <button class="pao-accion btn-cita-cancelar" data-id="${c.id}" style="background:var(--gris2)">Cancelar</button>
        </div>
      </div>`).join("") ||
      `<div class="carta" style="padding:26px;font-size:20px;color:var(--gris)">No hay citas pendientes ni próximas.</div>`;

    cont.innerHTML = `
      <div style="animation:aparecer .35s ease;max-width:760px" class="pao">
      <button id="volver" class="pao-accion" style="background:var(--marino);margin-bottom:22px">${ICO.atras(22)} Regresar al menú</button>
      <h1 style="margin:0 0 18px;font-size:30px;font-weight:800;color:var(--azul)">CITAS</h1>
      <div style="display:flex;flex-direction:column;gap:14px">${filas}</div>

      <div class="carta" style="padding:22px;margin-top:26px">
        <p style="margin:0 0 14px;font-size:21px;font-weight:800">Agendar una cita nueva</p>
        <div style="display:flex;flex-direction:column;gap:10px">
          <select id="nc-cliente" class="campo" style="font-size:17px">
            ${buscables.map((f) => `<option value="${f.cliente_id}">${f.cliente}</option>`).join("")}</select>
          <select id="nc-con" class="campo" style="font-size:17px">
            ${equipo.map((p) => `<option value="${p.usuario_id}">${p.nombre} — ${p.etiqueta}</option>`).join("")}</select>
          <input id="nc-fecha" type="datetime-local" class="campo" style="font-size:17px">
          <select id="nc-modalidad" class="campo" style="font-size:17px">
            <option value="presencial">En la oficina</option>
            <option value="videollamada">Videollamada</option>
            <option value="llamada">Por teléfono</option></select>
          <input id="nc-motivo" class="campo" placeholder="Motivo (opcional)" style="font-size:17px">
          <button id="nc-crear" class="pao-accion" style="background:var(--azul);width:100%">
            ${ICO.calendario(22)} AGENDAR Y AVISAR</button>
          <p id="nc-msj" class="oculto" style="margin:0;font-size:17px;font-weight:700"></p>
        </div>
      </div></div>`;

    $("#volver").onclick = () => vistaPao();
    $$(".btn-cita-confirmar").forEach((b) => b.onclick = async () => {
      const fecha = document.querySelector(`.cita-fecha[data-id="${b.dataset.id}"]`).value;
      b.disabled = true; b.textContent = "Guardando…";
      const r = await api(`/api/citas/${b.dataset.id}/confirmar`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fecha_hora: fecha ? new Date(fecha).toISOString() : null }) });
      if (r.ok) vistaCitasPao();
    });
    $$(".btn-cita-cancelar").forEach((b) => b.onclick = async () => {
      b.disabled = true;
      await api(`/api/citas/${b.dataset.id}/cancelar`, { method: "POST" });
      vistaCitasPao();
    });
    $("#nc-crear").onclick = async () => {
      const msj = $("#nc-msj"); const fecha = $("#nc-fecha").value;
      if (!fecha) { msj.textContent = "Elija fecha y hora."; msj.style.color = "var(--rojo)";
        msj.classList.remove("oculto"); return; }
      $("#nc-crear").disabled = true;
      const r = await api("/api/citas", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cliente_id: +$("#nc-cliente").value,
          con_usuario_id: +$("#nc-con").value,
          fecha_hora: new Date(fecha).toISOString(),
          modalidad: $("#nc-modalidad").value,
          motivo: $("#nc-motivo").value || null }) });
      const j = await r.json();
      $("#nc-crear").disabled = false;
      msj.textContent = r.ok ? j.mensaje : (j.detail || "No se pudo agendar.");
      msj.style.color = r.ok ? "var(--verde)" : "var(--rojo)";
      msj.classList.remove("oculto");
      if (r.ok) setTimeout(vistaCitasPao, 1200);
    };
  }

  /* ---------- Configuración visual de 2FA (pantalla de login) ---------- */
  if ($("#abrir-2fa")) {
    $("#abrir-2fa").onclick = () => $("#caja-2fa").classList.toggle("oculto");
    $("#btn-generar-qr").onclick = async () => {
      const msj = $("#msj-2fa");
      const datos = new URLSearchParams({ email: $("#email").value, password: $("#password").value });
      const r = await fetch("/api/auth/2fa/enrolar", { method: "POST", body: datos });
      const j = await r.json();
      if (!r.ok) {
        msj.textContent = j.detail === "2FA ya está activo para esta cuenta"
          ? "Su 2FA ya está activo: entre normalmente con su código."
          : (j.detail || "Escriba primero su correo y contraseña arriba.");
        msj.style.color = "var(--rojo)"; msj.classList.remove("oculto"); return;
      }
      $("#img-qr").src = j.qr;
      $("#zona-qr").classList.remove("oculto");
      msj.classList.add("oculto");
    };
    $("#btn-verificar-totp").onclick = async () => {
      const msj = $("#msj-2fa");
      const datos = new URLSearchParams({ email: $("#email").value,
        password: $("#password").value, codigo_totp: $("#verificar-totp").value.trim() });
      const r = await fetch("/api/auth/2fa/verificar", { method: "POST", body: datos });
      const j = await r.json();
      msj.textContent = r.ok ? "Listo: su 2FA quedó activo. Entre con su código de la app."
                             : (j.detail || "Código incorrecto, intente de nuevo.");
      msj.style.color = r.ok ? "var(--verde)" : "var(--rojo)";
      msj.classList.remove("oculto");
      if (r.ok) { $("#zona-qr").classList.add("oculto"); $("#codigo-totp").focus(); }
    };
  }

  /* ==================== ADMINISTRACIÓN (Director) ==================== */
  async function subAdmin() {
    const [clientes, personal] = await Promise.all([
      (await api("/api/admin/clientes")).json(),
      (await api("/api/admin/personal")).json(),
    ]);
    const contables = personal.filter((p) => p.activo && (p.rol === "contador" || p.rol === "director"));

    const filaCliente = (c) => `
      <div class="fila" style="flex-wrap:wrap;gap:10px 16px;${c.estatus === "suspendido" ? "opacity:.55" : ""}">
        <div style="flex:1;min-width:180px">
          <p style="margin:0;font-size:14px;font-weight:700">${c.nombre_comercial}</p>
          <p class="tnum" style="margin:2px 0 0;font-size:11.5px;color:var(--gris2)">${c.rfc} · ${c.telefono}</p>
          <p style="margin:3px 0 0;font-size:11.5px;font-weight:700;color:${c.regimen_fiscal ? "var(--azul)" : "var(--ambar)"}">
            ${c.regimen_fiscal ? (NOMBRES_REGIMEN[c.regimen_fiscal] || c.regimen_fiscal) : "⚠ Sin régimen fiscal — la calculadora no funcionará"}</p>
        </div>
        <label style="display:flex;flex-direction:column;gap:3px;font-size:10.5px;font-weight:700;color:var(--gris2);text-transform:uppercase;letter-spacing:.08em">
          Contador(a) asignado(a)
          <select class="campo adm-contador" data-c="${c.id}" style="padding:7px 9px;font-size:12.5px;min-width:170px">
            <option value="">— Sin asignar —</option>
            ${contables.map((p) => `<option value="${p.id}" ${p.id === c.contador_asignado_id ? "selected" : ""}>${p.nombre}</option>`).join("")}
          </select>
        </label>
        <div style="display:flex;gap:14px;flex-wrap:wrap;align-items:center">
          ${[["adm-especial", "Trato especial", c.tipo_cliente === "confianza_especial"],
             ["adm-urgente", "Requerim. urgente", c.requerimiento_urgente]].map(([cl, et, on]) => `
          <label style="display:flex;align-items:center;gap:7px;font-size:12px;font-weight:600;cursor:pointer">
            <input type="checkbox" class="${cl}" data-c="${c.id}" ${on ? "checked" : ""} style="width:17px;height:17px;accent-color:var(--azul)">
            ${et}</label>`).join("")}
          <label style="display:flex;align-items:center;gap:7px;font-size:12px;font-weight:600;cursor:pointer">
            <input type="checkbox" class="adm-imss" data-c="${c.id}" ${c.tiene_imss ? "checked" : ""} style="width:17px;height:17px;accent-color:var(--azul)">
            IMSS</label>
          <button class="chip adm-expediente" data-c="${c.id}" data-n="${c.nombre_comercial}">Expediente ›</button>
          <label style="display:flex;align-items:center;gap:7px;font-size:12px;font-weight:600;cursor:pointer">
            <input type="checkbox" class="adm-nomina" data-c="${c.id}" ${c.tiene_nomina ? "checked" : ""} style="width:17px;height:17px;accent-color:var(--azul)">
            Nómina</label>
          <select class="campo adm-periodicidad" data-c="${c.id}" style="padding:6px 8px;font-size:11.5px" ${c.tiene_nomina ? "" : "disabled"}>
            ${["semanal", "quincenal", "mensual"].map((p) => `<option value="${p}" ${c.periodicidad_nomina === p ? "selected" : ""}>${p}</option>`).join("")}
          </select>
          <button class="adm-editar chip" data-c="${c.id}" style="color:var(--azul);border-color:var(--azul-borde)">Editar</button>
          <button class="adm-password chip" data-c="${c.id}" title="Generar contraseña temporal para entregar">Contraseña</button>
          <button class="adm-estatus chip" data-c="${c.id}" data-a="${c.estatus === "activo" ? "baja" : "reactivar"}">
            ${c.estatus === "activo" ? "Suspender" : "Reactivar"}</button>
        </div>
      </div>`;

    $("#sub-vista").innerHTML = `
      <div style="display:flex;flex-wrap:wrap;gap:24px;align-items:flex-start;animation:aparecer .3s ease">
        <div style="flex:2;min-width:min(100%,420px)">
          <p class="micro" style="margin:0 0 12px">Clientes del despacho — todo con un clic</p>
          <div class="carta" style="overflow:hidden">${clientes.map(filaCliente).join("")}</div>
          <p class="micro" style="margin:28px 0 12px">Equipo interno</p>
          <div class="carta" style="overflow:hidden">
            ${personal.map((p) => `
            <div class="fila" style="${p.activo ? "" : "opacity:.55"}">
              <div style="flex:1"><p style="margin:0;font-size:14px;font-weight:700">${p.nombre}</p>
                <p style="margin:2px 0 0;font-size:11.5px;color:var(--gris2)">${p.email} · ${p.rol.replace("_", " ")}
                ${p.totp_habilitado ? " · 2FA activo" : " · <span style='color:var(--ambar)'>sin 2FA</span>"}</p></div>
              ${p.activo ? `<button class="adm-baja-personal chip" data-p="${p.id}">Dar de baja</button>` : "<span style='font-size:12px;color:var(--gris2)'>Inactivo</span>"}
            </div>`).join("")}
          </div>
        </div>
        <div style="flex:1;min-width:min(100%,300px);display:flex;flex-direction:column;gap:18px">
          <div class="carta" style="padding:20px">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:3px">
              <p style="margin:0;font-size:15px;font-weight:800;color:var(--marino)">Nuevo cliente</p>
              <button id="btn-alta-masiva" class="chip" style="color:var(--azul);border-color:var(--azul-borde)">⇪ Alta masiva</button>
            </div>
            <p style="margin:0 0 14px;font-size:11.5px;color:var(--gris2);line-height:1.5">El régimen fiscal define qué calculadora usará el contador con este cliente.</p>
            <div style="display:flex;flex-direction:column;gap:9px">
              <input id="nc2-nombre" class="campo" placeholder="Nombre comercial *" style="padding:10px;font-size:13px">
              <input id="nc2-razon" class="campo" placeholder="Razón social *" style="padding:10px;font-size:13px">
              <input id="nc2-rfc" class="campo" placeholder="RFC *" style="padding:10px;font-size:13px;text-transform:uppercase">
              <input id="nc2-tel" class="campo" placeholder="WhatsApp * (+52...)" style="padding:10px;font-size:13px">
              <input id="nc2-email" class="campo" placeholder="Correo (necesario para el portal)" style="padding:10px;font-size:13px">

              <p class="micro" style="margin:6px 0 0">Perfil fiscal</p>
              <select id="nc2-persona" class="campo" style="padding:10px;font-size:13px">
                <option value="">Tipo de persona…</option>
                <option value="fisica">Persona física</option>
                <option value="moral">Persona moral</option>
              </select>
              <select id="nc2-regimen" class="campo" style="padding:10px;font-size:13px">
                <option value="">Régimen fiscal…</option>
              </select>

              <p class="micro" style="margin:6px 0 0">Clasificación y obligaciones</p>
              <select id="nc2-tipo" class="campo" style="padding:10px;font-size:13px">
                <option value="estandar">Estándar</option>
                <option value="vip">VIP</option>
                <option value="confianza_especial">Confianza especial (sin cobranza automática)</option>
              </select>
              <div style="display:flex;gap:14px;flex-wrap:wrap;padding:2px 0">
                <label style="display:flex;align-items:center;gap:7px;font-size:12.5px;font-weight:600;cursor:pointer">
                  <input type="checkbox" id="nc2-imss" style="width:17px;height:17px;accent-color:var(--azul)"> IMSS</label>
                <label style="display:flex;align-items:center;gap:7px;font-size:12.5px;font-weight:600;cursor:pointer">
                  <input type="checkbox" id="nc2-nomina" style="width:17px;height:17px;accent-color:var(--azul)"> Nómina</label>
                <select id="nc2-periodicidad" class="campo" style="padding:6px 8px;font-size:11.5px;width:auto" disabled>
                  <option value="semanal">semanal</option>
                  <option value="quincenal" selected>quincenal</option>
                  <option value="mensual">mensual</option>
                </select>
              </div>

              <p class="micro" style="margin:6px 0 0">Cobranza · de aquí come el módulo de cobranza</p>
              <div style="display:grid;grid-template-columns:1.2fr 1fr .8fr;gap:8px">
                <input id="nc2-honorario" class="campo" type="number" step="0.01" placeholder="Honorario ($)" style="padding:10px;font-size:13px">
                <select id="nc2-per-honorario" class="campo" style="padding:10px;font-size:13px">
                  <option value="mensual">mensual</option>
                  <option value="bimestral">bimestral</option>
                  <option value="anual">anual</option>
                </select>
                <input id="nc2-corte" class="campo" type="number" min="1" max="28" value="1" placeholder="Día" style="padding:10px;font-size:13px">
              </div>
              <div style="display:grid;grid-template-columns:1.4fr 1fr;gap:8px">
                <input id="nc2-adeudo-concepto" class="campo" placeholder="Concepto del adeudo anterior (opcional)" style="padding:10px;font-size:13px">
                <input id="nc2-adeudo" class="campo" type="number" step="0.01" placeholder="Adeudo anterior ($)" style="padding:10px;font-size:13px">
              </div>

              <p class="micro" style="margin:6px 0 0">Bases de CONTPAQi (opcional)</p>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
                <input id="nc2-bd-conta" class="campo" placeholder="Contabilidad (ctEJEMPLO)" style="padding:10px;font-size:13px">
                <input id="nc2-bd-nomina" class="campo" placeholder="Nóminas (nomEJEMPLO)" style="padding:10px;font-size:13px">
              </div>

              <p class="micro" style="margin:6px 0 0">Acceso al portal</p>
              <label style="display:flex;align-items:center;gap:7px;font-size:12.5px;font-weight:600;cursor:pointer">
                <input type="checkbox" id="nc2-cuenta" style="width:17px;height:17px;accent-color:var(--azul)">
                Crear su cuenta ahora</label>
              <input id="nc2-pass" class="campo oculto" placeholder="Contraseña (vacío = el sistema genera una)" style="padding:10px;font-size:13px">

              <button id="nc2-crear" class="btn btn-azul" style="min-height:44px;font-size:13.5px;margin-top:4px">Dar de alta</button>
              <p id="nc2-msj" class="oculto" style="margin:0;font-size:12px;font-weight:700;line-height:1.6"></p>
            </div>
          </div>
          <div class="carta" style="padding:20px">
            <p style="margin:0 0 12px;font-size:15px;font-weight:800;color:var(--marino)">Nuevo integrante del equipo</p>
            <div style="display:flex;flex-direction:column;gap:9px">
              <input id="np-nombre" class="campo" placeholder="Nombre" style="padding:10px;font-size:13px">
              <input id="np-email" class="campo" placeholder="Correo" style="padding:10px;font-size:13px">
              <input id="np-pass" type="password" class="campo" placeholder="Contraseña temporal" style="padding:10px;font-size:13px">
              <select id="np-rol" class="campo" style="padding:10px;font-size:13px">
                <option value="contador">Contador(a) — elabora; no autoriza</option>
                <option value="admin_secretaria">Secretaria — cobranza y contabilidades</option>
                <option value="supervisor">Supervisor(a) — contadora y autoriza (puede autofirmar)</option>
                <option value="director">Director — acceso total al despacho</option>
                <option value="administrador">Administrador del sistema — acceso técnico total</option>
              </select>
              <p style="margin:0;font-size:11px;color:var(--gris2);line-height:1.5">
                El <strong>Contador</strong> nunca autoriza sus propios cálculos.
                La <strong>Supervisora</strong> sí puede, y esas autofirmas quedan marcadas en la bitácora.</p>
              <button id="np-crear" class="btn btn-azul" style="min-height:42px;font-size:13.5px">Dar de alta</button>
              <p id="np-msj" class="oculto" style="margin:0;font-size:12px;font-weight:700"></p>
            </div>
          </div>
        </div>
      </div>`;

    const post = (url) => api(url, { method: "POST" });
    $$(".adm-contador").forEach((sel) => sel.onchange = async () => {
      if (sel.value) await post(`/api/admin/clientes/${sel.dataset.c}/asignar-contador?usuario_id=${sel.value}`);
    });
    $$(".adm-especial").forEach((ch) => ch.onchange = () =>
      post(`/api/admin/clientes/${ch.dataset.c}/trato-especial?activar=${ch.checked}`));
    $$(".adm-urgente").forEach((ch) => ch.onchange = () =>
      post(`/api/admin/clientes/${ch.dataset.c}/requerimiento-urgente?activar=${ch.checked}`));
    const guardarObligaciones = (cid) => {
      const fila = document.querySelector(`.adm-imss[data-c="${cid}"]`).closest(".fila");
      const imss = fila.querySelector(".adm-imss").checked;
      const nomina = fila.querySelector(".adm-nomina").checked;
      const per = fila.querySelector(".adm-periodicidad");
      per.disabled = !nomina;
      return post(`/api/admin/clientes/${cid}/obligaciones?tiene_imss=${imss}&tiene_nomina=${nomina}&periodicidad_nomina=${per.value}`);
    };
    $$(".adm-expediente").forEach((b) => b.onclick = () =>
      vistaExpediente(+b.dataset.c, b.dataset.n, () => panelPrincipal("admin")));
    $$(".adm-imss,.adm-nomina,.adm-periodicidad").forEach((el) =>
      el.onchange = () => guardarObligaciones(el.dataset.c));
    $$(".adm-estatus").forEach((b) => b.onclick = async () => {
      await post(`/api/admin/clientes/${b.dataset.c}/${b.dataset.a}`); subAdmin(); });

    // --- EDITAR CLIENTE: todo corregible, con rastro de auditoría ---
    $$(".adm-editar").forEach((b) => b.onclick = () => {
      const c = clientes.find((x) => x.id === +b.dataset.c);
      abrirEdicionCliente(c, CAT);
    });

    // --- CONTRASEÑA TEMPORAL: se genera y se muestra para entregarla ---
    $$(".adm-password").forEach((b) => b.onclick = async () => {
      const c = clientes.find((x) => x.id === +b.dataset.c);
      if (!confirm(`¿Generar una contraseña temporal para ${c.nombre_comercial}?\n\n` +
                   `Si ya tenía una, dejará de funcionar. Se la entrega usted al cliente ` +
                   `y él la cambia al entrar.`)) return;
      const r = await api(`/api/admin/clientes/${c.id}/regenerar-password`, { method: "POST" });
      const j = await r.json();
      if (!r.ok) { alert(j.detail || "No se pudo generar."); return; }
      mostrarPasswordTemporal(c.nombre_comercial, j.email, j.password_temporal);
    });
    $$(".adm-baja-personal").forEach((b) => b.onclick = async () => {
      await post(`/api/admin/personal/${b.dataset.p}/baja`); subAdmin(); });

    $("#btn-alta-masiva").onclick = abrirAltaMasiva;

    // Catálogo de regímenes: el selector se filtra por tipo de persona
    const CAT = await (await api("/api/calculos/regimenes")).json();
    function llenarRegimenes(selector, tipoPersona, seleccionado) {
      const sel = $(selector);
      const opciones = Object.entries(CAT.regimenes).filter(([k]) => {
        if (k.startsWith("anual_")) return false;   // las anuales no son "el régimen del cliente"
        if (!tipoPersona) return true;
        return CAT.tipo_persona[k] === tipoPersona;
      });
      sel.innerHTML = `<option value="">Régimen fiscal…</option>` +
        opciones.map(([k, v]) => `<option value="${k}" ${k === seleccionado ? "selected" : ""}>${v}</option>`).join("");
    }
    llenarRegimenes("#nc2-regimen", "");
    $("#nc2-persona").onchange = () => llenarRegimenes("#nc2-regimen", $("#nc2-persona").value);
    $("#nc2-nomina").onchange = () => { $("#nc2-periodicidad").disabled = !$("#nc2-nomina").checked; };
    $("#nc2-cuenta").onchange = () => $("#nc2-pass").classList.toggle("oculto", !$("#nc2-cuenta").checked);

    $("#nc2-crear").onclick = async () => {
      const msj = $("#nc2-msj");
      const faltan = [];
      if (!$("#nc2-nombre").value) faltan.push("nombre comercial");
      if (!$("#nc2-razon").value) faltan.push("razón social");
      if (!$("#nc2-rfc").value) faltan.push("RFC");
      if (!$("#nc2-tel").value) faltan.push("WhatsApp");
      if ($("#nc2-cuenta").checked && !$("#nc2-email").value) faltan.push("correo (para el portal)");
      if (faltan.length) {
        msj.innerHTML = `Falta capturar: ${faltan.join(", ")}.`;
        msj.style.color = "var(--rojo)"; msj.classList.remove("oculto"); return;
      }
      $("#nc2-crear").disabled = true;
      const r = await api("/api/admin/clientes", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre_comercial: $("#nc2-nombre").value,
          razon_social: $("#nc2-razon").value, rfc: $("#nc2-rfc").value.toUpperCase(),
          telefono_whatsapp: $("#nc2-tel").value,
          email: $("#nc2-email").value || null, tipo_cliente: $("#nc2-tipo").value,
          tipo_persona: $("#nc2-persona").value || null,
          regimen_fiscal: $("#nc2-regimen").value || null,
          tiene_imss: $("#nc2-imss").checked, tiene_nomina: $("#nc2-nomina").checked,
          periodicidad_nomina: $("#nc2-periodicidad").value,
          honorario_mensual: $("#nc2-honorario").value ? +$("#nc2-honorario").value : null,
          periodicidad_honorario: $("#nc2-per-honorario").value,
          dia_corte_honorario: +$("#nc2-corte").value || 1,
          adeudo_previo_monto: $("#nc2-adeudo").value ? +$("#nc2-adeudo").value : null,
          adeudo_previo_concepto: $("#nc2-adeudo-concepto").value || null,
          bd_contpaq_contabilidad: $("#nc2-bd-conta").value || null,
          bd_contpaq_nomina: $("#nc2-bd-nomina").value || null,
          crear_cuenta: $("#nc2-cuenta").checked,
          password_portal: $("#nc2-pass").value || null }) });
      const j = await r.json();
      $("#nc2-crear").disabled = false;
      if (!r.ok) {
        msj.textContent = (j.detail && j.detail[0] && j.detail[0].msg) || j.detail || "Revise los datos.";
        msj.style.color = "var(--rojo)"; msj.classList.remove("oculto"); return;
      }
      if (j.password_temporal) {
        // Se muestra UNA sola vez: el Director la entrega al cliente
        msj.innerHTML = `Cliente dado de alta.<br><span style="color:var(--marino)">Contraseña para entregar:</span>
          <span class="tnum" style="display:inline-block;margin-top:4px;background:var(--azul-suave);border:1px solid var(--azul-borde);border-radius:8px;padding:6px 10px;font-size:14px;font-weight:800;color:var(--azul);user-select:all">${j.password_temporal}</span>
          <br><span style="font-weight:500;color:var(--gris2)">Anótela: no se vuelve a mostrar. El cliente deberá cambiarla al entrar.</span>`;
        msj.style.color = "var(--verde)"; msj.classList.remove("oculto");
        setTimeout(subAdmin, 12000);   // tiempo suficiente para copiarla
      } else {
        msj.textContent = "Cliente dado de alta.";
        msj.style.color = "var(--verde)"; msj.classList.remove("oculto");
        setTimeout(subAdmin, 900);
      }
    };
    $("#np-crear").onclick = async () => {
      const msj = $("#np-msj");
      const r = await api("/api/admin/personal", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre: $("#np-nombre").value, email: $("#np-email").value,
          password: $("#np-pass").value, rol: $("#np-rol").value }) });
      const j = await r.json();
      msj.textContent = r.ok ? "Integrante dado de alta. Deberá configurar su 2FA al entrar."
                             : ((j.detail && j.detail[0] && j.detail[0].msg) || j.detail || "Revise los datos.");
      msj.style.color = r.ok ? "var(--verde)" : "var(--rojo)";
      msj.classList.remove("oculto");
      if (r.ok) setTimeout(subAdmin, 1200);
    };
  }


  /* ==================== DETERMINACIÓN DE IMPUESTOS v1.2 ==================== */

  const ETQ_CAMPOS = {
    ingresos_acumulados: "Ingresos acumulados", deducciones_acumuladas: "Deducciones acumuladas",
    ingresos_nominales_acumulados: "Ingresos nominales acumulados", coeficiente_utilidad: "Coeficiente de utilidad",
    pagos_provisionales_anteriores: "Pagos provisionales anteriores", retenciones_isr: "Retenciones de ISR",
    iva_trasladado: "IVA trasladado cobrado", iva_acreditable: "IVA acreditable pagado",
    iva_retenido: "IVA retenido", base_nomina: "Base de nómina (ISN)", general: "Comentario general",
  };
  const ETQ_RESULT = {
    ingresos_acumulados: "Ingresos acumulados", deducciones_acumuladas: "(−) Deducciones acumuladas",
    base_gravable: "(=) Base gravable", limite_inferior: "(−) Límite inferior",
    excedente_limite_inferior: "(=) Excedente del límite inferior",
    tasa_marginal_pct: "(×) Tasa sobre excedente %", impuesto_marginal: "(=) Impuesto marginal",
    cuota_fija: "(+) Cuota fija", isr_causado_periodo: "(=) ISR causado del periodo",
    ingresos_nominales_acumulados: "Ingresos nominales acumulados",
    coeficiente_utilidad: "(×) Coeficiente de utilidad",
    utilidad_fiscal_estimada: "(=) Utilidad fiscal estimada", tasa_pct: "(×) Tasa %",
    pagos_provisionales_anteriores: "(−) Pagos provisionales anteriores",
    retenciones_isr: "(−) Retenciones de ISR", isr_a_cargo: "(=) ISR A CARGO",
    iva_trasladado: "IVA trasladado cobrado", iva_acreditable: "(−) IVA acreditable pagado",
    iva_retenido: "(−) IVA retenido", iva_a_cargo: "(=) IVA A CARGO", saldo_a_favor: "Saldo a favor",
    base_nomina: "Base de nómina", isn_determinado: "(=) ISN DETERMINADO (Zacatecas)",
    limite_superior: null, regimen: null, mes: null,
  };

  function tablaResultado(res) {
    const fila = (k, v, fuerte) => ETQ_RESULT[k] === null ? "" : `
      <div style="display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-bottom:1px solid #EEF0F4;${fuerte ? "font-weight:800;color:var(--marino)" : ""}">
        <span style="font-size:13px">${ETQ_RESULT[k] || k}</span>
        <span class="tnum" style="font-size:13px">${typeof v === "number" && !String(k).includes("pct") && k !== "coeficiente_utilidad" ? dinero(v) : v}</span></div>`;
    const bloque = (titulo, obj, claveFinal) => `
      <p class="micro" style="margin:16px 0 6px">${titulo}</p>
      ${Object.entries(obj).map(([k, v]) => fila(k, v, k === claveFinal)).join("")}`;
    return `${bloque("ISR — como en la página del SAT", res.isr, "isr_a_cargo")}
            ${bloque("IVA", res.iva, "iva_a_cargo")}
            ${bloque("Impuesto sobre nómina", res.isn, "isn_determinado")}
            <div style="display:flex;justify-content:space-between;padding:12px 0 0;font-size:16px;font-weight:800;color:var(--azul)">
              <span>TOTAL A PAGAR DEL PERIODO</span><span class="tnum">${dinero(res.total_a_pagar)}</span></div>
            <p style="margin:8px 0 0;font-size:11px;color:var(--gris2)">Tarifa ${res.anio_tarifa}: límites, cuota fija y tasa se rellenan en automático.</p>`;
  }

  const chipEstatus = (e) => {
    const c = { borrador: "var(--gris2)", en_autorizacion: "var(--ambar)",
      autorizado: "var(--verde)", rechazado: "var(--rojo)", declarado: "var(--azul)" }[e];
    return `<span style="font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:${c}">${e.replace("_", " ")}</span>`;
  };

  /* ---------- Pantalla del contador: capturar y calcular ---------- */
  async function vistaCalculos(volverA) {
    const cont = $("#contenido");
    const [clientes, catalogo, calcs] = await Promise.all([
      (await api("/api/citas/clientes-agendables")).json(),
      (await api("/api/calculos/regimenes")).json(),
      (await api(`/api/calculos/mios?mes=${MES}&anio=${ANIO}`)).json(),
    ]);
    const porCliente = {}; calcs.forEach((c) => porCliente[c.cliente_id] = c);
    const ETQ_V2 = {};
    Object.entries(catalogo.campos).forEach(([reg, lista]) =>
      ETQ_V2[reg] = Object.fromEntries(lista));

    cont.innerHTML = `
      <div style="animation:aparecer .3s ease">
      <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:16px">
        <button id="volver-calc" class="btn btn-linea" style="min-height:40px">${ICO.atras(15)} Regresar</button>
        <h1 class="h1" style="margin:0;flex:1">Determinación de impuestos · ${NOMBRE_MES}</h1>
        <button id="calc-split" class="chip oculto">◫ Balanza a un lado</button>
      </div>
      <div id="calc-zona" style="display:flex;flex-wrap:wrap;gap:20px;align-items:flex-start">
        <div class="carta" style="flex:1;min-width:min(100%,330px);padding:22px">
          <div style="display:flex;flex-direction:column;gap:10px">
            <label class="etiqueta" style="margin:0">Cliente
              <select id="calc-cliente" class="campo" style="margin-top:4px">${clientes.map((c) =>
                `<option value="${c.cliente_id}">${c.cliente}</option>`).join("")}</select></label>
            <p id="calc-regimen-badge" style="margin:0;font-size:12px;font-weight:800"></p>
            <p class="micro" style="margin:8px 0 0">Captura SOLO el mes — el sistema acumula, arrastra saldos a favor y sugiere pagos provisionales</p>
            <div id="calc-prediccion"></div>
        <div id="calc-saldos"></div>
        <div id="campos-v2" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(145px,1fr));gap:8px"></div>
            <button id="calc-guardar" class="btn btn-azul" style="min-height:46px;margin-top:6px">Calcular y guardar</button>
            <button id="calc-enviar" class="btn btn-linea oculto" style="min-height:44px">Enviar a autorización (Director y Supervisora)</button>
            <p id="calc-msj" class="oculto" style="margin:0;font-size:12.5px;font-weight:700"></p>
            <div id="calc-correcciones"></div>
          </div>
        </div>
        <div style="flex:1.15;min-width:min(100%,340px);display:flex;flex-direction:column;gap:16px">
          <div class="carta" style="padding:22px">
            <p style="margin:0 0 4px;font-size:15px;font-weight:800;color:var(--marino)">Hoja de cálculo (papel de trabajo)</p>
            <div id="calc-resultado"><p style="margin:12px 0 0;font-size:13px;color:var(--gris2)">
              Capture los datos del mes y toque «Calcular y guardar»: tarifas, tasas, acumulados y arrastres se rellenan solos (en azul).</p></div>
          </div>
          <div id="panel-balanza" class="carta oculto" style="padding:14px">
            <div style="display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;margin-bottom:8px">
              <p style="margin:0;flex:1;font-size:13px;font-weight:800;color:var(--marino)">Balanza de comprobación del periodo (CONTPAQ)</p>
              <label class="btn btn-linea" style="min-height:36px;font-size:12px;display:inline-flex;align-items:center;cursor:pointer;padding:0 12px">
                <span id="bal-etq-subir">Subir balanza (PDF)</span>
                <input type="file" accept="application/pdf" id="bal-archivo" style="display:none"></label>
            </div>
            <p id="bal-msj" class="oculto" style="margin:0 0 8px;font-size:12px;font-weight:700"></p>
            <div id="visor-balanza" style="min-height:460px"></div>
          </div>
        </div>
      </div></div>`;

    let balanzaDoc = null;
    function pintarCampos(regimen, valores = {}) {
      $("#campos-v2").innerHTML = (catalogo.campos[regimen] || []).map(([k, etq]) => `
        <label class="etiqueta" style="margin:0;font-size:10px">${etq}
          <input type="number" step="0.0001" data-k="${k}" class="campo dato-calc"
            value="${valores[k] ?? ""}" style="margin-top:3px;padding:8px 9px;font-size:12.5px"></label>`).join("");
    }
    async function refrescarBalanza(clienteId) {
      const r = await api(`/api/calculos/balanza-periodo?cliente_id=${clienteId}&mes=${MES}&anio=${ANIO}`);
      balanzaDoc = r.ok ? ((await r.json()).documento_id || null) : null;
      // El botón vive SIEMPRE: si no hay balanza, el panel invita a subirla.
      $("#calc-split").classList.remove("oculto");
      $("#calc-split").textContent = balanzaDoc ? "◫ Balanza a un lado" : "◫ Subir balanza";
      const be = $("#bal-etq-subir");
      if (be) be.textContent = balanzaDoc ? "Reemplazar balanza (PDF)" : "Subir balanza (PDF)";
    }
    function regimenDelCliente() {
      const c = clientes.find((x) => x.cliente_id === +$("#calc-cliente").value);
      return c && c.regimen_fiscal;
    }
    function cargarExistente() {
      const cid = +$("#calc-cliente").value;
      const reg = regimenDelCliente();
      const badge = $("#calc-regimen-badge");
      if (!reg) {
        badge.innerHTML = `<span style="color:var(--ambar)">⚠ Este cliente no tiene régimen configurado: defínalo en Administración → editar cliente.</span>`;
        $("#campos-v2").innerHTML = ""; $("#calc-resultado").innerHTML = "";
        $("#calc-enviar").classList.add("oculto"); $("#calc-correcciones").innerHTML = "";
        refrescarBalanza(cid); return;
      }
      badge.innerHTML = `<span style="color:var(--azul)">Régimen: ${catalogo.regimenes[reg]}</span>`;
      const c = porCliente[cid];
      pintarCampos(reg, c ? c.datos_entrada : {});
      $("#calc-resultado").innerHTML = c
        ? `<p style="margin:4px 0 8px">${chipEstatus(c.estatus)}
            ${c.autorizado_por ? `<span style="font-size:12px;color:var(--gris2)"> · autorizó ${c.autorizado_por}</span>` : ""}
            ${c.resultado && c.resultado.auto_autorizado ? `<span class="pildora ambar" style="margin-left:6px">Autofirmado</span>` : ""}</p>` + hojaHTML(c.resultado)
        : `<p style="margin:12px 0 0;font-size:13px;color:var(--gris2)">Sin captura de este periodo todavía.</p>`;
      $("#calc-enviar").classList.toggle("oculto", !c || !["borrador", "rechazado"].includes(c.estatus));
      if (c) $("#calc-enviar").dataset.id = c.id;
      const etq = ETQ_V2[reg] || {};
      $("#calc-correcciones").innerHTML = (c && (c.correcciones || []).length) ? `
        <p class="micro" style="margin:12px 0 6px;color:var(--rojo)">Correcciones recibidas</p>
        ${c.correcciones.map((x) => `<p style="margin:0 0 6px;font-size:12.5px;background:var(--rojo-suave);border:1px solid var(--rojo-borde);border-radius:8px;padding:8px 10px">
          <strong>${etq[x.campo] || ETQ_CAMPOS[x.campo] || x.campo}:</strong> ${x.comentario}
          <span style="color:var(--gris2)"> — ${x.autor}</span></p>`).join("")}` : "";
      refrescarBalanza(cid);
    }
    cargarExistente();
    $("#calc-cliente").onchange = () => { cargarExistente(); pintarPrediccion(); pintarSaldos(); };

    /* SALDOS A FAVOR DEL CLIENTE, aquí mismo. El saldo a favor es personal e
       intransferible: solo se muestran los de ESTE cliente, y se pueden
       aplicar sin salir de la hoja. */
    async function pintarSaldos() {
      const cid = +$("#calc-cliente").value;
      const zona = $("#calc-saldos");
      zona.innerHTML = "";
      if (!cid) return;
      const r = await api(`/api/saldos-favor?cliente_id=${cid}`);
      if (!r.ok) return;
      const j = await r.json();
      const disp = (j.saldos || []).filter((x) => x.estatus === "disponible" && x.remanente > 0.005);
      if (!disp.length && !(j.saldos || []).length) return;
      zona.innerHTML = `
        <div class="carta" style="padding:16px 20px;margin:0 0 16px;border-left:3px solid var(--verde)">
          <div style="display:flex;flex-wrap:wrap;gap:8px 14px;align-items:baseline">
            <p style="margin:0;flex:1;font-size:13px;font-weight:800;color:var(--marino)">Saldos a favor de este cliente</p>
            <span class="tnum" style="font-size:15px;font-weight:800;color:var(--verde)">${dinero(j.remanente_del_cliente || 0)}</span>
            <span style="font-size:11px;color:var(--gris2)">disponible para aplicar</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:6px;margin-top:10px">
            ${(j.saldos || []).map((x) => `
            <div style="display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;padding:8px 0;border-bottom:1px solid var(--borde-suave)" data-sf="${x.id}">
              <span style="flex:1;min-width:150px;font-size:12.5px">
                <strong>${x.impuesto_nombre}</strong> · ${x.periodo}
                ${x.por_prescribir ? `<span class="pildora ambar">prescribe en ${x.dias_para_prescribir} días</span>` : ""}
                ${x.prescrito ? `<span class="pildora roja">prescrito</span>` : ""}</span>
              <span class="tnum" style="font-size:12.5px;color:var(--gris)">de ${dinero(x.monto_original)}</span>
              <span class="tnum" style="font-size:13px;font-weight:800;color:${x.remanente > 0.005 ? "var(--verde)" : "var(--gris2)"}">${dinero(x.remanente)}</span>
              ${x.remanente > 0.005 && x.estatus === "disponible"
                ? `<button class="chip sf-aplicar-calc" data-s="${x.id}" data-r="${x.remanente}" data-i="${x.impuesto}">aplicar aquí</button>` : ""}
              <button class="chip sf-editar-calc" data-s="${x.id}" data-m="${x.monto_original}">corregir</button>
            </div>`).join("")}
          </div>
          <p class="sf-calc-msj oculto" style="margin:8px 0 0;font-size:12px;font-weight:700"></p>
          <p style="margin:8px 0 0;font-size:11px;color:var(--gris2)">El saldo a favor es personal e intransferible: solo pueden aplicarse los de este mismo contribuyente.</p>
        </div>`;
      const msj = zona.querySelector(".sf-calc-msj");
      $$(".sf-aplicar-calc").forEach((b) => b.onclick = async () => {
        const monto = prompt(`¿Cuánto aplicar de este saldo? (disponible: ${b.dataset.r})`, b.dataset.r);
        if (!monto) return;
        const r2 = await api(`/api/saldos-favor/${b.dataset.s}/aplicar`, { method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ monto: +monto, anio_aplicacion: ANIO,
            mes_aplicacion: MES, impuesto_destino: b.dataset.i }) });
        const jj = await r2.json().catch(() => ({}));
        msj.classList.remove("oculto");
        msj.style.color = r2.ok ? "var(--verde)" : "var(--rojo)";
        msj.textContent = r2.ok ? "Saldo aplicado a este periodo." : (jj.detail || "No se pudo aplicar.");
        if (r2.ok) pintarSaldos();
      });
      $$(".sf-editar-calc").forEach((b) => b.onclick = async () => {
        const monto = prompt("Corregir el monto original del saldo:", b.dataset.m);
        if (!monto) return;
        const r2 = await api(`/api/saldos-favor/${b.dataset.s}`, { method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ monto_original: +monto }) });
        const jj = await r2.json().catch(() => ({}));
        msj.classList.remove("oculto");
        msj.style.color = r2.ok ? "var(--verde)" : "var(--rojo)";
        msj.textContent = r2.ok ? "Saldo corregido." : (jj.detail || "No se pudo corregir.");
        if (r2.ok) pintarSaldos();
      });
    }
    pintarSaldos();

    /* Predicción fiscal híbrida (agente CONTPAQ): el pulso del mes ANTES del
       cierre, con su confianza. Orientativa: la hoja definitiva la hace el
       contador; por eso solo se muestra, no se guarda como cálculo. */
    async function pintarPrediccion() {
      const cid = +$("#calc-cliente").value;
      const zona = $("#calc-prediccion");
      if (!zona) return;
      zona.innerHTML = "";
      if (!cid) return;
      const r = await api(`/api/integracion/contpaq/${cid}?anio=${ANIO}&mes=${MES}`);
      if (!r.ok) return;
      const snap = (await r.json()).prediccion;
      if (!snap) return;
      const p = snap.datos.prediccion;
      const c = p.escenarios.central, pes = p.escenarios.pesimista, opt = p.escenarios.optimista;
      const CONF = { alta: "verde", media: "ambar", baja: "roja" };
      zona.innerHTML = `
        <div class="carta" style="padding:16px 20px;margin:0 0 16px;border-left:3px solid var(--azul)">
          <div style="display:flex;flex-wrap:wrap;gap:8px 14px;align-items:baseline">
            <p style="margin:0;font-size:13px;font-weight:800;color:var(--marino)">Predicción al cierre (CONTPAQ · día ${snap.datos.dia})</p>
            <span class="pildora ${p.modo_proyeccion === "hibrida" ? "verde" : "ambar"}">${p.modo_proyeccion === "hibrida" ? "híbrida · capturado al día" : "estacional · mes sin capturar"}</span>
            <span class="pildora ${CONF[p.confianza] || ""}">confianza ${p.confianza}</span>
            <span style="font-size:11px;color:var(--gris2)">factura global histórica: ${p.factor_cierre_pct}% del ingreso en los últimos 3 días</span>
          </div>
          ${p.fuentes ? `
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin-top:12px">
            ${p.fuentes.xml_puro ? `
            <div style="border:1px solid var(--borde-suave);border-radius:10px;padding:10px 12px">
              <p class="micro" style="margin:0">Timbrado real (XML)</p>
              <p class="tnum" style="margin:4px 0 0;font-size:14px;font-weight:800;color:${p.fuentes.xml_puro.resultado_a_la_fecha < 0 ? "var(--rojo)" : "var(--marino)"}">${dinero(p.fuentes.xml_puro.resultado_a_la_fecha)}</p>
              <p style="margin:2px 0 0;font-size:10.5px;color:var(--gris2)">ingresos ${dinero(p.fuentes.xml_puro.ingresos_mtd)} − egresos ${dinero(p.fuentes.xml_puro.egresos_mtd)}</p>
              ${p.fuentes.xml_puro.aviso ? `<p style="margin:5px 0 0;font-size:10.5px;color:var(--ambar);font-weight:600;line-height:1.4">${p.fuentes.xml_puro.aviso}</p>` : ""}
            </div>` : ""}
            ${p.fuentes.xml_corregida ? `
            <div style="border:1px solid var(--azul-borde);border-radius:10px;padding:10px 12px;background:var(--azul-suave)">
              <p class="micro" style="margin:0">XML + global esperada</p>
              <p class="tnum" style="margin:4px 0 0;font-size:14px;font-weight:800;color:var(--marino)">${dinero(p.fuentes.xml_corregida.ingreso_estimado_cierre)}</p>
              <p style="margin:2px 0 0;font-size:10.5px;color:var(--gris2)">utilidad est. ${dinero(p.fuentes.xml_corregida.utilidad_estimada)}</p>
            </div>` : ""}
            <div style="border:1px solid var(--borde-suave);border-radius:10px;padding:10px 12px">
              <p class="micro" style="margin:0">Histórico CONTPAQi</p>
              <p class="tnum" style="margin:4px 0 0;font-size:14px;font-weight:800;color:var(--marino)">${dinero(p.fuentes.historico.ingreso_estimado_cierre)}</p>
              <p style="margin:2px 0 0;font-size:10.5px;color:var(--gris2)">${p.fuentes.historico.modo === "hibrida" ? "capturado al día" : "estacional"}</p>
            </div>
          </div>
          <p style="margin:10px 0 2px;font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--azul)">Síntesis · ${p.sintesis.base}</p>` : ""}
          <div style="display:flex;flex-wrap:wrap;gap:18px;margin-top:10px">
            <div><p class="micro" style="margin:0">Ingreso estimado al cierre</p>
              <p class="tnum" style="margin:2px 0 0;font-size:16px;font-weight:800">${dinero(p.ingreso_estimado_cierre != null && !p.sintesis ? p.ingreso_estimado_cierre : p.ingreso_sintesis)}</p></div>
            <div><p class="micro" style="margin:0">Gasto línea base (móvil 3m)</p>
              <p class="tnum" style="margin:2px 0 0;font-size:16px;font-weight:700;color:var(--gris)">${dinero(p.gasto_linea_base)}</p></div>
            <div><p class="micro" style="margin:0">Impuesto estimado (±${p.coeficiente_variacion_pct}%)</p>
              <p class="tnum" style="margin:2px 0 0;font-size:16px;font-weight:800;color:var(--azul)">
                ${c.total_estimado != null ? `${dinero(pes.total_estimado)} — <span style="font-size:18px">${dinero(c.total_estimado)}</span> — ${dinero(opt.total_estimado)}` : "solo bases (régimen sin mapeo)"}</p></div>
          </div>
          ${p.aviso_captura ? `<p style="margin:8px 0 0;font-size:11.5px;color:var(--ambar);font-weight:600">${p.aviso_captura}</p>` : ""}
          ${p.base_estacional ? `<p style="margin:6px 0 0;font-size:11px;color:var(--gris2)">Base: ${p.base_estacional}</p>` : ""}
          ${snap.datos.comparacion ? `<p style="margin:10px 0 0;font-size:12px;font-weight:700;color:var(--verde)">El cálculo del periodo ya fue autorizado en ${dinero(snap.datos.comparacion.real_autorizado)} · precisión de la predicción: ${snap.datos.comparacion.precision_pct}%</p>` : ""}
          ${p.precarga_calculadora && !snap.datos.comparacion ? `<button id="pred-precargar" class="btn btn-linea" style="margin-top:10px;min-height:40px;font-size:12.5px">Usar como punto de partida en la hoja</button>` : ""}
          <p style="margin:10px 0 0;font-size:11px;color:var(--gris2);line-height:1.5">${p.leyenda}</p>
        </div>`;
      const btnPre = $("#pred-precargar");
      if (btnPre) btnPre.onclick = () => {
        let n = 0;
        Object.entries(p.precarga_calculadora || {}).forEach(([k, v]) => {
          const inp = document.querySelector(`#campos-v2 [data-k="${k}"]`);
          if (inp) { inp.value = v; inp.style.borderColor = "var(--azul)";
            inp.style.background = "var(--azul-suave)"; n++; }
        });
        btnPre.textContent = n
          ? `Precargados ${n} renglones (en azul) — ajústelos y calcule`
          : "Primero elija el cliente y espere el formulario";
      };
    }
    pintarPrediccion();
    $("#volver-calc").onclick = () => (volverA ? volverA() : panelPrincipal());
    // PANTALLA DIVIDIDA: mientras la balanza está guardada, el papel de
    // trabajo va centrado y ancho; al desplegarla, se parte la pantalla en
    // dos con SCROLL INDEPENDIENTE en cada lado (petición del Director:
    // "no perder de vista nada").
    function pintarBalanza() {
      const zona = $("#visor-balanza");
      if (balanzaDoc) return visorPDF(zona, balanzaDoc);
      zona.innerHTML = `
        <div style="display:grid;place-items:center;min-height:220px;text-align:center;padding:20px">
          <div>
            <p style="margin:0;font-size:13.5px;font-weight:700;color:var(--marino)">Aún no se ha subido la balanza de este periodo</p>
            <p style="margin:6px 0 0;font-size:12.5px;color:var(--gris);max-width:330px;line-height:1.6">
              Súbala con el botón de arriba (PDF exportado de CONTPAQ) y aparecerá aquí, al lado del papel de trabajo, para cotejar renglón por renglón.</p>
          </div>
        </div>`;
    }
    function modoDividido(activo) {
      const izq = $("#calc-zona").children[0];
      const der = $("#calc-zona").children[1];
      if (activo) {
        // Dos columnas con scroll propio, cada una a la altura de la ventana
        [izq, der].forEach((col) => {
          col.style.maxHeight = "calc(100vh - 190px)";
          col.style.overflowY = "auto";
        });
        der.style.flex = "1.4";
      } else {
        [izq, der].forEach((col) => { col.style.maxHeight = ""; col.style.overflowY = ""; });
        der.style.flex = "1.15";
      }
    }
    $("#calc-split").onclick = () => {
      const panel = $("#panel-balanza");
      panel.classList.toggle("oculto");
      const abierto = !panel.classList.contains("oculto");
      modoDividido(abierto);
      if (abierto) pintarBalanza();
    };
    // Subir/reemplazar la balanza sin salir de la calculadora
    $("#bal-archivo").onchange = async () => {
      const inp = $("#bal-archivo"), msj = $("#bal-msj");
      const archivo = inp.files[0];
      if (!archivo) return;
      msj.classList.remove("oculto");
      msj.style.color = "var(--gris)"; msj.textContent = "Subiendo la balanza…";
      const fd = new FormData();
      fd.append("categoria", "balanza_comprobacion");
      fd.append("anio", ANIO); fd.append("mes", MES);
      fd.append("archivo_pdf", archivo);
      const r = await api(`/api/obligaciones/${$("#calc-cliente").value}/subir-documento`,
        { method: "POST", body: fd });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) { msj.style.color = "var(--rojo)";
        msj.textContent = j.detail || "No se pudo subir la balanza."; return; }
      msj.style.color = "var(--verde)";
      msj.textContent = "Balanza guardada en la bóveda del cliente.";
      inp.value = "";
      await refrescarBalanza(+$("#calc-cliente").value);
      pintarBalanza();
    };
    $("#calc-guardar").onclick = async () => {
      const datos = {};
      $$(".dato-calc").forEach((i) => { if (i.value !== "") datos[i.dataset.k] = +i.value; });
      const r = await api("/api/calculos", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cliente_id: +$("#calc-cliente").value, mes: MES, anio: ANIO, datos }) });
      const j = await r.json(); const msj = $("#calc-msj");
      if (!r.ok) { msj.textContent = j.detail || "No se pudo guardar."; msj.style.color = "var(--rojo)";
        msj.classList.remove("oculto"); return; }
      porCliente[j.cliente_id] = j;
      $("#calc-resultado").innerHTML = `<p style="margin:4px 0 8px">${chipEstatus(j.estatus)}</p>` + hojaHTML(j.resultado);
      $("#calc-enviar").classList.remove("oculto"); $("#calc-enviar").dataset.id = j.id;
      msj.textContent = "Guardado y calculado."; msj.style.color = "var(--verde)"; msj.classList.remove("oculto");
    };
    $("#calc-enviar").onclick = async () => {
      const r = await api(`/api/calculos/${$("#calc-enviar").dataset.id}/enviar-autorizacion`, { method: "POST" });
      const j = await r.json(); const msj = $("#calc-msj");
      msj.textContent = r.ok ? j.mensaje : (j.detail || "No se pudo enviar.");
      msj.style.color = r.ok ? "var(--verde)" : "var(--rojo)"; msj.classList.remove("oculto");
      if (r.ok) { const c = porCliente[+$("#calc-cliente").value]; if (c) c.estatus = "en_autorizacion"; cargarExistente(); }
    };
  }

  /* ---------- Hoja genérica estilo papel de trabajo (motor v2) ---------- */
  function hojaHTML(resultado) {
    if (!resultado || !resultado.secciones) return tablaResultado(resultado || {});
    const fila = (f) => `
      <div style="display:flex;align-items:baseline;gap:8px;padding:4px 0;
                  border-bottom:1px solid var(--borde-suave);${f.fuerte ? "background:var(--azul-suave);border-radius:6px;padding:6px 8px;" : ""}">
        <span style="width:26px;font-size:11px;color:var(--gris2);text-align:center">${f.operador || ""}</span>
        <span style="flex:1;font-size:12.5px;${f.fuerte ? "font-weight:800;color:var(--marino)" : ""}">${f.concepto}
          ${f.clave === "auto" ? `<span style="font-size:9px;font-weight:800;color:var(--azul);letter-spacing:.06em;margin-left:4px">AUTO</span>` : ""}</span>
        ${f.acumulado !== undefined ? `<span class="tnum" style="font-size:11.5px;color:var(--gris2);min-width:86px;text-align:right">${dinero(f.acumulado)} <span style="font-size:9px">acum</span></span>` : ""}
        <span class="tnum" style="font-size:12.5px;min-width:92px;text-align:right;${f.fuerte ? "font-weight:800;" : ""}${f.clave === "auto" ? "color:var(--azul);font-weight:700;" : ""}">
          ${typeof f.valor === "number" ? dinero(f.valor) : f.valor}</span>
      </div>
      ${f.detalle ? `
      <details style="margin:1px 0 4px 34px">
        <summary style="font-size:10.5px;color:var(--azul);cursor:pointer;font-weight:700">cédula · cómo salió este número</summary>
        <div style="border-left:2px solid var(--azul-borde);margin:3px 0 4px 4px;padding:2px 0">
          ${f.detalle.map((d) => `
          <div style="display:flex;align-items:baseline;gap:8px;padding:2px 0 2px 10px">
            <span style="width:22px;font-size:10px;color:var(--gris2);text-align:center">${d.operador || ""}</span>
            <span style="flex:1;font-size:11px;color:var(--gris)">${d.concepto}</span>
            <span class="tnum" style="font-size:11px;min-width:80px;text-align:right;color:var(--marino)">${typeof d.valor === "number" ? dinero(d.valor) : (d.valor || "")}</span>
          </div>`).join("")}
        </div>
      </details>` : ""}`;
    return `
      ${resultado.regimen_nombre ? `<p class="micro" style="margin:0 0 8px">${resultado.regimen_nombre} · tarifas ${resultado.anio_tarifa}</p>` : ""}
      ${resultado.secciones.map((s) => `
        <p style="margin:12px 0 4px;font-size:11px;font-weight:800;letter-spacing:.08em;color:var(--marino);text-transform:uppercase">${s.titulo}</p>
        ${s.filas.map(fila).join("")}`).join("")}
      <p style="margin:14px 0 4px;font-size:11px;font-weight:800;letter-spacing:.08em;color:var(--marino);text-transform:uppercase">Resumen de impuestos</p>
      ${(resultado.resumen || []).map(fila).join("")}
      ${resultado.comparacion_prediccion ? (() => {
        const c = resultado.comparacion_prediccion;
        const color = c.precision_pct >= 85 ? "var(--verde)" : c.precision_pct >= 60 ? "var(--ambar)" : "var(--rojo)";
        return `
      <div style="margin-top:14px;border:1px solid var(--azul-borde);background:var(--azul-suave);border-radius:10px;padding:12px 14px">
        <p style="margin:0;font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--azul)">Predicción vs autorizado</p>
        <p style="margin:6px 0 0;font-size:12.5px;color:var(--marino);line-height:1.6">
          La predicción del día ${c.dia_prediccion ?? "—"} (${c.modo === "hibrida" ? "híbrida" : "estacional"}) estimó
          <strong class="tnum">${dinero(c.predicho_central)}</strong>${c.predicho_pesimista != null ? ` (rango ${dinero(c.predicho_pesimista)} — ${dinero(c.predicho_optimista)})` : ""};
          el cálculo autorizado quedó en <strong class="tnum">${dinero(c.real_autorizado)}</strong>:
          diferencia de <span class="tnum" style="font-weight:700">${c.diferencia >= 0 ? "+" : ""}${dinero(c.diferencia)}</span> (${c.diferencia_pct >= 0 ? "+" : ""}${c.diferencia_pct}%).</p>
        <p style="margin:6px 0 0;font-size:12.5px;font-weight:800;color:${color}">Precisión de la predicción: ${c.precision_pct}%</p>
      </div>`;
      })() : ""}`;
  }

  /* ---------- Visor de PDF embebido (balanza a un lado) ---------- */
  async function visorPDF(contenedor, documentoId) {
    contenedor.innerHTML = `<p style="margin:0;padding:16px;font-size:12.5px;color:var(--gris2)">Cargando documento…</p>`;
    let r;
    try {
      r = await api(`/api/obligaciones/boveda/${documentoId}/descargar`);
    } catch (e) {
      contenedor.innerHTML = `<div style="padding:18px;text-align:center">
        <p style="margin:0;font-size:13px;font-weight:700;color:var(--marino)">No se pudo cargar el documento</p>
        <p style="margin:6px 0 0;font-size:12.5px;color:var(--gris)">${e.message}</p></div>`;
      return;
    }
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      contenedor.innerHTML = `<div style="padding:18px;text-align:center">
        <p style="margin:0;font-size:13px;font-weight:700;color:var(--marino)">No se pudo abrir el documento</p>
        <p style="margin:6px 0 0;font-size:12.5px;color:var(--gris)">${j.detail || "Intente de nuevo en un momento."}</p></div>`;
      return;
    }
    // El servidor nos entrega el ARCHIVO (mismo origen). Antes devolvía la
    // URL firmada de Supabase y el navegador la bloqueaba por CORS:
    // "Failed to fetch". Por eso solo funcionaba abrirla en otra pestaña.
    let src;
    try {
      const bytes = await r.blob();
      src = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
    } catch (e) {
      reportarError("No se pudo leer el documento", e.message);
      contenedor.innerHTML = `<div style="padding:18px;text-align:center">
        <p style="margin:0;font-size:13px;font-weight:700;color:var(--marino)">No se pudo mostrar el documento</p>
        <p style="margin:6px 0 0;font-size:12.5px;color:var(--gris)">${e.message}</p></div>`;
      return;
    }
    contenedor.innerHTML = `
      <iframe src="${src}" style="width:100%;height:min(70vh,620px);border-radius:10px;border:1px solid var(--borde);background:#fff"
        title="Documento"></iframe>
      <a href="${src}" target="_blank" rel="noopener" style="display:inline-block;margin-top:8px;font-size:12px;color:var(--azul);font-weight:700">Abrir en pestaña aparte ↗</a>`;
  }

  /* Descarga con sesión: window.open NO manda el token, por eso el estado de
     cuenta abría una pestaña con {"detail":"Not authenticated"}. */
  async function descargarConSesion(ruta, nombre) {
    const r = await api(ruta);
    if (!r.ok) return;
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    if (nombre) {
      const a = document.createElement("a");
      a.href = url; a.download = nombre;
      document.body.appendChild(a); a.click(); a.remove();
    } else {
      window.open(url, "_blank");
    }
  }



  /* ---------- Cola de autorización EN PANTALLA DIVIDIDA ---------- */
  /* =====================================================================
     AUTORIZACIONES EN TRES NIVELES (petición del Director: "si al abrirlo
     sale todo, se llena de paja y no se distingue"):
       1. Contadores, con su avance x/xx — los que están al corriente se
          van al fondo para no estorbar.
       2. Al tocar un contador: SUS clientes y en qué punto va cada pago.
       3. Al tocar un cliente: la pantalla de autorización de siempre.
     ===================================================================== */
  const EST_CALC = {
    sin_calculo:     ["Sin elaborar",        "var(--gris2)", "var(--borde-suave)"],
    borrador:        ["Elaborado",           "var(--azul)",  "var(--azul-suave)"],
    en_autorizacion: ["Espera autorización", "var(--ambar)", "var(--ambar-suave)"],
    rechazado:       ["Regresado al contador","var(--rojo)", "var(--rojo-suave)"],
    autorizado:      ["Autorizado",          "var(--verde)", "var(--verde-suave)"],
    declarado:       ["Declarado y entregado","var(--verde)","var(--verde-suave)"],
  };

  async function vistaAutorizaciones(objetivo, volverA) {
    const grupos = await (await api(`/api/calculos/por-contador?mes=${MES}&anio=${ANIO}`)).json();
    const pendientes = grupos.filter((g) => !g.todo_listo);
    const alCorriente = grupos.filter((g) => g.todo_listo);
    const esperandoTotal = grupos.reduce((a, g) => a + g.esperando_firma, 0);

    const barra = (g) => `
      <div style="height:6px;border-radius:99px;background:var(--borde-suave);overflow:hidden;margin-top:8px">
        <div style="height:100%;width:${g.avance_pct}%;background:${g.avance_pct === 100 ? "var(--verde)" : "var(--azul)"};transition:width .4s"></div>
      </div>`;

    const tarjeta = (g) => `
      <button class="carta grupo-contador" data-cid="${g.contador_id ?? ""}"
        style="padding:18px 20px;text-align:left;border:1px solid var(--borde);cursor:pointer;width:100%;font-family:inherit;background:var(--tarjeta)">
        <div style="display:flex;flex-wrap:wrap;gap:8px 14px;align-items:baseline">
          <p style="margin:0;flex:1;font-size:15px;font-weight:800;color:var(--marino)">${g.contador}</p>
          ${g.esperando_firma ? `<span class="pildora ambar">${g.esperando_firma} espera${g.esperando_firma > 1 ? "n" : ""} su firma</span>` : ""}
          ${g.pendiente_contador ? `<span class="pildora">${g.pendiente_contador} le falta${g.pendiente_contador > 1 ? "n" : ""}</span>` : ""}
          ${g.todo_listo ? `<span class="pildora verde">al corriente</span>` : ""}
          <span class="tnum" style="font-size:13px;font-weight:800;color:var(--marino)">${g.cerrados}/${g.total_clientes}</span>
        </div>
        ${barra(g)}
        <p style="margin:8px 0 0;font-size:11.5px;color:var(--gris2)">${g.cerrados} de ${g.total_clientes} clientes cerrados este mes · toque para ver el detalle</p>
      </button>`;

    objetivo.innerHTML = `
      <div style="animation:aparecer .3s ease">
      ${volverA ? `<button id="volver-aut" class="btn btn-linea" style="margin-bottom:16px;min-height:40px">${ICO.atras(15)} Regresar</button>` : ""}
      <div style="display:flex;flex-wrap:wrap;gap:8px 16px;align-items:baseline;margin-bottom:16px">
        <p class="micro" style="margin:0;flex:1">Avance del despacho · ${NOMBRE_MES}</p>
        ${esperandoTotal ? `<span class="pildora ambar">${esperandoTotal} cálculo(s) esperando firma</span>`
          : `<span class="pildora verde">nada pendiente de firmar</span>`}
      </div>
      <div style="display:flex;flex-direction:column;gap:12px">
        ${pendientes.map(tarjeta).join("") || `<div class="carta" style="padding:24px;font-size:14px;color:var(--gris2)">Todos los contadores están al corriente este mes.</div>`}
      </div>
      ${alCorriente.length ? `
      <details style="margin-top:20px">
        <summary style="font-size:12.5px;font-weight:700;color:var(--azul);cursor:pointer">Al corriente (${alCorriente.length}) — sin nada pendiente</summary>
        <div style="display:flex;flex-direction:column;gap:12px;margin-top:12px">${alCorriente.map(tarjeta).join("")}</div>
      </details>` : ""}
      </div>`;

    if (volverA) $("#volver-aut").onclick = () => volverA();
    $$(".grupo-contador").forEach((b) => b.onclick = () => {
      const g = grupos.find((x) => String(x.contador_id ?? "") === b.dataset.cid);
      if (g) nivelClientes(objetivo, volverA, g);
    });
  }

  /* NIVEL 2 — los clientes de ese contador y en qué punto va cada uno */
  function nivelClientes(objetivo, volverA, g) {
    const volverAqui = () => vistaAutorizaciones(objetivo, volverA);
    objetivo.innerHTML = `
      <div style="animation:aparecer .3s ease">
        <button id="volver-nivel1" class="btn btn-linea" style="margin-bottom:16px;min-height:40px">${ICO.atras(15)} Todos los contadores</button>
        <div style="display:flex;flex-wrap:wrap;gap:8px 14px;align-items:baseline;margin-bottom:6px">
          <h2 style="margin:0;flex:1;font-size:19px;font-weight:800;color:var(--marino)">${g.contador}</h2>
          <span class="tnum" style="font-size:14px;font-weight:800">${g.cerrados}/${g.total_clientes} cerrados</span>
        </div>
        <p class="micro" style="margin:0 0 14px">Clientes a su cargo · ${NOMBRE_MES}</p>
        <div style="display:flex;flex-direction:column;gap:8px">
          ${g.clientes.map((f) => {
            const e = EST_CALC[f.estatus] || [f.estatus, "var(--gris)", "var(--borde-suave)"];
            const abrible = f.estatus === "en_autorizacion";
            return `
            <div class="fila-cliente ${abrible ? "abrible" : ""}" data-calc="${f.calculo_id ?? ""}"
              style="background:var(--tarjeta);border:1px solid var(--borde);border-radius:12px;padding:14px 16px;display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;${abrible ? "cursor:pointer;border-left:3px solid var(--ambar)" : ""}">
              <div style="flex:1;min-width:min(100%,200px)">
                <p style="margin:0;font-size:13.5px;font-weight:700;color:var(--marino)">${f.cliente}
                  ${f.tipo_cliente === "vip" ? `<span class="pildora">VIP</span>` : ""}
                  ${f.tipo_cliente === "confianza_especial" ? `<span class="pildora ambar">confianza especial</span>` : ""}</p>
                ${f.elaborado_por ? `<p style="margin:2px 0 0;font-size:11.5px;color:var(--gris2)">elaboró ${f.elaborado_por}</p>` : ""}
              </div>
              ${f.total_a_pagar != null ? `<span class="tnum" style="font-size:13.5px;font-weight:800;color:var(--marino)">${dinero(f.total_a_pagar)}</span>` : ""}
              <span style="font-size:10.5px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:${e[1]};background:${e[2]};padding:4px 10px;border-radius:99px">${e[0]}</span>
              ${abrible ? `<span style="font-size:11.5px;font-weight:800;color:var(--azul)">revisar ›</span>` : ""}
            </div>`;
          }).join("")}
        </div>
      </div>`;
    $("#volver-nivel1").onclick = volverAqui;
    $$(".fila-cliente.abrible").forEach((f) => f.onclick = () =>
      vistaColaAutorizacion(objetivo, () => nivelClientes(objetivo, volverA, g), f.dataset.calc));
  }

  /* NIVEL 3 — La pantalla de autorización de siempre (hoja + balanza).
     Si recibe soloCalcId, muestra UN cálculo: se llega aquí desde el
     contador → cliente, no como lista plana. */
  async function vistaColaAutorizacion(objetivo, volverA, soloCalcId) {
    const [todos, catalogo] = await Promise.all([
      (await api("/api/calculos/pendientes")).json(),
      (await api("/api/calculos/regimenes")).json(),
    ]);
    const pendientes = soloCalcId
      ? todos.filter((p) => p.id === +soloCalcId) : todos;
    const camposDe = (reg) => catalogo.campos[reg]
      ? catalogo.campos[reg] : Object.entries(ETQ_CAMPOS);

    objetivo.innerHTML = `
      <div style="animation:aparecer .3s ease">
      ${volverA ? `<button id="volver-aut" class="btn btn-linea" style="margin-bottom:16px;min-height:40px">${ICO.atras(15)} Regresar</button>` : ""}
      <p class="micro" style="margin:0 0 14px">${soloCalcId ? "Revisión del cálculo — la hoja y su balanza, lado a lado" : "Pendientes de autorización — la hoja de cálculo y su balanza de comprobación, lado a lado"}</p>
      <div style="display:flex;flex-direction:column;gap:18px">
      ${pendientes.map((p) => `
        <div class="carta" style="padding:22px" data-calc="${p.id}" data-reg="${p.regimen}">
          <div style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;align-items:baseline">
            <p style="margin:0;font-size:16px;font-weight:800;color:var(--marino)">${p.cliente}
              <span style="font-weight:500;color:var(--gris2);font-size:12.5px"> · ${String(p.mes).padStart(2, "0")}/${p.anio} · elaboró ${p.elaborado_por}
              ${catalogo.regimenes[p.regimen] ? ` · ${catalogo.regimenes[p.regimen]}` : ""}</span></p>
            <span class="tnum" style="font-size:16px;font-weight:800;color:var(--azul)">${dinero(p.total_a_pagar)}</span>
          </div>
          ${p.balanza_documento_id ? `
          <button class="chip aut-split" data-calc="${p.id}" style="margin-top:12px">◫ Ver balanza al lado</button>` : ""}
          <div class="aut-zona" style="display:flex;flex-wrap:wrap;gap:20px;margin-top:12px">
            <div class="aut-hoja" style="flex:1;min-width:min(100%,320px);max-width:760px;margin:0 auto">
              ${hojaHTML(p.resultado)}
              <details style="margin-top:10px">
                <summary style="font-size:12px;font-weight:700;color:var(--azul);cursor:pointer">Ver datos capturados por el contador</summary>
                ${Object.entries(p.datos_entrada).map(([k, v]) => `
                  <div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--borde-suave);font-size:12px">
                    <span>${(Object.fromEntries(camposDe(p.regimen)))[k] || ETQ_CAMPOS[k] || k}</span>
                    <span class="tnum">${k === "coeficiente_utilidad" ? v : dinero(v)}</span></div>`).join("")}
              </details>
            </div>
            <div class="aut-lado" style="flex:1.1;min-width:min(100%,320px)">
              ${p.balanza_documento_id
                ? `<div class="visor-aut oculto" data-doc="${p.balanza_documento_id}"></div>`
                : `<p style="margin:0 0 10px;padding:12px;font-size:12.5px;color:var(--ambar);background:var(--ambar-suave);border-radius:10px">
                     Sin balanza del periodo en la bóveda: pida al contador subirla para cotejar.</p>`}
              <p class="micro" style="margin:14px 0 6px">¿Correcciones puntuales?</p>
              <div style="display:flex;gap:6px">
                <select class="campo corr-campo" style="flex:1;padding:8px;font-size:12px">
                  ${camposDe(p.regimen).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select>
              </div>
              <div style="display:flex;gap:6px;margin-top:6px">
                <input class="campo corr-texto" placeholder="Ej. El IVA acreditable no coincide con la balanza" style="flex:1;padding:8px;font-size:12px">
                <button class="chip corr-agregar">Añadir</button>
              </div>
              <div class="corr-lista" style="margin-top:8px;display:flex;flex-direction:column;gap:5px"></div>
              <div style="display:flex;gap:10px;margin-top:14px">
                <button class="btn btn-azul btn-autorizar" style="flex:1;min-height:46px;background:var(--verde)">${ICO.check(16)} AUTORIZAR</button>
                <button class="btn btn-linea btn-rechazar" style="flex:1;min-height:46px;color:var(--rojo);border-color:var(--rojo)">Regresar con correcciones</button>
              </div>
              <p class="aut-msj oculto" style="margin:8px 0 0;font-size:12.5px;font-weight:700"></p>
            </div>
          </div>
        </div>`).join("") || `<div class="carta" style="padding:24px;font-size:14px;color:var(--gris2)">${soloCalcId ? "Este cálculo ya no está esperando firma (quizá alguien más lo atendió)." : "No hay determinaciones pendientes. Todo autorizado."}</div>`}
      </div></div>`;

    if (volverA) $("#volver-aut").onclick = () => volverA();
    // PANTALLA DIVIDIDA a petición: la hoja va centrada y ancha hasta que se
    // despliega la balanza; entonces cada lado toma su propio scroll para no
    // perder de vista ninguno de los dos.
    $$(".aut-split").forEach((b) => b.onclick = () => {
      const caja = b.closest("[data-calc]");
      const visor = caja.querySelector(".visor-aut");
      const zona = caja.querySelector(".aut-zona");
      const hoja = caja.querySelector(".aut-hoja");
      const lado = caja.querySelector(".aut-lado");
      const abrir = visor.classList.contains("oculto");
      visor.classList.toggle("oculto", !abrir);
      b.textContent = abrir ? "◫ Ocultar balanza" : "◫ Ver balanza al lado";
      hoja.style.maxWidth = abrir ? "none" : "760px";
      [hoja, lado].forEach((col) => {
        col.style.maxHeight = abrir ? "calc(100vh - 230px)" : "";
        col.style.overflowY = abrir ? "auto" : "";
      });
      if (abrir && !visor.dataset.pintado) {
        visor.dataset.pintado = "1";
        visorPDF(visor, visor.dataset.doc);
      }
    });
    $$(".corr-agregar").forEach((b) => b.onclick = () => {
      const caja = b.closest("[data-calc]");
      const sel = caja.querySelector(".corr-campo");
      const texto = caja.querySelector(".corr-texto").value.trim();
      if (!texto) return;
      const el = document.createElement("p");
      el.style.cssText = "margin:0;font-size:12px;background:var(--rojo-suave);border:1px solid var(--rojo-borde);border-radius:8px;padding:6px 9px";
      el.dataset.campo = sel.value; el.dataset.comentario = texto;
      el.innerHTML = `<strong>${sel.options[sel.selectedIndex].text}:</strong> ${texto}`;
      caja.querySelector(".corr-lista").appendChild(el);
      caja.querySelector(".corr-texto").value = "";
    });
    const recargarVista = () => (soloCalcId && volverA
      ? volverA() : vistaColaAutorizacion(objetivo, volverA, soloCalcId));
    $$(".btn-autorizar").forEach((b) => b.onclick = async () => {
      const caja = b.closest("[data-calc]"); b.disabled = true;
      const r = await api(`/api/calculos/${caja.dataset.calc}/autorizar`, { method: "POST" });
      const j = await r.json(); const msj = caja.querySelector(".aut-msj");
      msj.textContent = r.ok ? j.mensaje + " La balanza queda guardada y vinculada al cálculo." : (j.detail || "No se pudo autorizar.");
      msj.style.color = r.ok ? "var(--verde)" : "var(--rojo)"; msj.classList.remove("oculto");
      if (r.ok) setTimeout(recargarVista, 1400); else b.disabled = false;
    });
    $$(".btn-rechazar").forEach((b) => b.onclick = async () => {
      const caja = b.closest("[data-calc]");
      const correcciones = [...caja.querySelectorAll(".corr-lista p")]
        .map((p) => ({ campo: p.dataset.campo, comentario: p.dataset.comentario }));
      const msj = caja.querySelector(".aut-msj");
      if (!correcciones.length) { msj.textContent = "Añada al menos una corrección puntual antes de regresarlo.";
        msj.style.color = "var(--rojo)"; msj.classList.remove("oculto"); return; }
      b.disabled = true;
      const r = await api(`/api/calculos/${caja.dataset.calc}/rechazar`, { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ correcciones }) });
      const j = await r.json();
      msj.textContent = r.ok ? j.mensaje : (j.detail || "No se pudo regresar.");
      msj.style.color = r.ok ? "var(--verde)" : "var(--rojo)"; msj.classList.remove("oculto");
      if (r.ok) setTimeout(recargarVista, 1100); else b.disabled = false;
    });
  }

  /* ---------- Vista de la Supervisora (Artemisa) ---------- */
  async function vistaPatronal(volverA) {
    const cont = $("#contenido");
    const [imss, nominas] = await Promise.all([
      (await api(`/api/patronal/imss?mes=${MES}&anio=${ANIO}`)).json(),
      (await api("/api/patronal/nominas")).json(),
    ]);
    // Cada paso acepta VARIOS archivos y en su formato real: el IDSE trae los
    // suyos, el SUA genera .sua y más de un documento, y el pago en SIPARE
    // sí produce PDF. Nada de forzar PDF: el explorador los bloqueaba.
    const ACEPTA = ".pdf,.sua,.txt,.zip,.xls,.xlsx,.jpg,.jpeg,.png,application/pdf";
    // Conceptos del desglose patronal (los mismos que calcula el servidor
    // en services/carga_social.py). ⚠ Se perdió en un rediseño anterior y
    // dejó la pantalla del IMSS sin abrir: "ETQ_CUOTAS is not defined".
    const ETQ_CUOTAS = {
      cuota_fija: "Cuota fija EyM",
      excedente: "Excedente patronal",
      prestaciones_dinero: "Prestaciones en dinero",
      gastos_medicos: "Gastos médicos pensionados",
      invalidez_vida: "Invalidez y vida",
      guarderias: "Guarderías",
      retiro: "Retiro",
      ceav: "Cesantía y vejez",
      riesgo_trabajo: "Riesgo de trabajo",
      infonavit: "Infonavit",
    };
    const pasos = [["emision_idse_hecha", "1. Emisión IDSE", "emision_idse"],
      ["calculo_sua_hecho", "2. Cálculo SUA", "calculo_sua"],
      ["sipare_presentado", "3. Pago en SIPARE", "propuesta_sipare"]];

    cont.innerHTML = `
      <div style="animation:aparecer .3s ease">
      <button id="volver-pat" class="btn btn-linea" style="margin-bottom:18px;min-height:40px">${ICO.atras(15)} Regresar</button>
      <h1 class="h1" style="margin-top:0">IMSS y Nóminas · ${NOMBRE_MES}</h1>
      <div style="display:flex;flex-wrap:wrap;gap:22px;align-items:flex-start">
        <div style="flex:3;min-width:min(100%,380px);display:flex;flex-direction:column;gap:16px">
          <div class="carta" style="padding:14px 18px;display:flex;flex-wrap:wrap;gap:8px 22px;align-items:baseline">
            <p class="micro" style="margin:0">Ciclo patronal · IDSE → SUA → SIPARE → enviar</p>
            <p style="margin:0;font-size:12.5px;color:var(--gris)">
              <span class="tnum" style="font-weight:800;color:var(--marino)">${imss.filter((p) => p.notificado_cliente).length}</span> de
              <span class="tnum" style="font-weight:800">${imss.length}</span> clientes ya con su formato enviado</p>
          </div>
          <div id="pat-carga-social"></div>
          ${imss.map((p) => {
            // El caminito: qué paso sigue (el primero no hecho)
            const hechos = pasos.map(([campo]) => !!p[campo]);
            const actual = hechos.indexOf(false);          // -1 = los 3 listos
            return `
          <div class="carta" style="padding:20px" data-cid="${p.cliente_id}">
            <div style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;align-items:baseline">
              <p style="margin:0;font-size:15px;font-weight:800;color:var(--marino)">${p.cliente}</p>
              ${p.notificado_cliente ? `<span class="pildora verde">enviado al cliente</span>`
                : p.total_a_pagar ? `<span class="tnum" style="font-size:14px;font-weight:800;color:var(--azul)">${dinero(p.total_a_pagar)}</span>` : ""}
            </div>

            <!-- El caminito de pasos: verde lo hecho, azul el paso actual, gris lo que sigue -->
            <div style="display:flex;align-items:flex-start;gap:0;margin-top:16px">
              ${pasos.map(([campo, etq, cat], i) => {
                const hecho = hechos[i];
                const esActual = i === actual;
                const nombre = etq.replace(/^\d+\. /, "");
                const circulo = hecho
                  ? `<span style="width:30px;height:30px;border-radius:50%;background:var(--verde);color:#fff;display:grid;place-items:center;font-size:14px;font-weight:800;flex:none">✓</span>`
                  : esActual
                  ? `<span style="width:30px;height:30px;border-radius:50%;background:var(--azul);color:#fff;display:grid;place-items:center;font-size:13px;font-weight:800;flex:none">${i + 1}</span>`
                  : `<span style="width:30px;height:30px;border-radius:50%;background:var(--borde-suave);color:var(--gris2);display:grid;place-items:center;font-size:13px;font-weight:800;flex:none;border:1px solid var(--borde)">${i + 1}</span>`;
                const linea = i < pasos.length - 1
                  ? `<span style="flex:1;height:2px;margin-top:14px;background:${hecho ? "var(--verde)" : "var(--borde)"}"></span>` : "";
                const accion = hecho
                  ? `<span style="font-size:11px;color:var(--verde);font-weight:700">listo</span>`
                  : esActual
                  ? `<label style="font-size:11.5px;font-weight:800;color:var(--azul);cursor:pointer;text-decoration:underline">subir archivos
                       <input type="file" multiple accept="${ACEPTA}" class="paso-imss" data-paso="${campo}" data-cat="${cat}" style="display:none"></label>`
                  : `<span style="font-size:11px;color:var(--gris2)">después</span>`;
                return `
                <div style="display:flex;flex-direction:column;align-items:center;gap:4px;min-width:76px">
                  ${circulo}
                  <span style="font-size:11.5px;font-weight:700;color:${hecho ? "var(--verde)" : esActual ? "var(--marino)" : "var(--gris2)"}">${nombre}</span>
                  ${accion}
                </div>${linea}`;
              }).join("")}
              <span style="flex:1;height:2px;margin-top:14px;background:${actual === -1 ? "var(--verde)" : "var(--borde)"}"></span>
              <div style="display:flex;flex-direction:column;align-items:center;gap:4px;min-width:76px">
                ${p.notificado_cliente
                  ? `<span style="width:30px;height:30px;border-radius:50%;background:var(--verde);color:#fff;display:grid;place-items:center;font-size:14px;flex:none">✓</span>
                     <span style="font-size:11.5px;font-weight:700;color:var(--verde)">Enviado</span>`
                  : `<span style="width:30px;height:30px;border-radius:50%;background:${actual === -1 ? "var(--marino)" : "var(--borde-suave)"};color:${actual === -1 ? "#fff" : "var(--gris2)"};display:grid;place-items:center;font-size:14px;flex:none;${actual === -1 ? "" : "border:1px solid var(--borde)"}">✉</span>
                     <span style="font-size:11.5px;font-weight:700;color:${actual === -1 ? "var(--marino)" : "var(--gris2)"}">Enviar</span>
                     ${actual === -1 ? "" : `<span style="font-size:11px;color:var(--gris2)">al final</span>`}`}
              </div>
            </div>
            ${p.sipare_presentado && !p.notificado_cliente ? `
            <details style="margin-top:12px">
              <summary style="font-size:12px;font-weight:700;color:var(--azul);cursor:pointer">Desglose por concepto (el total se suma solo)</summary>
              <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:6px;margin-top:8px">
                ${Object.entries(ETQ_CUOTAS).map(([k, v]) => `
                <label class="etiqueta" style="margin:0;font-size:10px">${v}
                  <input type="number" min="0" step="0.01" value="${p.desglose_cuotas[k] ?? ""}" data-k="${k}"
                    class="campo cuota-imss" style="margin-top:2px;padding:7px 8px;font-size:12px"></label>`).join("")}
              </div>
              <button class="btn btn-linea btn-guardar-desglose" style="margin-top:8px;min-height:36px;font-size:12px">Guardar desglose</button>
            </details>
            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;align-items:center">
              <label class="btn btn-azul" style="min-height:42px;font-size:12.5px;cursor:pointer">
                ${ICO.enviar(14)} Subir FORMATO DE PAGO y enviar al cliente
                <input type="file" accept="application/pdf" class="formato-imss" style="display:none"></label>
            </div>` : ""}
            <p class="pat-msj oculto" style="margin:8px 0 0;font-size:12px;font-weight:700"></p>
          </div>`;}).join("") || `<div class="carta" style="padding:20px;font-size:13px;color:var(--gris2)">Ningún cliente tiene IMSS habilitado (se activa en Administración).</div>`}

          <p class="micro" style="margin:10px 0 0">Presentar ISN del mes (impuesto sobre nómina)</p>
          <div class="carta" style="padding:18px;display:flex;flex-wrap:wrap;gap:8px;align-items:flex-end">
            <label class="etiqueta" style="margin:0;flex:2;min-width:160px">Cliente
              <select id="isn-cliente" class="campo" style="margin-top:3px;padding:9px;font-size:13px">
                ${imss.map((p) => `<option value="${p.cliente_id}">${p.cliente}</option>`).join("")}</select></label>
            <label class="etiqueta" style="margin:0;flex:1;min-width:110px">Importe ISN
              <input id="isn-importe" type="number" min="0" step="0.01" class="campo" style="margin-top:3px;padding:9px;font-size:13px"></label>
            <label class="btn btn-azul" style="min-height:42px;font-size:12.5px;cursor:pointer">Formato + enviar
              <input id="isn-pdf" type="file" accept="application/pdf" style="display:none"></label>
            <p id="isn-msj" class="oculto" style="margin:0;width:100%;font-size:12px;font-weight:700"></p>
          </div>
        </div>

        <div style="flex:2;min-width:min(100%,300px)">
          <p class="micro" style="margin:0 0 10px">Tareas de nómina (${nominas.filter((t) => t.estatus === "pendiente").length} pendientes)</p>
          <div style="display:flex;flex-direction:column;gap:10px">
            ${nominas.map((t) => `
            <div class="carta" style="padding:14px 16px;display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center" data-t="${t.id}">
              <div style="flex:1;min-width:150px">
                <p style="margin:0;font-size:13px;font-weight:700">${t.cliente}</p>
                <p style="margin:2px 0 0;font-size:11.5px;color:${t.vencida ? "var(--rojo)" : "var(--gris2)"}">
                  ${t.etiqueta}${t.vencida ? " · VENCIDA" : ""}</p>
              </div>
              ${t.estatus === "terminada"
                ? `<span style="font-size:11px;font-weight:800;color:var(--verde);text-transform:uppercase">entregada ✓</span>`
                : `<label class="chip" style="cursor:pointer">Entregar PDF
                     <input type="file" accept="application/pdf" class="entregar-nomina" style="display:none"></label>`}
            </div>`).join("") || `<div class="carta" style="padding:16px;font-size:13px;color:var(--gris2)">Sin tareas de nómina por ahora.</div>`}
          </div>
        </div>
      </div></div>`;

    $("#volver-pat").onclick = () => (volverA ? volverA() : panelPrincipal());

    // Carga social proyectada por el agente CONTPAQ (si mandó nómina del mes)
    (async () => {
      const zona = $("#pat-carga-social");
      for (const p of imss.slice(0, 6)) {
        const r = await api(`/api/integracion/contpaq/${p.cliente_id}?anio=${ANIO}&mes=${MES}`);
        if (!r.ok) continue;
        const snap = (await r.json()).nomina;
        if (!snap) continue;
        const c = snap.datos.proyeccion;
        zona.insertAdjacentHTML("beforeend", `
          <div class="carta" style="padding:14px 18px;margin-bottom:14px;border-left:3px solid var(--azul)">
            <p style="margin:0;font-size:12.5px;font-weight:800;color:var(--marino)">${p.cliente}
              <span class="pildora">proyección CONTPAQ · ${c.empleados} empleados</span></p>
            <p style="margin:6px 0 0;font-size:12.5px;color:var(--gris)">
              IMSS patronal <span class="tnum" style="font-weight:700">${dinero(c.imss_patronal.total)}</span> ·
              Infonavit <span class="tnum" style="font-weight:700">${dinero(c.infonavit)}</span> ·
              ISN <span class="tnum" style="font-weight:700">${dinero(c.isn.importe)}</span> →
              <strong class="tnum" style="color:var(--marino)">${dinero(c.total_carga_social)}</strong></p>
          </div>`);
      }
    })();
    const recargar = () => vistaPatronal(volverA);

    $$(".paso-imss").forEach((inp) => inp.onchange = async () => {
      const caja = inp.closest("[data-cid]");
      const msj = caja.querySelector(".pat-msj");
      if (!inp.files.length) return;
      const fd = new FormData();
      fd.append("mes", MES); fd.append("anio", ANIO);
      fd.append("paso", inp.dataset.paso);
      fd.append("categoria_documento", inp.dataset.cat);
      // TODOS los archivos del paso (el SUA genera varios)
      Array.from(inp.files).forEach((f) => fd.append("archivos", f));
      if (msj) { msj.classList.remove("oculto"); msj.style.color = "var(--gris)";
        msj.textContent = `Subiendo ${inp.files.length} archivo(s)…`; }
      const r = await api(`/api/patronal/imss/${caja.dataset.cid}/paso`, { method: "POST", body: fd });
      if (r.ok) return recargar();
      // ANTES: si fallaba, no pasaba NADA (parecía que el archivo no cargaba).
      const j = await r.json().catch(() => ({}));
      if (msj) { msj.style.color = "var(--rojo)";
        msj.textContent = j.detail || "No se pudo guardar el archivo. Intente de nuevo."; }
    });
    $$(".btn-guardar-desglose").forEach((b) => b.onclick = async () => {
      const caja = b.closest("[data-cid]");
      const datos = {};
      caja.querySelectorAll(".cuota-imss").forEach((i) => { if (i.value !== "") datos[i.dataset.k] = +i.value; });
      const r = await api(`/api/patronal/imss/${caja.dataset.cid}/desglose?mes=${MES}&anio=${ANIO}`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos) });
      if (r.ok) return recargar();
      const j = await r.json().catch(() => ({}));
      const m = caja.querySelector(".pat-msj");
      if (m) { m.classList.remove("oculto"); m.style.color = "var(--rojo)";
        m.textContent = j.detail || "No se pudo guardar el desglose."; }
    });
    $$(".formato-imss").forEach((inp) => inp.onchange = async () => {
      const caja = inp.closest("[data-cid]");
      const fd = new FormData();
      fd.append("mes", MES); fd.append("anio", ANIO);
      fd.append("archivo_pdf", inp.files[0]);
      const r = await api(`/api/patronal/imss/${caja.dataset.cid}/presentar`, { method: "POST", body: fd });
      const j = await r.json(); const msj = caja.querySelector(".pat-msj");
      msj.textContent = r.ok ? ("Enviado al cliente." + (j.honorarios_enviados ? " Periodo completo: honorarios enviados." : ""))
                             : (j.detail || "No se pudo enviar.");
      msj.style.color = r.ok ? "var(--verde)" : "var(--rojo)";
      msj.classList.remove("oculto");
      if (r.ok) setTimeout(recargar, 1300);
    });
    $("#isn-pdf").onchange = async () => {
      const msj = $("#isn-msj");
      if (!$("#isn-importe").value) { msj.textContent = "Capture primero el importe del ISN.";
        msj.style.color = "var(--rojo)"; msj.classList.remove("oculto"); return; }
      const fd = new FormData();
      fd.append("mes", MES); fd.append("anio", ANIO);
      fd.append("importe", $("#isn-importe").value);
      fd.append("archivo_pdf", $("#isn-pdf").files[0]);
      const r = await api(`/api/patronal/isn/${$("#isn-cliente").value}/presentar`, { method: "POST", body: fd });
      const j = await r.json();
      msj.textContent = r.ok ? ("ISN presentado y enviado." + (j.honorarios_enviados ? " Periodo completo: honorarios enviados." : ""))
                             : (j.detail || "No se pudo presentar.");
      msj.style.color = r.ok ? "var(--verde)" : "var(--rojo)";
      msj.classList.remove("oculto");
      if (r.ok) setTimeout(recargar, 1300);
    };
    $$(".entregar-nomina").forEach((inp) => inp.onchange = async () => {
      const fd = new FormData();
      fd.append("archivo_pdf", inp.files[0]);
      const r = await api(`/api/patronal/nominas/${inp.closest("[data-t]").dataset.t}/terminar`,
        { method: "POST", body: fd });
      if (r.ok) return recargar();
      const j = await r.json().catch(() => ({}));
      alert(j.detail || "No se pudo entregar la nómina. Intente de nuevo.");
    });
  }

  /* ---------- Tablero de obligaciones (Supervisora y Director) ---------- */
  /* =====================================================================
     OBLIGACIONES CON DOS MIRADAS (petición del Director):
       · POR CLIENTE  — quién va bien y quién no, con el detalle de lo que
         falta a un clic (sin abrumar de entrada).
       · POR CONTADOR — quién está cumpliendo en tiempo y forma, con su
         avance; los que van al corriente se van al fondo.
     ===================================================================== */
  async function vistaTableroObligaciones(objetivo, modo) {
    modo = modo || "cliente";
    const filas = await (await api(`/api/patronal/tablero?mes=${MES}&anio=${ANIO}`)).json();
    const punto = (ok) => `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${ok ? "var(--verde)" : "var(--rojo)"};flex:none"></span>`;

    const filaCliente = (f) => `
      <div class="obl-cliente" data-oc="${f.cliente_id}" style="border-bottom:1px solid var(--borde-suave)">
        <div style="display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;padding:13px 16px;${f.faltantes.length ? "cursor:pointer" : ""}">
          <p style="margin:0;flex:1;min-width:160px;font-size:14px;font-weight:700;color:var(--marino)">${f.cliente}
            ${f.tipo_cliente === "confianza_especial" ? `<span class="pildora ambar">confianza especial</span>` : ""}
            ${f.completo ? `<span class="pildora verde">periodo completo</span>` : ""}</p>
          <span style="font-size:12px;display:flex;align-items:center;gap:5px">${punto(f.obligaciones.sat)} SAT</span>
          ${f.obligaciones.imss !== undefined ? `
            <span style="font-size:12px;display:flex;align-items:center;gap:5px">${punto(f.obligaciones.imss)} IMSS
              <span style="color:var(--gris2)">(${["idse","sua","sipare"].filter((k) => f.imss_pasos && f.imss_pasos[k]).length}/3)</span></span>` : ""}
          ${f.obligaciones.isn !== undefined ? `
            <span style="font-size:12px;display:flex;align-items:center;gap:5px">${punto(f.obligaciones.isn)} ISN</span>` : ""}
          ${f.nominas_pendientes ? `<span style="font-size:12px;font-weight:700;color:var(--ambar)">${f.nominas_pendientes} nómina(s)</span>` : ""}
          <span style="font-size:11.5px;color:var(--gris2);min-width:110px">${(f.contador || "").split(" ").slice(0, 2).join(" ")}</span>
          ${f.faltantes.length ? `<span class="obl-flecha" style="font-size:11.5px;font-weight:800;color:var(--azul)">detalle ›</span>` : ""}
        </div>
        ${f.faltantes.length ? `
        <div class="obl-detalle oculto" style="padding:0 16px 14px 16px">
          <div style="background:var(--rojo-suave);border-radius:10px;padding:12px 14px">
            <p class="micro" style="margin:0 0 6px;color:var(--rojo)">Qué falta</p>
            ${f.faltantes.map((x) => `<p style="margin:3px 0;font-size:12.5px;color:var(--marino)">• ${x}</p>`).join("")}
            <p style="margin:8px 0 0;font-size:11.5px;color:var(--gris)">Responsable: <strong>${f.contador}</strong></p>
          </div>
        </div>` : ""}
      </div>`;

    // --- Pivote por contador (mismo lenguaje que Autorizaciones) ---
    const porContador = {};
    filas.forEach((f) => {
      const g = porContador[f.contador_id ?? "sin"] ||
        (porContador[f.contador_id ?? "sin"] = { contador: f.contador, clientes: [] });
      g.clientes.push(f);
    });
    const grupos = Object.values(porContador).map((g) => {
      const completos = g.clientes.filter((x) => x.completo).length;
      return { ...g, completos, total: g.clientes.length,
               pct: g.clientes.length ? Math.round(completos / g.clientes.length * 100) : 0,
               al_corriente: completos === g.clientes.length };
    }).sort((a, b) => (a.al_corriente - b.al_corriente) || (a.pct - b.pct));

    const tarjetaContador = (g) => `
      <div class="carta" style="padding:18px 20px">
        <div style="display:flex;flex-wrap:wrap;gap:8px 14px;align-items:baseline">
          <p style="margin:0;flex:1;font-size:15px;font-weight:800;color:var(--marino)">${g.contador}</p>
          ${g.al_corriente ? `<span class="pildora verde">al corriente</span>`
            : `<span class="pildora ambar">${g.total - g.completos} con pendientes</span>`}
          <span class="tnum" style="font-size:13px;font-weight:800">${g.completos}/${g.total}</span>
        </div>
        <div style="height:6px;border-radius:99px;background:var(--borde-suave);overflow:hidden;margin-top:8px">
          <div style="height:100%;width:${g.pct}%;background:${g.pct === 100 ? "var(--verde)" : g.pct >= 60 ? "var(--azul)" : "var(--ambar)"};transition:width .4s"></div>
        </div>
        ${g.al_corriente ? "" : `
        <div style="margin-top:12px;display:flex;flex-direction:column;gap:6px">
          ${g.clientes.filter((x) => !x.completo).map((x) => `
          <div style="background:var(--papel);border-radius:9px;padding:9px 12px">
            <p style="margin:0;font-size:12.5px;font-weight:700;color:var(--marino)">${x.cliente}</p>
            ${x.faltantes.map((t) => `<p style="margin:2px 0 0;font-size:11.5px;color:var(--gris)">• ${t}</p>`).join("")}
          </div>`).join("")}
        </div>`}
      </div>`;

    objetivo.innerHTML = `
      <div style="animation:aparecer .3s ease">
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px;align-items:center">
        <p class="micro" style="margin:0;flex:1">Obligaciones del periodo · ${NOMBRE_MES}</p>
        <button id="obl-modo-cliente" class="chip ${modo === "cliente" ? "activo" : ""}">Por cliente</button>
        <button id="obl-modo-contador" class="chip ${modo === "contador" ? "activo" : ""}">Por contador responsable</button>
      </div>
      ${modo === "cliente" ? `
        <div class="carta" style="overflow:hidden;padding:0">
          ${filas.map(filaCliente).join("") || `<p style="padding:20px;margin:0;font-size:13px;color:var(--gris2)">Sin clientes activos.</p>`}
        </div>`
      : `<div style="display:flex;flex-direction:column;gap:12px">
          ${grupos.map(tarjetaContador).join("")}
        </div>`}
      </div>`;

    $("#obl-modo-cliente").onclick = () => vistaTableroObligaciones(objetivo, "cliente");
    $("#obl-modo-contador").onclick = () => vistaTableroObligaciones(objetivo, "contador");
    $$(".obl-cliente").forEach((c) => {
      const det = c.querySelector(".obl-detalle");
      if (!det) return;
      c.firstElementChild.onclick = () => {
        det.classList.toggle("oculto");
        const fl = c.querySelector(".obl-flecha");
        if (fl) fl.textContent = det.classList.contains("oculto") ? "detalle ›" : "ocultar ˅";
      };
    });
  }


  /* ---------- Certificados y firmas (equipo) ---------- */
  async function vistaCertificados(objetivo) {
    const certs = await (await api("/api/certificados")).json();
    const colorEst = { vigente: "var(--verde)", por_vencer: "var(--ambar)", vencido: "var(--rojo)" };
    objetivo.innerHTML = `
      <div style="animation:aparecer .3s ease;display:flex;flex-wrap:wrap;gap:22px;align-items:flex-start">
        <div style="flex:2;min-width:min(100%,380px)">
          <p class="micro" style="margin:0 0 12px">Firmas, sellos y certificados — descarga con código 2FA del momento</p>
          <div class="carta" style="overflow:hidden">
            ${certs.map((x) => `
            <div class="fila" style="flex-wrap:wrap;gap:8px 14px" data-cert="${x.id}">
              <div style="flex:1;min-width:180px">
                <p style="margin:0;font-size:13.5px;font-weight:700">${x.descripcion}</p>
                <p style="margin:2px 0 0;font-size:11.5px;color:var(--gris2)">${x.tipo_nombre} · ${x.cliente} · vence ${x.fecha_vencimiento}</p>
              </div>
              <span style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:${colorEst[x.estatus] || "var(--gris2)"}">
                ${x.estatus.replace("_", " ")}${x.en_renovacion ? " · en renovación" : ""}</span>
              <input type="text" inputmode="numeric" maxlength="6" placeholder="Código 2FA" class="campo cert-totp" style="width:110px;padding:7px;font-size:12px;text-align:center">
              <button class="chip cert-descargar">Descargar</button>
              ${x.estatus !== "vigente" && !x.en_renovacion ? `<button class="chip cert-renovar" style="color:var(--ambar);border-color:var(--ambar)">Pedir renovación</button>` : ""}
            </div>`).join("") || `<p style="margin:0;padding:18px;font-size:13px;color:var(--gris2)">Sin certificados registrados aún.</p>`}
          </div>
        </div>
        <div class="carta" style="flex:1;min-width:min(100%,290px);padding:20px">
          <p style="margin:0 0 4px;font-size:15px;font-weight:800;color:var(--marino)">Subir certificado o renovación</p>
          <p style="margin:0 0 12px;font-size:11.5px;color:var(--gris2)">Solo los archivos (.zip/.cer/.key/.pfx/.pdf). Las contraseñas de las llaves NUNCA se suben aquí.</p>
          <div style="display:flex;flex-direction:column;gap:9px">
            <select id="cert-tipo" class="campo" style="padding:9px;font-size:13px">
              <option value="efirma">e.firma (FIEL)</option>
              <option value="csd">CSD (sello digital SAT)</option>
              <option value="sello_imss">Certificado IMSS</option>
              <option value="certificado_estatal">Certificado estatal</option>
              <option value="otro">Otro</option></select>
            <input id="cert-desc" class="campo" placeholder="Descripción (ej. e.firma Grupo Norte)" style="padding:9px;font-size:13px">
            <select id="cert-cliente" class="campo" style="padding:9px;font-size:13px"><option value="">Del despacho P&A</option></select>
            <label class="etiqueta" style="margin:0;font-size:11px">Fecha de vencimiento
              <input id="cert-vence" type="date" class="campo" style="margin-top:3px;padding:9px;font-size:13px"></label>
            <select id="cert-reemplaza" class="campo" style="padding:9px;font-size:13px">
              <option value="">No reemplaza a ninguno</option>
              ${certs.map((x) => `<option value="${x.id}">Renueva: ${x.descripcion}</option>`).join("")}</select>
            <input id="cert-archivo" type="file" accept=".zip,.pdf,.cer,.key,.pfx,.p12" style="font-size:12px">
            <button id="cert-subir" class="btn btn-azul" style="min-height:44px;font-size:13px">Guardar en la bóveda blindada</button>
            <p id="cert-msj" class="oculto" style="margin:0;font-size:12px;font-weight:700"></p>
          </div>
        </div>
      </div>`;

    api("/api/citas/clientes-agendables").then((r) => r.json()).then((cs) => {
      $("#cert-cliente").innerHTML += cs.map((c) => `<option value="${c.cliente_id}">${c.cliente}</option>`).join("");
    });
    $$(".cert-descargar").forEach((b) => b.onclick = async () => {
      const caja = b.closest("[data-cert]");
      const codigo = caja.querySelector(".cert-totp").value.trim();
      if (codigo.length !== 6) { caja.querySelector(".cert-totp").focus(); return; }
      const fd = new FormData(); fd.append("codigo_totp", codigo);
      b.textContent = "…";
      const r = await api(`/api/certificados/${caja.dataset.cert}/descargar`, { method: "POST", body: fd });
      b.textContent = "Descargar";
      if (!r.ok) { b.textContent = "Código inválido"; setTimeout(() => b.textContent = "Descargar", 1800); return; }
      const tipo = r.headers.get("content-type") || "";
      // (el servidor entrega el archivo directo: sin URL de otro dominio)
      const blob = await r.blob(); const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement("a"), { href: url, download: "certificado" });
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    });
    $$(".cert-renovar").forEach((b) => b.onclick = async () => {
      b.disabled = true;
      await api(`/api/certificados/${b.closest("[data-cert]").dataset.cert}/solicitar-renovacion`, { method: "POST" });
      b.textContent = "Solicitada ✓";
    });
    $("#cert-subir").onclick = async () => {
      const msj = $("#cert-msj");
      const f = $("#cert-archivo").files[0];
      if (!f || !$("#cert-desc").value || !$("#cert-vence").value) {
        msj.textContent = "Complete descripción, vencimiento y archivo.";
        msj.style.color = "var(--rojo)"; msj.classList.remove("oculto"); return; }
      const fd = new FormData();
      fd.append("tipo", $("#cert-tipo").value);
      fd.append("descripcion", $("#cert-desc").value);
      fd.append("fecha_vencimiento", $("#cert-vence").value);
      if ($("#cert-cliente").value) fd.append("cliente_id", $("#cert-cliente").value);
      if ($("#cert-reemplaza").value) fd.append("reemplaza_a", $("#cert-reemplaza").value);
      fd.append("archivo", f);
      const r = await api("/api/certificados", { method: "POST", body: fd });
      const j = await r.json();
      msj.textContent = r.ok ? "Guardado: cifrado, vigilado y disponible para quien lo necesite." : (j.detail || "No se pudo guardar.");
      msj.style.color = r.ok ? "var(--verde)" : "var(--rojo)";
      msj.classList.remove("oculto");
      if (r.ok) setTimeout(() => vistaCertificados(objetivo), 1300);
    };
  }



  /* ---------- Respaldos de CONTPAQ (con rotación) ---------- */
  async function vistaRespaldos(objetivo) {
    const [clientes, data] = await Promise.all([
      (await api("/api/citas/clientes-agendables")).json(),
      (await api("/api/respaldos")).json(),
    ]);
    objetivo.innerHTML = `
      <div style="animation:aparecer .3s ease;display:flex;flex-wrap:wrap;gap:22px;align-items:flex-start">
        <div class="carta" style="flex:1;min-width:min(100%,300px);padding:22px">
          <p style="margin:0 0 4px;font-size:15px;font-weight:800;color:var(--marino)">Subir respaldo de CONTPAQ</p>
          <p style="margin:0 0 14px;font-size:12px;color:var(--gris2);line-height:1.6">
            Se conservan los <strong>${data.conservados_por_cliente} más recientes</strong> por cliente:
            al subir uno nuevo, el más antiguo se elimina solo. Acepta .zip, .rar, .bak, .7z, .sql</p>
          <div style="display:flex;flex-direction:column;gap:9px">
            <select id="resp-cliente" class="campo" style="padding:9px;font-size:13px">
              ${clientes.map((c) => `<option value="${c.cliente_id}">${c.cliente}</option>`).join("")}</select>
            <div style="display:flex;gap:8px">
              <select id="resp-mes" class="campo" style="flex:1;padding:9px;font-size:13px">
                ${["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
                  .map((m, i) => `<option value="${i + 1}" ${i + 1 === MES ? "selected" : ""}>${m}</option>`).join("")}</select>
              <input id="resp-anio" type="number" class="campo" value="${ANIO}" style="width:96px;padding:9px;font-size:13px">
            </div>
            <input id="resp-archivo" type="file" accept=".zip,.rar,.bak,.7z,.sql" style="font-size:12px">
            <button id="resp-subir" class="btn btn-azul" style="min-height:44px;font-size:13px">Guardar respaldo</button>
            <p id="resp-msj" class="oculto" style="margin:0;font-size:12px;font-weight:700;line-height:1.5"></p>
          </div>
        </div>
        <div style="flex:2;min-width:min(100%,340px)">
          <p class="micro" style="margin:0 0 12px">Respaldos guardados (los más nuevos primero)</p>
          <div class="carta" style="overflow:hidden">
            ${data.respaldos.map((r, i, arr) => `
            <div class="fila" style="flex-wrap:wrap;gap:8px 14px">
              <div style="flex:1;min-width:170px">
                <p style="margin:0;font-size:13.5px;font-weight:700">${r.cliente}
                  ${arr.findIndex((x) => x.cliente === r.cliente) === i ? `<span class="pildora verde" style="margin-left:6px">más reciente</span>` : ""}</p>
                <p style="margin:2px 0 0;font-size:11.5px;color:var(--gris2)">${r.periodo} · ${r.archivo}</p>
              </div>
              <button class="chip resp-bajar" data-id="${r.id}">Descargar</button>
            </div>`).join("") || `<p style="margin:0;padding:18px;font-size:13px;color:var(--gris2)">Aún no hay respaldos guardados.</p>`}
          </div>
        </div>
      </div>`;

    $("#resp-subir").onclick = async () => {
      const msj = $("#resp-msj");
      const f = $("#resp-archivo").files[0];
      if (!f) { msj.textContent = "Elija el archivo del respaldo."; msj.style.color = "var(--rojo)";
        msj.classList.remove("oculto"); return; }
      const fd = new FormData();
      fd.append("anio", $("#resp-anio").value);
      fd.append("mes", $("#resp-mes").value);
      fd.append("archivo", f);
      $("#resp-subir").disabled = true; $("#resp-subir").textContent = "Subiendo…";
      const r = await api(`/api/respaldos/${$("#resp-cliente").value}`, { method: "POST", body: fd });
      const j = await r.json();
      $("#resp-subir").disabled = false; $("#resp-subir").textContent = "Guardar respaldo";
      if (!r.ok) { msj.textContent = j.detail || "No se pudo guardar."; msj.style.color = "var(--rojo)";
        msj.classList.remove("oculto"); return; }
      msj.textContent = `Guardado (${j.mb} MB).`
        + (j.eliminados_por_rotacion.length ? ` Por rotación se eliminó: ${j.eliminados_por_rotacion.join(", ")}.` : "")
        + (j.advertencia ? ` ${j.advertencia}` : "");
      msj.style.color = j.advertencia ? "var(--ambar)" : "var(--verde)";
      msj.classList.remove("oculto");
      setTimeout(() => vistaRespaldos(objetivo), 1600);
    };
    $$(".resp-bajar").forEach((b) => b.onclick = async () => {
      const r = await api(`/api/respaldos/${b.dataset.id}/descargar`);
      if (!r.ok) return;
      const tipo = r.headers.get("content-type") || "";
      // (el servidor entrega el archivo directo: sin URL de otro dominio)
      const blob = await r.blob(); const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement("a"), { href: url, download: "respaldo" });
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    });
  }


  /* ---------- Nombres de régimen (para mostrarlos en listas) ---------- */
  let NOMBRES_REGIMEN = {};
  api("/api/calculos/regimenes").then((r) => r.ok && r.json()).then((j) => {
    if (j) NOMBRES_REGIMEN = j.regimenes;
  }).catch(() => {});

  /* ---------- Contraseña temporal: se muestra UNA vez para entregarla ---------- */
  function mostrarPasswordTemporal(cliente, email, password) {
    const capa = document.createElement("div");
    capa.style.cssText = "position:fixed;inset:0;background:rgba(10,28,51,.55);display:grid;place-items:center;z-index:90;padding:20px";
    capa.innerHTML = `
      <div class="carta" style="max-width:430px;width:100%;padding:28px">
        <p style="margin:0 0 6px;font-size:17px;font-weight:800;color:var(--marino)">Contraseña de ${cliente}</p>
        <p style="margin:0 0 18px;font-size:13px;color:var(--gris);line-height:1.6">
          Entréguesela al cliente (por teléfono o en persona). <strong>No se vuelve a mostrar</strong>,
          y él deberá cambiarla en su primer acceso.</p>
        <div style="background:var(--azul-suave);border:1px solid var(--azul-borde);border-radius:12px;padding:16px;text-align:center">
          <p style="margin:0 0 4px;font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--gris2)">Usuario</p>
          <p class="tnum" style="margin:0 0 12px;font-size:14px;font-weight:700;color:var(--marino);user-select:all">${email}</p>
          <p style="margin:0 0 4px;font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--gris2)">Contraseña temporal</p>
          <p class="tnum" style="margin:0;font-size:22px;font-weight:800;color:var(--azul);letter-spacing:.02em;user-select:all">${password}</p>
        </div>
        <div style="display:flex;gap:10px;margin-top:20px">
          <button id="pt-copiar" class="btn btn-linea" style="flex:1;min-height:44px">Copiar</button>
          <button id="pt-listo" class="btn btn-azul" style="flex:1;min-height:44px">Ya la anoté</button>
        </div>
      </div>`;
    document.body.appendChild(capa);
    capa.querySelector("#pt-copiar").onclick = () => {
      navigator.clipboard.writeText(password).then(() => {
        capa.querySelector("#pt-copiar").textContent = "Copiada ✓";
      }).catch(() => { capa.querySelector("#pt-copiar").textContent = "Selecciónela y copie"; });
    };
    capa.querySelector("#pt-listo").onclick = () => capa.remove();
  }

  /* ---------- Editar cliente: TODO corregible, con rastro de auditoría ---------- */
  function abrirEdicionCliente(c, CAT) {
    const capa = document.createElement("div");
    capa.style.cssText = "position:fixed;inset:0;background:rgba(10,28,51,.55);display:grid;place-items:center;z-index:90;padding:20px;overflow:auto";
    const regsDe = (tp) => Object.entries(CAT.regimenes)
      .filter(([k]) => !k.startsWith("anual_") && (!tp || CAT.tipo_persona[k] === tp));
    capa.innerHTML = `
      <div class="carta" style="max-width:520px;width:100%;padding:28px;max-height:92vh;overflow:auto">
        <p style="margin:0 0 4px;font-size:17px;font-weight:800;color:var(--marino)">Editar ${c.nombre_comercial}</p>
        <p style="margin:0 0 18px;font-size:12px;color:var(--gris2);line-height:1.5">
          Cada cambio queda registrado en la bitácora (qué se cambió, de qué valor a cuál, quién y cuándo).</p>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <label class="etiqueta" style="margin:0;grid-column:1/-1">Nombre comercial
            <input id="ed-nombre" class="campo" value="${c.nombre_comercial || ""}" style="margin-top:3px;padding:9px;font-size:13px"></label>
          <label class="etiqueta" style="margin:0;grid-column:1/-1">Razón social
            <input id="ed-razon" class="campo" value="${c.razon_social || ""}" style="margin-top:3px;padding:9px;font-size:13px"></label>
          <label class="etiqueta" style="margin:0">RFC
            <input id="ed-rfc" class="campo" value="${c.rfc || ""}" style="margin-top:3px;padding:9px;font-size:13px;text-transform:uppercase"></label>
          <label class="etiqueta" style="margin:0">WhatsApp
            <input id="ed-tel" class="campo" value="${c.telefono || ""}" style="margin-top:3px;padding:9px;font-size:13px"></label>
          <label class="etiqueta" style="margin:0;grid-column:1/-1">Correo
            <input id="ed-email" class="campo" value="${c.email || ""}" style="margin-top:3px;padding:9px;font-size:13px"></label>
          <label class="etiqueta" style="margin:0">Tipo de persona
            <select id="ed-persona" class="campo" style="margin-top:3px;padding:9px;font-size:13px">
              <option value="">— sin definir —</option>
              <option value="fisica" ${c.tipo_persona === "fisica" ? "selected" : ""}>Persona física</option>
              <option value="moral" ${c.tipo_persona === "moral" ? "selected" : ""}>Persona moral</option>
            </select></label>
          <label class="etiqueta" style="margin:0">Régimen fiscal
            <select id="ed-regimen" class="campo" style="margin-top:3px;padding:9px;font-size:13px">
              <option value="">— sin definir —</option>
              ${regsDe(c.tipo_persona).map(([k, v]) => `<option value="${k}" ${k === c.regimen_fiscal ? "selected" : ""}>${v}</option>`).join("")}
            </select></label>
        </div>
        <p id="ed-msj" class="oculto" style="margin:14px 0 0;font-size:12.5px;font-weight:700"></p>
        <div style="display:flex;gap:10px;margin-top:20px">
          <button id="ed-cancelar" class="btn btn-linea" style="flex:1;min-height:44px">Cancelar</button>
          <button id="ed-guardar" class="btn btn-azul" style="flex:1;min-height:44px">Guardar cambios</button>
        </div>
      </div>`;
    document.body.appendChild(capa);

    capa.querySelector("#ed-persona").onchange = (e) => {
      const sel = capa.querySelector("#ed-regimen");
      sel.innerHTML = `<option value="">— sin definir —</option>` +
        regsDe(e.target.value).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
    };
    capa.querySelector("#ed-cancelar").onclick = () => capa.remove();
    capa.querySelector("#ed-guardar").onclick = async () => {
      const msj = capa.querySelector("#ed-msj");
      const cuerpo = {
        nombre_comercial: capa.querySelector("#ed-nombre").value,
        razon_social: capa.querySelector("#ed-razon").value,
        rfc: capa.querySelector("#ed-rfc").value.toUpperCase(),
        telefono_whatsapp: capa.querySelector("#ed-tel").value,
        email: capa.querySelector("#ed-email").value || null,
        tipo_persona: capa.querySelector("#ed-persona").value || null,
        regimen_fiscal: capa.querySelector("#ed-regimen").value || null,
      };
      const r = await api(`/api/admin/clientes/${c.id}`, { method: "PUT",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo) });
      const j = await r.json();
      if (!r.ok) { msj.textContent = j.detail || "No se pudo guardar."; msj.style.color = "var(--rojo)";
        msj.classList.remove("oculto"); return; }
      msj.textContent = j.sin_cambios ? "No hubo cambios." : `Guardado: ${j.cambios.join(", ")}.`;
      msj.style.color = "var(--verde)"; msj.classList.remove("oculto");
      setTimeout(() => { capa.remove(); subAdmin(); }, 1100);
    };
  }


  /* ---------- INVENTARIO DE SALDOS A FAVOR ---------- */
  async function vistaSaldosFavor(objetivo) {
    const [clientes, data] = await Promise.all([
      (await api("/api/citas/clientes-agendables")).json(),
      (await api("/api/saldos-favor")).json(),
    ]);
    const COLOR_EST = { disponible: "var(--verde)", agotado: "var(--gris2)",
      en_devolucion: "var(--azul)", devuelto: "var(--marino)", prescrito: "var(--rojo)" };

    objetivo.innerHTML = `
      <div style="animation:aparecer .3s ease">
      <div class="carta" style="padding:18px 22px;margin-bottom:18px;display:flex;flex-wrap:wrap;gap:14px;align-items:center;justify-content:space-between">
        <div>
          <p class="micro" style="margin:0">Remanente total disponible</p>
          <p class="tnum" style="margin:4px 0 0;font-size:26px;font-weight:800;color:var(--verde)">${dinero(data.remanente_total_disponible)}</p>
        </div>
        <button id="sf-nuevo" class="btn btn-linea" style="min-height:42px;font-size:13px">Registrar saldo histórico</button>
      </div>

      <p class="micro" style="margin:0 0 12px">Saldos a favor — origen, aplicaciones y remanente</p>
      <div style="display:flex;flex-direction:column;gap:14px">
      ${data.saldos.map((s) => `
        <div class="carta" style="padding:20px" data-sf="${s.id}">
          <div style="display:flex;flex-wrap:wrap;gap:10px 18px;align-items:baseline">
            <p style="margin:0;font-size:15px;font-weight:800;color:var(--marino)">${s.cliente}
              <span style="font-weight:600;color:var(--azul)"> · ${s.impuesto_nombre} ${s.periodo}</span></p>
            <span style="font-size:10.5px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:${COLOR_EST[s.estatus] || "var(--gris2)"}">${s.estatus.replace("_", " ")}</span>
            ${s.por_prescribir ? `<span style="font-size:11px;font-weight:800;color:var(--ambar)">⚠ prescribe en ${s.dias_para_prescribir} días</span>` : ""}
            ${s.prescrito ? `<span style="font-size:11px;font-weight:800;color:var(--rojo)">PRESCRITO</span>` : ""}
          </div>

          <div style="display:flex;flex-wrap:wrap;gap:22px;margin-top:14px">
            <div><p class="micro" style="margin:0">Original</p>
              <p class="tnum" style="margin:2px 0 0;font-size:16px;font-weight:700">${dinero(s.monto_original)}</p></div>
            <div><p class="micro" style="margin:0">Aplicado</p>
              <p class="tnum" style="margin:2px 0 0;font-size:16px;font-weight:700;color:var(--gris)">${dinero(s.monto_aplicado)}</p></div>
            <div><p class="micro" style="margin:0">Remanente</p>
              <p class="tnum" style="margin:2px 0 0;font-size:20px;font-weight:800;color:${s.remanente > 0 ? "var(--verde)" : "var(--gris2)"}">${dinero(s.remanente)}</p></div>
            <div style="flex:1;min-width:170px">
              <p class="micro" style="margin:0">Declaración que lo originó</p>
              <p style="margin:2px 0 0;font-size:12.5px">
                ${s.numero_operacion ? `Op. <span class="tnum" style="font-weight:700">${s.numero_operacion}</span>` : `<span style="color:var(--ambar)">Sin número de operación</span>`}
                ${s.comprobante_documento_id
                  ? ` · <button class="sf-comprobante" data-doc="${s.comprobante_documento_id}" style="border:none;background:none;padding:0;color:var(--azul);font-weight:700;font-size:12.5px;cursor:pointer;text-decoration:underline">ver comprobante</button>`
                  : ` · <label style="color:var(--azul);font-weight:700;cursor:pointer;text-decoration:underline">adjuntar comprobante
                       <input type="file" accept="application/pdf" class="sf-subir-comp" style="display:none"></label>`}
              </p>
            </div>
          </div>

          ${s.aplicaciones.length ? `
            <details style="margin-top:12px">
              <summary style="font-size:12px;font-weight:700;color:var(--azul);cursor:pointer">Historial de aplicaciones (${s.aplicaciones.length})</summary>
              ${s.aplicaciones.map((a) => `
                <div style="display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-bottom:1px solid var(--borde-suave);font-size:12.5px">
                  <span>${a.impuesto_destino} · ${a.periodo}${a.numero_operacion_destino ? ` · op. ${a.numero_operacion_destino}` : ""}</span>
                  <span class="tnum" style="font-weight:700">${dinero(a.monto)}</span></div>`).join("")}
            </details>` : ""}

          ${s.remanente > 0 && s.estatus === "disponible" ? `
            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:14px;align-items:flex-end">
              <label class="etiqueta" style="margin:0;font-size:10px">Aplicar
                <input type="number" step="0.01" max="${s.remanente}" class="campo sf-monto" placeholder="Monto" style="margin-top:3px;padding:8px;font-size:12.5px;width:110px"></label>
              <label class="etiqueta" style="margin:0;font-size:10px">Contra
                <select class="campo sf-impuesto" style="margin-top:3px;padding:8px;font-size:12.5px;width:90px">
                  <option value="isr">ISR</option><option value="iva">IVA</option>
                  <option value="ieps">IEPS</option><option value="otro">Otro</option></select></label>
              <label class="etiqueta" style="margin:0;font-size:10px">Periodo
                <div style="display:flex;gap:4px;margin-top:3px">
                  <select class="campo sf-mes" style="padding:8px;font-size:12.5px;width:74px">
                    ${Array.from({ length: 12 }, (_, i) => `<option value="${i + 1}" ${i + 1 === MES ? "selected" : ""}>${String(i + 1).padStart(2, "0")}</option>`).join("")}
                    <option value="">Anual</option></select>
                  <input type="number" class="campo sf-anio" value="${ANIO}" style="padding:8px;font-size:12.5px;width:78px"></label>
                </div>
              <label class="etiqueta" style="margin:0;font-size:10px">N.º operación
                <input class="campo sf-op" placeholder="opcional" style="margin-top:3px;padding:8px;font-size:12.5px;width:120px"></label>
              <button class="btn btn-azul sf-aplicar" style="min-height:40px;font-size:12.5px">Aplicar saldo</button>
            </div>` : ""}
          <p class="sf-msj oculto" style="margin:8px 0 0;font-size:12px;font-weight:700"></p>
        </div>`).join("") || `<div class="carta" style="padding:22px;font-size:13.5px;color:var(--gris2)">
          No hay saldos a favor registrados. Se dan de alta solos cuando una declaración arroja saldo a favor.</div>`}
      </div></div>`;

    const recargar = () => vistaSaldosFavor(objetivo);
    $$(".sf-aplicar").forEach((b) => b.onclick = async () => {
      const caja = b.closest("[data-sf]");
      const msj = caja.querySelector(".sf-msj");
      const monto = +caja.querySelector(".sf-monto").value;
      if (!monto || monto <= 0) { msj.textContent = "Capture el monto a aplicar.";
        msj.style.color = "var(--rojo)"; msj.classList.remove("oculto"); return; }
      const mes = caja.querySelector(".sf-mes").value;
      b.disabled = true;
      const r = await api(`/api/saldos-favor/${caja.dataset.sf}/aplicar`, { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ monto, impuesto_destino: caja.querySelector(".sf-impuesto").value,
          mes_aplicacion: mes ? +mes : null, anio_aplicacion: +caja.querySelector(".sf-anio").value,
          numero_operacion_destino: caja.querySelector(".sf-op").value || null }) });
      const j = await r.json();
      b.disabled = false;
      if (!r.ok) { msj.textContent = j.detail || "No se pudo aplicar."; msj.style.color = "var(--rojo)";
        msj.classList.remove("oculto"); return; }
      msj.textContent = `Aplicado. Remanente: ${dinero(j.remanente)}.`;
      msj.style.color = "var(--verde)"; msj.classList.remove("oculto");
      setTimeout(recargar, 1200);
    });
    $$(".sf-subir-comp").forEach((inp) => inp.onchange = async () => {
      const caja = inp.closest("[data-sf]");
      const fd = new FormData();
      fd.append("archivo_pdf", inp.files[0]);
      const r = await api(`/api/saldos-favor/${caja.dataset.sf}/comprobante`, { method: "POST", body: fd });
      if (r.ok) return recargar();
      const j = await r.json().catch(() => ({}));
      const m = caja.querySelector(".sf-msj");
      if (m) { m.classList.remove("oculto"); m.style.color = "var(--rojo)";
        m.textContent = j.detail || "No se pudo subir el comprobante."; }
      else alert(j.detail || "No se pudo subir el comprobante.");
    });
    $$(".sf-comprobante").forEach((b) => b.onclick = () => abrirDocumento(b.dataset.doc));
    $("#sf-nuevo").onclick = () => abrirAltaSaldo(clientes, recargar);
  }

  /* ---------- Abrir un documento de la bóveda en pestaña nueva ---------- */
  async function abrirDocumento(documentoId) {
    const r = await api(`/api/obligaciones/boveda/${documentoId}/descargar`);
    if (!r.ok) return;
    const tipo = r.headers.get("content-type") || "";
    // (el servidor entrega el archivo directo: sin URL de otro dominio)
    const url = URL.createObjectURL(await r.blob());
    window.open(url, "_blank");
  }

  /* ---------- Alta manual de saldo (histórico, de antes del sistema) ---------- */
  function abrirAltaSaldo(clientes, alTerminar) {
    const capa = document.createElement("div");
    capa.style.cssText = "position:fixed;inset:0;background:rgba(10,28,51,.55);display:grid;place-items:center;z-index:90;padding:20px";
    capa.innerHTML = `
      <div class="carta" style="max-width:430px;width:100%;padding:26px">
        <p style="margin:0 0 4px;font-size:17px;font-weight:800;color:var(--marino)">Registrar saldo a favor</p>
        <p style="margin:0 0 16px;font-size:12px;color:var(--gris2);line-height:1.5">
          Para saldos históricos (de antes del sistema). Los nuevos se registran solos al presentar la declaración.</p>
        <div style="display:flex;flex-direction:column;gap:9px">
          <select id="sn-cliente" class="campo" style="padding:9px;font-size:13px">
            ${clientes.map((c) => `<option value="${c.cliente_id}">${c.cliente}</option>`).join("")}</select>
          <div style="display:flex;gap:8px">
            <select id="sn-impuesto" class="campo" style="flex:1;padding:9px;font-size:13px">
              <option value="isr">ISR</option><option value="iva">IVA</option>
              <option value="ieps">IEPS</option><option value="otro">Otro</option></select>
            <input id="sn-monto" type="number" step="0.01" class="campo" placeholder="Monto" style="flex:1;padding:9px;font-size:13px">
          </div>
          <div style="display:flex;gap:8px">
            <select id="sn-mes" class="campo" style="flex:1;padding:9px;font-size:13px">
              ${Array.from({ length: 12 }, (_, i) => `<option value="${i + 1}">${String(i + 1).padStart(2, "0")}</option>`).join("")}
              <option value="">Anual</option></select>
            <input id="sn-anio" type="number" class="campo" value="${ANIO}" style="flex:1;padding:9px;font-size:13px">
          </div>
          <input id="sn-op" class="campo" placeholder="Número de operación (opcional)" style="padding:9px;font-size:13px">
          <p id="sn-msj" class="oculto" style="margin:0;font-size:12px;font-weight:700"></p>
          <div style="display:flex;gap:10px;margin-top:6px">
            <button id="sn-cancelar" class="btn btn-linea" style="flex:1;min-height:44px">Cancelar</button>
            <button id="sn-guardar" class="btn btn-azul" style="flex:1;min-height:44px">Registrar</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(capa);
    capa.querySelector("#sn-cancelar").onclick = () => capa.remove();
    capa.querySelector("#sn-guardar").onclick = async () => {
      const msj = capa.querySelector("#sn-msj");
      const monto = +capa.querySelector("#sn-monto").value;
      if (!monto || monto <= 0) { msj.textContent = "Capture el monto."; msj.style.color = "var(--rojo)";
        msj.classList.remove("oculto"); return; }
      const mes = capa.querySelector("#sn-mes").value;
      const r = await api("/api/saldos-favor", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cliente_id: +capa.querySelector("#sn-cliente").value,
          impuesto: capa.querySelector("#sn-impuesto").value, monto_original: monto,
          mes: mes ? +mes : null, es_anual: !mes, anio: +capa.querySelector("#sn-anio").value,
          numero_operacion: capa.querySelector("#sn-op").value || null }) });
      const j = await r.json();
      if (!r.ok) { msj.textContent = j.detail || "No se pudo registrar."; msj.style.color = "var(--rojo)";
        msj.classList.remove("oculto"); return; }
      capa.remove(); alTerminar();
    };
  }


  /* ---------- ALTA MASIVA POR EXCEL ---------- */
  function abrirAltaMasiva() {
    const capa = document.createElement("div");
    capa.style.cssText = "position:fixed;inset:0;background:rgba(10,28,51,.55);display:grid;place-items:center;z-index:90;padding:20px;overflow:auto";
    capa.innerHTML = `
      <div class="carta" style="max-width:640px;width:100%;padding:28px;max-height:92vh;overflow:auto">
        <p style="margin:0 0 4px;font-size:18px;font-weight:800;color:var(--marino)">Alta masiva</p>
        <p style="margin:0 0 20px;font-size:13px;color:var(--gris);line-height:1.6">
          Dé de alta toda la cartera de una vez, desde un Excel. Primero verá una
          <strong>revisión</strong>: si algo está mal, se lo dice renglón por renglón y
          <strong>no se guarda nada</strong>.</p>

        <div style="display:flex;flex-direction:column;gap:14px">
          <div style="background:var(--azul-suave);border:1px solid var(--azul-borde);border-radius:12px;padding:16px">
            <p style="margin:0 0 4px;font-size:13.5px;font-weight:700;color:var(--marino)">Paso 1 · La plantilla</p>
            <p style="margin:0 0 10px;font-size:12.5px;color:var(--gris);line-height:1.5">
              Trae dos hojas (CLIENTES y PERSONAL), un ejemplo y la lista exacta de regímenes válidos.</p>
            <button id="am-plantilla" class="btn btn-azul" style="min-height:42px;font-size:13px">Descargar plantilla de Excel</button>
          </div>

          <div style="border:1px dashed var(--borde);border-radius:12px;padding:16px">
            <p style="margin:0 0 4px;font-size:13.5px;font-weight:700;color:var(--marino)">Paso 2 · Súbala llena</p>
            <p style="margin:0 0 10px;font-size:12.5px;color:var(--gris);line-height:1.5">
              Borre la fila del ejemplo (la amarilla) y llene sus renglones.</p>
            <input type="file" id="am-archivo" accept=".xlsx,.xlsm" style="font-size:12.5px;width:100%">
            <button id="am-revisar" class="btn btn-linea" style="margin-top:10px;min-height:42px;font-size:13px;width:100%">Revisar el archivo</button>
          </div>

          <div id="am-resultado"></div>
        </div>

        <button id="am-cerrar" class="btn btn-linea" style="margin-top:20px;min-height:44px;width:100%">Cerrar</button>
      </div>`;
    document.body.appendChild(capa);
    capa.querySelector("#am-cerrar").onclick = () => capa.remove();

    capa.querySelector("#am-plantilla").onclick = async () => {
      const r = await api("/api/importacion/plantilla");
      if (!r.ok) return;
      const url = URL.createObjectURL(await r.blob());
      const a = Object.assign(document.createElement("a"),
        { href: url, download: "alta_masiva_pafirma.xlsx" });
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    };

    const zona = capa.querySelector("#am-resultado");
    let archivoOk = null;

    capa.querySelector("#am-revisar").onclick = async () => {
      const f = capa.querySelector("#am-archivo").files[0];
      if (!f) { zona.innerHTML = `<p style="margin:0;font-size:13px;font-weight:700;color:var(--rojo)">Elija el archivo de Excel.</p>`; return; }
      zona.innerHTML = `<p style="margin:0;font-size:13px;color:var(--gris2)">Revisando…</p>`;
      const fd = new FormData(); fd.append("archivo", f);
      const r = await api("/api/importacion/revisar", { method: "POST", body: fd });
      const j = await r.json();
      if (!r.ok) {
        zona.innerHTML = `<p style="margin:0;font-size:13px;font-weight:700;color:var(--rojo)">${j.detail}</p>`;
        return;
      }
      archivoOk = j.se_puede_importar ? f : null;
      const errores = j.errores.length ? `
        <p style="margin:14px 0 8px;font-size:13px;font-weight:800;color:var(--rojo)">
          Corrija estos renglones en el Excel y vuelva a subirlo:</p>
        <div style="max-height:220px;overflow:auto;display:flex;flex-direction:column;gap:6px">
        ${j.errores.map((e) => `
          <div style="background:var(--rojo-suave);border:1px solid var(--rojo-borde);border-radius:8px;padding:8px 10px">
            <p style="margin:0;font-size:12.5px;font-weight:700">${e.hoja} · renglón ${e.renglon}${e.nombre ? ` · ${e.nombre}` : ""}</p>
            ${e.errores.map((x) => `<p style="margin:2px 0 0;font-size:12px;color:var(--rojo)">— ${x}</p>`).join("")}
          </div>`).join("")}
        </div>` : "";
      const listo = j.se_puede_importar ? `
        <div style="background:var(--verde-suave);border:1px solid var(--verde);border-radius:12px;padding:16px;margin-top:14px">
          <p style="margin:0 0 8px;font-size:13.5px;font-weight:800;color:var(--verde)">Todo correcto. Esto se va a dar de alta:</p>
          ${j.vista_previa.personal.map((p) => `
            <div style="display:flex;justify-content:space-between;gap:10px;padding:4px 0;font-size:12.5px;border-bottom:1px solid var(--borde-suave)">
              <span><strong>${p.nombre}</strong> · ${p.correo}</span><span style="color:var(--gris2)">${p.rol}</span></div>`).join("")}
          ${j.vista_previa.clientes.map((x) => `
            <div style="display:flex;justify-content:space-between;gap:10px;padding:4px 0;font-size:12.5px;border-bottom:1px solid var(--borde-suave)">
              <span><strong>${x.nombre}</strong></span>
              <span style="color:var(--gris2)">${x.regimen}${x.portal ? " · con portal" : ""}</span></div>`).join("")}
          <button id="am-confirmar" class="btn btn-azul" style="margin-top:14px;min-height:46px;width:100%;background:var(--verde)">
            Dar de alta ${j.personal.listos} persona${j.personal.listos === 1 ? "" : "s"} y ${j.clientes.listos} cliente${j.clientes.listos === 1 ? "" : "s"}</button>
        </div>` : "";
      zona.innerHTML = `
        <p style="margin:0;font-size:13px;font-weight:700">
          Personal: ${j.personal.listos}/${j.personal.total} · Clientes: ${j.clientes.listos}/${j.clientes.total}</p>
        ${errores}${listo}`;

      const btn = capa.querySelector("#am-confirmar");
      if (btn) btn.onclick = async () => {
        btn.disabled = true; btn.textContent = "Dando de alta…";
        const fd2 = new FormData(); fd2.append("archivo", archivoOk);
        const rr = await api("/api/importacion/confirmar", { method: "POST", body: fd2 });
        const jj = await rr.json();
        if (!rr.ok) {
          btn.disabled = false; btn.textContent = "Reintentar";
          zona.innerHTML = `<p style="margin:0;font-size:13px;font-weight:700;color:var(--rojo)">
            ${(jj.detail && jj.detail.mensaje) || jj.detail || "No se pudo dar de alta."}</p>`;
          return;
        }
        mostrarCredenciales(jj, capa);
      };
    };
  }

  /* ---------- Contraseñas del alta masiva: se muestran UNA vez ---------- */
  function mostrarCredenciales(j, capa) {
    const texto = j.credenciales
      .map((c) => `${c.tipo}\t${c.nombre}\t${c.usuario}\t${c.password}`).join("\n");
    capa.querySelector(".carta").innerHTML = `
      <p style="margin:0 0 4px;font-size:18px;font-weight:800;color:var(--marino)">
        Listo: ${j.personal_creado} del personal y ${j.clientes_creados} clientes</p>
      <p style="margin:0 0 18px;font-size:13px;color:var(--rojo);font-weight:700;line-height:1.6">
        ${j.aviso}</p>
      <div style="max-height:340px;overflow:auto;border:1px solid var(--borde);border-radius:12px">
        <div style="display:grid;grid-template-columns:70px 1fr 1fr 130px;gap:8px;padding:10px 12px;background:var(--azul-suave);position:sticky;top:0">
          ${["", "Nombre", "Usuario", "Contraseña"].map((t) => `<span class="micro" style="margin:0">${t}</span>`).join("")}
        </div>
        ${j.credenciales.map((c) => `
          <div style="display:grid;grid-template-columns:70px 1fr 1fr 130px;gap:8px;padding:9px 12px;border-top:1px solid var(--borde-suave);font-size:12.5px;align-items:center">
            <span style="font-size:10px;font-weight:800;color:var(--gris2);text-transform:uppercase">${c.tipo}</span>
            <span style="font-weight:600">${c.nombre}</span>
            <span class="tnum" style="color:var(--gris);overflow:hidden;text-overflow:ellipsis">${c.usuario}</span>
            <span class="tnum" style="font-weight:800;color:var(--azul);user-select:all">${c.password}</span>
          </div>`).join("")}
      </div>
      <div style="display:flex;gap:10px;margin-top:18px">
        <button id="am-copiar" class="btn btn-linea" style="flex:1;min-height:46px">Copiar todas</button>
        <button id="am-listo" class="btn btn-azul" style="flex:1;min-height:46px">Ya las anoté</button>
      </div>`;
    capa.querySelector("#am-copiar").onclick = () => {
      navigator.clipboard.writeText(texto).then(() => {
        capa.querySelector("#am-copiar").textContent = "Copiadas ✓";
      }).catch(() => { capa.querySelector("#am-copiar").textContent = "Selecciónelas y copie"; });
    };
    capa.querySelector("#am-listo").onclick = () => { capa.remove(); subAdmin(); };
  }


  /* ---------- SOLICITUDES DE FACTURA (las pide el cliente en su portal) ---------- */
  async function vistaFacturas(objetivo) {
    const filas = await (await api("/api/facturas")).json();
    const EST = { solicitada: ["Solicitada", "var(--azul)"],
      en_proceso: ["En proceso", "var(--ambar)"],
      emitida: ["Emitida", "var(--verde)"], rechazada: ["Rechazada", "var(--rojo)"] };
    const abiertas = filas.filter((f) => f.estatus === "solicitada" || f.estatus === "en_proceso");
    const resto = filas.filter((f) => !abiertas.includes(f));

    const tarjeta = (f) => `
      <div class="carta" style="padding:18px 20px" data-fx="${f.id}">
        <div style="display:flex;flex-wrap:wrap;gap:8px 16px;align-items:baseline">
          <p style="margin:0;font-size:14.5px;font-weight:800;color:var(--marino)">#${f.id} · ${f.cliente}</p>
          <span style="font-size:10.5px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:${(EST[f.estatus] || [])[1]}">${(EST[f.estatus] || [f.estatus])[0]}</span>
          ${f.atendida_por ? `<span style="font-size:11.5px;color:var(--gris2)">atiende ${f.atendida_por}</span>` : ""}
        </div>
        <p style="margin:8px 0 0;font-size:13px;color:var(--tinta)">
          Para <strong>${f.receptor_razon_social}</strong> · RFC <span class="tnum" style="font-weight:700">${f.receptor_rfc}</span>
          ${f.receptor_cp ? ` · CP ${f.receptor_cp}` : ""}${f.receptor_regimen ? ` · régimen ${f.receptor_regimen}` : ""}</p>
        <p style="margin:4px 0 0;font-size:12.5px;color:var(--gris)">
          ${f.concepto} · uso ${f.uso_cfdi} · forma ${f.forma_pago} · ${f.metodo_pago}
          ${f.monto ? ` · <span class="tnum" style="font-weight:800;color:var(--marino)">${dinero(f.monto)}</span>` : " · monto por definir"}</p>
        ${f.notas ? `<p style="margin:4px 0 0;font-size:12px;color:var(--gris2)">Nota del cliente: ${f.notas}</p>` : ""}
        ${f.motivo_rechazo ? `<p style="margin:4px 0 0;font-size:12px;color:var(--rojo)">Motivo: ${f.motivo_rechazo}</p>` : ""}
        ${f.estatus === "solicitada" || f.estatus === "en_proceso" ? `
          <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;align-items:center">
            ${f.estatus === "solicitada" ? `<button class="btn btn-linea fx-proceso" style="min-height:40px;font-size:12.5px">La tomo (en proceso)</button>` : ""}
            <label class="btn btn-azul" style="min-height:40px;font-size:12.5px;display:inline-flex;align-items:center;cursor:pointer">
              Subir factura timbrada (PDF)
              <input type="file" accept="application/pdf" class="fx-pdf" style="display:none"></label>
            <label style="font-size:12px;color:var(--gris2);cursor:pointer">+ XML (opcional)
              <input type="file" accept=".xml,text/xml,application/xml" class="fx-xml" style="display:none"></label>
            <span class="fx-xml-nombre" style="font-size:11.5px;color:var(--verde);font-weight:700"></span>
            <button class="btn btn-linea fx-rechazo" style="min-height:40px;font-size:12.5px;color:var(--rojo);border-color:var(--rojo-borde)">No procede…</button>
          </div>
          <div class="fx-zona-rechazo oculto" style="display:flex;gap:8px;margin-top:8px">
            <input class="campo fx-motivo" placeholder="Motivo (el cliente lo verá en su portal)" style="flex:1;padding:9px;font-size:12.5px">
            <button class="btn btn-azul fx-confirmar-rechazo" style="min-height:40px;font-size:12.5px;background:var(--rojo)">Rechazar</button>
          </div>` : ""}
        <p class="fx-msj oculto" style="margin:8px 0 0;font-size:12px;font-weight:700"></p>
      </div>`;

    objetivo.innerHTML = `
      <div style="animation:aparecer .3s ease">
      <p class="micro" style="margin:0 0 12px">Solicitudes de factura del portal — ${abiertas.length} por atender</p>
      <div style="display:flex;flex-direction:column;gap:12px">
        ${abiertas.map(tarjeta).join("") || `<div class="carta" style="padding:20px;font-size:13px;color:var(--gris2)">No hay solicitudes pendientes. Las que pidan los clientes en su portal aparecerán aquí.</div>`}
      </div>
      ${resto.length ? `<details style="margin-top:18px"><summary style="font-size:12.5px;font-weight:700;color:var(--azul);cursor:pointer">Atendidas recientemente (${resto.length})</summary>
        <div style="display:flex;flex-direction:column;gap:12px;margin-top:10px">${resto.map(tarjeta).join("")}</div></details>` : ""}
      </div>`;

    const recargar = () => vistaFacturas(objetivo);
    $$(".fx-proceso").forEach((b) => b.onclick = async () => {
      await api(`/api/facturas/${b.closest("[data-fx]").dataset.fx}/estatus`, { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ estatus: "en_proceso" }) });
      recargar();
    });
    $$(".fx-rechazo").forEach((b) => b.onclick = () =>
      b.closest("[data-fx]").querySelector(".fx-zona-rechazo").classList.toggle("oculto"));
    $$(".fx-confirmar-rechazo").forEach((b) => b.onclick = async () => {
      const caja = b.closest("[data-fx]");
      const msj = caja.querySelector(".fx-msj");
      const r = await api(`/api/facturas/${caja.dataset.fx}/estatus`, { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ estatus: "rechazada", motivo: caja.querySelector(".fx-motivo").value }) });
      if (!r.ok) { msj.textContent = (await r.json()).detail; msj.style.color = "var(--rojo)";
        msj.classList.remove("oculto"); return; }
      recargar();
    });
    $$(".fx-xml").forEach((inp) => inp.onchange = () => {
      inp.closest("[data-fx]").querySelector(".fx-xml-nombre").textContent =
        inp.files[0] ? `XML: ${inp.files[0].name} ✓` : "";
    });
    $$(".fx-pdf").forEach((inp) => inp.onchange = async () => {
      const caja = inp.closest("[data-fx]");
      const msj = caja.querySelector(".fx-msj");
      const fd = new FormData();
      fd.append("archivo_pdf", inp.files[0]);
      const xml = caja.querySelector(".fx-xml").files[0];
      if (xml) fd.append("archivo_xml", xml);
      const r = await api(`/api/facturas/${caja.dataset.fx}/emitida`, { method: "POST", body: fd });
      if (!r.ok) { msj.textContent = (await r.json()).detail; msj.style.color = "var(--rojo)";
        msj.classList.remove("oculto"); return; }
      msj.textContent = "Emitida: ya está en la bóveda del cliente y en su portal.";
      msj.style.color = "var(--verde)"; msj.classList.remove("oculto");
      setTimeout(recargar, 1200);
    });
  }


  /* =====================================================================
     EXPEDIENTE DEL CLIENTE — todo lo suyo en un solo lugar:
     su rastro documental completo, sus situaciones (el semáforo con
     criterio), sus adeudos, su estado de cuenta y su balance.
     ===================================================================== */
  async function vistaExpediente(clienteId, nombre, volverA) {
    const cont = $("#contenido");
    cont.innerHTML = `<div class="carta" style="padding:24px;font-size:13px;color:var(--gris2)">Abriendo el expediente…</div>`;
    const [exp, sits, adeudos, balances] = await Promise.all([
      (await api(`/api/clientes/${clienteId}/expediente`)).json(),
      (await api(`/api/situaciones?cliente_id=${clienteId}&abiertas=false`)).json(),
      (await api(`/api/clientes/${clienteId}/adeudos`)).json(),
      (await api(`/api/clientes/${clienteId}/estados-financieros`)).json(),
    ]);
    const SEV = { roja: ["roja", "var(--rojo)"], ambar: ["ambar", "var(--ambar)"],
                  informativa: ["", "var(--azul)"] };
    // El PUT de cliente es del Director/Administrador: si no, se ve pero no se edita
    const PUEDE_EDITAR_FICHA = ROL === "director" || ROL === "administrador";
    const saldoAdeudos = adeudos.filter((a) => !a.liquidado)
      .reduce((t, a) => t + a.saldo, 0);

    cont.innerHTML = `
      <div style="animation:aparecer .3s ease">
        <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:18px">
          <button id="volver-exp" class="btn btn-linea" style="min-height:40px">${ICO.atras(15)} Regresar</button>
          <h1 class="h1" style="margin:0;flex:1">${nombre}</h1>
          <button id="exp-estado-cuenta" class="chip">Estado de cuenta (PDF)</button>
        </div>

        <div style="display:flex;flex-wrap:wrap;gap:18px;align-items:flex-start">
          <div style="flex:1.1;min-width:min(100%,340px);display:flex;flex-direction:column;gap:16px">

            <!-- FICHA: cobranza y CONTPAQ, CORREGIBLES (no solo al dar de alta) -->
            <div class="carta" style="padding:20px">
              <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:baseline">
                <p style="margin:0;flex:1;font-size:15px;font-weight:800;color:var(--marino)">Cobranza y CONTPAQ</p>
                ${exp.ficha.honorario_mensual ? `<span class="tnum" style="font-size:15px;font-weight:800;color:var(--marino)">${dinero(exp.ficha.honorario_mensual)}</span>`
                  : `<span class="pildora ambar">sin honorario capturado</span>`}
              </div>
              <p class="micro" style="margin:6px 0 12px">${exp.ficha.razon_social} · ${exp.ficha.rfc}</p>
              ${PUEDE_EDITAR_FICHA ? `
              <div style="display:grid;grid-template-columns:1.2fr 1fr .7fr;gap:8px">
                <label class="etiqueta" style="margin:0">Honorario ($)
                  <input id="fx-honorario" class="campo" type="number" step="0.01" value="${exp.ficha.honorario_mensual ?? ""}" style="margin-top:3px;padding:9px;font-size:12.5px"></label>
                <label class="etiqueta" style="margin:0">Periodicidad
                  <select id="fx-per" class="campo" style="margin-top:3px;padding:9px;font-size:12.5px">
                    ${["mensual","bimestral","anual"].map((p) => `<option value="${p}" ${exp.ficha.periodicidad_honorario === p ? "selected" : ""}>${p}</option>`).join("")}
                  </select></label>
                <label class="etiqueta" style="margin:0">Día corte
                  <input id="fx-corte" class="campo" type="number" min="1" max="28" value="${exp.ficha.dia_corte_honorario || 1}" style="margin-top:3px;padding:9px;font-size:12.5px"></label>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px">
                <label class="etiqueta" style="margin:0">Base CONTPAQ contabilidad
                  <input id="fx-bd-conta" class="campo" value="${exp.ficha.bd_contpaq_contabilidad || ""}" placeholder="ctEJEMPLO" style="margin-top:3px;padding:9px;font-size:12.5px"></label>
                <label class="etiqueta" style="margin:0">Base CONTPAQ nóminas
                  <input id="fx-bd-nom" class="campo" value="${exp.ficha.bd_contpaq_nomina || ""}" placeholder="nomEJEMPLO" style="margin-top:3px;padding:9px;font-size:12.5px"></label>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px">
                <label class="etiqueta" style="margin:0">Base CONTPAQ ADD (XML)
                  <input id="fx-bd-add" class="campo" value="${exp.ficha.bd_contpaq_add || ""}" placeholder="adEJEMPLO" style="margin-top:3px;padding:9px;font-size:12.5px"></label>
                <label class="etiqueta" style="margin:0">Coeficiente de utilidad
                  <input id="fx-coef" class="campo" type="number" step="0.0001" value="${exp.ficha.coeficiente_utilidad ?? ""}" placeholder="0.10 (PM general)" style="margin-top:3px;padding:9px;font-size:12.5px"></label>
              </div>
              <label style="display:flex;align-items:center;gap:8px;margin-top:10px;font-size:12.5px;font-weight:600;cursor:pointer">
                <input type="checkbox" id="fx-boveda" ${exp.ficha.boveda_completa ? "checked" : ""} style="width:17px;height:17px;accent-color:var(--azul)">
                Dejarle ver TODO su expediente en el portal</label>
              <p style="margin:4px 0 0;font-size:11px;color:var(--gris2);line-height:1.5">Por defecto el cliente solo ve sus documentos útiles: constancias, formatos de pago, facturas y recibos. El papel de trabajo del despacho no se le muestra.</p>
              <button id="fx-guardar" class="btn btn-azul" style="margin-top:10px;min-height:42px;font-size:13px">Guardar cambios</button>
              <p id="fx-msj" class="oculto" style="margin:6px 0 0;font-size:12px;font-weight:700"></p>`
              : `<p style="margin:0;font-size:12.5px;color:var(--gris2)">Honorario ${dinero(exp.ficha.honorario_mensual)} · ${exp.ficha.periodicidad_honorario} · corte día ${exp.ficha.dia_corte_honorario}. Estos datos los edita el Director.</p>`}
            </div>

            <!-- COMPLEMENTARIAS: qué periodo se corrigió y cuál era el monto antes -->
            ${(exp.complementarias || []).length ? `
            <div class="carta" style="padding:20px;border-left:3px solid var(--ambar)">
              <p style="margin:0 0 4px;font-size:15px;font-weight:800;color:var(--marino)">Declaraciones complementarias</p>
              <p class="micro" style="margin:0 0 12px">Periodos corregidos · el expediente conserva todas las versiones</p>
              ${exp.complementarias.map((k) => `
              <div style="border:1px solid var(--borde);border-radius:10px;padding:12px 14px;margin-bottom:8px">
                <div style="display:flex;flex-wrap:wrap;gap:6px 12px;align-items:baseline">
                  <p style="margin:0;flex:1;font-size:13.5px;font-weight:700;color:var(--marino)">${String(k.mes).padStart(2,"0")}/${k.anio}</p>
                  <span class="pildora ambar">complementaria #${k.numero}</span>
                  ${k.vigente.presentada ? `<span class="tnum" style="font-size:13px;font-weight:800">${dinero(k.vigente.monto)}</span>`
                    : `<span class="pildora">por presentar</span>`}
                  ${k.vigente.pagada ? `<span class="pildora verde">pagada</span>` : ""}
                </div>
                <p style="margin:5px 0 0;font-size:12px;color:var(--gris)">Motivo: ${k.motivo || "—"}</p>
                ${k.versiones_anteriores.map((v) => `
                <p style="margin:4px 0 0;font-size:11.5px;color:var(--gris2)">
                  ↩ versión anterior${v.numero ? " #" + v.numero : " (original)"}: <span class="tnum">${dinero(v.monto)}</span>${v.pagada ? " · estaba pagada" : ""}${v.archivada_por ? " · archivó " + v.archivada_por : ""}</p>`).join("")}
              </div>`).join("")}
            </div>` : ""}

            <!-- SITUACIONES: el semáforo lo pone una persona -->
            <div class="carta" style="padding:20px">
              <p style="margin:0 0 4px;font-size:15px;font-weight:800;color:var(--marino)">Situaciones del cliente</p>
              <p class="micro" style="margin:0 0 12px">Requerimientos, auditorías y asuntos que el sistema no puede adivinar</p>
              <div style="display:flex;flex-direction:column;gap:8px">
                ${sits.map((x) => `
                <div class="carta" data-sit="${x.id}" style="padding:12px 14px;border-left:3px solid ${(SEV[x.severidad] || [])[1]};${x.abierta ? "" : "opacity:.5"}">
                  <div style="display:flex;flex-wrap:wrap;gap:6px 10px;align-items:baseline">
                    <p style="margin:0;flex:1;font-size:13.5px;font-weight:700;color:var(--marino)">${x.titulo}</p>
                    <span class="pildora ${(SEV[x.severidad] || [])[0]}">${x.severidad}</span>
                    ${x.visible_para_cliente ? `<span class="pildora">el cliente lo ve</span>`
                      : `<span style="font-size:11px;color:var(--gris2)">solo interno</span>`}
                  </div>
                  <p style="margin:4px 0 0;font-size:12px;color:var(--gris)">${x.tipo} · ${x.detalle_interno || "sin detalle"}</p>
                  ${x.mensaje_al_cliente ? `<p style="margin:4px 0 0;font-size:12px;color:var(--azul)">Al cliente: “${x.mensaje_al_cliente}”</p>` : ""}
                  ${x.abierta ? `
                  <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
                    <button class="chip sit-visible" data-s="${x.id}" data-on="${x.visible_para_cliente ? 1 : 0}">${x.visible_para_cliente ? "Ocultar al cliente" : "Mostrar al cliente"}</button>
                    <button class="chip sit-cerrar" data-s="${x.id}">Marcar resuelta</button>
                  </div>` : `<p style="margin:6px 0 0;font-size:11.5px;color:var(--gris2)">Resuelta${x.cerrada_por ? " por " + x.cerrada_por : ""}</p>`}
                  <p class="sit-msj oculto" style="margin:6px 0 0;font-size:11.5px;font-weight:700"></p>
                </div>`).join("") || `<p style="margin:0;font-size:12.5px;color:var(--gris2)">Sin situaciones registradas.</p>`}
              </div>
              <details style="margin-top:14px">
                <summary style="font-size:12.5px;font-weight:700;color:var(--azul);cursor:pointer">Registrar una situación</summary>
                <div style="display:flex;flex-direction:column;gap:8px;margin-top:10px">
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
                    <select id="sit-tipo" class="campo" style="padding:8px;font-size:12.5px">
                      <option value="requerimiento">Requerimiento del SAT</option>
                      <option value="auditoria">Auditoría / revisión</option>
                      <option value="discrepancia">Discrepancia fiscal</option>
                      <option value="aclaracion">Aclaración</option>
                      <option value="otro">Otro</option>
                    </select>
                    <select id="sit-sev" class="campo" style="padding:8px;font-size:12.5px">
                      <option value="ambar">Ámbar · atención</option>
                      <option value="roja">Roja · urgente</option>
                      <option value="informativa">Informativa</option>
                    </select>
                  </div>
                  <input id="sit-titulo" class="campo" placeholder="Título (ej. Requerimiento folio 12345)" style="padding:8px;font-size:12.5px">
                  <textarea id="sit-detalle" class="campo" rows="2" placeholder="Detalle interno (esto NO lo ve el cliente)" style="padding:8px;font-size:12.5px;resize:vertical"></textarea>
                  <textarea id="sit-mensaje" class="campo" rows="2" placeholder="Mensaje para el cliente, con sus palabras (opcional)" style="padding:8px;font-size:12.5px;resize:vertical"></textarea>
                  <label style="display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:600;cursor:pointer">
                    <input type="checkbox" id="sit-visible" style="width:17px;height:17px;accent-color:var(--azul)">
                    Mostrárselo al cliente en su portal</label>
                  <p style="margin:0;font-size:11px;color:var(--gris2);line-height:1.5">Los asuntos graves se avisan hablando, no con un foquito rojo. Encender el rojo del portal lo autoriza la Supervisora o el Director.</p>
                  <button id="sit-guardar" class="btn btn-azul" style="min-height:42px;font-size:13px">Registrar situación</button>
                  <p id="sit-alta-msj" class="oculto" style="margin:0;font-size:12px;font-weight:700"></p>
                </div>
              </details>
            </div>

            <!-- ADEUDOS -->
            <div class="carta" style="padding:20px">
              <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:baseline">
                <p style="margin:0;flex:1;font-size:15px;font-weight:800;color:var(--marino)">Adeudos anteriores</p>
                ${saldoAdeudos ? `<span class="tnum" style="font-size:15px;font-weight:800;color:var(--rojo)">${dinero(saldoAdeudos)}</span>` : `<span class="pildora verde">sin adeudos</span>`}
              </div>
              <div style="display:flex;flex-direction:column;gap:6px;margin-top:10px">
                ${adeudos.map((a) => `
                <div class="fila" data-ad="${a.id}" style="padding:9px 0;gap:10px;flex-wrap:wrap">
                  <span style="flex:1;min-width:150px;font-size:12.5px;${a.liquidado ? "text-decoration:line-through;opacity:.6" : ""}">${a.concepto}</span>
                  <span class="tnum" style="font-size:12.5px;font-weight:700">${dinero(a.saldo)}</span>
                  ${a.liquidado ? `<span class="pildora verde">liquidado</span>`
                    : `<button class="chip ad-abonar" data-a="${a.id}" data-s="${a.saldo}">Abonar</button>`}
                </div>`).join("") || `<p style="margin:0;font-size:12.5px;color:var(--gris2)">Sin adeudos anteriores registrados.</p>`}
              </div>
              <details style="margin-top:12px">
                <summary style="font-size:12.5px;font-weight:700;color:var(--azul);cursor:pointer">Registrar un adeudo</summary>
                <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">
                  <input id="ad-concepto" class="campo" placeholder="Concepto" style="flex:2;min-width:160px;padding:8px;font-size:12.5px">
                  <input id="ad-monto" class="campo" type="number" step="0.01" placeholder="Monto" style="flex:1;min-width:110px;padding:8px;font-size:12.5px">
                  <button id="ad-guardar" class="btn btn-azul" style="min-height:40px;font-size:12.5px">Agregar</button>
                </div>
              </details>
            </div>

            <!-- BALANCE -->
            <div class="carta" style="padding:20px">
              <p style="margin:0 0 4px;font-size:15px;font-weight:800;color:var(--marino)">Estados financieros</p>
              <p class="micro" style="margin:0 0 12px">Solo si existe uno, el cliente ve su resumen en el portal</p>
              ${balances.map((b) => `
              <div class="fila" style="padding:9px 0;gap:10px;flex-wrap:wrap">
                <span style="flex:1;min-width:110px;font-size:12.5px;font-weight:700">${b.periodo}</span>
                <span class="tnum" style="font-size:12px;color:var(--gris)">A ${dinero(b.activo_total)} · P ${dinero(b.pasivo_total)} · C ${dinero(b.capital_total)}</span>
                ${b.visible_para_cliente ? `<span class="pildora verde">visible</span>` : `<span class="pildora">interno</span>`}
              </div>`).join("") || `<p style="margin:0;font-size:12.5px;color:var(--gris2)">Sin estados financieros capturados.</p>`}
              <details style="margin-top:12px">
                <summary style="font-size:12.5px;font-weight:700;color:var(--azul);cursor:pointer">Capturar un balance</summary>
                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px;margin-top:10px">
                  <input id="ef-anio" class="campo" type="number" value="${ANIO}" placeholder="Año" style="padding:8px;font-size:12.5px">
                  <input id="ef-mes" class="campo" type="number" min="1" max="12" placeholder="Mes (vacío = anual)" style="padding:8px;font-size:12.5px">
                  <input id="ef-activo" class="campo" type="number" step="0.01" placeholder="Activo" style="padding:8px;font-size:12.5px">
                  <input id="ef-pasivo" class="campo" type="number" step="0.01" placeholder="Pasivo" style="padding:8px;font-size:12.5px">
                  <input id="ef-capital" class="campo" type="number" step="0.01" placeholder="Capital" style="padding:8px;font-size:12.5px">
                </div>
                <p style="margin:6px 0 0;font-size:11px;color:var(--gris2)">El activo debe ser igual a pasivo + capital.</p>
                <button id="ef-guardar" class="btn btn-azul" style="margin-top:8px;min-height:40px;font-size:12.5px">Guardar balance</button>
                <p id="ef-msj" class="oculto" style="margin:6px 0 0;font-size:12px;font-weight:700"></p>
              </details>
            </div>
          </div>

          <!-- RASTRO DOCUMENTAL COMPLETO -->
          <div style="flex:1;min-width:min(100%,320px)">
            <div class="carta" style="padding:20px">
              <p style="margin:0 0 4px;font-size:15px;font-weight:800;color:var(--marino)">Expediente documental</p>
              <p class="micro" style="margin:0 0 12px">${exp.total_documentos} documento(s) · todo lo que el despacho guarda de este cliente</p>
              ${exp.ejercicios.map((e) => `
              <details ${e.anio === ANIO ? "open" : ""} style="margin-bottom:8px">
                <summary style="font-size:13px;font-weight:800;color:var(--marino);cursor:pointer;padding:6px 0">Ejercicio ${e.anio} · ${e.documentos.length}</summary>
                ${e.documentos.map((d) => `
                <div class="fila" style="padding:8px 0;gap:10px;flex-wrap:wrap">
                  <span style="flex:1;min-width:150px;font-size:12.5px">${d.nombre}
                    ${d.mes ? `<span style="color:var(--gris2)"> · ${String(d.mes).padStart(2,"0")}/${d.anio}</span>` : ""}</span>
                  ${d.para_el_cliente ? `<span class="pildora verde">lo ve el cliente</span>` : `<span style="font-size:10.5px;color:var(--gris2)">interno</span>`}
                  <button class="chip exp-ver" data-doc="${d.id}">ver</button>
                  <button class="chip exp-bajar" data-doc="${d.id}" data-n="${d.nombre}">bajar</button>
                </div>`).join("")}
              </details>`).join("") || `<p style="margin:0;font-size:12.5px;color:var(--gris2)">Este cliente aún no tiene documentos.</p>`}
              <div id="exp-visor" style="margin-top:12px"></div>
            </div>
          </div>
        </div>
      </div>`;

    const recargar = () => vistaExpediente(clienteId, nombre, volverA);
    $("#volver-exp").onclick = () => (volverA ? volverA() : panelPrincipal());
    $("#exp-estado-cuenta").onclick = () =>
      descargarConSesion(`/api/clientes/${clienteId}/estado-cuenta?anio=${ANIO}`);
    $$(".exp-ver").forEach((b) => b.onclick = () => visorPDF($("#exp-visor"), b.dataset.doc));
    // Descarga directa: el contador se lleva el archivo, no solo lo mira
    $$(".exp-bajar").forEach((b) => b.onclick = async () => {
      await descargarConSesion(`/api/obligaciones/boveda/${b.dataset.doc}/descargar`,
        `${b.dataset.n}.pdf`.replace(/\s+/g, "_"));
    });

    if (PUEDE_EDITAR_FICHA) $("#fx-guardar").onclick = async () => {
      const msj = $("#fx-msj");
      const num = (id) => ($(id).value === "" ? null : +$(id).value);
      const r = await api(`/api/admin/clientes/${clienteId}`, { method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          honorario_mensual: num("#fx-honorario"),
          periodicidad_honorario: $("#fx-per").value,
          dia_corte_honorario: num("#fx-corte") || 1,
          bd_contpaq_contabilidad: $("#fx-bd-conta").value || null,
          bd_contpaq_nomina: $("#fx-bd-nom").value || null,
          bd_contpaq_add: $("#fx-bd-add").value || null,
          coeficiente_utilidad: num("#fx-coef"),
          boveda_completa: $("#fx-boveda").checked }) });
      const j = await r.json().catch(() => ({}));
      msj.classList.remove("oculto");
      if (!r.ok) { msj.style.color = "var(--rojo)";
        msj.textContent = j.detail || "No se pudo guardar."; return; }
      msj.style.color = "var(--verde)";
      msj.textContent = "Datos guardados.";
      setTimeout(recargar, 900);
    };

    $("#sit-guardar").onclick = async () => {
      const msj = $("#sit-alta-msj");
      const r = await api("/api/situaciones", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cliente_id: clienteId, tipo: $("#sit-tipo").value,
          severidad: $("#sit-sev").value, titulo: $("#sit-titulo").value,
          detalle_interno: $("#sit-detalle").value || null,
          mensaje_al_cliente: $("#sit-mensaje").value || null,
          visible_para_cliente: $("#sit-visible").checked }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) { msj.classList.remove("oculto"); msj.style.color = "var(--rojo)";
        msj.textContent = j.detail || "No se pudo registrar."; return; }
      if (j.aviso) { msj.classList.remove("oculto"); msj.style.color = "var(--ambar)";
        msj.textContent = j.aviso; setTimeout(recargar, 2600); return; }
      recargar();
    };
    $$(".sit-visible").forEach((b) => b.onclick = async () => {
      const caja = b.closest("[data-sit]");
      const r = await api(`/api/situaciones/${b.dataset.s}/visibilidad`, { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visible_para_cliente: b.dataset.on !== "1" }) });
      if (r.ok) return recargar();
      const j = await r.json().catch(() => ({}));
      const m = caja.querySelector(".sit-msj");
      m.classList.remove("oculto"); m.style.color = "var(--rojo)";
      m.textContent = j.detail || "No se pudo cambiar.";
    });
    $$(".sit-cerrar").forEach((b) => b.onclick = async () => {
      await api(`/api/situaciones/${b.dataset.s}/cerrar`, { method: "POST" });
      recargar();
    });
    $("#ad-guardar").onclick = async () => {
      const r = await api(`/api/clientes/${clienteId}/adeudos`, { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ concepto: $("#ad-concepto").value,
                               monto: +$("#ad-monto").value }) });
      if (r.ok) recargar();
    };
    $$(".ad-abonar").forEach((b) => b.onclick = async () => {
      const monto = prompt(`¿De cuánto es el abono? (saldo: ${b.dataset.s})`);
      if (!monto) return;
      const r = await api(`/api/adeudos/${b.dataset.a}/abono`, { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ monto: +monto }) });
      if (r.ok) recargar();
    });
    $("#ef-guardar").onclick = async () => {
      const msj = $("#ef-msj");
      const r = await api(`/api/clientes/${clienteId}/estado-financiero`, { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ anio: +$("#ef-anio").value,
          mes: $("#ef-mes").value ? +$("#ef-mes").value : null,
          activo_total: +$("#ef-activo").value, pasivo_total: +$("#ef-pasivo").value,
          capital_total: +$("#ef-capital").value }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) { msj.classList.remove("oculto"); msj.style.color = "var(--rojo)";
        msj.textContent = j.detail || "No se pudo guardar."; return; }
      recargar();
    };
  }

  if (token && ROL) arrancar();
})();
