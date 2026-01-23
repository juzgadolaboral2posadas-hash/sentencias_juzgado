import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

print("--- 📡 PROBANDO CONEXIÓN A GEMINI ---")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY no está definida en el entorno")

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-2.0-flash-lite",
    contents="Responde solo con la palabra: VIVO"
)

print(f"✅ RESPUESTA IA: {response.text}")

except Exception as e:
print(f"\n💀 ERROR CRÍTICO:\n{e}")