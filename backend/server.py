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
import re

ROOT_DIR = Path(__file__).parent

def sanitize_filename(name: str) -> str:
    """Sanitiza un nombre para usarlo como nombre de archivo válido."""
    if not name:
        return "SIN_NOMBRE"
    # Reemplazar caracteres no válidos para nombres de archivo (pero permitir guiones)
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Reemplazar múltiples espacios por uno solo
    sanitized = re.sub(r'\s+', '_', sanitized)
    # Reemplazar múltiples guiones bajos por uno solo
    sanitized = re.sub(r'_+', '_', sanitized)
    # Quitar guiones bajos al inicio y final
    sanitized = sanitized.strip('_')
    return sanitized or "SIN_NOMBRE"

def generate_pdf_filename_from_batch(docs: list) -> str:
    """
    Genera el nombre del PDF basado en el comprobante de egreso.
    Formato: {NumeroComprobanteEgreso}_{NombreTercero}.pdf
    Ejemplo: CE-19521_AVIANCA.pdf
    """
    # Buscar el comprobante de egreso en los documentos del lote
    comprobante = None
    for doc in docs:
        if doc.get('tipo_documento') == DocumentType.COMPROBANTE_EGRESO:
            comprobante = doc
            break
    
    if comprobante:
        numero = comprobante.get('numero_documento') or comprobante.get('analisis_completo', {}).get('numero_documento')
        tercero = comprobante.get('tercero') or comprobante.get('analisis_completo', {}).get('tercero')
        
        if numero:
            numero_sanitizado = sanitize_filename(numero)
            tercero_sanitizado = sanitize_filename(tercero) if tercero else "SIN_TERCERO"
            return f"{numero_sanitizado}_{tercero_sanitizado}.pdf"
    
    # Fallback: usar consecutivo si no hay comprobante de egreso válido
    return None

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
    CARGADO = "cargado"           # Recién subido (🔴)
    VALIDANDO = "validando"       # En proceso de validación (🟡)
    VALIDADO = "validado"         # Validado, listo para analizar (🟢)
    EN_PROCESO = "en_proceso"     # Analizando con IA
    ANALIZADO = "analizado"       # IA extrajo datos (🔵)
    TERMINADO = "terminado"       # En lote con PDF generado
    REVISION = "revision"         # Requiere revisión

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

async def correlate_documents_with_claude(documents: List[Dict]) -> List[Dict]:
    """
    Usa Claude Sonnet 4.5 para correlación inteligente de documentos.
    Versión mejorada con parámetros más flexibles.
    """
    if not documents:
        return []
    
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=str(uuid.uuid4()),
            system_message="""Eres un experto en correlación de documentos financieros colombianos.
Tu tarea es encontrar documentos que pertenecen a la MISMA transacción de pago o al MISMO proveedor/tercero.

CRITERIOS DE CORRELACIÓN (en orden de prioridad):

1. **MISMO NIT** = ALTA CONFIANZA
   - Si dos documentos tienen el mismo NIT, son del mismo proveedor
   - Ejemplo: NIT 901244056 = ASSIST UNO (aunque el nombre varíe)

2. **MISMO VALOR EXACTO o MUY CERCANO (±5%)** = ALTA CONFIANZA
   - Documentos con el mismo monto probablemente son de la misma transacción
   - Tolerancia del 5% para cubrir diferencias por impuestos/retenciones

3. **MISMO TERCERO** (nombres similares) = MEDIA-ALTA CONFIANZA
   - Reconocer variaciones del mismo proveedor:
     * "MOVISTAR" = "COLOMBIA TELECOMUNICACIONES" = "TELEFONICA"
     * "BEDS ON LINE" = "HOTELBEDS" = "HOTELBEDS USA"
     * "COLASISTENCIA" = "COLOMBIANA DE ASISTENCIA"
     * "CIC COLOMBIA TRAVEL" = "CIC TRAVEL"
     * "ASSIST UNO" = "ASSIST 1" = "ASSISTUNO"

4. **FECHAS CERCANAS (±30 días)** = Criterio de apoyo
   - Documentos del mismo mes/período suelen estar relacionados

5. **REFERENCIAS BANCARIAS o NÚMEROS DE DOCUMENTO** = ALTA CONFIANZA
   - Si comparten referencia bancaria, están relacionados

6. **SUMA DE FACTURAS = VALOR DEL PAGO**
   - Múltiples facturas pequeñas pueden sumar el valor de un comprobante de egreso
   - Ejemplo: 3 facturas de $78,894 + $45,655 + $68,459 ≈ CXP de $193,000

TIPOS DE AGRUPACIÓN:
- GRUPO COMPLETO: Comprobante Egreso + Cuenta por Pagar + Factura(s) + Soporte de Pago
- GRUPO PARCIAL: Al menos 2 documentos relacionados del mismo tercero
- GRUPO POR PROVEEDOR: Múltiples documentos del mismo NIT/tercero aunque tengan valores diferentes

IMPORTANTE: 
- Prioriza encontrar TODAS las correlaciones posibles, no solo las perfectas
- Es mejor agrupar de más que dejar documentos sueltos
- Agrupa por PROVEEDOR si no hay coincidencia exacta de valor"""
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        # Preparar resumen de documentos para Claude
        docs_summary = []
        for doc in documents:
            docs_summary.append({
                "id": doc.get("id"),
                "filename": doc.get("filename"),
                "tipo": doc.get("tipo_documento"),
                "tercero": doc.get("tercero"),
                "valor": doc.get("valor"),
                "nit": doc.get("nit"),
                "fecha": doc.get("fecha"),
                "numero_documento": doc.get("numero_documento"),
                "referencia_bancaria": doc.get("referencia_bancaria")
            })
        
        prompt = f"""Analiza estos {len(docs_summary)} documentos financieros y agrúpalos.

DOCUMENTOS DISPONIBLES:
{json.dumps(docs_summary, indent=2, ensure_ascii=False)}

INSTRUCCIONES:
1. Agrupa documentos que pertenezcan al MISMO PROVEEDOR o MISMA TRANSACCIÓN
2. Usa TODOS los criterios: NIT, valor (±5%), tercero similar, fechas cercanas, referencias
3. Si un proveedor tiene múltiples transacciones, crea UN GRUPO POR TRANSACCIÓN (mismo valor)
4. Si no hay coincidencia de valor pero sí de NIT/tercero, agrupa por proveedor
5. Busca si la SUMA de facturas pequeñas coincide con un pago mayor
6. Cada grupo debe tener al menos 2 documentos
7. MAXIMIZA las correlaciones - es mejor agrupar que dejar sueltos

Responde SOLO con este JSON (sin explicaciones ni texto adicional):
{{
    "grupos": [
        {{
            "tercero_principal": "nombre normalizado del tercero",
            "nit": "NIT si está disponible",
            "valor_referencia": 12345.67,
            "tipo_correlacion": "valor_exacto" | "mismo_nit" | "mismo_tercero" | "suma_facturas",
            "confianza": "alta" | "media" | "baja",
            "razon": "explicación breve de por qué están relacionados",
            "document_ids": ["id1", "id2", "id3"]
        }}
    ]
}}"""

        message = UserMessage(text=prompt)
        response = await chat.send_message(message)
        
        # Parsear respuesta
        response_clean = response.strip()
        json_match = re.search(r'\{[\s\S]*\}', response_clean)
        
        if json_match:
            data = json.loads(json_match.group())
            grupos = data.get("grupos", [])
            
            # Convertir al formato esperado
            correlations = []
            for grupo in grupos:
                doc_ids = grupo.get("document_ids", [])
                tipos = list(set(
                    next((d.get("tipo_documento") for d in documents if d.get("id") == doc_id), "")
                    for doc_id in doc_ids
                ))
                
                correlations.append({
                    "tercero": grupo.get("tercero_principal", ""),
                    "nit": grupo.get("nit", ""),
                    "valor": grupo.get("valor_referencia", 0),
                    "num_documentos": len(doc_ids),
                    "tipos_documentos": tipos,
                    "document_ids": doc_ids,
                    "tipo_correlacion": grupo.get("tipo_correlacion", "valor_exacto"),
                    "confianza": grupo.get("confianza", "media"),
                    "razon_correlacion": grupo.get("razon", "")
                })
            
            logging.info(f"Claude encontró {len(correlations)} correlaciones")
            return correlations
        else:
            logging.warning(f"No se pudo parsear respuesta de Claude: {response_clean[:200]}")
            return []
            
    except Exception as e:
        logging.error(f"Error en correlación con Claude: {str(e)}")
        return []

# Función de correlación básica mejorada (fallback)
def correlate_documents_basic(documents: List[Dict]) -> List[Dict]:
    """
    Correlación básica mejorada con múltiples criterios.
    Se usa como fallback si Claude falla.
    """
    if not documents:
        return []
    
    correlations = []
    processed_ids = set()
    
    # Indexar por NIT para búsqueda rápida
    by_nit = {}
    for doc in documents:
        nit = doc.get('nit', '').replace('-', '').replace('.', '').strip()
        if nit and len(nit) >= 6:
            if nit not in by_nit:
                by_nit[nit] = []
            by_nit[nit].append(doc)
    
    # Indexar por valor (redondeado)
    by_valor = {}
    for doc in documents:
        valor = doc.get('valor')
        if valor:
            valor_key = round(valor, -2)  # Redondear a centenas
            if valor_key not in by_valor:
                by_valor[valor_key] = []
            by_valor[valor_key].append(doc)
    
    # PASO 1: Correlacionar por NIT (alta confianza)
    for nit, docs_nit in by_nit.items():
        if len(docs_nit) >= 2:
            # Agrupar por valor dentro del mismo NIT
            sub_by_valor = {}
            for doc in docs_nit:
                if doc['id'] in processed_ids:
                    continue
                valor = doc.get('valor', 0)
                valor_key = round(valor, -2) if valor else 0
                if valor_key not in sub_by_valor:
                    sub_by_valor[valor_key] = []
                sub_by_valor[valor_key].append(doc)
            
            for valor_key, grupo in sub_by_valor.items():
                if len(grupo) >= 2:
                    for d in grupo:
                        processed_ids.add(d['id'])
                    
                    correlations.append({
                        "tercero": grupo[0].get('tercero', ''),
                        "nit": nit,
                        "valor": valor_key,
                        "num_documentos": len(grupo),
                        "tipos_documentos": list(set(d.get('tipo_documento', '') for d in grupo)),
                        "document_ids": [d['id'] for d in grupo],
                        "tipo_correlacion": "mismo_nit",
                        "confianza": "alta",
                        "razon_correlacion": f"Mismo NIT: {nit}"
                    })
    
    # PASO 2: Correlacionar por valor exacto (±5%)
    for doc in documents:
        if doc['id'] in processed_ids:
            continue
        
        valor = doc.get('valor')
        tercero = doc.get('tercero', '').upper()
        
        if not valor:
            continue
        
        matching = [doc]
        
        for other in documents:
            if other['id'] == doc['id'] or other['id'] in processed_ids:
                continue
            
            other_valor = other.get('valor')
            if not other_valor:
                continue
            
            # Tolerancia del 5%
            if abs(valor - other_valor) / valor <= 0.05:
                matching.append(other)
                processed_ids.add(other['id'])
        
        if len(matching) >= 2:
            processed_ids.add(doc['id'])
            correlations.append({
                "tercero": tercero,
                "nit": doc.get('nit', ''),
                "valor": valor,
                "num_documentos": len(matching),
                "tipos_documentos": list(set(d.get('tipo_documento', '') for d in matching)),
                "document_ids": [d['id'] for d in matching],
                "tipo_correlacion": "valor_exacto",
                "confianza": "alta" if len(matching) >= 3 else "media",
                "razon_correlacion": f"Valor similar: ${valor:,.2f}"
            })
    
    # PASO 3: Correlacionar por tercero similar (palabras en común)
    remaining = [d for d in documents if d['id'] not in processed_ids and d.get('tercero')]
    
    for doc in remaining:
        if doc['id'] in processed_ids:
            continue
        
        tercero = doc.get('tercero', '').upper()
        tercero_words = set(w for w in tercero.split() if len(w) > 3)
        
        if not tercero_words:
            continue
        
        matching = [doc]
        
        for other in remaining:
            if other['id'] == doc['id'] or other['id'] in processed_ids:
                continue
            
            other_tercero = other.get('tercero', '').upper()
            other_words = set(w for w in other_tercero.split() if len(w) > 3)
            
            # Al menos 1 palabra significativa en común
            if len(tercero_words & other_words) >= 1:
                matching.append(other)
                processed_ids.add(other['id'])
        
        if len(matching) >= 2:
            processed_ids.add(doc['id'])
            correlations.append({
                "tercero": tercero,
                "nit": doc.get('nit', ''),
                "valor": doc.get('valor', 0),
                "num_documentos": len(matching),
                "tipos_documentos": list(set(d.get('tipo_documento', '') for d in matching)),
                "document_ids": [d['id'] for d in matching],
                "tipo_correlacion": "mismo_tercero",
                "confianza": "media",
                "razon_correlacion": f"Tercero similar: {tercero[:30]}"
            })
    
    return correlations

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
    MAX_FILES = 70
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_TOTAL_SIZE = 100 * 1024 * 1024  # 100MB
    
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Máximo {MAX_FILES} archivos permitidos por carga")
    
    total_size = sum(file.size for file in files if hasattr(file, 'size'))
    if total_size > MAX_TOTAL_SIZE:
        raise HTTPException(status_code=400, detail="El tamaño total excede 100MB")
    
    # Obtener nombres de archivos existentes en esta carpeta/tipo
    existing_docs = await db.documents.find(
        {"tipo_documento": tipo_documento},
        {"filename": 1, "_id": 0}
    ).to_list(10000)
    existing_filenames = set(doc['filename'] for doc in existing_docs)
    
    uploaded_docs = []
    duplicates = []
    
    for file in files:
        # Verificar si ya existe un archivo con el mismo nombre en esta carpeta
        if file.filename in existing_filenames:
            duplicates.append(file.filename)
            continue
        
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
        
        # Añadir al set de existentes para detectar duplicados dentro del mismo lote
        existing_filenames.add(file.filename)
        
        # Limpiar archivo temporal
        try:
            os.remove(temp_path)
        except:
            pass
    
    await log_action(user, "UPLOAD_DOCUMENTS", f"Subidos {len(uploaded_docs)} documentos tipo {tipo_documento}, {len(duplicates)} duplicados omitidos")
    
    return {
        "uploaded": len(uploaded_docs), 
        "documents": uploaded_docs,
        "duplicates": len(duplicates),
        "duplicate_files": duplicates
    }

@api_router.get("/documents/list")
async def list_documents(authorization: str = Header(None), status: Optional[str] = None):
    user = await get_current_user(authorization)
    
    query = {}
    if status:
        query['status'] = status
    
    docs = await db.documents.find(query, {"_id": 0, "file_data": 0}).to_list(1000)
    
    return {"documents": docs}

@api_router.get("/documents/{doc_id}/view")
async def view_document(doc_id: str, authorization: str = Header(None)):
    """Obtiene el archivo original del documento para visualización"""
    user = await get_current_user(authorization)
    
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    if not doc.get('file_data'):
        raise HTTPException(status_code=404, detail="El documento no tiene contenido")
    
    # Determinar content type
    content_type = doc.get('mime_type', 'application/pdf')
    filename = doc.get('filename', 'documento')
    
    return StreamingResponse(
        io.BytesIO(doc['file_data']),
        media_type=content_type,
        headers={
            "Content-Disposition": f"inline; filename={filename}",
            "Content-Length": str(len(doc['file_data']))
        }
    )

@api_router.post("/documents/{doc_id}/validate")
async def validate_document(doc_id: str, authorization: str = Header(None)):
    """Valida que un documento se haya subido correctamente y está listo para analizar"""
    user = await get_current_user(authorization)
    
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    # Marcar como validando
    await db.documents.update_one({"id": doc_id}, {"$set": {"status": DocumentStatus.VALIDANDO}})
    
    try:
        file_data = doc.get('file_data')
        if not file_data or len(file_data) == 0:
            raise HTTPException(status_code=400, detail="Archivo vacío o corrupto")
        
        filename = doc.get('filename', '').lower()
        mime_type = doc.get('mime_type', '').lower()
        
        # Validar según tipo de archivo
        if filename.endswith('.pdf') or 'pdf' in mime_type:
            # Validar PDF
            try:
                reader = PdfReader(io.BytesIO(file_data))
                num_pages = len(reader.pages)
                if num_pages == 0:
                    raise ValueError("PDF sin páginas")
            except Exception as e:
                await db.documents.update_one({"id": doc_id}, {"$set": {"status": DocumentStatus.REVISION}})
                raise HTTPException(status_code=400, detail=f"PDF inválido: {str(e)}")
        
        elif filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')) or 'image' in mime_type:
            # Validar imagen
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(file_data))
                img.verify()
            except Exception as e:
                await db.documents.update_one({"id": doc_id}, {"$set": {"status": DocumentStatus.REVISION}})
                raise HTTPException(status_code=400, detail=f"Imagen inválida: {str(e)}")
        
        # Si pasó las validaciones, marcar como validado
        await db.documents.update_one({"id": doc_id}, {"$set": {"status": DocumentStatus.VALIDADO}})
        
        await log_action(user, "VALIDATE_DOCUMENT", f"Documento {doc['filename']} validado")
        
        return {"success": True, "status": "validado", "message": "Documento validado correctamente"}
    
    except HTTPException:
        raise
    except Exception as e:
        await db.documents.update_one({"id": doc_id}, {"$set": {"status": DocumentStatus.REVISION}})
        raise HTTPException(status_code=400, detail=f"Error al validar: {str(e)}")

@api_router.post("/documents/validate-folder/{tipo_documento}")
async def validate_folder(tipo_documento: str, authorization: str = Header(None)):
    """Valida todos los documentos de una carpeta/tipo"""
    user = await get_current_user(authorization)
    
    # Obtener documentos no validados de esta carpeta
    docs = await db.documents.find({
        "tipo_documento": tipo_documento,
        "status": DocumentStatus.CARGADO
    }, {"_id": 0, "id": 1, "filename": 1}).to_list(1000)
    
    if not docs:
        return {"success": True, "validated": 0, "message": "No hay documentos pendientes de validar"}
    
    validated = 0
    errors = []
    
    for doc in docs:
        try:
            # Llamar a la validación individual
            await validate_document(doc['id'], authorization)
            validated += 1
        except HTTPException as e:
            errors.append({"filename": doc['filename'], "error": e.detail})
        except Exception as e:
            errors.append({"filename": doc['filename'], "error": str(e)})
    
    await log_action(user, "VALIDATE_FOLDER", f"Validados {validated} documentos en {tipo_documento}")
    
    return {
        "success": True,
        "validated": validated,
        "errors": len(errors),
        "error_details": errors[:5]  # Mostrar máximo 5 errores
    }

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
                            "status": DocumentStatus.ANALIZADO,  # Cambio: ahora es ANALIZADO
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
        "status": DocumentStatus.ANALIZADO,  # Cambio: ahora es ANALIZADO
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
    """Analiza todos los documentos VALIDADOS con IA y busca correlaciones"""
    user = await get_current_user(authorization)
    logging.info("=== INICIO analyze_all_documents ===")
    
    # Verificar que todas las carpetas tengan sus documentos validados
    folder_order = [
        DocumentType.COMPROBANTE_EGRESO,
        DocumentType.CUENTA_POR_PAGAR,
        DocumentType.FACTURA,
        DocumentType.SOPORTE_PAGO
    ]
    
    # Obtener documentos validados (listos para analizar) - LIMITAR A 3 por llamada
    docs = await db.documents.find(
        {"status": DocumentStatus.VALIDADO},
        {"_id": 0}
    ).to_list(3)  # Solo 3 documentos por llamada para evitar timeout
    
    logging.info(f"Documentos a analizar: {len(docs)}")
    
    if not docs:
        return {"message": "No hay documentos pendientes de análisis", "analyzed": 0, "remaining": 0}
    
    # Contar total restante
    total_remaining = await db.documents.count_documents({"status": DocumentStatus.VALIDADO})
    logging.info(f"Total restantes: {total_remaining}")
    
    analyzed_count = 0
    errors = []
    
    for doc in docs:
        try:
            logging.info(f"Analizando: {doc['filename']}")
            # Guardar temporalmente para análisis
            temp_path = f"/tmp/{doc['id']}_{doc['filename']}"
            with open(temp_path, "wb") as f:
                f.write(doc['file_data'])
            
            # Analizar con Gemini
            analysis = await analyze_document_with_gpt(temp_path, doc['mime_type'])
            logging.info(f"Análisis completado: {doc['filename']}")
            
            # Actualizar documento con análisis
            update_data = {
                "status": DocumentStatus.ANALIZADO,
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
        "remaining": total_remaining - analyzed_count,
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
async def suggest_batches(authorization: str = Header(None), use_ai: bool = True):
    """
    Sugiere lotes automáticamente basándose en correlaciones de documentos analizados.
    
    Si use_ai=True (default), usa Claude Sonnet 4.5 para correlación inteligente.
    Si use_ai=False, usa el algoritmo básico de coincidencia por valor y tercero.
    """
    user = await get_current_user(authorization)
    
    logging.info("=== INICIO suggest_batches ===")
    logging.info(f"Usando IA: {use_ai}")
    
    # Obtener documentos analizados (sin lote asignado)
    docs = await db.documents.find(
        {
            "status": {"$in": ["en_proceso", "analizado", "validado"]},
            "$or": [
                {"batch_id": {"$exists": False}},
                {"batch_id": None}
            ]
        },
        {"_id": 0, "file_data": 0}
    ).to_list(1000)
    
    logging.info(f"Documentos encontrados: {len(docs)}")
    
    # Filtrar solo documentos con tercero Y valor
    docs_with_data = [d for d in docs if d.get('tercero') and d.get('valor')]
    logging.info(f"Documentos con tercero y valor: {len(docs_with_data)}")
    
    if not docs_with_data:
        return {"suggested_batches": [], "message": "No hay documentos analizados con datos extraídos"}
    
    # USAR CLAUDE PARA CORRELACIÓN INTELIGENTE
    if use_ai and len(docs_with_data) >= 2:
        logging.info("Usando Claude Sonnet 4.5 para correlación inteligente...")
        correlations = await correlate_documents_with_claude(docs_with_data)
        
        if correlations:
            await log_action(user, "SUGGEST_BATCHES_AI", f"Claude sugirió {len(correlations)} lotes")
            return {
                "suggested_batches": correlations,
                "total_suggestions": len(correlations),
                "message": f"Claude encontró {len(correlations)} grupos correlacionados",
                "method": "claude_ai"
            }
        else:
            logging.warning("Claude no encontró correlaciones, usando método básico...")
    
    # MÉTODO BÁSICO (fallback o si use_ai=False)
    correlations = []
    processed_docs = set()
    
    for doc in docs_with_data:
        if doc['id'] in processed_docs:
            continue
            
        valor = doc.get('valor')
        tercero = doc.get('tercero')
        
        if not valor or not tercero:
            continue
        
        matching_docs = [doc]
        
        for other_doc in docs_with_data:
            if other_doc['id'] == doc['id'] or other_doc['id'] in processed_docs:
                continue
            
            other_valor = other_doc.get('valor')
            other_tercero = other_doc.get('tercero')
            
            if not other_valor or not other_tercero:
                continue
            
            # Tercero: coincidencia parcial
            tercero_words = set(w for w in tercero.upper().split() if len(w) > 3)
            other_tercero_words = set(w for w in other_tercero.upper().split() if len(w) > 3)
            tercero_match = len(tercero_words.intersection(other_tercero_words)) >= 1
            
            # Valor: coincidencia dentro del 1%
            valor_match = abs(valor - other_valor) / valor < 0.01 if valor > 0 else False
            
            if tercero_match and valor_match:
                matching_docs.append(other_doc)
                processed_docs.add(other_doc['id'])
        
        if len(matching_docs) >= 2:
            processed_docs.add(doc['id'])
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
    
    await log_action(user, "SUGGEST_BATCHES", f"Se sugirieron {len(correlations)} lotes por correlación básica")
    
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

@api_router.delete("/documents/delete-all")
async def delete_all_documents(authorization: str = Header(None)):
    """Elimina todos los documentos, lotes y PDFs consolidados (solo admin)"""
    user = await get_current_user(authorization)
    
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden eliminar todos los documentos")
    
    # Eliminar PDFs consolidados
    pdf_result = await db.consolidated_pdfs.delete_many({})
    
    # Eliminar lotes
    batch_result = await db.batches.delete_many({})
    
    # Eliminar documentos
    doc_result = await db.documents.delete_many({})
    
    # Limpiar GridFS
    await db.fs.files.delete_many({})
    await db.fs.chunks.delete_many({})
    
    await log_action(user, "DELETE_ALL", f"Eliminados {doc_result.deleted_count} documentos, {batch_result.deleted_count} lotes, {pdf_result.deleted_count} PDFs")
    
    return {
        "success": True, 
        "deleted_documents": doc_result.deleted_count,
        "deleted_batches": batch_result.deleted_count,
        "deleted_pdfs": pdf_result.deleted_count
    }

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

@api_router.delete("/documents/folder/{tipo_documento}")
async def delete_folder_documents(tipo_documento: str, authorization: str = Header(None)):
    """Elimina todos los documentos de una carpeta/tipo que NO estén en un lote"""
    user = await get_current_user(authorization)
    
    # Validar tipo de documento
    valid_types = ['comprobante_egreso', 'cuenta_por_pagar', 'factura', 'soporte_pago']
    if tipo_documento not in valid_types:
        raise HTTPException(status_code=400, detail=f"Tipo de documento inválido. Debe ser uno de: {valid_types}")
    
    # Contar documentos en lotes (no se pueden eliminar)
    in_batch_count = await db.documents.count_documents({
        "tipo_documento": tipo_documento,
        "batch_id": {"$exists": True, "$ne": None}
    })
    
    # Eliminar documentos que NO están en un lote
    result = await db.documents.delete_many({
        "tipo_documento": tipo_documento,
        "$or": [
            {"batch_id": {"$exists": False}},
            {"batch_id": None}
        ]
    })
    
    await log_action(user, "DELETE_FOLDER", f"Eliminados {result.deleted_count} documentos de carpeta {tipo_documento}")
    
    return {
        "success": True,
        "deleted_count": result.deleted_count,
        "skipped_in_batch": in_batch_count,
        "message": f"Eliminados {result.deleted_count} documentos" + (f" ({in_batch_count} en lotes no eliminados)" if in_batch_count > 0 else "")
    }

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
    
    # Generar nombre del PDF basado en el comprobante de egreso
    pdf_filename = generate_pdf_filename_from_batch(sorted_docs)
    if not pdf_filename:
        # Fallback a consecutivo si no hay comprobante de egreso válido
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

@api_router.post("/documents/reanalyze-group")
async def reanalyze_group(document_ids: List[str], authorization: str = Header(None)):
    """Re-analiza un grupo específico de documentos Y busca nuevos documentos que coincidan"""
    user = await get_current_user(authorization)
    
    results = {"success": 0, "failed": 0, "errors": [], "new_matches": []}
    
    # Primero, re-analizar los documentos existentes del grupo
    group_terceros = set()
    group_valores = set()
    
    for doc_id in document_ids:
        try:
            doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
            if not doc:
                results["failed"] += 1
                results["errors"].append(f"Documento {doc_id} no encontrado")
                continue
            
            # Guardar temporalmente para análisis
            temp_path = f"/tmp/{doc_id}_{doc['filename']}"
            with open(temp_path, "wb") as f:
                f.write(doc['file_data'])
            
            # Re-analizar con IA
            analysis = await analyze_document_with_gpt(temp_path, doc['mime_type'])
            
            update_data = {
                "status": DocumentStatus.ANALIZADO,
                "analisis_completo": analysis
            }
            
            if analysis.get("valor") is not None:
                update_data["valor"] = analysis["valor"]
                group_valores.add(analysis["valor"])
            if analysis.get("fecha"):
                update_data["fecha"] = analysis["fecha"]
            if analysis.get("concepto"):
                update_data["concepto"] = analysis["concepto"]
            if analysis.get("tercero"):
                update_data["tercero"] = analysis["tercero"]
                group_terceros.add(analysis["tercero"].upper())
            if analysis.get("nit"):
                update_data["nit"] = analysis["nit"]
            if analysis.get("numero_documento"):
                update_data["numero_documento"] = analysis["numero_documento"]
            
            await db.documents.update_one({"id": doc_id}, {"$set": update_data})
            
            try:
                os.remove(temp_path)
            except:
                pass
            
            results["success"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"Error en {doc_id}: {str(e)}")
    
    # Segundo, buscar nuevos documentos que coincidan con el grupo
    if group_terceros or group_valores:
        # Buscar documentos analizados que no estén en un lote y que coincidan
        all_docs = await db.documents.find({
            "id": {"$nin": document_ids},  # No incluir los que ya están en el grupo
            "batch_id": {"$exists": False},  # No en un lote
            "status": {"$in": [DocumentStatus.ANALIZADO, DocumentStatus.EN_PROCESO, DocumentStatus.VALIDADO]}
        }, {"_id": 0, "file_data": 0}).to_list(1000)
        
        for doc in all_docs:
            doc_tercero = (doc.get('tercero') or '').upper()
            doc_valor = doc.get('valor')
            
            # Verificar coincidencia por tercero (coincidencia parcial)
            tercero_match = False
            for gt in group_terceros:
                if gt and doc_tercero:
                    # Coincidencia parcial: al menos 3 caracteres consecutivos iguales
                    if len(gt) >= 3 and len(doc_tercero) >= 3:
                        if gt in doc_tercero or doc_tercero in gt:
                            tercero_match = True
                            break
                        # Comparar palabras
                        gt_words = set(gt.split())
                        doc_words = set(doc_tercero.split())
                        if gt_words & doc_words:  # Intersección de palabras
                            tercero_match = True
                            break
            
            # Verificar coincidencia por valor (tolerancia del 1%)
            valor_match = False
            if doc_valor:
                for gv in group_valores:
                    if gv and abs(doc_valor - gv) / max(gv, 1) < 0.01:
                        valor_match = True
                        break
            
            # Si coincide por tercero Y valor, agregarlo a los nuevos matches
            if tercero_match and valor_match:
                results["new_matches"].append({
                    "id": doc['id'],
                    "filename": doc['filename'],
                    "tipo_documento": doc['tipo_documento'],
                    "tercero": doc.get('tercero'),
                    "valor": doc.get('valor')
                })
    
    await log_action(user, "REANALYZE_GROUP", f"Re-analizados {results['success']} documentos, {len(results['new_matches'])} nuevos coincidentes encontrados")
    
    return results

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
    
    # Generar nombre del PDF basado en el comprobante de egreso
    pdf_filename = generate_pdf_filename_from_batch(sorted_docs)
    if not pdf_filename:
        # Fallback a consecutivo si no hay comprobante de egreso válido
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

@api_router.delete("/pdfs/{pdf_id}")
async def delete_consolidated_pdf(pdf_id: str, authorization: str = Header(None)):
    """Elimina un PDF consolidado y su lote asociado"""
    user = await get_current_user(authorization)
    
    pdf = await db.consolidated_pdfs.find_one({"id": pdf_id}, {"_id": 0})
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF no encontrado")
    
    # Obtener el batch asociado
    batch = await db.batches.find_one({"id": pdf.get('batch_id')}, {"_id": 0})
    
    if batch:
        # Liberar los documentos del lote (quitar batch_id)
        await db.documents.update_many(
            {"batch_id": batch['id']},
            {"$unset": {"batch_id": ""}, "$set": {"status": DocumentStatus.ANALIZADO}}
        )
        # Eliminar el lote
        await db.batches.delete_one({"id": batch['id']})
    
    # Eliminar el PDF
    await db.consolidated_pdfs.delete_one({"id": pdf_id})
    
    await log_action(user, "DELETE_PDF", f"Eliminado PDF consolidado {pdf['filename']}")
    
    return {"success": True, "message": "PDF consolidado eliminado exitosamente"}

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