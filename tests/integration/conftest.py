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


@pytest.fixture(autouse=False)
def reset_subscription_usage(async_client, valid_token):
    """
    Use this fixture in any test that needs a clean subscription slate.
    Directly zeros out this month fraud_scores for the test client
    so the 50k starter limit is never hit during testing.
    """
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from data.schema import get_db, FraudScore
    from datetime import date, datetime
    db = next(get_db())
    try:
        today = date.today()
        first_day = datetime.combine(today.replace(day=1), datetime.min.time())
        db.query(FraudScore).filter(
            FraudScore.client_id == TEST_CLIENT_ID,
            FraudScore.created_at >= first_day
        ).delete()
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def unlimited_client_token():
    """
    Token for a hypothetical enterprise client — use when testing
    high-volume scenarios to avoid hitting the starter tier limit.
    For now maps to same client but signals intent in the test.
    """
    return make_token(TEST_CLIENT_ID, TEST_CLIENT_EMAIL)
