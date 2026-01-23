import os.path
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- SU ID DE CARPETA ---
CARPETA_ID = '1nNGnig29BrPUe84E12QEwBa-UqIZmjSP' 
# ------------------------

def probar_conexion():
    print("\n--- INICIANDO PRUEBA ---")
    
    if not os.path.exists('credenciales.json'):
        print("❌ ERROR: No encuentro 'credenciales.json' en la carpeta Jurisprudencia.")
        return

    try:
        print("1. Leyendo llave...")
        creds = service_account.Credentials.from_service_account_file(
            'credenciales.json', 
            scopes=['https://www.googleapis.com/auth/drive.metadata.readonly']
        )
        
        print("2. Conectando a Google Drive...")
        service = build('drive', 'v3', credentials=creds)

        print(f"3. Buscando archivos en carpeta {CARPETA_ID}...")
        results = service.files().list(
            q=f"'{CARPETA_ID}' in parents and trashed=false",
            pageSize=10,
            fields="files(id, name)"
        ).execute()
        
        items = results.get('files', [])

        if not items:
            print("⚠️ Conexión exitosa, pero no veo archivos.")
            print("   IMPORTANTE: ¿Recordó compartir la carpeta en Drive con el email del robot?")
        else:
            print("\n✅ ¡CONEXIÓN EXITOSA! Veo estos archivos:")
            for item in items:
                print(f"   📄 {item['name']}")

    except Exception as e:
        print(f"\n❌ Error técnico: {e}")

if __name__ == '__main__':
    probar_conexion()
