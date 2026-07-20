# -*- coding: utf-8 -*-
"""
EXPEDIENTE DEL CLIENTE — todo su rastro documental, y lo que él sí ve
=====================================================================
Tres cosas que faltaban:

1. EXPEDIENTE COMPLETO para el equipo: el despacho guarda TODO (balanzas,
   cálculos del SUA, respaldos, papeles de trabajo) porque algún día hará
   falta. Hasta ahora no había forma de consultarlo desde la aplicación.

2. BÓVEDA DEL CLIENTE SIN PAJA: al cliente no le sirve —ni le interesa— ver
   el respaldo de CONTPAQ o la emisión del IDSE. Solo se le muestran los
   documentos que él podría necesitar (constancias, formatos de pago,
   facturas, recibos de nómina, sus comprobantes). Si algún cliente quiere
   ver todo, se le enciende el acceso ampliado por cliente.

3. RESUMEN FINANCIERO honesto: activo, pasivo y capital SOLO si el despacho
   emitió un estado financiero. Si no existe, el módulo no aparece: jamás
   se le enseñan cifras inventadas.

Incluye además el ESTADO DE CUENTA DE HONORARIOS en PDF con el formato del
despacho (cargos del periodo, adeudos previos, pagos y saldo).
"""
import io
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

import config
from database import get_db
from models.models import (AdeudoPrevio, CategoriaDocumento, Cliente,
                           DocumentoClave, EstadoFinanciero, EstatusPago,
                           HonorarioCobranza, Usuario)
from services import almacenamiento, auditoria
from services.auth import cliente_autenticado, solo_equipo_contable

router = APIRouter(tags=["Expediente y cobranza"])

# Lo que al CLIENTE sí le sirve tener a la mano. El resto es papel de trabajo
# interno: se conserva siempre, pero no se le enseña para no llenarlo de paja.
CATEGORIAS_DEL_CLIENTE = {
    CategoriaDocumento.ACTA_CONSTITUTIVA,
    CategoriaDocumento.OPINION_32D,
    CategoriaDocumento.CONSTANCIA_SITUACION_FISCAL,
    CategoriaDocumento.ESTADO_FINANCIERO_DICTAMINADO,
    CategoriaDocumento.ESTADO_FINANCIERO,
    CategoriaDocumento.ACUSE_DECLARACION,       # su formato de pago del SAT
    CategoriaDocumento.FORMATO_PAGO_IMSS,
    CategoriaDocumento.FORMATO_PAGO_ISN,
    CategoriaDocumento.RECIBO_NOMINA,
    CategoriaDocumento.FACTURA_EMITIDA,
    CategoriaDocumento.COMPROBANTE_PAGO,        # los que él mismo subió
    CategoriaDocumento.ESTADO_CUENTA_HONORARIOS,
}

NOMBRES = {
    CategoriaDocumento.ACTA_CONSTITUTIVA: "Acta constitutiva",
    CategoriaDocumento.OPINION_32D: "Opinión de cumplimiento 32-D",
    CategoriaDocumento.CONSTANCIA_SITUACION_FISCAL: "Constancia de situación fiscal",
    CategoriaDocumento.ESTADO_FINANCIERO_DICTAMINADO: "Estado financiero dictaminado",
    CategoriaDocumento.ESTADO_FINANCIERO: "Estado financiero",
    CategoriaDocumento.ACUSE_SAT: "Acuse del SAT",
    CategoriaDocumento.ACUSE_DECLARACION: "Formato de pago (línea de captura)",
    CategoriaDocumento.COMPROBANTE_DECLARACION: "Declaración presentada",
    CategoriaDocumento.COMPROBANTE_PAGO: "Comprobante de pago",
    CategoriaDocumento.BALANZA_COMPROBACION: "Balanza de comprobación",
    CategoriaDocumento.CEDULA_ISN: "Cédula del ISN",
    CategoriaDocumento.PROPUESTA_SIPARE: "Pago en SIPARE",
    CategoriaDocumento.AVISO_INFONAVIT: "Aviso Infonavit",
    CategoriaDocumento.EMISION_IDSE: "Emisión IDSE",
    CategoriaDocumento.CALCULO_SUA: "Cálculo SUA",
    CategoriaDocumento.FORMATO_PAGO_IMSS: "Formato de pago IMSS",
    CategoriaDocumento.FORMATO_PAGO_ISN: "Formato de pago ISN",
    CategoriaDocumento.RECIBO_NOMINA: "Recibo de nómina",
    CategoriaDocumento.RESPALDO_CONTPAQ: "Respaldo CONTPAQ",
    CategoriaDocumento.FACTURA_EMITIDA: "Factura emitida",
    CategoriaDocumento.ESTADO_CUENTA_HONORARIOS: "Estado de cuenta de honorarios",
}


def _doc(d: DocumentoClave) -> dict:
    return {"id": d.id, "categoria": d.categoria.value,
            "nombre": NOMBRES.get(d.categoria, d.categoria.value.replace("_", " ")),
            "anio": d.anio, "mes": d.mes,
            "para_el_cliente": d.categoria in CATEGORIAS_DEL_CLIENTE,
            "subido_en": d.subido_en.isoformat() if d.subido_en else None}


# ---------------------------------------------------------------------------
# 1) EXPEDIENTE COMPLETO (equipo)
# ---------------------------------------------------------------------------
@router.get("/api/clientes/{cliente_id}/expediente")
def expediente(cliente_id: int, anio: int | None = None,
               u: Usuario = Depends(solo_equipo_contable),
               db: Session = Depends(get_db)):
    """Todo el rastro documental del cliente, agrupado por ejercicio."""
    cliente = db.query(Cliente).get(cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    q = db.query(DocumentoClave).filter_by(cliente_id=cliente_id)
    if anio:
        q = q.filter_by(anio=anio)
    docs = q.order_by(DocumentoClave.anio.desc(), DocumentoClave.mes.desc(),
                      DocumentoClave.id.desc()).all()
    por_anio: dict[int, list] = {}
    for d in docs:
        por_anio.setdefault(d.anio, []).append(_doc(d))
    return {
        "cliente": cliente.nombre_comercial,
        "cliente_id": cliente.id,
        # Datos corregibles (cobranza y CONTPAQ) para editarlos aquí mismo
        "ficha": {
            "razon_social": cliente.razon_social,
            "rfc": cliente.rfc,
            "honorario_mensual": cliente.honorario_mensual,
            "periodicidad_honorario": cliente.periodicidad_honorario,
            "dia_corte_honorario": cliente.dia_corte_honorario,
            "bd_contpaq_contabilidad": cliente.bd_contpaq_contabilidad,
            "bd_contpaq_nomina": cliente.bd_contpaq_nomina,
            "bd_contpaq_add": cliente.bd_contpaq_add,
            "coeficiente_utilidad": cliente.coeficiente_utilidad,
            "boveda_completa": bool(cliente.boveda_completa),
            "regimen_fiscal": cliente.regimen_fiscal,
        },
        "total_documentos": len(docs),
        "ejercicios": [{"anio": a, "documentos": v}
                       for a, v in sorted(por_anio.items(), reverse=True)],
        "complementarias": _complementarias(db, cliente_id),
    }


def _complementarias(db: Session, cliente_id: int) -> list:
    """Periodos donde hubo complementaria, con las versiones archivadas."""
    from models.models import ObligacionMensual
    filas = (db.query(ObligacionMensual)
             .filter(ObligacionMensual.cliente_id == cliente_id,
                     ObligacionMensual.es_complementaria.is_(True))
             .order_by(ObligacionMensual.anio.desc(),
                       ObligacionMensual.mes.desc()).all())
    salida = []
    for o in filas:
        salida.append({
            "obligacion_id": o.id, "mes": o.mes, "anio": o.anio,
            "numero": o.numero_complementaria,
            "motivo": o.motivo_complementaria,
            "vigente": {"monto": o.monto_impuesto_sat,
                        "presentada": bool(o.ruta_archivo_linea_captura),
                        "pagada": bool(o.pagado_en)},
            "versiones_anteriores": [
                {"numero": v.get("numero"),
                 "monto": v.get("monto_impuesto_sat"),
                 "pagada": bool(v.get("pagado_en")),
                 "archivada_en": v.get("archivada_en"),
                 "archivada_por": v.get("archivada_por")}
                for v in (o.historial_complementarias or [])],
        })
    return salida


# ---------------------------------------------------------------------------
# 2) ADEUDOS PREVIOS (la cobranza arranca con la verdad)
# ---------------------------------------------------------------------------
class NuevoAdeudo(BaseModel):
    concepto: str
    monto: float
    fecha_origen: str | None = None
    notas: str | None = None


@router.get("/api/clientes/{cliente_id}/adeudos")
def listar_adeudos(cliente_id: int, u: Usuario = Depends(solo_equipo_contable),
                   db: Session = Depends(get_db)):
    filas = (db.query(AdeudoPrevio).filter_by(cliente_id=cliente_id)
             .order_by(AdeudoPrevio.id.desc()).all())
    return [{"id": a.id, "concepto": a.concepto,
             "monto_original": a.monto_original, "monto_pagado": a.monto_pagado,
             "saldo": round(float(a.monto_original or 0) - float(a.monto_pagado or 0), 2),
             "fecha_origen": str(a.fecha_origen) if a.fecha_origen else None,
             "notas": a.notas, "liquidado": a.liquidado} for a in filas]


@router.post("/api/clientes/{cliente_id}/adeudos")
def agregar_adeudo(cliente_id: int, payload: NuevoAdeudo, request: Request,
                   u: Usuario = Depends(solo_equipo_contable),
                   db: Session = Depends(get_db)):
    if not db.query(Cliente).get(cliente_id):
        raise HTTPException(404, "Cliente no encontrado")
    if payload.monto <= 0:
        raise HTTPException(400, "El monto del adeudo debe ser mayor a cero")
    a = AdeudoPrevio(cliente_id=cliente_id, concepto=payload.concepto.strip()[:200],
                     monto_original=round(payload.monto, 2), monto_pagado=0,
                     fecha_origen=(date.fromisoformat(payload.fecha_origen)
                                   if payload.fecha_origen else None),
                     notas=(payload.notas or "").strip()[:300] or None,
                     registrado_por_id=u.id)
    db.add(a)
    db.flush()
    auditoria.registrar(db, usuario_id=u.id, accion="adeudo_previo_registrado",
                        tabla_afectada="adeudos_previos", registro_id=a.id,
                        request=request, monto=payload.monto)
    db.commit()
    return {"ok": True, "id": a.id}


class AbonoAdeudo(BaseModel):
    monto: float


@router.post("/api/adeudos/{adeudo_id}/abono")
def abonar_adeudo(adeudo_id: int, payload: AbonoAdeudo, request: Request,
                  u: Usuario = Depends(solo_equipo_contable),
                  db: Session = Depends(get_db)):
    a = db.query(AdeudoPrevio).get(adeudo_id)
    if not a:
        raise HTTPException(404, "Adeudo no encontrado")
    saldo = float(a.monto_original or 0) - float(a.monto_pagado or 0)
    if payload.monto <= 0 or payload.monto > saldo + 0.01:
        raise HTTPException(400, f"El abono debe estar entre $0.01 y ${saldo:,.2f}")
    a.monto_pagado = round(float(a.monto_pagado or 0) + payload.monto, 2)
    a.liquidado = float(a.monto_pagado) >= float(a.monto_original) - 0.01
    auditoria.registrar(db, usuario_id=u.id, accion="abono_adeudo_previo",
                        tabla_afectada="adeudos_previos", registro_id=a.id,
                        request=request, monto=payload.monto)
    db.commit()
    return {"ok": True, "saldo": round(float(a.monto_original) - float(a.monto_pagado), 2),
            "liquidado": a.liquidado}


# ---------------------------------------------------------------------------
# 3) ESTADOS FINANCIEROS (fuente del resumen del portal)
# ---------------------------------------------------------------------------
class NuevoEstadoFinanciero(BaseModel):
    anio: int
    mes: int | None = None
    activo_total: float
    pasivo_total: float
    capital_total: float
    visible_para_cliente: bool = True


@router.post("/api/clientes/{cliente_id}/estado-financiero")
def guardar_estado_financiero(cliente_id: int, payload: NuevoEstadoFinanciero,
                              request: Request,
                              u: Usuario = Depends(solo_equipo_contable),
                              db: Session = Depends(get_db)):
    if not db.query(Cliente).get(cliente_id):
        raise HTTPException(404, "Cliente no encontrado")
    dif = abs((payload.activo_total) - (payload.pasivo_total + payload.capital_total))
    if dif > 1.0:
        raise HTTPException(400, f"El balance no cuadra por ${dif:,.2f}: "
                                 f"activo debe ser igual a pasivo + capital")
    ef = (db.query(EstadoFinanciero)
          .filter_by(cliente_id=cliente_id, anio=payload.anio, mes=payload.mes)
          .first())
    if not ef:
        ef = EstadoFinanciero(cliente_id=cliente_id, anio=payload.anio, mes=payload.mes)
        db.add(ef)
    ef.activo_total = round(payload.activo_total, 2)
    ef.pasivo_total = round(payload.pasivo_total, 2)
    ef.capital_total = round(payload.capital_total, 2)
    ef.visible_para_cliente = payload.visible_para_cliente
    ef.capturado_por_id = u.id
    db.flush()
    auditoria.registrar(db, usuario_id=u.id, accion="estado_financiero_capturado",
                        tabla_afectada="estados_financieros", registro_id=ef.id,
                        request=request, periodo=f"{payload.anio}-{payload.mes or 'anual'}")
    db.commit()
    return {"ok": True, "id": ef.id}


@router.get("/api/clientes/{cliente_id}/estados-financieros")
def listar_estados_financieros(cliente_id: int,
                               u: Usuario = Depends(solo_equipo_contable),
                               db: Session = Depends(get_db)):
    filas = (db.query(EstadoFinanciero).filter_by(cliente_id=cliente_id)
             .order_by(EstadoFinanciero.anio.desc(),
                       EstadoFinanciero.mes.desc().nullsfirst()).all())
    return [_ef(e) for e in filas]


def _ef(e: EstadoFinanciero) -> dict:
    activo = float(e.activo_total or 0)
    pasivo = float(e.pasivo_total or 0)
    return {"id": e.id, "anio": e.anio, "mes": e.mes,
            "activo_total": activo, "pasivo_total": pasivo,
            "capital_total": float(e.capital_total or 0),
            "razon_circulante": (round(activo / pasivo, 2) if pasivo else None),
            "visible_para_cliente": e.visible_para_cliente,
            "periodo": (f"{e.mes:02d}/{e.anio}" if e.mes else f"Ejercicio {e.anio}")}


@router.get("/api/portal/resumen-financiero")
def resumen_financiero_cliente(cliente: Cliente = Depends(cliente_autenticado),
                               db: Session = Depends(get_db)):
    """
    Solo si el despacho emitió un estado financiero. Si no hay, se devuelve
    vacío y el portal NO muestra el módulo: nada de cifras inventadas.
    """
    e = (db.query(EstadoFinanciero)
         .filter_by(cliente_id=cliente.id, visible_para_cliente=True)
         .order_by(EstadoFinanciero.anio.desc(),
                   EstadoFinanciero.mes.desc().nullsfirst()).first())
    if not e:
        return {"hay_estado_financiero": False}
    d = _ef(e)
    return {"hay_estado_financiero": True, **d,
            "leyenda": ("Cifras tomadas del estado financiero que le preparó "
                        "el despacho para este periodo. Es un resumen: el "
                        "detalle está en el documento completo de su bóveda.")}


# ---------------------------------------------------------------------------
# 4) ESTADO DE CUENTA DE HONORARIOS (PDF con el formato del despacho)
# ---------------------------------------------------------------------------
@router.get("/api/clientes/{cliente_id}/estado-cuenta")
def estado_cuenta_honorarios(cliente_id: int, request: Request,
                             anio: int | None = None,
                             u: Usuario = Depends(solo_equipo_contable),
                             db: Session = Depends(get_db)):
    """Estado de cuenta completo del ejercicio: cargos, adeudos, saldo."""
    cliente = db.query(Cliente).get(cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    anio = anio or date.today().year
    pdf = _construir_estado_cuenta(db, cliente, anio)
    auditoria.registrar(db, usuario_id=u.id, accion="estado_cuenta_generado",
                        tabla_afectada="clientes", registro_id=cliente.id,
                        request=request, ejercicio=anio)
    db.commit()
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition":
                             f'inline; filename="estado_cuenta_{cliente.id}_{anio}.pdf"'})


def _construir_estado_cuenta(db: Session, cliente: Cliente, anio: int) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas as _canvas

    AZUL = (10 / 255, 90 / 255, 160 / 255)
    MARINO = (10 / 255, 28 / 255, 51 / 255)
    GRIS = (0.42, 0.46, 0.53)
    LINEA = (0.85, 0.87, 0.90)
    MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
             "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

    honorarios = (db.query(HonorarioCobranza)
                  .filter_by(cliente_id=cliente.id, anio=anio)
                  .order_by(HonorarioCobranza.mes).all())
    adeudos = (db.query(AdeudoPrevio).filter_by(cliente_id=cliente.id)
               .order_by(AdeudoPrevio.id).all())

    buf = io.BytesIO()
    c = _canvas.Canvas(buf, pagesize=letter)
    ancho, alto = letter
    M = 52                                   # margen

    def money(v):
        return f"${float(v or 0):,.2f}"

    # ── Membrete ───────────────────────────────────────────────────────
    c.setFillColorRGB(*MARINO)
    c.rect(0, alto - 96, ancho, 96, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Times-Bold", 22)
    c.drawString(M, alto - 48, "Pacheco & Aparicio")
    c.setFont("Times-Roman", 10.5)
    c.drawString(M, alto - 66, "Consultoría Jurídica Fiscal")
    c.drawString(M, alto - 80, "C.P. y Lic. Rodolfo Pacheco Ortega · Fresnillo, Zacatecas")
    c.setFont("Times-Bold", 11)
    c.drawRightString(ancho - M, alto - 48, "ESTADO DE CUENTA")
    c.setFont("Times-Roman", 10)
    c.drawRightString(ancho - M, alto - 64, f"Honorarios · Ejercicio {anio}")
    c.drawRightString(ancho - M, alto - 78,
                      f"Emitido el {date.today().strftime('%d/%m/%Y')}")

    # ── Datos del cliente ──────────────────────────────────────────────
    y = alto - 130
    c.setFillColorRGB(*MARINO)
    c.setFont("Times-Bold", 13)
    c.drawString(M, y, cliente.razon_social or cliente.nombre_comercial)
    y -= 16
    c.setFont("Times-Roman", 10)
    c.setFillColorRGB(*GRIS)
    c.drawString(M, y, f"Nombre comercial: {cliente.nombre_comercial}")
    y -= 13
    c.drawString(M, y, f"RFC: {cliente.rfc}")
    if cliente.periodicidad_honorario:
        y -= 13
        c.drawString(M, y, "Honorario contratado: "
                           f"{money(cliente.honorario_mensual)} "
                           f"({cliente.periodicidad_honorario})")

    # ── Tabla de cargos del ejercicio ──────────────────────────────────
    y -= 30
    c.setFillColorRGB(*MARINO)
    c.setFont("Times-Bold", 11)
    c.drawString(M, y, "Honorarios del ejercicio")
    y -= 8
    c.setStrokeColorRGB(*LINEA)
    c.line(M, y, ancho - M, y)
    y -= 16

    c.setFont("Times-Bold", 9.5)
    c.setFillColorRGB(*GRIS)
    c.drawString(M, y, "PERIODO")
    c.drawString(M + 150, y, "VENCIMIENTO")
    c.drawString(M + 270, y, "ESTATUS")
    c.drawRightString(ancho - M, y, "IMPORTE")
    y -= 6
    c.line(M, y, ancho - M, y)
    y -= 16

    total_cargos = total_pagado = total_pendiente = 0.0
    c.setFont("Times-Roman", 10)
    if not honorarios:
        c.setFillColorRGB(*GRIS)
        c.drawString(M, y, "Sin honorarios registrados en este ejercicio.")
        y -= 18
    for h in honorarios:
        if y < 150:                                # salto de página
            c.showPage()
            y = alto - 80
            c.setFont("Times-Roman", 10)
        monto = float(h.monto_honorario or 0)
        total_cargos += monto
        pagado = h.estatus_pago == EstatusPago.PAGADO
        if pagado:
            total_pagado += monto
        else:
            total_pendiente += monto
        c.setFillColorRGB(*MARINO)
        c.drawString(M, y, f"{MESES[h.mes]} {h.anio}")
        c.setFillColorRGB(*GRIS)
        c.drawString(M + 150, y, str(h.fecha_limite_pago or "—"))
        etiqueta = h.estatus_pago.value.replace("_", " ").capitalize()
        c.setFillColorRGB(*(0.09, 0.48, 0.27) if pagado else (0.70, 0.21, 0.16))
        c.drawString(M + 270, y, etiqueta)
        c.setFillColorRGB(*MARINO)
        c.drawRightString(ancho - M, y, money(monto))
        y -= 17

    # ── Adeudos previos ────────────────────────────────────────────────
    saldo_adeudos = sum(float(a.monto_original or 0) - float(a.monto_pagado or 0)
                        for a in adeudos if not a.liquidado)
    if adeudos:
        y -= 14
        c.setFillColorRGB(*MARINO)
        c.setFont("Times-Bold", 11)
        c.drawString(M, y, "Adeudos anteriores")
        y -= 8
        c.setStrokeColorRGB(*LINEA)
        c.line(M, y, ancho - M, y)
        y -= 16
        c.setFont("Times-Roman", 10)
        for a in adeudos:
            if y < 130:
                c.showPage()
                y = alto - 80
                c.setFont("Times-Roman", 10)
            saldo = float(a.monto_original or 0) - float(a.monto_pagado or 0)
            c.setFillColorRGB(*MARINO)
            c.drawString(M, y, a.concepto[:58])
            c.setFillColorRGB(*GRIS)
            c.drawString(M + 300, y, "Liquidado" if a.liquidado else "Pendiente")
            c.setFillColorRGB(*MARINO)
            c.drawRightString(ancho - M, y, money(saldo))
            y -= 17

    # ── Totales ────────────────────────────────────────────────────────
    y -= 12
    total_por_pagar = total_pendiente + saldo_adeudos
    c.setStrokeColorRGB(*LINEA)
    c.line(ancho / 2, y, ancho - M, y)
    y -= 18
    c.setFont("Times-Roman", 10.5)
    for etiqueta, valor in (("Honorarios del ejercicio", total_cargos),
                            ("Pagado a la fecha", total_pagado),
                            ("Adeudos anteriores", saldo_adeudos)):
        c.setFillColorRGB(*GRIS)
        c.drawRightString(ancho - M - 110, y, etiqueta + ":")
        c.setFillColorRGB(*MARINO)
        c.drawRightString(ancho - M, y, money(valor))
        y -= 16

    c.setFillColorRGB(*AZUL)
    c.rect(ancho / 2, y - 26, ancho / 2 - M, 30, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Times-Bold", 12)
    c.drawRightString(ancho - M - 110, y - 16, "SALDO POR PAGAR:")
    c.drawRightString(ancho - M, y - 16, money(total_por_pagar))
    y -= 52

    # ── Pie: cómo pagar y nota ─────────────────────────────────────────
    if y < 110:
        c.showPage()
        y = alto - 90
    c.setFillColorRGB(*MARINO)
    c.setFont("Times-Bold", 10)
    c.drawString(M, y, "Formas de pago")
    y -= 14
    c.setFont("Times-Roman", 9.5)
    c.setFillColorRGB(*GRIS)
    for linea in ("Transferencia o depósito a la cuenta del despacho, "
                  "o efectivo en oficina con folio de recepción.",
                  "Al pagar, envíe su comprobante desde su portal: "
                  "queda registrado al momento en su expediente."):
        c.drawString(M, y, linea)
        y -= 12

    c.setFont("Times-Italic", 8.5)
    c.setFillColorRGB(*GRIS)
    c.drawString(M, 42, "Documento informativo generado por el sistema interno de "
                        "Pacheco & Aparicio. No es un comprobante fiscal.")
    c.drawRightString(ancho - M, 42, f"{cliente.nombre_comercial} · {anio}")
    c.showPage()
    c.save()
    return buf.getvalue()


@router.get("/api/portal/estado-cuenta-anual")
def estado_cuenta_del_cliente(request: Request, anio: int | None = None,
                              cliente: Cliente = Depends(cliente_autenticado),
                              db: Session = Depends(get_db)):
    """
    ENTREGA TRANSPARENTE: el cliente descarga su estado de cuenta cuando
    quiera, deba o no deba. Nada de retenerlo como palanca de cobro.
    """
    anio = anio or date.today().year
    pdf = _construir_estado_cuenta(db, cliente, anio)
    auditoria.registrar(db, usuario_id=None, accion="estado_cuenta_cliente",
                        tabla_afectada="clientes", registro_id=cliente.id,
                        request=request, ejercicio=anio)
    db.commit()
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition":
                             f'inline; filename="estado_cuenta_{anio}.pdf"'})
