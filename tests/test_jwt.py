"""
JWT Authentication Tests
Tests for token generation, validation, and middleware
"""

import pytest
import jwt
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from security.jwt_handler import generate_token, decode_token, verify_token, JWT_SECRET_KEY, JWT_ALGORITHM


class TestJWTHandler:
    """Test JWT token generation and validation"""
    
    def test_valid_token_is_accepted(self):
        """Test that a valid token is accepted and decoded correctly"""
        token = generate_token(sub="user123", role="admin", expires_in_hours=1)
        
        assert token is not None
        assert isinstance(token, str)
        
        # Decode and verify
        payload = decode_token(token)
        assert payload["sub"] == "user123"
        assert payload["role"] == "admin"
        assert "exp" in payload
        assert "iat" in payload
    
    def test_expired_token_is_rejected(self):
        """Test that an expired token is rejected"""
        # Create a token that expires immediately
        now = datetime.utcnow()
        exp = now - timedelta(seconds=1)  # Already expired
        
        payload = {
            "sub": "user123",
            "role": "admin",
            "exp": exp,
            "iat": now
        }
        
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        
        # Should raise ExpiredSignatureError
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(token)
    
    def test_tampered_token_is_rejected(self):
        """Test that a tampered token is rejected"""
        token = generate_token(sub="user123", role="admin", expires_in_hours=1)
        
        # Tamper with the token by changing a character
        tampered_token = token[:-5] + "xxxxx"
        
        # Should raise an error
        with pytest.raises((jwt.DecodeError, jwt.InvalidSignatureError)):
            decode_token(tampered_token)
    
    def test_missing_token_returns_401(self):
        """Test that missing token is handled (this is middleware responsibility)"""
        # This test verifies the verify_token function returns False for invalid input
        result = verify_token("")
        assert result is False
        
        result = verify_token("invalid")
        assert result is False
    
    def test_wrong_algorithm_token_is_rejected(self):
        """Test that a token signed with wrong algorithm is rejected"""
        # Create a token with a different algorithm
        now = datetime.utcnow()
        exp = now + timedelta(hours=1)
        
        payload = {
            "sub": "user123",
            "role": "admin",
            "exp": exp,
            "iat": now
        }
        
        # Sign with HS512 instead of HS256
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS512")
        
        # Should raise InvalidAlgorithmError, InvalidSignatureError, or DecodeError
        with pytest.raises((jwt.InvalidAlgorithmError, jwt.InvalidSignatureError, jwt.DecodeError)):
            decode_token(token)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
