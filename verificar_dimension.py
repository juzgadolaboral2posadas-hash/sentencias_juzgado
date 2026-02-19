import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

def probar_dimension():
    print("--- PRUEBA DE DIMENSIONES DEL NUEVO MODELO ---")
    
    # 1. Configurar
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    # 2. El único modelo de embedding que tienes disponible
    modelo_candidato = "models/gemini-embedding-001"
    
    print(f"🧪 Probando modelo: {modelo_candidato}")
    
    try:
        # 3. Generar un vector de prueba
        respuesta = client.models.embed_content(
            model=modelo_candidato,
            contents="Prueba de concepto judicial."
        )
        
        # 4. Medir el tamaño
        vector = respuesta.embeddings[0].values
        tamano = len(vector)
        
        print(f"\n📏 TAMAÑO DEL VECTOR: {tamano} dimensiones")
        
        if tamano == 768:
            print("✅ COMPATIBLE: Puedes usar este modelo con tu base de datos actual.")
        else:
            print("❌ INCOMPATIBLE: Tu base de datos espera 768.")

    except Exception as e:
        print(f"❌ Error al probar: {e}")

if __name__ == "__main__":
    probar_dimension()