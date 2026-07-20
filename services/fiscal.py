# -*- coding: utf-8 -*-
"""
MOTOR DE DETERMINACIÓN DE IMPUESTOS — P&A (Fresnillo, Zacatecas)
================================================================
Replica el cálculo primordial de la página de declaración del SAT para
pagos provisionales mensuales, con las constantes auto-rellenadas:

- PERSONA FÍSICA (actividad empresarial): tarifa progresiva del Art. 96/106
  LISR elevada al periodo (límite inferior, cuota fija y tasa marginal se
  seleccionan y rellenan automáticamente según la base acumulada).
- PERSONA MORAL: coeficiente de utilidad × ingresos nominales acumulados,
  a la tasa del Art. 9 LISR (30%).
- IVA: trasladado cobrado − acreditable pagado (cargo o saldo a favor).
- ISN ZACATECAS: base de nómina × tasa estatal.

⚠ CONSTANTES A VERIFICAR CADA EJERCICIO por el Director o la Supervisora:
  - TARIFA_ISR_MENSUAL contra el Anexo 8 de la RMF vigente.
  - TASA_ISN_ZACATECAS contra la Ley de Hacienda del Estado.
El sistema expone la tarifa cargada en GET /api/calculos/tarifa para que
la revisión sea transparente.
"""

ANIO_TARIFA = 2025  # vigente desde 2023 (se actualiza cuando la inflación acumulada supera 10%)

# Tarifa MENSUAL Art. 96 LISR: (límite_inferior, límite_superior, cuota_fija, tasa_%)
# El último renglón usa None como límite superior (en adelante).
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

TASA_ISR_PERSONA_MORAL = 30.0   # Art. 9 LISR
TASA_ISN_ZACATECAS = 3.0        # Impuesto Sobre Nóminas estatal (verificar ejercicio)
TASA_IVA = 16.0


def _r(x: float) -> float:
    return round(x + 1e-9, 2)


def tarifa_del_periodo(mes: int) -> list:
    """Tarifa elevada al periodo: límites y cuota fija × número de mes."""
    return [(_r(li * mes), (_r(ls * mes) if ls else None), _r(cf * mes), tasa)
            for li, ls, cf, tasa in TARIFA_ISR_MENSUAL]


def calcular_isr_pf(base_gravable_acumulada: float, mes: int) -> dict:
    """
    ISR de persona física con la tarifa del periodo. Devuelve TODOS los
    renglones intermedios, igual que la página del SAT, para que el
    autorizador vea de dónde sale cada número.
    """
    base = max(0.0, base_gravable_acumulada)
    for li, ls, cf, tasa in tarifa_del_periodo(mes):
        if base >= li and (ls is None or base <= ls):
            excedente = _r(base - li)
            imp_marginal = _r(excedente * tasa / 100)
            return {
                "limite_inferior": li,
                "limite_superior": ls,
                "excedente_limite_inferior": excedente,
                "tasa_marginal_pct": tasa,
                "impuesto_marginal": imp_marginal,
                "cuota_fija": cf,
                "isr_causado_periodo": _r(imp_marginal + cf),
            }
    # base == 0 cae aquí
    return {"limite_inferior": 0, "limite_superior": None,
            "excedente_limite_inferior": 0, "tasa_marginal_pct": 0,
            "impuesto_marginal": 0, "cuota_fija": 0, "isr_causado_periodo": 0}


def calcular(regimen: str, mes: int, datos: dict) -> dict:
    """
    Cálculo completo del periodo a partir de los datos de la balanza.

    datos esperados (todos float, faltantes = 0):
      PF: ingresos_acumulados, deducciones_acumuladas
      PM: ingresos_nominales_acumulados, coeficiente_utilidad (ej. 0.0824)
      Ambos: pagos_provisionales_anteriores, retenciones_isr,
             iva_trasladado, iva_acreditable, iva_retenido,
             base_nomina (para ISN)
    """
    d = lambda k: float(datos.get(k) or 0)
    resultado = {"regimen": regimen, "mes": mes, "anio_tarifa": ANIO_TARIFA}

    # ---------- ISR ----------
    if regimen == "persona_fisica":
        base = _r(d("ingresos_acumulados") - d("deducciones_acumuladas"))
        renglones = calcular_isr_pf(base, mes)
        resultado["isr"] = {
            "ingresos_acumulados": d("ingresos_acumulados"),
            "deducciones_acumuladas": d("deducciones_acumuladas"),
            "base_gravable": max(0.0, base),
            **renglones,
        }
        causado = renglones["isr_causado_periodo"]
    elif regimen == "persona_moral":
        utilidad = _r(d("ingresos_nominales_acumulados") * d("coeficiente_utilidad"))
        causado = _r(utilidad * TASA_ISR_PERSONA_MORAL / 100)
        resultado["isr"] = {
            "ingresos_nominales_acumulados": d("ingresos_nominales_acumulados"),
            "coeficiente_utilidad": d("coeficiente_utilidad"),
            "utilidad_fiscal_estimada": utilidad,
            "tasa_pct": TASA_ISR_PERSONA_MORAL,
            "isr_causado_periodo": causado,
        }
    else:
        raise ValueError("Régimen no válido")

    isr_cargo = _r(max(0.0, causado - d("pagos_provisionales_anteriores")
                       - d("retenciones_isr")))
    resultado["isr"].update({
        "pagos_provisionales_anteriores": d("pagos_provisionales_anteriores"),
        "retenciones_isr": d("retenciones_isr"),
        "isr_a_cargo": isr_cargo,
    })

    # ---------- IVA ----------
    iva_neto = _r(d("iva_trasladado") - d("iva_acreditable") - d("iva_retenido"))
    resultado["iva"] = {
        "iva_trasladado": d("iva_trasladado"),
        "iva_acreditable": d("iva_acreditable"),
        "iva_retenido": d("iva_retenido"),
        "iva_a_cargo": max(0.0, iva_neto),
        "saldo_a_favor": _r(abs(min(0.0, iva_neto))),
        "tasa_pct": TASA_IVA,
    }

    # ---------- ISN Zacatecas ----------
    isn = _r(d("base_nomina") * TASA_ISN_ZACATECAS / 100)
    resultado["isn"] = {"base_nomina": d("base_nomina"),
                        "tasa_pct": TASA_ISN_ZACATECAS,
                        "isn_determinado": isn}

    resultado["total_a_pagar"] = _r(isr_cargo + resultado["iva"]["iva_a_cargo"] + isn)
    return resultado
