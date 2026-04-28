from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship, declarative_base
from pgvector.sqlalchemy import Vector
from datetime import datetime 
import enum

Base = declarative_base()

# 1. TABLA DE DEPENDENCIAS (Única definición)
class Dependencia(Base):
    __tablename__ = "dependencias"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True) 
    jurisdiccion = Column(String)                    
    
    # Relación inversa: permite saber qué usuarios pertenecen a esta dependencia
    usuarios = relationship("Usuario", back_populates="dependencia")
    # Relación inversa: permite saber qué sentencias pertenecen a esta dependencia
    sentencias = relationship("Sentencia", back_populates="dependencia")

# 2. TABLA DE USUARIOS
class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True) 
    hashed_password = Column(String)                   
    rol = Column(String, default="secretario") 
    dependencia_id = Column(Integer, ForeignKey("dependencias.id"), nullable=True)        
    activo = Column(Boolean, default=True)

    dependencia = relationship("Dependencia", back_populates="usuarios")

# 3. TABLA DE SENTENCIAS (Con Anonimización) (SE UNIFICO)

# 1. Agregamos los estados permitidos
class EstadoSentencia(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    ELIMINADO = "ELIMINADO"

# 2. Tu clase Sentencia intacta + los nuevos campos de estado
class Sentencia(Base):
    __tablename__ = "sentencias"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    uuid_seguro = Column(String, unique=True, index=True) 
    
    dependencia_id = Column(Integer, ForeignKey("dependencias.id"), index=True)
    tipo_resolucion = Column(String, default="Sentencia Definitiva", index=True) 
    
    caratula_real = Column(String)
    nro_expediente = Column(String)
    texto_anonimizado = Column(Text) 
    
    id_drive = Column(String, unique=True, index=True)
    link_web = Column(String)
    anio_carpeta = Column(String)
    
    texto_completo = Column(Text, nullable=True) 
    fecha_creacion = Column(DateTime, default=datetime.now)
    juzgado_origen = Column(String, nullable=True)

    # --- NUEVOS CAMPOS (Validación Humana) ---
    estado = Column(SQLEnum(EstadoSentencia), default=EstadoSentencia.PENDIENTE, index=True)
    usuario_validador_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    dependencia = relationship("Dependencia", back_populates="sentencias")
    indice = relationship("IndiceSentencia", back_populates="sentencia", uselist=False)

# 4. TABLA DE ÍNDICES (Vector de alta dimensionalidad)
class IndiceSentencia(Base):
    __tablename__ = "indices_sentencia"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    sentencia_id = Column(Integer, ForeignKey("sentencias.id"))
    caratula = Column(String)
    fecha = Column(String)
    voces = Column(Text)
    sumario_analitico = Column(Text)
    vector_embedding = Column(Vector(3072)) 

    sentencia = relationship("Sentencia", back_populates="indice")

# 5. TABLA DE REGLAS DE ESTILO
class ReglaEstilo(Base):
    __tablename__ = "reglas_estilo"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    categoria = Column(String)
    regla = Column(String)
    explicacion = Column(String)
    fecha_creacion = Column(DateTime, default=datetime.now)

# 6. TABLA DE AUDITORÍAS
class Auditoria(Base):
    __tablename__ = "auditorias"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime, default=datetime.now)
    usuario = Column(String) 
    nombre_archivo = Column(String)
    resultado_analisis = Column(String)
    validado = Column(Boolean, default=False)