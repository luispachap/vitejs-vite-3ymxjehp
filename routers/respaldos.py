# -*- coding: utf-8 -*-
"""
RESPALDOS DE CONTPAQ — con rotación automática
==============================================
Los respaldos periódicos que ya hace el despacho ahora viven también en el
sistema, cifrados y fuera de la oficina (si falla una computadora, el
respaldo está a salvo).

ROTACIÓN: se conservan los últimos N por cliente (configurable, por omisión
3). Al subir uno nuevo, el más antiguo se borra —del almacenamiento y de la
base— de forma automática. Así el espacio no crece sin control.

⚠ Ojo con el plan gratuito de Supabase (1 GB de almacenamiento en total):
los respaldos de CONTPAQ pesan. El sistema avisa cuando el acumulado del
cliente rebasa el umbral de advertencia.
"""
import os

from fastapi import (APIRouter, Depends, File, Form, HTTPException, Request,
                     UploadFile)
from sqlalchemy.orm import Session

from database import get_db
from models.models import CategoriaDocumento, Cliente, DocumentoClave, Usuario
from services import almacenamiento, auditoria
from services.auth import solo_equipo_contable

router = APIRouter(prefix="/api/respaldos", tags=["Respaldos CONTPAQ"])

RESPALDOS_A_CONSERVAR = int(os.getenv("RESPALDOS_CONTPAQ_A_CONSERVAR", "3"))
EXTENSIONES = (".zip", ".rar", ".bak", ".7z", ".sql")
MB_ADVERTENCIA = 300  # avisar si el cliente acumula más de esto


def _serializar(d: DocumentoClave, tamano=None) -> dict:
    return {"id": d.id, "cliente_id": d.cliente_id,
            "cliente": d.cliente.nombre_comercial if d.cliente else None,
            "periodo": f"{d.mes:02d}/{d.anio}",
            "archivo": almacenamiento.nombre_descarga(d.ruta_archivo),
            "subido_en": d.subido_en.isoformat() if d.subido_en else None}


@router.get("")
def listar_respaldos(cliente_id: int | None = None,
                     u: Usuario = Depends(solo_equipo_contable),
                     db: Session = Depends(get_db)):
    """Respaldos vigentes (los más nuevos primero), por cliente o todos."""
    q = (db.query(DocumentoClave)
         .filter(DocumentoClave.categoria == CategoriaDocumento.RESPALDO_CONTPAQ))
    if cliente_id:
        q = q.filter(DocumentoClave.cliente_id == cliente_id)
    docs = q.order_by(DocumentoClave.id.desc()).limit(60).all()
    return {"conservados_por_cliente": RESPALDOS_A_CONSERVAR,
            "respaldos": [_serializar(d) for d in docs]}


@router.post("/{cliente_id}")
def subir_respaldo(cliente_id: int, request: Request,
                   anio: int = Form(...), mes: int = Form(...),
                   archivo: UploadFile = File(...),
                   u: Usuario = Depends(solo_equipo_contable),
                   db: Session = Depends(get_db)):
    """
    Sube un respaldo y ROTA: conserva los N más recientes de ese cliente y
    elimina los anteriores (archivo y registro), dejando huella en la
    bitácora de cuál se sustituyó.
    """
    cliente = db.query(Cliente).get(cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    nombre = (archivo.filename or "").lower()
    if not any(nombre.endswith(e) for e in EXTENSIONES):
        raise HTTPException(400, f"Formato no permitido. Acepto: "
                                 f"{', '.join(EXTENSIONES)}")

    contenido = archivo.file.read()
    ruta = almacenamiento.guardar_documento(
        contenido, f"respaldos/cliente{cliente_id}",
        f"contpaq_{anio}_{mes:02d}_{nombre.replace(' ', '_')}")
    doc = DocumentoClave(cliente_id=cliente_id,
                         categoria=CategoriaDocumento.RESPALDO_CONTPAQ,
                         ruta_archivo=ruta, anio=anio, mes=mes)
    db.add(doc)
    db.flush()

    # --- ROTACIÓN: fuera los más viejos ---
    todos = (db.query(DocumentoClave)
             .filter(DocumentoClave.cliente_id == cliente_id,
                     DocumentoClave.categoria == CategoriaDocumento.RESPALDO_CONTPAQ)
             .order_by(DocumentoClave.id.desc()).all())
    eliminados = []
    for viejo in todos[RESPALDOS_A_CONSERVAR:]:
        try:
            almacenamiento.eliminar_documento(viejo.ruta_archivo)
        except Exception:
            pass  # si el archivo ya no existe, igual se limpia el registro
        eliminados.append(f"{viejo.mes:02d}/{viejo.anio}")
        db.delete(viejo)

    auditoria.registrar(db, usuario_id=u.id, accion="respaldo_contpaq",
                        tabla_afectada="documentos_clave", registro_id=doc.id,
                        request=request, cliente=cliente.nombre_comercial,
                        periodo=f"{anio}-{mes:02d}",
                        mb=round(len(contenido) / (1024 * 1024), 1),
                        rotados=eliminados)
    db.commit()

    mb = round(len(contenido) / (1024 * 1024), 1)
    return {"ok": True, "respaldo_id": doc.id, "mb": mb,
            "conservados": min(len(todos), RESPALDOS_A_CONSERVAR),
            "eliminados_por_rotacion": eliminados,
            "advertencia": (f"Este respaldo pesa {mb} MB. Vigile el espacio "
                            f"disponible del plan de almacenamiento."
                            if mb > MB_ADVERTENCIA else None)}


@router.get("/{documento_id}/descargar")
def descargar_respaldo(documento_id: int, request: Request,
                       u: Usuario = Depends(solo_equipo_contable),
                       db: Session = Depends(get_db)):
    """Recupera un respaldo (queda auditado quién lo bajó y cuándo)."""
    doc = db.query(DocumentoClave).get(documento_id)
    if not doc or doc.categoria != CategoriaDocumento.RESPALDO_CONTPAQ:
        raise HTTPException(404, "Respaldo no encontrado")
    auditoria.registrar(db, usuario_id=u.id, accion="descarga_respaldo",
                        tabla_afectada="documentos_clave", registro_id=doc.id,
                        request=request)
    db.commit()

    return almacenamiento.respuesta_archivo(doc.ruta_archivo, inline=False)
