# -*- coding: utf-8 -*-
"""
INTEGRACIÓN CONTPAQi — ingesta del agente local
===============================================
El SQL Server de CONTPAQi vive en la PC del despacho y NUNCA se expone a
internet. Un AGENTE local (carpeta /agente) lee esas bases en modo estricto
de solo lectura y EMPUJA aquí los resúmenes por HTTPS.

Seguridad:
  - Token de agente en la variable de entorno AGENTE_CONTPAQ_TOKEN (el mismo
    va en el config.ini del agente). Si no está configurada, la integración
    responde 503: apagada por defecto.
  - Comparación en tiempo constante (hmac.compare_digest).
  - El agente identifica a cada empresa por su RFC; aquí se resuelve al
    cliente (el RFC viaja cifrado en la base, así que se compara en memoria,
    igual que en el alta masiva).
Todo lo recibido queda en snapshots_contpaq (uno por cliente+tipo+periodo) y
en la bitácora.
"""
import hmac
import os
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.models import Cliente, SnapshotContpaq, Usuario
from services import auditoria, carga_social, prediccion_fiscal
from services.auth import solo_equipo_contable

router = APIRouter(prefix="/api/integracion/contpaq", tags=["Integración CONTPAQ"])


def _agente(x_token_agente: str = Header(None)) -> str:
    esperado = os.environ.get("AGENTE_CONTPAQ_TOKEN", "")
    if not esperado:
        raise HTTPException(503, "La integración CONTPAQ no está configurada "
                                 "(falta AGENTE_CONTPAQ_TOKEN en el servidor)")
    if not x_token_agente or not hmac.compare_digest(x_token_agente, esperado):
        raise HTTPException(401, "Token de agente inválido")
    return "agente"


def _cliente_por_rfc(db: Session, rfc: str) -> Cliente:
    rfc = (rfc or "").upper().replace(" ", "").replace("-", "")
    # El RFC va cifrado en la base: se compara en memoria (pocos cientos).
    for c in db.query(Cliente).all():
        if c.rfc == rfc:
            return c
    raise HTTPException(404, f"Ningún cliente tiene el RFC {rfc}: revise el "
                             f"mapeo empresa→RFC en el config.ini del agente")


def _guardar(db: Session, cliente_id: int, tipo: str, anio: int, mes: int,
             datos: dict, origen: str | None):
    snap = (db.query(SnapshotContpaq)
            .filter_by(cliente_id=cliente_id, tipo=tipo, anio=anio, mes=mes)
            .first())
    if snap:
        snap.datos, snap.origen = datos, origen
    else:
        snap = SnapshotContpaq(cliente_id=cliente_id, tipo=tipo, anio=anio,
                               mes=mes, datos=datos, origen=origen)
        db.add(snap)
    db.flush()
    return snap


# ---------------------------------------------------------------------------
# 1) RESULTADOS VISUALES (CONTPAQi Contabilidad → tablero del cliente)
# ---------------------------------------------------------------------------
class IngestaResultados(BaseModel):
    rfc: str
    anio: int
    meses: list          # [{mes, ingresos, costos, gastos, detalle:[{rubro, familia_sat, monto}]}]
    origen: str | None = None


@router.post("/resultados")
def recibir_resultados(payload: IngestaResultados, request: Request,
                       _: str = Depends(_agente), db: Session = Depends(get_db)):
    c = _cliente_por_rfc(db, payload.rfc)
    meses = []
    for m in payload.meses:
        ing, cos, gas = (round(float(m.get(k, 0) or 0), 2)
                         for k in ("ingresos", "costos", "gastos"))
        meses.append({"mes": int(m["mes"]), "ingresos": ing, "costos": cos,
                      "gastos": gas, "utilidad": round(ing - cos - gas, 2),
                      "detalle": m.get("detalle") or []})
    snap = _guardar(db, c.id, "resultados", payload.anio, 0,
                    {"meses": sorted(meses, key=lambda x: x["mes"])},
                    payload.origen)
    auditoria.registrar(db, usuario_id=None, accion="ingesta_contpaq_resultados",
                        tabla_afectada="snapshots_contpaq", registro_id=snap.id,
                        request=request, cliente=c.nombre_comercial,
                        anio=payload.anio, meses=len(meses))
    db.commit()
    return {"ok": True, "cliente": c.nombre_comercial, "meses": len(meses)}


# ---------------------------------------------------------------------------
# 2) CARGA SOCIAL PROYECTADA (CONTPAQi Nóminas → ISN + IMSS/Infonavit)
# ---------------------------------------------------------------------------
class IngestaNomina(BaseModel):
    rfc: str
    anio: int
    mes: int
    dias: int                     # días naturales del mes a proyectar
    empleados: list               # [{codigo?, sdi, salario_diario, dias?}]
    tasa_isn: float | None = None
    prima_riesgo: float | None = None
    origen: str | None = None


@router.post("/nomina")
def recibir_nomina(payload: IngestaNomina, request: Request,
                   _: str = Depends(_agente), db: Session = Depends(get_db)):
    c = _cliente_por_rfc(db, payload.rfc)
    proyeccion = carga_social.proyectar_carga_social(
        payload.empleados, payload.dias,
        tasa_isn=payload.tasa_isn or carga_social.TASA_ISN_ZACATECAS,
        prima_riesgo=payload.prima_riesgo or carga_social.PRIMA_RIESGO_DEFAULT)
    snap = _guardar(db, c.id, "nomina", payload.anio, payload.mes,
                    {"proyeccion": proyeccion}, payload.origen)
    auditoria.registrar(db, usuario_id=None, accion="ingesta_contpaq_nomina",
                        tabla_afectada="snapshots_contpaq", registro_id=snap.id,
                        request=request, cliente=c.nombre_comercial,
                        empleados=len(payload.empleados),
                        total=proyeccion["total_carga_social"])
    db.commit()
    return {"ok": True, "cliente": c.nombre_comercial, "proyeccion": proyeccion}


# ---------------------------------------------------------------------------
# 3) PREDICCIÓN FISCAL HÍBRIDA (historial de pólizas → ISR/IVA estimados)
# ---------------------------------------------------------------------------
class IngestaHistorial(BaseModel):
    rfc: str
    anio: int
    mes: int                      # mes en curso que se proyecta
    dia: int                      # día "de hoy" en la extracción
    dias_mes: int
    ingreso_real_mtd: float       # ingreso real acumulado del mes a la fecha
    historial: list               # [{mes, anio, ingreso_total, ingreso_ultimos_3_dias}]
    gastos: list                  # [{mes, anio, gasto_total}]
    iva_acreditable_hist: list | None = None
    extras: dict | None = None    # p. ej. {"coeficiente_utilidad": 0.10}
    polizas_mes_actual: int | None = None   # 0 = el mes no se ha capturado
    modo: str = "auto"            # auto | hibrida | estacional
    xml: dict | None = None       # {"ingresos_mtd", "egresos_mtd", "global_emitida"}
    origen: str | None = None


@router.post("/historial-fiscal")
def recibir_historial(payload: IngestaHistorial, request: Request,
                      _: str = Depends(_agente), db: Session = Depends(get_db)):
    c = _cliente_por_rfc(db, payload.rfc)
    if not c.regimen_fiscal:
        raise HTTPException(409, f"{c.nombre_comercial} no tiene régimen "
                                 f"fiscal capturado: la predicción necesita "
                                 f"saber con qué hoja calcular")
    pred = prediccion_fiscal.predecir(
        payload.historial, payload.gastos, payload.ingreso_real_mtd,
        payload.dia, payload.dias_mes, payload.mes, c.regimen_fiscal,
        iva_acreditable_hist=payload.iva_acreditable_hist,
        extras=payload.extras, anio=payload.anio,
        polizas_mes_actual=payload.polizas_mes_actual, modo=payload.modo,
        xml=payload.xml)
    snap = _guardar(db, c.id, "prediccion", payload.anio, payload.mes,
                    {"prediccion": pred, "dia": payload.dia,
                     "regimen": c.regimen_fiscal}, payload.origen)
    auditoria.registrar(db, usuario_id=None, accion="ingesta_contpaq_prediccion",
                        tabla_afectada="snapshots_contpaq", registro_id=snap.id,
                        request=request, cliente=c.nombre_comercial,
                        confianza=pred["confianza"],
                        estimado=pred["escenarios"]["central"].get("total_estimado"))
    db.commit()
    return {"ok": True, "cliente": c.nombre_comercial, "prediccion": pred}


# ---------------------------------------------------------------------------
# Consulta del equipo (la calculadora y el ciclo patronal los muestran)
# ---------------------------------------------------------------------------
@router.get("/{cliente_id}")
def snapshots_de_cliente(cliente_id: int, anio: int, mes: int,
                         u: Usuario = Depends(solo_equipo_contable),
                         db: Session = Depends(get_db)):
    q = db.query(SnapshotContpaq).filter_by(cliente_id=cliente_id)
    out = {}
    for tipo, m in (("resultados", 0), ("nomina", mes), ("prediccion", mes)):
        s = q.filter_by(tipo=tipo, anio=anio, mes=m).first()
        if s:
            out[tipo] = {"datos": s.datos, "origen": s.origen,
                         "recibido_en": s.recibido_en.isoformat()}
    return out
