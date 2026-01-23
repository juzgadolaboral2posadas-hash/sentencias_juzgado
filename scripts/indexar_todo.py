import sys
import os
import time
from dotenv import load_dotenv

# 1. Configuración de Rutas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import SessionLocal
import models
from agentes import bibliotecario
from google import genai

# 2. IMPORTACIÓN DE CLAVE
try:
    load_dotenv()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("La variable GEMINI_API_KEY está vacía en main.py")
    print(f"🔑 Clave API importada correctamente.")
except ImportError:
    print("❌ ERROR CRÍTICO: No se pudo importar 'main.py'.")
    sys.exit(1)
except Exception as e:
    print(f"❌ ERROR DE CLAVE: {e}")
    sys.exit(1)

# Inicializamos el cliente
client_ai = genai.Client(api_key=GEMINI_API_KEY)

def indexar_lote(tamano_lote=50):
    db = SessionLocal()
    
    # Buscamos sentencias con texto pero sin índice
    pendientes = db.query(models.Sentencia).filter(
        models.Sentencia.texto_completo != "Pendiente de procesamiento"
    ).outerjoin(models.IndiceSentencia).filter(
        models.IndiceSentencia.id == None
    ).limit(tamano_lote).all()

    total = len(pendientes)
    print(f"\n--- 🏭 INICIANDO PROCESAMIENTO ({total} documentos) ---")
    
    if total == 0:
        print("🎉 ¡Todo al día!")
        return False

    for i, sent in enumerate(pendientes):
        intentos = 0
        max_intentos = 3
        procesado = False

        while intentos < max_intentos and not procesado:
            try:
                print(f"[{i+1}/{total}] ID {sent.id} (Intento {intentos+1})...", end=" ", flush=True)
                
                exito = bibliotecario.procesar_un_expediente(client_ai, db, sent.id, sent.texto_completo)
                
                if exito:
                    print("✅ OK")
                    procesado = True
                    
                    # --- PAUSA TÁCTICA AUMENTADA ---
                    # 30 segundos para vaciar el contador de Tokens de Google
                    time.sleep(30) 
                else:
                    print("⚠️ Falló (sin excepción)")
                    break

            except Exception as e:
                error_str = str(e)
                # Si es error de saturación (429), castigo mayor
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    print(f"\n⏳ SATURACIÓN (429). Enfriando motores por 120 segundos...")
                    time.sleep(120) 
                    intentos += 1
                else:
                    print(f"\n❌ Error técnico en ID {sent.id}: {error_str}")
                    break 
        
        if not procesado:
            print(f"💀 Se omitió el ID {sent.id}.")

    db.close()
    return True

if __name__ == "__main__":
    print("🤖 Iniciando Indexador en MODO SEGURO (30s espera)...")
    try:
        while True:
            hay_mas = indexar_lote(50)
            if not hay_mas:
                break
            print("💤 Descanso largo de 10s entre lotes...")
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n🛑 Detenido por usuario.")