# -*- coding: utf-8 -*-
"""
VISTA SUPER-ADMIN / CFO (Luis y su Papá) — solo rol DIRECTOR.
=============================================================
- Ingresos generales del despacho (agregación en Python: montos cifrados).
- Consulta de la bitácora de auditoría (SOLO lectura: no existen endpoints
  de edición/borrado de logs en todo el sistema).
- Alta/baja de clientes y personal (baja = desactivación, nunca DELETE).
- Botón "Cliente Exento / Trato Especial": silencia por completo la
  cobranza automática (mensajes y llamadas IA); los rezagos de ese cliente
  pasan al terreno de las relaciones públicas humanas del Director.
"""
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.models import (Cliente, EstatusPago, HonorarioCobranza,
                           LogAuditoria, RolUsuario, TipoCliente, Usuario)
from services import auditoria
from services.auth import hash_password, solo_director

router = APIRouter(prefix="/api/admin", tags=["Super-Admin / CFO"])


_RE_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def _validar_correo(correo: str | None, obligatorio: bool = False) -> str | None:
    """
    Un correo mal escrito dejaba al cliente SIN PODER ENTRAR y sin que nadie
    se diera cuenta (la cuenta se creaba con el correo equivocado). Ahora se
    valida al dar de alta y al corregir.
    """
    correo = (correo or "").strip().lower()
    if not correo:
        if obligatorio:
            raise HTTPException(400, "Para crear su cuenta del portal hace "
                                     "falta el correo del cliente")
        return None
    if not _RE_CORREO.match(correo):
        raise HTTPException(400, f"El correo «{correo}» no tiene un formato "
                                 f"válido (debe ser como nombre@dominio.com)")
    return correo


@router.get("/ingresos")
def ingresos_generales(anio: int, u: Usuario = Depends(solo_director),
                       db: Session = Depends(get_db)):
    """Ingresos del despacho por mes (suma en Python: montos cifrados en BD)."""
    filas = (db.query(HonorarioCobranza)
             .filter(HonorarioCobranza.anio == anio).all())
    por_mes: dict[int, dict] = {m: {"facturado": 0.0, "cobrado": 0.0} for m in range(1, 13)}
    for h in filas:
        por_mes[h.mes]["facturado"] += h.monto_honorario
        if h.estatus_pago == EstatusPago.PAGADO:
            por_mes[h.mes]["cobrado"] += h.monto_honorario
    return {"anio": anio, "por_mes": por_mes,
            "total_facturado": sum(m["facturado"] for m in por_mes.values()),
            "total_cobrado": sum(m["cobrado"] for m in por_mes.values())}


@router.get("/clientes")
def listar_clientes_admin(u: Usuario = Depends(solo_director),
                          db: Session = Depends(get_db)):
    """Lista completa para el panel visual de administración."""
    return [{
        "id": c.id, "nombre_comercial": c.nombre_comercial,
        "razon_social": c.razon_social, "rfc": c.rfc,
        "telefono": c.telefono_whatsapp, "email": c.email,
        "tipo_cliente": c.tipo_cliente.value, "estatus": c.estatus.value,
        "automatizaciones_activas": c.automatizaciones_activas,
        "requerimiento_urgente": bool(c.requerimiento_urgente),
        "contador_asignado_id": c.contador_asignado_id,
        "contador_asignado": (c.contador_asignado.nombre
                              if c.contador_asignado else None),
        "tiene_imss": c.tiene_imss, "tiene_nomina": c.tiene_nomina,
        "periodicidad_nomina": c.periodicidad_nomina,
        "tipo_persona": c.tipo_persona, "regimen_fiscal": c.regimen_fiscal,
        "tiene_cuenta_portal": bool(c.usuario_portal_id),
        # Cobranza y CONTPAQ: para poder CORREGIRLOS, no solo capturarlos al alta
        "honorario_mensual": c.honorario_mensual,
        "periodicidad_honorario": c.periodicidad_honorario,
        "dia_corte_honorario": c.dia_corte_honorario,
        "bd_contpaq_contabilidad": c.bd_contpaq_contabilidad,
        "bd_contpaq_nomina": c.bd_contpaq_nomina,
        "bd_contpaq_add": c.bd_contpaq_add,
        "coeficiente_utilidad": c.coeficiente_utilidad,
        "boveda_completa": bool(c.boveda_completa),
        "opinion_32d_positiva": bool(c.opinion_32d_positiva),
    } for c in db.query(Cliente).order_by(Cliente.nombre_comercial).all()]


@router.get("/personal")
def listar_personal(u: Usuario = Depends(solo_director),
                    db: Session = Depends(get_db)):
    return [{"id": p.id, "nombre": p.nombre, "email": p.email,
             "rol": p.rol.value, "activo": p.activo,
             "totp_habilitado": p.totp_habilitado}
            for p in db.query(Usuario)
                       .filter(Usuario.rol != RolUsuario.CLIENTE)
                       .order_by(Usuario.nombre).all()]


@router.post("/clientes/{cliente_id}/reactivar")
def reactivar_cliente(cliente_id: int, request: Request,
                      u: Usuario = Depends(solo_director),
                      db: Session = Depends(get_db)):
    c = db.query(Cliente).get(cliente_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    c.estatus = "activo"
    auditoria.registrar(db, usuario_id=u.id, accion="reactivacion_cliente",
                        tabla_afectada="clientes", registro_id=c.id,
                        request=request)
    db.commit()
    return {"ok": True}


@router.post("/clientes/{cliente_id}/obligaciones")
def configurar_obligaciones(cliente_id: int, request: Request,
                            tiene_imss: bool = False,
                            tiene_nomina: bool = False,
                            periodicidad_nomina: str = "quincenal",
                            u: Usuario = Depends(solo_director),
                            db: Session = Depends(get_db)):
    """Habilita IMSS/nómina del cliente (define tareas y cierre de periodo)."""
    if periodicidad_nomina not in ("semanal", "quincenal", "mensual"):
        raise HTTPException(400, "Periodicidad no válida")
    c = db.query(Cliente).get(cliente_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    c.tiene_imss, c.tiene_nomina = tiene_imss, tiene_nomina
    c.periodicidad_nomina = periodicidad_nomina
    auditoria.registrar(db, usuario_id=u.id, accion="config_obligaciones",
                        tabla_afectada="clientes", registro_id=c.id,
                        request=request, imss=tiene_imss, nomina=tiene_nomina)
    db.commit()
    return {"ok": True}


@router.get("/auditoria")
def consultar_auditoria(limite: int = 100, u: Usuario = Depends(solo_director),
                        db: Session = Depends(get_db)):
    """Bitácora inmutable, más reciente primero. Solo lectura."""
    logs = (db.query(LogAuditoria)
            .order_by(LogAuditoria.timestamp.desc()).limit(min(limite, 500)).all())
    return [{"id": l.id, "usuario_id": l.usuario_id, "accion": l.accion,
             "tabla": l.tabla_afectada, "registro_id": l.registro_id,
             "detalles": l.detalles, "ip": l.ip_origen,
             "timestamp": l.timestamp} for l in logs]


class AltaCliente(BaseModel):
    nombre_comercial: str
    razon_social: str
    rfc: str
    telefono_whatsapp: str
    email: str | None = None
    tipo_cliente: TipoCliente = TipoCliente.ESTANDAR
    # Perfil fiscal (define la calculadora que usará el contador)
    tipo_persona: str | None = None          # fisica | moral
    regimen_fiscal: str | None = None        # llaves de fiscal_v2.REGIMENES
    contador_asignado_id: int | None = None
    tiene_imss: bool = False
    tiene_nomina: bool = False
    periodicidad_nomina: str = "quincenal"
    # COBRANZA: sin esto el módulo de cobranza no tiene de dónde tomar nada.
    honorario_mensual: float | None = None
    periodicidad_honorario: str = "mensual"     # mensual|bimestral|anual
    dia_corte_honorario: int = 1
    # Lo que YA debía antes de entrar al sistema (arranca con la verdad)
    adeudo_previo_monto: float | None = None
    adeudo_previo_concepto: str | None = None
    # Bases de CONTPAQi de este cliente (el agente las lee por RFC)
    bd_contpaq_contabilidad: str | None = None
    bd_contpaq_nomina: str | None = None
    bd_contpaq_add: str | None = None
    coeficiente_utilidad: float | None = None
    # Cuenta del portal: si crear_cuenta=True, se crea de una vez. La
    # contraseña puede darla el Director o dejarla en blanco para que el
    # sistema genere una TEMPORAL (que se muestra una vez y se entrega al
    # cliente; él la cambia en su primer acceso).
    crear_cuenta: bool = False
    password_portal: str | None = None


PALABRAS = ["fresnillo", "zacatecas", "despacho", "balanza", "cuenta",
            "factura", "auditor", "impuesto", "empresa", "recibo"]


def generar_password_temporal() -> str:
    """
    Contraseña temporal LEGIBLE, fácil de dictar por teléfono y difícil de
    adivinar (ej. "Despacho-4827-Zk"). El cliente debe cambiarla al entrar.
    """
    import secrets
    palabra = secrets.choice(PALABRAS).capitalize()
    numero = secrets.randbelow(9000) + 1000
    letras = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(2))
    return f"{palabra}-{numero}-{letras}"


def _validar_perfil_fiscal(tipo_persona, regimen_fiscal):
    from services import fiscal_v2
    if tipo_persona and tipo_persona not in ("fisica", "moral"):
        raise HTTPException(400, "tipo_persona debe ser 'fisica' o 'moral'")
    if regimen_fiscal:
        try:
            return fiscal_v2.normalizar_regimen(regimen_fiscal)
        except ValueError:
            raise HTTPException(400, f"Régimen no válido. Opciones: "
                                     f"{', '.join(fiscal_v2.REGIMENES)}")
    return regimen_fiscal


@router.post("/clientes")
def alta_cliente(payload: AltaCliente, request: Request,
                 u: Usuario = Depends(solo_director),
                 db: Session = Depends(get_db)):
    datos = payload.model_dump()
    password = datos.pop("password_portal", None)
    crear_cuenta = datos.pop("crear_cuenta", False) or bool(password)
    # El adeudo previo no es columna del cliente: se registra aparte
    adeudo_monto = datos.pop("adeudo_previo_monto", None)
    adeudo_concepto = datos.pop("adeudo_previo_concepto", None)
    datos["email"] = _validar_correo(datos.get("email"), obligatorio=crear_cuenta)
    datos["regimen_fiscal"] = _validar_perfil_fiscal(
        datos.get("tipo_persona"), datos.get("regimen_fiscal"))
    if datos.get("periodicidad_honorario") not in (None, "mensual", "bimestral", "anual"):
        raise HTTPException(400, "Periodicidad de honorarios no válida "
                                 "(mensual, bimestral o anual)")
    c = Cliente(**datos)
    db.add(c)
    db.flush()

    # Lo que ya debía ANTES de entrar al sistema
    if adeudo_monto and adeudo_monto > 0:
        from models.models import AdeudoPrevio
        db.add(AdeudoPrevio(
            cliente_id=c.id,
            concepto=(adeudo_concepto or "Saldo anterior al alta en el sistema")[:200],
            monto_original=round(adeudo_monto, 2), monto_pagado=0,
            registrado_por_id=u.id))
        db.flush()

    cuenta_creada = False
    password_entregar = None
    if crear_cuenta:
        if not c.email:
            raise HTTPException(400, "Para crear la cuenta del portal se "
                                     "necesita el correo del cliente")
        from services.auth import hash_password
        # Si el Director no escribe una, el sistema genera una TEMPORAL
        # legible para dictarla por teléfono o entregarla en mano.
        password_entregar = password or generar_password_temporal()
        if len(password_entregar) < 10:
            raise HTTPException(400, "La contraseña debe tener al menos 10 caracteres")
        usuario_portal = Usuario(nombre=c.nombre_comercial, email=c.email,
                                 rol=RolUsuario.CLIENTE,
                                 password_hash=hash_password(password_entregar),
                                 # Mientras no haya WhatsApp/correo conectados,
                                 # la contraseña se entrega en mano y el cliente
                                 # DEBE cambiarla en su primer acceso.
                                 debe_cambiar_password=True)
        db.add(usuario_portal)
        db.flush()
        c.usuario_portal_id = usuario_portal.id
        cuenta_creada = True

    auditoria.registrar(db, usuario_id=u.id, accion="alta_cliente",
                        tabla_afectada="clientes", registro_id=c.id,
                        request=request, nombre=c.nombre_comercial,
                        cuenta_portal=cuenta_creada)
    db.commit()
    return {"ok": True, "cliente_id": c.id, "cuenta_portal": cuenta_creada,
            # Se muestra UNA sola vez: el Director la entrega al cliente.
            "password_temporal": password_entregar,
            "aviso": ("Entregue esta contraseña al cliente. Se le pedirá "
                      "cambiarla en su primer acceso." if password_entregar else None)}


@router.post("/clientes/{cliente_id}/regenerar-password")
def regenerar_password_cliente(cliente_id: int, request: Request,
                               u: Usuario = Depends(solo_director),
                               db: Session = Depends(get_db)):
    """
    Genera una contraseña temporal nueva (si el cliente la olvidó o si nunca
    tuvo cuenta). Se muestra UNA vez para entregarla; el cliente la cambia al
    entrar. Cuando se conecte WhatsApp/correo, esto podrá enviarse solo.
    """
    from services.auth import hash_password
    c = db.query(Cliente).get(cliente_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")

    temporal = generar_password_temporal()
    if c.usuario_portal_id:
        # Ya tiene cuenta: se le repone la contraseña (su correo de acceso es
        # el del usuario, que puede diferir del correo de contacto del cliente)
        usuario = db.query(Usuario).get(c.usuario_portal_id)
        usuario.password_hash = hash_password(temporal)
        usuario.debe_cambiar_password = True
    else:
        if not c.email:
            raise HTTPException(400, "Para crear su acceso, primero capture el "
                                     "correo del cliente (botón Editar)")
        usuario = Usuario(nombre=c.nombre_comercial, email=c.email,
                          rol=RolUsuario.CLIENTE,
                          password_hash=hash_password(temporal),
                          debe_cambiar_password=True)
        db.add(usuario)
        db.flush()
        c.usuario_portal_id = usuario.id

    auditoria.registrar(db, usuario_id=u.id, accion="password_temporal_cliente",
                        tabla_afectada="clientes", registro_id=c.id,
                        request=request, cliente=c.nombre_comercial)
    db.commit()
    # Se dice EXPLÍCITAMENTE con qué correo entra: si el de contacto y el de
    # acceso difieren (por una corrección posterior), aquí se ve y se avisa.
    desincronizado = bool(c.email and c.email.lower() != usuario.email.lower())
    return {"ok": True, "email_de_acceso": usuario.email,
            "email_de_contacto": c.email,
            "password_temporal": temporal,
            "desincronizado": desincronizado,
            "aviso": ("Entréguela al cliente. Debe entrar con el correo "
                      f"{usuario.email} y cambiarla al primer acceso."
                      + (f" ⚠ OJO: el correo de contacto ({c.email}) es "
                         f"distinto al de acceso. Corrija el correo del "
                         f"cliente para emparejarlos."
                         if desincronizado else ""))}


@router.get("/cuentas-desincronizadas")
def cuentas_desincronizadas(u: Usuario = Depends(solo_director),
                            db: Session = Depends(get_db)):
    """
    Clientes cuyo correo de CONTACTO no coincide con el de ACCESO: son los
    que "no pueden entrar con ninguna contraseña". Pasa cuando se corrigió
    un correo mal escrito después de crear la cuenta.
    """
    salida = []
    for c in db.query(Cliente).filter(Cliente.usuario_portal_id.isnot(None)).all():
        cuenta = db.query(Usuario).get(c.usuario_portal_id)
        if cuenta and c.email and cuenta.email.lower() != c.email.lower():
            salida.append({"cliente_id": c.id, "cliente": c.nombre_comercial,
                           "email_contacto": c.email,
                           "email_acceso": cuenta.email})
    return salida


@router.post("/clientes/{cliente_id}/emparejar-correo")
def emparejar_correo(cliente_id: int, request: Request,
                     u: Usuario = Depends(solo_director),
                     db: Session = Depends(get_db)):
    """Pone en la cuenta de acceso el correo de contacto del cliente."""
    c = db.query(Cliente).get(cliente_id)
    if not c or not c.usuario_portal_id:
        raise HTTPException(404, "Ese cliente no tiene cuenta de portal")
    correo = _validar_correo(c.email)
    if not correo:
        raise HTTPException(400, "El cliente no tiene correo capturado")
    otro = (db.query(Usuario).filter(Usuario.email == correo,
                                     Usuario.id != c.usuario_portal_id).first())
    if otro:
        raise HTTPException(409, f"Ya hay otra cuenta con el correo {correo}")
    cuenta = db.query(Usuario).get(c.usuario_portal_id)
    anterior = cuenta.email
    cuenta.email = correo
    auditoria.registrar(db, usuario_id=u.id, accion="emparejar_correo_portal",
                        tabla_afectada="usuarios", registro_id=cuenta.id,
                        request=request, antes=anterior, ahora=correo)
    db.commit()
    return {"ok": True, "email_de_acceso": correo,
            "mensaje": f"Ahora el cliente entra con {correo}. Si no recuerda "
                       f"su contraseña, genérele una nueva."}


class EdicionCliente(BaseModel):
    """Todos los campos corregibles del cliente (los que vengan se aplican)."""
    nombre_comercial: str | None = None
    razon_social: str | None = None
    rfc: str | None = None
    telefono_whatsapp: str | None = None
    email: str | None = None
    tipo_persona: str | None = None
    regimen_fiscal: str | None = None
    contador_asignado_id: int | None = None
    tiene_imss: bool | None = None
    tiene_nomina: bool | None = None
    periodicidad_nomina: str | None = None
    nombre_alternativo_telefono: str | None = None
    numero_compartido: bool | None = None
    tipo_cliente: TipoCliente | None = None
    # Cobranza
    honorario_mensual: float | None = None
    periodicidad_honorario: str | None = None
    dia_corte_honorario: int | None = None
    # CONTPAQi
    bd_contpaq_contabilidad: str | None = None
    bd_contpaq_nomina: str | None = None
    bd_contpaq_add: str | None = None
    coeficiente_utilidad: float | None = None
    # Acceso ampliado a su expediente completo
    boveda_completa: bool | None = None
    opinion_32d_positiva: bool | None = None


@router.put("/clientes/{cliente_id}")
def editar_cliente(cliente_id: int, payload: EdicionCliente, request: Request,
                   u: Usuario = Depends(solo_director),
                   db: Session = Depends(get_db)):
    """
    Corrección de cualquier dato del cliente. TODO cambio deja rastro: la
    bitácora guarda campo por campo el valor anterior y el nuevo. (Los logs
    de auditoría son lo único intocable del sistema.)
    """
    c = db.query(Cliente).get(cliente_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")

    cambios = payload.model_dump(exclude_unset=True, exclude_none=True)
    # ⚠ EL CORREO ES TAMBIÉN SU USUARIO DE ACCESO. Antes se corregía aquí y
    # la CUENTA se quedaba con el correo viejo: el cliente no podía entrar
    # con ninguna contraseña, por más que se le regeneraran. Ahora se
    # actualizan los dos.
    if "email" in cambios:
        cambios["email"] = _validar_correo(cambios["email"])
        if cambios["email"] and c.usuario_portal_id:
            otro = (db.query(Usuario)
                    .filter(Usuario.email == cambios["email"],
                            Usuario.id != c.usuario_portal_id).first())
            if otro:
                raise HTTPException(409, f"Ya hay otra cuenta con el correo "
                                         f"{cambios['email']}")
            cuenta = db.query(Usuario).get(c.usuario_portal_id)
            if cuenta and cuenta.email != cambios["email"]:
                cuenta.email = cambios["email"]
                auditoria.registrar(db, usuario_id=u.id,
                                    accion="correo_cuenta_portal_actualizado",
                                    tabla_afectada="usuarios",
                                    registro_id=cuenta.id, request=request,
                                    nuevo=cambios["email"])
    if "regimen_fiscal" in cambios or "tipo_persona" in cambios:
        cambios["regimen_fiscal"] = _validar_perfil_fiscal(
            cambios.get("tipo_persona", c.tipo_persona),
            cambios.get("regimen_fiscal", c.regimen_fiscal))
        if not cambios["regimen_fiscal"]:
            cambios.pop("regimen_fiscal")

    difs = {}
    SENSIBLES = {"rfc"}  # cifrados: no exponer el valor previo en el log
    for campo, nuevo in cambios.items():
        viejo_v = getattr(c, campo, None)
        if viejo_v != nuevo:
            difs[campo] = ("(actualizado)" if campo in SENSIBLES
                           else {"antes": viejo_v, "ahora": nuevo})
            setattr(c, campo, nuevo)
    if not difs:
        return {"ok": True, "sin_cambios": True}

    auditoria.registrar(db, usuario_id=u.id, accion="edicion_cliente",
                        tabla_afectada="clientes", registro_id=c.id,
                        request=request, cambios=difs)
    db.commit()
    return {"ok": True, "cambios": list(difs.keys())}


@router.post("/clientes/{cliente_id}/baja")
def baja_cliente(cliente_id: int, request: Request,
                 u: Usuario = Depends(solo_director),
                 db: Session = Depends(get_db)):
    c = db.query(Cliente).get(cliente_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    c.estatus = "suspendido"
    auditoria.registrar(db, usuario_id=u.id, accion="baja_cliente",
                        tabla_afectada="clientes", registro_id=c.id,
                        request=request)
    db.commit()
    return {"ok": True}


@router.post("/clientes/{cliente_id}/trato-especial")
def trato_especial(cliente_id: int, activar: bool, request: Request,
                   u: Usuario = Depends(solo_director),
                   db: Session = Depends(get_db)):
    """
    Botón "Cliente Exento / Trato Especial".
    activar=True  -> tipo CONFIANZA_ESPECIAL + automatizaciones apagadas:
                     CERO recordatorios y CERO llamadas IA. Gestión 100%
                     humana del Director.
    activar=False -> regresa a ESTANDAR con automatizaciones encendidas.
    """
    c = db.query(Cliente).get(cliente_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    c.tipo_cliente = (TipoCliente.CONFIANZA_ESPECIAL if activar
                      else TipoCliente.ESTANDAR)
    c.automatizaciones_activas = not activar
    auditoria.registrar(db, usuario_id=u.id, accion="trato_especial",
                        tabla_afectada="clientes", registro_id=c.id,
                        request=request, activado=activar,
                        cliente=c.nombre_comercial)
    db.commit()
    return {"ok": True, "tipo_cliente": c.tipo_cliente.value,
            "automatizaciones_activas": c.automatizaciones_activas}


@router.post("/clientes/{cliente_id}/requerimiento-urgente")
def requerimiento_urgente(cliente_id: int, activar: bool, request: Request,
                          u: Usuario = Depends(solo_director),
                          db: Session = Depends(get_db)):
    """Enciende/apaga el estado ROJO del Semáforo Fiscal del cliente."""
    c = db.query(Cliente).get(cliente_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    c.requerimiento_urgente = activar
    auditoria.registrar(db, usuario_id=u.id, accion="requerimiento_urgente",
                        tabla_afectada="clientes", registro_id=c.id,
                        request=request, activado=activar)
    db.commit()
    return {"ok": True, "requerimiento_urgente": c.requerimiento_urgente}


@router.post("/clientes/{cliente_id}/asignar-contador")
def asignar_contador(cliente_id: int, usuario_id: int, request: Request,
                     u: Usuario = Depends(solo_director),
                     db: Session = Depends(get_db)):
    """Define qué contador(a) lleva la contabilidad de este cliente."""
    c = db.query(Cliente).get(cliente_id)
    contador = db.query(Usuario).get(usuario_id)
    if not c or not contador:
        raise HTTPException(404, "Cliente o contador no encontrados")
    # Quién puede llevar la contabilidad de un cliente: los contadores, pero
    # también Artemisa (supervisora Y contadora), Pao (que también hace
    # contabilidades), el Director y el Administrador.
    ROLES_QUE_LLEVAN_CONTABILIDAD = (
        RolUsuario.CONTADOR, RolUsuario.SUPERVISOR, RolUsuario.ADMIN_SECRETARIA,
        RolUsuario.DIRECTOR, RolUsuario.ADMINISTRADOR)
    if contador.rol not in ROLES_QUE_LLEVAN_CONTABILIDAD:
        raise HTTPException(400, "Solo se puede asignar personal contable")
    c.contador_asignado_id = contador.id
    auditoria.registrar(db, usuario_id=u.id, accion="asignacion_contador",
                        tabla_afectada="clientes", registro_id=c.id,
                        request=request, contador=contador.nombre)
    db.commit()
    return {"ok": True, "contador_asignado": contador.nombre}


class AltaPersonal(BaseModel):
    nombre: str
    email: str
    password: str
    rol: RolUsuario


@router.post("/personal")
def alta_personal(payload: AltaPersonal, request: Request,
                  u: Usuario = Depends(solo_director),
                  db: Session = Depends(get_db)):
    if db.query(Usuario).filter(Usuario.email == payload.email).first():
        raise HTTPException(409, "Ese correo ya está registrado")
    nuevo = Usuario(nombre=payload.nombre, email=payload.email,
                    rol=payload.rol,
                    password_hash=hash_password(payload.password))
    db.add(nuevo)
    db.flush()
    auditoria.registrar(db, usuario_id=u.id, accion="alta_personal",
                        tabla_afectada="usuarios", registro_id=nuevo.id,
                        request=request, rol=payload.rol.value)
    db.commit()
    return {"ok": True, "usuario_id": nuevo.id,
            "nota": "En producción deberá enrolar 2FA antes de su primer acceso"}


@router.post("/personal/{usuario_id}/baja")
def baja_personal(usuario_id: int, request: Request,
                  u: Usuario = Depends(solo_director),
                  db: Session = Depends(get_db)):
    p = db.query(Usuario).get(usuario_id)
    if not p:
        raise HTTPException(404, "Usuario no encontrado")
    if p.id == u.id:
        raise HTTPException(400, "No puede darse de baja a sí mismo")
    p.activo = False
    auditoria.registrar(db, usuario_id=u.id, accion="baja_personal",
                        tabla_afectada="usuarios", registro_id=p.id,
                        request=request)
    db.commit()
    return {"ok": True}
