# -*- coding: utf-8 -*-
"""
SOLICITUD DE FACTURAS — el cliente pide su factura como la necesita
===================================================================
Muchos clientes del despacho no facturan ellos mismos: le hablan a Pao o al
contador ("hazme una factura a tal RFC, de tanto, para gastos en general").
Este módulo formaliza esa llamada:

  1. El CLIENTE la solicita desde su portal, con los datos del receptor y
     las claves del SAT (uso de CFDI, forma y método de pago).
  2. El EQUIPO la ve en su sección "Facturas", la toma (en proceso), y al
     timbrar sube el PDF (y el XML si quiere): la factura queda en la
     BÓVEDA del cliente y la solicitud pasa a "emitida".
  3. Si algo no procede (RFC mal, receptor no localizado...), se RECHAZA con
     motivo, y el cliente lo ve tal cual en su portal.

El estatus vive aquí; el documento final vive en la bóveda (categoría
factura_emitida), como todo lo demás del expediente.
"""
from fastapi import (APIRouter, Depends, File, Form, HTTPException, Request,
                     UploadFile)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.models import (CategoriaDocumento, Cliente, DocumentoClave,
                           SolicitudFactura, Usuario)
from services import almacenamiento, auditoria
from services.auth import cliente_autenticado, solo_equipo_contable

router = APIRouter(tags=["Facturas"])

USOS_CFDI = ("G01", "G02", "G03", "I01", "I02", "I03", "I04", "I05", "I06",
             "I07", "I08", "D01", "D02", "D03", "D04", "D05", "D06", "D07",
             "D08", "D09", "D10", "S01", "CP01", "CN01")
FORMAS_PAGO = ("01", "02", "03", "04", "05", "06", "08", "12", "13", "14",
               "15", "17", "23", "24", "25", "26", "27", "28", "29", "30",
               "31", "99")
ESTATUS = ("solicitada", "en_proceso", "emitida", "rechazada")


def _serializar(f: SolicitudFactura) -> dict:
    return {"id": f.id, "cliente_id": f.cliente_id,
            "cliente": f.cliente.nombre_comercial if f.cliente else None,
            "receptor_rfc": f.receptor_rfc,
            "receptor_razon_social": f.receptor_razon_social,
            "receptor_cp": f.receptor_cp,
            "receptor_regimen": f.receptor_regimen,
            "uso_cfdi": f.uso_cfdi, "forma_pago": f.forma_pago,
            "metodo_pago": f.metodo_pago, "concepto": f.concepto,
            "monto": f.monto, "notas": f.notas, "estatus": f.estatus,
            "motivo_rechazo": f.motivo_rechazo,
            "atendida_por": (f.atendida_por.nombre if f.atendida_por else None),
            "factura_documento_id": f.factura_documento_id,
            "creado_en": f.creado_en.isoformat() if f.creado_en else None}


# ---------------------------------------------------------------------------
# PORTAL DEL CLIENTE
# ---------------------------------------------------------------------------
class NuevaSolicitud(BaseModel):
    receptor_rfc: str
    receptor_razon_social: str
    receptor_cp: str | None = None
    receptor_regimen: str | None = None     # clave SAT del receptor (601, 612…)
    uso_cfdi: str = "G03"
    forma_pago: str = "03"
    metodo_pago: str = "PUE"                # PUE | PPD
    concepto: str
    monto: float | None = None              # None = "el que corresponda"
    notas: str | None = None


@router.post("/api/portal/facturas")
def solicitar_factura(payload: NuevaSolicitud, request: Request,
                      cliente: Cliente = Depends(cliente_autenticado),
                      db: Session = Depends(get_db)):
    rfc = payload.receptor_rfc.upper().replace(" ", "").replace("-", "")
    if not (12 <= len(rfc) <= 13):
        raise HTTPException(400, "El RFC del receptor no se ve completo "
                                 "(12 letras y números para empresa, 13 para "
                                 "persona física)")
    if payload.uso_cfdi not in USOS_CFDI:
        raise HTTPException(400, "Uso de CFDI no válido")
    if payload.forma_pago not in FORMAS_PAGO:
        raise HTTPException(400, "Forma de pago no válida")
    if payload.metodo_pago not in ("PUE", "PPD"):
        raise HTTPException(400, "Método de pago no válido (PUE o PPD)")
    if not payload.concepto.strip():
        raise HTTPException(400, "Describa el concepto de la factura")
    if payload.monto is not None and payload.monto <= 0:
        raise HTTPException(400, "El monto debe ser mayor a cero (o déjelo "
                                 "vacío si el despacho lo determinará)")

    f = SolicitudFactura(
        cliente_id=cliente.id, receptor_rfc=rfc,
        receptor_razon_social=payload.receptor_razon_social.strip()[:200],
        receptor_cp=(payload.receptor_cp or "").strip()[:5] or None,
        receptor_regimen=(payload.receptor_regimen or "").strip()[:3] or None,
        uso_cfdi=payload.uso_cfdi, forma_pago=payload.forma_pago,
        metodo_pago=payload.metodo_pago,
        concepto=payload.concepto.strip()[:400],
        monto=round(payload.monto, 2) if payload.monto else None,
        notas=(payload.notas or "").strip()[:400] or None,
        estatus="solicitada")
    db.add(f)
    db.flush()
    auditoria.registrar(db, usuario_id=None, accion="solicitud_factura",
                        tabla_afectada="solicitudes_factura", registro_id=f.id,
                        request=request, cliente=cliente.nombre_comercial,
                        receptor=rfc, monto=payload.monto)
    db.commit()
    return {"ok": True, "folio": f.id,
            "mensaje": (f"Solicitud registrada con el folio #{f.id}. Su "
                        f"contador la recibió en este momento; en cuanto la "
                        f"factura esté timbrada aparecerá aquí mismo y en su "
                        f"bóveda.")}


@router.get("/api/portal/facturas")
def mis_facturas(cliente: Cliente = Depends(cliente_autenticado),
                 db: Session = Depends(get_db)):
    filas = (db.query(SolicitudFactura)
             .filter_by(cliente_id=cliente.id)
             .order_by(SolicitudFactura.id.desc()).limit(30).all())
    return [_serializar(f) for f in filas]


# ---------------------------------------------------------------------------
# EQUIPO
# ---------------------------------------------------------------------------
@router.get("/api/facturas")
def solicitudes(estatus: str | None = None,
                u: Usuario = Depends(solo_equipo_contable),
                db: Session = Depends(get_db)):
    q = db.query(SolicitudFactura)
    if estatus == "abiertas":
        q = q.filter(SolicitudFactura.estatus.in_(["solicitada", "en_proceso"]))
    elif estatus in ESTATUS:
        q = q.filter_by(estatus=estatus)
    return [_serializar(f)
            for f in q.order_by(SolicitudFactura.id.desc()).limit(80).all()]


class CambioEstatusFactura(BaseModel):
    estatus: str                    # en_proceso | rechazada
    motivo: str | None = None


@router.post("/api/facturas/{folio}/estatus")
def cambiar_estatus(folio: int, payload: CambioEstatusFactura, request: Request,
                    u: Usuario = Depends(solo_equipo_contable),
                    db: Session = Depends(get_db)):
    f = db.query(SolicitudFactura).get(folio)
    if not f:
        raise HTTPException(404, "Solicitud no encontrada")
    if payload.estatus not in ("en_proceso", "rechazada"):
        raise HTTPException(400, "Aquí solo se toma (en_proceso) o se rechaza; "
                                 "'emitida' se marca al subir la factura")
    if payload.estatus == "rechazada" and not (payload.motivo or "").strip():
        raise HTTPException(400, "Para rechazar, explique el motivo: el "
                                 "cliente lo verá en su portal")
    f.estatus = payload.estatus
    f.motivo_rechazo = (payload.motivo or "").strip()[:300] or None
    f.atendida_por_id = u.id
    auditoria.registrar(db, usuario_id=u.id, accion="estatus_factura",
                        tabla_afectada="solicitudes_factura", registro_id=f.id,
                        request=request, estatus=payload.estatus,
                        motivo=f.motivo_rechazo)
    db.commit()
    return _serializar(f)


@router.post("/api/facturas/{folio}/emitida")
def marcar_emitida(folio: int, request: Request,
                   archivo_pdf: UploadFile = File(...),
                   archivo_xml: UploadFile = File(None),
                   u: Usuario = Depends(solo_equipo_contable),
                   db: Session = Depends(get_db)):
    """
    La factura timbrada se sube aquí: el PDF (y el XML, si se adjunta) van a
    la BÓVEDA del cliente con categoría factura_emitida, y la solicitud pasa
    a 'emitida'. El cliente la descarga desde su portal, como todo lo demás.
    """
    f = db.query(SolicitudFactura).get(folio)
    if not f:
        raise HTTPException(404, "Solicitud no encontrada")
    if archivo_pdf.content_type != "application/pdf":
        raise HTTPException(400, "La factura debe subirse en PDF (el XML es "
                                 "opcional, como segundo archivo)")
    from datetime import date
    hoy = date.today()
    ruta = almacenamiento.guardar_documento(
        archivo_pdf.file.read(), f"documentos_clave/cliente{f.cliente_id}",
        f"factura_{f.id}_{f.receptor_rfc}.pdf")
    doc = DocumentoClave(cliente_id=f.cliente_id,
                         categoria=CategoriaDocumento.FACTURA_EMITIDA,
                         ruta_archivo=ruta, anio=hoy.year, mes=hoy.month)
    db.add(doc)
    db.flush()
    if archivo_xml is not None and archivo_xml.filename:
        ruta_xml = almacenamiento.guardar_documento(
            archivo_xml.file.read(), f"documentos_clave/cliente{f.cliente_id}",
            f"factura_{f.id}_{f.receptor_rfc}.xml")
        db.add(DocumentoClave(cliente_id=f.cliente_id,
                              categoria=CategoriaDocumento.FACTURA_EMITIDA,
                              ruta_archivo=ruta_xml, anio=hoy.year,
                              mes=hoy.month))
    f.estatus = "emitida"
    f.motivo_rechazo = None
    f.atendida_por_id = u.id
    f.factura_documento_id = doc.id
    auditoria.registrar(db, usuario_id=u.id, accion="factura_emitida",
                        tabla_afectada="solicitudes_factura", registro_id=f.id,
                        request=request, documento_id=doc.id,
                        receptor=f.receptor_rfc)
    db.commit()
    return _serializar(f)
