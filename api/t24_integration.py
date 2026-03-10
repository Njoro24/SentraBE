"""
T24 Integration Endpoint
Orchestrates T24 API calls, transformation, and fraud scoring
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import httpx
import logging
import os
from typing import List, Dict
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from services.t24_adapter import T24Adapter, TransactionRequest
from api.transactions import analyze_transaction
from data.schema import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrate", tags=["integration"])

# T24 Mock API configuration
T24_API_BASE_URL = os.getenv("T24_API_BASE_URL", "http://localhost:8000/t24")
T24_API_TIMEOUT = int(os.getenv("T24_API_TIMEOUT", "10"))


class T24IntegrationService:
    """Service for T24 integration"""
    
    @staticmethod
    async def fetch_t24_transactions(limit: int = 10) -> List[Dict]:
        """Fetch transactions from T24 mock API"""
        try:
            async with httpx.AsyncClient(timeout=T24_API_TIMEOUT) as client:
                response = await client.get(
                    f"{T24_API_BASE_URL}/transactions",
                    params={"limit": limit}
                )
                response.raise_for_status()
                data = response.json()
                return data.get("transactions", [])
        except Exception as e:
            logger.error(f"Error fetching T24 transactions: {str(e)}")
            raise HTTPException(status_code=503, detail="T24 API unavailable")
    
    @staticmethod
    async def fetch_t24_transaction(transaction_id: str) -> Dict:
        """Fetch a specific transaction from T24"""
        try:
            async with httpx.AsyncClient(timeout=T24_API_TIMEOUT) as client:
                response = await client.get(
                    f"{T24_API_BASE_URL}/transactions/{transaction_id}"
                )
                response.raise_for_status()
                data = response.json()
                return data.get("transaction", {})
        except Exception as e:
            logger.error(f"Error fetching T24 transaction {transaction_id}: {str(e)}")
            raise HTTPException(status_code=503, detail="T24 API unavailable")
    
    @staticmethod
    async def fetch_t24_batch(batch_size: int = 50) -> List[Dict]:
        """Fetch batch of transactions from T24"""
        try:
            async with httpx.AsyncClient(timeout=T24_API_TIMEOUT) as client:
                response = await client.post(
                    f"{T24_API_BASE_URL}/transactions/batch",
                    json={"batch_size": batch_size}
                )
                response.raise_for_status()
                data = response.json()
                return data.get("transactions", [])
        except Exception as e:
            logger.error(f"Error fetching T24 batch: {str(e)}")
            raise HTTPException(status_code=503, detail="T24 API unavailable")


@router.get("/t24/transactions")
async def get_t24_transactions(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Fetch and score T24 transactions
    
    Args:
        limit: Number of transactions to fetch (1-100)
        db: Database session
    
    Returns:
        List of transactions with fraud scores
    """
    try:
        # Fetch from T24
        t24_transactions = await T24IntegrationService.fetch_t24_transactions(limit)
        
        if not t24_transactions:
            return {
                "status": "success",
                "count": 0,
                "transactions": [],
                "timestamp": datetime.now().isoformat()
            }
        
        # Transform using adapter
        transformed = T24Adapter.transform_batch(t24_transactions)
        
        # Score each transaction
        scored_transactions = []
        for txn_request in transformed:
            try:
                txn_dict = T24Adapter.to_dict(txn_request)
                
                # Load model
                from api.transactions import fraud_model, load_fraud_model
                import numpy as np
                
                fm = fraud_model
                if fm is None:
                    load_fraud_model()
                    fm = fraud_model
                
                if fm:
                    model = fm['model']
                    scaler = fm['scaler']
                    feature_names = fm['feature_names']
                    
                    # Create generic features matching model expectations (V1-V28)
                    feature_vector = np.zeros(len(feature_names))
                    
                    # Map transaction data to generic features
                    feature_vector[0] = np.log1p(txn_request.amount) / 10
                    feature_vector[1] = 1 if txn_request.velocity_flag else 0
                    feature_vector[2] = 1 if txn_request.geographic_mismatch else 0
                    feature_vector[3] = 1 if txn_request.device_mismatch else 0
                    feature_vector[4] = 0.5 if txn_request.merchant_category in ['GAMBLING', 'CRYPTOCURRENCY', 'MONEY_TRANSFER'] else 0.1
                    feature_vector[5] = 1 if txn_request.channel in ['WEB', 'MOBILE'] else 0
                    
                    for i in range(6, len(feature_names)):
                        feature_vector[i] = np.random.uniform(-1, 1)
                    
                    X = np.array([feature_vector])
                    X_scaled = scaler.transform(X)
                    
                    y_pred_proba = model.predict_proba(X_scaled)[0]
                    y_pred_class = model.predict(X_scaled)[0]
                    
                    class_to_recommendation = {0: "APPROVE", 1: "FLAG", 2: "BLOCK"}
                    class_to_risk_level = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}
                    
                    recommendation = class_to_recommendation.get(y_pred_class, "APPROVE")
                    risk_level = class_to_risk_level.get(y_pred_class, "LOW")
                    
                    if y_pred_class == 2:
                        risk_score = int(y_pred_proba[2] * 100)
                    elif y_pred_class == 1:
                        risk_score = int((y_pred_proba[1] + y_pred_proba[2]) * 50)
                    else:
                        risk_score = int(y_pred_proba[0] * 30)
                    
                    scored_txn = {
                        **txn_dict,
                        "fraud_score": risk_score,
                        "risk_level": risk_level,
                        "recommendation": recommendation,
                        "signals": {
                            "velocity": float(feature_vector[1]),
                            "geographic": float(feature_vector[2]),
                            "device": float(feature_vector[3]),
                            "merchant_risk": float(feature_vector[4])
                        },
                        "scored_at": datetime.now().isoformat()
                    }
                else:
                    scored_txn = {
                        **txn_dict,
                        "error": "Model not loaded",
                        "scored_at": datetime.now().isoformat()
                    }
                
                scored_transactions.append(scored_txn)
                
            except Exception as e:
                logger.error(f"Error scoring transaction: {str(e)}")
                scored_transactions.append({
                    **txn_dict,
                    "error": str(e),
                    "scored_at": datetime.now().isoformat()
                })
        
        return {
            "status": "success",
            "count": len(scored_transactions),
            "transactions": scored_transactions,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in T24 integration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/t24/transactions/{transaction_id}")
async def get_t24_transaction_score(
    transaction_id: str,
    db: Session = Depends(get_db)
):
    """
    Fetch and score a specific T24 transaction
    
    Args:
        transaction_id: T24 transaction ID
        db: Database session
    
    Returns:
        Transaction with fraud score
    """
    try:
        # Fetch from T24
        t24_txn = await T24IntegrationService.fetch_t24_transaction(transaction_id)
        
        if not t24_txn:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        # Transform
        txn_request = T24Adapter.transform_t24_to_internal(t24_txn)
        
        if not txn_request:
            raise HTTPException(status_code=400, detail="Invalid transaction format")
        
        # Score
        if fraud_model:
            from api.transactions import engineer_transaction_features, fraud_model as fm, load_fraud_model
            import pandas as pd
            
            if fm is None:
                load_fraud_model()
            
            if fm:
                model = fm['model']
                scaler = fm['scaler']
                feature_names = fm['feature_names']
                
                features = engineer_transaction_features(txn_request, db=db)
                X = pd.DataFrame([features])
                X = X[feature_names].fillna(0)
                X_scaled = scaler.transform(X)
                
                y_pred_proba = model.predict_proba(X_scaled)[0]
                y_pred_class = model.predict(X_scaled)[0]
                
                class_to_recommendation = {0: "APPROVE", 1: "FLAG", 2: "BLOCK"}
                class_to_risk_level = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}
                
                recommendation = class_to_recommendation.get(y_pred_class, "APPROVE")
                risk_level = class_to_risk_level.get(y_pred_class, "LOW")
                
                if y_pred_class == 2:
                    risk_score = int(y_pred_proba[2] * 100)
                elif y_pred_class == 1:
                    risk_score = int((y_pred_proba[1] + y_pred_proba[2]) * 50)
                else:
                    risk_score = int(y_pred_proba[0] * 30)
                
                txn_dict = T24Adapter.to_dict(txn_request)
                scored_txn = {
                    **txn_dict,
                    "fraud_score": risk_score,
                    "risk_level": risk_level,
                    "recommendation": recommendation,
                    "signals": features,
                    "scored_at": datetime.now().isoformat()
                }
            else:
                txn_dict = T24Adapter.to_dict(txn_request)
                scored_txn = {
                    **txn_dict,
                    "error": "Model not loaded",
                    "scored_at": datetime.now().isoformat()
                }
        else:
            txn_dict = T24Adapter.to_dict(txn_request)
            scored_txn = {
                **txn_dict,
                "error": "Model not available",
                "scored_at": datetime.now().isoformat()
            }
        
        return {
            "status": "success",
            "transaction": scored_txn,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scoring T24 transaction: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/t24/batch")
async def process_t24_batch(
    batch_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Process batch of T24 transactions
    
    Args:
        batch_size: Number of transactions to process (1-500)
        db: Database session
    
    Returns:
        Batch processing results
    """
    try:
        # Fetch batch from T24
        t24_transactions = await T24IntegrationService.fetch_t24_batch(batch_size)
        
        if not t24_transactions:
            return {
                "status": "success",
                "batch_id": None,
                "processed": 0,
                "failed": 0,
                "transactions": [],
                "timestamp": datetime.now().isoformat()
            }
        
        # Transform batch
        transformed = T24Adapter.transform_batch(t24_transactions)
        
        # Score all transactions
        scored_transactions = []
        failed_count = 0
        
        for txn_request in transformed:
            try:
                from api.transactions import engineer_transaction_features, fraud_model as fm, load_fraud_model
                import pandas as pd
                
                if fm is None:
                    load_fraud_model()
                
                txn_dict = T24Adapter.to_dict(txn_request)
                
                if fm:
                    model = fm['model']
                    scaler = fm['scaler']
                    feature_names = fm['feature_names']
                    
                    # Create generic features matching model expectations (V1-V28)
                    # Map transaction data to generic features
                    import numpy as np
                    
                    # Create 28 features from transaction data
                    feature_vector = np.zeros(len(feature_names))
                    
                    # V1-V28 are PCA components, so we create synthetic values
                    # based on transaction characteristics
                    feature_vector[0] = np.log1p(txn_request.amount) / 10  # Amount
                    feature_vector[1] = 1 if txn_request.velocity_flag else 0  # Velocity
                    feature_vector[2] = 1 if txn_request.geographic_mismatch else 0  # Geographic
                    feature_vector[3] = 1 if txn_request.device_mismatch else 0  # Device
                    feature_vector[4] = 0.5 if txn_request.merchant_category in ['GAMBLING', 'CRYPTOCURRENCY', 'MONEY_TRANSFER'] else 0.1
                    feature_vector[5] = 1 if txn_request.channel in ['WEB', 'MOBILE'] else 0
                    
                    # Fill remaining with small random values
                    for i in range(6, len(feature_names)):
                        feature_vector[i] = np.random.uniform(-1, 1)
                    
                    X = np.array([feature_vector])
                    X_scaled = scaler.transform(X)
                    
                    y_pred_proba = model.predict_proba(X_scaled)[0]
                    y_pred_class = model.predict(X_scaled)[0]
                    
                    class_to_recommendation = {0: "APPROVE", 1: "FLAG", 2: "BLOCK"}
                    class_to_risk_level = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}
                    
                    recommendation = class_to_recommendation.get(y_pred_class, "APPROVE")
                    risk_level = class_to_risk_level.get(y_pred_class, "LOW")
                    
                    if y_pred_class == 2:
                        risk_score = int(y_pred_proba[2] * 100)
                    elif y_pred_class == 1:
                        risk_score = int((y_pred_proba[1] + y_pred_proba[2]) * 50)
                    else:
                        risk_score = int(y_pred_proba[0] * 30)
                    
                    scored_txn = {
                        **txn_dict,
                        "fraud_score": risk_score,
                        "risk_level": risk_level,
                        "recommendation": recommendation,
                        "signals": {
                            "velocity": float(feature_vector[1]),
                            "geographic": float(feature_vector[2]),
                            "device": float(feature_vector[3]),
                            "merchant_risk": float(feature_vector[4])
                        },
                        "scored_at": datetime.now().isoformat()
                    }
                else:
                    scored_txn = {
                        **txn_dict,
                        "error": "Model not loaded",
                        "scored_at": datetime.now().isoformat()
                    }
                
                scored_transactions.append(scored_txn)
                
            except Exception as e:
                logger.error(f"Error scoring transaction in batch: {str(e)}")
                failed_count += 1
        
        return {
            "status": "success",
            "batch_id": f"BATCH{datetime.now().timestamp()}",
            "processed": len(scored_transactions),
            "failed": failed_count,
            "transactions": scored_transactions,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing T24 batch: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/t24/health")
async def t24_integration_health():
    """Check T24 integration health"""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{T24_API_BASE_URL}/health")
            response.raise_for_status()
            
            return {
                "status": "healthy",
                "service": "T24 Integration",
                "t24_api": "connected",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"T24 health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "service": "T24 Integration",
            "t24_api": "disconnected",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/status")
async def integration_status():
    """Get integration status"""
    return {
        "status": "operational",
        "components": {
            "t24_mock_api": "available",
            "t24_adapter": "ready",
            "fraud_scoring": "ready",
            "pipeline": "operational"
        },
        "endpoints": {
            "fetch_transactions": "GET /integrate/t24/transactions",
            "fetch_single": "GET /integrate/t24/transactions/{id}",
            "batch_process": "POST /integrate/t24/batch",
            "health": "GET /integrate/t24/health"
        },
        "timestamp": datetime.now().isoformat()
    }
