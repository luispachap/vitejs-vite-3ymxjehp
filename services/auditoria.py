# -*- coding: utf-8 -*-
"""
SEGURIDAD 2: Registro de auditoría.
===================================
Punto único para escribir en LogsAuditoria. Los routers llaman a
`registrar()` ANTES de retornar la respuesta en toda acción sensible:
descargas de documentos, cambios de saldo/estatus, accesos al portal.

La tabla es de solo-inserción por diseño: el sistema NO expone ningún
endpoint de UPDATE o DELETE sobre logs_auditoria, y en producción se
recomienda además revocar esos permisos a nivel de PostgreSQL:

    REVOKE UPDATE, DELETE ON logs_auditoria FROM app_user;
"""
from fastapi import Request
from sqlalchemy.orm import Session

from models.models import LogAuditoria


def ip_de(request: Request) -> str:
    """IP real del cliente, respetando proxy inverso (nginx/Caddy)."""
    reenviada = request.headers.get("x-forwarded-for")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"


def registrar(db: Session, *, usuario_id: int | None, accion: str,
              tabla_afectada: str, registro_id: int | None,
              request: Request | None = None, **detalles) -> None:
    """
    Inserta el log de auditoría. Se llama dentro de la misma transacción
    que la acción auditada: si la acción falla, el log tampoco se guarda
    (y viceversa), manteniendo consistencia.
    """
    db.add(LogAuditoria(
        usuario_id=usuario_id,
        accion=accion,
        tabla_afectada=tabla_afectada,
        registro_id=registro_id,
        detalles=detalles or None,
        ip_origen=ip_de(request) if request else None,
    ))
