# -*- coding: utf-8 -*-
"""
Datos semilla para desarrollo local.  Ejecutar UNA vez:  python seed.py
Crea usuarios de cada rol y 3 clientes representativos (uno de cada tipo).
"""
import os
import sys
from datetime import date, timedelta

# SEGURIDAD 5: CANDADO DE PRODUCCIÓN.
# Este script inyecta datos de prueba y solo tiene sentido en desarrollo.
# Si ENVIRONMENT=production, aborta de inmediato para impedir cualquier
# contaminación o pérdida accidental de datos reales.
if os.getenv("ENVIRONMENT", "development") == "production":
    print("ABORTADO: seed.py está bloqueado en producción. "
          "Este script solo puede ejecutarse en entornos de desarrollo.")
    sys.exit(1)

from database import Base, SessionLocal, engine
from models.models import (Cliente, EstatusPago, HonorarioCobranza,
                           ObligacionMensual, RolUsuario, TipoCliente, Usuario)
from services.auth import hash_password

Base.metadata.create_all(bind=engine)
db = SessionLocal()

if db.query(Usuario).count() > 0:
    print("La base ya tiene datos; no se duplicó el seed.")
    raise SystemExit

# --- Usuarios internos ---
# Papá es el DIRECTOR (dueño del despacho); Luis es el ADMINISTRADOR del
# sistema (acceso técnico total: ve y mueve todo).
administrador = Usuario(nombre="Luis", rol=RolUsuario.ADMINISTRADOR,
                        email="admin@pya.mx", password_hash=hash_password("cambiar123"))
director = Usuario(nombre="C.P. Rodolfo Pacheco", rol=RolUsuario.DIRECTOR,
                   email="luis@pya.mx", password_hash=hash_password("cambiar123"))
pao = Usuario(nombre="Pao", rol=RolUsuario.ADMIN_SECRETARIA,
              email="pao@pya.mx", password_hash=hash_password("cambiar123"))
contador = Usuario(nombre="Carlos Contador", rol=RolUsuario.CONTADOR,
                   email="carlos@pya.mx", password_hash=hash_password("cambiar123"))
artemisa = Usuario(nombre="C.P. Artemisa", rol=RolUsuario.SUPERVISOR,
                   email="artemisa@pya.mx", password_hash=hash_password("cambiar123"))

# --- Cliente VIP con acceso al portal ---
u_cliente = Usuario(nombre="Grupo Norte SA", rol=RolUsuario.CLIENTE,
                    email="cliente@gruponorte.mx",
                    password_hash=hash_password("cambiar123"))
db.add_all([administrador, director, pao, contador, artemisa, u_cliente])
db.flush()

hoy = date.today()
clientes = [
    Cliente(nombre_comercial="Grupo Norte", razon_social="Grupo Norte SA de CV",
            rfc="GNO120101AB1", telefono_whatsapp="+528111111111",
            tipo_cliente=TipoCliente.VIP, usuario_portal_id=u_cliente.id,
            contador_asignado_id=artemisa.id,
            tiene_imss=True, tiene_nomina=True, periodicidad_nomina="quincenal",
            tipo_persona="moral", regimen_fiscal="pm_general"),
    Cliente(nombre_comercial="Ferretería Don Juan", razon_social="Juan Pérez",
            rfc="PEJJ800101XX2", telefono_whatsapp="+528122222222",
            tipo_cliente=TipoCliente.ESTANDAR),
    Cliente(nombre_comercial="Compadre Ramírez", razon_social="Ramírez Hnos SA",
            rfc="RHE900101YY3", telefono_whatsapp="+528133333333",
            tipo_cliente=TipoCliente.CONFIANZA_ESPECIAL),  # cobranza 100% humana
]
db.add_all(clientes)
db.flush()

for i, c in enumerate(clientes):
    db.add(ObligacionMensual(cliente_id=c.id, mes=hoy.month, anio=hoy.year,
                             desglose_impuestos={"iva": 42000, "isr": 61500,
                                                 "retenciones": 18300}))
    db.add(HonorarioCobranza(
        cliente_id=c.id, mes=hoy.month, anio=hoy.year,
        monto_honorario=[250000, 120000, 180000][i],
        estatus_pago=EstatusPago.PENDIENTE,
        fecha_limite_pago=hoy - timedelta(days=[5, 70, 95][i]),  # para probar el semáforo
    ))

db.commit()
print("Seed listo ✓")
print("  Administrador (Luis): admin@pya.mx / cambiar123")
print("  Director:  luis@pya.mx / cambiar123")
print("  Secretaria: pao@pya.mx / cambiar123")
print("  Contador:  carlos@pya.mx / cambiar123")
print("  Portal VIP: cliente@gruponorte.mx / cambiar123")
