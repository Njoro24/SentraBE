from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import secrets
import os

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pydantic models
class TokenData(BaseModel):
    client_id: int
    email: str

class Token(BaseModel):
    access_token: str
    token_type: str
    client_id: int
    name: str
    email: str
    subscription_tier: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    subscription_tier: str = "starter"

class LoginRequest(BaseModel):
    email: str
    password: str

class ClientResponse(BaseModel):
    id: int
    name: str
    email: str
    subscription_tier: str
    api_key: str
    is_active: bool
    created_at: datetime

# Password functions
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# JWT functions
def create_access_token(client_id: int, email: str, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"client_id": client_id, "email": email, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        client_id: int = payload.get("client_id")
        email: str = payload.get("email")
        if client_id is None or email is None:
            return None
        return TokenData(client_id=client_id, email=email)
    except JWTError:
        return None

# API Key generation
def generate_api_key() -> str:
    return secrets.token_urlsafe(32)
