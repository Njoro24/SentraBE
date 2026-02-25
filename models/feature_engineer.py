"""
Transaction Feature Engineering - Maps raw transaction data to 24 model features
"""

import numpy as np
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from data.schema import Transaction, FraudScore


class TransactionFeatureEngineer:
    """Engineer features from transaction data for fraud detection model"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def engineer_features(self, client_id: int, amount: float, merchant_category: str,
                         location: str, device_id: str, country_code: str = None,
                         client_created_at: datetime = None) -> pd.DataFrame:
        """
        Engineer 24 features from transaction data
        Returns: DataFrame with 24 features ready for model prediction
        """
        
        # Get client transaction history
        recent_txns = self.db.query(Transaction).filter(
            Transaction.client_id == client_id
        ).order_by(Transaction.timestamp.desc()).limit(100).all()
        
        # Time features
        now = datetime.utcnow()
        hour = now.hour
        day_of_week = now.weekday()
        is_night = 1 if (hour < 6 or hour > 22) else 0
        is_weekend = 1 if day_of_week >= 5 else 0
        
        # Amount features
        log_amount = np.log1p(amount)
        
        # Velocity features (transactions in last 24h)
        txns_24h = [t for t in recent_txns if (now - t.timestamp).total_seconds() < 86400]
        tx_count_24h = len(txns_24h)
        amount_24h = sum(t.amount for t in txns_24h)
        velocity_ratio = (amount / (amount_24h + 1)) if amount_24h > 0 else 1.0
        
        # Merchant risk scoring
        high_risk_merchants = ['Online Gambling', 'Money Transfer', 'Gift Cards', 'Crypto', 'Wire Transfer']
        merchant_risk = 0.8 if merchant_category in high_risk_merchants else 0.3
        
        # Geographic risk
        high_risk_countries = ['CN', 'RU', 'PK', 'BR', 'NG']
        is_foreign = 1 if country_code and country_code != 'KE' else 0
        country_fraud_rate = 0.08 if country_code in high_risk_countries else 0.03
        geographic_risk = country_fraud_rate * is_foreign
        
        # Device risk (new device = higher risk)
        device_is_new = 1  # Assume new for now
        
        # Distance from home (simplified)
        log_distance = np.log1p(5)  # Default 5km
        
        # Account age
        if client_created_at:
            age_days = (now - client_created_at).days
        else:
            age_days = 365
        
        # Declined attempts
        declined_24h = 0  # Would query from database in production
        
        # Unique merchants in 24h
        unique_merchants_24h = len(set(t.location for t in txns_24h)) if txns_24h else 1
        
        # Transaction count in 7 days
        txns_7d = [t for t in recent_txns if (now - t.timestamp).total_seconds() < 604800]
        tx_count_7d = len(txns_7d)
        
        # Days since last transaction
        days_since_last = (now - recent_txns[0].timestamp).days if recent_txns else 1
        
        # Construct feature DataFrame (24 features) - MUST match training feature names
        features = pd.DataFrame([{
            'log_amount': log_amount,
            'log_distance': log_distance,
            'hours_since_midnight': hour,
            'day_of_week': day_of_week,
            'is_weekend': is_weekend,
            'is_night': is_night,
            'merchant_risk_score': merchant_risk,
            'is_foreign': is_foreign,
            'country_fraud_rate': country_fraud_rate,
            'log_tx_count_24h': np.log1p(tx_count_24h),
            'transaction_count_7d': tx_count_7d,
            'days_since_last_transaction': days_since_last,
            'unique_merchants_24h': unique_merchants_24h,
            'declined_attempts_24h': declined_24h,
            'device_is_new': device_is_new,
            'ip_is_vpn': 0,
            'age_days': age_days,
            'velocity_ratio': velocity_ratio,
            'amount_per_tx_24h': amount / (tx_count_24h + 1),
            'geographic_risk': geographic_risk,
            'device_risk': 0.5,
            'time_risk': is_night * 0.3 + is_weekend * 0.1,
            'merchant_amount_risk': merchant_risk * log_amount / 10,
            'has_recent_declines': 0
        }])
        
        return features
