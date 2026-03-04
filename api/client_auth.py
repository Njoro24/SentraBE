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
    AuthService, OTPService, PasswordValidator, PhoneValidator
)
from api.auth import create_access_token, verify_token, TokenData

load_dotenv()

router = APIRouter(prefix="/auth", tags=["client-auth"])

# Request/Response models
class RegisterRequest(BaseModel):
    institution_name: str = Field(..., min_length=1)
    email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    phone_number: str = Field(..., min_length=10)
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

class PhoneValidationRequest(BaseModel):
    phone_number: str

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

class PhoneValidationResponse(BaseModel):
    valid: bool
    message: str


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
    Requires: institution name, work email, phone number, password.
    Returns client_id and requires email/phone verification.
    """
    
    success, message, client_id = AuthService.register(
        db,
        institution_name=request.institution_name,
        email=request.email,
        phone_number=request.phone_number,
        password=request.password,
        confirm_password=request.confirm_password
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Send OTP to email
    otp_email = OTPService.create_otp(db, client_id, 'registration', 'email')
    OTPService.send_otp_email(request.email, otp_email, 'registration')
    
    # Send OTP to phone
    otp_phone = OTPService.create_otp(db, client_id, 'registration', 'sms')
    OTPService.send_otp_sms(request.phone_number, otp_phone)
    
    return RegisterResponse(
        success=True,
        message="Registration successful. Verify your email and phone number.",
        client_id=client_id,
        requires_verification=True
    )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db)):
    """
    Login with email and password.
    Returns client_id and requires OTP verification unless device is trusted.
    """
    
    success, message, client_id = AuthService.login(db, request.email, request.password)
    
    if not success:
        raise HTTPException(status_code=401, detail=message)
    
    # Check if device is trusted
    device_fingerprint = AuthService.get_device_fingerprint(
        get_user_agent(http_request),
        get_client_ip(http_request)
    )
    
    is_trusted = AuthService.is_device_trusted(db, client_id, device_fingerprint)
    
    if is_trusted:
        # Skip OTP for trusted device
        client = db.query(Client).filter(Client.id == client_id).first()
        access_token = create_access_token(client_id, client.email)
        
        return LoginResponse(
            success=True,
            message="Login successful",
            client_id=client_id,
            requires_otp=False,
            access_token=access_token,
            token_type="bearer"
        )
    
    # Send OTP to phone and email
    otp_phone = OTPService.create_otp(db, client_id, 'login', 'sms')
    OTPService.send_otp_sms(request.phone_number, otp_phone)
    
    otp_email = OTPService.create_otp(db, client_id, 'login', 'email')
    client = db.query(Client).filter(Client.id == client_id).first()
    OTPService.send_otp_email(client.email, otp_email, 'login')
    
    # Store device info for later trust
    if request.remember_device and request.device_name:
        # Will be called after OTP verification
        pass
    
    return LoginResponse(
        success=True,
        message="OTP sent to your phone and email",
        client_id=client_id,
        requires_otp=True,
        otp_delivery_methods=["sms", "email"]
    )


@router.post("/verify-otp", response_model=OTPVerificationResponse)
async def verify_otp(request: OTPVerificationRequest, http_request: Request, db: Session = Depends(get_db)):
    """
    Verify OTP code for registration, login, or password reset.
    """
    
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
        # Check if both email and phone are verified
        email_verified = db.query(OTPRecord).filter(
            OTPRecord.client_id == request.client_id,
            OTPRecord.otp_type == 'registration',
            OTPRecord.delivery_method == 'email',
            OTPRecord.is_verified == True
        ).first()
        
        phone_verified = db.query(OTPRecord).filter(
            OTPRecord.client_id == request.client_id,
            OTPRecord.otp_type == 'registration',
            OTPRecord.delivery_method == 'sms',
            OTPRecord.is_verified == True
        ).first()
        
        if email_verified and phone_verified:
            client.email_verified = True
            client.phone_verified = True
            db.commit()
    
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


@router.post("/validate-phone", response_model=PhoneValidationResponse)
async def validate_phone(request: PhoneValidationRequest):
    """
    Validate East African phone number format in real-time.
    """
    
    is_valid, message = PhoneValidator.validate(request.phone_number)
    
    return PhoneValidationResponse(
        valid=is_valid,
        message=message
    )


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
