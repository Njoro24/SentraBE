"""Phase 1 — Scoring Model & API component tests"""
import pytest
import httpx
import time
import pickle
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from api.main import app

pytestmark = pytest.mark.asyncio


class TestPhase1ModelAccuracy:
    def test_model_file_exists(self):
        assert os.path.exists("fraud_model.pkl"), "fraud_model.pkl not found — run: python3 train_fraud_model.py"

    def test_model_loads_and_has_required_keys(self):
        if not os.path.exists("fraud_model.pkl"):
            pytest.skip("Model file not found")
        with open("fraud_model.pkl", "rb") as f:
            data = pickle.load(f)
        for key in ["model", "scaler", "feature_names"]:
            assert key in data, f"Missing key in model file: {key}"

    def test_model_accuracy_above_85_percent(self):
        if not os.path.exists("fraud_model.pkl"):
            pytest.skip("Model file not found")
        with open("fraud_model.pkl", "rb") as f:
            data = pickle.load(f)
        metrics = data.get("eval_metrics", {})
        accuracy = metrics.get("overall_accuracy")
        if accuracy is None:
            pytest.skip("No eval_metrics in model — re-run train_fraud_model.py")
        assert accuracy >= 0.85, f"Accuracy {accuracy:.2%} is below the 85% threshold"


class TestPhase1APIResponseShape:
    async def test_score_returns_required_fields(self, async_client, valid_token, sample_transaction):
        response = await async_client.post(
            "/v1/score",
            json=sample_transaction,
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
        body = response.json()
        for field in ["transaction_id", "risk_score", "risk_level", "recommendation", "processing_time_ms", "signals"]:
            assert field in body, f"Missing field in response: {field}"

    async def test_risk_score_is_between_0_and_100(self, async_client, valid_token, sample_transaction):
        response = await async_client.post(
            "/v1/score",
            json=sample_transaction,
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200
        score = response.json()["risk_score"]
        assert 0 <= score <= 100, f"risk_score {score} is outside 0-100"

    async def test_risk_level_is_valid(self, async_client, valid_token, sample_transaction):
        response = await async_client.post(
            "/v1/score",
            json=sample_transaction,
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200
        assert response.json()["risk_level"] in {"LOW", "MEDIUM", "HIGH"}

    async def test_recommendation_is_valid(self, async_client, valid_token, sample_transaction):
        response = await async_client.post(
            "/v1/score",
            json=sample_transaction,
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200
        assert response.json()["recommendation"] in {"APPROVE", "FLAG", "BLOCK"}

    async def test_signals_contains_all_keys(self, async_client, valid_token, sample_transaction):
        response = await async_client.post(
            "/v1/score",
            json=sample_transaction,
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200
        signals = response.json()["signals"]
        for key in ["velocity", "amount_anomaly", "device_new", "location_change"]:
            assert key in signals, f"Missing signal: {key}"


class TestPhase1Latency:
    async def test_single_request_under_200ms(self, async_client, valid_token, sample_transaction):
        start = time.time()
        response = await async_client.post(
            "/v1/score",
            json=sample_transaction,
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        elapsed_ms = (time.time() - start) * 1000
        assert response.status_code == 200
        assert elapsed_ms < 200, f"Request took {elapsed_ms:.1f}ms — exceeds 200ms threshold"

    async def test_p95_latency_across_20_requests(self, async_client, valid_token):
        times = []
        for i in range(20):
            payload = {
                "transaction_id": f"TXN-LAT-{i}-{datetime.utcnow().timestamp()}",
                "amount": 1000.0 + i * 100,
                "location": "Nairobi, KE",
                "device_id": f"device-lat-{i}",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            start = time.time()
            response = await async_client.post(
                "/v1/score",
                json=payload,
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            elapsed_ms = (time.time() - start) * 1000
            if response.status_code == 200:
                times.append(elapsed_ms)
        assert len(times) >= 15, f"Only {len(times)}/20 requests succeeded — check model and DB"
        times.sort()
        p50 = times[len(times) // 2]
        p95 = times[int(len(times) * 0.95) - 1]
        print(f"\nLatency — p50: {p50:.1f}ms  p95: {p95:.1f}ms  max: {times[-1]:.1f}ms")
        assert p95 < 200, f"p95 {p95:.1f}ms exceeds 200ms threshold"


class TestPhase1Security:
    async def test_missing_token_returns_401(self, async_client, sample_transaction):
        response = await async_client.post("/v1/score", json=sample_transaction)
        assert response.status_code == 401

    async def test_expired_token_returns_401(self, async_client, expired_token, sample_transaction):
        response = await async_client.post(
            "/v1/score",
            json=sample_transaction,
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401

    async def test_tampered_token_returns_401(self, async_client, valid_token, sample_transaction):
        parts = valid_token.split(".")
        tampered = parts[0] + "." + parts[1] + ".invalidsignature"
        response = await async_client.post(
            "/v1/score",
            json=sample_transaction,
            headers={"Authorization": f"Bearer {tampered}"}
        )
        assert response.status_code == 401

    async def test_no_bearer_prefix_returns_401(self, async_client, valid_token, sample_transaction):
        response = await async_client.post(
            "/v1/score",
            json=sample_transaction,
            headers={"Authorization": valid_token}
        )
        assert response.status_code == 401


class TestPhase1MalformedInputs:
    @pytest.mark.parametrize("bad_payload,label", [
        ({}, "empty body"),
        ({"transaction_id": "T"}, "missing amount"),
        ({"transaction_id": "T", "amount": "abc", "location": "X", "device_id": "d"}, "amount as string"),
        ({"transaction_id": "T", "amount": None, "location": "X", "device_id": "d"}, "null amount"),
        ({"transaction_id": "T", "amount": -500, "location": "X", "device_id": "d"}, "negative amount"),
        ({"transaction_id": "T", "amount": 0, "location": "X", "device_id": "d"}, "zero amount"),
        ({"transaction_id": "", "amount": 1000, "location": "X", "device_id": "d"}, "empty transaction_id"),
        ({"transaction_id": "T", "amount": 1000, "location": "X", "device_id": None}, "null device_id"),
    ])
    async def test_bad_payload_returns_4xx_not_500(self, async_client, valid_token, bad_payload, label):
        response = await async_client.post(
            "/v1/score",
            json=bad_payload,
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code != 500, f"[{label}] Got 500 — should be 4xx for malformed input"
        assert response.status_code in {400, 422}, f"[{label}] Expected 400 or 422, got {response.status_code}"


class TestPhase1ExtremeValues:
    @pytest.mark.parametrize("amount,label", [
        (0.01, "minimum amount"),
        (9_999_999.0, "very large amount"),
        (1.0, "one KES"),
        (50_000.0, "mid range"),
    ])
    async def test_extreme_amounts_return_valid_score(self, async_client, valid_token, amount, label):
        payload = {
            "transaction_id": f"TXN-EXT-{amount}-{datetime.utcnow().timestamp()}",
            "amount": amount,
            "location": "Nairobi, KE",
            "device_id": "device-extreme",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        response = await async_client.post(
            "/v1/score",
            json=payload,
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200, f"[{label}] Got {response.status_code}: {response.text}"
        assert response.json()["risk_level"] in {"LOW", "MEDIUM", "HIGH"}, f"[{label}] Unexpected risk_level: {response.json()['risk_level']}"

    async def test_brand_new_device_registers_signal(self, async_client, valid_token):
        payload = {
            "transaction_id": f"TXN-NEWDEV-{datetime.utcnow().timestamp()}",
            "amount": 5000.0,
            "location": "Nairobi, KE",
            "device_id": f"never-seen-before-{datetime.utcnow().timestamp()}",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        response = await async_client.post(
            "/v1/score",
            json=payload,
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code == 200
        assert response.json()["signals"]["device_new"] > 0, "Expected device_new > 0 for a brand new device"
