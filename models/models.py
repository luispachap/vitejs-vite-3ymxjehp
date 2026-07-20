# -*- coding: utf-8 -*-
"""
P&A Despacho Contable - Modelos de Base de Datos (SQLAlchemy 2.0)
=================================================================
MÓDULO 1: Arquitectura de datos y roles de acceso.

Notas de diseño:
- Enums de Python -> tipos Enum de SQL para integridad referencial de estatus.
- `Cliente.automatizaciones_activas` es el switch manual del panel de Pao.
- `HonorarioCobranza.historial_notificaciones` (JSON) guarda la bitácora
  cronológica de webhooks (entregado / leído / llamada IA) que sirve como
  herramienta de deslinde de responsabilidad legal de la firma.
"""
import enum
from datetime import datetime, date

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, JSON, UniqueConstraint, event
)
from sqlalchemy.orm import relationship

from database import Base
from services.campo_cifrado import TextoCifrado, NumeroCifrado, hash_busqueda


# ---------------------------------------------------------------------------
# ENUMS DE NEGOCIO
# ---------------------------------------------------------------------------

class RolUsuario(str, enum.Enum):
    ADMINISTRADOR = "administrador"        # Luis: acceso técnico TOTAL al sistema
                                           # (todo lo que ve cualquier rol + admin)
    DIRECTOR = "director"                  # Papá: dueño; acceso a TODO el despacho
    SUPERVISOR = "supervisor"              # Artemisa: jefa del despacho. También es
                                           # CONTADORA: elabora cálculos Y autoriza
                                           # los de otros (nunca los suyos).
    ADMIN_SECRETARIA = "admin_secretaria"  # Pao: panel simplificado de cobranza
    CONTADOR = "contador"                  # Equipo operativo
    CLIENTE = "cliente"                    # Acceso al Portal VIP


class TipoCliente(str, enum.Enum):
    VIP = "vip"
    ESTANDAR = "estandar"
    CONFIANZA_ESPECIAL = "confianza_especial"  # REGLA DE ORO: cobranza 100% humana


class EstatusCliente(str, enum.Enum):
    ACTIVO = "activo"
    SUSPENDIDO = "suspendido"


class EstatusContabilidad(str, enum.Enum):
    PENDIENTE = "pendiente"
    EN_PROCESO = "en_proceso"
    TERMINADO = "terminado"


class EstatusPago(str, enum.Enum):
    PAGADO = "pagado"
    PENDIENTE = "pendiente"
    EN_EFECTIVO = "en_efectivo"        # Sub-flujo tradicional (Módulo 5)
    POR_CONFIRMAR = "por_confirmar"    # Cliente subió comprobante; Pao valida


class CategoriaDocumento(str, enum.Enum):
    ACTA_CONSTITUTIVA = "acta_constitutiva"
    OPINION_32D = "opinion_32d"
    ESTADO_FINANCIERO_DICTAMINADO = "estado_financiero_dictaminado"
    ACUSE_SAT = "acuse_sat"
    CONSTANCIA_SITUACION_FISCAL = "constancia_situacion_fiscal"
    # Contabilidad y nómina (mensuales)
    BALANZA_COMPROBACION = "balanza_comprobacion"      # balanza del mes
    CEDULA_ISN = "cedula_isn"                          # impuesto sobre nómina (estatal)
    PROPUESTA_SIPARE = "propuesta_sipare"              # cuotas patronales IMSS
    AVISO_INFONAVIT = "aviso_infonavit"                # aportaciones/amortizaciones
    # Ciclo patronal completo (IDSE -> SUA -> SIPARE) y nóminas
    EMISION_IDSE = "emision_idse"                      # emisión descargada del IDSE
    CALCULO_SUA = "calculo_sua"                        # cálculo/respaldo del SUA
    FORMATO_PAGO_IMSS = "formato_pago_imss"            # formato final: el que paga el cliente
    FACTURA_EMITIDA = "factura_emitida"                # factura que el despacho timbró a petición del cliente
    RECIBO_NOMINA = "recibo_nomina"                    # nóminas del periodo
    FORMATO_PAGO_ISN = "formato_pago_isn"              # formato de pago del ISN estatal
    RESPALDO_CONTPAQ = "respaldo_contpaq"              # respaldos periódicos (rotación)
    # Una declaración presentada genera DOS archivos distintos:
    ACUSE_DECLARACION = "acuse_declaracion"            # acuse + línea de captura (formato de pago)
    COMPROBANTE_DECLARACION = "comprobante_declaracion"  # la declaración en sí (con sus datos)
    COMPROBANTE_PAGO = "comprobante_pago"              # el cliente comprueba que YA pagó
    ESTADO_FINANCIERO = "estado_financiero"            # balance emitido por el despacho
    ESTADO_CUENTA_HONORARIOS = "estado_cuenta_honorarios"  # el que genera el sistema


class EstatusTicket(str, enum.Enum):
    ABIERTO = "abierto"
    EN_PROCESO = "en_proceso"
    CERRADO = "cerrado"


class EstatusCalculo(str, enum.Enum):
    BORRADOR = "borrador"
    EN_AUTORIZACION = "en_autorizacion"   # enviado a Director y Supervisora
    AUTORIZADO = "autorizado"             # cualquiera de los dos lo autorizó
    RECHAZADO = "rechazado"               # regresó con correcciones puntuales
    DECLARADO = "declarado"               # línea de captura subida y enviada


class EstatusCita(str, enum.Enum):
    SOLICITADA = "solicitada"   # el cliente la pidió; Pao debe confirmarla
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    REALIZADA = "realizada"


# ---------------------------------------------------------------------------
# TABLAS
# ---------------------------------------------------------------------------

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False)
    rol = Column(Enum(RolUsuario), nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)

    # 2FA TOTP — obligatorio para personal interno en producción.
    # El secreto se guarda CIFRADO a nivel de campo.
    totp_secret = Column(TextoCifrado, nullable=True)
    # Contraseña temporal entregada en mano: obliga a cambiarla al primer acceso
    debe_cambiar_password = Column(Boolean, default=False, nullable=False)
    totp_habilitado = Column(Boolean, default=False, nullable=False)

    # Un usuario con rol CLIENTE se vincula 1:1 a un registro de Cliente
    cliente = relationship("Cliente", back_populates="usuario_portal",
                           uselist=False, foreign_keys="Cliente.usuario_portal_id")
    tickets_asignados = relationship("TicketTramite", back_populates="contador_asignado")


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre_comercial = Column(String(150), nullable=False, index=True)
    razon_social = Column(String(200), nullable=False)
    # RFC CIFRADO en reposo; unicidad y búsqueda vía rfc_hash (HMAC).
    rfc = Column(TextoCifrado, nullable=False)
    rfc_hash = Column(String(64), unique=True, nullable=False, index=True)
    # Teléfono principal (WhatsApp y Caller ID). INDEXADO: la búsqueda por
    # número entrante debe resolverse en milisegundos para no cortar la llamada.
    telefono_whatsapp = Column(String(20), nullable=False, index=True)
    # Telefonía (asistente de voz Sofía):
    # si contesta habitualmente otra persona (familiar/administrador)
    nombre_alternativo_telefono = Column(String(120), nullable=True)
    numero_compartido = Column(Boolean, default=False, nullable=False)

    # Autoregistro del portal: código de verificación temporal (WhatsApp)
    codigo_verificacion_hash = Column(String(64), nullable=True)
    codigo_verificacion_expira = Column(DateTime, nullable=True)

    # Perfil fiscal: define QUÉ calculadora usa el contador con este cliente
    tipo_persona = Column(String(10), nullable=True)     # fisica | moral
    regimen_fiscal = Column(String(40), nullable=True)   # llaves de fiscal_v2.REGIMENES

    # COBRANZA: sin esto el módulo de cobranza no tiene de dónde tomar nada.
    # Se captura al dar de alta (formulario y alta masiva).
    honorario_mensual = Column(NumeroCifrado, nullable=True)    # cifrado en reposo
    periodicidad_honorario = Column(String(12), default="mensual")  # mensual|bimestral|anual
    dia_corte_honorario = Column(Integer, default=1)            # día del mes en que se genera
    # Bases de CONTPAQi de ESTE cliente (el agente local las lee por RFC, pero
    # aquí quedan capturadas para que el despacho sepa cuál es cuál).
    bd_contpaq_contabilidad = Column(String(80), nullable=True)
    bd_contpaq_nomina = Column(String(80), nullable=True)
    bd_contpaq_add = Column(String(80), nullable=True)          # XML timbrados
    coeficiente_utilidad = Column(Float, nullable=True)         # PM régimen general

    # Obligaciones habilitadas (definen tareas y cuándo se cobran honorarios)
    tiene_imss = Column(Boolean, default=False, nullable=False)
    tiene_nomina = Column(Boolean, default=False, nullable=False)
    periodicidad_nomina = Column(String(12), default="quincenal")  # semanal|quincenal|mensual
    email = Column(String(120), nullable=True)
    tipo_cliente = Column(Enum(TipoCliente), default=TipoCliente.ESTANDAR, nullable=False)
    estatus = Column(Enum(EstatusCliente), default=EstatusCliente.ACTIVO, nullable=False)

    # Switch manual del panel de Pao (Módulo 3, pestaña roja).
    # False => PROHIBIDO enviar recordatorios de honorarios o llamadas IA.
    automatizaciones_activas = Column(Boolean, default=True, nullable=False)

    # Acceso ampliado: por defecto el cliente ve SOLO sus documentos útiles.
    # Si pide ver todo su expediente, se enciende aquí.
    boveda_completa = Column(Boolean, default=False, nullable=False)

    # Semáforo Fiscal del Portal VIP (Módulo 7)
    opinion_32d_positiva = Column(Boolean, default=True)
    requerimiento_urgente = Column(Boolean, default=False)  # estado ROJO manual

    usuario_portal_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    usuario_portal = relationship("Usuario", back_populates="cliente",
                                  foreign_keys=[usuario_portal_id])

    # Contador(a) que lleva la contabilidad de este cliente
    contador_asignado_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    contador_asignado = relationship("Usuario", foreign_keys=[contador_asignado_id])

    obligaciones = relationship("ObligacionMensual", back_populates="cliente",
                                cascade="all, delete-orphan")
    honorarios = relationship("HonorarioCobranza", back_populates="cliente",
                              cascade="all, delete-orphan")
    documentos = relationship("DocumentoClave", back_populates="cliente",
                              cascade="all, delete-orphan")
    tickets = relationship("TicketTramite", back_populates="cliente",
                           cascade="all, delete-orphan")


class ObligacionMensual(Base):
    """Contabilidad e impuestos del mes por cliente (Módulos 2 y 4)."""
    __tablename__ = "obligaciones_mensuales"
    __table_args__ = (
        UniqueConstraint("cliente_id", "mes", "anio", name="uq_obligacion_cliente_periodo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    mes = Column(Integer, nullable=False)   # 1-12
    anio = Column(Integer, nullable=False)
    estatus_contabilidad = Column(Enum(EstatusContabilidad),
                                  default=EstatusContabilidad.PENDIENTE, nullable=False)
    monto_impuesto_sat = Column(NumeroCifrado, nullable=True)  # cifrado en reposo
    ruta_archivo_linea_captura = Column(String(300), nullable=True)
    # Los DOS archivos de una declaración: el acuse (arriba, es el formato de
    # pago que recibe el cliente) y el COMPROBANTE de la declaración en sí.
    comprobante_documento_id = Column(Integer, ForeignKey("documentos_clave.id"),
                                      nullable=True)
    numero_operacion = Column(String(40), nullable=True)  # PDF del SAT
    fecha_vencimiento_sat = Column(Date, nullable=True)  # palanca de urgencia (Módulo 6)

    # Desglose para las gráficas Chart.js del Portal VIP (Módulo 7)
    # ej. {"iva": 42000.0, "isr": 61500.0, "retenciones": 18300.0}
    desglose_impuestos = Column(JSON, nullable=True)

    # ¿YA SE PAGÓ? Antes el sistema sabía que había línea de captura, pero no
    # si el cliente la pagó. Ahora él (o el equipo) sube su comprobante.
    comprobante_pago_documento_id = Column(Integer,
                                           ForeignKey("documentos_clave.id"),
                                           nullable=True)
    pagado_en = Column(DateTime, nullable=True)
    pagado_registrado_por = Column(String(12), nullable=True)   # cliente | equipo
    referencia_pago = Column(String(60), nullable=True)         # folio del banco

    # DECLARACIONES COMPLEMENTARIAS: una obligación puede corregir a otra.
    # VERIFICACIÓN MANUAL: cuando el sistema falla (o no hay internet) el
    # contador sigue trabajando —manda la línea por WhatsApp, entrega en
    # mano— y eso NO debe verse como incumplimiento ni preocupar al cliente.
    # Un mando (Supervisor/Director/Admin) da fe de que sí se hizo, con su
    # nombre y su motivo, y los documentos se suben después.
    verificado_manualmente = Column(Boolean, default=False, nullable=False)
    verificado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    verificado_en = Column(DateTime, nullable=True)
    motivo_verificacion = Column(String(300), nullable=True)
    documentos_pendientes = Column(Boolean, default=False, nullable=False)
    verificado_por = relationship("Usuario", foreign_keys=[verificado_por_id])

    # Una obligación es ÚNICA por cliente+mes+año, así que la complementaria
    # no crea otra fila: SUSTITUYE a la vigente y archiva la anterior aquí,
    # con sus montos, su acuse y su comprobante. El expediente conserva todo.
    es_complementaria = Column(Boolean, default=False, nullable=False)
    numero_complementaria = Column(Integer, default=0, nullable=False)  # 0 = normal
    motivo_complementaria = Column(String(300), nullable=True)
    historial_complementarias = Column(JSON, default=list)

    # Métrica de eficiencia: (timestamp_enviado - timestamp_creado)
    timestamp_creado = Column(DateTime, default=datetime.utcnow, nullable=False)
    timestamp_enviado = Column(DateTime, nullable=True)

    cliente = relationship("Cliente", back_populates="obligaciones")

    @property
    def minutos_hasta_envio(self):
        """Métrica de eficiencia operativa para el Tablero del Director."""
        if self.timestamp_enviado:
            return round((self.timestamp_enviado - self.timestamp_creado).total_seconds() / 60, 1)
        return None


class HonorarioCobranza(Base):
    """Cobranza de honorarios de la firma (Módulos 3, 4, 5 y 6)."""
    __tablename__ = "honorarios_cobranza"
    __table_args__ = (
        UniqueConstraint("cliente_id", "mes", "anio", name="uq_honorario_cliente_periodo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    mes = Column(Integer, nullable=False)
    anio = Column(Integer, nullable=False)
    monto_honorario = Column(NumeroCifrado, nullable=False)  # cifrado en reposo
    estatus_pago = Column(Enum(EstatusPago), default=EstatusPago.PENDIENTE, nullable=False)
    fecha_limite_pago = Column(Date, nullable=True)

    # Bitácora cronológica de deslinde legal (Módulo 4):
    # [{"evento": "enviado", "canal": "whatsapp", "ts": "...", "detalle": "..."},
    #  {"evento": "leido", "canal": "whatsapp", "ts": "..."},
    #  {"evento": "llamada_ia", "resultado": "promesa_pago", "ts": "...", "resumen": "..."}]
    historial_notificaciones = Column(JSON, default=list)

    # Sub-flujo de efectivo (Módulo 5)
    token_confirmacion = Column(String(64), nullable=True, unique=True, index=True)
    confirmado_por_cliente_en = Column(DateTime, nullable=True)
    folio_recepcion_efectivo = Column(String(20), nullable=True, unique=True)  # ej. "PA-1024"
    referencia_oxxo = Column(String(40), nullable=True)  # código de barras / referencia
    ruta_comprobante = Column(String(300), nullable=True)  # foto de ticket subida por cliente
    estatus_recoleccion = Column(String(30), nullable=True)  # solicitada / en_ruta / recibido
    fecha_pago = Column(DateTime, nullable=True)

    cliente = relationship("Cliente", back_populates="honorarios")

    @property
    def dias_vencido(self):
        """Días de adeudo para el Semáforo de Cartera Vencida (Módulo 2)."""
        if self.estatus_pago == EstatusPago.PAGADO or not self.fecha_limite_pago:
            return 0
        return max(0, (date.today() - self.fecha_limite_pago).days)


class DocumentoClave(Base):
    """Bóveda documental del Portal VIP (Módulo 7)."""
    __tablename__ = "documentos_clave"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    categoria = Column(Enum(CategoriaDocumento), nullable=False, index=True)
    ruta_archivo = Column(String(300), nullable=False)
    anio = Column(Integer, nullable=False, index=True)
    mes = Column(Integer, nullable=True)  # para documentos mensuales (balanza, ISN, SIPARE)
    subido_en = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Cliente", back_populates="documentos")


class TicketTramite(Base):
    """Buzón de solicitudes del Portal VIP (Módulos 1 y 7)."""
    __tablename__ = "tickets_tramites"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    tipo_tramite = Column(String(120), nullable=False)
    descripcion = Column(Text, nullable=True)
    estatus = Column(Enum(EstatusTicket), default=EstatusTicket.ABIERTO, nullable=False)
    asignado_a = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    timestamp_creado = Column(DateTime, default=datetime.utcnow, nullable=False)
    timestamp_cerrado = Column(DateTime, nullable=True)

    cliente = relationship("Cliente", back_populates="tickets")
    contador_asignado = relationship("Usuario", back_populates="tickets_asignados")


class LogAuditoria(Base):
    """
    SEGURIDAD 2: Bitácora de auditoría de solo-inserción.
    Registra toda acción sensible: descargas de documentos fiscales,
    modificaciones de saldos/estatus y accesos al portal de clientes.

    Inmutabilidad: la aplicación no expone UPDATE/DELETE sobre esta tabla.
    En PostgreSQL, reforzar a nivel de motor:
        REVOKE UPDATE, DELETE ON logs_auditoria FROM app_user;
    """
    __tablename__ = "logs_auditoria"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    accion = Column(String(120), nullable=False, index=True)
    # ej. "descarga_documento", "modificacion_saldo", "acceso_portal",
    #     "confirmacion_pago", "switch_automatizaciones", "descarga_linea_captura"
    tabla_afectada = Column(String(60), nullable=False)
    registro_id = Column(Integer, nullable=True)
    detalles = Column(JSON, nullable=True)       # contexto adicional de la acción
    ip_origen = Column(String(45), nullable=True)  # soporta IPv6
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    usuario = relationship("Usuario")


class CalculoImpuesto(Base):
    """
    Determinación mensual de impuestos: el corazón del proceso del despacho.
    El contador captura los datos que extrae de la balanza de CONTPAQ; el
    sistema calcula (services/fiscal.py) y rellena las constantes (tarifa,
    cuota fija, tasas); Director o Supervisora autorizan o regresan
    correcciones puntuales por campo.
    """
    __tablename__ = "calculos_impuestos"
    __table_args__ = (
        UniqueConstraint("cliente_id", "mes", "anio", name="uq_calculo_cliente_periodo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    mes = Column(Integer, nullable=False)
    anio = Column(Integer, nullable=False)
    regimen = Column(String(40), nullable=False)  # persona_fisica | persona_moral

    # Datos capturados de la balanza (entrada del contador), montos cifrados
    datos_entrada = Column(JSON, nullable=False)
    # Resultado completo del motor (todos los renglones tipo página del SAT)
    resultado = Column(JSON, nullable=False)
    total_a_pagar = Column(NumeroCifrado, nullable=True)

    estatus = Column(Enum(EstatusCalculo), default=EstatusCalculo.BORRADOR,
                     nullable=False, index=True)
    # Correcciones puntuales: [{"campo": "iva_acreditable", "comentario": "...",
    #                           "autor": "C.P. Artemisa", "ts": "..."}]
    correcciones = Column(JSON, default=list)

    elaborado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    autorizado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    timestamp_creado = Column(DateTime, default=datetime.utcnow)
    timestamp_enviado = Column(DateTime, nullable=True)
    timestamp_autorizado = Column(DateTime, nullable=True)

    cliente = relationship("Cliente")
    elaborado_por = relationship("Usuario", foreign_keys=[elaborado_por_id])
    autorizado_por = relationship("Usuario", foreign_keys=[autorizado_por_id])


class PagoIMSS(Base):
    """
    Ciclo patronal del mes: descargar emisión del IDSE -> calcular en el SUA
    -> presentar en el SIPARE. Cada paso es visible como tarea del contador
    y monitoreable por la Supervisora/Director. El desglose de conceptos se
    captura para que Sofía pueda detallar el pago si el cliente pregunta.
    """
    __tablename__ = "pagos_imss"
    __table_args__ = (UniqueConstraint("cliente_id", "mes", "anio",
                                       name="uq_pago_imss_periodo"),)

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    mes = Column(Integer, nullable=False)
    anio = Column(Integer, nullable=False)

    # Los tres pasos del proceso (tarea por terminar del contador)
    emision_idse_hecha = Column(Boolean, default=False, nullable=False)
    calculo_sua_hecho = Column(Boolean, default=False, nullable=False)
    sipare_presentado = Column(Boolean, default=False, nullable=False)

    # Desglose por concepto (captura manual; el total se suma solo):
    # {"cuota_fija_imss": x, "riesgos_trabajo": x, "invalidez_vida": x,
    #  "guarderias": x, "retiro": x, "cesantia_vejez": x,
    #  "infonavit_aportacion": x, "infonavit_amortizacion": x, ...}
    desglose_cuotas = Column(JSON, default=dict)
    total_a_pagar = Column(NumeroCifrado, nullable=True)

    formato_pago_documento_id = Column(Integer, ForeignKey("documentos_clave.id"),
                                       nullable=True)
    notificado_cliente = Column(Boolean, default=False, nullable=False)
    responsable_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    timestamp_creado = Column(DateTime, default=datetime.utcnow)
    timestamp_presentado = Column(DateTime, nullable=True)

    cliente = relationship("Cliente")
    responsable = relationship("Usuario", foreign_keys=[responsable_id])


class PagoISN(Base):
    """Impuesto Sobre Nómina estatal del mes: presentación + aviso al cliente."""
    __tablename__ = "pagos_isn"
    __table_args__ = (UniqueConstraint("cliente_id", "mes", "anio",
                                       name="uq_pago_isn_periodo"),)

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    mes = Column(Integer, nullable=False)
    anio = Column(Integer, nullable=False)
    importe = Column(NumeroCifrado, nullable=True)
    documento_id = Column(Integer, ForeignKey("documentos_clave.id"), nullable=True)
    notificado_cliente = Column(Boolean, default=False, nullable=False)
    presentado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    timestamp_presentado = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Cliente")


class TareaNomina(Base):
    """
    Tarea recurrente de emisión de nóminas (semanal/quincenal/mensual según
    el cliente). Las genera Celery beat; el contador la termina adjuntando
    el entregable; la Supervisora ve el estatus de todas.
    """
    __tablename__ = "tareas_nomina"
    __table_args__ = (UniqueConstraint("cliente_id", "fecha_objetivo",
                                       name="uq_tarea_nomina"),)

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    fecha_objetivo = Column(Date, nullable=False, index=True)
    etiqueta = Column(String(60), nullable=False)  # "Quincena 1 · julio 2026"
    estatus = Column(String(12), default="pendiente", nullable=False)  # pendiente|terminada
    documento_id = Column(Integer, ForeignKey("documentos_clave.id"), nullable=True)
    terminada_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    timestamp_terminada = Column(DateTime, nullable=True)

    cliente = relationship("Cliente")


class SituacionCliente(Base):
    """
    EL SEMÁFORO LO PONE UNA PERSONA, NO EL SISTEMA.
    Un requerimiento, una auditoría o una aclaración no se adivinan desde la
    base de datos: las conoce el contador o el supervisor. Aquí las registra,
    y decide —con criterio— si el cliente debe verlo en su portal o si es de
    esas cosas que se hablan por teléfono (Regla del despacho: no asustar al
    cliente con un semáforo; los asuntos graves se avisan hablando).
    """
    __tablename__ = "situaciones_cliente"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    tipo = Column(String(20), nullable=False)        # requerimiento|auditoria|aclaracion|otro
    severidad = Column(String(10), nullable=False, default="ambar")   # roja|ambar|informativa
    titulo = Column(String(160), nullable=False)
    detalle_interno = Column(String(600), nullable=True)   # SOLO equipo
    mensaje_al_cliente = Column(String(400), nullable=True)  # lo que él lee
    visible_para_cliente = Column(Boolean, default=False, nullable=False)
    abierta = Column(Boolean, default=True, nullable=False)
    creada_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    cerrada_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    creada_en = Column(DateTime, default=datetime.utcnow)
    cerrada_en = Column(DateTime, nullable=True)

    cliente = relationship("Cliente")
    creada_por = relationship("Usuario", foreign_keys=[creada_por_id])
    cerrada_por = relationship("Usuario", foreign_keys=[cerrada_por_id])


class AdeudoPrevio(Base):
    """
    Lo que el cliente ya debía ANTES de entrar al sistema. Se captura en el
    alta (individual y masiva) para que la cobranza arranque con la verdad.
    """
    __tablename__ = "adeudos_previos"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    concepto = Column(String(200), nullable=False)
    monto_original = Column(NumeroCifrado, nullable=False)
    monto_pagado = Column(NumeroCifrado, default=0, nullable=False)
    fecha_origen = Column(Date, nullable=True)
    notas = Column(String(300), nullable=True)
    liquidado = Column(Boolean, default=False, nullable=False)
    registrado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Cliente")


class EstadoFinanciero(Base):
    """
    Balance emitido POR EL DESPACHO. Solo si existe se le muestra al cliente el
    resumen (activo / pasivo / capital) en su portal: nunca se inventan cifras.
    """
    __tablename__ = "estados_financieros"
    __table_args__ = (UniqueConstraint("cliente_id", "anio", "mes",
                                       name="uq_estado_financiero_periodo"),)

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    anio = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=True)          # NULL = anual
    activo_total = Column(NumeroCifrado, nullable=False)
    pasivo_total = Column(NumeroCifrado, nullable=False)
    capital_total = Column(NumeroCifrado, nullable=False)
    documento_id = Column(Integer, ForeignKey("documentos_clave.id"), nullable=True)
    visible_para_cliente = Column(Boolean, default=True, nullable=False)
    capturado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Cliente")


class SolicitudFactura(Base):
    """
    El cliente pide su factura desde el portal ("hazme una a tal RFC, de
    tanto, para gastos en general") y el equipo la atiende: la toma, la
    timbra y sube el PDF/XML a la bóveda, o la rechaza con motivo.
    """
    __tablename__ = "solicitudes_factura"

    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    receptor_rfc = Column(String(13), nullable=False)
    receptor_razon_social = Column(String(200), nullable=False)
    receptor_cp = Column(String(5), nullable=True)
    receptor_regimen = Column(String(3), nullable=True)   # clave SAT (601, 612…)
    uso_cfdi = Column(String(5), nullable=False, default="G03")
    forma_pago = Column(String(2), nullable=False, default="03")
    metodo_pago = Column(String(3), nullable=False, default="PUE")
    concepto = Column(String(400), nullable=False)
    monto = Column(Float, nullable=True)                  # None = por definir
    notas = Column(String(400), nullable=True)
    estatus = Column(String(15), nullable=False, default="solicitada")
    motivo_rechazo = Column(String(300), nullable=True)
    atendida_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    factura_documento_id = Column(Integer, ForeignKey("documentos_clave.id"),
                                  nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Cliente")
    atendida_por = relationship("Usuario", foreign_keys=[atendida_por_id])


class SnapshotContpaq(Base):
    """
    Datos que el AGENTE LOCAL extrae de CONTPAQi (solo lectura) y empuja por
    HTTPS. Un registro por cliente + tipo + periodo; el nuevo pisa al viejo.
    tipos: 'resultados' (ingresos/costos/gastos por mes, para el tablero del
    cliente), 'nomina' (plantilla + carga social proyectada) y 'prediccion'
    (historial + proyección híbrida de ISR/IVA del mes en curso).
    """
    __tablename__ = "snapshots_contpaq"
    __table_args__ = (UniqueConstraint("cliente_id", "tipo", "anio", "mes",
                                       name="uq_snapshot_periodo"),)

    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    tipo = Column(String(20), nullable=False)
    anio = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)          # 0 = todo el ejercicio
    datos = Column(JSON, nullable=False)
    origen = Column(String(120), nullable=True)    # BD/equipo que lo generó
    recibido_en = Column(DateTime, default=datetime.utcnow,
                         onupdate=datetime.utcnow)

    cliente = relationship("Cliente")


class SaldoFavor(Base):
    """
    INVENTARIO DE SALDOS A FAVOR.
    Cada declaración que arroja saldo a favor crea un registro con su MONTO
    ORIGINAL. Cuando en una declaración posterior se aplica (compensa) una
    parte, se registra una Aplicacion y el REMANENTE baja. Así siempre se
    sabe: cuánto se generó, cuánto se ha aplicado, cuánto queda, y en qué
    declaración se originó (con su número de operación y su comprobante,
    que quedan a la mano para cuando el SAT los pida).
    """
    __tablename__ = "saldos_favor"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    impuesto = Column(String(20), nullable=False)   # isr | iva | ieps | otro
    # Periodo que lo originó
    mes = Column(Integer, nullable=True)            # NULL si es anual
    anio = Column(Integer, nullable=False)
    es_anual = Column(Boolean, default=False, nullable=False)

    monto_original = Column(NumeroCifrado, nullable=False)
    monto_aplicado = Column(NumeroCifrado, default=0, nullable=False)
    # remanente = original - aplicado (propiedad calculada, nunca desincronizado)

    # Datos de la declaración que lo originó (los que pide el SAT al aplicarlo)
    numero_operacion = Column(String(40), nullable=True)
    fecha_presentacion = Column(Date, nullable=True)
    comprobante_documento_id = Column(Integer, ForeignKey("documentos_clave.id"),
                                      nullable=True)
    calculo_id = Column(Integer, ForeignKey("calculos_impuestos.id"), nullable=True)

    estatus = Column(String(15), default="disponible", nullable=False)
    # disponible | agotado | en_devolucion | devuelto | prescrito
    notas = Column(Text, nullable=True)
    registrado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    timestamp_creado = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Cliente")
    aplicaciones = relationship("AplicacionSaldoFavor", back_populates="saldo",
                                cascade="all, delete-orphan")

    @property
    def remanente(self) -> float:
        return round((self.monto_original or 0) - (self.monto_aplicado or 0), 2)

    @property
    def periodo(self) -> str:
        if self.es_anual:
            return f"Anual {self.anio}"
        return f"{self.mes:02d}/{self.anio}" if self.mes else str(self.anio)

    # Los saldos a favor prescriben a los 5 años (Art. 22 CFF)
    ANIOS_PRESCRIPCION = 5


class AplicacionSaldoFavor(Base):
    """
    Cada vez que un saldo a favor se aplica (compensa) contra un impuesto en
    una declaración posterior. Deja el rastro completo: cuánto se aplicó, en
    qué declaración y contra qué impuesto.
    """
    __tablename__ = "aplicaciones_saldo_favor"

    id = Column(Integer, primary_key=True, index=True)
    saldo_favor_id = Column(Integer, ForeignKey("saldos_favor.id"), nullable=False,
                            index=True)
    monto_aplicado = Column(NumeroCifrado, nullable=False)
    # Declaración donde se aplicó
    mes_aplicacion = Column(Integer, nullable=True)
    anio_aplicacion = Column(Integer, nullable=False)
    impuesto_destino = Column(String(20), nullable=False)
    numero_operacion_destino = Column(String(40), nullable=True)
    calculo_id = Column(Integer, ForeignKey("calculos_impuestos.id"), nullable=True)
    aplicado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    saldo = relationship("SaldoFavor", back_populates="aplicaciones")


class CertificadoDigital(Base):
    """
    Bóveda blindada de firmas y sellos: e.firma (FIEL), CSD, certificados
    estatales y del IMSS. MUY delicados: cifrados en reposo, descarga del
    personal SOLO con código TOTP vigente (paso extra de seguridad), descarga
    del cliente reconfirmando su contraseña; todo auditado. El sistema vigila
    vencimientos y pide renovaciones; renovado, todos saben dónde está.
    """
    __tablename__ = "certificados_digitales"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True,
                        index=True)  # NULL = certificado del propio despacho
    tipo = Column(String(30), nullable=False)  # efirma|csd|sello_imss|certificado_estatal|otro
    descripcion = Column(String(200), nullable=False)
    ruta_archivo = Column(String(300), nullable=False)  # cifrado en reposo
    fecha_vencimiento = Column(Date, nullable=False, index=True)
    en_renovacion = Column(Boolean, default=False, nullable=False)
    reemplazado_por_id = Column(Integer, ForeignKey("certificados_digitales.id"),
                                nullable=True)
    subido_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    subido_en = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Cliente")

    DIAS_ALERTA = 30

    @property
    def estatus(self) -> str:
        from datetime import date as _d
        if self.reemplazado_por_id:
            return "reemplazado"
        hoy = _d.today()
        if self.fecha_vencimiento < hoy:
            return "vencido"
        if (self.fecha_vencimiento - hoy).days <= self.DIAS_ALERTA:
            return "por_vencer"
        return "vigente"


class Cita(Base):
    """
    Agenda de asesorías. El cliente la SOLICITA desde su portal (o Pao la crea
    directo por teléfono); Pao la CONFIRMA; la persona con quien es la cita
    recibe aviso por correo y la ve en su panel; el cliente recibe la
    confirmación por WhatsApp vía Regina.
    """
    __tablename__ = "citas"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    con_usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    fecha_hora = Column(DateTime, nullable=False, index=True)
    duracion_minutos = Column(Integer, default=60)
    modalidad = Column(String(20), default="presencial")  # presencial | videollamada | llamada
    motivo = Column(Text, nullable=True)
    estatus = Column(Enum(EstatusCita), default=EstatusCita.SOLICITADA, nullable=False)
    creada_por_usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    notas_internas = Column(Text, nullable=True)  # tarjetita para Pao
    timestamp_creado = Column(DateTime, default=datetime.utcnow)

    cliente = relationship("Cliente")
    con_usuario = relationship("Usuario", foreign_keys=[con_usuario_id])


# ---------------------------------------------------------------------------
# EVENTOS: mantener rfc_hash sincronizado automáticamente
# ---------------------------------------------------------------------------

@event.listens_for(Cliente, "before_insert")
@event.listens_for(Cliente, "before_update")
def _sincronizar_rfc_hash(mapper, connection, target):
    if target.rfc:
        target.rfc_hash = hash_busqueda(target.rfc)
