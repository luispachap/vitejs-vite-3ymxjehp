# -*- coding: utf-8 -*-
"""
INSTALACIÓN VISUAL DEL PRIMER DIRECTOR — /instalar
==================================================
El plan gratuito de Render no incluye Shell, así que el primer usuario se
crea desde esta pantalla (100% con clics, cero comandos).

DOBLE CANDADO DE SEGURIDAD:
1. Solo funciona mientras NO exista ningún usuario DIRECTOR. En cuanto se
   crea el primero, esta pantalla queda inutilizada PARA SIEMPRE (410).
2. Exige la "llave de instalación", que es la SECRET_KEY del sistema: solo
   quien configuró las variables en Render la conoce.

Sin JavaScript: formulario HTML puro (compatible con la CSP estricta).
Todo intento, exitoso o no, queda en la bitácora de auditoría.
"""
import hmac

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

import config
from database import get_db
from models.models import RolUsuario, Usuario
from services import auditoria
from services.auth import hash_password

router = APIRouter(tags=["Instalación"])

_ESTILO = """
<style>
  body{font-family:'Public Sans',system-ui,sans-serif;background:#F4F6F9;
       margin:0;display:grid;place-items:center;min-height:100vh;padding:20px;box-sizing:border-box}
  .caja{background:#fff;border:1px solid #E3E8EF;border-radius:16px;max-width:430px;
        width:100%;padding:34px 30px;box-shadow:0 10px 30px rgba(11,36,64,.08)}
  h1{font-size:21px;color:#0B2440;margin:0 0 6px}
  p{font-size:13.5px;color:#5B6472;line-height:1.6;margin:0 0 18px}
  label{display:block;font-size:12px;font-weight:700;color:#0B2440;margin:12px 0 4px}
  input{width:100%;box-sizing:border-box;border:1.5px solid #D7DEE8;border-radius:9px;
        padding:11px 12px;font-size:14px}
  input:focus{outline:none;border-color:#0A5AA0}
  button{width:100%;margin-top:20px;background:#0A5AA0;color:#fff;border:none;
         border-radius:10px;padding:13px;font-size:14.5px;font-weight:700;cursor:pointer}
  button:hover{background:#084a85}
  .error{background:#FDF1EF;border:1px solid #F2CFC8;color:#8C2F21;border-radius:9px;
         padding:11px 13px;font-size:13px;margin-bottom:6px}
  .ok{background:#F0F7F2;border:1px solid #BFDCC9;color:#14532D;border-radius:9px;
      padding:13px 15px;font-size:13.5px;line-height:1.65}
  a{color:#0A5AA0;font-weight:700}
  .pie{font-size:11px;color:#98A2B3;margin-top:16px;line-height:1.5}
</style>"""


def _pagina(cuerpo: str) -> str:
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Instalación · Pacheco &amp; Aparicio</title>{_ESTILO}</head>
<body><div class="caja">{cuerpo}</div></body></html>"""


def _hay_director(db: Session) -> bool:
    return (db.query(Usuario)
            .filter(Usuario.rol == RolUsuario.DIRECTOR).first() is not None)


_FORMULARIO = """
<h1>Instalación inicial</h1>
<p>Cree la cuenta del <strong>Director</strong> del despacho. Esta pantalla
se desactiva sola y para siempre en cuanto exista el primer Director.</p>
{aviso}
<form method="post" action="/instalar">
  <label for="nombre">Nombre completo</label>
  <input id="nombre" name="nombre" required maxlength="120" placeholder="C.P. Rodolfo Pacheco Ortega">
  <label for="email">Correo</label>
  <input id="email" name="email" type="email" required maxlength="120">
  <label for="password">Contraseña (mínimo 10 caracteres)</label>
  <input id="password" name="password" type="password" required minlength="10">
  <label for="confirmar">Confirme la contraseña</label>
  <input id="confirmar" name="confirmar" type="password" required minlength="10">
  <label for="llave">Llave de instalación (su SECRET_KEY de Render)</label>
  <input id="llave" name="llave" type="password" required>
  <button type="submit">Crear Director e instalar</button>
</form>
<p class="pie">Doble candado: requiere la SECRET_KEY que solo usted pegó en
Render, y deja de existir al crearse el Director. Todo intento queda en la
bitácora de auditoría.</p>"""

_YA_INSTALADO = """
<h1>Sistema ya instalado</h1>
<div class="ok">El Director ya fue creado, así que esta pantalla quedó
desactivada de forma permanente.<br><br>
Entre por el <a href="/equipo">portal del equipo</a> y, si es su primera
vez, use ahí mismo la opción <strong>"configurar mi código 2FA"</strong>.</div>"""


@router.get("/instalar", response_class=HTMLResponse, include_in_schema=False)
def pantalla_instalacion(db: Session = Depends(get_db)):
    if _hay_director(db):
        return _pagina(_YA_INSTALADO)
    return _pagina(_FORMULARIO.format(aviso=""))


@router.post("/instalar", response_class=HTMLResponse, include_in_schema=False)
def instalar(request: Request,
             nombre: str = Form(...), email: str = Form(...),
             password: str = Form(...), confirmar: str = Form(...),
             llave: str = Form(...),
             db: Session = Depends(get_db)):
    # Candado 1: una sola vez en la vida del sistema
    if _hay_director(db):
        return HTMLResponse(_pagina(_YA_INSTALADO), status_code=410)

    # Candado 2: la llave de instalación es la SECRET_KEY del despliegue
    if not config.SECRET_KEY or not hmac.compare_digest(llave.strip(),
                                                        config.SECRET_KEY):
        auditoria.registrar(db, usuario_id=None, accion="instalacion_denegada",
                            tabla_afectada="usuarios", registro_id=None,
                            request=request, motivo="llave_invalida")
        db.commit()
        return HTMLResponse(_pagina(_FORMULARIO.format(
            aviso='<div class="error">Llave de instalación incorrecta. Es la '
                  'SECRET_KEY exacta que pegó en las variables de Render.</div>')),
            status_code=403)

    if password != confirmar:
        return HTMLResponse(_pagina(_FORMULARIO.format(
            aviso='<div class="error">Las contraseñas no coinciden.</div>')),
            status_code=400)
    if len(password) < 10:
        return HTMLResponse(_pagina(_FORMULARIO.format(
            aviso='<div class="error">La contraseña debe tener al menos 10 caracteres.</div>')),
            status_code=400)

    director = Usuario(nombre=nombre.strip()[:120], email=email.strip().lower(),
                       rol=RolUsuario.DIRECTOR,
                       password_hash=hash_password(password))
    db.add(director)
    db.flush()
    auditoria.registrar(db, usuario_id=director.id, accion="instalacion_director",
                        tabla_afectada="usuarios", registro_id=director.id,
                        request=request)
    db.commit()

    return _pagina(f"""
<h1>Director creado</h1>
<div class="ok">Bienvenido, <strong>{director.nombre}</strong>. El sistema
quedó instalado y esta pantalla acaba de desactivarse para siempre.<br><br>
Siguientes pasos:<br>
1. Entre al <a href="/equipo">portal del equipo</a>.<br>
2. Toque <strong>"configurar mi código 2FA"</strong>, escanee el QR con
Google Authenticator y actívelo (obligatorio).<br>
3. Ya adentro, en la pestaña <strong>Administración</strong>, dé de alta a
la Supervisora, a Pao, a los contadores y a sus clientes, todo con clics.</div>""")
