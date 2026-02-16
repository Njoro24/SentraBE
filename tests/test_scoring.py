import pytest
import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.features import FeatureEngineer
from data.synthetic_data import generate_synthetic_transactions

class TestFeatureEngineering:
    """Test feature engineering pipeline"""
    
    @pytest.fixture
    def sample_data(self):
        """Generate sample transaction data"""
        return generate_synthetic_transactions(n_samples=100, fraud_ratio=0.5)
    
    @pytest.fixture
    def engineer(self):
        """Initialize feature engineer"""
        return FeatureEngineer()
    
    def test_feature_engineer_creates_correct_number_of_features(self, sample_data, engineer):
        """Test that correct number of features are created"""
        X = engineer.engineer_features(sample_data)
        assert X.shape[1] == len(engineer.feature_names)
    
    def test_feature_engineer_creates_correct_feature_names(self, sample_data, engineer):
        """Test that feature names are correct"""
        X = engineer.engineer_features(sample_data)
        assert list(X.columns) == engineer.feature_names
    
    def test_features_are_normalized(self, sample_data, engineer):
        """Test that features are in reasonable range"""
        X = engineer.engineer_features(sample_data)
        
        # Most features should be between 0 and 1 or -1 and 1
        for col in X.columns:
            if 'sin' not in col and 'cos' not in col:
                assert X[col].min() >= -0.1, f"{col} has values < -0.1"
                assert X[col].max() <= 1.1, f"{col} has values > 1.1"
    
    def test_scaler_fit_transform(self, sample_data, engineer):
        """Test scaler fit and transform"""
        X = engineer.engineer_features(sample_data)
        X_scaled = engineer.fit_transform(X)
        
        # Scaled features should have mean ~0 and std ~1
        assert np.abs(X_scaled.mean(axis=0)).max() < 0.1
        assert np.abs(X_scaled.std(axis=0) - 1).max() < 0.1
    
    def test_scaler_transform_consistency(self, sample_data, engineer):
        """Test that scaler produces consistent results"""
        X = engineer.engineer_features(sample_data)
        engineer.fit_scaler(X)
        
        X_scaled_1 = engineer.transform(X)
        X_scaled_2 = engineer.transform(X)
        
        np.testing.assert_array_almost_equal(X_scaled_1, X_scaled_2)

class TestSyntheticData:
    """Test synthetic data generation"""
    
    def test_synthetic_data_generation(self):
        """Test that synthetic data is generated correctly"""
        df = generate_synthetic_transactions(n_samples=1000, fraud_ratio=0.5)
        
        assert len(df) == 1000
        assert df['is_fraud'].sum() == 500
        assert (1 - df['is_fraud']).sum() == 500
    
    def test_synthetic_data_has_required_columns(self):
        """Test that all required columns are present"""
        df = generate_synthetic_transactions(n_samples=100)
        
        required_columns = [
            'transaction_id', 'amount', 'phone_number', 'device_id',
            'location', 'hour_of_day', 'day_of_week', 'transactions_today',
            'avg_transaction_amount', 'is_fraud', 'timestamp'
        ]
        
        for col in required_columns:
            assert col in df.columns, f"Missing column: {col}"
    
    def test_synthetic_data_fraud_ratio(self):
        """Test that fraud ratio is correct"""
        df = generate_synthetic_transactions(n_samples=1000, fraud_ratio=0.3)
        
        actual_ratio = df['is_fraud'].mean()
        assert 0.25 < actual_ratio < 0.35, f"Fraud ratio {actual_ratio} not close to 0.3"
    
    def test_synthetic_data_amount_distribution(self):
        """Test that amounts follow expected distribution"""
        df = generate_synthetic_transactions(n_samples=1000)
        
        # Amounts should be positive
        assert (df['amount'] > 0).all()
        
        # Fraudulent transactions should have higher average amount
        fraud_avg = df[df['is_fraud'] == 1]['amount'].mean()
        legit_avg = df[df['is_fraud'] == 0]['amount'].mean()
        
        assert fraud_avg > legit_avg, "Fraudulent transactions should have higher average amount"
    
    def test_synthetic_data_velocity_distribution(self):
        """Test that velocity follows expected distribution"""
        df = generate_synthetic_transactions(n_samples=1000)
        
        # Fraudulent transactions should have higher velocity
        fraud_velocity = df[df['is_fraud'] == 1]['transactions_today'].mean()
        legit_velocity = df[df['is_fraud'] == 0]['transactions_today'].mean()
        
        assert fraud_velocity > legit_velocity, "Fraudulent transactions should have higher velocity"

class TestFeatureSignals:
    """Test individual feature signals"""
    
    def test_velocity_signal_calculation(self):
        """Test velocity signal is calculated correctly"""
        df = pd.DataFrame({
            'amount': [1000, 2000],
            'phone_number': ['+254712345678', '+254712345678'],
            'device_id': ['DEV001', 'DEV001'],
            'location': ['Nairobi', 'Nairobi'],
            'hour_of_day': [10, 10],
            'day_of_week': [1, 1],
            'transactions_today': [1, 20],
            'avg_transaction_amount': [1000, 1000],
            'is_fraud': [0, 1]
        })
        
        engineer = FeatureEngineer()
        X = engineer.engineer_features(df)
        
        # Higher transactions_today should result in higher velocity score
        assert X['velocity_score'].iloc[1] > X['velocity_score'].iloc[0]
    
    def test_amount_anomaly_signal(self):
        """Test amount anomaly signal"""
        df = pd.DataFrame({
            'amount': [1000, 50000],
            'phone_number': ['+254712345678', '+254712345678'],
            'device_id': ['DEV001', 'DEV001'],
            'location': ['Nairobi', 'Nairobi'],
            'hour_of_day': [10, 10],
            'day_of_week': [1, 1],
            'transactions_today': [1, 1],
            'avg_transaction_amount': [1000, 1000],
            'is_fraud': [0, 1]
        })
        
        engineer = FeatureEngineer()
        X = engineer.engineer_features(df)
        
        # Large deviation from average should have higher anomaly score
        assert X['amount_anomaly'].iloc[1] > X['amount_anomaly'].iloc[0]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
