import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt
from datetime import datetime, timezone
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

mongo_url = os.environ['MONGO_URL']
db_name = os.environ['DB_NAME']

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

async def init_users():
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Check if users already exist
    existing_admin = await db.users.find_one({"email": "admin@docflow.com"})
    if existing_admin:
        print("Users already initialized")
        return
    
    users = [
        {
            "id": str(uuid.uuid4()),
            "email": "admin@docflow.com",
            "nombre": "Administrador",
            "role": "admin",
            "password": hash_password("admin123"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True
        },
        {
            "id": str(uuid.uuid4()),
            "email": "operativo@docflow.com",
            "nombre": "Usuario Operativo",
            "role": "operativo",
            "password": hash_password("operativo123"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True
        },
        {
            "id": str(uuid.uuid4()),
            "email": "revisor@docflow.com",
            "nombre": "Auditor Revisor",
            "role": "revisor",
            "password": hash_password("revisor123"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True
        }
    ]
    
    await db.users.insert_many(users)
    print(f"Initialized {len(users)} users successfully")
    client.close()

if __name__ == "__main__":
    asyncio.run(init_users())
