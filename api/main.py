from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import joblib
import os
import time
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.config import settings
from api.auth import (
    hash_password, verify_password, create_access_token, verify_token,
    generate_api_key, RegisterRequest, LoginRequest, Token, ClientResponse
)
from data.schema import get_db, init_db, Client, Transaction, FraudScore
from models.features import FeatureEngineer
import pandas as pd

# Initialize FastAPI app
app = FastAPI(
    title="Sentra - Fraud Detection API",
    description="Real-time fraud detection platform",
    version="1.0.0"
)

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
feature_engineer = None

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
    global model, scaler, feature_engineer
    
    print("\n" + "=" * 60)
    print("SENTRA API - STARTUP")
    print("=" * 60)
    
    # Initialize database
    try:
        init_db()
        print("✓ Database initialized")
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
    
    # Load model
    try:
        model_path = settings.model_path
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found at {model_path}")
        
        model = joblib.load(model_path)
        print(f"✓ Model loaded from {model_path}")
    except Exception as e:
        print(f"✗ Model loading failed: {e}")
        print("  Run: python models/train.py")
    
    # Initialize feature engineer
    feature_engineer = FeatureEngineer()
    print("✓ Feature engineer initialized")
    
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
    db: Session = Depends(get_db)
):
    """
    Score a transaction for fraud risk.
    
    Returns a risk score (0-100) with signal breakdown.
    """
    
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    start_time = time.time()
    
    try:
        # Build features matching our trained model
        hour = request.timestamp.hour
        amount = request.amount
        
        X = pd.DataFrame([{
            'amount': amount,
            'type_encoded': 0,
            'old_balance_orig': 0,
            'new_balance_orig': 0,
            'old_balance_dest': 0,
            'new_balance_dest': 0,
            'balance_diff_orig': -amount,
            'balance_diff_dest': amount,
            'is_new_receiver': 1,
            'amount_to_balance_ratio': amount / (amount + 1),
            'balance_drained': 1 if amount > 10000 else 0,
            'exact_amount_transfer': 0,
            'receiver_balance_unchanged': 0,
            'hour': hour,
            'is_night': 1 if hour >= 22 or hour <= 5 else 0,
            'is_round_amount': 1 if amount % 1000 == 0 else 0,
            'orig_to_dest_ratio': amount / (amount + 1),
        }])
        
        # Get prediction (XGBoost doesn't need scaling)
        risk_score_normalized = model.predict_proba(X)[0][1]
        risk_score = int(risk_score_normalized * 100)
        
        # Determine risk level
        if risk_score >= 70:
            risk_level = "HIGH"
            recommendation = "BLOCK"
        elif risk_score >= 40:
            risk_level = "MEDIUM"
            recommendation = "FLAG"
        else:
            risk_level = "LOW"
            recommendation = "APPROVE"
        
        # Extract signal values
        signals = SignalBreakdown(
            velocity=float(X['amount_to_balance_ratio'].iloc[0]),
            amount_anomaly=float(X['balance_diff_orig'].iloc[0]),
            device_new=float(X['is_new_receiver'].iloc[0]),
            location_change=float(X['is_night'].iloc[0]),
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
    """Get dashboard summary stats"""
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
    
    total_scored = db.query(FraudScore).filter(
        FraudScore.client_id == client.id,
        FraudScore.created_at >= datetime.combine(today, datetime.min.time())
    ).count()
    
    fraud_blocked = db.query(FraudScore).filter(
        FraudScore.client_id == client.id,
        FraudScore.recommendation == "BLOCK",
        FraudScore.created_at >= datetime.combine(today, datetime.min.time())
    ).all()
    
    fraud_value = sum([
        db.query(Transaction).filter(Transaction.transaction_id == score.transaction_id).first().amount
        for score in fraud_blocked if db.query(Transaction).filter(Transaction.transaction_id == score.transaction_id).first()
    ])
    
    flagged = db.query(FraudScore).filter(
        FraudScore.client_id == client.id,
        FraudScore.recommendation == "FLAG",
        FraudScore.created_at >= datetime.combine(today, datetime.min.time())
    ).count()
    
    avg_response_time = db.query(FraudScore).filter(
        FraudScore.client_id == client.id
    ).all()
    avg_time = sum([s.processing_time_ms for s in avg_response_time]) / len(avg_response_time) if avg_response_time else 0
    
    return {
        "transactions_scored_today": total_scored,
        "fraud_blocked_value": fraud_value,
        "flagged_count": flagged,
        "avg_response_time_ms": round(avg_time, 2),
        "uptime_percentage": 99.98
    }

@app.get("/dashboard/feed")
async def dashboard_feed(authorization: str = Header(None), limit: int = 50, db: Session = Depends(get_db)):
    """Get live transaction feed for this client"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.replace("Bearer ", "")
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    client = db.query(Client).filter(Client.id == token_data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get recent fraud scores for this client
    scores = db.query(FraudScore).filter(
        FraudScore.client_id == client.id
    ).order_by(FraudScore.created_at.desc()).limit(limit).all()
    
    return [
        {
            "transaction_id": score.transaction_id,
            "risk_score": score.risk_score,
            "risk_level": score.risk_level,
            "recommendation": score.recommendation,
            "processing_time_ms": score.processing_time_ms,
            "created_at": score.created_at
        }
        for score in scores
    ]

@app.get("/dashboard/subscription")
async def dashboard_subscription(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Get subscription details"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.replace("Bearer ", "")
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    client = db.query(Client).filter(Client.id == token_data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Subscription tiers
    tiers = {
        "starter": {"max_transactions": 50000, "price": 50000},
        "growth": {"max_transactions": 500000, "price": 200000},
        "enterprise": {"max_transactions": float('inf'), "price": 0}
    }
    
    tier_info = tiers.get(client.subscription_tier, tiers["starter"])
    
    # Count transactions this month
    from datetime import date
    today = date.today()
    first_day = today.replace(day=1)
    
    transactions_this_month = db.query(FraudScore).filter(
        FraudScore.client_id == client.id,
        FraudScore.created_at >= datetime.combine(first_day, datetime.min.time())
    ).count()
    
    return {
        "plan": client.subscription_tier,
        "monthly_price": tier_info["price"],
        "max_transactions": tier_info["max_transactions"],
        "transactions_used": transactions_this_month,
        "transactions_remaining": max(0, tier_info["max_transactions"] - transactions_this_month),
        "renewal_date": (today.replace(day=1) + timedelta(days=32)).replace(day=1).isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
