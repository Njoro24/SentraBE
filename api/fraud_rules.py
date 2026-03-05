"""
Rule-based fraud detection engine
Complements ML model with explicit business rules
"""
from enum import Enum
from typing import Tuple

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class Recommendation(str, Enum):
    APPROVE = "APPROVE"
    FLAG = "FLAG"
    BLOCK = "BLOCK"

def calculate_fraud_score(
    amount: float,
    location: str,
    merchant_category: str,
    device_id: str,
    is_new_device: bool,
    velocity: int,
    account_age_days: int,
    previous_declines: int
) -> Tuple[float, str, str]:
    """
    Rule-based fraud detection with three tiers: APPROVE, FLAG, BLOCK
    Returns: (risk_score, risk_level, recommendation)
    """
    risk_score = 0.0
    
    # HIGH-RISK RULES (BLOCK - score >= 70)
    # Rule 1: Very large amount + foreign location
    if amount > 150000 and location not in ["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret"]:
        risk_score += 35
    
    # Rule 2: Gambling/Crypto with large amount
    if merchant_category in ["Online Gambling", "Cryptocurrency", "Money Transfer"]:
        if amount > 50000:
            risk_score += 30
        elif amount > 20000:
            risk_score += 15
    
    # Rule 3: High velocity (multiple transactions in short time)
    if velocity > 5:
        risk_score += 25
    
    # Rule 4: New device + suspicious activity
    if is_new_device and amount > 30000:
        risk_score += 20
    
    # Rule 5: New account with large transaction
    if account_age_days < 7 and amount > 50000:
        risk_score += 25
    
    # Rule 6: Previous declined transactions
    if previous_declines >= 3:
        risk_score += 20
    
    # MEDIUM-RISK RULES (FLAG - score 40-69)
    # Rule 7: Moderate amount + foreign location
    if amount > 80000 and location not in ["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret"]:
        risk_score += 20
    
    # Rule 8: New device alone
    if is_new_device:
        risk_score += 10
    
    # Rule 9: High-risk merchant category
    if merchant_category in ["ATM Withdrawal", "Wire Transfer", "Cash Advance"]:
        if amount > 40000:
            risk_score += 15
    
    # Rule 10: Multiple high-risk signals
    high_risk_signals = 0
    if amount > 50000:
        high_risk_signals += 1
    if is_new_device:
        high_risk_signals += 1
    if velocity > 3:
        high_risk_signals += 1
    if account_age_days < 30:
        high_risk_signals += 1
    
    if high_risk_signals >= 3:
        risk_score += 15
    
    # Determine risk level and recommendation
    if risk_score >= 70:
        risk_level = RiskLevel.HIGH
        recommendation = Recommendation.BLOCK
    elif risk_score >= 40:
        risk_level = RiskLevel.MEDIUM
        recommendation = Recommendation.FLAG
    else:
        risk_level = RiskLevel.LOW
        recommendation = Recommendation.APPROVE
    
    # Cap score at 100
    risk_score = min(risk_score, 100.0)
    
    return risk_score, risk_level.value, recommendation.value
