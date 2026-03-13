"""
Field Encryptor
Encrypts sensitive transaction fields
"""

from typing import Dict, Any
from .encryption import encrypt, decrypt


# Sensitive fields to encrypt
SENSITIVE_FIELDS = {
    "account_id",
    "card_number",
    "device_id",
    "ip_address",
    "account_number",
    "counterparty_account"
}


def encrypt_transaction(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encrypt sensitive fields in a transaction.
    
    Args:
        transaction: Transaction dictionary
    
    Returns:
        New dictionary with sensitive fields encrypted
    """
    encrypted_txn = transaction.copy()
    
    for field in SENSITIVE_FIELDS:
        if field in encrypted_txn and encrypted_txn[field]:
            plaintext = str(encrypted_txn[field])
            encrypted_data = encrypt(plaintext)
            
            # Store encrypted data as nested dict
            encrypted_txn[f"{field}_encrypted"] = encrypted_data
            # Remove original plaintext
            del encrypted_txn[field]
    
    return encrypted_txn


def decrypt_transaction(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decrypt sensitive fields in a transaction.
    
    Args:
        transaction: Transaction dictionary with encrypted fields
    
    Returns:
        New dictionary with sensitive fields decrypted
    """
    decrypted_txn = transaction.copy()
    
    for field in SENSITIVE_FIELDS:
        encrypted_field = f"{field}_encrypted"
        if encrypted_field in decrypted_txn:
            encrypted_data = decrypted_txn[encrypted_field]
            plaintext = decrypt(
                encrypted_data["ciphertext"],
                encrypted_data["nonce"],
                encrypted_data["tag"]
            )
            
            # Restore original field
            decrypted_txn[field] = plaintext
            # Remove encrypted version
            del decrypted_txn[encrypted_field]
    
    return decrypted_txn


def is_field_encrypted(transaction: Dict[str, Any], field: str) -> bool:
    """
    Check if a field is encrypted in the transaction.
    
    Args:
        transaction: Transaction dictionary
        field: Field name to check
    
    Returns:
        True if field is encrypted, False otherwise
    """
    return f"{field}_encrypted" in transaction
