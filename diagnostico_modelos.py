import os
from google import genai
from dotenv import load_dotenv

# Cargar entorno
load_dotenv()

def diagnosticar_v2():
    print("--- INICIANDO DIAGNÓSTICO DE MODELOS V2 ---")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ ERROR: Falta la API Key.")
        return

    try:
        client = genai.Client(api_key=api_key)
        print("📡 Conectado. Obteniendo lista...")
        
        pager = client.models.list()
        
        encontrado_004 = False
        
        print("\n--- LISTADO DE MODELOS DISPONIBLES ---")
        for model in pager:
            # 1. Obtener nombre seguro
            # Intentamos acceder al nombre, o imprimimos el objeto crudo si falla
            nombre = getattr(model, 'name', 'SIN NOMBRE')
            
            # 2. Filtrar solo los que nos interesan para no llenar la pantalla
            # Buscamos 'embed' (vectores) o 'flash' (chat)
            if 'embed' in nombre or 'flash' in nombre:
                print(f"🔹 Modelo detectado: {nombre}")
                
                # 3. Verificamos si es el que buscamos
                if "text-embedding-004" in nombre:
                    encontrado_004 = True
                    print(f"   ✅ ¡ESTE ES! ID Exacto para copiar: '{nombre}'")
                    
                    # Introspección: Veamos qué metadatos tiene realmente
                    print(f"   🔎 Datos internos: {dir(model)}")

    
        print("\n---------------------------------------")
        if encontrado_004:
            print("✅ CONCLUSIÓN: El modelo EXISTE en tu cuenta.")
            print("   Acción: Copia el ID exacto que apareció arriba (con o sin 'models/').")
        else:
            print("❌ CONCLUSIÓN GRAVE: El modelo 004 NO aparece en tu lista.")
            print("   Posibles causas: API Key restringida o Región no soportada.")

    except Exception as e:
        print(f"\n❌ Error fatal: {e}")

if __name__ == "__main__":
    diagnosticar_v2()