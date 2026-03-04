from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/sentra_db"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Create admin models with the same Base
from data.admin_schema import create_admin_models
admin_models = create_admin_models(Base)

# Models
class Client(Base):
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    institution_name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    phone_number = Column(String, unique=True, index=True)
    password_hash = Column(String)
    subscription_tier = Column(String, default="starter")  # starter, growth, enterprise
    api_key = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    transactions = relationship("Transaction", back_populates="client")
    fraud_scores = relationship("FraudScore", back_populates="client")
    sessions = relationship("Session", back_populates="client")
    otp_records = relationship("OTPRecord", back_populates="client")
    password_history = relationship("PasswordHistory", back_populates="client")
    trusted_devices = relationship("TrustedDevice", back_populates="client")

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)  # starter, growth, enterprise
    monthly_price = Column(Float)
    max_transactions = Column(Integer)
    features = Column(String)  # JSON string of features

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    token = Column(String, unique=True, index=True)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    client = relationship("Client", back_populates="sessions")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    transaction_id = Column(String, index=True)
    amount = Column(Float)
    phone_number = Column(String, index=True)
    device_id = Column(String)
    location = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    client = relationship("Client", back_populates="transactions")

class FraudScore(Base):
    __tablename__ = "fraud_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    transaction_id = Column(String, index=True)
    risk_score = Column(Float)
    risk_level = Column(String)  # LOW, MEDIUM, HIGH
    velocity_signal = Column(Float)
    amount_anomaly_signal = Column(Float)
    device_new_signal = Column(Float)
    location_change_signal = Column(Float)
    recommendation = Column(String)  # APPROVE, FLAG, BLOCK
    processing_time_ms = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    client = relationship("Client", back_populates="fraud_scores")

class ModelMetadata(Base):
    __tablename__ = "model_metadata"
    
    id = Column(Integer, primary_key=True, index=True)
    model_version = Column(String)
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    training_samples = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class OTPRecord(Base):
    __tablename__ = "otp_records"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    otp_code = Column(String)
    otp_type = Column(String)  # registration, login, password_reset
    delivery_method = Column(String)  # email, sms
    is_verified = Column(Boolean, default=False)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    client = relationship("Client", back_populates="otp_records")

class PasswordHistory(Base):
    __tablename__ = "password_history"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    password_hash = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    client = relationship("Client", back_populates="password_history")

class TrustedDevice(Base):
    __tablename__ = "trusted_devices"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    device_fingerprint = Column(String, unique=True)
    device_name = Column(String)
    trusted_until = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    client = relationship("Client", back_populates="trusted_devices")

# Create tables
def init_db():
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created successfully")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
