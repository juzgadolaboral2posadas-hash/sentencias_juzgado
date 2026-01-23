import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import SessionLocal
import models
from sqlalchemy import text

def borrar_indices_sin_vector():
    db = SessionLocal()
    print("🧹 Buscando índices obsoletos (sin vector)...")
    
    # SQL directo para borrar filas donde el vector sea nulo
    # Nota: Dependiendo de pgvector, a veces es NULL o vacío.
    try:
        sql = text("DELETE FROM indices_sentencia WHERE vector_embedding IS NULL;")
        result = db.execute(sql)
        db.commit()
        print(f"✅ Se eliminaron {result.rowcount} índices viejos/incompletos.")
        print("👉 Ahora el script 'indexar_todo.py' los volverá a procesar automáticamente en su próxima vuelta.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    borrar_indices_sin_vector()