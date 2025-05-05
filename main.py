from fastapi import FastAPI, HTTPException, Query, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import firestore, bigquery
from typing import Optional
import unicodedata
import firebase_admin
from firebase_admin import credentials, auth, storage
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import pandas as pd
import io
from uuid import uuid4
import requests
import logging

# Inicializar Firebase Admin SDK
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {'storageBucket': 'pf25-emilio-jimenez.firebasestorage.app'})
except Exception as e:
    print(f"Error al inicializar Firebase Admin SDK: {e}")

app = FastAPI()
db = firestore.Client()

# Configuración de CORS
origins = [
    "https://pf25-emilio-jimenez.web.app/",
    "https://pf25-emilio-jimenez.firebaseapp.com/",
    "https://pf25-emilio-jimenez.web.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class User(BaseModel):
    nombre: str
    apellidos: str
    email: str
    numeroIdentificacion: str
    telefono: str
    fecha_nacimiento: str
    archivoUrl: Optional[str] = None  

def normalize_string(s: str) -> str:
    """Normaliza una cadena eliminando tildes y convirtiéndola a minúsculas."""
    s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')
    return s.lower()

def sanitize_url(url: Optional[str]) -> str:
    if isinstance(url, str) and url.startswith("http"):
        return url
    return ""

http_bearer = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(http_bearer)):
    try:
        decoded_token = auth.verify_id_token(credentials.credentials)
        uid = decoded_token.get('uid')
        if uid:
            return uid
        else:
            raise HTTPException(status_code=401, detail="Token de ID inválido")
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Token de ID inválido")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al verificar el token: {e}")

@app.post("/users", dependencies=[Depends(get_current_user)])
async def create_user(user: User, current_user: str = Depends(get_current_user)):
    print(f"Usuario autenticado (UID): {current_user}")
    try:
        sanitized_url = sanitize_url(user.archivoUrl)  
        doc_ref = db.collection("usuarios").document(user.numeroIdentificacion)
        doc_ref.set({
            "nombre": user.nombre,
            "apellidos": user.apellidos,
            "email": str(user.email),
            "numeroIdentificacion": user.numeroIdentificacion,
            "telefono": user.telefono,
            "fecha_nacimiento": user.fecha_nacimiento,
            "archivoUrl": sanitized_url, 
            "nombre_lower": normalize_string(user.nombre),
            "apellidos_lower": normalize_string(user.apellidos),
            "email_lower": normalize_string(str(user.email)),
            "numeroIdentificacion_lower": normalize_string(user.numeroIdentificacion)
        })
        insert_user_to_bigquery({
            "nombre": user.nombre,
            "apellidos": user.apellidos,
            "email": user.email,
            "numeroIdentificacion": user.numeroIdentificacion,
            "telefono": user.telefono,
            "fecha_nacimiento": user.fecha_nacimiento,
            "archivoUrl": sanitized_url
        })
        return {"message": "Usuario creado exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users", dependencies=[Depends(get_current_user)])
async def list_users(
    current_user: str = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    try:
        users = []
        docs = db.collection("usuarios").stream()
        for doc in docs:
            user_data = doc.to_dict()
            user_data["id"] = doc.id  
            users.append(user_data)

        total = len(users)
        start = (page - 1) * limit
        end = start + limit
        paginated_users = users[start:end]

        return {
            "data": paginated_users,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/search", dependencies=[Depends(get_current_user)])
async def search_users(
    filtro: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: str = Depends(get_current_user)
):
    try:
        filtro_normalizado = ""
        if filtro and isinstance(filtro, str):
            filtro_normalizado = normalize_string(filtro)

        users = []

        docs = db.collection("usuarios").stream()
        for doc in docs:
            user = doc.to_dict()

            if not (
                filtro_normalizado in user.get("nombre_lower", "") or
                filtro_normalizado in user.get("apellidos_lower", "") or
                filtro_normalizado in user.get("email_lower", "") or
                filtro_normalizado in user.get("numeroIdentificacion_lower", "") or
                filtro_normalizado in str(user.get("telefono", "")) or
                filtro_normalizado in str(user.get("fecha_nacimiento", "")) or
                filtro_normalizado in str(user.get("archivoUrl", ""))
            ):
                continue

            user["id"] = doc.id
            users.append(user)

        total = len(users)
        start = (page - 1) * limit
        end = start + limit
        paginated_users = users[start:end]

        return {
            "data": paginated_users,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RegistrationRequest(BaseModel):
    email: str
    password: str

@app.post("/register")
async def register_user(request: RegistrationRequest):
    try:
        user = auth.create_user(
            email=request.email,
            password=request.password
        )
        return {"uid": user.uid, "message": "Usuario registrado exitosamente"}
    except auth.EmailAlreadyExistsError:
        raise HTTPException(status_code=400, detail="El correo electrónico ya está en uso")
    except auth.InvalidEmailError:
        raise HTTPException(status_code=400, detail="Formato de correo electrónico inválido")
    except auth.WeakPasswordError:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al registrar el usuario: {e}")

class LoginRequest(BaseModel):
    token: str

@app.post("/login")
async def login_user(request: LoginRequest):
    try:
        decoded_token = auth.verify_id_token(request.token)
        uid = decoded_token.get('uid')
        if uid:
            return {"uid": uid, "message": "Inicio de sesión exitoso"}
        else:
            raise HTTPException(status_code=401, detail="Token de ID inválido")
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Token de ID inválido")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al iniciar sesión: {e}")
    
# Introducir archivos desde un documento de cálculo
@app.post("/users/bulk_upload", dependencies=[Depends(get_current_user)])
async def bulk_upload_users(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    try:
        # Verificar que el archivo sea de tipo Excel o CSV
        if file.content_type not in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "text/csv"]:
            raise HTTPException(status_code=400, detail="Tipo de archivo no soportado. Usa Excel (.xlsx) o CSV.")

        # Leer el contenido del archivo cargado
        contents = await file.read()

        # Leer el archivo Excel o CSV con pandas
        try:
            if file.filename.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(contents))
            else:
                df = pd.read_excel(io.BytesIO(contents), engine="openpyxl")
        except Exception as read_error:
            raise HTTPException(status_code=400, detail=f"Error al leer el archivo: {read_error}")

        # Normalizar encabezados de columnas
        df.columns = df.columns.str.strip().str.lower()

        # Verificar columnas requeridas
        required_fields = ["nombre", "apellidos", "email", "numeroidentificacion", "telefono", "fecha_nacimiento"]
        for field in required_fields:
            if field not in df.columns:
                raise HTTPException(status_code=400, detail=f"Falta la columna obligatoria: {field}")

        # Procesar cada fila
        for _, row in df.iterrows():
            archivo_url = row.get("archivourl", None)

            if pd.isna(archivo_url) or str(archivo_url).strip() == "" or not await is_valid_url(str(archivo_url).strip()):
                archivo_url = None
            else:
                archivo_url = await upload_image_from_url(str(archivo_url).strip())

            user_data = {
                "nombre": row["nombre"],
                "apellidos": row["apellidos"],
                "email": str(row["email"]),
                "numeroIdentificacion": str(row["numeroidentificacion"]),
                "telefono": str(row["telefono"]),
                "fecha_nacimiento": str(row["fecha_nacimiento"]),
                "nombre_lower": normalize_string(str(row["nombre"])),
                "apellidos_lower": normalize_string(str(row["apellidos"])),
                "email_lower": normalize_string(str(row["email"])),
                "numeroIdentificacion_lower": normalize_string(str(row["numeroidentificacion"]))
            }

            if archivo_url:
                user_data["archivoUrl"] = archivo_url

            doc_ref = db.collection("usuarios").document(str(row["numeroidentificacion"]))
            doc_ref.set(user_data)
            insert_user_to_bigquery(user_data)


        return {"message": f"{len(df)} usuarios importados correctamente."}

    except Exception as e:
        logging.exception("Error en la carga masiva de usuarios")
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {e}")


# Función para subir imagen desde URL
async def upload_image_from_url(image_url: str) -> str:
    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "application/octet-stream")
        if not content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=f"La URL no apunta a una imagen válida. Content-Type recibido: {content_type}"
            )

        file_name = f"uploads/{uuid4().hex}_{image_url.split('/')[-1]}"
        bucket = storage.bucket()
        blob = bucket.blob(file_name)
        blob.upload_from_file(io.BytesIO(response.content), content_type=content_type)
        blob.make_public()

        return blob.public_url

    except requests.exceptions.RequestException as e:
        logging.error(f"Error al descargar la imagen desde la URL: {image_url}, Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al descargar la imagen desde la URL: {e}")

    except Exception as e:
        logging.error(f"Error al subir la imagen: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al subir la imagen: {e}")


# Función para validar si una URL responde correctamente
async def is_valid_url(url: str) -> bool:
    try:
        response = requests.get(url, timeout=10)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


# Función para enviar todo a BigQuery
def insert_user_to_bigquery(user_data: dict):
    try:
        client = bigquery.Client()
        table_id = "pf25-emilio-jimenez.usuarios_dataset.usuarios"

        # Normalizar campos faltantes si no existen
        row_to_insert = {
            "nombre": user_data.get("nombre"),
            "apellidos": user_data.get("apellidos"),
            "email": user_data.get("email"),
            "numeroIdentificacion": user_data.get("numeroIdentificacion"),
            "telefono": user_data.get("telefono"),
            "fecha_nacimiento": user_data.get("fecha_nacimiento"),
            "archivoUrl": user_data.get("archivoUrl", None)
        }

        errors = client.insert_rows_json(table_id, [row_to_insert])
        if errors:
            logging.error(f"Error al insertar en BigQuery: {errors}")
    except Exception as e:
        logging.error(f"Error conectando o insertando en BigQuery: {str(e)}")
