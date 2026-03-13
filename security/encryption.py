"""
AES-256-GCM Encryption Module
Provides symmetric encryption/decryption for sensitive data
"""

import os
import base64
from typing import Dict
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv

load_dotenv()

# Load encryption key from environment
ENCRYPTION_KEY_B64 = os.getenv("ENCRYPTION_KEY", "x7U7+IP7TRpDjcX/jz1fHQDNcKH9a4hRd3SiF8Gkpfo=")

try:
    ENCRYPTION_KEY = base64.b64decode(ENCRYPTION_KEY_B64)
    if len(ENCRYPTION_KEY) != 32:
        raise ValueError(f"Encryption key must be 32 bytes, got {len(ENCRYPTION_KEY)}")
except Exception as e:
    raise ValueError(f"Invalid ENCRYPTION_KEY in .env: {str(e)}")


def encrypt(plaintext: str) -> Dict[str, str]:
    """
    Encrypt plaintext using AES-256-GCM.
    
    Args:
        plaintext: String to encrypt
    
    Returns:
        Dictionary with keys:
        - ciphertext: Base64-encoded encrypted data
        - nonce: Base64-encoded nonce (IV)
        - tag: Base64-encoded authentication tag
    """
    # Generate random 12-byte nonce
    nonce = os.urandom(12)
    
    # Create cipher
    cipher = AESGCM(ENCRYPTION_KEY)
    
    # Encrypt
    plaintext_bytes = plaintext.encode('utf-8')
    ciphertext = cipher.encrypt(nonce, plaintext_bytes, None)
    
    # Extract tag (last 16 bytes) and actual ciphertext
    actual_ciphertext = ciphertext[:-16]
    tag = ciphertext[-16:]
    
    return {
        "ciphertext": base64.b64encode(actual_ciphertext).decode('utf-8'),
        "nonce": base64.b64encode(nonce).decode('utf-8'),
        "tag": base64.b64encode(tag).decode('utf-8')
    }


def decrypt(ciphertext: str, nonce: str, tag: str) -> str:
    """
    Decrypt ciphertext using AES-256-GCM.
    
    Args:
        ciphertext: Base64-encoded encrypted data
        nonce: Base64-encoded nonce (IV)
        tag: Base64-encoded authentication tag
    
    Returns:
        Decrypted plaintext string
    
    Raises:
        cryptography.exceptions.InvalidTag: If authentication fails
    """
    # Decode from base64
    ciphertext_bytes = base64.b64decode(ciphertext)
    nonce_bytes = base64.b64decode(nonce)
    tag_bytes = base64.b64decode(tag)
    
    # Create cipher
    cipher = AESGCM(ENCRYPTION_KEY)
    
    # Combine ciphertext and tag for decryption
    combined = ciphertext_bytes + tag_bytes
    
    # Decrypt
    plaintext_bytes = cipher.decrypt(nonce_bytes, combined, None)
    
    return plaintext_bytes.decode('utf-8')
