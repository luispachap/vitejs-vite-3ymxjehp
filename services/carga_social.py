# -*- coding: utf-8 -*-
"""
CARGA SOCIAL PROYECTADA — ISN + cuotas patronales IMSS/Infonavit
================================================================
Estima el costo patronal del mes a partir de la plantilla que el agente
extrae de CONTPAQi Nóminas (empleados activos, su SDI y su salario diario).

CÓMO SE CALCULA (validable contra el SUA):
  - SBC = min(SDI, 25 UMA)  ......................... tope de ley (Art. 28 LSS)
  - Cuota fija EyM  = 20.40% de UMA × días .......... por trabajador (Art. 106-I)
  - Excedente EyM   = 1.10% × (SBC − 3 UMA) × días .. solo si SBC > 3 UMA (106-II)
  - Prestaciones en dinero = 0.70% × SBC × días ..... (Art. 107)
  - Gastos médicos pensionados = 1.05% × SBC × días . (Art. 25)
  - Invalidez y vida = 1.75% × SBC × días ........... (Art. 147)
  - Guarderías = 1.00% × SBC × días ................. (Art. 211)
  - Retiro = 2.00% × SBC × días ..................... (Art. 168-I)
  - CEAV patronal = tasa escalonada × SBC × días .... reforma 2020, EN TRANSICIÓN
      2023→2030 la tasa sube por rangos de UMA (de 3.150% hasta 11.875%).
      ⚠ Capturar cada ejercicio la tabla vigente en TABLA_CEAV_PATRON; si un
      rango no está capturado se usa el piso legal 3.150% y se AVISA.
  - Riesgo de trabajo = prima de la empresa × SBC × días (default clase I)
  - Infonavit = 5.00% × SBC × días .................. (Art. 29 LINFONAVIT)
  - ISN = tasa estatal × (salario diario × días) .... Zacatecas 3% (configurable)
      ⚠ El ISN real grava las REMUNERACIONES PAGADAS del periodo; usar el
      salario diario × días es una aproximación razonable para proyección.

ES UNA PROYECCIÓN: no considera ausentismos, incapacidades ni variables del
bimestre. No sustituye al SUA; sirve para que el cliente vea venir el costo.
"""
from services.fiscal_catalogo import UMA_DIARIA   # una sola fuente de verdad
from services.fiscal import TASA_ISN_ZACATECAS

# --- Parámetros (verificar cada ejercicio, igual que las tarifas de ISR) ---
TOPE_SBC_UMAS = 25
PRIMA_RIESGO_DEFAULT = 0.54355     # % · clase I (la real la fija el IMSS por empresa)
TASAS_PATRON = {                   # % sobre SBC × días
    "prestaciones_dinero": 0.70,
    "gastos_medicos_pensionados": 1.05,
    "invalidez_y_vida": 1.75,
    "guarderias": 1.00,
    "retiro": 2.00,
    "infonavit": 5.00,
}
CUOTA_FIJA_EYM_PCT = 20.40         # % de UMA por día por trabajador
EXCEDENTE_EYM_PCT = 1.10           # % sobre (SBC − 3 UMA)

# CEAV patronal por rangos de SBC en UMAs. ⚠ EN TRANSICIÓN (2023–2030):
# capture aquí la tabla del ejercicio vigente. Piso legal: 3.150% (1 UMA).
TABLA_CEAV_PATRON = [
    # (SBC hasta N UMAs, tasa %)  ← capturar la tabla del ejercicio
    (1.00, 3.150),
]
CEAV_PISO = 3.150


def _tasa_ceav(sbc: float, uma: float) -> tuple[float, bool]:
    """Devuelve (tasa %, aproximada?) según el SBC en UMAs."""
    umas = sbc / uma
    for tope, tasa in sorted(TABLA_CEAV_PATRON):
        if umas <= tope:
            return tasa, False
    return CEAV_PISO, True          # rango no capturado → piso legal + aviso


def proyectar_carga_social(empleados: list, dias: int,
                           tasa_isn: float = TASA_ISN_ZACATECAS,
                           prima_riesgo: float = PRIMA_RIESGO_DEFAULT,
                           uma: float = UMA_DIARIA) -> dict:
    """
    empleados: [{"sdi": float, "salario_diario": float, "dias": int?}, ...]
      (si un empleado trae sus propios días —alta a media quincena— se usan)
    dias: días naturales del mes a proyectar.
    """
    r = lambda x: round(x + 1e-9, 2)
    tope_sbc = TOPE_SBC_UMAS * uma
    ramos = {k: 0.0 for k in ("cuota_fija_eym", "excedente_eym",
                              "prestaciones_dinero", "gastos_medicos_pensionados",
                              "invalidez_y_vida", "guarderias", "retiro",
                              "ceav", "riesgo_trabajo")}
    infonavit = base_isn = 0.0
    ceav_aproximada = False

    for e in empleados:
        d = int(e.get("dias") or dias)
        sdi = float(e.get("sdi") or 0)
        sd = float(e.get("salario_diario") or sdi)
        sbc = min(sdi, tope_sbc)
        base = sbc * d

        ramos["cuota_fija_eym"] += CUOTA_FIJA_EYM_PCT / 100 * uma * d
        if sbc > 3 * uma:
            ramos["excedente_eym"] += EXCEDENTE_EYM_PCT / 100 * (sbc - 3 * uma) * d
        for ramo, tasa in TASAS_PATRON.items():
            if ramo == "infonavit":
                infonavit += tasa / 100 * base
            else:
                ramos[ramo] += tasa / 100 * base
        tasa_ceav, aprox = _tasa_ceav(sbc, uma)
        ceav_aproximada = ceav_aproximada or aprox
        ramos["ceav"] += tasa_ceav / 100 * base
        ramos["riesgo_trabajo"] += prima_riesgo / 100 * base
        base_isn += sd * d

    ramos = {k: r(v) for k, v in ramos.items()}
    imss = r(sum(ramos.values()))
    infonavit = r(infonavit)
    isn = r(base_isn * tasa_isn / 100)

    avisos = ["Proyección estimada: no incluye ausentismos, incapacidades ni "
              "variables del bimestre. El cálculo oficial es el del SUA."]
    if ceav_aproximada:
        avisos.append("CEAV: hay salarios fuera de los rangos capturados; se "
                      "usó el piso legal de 3.150%. Capture la tabla del "
                      "ejercicio en TABLA_CEAV_PATRON para afinar.")
    avisos.append(f"ISN estimado con tasa estatal del {tasa_isn}% sobre "
                  f"salario diario × días (el impuesto real grava las "
                  f"remuneraciones pagadas del periodo).")

    return {
        "empleados": len(empleados),
        "dias": dias,
        "uma": uma,
        "prima_riesgo": prima_riesgo,
        "imss_patronal": {"ramos": ramos, "total": imss},
        "infonavit": infonavit,
        "isn": {"base": r(base_isn), "tasa": tasa_isn, "importe": isn},
        "total_carga_social": r(imss + infonavit + isn),
        "avisos": avisos,
    }
