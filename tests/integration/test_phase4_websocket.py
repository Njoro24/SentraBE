"""
Phase 4 — WebSocket Dashboard Tests
Tests: connection, alert streaming, stability, feedback marking
"""
import pytest
import asyncio
import json
import uuid
import time
from datetime import datetime
from kafka import KafkaProducer
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
load_dotenv()

WS_URL      = "ws://localhost:8080"
BOOTSTRAP   = ["localhost:9092"]
ALERT_TOPIC = "sentra.alerts.fraud"

SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
SASL_MECHANISM    = os.getenv("KAFKA_SASL_MECHANISM", "PLAIN")
SASL_USERNAME     = os.getenv("KAFKA_SASL_USERNAME", "")
SASL_PASSWORD     = os.getenv("KAFKA_SASL_PASSWORD", "")


def sasl_config():
    if SECURITY_PROTOCOL == "SASL_PLAINTEXT":
        return {
            "security_protocol": SECURITY_PROTOCOL,
            "sasl_mechanism":    SASL_MECHANISM,
            "sasl_plain_username": SASL_USERNAME,
            "sasl_plain_password": SASL_PASSWORD,
        }
    return {}


def make_alert(transaction_id=None):
    return {
        "transaction_id": transaction_id or f"TXN-WS-{uuid.uuid4().hex[:8]}",
        "risk_score":     85,
        "risk_level":     "HIGH",
        "recommendation": "BLOCK",
        "amount":         50000.0,
        "location":       "Nairobi, KE",
        "timestamp":      datetime.utcnow().isoformat(),
        "signals": {
            "velocity":        0.9,
            "amount_anomaly":  0.8,
            "device_new":      1.0,
            "location_change": 0.7
        }
    }


def publish_alert(alert):
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks=1,
        **sasl_config()
    )
    producer.send(ALERT_TOPIC, alert)
    producer.flush()
    producer.close()


# ─────────────────────────────────────────────────────────────────
# CONNECTION TESTS
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_websocket_server_is_reachable():
    import websockets
    try:
        async with websockets.connect(WS_URL, open_timeout=5) as ws:
            assert ws.open
    except Exception as e:
        pytest.fail(f"Cannot connect: {e}")


@pytest.mark.asyncio
async def test_auth_message_accepted():
    import websockets
    async with websockets.connect(WS_URL, open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "auth", "client_id": 1, "api_key": "k"}))
        response = await asyncio.wait_for(ws.recv(), timeout=5)
        data = json.loads(response)
        assert data["type"] == "auth_success"


@pytest.mark.asyncio
async def test_status_message_received_after_auth():
    import websockets
    async with websockets.connect(WS_URL, open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "auth", "client_id": 1, "api_key": "k"}))
        await asyncio.wait_for(ws.recv(), timeout=5)  # auth_success
        response = await asyncio.wait_for(ws.recv(), timeout=5)  # status
        data = json.loads(response)
        assert data["type"] == "status"


@pytest.mark.asyncio
async def test_ping_pong():
    import websockets
    async with websockets.connect(WS_URL, open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "auth", "client_id": 1, "api_key": "k"}))
        await asyncio.wait_for(ws.recv(), timeout=5)
        await asyncio.wait_for(ws.recv(), timeout=5)
        await ws.send(json.dumps({"type": "ping"}))
        response = await asyncio.wait_for(ws.recv(), timeout=5)
        assert json.loads(response)["type"] == "pong"


@pytest.mark.asyncio
async def test_multiple_clients_connect_simultaneously():
    import websockets
    connections = []
    try:
        for i in range(5):
            ws = await websockets.connect(WS_URL, open_timeout=5)
            await ws.send(json.dumps({"type": "auth", "client_id": i, "api_key": "k"}))
            connections.append(ws)
        assert len(connections) == 5
    finally:
        for ws in connections:
            await ws.close()


# ─────────────────────────────────────────────────────────────────
# STREAMING TESTS
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_alert_published_to_kafka_appears_on_websocket():
    import websockets
    txn_id = f"TXN-WS-STREAM-{uuid.uuid4().hex[:8]}"

    async with websockets.connect(WS_URL, open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "auth", "client_id": 1, "api_key": "k"}))
        await asyncio.wait_for(ws.recv(), timeout=5)
        await asyncio.wait_for(ws.recv(), timeout=5)

        publish_alert(make_alert(txn_id))

        received = None
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                data = json.loads(msg)
                if data.get("type") == "fraud_alert":
                    if data["data"].get("transaction_id") == txn_id:
                        received = data
                        break
            except asyncio.TimeoutError:
                continue

        assert received is not None, f"Alert {txn_id} not received within 10s"
        print(f"\n  Alert received: {txn_id}")


@pytest.mark.asyncio
async def test_alert_contains_required_fields():
    import websockets
    txn_id = f"TXN-WS-FIELDS-{uuid.uuid4().hex[:8]}"

    async with websockets.connect(WS_URL, open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "auth", "client_id": 1, "api_key": "k"}))
        await asyncio.wait_for(ws.recv(), timeout=5)
        await asyncio.wait_for(ws.recv(), timeout=5)

        publish_alert(make_alert(txn_id))

        received = None
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                data = json.loads(msg)
                if data.get("type") == "fraud_alert":
                    if data["data"].get("transaction_id") == txn_id:
                        received = data["data"]
                        break
            except asyncio.TimeoutError:
                continue

        assert received is not None
        for field in ["transaction_id", "risk_score", "risk_level",
                      "recommendation", "timestamp"]:
            assert field in received, f"Missing field: {field}"


@pytest.mark.asyncio
async def test_10_alerts_all_received():
    import websockets
    batch_id = uuid.uuid4().hex[:8]
    txn_ids = [f"TXN-BATCH-{batch_id}-{i}" for i in range(10)]

    async with websockets.connect(WS_URL, open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "auth", "client_id": 1, "api_key": "k"}))
        await asyncio.wait_for(ws.recv(), timeout=5)
        await asyncio.wait_for(ws.recv(), timeout=5)

        for txn_id in txn_ids:
            publish_alert(make_alert(txn_id))

        received_ids = set()
        deadline = time.time() + 15
        while time.time() < deadline and len(received_ids) < 10:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                data = json.loads(msg)
                if data.get("type") == "fraud_alert":
                    tid = data["data"].get("transaction_id", "")
                    if tid in txn_ids:
                        received_ids.add(tid)
            except asyncio.TimeoutError:
                continue

        print(f"\n  Received {len(received_ids)}/10 alerts")
        assert len(received_ids) == 10, f"Only received {len(received_ids)}/10"


# ─────────────────────────────────────────────────────────────────
# STABILITY TEST
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connection_stays_open_for_60_seconds():
    import websockets
    async with websockets.connect(WS_URL, open_timeout=5) as ws:
        await ws.send(json.dumps({"type": "auth", "client_id": 1, "api_key": "k"}))
        await asyncio.wait_for(ws.recv(), timeout=5)
        await asyncio.wait_for(ws.recv(), timeout=5)

        start = time.time()
        disconnected = False

        while time.time() - start < 60:
            try:
                await ws.send(json.dumps({"type": "ping"}))
                await asyncio.wait_for(ws.recv(), timeout=5)
                await asyncio.sleep(10)
            except Exception as e:
                disconnected = True
                break

        elapsed = time.time() - start
        print(f"\n  Connection stable for {elapsed:.1f}s")
        assert not disconnected
        assert elapsed >= 59


# ─────────────────────────────────────────────────────────────────
# FEEDBACK TESTS
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mark_alert_correct(async_client, valid_token):
    txn_id = f"TXN-FB-{uuid.uuid4().hex[:8]}"
    response = await async_client.post(
        f"/alerts/{txn_id}/feedback",
        json={"marked_status": "correct", "analyst_notes": "Confirmed fraud"},
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    assert response.status_code in {200, 201}, f"Got {response.status_code}: {response.text}"


@pytest.mark.asyncio
async def test_mark_alert_incorrect(async_client, valid_token):
    txn_id = f"TXN-FB-{uuid.uuid4().hex[:8]}"
    response = await async_client.post(
        f"/alerts/{txn_id}/feedback",
        json={"marked_status": "incorrect", "analyst_notes": "False positive"},
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    assert response.status_code in {200, 201}


@pytest.mark.asyncio
async def test_mark_alert_escalate(async_client, valid_token):
    txn_id = f"TXN-FB-{uuid.uuid4().hex[:8]}"
    response = await async_client.post(
        f"/alerts/{txn_id}/feedback",
        json={"marked_status": "escalate"},
        headers={"Authorization": f"Bearer {valid_token}"}
    )
    assert response.status_code in {200, 201}


@pytest.mark.asyncio
async def test_50_correct_and_50_incorrect_stored(async_client, valid_token):
    from data.schema import get_db, AlertFeedback

    batch = uuid.uuid4().hex[:6]
    correct_ids   = [f"TXN-CORRECT-{batch}-{i}" for i in range(50)]
    incorrect_ids = [f"TXN-INCORRECT-{batch}-{i}" for i in range(50)]

    for txn_id in correct_ids:
        await async_client.post(
            f"/alerts/{txn_id}/feedback",
            json={"marked_status": "correct"},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
    for txn_id in incorrect_ids:
        await async_client.post(
            f"/alerts/{txn_id}/feedback",
            json={"marked_status": "incorrect"},
            headers={"Authorization": f"Bearer {valid_token}"}
        )

    db = next(get_db())
    try:
        stored_correct = db.query(AlertFeedback).filter(
            AlertFeedback.transaction_id.in_(correct_ids),
            AlertFeedback.marked_status == "correct"
        ).count()
        stored_incorrect = db.query(AlertFeedback).filter(
            AlertFeedback.transaction_id.in_(incorrect_ids),
            AlertFeedback.marked_status == "incorrect"
        ).count()
    finally:
        db.close()

    print(f"\n  Stored: {stored_correct} correct, {stored_incorrect} incorrect")
    assert stored_correct == 50, f"Expected 50 correct, got {stored_correct}"
    assert stored_incorrect == 50, f"Expected 50 incorrect, got {stored_incorrect}"
