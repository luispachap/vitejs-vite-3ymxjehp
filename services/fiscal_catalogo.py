# -*- coding: utf-8 -*-
"""
CATÁLOGO FISCAL COMPLETO — todos los regímenes de México
========================================================
Extiende fiscal_v2 con el resto de los regímenes vigentes y las
declaraciones ANUALES. Cada régimen tiene su propia calculadora, aunque
varios compartan estructura: los renglones y las constantes son distintos
y eso es justo lo que importa para no equivocarse.

PERSONAS FÍSICAS (Título IV LISR)
  pf_sueldos_salarios      Cap. I    · Sueldos y salarios
  pf_actividad_empresarial Cap. II-I · Actividad empresarial y profesional
  pf_resico                Cap. II-III (Art. 113-E) · RESICO
  rif                      Transitorio · RIF (bimestral)
  pf_plataformas           Cap. II-II (Art. 113-A) · Plataformas tecnológicas
  pf_arrendamiento         Cap. III  · Arrendamiento (deducción opcional 35%)
  pf_agape                 Cap. VIII · Agrícolas, ganaderas, silvícolas, pesqueras
  pf_enajenacion           Cap. IV   · Enajenación de bienes
  pf_adquisicion           Cap. V    · Adquisición de bienes
  pf_intereses             Cap. VI   · Intereses
  pf_dividendos            Cap. VIII · Dividendos
  pf_demas_ingresos        Cap. IX   · Demás ingresos

PERSONAS MORALES
  pm_general               Título II  · Régimen general (coeficiente Art. 14)
  pm_resico                Título VII Cap. XII · RESICO PM (flujo)
  pm_no_lucrativas         Título III · Fines no lucrativos
  pm_coordinados           Cap. VII   · Coordinados (autotransporte)
  pm_agape                 Cap. VIII  · AGAPE personas morales

ANUALES
  anual_pf_general         PF: acumula todos los capítulos + deducciones
                           personales (tope: 5 UMA anuales o 15% del ingreso)
  anual_pf_resico          RESICO PF anual (tasas Art. 113-F)
  anual_pm_general         PM: resultado fiscal, PTU, pérdidas, tasa 30%
  anual_pm_resico          PM RESICO anual

⚠ CONSTANTES A VERIFICAR CADA EJERCICIO (Anexo 8 RMF, LISR, valor de la UMA).
"""

# --- Constantes del ejercicio (VERIFICAR ANUALMENTE) ---
UMA_DIARIA = 113.14          # 2025
UMA_ANUAL = UMA_DIARIA * 365
TOPE_DEDUCCIONES_PERSONALES_UMA = 5      # 5 UMA anuales
TOPE_DEDUCCIONES_PERSONALES_PCT = 15.0   # o 15% del ingreso total (el menor)
TASA_ISR_PM = 30.0
TASA_IVA = 16.0

# Tarifa ANUAL Art. 152 LISR (= mensual × 12, publicada en Anexo 8)
TARIFA_ISR_ANUAL = [
    (0.01,        8952.49,     0.00,       1.92),
    (8952.50,     75984.55,    171.88,     6.40),
    (75984.56,    133536.07,   4461.94,    10.88),
    (133536.08,   155229.80,   10723.55,   16.00),
    (155229.81,   185852.57,   14194.54,   17.92),
    (185852.58,   374837.88,   19682.13,   21.36),
    (374837.89,   590795.99,   60049.40,   23.52),
    (590796.00,   1127926.84,  110842.74,  30.00),
    (1127926.85,  1503902.46,  271981.99,  32.00),
    (1503902.47,  4511707.37,  392294.17,  34.00),
    (4511707.38,  None,        1414947.85, 35.00),
]

# Tasas ANUALES RESICO PF, Art. 113-F LISR
TASAS_RESICO_PF_ANUAL = [
    (300000.00,   1.00),
    (600000.00,   1.10),
    (1000000.00,  1.50),
    (2500000.00,  2.00),
    (3500000.00,  2.50),
]

# Retención de plataformas tecnológicas, Art. 113-A (tasas por actividad)
TASAS_PLATAFORMAS = {
    "servicios_transporte_pasajeros_entrega": 2.1,   # Uber, Didi, Rappi...
    "hospedaje": 4.0,                                 # Airbnb...
    "enajenacion_bienes_prestacion_servicios": 1.0,  # Mercado Libre, Amazon...
}

# Retención de dividendos (Art. 140 LISR): 10% adicional definitivo
TASA_DIVIDENDOS_ADICIONAL = 10.0
FACTOR_PIRAMIDACION = 1.4286  # Art. 10: dividendo × 1.4286 × 30%

# Retención de intereses: tasa anual sobre el capital (Ley de Ingresos)
TASA_RETENCION_INTERESES = 0.50  # 2025 (verificar cada año en la LIF)

REGIMENES_EXTRA = {
    # Personas físicas
    "pf_sueldos_salarios": "PF · Sueldos y salarios",
    "pf_plataformas": "PF · Plataformas tecnológicas (Art. 113-A)",
    "pf_arrendamiento": "PF · Arrendamiento",
    "pf_agape": "PF · Agrícolas, ganaderas, silvícolas y pesqueras",
    "pf_enajenacion": "PF · Enajenación de bienes",
    "pf_adquisicion": "PF · Adquisición de bienes",
    "pf_intereses": "PF · Intereses",
    "pf_dividendos": "PF · Dividendos",
    "pf_demas_ingresos": "PF · Demás ingresos",
    # Personas morales
    "pm_no_lucrativas": "PM · Fines no lucrativos (Título III)",
    "pm_coordinados": "PM · Coordinados (autotransporte)",
    "pm_agape": "PM · AGAPE personas morales",
    # Anuales
    "anual_pf_general": "ANUAL · Persona física (todos sus ingresos)",
    "anual_pf_resico": "ANUAL · RESICO persona física",
    "anual_pm_general": "ANUAL · Persona moral, régimen general",
    "anual_pm_resico": "ANUAL · Persona moral RESICO",
}

TIPO_PERSONA_DE_REGIMEN = {
    "pf_sueldos_salarios": "fisica", "pf_actividad_empresarial": "fisica",
    "pf_resico": "fisica", "rif": "fisica", "pf_plataformas": "fisica",
    "pf_arrendamiento": "fisica", "pf_agape": "fisica",
    "pf_enajenacion": "fisica", "pf_adquisicion": "fisica",
    "pf_intereses": "fisica", "pf_dividendos": "fisica",
    "pf_demas_ingresos": "fisica",
    "pm_general": "moral", "pm_resico": "moral", "pm_no_lucrativas": "moral",
    "pm_coordinados": "moral", "pm_agape": "moral",
}

# Periodicidad de la declaración por régimen
PERIODICIDAD = {"rif": "bimestral"}          # el resto: mensual
ES_ANUAL = lambda r: r.startswith("anual_")  # noqa: E731

CAMPOS_EXTRA = {
    "pf_sueldos_salarios": [
        ("sueldos_gravados", "Sueldos y salarios gravados"),
        ("aguinaldo_gravado", "Aguinaldo gravado"),
        ("prima_vacacional_gravada", "Prima vacacional gravada"),
        ("ptu_gravada", "PTU gravada"),
        ("otros_gravados", "Otras percepciones gravadas"),
        ("subsidio_empleo", "Subsidio para el empleo"),
        ("isr_retenido", "ISR retenido por el patrón"),
    ],
    "pf_plataformas": [
        ("ingresos_plataforma", "Ingresos cobrados por plataforma"),
        ("tipo_actividad_tasa", "Tasa Art. 113-A % (2.1 transporte / 4 hospedaje / 1 bienes)"),
        ("isr_retenido_plataforma", "ISR retenido por la plataforma"),
        ("ingresos_directos_publico", "Ingresos directos al público (sin plataforma)"),
        ("iva_trasladado", "IVA trasladado"),
        ("iva_acreditable", "IVA acreditable"),
        ("iva_retenido_plataforma", "IVA retenido por la plataforma"),
        ("opta_pago_definitivo", "¿Pago definitivo? (1 = sí, 0 = no)"),
    ],
    "pf_arrendamiento": [
        ("ingresos_rentas", "Rentas cobradas del periodo"),
        ("usa_deduccion_ciega", "¿Deducción opcional 35%? (1 = sí, 0 = no)"),
        ("predial", "Impuesto predial"),
        ("mantenimiento", "Mantenimiento y conservación"),
        ("intereses_hipoteca", "Intereses reales de hipoteca"),
        ("seguros", "Primas de seguros"),
        ("depreciacion_construccion", "Depreciación de construcción (5%)"),
        ("otras_deducciones", "Otras deducciones autorizadas"),
        ("pagos_provisionales", "Pagos provisionales anteriores"),
        ("isr_retenido_pm", "ISR retenido por persona moral (10%)"),
        ("iva_trasladado", "IVA trasladado (locales comerciales)"),
        ("iva_acreditable", "IVA acreditable"),
        ("iva_retenido", "IVA retenido (por PM: 2/3 partes)"),
    ],
    "pf_agape": [
        ("ingresos_actividad", "Ingresos por actividad AGAPE"),
        ("deducciones_autorizadas", "Deducciones autorizadas"),
        ("ingreso_exento_uma", "Ingreso exento (40 UMA anuales/socio)"),
        ("aplica_reduccion", "¿Reducción 40% ISR? (1 = sí, 0 = no)"),
        ("pagos_provisionales", "Pagos provisionales anteriores"),
        ("iva_trasladado", "IVA trasladado"),
        ("iva_acreditable", "IVA acreditable"),
    ],
    "pf_enajenacion": [
        ("precio_venta", "Precio de venta"),
        ("costo_actualizado", "Costo comprobado actualizado"),
        ("gastos_notariales", "Gastos notariales, impuestos y derechos"),
        ("comisiones", "Comisiones y mediaciones"),
        ("anios_transcurridos", "Años transcurridos (máx. 20)"),
        ("isr_retenido_notario", "ISR retenido por el notario"),
        ("exento_casa_habitacion", "Exención casa habitación (700,000 UDIS)"),
    ],
    "pf_adquisicion": [
        ("valor_avaluo", "Valor del avalúo / bien adquirido"),
        ("deducciones_autorizadas", "Deducciones autorizadas (Art. 131)"),
        ("isr_retenido", "ISR retenido (20% provisional)"),
    ],
    "pf_intereses": [
        ("intereses_nominales", "Intereses nominales cobrados"),
        ("ajuste_inflacion", "Ajuste anual por inflación (deducible)"),
        ("isr_retenido_banco", "ISR retenido por la institución"),
    ],
    "pf_dividendos": [
        ("dividendo_percibido", "Dividendo percibido"),
        ("isr_pagado_moral", "ISR pagado por la persona moral (acreditable)"),
        ("proviene_de_cufin", "¿Proviene de CUFIN? (1 = sí, 0 = no)"),
        ("isr_retenido_10", "ISR retenido 10% (definitivo, Art. 140)"),
    ],
    "pf_demas_ingresos": [
        ("ingresos_percibidos", "Ingresos percibidos"),
        ("deducciones_autorizadas", "Deducciones autorizadas"),
        ("isr_retenido", "ISR retenido (20% provisional)"),
    ],
    "pm_no_lucrativas": [
        ("ingresos_propios_actividad", "Ingresos por su actividad (no gravados)"),
        ("remanente_distribuible", "Remanente distribuible (Art. 79)"),
        ("ingresos_gravados_no_relacionados", "Ingresos gravados no relacionados (>5%)"),
        ("isr_ret_salarios", "ISR retenido por salarios"),
        ("isr_ret_honorarios", "ISR retenido por honorarios"),
        ("iva_trasladado", "IVA trasladado"),
        ("iva_acreditable", "IVA acreditable"),
        ("iva_retenciones", "IVA retenciones a enterar"),
    ],
    "pm_coordinados": [
        ("ingresos_cobrados", "Ingresos cobrados del periodo"),
        ("deducciones_pagadas", "Deducciones pagadas (flujo)"),
        ("aplica_facilidades", "¿Facilidades administrativas? (1 = sí, 0 = no)"),
        ("deduccion_facilidades_pct", "% de deducción por facilidades (ej. 8)"),
        ("pagos_provisionales", "Pagos provisionales anteriores"),
        ("iva_trasladado", "IVA trasladado"),
        ("iva_acreditable", "IVA acreditable"),
        ("isr_ret_salarios", "ISR retenido por salarios"),
    ],
    "pm_agape": [
        ("ingresos_actividad", "Ingresos por actividad AGAPE"),
        ("deducciones_autorizadas", "Deducciones autorizadas"),
        ("numero_socios", "Número de socios (para exención)"),
        ("aplica_reduccion", "¿Reducción 30% ISR? (1 = sí, 0 = no)"),
        ("pagos_provisionales", "Pagos provisionales anteriores"),
        ("iva_trasladado", "IVA trasladado"),
        ("iva_acreditable", "IVA acreditable"),
    ],
    # ---------------- ANUALES ----------------
    "anual_pf_general": [
        ("ingresos_actividad_empresarial", "Ingresos acumulables por actividad empresarial/profesional"),
        ("deducciones_actividad", "Deducciones autorizadas de la actividad"),
        ("ingresos_sueldos", "Ingresos por sueldos y salarios"),
        ("ingresos_arrendamiento", "Ingresos por arrendamiento"),
        ("deducciones_arrendamiento", "Deducciones de arrendamiento"),
        ("ingresos_intereses_reales", "Intereses reales acumulables"),
        ("otros_ingresos_acumulables", "Otros ingresos acumulables"),
        ("perdidas_fiscales_anteriores", "Pérdidas fiscales de ejercicios anteriores"),
        # Deducciones personales (Art. 151) — el sistema aplica el tope solo
        ("dp_honorarios_medicos", "Honorarios médicos, dentales y hospitalarios"),
        ("dp_gastos_funerarios", "Gastos funerarios"),
        ("dp_donativos", "Donativos (máx. 7% del ingreso del año anterior)"),
        ("dp_intereses_hipotecarios", "Intereses reales de crédito hipotecario"),
        ("dp_aportaciones_retiro", "Aportaciones complementarias de retiro"),
        ("dp_primas_seguros_gastos_medicos", "Primas de seguros de gastos médicos"),
        ("dp_transporte_escolar", "Transporte escolar obligatorio"),
        ("dp_colegiaturas", "Colegiaturas (topes por nivel)"),
        ("estimulo_colegiaturas_tope", "Tope aplicable de colegiaturas (calculado aparte)"),
        ("pagos_provisionales_efectuados", "Pagos provisionales efectuados en el ejercicio"),
        ("isr_retenido_total", "ISR retenido en el ejercicio (patrones, PM, bancos)"),
        ("subsidio_empleo_acreditado", "Subsidio para el empleo acreditado"),
    ],
    "anual_pf_resico": [
        ("ingresos_anuales_cobrados", "Ingresos anuales efectivamente cobrados"),
        ("isr_pagos_mensuales", "ISR pagado en los meses del ejercicio"),
        ("isr_retenido_pm", "ISR retenido por personas morales (1.25%)"),
    ],
    "anual_pm_general": [
        ("ingresos_acumulables", "Ingresos acumulables del ejercicio"),
        ("ajuste_anual_inflacion_acumulable", "Ajuste anual por inflación acumulable"),
        ("deducciones_autorizadas", "Deducciones autorizadas"),
        ("ajuste_anual_inflacion_deducible", "Ajuste anual por inflación deducible"),
        ("ptu_pagada_ejercicio", "PTU pagada en el ejercicio"),
        ("perdidas_fiscales_anteriores", "Pérdidas fiscales pendientes de amortizar"),
        ("pagos_provisionales_efectuados", "Pagos provisionales efectuados"),
        ("isr_retenido", "ISR retenido (intereses, etc.)"),
        ("estimulos_fiscales", "Estímulos fiscales acreditables"),
        ("isr_pagado_extranjero", "ISR pagado en el extranjero (acreditable)"),
    ],
    "anual_pm_resico": [
        ("ingresos_cobrados_ejercicio", "Ingresos efectivamente cobrados del ejercicio"),
        ("deducciones_pagadas_ejercicio", "Deducciones efectivamente pagadas"),
        ("ptu_pagada_ejercicio", "PTU pagada en el ejercicio"),
        ("perdidas_fiscales_anteriores", "Pérdidas fiscales pendientes"),
        ("pagos_provisionales_efectuados", "Pagos provisionales efectuados"),
        ("isr_retenido", "ISR retenido"),
    ],
}
