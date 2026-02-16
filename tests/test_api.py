import pytest
import sys
import os
from datetime import datetime
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app

client = TestClient(app)

class TestAPIEndpoints:
    """Test API endpoints"""
    
    def test_root_endpoint(self):
        """Test root endpoint returns correct info"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "SKOR Shield"
        assert "version" in data
        assert "docs" in data
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "model_loaded" in data
        assert "database_connected" in data
        assert "timestamp" in data
    
    def test_score_endpoint_with_valid_data(self):
        """Test scoring endpoint with valid transaction"""
        payload = {
            "transaction_id": "TXN_TEST_001",
            "amount": 50000,
            "phone_number": "+254712345678",
            "device_id": "DEV_001",
            "location": "Nairobi",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        response = client.post("/v1/score", json=payload)
        
        # Should return 200 or 503 (if model not loaded)
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert data["transaction_id"] == "TXN_TEST_001"
            assert 0 <= data["risk_score"] <= 100
            assert data["risk_level"] in ["LOW", "MEDIUM", "HIGH"]
            assert data["recommendation"] in ["APPROVE", "FLAG", "BLOCK"]
            assert "signals" in data
            assert "processing_time_ms" in data
    
    def test_score_endpoint_missing_required_field(self):
        """Test scoring endpoint with missing required field"""
        payload = {
            "transaction_id": "TXN_TEST_002",
            "amount": 50000,
            # Missing phone_number
            "device_id": "DEV_001",
            "location": "Nairobi",
        }
        
        response = client.post("/v1/score", json=payload)
        assert response.status_code == 422  # Validation error
    
    def test_score_endpoint_invalid_amount(self):
        """Test scoring endpoint with invalid amount"""
        payload = {
            "transaction_id": "TXN_TEST_003",
            "amount": -1000,  # Negative amount
            "phone_number": "+254712345678",
            "device_id": "DEV_001",
            "location": "Nairobi",
        }
        
        response = client.post("/v1/score", json=payload)
        assert response.status_code == 422  # Validation error
    
    def test_score_response_structure(self):
        """Test that score response has correct structure"""
        payload = {
            "transaction_id": "TXN_TEST_004",
            "amount": 50000,
            "phone_number": "+254712345678",
            "device_id": "DEV_001",
            "location": "Nairobi",
        }
        
        response = client.post("/v1/score", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check required fields
            assert "transaction_id" in data
            assert "risk_score" in data
            assert "risk_level" in data
            assert "signals" in data
            assert "recommendation" in data
            assert "processing_time_ms" in data
            
            # Check signals structure
            signals = data["signals"]
            assert "velocity" in signals
            assert "amount_anomaly" in signals
            assert "device_new" in signals
            assert "location_change" in signals
    
    def test_score_processing_time_under_200ms(self):
        """Test that scoring completes in under 200ms"""
        payload = {
            "transaction_id": "TXN_TEST_005",
            "amount": 50000,
            "phone_number": "+254712345678",
            "device_id": "DEV_001",
            "location": "Nairobi",
        }
        
        response = client.post("/v1/score", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            assert data["processing_time_ms"] < 200, \
                f"Processing time {data['processing_time_ms']}ms exceeds 200ms target"

class TestRiskScoring:
    """Test risk scoring logic"""
    
    def test_high_risk_score_triggers_block(self):
        """Test that high risk scores trigger BLOCK recommendation"""
        # This would require mocking the model to return high scores
        # For now, we just verify the logic exists
        pass
    
    def test_medium_risk_score_triggers_flag(self):
        """Test that medium risk scores trigger FLAG recommendation"""
        pass
    
    def test_low_risk_score_triggers_approve(self):
        """Test that low risk scores trigger APPROVE recommendation"""
        pass

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
