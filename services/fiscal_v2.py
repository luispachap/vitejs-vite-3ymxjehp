# -*- coding: utf-8 -*-
"""
MOTOR FISCAL v2 — Réplica de los papeles de trabajo del despacho
================================================================
Cada régimen reproduce renglón por renglón el formato de Excel que usan
los contadores de P&A, con las constantes AUTO-RELLENADAS:

  pf_actividad_empresarial  PAPEL_DE_TRABAJO_ACTIVIDAD_EMPRESARIAL_Y_PROF_PF
  pf_resico                 RESICO_PERSONA_FISICA (tasa Art. 113-E automática)
  rif                       FORMATO_DE_CALCULO_DE_IMPUESTOS_RIF (bimestral,
                            factor de IVA y reducción por años)
  pm_general                PAPEL_DE_TRABAJO_PERSONA_MORAL_REGIMEN_GENERAL
                            (coeficiente de utilidad, Art. 14 LISR)
  pm_resico                 PAPEL_DE_TRABAJO_PERSONA_MORAL_RESICO (flujo)

Como en las hojas, el CONTADOR CAPTURA SOLO EL MES: el sistema acumula con
los meses anteriores guardados en la base (contexto), arrastra el saldo a
favor de IVA del periodo anterior y aplica tarifas/tasas oficiales.

El resultado es una "hoja" genérica (secciones → renglones) que el
frontend pinta idéntica al papel de trabajo, para cualquier régimen.

⚠ CONSTANTES A VERIFICAR CADA EJERCICIO (Anexo 8 RMF / leyes vigentes):
TARIFA_ISR_MENSUAL, TASAS_RESICO_PF, TASA_ISR_PM, TASA_IVA, tarifa RIF.
"""

ANIO_TARIFA = 2025

# Tarifa MENSUAL Art. 96 LISR (vigente desde 2023)
TARIFA_ISR_MENSUAL = [
    (0.01,       746.04,    0.00,      1.92),
    (746.05,     6332.05,   14.32,     6.40),
    (6332.06,    11128.01,  371.83,    10.88),
    (11128.02,   12935.82,  893.63,    16.00),
    (12935.83,   15487.71,  1182.88,   17.92),
    (15487.72,   31236.49,  1640.18,   21.36),
    (31236.50,   49233.00,  5004.12,   23.52),
    (49233.01,   93993.90,  9236.89,   30.00),
    (93993.91,   125325.20, 22665.17,  32.00),
    (125325.21,  375975.61, 32691.18,  34.00),
    (375975.62,  None,      117912.32, 35.00),
]

# Tasas mensuales RESICO Persona Física, Art. 113-E LISR (ingresos del mes)
TASAS_RESICO_PF = [
    (25000.00,   1.00),
    (50000.00,   1.10),
    (83333.33,   1.50),
    (208333.33,  2.00),
    (3500000.00, 2.50),  # tope: hasta 3.5 MDP anuales
]

TASA_ISR_PM = 30.0        # Art. 9 LISR
TASA_IVA = 16.0

from services.fiscal_catalogo import (CAMPOS_EXTRA, ES_ANUAL,
                                      FACTOR_PIRAMIDACION, PERIODICIDAD,
                                      REGIMENES_EXTRA, TARIFA_ISR_ANUAL,
                                      TASAS_RESICO_PF_ANUAL,
                                      TASA_DIVIDENDOS_ADICIONAL,
                                      TIPO_PERSONA_DE_REGIMEN,
                                      TOPE_DEDUCCIONES_PERSONALES_PCT,
                                      TOPE_DEDUCCIONES_PERSONALES_UMA,
                                      UMA_ANUAL, UMA_DIARIA)

REGIMENES = {
    "pf_actividad_empresarial": "PF · Actividad Empresarial y Profesional",
    "pf_resico": "PF · RESICO",
    "rif": "PF · RIF (bimestral)",
    "pm_general": "PM · Régimen General",
    "pm_resico": "PM · RESICO",
}
REGIMENES.update(REGIMENES_EXTRA)
# Compatibilidad con cálculos guardados por el motor v1
ALIAS = {"persona_fisica": "pf_actividad_empresarial",
         "persona_moral": "pm_general"}

# Campos de captura por régimen (el frontend arma el formulario con esto)
CAMPOS = {
    "pf_actividad_empresarial": [
        ("ingresos_16", "Ingresos 16%"), ("ingresos_0", "Ingresos 0%"),
        ("otros_ingresos", "Otros ingresos"),
        ("descuentos_venta", "Descuentos sobre venta"),
        ("compras_contado", "Compras de contado"),
        ("gastos_pagados", "Total gastos pagados"),
        ("no_deducibles", "No deducibles"),
        ("gastos_financieros", "Gastos financieros"),
        ("deduccion_inversiones", "Deducción de inversiones"),
        ("descuentos_compras", "Descuentos sobre compras"),
        ("perdidas_anteriores", "P.F.E.A.P.A. (pérdidas por amortizar)"),
        ("pagos_provisionales", "Pagos provisionales anteriores"),
        ("iva_trasladado", "IVA efectivamente trasladado (auto 16% editable)"),
        ("iva_acreditable", "IVA efectivamente acreditable"),
        ("iva_retenido", "IVA retenido al contribuyente"),
        ("isr_ret_salarios", "ISR retenido por salarios"),
        ("subsidio_empleo", "Subsidio para el empleo"),
        ("recargos", "Recargos"), ("actualizacion", "Actualización"),
        ("spe", "SPE"), ("compensaciones", "Compensaciones"),
    ],
    "pf_resico": [
        ("ingresos_cobrados", "Ingresos cobrados del mes"),
        ("retencion_isr_resico", "Retención de ISR RESICO (1.25%)"),
        ("iva_trasladado", "IVA efectivamente trasladado"),
        ("iva_acreditable", "IVA efectivamente acreditable"),
        ("iva_retenido", "IVA retenido"),
        ("ieps_trasladado", "IEPS trasladado"),
        ("ieps_acreditable", "IEPS acreditable"),
        ("isr_ret_salarios", "ISR retenido por salarios"),
        ("spe", "SPE"), ("compensaciones", "Compensaciones"),
    ],
    "rif": [
        ("ingresos_publico_general", "Ingresos público en general"),
        ("ingresos_16", "Ingresos al 16%"),
        ("compras_16", "Compras al 16%"), ("compras_0", "Compras al 0%"),
        ("descuentos_compras", "Descuento s/compra"),
        ("compra_activos", "Compra de activos fijos"),
        ("gastos_generales", "Gastos generales"),
        ("gastos_financieros", "Gastos financieros"),
        ("no_deducibles", "No deducibles"),
        ("perdidas_anteriores", "Pérdida de ejercicios anteriores"),
        ("ptu_pagada", "PTU pagada"),
        ("porcentaje_reduccion", "% de reducción RIF (por años, ej. 100)"),
        ("iva_acreditable", "IVA acreditable (antes de factor)"),
        ("tasa_iva_publico_general", "Tasa IVA público en general % (sector)"),
        ("isr_ret_salarios", "ISR retenido por salarios"),
        ("subsidio_empleo", "Subsidio para el empleo"),
        ("spe", "SPE"),
    ],
    "pm_general": [
        ("ingresos_nominales", "Ingresos nominales del mes"),
        ("inventario_acumulable", "Inventario acumulable del mes"),
        ("coeficiente_utilidad", "Coeficiente de utilidad (ej. 0.0824)"),
        ("ptu_pagada_periodo", "PTU pagada del periodo (may-dic)"),
        ("pagos_provisionales", "Pagos provisionales anteriores"),
        ("iva_trasladado", "IVA efectivamente trasladado"),
        ("iva_acreditable", "IVA efectivamente acreditable"),
        ("iva_retenido_mes", "IVA retenido del mes"),
        ("iva_retenido_pagado", "IVA retenido pagado"),
        ("ieps_trasladado", "IEPS trasladado"),
        ("ieps_acreditable", "IEPS acreditable"),
        ("iva_retenciones", "IVA retenciones (a enterar)"),
        ("isr_ret_honorarios", "ISR retenido honorarios"),
        ("isr_ret_salarios", "ISR retenido salarios"),
        ("isr_resico_retenido", "ISR RESICO retenido"),
        ("spe", "SPE"), ("compensaciones", "Compensaciones"),
    ],
    "pm_resico": [
        ("ingresos_16", "Ingresos cobrados tasa 16%"),
        ("ingresos_0", "Ingresos cobrados tasa 0%"),
        ("otros_ingresos", "Otros ingresos"),
        ("descuentos_venta", "Descuentos sobre venta"),
        ("compras_pagadas", "Compras pagadas"),
        ("gastos_pagados", "Total gastos pagados"),
        ("no_deducibles", "No deducibles"),
        ("gastos_financieros", "Gastos financieros pagados"),
        ("deduccion_inversiones", "Deducción de inversiones"),
        ("descuentos_compras", "Descuentos sobre compras"),
        ("perdidas_anteriores", "P.F.E.A.P.A."),
        ("pagos_provisionales", "Pagos provisionales anteriores"),
        ("iva_trasladado", "IVA efectivamente trasladado"),
        ("iva_acreditable", "IVA efectivamente acreditable"),
        ("iva_retenido_mes", "IVA retenido del mes"),
        ("iva_retenido_pagado", "IVA retenido pagado"),
        ("ieps_trasladado", "IEPS trasladado"),
        ("ieps_acreditable", "IEPS acreditable"),
        ("iva_retenciones", "IVA retenciones (a enterar)"),
        ("isr_ret_honorarios", "ISR retenido honorarios"),
        ("isr_ret_salarios", "ISR retenido salarios"),
        ("isr_resico_retenido", "ISR RESICO retenido"),
        ("spe", "SPE"), ("compensaciones", "Compensaciones"),
    ],
}


CAMPOS.update(CAMPOS_EXTRA)

# Regímenes agrupados para los selectores de la interfaz
GRUPOS_REGIMEN = {
    "Personas físicas": [
        "pf_sueldos_salarios", "pf_actividad_empresarial", "pf_resico", "rif",
        "pf_plataformas", "pf_arrendamiento", "pf_agape", "pf_enajenacion",
        "pf_adquisicion", "pf_intereses", "pf_dividendos", "pf_demas_ingresos",
    ],
    "Personas morales": [
        "pm_general", "pm_resico", "pm_no_lucrativas", "pm_coordinados",
        "pm_agape",
    ],
    "Declaraciones anuales": [
        "anual_pf_general", "anual_pf_resico", "anual_pm_general",
        "anual_pm_resico",
    ],
}


def _r(x):
    return round((x or 0) + 1e-9, 2)


def normalizar_regimen(regimen: str) -> str:
    regimen = ALIAS.get(regimen, regimen)
    if regimen not in REGIMENES:
        raise ValueError(f"Régimen no soportado: {regimen}")
    return regimen


def renglon_tarifa(base: float, tarifa) -> dict:
    """Localiza el renglón (límite inferior, cuota fija, tasa) para la base."""
    base = max(0.0, base)
    for li, ls, cf, tasa in tarifa:
        if base >= li and (ls is None or base <= ls):
            exc = _r(base - li)
            return {"limite_inferior": li, "excedente": exc,
                    "tasa_pct": tasa, "impuesto_marginal": _r(exc * tasa / 100),
                    "cuota_fija": cf,
                    "impuesto_causado": _r(_r(exc * tasa / 100) + cf)}
    return {"limite_inferior": 0, "excedente": 0, "tasa_pct": 0,
            "impuesto_marginal": 0, "cuota_fija": 0, "impuesto_causado": 0}


def tarifa_elevada(mes: int, factor: int = 1) -> list:
    """Tarifa mensual elevada al periodo (mes) o al bimestre (factor=2 en RIF)."""
    n = mes * factor if factor == 1 else factor
    return [(_r(li * n), (_r(ls * n) if ls else None), _r(cf * n), tasa)
            for li, ls, cf, tasa in TARIFA_ISR_MENSUAL]


def tasa_resico_pf(ingresos_mes: float) -> float:
    for tope, tasa in TASAS_RESICO_PF:
        if ingresos_mes <= tope:
            return tasa
    return TASAS_RESICO_PF[-1][1]


# ---------------------------------------------------------------------------
# CAPTURA DESGLOSADA: el contador NO debe sumar afuera para luego meter un
# total. Los campos "gordos" se parten en los renglones del papel de trabajo
# real; el sistema los suma, y la fila del total lleva su cédula desplegable.
# ---------------------------------------------------------------------------
DESGLOSE_CAMPOS = {
    "gastos_pagados": [
        ("gastos_venta", "Gastos de venta"),
        ("gastos_admon", "Gastos de administración"),
        ("gastos_operacion_otros", "Otros gastos de operación"),
    ],
    "gastos_generales": [
        ("gastos_venta", "Gastos de venta"),
        ("gastos_admon", "Gastos de administración"),
        ("gastos_operacion_otros", "Otros gastos de operación"),
    ],
}


def _campos_captura(regimen):
    """CAMPOS con los agregados reemplazados por sus renglones, in situ."""
    salida = []
    for k, etq in CAMPOS.get(regimen, []):
        if k in DESGLOSE_CAMPOS:
            salida.extend(DESGLOSE_CAMPOS[k])
        else:
            salida.append((k, etq))
    return salida


CAMPOS_CAPTURA = {r: _campos_captura(r) for r in CAMPOS}


# ---------------------------------------------------------------------------
# Constructores de "hoja" (lo que el frontend pinta como el papel de trabajo)
# ---------------------------------------------------------------------------

def _fila(concepto, valor, operador="", clave=None, fuerte=False, acumulado=None,
          detalle=None):
    f = {"concepto": concepto, "valor": _r(valor) if isinstance(valor, (int, float)) else valor,
         "operador": operador, "fuerte": fuerte}
    if clave:
        f["clave"] = clave
    if acumulado is not None:
        f["acumulado"] = _r(acumulado)
    if detalle:
        f["detalle"] = detalle          # cédula desplegable: cómo salió el número
    return f


def _resumen(pares, restas=()):
    filas, total = [], 0.0
    for etiqueta, valor in pares:
        signo = -1 if etiqueta in restas else 1
        total += signo * (valor or 0)
        filas.append(_fila(etiqueta, valor, "(-)" if signo < 0 else ""))
    filas.append(_fila("NETO A PAGAR", max(0.0, _r(total)), "(=)", fuerte=True))
    return filas, max(0.0, _r(total)), _r(total)


def _bloque_iva_flujo(d, ctx, con_retenidos_pm=False):
    """IVA como en los papeles: a cargo del mes − saldo a favor anterior."""
    favor_ant = ctx.get("iva_favor_anterior", 0.0)
    if con_retenidos_pm:
        a_cargo = _r(d("iva_trasladado") - d("iva_acreditable")
                     + d("iva_retenido_mes") - d("iva_retenido_pagado"))
        filas = [
            _fila("IVA efectivamente trasladado", d("iva_trasladado")),
            _fila("IVA efectivamente acreditable", d("iva_acreditable"), "(-)"),
            _fila("IVA retenido del mes", d("iva_retenido_mes"), "(+)"),
            _fila("IVA retenido pagado", d("iva_retenido_pagado"), "(-)"),
        ]
    else:
        a_cargo = _r(d("iva_trasladado") - d("iva_acreditable") - d("iva_retenido"))
        filas = [
            _fila("IVA efectivamente trasladado", d("iva_trasladado")),
            _fila("IVA efectivamente acreditable", d("iva_acreditable"), "(-)"),
            _fila("IVA retenido al contribuyente", d("iva_retenido"), "(-)"),
        ]
    neto = _r(a_cargo - favor_ant)
    filas += [_fila("IVA A PAGAR", a_cargo, "(=)"),
              _fila("IVA a favor de periodos anteriores", favor_ant, "(-)",
                    clave="auto"),
              _fila("IVA NETO POR PAGAR", neto, "(=)", fuerte=True)]
    return filas, max(0.0, neto), neto  # neto<0 => saldo a favor que arrastra


def _seccion_ieps(d):
    a_cargo = _r(d("ieps_trasladado") - d("ieps_acreditable"))
    return ([_fila("IEPS trasladado", d("ieps_trasladado")),
             _fila("IEPS acreditable", d("ieps_acreditable"), "(-)"),
             _fila("IEPS A CARGO", max(0.0, a_cargo), "(=)", fuerte=True)],
            max(0.0, a_cargo))


# ---------------------------------------------------------------------------
# CÁLCULO POR RÉGIMEN
# ---------------------------------------------------------------------------

def _calcular_nucleo(regimen: str, mes: int, datos: dict, contexto: dict | None = None) -> dict:
    """
    datos: SOLO el mes (como captura el contador en el papel).
    contexto: {"acum": {campo: suma_meses_anteriores},
               "iva_favor_anterior": float,
               "pagos_provisionales_sugeridos": float}
    """
    regimen = normalizar_regimen(regimen)
    ctx = contexto or {}
    acum_ant = ctx.get("acum", {})
    d = lambda k: float(datos.get(k) or 0)
    ac = lambda k: _r(d(k) + float(acum_ant.get(k) or 0))  # acumulado ejercicio

    # --- Declaraciones ANUALES (no acumulan meses: son del ejercicio) ---
    if ES_ANUAL(regimen):
        anual = _calcular_anual(regimen, datos, ctx)
        if anual:
            anual.update({"regimen": regimen,
                          "regimen_nombre": REGIMENES[regimen],
                          "mes": mes, "anio_tarifa": ANIO_TARIFA,
                          "es_anual": True})
            return anual

    # --- Regímenes del catálogo extendido ---
    extra = _calcular_extra(regimen, mes, datos, ctx, acum_ant)
    if extra:
        secciones_x, resumen_x, total_x, iva_x, isr_x = extra
        return {"regimen": regimen, "regimen_nombre": REGIMENES[regimen],
                "mes": mes, "anio_tarifa": ANIO_TARIFA,
                "secciones": secciones_x, "resumen": resumen_x,
                "total_a_pagar": total_x, "iva_neto_crudo": _r(iva_x),
                "total_isr_periodo": _r(isr_x),
                "periodicidad": PERIODICIDAD.get(regimen, "mensual")}

    secciones = []

    if regimen in ("pf_actividad_empresarial", "pm_resico"):
        ingresos_m = _r(d("ingresos_16") + d("ingresos_0") + d("otros_ingresos")
                        - d("descuentos_venta"))
        ingresos_a = _r(ac("ingresos_16") + ac("ingresos_0") + ac("otros_ingresos")
                        - ac("descuentos_venta"))
        compras = "compras_contado" if regimen == "pf_actividad_empresarial" else "compras_pagadas"
        deduc_m = _r(d(compras) + d("gastos_pagados") - d("no_deducibles")
                     + d("gastos_financieros") + d("deduccion_inversiones")
                     - d("descuentos_compras"))
        deduc_a = _r(ac(compras) + ac("gastos_pagados") - ac("no_deducibles")
                     + ac("gastos_financieros") + ac("deduccion_inversiones")
                     - ac("descuentos_compras"))
        utilidad = _r(ingresos_a - deduc_a)
        base = _r(max(0.0, utilidad - d("perdidas_anteriores")))

        isr_filas = [
            _fila("TOTAL INGRESOS", ingresos_m, "", acumulado=ingresos_a, fuerte=True),
            _fila("TOTAL DEDUCCIONES", deduc_m, "(-)", acumulado=deduc_a, fuerte=True),
            _fila("UTILIDAD FISCAL", _r(ingresos_m - deduc_m), "(=)",
                  acumulado=utilidad),
            _fila("P.F.E.A.P.A.", d("perdidas_anteriores"), "(-)"),
            _fila("Base para impuesto", base, "(=)"),
        ]
        if regimen == "pf_actividad_empresarial":
            t = renglon_tarifa(base, tarifa_elevada(mes))
            causado = t["impuesto_causado"]
            isr_filas += [
                _fila("Límite inferior", t["limite_inferior"], "(-)", clave="auto"),
                _fila("Excedente del límite inferior", t["excedente"], "(=)"),
                _fila("Tasa de impuesto %", t["tasa_pct"], "(×)", clave="auto"),
                _fila("Impuesto marginal", t["impuesto_marginal"], "(=)"),
                _fila("Cuota fija", t["cuota_fija"], "(+)", clave="auto"),
            ]
        else:
            causado = _r(base * TASA_ISR_PM / 100)
            isr_filas.append(_fila("Tasa Art. 9 LISR %", TASA_ISR_PM, "(×)",
                                   clave="auto"))
        pagos = d("pagos_provisionales") or ctx.get("pagos_provisionales_sugeridos", 0)
        isr_pagar = _r(max(0.0, causado - pagos))
        isr_filas += [_fila("Impuesto causado", causado, "(=)"),
                      _fila("Pagos provisionales", pagos, "(-)"),
                      _fila("ISR POR PAGAR", isr_pagar, "(=)", fuerte=True)]
        secciones.append({"titulo": "IMPUESTO SOBRE LA RENTA", "filas": isr_filas})

        if regimen == "pf_actividad_empresarial" and not d("iva_trasladado"):
            datos = dict(datos); datos["iva_trasladado"] = _r(d("ingresos_16") * TASA_IVA / 100)
            d = lambda k: float(datos.get(k) or 0)
        iva_filas, iva_pagar, iva_neto_crudo = _bloque_iva_flujo(
            d, ctx, con_retenidos_pm=(regimen == "pm_resico"))
        secciones.append({"titulo": "IMPUESTO AL VALOR AGREGADO", "filas": iva_filas})

        if regimen == "pm_resico":
            ieps_filas, ieps = _seccion_ieps(d)
            secciones.append({"titulo": "IEPS", "filas": ieps_filas})
            pares = [("ISR Persona Moral", isr_pagar), ("IVA", iva_pagar),
                     ("IEPS", ieps), ("IVA retenciones", d("iva_retenciones")),
                     ("ISR retenido honorarios", d("isr_ret_honorarios")),
                     ("ISR retenido salarios", d("isr_ret_salarios")),
                     ("ISR RESICO", d("isr_resico_retenido")),
                     ("SPE", d("spe")), ("Compensaciones", d("compensaciones"))]
            resumen, total, _t = _resumen(pares, restas=("SPE", "Compensaciones"))
        else:
            ret_sal = _r(d("isr_ret_salarios") - d("subsidio_empleo"))
            pares = [("ISR por pagar", isr_pagar), ("IVA a pagar", iva_pagar),
                     ("ISR ret. salarios (neto de subsidio)", max(0.0, ret_sal)),
                     ("Recargos", d("recargos")), ("Actualización", d("actualizacion")),
                     ("SPE", d("spe")), ("Compensaciones", d("compensaciones"))]
            resumen, total, _t = _resumen(pares, restas=("SPE", "Compensaciones"))

    elif regimen == "pf_resico":
        ingresos = d("ingresos_cobrados")
        tasa = tasa_resico_pf(ingresos)
        isr = _r(ingresos * tasa / 100)
        neto_isr = _r(max(0.0, isr - d("retencion_isr_resico")))
        _ced_resico = [{"concepto": ("→ hasta $" + f"{tope:,.2f}" if tope else "→ en adelante")
                                    + " al mes", "valor": f"{tx}%",
                        "operador": "•" if tx == tasa else ""}
                       for tope, tx in TASAS_RESICO_PF]
        secciones.append({"titulo": "ISR RESICO (Art. 113-E)", "filas": [
            _fila("Ingresos cobrados", ingresos),
            _fila("Tasa aplicable %", tasa, "(×)", clave="auto",
                  detalle=[{"concepto": f"Ingresos del mes: ${ingresos:,.2f}",
                            "valor": "", "operador": ""}] + _ced_resico),
            _fila("ISR a pagar", isr, "(=)"),
            _fila("Retención de ISR RESICO", d("retencion_isr_resico"), "(-)"),
            _fila("NETO ISR", neto_isr, "(=)", fuerte=True)]})
        iva_filas, iva_pagar, _c = _bloque_iva_flujo(d, ctx)
        secciones.append({"titulo": "IMPUESTO AL VALOR AGREGADO", "filas": iva_filas})
        ieps_filas, ieps = _seccion_ieps(d)
        secciones.append({"titulo": "IEPS", "filas": ieps_filas})
        isr_pagar = neto_isr
        pares = [("ISR RESICO", neto_isr), ("IVA", iva_pagar), ("IEPS", ieps),
                 ("ISR ret. por salarios", d("isr_ret_salarios")),
                 ("SPE", d("spe")), ("Compensaciones", d("compensaciones"))]
        resumen, total, _t = _resumen(pares, restas=("SPE", "Compensaciones"))
        iva_neto_crudo = iva_pagar

    elif regimen == "rif":
        total_ing = _r(d("ingresos_publico_general") + d("ingresos_16"))
        factor = round(d("ingresos_16") / total_ing, 4) if total_ing else 0.0
        iva_acred_real = _r(d("iva_acreditable") * factor)
        iva_no_acred = _r(d("iva_acreditable") - iva_acred_real)
        compras = _r(d("compras_16") + d("compras_0") - d("descuentos_compras"))
        deducciones = _r(compras + d("compra_activos") + d("gastos_generales")
                         + d("gastos_financieros") + iva_no_acred - d("no_deducibles"))
        utilidad = _r(total_ing - deducciones)
        base = _r(max(0.0, utilidad - d("perdidas_anteriores") - d("ptu_pagada")))
        t = renglon_tarifa(base, tarifa_elevada(mes, factor=2))  # BIMESTRAL
        reduccion = min(100.0, max(0.0, d("porcentaje_reduccion")))
        isr_cargo = t["impuesto_causado"]
        isr_pagar = _r(isr_cargo * (1 - reduccion / 100))
        secciones.append({"titulo": "ISR RIF (bimestre)", "filas": [
            _fila("Ingresos público en general", d("ingresos_publico_general")),
            _fila("Ingresos al 16%", d("ingresos_16"), "(+)"),
            _fila("TOTAL INGRESOS", total_ing, "(=)", fuerte=True),
            _fila("TOTAL DEDUCCIONES (incluye IVA no acreditable)", deducciones, "(-)"),
            _fila("UTILIDAD FISCAL", utilidad, "(=)"),
            _fila("Pérdidas ejercicios anteriores", d("perdidas_anteriores"), "(-)"),
            _fila("PTU", d("ptu_pagada"), "(-)"),
            _fila("BASE PARA IMPUESTO", base, "(=)"),
            _fila("Límite inferior (bimestral)", t["limite_inferior"], "(-)", clave="auto"),
            _fila("Excedente s/límite inferior", t["excedente"], "(=)"),
            _fila("Tasa %", t["tasa_pct"], "(×)", clave="auto"),
            _fila("Impuesto marginal", t["impuesto_marginal"], "(=)"),
            _fila("Cuota fija (bimestral)", t["cuota_fija"], "(+)", clave="auto"),
            _fila("ISR A CARGO", isr_cargo, "(=)"),
            _fila(f"Reducción {reduccion:.0f}%", _r(isr_cargo * reduccion / 100), "(-)"),
            _fila("ISR A PAGAR", isr_pagar, "(=)", fuerte=True)]})
        iva_trasl = _r(d("ingresos_16") * TASA_IVA / 100)
        iva_cargo = _r(iva_trasl - iva_acred_real)
        tasa_pg = d("tasa_iva_publico_general") or 2.0
        iva_pg_sin = _r(d("ingresos_publico_general") * tasa_pg / 100)
        iva_pg = _r(iva_pg_sin * (1 - reduccion / 100))
        iva_total = _r(max(0.0, iva_cargo) + iva_pg)
        secciones.append({"titulo": "IVA (con factor de acreditamiento)", "filas": [
            _fila("Factor de acreditamiento", factor, "", clave="auto"),
            _fila("IVA efectivamente trasladado (16%)", iva_trasl, "", clave="auto"),
            _fila("IVA realmente acreditable (× factor)", iva_acred_real, "(-)", clave="auto"),
            _fila("IVA a cargo", iva_cargo, "(=)"),
            _fila(f"IVA público en general ({tasa_pg:.0f}%)", iva_pg_sin, "(+)", clave="auto"),
            _fila(f"Reducción {reduccion:.0f}% s/IVA PG", _r(iva_pg_sin - iva_pg), "(-)"),
            _fila("TOTAL IVA A PAGAR", iva_total, "(=)", fuerte=True)]})
        ret_sal = _r(max(0.0, d("isr_ret_salarios") - d("subsidio_empleo")))
        pares = [("ISR RIF", isr_pagar), ("ISR ret. por salarios", ret_sal),
                 ("IVA", iva_total), ("SPE", d("spe"))]
        resumen, total, _t = _resumen(pares, restas=("SPE",))
        iva_neto_crudo = iva_total

    elif regimen == "pm_general":
        ingresos_a = _r(ac("ingresos_nominales") + ac("inventario_acumulable"))
        coef = d("coeficiente_utilidad")
        utilidad = _r(ingresos_a * coef)
        base = _r(max(0.0, utilidad - d("ptu_pagada_periodo")))
        causado = _r(base * TASA_ISR_PM / 100)
        pagos = d("pagos_provisionales") or ctx.get("pagos_provisionales_sugeridos", 0)
        isr_pagar = _r(max(0.0, causado - pagos))
        secciones.append({"titulo": "ISR (Art. 14 LISR, coeficiente)", "filas": [
            _fila("Ingresos nominales del mes", d("ingresos_nominales")),
            _fila("Ingresos nominales ACUMULADOS", ingresos_a, "", clave="auto",
                  fuerte=True),
            _fila("Coeficiente de utilidad", coef, "(×)"),
            _fila("Utilidad fiscal Art. 14", utilidad, "(=)"),
            _fila("PTU pagada del periodo", d("ptu_pagada_periodo"), "(-)"),
            _fila("Base para impuesto", base, "(=)"),
            _fila("Tasa Art. 9 LISR %", TASA_ISR_PM, "(×)", clave="auto"),
            _fila("ISR causado", causado, "(=)"),
            _fila("Pagos provisionales", pagos, "(-)"),
            _fila("ISR A PAGAR", isr_pagar, "(=)", fuerte=True)]})
        iva_filas, iva_pagar, iva_neto_crudo = _bloque_iva_flujo(
            d, ctx, con_retenidos_pm=True)
        secciones.append({"titulo": "IVA (Art. 1 LIVA)", "filas": iva_filas})
        ieps_filas, ieps = _seccion_ieps(d)
        secciones.append({"titulo": "IEPS", "filas": ieps_filas})
        pares = [("ISR Persona Moral", isr_pagar), ("IVA", iva_pagar),
                 ("IEPS", ieps), ("IVA retenciones", d("iva_retenciones")),
                 ("ISR retenido honorarios", d("isr_ret_honorarios")),
                 ("ISR retenido salarios", d("isr_ret_salarios")),
                 ("ISR RESICO", d("isr_resico_retenido")),
                 ("SPE", d("spe")), ("Compensaciones", d("compensaciones"))]
        resumen, total, _t = _resumen(pares, restas=("SPE", "Compensaciones"))

    return {
        "regimen": regimen, "regimen_nombre": REGIMENES[regimen],
        "mes": mes, "anio_tarifa": ANIO_TARIFA,
        "secciones": secciones,
        "resumen": resumen,
        "total_a_pagar": total,
        # negativo => saldo a favor de IVA que el sistema arrastra al mes sig.
        "iva_neto_crudo": _r(iva_neto_crudo),
        # ISR efectivamente a pagar este periodo (alimenta el renglón
        # "pagos provisionales" de los meses siguientes)
        "total_isr_periodo": _r(isr_pagar),
    }


# ---------------------------------------------------------------------------
# CONTEXTO DESDE LA BASE: la BD "acumula" como las hojas de Excel
# ---------------------------------------------------------------------------

def calcular(regimen: str, mes: int, datos: dict, contexto: dict | None = None) -> dict:
    """
    Punto de entrada oficial. Antes de calcular, convierte los RENGLONES
    capturados (gastos de venta, de administración, otros…) en el campo
    agregado que el motor conoce, y al final cuelga esa cédula en la fila
    correspondiente de la hoja: el contador captura como en su papel de
    trabajo y el sistema enseña la suma, no la esconde.
    """
    datos = dict(datos or {})
    reg = normalizar_regimen(regimen)
    desglose = {}
    for agr, subs in DESGLOSE_CAMPOS.items():
        if agr in {c for c, _ in CAMPOS.get(reg, [])} \
                and any(sc in datos for sc, _ in subs):
            datos[agr] = _r(sum(float(datos.get(sc) or 0) for sc, _ in subs))
            desglose[agr] = [
                {"concepto": etq, "valor": _r(float(datos.get(sc) or 0)),
                 "operador": "(+)"} for sc, etq in subs]
    resultado = _calcular_nucleo(regimen, mes, datos, contexto)
    resultado = _colgar_desglose(resultado, reg, desglose)

    # La hoja debe leerse SOLA, sin voltear al formulario: todo lo capturado,
    # renglón por renglón, antes de los totales (el reclamo clásico del
    # contador: "no me digas cuánto, enséñame de dónde").
    ultimo_sub = {subs[-1][0]: agr for agr, subs in DESGLOSE_CAMPOS.items()}
    etiquetas = dict(CAMPOS.get(reg, []))
    filas_cap = []
    for k, etq in CAMPOS_CAPTURA.get(reg, []):
        v = datos.get(k)
        if isinstance(v, (int, float)) and abs(v) > 1e-9:
            filas_cap.append(_fila(etq, v))
        if k in ultimo_sub and ultimo_sub[k] in desglose:
            agr = ultimo_sub[k]
            filas_cap.append(_fila(f"(=) {etiquetas.get(agr, agr)}",
                                   datos.get(agr, 0.0), "(=)", fuerte=True))
    for agr in DESGLOSE_CAMPOS:
        if agr not in desglose and isinstance(datos.get(agr), (int, float)) \
                and abs(datos[agr]) > 1e-9 and agr in etiquetas:
            filas_cap.append(_fila(etiquetas[agr], datos[agr]))
    if filas_cap and resultado.get("secciones"):
        resultado["secciones"].insert(
            0, {"titulo": "Captura del periodo · papel de trabajo",
                "filas": filas_cap})
    return resultado


def _colgar_desglose(resultado: dict, regimen: str, desglose: dict) -> dict:
    """Encuentra la fila del campo agregado y le cuelga su cédula (los
    renglones capturados). Si no la halla, antepone la sección
    'Papel de trabajo' para que el desglose JAMÁS se pierda."""
    if not desglose:
        return resultado
    etiquetas = dict(CAMPOS.get(regimen, []))
    pendientes = dict(desglose)
    for seccion in resultado.get("secciones", []):
        for fila in seccion.get("filas", []):
            for agr in list(pendientes):
                etq = etiquetas.get(agr, agr)
                if fila.get("clave") == agr or fila.get("concepto") == etq \
                        or etq.lower() in str(fila.get("concepto", "")).lower():
                    fila["detalle"] = pendientes.pop(agr)
                    fila["clave"] = fila.get("clave") or "auto"
                    break
    return resultado


def contexto_desde_bd(db, cliente_id: int, mes: int, anio: int,
                      regimen: str) -> dict:
    """
    Reconstruye lo que en el Excel hacían las referencias entre hojas:
    - acum: suma de los datos capturados en los meses anteriores del ejercicio
    - iva_favor_anterior: si el IVA del periodo anterior salió negativo
    - pagos_provisionales_sugeridos: suma de ISR autorizado en meses previos
    """
    from models.models import CalculoImpuesto, EstatusCalculo
    regimen = normalizar_regimen(regimen)
    anteriores = (db.query(CalculoImpuesto)
                  .filter(CalculoImpuesto.cliente_id == cliente_id,
                          CalculoImpuesto.anio == anio,
                          CalculoImpuesto.mes < mes)
                  .order_by(CalculoImpuesto.mes.asc()).all())
    acum: dict = {}
    pagos = 0.0
    favor = 0.0
    ultimo_mes_visto = None
    for c in anteriores:
        if normalizar_regimen(c.regimen) != regimen:
            continue  # cambió de régimen: no se mezclan acumulados
        for k, v in (c.datos_entrada or {}).items():
            try:
                acum[k] = _r(acum.get(k, 0) + float(v or 0))
            except (TypeError, ValueError):
                pass
        res = c.resultado or {}
        crudo = res.get("iva_neto_crudo")
        if ultimo_mes_visto is None or c.mes > ultimo_mes_visto:
            ultimo_mes_visto = c.mes
            favor = -float(crudo) if (crudo is not None and crudo < 0) else 0.0
        if c.estatus in (EstatusCalculo.AUTORIZADO, EstatusCalculo.DECLARADO):
            pagos = _r(pagos + float(res.get("total_isr_periodo") or 0))
    return {"acum": acum, "iva_favor_anterior": _r(favor),
            "pagos_provisionales_sugeridos": _r(pagos)}


# ===========================================================================
# CALCULADORAS DE LOS REGÍMENES RESTANTES Y DECLARACIONES ANUALES
# ===========================================================================

def tarifa_anual():
    return TARIFA_ISR_ANUAL


def tasa_resico_pf_anual(ingresos_anuales: float) -> float:
    for tope, tasa in TASAS_RESICO_PF_ANUAL:
        if ingresos_anuales <= tope:
            return tasa
    return TASAS_RESICO_PF_ANUAL[-1][1]


def _calcular_extra(regimen, mes, datos, ctx, acum_ant):
    """Regímenes del catálogo extendido. Devuelve (secciones, resumen, total,
    iva_neto_crudo, isr_periodo) o None si el régimen no es de este bloque."""
    d = lambda k: float(datos.get(k) or 0)          # noqa: E731
    ac = lambda k: _r(d(k) + float(acum_ant.get(k) or 0))  # noqa: E731
    secciones = []
    iva_neto_crudo = 0.0

    # ---------------- PF · SUELDOS Y SALARIOS ----------------
    if regimen == "pf_sueldos_salarios":
        base = _r(d("sueldos_gravados") + d("aguinaldo_gravado")
                  + d("prima_vacacional_gravada") + d("ptu_gravada")
                  + d("otros_gravados"))
        t = renglon_tarifa(base, TARIFA_ISR_MENSUAL)
        causado = t["impuesto_causado"]
        neto = _r(causado - d("subsidio_empleo"))
        a_cargo = _r(max(0.0, neto - d("isr_retenido")))
        secciones.append({"titulo": "ISR RETENCIONES (Art. 96)", "filas": [
            _fila("Sueldos y salarios gravados", d("sueldos_gravados")),
            _fila("Aguinaldo gravado", d("aguinaldo_gravado"), "(+)"),
            _fila("Prima vacacional gravada", d("prima_vacacional_gravada"), "(+)"),
            _fila("PTU gravada", d("ptu_gravada"), "(+)"),
            _fila("Otras percepciones gravadas", d("otros_gravados"), "(+)"),
            _fila("BASE GRAVABLE", base, "(=)", fuerte=True),
            _fila("Límite inferior", t["limite_inferior"], "(-)", clave="auto"),
            _fila("Excedente", t["excedente"], "(=)"),
            _fila("Tasa %", t["tasa_pct"], "(×)", clave="auto"),
            _fila("Impuesto marginal", t["impuesto_marginal"], "(=)"),
            _fila("Cuota fija", t["cuota_fija"], "(+)", clave="auto"),
            _fila("ISR causado", causado, "(=)"),
            _fila("Subsidio para el empleo", d("subsidio_empleo"), "(-)"),
            _fila("ISR a retener", max(0.0, neto), "(=)"),
            _fila("ISR ya retenido", d("isr_retenido"), "(-)"),
            _fila("DIFERENCIA POR ENTERAR", a_cargo, "(=)", fuerte=True)]})
        resumen, total, _x = _resumen([("ISR retenciones por salarios", a_cargo)])
        return secciones, resumen, total, 0.0, a_cargo

    # ---------------- PF · PLATAFORMAS TECNOLÓGICAS ----------------
    if regimen == "pf_plataformas":
        tasa = d("tipo_actividad_tasa") or 2.1
        isr_plataforma = _r(d("ingresos_plataforma") * tasa / 100)
        definitivo = d("opta_pago_definitivo") == 1
        retenido = d("isr_retenido_plataforma")
        if definitivo:
            a_cargo = _r(max(0.0, isr_plataforma - retenido))
            nota = "Pago DEFINITIVO: no se acumula a otros ingresos."
        else:
            a_cargo = _r(max(0.0, isr_plataforma - retenido))
            nota = "Pago PROVISIONAL: se acumula en la declaración anual."
        # Ingresos cobrados directamente (sin plataforma) también pagan la tasa
        isr_directo = _r(d("ingresos_directos_publico") * tasa / 100)
        secciones.append({"titulo": "ISR PLATAFORMAS (Art. 113-A)", "filas": [
            _fila("Ingresos cobrados por la plataforma", d("ingresos_plataforma")),
            _fila(f"Tasa de retención {tasa}%", tasa, "(×)", clave="auto"),
            _fila("ISR causado por plataforma", isr_plataforma, "(=)"),
            _fila("ISR retenido por la plataforma", retenido, "(-)"),
            _fila("Ingresos directos al público", d("ingresos_directos_publico")),
            _fila("ISR por ingresos directos", isr_directo, "(=)", clave="auto"),
            _fila("ISR POR PAGAR", _r(a_cargo + isr_directo), "(=)", fuerte=True),
            _fila(nota, 0, ""), ]})
        iva_filas, iva_pagar, iva_neto_crudo = _bloque_iva_flujo(d, ctx)
        secciones.append({"titulo": "IVA", "filas": iva_filas})
        isr_total = _r(a_cargo + isr_directo)
        resumen, total, _x = _resumen([("ISR plataformas", isr_total),
                                       ("IVA", iva_pagar)])
        return secciones, resumen, total, iva_neto_crudo, isr_total

    # ---------------- PF · ARRENDAMIENTO ----------------
    if regimen == "pf_arrendamiento":
        ingresos = ac("ingresos_rentas")
        ingresos_mes = d("ingresos_rentas")
        ciega = d("usa_deduccion_ciega") == 1
        if ciega:
            # Deducción opcional 35% + predial (Art. 115 penúltimo párrafo)
            deducciones = _r(ingresos * 0.35 + ac("predial"))
            filas_ded = [
                _fila("Deducción opcional 35% (ciega)", _r(ingresos * 0.35),
                      "", clave="auto"),
                _fila("Impuesto predial", ac("predial"), "(+)")]
        else:
            deducciones = _r(ac("predial") + ac("mantenimiento")
                             + ac("intereses_hipoteca") + ac("seguros")
                             + ac("depreciacion_construccion")
                             + ac("otras_deducciones"))
            filas_ded = [
                _fila("Impuesto predial", ac("predial")),
                _fila("Mantenimiento y conservación", ac("mantenimiento"), "(+)"),
                _fila("Intereses reales de hipoteca", ac("intereses_hipoteca"), "(+)"),
                _fila("Primas de seguros", ac("seguros"), "(+)"),
                _fila("Depreciación construcción 5%", ac("depreciacion_construccion"), "(+)"),
                _fila("Otras deducciones", ac("otras_deducciones"), "(+)")]
        base = _r(max(0.0, ingresos - deducciones))
        t = renglon_tarifa(base, tarifa_elevada(mes))
        causado = t["impuesto_causado"]
        pagos = d("pagos_provisionales") or ctx.get("pagos_provisionales_sugeridos", 0)
        isr_pagar = _r(max(0.0, causado - pagos - ac("isr_retenido_pm")))
        secciones.append({"titulo": "ISR ARRENDAMIENTO (Cap. III)", "filas": [
            _fila("Rentas cobradas del mes", ingresos_mes, "", acumulado=ingresos,
                  fuerte=True)] + filas_ded + [
            _fila("TOTAL DEDUCCIONES", deducciones, "(-)", fuerte=True),
            _fila("BASE GRAVABLE", base, "(=)"),
            _fila("Límite inferior", t["limite_inferior"], "(-)", clave="auto"),
            _fila("Excedente", t["excedente"], "(=)"),
            _fila("Tasa %", t["tasa_pct"], "(×)", clave="auto"),
            _fila("Impuesto marginal", t["impuesto_marginal"], "(=)"),
            _fila("Cuota fija", t["cuota_fija"], "(+)", clave="auto"),
            _fila("ISR causado", causado, "(=)"),
            _fila("Pagos provisionales anteriores", pagos, "(-)"),
            _fila("ISR retenido por personas morales (10%)",
                  ac("isr_retenido_pm"), "(-)"),
            _fila("ISR POR PAGAR", isr_pagar, "(=)", fuerte=True)]})
        iva_filas, iva_pagar, iva_neto_crudo = _bloque_iva_flujo(d, ctx)
        secciones.append({"titulo": "IVA (locales comerciales)", "filas": iva_filas})
        resumen, total, _x = _resumen([("ISR arrendamiento", isr_pagar),
                                       ("IVA", iva_pagar)])
        return secciones, resumen, total, iva_neto_crudo, isr_pagar

    # ---------------- PF/PM · AGAPE ----------------
    if regimen in ("pf_agape", "pm_agape"):
        es_pm = regimen == "pm_agape"
        ingresos = ac("ingresos_actividad")
        deducciones = ac("deducciones_autorizadas")
        # La exención del Art. 74 es ANUAL: en pagos provisionales se
        # prorratea al periodo transcurrido (mes/12), como marca la RMF.
        proporcion = mes / 12.0
        if es_pm:
            socios = max(1, int(d("numero_socios") or 1))
            tope_exento = _r(20 * UMA_ANUAL * socios * proporcion)
            etiqueta_exento = (f"Ingreso exento (20 UMA × {socios} socio(s), "
                               f"proporción {mes}/12)")
        else:
            tope_exento = _r(40 * UMA_ANUAL * proporcion)
            etiqueta_exento = f"Ingreso exento (40 UMA anuales, proporción {mes}/12)"
        # Si el contador captura un exento distinto, se respeta el suyo
        capturado = d("ingreso_exento_uma") if not es_pm else 0
        exento = _r(min(ingresos, capturado if capturado > 0 else tope_exento))
        base = _r(max(0.0, ingresos - exento - deducciones))
        if es_pm:
            causado = _r(base * TASA_ISR_PM / 100)
            fila_tasa = _fila("Tasa Art. 9 LISR %", TASA_ISR_PM, "(×)", clave="auto")
            pct_red = 30.0
        else:
            t = renglon_tarifa(base, tarifa_elevada(mes))
            causado = t["impuesto_causado"]
            fila_tasa = _fila("Tarifa Art. 96 (auto)", t["tasa_pct"], "(×)", clave="auto")
            pct_red = 40.0
        reduccion = _r(causado * pct_red / 100) if d("aplica_reduccion") == 1 else 0.0
        pagos = d("pagos_provisionales") or ctx.get("pagos_provisionales_sugeridos", 0)
        isr_pagar = _r(max(0.0, causado - reduccion - pagos))
        secciones.append({"titulo": "ISR AGAPE (Art. 74 LISR)", "filas": [
            _fila("Ingresos de la actividad", d("ingresos_actividad"),
                  "", acumulado=ingresos, fuerte=True),
            _fila(etiqueta_exento, exento, "(-)", clave="auto"),
            _fila("Deducciones autorizadas", deducciones, "(-)",
                  acumulado=deducciones),
            _fila("BASE GRAVABLE", base, "(=)"),
            fila_tasa,
            _fila("ISR causado", causado, "(=)"),
            _fila(f"Reducción {pct_red:.0f}% (Art. 74)", reduccion, "(-)"),
            _fila("Pagos provisionales anteriores", pagos, "(-)"),
            _fila("ISR POR PAGAR", isr_pagar, "(=)", fuerte=True)]})
        iva_filas, iva_pagar, iva_neto_crudo = _bloque_iva_flujo(d, ctx)
        secciones.append({"titulo": "IVA", "filas": iva_filas})
        resumen, total, _x = _resumen([("ISR AGAPE", isr_pagar), ("IVA", iva_pagar)])
        return secciones, resumen, total, iva_neto_crudo, isr_pagar

    # ---------------- PF · ENAJENACIÓN DE BIENES ----------------
    if regimen == "pf_enajenacion":
        ganancia = _r(d("precio_venta") - d("costo_actualizado")
                      - d("gastos_notariales") - d("comisiones")
                      - d("exento_casa_habitacion"))
        anios = max(1, min(20, int(d("anios_transcurridos") or 1)))
        acumulable = _r(max(0.0, ganancia) / anios)
        no_acumulable = _r(max(0.0, ganancia) - acumulable)
        t = renglon_tarifa(acumulable, TARIFA_ISR_ANUAL)
        isr_acumulable = t["impuesto_causado"]
        tasa_efectiva = (round(isr_acumulable / acumulable * 100, 4)
                         if acumulable else 0.0)
        isr_no_acumulable = _r(no_acumulable * tasa_efectiva / 100)
        total_isr = _r(isr_acumulable + isr_no_acumulable)
        a_cargo = _r(max(0.0, total_isr - d("isr_retenido_notario")))
        secciones.append({"titulo": "ISR ENAJENACIÓN (Cap. IV, Art. 120)", "filas": [
            _fila("Precio de venta", d("precio_venta")),
            _fila("Costo comprobado actualizado", d("costo_actualizado"), "(-)"),
            _fila("Gastos notariales, impuestos y derechos", d("gastos_notariales"), "(-)"),
            _fila("Comisiones y mediaciones", d("comisiones"), "(-)"),
            _fila("Exención casa habitación", d("exento_casa_habitacion"), "(-)"),
            _fila("GANANCIA", max(0.0, ganancia), "(=)", fuerte=True),
            _fila(f"Años transcurridos (máx. 20)", anios, "(÷)"),
            _fila("Ganancia ACUMULABLE", acumulable, "(=)", clave="auto"),
            _fila("Ganancia NO acumulable", no_acumulable, "", clave="auto"),
            _fila("ISR sobre acumulable (tarifa anual)", isr_acumulable, "", clave="auto"),
            _fila("Tasa efectiva %", tasa_efectiva, "", clave="auto"),
            _fila("ISR sobre no acumulable", isr_no_acumulable, "(+)", clave="auto"),
            _fila("ISR TOTAL", total_isr, "(=)"),
            _fila("ISR retenido por el notario", d("isr_retenido_notario"), "(-)"),
            _fila("ISR POR PAGAR", a_cargo, "(=)", fuerte=True)]})
        resumen, total, _x = _resumen([("ISR enajenación", a_cargo)])
        return secciones, resumen, total, 0.0, a_cargo

    # ---------------- PF · ADQUISICIÓN DE BIENES ----------------
    if regimen == "pf_adquisicion":
        base = _r(max(0.0, d("valor_avaluo") - d("deducciones_autorizadas")))
        provisional = _r(base * 0.20)  # Art. 132: 20% provisional
        a_cargo = _r(max(0.0, provisional - d("isr_retenido")))
        secciones.append({"titulo": "ISR ADQUISICIÓN (Cap. V, Art. 132)", "filas": [
            _fila("Valor del avalúo / bien adquirido", d("valor_avaluo")),
            _fila("Deducciones autorizadas (Art. 131)", d("deducciones_autorizadas"), "(-)"),
            _fila("BASE GRAVABLE", base, "(=)", fuerte=True),
            _fila("Tasa provisional 20%", 20.0, "(×)", clave="auto"),
            _fila("Pago provisional", provisional, "(=)"),
            _fila("ISR retenido", d("isr_retenido"), "(-)"),
            _fila("ISR POR PAGAR", a_cargo, "(=)", fuerte=True)]})
        resumen, total, _x = _resumen([("ISR adquisición", a_cargo)])
        return secciones, resumen, total, 0.0, a_cargo

    # ---------------- PF · INTERESES ----------------
    if regimen == "pf_intereses":
        reales = _r(d("intereses_nominales") - d("ajuste_inflacion"))
        secciones.append({"titulo": "INTERESES (Cap. VI)", "filas": [
            _fila("Intereses nominales cobrados", d("intereses_nominales")),
            _fila("Ajuste anual por inflación", d("ajuste_inflacion"), "(-)"),
            _fila("INTERÉS REAL ACUMULABLE", reales, "(=)", fuerte=True),
            _fila("ISR retenido por la institución", d("isr_retenido_banco"), ""),
            _fila("Se acumula en la declaración ANUAL; la retención es acreditable.",
                  0, "")]})
        resumen, total, _x = _resumen([("ISR por pagar (se define en la anual)", 0.0)])
        return secciones, resumen, total, 0.0, 0.0

    # ---------------- PF · DIVIDENDOS ----------------
    if regimen == "pf_dividendos":
        dividendo = d("dividendo_percibido")
        piramidado = _r(dividendo * FACTOR_PIRAMIDACION)
        isr_acreditable = _r(piramidado * TASA_ISR_PM / 100)
        retenido_10 = d("isr_retenido_10") or _r(dividendo * TASA_DIVIDENDOS_ADICIONAL / 100)
        secciones.append({"titulo": "DIVIDENDOS (Art. 140)", "filas": [
            _fila("Dividendo percibido", dividendo),
            _fila(f"Factor de piramidación {FACTOR_PIRAMIDACION}", FACTOR_PIRAMIDACION,
                  "(×)", clave="auto"),
            _fila("Dividendo ACUMULABLE (piramidado)", piramidado, "(=)", fuerte=True),
            _fila("ISR pagado por la persona moral (acreditable)", isr_acreditable,
                  "", clave="auto"),
            _fila("¿Proviene de CUFIN?", d("proviene_de_cufin"), ""),
            _fila(f"ISR retenido {TASA_DIVIDENDOS_ADICIONAL}% (DEFINITIVO)",
                  retenido_10, "", fuerte=True),
            _fila("El acumulable y el acreditable van en la declaración ANUAL.",
                  0, "")]})
        resumen, total, _x = _resumen([("ISR adicional definitivo 10%", retenido_10)])
        return secciones, resumen, total, 0.0, retenido_10

    # ---------------- PF · DEMÁS INGRESOS ----------------
    if regimen == "pf_demas_ingresos":
        base = _r(max(0.0, d("ingresos_percibidos") - d("deducciones_autorizadas")))
        provisional = _r(base * 0.20)
        a_cargo = _r(max(0.0, provisional - d("isr_retenido")))
        secciones.append({"titulo": "DEMÁS INGRESOS (Cap. IX)", "filas": [
            _fila("Ingresos percibidos", d("ingresos_percibidos")),
            _fila("Deducciones autorizadas", d("deducciones_autorizadas"), "(-)"),
            _fila("BASE GRAVABLE", base, "(=)", fuerte=True),
            _fila("Pago provisional 20%", provisional, "(=)", clave="auto"),
            _fila("ISR retenido", d("isr_retenido"), "(-)"),
            _fila("ISR POR PAGAR", a_cargo, "(=)", fuerte=True)]})
        resumen, total, _x = _resumen([("ISR demás ingresos", a_cargo)])
        return secciones, resumen, total, 0.0, a_cargo

    # ---------------- PM · FINES NO LUCRATIVOS ----------------
    if regimen == "pm_no_lucrativas":
        remanente = d("remanente_distribuible")
        gravados = d("ingresos_gravados_no_relacionados")
        isr_remanente = _r(remanente * TASA_ISR_PM / 100)
        isr_gravados = _r(gravados * TASA_ISR_PM / 100)
        secciones.append({"titulo": "TÍTULO III · NO CONTRIBUYENTE DE ISR", "filas": [
            _fila("Ingresos propios de su actividad (NO gravados)",
                  d("ingresos_propios_actividad"), "", clave="auto"),
            _fila("Remanente distribuible (Art. 79)", remanente),
            _fila("ISR sobre remanente (30%)", isr_remanente, "(=)", clave="auto"),
            _fila("Ingresos gravados no relacionados (>5%)", gravados),
            _fila("ISR sobre esos ingresos (30%)", isr_gravados, "(=)", clave="auto"),
            _fila("ISR A CARGO", _r(isr_remanente + isr_gravados), "(=)", fuerte=True)]})
        iva_filas, iva_pagar, iva_neto_crudo = _bloque_iva_flujo(d, ctx)
        secciones.append({"titulo": "IVA", "filas": iva_filas})
        isr_total = _r(isr_remanente + isr_gravados)
        resumen, total, _x = _resumen([
            ("ISR (remanente y no relacionados)", isr_total),
            ("IVA", iva_pagar),
            ("IVA retenciones", d("iva_retenciones")),
            ("ISR retenido salarios", d("isr_ret_salarios")),
            ("ISR retenido honorarios", d("isr_ret_honorarios"))])
        return secciones, resumen, total, iva_neto_crudo, isr_total

    # ---------------- PM · COORDINADOS ----------------
    if regimen == "pm_coordinados":
        ingresos = ac("ingresos_cobrados")
        deducciones = ac("deducciones_pagadas")
        facilidad = 0.0
        if d("aplica_facilidades") == 1:
            pct = d("deduccion_facilidades_pct") or 8.0
            facilidad = _r(ingresos * pct / 100)
        base = _r(max(0.0, ingresos - deducciones - facilidad))
        causado = _r(base * TASA_ISR_PM / 100)
        pagos = d("pagos_provisionales") or ctx.get("pagos_provisionales_sugeridos", 0)
        isr_pagar = _r(max(0.0, causado - pagos))
        secciones.append({"titulo": "ISR COORDINADOS (Cap. VII, flujo)", "filas": [
            _fila("Ingresos cobrados", d("ingresos_cobrados"), "",
                  acumulado=ingresos, fuerte=True),
            _fila("Deducciones pagadas", deducciones, "(-)", acumulado=deducciones),
            _fila("Deducción por facilidades administrativas", facilidad, "(-)",
                  clave="auto"),
            _fila("BASE GRAVABLE", base, "(=)"),
            _fila("Tasa Art. 9 LISR %", TASA_ISR_PM, "(×)", clave="auto"),
            _fila("ISR causado", causado, "(=)"),
            _fila("Pagos provisionales anteriores", pagos, "(-)"),
            _fila("ISR POR PAGAR", isr_pagar, "(=)", fuerte=True)]})
        iva_filas, iva_pagar, iva_neto_crudo = _bloque_iva_flujo(d, ctx)
        secciones.append({"titulo": "IVA", "filas": iva_filas})
        resumen, total, _x = _resumen([("ISR coordinados", isr_pagar),
                                       ("IVA", iva_pagar),
                                       ("ISR retenido salarios", d("isr_ret_salarios"))])
        return secciones, resumen, total, iva_neto_crudo, isr_pagar

    return None


def _calcular_anual(regimen, datos, ctx):
    """Declaraciones ANUALES. Devuelve el mismo formato de hoja."""
    d = lambda k: float(datos.get(k) or 0)          # noqa: E731
    secciones = []

    # ---------------- ANUAL · PERSONA FÍSICA (todos sus ingresos) ----------------
    if regimen == "anual_pf_general":
        util_actividad = _r(d("ingresos_actividad_empresarial")
                            - d("deducciones_actividad"))
        util_arren = _r(d("ingresos_arrendamiento") - d("deducciones_arrendamiento"))
        ingreso_total = _r(max(0.0, util_actividad) + d("ingresos_sueldos")
                           + max(0.0, util_arren) + d("ingresos_intereses_reales")
                           + d("otros_ingresos_acumulables"))
        base_antes_dp = _r(max(0.0, ingreso_total - d("perdidas_fiscales_anteriores")))

        # Deducciones personales con el TOPE del Art. 151 (el sistema lo aplica solo)
        dp_bruto = _r(d("dp_honorarios_medicos") + d("dp_gastos_funerarios")
                      + d("dp_intereses_hipotecarios") + d("dp_aportaciones_retiro")
                      + d("dp_primas_seguros_gastos_medicos")
                      + d("dp_transporte_escolar"))
        tope_uma = _r(TOPE_DEDUCCIONES_PERSONALES_UMA * UMA_ANUAL)
        tope_pct = _r(ingreso_total * TOPE_DEDUCCIONES_PERSONALES_PCT / 100)
        tope = min(tope_uma, tope_pct)
        dp_limitadas = min(dp_bruto, tope)
        # Donativos (7% del ingreso del ejercicio anterior) y colegiaturas
        # (estímulo, NO sujeto al tope general) van aparte
        dp_total = _r(dp_limitadas + d("dp_donativos")
                      + min(d("dp_colegiaturas"),
                            d("estimulo_colegiaturas_tope") or d("dp_colegiaturas")))
        base = _r(max(0.0, base_antes_dp - dp_total))

        t = renglon_tarifa(base, TARIFA_ISR_ANUAL)
        causado = t["impuesto_causado"]
        acreditamientos = _r(d("pagos_provisionales_efectuados")
                             + d("isr_retenido_total")
                             + d("subsidio_empleo_acreditado"))
        diferencia = _r(causado - acreditamientos)

        secciones.append({"titulo": "INGRESOS ACUMULABLES DEL EJERCICIO", "filas": [
            _fila("Utilidad de actividad empresarial/profesional",
                  max(0.0, util_actividad), "", clave="auto"),
            _fila("Sueldos y salarios", d("ingresos_sueldos"), "(+)"),
            _fila("Utilidad de arrendamiento", max(0.0, util_arren), "(+)", clave="auto"),
            _fila("Intereses reales acumulables", d("ingresos_intereses_reales"), "(+)"),
            _fila("Otros ingresos acumulables", d("otros_ingresos_acumulables"), "(+)"),
            _fila("TOTAL DE INGRESOS ACUMULABLES", ingreso_total, "(=)", fuerte=True),
            _fila("Pérdidas fiscales de ejercicios anteriores",
                  d("perdidas_fiscales_anteriores"), "(-)"),
            _fila("Base antes de deducciones personales", base_antes_dp, "(=)")]})

        secciones.append({"titulo": "DEDUCCIONES PERSONALES (Art. 151)", "filas": [
            _fila("Honorarios médicos, dentales y hospitalarios", d("dp_honorarios_medicos")),
            _fila("Gastos funerarios", d("dp_gastos_funerarios"), "(+)"),
            _fila("Intereses reales de crédito hipotecario", d("dp_intereses_hipotecarios"), "(+)"),
            _fila("Aportaciones complementarias de retiro", d("dp_aportaciones_retiro"), "(+)"),
            _fila("Primas de seguros de gastos médicos", d("dp_primas_seguros_gastos_medicos"), "(+)"),
            _fila("Transporte escolar obligatorio", d("dp_transporte_escolar"), "(+)"),
            _fila("Suma sujeta al tope", dp_bruto, "(=)"),
            _fila(f"Tope: 5 UMA anuales ({dinero_txt(tope_uma)})", tope_uma, "", clave="auto"),
            _fila(f"Tope: 15% del ingreso ({dinero_txt(tope_pct)})", tope_pct, "", clave="auto"),
            _fila("TOPE APLICABLE (el menor)", tope, "(=)", clave="auto", fuerte=True),
            _fila("Deducciones personales limitadas", dp_limitadas, "(=)", clave="auto"),
            _fila("Donativos (fuera del tope general)", d("dp_donativos"), "(+)"),
            _fila("Colegiaturas (estímulo, topes por nivel)",
                  min(d("dp_colegiaturas"),
                      d("estimulo_colegiaturas_tope") or d("dp_colegiaturas")), "(+)"),
            _fila("TOTAL DEDUCCIONES PERSONALES", dp_total, "(=)", fuerte=True)]})

        secciones.append({"titulo": "ISR DEL EJERCICIO (tarifa anual Art. 152)", "filas": [
            _fila("BASE GRAVABLE", base, "", fuerte=True),
            _fila("Límite inferior", t["limite_inferior"], "(-)", clave="auto"),
            _fila("Excedente del límite inferior", t["excedente"], "(=)"),
            _fila("Tasa %", t["tasa_pct"], "(×)", clave="auto"),
            _fila("Impuesto marginal", t["impuesto_marginal"], "(=)"),
            _fila("Cuota fija", t["cuota_fija"], "(+)", clave="auto"),
            _fila("ISR CAUSADO DEL EJERCICIO", causado, "(=)", fuerte=True),
            _fila("Pagos provisionales efectuados", d("pagos_provisionales_efectuados"), "(-)"),
            _fila("ISR retenido en el ejercicio", d("isr_retenido_total"), "(-)"),
            _fila("Subsidio para el empleo acreditado", d("subsidio_empleo_acreditado"), "(-)"),
            _fila("ISR A CARGO" if diferencia >= 0 else "SALDO A FAVOR",
                  abs(diferencia), "(=)", fuerte=True)]})

        a_cargo = max(0.0, diferencia)
        saldo_favor = max(0.0, -diferencia)
        resumen = [_fila("ISR del ejercicio a cargo", a_cargo, "", fuerte=True)]
        if saldo_favor:
            resumen.append(_fila("SALDO A FAVOR (susceptible de devolución "
                                 "o compensación)", saldo_favor, "", fuerte=True))
        return {"secciones": secciones, "resumen": resumen,
                "total_a_pagar": a_cargo, "saldo_a_favor": saldo_favor,
                "iva_neto_crudo": 0.0, "total_isr_periodo": a_cargo}

    # ---------------- ANUAL · RESICO PF ----------------
    if regimen == "anual_pf_resico":
        ingresos = d("ingresos_anuales_cobrados")
        tasa = tasa_resico_pf_anual(ingresos)
        causado = _r(ingresos * tasa / 100)
        acreditable = _r(d("isr_pagos_mensuales") + d("isr_retenido_pm"))
        diferencia = _r(causado - acreditable)
        secciones.append({"titulo": "ISR RESICO ANUAL (Art. 113-F)", "filas": [
            _fila("Ingresos anuales efectivamente cobrados", ingresos, "", fuerte=True),
            _fila("Tasa anual aplicable %", tasa, "(×)", clave="auto"),
            _fila("ISR DEL EJERCICIO", causado, "(=)", fuerte=True),
            _fila("ISR pagado en los meses", d("isr_pagos_mensuales"), "(-)"),
            _fila("ISR retenido por personas morales (1.25%)", d("isr_retenido_pm"), "(-)"),
            _fila("ISR A CARGO" if diferencia >= 0 else "SALDO A FAVOR",
                  abs(diferencia), "(=)", fuerte=True)]})
        a_cargo = max(0.0, diferencia)
        saldo_favor = max(0.0, -diferencia)
        resumen = [_fila("ISR anual a cargo", a_cargo, "", fuerte=True)]
        if saldo_favor:
            resumen.append(_fila("SALDO A FAVOR", saldo_favor, "", fuerte=True))
        return {"secciones": secciones, "resumen": resumen,
                "total_a_pagar": a_cargo, "saldo_a_favor": saldo_favor,
                "iva_neto_crudo": 0.0, "total_isr_periodo": a_cargo}

    # ---------------- ANUAL · PERSONA MORAL ----------------
    if regimen in ("anual_pm_general", "anual_pm_resico"):
        if regimen == "anual_pm_general":
            ingresos = _r(d("ingresos_acumulables")
                          + d("ajuste_anual_inflacion_acumulable"))
            deducciones = _r(d("deducciones_autorizadas")
                             + d("ajuste_anual_inflacion_deducible"))
            filas_ing = [
                _fila("Ingresos acumulables", d("ingresos_acumulables")),
                _fila("Ajuste anual por inflación acumulable",
                      d("ajuste_anual_inflacion_acumulable"), "(+)"),
                _fila("TOTAL DE INGRESOS", ingresos, "(=)", fuerte=True),
                _fila("Deducciones autorizadas", d("deducciones_autorizadas"), "(-)"),
                _fila("Ajuste anual por inflación deducible",
                      d("ajuste_anual_inflacion_deducible"), "(-)")]
            titulo = "RESULTADO FISCAL (Art. 9, Título II)"
        else:
            ingresos = d("ingresos_cobrados_ejercicio")
            deducciones = d("deducciones_pagadas_ejercicio")
            filas_ing = [
                _fila("Ingresos efectivamente cobrados", ingresos, "", fuerte=True),
                _fila("Deducciones efectivamente pagadas", deducciones, "(-)")]
            titulo = "RESULTADO FISCAL (RESICO PM, flujo)"

        utilidad = _r(ingresos - deducciones)
        utilidad_menos_ptu = _r(utilidad - d("ptu_pagada_ejercicio"))
        resultado = _r(max(0.0, utilidad_menos_ptu - d("perdidas_fiscales_anteriores")))
        causado = _r(resultado * TASA_ISR_PM / 100)
        acreditamientos = _r(d("pagos_provisionales_efectuados") + d("isr_retenido")
                             + (d("estimulos_fiscales") if regimen == "anual_pm_general" else 0)
                             + (d("isr_pagado_extranjero") if regimen == "anual_pm_general" else 0))
        diferencia = _r(causado - acreditamientos)
        perdida = _r(max(0.0, -utilidad_menos_ptu))

        secciones.append({"titulo": titulo, "filas": filas_ing + [
            _fila("UTILIDAD FISCAL" if utilidad >= 0 else "PÉRDIDA FISCAL",
                  abs(utilidad), "(=)", fuerte=True),
            _fila("PTU pagada en el ejercicio", d("ptu_pagada_ejercicio"), "(-)"),
            _fila("Pérdidas fiscales de ejercicios anteriores",
                  d("perdidas_fiscales_anteriores"), "(-)"),
            _fila("RESULTADO FISCAL", resultado, "(=)", fuerte=True),
            _fila("Tasa Art. 9 LISR %", TASA_ISR_PM, "(×)", clave="auto"),
            _fila("ISR DEL EJERCICIO", causado, "(=)", fuerte=True),
            _fila("Pagos provisionales efectuados",
                  d("pagos_provisionales_efectuados"), "(-)"),
            _fila("ISR retenido", d("isr_retenido"), "(-)")]
            + ([_fila("Estímulos fiscales acreditables", d("estimulos_fiscales"), "(-)"),
                _fila("ISR pagado en el extranjero", d("isr_pagado_extranjero"), "(-)")]
               if regimen == "anual_pm_general" else [])
            + [_fila("ISR A CARGO" if diferencia >= 0 else "SALDO A FAVOR",
                     abs(diferencia), "(=)", fuerte=True)]})

        if perdida:
            secciones.append({"titulo": "PÉRDIDA FISCAL POR AMORTIZAR", "filas": [
                _fila("Pérdida del ejercicio (amortizable 10 años)", perdida,
                      "", fuerte=True)]})

        a_cargo = max(0.0, diferencia)
        saldo_favor = max(0.0, -diferencia)
        resumen = [_fila("ISR del ejercicio a cargo", a_cargo, "", fuerte=True)]
        if saldo_favor:
            resumen.append(_fila("SALDO A FAVOR", saldo_favor, "", fuerte=True))
        return {"secciones": secciones, "resumen": resumen,
                "total_a_pagar": a_cargo, "saldo_a_favor": saldo_favor,
                "perdida_fiscal": perdida,
                "iva_neto_crudo": 0.0, "total_isr_periodo": a_cargo}

    return None


def dinero_txt(x):
    return f"${x:,.2f}"
