import os
from google import genai
from sqlalchemy.orm import Session
import models
from dotenv import load_dotenv
load_dotenv()

class BuscadorSemantico:
    def __init__(self):
        # INTENTO 1: Buscar en variables de entorno del sistema
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            print("❌ ERROR FATAL: No hay API Key para el buscador.")
            # Esto evitará que explote al arrancar, pero fallará al buscar
            self.client = None 
        else:
            self.client = genai.Client(api_key=api_key)

    def buscar_similar(self, db: Session, consulta: str, top_k: int = 5):
        """
        Genera el embedding de la consulta y busca los registros más cercanos en la BD.
        """
        # Protección si no hay cliente
        if not self.client:
            print("⚠️ El buscador no está configurado (Falta API Key)")
            return []

        try:
            # 1. Generar el embedding de la pregunta del usuario
            response = self.client.models.embed_content(
                model="text-embedding-004",
                contents=consulta
            )
            
            # Extraer el vector numérico
            embedding_consulta = response.embeddings[0].values

            # 2. Buscar en la base de datos usando pgvector
            resultados = db.query(models.IndiceSentencia).order_by(
                models.IndiceSentencia.vector_embedding.cosine_distance(embedding_consulta)
            ).limit(top_k).all()

            # Devolvemos una lista de diccionarios con la info formateada
            items_formateados = []
            for item in resultados:
                items_formateados.append({
                    "caratula": item.caratula,
                    "fecha": item.fecha,
                    "voces": item.voces,
                    "sumario": item.sumario_analitico,
                    "link": getattr(item.sentencia, "link_web", "#") 
                })
            
            return items_formateados

        except Exception as e:
            print(f"Error en búsqueda semántica: {e}")
            return []

# Instancia global que importará main.py
buscador_semantico = BuscadorSemantico()