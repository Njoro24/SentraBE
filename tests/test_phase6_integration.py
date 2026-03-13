"""
Phase 6 Integration Tests
End-to-end tests for JWT authentication, encryption, and audit logging
"""

import pytest
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from security.jwt_handler import generate_token, decode_token
from security.field_encryptor import encrypt_transaction, decrypt_transaction
from security.audit_log import write_log, verify_chain, clear_audit_log, get_log_entries
from security.encryption import encrypt, decrypt


class TestPhase6Integration:
    """End-to-end integration tests for Phase 6 Security"""
    
    def setup_method(self):
        """Clear audit log before each test"""
        clear_audit_log()
    
    def teardown_method(self):
        """Clear audit log after each test"""
        clear_audit_log()
    
    def test_generate_valid_token_and_decode(self):
        """Test that a valid token can be generated and decoded"""
        # Generate token
        token = generate_token(sub="test_user", role="admin", expires_in_hours=1)
        
        assert token is not None
        assert isinstance(token, str)
        
        # Decode token
        payload = decode_token(token)
        
        assert payload["sub"] == "test_user"
        assert payload["role"] == "admin"
        assert "exp" in payload
        assert "iat" in payload
    
    def test_encrypt_transaction_and_verify_no_plaintext(self):
        """Test that transaction encryption hides sensitive fields"""
        transaction = {
            "transaction_id": "txn_12345",
            "amount": 5000.0,
            "account_id": "ACC-98765",
            "card_number": "4111111111111111",
            "device_id": "device-abc123",
            "ip_address": "192.168.1.100",
            "merchant_name": "Store XYZ",
            "timestamp": "2024-01-01T12:00:00"
        }
        
        # Encrypt
        encrypted_txn = encrypt_transaction(transaction)
        
        # Verify sensitive fields are not in plaintext
        encrypted_str = json.dumps(encrypted_txn)
        
        assert "ACC-98765" not in encrypted_str
        assert "4111111111111111" not in encrypted_str
        assert "device-abc123" not in encrypted_str
        assert "192.168.1.100" not in encrypted_str
        
        # Non-sensitive fields should still be visible
        assert "txn_12345" in encrypted_str
        assert "Store XYZ" in encrypted_str
    
    def test_audit_log_chain_integrity(self):
        """Test that audit log chain remains intact"""
        # Write entries
        write_log("TOKEN_ISSUED", "admin", {"token_id": "token_001"})
        write_log("SCORE_REQUEST", "client_app", {"transaction_id": "txn_001"})
        write_log("TRANSACTION_STORED", "t24_adapter", {"account": "ACC_001"})
        
        # Verify chain
        assert verify_chain() is True
        
        # Get entries
        entries = get_log_entries()
        assert len(entries) == 3
        
        # Verify chain structure
        assert entries[0]["previous_hash"] == "GENESIS"
        assert entries[1]["previous_hash"] == entries[0]["entry_hash"]
        assert entries[2]["previous_hash"] == entries[1]["entry_hash"]
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption preserve data"""
        original_value = "sensitive-account-12345"
        
        # Encrypt
        encrypted = encrypt(original_value)
        
        # Decrypt
        decrypted = decrypt(
            encrypted["ciphertext"],
            encrypted["nonce"],
            encrypted["tag"]
        )
        
        assert decrypted == original_value
    
    def test_different_encryptions_produce_different_ciphertexts(self):
        """Test that same value encrypted twice produces different ciphertexts"""
        value = "test-value"
        
        encrypted1 = encrypt(value)
        encrypted2 = encrypt(value)
        
        # Ciphertexts should be different
        assert encrypted1["ciphertext"] != encrypted2["ciphertext"]
        assert encrypted1["nonce"] != encrypted2["nonce"]
        
        # But both should decrypt to same value
        decrypted1 = decrypt(
            encrypted1["ciphertext"],
            encrypted1["nonce"],
            encrypted1["tag"]
        )
        decrypted2 = decrypt(
            encrypted2["ciphertext"],
            encrypted2["nonce"],
            encrypted2["tag"]
        )
        
        assert decrypted1 == decrypted2 == value
    
    def test_full_security_workflow(self):
        """Test complete security workflow"""
        # Step 1: Generate JWT token
        token = generate_token(sub="user_123", role="analyst", expires_in_hours=1)
        payload = decode_token(token)
        
        assert payload["sub"] == "user_123"
        assert payload["role"] == "analyst"
        
        # Step 2: Log token issuance
        write_log(
            event_type="TOKEN_ISSUED",
            actor="auth_service",
            payload={"user_id": "user_123", "role": "analyst"}
        )
        
        # Step 3: Create and encrypt transaction
        transaction = {
            "transaction_id": "txn_999",
            "amount": 10000.0,
            "account_id": "ACC-SECRET-123",
            "card_number": "5555555555555555",
            "device_id": "device-secret-xyz",
            "ip_address": "10.0.0.1",
            "merchant_name": "Premium Store",
            "timestamp": "2024-01-01T15:30:00"
        }
        
        encrypted_txn = encrypt_transaction(transaction)
        
        # Step 4: Log transaction storage
        write_log(
            event_type="TRANSACTION_STORED",
            actor="t24_adapter",
            payload={
                "transaction_id": "txn_999",
                "amount": 10000.0,
                "encrypted": True
            }
        )
        
        # Step 5: Log score request
        write_log(
            event_type="SCORE_REQUEST",
            actor="user_123",
            payload={
                "transaction_id": "txn_999",
                "role": "analyst"
            }
        )
        
        # Step 6: Verify audit chain
        assert verify_chain() is True
        
        # Step 7: Verify encrypted transaction has no plaintext
        encrypted_str = json.dumps(encrypted_txn)
        assert "ACC-SECRET-123" not in encrypted_str
        assert "5555555555555555" not in encrypted_str
        assert "device-secret-xyz" not in encrypted_str
        assert "10.0.0.1" not in encrypted_str
        
        # Step 8: Verify audit log entries
        entries = get_log_entries()
        assert len(entries) == 3
        
        event_types = [e["event_type"] for e in entries]
        assert "TOKEN_ISSUED" in event_types
        assert "TRANSACTION_STORED" in event_types
        assert "SCORE_REQUEST" in event_types
    
    def test_tampered_audit_log_detected(self):
        """Test that tampering with audit log is detected"""
        import sqlite3
        from security.audit_log import AUDIT_LOG_DB
        
        # Write entries
        write_log("EVENT_1", "actor_1", {"data": "value_1"})
        write_log("EVENT_2", "actor_2", {"data": "value_2"})
        
        # Verify chain passes
        assert verify_chain() is True
        
        # Tamper with an entry
        conn = sqlite3.connect(AUDIT_LOG_DB)
        cursor = conn.cursor()
        cursor.execute('UPDATE audit_log SET event_type = ? WHERE id = ?', ('TAMPERED', 1))
        conn.commit()
        conn.close()
        
        # Verify chain should fail
        with pytest.raises(ValueError):
            verify_chain()


class TestSecuritySummary:
    """Summary test to verify all security pillars are working"""
    
    def test_all_security_pillars_operational(self):
        """Verify all three security pillars are operational"""
        
        # Pillar 1: JWT Authentication
        try:
            token = generate_token(sub="test", role="admin", expires_in_hours=1)
            payload = decode_token(token)
            jwt_working = payload["sub"] == "test"
        except:
            jwt_working = False
        
        # Pillar 2: Data Encryption
        try:
            plaintext = "test-data"
            encrypted = encrypt(plaintext)
            decrypted = decrypt(
                encrypted["ciphertext"],
                encrypted["nonce"],
                encrypted["tag"]
            )
            encryption_working = decrypted == plaintext
        except:
            encryption_working = False
        
        # Pillar 3: Audit Logs
        try:
            clear_audit_log()
            write_log("TEST", "test_actor", {"test": "data"})
            audit_working = verify_chain() is True
            clear_audit_log()
        except:
            audit_working = False
        
        # All pillars should be working
        assert jwt_working is True, "JWT Authentication not working"
        assert encryption_working is True, "Data Encryption not working"
        assert audit_working is True, "Audit Logs not working"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
