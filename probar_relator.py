import requests
import json

# --- SU PREGUNTA JURÍDICA AQUÍ ---
pregunta = "criterio sobre despido por embarazo"
# ---------------------------------

url = "http://127.0.0.1:8000/consultar-jurisprudencia/"
datos = {"pregunta": pregunta}

print(f"⚖️  Preguntando al Relator sobre: '{pregunta}'...")

try:
    respuesta = requests.post(url, json=datos)
    
    if respuesta.status_code == 200:
        info = respuesta.json()
        print("\n" + "="*60)
        print("🤖 RESPUESTA DEL RELATOR:")
        print("="*60)
        print(info["respuesta"])
        print("\n" + "-"*60)
        print(f"📂 Expedientes consultados: {info.get('casos_usados', [])}")
        print("="*60 + "\n")
    else:
        print("❌ Error:", respuesta.text)
except Exception as e:
    print("❌ Error de conexión:", e)
