# -*- coding: utf-8 -*-
"""
MÓDULO DE COBRANZA AUTOMATIZADA: tareas asíncronas (Celery + Redis).
====================================================================
- Los envíos de WhatsApp/correo NO bloquean las peticiones web: se encolan.
- Celery Beat corre diario `programar_recordatorios_vencimiento_sat`:
  para cada honorario PENDIENTE cuyo cliente ignoró los mensajes, agenda
  recordatorios anclados EXCLUSIVAMENTE a la fecha límite del SAT
  ("su IVA vence mañana, evite recargos"), abriendo el canal de forma
  orgánica sin presionar directamente por los honorarios.

REGLA DE ORO: cada tarea valida `puede_automatizar_cobranza()` en el
momento de EJECUTAR (no solo al encolar) — si Pao apagó el switch o el
Director marcó al cliente como Trato Especial después de encolada la
tarea, el envío se cancela silenciosamente.

Arranque local:
    redis-server &
    celery -A services.tareas worker --loglevel=info &
    celery -A services.tareas beat --loglevel=info &
"""
import logging
from datetime import date, timedelta

from celery import Celery
from celery.schedules import crontab

import config
from database import SessionLocal
from models.models import EstatusPago, HonorarioCobranza
from services import whatsapp
from services.reglas_negocio import puede_automatizar_cobranza

logger = logging.getLogger("pya.tareas")

celery_app = Celery("pa_despacho", broker=config.REDIS_URL,
                    backend=config.REDIS_URL)
celery_app.conf.timezone = "America/Monterrey"
celery_app.conf.beat_schedule = {
    "generar-tareas-nomina": {
        "task": "services.tareas.generar_tareas_nomina",
        "schedule": crontab(hour=6, minute=0),  # diario 6:00
    },
    "vigilar-certificados": {
        "task": "services.tareas.vigilar_certificados",
        "schedule": crontab(hour=6, minute=30),  # diario 6:30
    },
    "recordatorios-vencimiento-sat-diario": {
        "task": "services.tareas.programar_recordatorios_vencimiento_sat",
        "schedule": crontab(hour=9, minute=30),  # 9:30 am, horario laboral
    },
}


@celery_app.task
def enviar_whatsapp_asincrono(telefono: str, mensaje: str,
                              adjunto_ruta: str | None = None):
    whatsapp._enviar(telefono, mensaje, adjunto_ruta)


@celery_app.task
def recordatorio_vencimiento_sat(honorario_id: int):
    """Recordatorio individual, con revalidación de la Regla de Oro."""
    db = SessionLocal()
    try:
        h = db.query(HonorarioCobranza).get(honorario_id)
        if not h or h.estatus_pago == EstatusPago.PAGADO:
            return "omitido: pagado o inexistente"
        # --- REGLA DE ORO revalidada al momento de ejecutar ---
        if not puede_automatizar_cobranza(h.cliente):
            return "omitido: regla de oro (trato especial / switch apagado)"

        obligacion = next((o for o in h.cliente.obligaciones
                           if o.mes == h.mes and o.anio == h.anio), None)
        vence = obligacion.fecha_vencimiento_sat if obligacion else None
        mensaje = (
            f"Hola {h.cliente.nombre_comercial}, le recuerda Regina de P&A: "
            f"su declaración del SAT vence "
            f"{'el ' + vence.strftime('%d de %B') if vence else 'próximamente'}. "
            f"Le reenvío su línea de captura para evitar recargos. "
            f"Quedamos atentos a cualquier duda. ¡Buen día!"
        )
        whatsapp._enviar(h.cliente.telefono_whatsapp, mensaje,
                         obligacion.ruta_archivo_linea_captura if obligacion else None)
        whatsapp.registrar_evento_bitacora(h, "recordatorio_vencimiento_sat",
                                           canal="whatsapp")
        db.commit()
        return "enviado"
    finally:
        db.close()


@celery_app.task
def programar_recordatorios_vencimiento_sat():
    """
    Barrido diario (Celery Beat): honorarios pendientes con mensajes
    ignorados -> recordatorio si el vencimiento del SAT está a <= 2 días.
    """
    db = SessionLocal()
    programados = 0
    try:
        hoy = date.today()
        pendientes = (db.query(HonorarioCobranza)
                      .filter(HonorarioCobranza.estatus_pago == EstatusPago.PENDIENTE)
                      .all())
        for h in pendientes:
            if not puede_automatizar_cobranza(h.cliente):
                continue
            historial = h.historial_notificaciones or []
            respondio = any(e.get("evento") == "respuesta_cliente" for e in historial)
            ya_hoy = any(e.get("evento") == "recordatorio_vencimiento_sat"
                         and e.get("ts", "").startswith(hoy.isoformat())
                         for e in historial)
            if respondio or ya_hoy:
                continue
            obligacion = next((o for o in h.cliente.obligaciones
                               if o.mes == h.mes and o.anio == h.anio), None)
            if not obligacion or not obligacion.fecha_vencimiento_sat:
                continue
            if hoy <= obligacion.fecha_vencimiento_sat <= hoy + timedelta(days=2):
                recordatorio_vencimiento_sat.delay(h.id)
                programados += 1
        return f"{programados} recordatorios programados"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# NÓMINAS: generación de tareas recurrentes por periodicidad del cliente
# ---------------------------------------------------------------------------

MESES_ES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _fechas_nomina_proximas(periodicidad: str, hoy):
    """Próximas fechas objetivo (7 días hacia adelante) según periodicidad."""
    import calendar
    from datetime import timedelta
    fechas = []
    for delta in range(0, 8):
        d = hoy + timedelta(days=delta)
        ultimo = calendar.monthrange(d.year, d.month)[1]
        if periodicidad == "semanal" and d.weekday() == 4:      # viernes
            fechas.append((d, f"Semana al {d.day} de {MESES_ES[d.month]} {d.year}"))
        elif periodicidad == "quincenal" and d.day in (15, ultimo):
            q = "Quincena 1" if d.day == 15 else "Quincena 2"
            fechas.append((d, f"{q} · {MESES_ES[d.month]} {d.year}"))
        elif periodicidad == "mensual" and d.day == ultimo:
            fechas.append((d, f"Nómina mensual · {MESES_ES[d.month]} {d.year}"))
    return fechas


@celery_app.task
def generar_tareas_nomina():
    """
    Diario: crea las tareas de emisión de nóminas que vengan en los próximos
    7 días para cada cliente con nómina habilitada (semanal=viernes,
    quincenal=15 y último, mensual=último). El unique evita duplicados: el
    sistema "acarrea" a los contadores sin repetir tareas.
    """
    from datetime import date
    from models.models import Cliente, TareaNomina
    db = SessionLocal()
    creadas = 0
    try:
        for cliente in (db.query(Cliente)
                        .filter(Cliente.tiene_nomina,
                                Cliente.estatus == "activo").all()):
            for fecha, etiqueta in _fechas_nomina_proximas(
                    cliente.periodicidad_nomina or "quincenal", date.today()):
                existe = (db.query(TareaNomina)
                          .filter_by(cliente_id=cliente.id,
                                     fecha_objetivo=fecha).first())
                if not existe:
                    db.add(TareaNomina(cliente_id=cliente.id,
                                       fecha_objetivo=fecha, etiqueta=etiqueta))
                    creadas += 1
        db.commit()
        return {"tareas_creadas": creadas}
    finally:
        db.close()


@celery_app.task
def vigilar_certificados():
    """
    Diario: revisa e.firmas, CSD y certificados IMSS/estatales. A 30 días
    del vencimiento (o ya vencidos) avisa por correo a la Supervisora y al
    Director para que soliciten la renovación a tiempo.
    """
    from datetime import date
    from models.models import CertificadoDigital, RolUsuario, Usuario
    from services import correo
    db = SessionLocal()
    avisos = 0
    try:
        criticos = [c for c in db.query(CertificadoDigital)
                    .filter(CertificadoDigital.reemplazado_por_id.is_(None)).all()
                    if c.estatus in ("por_vencer", "vencido") and not c.en_renovacion]
        if criticos:
            lineas = "\n".join(
                f"- {c.descripcion} "
                f"({c.cliente.nombre_comercial if c.cliente else 'despacho'}): "
                f"vence {c.fecha_vencimiento} [{c.estatus.replace('_', ' ')}]"
                for c in criticos)
            for a in (db.query(Usuario)
                      .filter(Usuario.rol.in_([RolUsuario.DIRECTOR,
                                               RolUsuario.SUPERVISOR]),
                              Usuario.activo).all()):
                correo.enviar_correo(
                    a.email,
                    f"ATENCIÓN: {len(criticos)} certificado(s) por vencer o vencidos",
                    "Certificados que requieren renovación:\n\n" + lineas +
                    "\n\nMárquelos 'en renovación' en el sistema y suban el "
                    "nuevo con 'reemplaza a' cuando esté listo.")
                avisos += 1
        return {"criticos": len(criticos), "avisos": avisos}
    finally:
        db.close()
