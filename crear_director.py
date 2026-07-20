# -*- coding: utf-8 -*-
"""
Crea el PRIMER usuario Director en producción (seed.py está bloqueado ahí).
Uso (una sola vez, desde la consola del servidor):
    python crear_director.py "Luis" luis@pacheco-aparicio.com
La contraseña se pide en pantalla sin mostrarse y se guarda hasheada.
"""
import getpass
import sys

from database import Base, SessionLocal, engine
from models.models import RolUsuario, Usuario
from services.auth import hash_password

if len(sys.argv) != 3:
    print('Uso: python crear_director.py "Nombre" correo@dominio.com')
    sys.exit(1)

nombre, email = sys.argv[1], sys.argv[2]
Base.metadata.create_all(bind=engine)
db = SessionLocal()

if db.query(Usuario).filter(Usuario.email == email).first():
    print("Ya existe un usuario con ese correo."); sys.exit(1)

pw = getpass.getpass("Contraseña para el Director: ")
if len(pw) < 10:
    print("Mínimo 10 caracteres."); sys.exit(1)
if pw != getpass.getpass("Confirme la contraseña: "):
    print("No coinciden."); sys.exit(1)

db.add(Usuario(nombre=nombre, email=email, rol=RolUsuario.DIRECTOR,
               password_hash=hash_password(pw)))
db.commit()
print(f"Director '{nombre}' creado. Siguiente paso obligatorio: enrolar su 2FA")
print("en POST /api/auth/2fa/enrolar antes del primer login en producción.")
