# -*- coding: utf-8 -*-
"""
MOTOR DE PREDICCIÓN FISCAL — proyección híbrida a mitad de mes
==============================================================
El problema real: buena parte del ingreso se timbra hasta el ÚLTIMO día del
mes (la factura global al público general), así que a mitad de mes el
acumulado "se ve" mucho más chico de lo que va a cerrar. Este motor corrige
ese sesgo con el propio historial del cliente en CONTPAQi.

CÓMO SE CALCULA (paso a paso, para validarlo contablemente):

  1. FACTOR DE CIERRE (la factura global)
     De cada mes histórico: fracción_cierre = ingreso de los últimos 3 días
     naturales ÷ ingreso total del mes. El factor es el PROMEDIO de esas
     fracciones (6 a 12 meses). Ej.: si en promedio el 39.7% del ingreso se
     timbra en el cierre, el 60.3% se factura "de manera ordinaria".

  2. PROYECCIÓN DEL INGRESO AL CIERRE (híbrida: real + histórico)
     · días ordinarios del mes = días del mes − 3
     · avance ordinario = min(día de hoy, días ordinarios) ÷ días ordinarios
     · ingreso ordinario proyectado = ingreso REAL acumulado ÷ avance
     · INGRESO ESTIMADO AL CIERRE = ordinario proyectado ÷ (1 − factor_cierre)
     Lectura contable: "llevamos $30,000 reales al día 15; al ritmo ordinario
     el mes trae $56,000 facturados fuera del cierre; como históricamente eso
     es el 60.3% del total, el cierre estimado es $92,818".

  3. LÍNEA BASE DE DEDUCCIONES
     Promedio móvil de los gastos/egresos de los últimos 3 meses. El IVA
     acreditable estimado usa el promedio del IVA acreditable histórico si el
     agente lo trae; si no, gastos × 16% (aviso explícito).

  4. ISR e IVA ESTIMADOS — con la calculadora del despacho
     Las bases proyectadas se pasan a fiscal_v2.calcular() con el RÉGIMEN DEL
     CLIENTE (la misma hoja que autoriza Artemisa), sin acumulados previos.
     No hay una fórmula paralela que pueda contradecir a la oficial.

  4-bis. LOS DOS MODOS (la realidad del despacho)
     La mayoría de los clientes NO se captura día con día: sus pólizas entran
     hasta el cierre. A mitad de mes CONTPAQi dice "$0", y eso no significa
     que no vendieron: significa que nadie ha capturado. Por eso:
     · MODO HÍBRIDO — cliente capturado al día: real acumulado + factor de
       cierre (lo de arriba).
     · MODO ESTACIONAL — mes sin capturar: se estima SOLO con historial:
       promedio 50/50 entre el móvil de 3 meses y el MISMO MES del año
       anterior (si existe). Lectura contable: "su último trimestre promedia
       $100,000 y el julio pasado cerró en $120,000 → estimamos $110,000".
     · DETECCIÓN AUTOMÁTICA: si el mes en curso no tiene pólizas, o lo real
       a la fecha es menos del 15% del ritmo que tocaría llevar, el motor
       cambia solo a estacional y LO DICE (no confunde falta de captura con
       caída de ventas).

  4-ter. LAS TRES FUENTES (ninguna es la única verdad)
     · TIMBRADO (XML, tal cual): lo facturado real a la fecha según el ADD.
       ⚠ A mitad de mes suele verse una "PÉRDIDA BRUTAL" que NO es real: los
       gastos (recibidos) fluyen todo el mes, pero la factura GLOBAL del
       público en general se emite hasta el cierre. El motor lo advierte.
     · XML + GLOBAL ESPERADA: proyecta el ritmo de lo timbrado al cierre y le
       repone la global con el factor histórico (misma álgebra híbrida).
       Si la global YA se emitió, proyecta por avance natural del mes.
     · HISTÓRICO CONTPAQi: la híbrida/estacional de pólizas ya existente.
     La SÍNTESIS pondera las fuentes disponibles (default 50% XML corregida,
     50% histórico) y sobre ella corren los escenarios. El contador ve las
     tres por separado: él decide cuál pesa más (hay XML que él sabe que se
     cancelarán, meses atípicos, etc.).

  5. CONFIANZA (desviación estándar)
     CV = desviación estándar muestral de los ingresos mensuales ÷ su media.
     · CV < 15%  → confianza ALTA      · CV < 30% → MEDIA     · resto → BAJA
     El margen se materializa recalculando todo con ingreso × (1 ± CV):
     escenarios pesimista / central / optimista, en pesos.
"""
from datetime import date
from statistics import mean, stdev


def dt_hoy() -> int:
    return date.today().year

from services import fiscal_v2

TASA_IVA = 16.0
DIAS_CIERRE = 3          # los "últimos días" donde cae la factura global
PESO_MISMO_MES = 0.5     # peso del mismo mes del año anterior (estacional)
PESO_XML_SINTESIS = 0.5  # peso de la fuente XML corregida en la síntesis
UMBRAL_CAPTURA = 0.15    # real < 15% del ritmo esperado → mes sin capturar

# Qué campos de la calculadora alimenta la proyección, según el régimen.
# (ingreso, gasto, iva_tras, iva_acred) → nombres de campos de fiscal_v2
MAPA_REGIMEN = {
    "pf_resico": {"ingreso": "ingresos_cobrados"},
    "pm_resico": {"ingreso": "ingresos_cobrados", "gasto": "deducciones_autorizadas"},
    "pf_actividad_empresarial": {"ingreso": "ingresos_16", "gasto": "gastos_pagados"},
    "pm_general": {"ingreso": "ingresos_nominales"},   # requiere coeficiente
    "rif": {"ingreso": "ingresos_16", "gasto": "gastos_generales"},
    "pf_arrendamiento": {"ingreso": "rentas_cobradas_16"},
    "pf_plataformas": {"ingreso": "ingresos_plataforma"},
}


def _proyectar_ingreso(ingreso_real: float, dia: int, dias_mes: int,
                       factor_cierre: float) -> dict:
    ordinarios = max(dias_mes - DIAS_CIERRE, 1)
    avance = min(dia, ordinarios) / ordinarios
    if dia > ordinarios:                       # ya estamos en el cierre
        # lo real ya incluye parte del cierre: prorratear el cierre transcurrido
        cierre_avance = (dia - ordinarios) / DIAS_CIERRE
        avance_total = (1 - factor_cierre) + factor_cierre * cierre_avance
        estimado = ingreso_real / max(avance_total, 1e-9)
        ordinario_proy = estimado * (1 - factor_cierre)
    else:
        ordinario_proy = ingreso_real / max(avance, 1e-9)
        estimado = ordinario_proy / max(1 - factor_cierre, 1e-9)
    return {"avance_ordinario": round(avance, 4),
            "ingreso_ordinario_proyectado": round(ordinario_proy, 2),
            "ingreso_estimado_cierre": round(estimado, 2)}


def _estimar_estacional(historial: list, mes: int, anio: int) -> dict:
    """Estimación SIN datos del mes en curso: móvil 3m + mismo mes año previo."""
    orden = sorted(historial, key=lambda h: (h["anio"], h["mes"]))
    movil3 = round(mean([h["ingreso_total"] for h in orden[-3:]]), 2)
    previo = next((h["ingreso_total"] for h in orden
                   if h["mes"] == mes and h["anio"] == anio - 1), None)
    if previo is not None:
        estimado = round(PESO_MISMO_MES * previo
                         + (1 - PESO_MISMO_MES) * movil3, 2)
        base = (f"50% mismo mes del año anterior (${previo:,.2f}) + "
                f"50% promedio móvil 3 meses (${movil3:,.2f})")
    else:
        estimado, base = movil3, "promedio móvil de los últimos 3 meses"
    return {"ingreso_estimado_cierre": estimado, "base_estacional": base,
            "movil_3m": movil3, "mismo_mes_anio_anterior": previo}


def _isr_iva(regimen: str, mes: int, ingreso: float, gasto: float,
             iva_acreditable: float, extras: dict) -> dict:
    """Corre la calculadora oficial con las bases proyectadas."""
    mapa = MAPA_REGIMEN.get(regimen)
    iva_tras = round(ingreso * TASA_IVA / 100, 2)
    if not mapa:
        return {"calculado_con": None, "total_estimado": None,
                "iva_trasladado_estimado": iva_tras,
                "iva_acreditable_estimado": iva_acreditable,
                "iva_estimado": round(max(iva_tras - iva_acreditable, 0), 2),
                "nota": f"El régimen '{regimen}' no está en el mapeo de "
                        f"proyección: se reportan solo las bases y el IVA."}
    datos = {mapa["ingreso"]: ingreso}
    if "gasto" in mapa:
        datos[mapa["gasto"]] = gasto
    campos = {c for c, _ in fiscal_v2.CAMPOS.get(regimen, [])}
    if "iva_trasladado" in campos:
        datos["iva_trasladado"] = iva_tras
    if "iva_acreditable" in campos:
        datos["iva_acreditable"] = iva_acreditable
    for k, v in (extras or {}).items():         # p. ej. coeficiente_utilidad
        if k in campos:
            datos[k] = v
    res = fiscal_v2.calcular(regimen, mes, datos, {})
    return {"calculado_con": fiscal_v2.REGIMENES.get(regimen, regimen),
            "total_estimado": res.get("total_a_pagar"),
            "iva_trasladado_estimado": iva_tras,
            "iva_acreditable_estimado": iva_acreditable,
            "iva_estimado": round(max(iva_tras - iva_acreditable, 0), 2),
            "nota": "Periodo aislado: sin acumulados previos ni saldos a "
                    "favor arrastrados; el cálculo definitivo los aplicará."}


def _fuente_xml(xml: dict, dia: int, dias_mes: int,
                factor_cierre: float) -> tuple[dict, dict | None]:
    """
    xml = {"ingresos_mtd": $, "egresos_mtd": $, "global_emitida": bool}
    Devuelve (xml_puro, xml_corregida). La corregida repone la global.
    """
    ing, egr = float(xml.get("ingresos_mtd") or 0), float(xml.get("egresos_mtd") or 0)
    global_ya = bool(xml.get("global_emitida"))
    puro = {"ingresos_mtd": round(ing, 2), "egresos_mtd": round(egr, 2),
            "resultado_a_la_fecha": round(ing - egr, 2),
            "aviso": (None if global_ya or ing >= egr else
                      "Este resultado NO refleja la realidad: la factura "
                      "global del público en general aún no se emite; los "
                      "gastos fluyen todo el mes y los ingresos se concentran "
                      "en el cierre.")}
    if ing <= 0:
        return puro, None
    if global_ya:
        avance = max(dia / dias_mes, 1e-9)     # la global ya fluyó: ritmo total
        ing_cierre = round(ing / avance, 2)
        base = "XML proyectados por avance natural (la global ya se emitió)"
    else:
        ordinarios = max(dias_mes - DIAS_CIERRE, 1)
        avance = min(dia, ordinarios) / ordinarios
        ing_proy = ing / max(avance, 1e-9)
        ing_cierre = round(ing_proy / max(1 - factor_cierre, 1e-9), 2)
        base = (f"ritmo timbrado proyectado ÷ (1 − factor de global "
                f"{round(factor_cierre*100,2)}%)")
    egr_cierre = round(egr / max(dia / dias_mes, 1e-9), 2)
    return puro, {"ingreso_estimado_cierre": ing_cierre,
                  "egresos_estimados_cierre": egr_cierre,
                  "utilidad_estimada": round(ing_cierre - egr_cierre, 2),
                  "base": base}


def _precarga_calculadora(regimen: str, ingreso: float, gasto: float,
                          iva_acred: float, extras: dict | None) -> dict | None:
    """
    Traduce el escenario central a los RENGLONES del formulario de la
    calculadora, para "moverle desde ahí": el ingreso cae en el campo de
    ingresos del régimen; el gasto (que la predicción solo conoce como línea
    base global) cae en 'Otros gastos de operación' para que el contador lo
    reparta; el IVA se precarga con el trasladado teórico y el acreditable
    histórico. Es un punto de partida, no un cálculo.
    """
    mapa = MAPA_REGIMEN.get(regimen)
    if not mapa:
        return None
    campos = ({c for c, _ in fiscal_v2.CAMPOS.get(regimen, [])}
              | {c for c, _ in fiscal_v2.CAMPOS_CAPTURA.get(regimen, [])})
    pre = {mapa["ingreso"]: round(ingreso, 2)}
    if "gasto" in mapa and gasto:
        destino = mapa["gasto"]
        if destino in fiscal_v2.DESGLOSE_CAMPOS:
            destino = fiscal_v2.DESGLOSE_CAMPOS[destino][-1][0]
        pre[destino] = round(gasto, 2)
    if "iva_trasladado" in campos:
        pre["iva_trasladado"] = round(ingreso * TASA_IVA / 100, 2)
    if "iva_acreditable" in campos and iva_acred:
        pre["iva_acreditable"] = round(iva_acred, 2)
    for k, v in (extras or {}).items():
        if k in campos:
            pre[k] = v
    return pre


def predecir(historial: list, gastos: list, ingreso_real_mtd: float,
             dia: int, dias_mes: int, mes: int, regimen: str,
             iva_acreditable_hist: list | None = None,
             extras: dict | None = None,
             anio: int | None = None,
             polizas_mes_actual: int | None = None,
             modo: str = "auto",
             xml: dict | None = None) -> dict:
    """
    historial: [{"mes": 1..12, "anio": aaaa, "ingreso_total": x,
                 "ingreso_ultimos_3_dias": y}, ...]  (6 a 12 meses)
    gastos:    [{"mes":…, "anio":…, "gasto_total": z}, ...]
    ingreso_real_mtd: ingreso real acumulado del mes en curso a la fecha.
    """
    if len(historial) < 3:
        raise ValueError("Se necesitan al menos 3 meses de historial")

    # 1) Factor de cierre (la factura global)
    fracciones = [h["ingreso_ultimos_3_dias"] / h["ingreso_total"]
                  for h in historial if h.get("ingreso_total")]
    factor_cierre = round(mean(fracciones), 4)

    # 2) ¿Con qué modo se proyecta? La realidad del despacho: la mayoría se
    #    captura hasta el cierre, así que "$0 a la fecha" casi nunca es caída
    #    de ventas: es falta de captura.
    estacional = _estimar_estacional(historial, mes, (anio or 0) or dt_hoy())
    aviso_captura = None
    modo_final = modo
    if modo == "auto":
        ordinarios = max(dias_mes - DIAS_CIERRE, 1)
        avance = min(dia, ordinarios) / ordinarios
        ritmo_esperado = estacional["ingreso_estimado_cierre"] * \
            (1 - factor_cierre) * avance
        if (polizas_mes_actual == 0) or ingreso_real_mtd <= 0:
            modo_final = "estacional"
            aviso_captura = ("El mes en curso no tiene pólizas capturadas en "
                             "CONTPAQi: la proyección es estacional (historial).")
        elif dia >= 5 and ritmo_esperado > 0 and \
                ingreso_real_mtd < UMBRAL_CAPTURA * ritmo_esperado:
            modo_final = "estacional"
            aviso_captura = (f"Lo capturado a la fecha (${ingreso_real_mtd:,.2f}) "
                             f"está muy por debajo del ritmo histórico "
                             f"(~${ritmo_esperado:,.2f} al día {dia}): lo más "
                             f"probable es que el mes aún no se capture; la "
                             f"proyección es estacional.")
        else:
            modo_final = "hibrida"

    if modo_final == "estacional":
        proy = {"avance_ordinario": None, "ingreso_ordinario_proyectado": None,
                "ingreso_estimado_cierre": estacional["ingreso_estimado_cierre"],
                "base_estacional": estacional["base_estacional"],
                "movil_3m": estacional["movil_3m"],
                "mismo_mes_anio_anterior": estacional["mismo_mes_anio_anterior"]}
    else:
        proy = _proyectar_ingreso(ingreso_real_mtd, dia, dias_mes, factor_cierre)

    # 3) Línea base de deducciones (promedio móvil 3 meses)
    ult3 = sorted(gastos, key=lambda g: (g["anio"], g["mes"]))[-3:]
    gasto_base = round(mean([g["gasto_total"] for g in ult3]), 2) if ult3 else 0.0
    if iva_acreditable_hist:
        iva_acred = round(mean(iva_acreditable_hist[-3:]), 2)
        origen_iva = "promedio del IVA acreditable real (últimos 3 meses)"
    else:
        iva_acred = round(gasto_base * TASA_IVA / 100, 2)
        origen_iva = ("gastos × 16% (aproximación: no todo gasto lleva IVA; "
                      "el agente puede traer el IVA acreditable real)")

    # 4) Confianza por desviación estándar de los ingresos históricos
    ingresos_hist = [h["ingreso_total"] for h in historial]
    sigma = round(stdev(ingresos_hist), 2) if len(ingresos_hist) > 1 else 0.0
    cv = round(sigma / mean(ingresos_hist), 4) if mean(ingresos_hist) else 0.0
    confianza = "alta" if cv < 0.15 else "media" if cv < 0.30 else "baja"

    # 4-ter) Las tres fuentes y la síntesis
    fuentes = {"historico": {"modo": modo_final, **proy,
                             "aviso": aviso_captura}}
    if xml:
        xml_puro, xml_corr = _fuente_xml(xml, dia, dias_mes, factor_cierre)
        fuentes["xml_puro"] = xml_puro
        if xml_corr:
            fuentes["xml_corregida"] = xml_corr
    if "xml_corregida" in fuentes:
        w = PESO_XML_SINTESIS
        ing_sintesis = round(w * fuentes["xml_corregida"]["ingreso_estimado_cierre"]
                             + (1 - w) * proy["ingreso_estimado_cierre"], 2)
        base_sintesis = (f"{round(w*100)}% XML corregida + "
                         f"{round((1-w)*100)}% histórico CONTPAQi")
    else:
        ing_sintesis = proy["ingreso_estimado_cierre"]
        base_sintesis = "solo histórico CONTPAQi (sin fuente XML)"
    sintesis = {"ingreso_estimado_cierre": ing_sintesis, "base": base_sintesis}

    # 5) ISR/IVA con la calculadora oficial, en tres escenarios (la síntesis)
    escenarios = {}
    for nombre, mult in (("pesimista", 1 - cv), ("central", 1.0),
                         ("optimista", 1 + cv)):
        ing = round(ing_sintesis * mult, 2)
        calc = _isr_iva(regimen, mes, ing, gasto_base, iva_acred, extras or {})
        escenarios[nombre] = {"ingreso": ing,
                              "utilidad_proyectada": round(ing - gasto_base, 2),
                              **calc}

    return {
        "modo_proyeccion": modo_final,
        "aviso_captura": aviso_captura,
        "fuentes": fuentes,
        "sintesis": sintesis,
        "factor_cierre": factor_cierre,
        "factor_cierre_pct": round(factor_cierre * 100, 2),
        "meses_analizados": len(historial),
        **proy,
        "gasto_linea_base": gasto_base,
        "origen_iva_acreditable": origen_iva,
        "desviacion_estandar_ingresos": sigma,
        "coeficiente_variacion_pct": round(cv * 100, 2),
        "confianza": confianza,
        "ingreso_sintesis": ing_sintesis,
        "precarga_calculadora": _precarga_calculadora(
            regimen, ing_sintesis, gasto_base, iva_acred, extras),
        "escenarios": escenarios,
        "leyenda": ("Proyección orientativa construida con el historial de "
                    "CONTPAQi y calculada con la misma hoja fiscal del "
                    "despacho. El pago definitivo es el que elabore y "
                    "autorice su contador al cierre."),
    }
