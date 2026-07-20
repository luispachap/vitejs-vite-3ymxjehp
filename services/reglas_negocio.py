# -*- coding: utf-8 -*-
"""
REGLA DE ORO OPERATIVA: "MODO HUMANO PRIMERO"
=============================================
Esta función es el ÚNICO punto de decisión válido antes de disparar
cualquier automatización de COBRANZA (recordatorios de honorarios por
WhatsApp o llamadas de la IA de voz "Regina").

Toda ruta o servicio que intente cobrar automáticamente DEBE pasar por aquí.
Nunca se debe evaluar esta regla "a mano" en otro lugar del código.
"""
from models.models import Cliente, TipoCliente


def puede_automatizar_cobranza(cliente: Cliente) -> bool:
    """
    Retorna True SOLO si es permitido enviar recordatorios de honorarios
    automáticos o disparar llamadas de IA a este cliente.

    PROHIBIDO automatizar si:
    1. El cliente es Tipo_Cliente = CONFIANZA_ESPECIAL (cobranza 100% humana,
       manejada directamente por el Director).
    2. El switch 'automatizaciones_activas' fue apagado manualmente por la
       secretaria en su panel (pestaña roja, Módulo 3).
    """
    if cliente.tipo_cliente == TipoCliente.CONFIANZA_ESPECIAL:
        return False
    if not cliente.automatizaciones_activas:
        return False
    return True


def puede_enviar_linea_captura(cliente: Cliente) -> bool:
    """
    Regla de Entrega Transparente ("Cero Secuestro de Impuestos", Módulo 4):
    la línea de captura del SAT se envía SIEMPRE, a TODOS los clientes activos,
    sin importar su estatus de pago de honorarios. Es puramente informativa.
    """
    return cliente.estatus.value == "activo"
