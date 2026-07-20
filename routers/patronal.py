# -*- coding: utf-8 -*-
"""
OBLIGACIONES PATRONALES — IMSS (IDSE→SUA→SIPARE), ISN y NÓMINAS
===============================================================
- IMSS: los tres pasos del ciclo son tareas visibles del contador; cada
  documento (emisión IDSE, cálculo SUA, propuesta SIPARE, formato final)
  se guarda cifrado en la bóveda del cliente y ahí se queda el tiempo que
  haga falta. El desglose por concepto se captura a mano y el total se
  suma solo; al presentar y subir el FORMATO FINAL, ese es el que llega al
  cliente por la asistente, con el detalle disponible para Sofía.
- ISN: presentación mensual con importe y formato de pago; aviso individual.
- Nóminas: tareas recurrentes por periodicidad del cliente (semanal,
  quincenal o mensual) generadas por Celery beat; el contador las termina
  adjuntando el entregable.
- Tablero de supervisión: la Supervisora y el Director ven el estatus de
  cada obligación por cliente y quién trae qué pendiente.
"""
from datetime import date, datetime

from fastapi import (APIRouter, Depends, File, Form, HTTPException, Request,
                     UploadFile)
from sqlalchemy.orm import Session

from database import get_db
from models.models import (CategoriaDocumento, Cliente, DocumentoClave,
                           PagoIMSS, PagoISN, TareaNomina, Usuario)
from services import almacenamiento, auditoria, pagos_periodo, whatsapp
from services.auth import solo_autorizadores, solo_equipo_contable

router = APIRouter(prefix="/api/patronal", tags=["Obligaciones patronales"])

PASOS_IMSS = ("emision_idse_hecha", "calculo_sua_hecho", "sipare_presentado")
CATEGORIAS_IMSS = {
    "emision_idse": CategoriaDocumento.EMISION_IDSE,
    "calculo_sua": CategoriaDocumento.CALCULO_SUA,
    "propuesta_sipare": CategoriaDocumento.PROPUESTA_SIPARE,
    "formato_pago_imss": CategoriaDocumento.FORMATO_PAGO_IMSS,
}


def _guardar_doc(db, cliente, archivo, categoria: CategoriaDocumento,
                 anio: int, mes: int, sufijo: str = "") -> DocumentoClave:
    # El ciclo patronal NO es puro PDF: el SUA genera .sua y varios archivos,
    # el IDSE trae los suyos. Se conserva la extensión real del archivo.
    import os as _os
    ext = (_os.path.splitext(archivo.filename or "")[1] or ".pdf").lower()[:8]
    nombre = f"cliente{cliente.id}_{anio}_{mes:02d}_{categoria.value}{sufijo}{ext}"
    ruta = almacenamiento.guardar_documento(
        archivo.file.read(), f"documentos_clave/cliente{cliente.id}", nombre)
    doc = DocumentoClave(cliente_id=cliente.id, categoria=categoria,
                         ruta_archivo=ruta, anio=anio, mes=mes)
    db.add(doc)
    db.flush()
    return doc


def _obtener_pago(db, cliente_id: int, mes: int, anio: int,
                  usuario: Usuario) -> PagoIMSS:
    pago = (db.query(PagoIMSS)
            .filter_by(cliente_id=cliente_id, mes=mes, anio=anio).first())
    if not pago:
        pago = PagoIMSS(cliente_id=cliente_id, mes=mes, anio=anio,
                        responsable_id=usuario.id)
        db.add(pago)
        db.flush()
    return pago


def _serializar_pago(p: PagoIMSS) -> dict:
    return {"id": p.id, "cliente_id": p.cliente_id,
            "cliente": p.cliente.nombre_comercial, "mes": p.mes, "anio": p.anio,
            "emision_idse_hecha": p.emision_idse_hecha,
            "calculo_sua_hecho": p.calculo_sua_hecho,
            "sipare_presentado": p.sipare_presentado,
            "desglose_cuotas": p.desglose_cuotas or {},
            "total_a_pagar": p.total_a_pagar,
            "formato_subido": bool(p.formato_pago_documento_id),
            "notificado_cliente": p.notificado_cliente,
            "responsable": p.responsable.nombre if p.responsable else None}


# ---------------------------------------------------------------------------
# IMSS: pasos, documentos y desglose
# ---------------------------------------------------------------------------

@router.get("/imss")
def panel_imss(mes: int, anio: int,
               u: Usuario = Depends(solo_equipo_contable),
               db: Session = Depends(get_db)):
    """Clientes con IMSS habilitado y el avance de su ciclo del periodo."""
    salida = []
    for cliente in (db.query(Cliente)
                    .filter(Cliente.tiene_imss, Cliente.estatus == "activo")
                    .order_by(Cliente.nombre_comercial).all()):
        pago = (db.query(PagoIMSS)
                .filter_by(cliente_id=cliente.id, mes=mes, anio=anio).first())
        salida.append(_serializar_pago(pago) if pago else
                      {"cliente_id": cliente.id,
                       "cliente": cliente.nombre_comercial, "mes": mes,
                       "anio": anio, "emision_idse_hecha": False,
                       "calculo_sua_hecho": False, "sipare_presentado": False,
                       "desglose_cuotas": {}, "total_a_pagar": None,
                       "formato_subido": False, "notificado_cliente": False,
                       "responsable": None})
    return salida


@router.post("/imss/{cliente_id}/paso")
def marcar_paso_imss(cliente_id: int, request: Request,
                     mes: int = Form(...), anio: int = Form(...),
                     paso: str = Form(...),
                     categoria_documento: str = Form(None),
                     archivo_pdf: UploadFile = File(None),
                     archivos: list[UploadFile] = File(None),
                     u: Usuario = Depends(solo_equipo_contable),
                     db: Session = Depends(get_db)):
    """
    Marca un paso del ciclo (emision_idse_hecha | calculo_sua_hecho |
    sipare_presentado) y opcionalmente adjunta su documento de respaldo
    (emisión del IDSE, cálculo del SUA o propuesta SIPARE), que queda
    guardado en la bóveda para revisiones o correcciones futuras del SUA.
    """
    if paso not in PASOS_IMSS:
        raise HTTPException(400, "Paso no válido")
    cliente = db.query(Cliente).get(cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    pago = _obtener_pago(db, cliente_id, mes, anio, u)
    setattr(pago, paso, True)
    pago.responsable_id = u.id
    if paso == "sipare_presentado":
        pago.timestamp_presentado = datetime.utcnow()

    # Un paso puede traer VARIOS archivos (el SUA genera más de uno) y en
    # el formato que el IMSS entregue (.sua, .pdf, .txt, .zip…).
    entrantes = [a for a in ([archivo_pdf] + list(archivos or [])) 
                 if a is not None and getattr(a, "filename", "")]
    doc_id, docs_ids = None, []
    if entrantes:
        cat = CATEGORIAS_IMSS.get(categoria_documento or "")
        if not cat:
            raise HTTPException(400, "Categoría de documento no válida")
        for i, arch in enumerate(entrantes):
            sufijo = f"_{i + 1}" if len(entrantes) > 1 else ""
            docs_ids.append(_guardar_doc(db, cliente, arch, cat, anio, mes,
                                         sufijo).id)
        doc_id = docs_ids[0]

    auditoria.registrar(db, usuario_id=u.id, accion="paso_imss",
                        tabla_afectada="pagos_imss", registro_id=pago.id,
                        request=request, paso=paso, documento_id=doc_id,
                        documentos=docs_ids,
                        cliente=cliente.nombre_comercial)
    db.commit()
    return _serializar_pago(pago)


@router.post("/imss/{cliente_id}/desglose")
def capturar_desglose_imss(cliente_id: int, request: Request,
                           payload: dict,
                           mes: int, anio: int,
                           u: Usuario = Depends(solo_equipo_contable),
                           db: Session = Depends(get_db)):
    """
    Desglose por concepto (captura manual). El TOTAL se autorellena con la
    suma; Sofía usa este detalle si el cliente pregunta cuánto corresponde
    a cada concepto (cuotas IMSS, retiro, cesantía, INFONAVIT, etc.).
    """
    desglose = {str(k): float(v) for k, v in (payload or {}).items()
                if v is not None and float(v) >= 0}
    pago = _obtener_pago(db, cliente_id, mes, anio, u)
    pago.desglose_cuotas = desglose
    pago.total_a_pagar = round(sum(desglose.values()), 2)
    auditoria.registrar(db, usuario_id=u.id, accion="desglose_imss",
                        tabla_afectada="pagos_imss", registro_id=pago.id,
                        request=request, total=pago.total_a_pagar)
    db.commit()
    return _serializar_pago(pago)


@router.post("/imss/{cliente_id}/presentar")
def presentar_formato_imss(cliente_id: int, request: Request,
                           mes: int = Form(...), anio: int = Form(...),
                           archivo_pdf: UploadFile = File(...),
                           u: Usuario = Depends(solo_equipo_contable),
                           db: Session = Depends(get_db)):
    """
    Sube el FORMATO DE PAGO FINAL del IMSS (el que el cliente paga) y lo
    envía de inmediato por la asistente con el total y desglose disponible.
    Si con esto se completa el periodo, dispara el estado de cuenta de
    honorarios (esquema: honorarios con el último pago).
    """
    cliente = db.query(Cliente).get(cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    if archivo_pdf.content_type != "application/pdf":
        raise HTTPException(400, "El archivo debe ser PDF")

    pago = _obtener_pago(db, cliente_id, mes, anio, u)
    if not pago.sipare_presentado:
        raise HTTPException(409, "Primero marque el ciclo completo: la "
                                 "propuesta debe estar presentada en el SIPARE.")
    doc = _guardar_doc(db, cliente, archivo_pdf,
                       CategoriaDocumento.FORMATO_PAGO_IMSS, anio, mes)
    pago.formato_pago_documento_id = doc.id

    total = pago.total_a_pagar or 0
    whatsapp._enviar(
        cliente.telefono_whatsapp,
        f"Hola {cliente.nombre_comercial}, le saluda Regina de Pacheco & "
        f"Aparicio. Sus cuotas del IMSS del mes ya están presentadas"
        f"{f' por ${total:,.2f}' if total else ''}. Le adjunto su formato de "
        f"pago para que pueda cubrirlo con calma. Si desea el desglose por "
        f"concepto, con gusto se lo detallamos.",
        adjunto_ruta=doc.ruta_archivo)
    pago.notificado_cliente = True

    auditoria.registrar(db, usuario_id=u.id, accion="presentacion_imss",
                        tabla_afectada="pagos_imss", registro_id=pago.id,
                        request=request, total=total,
                        cliente=cliente.nombre_comercial)
    honorarios = pagos_periodo.notificar_honorarios_si_completo(
        db, cliente, mes, anio)
    db.commit()
    return {"ok": True, "notificado": True,
            "honorarios_enviados": honorarios}


# ---------------------------------------------------------------------------
# ISN: presentación mensual
# ---------------------------------------------------------------------------

@router.post("/isn/{cliente_id}/presentar")
def presentar_isn(cliente_id: int, request: Request,
                  mes: int = Form(...), anio: int = Form(...),
                  importe: float = Form(...),
                  archivo_pdf: UploadFile = File(...),
                  u: Usuario = Depends(solo_equipo_contable),
                  db: Session = Depends(get_db)):
    """Presenta el ISN del mes: guarda el formato, avisa al cliente con el
    importe exacto del impuesto sobre nómina y, si es la última obligación
    del periodo, dispara los honorarios."""
    cliente = db.query(Cliente).get(cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    if archivo_pdf.content_type != "application/pdf":
        raise HTTPException(400, "El archivo debe ser PDF")

    doc = _guardar_doc(db, cliente, archivo_pdf,
                       CategoriaDocumento.FORMATO_PAGO_ISN, anio, mes)
    pago = (db.query(PagoISN)
            .filter_by(cliente_id=cliente_id, mes=mes, anio=anio).first())
    if not pago:
        pago = PagoISN(cliente_id=cliente_id, mes=mes, anio=anio)
        db.add(pago)
    pago.importe = importe
    pago.documento_id = doc.id
    pago.presentado_por_id = u.id
    db.flush()

    whatsapp._enviar(
        cliente.telefono_whatsapp,
        f"Hola {cliente.nombre_comercial}, le saluda Regina. Su impuesto "
        f"sobre nómina del estado ya quedó presentado: corresponde "
        f"${importe:,.2f} de este concepto. Le adjunto el formato de pago. "
        f"¡Excelente día!",
        adjunto_ruta=doc.ruta_archivo)
    pago.notificado_cliente = True

    auditoria.registrar(db, usuario_id=u.id, accion="presentacion_isn",
                        tabla_afectada="pagos_isn", registro_id=pago.id,
                        request=request, importe=importe,
                        cliente=cliente.nombre_comercial)
    honorarios = pagos_periodo.notificar_honorarios_si_completo(
        db, cliente, mes, anio)
    db.commit()
    return {"ok": True, "honorarios_enviados": honorarios}


# ---------------------------------------------------------------------------
# NÓMINAS: tareas recurrentes
# ---------------------------------------------------------------------------

@router.get("/nominas")
def tareas_nomina(u: Usuario = Depends(solo_equipo_contable),
                  db: Session = Depends(get_db)):
    """Tareas de nómina pendientes (y las terminadas recientes del periodo)."""
    tareas = (db.query(TareaNomina)
              .order_by(TareaNomina.estatus.desc(),
                        TareaNomina.fecha_objetivo.asc())
              .limit(120).all())
    return [{"id": t.id, "cliente": t.cliente.nombre_comercial,
             "cliente_id": t.cliente_id, "fecha_objetivo": str(t.fecha_objetivo),
             "etiqueta": t.etiqueta, "estatus": t.estatus,
             "vencida": t.estatus == "pendiente" and t.fecha_objetivo < date.today()}
            for t in tareas]


@router.post("/nominas/{tarea_id}/terminar")
def terminar_tarea_nomina(tarea_id: int, request: Request,
                          archivo_pdf: UploadFile = File(...),
                          u: Usuario = Depends(solo_equipo_contable),
                          db: Session = Depends(get_db)):
    """La tarea SOLO se completa entregando su documento (nóminas del
    periodo), que queda guardado en la bóveda del cliente."""
    tarea = db.query(TareaNomina).get(tarea_id)
    if not tarea:
        raise HTTPException(404, "Tarea no encontrada")
    if tarea.estatus == "terminada":
        raise HTTPException(409, "Esta tarea ya está terminada")
    if archivo_pdf.content_type != "application/pdf":
        raise HTTPException(400, "El entregable debe ser PDF")

    doc = _guardar_doc(db, tarea.cliente, archivo_pdf,
                       CategoriaDocumento.RECIBO_NOMINA,
                       tarea.fecha_objetivo.year, tarea.fecha_objetivo.month)
    tarea.documento_id = doc.id
    tarea.estatus = "terminada"
    tarea.terminada_por_id = u.id
    tarea.timestamp_terminada = datetime.utcnow()
    auditoria.registrar(db, usuario_id=u.id, accion="nomina_terminada",
                        tabla_afectada="tareas_nomina", registro_id=tarea.id,
                        request=request, cliente=tarea.cliente.nombre_comercial)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# TABLERO DE SUPERVISIÓN (Supervisora y Director)
# ---------------------------------------------------------------------------

@router.get("/tablero")
def tablero_supervision(mes: int, anio: int,
                        u: Usuario = Depends(solo_autorizadores),
                        db: Session = Depends(get_db)):
    """
    Estatus de cada obligación por cliente para tomar medidas: SAT, IMSS
    (con su paso exacto), ISN y nóminas pendientes/vencidas del periodo.
    """
    salida = []
    for cliente in (db.query(Cliente)
                    .filter(Cliente.estatus == "activo")
                    .order_by(Cliente.nombre_comercial).all()):
        estado = pagos_periodo.estado_obligaciones(db, cliente, mes, anio)
        pago_imss = (db.query(PagoIMSS)
                     .filter_by(cliente_id=cliente.id, mes=mes, anio=anio)
                     .first()) if cliente.tiene_imss else None
        pendientes_nomina = (db.query(TareaNomina)
                             .filter_by(cliente_id=cliente.id,
                                        estatus="pendiente").count()
                             if cliente.tiene_nomina else 0)
        # QUÉ falta exactamente (para no obligar a adivinar viendo puntitos)
        faltantes = []
        if not estado.get("sat", True):
            faltantes.append("Declaración del SAT sin presentar")
        if estado.get("imss") is False:
            pasos_falta = []
            if not (pago_imss and pago_imss.emision_idse_hecha):
                pasos_falta.append("emisión IDSE")
            if not (pago_imss and pago_imss.calculo_sua_hecho):
                pasos_falta.append("cálculo SUA")
            if not (pago_imss and pago_imss.sipare_presentado):
                pasos_falta.append("pago en SIPARE")
            faltantes.append("IMSS: falta " + ", ".join(pasos_falta))
        if estado.get("isn") is False:
            faltantes.append("ISN del periodo sin presentar")
        if pendientes_nomina:
            faltantes.append(f"{pendientes_nomina} nómina(s) por entregar")

        salida.append({
            "cliente_id": cliente.id, "cliente": cliente.nombre_comercial,
            "contador_id": cliente.contador_asignado_id,
            "contador": (cliente.contador_asignado.nombre
                         if cliente.contador_asignado else "Sin contador asignado"),
            "tipo_cliente": cliente.tipo_cliente.value,
            "obligaciones": estado,
            "faltantes": faltantes,
            "completo": all(estado.values()) and not pendientes_nomina,
            "imss_pasos": ({"idse": pago_imss.emision_idse_hecha,
                            "sua": pago_imss.calculo_sua_hecho,
                            "sipare": pago_imss.sipare_presentado}
                           if pago_imss else
                           ({"idse": False, "sua": False, "sipare": False}
                            if cliente.tiene_imss else None)),
            "responsable_imss": (pago_imss.responsable.nombre
                                 if pago_imss and pago_imss.responsable else None),
            "nominas_pendientes": pendientes_nomina,
        })
    return salida
