import os
import uuid
import sys
from sqlalchemy.orm import Session

# Importamos modelos y dependencias locales
import models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from anonimizador import anonimizador 
from pdf_utils import extraer_texto_pdf

class Bibliotecario:
    def __init__(self):
        # 💡 GRAN CAMBIO ARQUITECTÓNICO:
        # Ya no instanciamos 'genai.Client' aquí. La generación del sumario 
        # y la vectorización (3072 dimensiones) se delegaron a main.py 
        # (endpoint de validación) para que ocurran solo POST-revisión humana.
        pass

    def procesar_nueva_sentencia(self, db: Session, ruta_pdf: str, metadata_drive: dict, dependencia_destino: int):
        """
        Ingesta Fase 1: Extracción y NLP.
        Prepara el documento como PENDIENTE para la revisión del Juez/Secretario.
        """
        id_drive_archivo = metadata_drive.get('id_drive')

        # --- 1. IDEMPOTENCIA Y RACE CONDITIONS ---
        existe = db.query(models.Sentencia).filter_by(id_drive=id_drive_archivo).first()
        if existe:
            print(f"⏭️ El archivo {id_drive_archivo} ya existe en BD. Omitiendo.")
            return None

        # --- 2. GOBERNANZA ESTRICTA ---
        if not dependencia_destino:
            raise ValueError("❌ Seguridad: Dependencia destino no especificada. Operación cancelada.")

        print(f"📖 Bibliotecario: Preparando borrador para {metadata_drive.get('caratula_original', 'S/D')}")

        # --- 3. EXTRACCIÓN Y ANONIMIZACIÓN LOCAL (Sin costo de API) ---
        texto_crudo = extraer_texto_pdf(ruta_pdf)
        texto_seguro = anonimizador.anonimizar_texto(texto_crudo)

        try:
            # --- 4. GUARDADO SEGURO (NACE BLOQUEADA) ---
            # Guardamos la sentencia exclusivamente con el estado PENDIENTE.
            # No se crea la tabla IndiceSentencia, por lo que es invisible al buscador.
            nueva_sentencia = models.Sentencia(
                uuid_seguro=str(uuid.uuid4()),
                id_drive=id_drive_archivo,
                texto_completo=texto_crudo,      # Nivel 1/2
                texto_anonimizado=texto_seguro,  # El humano lo editará luego
                caratula_real=metadata_drive.get('caratula_original', 'Reservada'),
                nro_expediente=metadata_drive.get('nro_expediente', 'S/D'),
                dependencia_id=dependencia_destino,
                estado=models.EstadoSentencia.PENDIENTE # <-- Cumplimiento HITL
            )
            
            db.add(nueva_sentencia)
            db.commit() 
            
            print("✅ Bibliotecario: Ingesta segura completada. Pendiente de validación humana.")
            return nueva_sentencia.uuid_seguro

        except Exception as error_procesamiento:
            # FAIL-SAFE: En caso de error de base de datos
            db.rollback()
            print(f"❌ Error en procesamiento de {id_drive_archivo}: {str(error_procesamiento)}")
            return None