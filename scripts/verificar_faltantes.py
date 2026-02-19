import os
import io
import json
import re
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from dotenv import load_dotenv

# Cargar variables locales (si existen)
load_dotenv()

# --- CONFIGURACIÓN ---
CARPETA_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
NOMBRE_EXCEL_1 = os.getenv("FILENAME_EXCEL_HISTORICO", "CARGA ANTECEDENTES SENTENCIAS LABORAL 2.xlsx")
NOMBRE_EXCEL_2 = os.getenv("FILENAME_EXCEL_ACTUAL", "SENTENCIAS LABORAL 2.xlsx")

def validar_entorno():
    if not CARPETA_ID or not os.getenv("GOOGLE_CREDENTIALS_JSON"):
        raise ValueError("❌ Faltan variables de entorno obligatorias en .env")

def conectar_drive():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    try:
        creds_info = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=['https://www.googleapis.com/auth/drive']
        )
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ Error de autenticación: {e}")
        return None

def descargar_excel_en_memoria(service, file_id, nombre):
    """Descarga el archivo a la RAM."""
    print(f"📥 Descargando '{nombre}' (ID: {file_id})...")
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)
        return fh
    except Exception as e:
        print(f"❌ Error descargando {nombre}: {e}")
        return None

def buscar_id_por_nombre(service, nombre_archivo):
    """Busca archivo por nombre exacto en todo el Drive."""
    try:
        query = f"name = '{nombre_archivo}' and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)", pageSize=1).execute()
        files = results.get('files', [])
        if files: return files[0]['id']
        return None
    except Exception as e:
        print(f"⚠️ Error buscando archivo '{nombre_archivo}': {e}")
        return None

def listar_archivos_recursivo(service, root_folder_id):
    """Escanea recursivamente buscando PDFs."""
    archivos = []
    cola = [root_folder_id]
    procesados = 0
    
    print("📡 Iniciando escaneo recursivo de PDFs en Drive...")
    while cola:
        folder_id = cola.pop(0)
        procesados += 1
        page_token = None
        
        if procesados % 10 == 0:
            print(f"   📂 Escaneando carpeta #{procesados}...")

        while True:
            try:
                results = service.files().list(
                    q=f"'{folder_id}' in parents and trashed=false",
                    fields="nextPageToken, files(id, name, mimeType)",
                    pageSize=1000,
                    pageToken=page_token
                ).execute()
                
                for item in results.get('files', []):
                    if item['mimeType'] == 'application/vnd.google-apps.folder':
                        cola.append(item['id'])
                    elif 'pdf' in item['mimeType'] or item['name'].lower().endswith('.pdf'):
                        archivos.append(item)
                
                page_token = results.get('nextPageToken')
                if not page_token: break
            except Exception as e:
                print(f"⚠️ Error leyendo carpeta {folder_id}: {e}")
                break
    return archivos

def extraer_clave_normalizada(texto):
    """Convierte '123/2022' o nombres de archivo en '123-2022'."""
    if not texto: return None
    s = str(texto).strip().lower()
    match = re.search(r'(\d+)[\/\-\_\s].*?(\d{2,4})', s)
    if match:
        numero = match.group(1)
        anio = match.group(2)
        if len(anio) == 2:
            anio = f"19{anio}" if int(anio) > 50 else f"20{anio}"
        
        clave = f"{numero}-{anio}"
        if "bis" in s:
             match_bis = re.search(r'bis\s*(\d*)', s)
             sufijo = match_bis.group(1) if match_bis and match_bis.group(1) else "1"
             clave = f"{clave}-bis-{sufijo}"
        return clave
    return None

def main():
    try:
        validar_entorno()
    except ValueError as e:
        print(e)
        return

    service = conectar_drive()
    if not service: return

    # 1. BUSCAR EXCELS
    print("🔍 Buscando archivos de control (Excel)...")
    id_excel_1 = buscar_id_por_nombre(service, NOMBRE_EXCEL_1)
    id_excel_2 = buscar_id_por_nombre(service, NOMBRE_EXCEL_2)

    if not id_excel_1: print(f"⚠️ NO SE ENCONTRÓ: {NOMBRE_EXCEL_1}")
    if not id_excel_2: print(f"⚠️ NO SE ENCONTRÓ: {NOMBRE_EXCEL_2}")

    # 2. ESCANEAR PDFs
    pdfs_en_drive = listar_archivos_recursivo(service, CARPETA_ID)
    print(f"✅ Se encontraron {len(pdfs_en_drive)} archivos PDF en Drive.")

    mapa_pdfs = {}
    pdfs_sin_identificar = []
    for pdf in pdfs_en_drive:
        clave = extraer_clave_normalizada(pdf['name'])
        if clave:
            mapa_pdfs[clave] = pdf
        else:
            pdfs_sin_identificar.append(pdf)

    # 3. PROCESAR EXCELS
    master_dict = {}

    # Excel 1
    if id_excel_1:
        fh = descargar_excel_en_memoria(service, id_excel_1, NOMBRE_EXCEL_1)
        if fh:
            try:
                df = pd.read_excel(fh, usecols="A,B,N", header=0)
                df.columns = ['expediente', 'caratula', 'fecha']
                for _, row in df.iterrows():
                    if pd.isna(row['fecha']): continue
                    clave = extraer_clave_normalizada(row['expediente'])
                    if clave:
                        master_dict[clave] = {
                            "Expediente": row['expediente'],
                            "Caratula": row['caratula'],
                            "Fecha": row['fecha'],
                            "Fuente": "Excel Histórico",
                            "Estado": "Pendiente",
                            "Link_Drive": None
                        }
            except Exception as e:
                print(f"❌ Error leyendo Excel 1: {e}")

    # Excel 2
    if id_excel_2:
        fh = descargar_excel_en_memoria(service, id_excel_2, NOMBRE_EXCEL_2)
        if fh:
            try:
                df = pd.read_excel(fh, usecols="A,B,O", header=0) 
                df.columns = ['expediente', 'caratula', 'fecha']
                for _, row in df.iterrows():
                    if pd.isna(row['fecha']): continue
                    clave = extraer_clave_normalizada(row['expediente'])
                    if clave:
                        if clave not in master_dict:
                            master_dict[clave] = {
                                "Expediente": row['expediente'],
                                "Caratula": row['caratula'],
                                "Fecha": row['fecha'],
                                "Fuente": "Excel Actual",
                                "Estado": "Pendiente",
                                "Link_Drive": None
                            }
                        else:
                            master_dict[clave]["Fuente"] += " + Actual"
            except Exception as e:
                print(f"❌ Error leyendo Excel 2: {e}")

    print(f"📊 Total de sentencias esperadas (según Excel): {len(master_dict)}")

    # 4. CRUZAMIENTO
    for clave, datos in master_dict.items():
        if clave in mapa_pdfs:
            datos["Estado"] = "✅ OK (Completo)"
            datos["Link_Drive"] = f"https://drive.google.com/file/d/{mapa_pdfs[clave]['id']}"
            mapa_pdfs[clave]['reclamado'] = True
        else:
            datos["Estado"] = "❌ Faltante (Sin PDF)"

    lista_no_en_excel = []
    for clave, pdf in mapa_pdfs.items():
        if not pdf.get('reclamado'):
            lista_no_en_excel.append({
                "Expediente": f"PDF: {clave}",
                "Caratula": pdf['name'],
                "Fecha": None,
                "Fuente": "Solo en Drive (PDF)",
                "Estado": "⚠️ No registrado en Excel",
                "Link_Drive": f"https://drive.google.com/file/d/{pdf['id']}"
            })

    # 5. GENERAR SALIDA CON FORMATO
    lista_consolidada = list(master_dict.values()) + lista_no_en_excel
    df_consolidado = pd.DataFrame(lista_consolidada)
    
    # Ordenar y Formatear
    try:
        # 1. Convertir a objeto fecha real para poder ordenar correctamente
        df_consolidado['Fecha_Orden'] = pd.to_datetime(df_consolidado['Fecha'], errors='coerce')
        df_consolidado = df_consolidado.sort_values('Fecha_Orden', ascending=False)
        
        # 2. Convertir la columna visible 'Fecha' al formato estricto dd/mm/aaaa
        #    Si la fecha es NaT (vacía), se deja vacía.
        df_consolidado['Fecha'] = df_consolidado['Fecha_Orden'].dt.strftime('%d/%m/%Y').fillna('')
        
    except Exception as e:
        print(f"⚠️ Advertencia menor: No se pudo formatear fechas ({e})")

    df_faltantes = df_consolidado[df_consolidado['Estado'].str.contains("Faltante", na=False)].copy()
    df_huerfanos = pd.DataFrame(lista_no_en_excel)

    nombre_archivo = "AUDITORIA_INTEGRAL_SENTENCIAS.xlsx"
    print(f"\n💾 Guardando reporte en '{nombre_archivo}'...")
    
    with pd.ExcelWriter(nombre_archivo, engine='openpyxl') as writer:
        # Eliminamos la columna auxiliar de orden antes de guardar
        df_consolidado.drop(columns=['Fecha_Orden'], errors='ignore').to_excel(writer, sheet_name='Consolidado_Total', index=False)
        df_faltantes.drop(columns=['Fecha_Orden'], errors='ignore').to_excel(writer, sheet_name='Faltan_PDFs', index=False)
        df_huerfanos.to_excel(writer, sheet_name='No_en_Excel', index=False)
        if pdfs_sin_identificar:
            pd.DataFrame(pdfs_sin_identificar).to_excel(writer, sheet_name='PDFs_Nombre_Raro', index=False)

    print("\n✅ PROCESO COMPLETADO")
    print(f"   🔹 Universo Total: {len(df_consolidado)}")
    print(f"   🔹 Faltan PDFs: {len(df_faltantes)}")
    print(f"   🔹 Sobran PDFs: {len(df_huerfanos)}")

if __name__ == "__main__":
    main()