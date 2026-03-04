"""
Comprehensive authentication service with registration, login, OTP, and password management
"""

import re
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from data.schema import Client, OTPRecord, PasswordHistory, TrustedDevice
from api.auth import hash_password, verify_password
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "noreply@sentra.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

class PasswordValidator:
    """Validate password strength according to requirements"""
    
    MIN_LENGTH = 12
    UPPERCASE_PATTERN = r'[A-Z]'
    LOWERCASE_PATTERN = r'[a-z]'
    NUMBER_PATTERN = r'\d'
    SPECIAL_PATTERN = r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]'
    
    @staticmethod
    def validate(password: str) -> Tuple[bool, str, str]:
        """
        Validate password and return (is_valid, strength, message)
        Strength: weak, fair, strong, very_strong
        """
        if len(password) < PasswordValidator.MIN_LENGTH:
            return False, "weak", f"Password must be at least {PasswordValidator.MIN_LENGTH} characters"
        
        has_upper = bool(re.search(PasswordValidator.UPPERCASE_PATTERN, password))
        has_lower = bool(re.search(PasswordValidator.LOWERCASE_PATTERN, password))
        has_number = bool(re.search(PasswordValidator.NUMBER_PATTERN, password))
        has_special = bool(re.search(PasswordValidator.SPECIAL_PATTERN, password))
        
        requirements_met = sum([has_upper, has_lower, has_number, has_special])
        
        if requirements_met < 4:
            missing = []
            if not has_upper:
                missing.append("uppercase letter")
            if not has_lower:
                missing.append("lowercase letter")
            if not has_number:
                missing.append("number")
            if not has_special:
                missing.append("special character")
            return False, "weak", f"Password must contain: {', '.join(missing)}"
        
        # Determine strength
        length_score = min(len(password) / 20, 1)  # Max 1 point
        if length_score >= 0.8:
            strength = "very_strong"
        elif length_score >= 0.6:
            strength = "strong"
        elif length_score >= 0.4:
            strength = "fair"
        else:
            strength = "weak"
        
        return True, strength, "Password meets all requirements"
    
    @staticmethod
    def get_strength_score(password: str) -> int:
        """Return strength as 0-100 score"""
        if not password:
            return 0
        
        score = 0
        score += min(len(password) * 2, 30)  # Length: max 30
        score += 10 if re.search(PasswordValidator.UPPERCASE_PATTERN, password) else 0
        score += 10 if re.search(PasswordValidator.LOWERCASE_PATTERN, password) else 0
        score += 10 if re.search(PasswordValidator.NUMBER_PATTERN, password) else 0
        score += 10 if re.search(PasswordValidator.SPECIAL_PATTERN, password) else 0
        score += 20 if len(password) >= 16 else 0  # Bonus for very long
        
        return min(score, 100)


class PhoneValidator:
    """Validate East African phone numbers"""
    
    # East African country codes
    COUNTRY_CODES = {
        'KE': '+254',  # Kenya
        'UG': '+256',  # Uganda
        'TZ': '+255',  # Tanzania
        'RW': '+250',  # Rwanda
        'ET': '+251',  # Ethiopia
        'SS': '+211',  # South Sudan
    }
    
    @staticmethod
    def validate(phone: str) -> Tuple[bool, str]:
        """Validate East African phone number format"""
        # Remove spaces and dashes
        phone = re.sub(r'[\s\-]', '', phone)
        
        # Check if it starts with + and country code
        for country, code in PhoneValidator.COUNTRY_CODES.items():
            if phone.startswith(code):
                # Should have 12-13 digits total (code + number)
                if len(phone) >= 12 and len(phone) <= 13:
                    return True, f"Valid {country} number"
        
        # Check if it's a local format (starts with 0 or 7)
        if phone.startswith('0') or phone.startswith('7'):
            if len(phone) == 10:  # Local format like 0712345678
                return True, "Valid local format"
        
        return False, "Invalid East African phone number format"


class OTPService:
    """Handle OTP generation, delivery, and verification"""
    
    OTP_LENGTH = 6
    OTP_EXPIRY_MINUTES = 10
    
    @staticmethod
    def generate_otp() -> str:
        """Generate a 6-digit OTP"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(OTPService.OTP_LENGTH)])
    
    @staticmethod
    def create_otp(db: Session, client_id: int, otp_type: str, delivery_method: str) -> str:
        """Create and store OTP record"""
        otp_code = OTPService.generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=OTPService.OTP_EXPIRY_MINUTES)
        
        otp_record = OTPRecord(
            client_id=client_id,
            otp_code=otp_code,
            otp_type=otp_type,
            delivery_method=delivery_method,
            expires_at=expires_at
        )
        db.add(otp_record)
        db.commit()
        
        return otp_code
    
    @staticmethod
    def send_otp_email(email: str, otp_code: str, otp_type: str) -> bool:
        """Send OTP via email"""
        try:
            subject_map = {
                'registration': 'Verify Your Email - Sentra Registration',
                'login': 'Your Sentra Login Code',
                'password_reset': 'Reset Your Sentra Password'
            }
            
            subject = subject_map.get(otp_type, 'Sentra Verification Code')
            
            html_body = f"""
            <html>
                <body style="font-family: Arial, sans-serif; background: #0f1419; color: #e0e0e0;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h2 style="color: #00d9ff;">Sentra Verification</h2>
                        <p>Your verification code is:</p>
                        <div style="background: #1a2332; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                            <h1 style="color: #00d9ff; letter-spacing: 5px; margin: 0;">{otp_code}</h1>
                        </div>
                        <p style="color: #999;">This code expires in 10 minutes.</p>
                        <p style="color: #999; font-size: 12px;">If you didn't request this code, please ignore this email.</p>
                    </div>
                </body>
            </html>
            """
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = SENDER_EMAIL
            msg['To'] = email
            
            msg.attach(MIMEText(html_body, 'html'))
            
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"Failed to send OTP email: {e}")
            return False
    
    @staticmethod
    def send_otp_sms(phone: str, otp_code: str) -> bool:
        """Send OTP via SMS (placeholder - integrate with SMS provider)"""
        try:
            # TODO: Integrate with SMS provider (Twilio, Africa's Talking, etc.)
            print(f"SMS to {phone}: Your Sentra verification code is {otp_code}")
            return True
        except Exception as e:
            print(f"Failed to send OTP SMS: {e}")
            return False
    
    @staticmethod
    def verify_otp(db: Session, client_id: int, otp_code: str, otp_type: str) -> Tuple[bool, str]:
        """Verify OTP code"""
        otp_record = db.query(OTPRecord).filter(
            OTPRecord.client_id == client_id,
            OTPRecord.otp_code == otp_code,
            OTPRecord.otp_type == otp_type,
            OTPRecord.is_verified == False,
            OTPRecord.expires_at > datetime.utcnow()
        ).first()
        
        if not otp_record:
            return False, "Invalid or expired OTP"
        
        otp_record.is_verified = True
        db.commit()
        
        return True, "OTP verified successfully"


class AuthService:
    """Main authentication service"""
    
    @staticmethod
    def register(db: Session, institution_name: str, email: str, phone_number: str, 
                 password: str, confirm_password: str) -> Tuple[bool, str, Optional[int]]:
        """Register a new client"""
        
        # Validate password
        is_valid, strength, msg = PasswordValidator.validate(password)
        if not is_valid:
            return False, msg, None
        
        # Validate password confirmation
        if password != confirm_password:
            return False, "Passwords do not match", None
        
        # Validate phone number
        is_valid_phone, phone_msg = PhoneValidator.validate(phone_number)
        if not is_valid_phone:
            return False, phone_msg, None
        
        # Check if email already exists
        existing_email = db.query(Client).filter(Client.email == email).first()
        if existing_email:
            return False, "Email already registered", None
        
        # Check if phone already exists
        existing_phone = db.query(Client).filter(Client.phone_number == phone_number).first()
        if existing_phone:
            return False, "Phone number already registered", None
        
        # Create new client
        from api.auth import generate_api_key
        client = Client(
            institution_name=institution_name,
            email=email,
            phone_number=phone_number,
            password_hash=hash_password(password),
            api_key=generate_api_key(),
            is_active=True,
            email_verified=False,
            phone_verified=False
        )
        
        db.add(client)
        db.commit()
        db.refresh(client)
        
        # Store password in history
        password_history = PasswordHistory(
            client_id=client.id,
            password_hash=client.password_hash
        )
        db.add(password_history)
        db.commit()
        
        return True, "Registration successful", client.id
    
    @staticmethod
    def login(db: Session, email: str, password: str) -> Tuple[bool, str, Optional[int]]:
        """Authenticate user login"""
        
        client = db.query(Client).filter(Client.email == email).first()
        
        if not client:
            return False, "Invalid email or password", None
        
        # Check if account is locked
        if client.locked_until and client.locked_until > datetime.utcnow():
            remaining = (client.locked_until - datetime.utcnow()).total_seconds() / 60
            return False, f"Account locked. Try again in {int(remaining)} minutes", None
        
        # Verify password
        if not verify_password(password, client.password_hash):
            client.failed_login_attempts += 1
            
            if client.failed_login_attempts >= 5:
                client.locked_until = datetime.utcnow() + timedelta(minutes=15)
                db.commit()
                return False, "Too many failed attempts. Account locked for 15 minutes", None
            
            db.commit()
            return False, f"Invalid email or password ({client.failed_login_attempts}/5 attempts)", None
        
        # Reset failed attempts on successful login
        client.failed_login_attempts = 0
        client.locked_until = None
        db.commit()
        
        return True, "Login successful", client.id
    
    @staticmethod
    def initiate_password_reset(db: Session, email: str) -> Tuple[bool, str]:
        """Initiate password reset flow"""
        
        client = db.query(Client).filter(Client.email == email).first()
        
        if not client:
            # Don't reveal if email exists
            return True, "If email exists, reset link will be sent"
        
        # Generate reset token (OTP)
        otp_code = OTPService.create_otp(db, client.id, 'password_reset', 'email')
        
        # Send reset link via email
        success = OTPService.send_otp_email(email, otp_code, 'password_reset')
        
        if success:
            return True, "Password reset link sent to email"
        else:
            return False, "Failed to send reset email"
    
    @staticmethod
    def reset_password(db: Session, client_id: int, otp_code: str, new_password: str, 
                      confirm_password: str) -> Tuple[bool, str]:
        """Reset password with OTP verification"""
        
        # Verify OTP
        is_valid, msg = OTPService.verify_otp(db, client_id, otp_code, 'password_reset')
        if not is_valid:
            return False, msg
        
        # Validate new password
        is_valid, strength, msg = PasswordValidator.validate(new_password)
        if not is_valid:
            return False, msg
        
        if new_password != confirm_password:
            return False, "Passwords do not match"
        
        # Check password history (last 5 passwords)
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            return False, "Client not found"
        
        recent_passwords = db.query(PasswordHistory).filter(
            PasswordHistory.client_id == client_id
        ).order_by(PasswordHistory.created_at.desc()).limit(5).all()
        
        for pwd_record in recent_passwords:
            if verify_password(new_password, pwd_record.password_hash):
                return False, "Cannot reuse one of your last 5 passwords"
        
        # Update password
        client.password_hash = hash_password(new_password)
        db.add(client)
        
        # Add to history
        password_history = PasswordHistory(
            client_id=client_id,
            password_hash=client.password_hash
        )
        db.add(password_history)
        db.commit()
        
        return True, "Password reset successfully"
    
    @staticmethod
    def get_device_fingerprint(user_agent: str, ip_address: str) -> str:
        """Generate device fingerprint from user agent and IP"""
        fingerprint_str = f"{user_agent}:{ip_address}"
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()
    
    @staticmethod
    def trust_device(db: Session, client_id: int, device_fingerprint: str, device_name: str) -> bool:
        """Mark device as trusted for 30 days"""
        try:
            trusted_device = TrustedDevice(
                client_id=client_id,
                device_fingerprint=device_fingerprint,
                device_name=device_name,
                trusted_until=datetime.utcnow() + timedelta(days=30)
            )
            db.add(trusted_device)
            db.commit()
            return True
        except Exception as e:
            print(f"Failed to trust device: {e}")
            return False
    
    @staticmethod
    def is_device_trusted(db: Session, client_id: int, device_fingerprint: str) -> bool:
        """Check if device is trusted"""
        trusted_device = db.query(TrustedDevice).filter(
            TrustedDevice.client_id == client_id,
            TrustedDevice.device_fingerprint == device_fingerprint,
            TrustedDevice.trusted_until > datetime.utcnow()
        ).first()
        
        return trusted_device is not None
