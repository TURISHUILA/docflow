from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Form, status, Header
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
import io
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
from PIL import Image
import json
import tempfile

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

# Emergent LLM Key
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

app = FastAPI()
api_router = APIRouter(prefix="/api")

# Models
class UserRole:
    ADMIN = "admin"
    OPERATIVO = "operativo"
    REVISOR = "revisor"

class DocumentType:
    COMPROBANTE_EGRESO = "comprobante_egreso"
    CUENTA_POR_PAGAR = "cuenta_por_pagar"
    FACTURA = "factura"
    SOPORTE_PAGO = "soporte_pago"

class DocumentStatus:
    CARGADO = "cargado"  # blue
    EN_PROCESO = "en_proceso"  # yellow
    TERMINADO = "terminado"  # green
    REVISION = "revision"  # red

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    nombre: str
    role: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True

class UserCreate(BaseModel):
    email: EmailStr
    nombre: str
    password: str
    role: str = UserRole.OPERATIVO

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    tipo_documento: str
    batch_id: Optional[str] = None
    status: str = DocumentStatus.CARGADO
    uploaded_by: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    file_size: int
    mime_type: str
    # Datos extraídos
    valor: Optional[float] = None
    fecha: Optional[str] = None
    concepto: Optional[str] = None
    tercero: Optional[str] = None
    referencia_bancaria: Optional[str] = None
    analisis_completo: Optional[Dict[str, Any]] = None

class DocumentBatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = DocumentStatus.EN_PROCESO
    documentos: List[str] = []  # IDs de documentos
    pdf_generado_id: Optional[str] = None
    requiere_revision: bool = False
    mensaje_revision: Optional[str] = None

class ConsolidatedPDF(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    batch_id: str
    filename: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str
    file_size: int

class AuditLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    user_email: str
    action: str
    details: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Helper Functions
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(authorization: str = Header(None)) -> User:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="No autorizado")
    
    token = authorization.replace('Bearer ', '')
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
        if not user_doc:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        
        return User(**user_doc)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

async def log_action(user: User, action: str, details: str):
    log = AuditLog(
        user_id=user.id,
        user_email=user.email,
        action=action,
        details=details
    )
    doc = log.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.audit_logs.insert_one(doc)

async def analyze_document_with_gpt(file_path: str, mime_type: str) -> Dict[str, Any]:
    """Analiza un documento usando Gemini para extraer información y correlacionar.
    IMPORTANTE: FileContentWithMimeType solo funciona con Gemini provider."""
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=str(uuid.uuid4()),
            system_message="""Eres un experto en análisis de documentos contables y financieros colombianos.
Tu tarea es extraer información EXACTA y PRECISA de documentos de pago.
REGLAS CRÍTICAS:
1. El TERCERO y el NIT deben corresponder al mismo beneficiario/proveedor
2. El VALOR debe ser el monto total exacto del documento
3. NO inventes datos - si no puedes leer algo claramente, usa null
4. Lee TODO el documento antes de responder"""
        ).with_model("gemini", "gemini-2.5-flash")
        
        file_content = FileContentWithMimeType(
            file_path=file_path,
            mime_type=mime_type
        )
        
        prompt = """ANALIZA CUIDADOSAMENTE este documento financiero colombiano.

INSTRUCCIONES IMPORTANTES:
1. Lee COMPLETAMENTE el documento antes de extraer datos
2. El TERCERO es el beneficiario/proveedor que RECIBE el pago (no quien paga)
3. El NIT debe corresponder EXACTAMENTE al TERCERO mencionado
4. El VALOR es el monto TOTAL a pagar (busca "VALOR TOTAL", "TOTAL A PAGAR", "NETO A PAGAR")
5. Si hay varios valores, usa el TOTAL final

CAMPOS A EXTRAER - Responde SOLO con este JSON:
{
    "tipo_documento": "comprobante_egreso" | "cuenta_por_pagar" | "factura" | "soporte_pago",
    "numero_documento": "número exacto del documento (CE-XXXX, CXP-XXXX, FV-XXXX)",
    "valor": 0.00,
    "fecha": "YYYY-MM-DD",
    "tercero": "NOMBRE COMPLETO DEL BENEFICIARIO/PROVEEDOR",
    "nit": "NIT o cédula del tercero (solo números y guión de verificación)",
    "concepto": "descripción o concepto del pago",
    "referencia_bancaria": "referencia si es transferencia bancaria",
    "banco": "nombre del banco si aplica"
}

VALIDACIONES:
- Si el tercero es "AVIANCA", el NIT debe ser de Avianca (890903407)
- Si el tercero es una persona natural, el NIT será su cédula
- El valor debe ser un número positivo sin símbolos de moneda
- La fecha debe estar en formato YYYY-MM-DD

Si un campo no se puede determinar con certeza, usa null.
Responde ÚNICAMENTE con el JSON, sin explicaciones adicionales."""
        
        message = UserMessage(
            text=prompt,
            file_contents=[file_content]
        )
        
        response = await chat.send_message(message)
        
        # Limpiar y parsear respuesta
        response_clean = response.strip()
        
        # Intentar extraer JSON de la respuesta
        import re
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_clean, re.DOTALL)
        
        if json_match:
            data = json.loads(json_match.group())
            
            # Validar y limpiar datos
            if data.get('valor'):
                # Limpiar valor (remover comas, símbolos, puntos de miles)
                valor_str = str(data['valor']).replace(',', '').replace('$', '').replace(' ', '')
                # Si tiene punto como separador de miles (ej: 1.000.000), removerlo
                if valor_str.count('.') > 1:
                    valor_str = valor_str.replace('.', '')
                try:
                    data['valor'] = float(valor_str)
                except:
                    data['valor'] = None
            
            # Normalizar tercero (mayúsculas, sin espacios extras)
            if data.get('tercero'):
                data['tercero'] = ' '.join(data['tercero'].upper().split())
            
            # Limpiar NIT (solo números y guión)
            if data.get('nit'):
                nit_str = str(data['nit']).replace('.', '').replace(' ', '')
                data['nit'] = nit_str
            
            return data
        else:
            logging.warning(f"No se pudo parsear JSON de Gemini: {response_clean[:200]}")
            return {"raw_response": response_clean, "error": "No se pudo extraer JSON de la respuesta"}
            
    except Exception as e:
        logging.error(f"Error analyzing document: {str(e)}")
        return {"error": str(e)}

async def analyze_pdf_page(page_path: str, page_num: int) -> Dict[str, Any]:
    """Analiza una página individual de un PDF para extraer información"""
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=str(uuid.uuid4()),
            system_message="""Eres un experto en análisis de documentos contables colombianos.
Analiza esta página/imagen de un documento financiero y extrae la información.
Si la página contiene un documento válido (factura, comprobante, soporte de pago, etc.), extrae los datos.
Si la página está en blanco, es una portada, o no contiene información financiera relevante, indica que no es válida."""
        ).with_model("gemini", "gemini-2.5-flash")
        
        file_content = FileContentWithMimeType(
            file_path=page_path,
            mime_type="application/pdf"
        )
        
        prompt = """Analiza esta página de un documento financiero.

PRIMERO determina si esta página contiene un documento financiero válido:
- ¿Es una factura, comprobante de egreso, cuenta por pagar, o soporte de pago?
- ¿Contiene información de tercero/beneficiario y valor?
- ¿O es una página en blanco, portada, índice, o sin información relevante?

Responde con este JSON:
{
    "es_documento_valido": true o false,
    "tipo_documento": "comprobante_egreso" | "cuenta_por_pagar" | "factura" | "soporte_pago" | "otro" | null,
    "numero_documento": "número del documento si existe",
    "valor": número decimal o null,
    "fecha": "YYYY-MM-DD" o null,
    "tercero": "NOMBRE DEL BENEFICIARIO/PROVEEDOR" o null,
    "nit": "NIT o cédula" o null,
    "concepto": "descripción del pago" o null,
    "referencia_bancaria": "referencia si existe" o null,
    "banco": "nombre del banco si aplica" o null,
    "descripcion_pagina": "breve descripción de qué contiene esta página"
}

Si no es un documento válido, solo incluye:
{
    "es_documento_valido": false,
    "descripcion_pagina": "descripción de qué contiene (ej: página en blanco, portada, etc.)"
}"""
        
        message = UserMessage(
            text=prompt,
            file_contents=[file_content]
        )
        
        response = await chat.send_message(message)
        response_clean = response.strip()
        
        import re
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_clean, re.DOTALL)
        
        if json_match:
            data = json.loads(json_match.group())
            data['page_number'] = page_num
            
            # Limpiar valor
            if data.get('valor'):
                valor_str = str(data['valor']).replace(',', '').replace('$', '').replace(' ', '')
                if valor_str.count('.') > 1:
                    valor_str = valor_str.replace('.', '')
                try:
                    data['valor'] = float(valor_str)
                except:
                    data['valor'] = None
            
            # Normalizar tercero
            if data.get('tercero'):
                data['tercero'] = ' '.join(data['tercero'].upper().split())
            
            return data
        else:
            return {"es_documento_valido": False, "page_number": page_num, "error": "No se pudo analizar"}
            
    except Exception as e:
        logging.error(f"Error analyzing page {page_num}: {str(e)}")
        return {"es_documento_valido": False, "page_number": page_num, "error": str(e)}

def split_pdf_to_pages(pdf_data: bytes) -> List[bytes]:
    """Divide un PDF en páginas individuales, cada una como bytes de PDF"""
    pages = []
    try:
        reader = PdfReader(io.BytesIO(pdf_data))
        for page_num in range(len(reader.pages)):
            writer = PdfWriter()
            writer.add_page(reader.pages[page_num])
            
            page_buffer = io.BytesIO()
            writer.write(page_buffer)
            page_buffer.seek(0)
            pages.append(page_buffer.read())
    except Exception as e:
        logging.error(f"Error splitting PDF: {str(e)}")
    return pages

# Auth Endpoints
@api_router.post("/auth/register", response_model=User)
async def register(user_data: UserCreate, authorization: str = Header(None)):
    # Solo admin puede crear usuarios
    current_user = await get_current_user(authorization) if authorization else None
    if current_user and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Solo administradores pueden crear usuarios")
    
    # Verificar si el email ya existe
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    
    user = User(
        email=user_data.email,
        nombre=user_data.nombre,
        role=user_data.role
    )
    
    doc = user.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['password'] = hash_password(user_data.password)
    
    await db.users.insert_one(doc)
    
    if current_user:
        await log_action(current_user, "CREATE_USER", f"Creado usuario {user.email}")
    
    return user

@api_router.post("/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    user_doc = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    
    if not verify_password(credentials.password, user_doc['password']):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    
    user_doc.pop('password')
    user = User(**user_doc)
    
    access_token = create_access_token(data={"sub": user.id})
    
    return Token(access_token=access_token, token_type="bearer", user=user)

@api_router.get("/auth/me", response_model=User)
async def get_me(authorization: str = Header(None)):
    return await get_current_user(authorization)

# Document Endpoints
@api_router.post("/documents/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    tipo_documento: str = Form(...),
    authorization: str = Header(None)
):
    user = await get_current_user(authorization)
    
    # Validaciones
    MAX_FILES = 20
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_TOTAL_SIZE = 100 * 1024 * 1024  # 100MB
    
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Máximo {MAX_FILES} archivos permitidos por carga")
    
    total_size = sum(file.size for file in files if hasattr(file, 'size'))
    if total_size > MAX_TOTAL_SIZE:
        raise HTTPException(status_code=400, detail="El tamaño total excede 100MB")
    
    uploaded_docs = []
    
    for file in files:
        # Validar tamaño individual
        file_data = await file.read()
        if len(file_data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400, 
                detail=f"El archivo {file.filename} excede el tamaño máximo de 10MB"
            )
        
        # Guardar archivo en MongoDB GridFS
        file_id = str(uuid.uuid4())
        
        # Guardar temporalmente para análisis
        temp_path = f"/tmp/{file_id}_{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(file_data)
        
        # Crear metadata del documento
        doc_metadata = DocumentMetadata(
            filename=file.filename,
            tipo_documento=tipo_documento,
            uploaded_by=user.id,
            file_size=len(file_data),
            mime_type=file.content_type or "application/octet-stream"
        )
        
        # Guardar en MongoDB
        metadata_dict = doc_metadata.model_dump()
        metadata_dict['uploaded_at'] = metadata_dict['uploaded_at'].isoformat()
        metadata_dict['file_data'] = file_data
        
        await db.documents.insert_one(metadata_dict)
        
        uploaded_docs.append({
            "id": doc_metadata.id,
            "filename": doc_metadata.filename,
            "status": doc_metadata.status
        })
        
        # Limpiar archivo temporal
        try:
            os.remove(temp_path)
        except:
            pass
    
    await log_action(user, "UPLOAD_DOCUMENTS", f"Subidos {len(files)} documentos tipo {tipo_documento}")
    
    return {"uploaded": len(uploaded_docs), "documents": uploaded_docs}

@api_router.get("/documents/list")
async def list_documents(authorization: str = Header(None), status: Optional[str] = None):
    user = await get_current_user(authorization)
    
    query = {}
    if status:
        query['status'] = status
    
    docs = await db.documents.find(query, {"_id": 0, "file_data": 0}).to_list(1000)
    
    return {"documents": docs}

@api_router.post("/documents/{doc_id}/analyze")
async def analyze_document(doc_id: str, authorization: str = Header(None)):
    """
    Analiza un documento con IA. Si es un PDF multipágina, lo divide automáticamente
    y analiza cada página por separado.
    """
    user = await get_current_user(authorization)
    
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    # Verificar si es PDF y tiene múltiples páginas
    is_pdf = doc.get('filename', '').lower().endswith('.pdf') or doc.get('mime_type', '').lower().endswith('pdf')
    
    if is_pdf and not doc.get('parent_document_id') and not doc.get('split_into'):
        # Verificar número de páginas
        try:
            reader = PdfReader(io.BytesIO(doc['file_data']))
            num_pages = len(reader.pages)
            
            if num_pages > 1:
                # Dividir automáticamente el PDF multipágina
                pages_data = split_pdf_to_pages(doc['file_data'])
                created_docs = []
                skipped_pages = []
                
                for page_num, page_data in enumerate(pages_data, 1):
                    temp_path = f"/tmp/page_{doc_id}_{page_num}.pdf"
                    with open(temp_path, "wb") as f:
                        f.write(page_data)
                    
                    # Analizar página con IA
                    analysis = await analyze_pdf_page(temp_path, page_num)
                    
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                    
                    # Si la página contiene un documento válido
                    if analysis.get('es_documento_valido', False) and (analysis.get('tercero') or analysis.get('valor')):
                        new_doc_id = str(uuid.uuid4())
                        original_name = doc['filename'].replace('.pdf', '').replace('.PDF', '')
                        
                        new_doc = {
                            "id": new_doc_id,
                            "filename": f"{original_name}_pag{page_num}.pdf",
                            "tipo_documento": analysis.get('tipo_documento') or doc.get('tipo_documento'),
                            "uploaded_by": user.id,
                            "file_size": len(page_data),
                            "mime_type": "application/pdf",
                            "status": DocumentStatus.EN_PROCESO,
                            "uploaded_at": datetime.now(timezone.utc).isoformat(),
                            "file_data": page_data,
                            "parent_document_id": doc_id,
                            "page_number": page_num,
                            "valor": analysis.get('valor'),
                            "tercero": analysis.get('tercero'),
                            "nit": analysis.get('nit'),
                            "fecha": analysis.get('fecha'),
                            "concepto": analysis.get('concepto'),
                            "numero_documento": analysis.get('numero_documento'),
                            "referencia_bancaria": analysis.get('referencia_bancaria'),
                            "banco": analysis.get('banco'),
                            "analisis_completo": analysis
                        }
                        
                        await db.documents.insert_one(new_doc)
                        created_docs.append({
                            "id": new_doc_id,
                            "filename": new_doc['filename'],
                            "page_number": page_num,
                            "tercero": analysis.get('tercero'),
                            "valor": analysis.get('valor')
                        })
                    else:
                        skipped_pages.append(page_num)
                
                # Marcar documento original como dividido
                await db.documents.update_one(
                    {"id": doc_id},
                    {"$set": {
                        "status": "dividido",
                        "split_into": [d['id'] for d in created_docs],
                        "total_pages": num_pages
                    }}
                )
                
                await log_action(user, "AUTO_SPLIT_ANALYZE", f"PDF {doc['filename']} dividido en {len(created_docs)} documentos")
                
                return {
                    "success": True,
                    "was_split": True,
                    "message": f"PDF multipágina dividido y analizado",
                    "total_pages": num_pages,
                    "documents_created": len(created_docs),
                    "created_documents": created_docs
                }
        except Exception as e:
            logging.warning(f"Error checking PDF pages: {e}")
    
    # Análisis normal para documentos de una página
    temp_path = f"/tmp/{doc_id}_{doc['filename']}"
    with open(temp_path, "wb") as f:
        f.write(doc['file_data'])
    
    analysis = await analyze_document_with_gpt(temp_path, doc['mime_type'])
    
    update_data = {
        "status": DocumentStatus.EN_PROCESO,
        "analisis_completo": analysis
    }
    
    if analysis.get("valor") is not None:
        update_data["valor"] = analysis["valor"]
    if analysis.get("fecha"):
        update_data["fecha"] = analysis["fecha"]
    if analysis.get("concepto"):
        update_data["concepto"] = analysis["concepto"]
    if analysis.get("tercero"):
        update_data["tercero"] = analysis["tercero"]
    if analysis.get("nit"):
        update_data["nit"] = analysis["nit"]
    if analysis.get("referencia_bancaria"):
        update_data["referencia_bancaria"] = analysis["referencia_bancaria"]
    if analysis.get("numero_documento"):
        update_data["numero_documento"] = analysis["numero_documento"]
    if analysis.get("banco"):
        update_data["banco"] = analysis["banco"]
    
    await db.documents.update_one({"id": doc_id}, {"$set": update_data})
    
    try:
        os.remove(temp_path)
    except:
        pass
    
    await log_action(user, "ANALYZE_DOCUMENT", f"Analizado documento {doc['filename']}")
    
    return {"success": True, "analysis": analysis, "was_split": False}

@api_router.post("/documents/analyze-all")
async def analyze_all_documents(authorization: str = Header(None)):
    """Analiza todos los documentos que no han sido analizados aún (status=cargado)"""
    user = await get_current_user(authorization)
    
    # Obtener documentos sin analizar
    docs = await db.documents.find(
        {"status": DocumentStatus.CARGADO},
        {"_id": 0}
    ).to_list(1000)
    
    if not docs:
        return {"message": "No hay documentos pendientes de análisis", "analyzed": 0}
    
    analyzed_count = 0
    errors = []
    
    for doc in docs:
        try:
            # Guardar temporalmente para análisis
            temp_path = f"/tmp/{doc['id']}_{doc['filename']}"
            with open(temp_path, "wb") as f:
                f.write(doc['file_data'])
            
            # Analizar con Gemini
            analysis = await analyze_document_with_gpt(temp_path, doc['mime_type'])
            
            # Actualizar documento con análisis
            update_data = {
                "status": DocumentStatus.EN_PROCESO,
                "analisis_completo": analysis
            }
            
            if analysis.get("valor") is not None:
                update_data["valor"] = analysis["valor"]
            if analysis.get("fecha"):
                update_data["fecha"] = analysis["fecha"]
            if analysis.get("concepto"):
                update_data["concepto"] = analysis["concepto"]
            if analysis.get("tercero"):
                update_data["tercero"] = analysis["tercero"]
            if analysis.get("nit"):
                update_data["nit"] = analysis["nit"]
            if analysis.get("referencia_bancaria"):
                update_data["referencia_bancaria"] = analysis["referencia_bancaria"]
            if analysis.get("numero_documento"):
                update_data["numero_documento"] = analysis["numero_documento"]
            if analysis.get("banco"):
                update_data["banco"] = analysis["banco"]
            
            await db.documents.update_one({"id": doc['id']}, {"$set": update_data})
            analyzed_count += 1
            
            # Limpiar archivo temporal
            try:
                os.remove(temp_path)
            except:
                pass
                
        except Exception as e:
            errors.append({"doc_id": doc['id'], "filename": doc['filename'], "error": str(e)})
    
    await log_action(user, "ANALYZE_ALL", f"Analizados {analyzed_count} documentos de {len(docs)}")
    
    return {
        "message": f"Análisis completado",
        "analyzed": analyzed_count,
        "total": len(docs),
        "errors": errors if errors else None
    }

@api_router.post("/documents/{doc_id}/split-pages")
async def split_multipage_document(doc_id: str, authorization: str = Header(None)):
    """
    Procesa un PDF multipágina: divide en páginas, analiza cada una con IA,
    y crea documentos individuales por cada página válida encontrada.
    """
    user = await get_current_user(authorization)
    
    # Obtener documento original
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    if not doc.get('file_data'):
        raise HTTPException(status_code=400, detail="El documento no tiene contenido")
    
    # Verificar que sea PDF
    if not doc.get('mime_type', '').lower().endswith('pdf') and not doc.get('filename', '').lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se pueden dividir archivos PDF")
    
    # Dividir PDF en páginas
    pages_data = split_pdf_to_pages(doc['file_data'])
    
    if len(pages_data) <= 1:
        return {
            "success": False,
            "message": "El documento tiene solo 1 página, no es necesario dividir",
            "total_pages": len(pages_data)
        }
    
    created_docs = []
    skipped_pages = []
    
    for page_num, page_data in enumerate(pages_data, 1):
        # Guardar página temporalmente para análisis
        temp_path = f"/tmp/page_{doc_id}_{page_num}.pdf"
        with open(temp_path, "wb") as f:
            f.write(page_data)
        
        # Analizar página con IA
        analysis = await analyze_pdf_page(temp_path, page_num)
        
        # Limpiar archivo temporal
        try:
            os.remove(temp_path)
        except:
            pass
        
        # Si la página contiene un documento válido, crear documento individual
        if analysis.get('es_documento_valido', False) and analysis.get('tercero'):
            new_doc_id = str(uuid.uuid4())
            original_name = doc['filename'].replace('.pdf', '').replace('.PDF', '')
            
            new_doc = {
                "id": new_doc_id,
                "filename": f"{original_name}_pag{page_num}.pdf",
                "tipo_documento": analysis.get('tipo_documento') or doc.get('tipo_documento'),
                "uploaded_by": user.id,
                "file_size": len(page_data),
                "mime_type": "application/pdf",
                "status": DocumentStatus.EN_PROCESO,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "file_data": page_data,
                "parent_document_id": doc_id,
                "page_number": page_num,
                "valor": analysis.get('valor'),
                "tercero": analysis.get('tercero'),
                "nit": analysis.get('nit'),
                "fecha": analysis.get('fecha'),
                "concepto": analysis.get('concepto'),
                "numero_documento": analysis.get('numero_documento'),
                "referencia_bancaria": analysis.get('referencia_bancaria'),
                "banco": analysis.get('banco'),
                "analisis_completo": analysis
            }
            
            await db.documents.insert_one(new_doc)
            
            created_docs.append({
                "id": new_doc_id,
                "filename": new_doc['filename'],
                "page_number": page_num,
                "tipo_documento": new_doc['tipo_documento'],
                "tercero": analysis.get('tercero'),
                "valor": analysis.get('valor'),
                "descripcion": analysis.get('descripcion_pagina')
            })
        else:
            skipped_pages.append({
                "page_number": page_num,
                "reason": analysis.get('descripcion_pagina', 'Página sin documento válido')
            })
    
    # Marcar documento original como "procesado/dividido"
    await db.documents.update_one(
        {"id": doc_id},
        {"$set": {
            "status": "dividido",
            "split_into": [d['id'] for d in created_docs],
            "total_pages": len(pages_data)
        }}
    )
    
    await log_action(user, "SPLIT_DOCUMENT", f"Documento {doc['filename']} dividido en {len(created_docs)} páginas válidas de {len(pages_data)} totales")
    
    return {
        "success": True,
        "message": f"PDF dividido exitosamente",
        "original_document": doc['filename'],
        "total_pages": len(pages_data),
        "valid_documents_created": len(created_docs),
        "skipped_pages": len(skipped_pages),
        "created_documents": created_docs,
        "skipped_details": skipped_pages
    }

@api_router.post("/documents/auto-split-all")
async def auto_split_all_multipage(authorization: str = Header(None)):
    """
    Busca y procesa automáticamente todos los PDFs multipágina que no han sido divididos.
    """
    user = await get_current_user(authorization)
    
    # Buscar documentos PDF que tengan más de 1 página y no hayan sido divididos
    docs = await db.documents.find(
        {
            "status": {"$in": [DocumentStatus.CARGADO, DocumentStatus.EN_PROCESO]},
            "split_into": {"$exists": False},
            "parent_document_id": {"$exists": False}  # No procesar páginas ya extraídas
        },
        {"_id": 0, "file_data": 0}
    ).to_list(1000)
    
    results = []
    
    for doc in docs:
        # Verificar si es PDF
        if not doc.get('filename', '').lower().endswith('.pdf'):
            continue
        
        # Obtener documento completo para verificar páginas
        full_doc = await db.documents.find_one({"id": doc['id']}, {"_id": 0})
        if not full_doc or not full_doc.get('file_data'):
            continue
        
        # Verificar número de páginas
        try:
            reader = PdfReader(io.BytesIO(full_doc['file_data']))
            num_pages = len(reader.pages)
            
            if num_pages > 1:
                results.append({
                    "id": doc['id'],
                    "filename": doc['filename'],
                    "pages": num_pages,
                    "status": "pendiente_division"
                })
        except:
            continue
    
    return {
        "multipage_documents": results,
        "total_found": len(results),
        "message": f"Se encontraron {len(results)} documentos multipágina para dividir"
    }

# Batch Processing Endpoints
@api_router.get("/documents/suggest-batches")
async def suggest_batches(authorization: str = Header(None)):
    """Sugiere lotes automáticamente basándose en correlaciones de documentos analizados"""
    user = await get_current_user(authorization)
    
    # Obtener documentos en proceso (ya analizados)
    docs = await db.documents.find(
        {"status": DocumentStatus.EN_PROCESO},
        {"_id": 0}
    ).to_list(1000)
    
    if not docs:
        return {"suggested_batches": [], "message": "No hay documentos analizados disponibles"}
    
    # Agrupar por coincidencias
    correlations = []
    processed_docs = set()
    
    for doc in docs:
        if doc['id'] in processed_docs:
            continue
            
        # Buscar documentos que coincidan
        valor = doc.get('valor')
        tercero = doc.get('tercero')
        
        if not valor or not tercero:
            continue
        
        # Buscar coincidencias (mismo tercero y valor similar ±1%)
        matching_docs = [doc]
        
        for other_doc in docs:
            if other_doc['id'] == doc['id'] or other_doc['id'] in processed_docs:
                continue
            
            other_valor = other_doc.get('valor')
            other_tercero = other_doc.get('tercero')
            
            if not other_valor or not other_tercero:
                continue
            
            # Verificar coincidencias
            # Tercero: buscar coincidencia parcial (al menos una palabra en común con más de 3 caracteres)
            tercero_words = set(w for w in tercero.upper().split() if len(w) > 3)
            other_tercero_words = set(w for w in other_tercero.upper().split() if len(w) > 3)
            tercero_match = len(tercero_words.intersection(other_tercero_words)) >= 1
            
            # Valor: coincidencia dentro del 1%
            valor_match = abs(valor - other_valor) / valor < 0.01 if valor > 0 else False
            
            if tercero_match and valor_match:
                matching_docs.append(other_doc)
                processed_docs.add(other_doc['id'])
        
        if len(matching_docs) >= 2:  # Al menos 2 documentos relacionados
            processed_docs.add(doc['id'])
            
            # Verificar tipos de documentos
            tipos = {d['tipo_documento'] for d in matching_docs}
            doc_ids = [d['id'] for d in matching_docs]
            
            correlations.append({
                "tercero": tercero,
                "valor": valor,
                "num_documentos": len(matching_docs),
                "tipos_documentos": list(tipos),
                "document_ids": doc_ids,
                "confianza": "alta" if len(matching_docs) >= 3 else "media"
            })
    
    await log_action(user, "SUGGEST_BATCHES", f"Se sugirieron {len(correlations)} lotes por correlación")
    
    return {
        "suggested_batches": correlations,
        "total_suggestions": len(correlations),
        "message": f"Se encontraron {len(correlations)} grupos de documentos correlacionados"
    }

@api_router.post("/batches/create")
async def create_batch(
    document_ids: List[str],
    authorization: str = Header(None)
):
    user = await get_current_user(authorization)
    
    batch = DocumentBatch(
        created_by=user.id,
        documentos=document_ids
    )
    
    doc = batch.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    
    await db.batches.insert_one(doc)
    
    # Actualizar documentos con batch_id
    await db.documents.update_many(
        {"id": {"$in": document_ids}},
        {"$set": {"batch_id": batch.id}}
    )
    
    await log_action(user, "CREATE_BATCH", f"Creado lote {batch.id} con {len(document_ids)} documentos")
    
    return batch

@api_router.get("/batches/list")
async def list_batches(authorization: str = Header(None)):
    user = await get_current_user(authorization)
    
    batches = await db.batches.find({}, {"_id": 0}).to_list(1000)
    
    return {"batches": batches}

@api_router.delete("/batches/{batch_id}")
async def delete_batch(batch_id: str, authorization: str = Header(None)):
    """Elimina un lote y su PDF consolidado asociado"""
    user = await get_current_user(authorization)
    
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    
    # Eliminar PDF consolidado si existe
    if batch.get('pdf_generado_id'):
        await db.consolidated_pdfs.delete_one({"id": batch['pdf_generado_id']})
    
    # Liberar documentos del lote (quitar batch_id)
    await db.documents.update_many(
        {"batch_id": batch_id},
        {"$unset": {"batch_id": ""}}
    )
    
    # Eliminar el lote
    await db.batches.delete_one({"id": batch_id})
    
    await log_action(user, "DELETE_BATCH", f"Eliminado lote {batch_id}")
    
    return {"success": True, "message": "Lote eliminado exitosamente"}

@api_router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, authorization: str = Header(None)):
    """Elimina un documento individual"""
    user = await get_current_user(authorization)
    
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0, "file_data": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    # Verificar si el documento está en un lote
    if doc.get('batch_id'):
        raise HTTPException(status_code=400, detail="No se puede eliminar un documento que está en un lote. Elimine el lote primero.")
    
    await db.documents.delete_one({"id": doc_id})
    
    await log_action(user, "DELETE_DOCUMENT", f"Eliminado documento {doc['filename']}")
    
    return {"success": True, "message": "Documento eliminado exitosamente"}

@api_router.post("/documents/{doc_id}/replace")
async def replace_document(
    doc_id: str,
    file: UploadFile = File(...),
    authorization: str = Header(None)
):
    """Reemplaza un documento existente con un nuevo archivo"""
    user = await get_current_user(authorization)
    
    # Buscar documento existente
    existing_doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not existing_doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    # Leer nuevo archivo
    file_data = await file.read()
    
    # Validar tamaño
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="El archivo excede el tamaño máximo de 10MB")
    
    # Actualizar documento con nuevo archivo
    update_data = {
        "filename": file.filename,
        "file_data": file_data,
        "file_size": len(file_data),
        "mime_type": file.content_type or "application/octet-stream",
        "replaced_at": datetime.now(timezone.utc).isoformat(),
        "replaced_by": user.id,
        # Resetear análisis para que se pueda re-validar
        "status": DocumentStatus.CARGADO,
        "valor": None,
        "tercero": None,
        "nit": None,
        "concepto": None,
        "fecha": None,
        "numero_documento": None,
        "referencia_bancaria": None,
        "banco": None,
        "analisis_completo": None
    }
    
    await db.documents.update_one({"id": doc_id}, {"$set": update_data})
    
    # Si el documento está en un lote, marcar el lote como pendiente de regenerar PDF
    if existing_doc.get('batch_id'):
        await db.batches.update_one(
            {"id": existing_doc['batch_id']},
            {"$set": {"needs_regeneration": True, "status": DocumentStatus.EN_PROCESO}}
        )
    
    await log_action(user, "REPLACE_DOCUMENT", f"Reemplazado documento {existing_doc['filename']} por {file.filename}")
    
    return {
        "success": True, 
        "message": "Documento reemplazado exitosamente",
        "new_filename": file.filename,
        "needs_revalidation": True,
        "batch_needs_regeneration": existing_doc.get('batch_id') is not None
    }

@api_router.get("/batches/{batch_id}/documents")
async def get_batch_documents(batch_id: str, authorization: str = Header(None)):
    """Obtiene los documentos de un lote específico"""
    user = await get_current_user(authorization)
    
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    
    # Obtener documentos del lote
    docs = await db.documents.find(
        {"id": {"$in": batch.get('documentos', [])}},
        {"_id": 0, "file_data": 0}
    ).to_list(100)
    
    # Ordenar por tipo
    order = ['comprobante_egreso', 'cuenta_por_pagar', 'soporte_pago', 'factura']
    docs = sorted(docs, key=lambda d: order.index(d['tipo_documento']) if d['tipo_documento'] in order else 999)
    
    return {
        "batch": batch,
        "documents": docs,
        "needs_regeneration": batch.get('needs_regeneration', False)
    }

@api_router.post("/batches/{batch_id}/add-document")
async def add_document_to_batch(
    batch_id: str,
    tipo_documento: str = Form(...),
    file: UploadFile = File(...),
    authorization: str = Header(None)
):
    """Agrega un nuevo documento a un lote existente"""
    user = await get_current_user(authorization)
    
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    
    # Validar tipo de documento
    valid_types = ['comprobante_egreso', 'cuenta_por_pagar', 'factura', 'soporte_pago']
    if tipo_documento not in valid_types:
        raise HTTPException(status_code=400, detail=f"Tipo de documento inválido. Debe ser uno de: {valid_types}")
    
    # Leer archivo
    file_data = await file.read()
    
    # Validar tamaño
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="El archivo excede el tamaño máximo de 10MB")
    
    # Crear nuevo documento
    doc_id = str(uuid.uuid4())
    doc_metadata = {
        "id": doc_id,
        "filename": file.filename,
        "tipo_documento": tipo_documento,
        "uploaded_by": user.id,
        "file_size": len(file_data),
        "mime_type": file.content_type or "application/octet-stream",
        "status": DocumentStatus.CARGADO,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "file_data": file_data
    }
    
    await db.documents.insert_one(doc_metadata)
    
    # Agregar documento al lote
    new_docs = batch.get('documentos', []) + [doc_id]
    await db.batches.update_one(
        {"id": batch_id},
        {"$set": {"documentos": new_docs, "needs_regeneration": True, "status": DocumentStatus.EN_PROCESO}}
    )
    
    await log_action(user, "ADD_TO_BATCH", f"Documento {file.filename} agregado al lote {batch_id}")
    
    return {
        "success": True,
        "message": "Documento agregado al lote",
        "document_id": doc_id,
        "filename": file.filename,
        "total_documents": len(new_docs)
    }

@api_router.delete("/batches/{batch_id}/documents/{doc_id}")
async def remove_document_from_batch(batch_id: str, doc_id: str, authorization: str = Header(None)):
    """Quita un documento de un lote (no lo elimina, solo lo saca del lote)"""
    user = await get_current_user(authorization)
    
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    
    if doc_id not in batch.get('documentos', []):
        raise HTTPException(status_code=404, detail="Documento no encontrado en este lote")
    
    # Verificar que quede al menos 1 documento
    if len(batch.get('documentos', [])) <= 1:
        raise HTTPException(status_code=400, detail="No se puede quitar el único documento del lote. Elimine el lote completo.")
    
    # Quitar documento del lote
    new_docs = [d for d in batch['documentos'] if d != doc_id]
    await db.batches.update_one(
        {"id": batch_id},
        {"$set": {"documentos": new_docs, "needs_regeneration": True}}
    )
    
    # Quitar batch_id del documento (liberarlo)
    await db.documents.update_one(
        {"id": doc_id},
        {"$unset": {"batch_id": ""}}
    )
    
    await log_action(user, "REMOVE_FROM_BATCH", f"Documento {doc_id} removido del lote {batch_id}")
    
    return {
        "success": True, 
        "message": "Documento removido del lote",
        "remaining_documents": len(new_docs)
    }

@api_router.post("/batches/{batch_id}/regenerate-pdf")
async def regenerate_pdf(batch_id: str, authorization: str = Header(None)):
    """Regenera el PDF consolidado de un lote (después de reemplazar documentos)"""
    user = await get_current_user(authorization)
    
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    
    # Eliminar PDF anterior si existe
    if batch.get('pdf_generado_id'):
        await db.consolidated_pdfs.delete_one({"id": batch['pdf_generado_id']})
    
    # Generar nuevo consecutivo
    current_year = datetime.now(timezone.utc).year
    count = await db.consolidated_pdfs.count_documents({}) + 1
    consecutive_number = f"{current_year}-{count:04d}"
    
    # Obtener documentos del lote
    docs = await db.documents.find(
        {"id": {"$in": batch['documentos']}},
        {"_id": 0}
    ).to_list(1000)
    
    # Ordenar documentos
    order = [
        DocumentType.COMPROBANTE_EGRESO,
        DocumentType.CUENTA_POR_PAGAR,
        DocumentType.SOPORTE_PAGO,
        DocumentType.FACTURA
    ]
    sorted_docs = sorted(docs, key=lambda d: order.index(d['tipo_documento']) if d['tipo_documento'] in order else 999)
    
    # Crear PDF consolidado
    merger = PdfMerger()
    temp_files = []
    
    for doc in sorted_docs:
        if doc.get('file_data'):
            temp_path = f"/tmp/merge_{doc['id']}.pdf"
            temp_files.append(temp_path)
            
            with open(temp_path, "wb") as f:
                f.write(doc['file_data'])
            
            try:
                merger.append(temp_path)
            except Exception as e:
                logging.warning(f"No se pudo agregar {doc['filename']}: {e}")
    
    output_path = f"/tmp/consolidated_{batch_id}.pdf"
    merger.write(output_path)
    merger.close()
    
    with open(output_path, "rb") as f:
        pdf_data = f.read()
    
    # Limpiar archivos temporales
    for temp_file in temp_files:
        try:
            os.remove(temp_file)
        except:
            pass
    try:
        os.remove(output_path)
    except:
        pass
    
    # Guardar nuevo PDF
    pdf_filename = f"Documentos_Consolidados_{consecutive_number}.pdf"
    
    consolidated = ConsolidatedPDF(
        batch_id=batch_id,
        filename=pdf_filename,
        created_by=user.id,
        file_size=len(pdf_data)
    )
    
    consolidated_dict = consolidated.model_dump()
    consolidated_dict['created_at'] = consolidated_dict['created_at'].isoformat()
    consolidated_dict['pdf_data'] = pdf_data
    
    await db.consolidated_pdfs.insert_one(consolidated_dict)
    
    # Actualizar batch
    await db.batches.update_one(
        {"id": batch_id},
        {"$set": {
            "pdf_generado_id": consolidated.id, 
            "status": DocumentStatus.TERMINADO,
            "needs_regeneration": False
        }}
    )
    
    await log_action(user, "REGENERATE_PDF", f"Regenerado PDF consolidado para lote {batch_id}")
    
    return {"success": True, "pdf_id": consolidated.id, "filename": pdf_filename}

@api_router.delete("/documents/bulk")
async def delete_documents_bulk(
    document_ids: List[str],
    authorization: str = Header(None)
):
    """Elimina múltiples documentos"""
    user = await get_current_user(authorization)
    
    # Verificar que ningún documento esté en un lote
    docs_in_batch = await db.documents.count_documents({
        "id": {"$in": document_ids},
        "batch_id": {"$exists": True, "$ne": None}
    })
    
    if docs_in_batch > 0:
        raise HTTPException(status_code=400, detail=f"{docs_in_batch} documento(s) están en lotes. Elimine los lotes primero.")
    
    result = await db.documents.delete_many({"id": {"$in": document_ids}})
    
    await log_action(user, "DELETE_DOCUMENTS_BULK", f"Eliminados {result.deleted_count} documentos")
    
    return {"success": True, "deleted_count": result.deleted_count}

@api_router.get("/documents/by-date")
async def get_documents_by_date(authorization: str = Header(None)):
    """Obtiene documentos agrupados por fecha de subida"""
    user = await get_current_user(authorization)
    
    docs = await db.documents.find({}, {"_id": 0, "file_data": 0}).to_list(10000)
    
    # Agrupar por fecha
    by_date = {}
    for doc in docs:
        # Extraer solo la fecha (sin hora) - usar uploaded_at
        uploaded = doc.get('uploaded_at') or doc.get('created_at')
        if uploaded:
            if isinstance(uploaded, str):
                date_str = uploaded[:10]  # YYYY-MM-DD
            else:
                date_str = uploaded.strftime('%Y-%m-%d')
        else:
            # Si no tiene fecha, usar fecha actual
            date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        if date_str not in by_date:
            by_date[date_str] = {
                "date": date_str,
                "documents": [],
                "total_count": 0,
                "has_batched": False
            }
        
        by_date[date_str]["documents"].append(doc)
        by_date[date_str]["total_count"] += 1
        if doc.get('batch_id'):
            by_date[date_str]["has_batched"] = True
    
    # Convertir a lista ordenada por fecha (más reciente primero)
    result = sorted(by_date.values(), key=lambda x: x['date'], reverse=True)
    
    return {"groups": result}

@api_router.delete("/documents/by-date/{date}")
async def delete_documents_by_date(date: str, authorization: str = Header(None)):
    """Elimina todos los documentos de una fecha específica (formato: YYYY-MM-DD)"""
    user = await get_current_user(authorization)
    
    # Buscar documentos de esa fecha
    docs = await db.documents.find({}, {"_id": 0, "file_data": 0}).to_list(10000)
    
    docs_to_delete = []
    batched_count = 0
    
    for doc in docs:
        created = doc.get('created_at', '')
        if isinstance(created, str):
            date_str = created[:10]
        else:
            date_str = created.strftime('%Y-%m-%d') if created else ''
        
        if date_str == date:
            if doc.get('batch_id'):
                batched_count += 1
            else:
                docs_to_delete.append(doc['id'])
    
    if batched_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"{batched_count} documento(s) están en lotes. Elimine los lotes primero."
        )
    
    if not docs_to_delete:
        return {"success": True, "deleted_count": 0, "message": "No hay documentos para eliminar en esta fecha"}
    
    result = await db.documents.delete_many({"id": {"$in": docs_to_delete}})
    
    await log_action(user, "DELETE_BY_DATE", f"Eliminados {result.deleted_count} documentos de {date}")
    
    return {"success": True, "deleted_count": result.deleted_count, "date": date}

@api_router.post("/batches/{batch_id}/generate-pdf")
async def generate_consolidated_pdf(batch_id: str, authorization: str = Header(None)):
    user = await get_current_user(authorization)
    
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    
    # Generar consecutivo automático
    current_year = datetime.now(timezone.utc).year
    count = await db.consolidated_pdfs.count_documents({}) + 1
    consecutive_number = f"{current_year}-{count:04d}"  # Ej: 2025-0001
    
    # Obtener documentos del lote
    docs = await db.documents.find(
        {"id": {"$in": batch['documentos']}},
        {"_id": 0}
    ).to_list(1000)
    
    # Ordenar documentos según el orden especificado:
    # 1. Comprobante de Egreso
    # 2. Cuenta Por Pagar  
    # 3. Soporte de Pago
    # 4. Factura (si existe)
    order = [
        DocumentType.COMPROBANTE_EGRESO,
        DocumentType.CUENTA_POR_PAGAR,
        DocumentType.SOPORTE_PAGO,
        DocumentType.FACTURA
    ]
    
    sorted_docs = sorted(docs, key=lambda d: order.index(d['tipo_documento']) if d['tipo_documento'] in order else 999)
    
    # Crear PDF consolidado uniendo los documentos originales
    pdf_writer = PdfWriter()
    
    for doc in sorted_docs:
        try:
            # Leer documento original
            file_data = doc['file_data']
            
            # Si es PDF, agregar todas sus páginas
            if doc['mime_type'] == 'application/pdf':
                pdf_reader = PdfReader(io.BytesIO(file_data))
                for page in pdf_reader.pages:
                    pdf_writer.add_page(page)
            # Si es imagen, convertir a PDF
            elif 'image' in doc['mime_type']:
                img = Image.open(io.BytesIO(file_data))
                # Convertir imagen a RGB si es necesario
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PDF')
                img_buffer.seek(0)
                img_reader = PdfReader(img_buffer)
                for page in img_reader.pages:
                    pdf_writer.add_page(page)
        except Exception as e:
            logging.error(f"Error adding document {doc['filename']} to PDF: {str(e)}")
    
    # Guardar PDF consolidado
    pdf_buffer = io.BytesIO()
    pdf_writer.write(pdf_buffer)
    pdf_data = pdf_buffer.getvalue()
    
    # Guardar metadata del PDF consolidado
    pdf_filename = f"Documentos_Consolidados_{consecutive_number}.pdf"
    
    consolidated = ConsolidatedPDF(
        batch_id=batch_id,
        filename=pdf_filename,
        created_by=user.id,
        file_size=len(pdf_data)
    )
    
    consolidated_dict = consolidated.model_dump()
    consolidated_dict['created_at'] = consolidated_dict['created_at'].isoformat()
    consolidated_dict['pdf_data'] = pdf_data
    
    await db.consolidated_pdfs.insert_one(consolidated_dict)
    
    # Actualizar batch
    await db.batches.update_one(
        {"id": batch_id},
        {"$set": {"pdf_generado_id": consolidated.id, "status": DocumentStatus.TERMINADO}}
    )
    
    await log_action(user, "GENERATE_PDF", f"Generado PDF consolidado para lote {batch_id}")
    
    return {"success": True, "pdf_id": consolidated.id}

@api_router.get("/pdfs/{pdf_id}/download")
async def download_pdf(pdf_id: str, authorization: str = Header(None)):
    user = await get_current_user(authorization)
    
    pdf = await db.consolidated_pdfs.find_one({"id": pdf_id}, {"_id": 0})
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF no encontrado")
    
    await log_action(user, "DOWNLOAD_PDF", f"Descargado PDF {pdf['filename']}")
    
    return StreamingResponse(
        io.BytesIO(pdf['pdf_data']),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={pdf['filename']}"}
    )

@api_router.get("/pdfs/list")
async def list_pdfs(authorization: str = Header(None)):
    user = await get_current_user(authorization)
    
    pdfs = await db.consolidated_pdfs.find({}, {"_id": 0, "pdf_data": 0}).to_list(1000)
    
    return {"pdfs": pdfs}

@api_router.get("/pdfs/{pdf_id}/details")
async def get_pdf_details(pdf_id: str, authorization: str = Header(None)):
    """Obtiene los detalles completos de un PDF consolidado incluyendo los documentos que lo conforman"""
    user = await get_current_user(authorization)
    
    pdf = await db.consolidated_pdfs.find_one({"id": pdf_id}, {"_id": 0, "pdf_data": 0})
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF no encontrado")
    
    # Obtener el batch asociado
    batch = await db.batches.find_one({"id": pdf['batch_id']}, {"_id": 0})
    
    # Obtener los documentos del batch
    documents = []
    if batch and batch.get('documentos'):
        docs = await db.documents.find(
            {"id": {"$in": batch['documentos']}},
            {"_id": 0, "file_data": 0}
        ).to_list(100)
        
        # Ordenar por tipo de documento
        order = ['comprobante_egreso', 'cuenta_por_pagar', 'soporte_pago', 'factura']
        documents = sorted(docs, key=lambda d: order.index(d['tipo_documento']) if d['tipo_documento'] in order else 999)
    
    # Calcular información resumida
    terceros = list(set(d.get('tercero') for d in documents if d.get('tercero')))
    valores = [d.get('valor') for d in documents if d.get('valor')]
    
    return {
        "pdf": pdf,
        "batch": batch,
        "documents": documents,
        "summary": {
            "total_documentos": len(documents),
            "terceros": terceros,
            "valor_total": sum(valores) if valores else 0,
            "tipos": list(set(d.get('tipo_documento') for d in documents))
        }
    }

# User Management (Admin only)
@api_router.get("/users/list")
async def list_users(authorization: str = Header(None)):
    user = await get_current_user(authorization)
    
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Solo administradores")
    
    users = await db.users.find({}, {"_id": 0, "password": 0}).to_list(1000)
    
    return {"users": users}

@api_router.put("/users/{user_id}/toggle-active")
async def toggle_user_active(user_id: str, authorization: str = Header(None)):
    user = await get_current_user(authorization)
    
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Solo administradores")
    
    target_user = await db.users.find_one({"id": user_id})
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    new_status = not target_user.get('is_active', True)
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_active": new_status}}
    )
    
    await log_action(user, "TOGGLE_USER", f"Usuario {target_user['email']} {'activado' if new_status else 'desactivado'}")
    
    return {"success": True, "is_active": new_status}

# Audit Logs
@api_router.get("/audit/logs")
async def get_audit_logs(authorization: str = Header(None), limit: int = 100):
    user = await get_current_user(authorization)
    
    if user.role not in [UserRole.ADMIN, UserRole.REVISOR]:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    logs = await db.audit_logs.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    
    return {"logs": logs}

# Dashboard Stats
@api_router.get("/dashboard/stats")
async def get_dashboard_stats(authorization: str = Header(None)):
    user = await get_current_user(authorization)
    
    total_docs = await db.documents.count_documents({})
    docs_cargados = await db.documents.count_documents({"status": DocumentStatus.CARGADO})
    docs_en_proceso = await db.documents.count_documents({"status": DocumentStatus.EN_PROCESO})
    docs_terminados = await db.documents.count_documents({"status": DocumentStatus.TERMINADO})
    docs_revision = await db.documents.count_documents({"status": DocumentStatus.REVISION})
    
    total_batches = await db.batches.count_documents({})
    pdfs_generados = await db.consolidated_pdfs.count_documents({})
    
    return {
        "total_documentos": total_docs,
        "documentos_cargados": docs_cargados,
        "documentos_en_proceso": docs_en_proceso,
        "documentos_terminados": docs_terminados,
        "documentos_revision": docs_revision,
        "total_lotes": total_batches,
        "pdfs_generados": pdfs_generados
    }

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()