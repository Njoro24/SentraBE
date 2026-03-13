"""
JWT Middleware for FastAPI
Validates JWT tokens from Authorization header
"""

from fastapi import Depends, HTTPException, status, Header
from typing import Optional, Dict
import jwt
from .jwt_handler import decode_token, JWT_ALGORITHM, JWT_SECRET_KEY


async def verify_jwt_token(authorization: Optional[str] = Header(None)) -> Dict:
    """
    FastAPI dependency to verify JWT token from Authorization header.
    
    Args:
        authorization: Authorization header value (e.g., "Bearer <token>")
    
    Returns:
        Decoded token payload
    
    Raises:
        HTTPException: 401 if token is missing, invalid, or expired
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Extract token from "Bearer <token>" format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = parts[1]
    
    try:
        payload = decode_token(token)
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.DecodeError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not decode token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )
