# forzar_tablas.py
from database import engine
import models

print("--- INICIANDO REPARACIÓN DE TABLAS ---")

# 1. Aseguramos que SQLAlchemy "vea" las clases
print(f"Modelos detectados: {models.Base.metadata.tables.keys()}")

# 2. Ordenamos crear todo lo que no exista
try:
    models.Base.metadata.create_all(bind=engine)
    print("✅ ÉXITO: Las tablas 'reglas_estilo' y 'auditorias' han sido creadas.")
except Exception as e:
    print(f"❌ ERROR: {e}")

print("--- FIN ---")