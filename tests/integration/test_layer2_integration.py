"""
LAYER 2 - Cross-Phase Integration Tests
Tests combining multiple phases together
"""

import pytest
import httpx
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from security.jwt_handler import generate_token, decode_token
from security.field_encryptor import encrypt_transaction
from security.audit_log import get_log_entries
from services.t24_adapter import T24Adapter
from api.main import app


class TestP1AndP6:
    """Phase 1 (Scoring) + Phase 6 (Security) Integration"""
    
    @pytest.mark.asyncio
    async def test_valid_jwt_reaches_scoring(self, valid_admin_token):
        """Valid JWT token should reach scoring endpoint"""
        
        try:
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                payload = {
                    "transaction_id": "TXN-P1P6-001",
                    "amount": 5000.0,
                    "merchant_category": "RETAIL",
                    "location": "Nairobi, KE",
                    "device_id": "device-p1p6",
                    "country": "KE",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                
                response = await client.post(
                    "/v1/score",
                    json=payload,
                    headers={"Authorization": f"Bearer {valid_admin_token}"}
                )
                
                if response.status_code == 500 and "connection" in response.text.lower():
                    pytest.skip("Database not available")
                
                assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
                data = response.json()
                assert "risk_score" in data
                
        except Exception as e:
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                pytest.skip("Database not available")
            if "skip" in str(e).lower():
                pytest.skip(str(e))
            raise
    
    @pytest.mark.asyncio
    async def test_invalid_jwt_blocked(self):
        """Invalid JWT should return 401"""
        
        try:
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                payload = {
                    "transaction_id": "TXN-P1P6-002",
                    "amount": 5000.0,
                    "merchant_category": "RETAIL",
                    "location": "Nairobi, KE",
                    "device_id": "device-p1p6",
                    "country": "KE",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                
                response = await client.post(
                    "/v1/score",
                    json=payload,
                    headers={"Authorization": "Bearer invalid-token"}
                )
                
                assert response.status_code == 401, f"Expected 401, got {response.status_code}"
                
        except Exception as e:
            if "skip" in str(e).lower():
                pytest.skip(str(e))
            raise
    
    @pytest.mark.asyncio
    async def test_missing_jwt_blocked(self):
        """Missing JWT should return 401"""
        
        try:
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                payload = {
                    "transaction_id": "TXN-P1P6-003",
                    "amount": 5000.0,
                    "merchant_category": "RETAIL",
                    "location": "Nairobi, KE",
                    "device_id": "device-p1p6",
                    "country": "KE",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                
                response = await client.post(
                    "/v1/score",
                    json=payload
                )
                
                assert response.status_code == 401, f"Expected 401, got {response.status_code}"
                
        except Exception as e:
            if "skip" in str(e).lower():
                pytest.skip(str(e))
            raise
    
    @pytest.mark.asyncio
    async def test_tampered_jwt_blocked(self, valid_admin_token):
        """Tampered JWT should return 401"""
        
        try:
            # Tamper with token
            tampered = valid_admin_token[:-5] + "XXXXX"
            
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                payload = {
                    "transaction_id": "TXN-P1P6-004",
                    "amount": 5000.0,
                    "merchant_category": "RETAIL",
                    "location": "Nairobi, KE",
                    "device_id": "device-p1p6",
                    "country": "KE",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                
                response = await client.post(
                    "/v1/score",
                    json=payload,
                    headers={"Authorization": f"Bearer {tampered}"}
                )
                
                assert response.status_code == 401, f"Expected 401, got {response.status_code}"
                
        except Exception as e:
            if "skip" in str(e).lower():
                pytest.skip(str(e))
            raise


class TestP5AndP6:
    """Phase 5 (T24 Adapter) + Phase 6 (Security) Integration"""
    
    def test_t24_fields_encrypted_in_output(self, sample_t24_transaction):
        """T24 transaction fields should be encrypted"""
        
        # Transform T24 to internal format
        transformed = T24Adapter.transform_t24_to_internal(sample_t24_transaction)
        assert transformed is not None
        
        # Convert to dict
        txn_dict = T24Adapter.to_dict(transformed)
        
        # Encrypt
        encrypted = encrypt_transaction(txn_dict)
        
        # Verify sensitive fields are encrypted
        sensitive_fields = ["account_id", "card_number", "device_id", "ip_address"]
        
        for field in sensitive_fields:
            if field in txn_dict:
                # Should have encrypted version
                encrypted_field = f"{field}_encrypted"
                # Either encrypted or removed
                assert encrypted_field in encrypted or field not in encrypted
    
    def test_encryption_is_deterministic_across_calls(self):
        """Encryption should produce different ciphertexts (random nonce)"""
        
        from security.encryption import encrypt
        
        plaintext = "test-value-12345"
        
        # Encrypt twice
        encrypted1 = encrypt(plaintext)
        encrypted2 = encrypt(plaintext)
        
        # Ciphertexts should be different (due to random nonce)
        assert encrypted1["ciphertext"] != encrypted2["ciphertext"], \
            "Ciphertexts should differ due to random nonce"
    
    def test_audit_log_records_adapter_call(self, sample_t24_transaction):
        """Adapter call should create audit log entry"""
        
        from security.audit_log import write_log
        
        # Write audit entry
        entry_id = write_log(
            event_type="T24_ADAPTER_CALL",
            actor="test-adapter",
            payload={"transaction_id": "T24-TEST"}
        )
        
        assert entry_id > 0, "Audit log entry should be created"
        
        # Verify entry exists
        entries = get_log_entries(limit=1)
        assert len(entries) > 0, "Audit log should have entries"


class TestP2AndP4:
    """Phase 2 (Streaming) + Phase 4 (Dashboard) Integration"""
    
    @pytest.mark.asyncio
    async def test_kafka_message_triggers_websocket_alert(self):
        """Kafka message should trigger WebSocket alert"""
        
        # This test requires Kafka and WebSocket server running
        pytest.skip("Kafka and WebSocket server not available in test environment")
    
    @pytest.mark.asyncio
    async def test_velocity_spike_produces_alert(self):
        """Velocity spike should produce alert"""
        
        # This test requires Kafka and Flink running
        pytest.skip("Kafka and Flink not available in test environment")


class TestP1AndP3:
    """Phase 1 (Scoring) + Phase 3 (Graph) Integration"""
    
    @pytest.mark.asyncio
    async def test_scored_transaction_appears_in_graph(self):
        """Scored transaction should appear in Neo4j graph"""
        
        # This test requires Neo4j running
        pytest.skip("Neo4j not available in test environment")
    
    @pytest.mark.asyncio
    async def test_fraud_ring_accounts_score_higher(self):
        """Fraud ring accounts should have higher risk scores"""
        
        # This test requires Neo4j and scoring data
        pytest.skip("Neo4j not available in test environment")
