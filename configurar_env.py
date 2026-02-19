import json
import os

# Archivos de entrada y salida
ARCHIVO_JSON = 'credenciales.json'
ARCHIVO_ENV = '.env'

def generar_env_seguro():
    print(f"🔧 Iniciando configuración automática de {ARCHIVO_ENV}...")

    # 1. Verificar que existe el JSON fuente
    if not os.path.exists(ARCHIVO_JSON):
        print(f"❌ ERROR: No encuentro el archivo '{ARCHIVO_JSON}'.")
        print("   Por favor, copia el archivo de credenciales a esta carpeta temporalmente.")
        return

    # 2. Leer el JSON y convertirlo a una sola línea válida
    try:
        with open(ARCHIVO_JSON, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        
        # json.dumps se encarga de escapar todo correctamente (comillas, newlines, etc.)
        json_una_linea = json.dumps(datos)
        
    except Exception as e:
        print(f"❌ ERROR: El archivo '{ARCHIVO_JSON}' no es un JSON válido o está corrupto.")
        print(f"   Detalle: {e}")
        return

    # 3. Leer el .env actual (para no borrar otras variables)
    lineas_existentes = []
    if os.path.exists(ARCHIVO_ENV):
        with open(ARCHIVO_ENV, 'r', encoding='utf-8') as f:
            lineas_existentes = f.readlines()

    # 4. Escribir el nuevo .env
    with open(ARCHIVO_ENV, 'w', encoding='utf-8') as f:
        # Escribimos todas las líneas que NO sean la de credenciales
        for linea in lineas_existentes:
            if not linea.strip().startswith("GOOGLE_CREDENTIALS_JSON"):
                f.write(linea)
        
        # Aseguramos que haya un salto de línea antes de agregar la nueva variable
        if lineas_existentes and not lineas_existentes[-1].endswith('\n'):
            f.write('\n')

        # Agregamos la variable formateada con comillas simples
        # Usamos raw string (f-string) para evitar problemas de escape adicionales
        f.write(f"GOOGLE_CREDENTIALS_JSON='{json_una_linea}'\n")

    print(f"✅ ¡ÉXITO! Se ha actualizado {ARCHIVO_ENV} con el formato correcto.")
    print("----------------------------------------------------------------")
    print(f"⚠️ IMPORTANTE (SEGURIDAD):")
    print(f"   Ahora debes BORRAR o MOVER el archivo '{ARCHIVO_JSON}' fuera de esta carpeta.")
    print("   El sistema ya no lo necesita, ahora lee desde el .env.")

if __name__ == "__main__":
    generar_env_seguro()