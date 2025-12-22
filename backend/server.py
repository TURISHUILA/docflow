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
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import json

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
    """Analiza un documento usando GPT-5.2 para extraer información"""
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=str(uuid.uuid4()),
            system_message="Eres un experto en análisis de documentos contables. Extrae información precisa de documentos financieros."
        ).with_model("openai", "gpt-5.2")
        
        file_content = FileContentWithMimeType(
            file_path=file_path,
            mime_type=mime_type
        )
        
        prompt = """Analiza este documento y extrae la siguiente información en formato JSON:
        {
            "tipo_documento": "comprobante_egreso" | "cuenta_por_pagar" | "factura" | "soporte_pago",
            "valor": número decimal,
            "fecha": "YYYY-MM-DD",
            "concepto": "texto del concepto",
            "tercero": "nombre del beneficiario",
            "referencia_bancaria": "número de referencia si existe"
        }
        
        Si algún campo no está presente, usa null. Responde solo con el JSON, sin texto adicional."""
        
        message = UserMessage(
            text=prompt,
            file_contents=[file_content]
        )
        
        response = await chat.send_message(message)
        
        # Intentar parsear la respuesta como JSON
        try:
            data = json.loads(response)
            return data
        except:
            # Si no es JSON válido, intentar extraer JSON del texto
            import re
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"raw_response": response}
    except Exception as e:
        logging.error(f"Error analyzing document: {str(e)}")
        return {"error": str(e)}

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
        # Guardar archivo en MongoDB GridFS
        file_data = await file.read()
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
    user = await get_current_user(authorization)
    
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    # Guardar temporalmente para análisis
    temp_path = f"/tmp/{doc_id}_{doc['filename']}"
    with open(temp_path, "wb") as f:
        f.write(doc['file_data'])
    
    # Analizar con GPT-5.2
    analysis = await analyze_document_with_gpt(temp_path, doc['mime_type'])
    
    # Actualizar documento con análisis
    update_data = {
        "status": DocumentStatus.EN_PROCESO,
        "analisis_completo": analysis
    }
    
    if "valor" in analysis:
        update_data["valor"] = analysis["valor"]
    if "fecha" in analysis:
        update_data["fecha"] = analysis["fecha"]
    if "concepto" in analysis:
        update_data["concepto"] = analysis["concepto"]
    if "tercero" in analysis:
        update_data["tercero"] = analysis["tercero"]
    if "referencia_bancaria" in analysis:
        update_data["referencia_bancaria"] = analysis["referencia_bancaria"]
    
    await db.documents.update_one({"id": doc_id}, {"$set": update_data})
    
    # Limpiar archivo temporal
    try:
        os.remove(temp_path)
    except:
        pass
    
    await log_action(user, "ANALYZE_DOCUMENT", f"Analizado documento {doc['filename']}")
    
    return {"success": True, "analysis": analysis}

# Batch Processing Endpoints
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

@api_router.post("/batches/{batch_id}/generate-pdf")
async def generate_consolidated_pdf(batch_id: str, authorization: str = Header(None)):
    user = await get_current_user(authorization)
    
    batch = await db.batches.find_one({"id": batch_id}, {"_id": 0})
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    
    # Obtener documentos del lote
    docs = await db.documents.find(
        {"id": {"$in": batch['documentos']}},
        {"_id": 0}
    ).to_list(1000)
    
    # Ordenar documentos según tipo
    order = [
        DocumentType.COMPROBANTE_EGRESO,
        DocumentType.CUENTA_POR_PAGAR,
        DocumentType.FACTURA,
        DocumentType.SOPORTE_PAGO
    ]
    
    sorted_docs = sorted(docs, key=lambda d: order.index(d['tipo_documento']) if d['tipo_documento'] in order else 999)
    
    # Crear PDF consolidado
    pdf_writer = PdfWriter()
    
    for doc in sorted_docs:
        try:
            # Leer documento
            file_data = doc['file_data']
            
            # Si es PDF, agregar páginas
            if doc['mime_type'] == 'application/pdf':
                pdf_reader = PdfReader(io.BytesIO(file_data))
                for page in pdf_reader.pages:
                    pdf_writer.add_page(page)
            # Si es imagen, convertir a PDF
            elif 'image' in doc['mime_type']:
                img = Image.open(io.BytesIO(file_data))
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PDF')
                img_buffer.seek(0)
                img_reader = PdfReader(img_buffer)
                for page in img_reader.pages:
                    pdf_writer.add_page(page)
        except Exception as e:
            logging.error(f"Error adding document to PDF: {str(e)}")
    
    # Guardar PDF
    pdf_buffer = io.BytesIO()
    pdf_writer.write(pdf_buffer)
    pdf_data = pdf_buffer.getvalue()
    
    # Guardar metadata del PDF consolidado
    consolidated = ConsolidatedPDF(
        batch_id=batch_id,
        filename=f"consolidado_{batch_id}.pdf",
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