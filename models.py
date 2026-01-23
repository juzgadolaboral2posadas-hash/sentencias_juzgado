from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship, declarative_base
from pgvector.sqlalchemy import Vector
from datetime import datetime 

Base = declarative_base()

# 1. TABLA DE USUARIOS (NUEVA)
class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True) # Ej: "Juez_Garcia"
    hashed_password = Column(String)                   # Contraseña encriptada
    rol = Column(String, default="secretario")         # "juez" o "secretario"
    activo = Column(Boolean, default=True)

# 2. TABLA DE SENTENCIAS
class Sentencia(Base):
    __tablename__ = "sentencias"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    id_drive = Column(String, unique=True, index=True)
    link_web = Column(String)
    anio_carpeta = Column(String)
    texto_completo = Column(Text)
    fecha_creacion = Column(DateTime, default=datetime.now)

    indice = relationship("IndiceSentencia", back_populates="sentencia", uselist=False)

# 3. TABLA DE ÍNDICES
class IndiceSentencia(Base):
    __tablename__ = "indices_sentencia"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    sentencia_id = Column(Integer, ForeignKey("sentencias.id"))
    caratula = Column(String)
    fecha = Column(String)
    voces = Column(Text)
    sumario_analitico = Column(Text)
    vector_embedding = Column(Vector(768))

    sentencia = relationship("Sentencia", back_populates="indice")

# 4. TABLA DE REGLAS DE ESTILO
class ReglaEstilo(Base):
    __tablename__ = "reglas_estilo"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    categoria = Column(String)
    regla = Column(String)
    explicacion = Column(String)
    fecha_creacion = Column(DateTime, default=datetime.now)

# 5. TABLA DE AUDITORÍAS
class Auditoria(Base):
    __tablename__ = "auditorias"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime, default=datetime.now)
    usuario = Column(String) # Guardamos el nombre del usuario que hizo la auditoría
    nombre_archivo = Column(String)
    resultado_analisis = Column(String)
    validado = Column(Boolean, default=False)