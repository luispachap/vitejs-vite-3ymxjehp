# -*- coding: utf-8 -*-
"""
MÓDULO 2 + disparo del MÓDULO 4.
Panel de Contadores: carga de línea de captura -> envío automático vía Regina.
Tablero del Director: métricas agregadas y semáforo de cartera vencida.
"""
import os
from datetime import datetime, date

from pydantic import BaseModel

from fastapi import (APIRouter, Depends, File, Form, HTTPException,
                     Request, UploadFile)
from fastapi.responses import Response
from sqlalchemy.orm import Session

import config
from database import get_db
from models.models import (CategoriaDocumento, Cliente, DocumentoClave,
                           EstatusContabilidad, EstatusPago, HonorarioCobranza,
                           ObligacionMensual, RolUsuario, Usuario)
from services.auth import requiere_rol, solo_equipo_contable, solo_director
import secrets
from services import almacenamiento, auditoria, correo, whatsapp
from services.reglas_negocio import puede_automatizar_cobranza, puede_enviar_linea_captura

router = APIRouter(prefix="/api/obligaciones", tags=["Obligaciones (Contadores/Director)"])


# ---------------------------------------------------------------------------
# PANEL DE CONTADORES
# ---------------------------------------------------------------------------

@router.post("/{cliente_id}/subir-linea-captura")
def subir_linea_captura(
    cliente_id: int,
    mes: int = Form(...),
    anio: int = Form(...),
    monto_impuesto: float = Form(...),
    fecha_vencimiento: date = Form(...),
    archivo_pdf: UploadFile = File(...),
    # Desglose por concepto (opcional): alimenta la gráfica del portal
    iva: float | None = Form(None),
    isr: float | None = Form(None),
    retenciones: float | None = Form(None),
    isn: float | None = Form(None),            # impuesto sobre nómina
    cuotas_imss: float | None = Form(None),    # cuotas patronales
    infonavit: float | None = Form(None),
    # --- LOS DOS ARCHIVOS QUE GENERA UNA DECLARACIÓN PRESENTADA ---
    # archivo_pdf (arriba)  = ACUSE / línea de captura: el FORMATO DE PAGO,
    #                         que es el que se le envía al cliente.
    # comprobante_pdf       = COMPROBANTE de la declaración: la declaración en
    #                         sí, con todos sus datos. Se guarda en el
    #                         expediente (indispensable si hay saldo a favor).
    comprobante_pdf: UploadFile = File(None),
    numero_operacion: str | None = Form(None),
    # Si la declaración arrojó SALDO A FAVOR, entra solo al inventario.
    saldo_a_favor: float | None = Form(None),
    impuesto_saldo_favor: str | None = Form(None),   # isr | iva | ieps
    request: Request = None,
    usuario: Usuario = Depends(solo_equipo_contable),
    db: Session = Depends(get_db),
):
    """
    El contador sube el PDF del SAT y captura el monto. El sistema:
    1. Marca la contabilidad como TERMINADA.
    2. Dispara INMEDIATAMENTE el WhatsApp de Regina (Entrega Transparente:
       el impuesto NUNCA se retiene por adeudos de honorarios).
    3. Registra timestamp_enviado para la métrica de eficiencia.
    """
    cliente = db.query(Cliente).get(cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    if archivo_pdf.content_type != "application/pdf":
        raise HTTPException(400, "El archivo debe ser un PDF del SAT")

    # CANDADO DE PROCESO: si el periodo tiene cálculo en el sistema, debe
    # estar AUTORIZADO por el Director o la Supervisora antes de declararse.
    # (Sin cálculo registrado se permite, para la transición gradual.)
    from models.models import CalculoImpuesto, EstatusCalculo
    calc = (db.query(CalculoImpuesto)
            .filter_by(cliente_id=cliente_id, mes=mes, anio=anio).first())
    if calc and calc.estatus not in (EstatusCalculo.AUTORIZADO,
                                     EstatusCalculo.DECLARADO):
        raise HTTPException(409, f"La determinación de este periodo está "
                                 f"'{calc.estatus.value}': debe autorizarla el "
                                 f"Director o la Supervisora antes de declarar.")

    # SEGURIDAD: el PDF va al almacenamiento cifrado (S3 privado en prod,
    # Fernet local en dev). El nombre del objeto NO contiene el RFC.
    nombre = f"cliente{cliente.id}_{anio}-{mes:02d}_linea_captura.pdf"
    contenido = archivo_pdf.file.read()
    ruta = almacenamiento.guardar_documento(contenido, "lineas_captura", nombre)

    # Crear/actualizar obligación del periodo
    obligacion = (db.query(ObligacionMensual)
                  .filter_by(cliente_id=cliente_id, mes=mes, anio=anio).first())
    if not obligacion:
        obligacion = ObligacionMensual(cliente_id=cliente_id, mes=mes, anio=anio)
        db.add(obligacion)

    obligacion.estatus_contabilidad = EstatusContabilidad.TERMINADO
    obligacion.monto_impuesto_sat = monto_impuesto
    obligacion.ruta_archivo_linea_captura = ruta
    # Ya llegaron los papeles: se apaga el aviso de la verificación manual
    obligacion.documentos_pendientes = False
    obligacion.fecha_vencimiento_sat = fecha_vencimiento

    desglose = {k: v for k, v in [("iva", iva), ("isr", isr),
                ("retenciones", retenciones), ("isn", isn),
                ("cuotas_imss", cuotas_imss), ("infonavit", infonavit)]
                if v is not None and v > 0}
    if desglose:
        obligacion.desglose_impuestos = desglose

    # Honorario del periodo (si Pao/el sistema ya lo generó)
    honorario = (db.query(HonorarioCobranza)
                 .filter_by(cliente_id=cliente_id, mes=mes, anio=anio).first())

    # --- REGLA DE ORO ---
    # La línea de captura se envía SIEMPRE; los honorarios solo se mencionan
    # si la automatización de cobranza está permitida para este cliente.
    if puede_enviar_linea_captura(cliente):
        from services import pagos_periodo
        # Esquema "honorarios con el último pago": si el cliente tiene IMSS
        # o nómina habilitados y aún no se presentan, el estado de cuenta se
        # enviará cuando se complete la última obligación del periodo.
        incluir_honorarios = (honorario is not None
                              and honorario.estatus_pago == EstatusPago.PENDIENTE
                              and puede_automatizar_cobranza(cliente)
                              and pagos_periodo.periodo_completo(db, cliente, mes, anio))
        # Link corto de confirmación (un solo propósito, sin login)
        if honorario is not None and not honorario.token_confirmacion:
            honorario.token_confirmacion = secrets.token_hex(16)

        whatsapp.enviar_entrega_impuesto(cliente, honorario, ruta, incluir_honorarios)
        if cliente.email:
            cuerpo = (f"Estimado {cliente.nombre_comercial}:\n\n"
                      f"Adjuntamos su línea de captura del SAT del periodo "
                      f"{anio}-{mes:02d}, lista para pagarse antes del vencimiento.")
            if incluir_honorarios and honorario:
                cuerpo += (f"\n\nPor separado, su estado de cuenta de honorarios "
                           f"del mes: ${'{:,.2f}'.format(honorario.monto_honorario)}. "
                           f"Puede confirmar su movimiento aquí: "
                           f"{config.BASE_URL}/c/{honorario.token_confirmacion}")
            cuerpo += "\n\nSaludos cordiales,\nRegina · Asistente Digital de P&A"
            correo.enviar_correo(cliente.email,
                                 "Su declaración del mes está lista - P&A",
                                 cuerpo, adjunto=contenido, nombre_adjunto=nombre)
        obligacion.timestamp_enviado = datetime.utcnow()

    if calc:
        calc.estatus = EstatusCalculo.DECLARADO  # ciclo completo

    db.flush()

    # --- COMPROBANTE de la declaración (la declaración en sí) ---
    comprobante_doc = None
    if comprobante_pdf is not None and comprobante_pdf.filename:
        if comprobante_pdf.content_type != "application/pdf":
            raise HTTPException(400, "El comprobante debe ser PDF")
        ruta_comp = almacenamiento.guardar_documento(
            comprobante_pdf.file.read(),
            f"documentos_clave/cliente{cliente_id}",
            f"comprobante_declaracion_{anio}_{mes:02d}.pdf")
        comprobante_doc = DocumentoClave(
            cliente_id=cliente_id,
            categoria=CategoriaDocumento.COMPROBANTE_DECLARACION,
            ruta_archivo=ruta_comp, anio=anio, mes=mes)
        db.add(comprobante_doc)
        db.flush()
        obligacion.comprobante_documento_id = comprobante_doc.id
    if numero_operacion:
        obligacion.numero_operacion = numero_operacion.strip()[:40]

    # --- SALDO A FAVOR: entra al inventario para poder aplicarlo después ---
    saldo_registrado = None
    if saldo_a_favor and saldo_a_favor > 0:
        from models.models import SaldoFavor
        impuesto = (impuesto_saldo_favor or "isr").lower()
        if impuesto not in ("isr", "iva", "ieps", "otro"):
            raise HTTPException(400, "Impuesto del saldo a favor no válido")
        saldo_registrado = SaldoFavor(
            cliente_id=cliente_id, impuesto=impuesto, mes=mes, anio=anio,
            es_anual=False, monto_original=round(saldo_a_favor, 2),
            monto_aplicado=0, numero_operacion=(numero_operacion or None),
            fecha_presentacion=date.today(),
            comprobante_documento_id=(comprobante_doc.id if comprobante_doc else None),
            estatus="disponible", registrado_por_id=usuario.id,
            notas="Registrado automáticamente al presentar la declaración")
        db.add(saldo_registrado)
        db.flush()

    auditoria.registrar(db, usuario_id=usuario.id,
                        accion="carga_linea_captura",
                        tabla_afectada="obligaciones_mensuales",
                        registro_id=obligacion.id, request=request,
                        cliente=cliente.nombre_comercial,
                        periodo=f"{anio}-{mes:02d}",
                        monto_impuesto=monto_impuesto)
    db.commit()
    return {
        "ok": True,
        "minutos_hasta_envio": obligacion.minutos_hasta_envio,
        "automatizacion_cobranza": puede_automatizar_cobranza(cliente),
        "comprobante_guardado": bool(comprobante_doc),
        "saldo_favor_registrado": (
            {"id": saldo_registrado.id,
             "monto": saldo_registrado.monto_original,
             "impuesto": saldo_registrado.impuesto}
            if saldo_registrado else None),
    }


@router.post("/{cliente_id}/subir-documento")
def subir_documento_boveda(
    cliente_id: int,
    categoria: str = Form(...),
    anio: int = Form(...),
    mes: int | None = Form(None),
    archivo_pdf: UploadFile = File(...),
    request: Request = None,
    usuario: Usuario = Depends(solo_equipo_contable),
    db: Session = Depends(get_db),
):
    """
    Sube a la bóveda del cliente: balanza de comprobación, cédula de ISN,
    propuesta SIPARE (cuotas patronales), acuses, etc. Cifrado + auditoría.
    """
    from models.models import CategoriaDocumento, DocumentoClave
    cliente = db.query(Cliente).get(cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    try:
        cat = CategoriaDocumento(categoria)
    except ValueError:
        raise HTTPException(400, "Categoría no válida")
    if archivo_pdf.content_type != "application/pdf":
        raise HTTPException(400, "El archivo debe ser PDF")

    sufijo = f"_{mes:02d}" if mes else ""
    nombre = f"cliente{cliente.id}_{anio}{sufijo}_{cat.value}.pdf"
    ruta = almacenamiento.guardar_documento(
        archivo_pdf.file.read(), f"documentos_clave/cliente{cliente.id}", nombre)

    doc = DocumentoClave(cliente_id=cliente.id, categoria=cat,
                         ruta_archivo=ruta, anio=anio, mes=mes)
    db.add(doc)
    db.flush()
    auditoria.registrar(db, usuario_id=usuario.id, accion="carga_documento_boveda",
                        tabla_afectada="documentos_clave", registro_id=doc.id,
                        request=request, categoria=cat.value,
                        cliente=cliente.nombre_comercial,
                        periodo=f"{anio}" + (f"-{mes:02d}" if mes else ""))
    db.commit()
    return {"ok": True, "documento_id": doc.id}


@router.get("/boveda/{documento_id}/descargar")
def descargar_documento_interno(
    documento_id: int, request: Request,
    usuario: Usuario = Depends(solo_equipo_contable),
    db: Session = Depends(get_db),
):
    """Descarga interna de la bóveda (ej. balanza para cotejar el cálculo)."""
    from models.models import DocumentoClave
    doc = db.query(DocumentoClave).get(documento_id)
    if not doc:
        raise HTTPException(404, "Documento no encontrado")

    auditoria.registrar(db, usuario_id=usuario.id, accion="descarga_documento",
                        tabla_afectada="documentos_clave", registro_id=doc.id,
                        request=request, categoria=doc.categoria.value,
                        contexto="revision_interna")
    db.commit()

    return almacenamiento.respuesta_archivo(doc.ruta_archivo)


@router.post("/{obligacion_id}/comprobante-pago")
def subir_comprobante_pago(obligacion_id: int, request: Request,
                           referencia: str = Form(None),
                           archivo_pdf: UploadFile = File(...),
                           usuario: Usuario = Depends(solo_equipo_contable),
                           db: Session = Depends(get_db)):
    """
    El equipo registra que la línea de captura YA SE PAGÓ, con su comprobante.
    Antes el sistema sabía que existía la línea, pero no si el cliente pagó.
    """
    from models.models import CategoriaDocumento, DocumentoClave, ObligacionMensual
    o = db.query(ObligacionMensual).get(obligacion_id)
    if not o:
        raise HTTPException(404, "Obligación no encontrada")
    doc = _guardar_comprobante(db, o, archivo_pdf)
    o.comprobante_pago_documento_id = doc.id
    o.pagado_en = datetime.utcnow()
    o.pagado_registrado_por = "equipo"
    o.referencia_pago = (referencia or "").strip()[:60] or None
    auditoria.registrar(db, usuario_id=usuario.id, accion="comprobante_pago_registrado",
                        tabla_afectada="obligaciones_mensuales", registro_id=o.id,
                        request=request, documento_id=doc.id, origen="equipo")
    db.commit()
    return {"ok": True, "documento_id": doc.id,
            "mensaje": "Pago registrado con su comprobante."}


def _guardar_comprobante(db, obligacion, archivo):
    from models.models import CategoriaDocumento, DocumentoClave
    if archivo.content_type not in ("application/pdf", "image/jpeg", "image/png"):
        raise HTTPException(400, "El comprobante debe ser PDF o imagen (JPG/PNG)")
    import os as _os
    ext = (_os.path.splitext(archivo.filename or "")[1] or ".pdf").lower()[:6]
    nombre = (f"cliente{obligacion.cliente_id}_{obligacion.anio}_"
              f"{obligacion.mes:02d}_comprobante_pago{ext}")
    ruta = almacenamiento.guardar_documento(
        archivo.file.read(), f"documentos_clave/cliente{obligacion.cliente_id}", nombre)
    doc = DocumentoClave(cliente_id=obligacion.cliente_id,
                         categoria=CategoriaDocumento.COMPROBANTE_PAGO,
                         ruta_archivo=ruta, anio=obligacion.anio, mes=obligacion.mes)
    db.add(doc)
    db.flush()
    return doc


class NuevaComplementaria(BaseModel):
    motivo: str


@router.post("/{obligacion_id}/complementaria")
def crear_complementaria(obligacion_id: int, payload: NuevaComplementaria,
                         request: Request,
                         usuario: Usuario = Depends(solo_equipo_contable),
                         db: Session = Depends(get_db)):
    """
    Declaración COMPLEMENTARIA: corrige a una ya presentada. Se crea una
    obligación nueva del mismo periodo, ligada a la original, para que el
    expediente conserve las dos y se vea cuál corrige a cuál.
    """
    from models.models import EstatusContabilidad, ObligacionMensual
    o = db.query(ObligacionMensual).get(obligacion_id)
    if not o:
        raise HTTPException(404, "Obligación no encontrada")
    if not (payload.motivo or "").strip():
        raise HTTPException(400, "Explique por qué se presenta la complementaria")
    if not o.ruta_archivo_linea_captura:
        raise HTTPException(409, "Este periodo aún no tiene una declaración "
                                 "presentada: no hay qué complementar")

    # Se ARCHIVA la versión vigente (montos, acuse, comprobante, pago) y la
    # obligación queda lista para recibir la complementaria. Los documentos
    # siguen en la bóveda: el expediente conserva las dos declaraciones.
    historial = list(o.historial_complementarias or [])
    historial.append({
        "numero": o.numero_complementaria,
        "monto_impuesto_sat": o.monto_impuesto_sat,
        "numero_operacion": o.numero_operacion,
        "acuse": o.ruta_archivo_linea_captura,
        "comprobante_documento_id": o.comprobante_documento_id,
        "comprobante_pago_documento_id": o.comprobante_pago_documento_id,
        "pagado_en": o.pagado_en.isoformat() if o.pagado_en else None,
        "desglose": o.desglose_impuestos,
        "archivada_en": datetime.utcnow().isoformat(),
        "archivada_por": usuario.nombre,
    })
    o.historial_complementarias = historial
    o.numero_complementaria = (o.numero_complementaria or 0) + 1
    o.es_complementaria = True
    o.motivo_complementaria = payload.motivo.strip()[:300]
    o.estatus_contabilidad = EstatusContabilidad.EN_PROCESO
    # La complementaria se presenta desde cero: acuse, comprobante y pago
    o.ruta_archivo_linea_captura = None
    o.comprobante_documento_id = None
    o.comprobante_pago_documento_id = None
    o.pagado_en = None
    o.pagado_registrado_por = None
    o.referencia_pago = None
    auditoria.registrar(db, usuario_id=usuario.id, accion="complementaria_iniciada",
                        tabla_afectada="obligaciones_mensuales", registro_id=o.id,
                        request=request, numero=o.numero_complementaria,
                        motivo=payload.motivo[:120])
    db.commit()
    return {"ok": True, "obligacion_id": o.id,
            "numero_complementaria": o.numero_complementaria,
            "mensaje": (f"Complementaria #{o.numero_complementaria} iniciada para "
                        f"{o.mes:02d}/{o.anio}. La declaración anterior quedó "
                        f"archivada en el expediente. Suba el acuse nuevo cuando "
                        f"la presente.")}


class VerificacionManual(BaseModel):
    motivo: str
    documentos_pendientes: bool = True
    marcar_entregado: bool = True
    marcar_pagado: bool = False


@router.post("/{obligacion_id}/verificacion-manual")
def verificar_manualmente(obligacion_id: int, payload: VerificacionManual,
                          request: Request,
                          usuario: Usuario = Depends(requiere_rol(
                              RolUsuario.SUPERVISOR, RolUsuario.DIRECTOR,
                              RolUsuario.ADMINISTRADOR)),
                          db: Session = Depends(get_db)):
    """
    DAR FE DE QUE SÍ SE HIZO, aunque no esté en el sistema.
    Si la aplicación falló, o no hubo internet, o el contador mandó la línea
    de captura por WhatsApp: el trabajo se hizo. Un mando lo verifica con su
    nombre y su motivo para que el cliente no se preocupe de balde ni el
    contador aparezca incumplido. Los documentos se suben después y la marca
    de 'documentos pendientes' se apaga sola al subirlos.
    """
    from models.models import ObligacionMensual
    o = db.query(ObligacionMensual).get(obligacion_id)
    if not o:
        raise HTTPException(404, "Obligación no encontrada")
    if not (payload.motivo or "").strip():
        raise HTTPException(400, "Explique por qué se verifica a mano "
                                 "(queda en la bitácora con su nombre)")
    o.verificado_manualmente = True
    o.verificado_por_id = usuario.id
    o.verificado_en = datetime.utcnow()
    o.motivo_verificacion = payload.motivo.strip()[:300]
    o.documentos_pendientes = payload.documentos_pendientes
    if payload.marcar_entregado and not o.timestamp_enviado:
        o.timestamp_enviado = datetime.utcnow()
    if payload.marcar_pagado and not o.pagado_en:
        o.pagado_en = datetime.utcnow()
        o.pagado_registrado_por = "equipo"
    auditoria.registrar(db, usuario_id=usuario.id, accion="verificacion_manual",
                        tabla_afectada="obligaciones_mensuales", registro_id=o.id,
                        request=request, motivo=o.motivo_verificacion,
                        entregado=payload.marcar_entregado,
                        pagado=payload.marcar_pagado)
    db.commit()
    return {"ok": True,
            "mensaje": (f"Verificado por {usuario.nombre}. "
                        + ("Quedan documentos por subir: al cargarlos se "
                           "quita el aviso." if payload.documentos_pendientes
                           else "Sin documentos pendientes."))}


@router.get("/panel-contador")
def panel_contador(
    mes: int, anio: int,
    usuario: Usuario = Depends(solo_equipo_contable),
    db: Session = Depends(get_db),
):
    """Lista de trabajo del contador: cada cliente activo y su estatus del periodo."""
    clientes = db.query(Cliente).filter(Cliente.estatus == "activo").all()
    filas = []
    for cl in clientes:
        ob = next((o for o in cl.obligaciones if o.mes == mes and o.anio == anio), None)
        filas.append({
            "cliente_id": cl.id,
            "cliente": cl.nombre_comercial,
            "tipo_cliente": cl.tipo_cliente.value,
            "estatus": ob.estatus_contabilidad.value if ob else "pendiente",
            "monto_impuesto": ob.monto_impuesto_sat if ob else None,
            "enviado": bool(ob and ob.timestamp_enviado),
            "obligacion_id": ob.id if ob else None,
            # ¿YA SE PAGÓ? y ¿es complementaria?
            "pagado": bool(ob and ob.pagado_en),
            "pagado_por": ob.pagado_registrado_por if ob else None,
            "referencia_pago": ob.referencia_pago if ob else None,
            "presentada": bool(ob and ob.ruta_archivo_linea_captura),
            "es_complementaria": bool(ob and ob.es_complementaria),
            "numero_complementaria": (ob.numero_complementaria if ob else 0),
            # Verificación manual: alguien dio fe de que sí se hizo
            "verificado_manualmente": bool(ob and ob.verificado_manualmente),
            "verificado_por": (ob.verificado_por.nombre
                               if ob and ob.verificado_por else None),
            "motivo_verificacion": ob.motivo_verificacion if ob else None,
            "documentos_pendientes": bool(ob and ob.documentos_pendientes),
        })
    filas.sort(key=lambda f: (f["estatus"] == "terminado", f["cliente"]))
    return filas


# ---------------------------------------------------------------------------
# TABLERO DE PROGRESO DEL DESPACHO (VISTA DIRECTOR)
# ---------------------------------------------------------------------------

@router.get("/tablero-director")
def tablero_director(
    mes: int, anio: int,
    usuario: Usuario = Depends(solo_director),
    db: Session = Depends(get_db),
):
    total_clientes = db.query(Cliente).filter(Cliente.estatus == "activo").count()
    obligaciones = (db.query(ObligacionMensual)
                    .filter_by(mes=mes, anio=anio).all())

    terminadas = [o for o in obligaciones
                  if o.estatus_contabilidad == EstatusContabilidad.TERMINADO]
    enviadas = [o for o in obligaciones if o.timestamp_enviado]
    tiempos = [o.minutos_hasta_envio for o in enviadas if o.minutos_hasta_envio is not None]

    return {
        "progreso_contabilidades": {
            "terminadas": len(terminadas),
            "total": total_clientes,
            "porcentaje": round(len(terminadas) / total_clientes * 100, 1) if total_clientes else 0,
        },
        "impuestos_enviados": {"enviados": len(enviadas), "total": total_clientes},
        "eficiencia_promedio_minutos": round(sum(tiempos) / len(tiempos), 1) if tiempos else None,
        # AUTOFIRMAS del periodo: cálculos que su autor mismo autorizó (la
        # Supervisora puede hacerlo). No es una alarma: es visibilidad, para
        # que el Director sepa cuáles no pasaron por un segundo par de ojos.
        "autoautorizaciones": _autoautorizaciones(db, mes, anio),
    }


def _autoautorizaciones(db, mes: int, anio: int) -> list:
    from models.models import CalculoImpuesto, EstatusCalculo
    calcs = (db.query(CalculoImpuesto)
             .filter(CalculoImpuesto.mes == mes, CalculoImpuesto.anio == anio,
                     CalculoImpuesto.estatus.in_([EstatusCalculo.AUTORIZADO,
                                                  EstatusCalculo.DECLARADO]))
             .all())
    return [{"cliente": c.cliente.nombre_comercial if c.cliente else None,
             "quien": c.elaborado_por.nombre if c.elaborado_por else None,
             "total": c.total_a_pagar}
            for c in calcs if (c.resultado or {}).get("auto_autorizado")]


@router.get("/semaforo-cartera")
def semaforo_cartera_vencida(
    usuario: Usuario = Depends(solo_director),
    db: Session = Depends(get_db),
):
    """
    Semáforo de Cartera Vencida: clientes con 60/90+ días de adeudo o con
    patrón de 'visto sin respuesta', con resumen analítico por cliente.
    """
    pendientes = (db.query(HonorarioCobranza)
                  .filter(HonorarioCobranza.estatus_pago != EstatusPago.PAGADO).all())

    resultado = []
    for h in pendientes:
        historial = h.historial_notificaciones or []
        eventos_leido = [e for e in historial if e.get("evento") == "leido"]
        eventos_respuesta = [e for e in historial if e.get("evento") == "respuesta_cliente"]
        ultima_notif = historial[-1]["ts"] if historial else None
        visto_recurrente = len(eventos_leido) >= 2 and len(eventos_respuesta) == 0

        if h.dias_vencido >= config.DIAS_ALERTA_ROJA_PARPADEANTE:
            nivel = "rojo_parpadeante"
        elif h.dias_vencido >= config.DIAS_ALERTA_ROJA or visto_recurrente:
            nivel = "rojo"
        elif h.dias_vencido >= config.DIAS_ALERTA_AMARILLA:
            nivel = "amarillo"
        else:
            continue  # el semáforo solo muestra cartera en riesgo

        resultado.append({
            "cliente": h.cliente.nombre_comercial,
            "tipo_cliente": h.cliente.tipo_cliente.value,
            "nivel": nivel,
            "monto_adeudado": h.monto_honorario,
            "dias_vencido": h.dias_vencido,
            "ultima_notificacion": ultima_notif,
            "estatus_lectura": "visto_sin_respuesta" if visto_recurrente
                               else ("leido" if eventos_leido else "sin_confirmar"),
        })

    resultado.sort(key=lambda x: x["dias_vencido"], reverse=True)
    return {"cartera_en_riesgo": resultado,
            "monto_total_riesgo": sum(r["monto_adeudado"] for r in resultado)}


@router.get("/{obligacion_id}/descargar-linea-captura")
def descargar_linea_captura_interna(
    obligacion_id: int, request: Request,
    usuario: Usuario = Depends(solo_equipo_contable),
    db: Session = Depends(get_db),
):
    """
    Descarga interna (contadores/director): descifrado EN MEMORIA + auditoría.
    Queda grabado qué miembro del equipo descargó qué documento y cuándo.
    """
    obligacion = db.query(ObligacionMensual).get(obligacion_id)
    if not obligacion or not obligacion.ruta_archivo_linea_captura:
        raise HTTPException(404, "Línea de captura no encontrada")

    ruta = obligacion.ruta_archivo_linea_captura
    auditoria.registrar(db, usuario_id=usuario.id,
                        accion="descarga_linea_captura",
                        tabla_afectada="obligaciones_mensuales",
                        registro_id=obligacion.id, request=request,
                        cliente_id=obligacion.cliente_id)
    db.commit()

    return almacenamiento.respuesta_archivo(ruta)
