# -*- coding: utf-8 -*-
"""
DETERMINACIÓN Y AUTORIZACIÓN DE IMPUESTOS
=========================================
El proceso central del despacho, digitalizado:

  contador captura datos de la balanza (CONTPAQ)
      → el sistema calcula y rellena constantes (services/fiscal.py)
      → enviar a autorización (aviso a Director Y Supervisora)
      → cualquiera de los dos AUTORIZA, o RECHAZA con correcciones
        puntuales por campo
      → autorizado: se declara ante el SAT y se sube la línea de captura
        (routers/obligaciones.py exige la autorización) → DECLARADO
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.models import (CalculoImpuesto, CategoriaDocumento, Cliente,
                           DocumentoClave, EstatusCalculo, EstatusCliente,
                           RolUsuario, SnapshotContpaq, Usuario)
from services import auditoria, correo, fiscal, fiscal_v2
from services.auth import solo_autorizadores, solo_equipo_contable

router = APIRouter(prefix="/api/calculos", tags=["Determinación de impuestos"])

CAMPOS_ENTRADA_VALIDOS = {
    "ingresos_acumulados", "deducciones_acumuladas",
    "ingresos_nominales_acumulados", "coeficiente_utilidad",
    "pagos_provisionales_anteriores", "retenciones_isr",
    "iva_trasladado", "iva_acreditable", "iva_retenido", "base_nomina",
}


def _serializar(c: CalculoImpuesto, incluir_balanza=None) -> dict:
    return {
        "id": c.id, "cliente_id": c.cliente_id,
        "cliente": c.cliente.nombre_comercial, "mes": c.mes, "anio": c.anio,
        "regimen": c.regimen, "datos_entrada": c.datos_entrada,
        "resultado": c.resultado, "total_a_pagar": c.total_a_pagar,
        "estatus": c.estatus.value, "correcciones": c.correcciones or [],
        "elaborado_por": c.elaborado_por.nombre,
        "autorizado_por": (c.autorizado_por.nombre if c.autorizado_por else None),
        "balanza_documento_id": incluir_balanza,
    }


def _balanza_del_periodo(db: Session, c: CalculoImpuesto):
    """Balanza de comprobación del mismo periodo en la bóveda (para comparar)."""
    # ⚠ SIN FALLBACK: antes, si no había balanza se devolvía CUALQUIER
    # documento del periodo (llegó a mostrarse el PDF del IDSE rotulado como
    # "balanza"). Si no hay balanza, no hay balanza: el frontend lo dice.
    doc = (db.query(DocumentoClave)
           .filter_by(cliente_id=c.cliente_id, anio=c.anio, mes=c.mes,
                      categoria=CategoriaDocumento.BALANZA_COMPROBACION)
           .order_by(DocumentoClave.id.desc()).first())
    return doc.id if doc else None


@router.get("/tarifa")
def ver_tarifa(u: Usuario = Depends(solo_equipo_contable)):
    """Transparencia: la tarifa y tasas que el sistema rellena en automático."""
    return {"anio_tarifa": fiscal.ANIO_TARIFA,
            "tarifa_isr_mensual": fiscal.TARIFA_ISR_MENSUAL,
            "tasa_isr_persona_moral_pct": fiscal.TASA_ISR_PERSONA_MORAL,
            "tasa_isn_zacatecas_pct": fiscal.TASA_ISN_ZACATECAS,
            "tasa_iva_pct": fiscal.TASA_IVA,
            "nota": "Verificar cada ejercicio contra el Anexo 8 RMF y la "
                    "Ley de Hacienda de Zacatecas."}


@router.get("/balanza-periodo")
def balanza_periodo(cliente_id: int, mes: int, anio: int,
                    u: Usuario = Depends(solo_equipo_contable),
                    db: Session = Depends(get_db)):
    """Balanza de comprobación del periodo (para verla al lado del cálculo)."""
    doc = (db.query(DocumentoClave)
           .filter_by(cliente_id=cliente_id, mes=mes, anio=anio,
                      categoria=CategoriaDocumento.BALANZA_COMPROBACION)
           .order_by(DocumentoClave.id.desc()).first())
    return {"documento_id": doc.id if doc else None,
            "hay_balanza": bool(doc)}


@router.get("/regimenes")
def regimenes_y_campos(u: Usuario = Depends(solo_equipo_contable)):
    """Catálogo de regímenes y sus campos de captura (para el formulario)."""
    return {"regimenes": fiscal_v2.REGIMENES, "campos": fiscal_v2.CAMPOS_CAPTURA,
            "tipo_persona": fiscal_v2.TIPO_PERSONA_DE_REGIMEN,
            "grupos": fiscal_v2.GRUPOS_REGIMEN,
            "anio_tarifa": fiscal_v2.ANIO_TARIFA}


class DatosCalculo(BaseModel):
    cliente_id: int
    mes: int
    anio: int
    regimen: str | None = None   # normalmente viene del cliente
    datos: dict                  # campos de CAMPOS_ENTRADA_VALIDOS


@router.post("")
def crear_o_actualizar(payload: DatosCalculo, request: Request,
                       u: Usuario = Depends(solo_equipo_contable),
                       db: Session = Depends(get_db)):
    """
    Captura/edición del cálculo. El sistema calcula al instante y devuelve el
    desglose completo tipo página del SAT. Si estaba RECHAZADO, al guardar
    vuelve a BORRADOR (listo para reenviarse con las correcciones aplicadas).
    """
    cliente = db.query(Cliente).get(payload.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    # El régimen es un dato DEL CLIENTE (se define en Administración); el
    # formulario ya no lo pregunta. Compatibilidad: si el cliente aún no lo
    # tiene configurado, se acepta el del payload (llaves v1 incluidas).
    try:
        regimen = fiscal_v2.normalizar_regimen(
            cliente.regimen_fiscal or payload.regimen or "")
    except ValueError:
        raise HTTPException(400, "Este cliente no tiene régimen fiscal "
                                 "configurado. Defínalo en Administración → "
                                 "editar cliente.")

    campos_validos = ({c for c, _ in fiscal_v2.CAMPOS[regimen]}
                      | {c for c, _ in fiscal_v2.CAMPOS_CAPTURA.get(regimen, [])})
    datos = {k: float(v) for k, v in (payload.datos or {}).items()
             if k in campos_validos and v is not None}

    # La BD acumula como las hojas: meses anteriores + saldo a favor de IVA
    contexto = fiscal_v2.contexto_desde_bd(db, cliente.id, payload.mes,
                                           payload.anio, regimen)
    resultado = fiscal_v2.calcular(regimen, payload.mes, datos, contexto)

    calc = (db.query(CalculoImpuesto)
            .filter_by(cliente_id=payload.cliente_id, mes=payload.mes,
                       anio=payload.anio).first())
    if calc and calc.estatus in (EstatusCalculo.AUTORIZADO, EstatusCalculo.DECLARADO):
        raise HTTPException(409, "Este periodo ya fue autorizado: no puede "
                                 "modificarse. Consulte al Director o a la Supervisora.")
    if not calc:
        calc = CalculoImpuesto(cliente_id=payload.cliente_id, mes=payload.mes,
                               anio=payload.anio, elaborado_por_id=u.id,
                               datos_entrada={}, resultado={})
        db.add(calc)

    calc.regimen = regimen
    calc.datos_entrada = datos
    calc.resultado = resultado
    calc.total_a_pagar = resultado["total_a_pagar"]
    calc.estatus = EstatusCalculo.BORRADOR
    db.flush()
    auditoria.registrar(db, usuario_id=u.id, accion="captura_calculo",
                        tabla_afectada="calculos_impuestos", registro_id=calc.id,
                        request=request, cliente=cliente.nombre_comercial,
                        periodo=f"{payload.anio}-{payload.mes:02d}",
                        total=resultado["total_a_pagar"])
    db.commit()
    return _serializar(calc, _balanza_del_periodo(db, calc))


@router.post("/{calculo_id}/enviar-autorizacion")
def enviar_autorizacion(calculo_id: int, request: Request,
                        u: Usuario = Depends(solo_equipo_contable),
                        db: Session = Depends(get_db)):
    """Lo manda a los DOS (Director y Supervisora); cualquiera autoriza."""
    calc = db.query(CalculoImpuesto).get(calculo_id)
    if not calc:
        raise HTTPException(404, "Cálculo no encontrado")
    if calc.estatus not in (EstatusCalculo.BORRADOR, EstatusCalculo.RECHAZADO):
        raise HTTPException(409, f"El cálculo está '{calc.estatus.value}'")

    calc.estatus = EstatusCalculo.EN_AUTORIZACION
    calc.timestamp_enviado = datetime.utcnow()

    autorizadores = (db.query(Usuario)
                     .filter(Usuario.rol.in_([RolUsuario.DIRECTOR,
                                              RolUsuario.SUPERVISOR]),
                             Usuario.activo).all())
    for a in autorizadores:
        correo.enviar_correo(
            a.email,
            f"Autorización pendiente: {calc.cliente.nombre_comercial} "
            f"{calc.anio}-{calc.mes:02d}",
            f"{u.nombre} envió a autorización la determinación de impuestos.\n\n"
            f"Cliente: {calc.cliente.nombre_comercial}\n"
            f"Periodo: {calc.mes:02d}/{calc.anio}\n"
            f"Total a pagar: ${calc.total_a_pagar:,.2f}\n\n"
            f"Revísela en su panel, sección Autorizaciones.")

    auditoria.registrar(db, usuario_id=u.id, accion="envio_autorizacion",
                        tabla_afectada="calculos_impuestos", registro_id=calc.id,
                        request=request)
    db.commit()
    return {"ok": True, "mensaje": "Enviado al Director y a la Supervisora; "
                                   "cualquiera de los dos puede autorizarlo."}


@router.get("/pendientes")
def cola_de_autorizacion(u: Usuario = Depends(solo_autorizadores),
                         db: Session = Depends(get_db)):
    """La cola de revisión del Director y la Supervisora."""
    calcs = (db.query(CalculoImpuesto)
             .filter(CalculoImpuesto.estatus == EstatusCalculo.EN_AUTORIZACION)
             .order_by(CalculoImpuesto.timestamp_enviado.asc()).all())
    return [_serializar(c, _balanza_del_periodo(db, c)) for c in calcs]


@router.get("/por-contador")
def avance_por_contador(mes: int, anio: int,
                        u: Usuario = Depends(solo_autorizadores),
                        db: Session = Depends(get_db)):
    """
    La cola de autorización ORGANIZADA POR CONTADOR, no como una lista plana
    de cálculos (que se volvía paja ilegible).

    Por cada contador: cuántos clientes tiene a su cargo y en qué punto va
    cada uno — sin cálculo, elaborado (borrador), enviado a autorización,
    regresado con correcciones, autorizado o ya declarado. Los que están al
    corriente ('todo_listo') se mandan al fondo para que arriba queden los
    que deben trabajo.
    """
    contadores = {}
    clientes = (db.query(Cliente)
                .filter(Cliente.estatus == EstatusCliente.ACTIVO).all())
    for cl in clientes:
        cid = cl.contador_asignado_id
        c = contadores.setdefault(cid, {
            "contador_id": cid,
            "contador": (cl.contador_asignado.nombre if cl.contador_asignado
                         else "Sin contador asignado"),
            "clientes": []})
        c["clientes"].append({"cliente_id": cl.id, "cliente": cl.nombre_comercial,
                              "tipo_cliente": cl.tipo_cliente.value,
                              "regimen_fiscal": cl.regimen_fiscal,
                              "calculo_id": None, "estatus": "sin_calculo",
                              "total_a_pagar": None, "enviado_en": None})

    calcs = (db.query(CalculoImpuesto)
             .filter(CalculoImpuesto.mes == mes, CalculoImpuesto.anio == anio).all())
    por_cliente = {c.cliente_id: c for c in
                   sorted(calcs, key=lambda x: x.id)}   # el más reciente gana
    for grupo in contadores.values():
        for fila in grupo["clientes"]:
            calc = por_cliente.get(fila["cliente_id"])
            if not calc:
                continue
            fila.update({
                "calculo_id": calc.id, "estatus": calc.estatus.value,
                "total_a_pagar": calc.total_a_pagar,
                "elaborado_por": (calc.elaborado_por.nombre
                                  if calc.elaborado_por else None),
                "enviado_en": (calc.timestamp_enviado.isoformat()
                               if calc.timestamp_enviado else None)})

    salida = []
    for grupo in contadores.values():
        conteo = {}
        for f in grupo["clientes"]:
            conteo[f["estatus"]] = conteo.get(f["estatus"], 0) + 1
        total = len(grupo["clientes"])
        # "Cerrado" = ya no depende de este contador: autorizado o declarado.
        cerrados = conteo.get("autorizado", 0) + conteo.get("declarado", 0)
        # Lo que ESPERA FIRMA del autorizador ahora mismo:
        esperando = conteo.get("en_autorizacion", 0)
        # Lo que le falta MOVER al contador (no ha mandado nada, o le
        # regresaron correcciones):
        pendiente_contador = (conteo.get("sin_calculo", 0)
                              + conteo.get("borrador", 0)
                              + conteo.get("rechazado", 0))
        grupo.update({
            "total_clientes": total,
            "esperando_firma": esperando,
            "pendiente_contador": pendiente_contador,
            "cerrados": cerrados,
            "avance_pct": round(cerrados / total * 100) if total else 0,
            "conteo": conteo,
            "todo_listo": esperando == 0 and pendiente_contador == 0,
        })
        # Dentro de cada contador: primero lo que espera firma
        orden = {"en_autorizacion": 0, "rechazado": 1, "borrador": 2,
                 "sin_calculo": 3, "autorizado": 4, "declarado": 5}
        grupo["clientes"].sort(key=lambda f: (orden.get(f["estatus"], 9),
                                              f["cliente"]))
        salida.append(grupo)

    # Los que están al corriente, hasta abajo (para no estorbar la lista)
    salida.sort(key=lambda g: (g["todo_listo"], -g["esperando_firma"],
                               -g["pendiente_contador"], g["contador"]))
    return salida


@router.post("/{calculo_id}/autorizar")
def autorizar(calculo_id: int, request: Request,
              u: Usuario = Depends(solo_autorizadores),
              db: Session = Depends(get_db)):
    calc = db.query(CalculoImpuesto).get(calculo_id)
    if not calc:
        raise HTTPException(404, "Cálculo no encontrado")
    if calc.estatus != EstatusCalculo.EN_AUTORIZACION:
        raise HTTPException(409, f"El cálculo está '{calc.estatus.value}'")
    # Segregación de funciones: un CONTADOR nunca autoriza lo que él elaboró.
    # La SUPERVISORA (jefa del despacho), el DIRECTOR y el ADMINISTRADOR SÍ
    # pueden autorizar sus propios cálculos —decisión del despacho: quien
    # revisa a los demás responde por lo suyo— pero queda REGISTRADO como
    # autoautorización, visible en la bitácora y en el tablero del Director.
    auto_autorizado = calc.elaborado_por_id == u.id
    if auto_autorizado and u.rol == RolUsuario.CONTADOR:
        raise HTTPException(403, "Quien elabora no puede autorizar su propio "
                                 "cálculo (segregación de funciones)")

    # La balanza que originó el cálculo queda VINCULADA al autorizarse:
    # si mañana hace falta, se sabe exactamente cuál se usó.
    balanza = _balanza_del_periodo(db, calc)
    if balanza:
        resultado = dict(calc.resultado or {})
        resultado["balanza_documento_id"] = balanza
        calc.resultado = resultado
    if auto_autorizado:
        resultado = dict(calc.resultado or {})
        resultado["auto_autorizado"] = True
        calc.resultado = resultado
    # PREDICCIÓN vs AUTORIZADO: si el agente CONTPAQ predijo este periodo,
    # el cálculo autorizado la sustituye y queda la comparación en ambos
    # lados: en la hoja ("qué tan precisa fue") y en el snapshot (historial
    # de precisión del motor por cliente).
    snap = (db.query(SnapshotContpaq)
            .filter_by(cliente_id=calc.cliente_id, tipo="prediccion",
                       anio=calc.anio, mes=calc.mes).first())
    if snap and (snap.datos or {}).get("prediccion"):
        pred = snap.datos["prediccion"]
        esc = pred.get("escenarios", {})
        central = (esc.get("central") or {}).get("total_estimado")
        if central is not None:
            real = float(calc.total_a_pagar or 0)
            dif = round(real - float(central), 2)
            base_pct = max(abs(real), abs(float(central)), 0.01)
            comparacion = {
                "predicho_central": round(float(central), 2),
                "predicho_pesimista": (esc.get("pesimista") or {}).get("total_estimado"),
                "predicho_optimista": (esc.get("optimista") or {}).get("total_estimado"),
                "real_autorizado": round(real, 2),
                "diferencia": dif,
                "diferencia_pct": round(dif / base_pct * 100, 2),
                "precision_pct": round(max(0.0, 100 - abs(dif) / base_pct * 100), 2),
                "dia_prediccion": snap.datos.get("dia"),
                "modo": pred.get("modo_proyeccion"),
            }
            resultado = dict(calc.resultado or {})
            resultado["comparacion_prediccion"] = comparacion
            calc.resultado = resultado
            snap.datos = {**snap.datos, "comparacion": comparacion}

    calc.estatus = EstatusCalculo.AUTORIZADO
    calc.autorizado_por_id = u.id
    calc.timestamp_autorizado = datetime.utcnow()
    correo.enviar_correo(
        calc.elaborado_por.email,
        f"AUTORIZADO: {calc.cliente.nombre_comercial} {calc.anio}-{calc.mes:02d}",
        f"{u.nombre} autorizó su determinación de impuestos "
        f"(${calc.total_a_pagar:,.2f}). Ya puede presentar la declaración y "
        f"subir la línea de captura al sistema.")
    auditoria.registrar(db, usuario_id=u.id,
                        accion=("autoautorizacion_calculo" if auto_autorizado
                                else "autorizacion_calculo"),
                        tabla_afectada="calculos_impuestos", registro_id=calc.id,
                        request=request, total=calc.total_a_pagar,
                        auto_autorizado=auto_autorizado,
                        elaboro=calc.elaborado_por.nombre)
    db.commit()
    return {"ok": True, "auto_autorizado": auto_autorizado,
            "mensaje": ("Autorizado por usted mismo (queda registrado como "
                        "autoautorización). Ya puede declarar."
                        if auto_autorizado else
                        f"Autorizado. {calc.elaborado_por.nombre} ya puede declarar.")}


class Rechazo(BaseModel):
    correcciones: list[dict]  # [{"campo": "...", "comentario": "..."}]


@router.post("/{calculo_id}/rechazar")
def rechazar(calculo_id: int, payload: Rechazo, request: Request,
             u: Usuario = Depends(solo_autorizadores),
             db: Session = Depends(get_db)):
    """Regresa el cálculo con correcciones puntuales por campo."""
    calc = db.query(CalculoImpuesto).get(calculo_id)
    if not calc:
        raise HTTPException(404, "Cálculo no encontrado")
    if calc.estatus != EstatusCalculo.EN_AUTORIZACION:
        raise HTTPException(409, f"El cálculo está '{calc.estatus.value}'")
    if not payload.correcciones:
        raise HTTPException(400, "Indique al menos una corrección")

    ahora = datetime.utcnow().isoformat() + "Z"
    nuevas = [{"campo": c.get("campo", "general"),
               "comentario": (c.get("comentario") or "").strip()[:500],
               "autor": u.nombre, "ts": ahora}
              for c in payload.correcciones if c.get("comentario")]
    calc.correcciones = list(calc.correcciones or []) + nuevas
    calc.estatus = EstatusCalculo.RECHAZADO

    detalle = "\n".join(f"- {c['campo']}: {c['comentario']}" for c in nuevas)
    correo.enviar_correo(
        calc.elaborado_por.email,
        f"Correcciones: {calc.cliente.nombre_comercial} {calc.anio}-{calc.mes:02d}",
        f"{u.nombre} regresó la determinación con correcciones puntuales:\n\n"
        f"{detalle}\n\nCorrija los datos en el sistema y reenvíe a autorización.")
    auditoria.registrar(db, usuario_id=u.id, accion="rechazo_calculo",
                        tabla_afectada="calculos_impuestos", registro_id=calc.id,
                        request=request, correcciones=len(nuevas))
    db.commit()
    return {"ok": True, "mensaje": f"Regresado a {calc.elaborado_por.nombre} "
                                   f"con {len(nuevas)} corrección(es)."}


@router.get("/mios")
def mis_calculos(mes: int, anio: int,
                 u: Usuario = Depends(solo_equipo_contable),
                 db: Session = Depends(get_db)):
    """Cálculos del periodo para el panel del contador (todos los del equipo)."""
    calcs = (db.query(CalculoImpuesto)
             .filter_by(mes=mes, anio=anio)
             .order_by(CalculoImpuesto.timestamp_creado.desc()).all())
    return [_serializar(c, _balanza_del_periodo(db, c)) for c in calcs]


@router.get("/{calculo_id}")
def ver_calculo(calculo_id: int,
                u: Usuario = Depends(solo_equipo_contable),
                db: Session = Depends(get_db)):
    calc = db.query(CalculoImpuesto).get(calculo_id)
    if not calc:
        raise HTTPException(404, "Cálculo no encontrado")
    return _serializar(calc, _balanza_del_periodo(db, calc))
