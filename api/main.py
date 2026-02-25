from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime
import joblib
import os
import time
import sys
import numpy as np
import pandas as pd
import pickle
import json
from kafka import KafkaProducer

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.config import settings
from api.auth import (
    hash_password, verify_password, create_access_token, verify_token,
    generate_api_key, RegisterRequest, LoginRequest, Token, ClientResponse
)
from api.subscriptions import SubscriptionManager, SubscriptionInfo
from api import transactions as transactions_module
from api.transactions import router as transactions_router, load_fraud_model, init_kafka_producer
from data.schema import get_db, init_db, Client, Transaction, FraudScore
from models.features import FeatureEngineer

# Initialize FastAPI app
app = FastAPI(
    title="Sentra - Fraud Detection API",
    description="Real-time fraud detection platform",
    version="1.0.0"
)

# Include transaction router
app.include_router(transactions_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
model = None
scaler = None
feature_names = None
threshold = None
kafka_producer = None

# Pydantic models
class TransactionRequest(BaseModel):
    transaction_id: str = Field(..., description="Unique transaction ID")
    amount: float = Field(..., gt=0, description="Transaction amount in KES")
    phone_number: str = Field(..., description="Customer phone number")
    device_id: str = Field(..., description="Device identifier")
    location: str = Field(..., description="Transaction location")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Transaction timestamp")

class SignalBreakdown(BaseModel):
    velocity: float
    amount_anomaly: float
    device_new: float
    location_change: float

class ScoreResponse(BaseModel):
    transaction_id: str
    risk_score: float
    risk_level: str
    signals: SignalBreakdown
    recommendation: str
    processing_time_ms: float

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    database_connected: bool
    timestamp: datetime

# Startup event
@app.on_event("startup")
async def startup_event():
    """Load model and initialize database on startup"""
    global model, scaler, feature_names, threshold, kafka_producer
    
    print("\n" + "=" * 60)
    print("SENTRA API - STARTUP")
    print("=" * 60)
    
    # Initialize database
    try:
        init_db()
        print("✓ Database initialized")
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
    
    # Load model from pickle
    try:
        model_path = "fraud_model.pkl"
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found at {model_path}")
        
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
        
        model = model_data['model']
        scaler = model_data['scaler']
        feature_names = model_data['feature_names']
        threshold = 0.5
        
        # Also set in transactions module
        transactions_module.fraud_model = model_data
        
        print(f"✓ Model loaded from {model_path}")
        metrics = model_data.get('eval_metrics', {})
        print(f"  • Accuracy: {metrics.get('accuracy', 'N/A')}")
        print(f"  • Precision: {metrics.get('precision', 'N/A')}")
        print(f"  • Recall: {metrics.get('recall', 'N/A')}")
    except Exception as e:
        print(f"✗ Model loading failed: {e}")
        print("  Run: python3 train_fraud_model.py")
        model = None
    
    # Initialize Kafka producer
    try:
        from kafka import KafkaProducer
        kafka_producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks='all',
            retries=3
        )
        print("✓ Kafka producer ready for alerts")
    except Exception as e:
        print(f"⚠ Kafka producer not available: {e}")
        kafka_producer = None
    
    print("=" * 60 + "\n")

# Health check endpoint
@app.get("/v1/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    """Check API health status"""
    try:
        # Test database connection
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_connected = True
    except:
        db_connected = False
    
    return HealthResponse(
        status="healthy" if model and db_connected else "degraded",
        model_loaded=model is not None,
        database_connected=db_connected,
        timestamp=datetime.utcnow()
    )

# Main scoring endpoint
@app.post("/v1/score", response_model=ScoreResponse)
async def score_transaction(
    request: TransactionRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Score a transaction for fraud risk.
    
    Requires authentication. Enforces subscription limits.
    Returns a risk score (0-100) with signal breakdown.
    """
    
    # ─────────────────────────────────────────────────────────────────────────
    # AUTHENTICATION & AUTHORIZATION
    # ─────────────────────────────────────────────────────────────────────────
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.replace("Bearer ", "")
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    client = db.query(Client).filter(Client.id == token_data.client_id).first()
    if not client or not client.is_active:
        raise HTTPException(status_code=403, detail="Client not found or inactive")
    
    # ─────────────────────────────────────────────────────────────────────────
    # SUBSCRIPTION LIMIT CHECK
    # ─────────────────────────────────────────────────────────────────────────
    
    can_process, message = SubscriptionManager.can_process_transaction(client, db)
    if not can_process:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Monthly limit exceeded",
                "message": message,
                "subscription": client.subscription_tier,
                "upgrade_url": "/dashboard/subscription"
            }
        )
    
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    start_time = time.time()
    
    try:
        # Build features using proper feature engineering
        from models.feature_engineer import TransactionFeatureEngineer
        
        feature_engineer = TransactionFeatureEngineer(db=db)
        X = feature_engineer.engineer_features(
            client_id=client.id,
            amount=request.amount,
            merchant_category=getattr(request, 'merchant_category', 'General'),
            location=request.location,
            device_id=request.device_id,
            country_code=getattr(request, 'country', 'KE'),
            client_created_at=client.created_at
        )
        
        # Scale features
        X_scaled = scaler.transform(X)
        
        # Get prediction probability
        risk_score_normalized = model.predict_proba(X_scaled)[0][1]
        
        # Apply threshold
        if threshold is not None:
            is_fraud = risk_score_normalized >= threshold
        else:
            is_fraud = risk_score_normalized >= 0.5
        
        # Convert to 0-100 scale
        risk_score = int(risk_score_normalized * 100)
        
        # Determine risk level and recommendation
        if is_fraud or risk_score >= 70:
            risk_level = "HIGH"
            recommendation = "BLOCK"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
            recommendation = "FLAG"
        else:
            risk_level = "LOW"
            recommendation = "APPROVE"
        
        # Extract signal values from features
        signals = SignalBreakdown(
            velocity=float(X['velocity_ratio'].iloc[0]),
            amount_anomaly=float(X['amount_per_tx_24h'].iloc[0]),
            device_new=float(X['device_is_new'].iloc[0]),
            location_change=float(X['geographic_risk'].iloc[0]),
        )
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Create response
        response = ScoreResponse(
            transaction_id=request.transaction_id,
            risk_score=risk_score,
            risk_level=risk_level,
            signals=signals,
            recommendation=recommendation,
            processing_time_ms=round(processing_time_ms, 2)
        )
        
        # Store in database
        try:
            # Store transaction
            transaction = Transaction(
                client_id=client.id,
                transaction_id=request.transaction_id,
                amount=request.amount,
                phone_number=request.phone_number,
                device_id=request.device_id,
                location=request.location,
                timestamp=request.timestamp
            )
            db.add(transaction)
            
            # Store score
            fraud_score = FraudScore(
                client_id=client.id,
                transaction_id=request.transaction_id,
                risk_score=risk_score,
                risk_level=risk_level,
                velocity_signal=signals.velocity,
                amount_anomaly_signal=signals.amount_anomaly,
                device_new_signal=signals.device_new,
                location_change_signal=signals.location_change,
                recommendation=recommendation,
                processing_time_ms=processing_time_ms
            )
            db.add(fraud_score)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Warning: Failed to store score in database: {e}")
        
        # ── STREAM TO KAFKA ──
        print(f"DEBUG: kafka_producer = {kafka_producer}")
        print(f"DEBUG: risk_level = {risk_level}")
        if risk_level == "HIGH":
            if kafka_producer:
                try:
                    kafka_event = {
                        'transaction_id': request.transaction_id,
                        'client_id': client.id,
                        'amount': request.amount,
                        'risk_score': float(risk_score),
                        'risk_level': risk_level,
                        'recommendation': recommendation,
                        'timestamp': request.timestamp.isoformat(),
                        'signals': {
                            'velocity': signals.velocity,
                            'amount_anomaly': signals.amount_anomaly,
                            'device_new': signals.device_new,
                            'location_change': signals.location_change
                        }
                    }
                    print(f"DEBUG: Sending to Kafka: {kafka_event}")
                    future = kafka_producer.send('fraud-alerts', kafka_event)
                    future.get(timeout=5)
                    print(f"✓ Streamed to Kafka: {request.transaction_id}")
                except Exception as e:
                    print(f"✗ Kafka error: {type(e).__name__}: {e}")
            else:
                print(f"⚠ kafka_producer is None")
        else:
            print(f"⚠ risk_level is {risk_level}, not HIGH")
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")

# Root endpoint
@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "Sentra",
        "version": "1.0.0",
        "description": "Intelligent fraud detection platform",
        "docs": "/docs",
        "health": "/v1/health",
        "score": "/v1/score"
    }

# ── AUTHENTICATION ENDPOINTS ──

@app.post("/auth/register", response_model=Token)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new bank/institution"""
    # Check if email already exists
    existing_client = db.query(Client).filter(Client.email == request.email).first()
    if existing_client:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new client
    api_key = generate_api_key()
    client = Client(
        name=request.name,
        email=request.email,
        password_hash=hash_password(request.password),
        subscription_tier=request.subscription_tier,
        api_key=api_key
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    
    # Create JWT token
    access_token = create_access_token(client.id, client.email)
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        client_id=client.id,
        name=client.name,
        email=client.email,
        subscription_tier=client.subscription_tier
    )

@app.post("/auth/login", response_model=Token)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password"""
    client = db.query(Client).filter(Client.email == request.email).first()
    if not client or not verify_password(request.password, client.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not client.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")
    
    # Create JWT token
    access_token = create_access_token(client.id, client.email)
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        client_id=client.id,
        name=client.name,
        email=client.email,
        subscription_tier=client.subscription_tier
    )

@app.get("/auth/me", response_model=ClientResponse)
async def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Get current logged in user details"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.replace("Bearer ", "")
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    client = db.query(Client).filter(Client.id == token_data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    return ClientResponse(
        id=client.id,
        name=client.name,
        email=client.email,
        subscription_tier=client.subscription_tier,
        api_key=client.api_key,
        is_active=client.is_active,
        created_at=client.created_at
    )

# ── DASHBOARD ENDPOINTS ──

@app.get("/dashboard/summary")
async def dashboard_summary(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Get dashboard summary stats for this client"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.replace("Bearer ", "")
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    client = db.query(Client).filter(Client.id == token_data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get today's stats
    from datetime import date
    today = date.today()
    
    # Total scored today
    total_scored = db.query(FraudScore).filter(
        FraudScore.client_id == client.id,
        FraudScore.created_at >= datetime.combine(today, datetime.min.time())
    ).count()
    
    # Fraud blocked today
    fraud_blocked = db.query(FraudScore).filter(
        FraudScore.client_id == client.id,
        FraudScore.recommendation == "BLOCK",
        FraudScore.created_at >= datetime.combine(today, datetime.min.time())
    ).all()
    
    fraud_value = 0
    for score in fraud_blocked:
        transaction = db.query(Transaction).filter(
            Transaction.transaction_id == score.transaction_id
        ).first()
        if transaction:
            fraud_value += transaction.amount
    
    # Flagged today
    flagged = db.query(FraudScore).filter(
        FraudScore.client_id == client.id,
        FraudScore.recommendation == "FLAG",
        FraudScore.created_at >= datetime.combine(today, datetime.min.time())
    ).count()
    
    # Average response time
    all_scores = db.query(FraudScore).filter(
        FraudScore.client_id == client.id
    ).all()
    avg_time = sum([s.processing_time_ms for s in all_scores]) / len(all_scores) if all_scores else 0
    
    # Get subscription warning
    warning = SubscriptionManager.get_usage_warning(client, db)
    
    return {
        "transactions_scored_today": total_scored,
        "fraud_blocked_count": len(fraud_blocked),
        "fraud_blocked_value": fraud_value,
        "flagged_count": flagged,
        "avg_response_time_ms": round(avg_time, 2),
        "uptime_percentage": 99.98,
        "subscription_tier": client.subscription_tier,
        "usage_warning": {
            "level": warning.level,
            "message": warning.message,
            "usage_percentage": warning.usage_percentage
        }
    }

@app.get("/dashboard/feed")
async def dashboard_feed(authorization: str = Header(None), limit: int = 50, db: Session = Depends(get_db)):
    """Get live transaction feed for this client with full details"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.replace("Bearer ", "")
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    client = db.query(Client).filter(Client.id == token_data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get recent fraud scores for this client with transaction details
    scores = db.query(FraudScore).filter(
        FraudScore.client_id == client.id
    ).order_by(FraudScore.created_at.desc()).limit(limit).all()
    
    feed = []
    for score in scores:
        # Get associated transaction
        transaction = db.query(Transaction).filter(
            Transaction.transaction_id == score.transaction_id
        ).first()
        
        feed.append({
            "transaction_id": score.transaction_id,
            "amount": transaction.amount if transaction else 0,
            "phone_number": transaction.phone_number if transaction else "N/A",
            "location": transaction.location if transaction else "N/A",
            "risk_score": score.risk_score,
            "risk_level": score.risk_level,
            "recommendation": score.recommendation,
            "signals": {
                "velocity": score.velocity_signal,
                "amount_anomaly": score.amount_anomaly_signal,
                "device_new": score.device_new_signal,
                "location_change": score.location_change_signal
            },
            "processing_time_ms": score.processing_time_ms,
            "created_at": score.created_at.isoformat()
        })
    
    return feed

@app.get("/dashboard/subscription")
async def dashboard_subscription(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Get subscription details and usage for this client"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.replace("Bearer ", "")
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    client = db.query(Client).filter(Client.id == token_data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get subscription info
    subscription_info = SubscriptionManager.get_subscription_info(client, db)
    
    return subscription_info.dict()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
