"""
Alert Feedback API
Handles analyst feedback on fraud alerts for continuous learning
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from sqlalchemy import func
import logging

from data.schema import get_db, AlertFeedback, FraudScore, Client
from api.auth import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["feedback"])


class FeedbackRequest(BaseModel):
    marked_status: str  # correct, incorrect, escalate
    analyst_notes: str = None
    analyst_recommendation: str = None  # What analyst thinks it should be


class FeedbackResponse(BaseModel):
    id: int
    alert_id: str
    transaction_id: str
    marked_status: str
    analyst_notes: str
    created_at: datetime


class FeedbackStats(BaseModel):
    total_alerts_marked: int
    correct_count: int
    incorrect_count: int
    escalate_count: int
    accuracy_percentage: float
    by_risk_level: dict
    by_recommendation: dict
    recent_feedback: list


@router.post("/{alert_id}/feedback")
async def save_alert_feedback(
    alert_id: str,
    feedback: FeedbackRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Save analyst feedback on an alert
    
    Args:
        alert_id: Alert ID to mark
        feedback: Feedback data (marked_status, notes, recommendation)
        authorization: JWT token
        db: Database session
    
    Returns:
        Saved feedback record
    """
    try:
        # Verify token and get client
        token_data = verify_token(authorization)
        if not token_data:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        client_id = token_data.get("client_id")
        
        # Get fraud score to extract transaction_id and original values
        fraud_score = db.query(FraudScore).filter(
            FraudScore.transaction_id == alert_id
        ).first()
        
        if not fraud_score:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Check if feedback already exists
        existing_feedback = db.query(AlertFeedback).filter(
            AlertFeedback.alert_id == alert_id,
            AlertFeedback.client_id == client_id
        ).first()
        
        if existing_feedback:
            # Update existing feedback
            existing_feedback.marked_status = feedback.marked_status
            existing_feedback.analyst_notes = feedback.analyst_notes
            existing_feedback.analyst_recommendation = feedback.analyst_recommendation
            existing_feedback.updated_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Updated feedback for alert {alert_id}")
            return {
                "id": existing_feedback.id,
                "alert_id": existing_feedback.alert_id,
                "transaction_id": existing_feedback.transaction_id,
                "marked_status": existing_feedback.marked_status,
                "analyst_notes": existing_feedback.analyst_notes,
                "created_at": existing_feedback.created_at,
                "status": "updated"
            }
        
        # Create new feedback record
        alert_feedback = AlertFeedback(
            client_id=client_id,
            alert_id=alert_id,
            transaction_id=fraud_score.transaction_id,
            marked_status=feedback.marked_status,
            analyst_notes=feedback.analyst_notes,
            original_risk_level=fraud_score.risk_level,
            original_recommendation=fraud_score.recommendation,
            analyst_recommendation=feedback.analyst_recommendation
        )
        
        db.add(alert_feedback)
        db.commit()
        db.refresh(alert_feedback)
        
        logger.info(f"Saved feedback for alert {alert_id}: {feedback.marked_status}")
        
        return {
            "id": alert_feedback.id,
            "alert_id": alert_feedback.alert_id,
            "transaction_id": alert_feedback.transaction_id,
            "marked_status": alert_feedback.marked_status,
            "analyst_notes": alert_feedback.analyst_notes,
            "created_at": alert_feedback.created_at,
            "status": "created"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feedback/stats")
async def get_feedback_stats(
    days: int = 30,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Get feedback statistics and accuracy metrics
    
    Args:
        days: Number of days to look back (default: 30)
        authorization: JWT token
        db: Database session
    
    Returns:
        Feedback statistics and accuracy metrics
    """
    try:
        # Verify token and get client
        token_data = verify_token(authorization)
        if not token_data:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        client_id = token_data.get("client_id")
        
        # Get feedback from last N days
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        feedback_records = db.query(AlertFeedback).filter(
            AlertFeedback.client_id == client_id,
            AlertFeedback.created_at >= cutoff_date
        ).all()
        
        if not feedback_records:
            return {
                "total_alerts_marked": 0,
                "correct_count": 0,
                "incorrect_count": 0,
                "escalate_count": 0,
                "accuracy_percentage": 0.0,
                "by_risk_level": {},
                "by_recommendation": {},
                "recent_feedback": [],
                "period_days": days
            }
        
        # Calculate statistics
        total = len(feedback_records)
        correct = len([f for f in feedback_records if f.marked_status == "correct"])
        incorrect = len([f for f in feedback_records if f.marked_status == "incorrect"])
        escalate = len([f for f in feedback_records if f.marked_status == "escalate"])
        
        accuracy = (correct / total * 100) if total > 0 else 0.0
        
        # Group by risk level
        by_risk_level = {}
        for record in feedback_records:
            risk_level = record.original_risk_level
            if risk_level not in by_risk_level:
                by_risk_level[risk_level] = {"total": 0, "correct": 0, "incorrect": 0, "escalate": 0}
            
            by_risk_level[risk_level]["total"] += 1
            by_risk_level[risk_level][record.marked_status] += 1
        
        # Group by recommendation
        by_recommendation = {}
        for record in feedback_records:
            rec = record.original_recommendation
            if rec not in by_recommendation:
                by_recommendation[rec] = {"total": 0, "correct": 0, "incorrect": 0, "escalate": 0}
            
            by_recommendation[rec]["total"] += 1
            by_recommendation[rec][record.marked_status] += 1
        
        # Get recent feedback (last 10)
        recent = sorted(feedback_records, key=lambda x: x.created_at, reverse=True)[:10]
        recent_feedback = [
            {
                "alert_id": f.alert_id,
                "transaction_id": f.transaction_id,
                "marked_status": f.marked_status,
                "original_risk_level": f.original_risk_level,
                "original_recommendation": f.original_recommendation,
                "analyst_recommendation": f.analyst_recommendation,
                "created_at": f.created_at
            }
            for f in recent
        ]
        
        return {
            "total_alerts_marked": total,
            "correct_count": correct,
            "incorrect_count": incorrect,
            "escalate_count": escalate,
            "accuracy_percentage": round(accuracy, 2),
            "by_risk_level": by_risk_level,
            "by_recommendation": by_recommendation,
            "recent_feedback": recent_feedback,
            "period_days": days
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting feedback stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feedback/by-alert/{alert_id}")
async def get_alert_feedback(
    alert_id: str,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Get feedback for a specific alert
    
    Args:
        alert_id: Alert ID
        authorization: JWT token
        db: Database session
    
    Returns:
        Feedback record if exists
    """
    try:
        # Verify token and get client
        token_data = verify_token(authorization)
        if not token_data:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        client_id = token_data.get("client_id")
        
        feedback = db.query(AlertFeedback).filter(
            AlertFeedback.alert_id == alert_id,
            AlertFeedback.client_id == client_id
        ).first()
        
        if not feedback:
            return {"feedback": None, "has_feedback": False}
        
        return {
            "feedback": {
                "id": feedback.id,
                "alert_id": feedback.alert_id,
                "transaction_id": feedback.transaction_id,
                "marked_status": feedback.marked_status,
                "analyst_notes": feedback.analyst_notes,
                "analyst_recommendation": feedback.analyst_recommendation,
                "original_risk_level": feedback.original_risk_level,
                "original_recommendation": feedback.original_recommendation,
                "created_at": feedback.created_at,
                "updated_at": feedback.updated_at
            },
            "has_feedback": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting alert feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
