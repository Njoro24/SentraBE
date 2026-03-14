import pytest
import pytest_asyncio
import httpx
import pickle
import os
import sys
from datetime import datetime, timedelta
from jose import jwt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

SECRET_KEY        = "your-secret-key-change-in-production-12345"
ALGORITHM         = "HS256"
TEST_CLIENT_ID    = 1
TEST_CLIENT_EMAIL = "meshackgenz@gmail.com"


def make_token(client_id, email, expires_delta=None):
    expire = datetime.utcnow() + (expires_delta or timedelta(days=30))
    return jwt.encode(
        {"client_id": client_id, "email": email, "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM
    )


def load_model_into_app():
    import api.main as main_module
    for path in ["fraud_model.pkl", "models/xgboost_model.pkl"]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                model_data = pickle.load(f)
            main_module.model         = model_data["model"]
            main_module.scaler        = model_data["scaler"]
            main_module.feature_names = model_data["feature_names"]
            main_module.threshold     = 0.5
            try:
                import api.transactions as txn_module
                txn_module.fraud_model = model_data
            except Exception:
                pass
            print(f"[conftest] Model loaded from {path}")
            return
    raise FileNotFoundError("No model file found. Run: python3 train_fraud_model.py")


load_model_into_app()

from api.main import app


@pytest_asyncio.fixture
async def async_client():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def valid_token():
    return make_token(TEST_CLIENT_ID, TEST_CLIENT_EMAIL)


@pytest.fixture
def expired_token():
    return make_token(TEST_CLIENT_ID, TEST_CLIENT_EMAIL, expires_delta=timedelta(hours=-1))


@pytest.fixture
def sample_transaction():
    return {
        "transaction_id": f"TXN-TEST-{datetime.utcnow().timestamp()}",
        "amount": 5000.0,
        "location": "Nairobi, KE",
        "device_id": "device-test-123",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
