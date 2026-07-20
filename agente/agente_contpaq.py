# -*- coding: utf-8 -*-
"""
AGENTE CONTPAQ — extracción local en SOLO LECTURA
=================================================
Corre EN la PC del despacho (donde vive el SQL Server de CONTPAQi), lee las
bases de Contabilidad y Nóminas y EMPUJA los resúmenes por HTTPS al sistema.
El SQL Server jamás se expone a internet.

Solo lectura, garantizado en tres capas:
  1. Usuario SQL 'lector_pya' con db_datareader y DENY de escritura
     (crear con crear_usuario_lectura.sql).
  2. La conexión se abre con ApplicationIntent=ReadOnly.
  3. Este script solo contiene SELECT.

Modos:
  python agente_contpaq.py --descubrir   → imprime las BDs y el esquema real
                                           (los nombres de campos de CONTPAQi
                                           varían por versión: ajuste CAMPOS)
  python agente_contpaq.py --prueba      → extrae y muestra, SIN enviar
  python agente_contpaq.py --enviar      → extrae y envía al sistema

Programación sugerida (diario 7:00 am, Tareas de Windows):
  schtasks /Create /SC DAILY /ST 07:00 /TN "Agente P&A CONTPAQ" ^
    /TR "py C:\\pya\\agente_contpaq.py --enviar"
"""
import argparse
import calendar
import configparser
import datetime as dt
import json
import sys

import pyodbc
import requests

CFG = configparser.ConfigParser()

# ─────────────────────────────────────────────────────────────────────────────
# NOMBRES DE TABLAS/CAMPOS DE CONTPAQi.
# Estos son los del esquema clásico; CONTPAQi los cambia entre versiones.
# Corra --descubrir y ajuste aquí lo que difiera en SU instalación.
# ─────────────────────────────────────────────────────────────────────────────
CAMPOS = {
    # CONTPAQi CONTABILIDAD (una BD por empresa)
    "polizas":       "Polizas",        # cabecera de póliza
    "pol_id":        "Id",
    "pol_fecha":     "Fecha",
    # Movimientos: los renglones de cada póliza (cargo/abono por cuenta)
    "movs":          "Movimientos",
    "mov_poliza":    "IdPoliza",
    "mov_cuenta":    "IdCuenta",
    "mov_tipo":      "TipoMovto",      # 0 = cargo, 1 = abono
    "mov_importe":   "Importe",
    # Cuentas: el catálogo (jerarquía por IdPadre; CodigoAgrupador = SAT)
    "cuentas":       "Cuentas",
    "cta_id":        "Id",
    "cta_nombre":    "Nombre",
    "cta_padre":     "IdPadre",
    "cta_agrupador": "CodigoAgrupador",
    # CONTPAQi NÓMINAS (una BD por empresa)
    "empleados":     "Empleados",
    "emp_codigo":    "CodigoEmpleado",
    "emp_baja":      "Baja",           # 0 = activo
    "emp_sd":        "SalarioDiario",
    "emp_sdi":       "SalarioDiarioIntegrado",
}

# ADD de CONTPAQi (Administrador de Documentos Digitales): los XML timbrados.
# Es la fuente "lo facturado de verdad a la fecha", exista o no captura
# contable. Los nombres varían MUCHO por versión: valídelos con --descubrir.
CAMPOS_ADD = {
    "docs":       "DocumentMetadata",
    "fecha":      "IssuedDate",
    "total":      "Total",
    "emisor":     "Rfc",              # RFC del emisor del CFDI
    "receptor":   "ReceiverRfc",
    "cancelado":  "Cancelled",        # 0/false = vigente
    "tipo":       "DocumentTypeId",   # ingreso; si difiere, ajuste el filtro
}

# Ingresos = CFDI EMITIDOS por la empresa · Egresos = RECIBIDOS por ella.
# La GLOBAL se detecta por el receptor genérico del público (XAXX010101000).
SQL_XML_MES = """
SELECT
  SUM(CASE WHEN {emisor} = ?   AND {cancelado} = 0 THEN {total} ELSE 0 END),
  SUM(CASE WHEN {receptor} = ? AND {cancelado} = 0 THEN {total} ELSE 0 END),
  SUM(CASE WHEN {emisor} = ? AND {receptor} = 'XAXX010101000'
            AND {cancelado} = 0 THEN 1 ELSE 0 END)
FROM {docs}
WHERE {fecha} >= ? AND {fecha} < ?
"""


def extraer_xml_mes(base_add: str, rfc: str, desde, hasta):
    with conectar(base_add) as cx:
        fila = cx.cursor().execute(
            SQL_XML_MES.format(**CAMPOS_ADD),
            rfc, rfc, rfc, desde, hasta).fetchone()
    return {"ingresos_mtd": round(float(fila[0] or 0), 2),
            "egresos_mtd": round(float(fila[1] or 0), 2),
            "global_emitida": bool(fila[2])}


# El Código Agrupador del SAT clasifica el catálogo sin depender de cómo
# numere las cuentas cada empresa: 4xx = ingresos · 5xx = costos · 6/7xx = gastos
FAMILIAS = {"4": "ingresos", "5": "costos", "6": "gastos", "7": "gastos"}


def conectar(base: str):
    c = CFG["sqlserver"]
    cadena = (f"DRIVER={{{c.get('driver', 'ODBC Driver 17 for SQL Server')}}};"
              f"SERVER={c['servidor']};DATABASE={base};"
              f"UID={c['usuario']};PWD={c['password']};"
              f"ApplicationIntent=ReadOnly;TrustServerCertificate=yes")
    cx = pyodbc.connect(cadena, autocommit=False)
    cx.setencoding("utf-8")
    return cx


# ─────────────────────────────────────────────────────────────────────────────
# QUERY 1 · CONTABILIDAD: ingresos/costos/gastos por MES y por RUBRO nivel 1,
# separando cuánto del ingreso cae en los ÚLTIMOS 3 DÍAS del mes (la factura
# global). Un solo query alimenta el tablero de resultados Y la predicción.
# ─────────────────────────────────────────────────────────────────────────────
SQL_RESULTADOS = """
WITH nivel1 AS (
    -- ancestro de PRIMER NIVEL de cada cuenta (para agrupar los rubros)
    SELECT {cta_id} AS id, {cta_id} AS raiz, {cta_nombre} AS rubro,
           {cta_agrupador} AS agrupador
      FROM {cuentas} WHERE {cta_padre} IS NULL OR {cta_padre} = 0
    UNION ALL
    SELECT c.{cta_id}, n.raiz, n.rubro, c.{cta_agrupador}
      FROM {cuentas} c JOIN nivel1 n ON c.{cta_padre} = n.id
)
SELECT  YEAR(p.{pol_fecha})              AS anio,
        MONTH(p.{pol_fecha})             AS mes,
        LEFT(n.agrupador, 1)             AS familia_sat,   -- 4/5/6/7
        raiz.{cta_nombre}                AS rubro_nivel1,
        SUM(CASE WHEN m.{mov_tipo} = 0 THEN m.{mov_importe} ELSE 0 END) AS cargos,
        SUM(CASE WHEN m.{mov_tipo} = 1 THEN m.{mov_importe} ELSE 0 END) AS abonos,
        -- lo timbrado en los ÚLTIMOS 3 DÍAS naturales del mes:
        SUM(CASE WHEN m.{mov_tipo} = 1
                  AND DAY(p.{pol_fecha}) > DAY(EOMONTH(p.{pol_fecha})) - 3
                 THEN m.{mov_importe} ELSE 0 END)          AS abonos_cierre,
        SUM(CASE WHEN m.{mov_tipo} = 0
                  AND DAY(p.{pol_fecha}) > DAY(EOMONTH(p.{pol_fecha})) - 3
                 THEN m.{mov_importe} ELSE 0 END)          AS cargos_cierre
FROM {movs} m
JOIN {polizas} p ON p.{pol_id} = m.{mov_poliza}
JOIN nivel1 n    ON n.id       = m.{mov_cuenta}
JOIN {cuentas} raiz ON raiz.{cta_id} = n.raiz
WHERE p.{pol_fecha} >= ? AND p.{pol_fecha} < ?
  AND LEFT(n.agrupador, 1) IN ('4','5','6','7')
  -- Si su versión marca pólizas canceladas, agregue: AND p.Cancelada = 0
GROUP BY YEAR(p.{pol_fecha}), MONTH(p.{pol_fecha}),
         LEFT(n.agrupador, 1), raiz.{cta_nombre}
OPTION (MAXRECURSION 32)
"""

# IVA acreditable REAL por mes (Código Agrupador SAT 118/119: IVA acreditable
# pagado / pendiente de pago). Mejora la predicción: no todo gasto lleva IVA.
SQL_IVA_ACREDITABLE = """
SELECT YEAR(p.{pol_fecha}) AS anio, MONTH(p.{pol_fecha}) AS mes,
       SUM(CASE WHEN m.{mov_tipo} = 0 THEN m.{mov_importe}
                ELSE -m.{mov_importe} END) AS iva_acreditable
FROM {movs} m
JOIN {polizas} p  ON p.{pol_id}  = m.{mov_poliza}
JOIN {cuentas} c  ON c.{cta_id}  = m.{mov_cuenta}
WHERE p.{pol_fecha} >= ? AND p.{pol_fecha} < ?
  AND LEFT(c.{cta_agrupador}, 3) IN ('118', '119')
GROUP BY YEAR(p.{pol_fecha}), MONTH(p.{pol_fecha})
"""

# ─────────────────────────────────────────────────────────────────────────────
# QUERY 2 · NÓMINAS: empleados ACTIVOS con su SDI y salario diario.
# La proyección de IMSS/ISN la calcula el servidor (una sola fuente fiscal).
# ─────────────────────────────────────────────────────────────────────────────
# ¿El mes en curso YA se capturó? La mayoría de los clientes se captura al
# CIERRE: si no hay pólizas del mes, la predicción debe ser estacional y no
# confundir "sin capturar" con "sin ventas".
SQL_POLIZAS_MES = """
SELECT COUNT(*) FROM {polizas}
WHERE {pol_fecha} >= ? AND {pol_fecha} < ?
"""

SQL_EMPLEADOS = """
SELECT {emp_codigo}      AS codigo,
       {emp_sd}          AS salario_diario,
       {emp_sdi}         AS sdi
FROM {empleados}
WHERE {emp_baja} = 0                 -- solo activos
  AND {emp_sdi} > 0
"""


def q(sql: str) -> str:
    return sql.format(**CAMPOS)


def extraer_contabilidad(base: str, desde: dt.date, hasta: dt.date):
    """Devuelve resultados por mes/rubro + serie para la predicción."""
    with conectar(base) as cx:
        filas = cx.cursor().execute(q(SQL_RESULTADOS), desde, hasta).fetchall()
        iva = cx.cursor().execute(q(SQL_IVA_ACREDITABLE), desde, hasta).fetchall()

    meses, serie = {}, {}
    for anio, mes, fam, rubro, cargos, abonos, ab_cie, ca_cie in filas:
        familia = FAMILIAS.get(str(fam))
        if not familia:
            continue
        # Naturaleza: los ingresos (acreedores) suman por ABONOS − cargos;
        # costos y gastos (deudores), por CARGOS − abonos.
        neto = (abonos - cargos) if familia == "ingresos" else (cargos - abonos)
        cierre = (ab_cie - ca_cie) if familia == "ingresos" else 0
        k = (anio, mes)
        m = meses.setdefault(k, {"anio": anio, "mes": mes, "ingresos": 0,
                                 "costos": 0, "gastos": 0, "detalle": []})
        m[familia] = round(m[familia] + float(neto), 2)
        m["detalle"].append({"rubro": rubro, "familia_sat": str(fam),
                             "monto": round(float(neto), 2)})
        if familia == "ingresos":
            s = serie.setdefault(k, {"anio": anio, "mes": mes,
                                     "ingreso_total": 0.0,
                                     "ingreso_ultimos_3_dias": 0.0})
            s["ingreso_total"] = round(s["ingreso_total"] + float(neto), 2)
            s["ingreso_ultimos_3_dias"] = round(
                s["ingreso_ultimos_3_dias"] + float(cierre), 2)
    iva_por_mes = {(a, m): round(float(v or 0), 2) for a, m, v in iva}
    return (sorted(meses.values(), key=lambda x: (x["anio"], x["mes"])),
            sorted(serie.values(), key=lambda x: (x["anio"], x["mes"])),
            iva_por_mes)


def extraer_nomina(base: str):
    with conectar(base) as cx:
        filas = cx.cursor().execute(q(SQL_EMPLEADOS)).fetchall()
    return [{"codigo": str(c).strip(), "salario_diario": float(sd or 0),
             "sdi": float(sdi or 0)} for c, sd, sdi in filas]


def descubrir():
    """Imprime las bases ct*/nom* y el esquema real de las tablas clave."""
    with conectar("master") as cx:
        cur = cx.cursor()
        bds = [r[0] for r in cur.execute(
            "SELECT name FROM sys.databases WHERE name LIKE 'ct%' "
            "OR name LIKE 'nom%' ORDER BY name")]
    print("Bases CONTPAQi encontradas:", ", ".join(bds) or "ninguna")
    for bd in bds[:6]:
        print(f"\n─── {bd} ───")
        with conectar(bd) as cx:
            cur = cx.cursor()
            for tabla in ("Polizas", "Movimientos", "Cuentas", "Empleados",
                          "Periodos"):
                cols = [r[0] for r in cur.execute(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_NAME = ?", tabla)]
                if cols:
                    print(f"  {tabla}: {', '.join(cols[:14])}")
    print("\nSi algún nombre difiere de CAMPOS (arriba del script), ajústelo.")


def enviar(ruta: str, payload: dict):
    r = requests.post(CFG["api"]["url"].rstrip("/") + ruta,
                      json=payload,
                      headers={"X-Token-Agente": CFG["api"]["token"]},
                      timeout=60)
    print(f"  → {ruta}: {r.status_code} {r.text[:140]}")
    r.raise_for_status()


def correr(modo_envio: bool):
    hoy = dt.date.today()
    dias_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    desde = (hoy.replace(day=1) - dt.timedelta(days=370)).replace(day=1)
    hasta = hoy + dt.timedelta(days=1)

    for seccion in CFG.sections():
        if not seccion.startswith("empresa:"):
            continue
        e = CFG[seccion]
        rfc, origen = e["rfc"], seccion.split(":", 1)[1]
        print(f"\n═══ {origen} (RFC {rfc}) ═══")

        if e.get("bd_contabilidad"):
            meses, serie, iva = extraer_contabilidad(
                e["bd_contabilidad"], desde, hasta)
            historicos = [m for m in serie
                          if (m["anio"], m["mes"]) != (hoy.year, hoy.month)][-12:]
            actual = [m for m in serie
                      if (m["anio"], m["mes"]) == (hoy.year, hoy.month)]
            # Fuente XML (ADD): lo timbrado del mes en curso, tal cual
            datos_xml = None
            if e.get("bd_add"):
                try:
                    datos_xml = extraer_xml_mes(
                        e["bd_add"], rfc, hoy.replace(day=1), hasta)
                    print(f"  XML del mes: ingresos {datos_xml['ingresos_mtd']:,.2f} · "
                          f"egresos {datos_xml['egresos_mtd']:,.2f} · "
                          f"global {'ya emitida' if datos_xml['global_emitida'] else 'pendiente'}")
                except Exception as ex:
                    print(f"  ADD no disponible ({ex}): la predicción irá sin fuente XML")
            with conectar(e["bd_contabilidad"]) as cx:
                polizas_mes = cx.cursor().execute(
                    q(SQL_POLIZAS_MES), hoy.replace(day=1), hasta).fetchone()[0]
            print(f"  contabilidad: {len(meses)} meses, "
                  f"{len(historicos)} históricos, "
                  f"pólizas del mes en curso: {polizas_mes}"
                  + ("" if polizas_mes else " (sin capturar → estacional)"))
            if modo_envio:
                enviar("/api/integracion/contpaq/resultados", {
                    "rfc": rfc, "anio": hoy.year, "origen": origen,
                    "meses": [m for m in meses if m["anio"] == hoy.year]})
                # SIEMPRE que haya historial se manda la predicción, aunque
                # el mes en curso venga vacío: el servidor decide el modo.
                if len(historicos) >= 3:
                    gastos = [{"anio": m["anio"], "mes": m["mes"],
                               "gasto_total": m["costos"] + m["gastos"]}
                              for m in meses
                              if (m["anio"], m["mes"]) in
                                 [(h["anio"], h["mes"]) for h in historicos]]
                    extras = ({"coeficiente_utilidad": e.getfloat("coeficiente_utilidad")}
                              if e.get("coeficiente_utilidad") else None)
                    enviar("/api/integracion/contpaq/historial-fiscal", {
                        "rfc": rfc, "anio": hoy.year, "mes": hoy.month,
                        "dia": hoy.day, "dias_mes": dias_mes,
                        "ingreso_real_mtd": (actual[0]["ingreso_total"]
                                             if actual else 0),
                        "polizas_mes_actual": int(polizas_mes),
                        "historial": historicos, "gastos": gastos,
                        "iva_acreditable_hist": [
                            iva.get((h["anio"], h["mes"]), 0)
                            for h in historicos],
                        "extras": extras, "origen": origen,
                        "xml": datos_xml})
            else:
                print(json.dumps(meses[-2:], indent=2, ensure_ascii=False))

        if e.get("bd_nomina"):
            plantilla = extraer_nomina(e["bd_nomina"])
            print(f"  nómina: {len(plantilla)} empleados activos")
            if modo_envio:
                enviar("/api/integracion/contpaq/nomina", {
                    "rfc": rfc, "anio": hoy.year, "mes": hoy.month,
                    "dias": dias_mes, "empleados": plantilla,
                    "tasa_isn": e.getfloat("tasa_isn", fallback=None),
                    "prima_riesgo": e.getfloat("prima_riesgo", fallback=None),
                    "origen": origen})
            else:
                print(json.dumps(plantilla[:3], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.ini")
    ap.add_argument("--descubrir", action="store_true")
    ap.add_argument("--prueba", action="store_true")
    ap.add_argument("--enviar", action="store_true")
    args = ap.parse_args()
    CFG.read(args.config, encoding="utf-8")
    if args.descubrir:
        descubrir()
    elif args.prueba or args.enviar:
        correr(modo_envio=args.enviar)
    else:
        print("Use --descubrir, --prueba o --enviar")
        sys.exit(1)
