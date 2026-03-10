"""
Continuous Learning Service
Processes analyst feedback to improve model thresholds and rules
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
import json
import os

from data.schema import AlertFeedback, FraudScore, ModelMetadata

logger = logging.getLogger(__name__)


class ContinuousLearningService:
    """Service for continuous model improvement based on feedback"""
    
    @staticmethod
    def analyze_feedback(db: Session, days: int = 7):
        """
        Analyze feedback from last N days to identify model improvements
        
        Args:
            db: Database session
            days: Number of days to analyze
        
        Returns:
            Analysis results with recommendations
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get all feedback from period
        feedback_records = db.query(AlertFeedback).filter(
            AlertFeedback.created_at >= cutoff_date
        ).all()
        
        if not feedback_records:
            return {
                "status": "no_data",
                "message": "No feedback data available",
                "recommendations": []
            }
        
        # Analyze by risk level
        risk_level_analysis = ContinuousLearningService._analyze_by_risk_level(feedback_records)
        
        # Analyze by recommendation
        recommendation_analysis = ContinuousLearningService._analyze_by_recommendation(feedback_records)
        
        # Generate recommendations
        recommendations = ContinuousLearningService._generate_recommendations(
            risk_level_analysis,
            recommendation_analysis,
            feedback_records
        )
        
        return {
            "status": "success",
            "period_days": days,
            "total_feedback": len(feedback_records),
            "risk_level_analysis": risk_level_analysis,
            "recommendation_analysis": recommendation_analysis,
            "recommendations": recommendations,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _analyze_by_risk_level(feedback_records):
        """Analyze feedback grouped by risk level"""
        analysis = {}
        
        for record in feedback_records:
            risk_level = record.original_risk_level
            
            if risk_level not in analysis:
                analysis[risk_level] = {
                    "total": 0,
                    "correct": 0,
                    "incorrect": 0,
                    "escalate": 0,
                    "accuracy": 0.0
                }
            
            analysis[risk_level]["total"] += 1
            
            if record.marked_status == "correct":
                analysis[risk_level]["correct"] += 1
            elif record.marked_status == "incorrect":
                analysis[risk_level]["incorrect"] += 1
            elif record.marked_status == "escalate":
                analysis[risk_level]["escalate"] += 1
        
        # Calculate accuracy for each level
        for level, data in analysis.items():
            if data["total"] > 0:
                data["accuracy"] = (data["correct"] / data["total"]) * 100
        
        return analysis
    
    @staticmethod
    def _analyze_by_recommendation(feedback_records):
        """Analyze feedback grouped by recommendation"""
        analysis = {}
        
        for record in feedback_records:
            rec = record.original_recommendation
            
            if rec not in analysis:
                analysis[rec] = {
                    "total": 0,
                    "correct": 0,
                    "incorrect": 0,
                    "escalate": 0,
                    "accuracy": 0.0
                }
            
            analysis[rec]["total"] += 1
            
            if record.marked_status == "correct":
                analysis[rec]["correct"] += 1
            elif record.marked_status == "incorrect":
                analysis[rec]["incorrect"] += 1
            elif record.marked_status == "escalate":
                analysis[rec]["escalate"] += 1
        
        # Calculate accuracy for each recommendation
        for rec, data in analysis.items():
            if data["total"] > 0:
                data["accuracy"] = (data["correct"] / data["total"]) * 100
        
        return analysis
    
    @staticmethod
    def _generate_recommendations(risk_analysis, rec_analysis, feedback_records):
        """Generate model improvement recommendations"""
        recommendations = []
        
        # Check for low accuracy in risk levels
        for level, data in risk_analysis.items():
            if data["total"] >= 5:  # Only if enough samples
                if data["accuracy"] < 70:
                    recommendations.append({
                        "type": "threshold_adjustment",
                        "severity": "high" if data["accuracy"] < 50 else "medium",
                        "target": f"risk_level_{level}",
                        "issue": f"{level} risk level has {data['accuracy']:.1f}% accuracy",
                        "action": f"Review and adjust thresholds for {level} risk classification",
                        "samples": data["total"],
                        "current_accuracy": data["accuracy"]
                    })
        
        # Check for low accuracy in recommendations
        for rec, data in rec_analysis.items():
            if data["total"] >= 5:  # Only if enough samples
                if data["accuracy"] < 70:
                    recommendations.append({
                        "type": "recommendation_adjustment",
                        "severity": "high" if data["accuracy"] < 50 else "medium",
                        "target": f"recommendation_{rec}",
                        "issue": f"{rec} recommendation has {data['accuracy']:.1f}% accuracy",
                        "action": f"Review decision logic for {rec} recommendations",
                        "samples": data["total"],
                        "current_accuracy": data["accuracy"]
                    })
        
        # Check for high false positive rate (incorrect marked as correct)
        false_positives = len([f for f in feedback_records if f.marked_status == "incorrect"])
        if false_positives > 0:
            fp_rate = (false_positives / len(feedback_records)) * 100
            if fp_rate > 20:
                recommendations.append({
                    "type": "false_positive_reduction",
                    "severity": "high" if fp_rate > 30 else "medium",
                    "target": "model_precision",
                    "issue": f"High false positive rate: {fp_rate:.1f}%",
                    "action": "Increase model threshold to reduce false positives",
                    "samples": len(feedback_records),
                    "false_positive_rate": fp_rate
                })
        
        # Check for high false negative rate (correct marked as incorrect)
        false_negatives = len([f for f in feedback_records if f.marked_status == "correct"])
        if false_negatives > 0:
            fn_rate = (false_negatives / len(feedback_records)) * 100
            if fn_rate < 30:  # Low recall
                recommendations.append({
                    "type": "false_negative_reduction",
                    "severity": "high" if fn_rate < 20 else "medium",
                    "target": "model_recall",
                    "issue": f"Low recall rate: {fn_rate:.1f}% correct detections",
                    "action": "Lower model threshold to improve fraud detection",
                    "samples": len(feedback_records),
                    "recall_rate": fn_rate
                })
        
        # Sort by severity
        recommendations.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["severity"], 3))
        
        return recommendations
    
    @staticmethod
    def apply_threshold_adjustment(adjustment_factor: float = 0.95):
        """
        Apply threshold adjustment to model
        
        Args:
            adjustment_factor: Factor to adjust threshold (0.95 = 5% lower)
        
        Returns:
            Adjustment result
        """
        try:
            model_path = "fraud_model.pkl"
            
            if not os.path.exists(model_path):
                return {
                    "status": "error",
                    "message": "Model file not found"
                }
            
            import pickle
            
            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)
            
            # Adjust threshold
            old_threshold = model_data.get('threshold', 0.5)
            new_threshold = old_threshold * adjustment_factor
            
            model_data['threshold'] = new_threshold
            model_data['adjusted_at'] = datetime.utcnow().isoformat()
            model_data['adjustment_factor'] = adjustment_factor
            
            # Save updated model
            with open(model_path, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"Threshold adjusted from {old_threshold} to {new_threshold}")
            
            return {
                "status": "success",
                "old_threshold": old_threshold,
                "new_threshold": new_threshold,
                "adjustment_factor": adjustment_factor,
                "adjusted_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error adjusting threshold: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    @staticmethod
    def get_learning_metrics(db: Session, days: int = 30):
        """
        Get continuous learning metrics
        
        Args:
            db: Database session
            days: Number of days to analyze
        
        Returns:
            Learning metrics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        feedback_records = db.query(AlertFeedback).filter(
            AlertFeedback.created_at >= cutoff_date
        ).all()
        
        if not feedback_records:
            return {
                "total_feedback": 0,
                "overall_accuracy": 0.0,
                "improvement_trend": [],
                "model_adjustments": 0
            }
        
        # Calculate overall accuracy
        correct = len([f for f in feedback_records if f.marked_status == "correct"])
        overall_accuracy = (correct / len(feedback_records)) * 100 if feedback_records else 0
        
        # Calculate daily trend
        daily_data = {}
        for record in feedback_records:
            date = record.created_at.date()
            if date not in daily_data:
                daily_data[date] = {"total": 0, "correct": 0}
            
            daily_data[date]["total"] += 1
            if record.marked_status == "correct":
                daily_data[date]["correct"] += 1
        
        improvement_trend = [
            {
                "date": str(date),
                "accuracy": (data["correct"] / data["total"] * 100) if data["total"] > 0 else 0,
                "samples": data["total"]
            }
            for date, data in sorted(daily_data.items())
        ]
        
        return {
            "total_feedback": len(feedback_records),
            "overall_accuracy": round(overall_accuracy, 2),
            "improvement_trend": improvement_trend,
            "period_days": days,
            "generated_at": datetime.utcnow().isoformat()
        }
