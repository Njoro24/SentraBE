"""
Shared fixtures for integration tests
Provides async test client, JWT tokens, and sample payloads
"""

import pytest
import pytest_asyncio
import httpx
from datetime import datetime, timedelta
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from security.jwt_handler import generate_token, decode_token
from api.main import app


@pytest_asyncio.fixture
async def async_client():
    """Async HTTP client for testing FastAPI endpoints"""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def valid_admin_token():
    """Generate a valid JWT token for admin role"""
    token = generate_token(
        sub="admin-user-123",
        role="admin",
        expires_in_hours=1
    )
    return token


@pytest.fixture
def valid_analyst_token():
    """Generate a valid JWT token for analyst role"""
    token = generate_token(
        sub="analyst-user-456",
        role="analyst",
        expires_in_hours=1
    )
    return token


@pytest.fixture
def expired_token():
    """Generate an expired JWT token"""
    token = generate_token(
        sub="expired-user-789",
        role="analyst",
        expires_in_hours=-1  # Expired 1 hour ago
    )
    return token


@pytest.fixture
def sample_transaction_payload():
    """Sample transaction payload matching /score endpoint schema"""
    return {
        "transaction_id": "TXN-TEST-001",
        "amount": 5000.0,
        "merchant_category": "RETAIL",
        "location": "Nairobi, KE",
        "device_id": "device-test-123",
        "country": "KE",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@pytest.fixture
def sample_t24_transaction():
    """Sample T24-format transaction"""
    return {
        "TRANSACTION_ID": "T24-TEST-001",
        "AMOUNT": 10000,
        "CURRENCY": "KES",
        "ACCOUNT_NUMBER": "1234567890",
        "COUNTERPARTY_ACCOUNT": "0987654321",
        "MERCHANT_NAME": "TEST MERCHANT",
        "MERCHANT_CATEGORY": "Retail",
        "MERCHANT_LOCATION": "Nairobi",
        "CHANNEL": "MOBILE_BANKING",
        "DEVICE_ID": "DEV-TEST-001",
        "IP_ADDRESS": "192.168.1.1",
        "TIMESTAMP": datetime.utcnow().isoformat(),
        "VELOCITY_FLAG": False,
        "GEOGRAPHIC_MISMATCH": False,
        "DEVICE_MISMATCH": False
    }
