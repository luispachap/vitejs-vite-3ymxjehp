# -*- coding: utf-8 -*-
"""
PROGRAMADOR INTERNO (sustituye a Celery+Redis en despliegues sencillos)
=======================================================================
A la escala del despacho, las tareas automáticas son 3 rutinas diarias.
Correrlas DENTRO del propio servicio web ahorra dos servicios de paga en
Render (worker ~$7 + Redis ~$10): el sistema completo vive en $7/mes.

Las tres rutinas (hora de Zacatecas, America/Mexico_City):
  06:00  generar_tareas_nomina        -> crea las tareas de nómina próximas
  06:30  vigilar_certificados         -> avisa vencimientos de e.firma/CSD
  09:30  programar_recordatorios_...  -> recordatorios de vencimiento SAT

Si el despacho crece y algún día se quiere el worker dedicado, basta con
poner USAR_PROGRAMADOR_INTERNO=false en Render y volver a agregar los
servicios de Celery/Redis del render.yaml v1.3 (el código de services/
tareas.py sigue siendo compatible con ambos modos).
"""
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger("programador")
ZONA = ZoneInfo("America/Mexico_City")

_scheduler: BackgroundScheduler | None = None


def iniciar():
    """Arranca las rutinas diarias dentro del proceso web (idempotente)."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    # Las tareas de Celery son funciones normales al llamarse directo:
    # aquí las ejecutamos en el proceso, sin broker de por medio.
    from services.tareas import (generar_tareas_nomina,
                                 programar_recordatorios_vencimiento_sat,
                                 vigilar_certificados)

    _scheduler = BackgroundScheduler(timezone=ZONA)
    _scheduler.add_job(generar_tareas_nomina,
                       CronTrigger(hour=6, minute=0, timezone=ZONA),
                       id="tareas_nomina", replace_existing=True)
    _scheduler.add_job(vigilar_certificados,
                       CronTrigger(hour=6, minute=30, timezone=ZONA),
                       id="certificados", replace_existing=True)
    _scheduler.add_job(programar_recordatorios_vencimiento_sat,
                       CronTrigger(hour=9, minute=30, timezone=ZONA),
                       id="recordatorios_sat", replace_existing=True)
    _scheduler.start()
    log.info("Programador interno iniciado: %s rutinas diarias",
             len(_scheduler.get_jobs()))
    return _scheduler
