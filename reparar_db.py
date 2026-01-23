from database import engine
from sqlalchemy import text

# Conectamos a la base de datos
with engine.connect() as connection:
    try:
        print("Eliminando tabla vieja 'reglas_estilo'...")
        # Borramos la tabla conflictiva
        connection.execute(text("DROP TABLE IF EXISTS reglas_estilo CASCADE;"))
        # Borramos también la de auditorías por si acaso quedó con formato viejo
        connection.execute(text("DROP TABLE IF EXISTS auditorias CASCADE;"))
        connection.commit()
        print("✅ Tablas eliminadas con éxito.")
        print("Reinicie main.py y se crearán automáticamente con las columnas nuevas.")
    except Exception as e:
        print(f"Error: {e}")