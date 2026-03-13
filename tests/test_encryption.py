"""
Encryption Tests
Tests for AES-256-GCM encryption and field encryption
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from security.encryption import encrypt, decrypt
from security.field_encryptor import encrypt_transaction, decrypt_transaction, is_field_encrypted
from cryptography.exceptions import InvalidTag


class TestEncryption:
    """Test AES-256-GCM encryption and decryption"""
    
    def test_encrypt_then_decrypt_returns_original_value(self):
        """Test that encrypt then decrypt returns the original plaintext"""
        original = "test-account-12345"
        
        # Encrypt
        encrypted = encrypt(original)
        assert "ciphertext" in encrypted
        assert "nonce" in encrypted
        assert "tag" in encrypted
        
        # Decrypt
        decrypted = decrypt(
            encrypted["ciphertext"],
            encrypted["nonce"],
            encrypted["tag"]
        )
        
        assert decrypted == original
    
    def test_ciphertext_does_not_equal_plaintext(self):
        """Test that ciphertext is different from plaintext"""
        plaintext = "sensitive-data-12345"
        
        encrypted = encrypt(plaintext)
        ciphertext = encrypted["ciphertext"]
        
        # Ciphertext should not contain plaintext
        assert plaintext not in ciphertext
        assert ciphertext != plaintext
    
    def test_different_encryptions_produce_different_ciphertexts(self):
        """Test that same plaintext encrypted twice produces different ciphertexts"""
        plaintext = "same-value"
        
        # Encrypt twice
        encrypted1 = encrypt(plaintext)
        encrypted2 = encrypt(plaintext)
        
        # Ciphertexts should be different (due to random nonce)
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
        
        assert decrypted1 == decrypted2 == plaintext
    
    def test_tampered_ciphertext_fails_decryption(self):
        """Test that tampered ciphertext fails decryption"""
        plaintext = "important-data"
        
        encrypted = encrypt(plaintext)
        
        # Tamper with ciphertext
        tampered_ciphertext = encrypted["ciphertext"][:-5] + "xxxxx"
        
        # Should raise InvalidTag or similar error
        with pytest.raises(Exception):  # Could be InvalidTag or other crypto error
            decrypt(
                tampered_ciphertext,
                encrypted["nonce"],
                encrypted["tag"]
            )


class TestFieldEncryptor:
    """Test field-level encryption for transactions"""
    
    def test_encrypt_transaction_encrypts_sensitive_fields(self):
        """Test that encrypt_transaction encrypts all sensitive fields"""
        transaction = {
            "transaction_id": "txn123",
            "amount": 1000.0,
            "account_id": "ACC-12345",
            "card_number": "4111111111111111",
            "device_id": "device-xyz",
            "ip_address": "192.168.1.1",
            "merchant_name": "Store ABC"
        }
        
        encrypted_txn = encrypt_transaction(transaction)
        
        # Sensitive fields should be encrypted
        assert "account_id_encrypted" in encrypted_txn
        assert "card_number_encrypted" in encrypted_txn
        assert "device_id_encrypted" in encrypted_txn
        assert "ip_address_encrypted" in encrypted_txn
        
        # Original fields should be removed
        assert "account_id" not in encrypted_txn
        assert "card_number" not in encrypted_txn
        assert "device_id" not in encrypted_txn
        assert "ip_address" not in encrypted_txn
        
        # Non-sensitive fields should remain
        assert encrypted_txn["transaction_id"] == "txn123"
        assert encrypted_txn["amount"] == 1000.0
        assert encrypted_txn["merchant_name"] == "Store ABC"
    
    def test_decrypt_transaction_restores_original_fields(self):
        """Test that decrypt_transaction restores original fields"""
        original_transaction = {
            "transaction_id": "txn123",
            "amount": 1000.0,
            "account_id": "ACC-12345",
            "card_number": "4111111111111111",
            "device_id": "device-xyz",
            "ip_address": "192.168.1.1",
            "merchant_name": "Store ABC"
        }
        
        # Encrypt
        encrypted_txn = encrypt_transaction(original_transaction)
        
        # Decrypt
        decrypted_txn = decrypt_transaction(encrypted_txn)
        
        # Should match original
        assert decrypted_txn["account_id"] == original_transaction["account_id"]
        assert decrypted_txn["card_number"] == original_transaction["card_number"]
        assert decrypted_txn["device_id"] == original_transaction["device_id"]
        assert decrypted_txn["ip_address"] == original_transaction["ip_address"]
        assert decrypted_txn["transaction_id"] == original_transaction["transaction_id"]
        assert decrypted_txn["amount"] == original_transaction["amount"]
    
    def test_is_field_encrypted_detects_encrypted_fields(self):
        """Test that is_field_encrypted correctly identifies encrypted fields"""
        transaction = {
            "transaction_id": "txn123",
            "account_id": "ACC-12345"
        }
        
        encrypted_txn = encrypt_transaction(transaction)
        
        # Check encrypted fields
        assert is_field_encrypted(encrypted_txn, "account_id") is True
        assert is_field_encrypted(encrypted_txn, "transaction_id") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
