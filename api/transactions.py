"""
Transaction analysis endpoint - handles fraud scoring and real-time alerts
"""

import pickle
import json
import time
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from kafka import KafkaProducer
import numpy as np
import pandas as pd

from data.schema import get_db, Client, Transaction, FraudScore
from api.auth import verify_token
from api.fraud_rules import calculate_fraud_score as calculate_fraud_score_rules

router = APIRouter(prefix="/transactions", tags=["transactions"])

# Global model and Kafka producer
fraud_model = None
kafka_producer = None


def load_fraud_model():
    """Load the trained fraud detection model"""
    global fraud_model
    try:
        import os
        # Try multiple paths
        paths_to_try = [
            'fraud_model.pkl',
            os.path.join(os.path.dirname(__file__), '..', 'fraud_model.pkl'),
            '/home/meshack-gikonyo/MY-Projects/Bank/SentraBE/fraud_model.pkl'
        ]
        
        for model_path in paths_to_try:
            if os.path.exists(model_path):
                with open(model_path, 'rb') as f:
                    fraud_model = pickle.load(f)
                    print(f"✓ Fraud model loaded successfully from {model_path}")
                    return True
        
        print(f"✗ Fraud model not found in any of: {paths_to_try}")
        return False
    except Exception as e:
        print(f"✗ Failed to load fraud model: {e}")
        import traceback
        traceback.print_exc()
        return False


def init_kafka_producer():
    """Initialize Kafka producer for alerts"""
    global kafka_producer
    try:
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # Get Kafka bootstrap servers from environment
        kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092').split(',')
        
        print(f"Attempting to connect to Kafka at: {kafka_servers}")
        
        kafka_producer = KafkaProducer(
            bootstrap_servers=kafka_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            acks='all',
            retries=3,
            request_timeout_ms=10000,
            connections_max_idle_ms=540000
        )
        print("✓ Kafka producer initialized successfully")
        return True
    except Exception as e:
        print(f"⚠ Kafka producer initialization failed: {e}")
        print("⚠ Continuing without Kafka - alerts will not be sent to Kafka")
        print("⚠ Make sure Docker containers are running: docker-compose up -d")
        return False


class TransactionRequest(BaseModel):
    """Transaction scoring request"""
    transaction_id: str = Field(..., description="Unique transaction ID")
    amount: float = Field(..., gt=0, description="Transaction amount")
    phone_number: str = Field(..., description="Customer phone number")
    device_id: str = Field(..., description="Device identifier")
    location: str = Field(..., description="Transaction location")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    merchant_category: str = Field(default="General", description="Merchant category")
    country: str = Field(default="KE", description="Country code")


class FraudScoreResponse(BaseModel):
    """Fraud score response"""
    transaction_id: str
    risk_score: float
    risk_level: str
    recommendation: str
    processing_time_ms: float
    model_version: str = "1.0.0"


@router.post("/analyze", response_model=FraudScoreResponse)
async def analyze_transaction(
    request: TransactionRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Analyze a transaction for fraud risk using the trained ML model.
    
    Returns risk score (0-100) and recommendation (APPROVE/FLAG/BLOCK).
    Sends fraud alerts to Kafka for real-time streaming.
    """
    
    # Authentication
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.replace("Bearer ", "")
    token_data = verify_token(token)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    client = db.query(Client).filter(Client.id == token_data.client_id).first()
    if not client or not client.is_active:
        raise HTTPException(status_code=403, detail="Client not found or inactive")
    
    start_time = time.time()
    
    try:
        # Load model if not already loaded
        if fraud_model is None:
            load_fraud_model()
        
        if fraud_model is None:
            raise HTTPException(status_code=503, detail="Fraud model not loaded")
        
        # Extract model components
        model = fraud_model['model']
        scaler = fraud_model['scaler']
        feature_names = fraud_model['feature_names']
        
        # Engineer features for the transaction
        features = engineer_transaction_features(request, db=db, phone_number=request.phone_number)
        
        # Create feature vector matching model training
        X = pd.DataFrame([features])
        X = X[feature_names].fillna(0)
        
        # Scale features
        X_scaled = scaler.transform(X)
        
        # Get prediction from trained model
        # Model can be 2-class (old) or 3-class (new)
        y_pred_proba = model.predict_proba(X_scaled)[0]
        num_classes = len(y_pred_proba)
        
        if num_classes == 3:
            # New 3-class model: 0=APPROVE, 1=FLAG, 2=BLOCK
            y_pred_class = model.predict(X_scaled)[0]
            class_to_recommendation = {0: "APPROVE", 1: "FLAG", 2: "BLOCK"}
            class_to_risk_level = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}
            
            recommendation = class_to_recommendation[y_pred_class]
            risk_level = class_to_risk_level[y_pred_class]
            
            if y_pred_class == 2:  # BLOCK
                risk_score = int(y_pred_proba[2] * 100)
            elif y_pred_class == 1:  # FLAG
                risk_score = int((y_pred_proba[1] + y_pred_proba[2]) * 50)
            else:  # APPROVE
                risk_score = int(y_pred_proba[0] * 30)
            
            print(f"✓ 3-Class Model: {recommendation} (score {risk_score})")
            print(f"  Probabilities: APPROVE={y_pred_proba[0]:.3f}, FLAG={y_pred_proba[1]:.3f}, BLOCK={y_pred_proba[2]:.3f}")
        else:
            # Old 2-class model: 0=APPROVE, 1=FRAUD
            risk_score_normalized = y_pred_proba[1]
            risk_score = int(risk_score_normalized * 100)
            
            if risk_score >= 70:
                risk_level = "HIGH"
                recommendation = "BLOCK"
            elif risk_score >= 40:
                risk_level = "MEDIUM"
                recommendation = "FLAG"
            else:
                risk_level = "LOW"
                recommendation = "APPROVE"
            
            print(f"✓ 2-Class Model: {recommendation} (score {risk_score})")
        
        
        print(f"Transaction {request.transaction_id}: score={risk_score}, level={risk_level}")
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Store transaction in database
        try:
            transaction = Transaction(
                client_id=client.id,
                transaction_id=request.transaction_id,
                amount=request.amount,
                phone_number=request.phone_number,
                device_id=request.device_id,
                location=request.location,
                timestamp=datetime.fromisoformat(request.timestamp)
            )
            db.add(transaction)
            
            fraud_score_record = FraudScore(
                client_id=client.id,
                transaction_id=request.transaction_id,
                risk_score=risk_score,
                risk_level=risk_level,
                velocity_signal=features.get('velocity_ratio', 0),
                amount_anomaly_signal=features.get('amount_per_tx_24h', 0),
                device_new_signal=features.get('device_risk', 0),
                location_change_signal=features.get('geographic_risk', 0),
                recommendation=recommendation,
                processing_time_ms=processing_time_ms
            )
            db.add(fraud_score_record)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Warning: Failed to store score in database: {e}")
        
        # Send fraud alert to Kafka if HIGH risk
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
                        'timestamp': datetime.utcnow().isoformat(),
                        'phone_number': request.phone_number,
                        'location': request.location,
                        'signals': {
                            'velocity': features.get('velocity_ratio', 0),
                            'amount_anomaly': features.get('amount_per_tx_24h', 0),
                            'device_new': features.get('device_risk', 0),
                            'location_change': features.get('geographic_risk', 0)
                        }
                    }
                    future = kafka_producer.send('sentra.alerts.fraud', kafka_event)
                    future.get(timeout=5)  # Wait for confirmation
                    print(f"✓ Streamed to Kafka: {request.transaction_id}")
                except Exception as e:
                    print(f"✗ Kafka error: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"⚠ Kafka producer not initialized")
        
        return FraudScoreResponse(
            transaction_id=request.transaction_id,
            risk_score=risk_score,
            risk_level=risk_level,
            recommendation=recommendation,
            processing_time_ms=round(processing_time_ms, 2)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")


def engineer_transaction_features(request: TransactionRequest, db: Session = None, phone_number: str = None) -> dict:
    """Engineer features from transaction data using actual historical patterns"""
    from datetime import timedelta
    from sqlalchemy import func
    
    # Parse timestamp
    try:
        ts = datetime.fromisoformat(request.timestamp)
        hour = ts.hour
        day_of_week = ts.weekday()
    except:
        ts = datetime.utcnow()
        hour = ts.hour
        day_of_week = ts.weekday()
    
    # Time-based features
    is_night = 1 if (hour < 6 or hour > 22) else 0
    is_weekend = 1 if day_of_week >= 5 else 0
    
    # Amount features
    log_amount = np.log1p(request.amount)
    
    # Merchant risk
    high_risk_merchants = ['Online Gambling', 'Money Transfer', 'Gift Cards', 'Crypto', 'Wire Transfer']
    merchant_risk_score = 0.8 if request.merchant_category in high_risk_merchants else 0.3
    
    # Geographic risk
    high_risk_countries = ['CN', 'RU', 'PK', 'BR', 'NG', 'VN']
    is_foreign = 1 if request.country != 'KE' else 0
    country_fraud_rate = 0.08 if request.country in high_risk_countries else 0.03
    geographic_risk = country_fraud_rate * (1 + is_foreign)
    
    # Initialize defaults
    device_is_new = 1
    velocity_ratio = 1.0
    amount_per_tx_24h = request.amount
    tx_count_24h = 1
    tx_count_7d = 1
    days_since_last = 1
    unique_merchants_24h = 1
    declined_attempts_24h = 0
    age_days = 1
    
    # Query historical data if database available
    if db and phone_number:
        try:
            # Get all transactions for this phone number
            historical_txns = db.query(Transaction).filter(
                Transaction.phone_number == phone_number
            ).order_by(Transaction.timestamp.desc()).all()
            
            if historical_txns:
                # Account age
                oldest_txn = historical_txns[-1]
                age_days = max((ts - oldest_txn.timestamp).days, 1)
                
                # Device analysis
                known_devices = {txn.device_id for txn in historical_txns}
                device_is_new = 1 if request.device_id not in known_devices else 0
                
                # 24-hour window analysis
                window_24h = ts - timedelta(hours=24)
                recent_24h = [txn for txn in historical_txns if txn.timestamp >= window_24h]
                tx_count_24h = len(recent_24h)
                
                if recent_24h:
                    # Velocity calculation
                    time_span_hours = (ts - recent_24h[-1].timestamp).total_seconds() / 3600
                    velocity_ratio = tx_count_24h / max(time_span_hours, 1)
                    
                    # Amount per transaction
                    total_amount_24h = sum(txn.amount for txn in recent_24h)
                    amount_per_tx_24h = total_amount_24h / len(recent_24h)
                    
                    # Unique merchants (using location as proxy)
                    unique_merchants_24h = len(set(txn.location for txn in recent_24h))
                
                # 7-day window
                window_7d = ts - timedelta(days=7)
                tx_count_7d = len([txn for txn in historical_txns if txn.timestamp >= window_7d])
                
                # Days since last transaction
                if len(historical_txns) > 0:
                    days_since_last = max((ts - historical_txns[0].timestamp).days, 0)
                
                # Check for declined attempts (using fraud scores as proxy)
                declined_attempts_24h = db.query(FraudScore).filter(
                    FraudScore.transaction_id.in_([txn.transaction_id for txn in recent_24h]),
                    FraudScore.recommendation == 'BLOCK'
                ).count()
                
        except Exception as e:
            print(f"Warning: Could not fetch historical data: {e}")
    
    # Calculate derived risk scores
    device_risk = device_is_new * 0.7  # New devices are risky
    
    # Velocity risk (high transaction frequency)
    if velocity_ratio > 5:
        velocity_risk = 0.9
    elif velocity_ratio > 2:
        velocity_risk = 0.6
    else:
        velocity_risk = 0.2
    
    # Time risk
    time_risk = (is_night * 0.4 + is_weekend * 0.2)
    
    # Merchant amount risk
    merchant_amount_risk = (merchant_risk_score * log_amount / 10)
    
    # New account risk
    if age_days < 7:
        account_age_risk = 0.8
    elif age_days < 30:
        account_age_risk = 0.5
    else:
        account_age_risk = 0.1
    
    # Multiple merchants risk
    if unique_merchants_24h > 5:
        merchant_diversity_risk = 0.7
    elif unique_merchants_24h > 3:
        merchant_diversity_risk = 0.4
    else:
        merchant_diversity_risk = 0.1
    
    # Construct feature dict
    features = {
        'log_amount': log_amount,
        'log_distance': np.log1p(5),  # Default distance
        'hours_since_midnight': hour,
        'day_of_week': day_of_week,
        'is_weekend': is_weekend,
        'is_night': is_night,
        'merchant_risk_score': merchant_risk_score,
        'is_foreign': is_foreign,
        'country_fraud_rate': country_fraud_rate,
        'log_tx_count_24h': np.log1p(tx_count_24h),
        'transaction_count_7d': tx_count_7d,
        'days_since_last_transaction': days_since_last,
        'unique_merchants_24h': unique_merchants_24h,
        'declined_attempts_24h': declined_attempts_24h,
        'device_is_new': device_is_new,
        'ip_is_vpn': 0,  # Would need IP analysis service
        'age_days': age_days,
        'velocity_ratio': velocity_ratio,
        'amount_per_tx_24h': amount_per_tx_24h,
        'geographic_risk': geographic_risk,
        'device_risk': device_risk,
        'time_risk': time_risk,
        'merchant_amount_risk': merchant_amount_risk,
        'has_recent_declines': 1 if declined_attempts_24h > 0 else 0,
        'velocity_risk': velocity_risk,
        'account_age_risk': account_age_risk,
        'merchant_diversity_risk': merchant_diversity_risk
    }
    
    return features


def calculate_risk_score(features: dict) -> int:
    """Calculate fraud risk score based on features (0-100)"""
    
    score = 0
    
    # Amount risk (high amounts = higher risk)
    log_amount = features.get('log_amount', 0)
    score += min(log_amount * 5, 20)  # Max 20 points
    
    # Merchant risk
    merchant_risk = features.get('merchant_risk_score', 0)
    score += merchant_risk * 25  # Max 25 points
    
    # Geographic risk
    geographic_risk = features.get('geographic_risk', 0)
    score += geographic_risk * 20  # Max 20 points
    
    # Device risk
    device_risk = features.get('device_risk', 0)
    score += device_risk * 15  # Max 15 points
    
    # Time risk (night transactions = higher risk)
    time_risk = features.get('time_risk', 0)
    score += time_risk * 10  # Max 10 points
    
    # Velocity risk
    velocity_ratio = features.get('velocity_ratio', 0)
    score += min(velocity_ratio * 5, 10)  # Max 10 points
    
    # Declined attempts
    declined = features.get('has_recent_declines', 0)
    score += declined * 5  # Max 5 points
    
    return min(int(score), 100)  # Cap at 100
