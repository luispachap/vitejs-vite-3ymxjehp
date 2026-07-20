/* Pacheco & Aparicio · Portal de clientes — conectado a la API FastAPI.
   Servir desde /static/clientes/app.js (CSP: script-src 'self'). */
(function () {
  "use strict";

  // Nodo fantasma: absorbe escrituras a elementos que ya no están (el cliente
  // navegó mientras cargaba), en vez de tronar con "null".
  var NODO_FANTASMA = new Proxy({ _fantasma: true }, {
    get: function (_, k) {
      if (k === "classList") return { add: function () {}, remove: function () {},
        toggle: function () {}, contains: function () { return false; } };
      if (k === "style" || k === "dataset") return {};
      if (k === "files") return [];
      if (k === "value" || k === "textContent" || k === "innerHTML") return "";
      if (k === "checked") return false;
      if (k === "querySelectorAll") return function () { return []; };
      if (k === "querySelector" || k === "closest") return function () { return NODO_FANTASMA; };
      return typeof k === "string" ? function () {} : undefined;
    },
    set: function () { return true; },
  });
  var $ = function (s) { return document.querySelector(s) || NODO_FANTASMA; };
  // ⚠ FALTABA: cinco funciones del portal usaban $$ y nunca se definió, así
  // que tronaban EN SILENCIO (dentro de promesas): los pagos de IMSS/ISN, la
  // descarga rápida, los certificados y los horarios de citas.
  var $$ = function (s) { return [].slice.call(document.querySelectorAll(s)); };
  var token = sessionStorage.getItem("pya_token") || null;
  var hoy = new Date();
  var MES = hoy.getMonth() + 1;
  var ANIO = hoy.getFullYear();
  var NOMBRE_MES = hoy.toLocaleDateString("es-MX", { month: "long", year: "numeric" });
  var dinero = function (n) {
    return n == null ? "—" : Number(n).toLocaleString("es-MX",
      { style: "currency", currency: "MXN", maximumFractionDigits: 0 });
  };

  var COLORES = { verde: "#167A46", amarillo: "#96690A", rojo: "#B4362A" };
  var TEXTO_ANILLO = {
    verde: "OPINIÓN 32D POSITIVA · AL CORRIENTE ANTE EL SAT · ",
    amarillo: "LÍNEA DE CAPTURA VIGENTE · PENDIENTE DE PAGO AL SAT · ",
    rojo: "REQUERIMIENTO EN ATENCIÓN · SU CONTADOR YA LO ATIENDE · "
  };
  var SUB_SEMAFORO = {
    verde: "Opinión de cumplimiento 32D positiva. No necesita hacer nada.",
    amarillo: "Descárguela en Sus pagos del mes, aquí abajo, y páguela antes del vencimiento.",
    rojo: "No necesita hacer nada por ahora: le avisaremos en cuanto quede resuelto."
  };

  /* Aviso de fallo visible: si algo no se pudo hacer, el cliente se entera
     (antes la app simplemente no respondía). Discreto y en su idioma. */
  function avisarFallo(texto) {
    var caja = document.getElementById("aviso-fallo");
    if (!caja) {
      caja = document.createElement("div");
      caja.id = "aviso-fallo";
      caja.style.cssText = "position:fixed;left:50%;bottom:26px;transform:translateX(-50%);" +
        "background:#B4362A;color:#fff;font-size:13px;font-weight:600;padding:12px 20px;" +
        "border-radius:12px;box-shadow:0 12px 30px -10px rgba(0,0,0,.45);z-index:99;" +
        "margin:0;max-width:88vw;text-align:center";
      document.body.appendChild(caja);
    }
    caja.textContent = texto;
    caja.style.display = "block";
    clearTimeout(caja._t);
    caja._t = setTimeout(function () { caja.style.display = "none"; }, 6000);
  }
  window.addEventListener("unhandledrejection", function (e) {
    var m = (e.reason && e.reason.message) || "";
    if (m && m.indexOf("sesión") === -1) avisarFallo("Algo no se pudo completar: " + m);
  });

  function api(ruta, opciones) {
    opciones = opciones || {};
    var headers = Object.assign({}, opciones.headers || {},
      token ? { Authorization: "Bearer " + token } : {});
    return fetch(ruta, Object.assign({}, opciones, { headers: headers }))
      .then(function (r) {
        if (r.status === 401) { salir(); throw new Error("sesión expirada"); }
        if (!r.ok) {
          r.clone().json().then(function (j) {
            if (j && j.detail) avisarFallo(typeof j.detail === "string" ? j.detail : "No se pudo completar la acción.");
          }).catch(function () { avisarFallo("No se pudo completar la acción (error " + r.status + ")."); });
        }
        return r;
      }, function (e) { avisarFallo("Sin conexión con el servidor."); throw e; });
  }

  function salir() {
    sessionStorage.removeItem("pya_token");
    token = null;
    $("#vista-portal").classList.add("oculto");
    $("#vista-login").classList.remove("oculto");
  }
  $("#btn-salir").addEventListener("click", salir);

  /* ---------- Login ---------- */
  $("#form-login").addEventListener("submit", function (e) {
    e.preventDefault();
    var err = $("#login-error");
    err.classList.add("oculto");
    fetch("/api/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: $("#email").value, password: $("#password").value })
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) {
          err.textContent = res.j.detail === "totp_requerido"
            ? "Esta cuenta requiere su código de autenticador."
            : "Correo o contraseña incorrectos. Verifique e intente de nuevo.";
          err.classList.remove("oculto");
          return;
        }
        if (res.j.rol !== "cliente") {
          err.textContent = "Esta es la entrada de clientes. El equipo entra por su propio acceso.";
          err.classList.remove("oculto");
          return;
        }
        token = res.j.access_token;
        sessionStorage.setItem("pya_token", token);
        if (res.j.debe_cambiar_password) {
          // Entró con la temporal que le dio el despacho: la cambia ahora
          window.__passTemporal = $("#password").value;
          pedirCambioPassword();
          return;
        }
        cargarPortal();
      })
      .catch(function () {
        err.textContent = "No se pudo conectar con el despacho. Intente de nuevo.";
        err.classList.remove("oculto");
      });
  });

  /* ---------- Sello del semáforo ---------- */
  function dibujarSello(estado) {
    var color = COLORES[estado] || "#0A5AA1";
    var texto = TEXTO_ANILLO[estado] || "";
    $("#sello").innerHTML =
      '<svg viewBox="0 0 220 220" role="img" aria-label="Sello de estatus fiscal" style="width:100%;height:100%">' +
      '<circle cx="110" cy="110" r="106" fill="none" stroke="' + color + '" stroke-width="2.5"/>' +
      '<circle cx="110" cy="110" r="72" fill="none" stroke="' + color + '" stroke-width="1.4"/>' +
      '<g class="anillo"><path id="curva" d="M110,110 m-89,0 a89,89 0 1,1 178,0 a89,89 0 1,1 -178,0" fill="none"/>' +
      '<text style="font-family:\'Public Sans\',sans-serif;font-weight:600;font-size:10.5px;letter-spacing:3.4px" fill="' + color + '">' +
      '<textPath href="#curva">' + texto + '</textPath></text></g>' +
      '<image href="/static/marca/monograma.png" x="59" y="59" width="102" height="102" preserveAspectRatio="xMidYMid meet"/></svg>';
  }

  /* ---------- Dona de impuestos (CSS conic-gradient, sin dependencias) ---------- */
  function dibujarDona(desglose) {
    var etiquetas = { iva: "IVA", isr: "ISR", retenciones: "Retenciones",
      isn: "Imp. sobre nómina (ISN)", cuotas_imss: "Cuotas IMSS",
      infonavit: "INFONAVIT" };
    var paleta = ["#0A1C33", "#0A5AA1", "#8FB4D9", "#C9D8EA", "#5C6879"];
    var entradas = Object.keys(desglose).map(function (k) { return [k, Number(desglose[k]) || 0]; })
      .filter(function (par) { return par[1] > 0; })
      .sort(function (a, b) { return b[1] - a[1]; });
    var total = entradas.reduce(function (s, par) { return s + par[1]; }, 0);
    if (!total) { $("#sin-desglose").classList.remove("oculto"); return; }

    var acumulado = 0;
    var paradas = entradas.map(function (par, i) {
      var inicio = acumulado / total * 100;
      acumulado += par[1];
      var fin = acumulado / total * 100;
      return paleta[i % paleta.length] + " " + inicio + "% " + fin + "%";
    });
    $("#dona").style.background = "conic-gradient(" + paradas.join(", ") + ")";
    $("#dona-total").textContent = dinero(total);
    $("#leyenda").innerHTML = entradas.map(function (par, i) {
      return '<li style="display:flex;align-items:center;gap:11px">' +
        '<span style="width:11px;height:11px;border-radius:50%;background:' + paleta[i % paleta.length] + ';flex:none"></span>' +
        '<span style="font-size:14px;color:#43506B;flex:1">' + (etiquetas[par[0]] || par[0].toUpperCase()) + "</span>" +
        '<span class="tnum" style="font-size:14px;font-weight:700;color:#0A1C33">' + dinero(par[1]) + "</span></li>";
    }).join("");
  }

  /* ---------- Cambio obligatorio de la contraseña temporal ---------- */
  function pedirCambioPassword() {
    $("#form-login").classList.add("oculto");
    $("#form-cambio").classList.remove("oculto");
    $("#cp-nueva").focus();
  }
  $("#btn-cambiar").addEventListener("click", function () {
    var msj = $("#cp-msj");
    var nueva = $("#cp-nueva").value, nueva2 = $("#cp-nueva2").value;
    if (nueva.length < 10) {
      msj.textContent = "Debe tener al menos 10 caracteres.";
      msj.style.color = "var(--rojo)"; msj.classList.remove("oculto"); return;
    }
    if (nueva !== nueva2) {
      msj.textContent = "Las contraseñas no coinciden.";
      msj.style.color = "var(--rojo)"; msj.classList.remove("oculto"); return;
    }
    var b = $("#btn-cambiar");
    b.disabled = true; b.textContent = "Guardando…";
    api("/api/auth/cambiar-password", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password_actual: window.__passTemporal, password_nueva: nueva })
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        b.disabled = false; b.textContent = "Guardar y entrar";
        if (!res.ok) {
          msj.textContent = res.j.detail || "No se pudo cambiar.";
          msj.style.color = "var(--rojo)"; msj.classList.remove("oculto"); return;
        }
        window.__passTemporal = null;
        $("#form-cambio").classList.add("oculto");
        cargarPortal();
      });
  });

  /* ---------- Descargas (blob local o URL firmada S3) ---------- */
  function descargar(ruta, aviso) {
    api(ruta).then(function (r) {
      if (!r.ok) {
        mostrarAviso("Aún no hay documento para este periodo.");
        return;
      }
      var tipo = r.headers.get("content-type") || "";
      if (tipo.indexOf("application/json") !== -1) {
        r.blob().then(function (b) {
          var url = URL.createObjectURL(b);
          window.open(url, "_blank");
        });
        if (aviso) mostrarAviso(aviso);
        return;
      }
      r.blob().then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url; a.download = "";
        document.body.appendChild(a); a.click(); a.remove();
        URL.revokeObjectURL(url);
        if (aviso) mostrarAviso(aviso);
      });
    });
  }
  // La Zona Express desapareció: sus dos botones viven ahora donde corresponde
  // (el formato de pago en "Sus pagos del mes"; el estado de cuenta en
  // "Descarga rápida"). El aviso de descarga ahora es flotante, discreto,
  // y se va solo.
  function mostrarAviso(texto) {
    var el = document.getElementById("aviso-flotante");
    if (!el) {
      el = document.createElement("p");
      el.id = "aviso-flotante";
      el.style.cssText = "position:fixed;left:50%;bottom:26px;transform:translateX(-50%);" +
        "background:var(--marino);color:#fff;font-size:13px;font-weight:600;" +
        "padding:12px 20px;border-radius:99px;box-shadow:0 12px 30px -10px rgba(10,28,51,.5);" +
        "z-index:99;margin:0;max-width:88vw;text-align:center;animation:aparecer .25s ease";
      document.body.appendChild(el);
    }
    el.textContent = texto;
    el.style.display = "block";
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.style.display = "none"; }, 4200);
  }

  /* ---------- Bóveda ---------- */
  var NOMBRES_DOC = {
    factura_emitida: "Factura emitida",
    acta_constitutiva: "Acta Constitutiva",
    opinion_32d: "Opinión de cumplimiento 32D",
    estado_financiero_dictaminado: "Estado financiero dictaminado",
    acuse_sat: "Acuse de pago SAT",
    constancia_situacion_fiscal: "Constancia de Situación Fiscal",
    balanza_comprobacion: "Balanza de comprobación",
    cedula_isn: "Impuesto sobre nómina (cédula ISN)",
    propuesta_sipare: "Cuotas patronales IMSS (SIPARE)",
    aviso_infonavit: "Aportaciones INFONAVIT"
  };
  var MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  var ICO_DESCARGA = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/></svg>';
  var ICO_CARPETA = '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#0A5AA1" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>';

  function pintarBoveda(b) {
    var anios = Object.keys(b).sort(function (a, z) { return z - a; });
    if (!anios.length) { $("#boveda-vacia").classList.remove("oculto"); return; }
    $("#boveda").innerHTML = anios.map(function (anio, idx) {
      var docs = b[anio].map(function (d) {
        var fecha = d.mes ? (MESES[d.mes].charAt(0).toUpperCase() + MESES[d.mes].slice(1)) :
          (d.subido_en ? new Date(d.subido_en).toLocaleDateString("es-MX", { month: "long", year: "numeric" }) : "");
        return '<div class="fila-doc">' +
          '<div style="min-width:0"><p style="margin:0;font-size:14px;font-weight:600;color:#111826">' +
          (NOMBRES_DOC[d.categoria] || d.categoria) + "</p>" +
          '<p style="margin:2px 0 0;font-size:12px;color:#8A93A6">' + fecha + " · PDF</p></div>" +
          '<button class="btn-descarga" data-doc="' + d.id + '">' + ICO_DESCARGA + "Descargar</button></div>";
      }).join("");
      return '<details class="carta" style="overflow:hidden" ' + (idx === 0 ? "open" : "") + ">" +
        '<summary style="display:flex;align-items:center;gap:12px;padding:18px 20px;cursor:pointer;user-select:none;list-style:none">' +
        ICO_CARPETA +
        '<span class="serif" style="font-weight:700;font-size:17.5px;color:#0A1C33">Ejercicio ' + anio + "</span>" +
        '<span style="margin-left:auto;font-size:12px;color:#8A93A6">' + b[anio].length +
        " documento" + (b[anio].length === 1 ? "" : "s") + "</span></summary>" +
        '<div style="border-top:1px solid #E4E7ED">' + docs + "</div></details>";
    }).join("");
    Array.prototype.forEach.call(document.querySelectorAll(".btn-descarga[data-doc]"), function (btn) {
      btn.addEventListener("click", function () {
        descargar("/api/portal/boveda/" + btn.getAttribute("data-doc") + "/descargar",
          "Documento descargado desde la bóveda.");
      });
    });
  }

  /* ---------- Pagos del mes y descargas frecuentes ---------- */
  function pintarPagos(d) {
    var pagos = d.pagos_del_mes || [];
    // La tarjeta del SAT es fija (monto + dona); aquí solo se le ponen su
    // vencimiento y su botón de descarga cuando la declaración ya está.
    var sat = null, otros = [];
    pagos.forEach(function (p) {
      if (!sat && /SAT|federal/i.test(p.concepto || "")) sat = p; else otros.push(p);
    });
    if (sat) {
      if (sat.vence) {
        $("#sat-vence").textContent = "Vence el " + sat.vence;
        $("#sat-vence").classList.remove("oculto");
      }
      if (sat.descarga) {
        var b = $("#btn-pago-sat");
        b.classList.remove("oculto");
        b.onclick = function () { descargar(sat.descarga, "Descargando su formato de pago…"); };
      }
      // ¿Ya lo pagó? Su comprobante evita que le sigan recordando un pago hecho.
      if (sat.obligacion_id) {
        OBLIGACION_SAT = sat.obligacion_id;
        $("#sat-comprobante").classList.remove("oculto");
        if (sat.pagado) {
          $("#sat-pagado").textContent = "Pago registrado" +
            (sat.referencia_pago ? " · referencia " + sat.referencia_pago : "") +
            ". Gracias: ya no le recordaremos este pago.";
          $("#sat-pagado").classList.remove("oculto");
          $("#sat-subir-zona").classList.add("oculto");
        }
        if (sat.es_complementaria) {
          $("#sat-vence").textContent = "Declaración complementaria #" +
            sat.numero_complementaria + (sat.vence ? " · vence el " + sat.vence : "");
          $("#sat-vence").classList.remove("oculto");
        }
      }
    }
    // IMSS, ISN y lo demás: tarjeta cada uno, con su desglose desplegable.
    $("#lista-pagos").innerHTML = otros.map(function (p) {
      var det = p.desglose ? Object.keys(p.desglose).map(function (k) {
        return '<div style="display:flex;justify-content:space-between;gap:10px;font-size:12.5px;padding:4px 0;border-bottom:1px solid var(--borde);color:var(--gris)">' +
          "<span>" + k.replace(/_/g, " ") + '</span><span class="tnum" style="font-weight:600">' + dinero(p.desglose[k]) + "</span></div>";
      }).join("") : "";
      return '<div style="background:var(--tarjeta);border:1px solid var(--borde);border-radius:16px;padding:clamp(18px,3vw,24px);display:flex;flex-wrap:wrap;gap:8px 26px;align-items:center">' +
        '<div style="flex:1;min-width:min(100%,220px)">' +
        '<p class="micro" style="margin:0">' + p.concepto + "</p>" +
        '<p class="serif tnum" style="margin:8px 0 0;font-weight:700;font-size:clamp(26px,4vw,34px);color:var(--marino)">' + dinero(p.monto) + "</p>" +
        (p.vence ? '<p style="margin:8px 0 0;font-size:12.5px;font-weight:700;color:var(--ambar)">Vence el ' + p.vence + "</p>" : "") +
        (det ? '<details style="margin:10px 0 0"><summary style="font-size:12px;font-weight:700;color:var(--azul);cursor:pointer">Ver desglose</summary><div style="margin-top:6px">' + det + "</div></details>" : "") +
        "</div>" +
        '<button class="btn btn-azul btn-pago" data-ruta="' + p.descarga + '" style="min-height:48px;font-size:13.5px">Descargar formato de pago</button></div>';
    }).join("");
    $$(".btn-pago").forEach(function (b) {
      b.addEventListener("click", function () { descargar(b.dataset.ruta, "Descargando su formato de pago…"); });
    });
    var f = d.descargas_frecuentes || {};
    var chips = [];
    if (f.constancia_situacion_fiscal)
      chips.push({ etq: "Constancia de situación fiscal", sub: f.constancia_situacion_fiscal.periodo,
                   ruta: "/api/portal/boveda/" + f.constancia_situacion_fiscal.documento_id + "/descargar" });
    if (f.opinion_32d)
      chips.push({ etq: "Opinión de cumplimiento (32D)", sub: f.opinion_32d.periodo,
                   ruta: "/api/portal/boveda/" + f.opinion_32d.documento_id + "/descargar" });
    if (f.estado_cuenta_honorarios)
      chips.push({ etq: "Estado de cuenta de honorarios", sub: "este mes", ruta: f.estado_cuenta_honorarios });
    $("#lista-frecuentes").innerHTML = chips.length ? chips.map(function (c) {
      return '<button class="btn-frec" data-ruta="' + c.ruta + '" style="display:flex;flex-direction:column;align-items:flex-start;gap:3px;background:var(--tarjeta);border:1px solid var(--borde);border-radius:14px;padding:16px 20px;cursor:pointer;text-align:left;min-width:200px">' +
        '<span style="font-size:14px;font-weight:700;color:var(--marino)">' + c.etq + "</span>" +
        '<span style="font-size:12px;color:var(--gris2)">' + c.sub + " · descargar</span></button>";
    }).join("") : '<p style="margin:0;font-size:13.5px;color:var(--gris2)">Su despacho aún no ha cargado estos documentos. Puede solicitarlos en el buzón.</p>';
    $$(".btn-frec").forEach(function (b) {
      b.addEventListener("click", function () { descargar(b.dataset.ruta, "Preparando su documento…"); });
    });
  }

  /* ---------- Certificados y firmas (bóveda blindada) ---------- */
  function cargarCertificados() {
    api("/api/certificados/mios").then(function (r) { return r.json(); }).then(function (certs) {
      if (!certs.length) return;
      $("#seccion-certificados").classList.remove("oculto");
      var colores = { vigente: "#167A46", por_vencer: "#96690A", vencido: "#BE3A2B" };
      $("#lista-certificados").innerHTML = certs.map(function (c) {
        return '<div style="background:var(--tarjeta);border:1px solid var(--borde);border-radius:12px;padding:16px 18px;display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center" data-cert="' + c.id + '">' +
          '<div style="flex:1;min-width:180px"><p style="margin:0;font-size:14.5px;font-weight:700;color:var(--marino)">' + c.descripcion + "</p>" +
          '<p style="margin:3px 0 0;font-size:12px;color:var(--gris)">' + c.tipo_nombre + " · vence " + c.fecha_vencimiento + "</p></div>" +
          '<span class="pildora ' + ({vigente:"verde",por_vencer:"ambar",vencido:"roja"}[c.estatus] || "") + '">' + c.estatus.replace("_", " ") + "</span>" +
          '<input type="password" placeholder="Su contraseña" class="campo cert-pass" style="width:150px;padding:8px 10px;font-size:12.5px">' +
          '<button class="btn btn-azul cert-bajar" style="min-height:40px;font-size:12.5px">Descargar</button></div>';
      }).join("");
      $$(".cert-bajar").forEach(function (b) {
        b.addEventListener("click", function () {
          var caja = b.closest("[data-cert]");
          var pass = caja.querySelector(".cert-pass").value;
          if (!pass) { caja.querySelector(".cert-pass").focus(); return; }
          var fd = new FormData(); fd.append("password", pass);
          b.textContent = "…";
          api("/api/certificados/mios/" + caja.dataset.cert + "/descargar", { method: "POST", body: fd })
            .then(function (r) {
              b.textContent = "Descargar";
              if (!r.ok) { b.textContent = "Contraseña incorrecta"; setTimeout(function () { b.textContent = "Descargar"; }, 2000); return null; }
              var tipo = r.headers.get("content-type") || "";
              if (tipo.indexOf("application/json") >= 0) {
                return r.blob().then(function (b) {
                  window.open(URL.createObjectURL(b), "_blank");
                });
              }
              return r.blob().then(function (blob) {
                var url = URL.createObjectURL(blob);
                var a = document.createElement("a"); a.href = url; a.download = "certificado";
                document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
              });
            });
        });
      });
    });
  }

  /* ---------- Agenda de asesorías ---------- */
  function cargarCitas() {
    api("/api/citas/opciones").then(function (r) { return r.json(); }).then(function (ops) {
      $("#cita-con").innerHTML = ops.map(function (o) {
        return '<option value="' + o.usuario_id + '">' + o.nombre + " — " + o.etiqueta + "</option>";
      }).join("");
    });
    api("/api/citas/mis-citas").then(function (r) { return r.json(); }).then(function (cs) {
      $("#mis-citas-lista").innerHTML = cs.map(function (c) {
        var f = new Date(c.fecha_hora);
        var pend = c.estatus === "solicitada";
        return '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px;background:var(--tarjeta);border:1px solid var(--borde);border-radius:12px;padding:14px 18px">' +
          '<span class="tnum" style="font-size:14px;font-weight:700;color:var(--marino)">' +
          f.toLocaleDateString("es-MX", { day: "2-digit", month: "long" }) + " · " +
          f.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" }) + "</span>" +
          '<span style="font-size:14px;color:#43506B;flex:1;min-width:140px">con ' + c.con + "</span>" +
          '<span style="font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:' +
          (pend ? "#96690A" : "#167A46") + '">' + (pend ? "por confirmar" : "confirmada") + "</span></div>";
      }).join("");
    });
  }
  /* Horarios libres reales de la persona elegida ese día */
  var horaElegida = null;
  function cargarDisponibilidad() {
    var dia = $("#cita-dia").value, con = $("#cita-con").value;
    horaElegida = null;
    if (!dia || !con) return;
    var caja = $("#cita-slots");
    caja.innerHTML = '<p style="margin:0;font-size:13px;color:var(--gris2)">Consultando su agenda…</p>';
    api("/api/citas/disponibilidad?usuario_id=" + con + "&fecha=" + dia)
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.slots || !d.slots.length) {
          caja.innerHTML = '<p style="margin:0;font-size:13px;color:var(--ambar);font-weight:600">' +
            (d.nota || "Sin horarios libres ese día. Pruebe con otra fecha.") + "</p>";
          return;
        }
        caja.innerHTML = d.slots.map(function (h) {
          return '<button type="button" class="slot" data-h="' + h + '" style="border:1.5px solid var(--borde);background:var(--tarjeta);color:var(--marino);border-radius:10px;padding:10px 16px;font-size:13.5px;font-weight:700;cursor:pointer">' + h + "</button>";
        }).join("");
        $$(".slot").forEach(function (b) {
          b.addEventListener("click", function () {
            $$(".slot").forEach(function (x) {
              x.style.borderColor = "var(--borde)"; x.style.background = "var(--tarjeta)"; x.style.color = "var(--marino)";
            });
            b.style.borderColor = "var(--azul)"; b.style.background = "var(--azul)"; b.style.color = "#fff";
            horaElegida = b.dataset.h;
          });
        });
      });
  }
  $("#cita-dia").addEventListener("change", cargarDisponibilidad);
  $("#cita-con").addEventListener("change", cargarDisponibilidad);

  $("#form-cita").addEventListener("submit", function (e) {
    e.preventDefault();
    var dia = $("#cita-dia").value;
    if (!dia || !horaElegida) { mostrarAviso("Elija un horario disponible."); return; }
    api("/api/citas/solicitar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        con_usuario_id: Number($("#cita-con").value),
        fecha_hora: new Date(dia + "T" + horaElegida + ":00").toISOString(),
        modalidad: $("#cita-modalidad").value,
        motivo: $("#cita-motivo").value || null
      })
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) return;
        $("#cita-ok-titulo").textContent = res.j.mensaje;
        $("#form-cita").classList.add("oculto");
        $("#cita-ok").classList.remove("oculto");
        cargarCitas();
      });
  });
  $("#btn-otra-cita").addEventListener("click", function () {
    $("#cita-ok").classList.add("oculto");
    $("#form-cita").classList.remove("oculto");
    $("#cita-motivo").value = "";
    horaElegida = null;
    cargarDisponibilidad();
  });

  /* ---------- Buzón de trámites ---------- */
  $("#form-tramite").addEventListener("submit", function (e) {
    e.preventDefault();
    api("/api/portal/solicitar-tramite", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tipo_tramite: $("#tipo-tramite").value,
        descripcion: $("#detalle-tramite").value || null
      })
    }).then(function (r) { return r.json(); })
      .then(function (j) {
        $("#tramite-ok-titulo").textContent = "Su solicitud quedó registrada · folio #" + j.ticket_id;
        $("#form-tramite").classList.add("oculto");
        $("#tramite-ok").classList.remove("oculto");
        $("#detalle-tramite").value = "";
      });
  });
  /* ---------- COMPROBANTE DE PAGO ---------- */
  var OBLIGACION_SAT = null;
  $("#sat-comprobante-archivo").addEventListener("change", function () {
    var inp = $("#sat-comprobante-archivo"), msj = $("#sat-comprobante-msj");
    if (!inp.files.length || !OBLIGACION_SAT) return;
    var fd = new FormData();
    fd.append("archivo_pdf", inp.files[0]);
    fd.append("referencia", $("#sat-referencia").value || "");
    msj.classList.remove("oculto");
    msj.style.color = "var(--gris)";
    msj.textContent = "Enviando su comprobante…";
    api("/api/portal/obligaciones/" + OBLIGACION_SAT + "/comprobante-pago",
        { method: "POST", body: fd })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (!res.ok) { msj.style.color = "var(--rojo)";
          msj.textContent = res.j.detail || "No se pudo enviar el comprobante."; return; }
        msj.style.color = "var(--verde)";
        msj.textContent = res.j.mensaje;
        setTimeout(cargarPortal, 1400);
      });
  });

  /* ---------- RESUMEN FINANCIERO (solo si el despacho lo emitió) ---------- */
  function cargarResumenFinanciero() {
    api("/api/portal/resumen-financiero").then(function (r) { return r.json(); })
      .then(function (f) {
        if (!f || !f.hay_estado_financiero) return;   // sin balance, no se muestra
        $("#seccion-financiero").classList.remove("oculto");
        $("#fin-periodo").textContent = "Cifras al cierre de " + f.periodo +
          (f.razon_circulante ? " · por cada peso que debe, tiene $" + f.razon_circulante : "");
        $("#fin-activo").textContent = dinero(f.activo_total);
        $("#fin-pasivo").textContent = dinero(f.pasivo_total);
        $("#fin-capital").textContent = dinero(f.capital_total);
        $("#fin-leyenda").textContent = f.leyenda;
      }).catch(function () {});
  }

  $("#btn-estado-cuenta").addEventListener("click", function () {
    descargar("/api/portal/estado-cuenta-anual", "Generando su estado de cuenta…");
  });

  /* ---------- SOLICITUD DE FACTURAS ---------- */
  var EST_FX = { solicitada: ["Solicitada", "var(--azul)"],
    en_proceso: ["En proceso", "var(--ambar)"], emitida: ["Emitida ✓", "var(--verde)"],
    rechazada: ["No procedió", "var(--rojo)"] };
  function cargarMisFacturas() {
    api("/api/portal/facturas").then(function (r) { return r.json(); }).then(function (fs) {
      $("#mis-facturas-lista").innerHTML = fs.map(function (f) {
        var e = EST_FX[f.estatus] || [f.estatus, "var(--gris)"];
        return '<div style="background:var(--tarjeta);border:1px solid var(--borde);border-radius:12px;padding:14px 16px">' +
          '<div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap">' +
          '<p style="margin:0;font-size:13.5px;font-weight:700;color:var(--marino)">Folio #' + f.id + " · " + f.receptor_razon_social + "</p>" +
          '<span style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:' + e[1] + '">' + e[0] + "</span></div>" +
          '<p style="margin:4px 0 0;font-size:12.5px;color:var(--gris)">' + f.concepto +
          (f.monto ? ' · <span class="tnum" style="font-weight:700">' + dinero(f.monto) + "</span>" : "") + "</p>" +
          (f.motivo_rechazo ? '<p style="margin:6px 0 0;font-size:12.5px;color:var(--rojo)">Motivo: ' + f.motivo_rechazo + "</p>" : "") +
          (f.estatus === "emitida" ? '<p style="margin:6px 0 0;font-size:12.5px;color:var(--verde);font-weight:600">Ya está en su bóveda de documentos, lista para descargar.</p>' : "") +
          "</div>";
      }).join("");
    }).catch(function () {});
  }
  $("#form-factura").addEventListener("submit", function (ev) {
    ev.preventDefault();
    var msj = $("#fx-msj");
    api("/api/portal/facturas", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        receptor_rfc: $("#fx-rfc").value, receptor_razon_social: $("#fx-razon").value,
        receptor_cp: $("#fx-cp").value || null, receptor_regimen: $("#fx-regimen").value || null,
        uso_cfdi: $("#fx-uso").value, forma_pago: $("#fx-forma").value,
        metodo_pago: $("#fx-metodo").value, concepto: $("#fx-concepto").value,
        monto: $("#fx-monto").value ? +$("#fx-monto").value : null,
        notas: $("#fx-notas").value || null }) })
      .then(function (r) { return r.json().then(function (jj) { return { ok: r.ok, j: jj }; }); })
      .then(function (res) {
        if (!res.ok) { msj.textContent = res.j.detail || "Revise los datos.";
          msj.style.color = "var(--rojo)"; msj.classList.remove("oculto"); return; }
        $("#form-factura").classList.add("oculto");
        $("#factura-ok").classList.remove("oculto");
        $("#factura-ok-titulo").textContent = "Solicitud registrada · folio #" + res.j.folio;
        cargarMisFacturas();
      });
  });
  $("#btn-otra-factura").addEventListener("click", function () {
    $("#form-factura").reset(); $("#form-factura").classList.remove("oculto");
    $("#factura-ok").classList.add("oculto"); $("#fx-msj").classList.add("oculto");
  });

  $("#btn-otro-tramite").addEventListener("click", function () {
    $("#tramite-ok").classList.add("oculto");
    $("#form-tramite").classList.remove("oculto");
  });

  /* ---------- Carga del portal ---------- */
  function cargarPortal() {
    $("#vista-login").classList.add("oculto");
    $("#vista-portal").classList.remove("oculto");
    cargarMisFacturas();
    cargarResumenFinanciero();
    $("#cab-periodo").textContent = NOMBRE_MES;
    window.scrollTo(0, 0);

    api("/api/portal/dashboard?mes=" + MES + "&anio=" + ANIO)
      .then(function (r) { return r.json(); })
      .then(function (d) {
        $("#cab-empresa").textContent = d.empresa || "";
        var estado = d.semaforo_sat.estado;
        dibujarSello(estado);
        $("#semaforo-titulo").textContent = d.semaforo_sat.mensaje;
        $("#semaforo-titulo").style.color = COLORES[estado] || "#0A1C33";
        $("#semaforo-sub").textContent = SUB_SEMAFORO[estado] || "";
        $("#progreso-barra").style.width = d.progreso_contabilidad.porcentaje + "%";
        $("#progreso-texto").textContent = d.progreso_contabilidad.porcentaje + "%";
        $("#impuesto-total").textContent = dinero(d.monto_total_impuesto);
        $("#impuesto-periodo").textContent = "MXN · periodo " + NOMBRE_MES;
        if (d.desglose_impuestos) dibujarDona(d.desglose_impuestos);
        else $("#sin-desglose").classList.remove("oculto");
        pintarPagos(d);
      });

    cargarCitas();
  cargarCertificados();
  api("/api/portal/boveda")
      .then(function (r) { return r.json(); })
      .then(pintarBoveda);
  }

  if (token) cargarPortal();
})();
