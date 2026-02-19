import os
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from dotenv import load_dotenv  # <--- NUEVO: Importar librería de entorno

# --- CARGA DE ENTORNO ---
# Esto busca un archivo .env local y carga sus variables.
# Si el archivo no existe (ej: en Producción/Railway), no hace nada y sigue.
load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """
    Autentica y retorna el servicio de Google Drive API.
    Lee la configuración desde la variable de entorno 'GOOGLE_CREDENTIALS_JSON'.
    """
    
    # 1. Obtener el string del JSON desde las variables de entorno
    creds_json_str = os.getenv("GOOGLE_CREDENTIALS_JSON")
    
    if not creds_json_str:
        # Debug: Ayuda visual para entender por qué falla
        print(f"⚠️ DEBUG: Variables disponibles: {list(os.environ.keys())}")
        raise ValueError(
            "❌ ERROR DE SEGURIDAD: La variable 'GOOGLE_CREDENTIALS_JSON' está vacía o no existe.\n"
            "   -> En Local: Asegurate de tener python-dotenv instalado y el archivo .env creado.\n"
            "   -> En Prod: Configura la variable en el dashboard de Railway."
        )

    try:
        # 2. Convertir string a JSON
        # Limpieza básica por si el copy-paste incluyó comillas extra al inicio/final
        creds_json_str = creds_json_str.strip()
        if creds_json_str.startswith("'") and creds_json_str.endswith("'"):
             creds_json_str = creds_json_str[1:-1]
        
        creds_info = json.loads(creds_json_str)
        
        creds = service_account.Credentials.from_service_account_info(
            creds_info, 
            scopes=SCOPES
        )
        return build('drive', 'v3', credentials=creds)
        
    except json.JSONDecodeError as e:
        print(f"❌ ERROR DE FORMATO JSON: {e}")
        print(f"   Inicio del contenido recibido: {creds_json_str[:50]}...")
        raise ValueError("La variable GOOGLE_CREDENTIALS_JSON no contiene un JSON válido.")
    except Exception as e:
        raise ConnectionError(f"ERROR: Falló la conexión con Drive: {str(e)}")

def descargar_archivo_a_memoria(service, file_id, file_name="archivo"):
    """Descarga archivo a memoria (Fileless)."""
    if not file_id:
        return None

    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        return fh
    except Exception as e:
        print(f"❌ Error descargando '{file_name}': {e}")
        return None

def validar_carpeta_base():
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not folder_id:
        print("⚠️ ADVERTENCIA: Variable 'GOOGLE_DRIVE_FOLDER_ID' no configurada.")
        return None
    return folder_id

if __name__ == "__main__":
    print("🔬 Iniciando prueba de conexión segura a Drive...")
    try:
        # Verificar que la carga funcionó
        if not os.getenv("GOOGLE_CREDENTIALS_JSON"):
            print("❌ ERROR: Aún no detecto las variables. ¿Ejecutaste 'pip install python-dotenv'?")
        else:
            srv = get_drive_service()
            print("✅ Autenticación exitosa. Servicio de Drive listo.")
            folder = validar_carpeta_base()
            if folder:
                print(f"✅ ID de Carpeta Base detectado: {folder}")
            else:
                print("⚠️ No se detectó ID de carpeta, pero la autenticación funcionó.")
    except Exception as e:
        print(f"❌ Test fallido: {e}")
        