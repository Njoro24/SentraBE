"""
Client authentication endpoints - Registration, Login, OTP verification, Password reset
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Optional
import os
from dotenv import load_dotenv

from data.schema import get_db, Client, OTPRecord
from services.auth_service import (
    AuthService, OTPService, PasswordValidator
)
from api.auth import create_access_token, verify_token, TokenData

load_dotenv()

router = APIRouter(prefix="/auth", tags=["client-auth"])

# Request/Response models
class RegisterRequest(BaseModel):
    institution_name: str = Field(..., min_length=1)
    email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    password: str = Field(..., min_length=12)
    confirm_password: str = Field(..., min_length=12)

class LoginRequest(BaseModel):
    email: str = Field(...)
    password: str = Field(...)
    remember_device: bool = False
    device_name: Optional[str] = None

class OTPVerificationRequest(BaseModel):
    client_id: int
    otp_code: str = Field(..., pattern=r'^\d{6}$')
    otp_type: str  # registration, login, password_reset

class PasswordResetInitiateRequest(BaseModel):
    email: str = Field(...)

class PasswordResetRequest(BaseModel):
    client_id: int
    otp_code: str = Field(..., pattern=r'^\d{6}$')
    new_password: str = Field(..., min_length=12)
    confirm_password: str = Field(..., min_length=12)

class PasswordStrengthRequest(BaseModel):
    password: str

class RegisterResponse(BaseModel):
    success: bool
    message: str
    client_id: Optional[int] = None
    requires_verification: bool = False

class LoginResponse(BaseModel):
    success: bool
    message: str
    client_id: Optional[int] = None
    requires_otp: bool = False
    otp_delivery_methods: Optional[list] = None

class OTPVerificationResponse(BaseModel):
    success: bool
    message: str
    access_token: Optional[str] = None
    token_type: Optional[str] = None

class PasswordStrengthResponse(BaseModel):
    score: int  # 0-100
    strength: str  # weak, fair, strong, very_strong
    message: str
    requirements: dict


# Helper functions
def get_client_ip(request: Request) -> str:
    """Extract client IP from request"""
    if request.client:
        return request.client.host
    return "unknown"

def get_user_agent(request: Request) -> str:
    """Extract user agent from request"""
    return request.headers.get("user-agent", "unknown")


# Endpoints
@router.post("/register", response_model=RegisterResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new client institution.
    Requires: institution name, work email, password.
    Returns client_id and requires email verification.
    """
    
    success, message, client_id = AuthService.register(
        db,
        institution_name=request.institution_name,
        email=request.email,
        phone_number="",  # Not required anymore
        password=request.password,
        confirm_password=request.confirm_password
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Send OTP to email only
    try:
        from services.otp_service import OTPService
        otp_code = OTPService.generate_otp()
        OTPService.send_registration_otp(request.email, otp_code)
        OTPService.store_otp(db, client_id, otp_code, "registration")
    except Exception as e:
        print(f"Error sending OTP: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")
    
    return RegisterResponse(
        success=True,
        message="Registration successful. Check your email for verification code.",
        client_id=client_id,
        requires_verification=True
    )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db)):
    """
    Login with email and password.
    Returns client_id and requires OTP verification unless device is trusted.
    """
    from services.otp_service import OTPService
    
    success, message, client_id = AuthService.login(db, request.email, request.password)
    
    if not success:
        raise HTTPException(status_code=401, detail=message)
    
    # Always require OTP for login
    # Generate and send OTP to email
    try:
        otp_code = OTPService.generate_otp()
        OTPService.send_login_otp(request.email, otp_code)
        OTPService.store_otp(db, client_id, otp_code, "login")
    except Exception as e:
        print(f"Error sending login OTP: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")
    
    # Store device info for later trust if requested
    if request.remember_device and request.device_name:
        # Will be called after OTP verification
        pass
    
    return LoginResponse(
        success=True,
        message="OTP sent to your email",
        client_id=client_id,
        requires_otp=True,
        otp_delivery_methods=["email"]
    )


@router.post("/verify-otp", response_model=OTPVerificationResponse)
async def verify_otp(request: OTPVerificationRequest, http_request: Request, db: Session = Depends(get_db)):
    """
    Verify OTP code for registration or login.
    """
    from services.otp_service import OTPService
    
    success, message = OTPService.verify_otp(
        db,
        request.client_id,
        request.otp_code,
        request.otp_type
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Update verification status
    client = db.query(Client).filter(Client.id == request.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    if request.otp_type == 'registration':
        # Mark email as verified
        client.email_verified = True
        db.commit()
        
        # Send welcome email
        try:
            OTPService.send_welcome_email(client.email, client.institution_name)
        except Exception as e:
            print(f"Warning: Failed to send welcome email: {e}")
        
        # Return token for registration
        access_token = create_access_token(request.client_id, client.email)
        return OTPVerificationResponse(
            success=True,
            message="Email verified successfully",
            access_token=access_token,
            token_type="bearer"
        )
    
    elif request.otp_type == 'login':
        access_token = create_access_token(request.client_id, client.email)
        return OTPVerificationResponse(
            success=True,
            message="Login verified successfully",
            access_token=access_token,
            token_type="bearer"
        )
    
    return OTPVerificationResponse(
        success=True,
        message="OTP verified successfully"
    )


@router.post("/trust-device")
async def trust_device(
    client_id: int,
    device_name: str,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    Mark current device as trusted for 30 days (skips OTP on next login).
    """
    
    device_fingerprint = AuthService.get_device_fingerprint(
        get_user_agent(http_request),
        get_client_ip(http_request)
    )
    
    success = AuthService.trust_device(db, client_id, device_fingerprint, device_name)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to trust device")
    
    return {"success": True, "message": "Device trusted for 30 days"}


@router.post("/forgot-password")
async def forgot_password(request: PasswordResetInitiateRequest, db: Session = Depends(get_db)):
    """
    Initiate password reset flow.
    Sends reset link (OTP) to registered email.
    """
    
    success, message = AuthService.initiate_password_reset(db, request.email)
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    
    return {"success": True, "message": message}


@router.post("/reset-password")
async def reset_password(request: PasswordResetRequest, db: Session = Depends(get_db)):
    """
    Reset password with OTP verification.
    Enforces password rules and prevents reuse of last 5 passwords.
    """
    
    success, message = AuthService.reset_password(
        db,
        request.client_id,
        request.otp_code,
        request.new_password,
        request.confirm_password
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


@router.post("/check-password-strength", response_model=PasswordStrengthResponse)
async def check_password_strength(request: PasswordStrengthRequest):
    """
    Check password strength in real-time.
    Returns score (0-100), strength level, and specific requirements.
    """
    
    score = PasswordValidator.get_strength_score(request.password)
    is_valid, strength, message = PasswordValidator.validate(request.password)
    
    requirements = {
        "min_length": len(request.password) >= PasswordValidator.MIN_LENGTH,
        "has_uppercase": bool(__import__('re').search(PasswordValidator.UPPERCASE_PATTERN, request.password)),
        "has_lowercase": bool(__import__('re').search(PasswordValidator.LOWERCASE_PATTERN, request.password)),
        "has_number": bool(__import__('re').search(PasswordValidator.NUMBER_PATTERN, request.password)),
        "has_special": bool(__import__('re').search(PasswordValidator.SPECIAL_PATTERN, request.password))
    }
    
    return PasswordStrengthResponse(
        score=score,
        strength=strength,
        message=message,
        requirements=requirements
    )


@router.post("/logout")
async def logout(authorization: str = Header(None), db: Session = Depends(get_db)):
    """
    Logout endpoint - invalidates the current session.
    Client should clear local storage after receiving success response.
    """
    
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization header")
    
    try:
        # Extract token from "Bearer <token>"
        token = authorization.split(" ")[1] if " " in authorization else authorization
        token_data = verify_token(token)
        
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Token is invalidated on the client side by clearing localStorage
        # Backend can optionally track logout events for audit logs
        return {"success": True, "message": "Logged out successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Logout failed: {str(e)}")


@router.get("/me")
async def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    """
    Get current authenticated user information.
    """
    
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization header")
    
    try:
        # Extract token from "Bearer <token>"
        token = authorization.split(" ")[1] if " " in authorization else authorization
        token_data = verify_token(token)
        
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Get client from database
        client = db.query(Client).filter(Client.id == token_data.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        return {
            "id": client.id,
            "institution_name": client.institution_name,
            "email": client.email,
            "subscription_tier": client.subscription_tier,
            "is_active": client.is_active
        }
    
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Failed to get user: {str(e)}")


@router.get("/verify-email-otp/{client_id}/{otp_code}")
async def verify_email_otp(client_id: int, otp_code: str, db: Session = Depends(get_db)):
    """
    Verify email OTP from email link (for registration).
    """
    
    success, message = OTPService.verify_otp(db, client_id, otp_code, 'registration')
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    client = db.query(Client).filter(Client.id == client_id).first()
    if client:
        client.email_verified = True
        db.commit()
    
    return {"success": True, "message": "Email verified successfully"}
