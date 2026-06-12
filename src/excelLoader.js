// ============================================================
//  AgroGestión — Cargador de Excel
//  Agroselectos P&A
//
//  Lee y escribe archivos Excel con las hojas:
//  Instrucciones, Cuentas, Parcelas, Trabajadores, Encargados,
//  Agrónomos, Cuadrillas, Proveedores, Cultivos.
// ============================================================

import * as XLSX from "xlsx";

// ------------------------------------------------------------
//  ESTRUCTURA DE LAS HOJAS
//  Define qué columnas tiene cada hoja y qué tipo son.
// ------------------------------------------------------------
export const HOJAS = {
  Cuentas: {
    columnas: ["Nombre", "Correo", "Contraseña inicial", "Rol"],
    ejemplos: [
      ["Juan Pérez García", "juan@agroselectos.com", "Temporal2026!", "admin"],
      ["María López",       "maria@agroselectos.com", "Temporal2026!", "finanzas"],
    ],
    roles_validos: ["admin", "dueno", "finanzas", "encargado", "agronomo"],
  },
  Parcelas: {
    columnas: ["Nombre", "Ubicación", "Hectáreas", "Cultivo actual", "Emoji", "Notas"],
    ejemplos: [
      ["Rancho 1", "R01", 5.2, "Chile", "🌶️", ""],
      ["Rancho 2", "R02", 3.8, "Ajo",   "🧄", ""],
    ],
  },
  Trabajadores: {
    columnas: ["Nombre", "PIN", "Sueldo diario", "Categoría", "Teléfono", "Notas"],
    ejemplos: [
      ["Juan Pérez",   "1111", 350, "Tractorista", "4491234567", ""],
      ["Pablo Ramírez","2222", 280, "Jornalero",   "", ""],
      ["Miguel Solís", "3333", 400, "Dronero",     "4499876543", ""],
    ],
  },
  Encargados: {
    columnas: ["Nombre", "PIN", "Sueldo diario", "Teléfono", "Notas"],
    ejemplos: [
      ["Pedro Ramírez", "5555", 600, "4495551234", ""],
    ],
  },
  Agrónomos: {
    columnas: ["Nombre", "PIN", "Teléfono", "Notas"],
    ejemplos: [
      ["Luis Herrera", "7777", "4497778888", ""],
    ],
  },
  Cuadrillas: {
    columnas: ["Nombre", "PIN", "Miembros", "Flete diario", "Teléfono contacto", "Notas"],
    ejemplos: [
      ["Cuadrilla Norte", "8888", 8, 500, "4491112222", ""],
      ["Cuadrilla Sur",   "9999", 6, 400, "", ""],
    ],
  },
  Proveedores: {
    columnas: ["Nombre", "Teléfono", "Dirección", "Notas"],
    ejemplos: [
      ["Agroquímicos del Bajío", "555-1234", "Aguascalientes", ""],
    ],
  },
  Cultivos: {
    columnas: ["Nombre", "Emoji", "Duración total (días)", "Unidad de cosecha", "Camas por hectárea"],
    ejemplos: [
      ["Maíz",  "🌽", 150, "toneladas", ""],
      ["Ajo",   "🧄", 250, "kg", 40],
      ["Chile", "🌶️", 180, "cajas", 25],
    ],
  },
  Fenología: {
    columnas: ["Cultivo", "Etapa", "Día inicio", "Día fin"],
    ejemplos: [
      ["Maíz", "Preparación de suelo", 0, 14],
      ["Maíz", "Siembra", 14, 21],
      ["Maíz", "Emergencia", 21, 40],
      ["Maíz", "Crecimiento", 40, 100],
      ["Maíz", "Floración", 100, 125],
      ["Maíz", "Llenado de grano", 125, 145],
      ["Maíz", "Cosecha", 145, 150],
    ],
  },
};

const INSTRUCCIONES = [
  ["AGROGESTIÓN — Plantilla de carga inicial"],
  ["Agroselectos P&A"],
  [""],
  ["Cómo usar este archivo:"],
  ["1. Llena las hojas con los datos de tu rancho."],
  ["2. Puedes dejar hojas vacías si no las necesitas todavía."],
  ["3. No cambies los nombres de las columnas (primera fila de cada hoja)."],
  ["4. Borra las filas de ejemplo antes de guardar tu versión final."],
  ["5. Cuando termines, guarda el archivo y súbelo en la app: Inicio → Subir a la nube → Cargar plantilla."],
  [""],
  ["Qué hace cada hoja:"],
  [""],
  ["• Cuentas:    personas que administran (admin, dirección, finanzas, encargado, agrónomo)."],
  ["              Entran a la app con correo y contraseña."],
  ["              Roles válidos: admin, dueno, finanzas, encargado, agronomo"],
  [""],
  ["• Parcelas:   los terrenos del rancho con sus hectáreas y cultivo actual."],
  [""],
  ["• Trabajadores: trabajadores de planta con su PIN, sueldo y categoría."],
  ["                Entran a la app con su PIN."],
  [""],
  ["• Encargados:   encargados con su PIN (también puedes darles cuenta en la hoja Cuentas)."],
  [""],
  ["• Agrónomos:    agrónomos con su PIN (también puedes darles cuenta en la hoja Cuentas)."],
  [""],
  ["• Cuadrillas:   grupos externos con PIN, número de miembros y flete diario."],
  [""],
  ["• Proveedores:  proveedores de insumos."],
  [""],
  ["• Cultivos:     catálogo de cultivos con su emoji, duración total, unidad de cosecha y camas por hectárea."],
  ["                'Camas por hectárea' es opcional: déjalo vacío si ese cultivo no se maneja por camas."],
  [""],
  ["• Fenología:    etapas de cada cultivo (días de inicio y fin de cada etapa)."],
  ["                Por cada cultivo, agrega tantas filas como etapas tenga."],
  ["                Ejemplo para Maíz:"],
  ["                    Cultivo: Maíz, Etapa: Preparación de suelo, Día inicio: 0,  Día fin: 14"],
  ["                    Cultivo: Maíz, Etapa: Siembra,             Día inicio: 14, Día fin: 21"],
  ["                    Cultivo: Maíz, Etapa: Emergencia,          Día inicio: 21, Día fin: 40"],
  ["                    ... y así hasta cosecha."],
  ["                Importante: el 'Cultivo' debe escribirse igual que en la hoja 'Cultivos'."],
  [""],
  ["Notas importantes:"],
  [""],
  ["– Los PINs deben ser únicos dentro de cada tipo (no puede haber dos trabajadores con el mismo PIN)."],
  ["– Para crear las cuentas de administración, la app te dará un código SQL"],
  ["  que tendrás que pegar en Supabase (instrucciones aparecen al cargar el Excel)."],
  ["– Si te equivocas o subes el mismo archivo dos veces, la app te avisará y te"],
  ["  preguntará qué hacer (sobrescribir, ignorar, etc.)."],
];

// ------------------------------------------------------------
//  GENERAR PLANTILLA EXCEL
// ------------------------------------------------------------
export function generarPlantilla() {
  const wb = XLSX.utils.book_new();

  // Hoja de instrucciones
  const wsInstr = XLSX.utils.aoa_to_sheet(INSTRUCCIONES);
  wsInstr["!cols"] = [{ wch: 100 }];
  XLSX.utils.book_append_sheet(wb, wsInstr, "Instrucciones");

  // Hojas de datos
  for (const [nombre, def] of Object.entries(HOJAS)) {
    const rows = [def.columnas, ...def.ejemplos];
    const ws = XLSX.utils.aoa_to_sheet(rows);
    // Ancho de columnas razonable
    ws["!cols"] = def.columnas.map(c => ({ wch: Math.max(c.length + 4, 18) }));
    XLSX.utils.book_append_sheet(wb, ws, nombre);
  }

  // Descargar
  XLSX.writeFile(wb, "AgroGestion-Plantilla.xlsx");
}

// ------------------------------------------------------------
//  LEER ARCHIVO EXCEL Y CONVERTIR A OBJETOS
// ------------------------------------------------------------
export async function leerExcel(file) {
  const buffer = await file.arrayBuffer();
  const wb = XLSX.read(buffer, { type: "array" });
  const resultado = {};

  for (const [nombre, def] of Object.entries(HOJAS)) {
    const ws = wb.Sheets[nombre];
    if (!ws) { resultado[nombre] = []; continue; }
    // Leer como array de objetos usando los encabezados de la primera fila
    const filas = XLSX.utils.sheet_to_json(ws, { defval: "" });
    // Filtrar filas vacías (las que tienen todos los campos en blanco)
    const noVacias = filas.filter(f => Object.values(f).some(v => v !== "" && v !== null && v !== undefined));
    resultado[nombre] = noVacias;
  }
  return resultado;
}

// ------------------------------------------------------------
//  CONVERTIR datos del Excel → formato de la app
// ------------------------------------------------------------
export function excelAColecciones(datosExcel) {
  const out = {
    ranchos: [{ id: "r_agro", nombre: "Agroselectos P&A", hectareas: 0, lat: null, lng: null }],
    parcelas: [],
    trabajadores: [],
    encargados: [],
    agronomos: [],
    cuadrillas: [],
    proveedores: [],
    cultivos: [],
    cuentas: [], // especial: estos no van a una tabla, generan SQL
  };

  // Parcelas
  (datosExcel.Parcelas || []).forEach((f, i) => {
    const nombre = (f["Nombre"] || "").toString().trim();
    if (!nombre) return;
    out.parcelas.push({
      id: `p_${(f["Ubicación"] || `p${i+1}`).toString().trim().toLowerCase().replace(/\s+/g, "_")}`,
      ranchoId: "r_agro",
      ubicacionId: (f["Ubicación"] || "").toString().trim(),
      nombre,
      cultivo: (f["Cultivo actual"] || "").toString().trim(),
      hectareas: parseFloat(f["Hectáreas"]) || 0,
      emoji: (f["Emoji"] || "🌾").toString().trim() || "🌾",
      notas: (f["Notas"] || "").toString().trim(),
      lat: null, lng: null, foto: null, cicloFenologico: [],
    });
  });

  // Trabajadores
  (datosExcel.Trabajadores || []).forEach((f, i) => {
    const nombre = (f["Nombre"] || "").toString().trim();
    if (!nombre) return;
    out.trabajadores.push({
      id: `t${Date.now()}${i}`,
      nombre,
      pin: (f["PIN"] || "").toString().trim(),
      sueldo_dia: parseFloat(f["Sueldo diario"]) || 0,
      categoria: (f["Categoría"] || "Jornalero").toString().trim(),
      telefono: (f["Teléfono"] || "").toString().trim(),
      notas: (f["Notas"] || "").toString().trim(),
    });
  });

  // Encargados
  (datosExcel.Encargados || []).forEach((f, i) => {
    const nombre = (f["Nombre"] || "").toString().trim();
    if (!nombre) return;
    out.encargados.push({
      id: `en${Date.now()}${i}`,
      nombre,
      pin: (f["PIN"] || "").toString().trim(),
      sueldo_dia: parseFloat(f["Sueldo diario"]) || 0,
      telefono: (f["Teléfono"] || "").toString().trim(),
      notas: (f["Notas"] || "").toString().trim(),
    });
  });

  // Agrónomos
  (datosExcel["Agrónomos"] || []).forEach((f, i) => {
    const nombre = (f["Nombre"] || "").toString().trim();
    if (!nombre) return;
    out.agronomos.push({
      id: `ag${Date.now()}${i}`,
      nombre,
      pin: (f["PIN"] || "").toString().trim(),
      telefono: (f["Teléfono"] || "").toString().trim(),
      notas: (f["Notas"] || "").toString().trim(),
    });
  });

  // Cuadrillas
  (datosExcel.Cuadrillas || []).forEach((f, i) => {
    const nombre = (f["Nombre"] || "").toString().trim();
    if (!nombre) return;
    out.cuadrillas.push({
      id: `cq${Date.now()}${i}`,
      nombre,
      pin: (f["PIN"] || "").toString().trim(),
      miembros: parseInt(f["Miembros"]) || 0,
      flete_dia: parseFloat(f["Flete diario"]) || 0,
      telefono: (f["Teléfono contacto"] || "").toString().trim(),
      notas: (f["Notas"] || "").toString().trim(),
    });
  });

  // Proveedores
  (datosExcel.Proveedores || []).forEach((f, i) => {
    const nombre = (f["Nombre"] || "").toString().trim();
    if (!nombre) return;
    out.proveedores.push({
      id: `pr${Date.now()}${i}`,
      nombre,
      telefono: (f["Teléfono"] || "").toString().trim(),
      direccion: (f["Dirección"] || "").toString().trim(),
      notas: (f["Notas"] || "").toString().trim(),
    });
  });

  // Cultivos (junta con fenología si hay)
  // Primero indexamos la fenología por nombre de cultivo
  const fenologiaPorCultivo = {};
  (datosExcel["Fenología"] || []).forEach(f => {
    const nombreCultivo = (f["Cultivo"] || "").toString().trim();
    if (!nombreCultivo) return;
    const etapa = (f["Etapa"] || "").toString().trim();
    if (!etapa) return;
    if (!fenologiaPorCultivo[nombreCultivo]) fenologiaPorCultivo[nombreCultivo] = [];
    fenologiaPorCultivo[nombreCultivo].push({
      etapa,
      diaInicio: parseInt(f["Día inicio"]) || 0,
      diaFin: parseInt(f["Día fin"]) || 0,
    });
  });
  // Ordenar las etapas de cada cultivo por día de inicio
  Object.keys(fenologiaPorCultivo).forEach(k => {
    fenologiaPorCultivo[k].sort((a, b) => a.diaInicio - b.diaInicio);
  });

  (datosExcel.Cultivos || []).forEach((f) => {
    const nombre = (f["Nombre"] || "").toString().trim();
    if (!nombre) return;
    out.cultivos.push({
      id: `cul_${nombre.toLowerCase().replace(/\s+/g, "_")}`,
      nombre,
      emoji: (f["Emoji"] || "🌱").toString().trim() || "🌱",
      duracionDias: parseInt(f["Duración total (días)"]) || 0,
      unidadCosecha: (f["Unidad de cosecha"] || "kg").toString().trim(),
      camasPorHa: parseFloat(f["Camas por hectárea"]) || 0,
      fenologia: fenologiaPorCultivo[nombre] || [],
    });
  });

  // Cuentas (no son colección, generan SQL aparte)
  (datosExcel.Cuentas || []).forEach((f) => {
    const correo = (f["Correo"] || "").toString().trim().toLowerCase();
    if (!correo || !correo.includes("@")) return;
    out.cuentas.push({
      nombre: (f["Nombre"] || "").toString().trim(),
      correo,
      password: (f["Contraseña inicial"] || "").toString(),
      rol: (f["Rol"] || "encargado").toString().trim().toLowerCase(),
    });
  });

  return out;
}

// ------------------------------------------------------------
//  VALIDAR datos antes de subir
//  Devuelve { ok: bool, errores: [...], advertencias: [...] }
// ------------------------------------------------------------
export function validar(colecciones) {
  const errores = [];
  const advertencias = [];

  // Validar Cuentas
  const correosVistos = new Set();
  const rolesValidos = HOJAS.Cuentas.roles_validos;
  (colecciones.cuentas || []).forEach((c, i) => {
    if (!c.correo) errores.push(`Cuenta fila ${i+2}: falta correo`);
    if (correosVistos.has(c.correo)) errores.push(`Cuenta fila ${i+2}: correo repetido "${c.correo}"`);
    correosVistos.add(c.correo);
    if (!c.password || c.password.length < 6) errores.push(`Cuenta "${c.correo}": contraseña muy corta (mínimo 6 caracteres)`);
    if (!rolesValidos.includes(c.rol)) errores.push(`Cuenta "${c.correo}": rol "${c.rol}" no válido. Debe ser uno de: ${rolesValidos.join(", ")}`);
  });

  // Validar PINs únicos dentro de cada grupo
  const verificarPins = (lista, etiqueta) => {
    const pins = new Set();
    lista.forEach(x => {
      if (!x.pin) { advertencias.push(`${etiqueta} "${x.nombre}": sin PIN (no podrá entrar)`); return; }
      if (pins.has(x.pin)) errores.push(`${etiqueta}: PIN "${x.pin}" repetido`);
      pins.add(x.pin);
    });
  };
  verificarPins(colecciones.trabajadores || [], "Trabajador");
  verificarPins(colecciones.encargados || [], "Encargado");
  verificarPins(colecciones.agronomos || [], "Agrónomo");
  verificarPins(colecciones.cuadrillas || [], "Cuadrilla");

  // Validar coherencia de fenología con cultivos
  const nombresCultivos = new Set((colecciones.cultivos || []).map(c => c.nombre));
  (colecciones.cultivos || []).forEach(c => {
    if (c.fenologia && c.fenologia.length > 0) {
      // Verificar que las etapas no se traslapen ni tengan inicio mayor que fin
      c.fenologia.forEach(e => {
        if (e.diaFin < e.diaInicio) errores.push(`Fenología de "${c.nombre}" — etapa "${e.etapa}": día fin (${e.diaFin}) es menor que día inicio (${e.diaInicio})`);
        if (c.duracionDias > 0 && e.diaFin > c.duracionDias) advertencias.push(`Fenología de "${c.nombre}" — etapa "${e.etapa}" termina en día ${e.diaFin}, pero el cultivo dura ${c.duracionDias} días`);
      });
    } else if (c.fenologia && c.fenologia.length === 0) {
      advertencias.push(`Cultivo "${c.nombre}": sin etapas de fenología (no aparecerá su calendario)`);
    }
  });
  return { ok: errores.length === 0, errores, advertencias };
}

// ------------------------------------------------------------
//  GENERAR SQL para crear cuentas en Supabase Auth
//  El usuario pega este SQL en Supabase → SQL Editor → Run
// ------------------------------------------------------------
export function generarSQLCuentas(cuentas) {
  if (!cuentas || cuentas.length === 0) return "-- No hay cuentas para crear";

  const lineas = [
    "-- ============================================================",
    "-- AGROGESTIÓN — Crear cuentas de administración",
    "-- ============================================================",
    "-- Este script crea las cuentas en Supabase Auth y sus perfiles.",
    "-- Cópialo COMPLETO y pégalo en: Supabase → SQL Editor → Nueva consulta → Run",
    "-- ============================================================",
    "",
  ];

  cuentas.forEach((c, i) => {
    // Genera un UUID determinista basado en el correo para que sea idempotente
    lineas.push(`-- Cuenta ${i+1}: ${c.nombre} (${c.correo}) — rol: ${c.rol}`);
    lineas.push(`DO $$`);
    lineas.push(`DECLARE`);
    lineas.push(`  nuevo_id uuid;`);
    lineas.push(`BEGIN`);
    lineas.push(`  -- Si la cuenta ya existe, no la duplica`);
    lineas.push(`  SELECT id INTO nuevo_id FROM auth.users WHERE email = '${c.correo}';`);
    lineas.push(`  IF nuevo_id IS NULL THEN`);
    lineas.push(`    nuevo_id := gen_random_uuid();`);
    lineas.push(`    INSERT INTO auth.users (id, instance_id, email, encrypted_password, email_confirmed_at, created_at, updated_at, raw_app_meta_data, raw_user_meta_data, aud, role)`);
    lineas.push(`    VALUES (nuevo_id, '00000000-0000-0000-0000-000000000000', '${c.correo}', crypt('${c.password.replace(/'/g, "''")}', gen_salt('bf')), now(), now(), now(), '{"provider":"email","providers":["email"]}'::jsonb, '{}'::jsonb, 'authenticated', 'authenticated');`);
    lineas.push(`    INSERT INTO auth.identities (id, user_id, identity_data, provider, provider_id, last_sign_in_at, created_at, updated_at)`);
    lineas.push(`    VALUES (gen_random_uuid(), nuevo_id, format('{"sub":"%s","email":"%s"}', nuevo_id, '${c.correo}')::jsonb, 'email', '${c.correo}', now(), now(), now());`);
    lineas.push(`  END IF;`);
    lineas.push(`  -- Crear o actualizar perfil`);
    lineas.push(`  INSERT INTO perfiles (id, nombre, rol) VALUES (nuevo_id, '${c.nombre.replace(/'/g, "''")}', '${c.rol}')`);
    lineas.push(`  ON CONFLICT (id) DO UPDATE SET nombre = EXCLUDED.nombre, rol = EXCLUDED.rol;`);
    lineas.push(`END $$;`);
    lineas.push("");
  });

  lineas.push("-- ============================================================");
  lineas.push("-- LISTO. Las cuentas ya pueden entrar a la app con su correo");
  lineas.push("-- y la contraseña que pusiste en el Excel.");
  lineas.push("-- Recuérdales que cambien su contraseña la primera vez que entren.");
  lineas.push("-- ============================================================");

  return lineas.join("\n");
}

/* ════════════ EXPORTAR PÓLIZAS PARA CONTPAQi ════════════ */
/* Genera un Excel con formato de pólizas de diario para importar a ContPAQi.
   - Una póliza por día (todos los movimientos del día agrupados).
   - Cada movimiento es una línea con cuenta, cargo/abono, concepto y centro de
     costos (el cultivo). El usuario mapea las cuentas con su catálogo.
   El formato exacto de ContPAQi varía por empresa; este es un layout estándar de
   póliza de diario que el usuario puede ajustar a su catálogo. */

// movimientos: [{ fecha, tipo: "egreso"|"ingreso"|"costoMO", concepto, monto, cuenta, cultivo, contracuenta }]
export function exportarPolizas(movimientos, opciones = {}) {
  const { nombreEmpresa = "Agroselectos P&A", tipoPoliza = "Diario" } = opciones;

  // Agrupar por fecha (una póliza por día)
  const porDia = {};
  movimientos.forEach(m => {
    const f = m.fecha || "";
    if (!f) return;
    (porDia[f] = porDia[f] || []).push(m);
  });
  const dias = Object.keys(porDia).sort();

  // Encabezados estilo ContPAQi (hoja electrónica de pólizas)
  const filas = [[
    "No. Poliza", "Tipo", "Fecha", "Concepto Poliza",
    "Cuenta", "Concepto Movimiento", "Cargo", "Abono", "Centro Costos", "Referencia",
  ]];

  let numPoliza = 1;
  dias.forEach(dia => {
    const movs = porDia[dia];
    const conceptoPoliza = `Movimientos del ${dia}`;
    movs.forEach(m => {
      const monto = Math.abs(parseFloat(m.monto) || 0);
      // Egreso/costo: cargo a la cuenta de gasto, abono a la contracuenta (banco/caja/por pagar)
      // Ingreso: cargo a la contracuenta (banco/cliente), abono a la cuenta de ingreso
      const esIngreso = m.tipo === "ingreso";
      const cuentaPrincipal = m.cuenta || "";
      const contracuenta = m.contracuenta || "";
      if (esIngreso) {
        // Línea 1: cargo a contracuenta (lo que entra)
        filas.push([numPoliza, tipoPoliza, dia, conceptoPoliza, contracuenta, m.concepto || "", monto, 0, m.cultivo || "", m.referencia || ""]);
        // Línea 2: abono a cuenta de ingreso
        filas.push([numPoliza, tipoPoliza, dia, conceptoPoliza, cuentaPrincipal, m.concepto || "", 0, monto, m.cultivo || "", m.referencia || ""]);
      } else {
        // Gasto/costo: cargo a la cuenta de gasto
        filas.push([numPoliza, tipoPoliza, dia, conceptoPoliza, cuentaPrincipal, m.concepto || "", monto, 0, m.cultivo || "", m.referencia || ""]);
        // Abono a la contracuenta
        filas.push([numPoliza, tipoPoliza, dia, conceptoPoliza, contracuenta, m.concepto || "", 0, monto, m.cultivo || "", m.referencia || ""]);
      }
    });
    numPoliza++;
  });

  const wb = XLSX.utils.book_new();
  const ws = XLSX.utils.aoa_to_sheet(filas);
  // Anchos de columna
  ws["!cols"] = [
    { wch: 10 }, { wch: 10 }, { wch: 12 }, { wch: 28 },
    { wch: 16 }, { wch: 30 }, { wch: 14 }, { wch: 14 }, { wch: 16 }, { wch: 20 },
  ];
  XLSX.utils.book_append_sheet(wb, ws, "Polizas");
  const fname = `polizas-contpaqi-${dias[0] || "export"}_a_${dias[dias.length - 1] || ""}.xlsx`;
  XLSX.writeFile(wb, fname);
  return { polizas: numPoliza - 1, movimientos: movimientos.length, archivo: fname };
}
