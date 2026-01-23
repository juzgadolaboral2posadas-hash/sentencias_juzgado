from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
# Tus credenciales exactas
load_dotenv()
URL_DB = os.getenv("DATABASE_URL")

# Motor de conexión
engine = create_engine(URL_DB)

# Fábrica de sesiones
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- FUNCIÓN GET_DB (LA QUE FALTABA) ---
# Esta función es vital: crea una sesión para cada petición y la cierra al terminar.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()