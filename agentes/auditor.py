from datetime import datetime
import models

def ejecutar_auditoria(cliente_ai, db, texto_borrador, nombre_archivo):
    """
    Agente de Control de Proyectos.
    Conecta con la BD para leer reglas personalizadas y usa Gemini para el análisis.
    """
    # 0. GUARDIA DE SEGURIDAD (Evitar enviar texto vacío)
    if not texto_borrador or len(texto_borrador.strip()) < 50:
        return {
            "informe_ia": "⚠️ **ERROR: El documento parece estar vacío o es demasiado corto.**\n\nPor favor, pegue el texto completo del proyecto o suba el archivo nuevamente."
        }
    
    # 1. Recuperar reglas activas (Adaptado a la estructura nueva)
    try:
        reglas_db = db.query(models.ReglaEstilo).all()
    except Exception:
        reglas_db = []
    
    # Formateamos las reglas para el Prompt
    if reglas_db:
        lista_reglas_txt = "\n".join([
            f"- [{r.categoria.upper()}] Regla: '{r.regla}'. Instrucción: {r.explicacion}" 
            for r in reglas_db
        ])
    else:
        lista_reglas_txt = "No hay reglas internas específicas cargadas para este análisis."

    # 2. PROMPT CON ESTRUCTURA XML (Mejor comprensión para Gemini)
    # Usamos etiquetas claras para que la IA sepa qué es instrucción y qué es dato.
    prompt = f"""
    ROL: Analista Jurídico Especializado (Juzgado Laboral N.º 2).
    TU FUNCIÓN: Analizar claridad del texto, técnica, doctrinaria y gramaticalmente el siguiente proyecto de sentencia. 
    
    *** REGLAS INVIOLABLES ***
    1. NO inventes nada. No inventes hechos. Ajusta el análisis al texto provisto por el usuario. Si el texto no menciona algo, no lo asumas.
    2. Si el texto está incompleto, dilo.
    3. Verifica que las citas legales existan. Debes controlar el formato de las citas bibliograficas y jurisprudenciales existentes en el texto. Si no hay citas que controlar simplemente dilo.

    REGLAS DE ESTILO ESPECÍFICAS DEL JUZGADO (Prioridad Alta):
    {lista_reglas_txt if reglas_db else "No hay reglas internas cargadas hoy."}
    
    *** TEXTO A ANALIZAR (PROYECTO REAL) ***
    <proyecto_sentencia>
    {texto_borrador}
    </proyecto_sentencia>

    --- INSTRUCCIONES DE ANÁLISIS ---
    
    ETAPA 1 – VOCES JURÍDICAS Y SUMARIO
    Genera un encabezado con:
    1. Carátula (extraída del texto, si existe, sino usa "{nombre_archivo}").
    2. Voces temáticas (Descriptor jurídico normalizado SAIJ, separado por guiones, no usar mayúsculas).
    3. Normas citadas (Ley, art, inc).
    4. Sumario: Resumen técnico <80 palabras.
    
    ETAPA 2 – CALIDAD DE REDACCIÓN Y CITAS
    Analiza lenguaje, claridad y coherencia.
    - Crea una TABLA DE ERRORES ORTOGRÁFICOS (Error | Corrección).
    - Revisa CITAS DOCTRINARIAS: Deben tener Autor, Título, Editorial, Año, página.
    - Revisa CITAS JURISPRUDENCIALES: Deben tener Tribunal, Carátula, Fecha, Publicación.
    - Si las citas son de Cámara de Apelaciones de Posadas (Alzada) o de STJ Misiones deben indicar la carátula, fecha de sentencia y Sala I o Sala II, en el caso de la Cámara. Las del STJ Misiones: carátula y fecha de la sentencia.
    - No inventar citas, ni datos faltantes.
    - IMPORTANTE: Si las citas están bien, NO digas nada. Solo reporta las citas mal formadas o sospechosas.
    *Si encuentras citas mal formadas, listarlas y sugerir corrección.*
    
    ETAPA 3 – CONTROL DE COHERENCIA Y REGLAS
    (Nota: Analiza la coherencia interna y el cumplimiento de las REGLAS DE ESTILO listadas arriba).
    - REGLA DE SILENCIO: Si el texto cumple las reglas, escribe ÚNICAMENTE: "✅ Sin inconsistencias de estilo detectadas."
    - NO listes las reglas que se cumplieron. Solo lista las VIOLACIONES detectadas.
    - Aplica los Umbrales de Advertencia (Baja, Media, Alta) si detectas contradicciones lógicas o violaciones a las reglas del juzgado.
    
    ETAPA 4 – RAZONAMIENTO JUDICIAL
    1. Antecedentes y Planteos (Síntesis estricta).    
    2. Solución Proyectada (Qué se decide).
    3. Fundamentos Jurídicos (Premisas explícitas e implícitas).
    4. Evaluación Argumental (Puntos fuertes y débiles, saltos lógicos).
    5. Análisis Probatorio (Cómo se valoró la prueba, sin verificar el expediente real).
          
    SEMÁFORO DE CALIDAD
    * 🔴 **Errores Graves:** (Contradicciones, citas inventadas, fallas en la fundamentación, falta de resolución).
    * 🟡 **Advertencias:** (Errores ortográficos, frases confusas).
    * 🟢 **Aciertos:** (Buena fundamentación).

    --- FORMATO DE SALIDA ---
    Usa Markdown. Respeta negritas y tablas.
    
    INSTRUCCIONES DE FORMATO OBLIGATORIAS (Output):
    1. TÍTULO: Comienza DIRECTAMENTE con: "INFORME DE AUDITORÍA"
    2. PROHIBIDO presentarse (No digas "Soy el auditor", "Como IA...", etc).
    3. PROHIBIDO saludar ni despedirse.
    4. Estructura visualmente en dos secciones: "ANÁLISIS DE ESTILO" y "COHERENCIA LÓGICA".
    
    CLÁUSULA FINAL OBLIGATORIA:
    "El presente análisis se apoya exclusivamente en el contenido del proyecto. NO implica conformidad o validación de la solución ni del análisis probatorio. Análisis generado por IA."
    """
    try:
        # 3. Llamada a Gemini
        response = cliente_ai.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt,
            config={'temperature': 0.0}
        )
        informe = response.text
        
        # 4. Guardado en Base de Datos (Tabla Auditoria debe existir en models.py)
        # Si no tienes la tabla Auditoria aún, comenta este bloque.
        try:
            nueva_auditoria = models.Auditoria(
                fecha=datetime.now(),
                usuario="Juzgado",
                nombre_archivo=nombre_archivo,
                resultado_analisis=informe,
                validado=False
            )
            db.add(nueva_auditoria)
            db.commit()
            id_auditoria = nueva_auditoria.id
        except Exception as e:
            print(f"No se pudo guardar historial: {e}")
            id_auditoria = 0
        
        return {"informe_ia": informe, "id_auditoria": id_auditoria}

    except Exception as e:
        return {"error": f"Error en Agente Auditor: {str(e)}"}