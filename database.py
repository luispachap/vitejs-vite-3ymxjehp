# -*- coding: utf-8 -*-
"""Conexión a base de datos: SQLite para desarrollo local, PostgreSQL en producción."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Desarrollo local: SQLite (archivo pa_despacho.db en la raíz del proyecto).
# Producción: exportar DATABASE_URL, ej.:
#   postgresql+psycopg2://usuario:password@localhost:5432/pa_despacho
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pa_despacho.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependencia de FastAPI: una sesión por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
