import os

# Obtiene la carpeta donde estamos parados
carpeta_actual = os.getcwd()

print(f"--- RASTREANDO ARCHIVOS DE BASE DE DATOS (.db) ---")
print(f"Buscando en: {carpeta_actual} y subcarpetas...")

encontrado = False
for root, dirs, files in os.walk(carpeta_actual):
    for file in files:
        if file.endswith(".db"):
            ruta_completa = os.path.join(root, file)
            print(f"\n✅ ¡EUREKA! ENCONTRADO:")
            print(f"   Nombre: {file}")
            print(f"   Ubicación: {ruta_completa}")
            encontrado = True

if not encontrado:
    print("\n❌ No se encontraron archivos .db. Algo raro pasa.")
