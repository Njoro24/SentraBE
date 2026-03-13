"""
JWT Token Handler
Generates and manages signed JWT tokens using HS256 algorithm
"""

import jwt
from datetime import datetime, timedelta
from typing import Dict, Optional
import os
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production-12345")
JWT_ALGORITHM = "HS256"


def generate_token(
    sub: str,
    role: str,
    expires_in_hours: int = 1
) -> str:
    """
    Generate a signed JWT token.
    
    Args:
        sub: Subject (typically user ID or username)
        role: User role (e.g., 'admin', 'analyst', 'client')
        expires_in_hours: Token expiration time in hours
    
    Returns:
        Encoded JWT token string
    """
    now = datetime.utcnow()
    exp = now + timedelta(hours=expires_in_hours)
    
    payload = {
        "sub": sub,
        "role": role,
        "exp": exp,
        "iat": now
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def decode_token(token: str) -> Optional[Dict]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded payload dict or None if invalid
    
    Raises:
        jwt.ExpiredSignatureError: If token is expired
        jwt.InvalidSignatureError: If signature is invalid
        jwt.DecodeError: If token cannot be decoded
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise
    except jwt.InvalidSignatureError:
        raise
    except jwt.DecodeError:
        raise


def verify_token(token: str) -> bool:
    """
    Verify if a token is valid and not expired.
    
    Args:
        token: JWT token string
    
    Returns:
        True if valid, False otherwise
    """
    try:
        decode_token(token)
        return True
    except:
        return False
