import models
from sqlalchemy.orm import Session
from sqlalchemy import text
from google import genai
from datetime import datetime

def parsear_fecha(fecha_str):
    """
    Intenta convertir el string de fecha a objeto datetime para poder ordenar.
    Soporta formatos DD-MM-YYYY, YYYY-MM-DD, etc.
    Si falla, devuelve una fecha muy antigua.
    """
    if not fecha_str:
        return datetime.min
    
    formatos = ["%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"]
    
    # Limpieza básica
    fecha_limpia = fecha_str.strip().split(" ")[0] # Por si viene con hora
    
    for fmt in formatos:
        try:
            return datetime.strptime(fecha_limpia, fmt)
        except ValueError:
            continue
    return datetime.min

def analizar_consulta(cliente_ai, db: Session, consulta_usuario: str):
    """
    Motor RAG Híbrido (Semántica + Recencia):
    1. Busca una red amplia de candidatos por similitud (Vectores).
    2. Aplica un filtro inteligente: Retiene los MUY parecidos y los MÁS NUEVOS.
    3. Genera análisis evolutivo con Gemini.
    """
    
    print(f"🔎 Relator analizando contexto: '{consulta_usuario[:50]}...'")

    # PASO 1: Vectorizar la consulta (captura hechos y contexto detallado)
    try:
        resultado_embedding = cliente_ai.models.embed_content(
            model="text-embedding-004",
            contents=consulta_usuario
        )
        vector_consulta = resultado_embedding.embeddings[0].values
    except Exception as e:
        return f"Error técnico interpretando la consulta: {e}", []

# ---------------------------------------------------------
    # PASO 2: Búsqueda Vectorial (Materia Prima)
    # ---------------------------------------------------------
    columna_distancia = models.IndiceSentencia.vector_embedding.cosine_distance(vector_consulta).label("distancia")
    
    # Traemos 80 candidatos ordenados por MEJOR COINCIDENCIA (menor distancia)
    resultados_brutos = db.query(models.IndiceSentencia, columna_distancia).order_by(columna_distancia).limit(80).all()

    if not resultados_brutos:
        return "No se encontraron antecedentes.", []

    # ---------------------------------------------------------
    # PASO 3: Preparación para la IA (Variable 'seleccion_final')
    # ---------------------------------------------------------
    # Filtramos con criterio amplio (0.60) para dar contexto a la IA
    pool_ia = []
    for item, dist in resultados_brutos:
        if dist < 0.60:
            pool_ia.append(item)

    # Ordenamos por FECHA para el análisis evolutivo
    pool_ia.sort(key=lambda x: parsear_fecha(x.fecha), reverse=True)
    
    # ESTA ES LA VARIABLE QUE BUSCA EL PASO 5:
    seleccion_final = pool_ia[:40]

    # Preparamos el texto completo para el prompt
    texto_antecedentes = ""
    for idx, item in enumerate(seleccion_final):
        try:
            contenido = item.sentencia.texto
            if not contenido: contenido = item.sumario_analitico
        except:
            contenido = item.sumario_analitico

        texto_antecedentes += f"""
        --- DOCUMENTO {idx+1} ---
        Carátula: {item.caratula}
        Fecha: {item.fecha}
        CONTENIDO: {contenido[:40000]}
        -----------------
        """

    # ---------------------------------------------------------
    # PASO 4: Preparación para FRONTEND (La Lista "Vip")
    # ---------------------------------------------------------
    # 1. Usamos 'resultados_brutos' (ya ordenados por relevancia).
    # 2. Filtramos ESTRICTO (0.45).
    # 3. Tomamos solo el TOP 10.
    
    candidatos_visuales = []
    UMBRAL_VISUAL = 0.45 
    
    for item, dist in resultados_brutos:
        if dist < UMBRAL_VISUAL:
            candidatos_visuales.append(item)
    
    # CORTE DE CANTIDAD: Nos quedamos solo con los 10 más relevantes
    candidatos_visuales = candidatos_visuales[:10]

    # REORDENAMIENTO FINAL: Esos 10 mejores, los mostramos por fecha (más nuevo arriba)
    candidatos_visuales.sort(key=lambda x: parsear_fecha(x.fecha), reverse=True)

    lista_fallos_frontend = []
    for item in candidatos_visuales:
        try: link = getattr(item.sentencia, "link_web", "#")
        except: link = "#"

        lista_fallos_frontend.append({
            "caratula": item.caratula,
            "fecha": item.fecha,
            "link": link
        })
        
    # Si no quedó ninguno para mostrar, ponemos el Top 1 absoluto como fallback
    if not lista_fallos_frontend and resultados_brutos:
        best_match = resultados_brutos[0][0]
        lista_fallos_frontend.append({
            "caratula": best_match.caratula,
            "fecha": best_match.fecha,
            "link": getattr(best_match.sentencia, "link_web", "#")
        })

    # --- EL CÓDIGO SIGUE CON EL PASO 5 (Prompt) ---

    # PASO 5: El Prompt "Anti-Pereza" y "Evolutivo"
    print(f"🧠 Analizando {len(seleccion_final)} fallos seleccionados...")
    
    prompt_final = f"""
    ROL: Relator Jefe de Jurisprudencia del Juzgado Laboral.
    OBJETIVO: Detectar la línea jurisprudencial vigente y su evolución.
    
    CONSULTA (HECHOS Y TEMA): "{consulta_usuario}"
    
    BASE DE DATOS (Selección de fallos más relevantes y recientes):
    {texto_antecedentes}
    
    --- REGLAS DE ESTILO ---
    1. REFERENCIAS: Cita los fallos por su CARÁTULA REAL (tal cual figura en el antecedente).
    2. REDACCIÓN: Al explicar los hechos, usa ROLES (El Actor, La Demandada, La ART) en lugar de repetir nombres propios, para mantener un estilo técnico y profesional.

        INSTRUCCIONES DE ANÁLISIS:
    1. LECTURA TOTAL: Debes considerar los {len(seleccion_final)} resúmenes provistos y el text completo de las sentencias.
    2. FILTRO DE CONTEXTO: La consulta puede incluir hechos específicos (ej: "embarazo", "accidente in itinere"). Descarta aquellos fallos de la lista que, aunque hablen del tema general, no coincidan con los hechos clave de la consulta.
    3. ANÁLISIS EVOLUTIVO (CRÍTICO):
       - Identifica los fallos más antiguos y compáralos con los más recientes de la lista.
       - ¿El criterio se mantuvo o cambió? (Ej: ¿Antes se rechazaba y ahora se acepta?).
       - Si hay contradicciones, da prioridad al criterio de los fallos más recientes (2024-2026).
    
    ESTRUCTURA DE LA RESPUESTA:
    1. POSTURA ACTUAL DEL JUZGADO:
       - Respuesta directa y contundente a la consulta basada en la tendencia reciente.
       - Evita decir "el criterio del Juzgado" o "el criterio del Juez" es preferible decir "la jurisprudencia del juzgado muestra...": "la interpretación del juzgado...", etc.    
    2. EVOLUCIÓN Y FUNDAMENTOS:
       - Explicación profunda y fundada de cómo se llegó a esta postura.
       - Menciona si hubo un cambio legislativo o de postura notorio. 
       - Análisis crítrico y profundo de los fundamentos jurídicos usados.  
    3. PRECEDENTES CLAVE (Citas):
       - Lista 3 o 4 fallos que fundamenten tu respuesta (Prioriza los más recientes o los fácticamente idénticos).
       - Formato: "Carátula (Fecha): Síntesis".
       - Solo lista fallos relevanes que se relacionen directamente con los hechos de la consulta.
       - No te presentes. No digas que eres relator jefe. Ve directo al análisis.
    
    NOTA: Si no hay fallos que coincidan con los hechos específicos, indícalo: "No hay precedentes con esta plataforma fáctica exacta, pero por analogía el criterio es..."
    CLÁUSULA FINAL OBLIGATORIA:
    "El presente análisis fue generado por IA. La interpretación efectuada DEBE corroborarse por el usuario."
    """

    try:
        response = cliente_ai.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt_final,
            config={'temperature': 0.0}
        )
        return response.text, lista_fallos_frontend
        
    except Exception as e:
        return f"Error generando la respuesta de la IA: {e}", []