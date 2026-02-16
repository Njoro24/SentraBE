import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler

class FeatureEngineer:
    """
    Handles feature engineering for fraud detection.
    Transforms raw transaction data into ML-ready features.
    """
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.feature_names = [
            'amount_normalized',
            'velocity_score',
            'amount_anomaly',
            'device_new',
            'location_change',
            'hour_of_day_sin',
            'hour_of_day_cos',
            'day_of_week_sin',
            'day_of_week_cos',
        ]
    
    def engineer_features(self, df):
        """
        Create features from raw transaction data.
        
        Args:
            df: DataFrame with raw transaction data
        
        Returns:
            DataFrame with engineered features
        """
        features = pd.DataFrame()
        
        # 1. Amount normalization
        features['amount_normalized'] = np.log1p(df['amount']) / np.log1p(df['amount'].max())
        
        # 2. Velocity score (transactions per day)
        features['velocity_score'] = df['transactions_today'] / (df['transactions_today'].max() + 1)
        
        # 3. Amount anomaly (deviation from user average)
        features['amount_anomaly'] = np.abs(df['amount'] - df['avg_transaction_amount']) / (df['avg_transaction_amount'] + 1)
        features['amount_anomaly'] = np.clip(features['amount_anomaly'], 0, 1)
        
        # 4. Device new (binary: is this a new device?)
        # Simulate: if device_id appears in first 80% of data, it's known
        known_devices = set(df['device_id'].iloc[:int(len(df)*0.8)])
        features['device_new'] = (~df['device_id'].isin(known_devices)).astype(int)
        
        # 5. Location change (binary: is this a new location?)
        known_locations = set(df['location'].iloc[:int(len(df)*0.8)])
        features['location_change'] = (~df['location'].isin(known_locations)).astype(int)
        
        # 6-7. Hour of day (circular encoding)
        hour_rad = 2 * np.pi * df['hour_of_day'] / 24
        features['hour_of_day_sin'] = np.sin(hour_rad)
        features['hour_of_day_cos'] = np.cos(hour_rad)
        
        # 8-9. Day of week (circular encoding)
        day_rad = 2 * np.pi * df['day_of_week'] / 7
        features['day_of_week_sin'] = np.sin(day_rad)
        features['day_of_week_cos'] = np.cos(day_rad)
        
        return features
    
    def fit_scaler(self, X):
        """Fit the scaler on training data"""
        self.scaler.fit(X)
        return self
    
    def transform(self, X):
        """Scale features"""
        return self.scaler.transform(X)
    
    def fit_transform(self, X):
        """Fit and transform in one step"""
        return self.scaler.fit_transform(X)
