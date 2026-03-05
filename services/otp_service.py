import resend
import os
import random
import string
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sqlalchemy.orm import Session

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")

class OTPService:
    """Service for generating and sending OTP codes via email"""
    
    OTP_LENGTH = 6
    OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRATION_MINUTES", 5))
    
    @staticmethod
    def generate_otp():
        """Generate a random 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=OTPService.OTP_LENGTH))
    
    @staticmethod
    def send_registration_otp(email: str, otp_code: str):
        """Send OTP for registration verification"""
        try:
            email_content = f"""
            <h2>Welcome to Sentra</h2>
            <p>Your email verification code is:</p>
            <h1 style="font-size: 32px; letter-spacing: 5px; color: #0f4db5;">{otp_code}</h1>
            <p>This code will expire in {OTPService.OTP_EXPIRY_MINUTES} minutes.</p>
            <p>If you didn't request this code, please ignore this email.</p>
            """
            
            response = resend.Emails.send({
                "from": "onboarding@resend.dev",
                "to": email,
                "subject": "Sentra - Email Verification Code",
                "html": email_content,
            })
            
            print(f"OTP email sent to {email}: {response}")
            return response
        except Exception as e:
            print(f"Error sending OTP email: {e}")
            raise
    
    @staticmethod
    def send_password_reset_otp(email: str, otp_code: str):
        """Send OTP for password reset"""
        try:
            email_content = f"""
            <h2>Password Reset Request</h2>
            <p>Your password reset code is:</p>
            <h1 style="font-size: 32px; letter-spacing: 5px; color: #0f4db5;">{otp_code}</h1>
            <p>This code will expire in {OTPService.OTP_EXPIRY_MINUTES} minutes.</p>
            <p>If you didn't request this, please ignore this email.</p>
            """
            
            response = resend.Emails.send({
                "from": "onboarding@resend.dev",
                "to": email,
                "subject": "Sentra - Password Reset Code",
                "html": email_content,
            })
            
            print(f"Password reset OTP sent to {email}: {response}")
            return response
        except Exception as e:
            print(f"Error sending password reset OTP: {e}")
            raise
    
    @staticmethod
    def send_welcome_email(email: str, institution_name: str):
        """Send welcome email after successful registration"""
        try:
            email_content = f"""
            <h2>Welcome to Sentra, {institution_name}!</h2>
            <p>Your account has been successfully verified.</p>
            <p>You can now log in to your dashboard and start using Sentra's fraud detection platform.</p>
            <p><a href="https://sentra.io/login" style="background-color: #0f4db5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Go to Dashboard</a></p>
            <p>If you have any questions, contact our support team at support@sentra.io</p>
            """
            
            response = resend.Emails.send({
                "from": "onboarding@resend.dev",
                "to": email,
                "subject": "Welcome to Sentra",
                "html": email_content,
            })
            
            print(f"Welcome email sent to {email}: {response}")
            return response
        except Exception as e:
            print(f"Error sending welcome email: {e}")
            raise
    
    @staticmethod
    def send_login_otp(email: str, otp_code: str):
        """Send OTP for login verification"""
        try:
            email_content = f"""
            <h2>Login Verification</h2>
            <p>Your login verification code is:</p>
            <h1 style="font-size: 32px; letter-spacing: 5px; color: #0f4db5;">{otp_code}</h1>
            <p>This code will expire in {OTPService.OTP_EXPIRY_MINUTES} minutes.</p>
            <p>If you didn't request this code, please ignore this email.</p>
            """
            
            response = resend.Emails.send({
                "from": "onboarding@resend.dev",
                "to": email,
                "subject": "Sentra - Login Verification Code",
                "html": email_content,
            })
            
            print(f"Login OTP sent to {email}: {response}")
            return response
        except Exception as e:
            print(f"Error sending login OTP: {e}")
            raise
    
    @staticmethod
    def store_otp(db: Session, client_id: int, otp_code: str, otp_type: str = "registration"):
        """Store OTP in database"""
        from data.schema import OTPRecord
        
        expires_at = datetime.utcnow() + timedelta(minutes=OTPService.OTP_EXPIRY_MINUTES)
        
        otp_record = OTPRecord(
            client_id=client_id,
            otp_code=otp_code,
            otp_type=otp_type,
            delivery_method="email",
            is_verified=False,
            expires_at=expires_at
        )
        
        db.add(otp_record)
        db.commit()
        db.refresh(otp_record)
        
        return otp_record
    
    @staticmethod
    def verify_otp(db: Session, client_id: int, otp_code: str, otp_type: str = "registration"):
        """Verify OTP code"""
        from data.schema import OTPRecord
        
        otp_record = db.query(OTPRecord).filter(
            OTPRecord.client_id == client_id,
            OTPRecord.otp_type == otp_type,
            OTPRecord.is_verified == False
        ).order_by(OTPRecord.created_at.desc()).first()
        
        if not otp_record:
            return False, "No OTP found"
        
        if datetime.utcnow() > otp_record.expires_at:
            return False, "OTP expired"
        
        if otp_record.otp_code != otp_code:
            return False, "Invalid OTP code"
        
        otp_record.is_verified = True
        db.commit()
        
        return True, "OTP verified successfully"
