# -*- coding: utf-8 -*-
"""
INVENTARIO DE SALDOS A FAVOR
============================
Cuando una declaración arroja saldo a favor, ese dinero NO se pierde: queda
"en inventario" hasta que se aplica (compensa) contra un impuesto futuro o
se solicita en devolución.

El problema real que resuelve: pueden existir VARIOS saldos a favor
simultáneos, y una sola declaración puede aplicar una parte de uno de ellos,
dejando un REMANENTE. Sin control, se pierde el rastro de cuánto queda de
cada uno y de qué declaración salió.

Este módulo lleva, por cada saldo:
  - monto ORIGINAL (el que arrojó la declaración)
  - monto APLICADO (suma de todas sus aplicaciones)
  - REMANENTE (lo que aún se puede usar)
  - la DECLARACIÓN QUE LO ORIGINÓ: periodo, número de operación y su
    comprobante en PDF, siempre a la mano (el SAT los pide al compensar)
  - cada APLICACIÓN: cuánto, en qué declaración, contra qué impuesto

Además avisa de la PRESCRIPCIÓN: los saldos a favor prescriben a los 5 años
(Art. 22 CFF); el sistema marca los que están por vencer.
"""
from datetime import date, datetime

from fastapi import (APIRouter, Depends, File, Form, HTTPException, Request,
                     UploadFile)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.models import (AplicacionSaldoFavor, CategoriaDocumento, Cliente,
                           DocumentoClave, SaldoFavor, Usuario)
from services import almacenamiento, auditoria
from services.auth import solo_equipo_contable

router = APIRouter(prefix="/api/saldos-favor", tags=["Saldos a favor"])

IMPUESTOS = ("isr", "iva", "ieps", "otro")
NOMBRE_IMPUESTO = {"isr": "ISR", "iva": "IVA", "ieps": "IEPS", "otro": "Otro"}
DIAS_ALERTA_PRESCRIPCION = 180


def _serializar(s: SaldoFavor, db: Session) -> dict:
    hoy = date.today()
    origen = s.fecha_presentacion or date(s.anio, s.mes or 12, 1)
    prescribe = date(origen.year + SaldoFavor.ANIOS_PRESCRIPCION,
                     origen.month, origen.day)
    dias = (prescribe - hoy).days
    return {
        "id": s.id, "cliente_id": s.cliente_id,
        "cliente": s.cliente.nombre_comercial if s.cliente else None,
        "impuesto": s.impuesto,
        "impuesto_nombre": NOMBRE_IMPUESTO.get(s.impuesto, s.impuesto),
        "periodo": s.periodo, "mes": s.mes, "anio": s.anio,
        "es_anual": s.es_anual,
        "monto_original": s.monto_original,
        "monto_aplicado": s.monto_aplicado or 0,
        "remanente": s.remanente,
        "numero_operacion": s.numero_operacion,
        "fecha_presentacion": (str(s.fecha_presentacion)
                               if s.fecha_presentacion else None),
        "comprobante_documento_id": s.comprobante_documento_id,
        "estatus": s.estatus,
        "notas": s.notas,
        "prescribe": str(prescribe),
        "dias_para_prescribir": dias,
        "por_prescribir": 0 < dias <= DIAS_ALERTA_PRESCRIPCION,
        "prescrito": dias <= 0,
        "aplicaciones": [{
            "id": a.id, "monto": a.monto_aplicado,
            "periodo": (f"{a.mes_aplicacion:02d}/{a.anio_aplicacion}"
                        if a.mes_aplicacion else f"Anual {a.anio_aplicacion}"),
            "impuesto_destino": NOMBRE_IMPUESTO.get(a.impuesto_destino,
                                                    a.impuesto_destino),
            "numero_operacion_destino": a.numero_operacion_destino,
            "fecha": a.timestamp.isoformat() if a.timestamp else None,
        } for a in sorted(s.aplicaciones, key=lambda x: x.id)],
    }


@router.get("")
def listar_saldos(cliente_id: int | None = None,
                  solo_disponibles: bool = False,
                  u: Usuario = Depends(solo_equipo_contable),
                  db: Session = Depends(get_db)):
    """
    Inventario completo. Con `solo_disponibles=true` devuelve únicamente los
    que aún tienen remanente (lo que el contador necesita al momento de
    decidir qué aplicar en la declaración del mes).
    """
    q = db.query(SaldoFavor)
    if cliente_id:
        q = q.filter(SaldoFavor.cliente_id == cliente_id)
    saldos = [_serializar(s, db)
              for s in q.order_by(SaldoFavor.anio.desc(),
                                  SaldoFavor.mes.desc().nullslast()).all()]
    if solo_disponibles:
        saldos = [s for s in saldos if s["remanente"] > 0.005
                  and s["estatus"] == "disponible"]
    # ⚠ El saldo a favor es PERSONAL E INTRANSFERIBLE: sumar los de varios
    # clientes no significa nada (nadie puede aplicar el saldo de otro).
    # Solo se totaliza cuando se está viendo UN cliente; si no, se agrupa.
    if cliente_id:
        total = round(sum(s["remanente"] for s in saldos
                          if s["estatus"] == "disponible"), 2)
        return {"saldos": saldos, "cliente_id": cliente_id,
                "remanente_del_cliente": total}
    por_cliente = {}
    for s_ in saldos:
        g = por_cliente.setdefault(s_["cliente_id"], {
            "cliente_id": s_["cliente_id"], "cliente": s_.get("cliente"),
            "remanente": 0.0, "saldos": []})
        g["saldos"].append(s_)
        if s_["estatus"] == "disponible":
            g["remanente"] = round(g["remanente"] + s_["remanente"], 2)
    return {"saldos": saldos,
            "por_cliente": sorted(por_cliente.values(),
                                  key=lambda g: -g["remanente"]),
            "nota": ("El saldo a favor es personal e intransferible: se "
                     "muestra por cliente, nunca sumado entre ellos.")}


class AltaSaldo(BaseModel):
    cliente_id: int
    impuesto: str                    # isr | iva | ieps | otro
    anio: int
    mes: int | None = None           # None si es de la declaración anual
    es_anual: bool = False
    monto_original: float
    numero_operacion: str | None = None
    fecha_presentacion: date | None = None
    calculo_id: int | None = None
    notas: str | None = None


@router.post("")
def registrar_saldo(payload: AltaSaldo, request: Request,
                    u: Usuario = Depends(solo_equipo_contable),
                    db: Session = Depends(get_db)):
    """
    Registra un saldo a favor que arrojó una declaración. Normalmente se
    dispara solo al presentar la declaración, pero también puede capturarse
    a mano (por ejemplo, saldos históricos de antes del sistema).
    """
    if payload.impuesto not in IMPUESTOS:
        raise HTTPException(400, f"Impuesto no válido: {', '.join(IMPUESTOS)}")
    if payload.monto_original <= 0:
        raise HTTPException(400, "El monto debe ser mayor a cero")
    if not db.query(Cliente).get(payload.cliente_id):
        raise HTTPException(404, "Cliente no encontrado")

    saldo = SaldoFavor(
        cliente_id=payload.cliente_id, impuesto=payload.impuesto,
        mes=None if payload.es_anual else payload.mes, anio=payload.anio,
        es_anual=payload.es_anual,
        monto_original=round(payload.monto_original, 2), monto_aplicado=0,
        numero_operacion=payload.numero_operacion,
        fecha_presentacion=payload.fecha_presentacion or date.today(),
        calculo_id=payload.calculo_id, notas=payload.notas,
        estatus="disponible", registrado_por_id=u.id)
    db.add(saldo)
    db.flush()
    auditoria.registrar(db, usuario_id=u.id, accion="alta_saldo_favor",
                        tabla_afectada="saldos_favor", registro_id=saldo.id,
                        request=request, impuesto=payload.impuesto,
                        monto=payload.monto_original, periodo=saldo.periodo)
    db.commit()
    return _serializar(saldo, db)


class AplicacionSaldo(BaseModel):
    monto: float
    anio_aplicacion: int
    mes_aplicacion: int | None = None
    impuesto_destino: str
    numero_operacion_destino: str | None = None
    calculo_id: int | None = None


class EdicionSaldo(BaseModel):
    """Corrección de un saldo mal capturado (error de dedo)."""
    impuesto: str | None = None
    anio: int | None = None
    mes: int | None = None
    es_anual: bool | None = None
    monto_original: float | None = None
    numero_operacion: str | None = None
    fecha_presentacion: date | None = None
    notas: str | None = None


@router.put("/{saldo_id}")
def editar_saldo(saldo_id: int, payload: EdicionSaldo, request: Request,
                 u: Usuario = Depends(solo_equipo_contable),
                 db: Session = Depends(get_db)):
    """
    Corrige un saldo capturado con error. CANDADO: el monto no puede quedar
    por debajo de lo ya aplicado (si no, el remanente sería negativo y la
    declaración donde se aplicó quedaría descuadrada).
    """
    s_ = db.query(SaldoFavor).get(saldo_id)
    if not s_:
        raise HTTPException(404, "Saldo a favor no encontrado")
    cambios = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "impuesto" in cambios and cambios["impuesto"] not in IMPUESTOS:
        raise HTTPException(400, f"Impuesto no válido. Use: {', '.join(IMPUESTOS)}")
    if "monto_original" in cambios:
        aplicado = float(s_.monto_aplicado or 0)
        if cambios["monto_original"] < aplicado - 0.005:
            raise HTTPException(409,
                f"No puede bajar el monto a ${cambios['monto_original']:,.2f}: "
                f"de este saldo ya se aplicaron ${aplicado:,.2f}. Primero "
                f"revierta las aplicaciones que correspondan.")
        if cambios["monto_original"] <= 0:
            raise HTTPException(400, "El monto debe ser mayor a cero")
    difs = {}
    for campo, nuevo in cambios.items():
        viejo_v = getattr(s_, campo, None)
        if viejo_v != nuevo:
            difs[campo] = {"antes": str(viejo_v), "ahora": str(nuevo)}
            setattr(s_, campo, nuevo)
    if not difs:
        return {"ok": True, "sin_cambios": True}
    auditoria.registrar(db, usuario_id=u.id, accion="edicion_saldo_favor",
                        tabla_afectada="saldos_favor", registro_id=s_.id,
                        request=request, cambios=difs)
    db.commit()
    return {"ok": True, "cambios": list(difs.keys()), "saldo": _serializar(s_, db)}


@router.post("/{saldo_id}/aplicar")
def aplicar_saldo(saldo_id: int, payload: AplicacionSaldo, request: Request,
                  u: Usuario = Depends(solo_equipo_contable),
                  db: Session = Depends(get_db)):
    """
    Aplica (compensa) una parte —o todo— del saldo contra un impuesto de una
    declaración posterior. El REMANENTE baja automáticamente y el saldo se
    marca 'agotado' cuando llega a cero. Nunca se puede aplicar más de lo
    que queda.
    """
    saldo = db.query(SaldoFavor).get(saldo_id)
    if not saldo:
        raise HTTPException(404, "Saldo a favor no encontrado")
    if saldo.estatus not in ("disponible",):
        raise HTTPException(409, f"Este saldo está '{saldo.estatus}': no se "
                                 f"puede aplicar")
    if payload.impuesto_destino not in IMPUESTOS:
        raise HTTPException(400, "Impuesto destino no válido")
    monto = round(payload.monto, 2)
    if monto <= 0:
        raise HTTPException(400, "El monto a aplicar debe ser mayor a cero")
    if monto > saldo.remanente + 0.005:
        raise HTTPException(400, f"No puede aplicar ${monto:,.2f}: el "
                                 f"remanente de este saldo es "
                                 f"${saldo.remanente:,.2f}")

    aplicacion = AplicacionSaldoFavor(
        saldo_favor_id=saldo.id, monto_aplicado=monto,
        mes_aplicacion=payload.mes_aplicacion,
        anio_aplicacion=payload.anio_aplicacion,
        impuesto_destino=payload.impuesto_destino,
        numero_operacion_destino=payload.numero_operacion_destino,
        calculo_id=payload.calculo_id, aplicado_por_id=u.id)
    db.add(aplicacion)
    saldo.monto_aplicado = round((saldo.monto_aplicado or 0) + monto, 2)
    if saldo.remanente <= 0.005:
        saldo.estatus = "agotado"
    db.flush()

    auditoria.registrar(db, usuario_id=u.id, accion="aplicacion_saldo_favor",
                        tabla_afectada="saldos_favor", registro_id=saldo.id,
                        request=request, monto=monto,
                        origen=saldo.periodo,
                        destino=(f"{payload.mes_aplicacion:02d}/{payload.anio_aplicacion}"
                                 if payload.mes_aplicacion
                                 else f"Anual {payload.anio_aplicacion}"),
                        impuesto=payload.impuesto_destino,
                        remanente=saldo.remanente)
    db.commit()
    return _serializar(saldo, db)


@router.post("/{saldo_id}/comprobante")
def adjuntar_comprobante(saldo_id: int, request: Request,
                         archivo_pdf: UploadFile = File(...),
                         numero_operacion: str = Form(None),
                         u: Usuario = Depends(solo_equipo_contable),
                         db: Session = Depends(get_db)):
    """
    Adjunta el COMPROBANTE de la declaración que originó el saldo (la
    declaración en sí). Es el documento que el SAT pide al compensar o al
    solicitar devolución: aquí queda para siempre, a un clic.
    """
    saldo = db.query(SaldoFavor).get(saldo_id)
    if not saldo:
        raise HTTPException(404, "Saldo a favor no encontrado")
    if archivo_pdf.content_type != "application/pdf":
        raise HTTPException(400, "El comprobante debe ser PDF")

    ruta = almacenamiento.guardar_documento(
        archivo_pdf.file.read(), f"documentos_clave/cliente{saldo.cliente_id}",
        f"comprobante_saldo_{saldo.anio}_{saldo.mes or 'anual'}_{saldo.impuesto}.pdf")
    doc = DocumentoClave(cliente_id=saldo.cliente_id,
                         categoria=CategoriaDocumento.COMPROBANTE_DECLARACION,
                         ruta_archivo=ruta, anio=saldo.anio,
                         mes=saldo.mes or 12)
    db.add(doc)
    db.flush()
    saldo.comprobante_documento_id = doc.id
    if numero_operacion:
        saldo.numero_operacion = numero_operacion
    auditoria.registrar(db, usuario_id=u.id, accion="comprobante_saldo_favor",
                        tabla_afectada="saldos_favor", registro_id=saldo.id,
                        request=request, documento_id=doc.id)
    db.commit()
    return _serializar(saldo, db)


class CambioEstatus(BaseModel):
    estatus: str      # disponible | en_devolucion | devuelto | prescrito
    notas: str | None = None


@router.post("/{saldo_id}/estatus")
def cambiar_estatus(saldo_id: int, payload: CambioEstatus, request: Request,
                    u: Usuario = Depends(solo_equipo_contable),
                    db: Session = Depends(get_db)):
    """Marca el saldo en devolución, devuelto o prescrito (con nota)."""
    validos = ("disponible", "en_devolucion", "devuelto", "prescrito")
    if payload.estatus not in validos:
        raise HTTPException(400, f"Estatus no válido: {', '.join(validos)}")
    saldo = db.query(SaldoFavor).get(saldo_id)
    if not saldo:
        raise HTTPException(404, "Saldo a favor no encontrado")

    anterior = saldo.estatus
    saldo.estatus = payload.estatus
    if payload.notas:
        saldo.notas = payload.notas
    auditoria.registrar(db, usuario_id=u.id, accion="estatus_saldo_favor",
                        tabla_afectada="saldos_favor", registro_id=saldo.id,
                        request=request, antes=anterior, ahora=payload.estatus)
    db.commit()
    return _serializar(saldo, db)
