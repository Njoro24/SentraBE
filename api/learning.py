"""
Continuous Learning API
Endpoints for model improvement based on analyst feedback
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
import logging

from data.schema import get_db
from api.auth import verify_token
from services.continuous_learning import ContinuousLearningService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/analysis")
async def get_learning_analysis(
    days: int = Query(7, ge=1, le=90),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Get continuous learning analysis
    
    Args:
        days: Number of days to analyze (1-90)
        authorization: JWT token
        db: Database session
    
    Returns:
        Learning analysis with recommendations
    """
    try:
        # Verify token
        token_data = verify_token(authorization)
        if not token_data:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get analysis
        analysis = ContinuousLearningService.analyze_feedback(db, days)
        
        return analysis
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting learning analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_learning_metrics(
    days: int = Query(30, ge=1, le=90),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Get continuous learning metrics
    
    Args:
        days: Number of days to analyze (1-90)
        authorization: JWT token
        db: Database session
    
    Returns:
        Learning metrics and trends
    """
    try:
        # Verify token
        token_data = verify_token(authorization)
        if not token_data:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get metrics
        metrics = ContinuousLearningService.get_learning_metrics(db, days)
        
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting learning metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply-adjustment")
async def apply_threshold_adjustment(
    adjustment_factor: float = Query(0.95, ge=0.8, le=1.2),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Apply threshold adjustment to model
    
    Args:
        adjustment_factor: Factor to adjust threshold (0.95 = 5% lower)
        authorization: JWT token
        db: Database session
    
    Returns:
        Adjustment result
    """
    try:
        # Verify token (admin only)
        token_data = verify_token(authorization)
        if not token_data:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Apply adjustment
        result = ContinuousLearningService.apply_threshold_adjustment(adjustment_factor)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        
        logger.info(f"Threshold adjustment applied: {adjustment_factor}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying adjustment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations")
async def get_recommendations(
    days: int = Query(7, ge=1, le=90),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Get model improvement recommendations
    
    Args:
        days: Number of days to analyze (1-90)
        authorization: JWT token
        db: Database session
    
    Returns:
        List of recommendations
    """
    try:
        # Verify token
        token_data = verify_token(authorization)
        if not token_data:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get analysis
        analysis = ContinuousLearningService.analyze_feedback(db, days)
        
        return {
            "recommendations": analysis.get("recommendations", []),
            "total_recommendations": len(analysis.get("recommendations", [])),
            "high_priority": len([r for r in analysis.get("recommendations", []) if r.get("severity") == "high"]),
            "period_days": days
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
