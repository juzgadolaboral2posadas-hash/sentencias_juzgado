import os
import shutil
import re
import io
from typing import List, Optional, Dict
from collections import Counter
from datetime import datetime, timedelta

# --- IMPORTS DE FASTAPI ---
from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, HTTPException, status, Cookie
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi import Response # Para los headers de No-Cache
from pydantic import BaseModel

# --- IMPORTS DE BASE DE DATOS ---
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text, desc
from database import engine, get_db
import models

# --- SEGURIDAD ---
from passlib.context import CryptContext
from jose import JWTError, jwt
from dotenv import load_dotenv

# --- IA Y LIBRERÍAS DE ARCHIVOS (USAMOS LAS QUE YA TIENES) ---
from google import genai
import fitz # PyMuPDF (PDF) - El que instalamos hoy y funcionó
import docx # python-docx (Word) - El que tenías en tu backup
from odf import text as odf_text, teletype # odfpy (OpenOffice) - El que tenías en tu backup
from odf.opendocument import load

# --- AGENTES PROPIOS ---
from buscador import buscador_semantico
from agentes import auditor 
from agentes import relator
from agentes import buscador_publico

# ==========================================
# 1. CONFIGURACIÓN GLOBAL
# ==========================================

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Inicializamos cliente global
try:
    client_ai = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Error iniciando Gemini: {e}")
    client_ai = None

SECRET_KEY = os.getenv("SECRET_KEY") 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 

# Crear tablas
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="SGP - Juzgado Laboral 2")
app.mount("/static", StaticFiles(directory="static"), name="static")
# Usamos 'templates' como carpeta
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ==========================================
# 2. SISTEMA DE LOGIN
# ==========================================

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token: return None
    try:
        if token.startswith("Bearer "): token = token.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: return None
    except JWTError: return None
    return db.query(models.Usuario).filter(models.Usuario.username == username).first()

async def login_required(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login requerido")
    return user

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/token")
async def login_for_access_token(response: JSONResponse, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.Usuario).filter(models.Usuario.username == username).first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        return JSONResponse(status_code=400, content={"error": "Datos incorrectos"})
    
    encoded_jwt = jwt.encode({"sub": user.username}, SECRET_KEY, algorithm=ALGORITHM)
    resp = JSONResponse(content={"mensaje": "Login exitoso", "redirect": "/"})
    resp.set_cookie(key="access_token", value=f"Bearer {encoded_jwt}", httponly=True)
    return resp

@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie("access_token")
    return resp

# ==========================================
# 3. TABLERO DE CONTROL (DASHBOARD)
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    if not user: return RedirectResponse("/login")
    
    # Pre-cálculo para evitar errores visuales
    try:
        cant_sentencias = db.query(models.Sentencia).count()
        cant_auditorias = db.query(models.Auditoria).count()
        ultima = db.query(models.Sentencia).order_by(desc(models.Sentencia.fecha_creacion)).first()
        fecha = ultima.fecha_creacion.strftime('%d/%m/%Y') if ultima else "S/D"
    except:
        cant_sentencias, cant_auditorias, fecha = 0, 0, "Error"

    # IMPORTANTE: Usamos 'inicio.html' como pediste
    return templates.TemplateResponse("inicio.html", {
        "request": request, "user": user,
        "stats": {"sentencias": cant_sentencias, "auditorias": cant_auditorias, "actualizacion": fecha}
    })
    # 1. LA LÓGICA DE CUARENTENA VA AQUÍ ADENTRO (Donde 'db' sí existe)
    from datetime import datetime, timedelta
    fecha_limite = datetime.now() - timedelta(days=30)

    # Calculamos cuántas sentencias viejas hay pendientes
    en_cuarentena = db.query(models.Sentencia).filter(
        models.Sentencia.estado == models.EstadoSentencia.PENDIENTE,
        models.Sentencia.fecha_creacion < fecha_limite, # <-- USAMOS TU CAMPO ORIGINAL
        models.Sentencia.dependencia_id == usuario_actual.dependencia_id
    ).count()

    # ... (aquí pueden estar tus otras estadísticas) ...

    # 2. PASAMOS EL DATO A LA PLANTILLA
    return templates.TemplateResponse("inicio.html", {
        "request": request,
        "user": usuario_actual,
        "en_cuarentena": en_cuarentena # Inyectamos la variable para el HTML
    })

# LOCALIZACIÓN: main.py -> app.get("/estado-carga/")
# Reemplazar la lógica de conteo por esta que respeta la multi-dependencia:

@app.get("/estado-carga/")
async def estado_carga(db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    try:
        dep_id = user.dependencia_id
        
        # Consultas con comparación EXPLÍCITA (==) para evitar el error de DatatypeMismatch
        total_sentencias = db.query(models.Sentencia).filter(models.Sentencia.dependencia_id == dep_id).count()
        
        indices = db.query(models.IndiceSentencia)\
            .join(models.Sentencia)\
            .filter(models.Sentencia.dependencia_id == dep_id)\
            .options(joinedload(models.IndiceSentencia.sentencia))\
            .all()

        total_procesadas = len(indices)
        pendientes = max(0, total_sentencias - total_procesadas)
        progreso = round((total_procesadas / total_sentencias) * 100, 1) if total_sentencias > 0 else 0
        
        ultima = db.query(models.Sentencia)\
            .filter(models.Sentencia.dependencia_id == dep_id)\
            .order_by(desc(models.Sentencia.fecha_creacion)).first()
        fecha_str = ultima.fecha_creacion.strftime("%d/%m/%Y %H:%M hs") if ultima else "Sin datos"

        # ... (Tu lógica de contadores de años, tipos y resultados que ya tienes) ...
        # Asegúrate de inicializar los Counter() vacíos antes del bucle
        conteo_anios = Counter()
        conteo_tipos = Counter()
        conteo_resultados = Counter()
        conteo_cruzado = {}
        
        # --- LÓGICA DE CLASIFICACIÓN FINAL (DEPURADA) ---
        for ind in indices:
            # Normalizamos texto
            texto = ((ind.caratula or "") + " " + (ind.voces or "") + " " + (ind.sumario_analitico or "")).lower()
            # 2. TEXTO PARA RESULTADO (Usamos EL FINAL del Texto Original)
            # Tomamos los últimos 3000 caracteres donde suele estar el "RESUELVO"
            texto_fallo = ""
            if ind.sentencia and ind.sentencia.texto_completo:
                texto_fallo = ind.sentencia.texto_completo[-3000:].lower()

            # --- LÓGICA DE TIPOS (TU VERSIÓN DEFINITIVA) ---   
            # DEFAULT: Si no cae en nada específico, es Ordinario (Esto asegura que aparezcan)
            tipo = "LABORAL ORDINARIO ART. 76" 

            # --- NIVEL 1: PROCESOS ESPECÍFICOS ---

            # 1. Recurso Comisión Médica
            if "227" in texto or "comision medica" in texto or "ccmm" in texto:
                tipo = "RECURSO CONTRA DICTAMEN CM ART 227"

            # 2. Accidente Abreviado (Sin "Ley XIII" para evitar falsos positivos)
            elif "223" in texto or "accion especial" in texto or "prestacion" in texto:
                tipo = "ACCIDENTE ABREVIADO ART 223"

            # 3. Laboral Abreviado (CONDICIÓN ESTRICTA: "Laboral" Y "Abreviado" o "202")
            elif "202-" in texto or ("acciones laborales abreviada" in texto):
                tipo = "LABORAL ABREVIADO ART. 202"

            # 4. Tutela Anticipada (NUEVA CATEGORÍA INDEPENDIENTE)
            elif "tutela anticipada" in texto:
                tipo = "TUTELA ANTICIPADA"

            # 5. Sumarísimo CPCC
            elif "466" in texto:
                tipo = "SUMARISIMO ART 466 DEL CPCCFYVF"

            # --- NIVEL 2: GRUPOS TEMÁTICOS ---

            # 6. Honorarios
            elif "honorarios" in texto and ("extrajudicial" in texto or "regulacion" in texto or "sumarisimo" in texto):
                tipo = "REGULACION HONORARIOS EXTRAJUDICIALES"

            # 7. Amparos y Sindicales
            elif "amparo" in texto or "218" in texto or "sindical" in texto or "declarativa" in texto:
                tipo = "ACCION DECLARATIVA Y AMPARO ART. 218"

            # 8. Sumarísimos Laborales
            elif "sumarisimo" in texto or "214" in texto or "213" in texto:
                tipo = "SUMARISIMO ART 214"

            # --- NIVEL 3: ACCIDENTES ORDINARIOS ---
            
            # Si dice "accidente" o "219" y NO entró en el Abreviado (223) de arriba.
            elif "accidente" in texto or "enfermedad" in texto or "219" in texto or "daños" in texto:
                tipo = "ACCIDENTE ORDINARIO ART 219"

            # --- VALIDACIÓN FINAL PARA ORDINARIOS ---
            # Si el tipo sigue siendo el Default, pero tiene palabras de despido/cobro, confirmamos.
            # (No hace falta cambiar nada porque ya es el default, pero sirve de control mental).
            
            # FIN LÓGICA
            
           # --- LÓGICA DE RESULTADOS (VERSIÓN PRECISIÓN QUIRÚRGICA) ---
            resultado = "NO DETERMINADO"
            texto_analisis = ""
            
            if ind.sentencia and ind.sentencia.texto_completo:
                # 1. LIMPIEZA
                texto_analisis = ind.sentencia.texto_completo[-4000:].lower().replace("\n", " ").replace("\r", " ")
                texto_analisis = re.sub(r'\s+', ' ', texto_analisis)

            if texto_analisis:
                # A. PARCIALIDAD (Prioridad Absoluta)
                # Detecta: "parcialmente", "prospera en parte", "procedencia parcial"
                if "parcial" in texto_analisis or "prospera en parte" in texto_analisis:
                    resultado = "ADMITE PARCIALMENTE"
                
                # (Eliminada la categoría Homologación por instrucción)

                # B. ANÁLISIS DE FONDO
                else:
                    es_rechazo = False
                    es_admision = False

                    # LISTA DE OBJETOS: Usamos \b para que 'demanda' no coincida con 'demandada'
                    # Esto es CRÍTICO para evitar errores con "la excepcion de la demandada"
                    objetos = r'(demanda|accion|pretension|reclamo|recurso|regulacion)\b'

                    # --- DETECCIÓN DE RECHAZO ---
                    # Busca: "rechazar... [hasta 120 letras] ... demanda"
                    patron_rechazo = rf'(rechaz\w+|desestim\w+|no hacer lugar).{{0,120}}{objetos}'
                    
                    if re.search(patron_rechazo, texto_analisis):
                        es_rechazo = True
                    
                    if "absolver" in texto_analisis or "caducidad de instancia" in texto_analisis or "declarar perimida" in texto_analisis:
                        es_rechazo = True

                    # --- DETECCIÓN DE ADMISIÓN ---
                    # 1. Hacer lugar (Evitando el "no")
                    match_hl = re.search(rf'hac\w+\s+lugar.{{0,120}}{objetos}', texto_analisis)
                    if match_hl:
                        inicio = match_hl.start()
                        # Miramos 10 caracteres atrás por seguridad
                        if "no " not in texto_analisis[max(0, inicio-10):inicio]:
                            es_admision = True
                    
                    # 2. Condenar (Fuerte indicador de éxito)
                    if "condenar" in texto_analisis or "condenando" in texto_analisis:
                        es_admision = True
                        
                    # 3. Admitir / Prosperar / Acoger
                    patron_admision = rf'(admiti\w+|prospera\w+|acoge\w+).{{0,120}}{objetos}'
                    if re.search(patron_admision, texto_analisis):
                        es_admision = True

                    # --- DEFINICIÓN FINAL ---
                    if es_rechazo and es_admision:
                        resultado = "ADMITE PARCIALMENTE"
                    elif es_rechazo:
                        resultado = "RECHAZA DEMANDA"
                    elif es_admision:
                        resultado = "HACE LUGAR"
            # FIN LÓGICA RESULTADOS
            
            # Acumuladores    
            anio = "S/D"
            if ind.fecha:
                match = re.search(r'\d{4}', ind.fecha)
                if match: anio = match.group(0)
            
            conteo_anios[anio] += 1
            conteo_tipos[tipo] += 1
            conteo_resultados[resultado] += 1 # <--- SUMAR AL CONTADOR
            if anio not in conteo_cruzado: conteo_cruzado[anio] = Counter()
            conteo_cruzado[anio][tipo] += 1

        progreso = round((total_procesadas / total_sentencias) * 100, 1) if total_sentencias > 0 else 0
        
        # ... (dentro de app.get("/estado-carga/"))
        
        return {
            "Estado_IA": "EN LÍNEA",
            "Total_Sentencias": total_sentencias,
            "Pendientes": pendientes,
            "Progreso": progreso,
            "Ultima_Actualizacion": fecha_str,
            "Stats_Anios": dict(sorted(conteo_anios.items())),
            "Stats_Tipos": dict(conteo_tipos.most_common()),
            "Stats_Resultados": dict(conteo_resultados.most_common()),
            "Stats_Cruzadas": conteo_cruzado,
            "dependencia_nombre": user.dependencia.nombre if user.dependencia else "Juzgado Laboral 2"
        }
    except Exception as e:
        db.rollback() 
        import traceback
        print("-" * 50)
        print(f"ERROR CRÍTICO EN DASHBOARD: {e}")
        traceback.print_exc() # Esto te dirá la línea exacta en la terminal
        print("-" * 50)
        
        # Devolvemos TODAS las llaves que inicio.html espera, aunque sea en 0
        return {
            "Total_Sentencias": 0, 
            "Pendientes": 0, 
            "Progreso": 0,
            "Ultima_Actualizacion": f"Fallo: {str(e)[:30]}",
            "Stats_Anios": {}, 
            "Stats_Tipos": {}, 
            "Stats_Resultados": {}, 
            "Stats_Cruzadas": {}, # <--- ESTO FALTABA EN TU EXCEPT Y ROMPE EL JS
            "Estado_IA": "ERROR",
            "dependencia_nombre": "Error de Acceso"
        }

# ==========================================
# 4. AUDITORIA Y CARGA DE ARCHIVOS
# ==========================================

@app.get("/auditoria", response_class=HTMLResponse)
async def pag_auditoria(request: Request, user: models.Usuario = Depends(login_required)):
    return templates.TemplateResponse("auditoria.html", {"request": request, "user": user})

@app.post("/extraer-texto-archivo/")
async def extraer_texto_directo(file: UploadFile = File(...), user: models.Usuario = Depends(login_required)):
    """
    Extrae texto usando las librerías que ya tienes instaladas.
    Soporta PDF (PyMuPDF), Word (python-docx) y ODT (odfpy).
    """
    filename = file.filename.lower()
    content = await file.read()
    texto_extraido = ""

    try:
        # 1. Procesar PDF (PyMuPDF - que instalamos hoy y anduvo)
        if filename.endswith(".pdf"):
            with fitz.open(stream=content, filetype="pdf") as doc:
                for page in doc:
                    texto_extraido += page.get_text() + "\n"
        
        # 2. Procesar WORD (python-docx - que tenías en tu backup)
        elif filename.endswith(".docx"):
            doc = docx.Document(io.BytesIO(content))
            for para in doc.paragraphs:
                texto_extraido += para.text + "\n"

        # 3. Procesar OPENOFFICE (odfpy - que tenías en tu backup)
        elif filename.endswith(".odt"):
            odt_doc = load(io.BytesIO(content))
            allparagraphs = odt_doc.getElementsByType(odf_text.P)
            for p in allparagraphs:
                texto_extraido += teletype.extractText(p) + "\n"

        # 4. Procesar TXT
        elif filename.endswith(".txt"):
            texto_extraido = content.decode("utf-8", errors="ignore")
        
        else:
            return JSONResponse(status_code=400, content={"error": "Formato no soportado. Use PDF, DOCX o ODT."})

        if not texto_extraido.strip():
            return JSONResponse(status_code=400, content={"error": "El archivo parece estar vacío o es una imagen."})

        return {"texto": texto_extraido}

    except Exception as e:
        # Debug: Imprimir error en consola para saber qué librería falló
        print(f"Error lectura ({filename}): {e}")
        return JSONResponse(status_code=500, content={"error": f"Error leyendo el archivo: {str(e)}"})

from pydantic import BaseModel
class SolicitudAuditoria(BaseModel):
    texto: str
    nombre_archivo: str

@app.post("/api/auditar")
async def procesar_auditoria(solicitud: SolicitudAuditoria, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    resultado = auditor.ejecutar_auditoria(client, db, solicitud.texto, solicitud.nombre_archivo)
    
    if resultado.get("id_auditoria") and resultado["id_auditoria"] > 0:
        aud_db = db.query(models.Auditoria).filter(models.Auditoria.id == resultado["id_auditoria"]).first()
        if aud_db:
            aud_db.usuario = user.username
            db.commit()
    return resultado

@app.get("/historial", response_class=HTMLResponse)
async def ver_historial(request: Request, orden: str = "fecha", db: Session = Depends(get_db), user: models.Usuario = Depends(login_required)):
    query = db.query(models.Auditoria)
    if orden == "usuario": query = query.order_by(models.Auditoria.usuario.asc(), models.Auditoria.fecha.desc())
    else: query = query.order_by(models.Auditoria.fecha.desc())
    return templates.TemplateResponse("historial.html", {"request": request, "auditorias": query.limit(50).all(), "orden_actual": orden, "user": user})

@app.get("/api/auditoria/{id_auditoria}")
async def obtener_detalle(id_auditoria: int, db: Session = Depends(get_db), user: models.Usuario = Depends(login_required)):
    aud = db.query(models.Auditoria).filter(models.Auditoria.id == id_auditoria).first()
    return {"informe": aud.resultado_analisis} if aud else {"error": "No encontrada"}

@app.delete("/api/auditoria/{id_auditoria}")
async def eliminar_auditoria(id_auditoria: int, db: Session = Depends(get_db), user: models.Usuario = Depends(login_required)):
    if user.rol != "juez": return JSONResponse(status_code=403, content={"error": "Permiso denegado"})
    aud = db.query(models.Auditoria).filter(models.Auditoria.id == id_auditoria).first()
    if aud:
        db.delete(aud)
        db.commit()
    return {"mensaje": "Eliminado"}

from pydantic import BaseModel

# 1. PRIMERO DEFINIMOS LA CLASE (Esto arregla el NameError)
class ConsultaJuridica(BaseModel):
    pregunta: str
# Esta es la ruta exacta que usa tu relator.html
@app.post("/consultar-jurisprudencia/")
async def consultar_relator_endpoint(
    datos: ConsultaJuridica, 
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(login_required)
):
    if not client_ai:
        return {
            "respuesta": "Error crítico: La IA no se inició correctamente al arrancar el servidor (Verifique API KEY al inicio).", 
            "casos_usados": []
        }
    # Llamada al relator modificado
    texto_resp, lista_fallos = relator.analizar_consulta(client_ai, db, datos.pregunta)
    
    return {
        "respuesta": texto_resp,
        "casos_usados": lista_fallos 
    }

# ==========================================
# 5. REGLAS DE ESTILO (BIBLIOTECA)
# ==========================================

@app.get("/biblioteca", response_class=HTMLResponse)
async def ver_biblioteca(request: Request, db: Session = Depends(get_db), user: models.Usuario = Depends(login_required)):
    reglas = db.query(models.ReglaEstilo).order_by(models.ReglaEstilo.id.desc()).all()
    # Usamos 'biblioteca.html'
    return templates.TemplateResponse("biblioteca.html", {"request": request, "reglas": reglas, "user": user})

@app.post("/api/reglas")
async def crear_regla(categoria: str = Form(...), regla: str = Form(...), explicacion: str = Form(...), db: Session = Depends(get_db), user: models.Usuario = Depends(login_required)):
    try:
        nueva = models.ReglaEstilo(categoria=categoria, regla=regla, explicacion=explicacion)
        db.add(nueva)
        db.commit()
        return RedirectResponse("/biblioteca", status_code=303)
    except Exception as e:
        print(f"Error creando regla: {e}")
        return JSONResponse(status_code=500, content={"error": "No se pudo guardar la regla"})

@app.post("/api/borrar_regla/{id_regla}")
async def borrar_regla(id_regla: int, db: Session = Depends(get_db), user: models.Usuario = Depends(login_required)):
    r = db.query(models.ReglaEstilo).filter(models.ReglaEstilo.id == id_regla).first()
    if r:
        db.delete(r)
        db.commit()
    return RedirectResponse("/biblioteca", status_code=303)

# ==========================================
# 6. RELATOR IA Y BUSCADOR
# ==========================================

@app.get("/buscar/")
async def buscar(request: Request, q: str = "", db: Session = Depends(get_db), user: models.Usuario = Depends(login_required)):
    # Inyectamos clave al buscador
    buscador_semantico.client = client_ai 
    res = buscador_semantico.buscar_similar(db, q) if q else []
    return templates.TemplateResponse("resultados.html", {"request": request, "resultados": res, "query": q, "user": user})

@app.get("/relatoria", response_class=HTMLResponse)
async def pag_relatoria(request: Request, user: models.Usuario = Depends(login_required)):
    # Usamos 'relator.html'
    return templates.TemplateResponse("relator.html", {"request": request, "user": user})

@app.post("/api/relatar")
async def consultar_relator_api(consulta: str = Form(...), db: Session = Depends(get_db), user: models.Usuario = Depends(login_required)):
    if not client_ai:
        return {"respuesta": "Error: API Key de IA no configurada o inválida."}

    try:
        # Usa tu función 'investigar_y_responder' del archivo 'relator.py'
        respuesta = relator.investigar_y_responder(client_ai, db, consulta)
    except Exception as e:
        print(f"Error Relator: {e}")
        respuesta = f"Error interno: {str(e)}. Intente reformular."
            
    return {"respuesta": respuesta}
from pydantic import BaseModel

class ConsultaJuridica(BaseModel):
    pregunta: str

@app.post("/consultar-jurisprudencia/")
async def consultar_relator_endpoint(
    datos: ConsultaJuridica, 
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(login_required)
):
    if not client_ai:
        return {"respuesta": "Error: API Key no configurada en el servidor.", "casos_usados": []}

    # 1. Llamamos al cerebro del relator
    texto_resp, lista_fallos = relator.analizar_consulta(client_ai, db, datos.pregunta)
    
    # 2. Devolvemos los datos EXACTAMENTE como los espera relator.html
    return {
        "respuesta": texto_resp,
        "casos_usados": lista_fallos  # CORRECCIÓN: Antes se llamaba 'referencias' y el HTML no lo leía
    }
from pydantic import BaseModel

class ConsultaPublica(BaseModel):
    consulta: str
    juzgado: str = "Todos"

@app.post("/api/buscar-publico")
def api_buscar_publico(datos: ConsultaPublica, db: Session = Depends(get_db)):
    """
    Ruta ABIERTA. No requiere Depends(get_current_user).
    Alimentará la Landing Page con las tarjetas de resultados.
    """
    try:
        # Instanciamos el cliente de Gemini de forma segura
        import os
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="API Key no configurada")
            
        cliente_ai = genai.Client(api_key=api_key)
        
        resultado = buscador_publico.buscar_jurisprudencia_publica(
            cliente_ai=cliente_ai, 
            db=db, 
            consulta=datos.consulta, 
            juzgado_filtro=datos.juzgado
        )
        
        if resultado["error"]:
            raise HTTPException(status_code=503, detail=resultado["error"])
            
        return resultado["tarjetas"]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # En la ruta de creación de usuarios (/api/usuarios/crear)

class NuevoUsuarioDef(BaseModel):
        username: str
        password: str
        rol: str
        dependencia_id: int = None  # Nuevo campo necesario para la lógica que mencionas

@app.post("/api/usuarios/crear")
def api_crear_usuario(
    datos: NuevoUsuarioDef, 
    db: Session = Depends(get_db), 
    admin_user: models.Usuario = Depends(get_current_user)
    ):
    # 1. Definir permisos
    permisos = {
        "superadmin": ["juez", "secretario_adm", "secretario"],
        "juez": ["secretario_adm", "secretario"],
        "secretario_adm": ["secretario"]
    }
    # ... validaciones de rol ...

    if datos.rol not in permisos.get(admin_user.rol, []):
        raise HTTPException(status_code=403, detail="Permisos insuficientes")

    # 2. Definir la variable dependencia_destino (Soluciona el error de definición)
    if admin_user.rol == "superadmin":
        dependencia_destino = datos.dependencia_id
    else:
        dependencia_destino = admin_user.dependencia_id

    # 3. Guardar (Aquí usamos admin_user.username para la auditoría)
    clave_segura = pwd_context.hash(datos.password)
    nuevo = models.Usuario(
        username=datos.username,
        hashed_password=clave_segura,
        rol=datos.rol,
        dependencia_id=dependencia_destino # Aquí ya está definida
    )
    db.add(nuevo)
    
    # Registro de auditoría usando admin_user (el que está logueado)
    auditoria = models.Auditoria(
        usuario=admin_user.username, 
        nombre_archivo="SISTEMA_ADMIN",
        resultado_analisis=f"Alta de {datos.username} en dep {dependencia_destino}"
    )
    db.add(auditoria)
    db.commit()
    return {"mensaje": "Cuenta institucional provisionada correctamente."}

class ValidacionSentenciaRequest(BaseModel):
        texto_editado: str # El humano envía el texto corregido aquí

@app.post("/biblioteca/validar/{sentencia_id}")
async def validar_y_vectorizar(
    sentencia_id: int, 
    payload: ValidacionSentenciaRequest,
    db: Session = Depends(get_db), 
    usuario_actual: models.Usuario = Depends(get_current_user)
):
    # 1. CONTROL DE ACCESO (Auditoría)
    if usuario_actual.rol not in ["juez", "secretario", "secretario_adm"]:
        raise HTTPException(status_code=403, detail="Acceso denegado. Se requiere Nivel 1 o 2.")

    # Buscamos la sentencia
    sentencia = db.query(models.Sentencia).filter(models.Sentencia.id == sentencia_id).first()
    if not sentencia:
        raise HTTPException(status_code=404, detail="Sentencia no encontrada.")

    # 2. IDEMPOTENCIA (Auditoría)
    if sentencia.estado == models.EstadoSentencia.APROBADO:
        raise HTTPException(status_code=400, detail="Esta sentencia ya fue aprobada y vectorizada.")

    # 3. VALIDACIÓN DE DEPENDENCIA (Gobernanza)
    if sentencia.dependencia_id != usuario_actual.dependencia_id:
        raise HTTPException(status_code=403, detail="Violación de seguridad: No puedes validar fallos de otro juzgado.")

    try:
        # 4. TRAZABILIDAD DE EDICIÓN HUMANA (Tu requerimiento)
        if payload.texto_editado != sentencia.texto_anonimizado:
            # Si el humano modificó el texto, guardamos el registro forense
            log_correccion = models.LogAnonimizacion(
                sentencia_id=sentencia.id,
                usuario_id=usuario_actual.id,
                texto_ia_original=sentencia.texto_anonimizado,
                texto_humano_corregido=payload.texto_editado
            )
            db.add(log_correccion)
            # Actualizamos la sentencia con el texto limpio definitivo
            sentencia.texto_anonimizado = payload.texto_editado

        # 5. GENERACIÓN DE ÍNDICE Y VECTORES (IA sobre texto corregido)
        # Aquí el bibliotecario/agente IA entra en acción usando el texto_editado
        prompt = f"""
        Analiza esta sentencia laboral estrictamente anonimizada:
        {sentencia.texto_anonimizado[:15000]} 
        
        Genera un JSON con "voces", "sumario_analitico" (sin nombres propios) y "fecha".
        """
        
        resp_ia = client.models.generate_content(
            model="gemini-2.0-flash-lite", contents=prompt, config={'response_mime_type': 'application/json'}
        )
        data_ia = resp_ia.parsed

        texto_vector = f"Temas: {data_ia.get('voces')}. Resumen: {data_ia.get('sumario_analitico')}"
        resp_emb = client.models.embed_content(model="models/text-embedding-004", contents=texto_vector)
        vector_nuevo = resp_emb.embeddings[0].values

        # 6. GUARDADO FINAL Y CAMBIO DE ESTADO
        nuevo_indice = models.IndiceSentencia(
            sentencia_id=sentencia.id,
            caratula=sentencia.caratula_real, # Protegido en Nivel 3
            fecha=data_ia.get('fecha'),
            voces=data_ia.get('voces'),
            sumario_analitico=data_ia.get('sumario_analitico'),
            vector_embedding=vector_nuevo
        )
        db.add(nuevo_indice)
        
        # Aprobamos y firmamos
        sentencia.estado = models.EstadoSentencia.APROBADO
        sentencia.usuario_validador_id = usuario_actual.id

        # Auditoría General
        log_admin = models.Auditoria(
            usuario=usuario_actual.username,
            accion="Validación y Vectorización",
            detalle=f"Aprobó sentencia UUID: {sentencia.uuid_seguro}"
        )
        db.add(log_admin)

        db.commit()
        return {"status": "success", "message": "Sentencia aprobada, corregida e indexada exitosamente."}

    except Exception as e:
        # FAIL-SAFE: Si Gemini falla, hacemos rollback y queda en PENDIENTE
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error en procesamiento IA: {str(e)}")

        # GET con prevención de caché (Exigencia del Auditor)
@app.get("/biblioteca/validar/{sentencia_id}")
async def obtener_texto_para_validar(
    sentencia_id: int, 
    response: Response, # Inyectamos Response para modificar headers
    db: Session = Depends(get_db), 
    usuario_actual: models.Usuario = Depends(get_current_user)
):
    if usuario_actual.rol not in ["juez", "secretario"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
        
    sentencia = db.query(models.Sentencia).filter(models.Sentencia.id == sentencia_id).first()
    
    # POLÍTICA STRICT NO-CACHE (Previene exposición de Texto Original)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    return {
        "texto_original": sentencia.texto_completo,
        "texto_anonimizado": sentencia.texto_anonimizado
    }

# Botón de Pánico: Borrado Lógico
@app.delete("/biblioteca/sentencia/{sentencia_id}")
async def borrado_logico(
    sentencia_id: int, 
    db: Session = Depends(get_db), 
    usuario_actual: models.Usuario = Depends(get_current_user)
):
    # Solo el juez puede borrar fallos
    if usuario_actual.rol != "juez":
        raise HTTPException(status_code=403, detail="Solo el Juez puede eliminar sentencias.")
        
    sentencia = db.query(models.Sentencia).filter(models.Sentencia.id == sentencia_id).first()
    if sentencia:
        # BORRADO LÓGICO
        sentencia.estado = models.EstadoSentencia.ELIMINADO
        
        # Eliminamos el vector de la tabla de índices para que desaparezca de las búsquedas
        db.query(models.IndiceSentencia).filter(models.IndiceSentencia.sentencia_id == sentencia_id).delete()
        
        log_borrado = models.Auditoria(
            usuario=usuario_actual.username, accion="Borrado Lógico", detalle=f"Eliminó UUID {sentencia.uuid_seguro}"
        )
        db.add(log_borrado)
        db.commit()
        
    return {"message": "Sentencia eliminada del índice público correctamente."}