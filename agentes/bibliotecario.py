import models
import json
import re
from sqlalchemy.orm import Session
from google import genai

# Configuración del Modelo (Mantenemos tu elección por rendimiento/cuota)
MODELO_IA = 'gemini-2.0-flash-lite'

def limpiar_json_ia(texto_sucio):
    """
    Limpia la respuesta de la IA para obtener un JSON válido.
    Mejorada con Regex para encontrar el JSON aunque la IA añada texto introductorio.
    """
    if not texto_sucio: return "{}"
    
    # 1. Intentar quitar bloques de código markdown
    texto = re.sub(r"```json\s*", "", texto_sucio, flags=re.IGNORECASE)
    texto = re.sub(r"```\s*$", "", texto)
    
    # 2. Si aún hay basura alrededor, buscar el primer '{' y el último '}'
    match = re.search(r'\{.*\}', texto, re.DOTALL)
    if match:
        return match.group()
        
    return texto.strip()

def obtener_embedding(cliente_ai, texto):
    """
    Convierte texto en un vector de 768 números usando el modelo de embeddings.
    """
    try:
        # Recortamos a 9000 chars para evitar error de límite de tokens en el modelo de embedding
        texto_clean = texto.replace("\n", " ").strip()[:9000]
        
        resultado = cliente_ai.models.embed_content(
            model="models/text-embedding-004",
            contents=texto_clean
        )
        return resultado.embeddings[0].values
    except Exception as e:
        print(f"⚠️ Error generando embedding: {e}")
        return None

def procesar_un_expediente(cliente_ai, db: Session, sentencia_id: int, texto_completo: str):
    """
    1. Analiza el texto con TU PROMPT ORIGINAL (Consistencia garantizada).
    2. Genera el vector numérico.
    3. Guarda todo en la base de datos.
    """
    
    # --- TU PROMPT ORIGINAL Y VALIDADO (INTACTO) ---
    prompt = f"""
    ROL: Secretario de Jurisprudencia Experto.
    TAREA: Analizar la sentencia judicial provista y estructurar sus datos clave para una base de datos.
    
    TEXTO DE LA SENTENCIA:
    {texto_completo[:90000]} 
    
    --- INSTRUCCIONES ESTRICTAS DE EXTRACCIÓN ---
    
    1. CARÁTULA REAL: 
       - Debe incluir el NÚMERO DE EXPEDIENTE si figura en el texto.
       - Formato deseado: "Expte N° [Numero] - [Actor] c/ [Demandado] s/ [Objeto]"
       - Búscala al inicio (Vistos:...: o Causa:...) o en el encabezado.
       - Extráela EXACTAMENTE como figura en el texto (Autos, Vistos o Encabezado).
       - NO modifiques, abrevies ni anonimices nada en este campo.
       
    2. FECHA:
       - Extrae la fecha de la sentencia (generalmente al inicio luego del lugar (Posadas,...). Formato DD-MM-YYYY (si es posible), en el texto surgirá el mes en letras.
       
    3. VOCES (TAGS):
       - Lista de conceptos jurídicos tratados.
       - OBLIGATORIO: Usar minúsculas.
       - Separados por guiones.
       - Ej: "accidente de trabajo - cálculo ibm - ley 27348 - inconstitucionalidad"
       
    4. SUMARIO ANALÍTICO (NO RESUMIR EN EXCESO):
       - No quiero un tweet. Quiero un análisis detallado.
       - En este resumen, EVITA usar los nombres propios.
       - Usa ROLES PROCESALES para explicar los hechos: "El actor reclamó...", "La demandada contestó...", "El testigo afirmó...", "el perito....
       - Para CADA tema/rubro tratado (ej: despido, horas extras, multa art 80), explica:
         A) El planteo.
         B) La SOLUCIÓN ADOPTADA por el Juez (se hizo lugar o se rechazó).
         C) El fundamento central.
       
    SALIDA ESPERADA (Formato JSON puro):
    {{
        "caratula": "...",
        "fecha": "...",
        "voces": "...",
        "sumario": "..."
    }}
    """
    
    try:
        # 1. GENERAR Metadata (Usando flash-lite por rendimiento)
        response = cliente_ai.models.generate_content(
            model=MODELO_IA, 
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )
        
        texto_limpio = limpiar_json_ia(response.text)
        
        try:
            datos = json.loads(texto_limpio)
        except json.JSONDecodeError:
            print(f"⚠️ Error de JSON en ID {sentencia_id}. Reintentando limpieza...")
            # Fallback simple si la limpieza regex falló
            datos = {}

        # Blindaje contra listas (si la IA devuelve [{}])
        if isinstance(datos, list):
            datos = datos[0] if len(datos) > 0 else {}

        # Validar datos extraídos (Defaults seguros)
        caratula = datos.get("caratula", "Sin Carátula")
        voces = datos.get("voces", "")
        sumario = datos.get("sumario", "")
        fecha = datos.get("fecha", "S/F")

        # 2. GENERAR VECTOR (La "Huella Digital" Semántica)
        # Combinamos voces y sumario tal como lo venías haciendo
        texto_para_vectorizar = f"Temas: {voces}. Resumen: {sumario}"
        vector = obtener_embedding(cliente_ai, texto_para_vectorizar)

        # 3. GUARDAR EN BASE DE DATOS
        nuevo_indice = models.IndiceSentencia(
            sentencia_id=sentencia_id,
            caratula=caratula,
            fecha=fecha,
            voces=voces.lower(),
            sumario_analitico=sumario,
            vector_embedding=vector
        )
        
        db.add(nuevo_indice)
        db.commit()
        return True

    except Exception as e:
        print(f"❌ Error procesando ID {sentencia_id}: {e}")
        db.rollback() 
        # No relanzamos la excepción (raise e) para que el script masivo NO se detenga,
        # sino que anote el error y pase al siguiente archivo.
        return False