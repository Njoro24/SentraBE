"""Phase 4 — Feedback System Tests"""
import pytest
import uuid
import asyncio
from datetime import datetime

pytestmark = pytest.mark.asyncio


class TestPhase4FeedbackMarking:
    async def test_mark_alert_correct(self, async_client, valid_token):
        """Mark alert as correct via API"""
        txn_id = f"TXN-FB-{uuid.uuid4().hex[:8]}"
        score_payload = {
            "transaction_id": txn_id,
            "amount": 5000.0,
            "location": "Nairobi, KE",
            "device_id": "device-test-123",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        score_response = await async_client.post(
            "/v1/score",
            json=score_payload,
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert score_response.status_code == 200, f"Score failed: {score_response.text}"
        
        response = await async_client.post(
            f"/alerts/{txn_id}/feedback",
            json={"marked_status": "correct", "analyst_notes": "Confirmed fraud"},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code in {200, 201}, f"Got {response.status_code}: {response.text}"

    async def test_mark_alert_incorrect(self, async_client, valid_token):
        """Mark alert as incorrect via API"""
        txn_id = f"TXN-FB-{uuid.uuid4().hex[:8]}"
        score_payload = {
            "transaction_id": txn_id,
            "amount": 5000.0,
            "location": "Nairobi, KE",
            "device_id": "device-test-123",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        score_response = await async_client.post(
            "/v1/score",
            json=score_payload,
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert score_response.status_code == 200
        
        response = await async_client.post(
            f"/alerts/{txn_id}/feedback",
            json={"marked_status": "incorrect", "analyst_notes": "False positive"},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code in {200, 201}

    async def test_mark_alert_escalate(self, async_client, valid_token):
        """Mark alert as escalate via API"""
        txn_id = f"TXN-FB-{uuid.uuid4().hex[:8]}"
        score_payload = {
            "transaction_id": txn_id,
            "amount": 5000.0,
            "location": "Nairobi, KE",
            "device_id": "device-test-123",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        score_response = await async_client.post(
            "/v1/score",
            json=score_payload,
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert score_response.status_code == 200
        
        response = await async_client.post(
            f"/alerts/{txn_id}/feedback",
            json={"marked_status": "escalate"},
            headers={"Authorization": f"Bearer {valid_token}"}
        )
        assert response.status_code in {200, 201}

    async def test_50_correct_and_50_incorrect_stored(self, async_client, valid_token):
        """Mark 10 correct and 10 incorrect — verify all stored"""
        from data.schema import get_db, AlertFeedback
        
        batch = uuid.uuid4().hex[:6]
        correct_ids = [f"TXN-CORRECT-{batch}-{i}" for i in range(10)]
        incorrect_ids = [f"TXN-INCORRECT-{batch}-{i}" for i in range(10)]
        
        # Score all transactions first with delays to avoid rate limit
        for txn_id in correct_ids + incorrect_ids:
            payload = {
                "transaction_id": txn_id,
                "amount": 5000.0,
                "location": "Nairobi, KE",
                "device_id": "device-test-123",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            response = await async_client.post(
                "/v1/score",
                json=payload,
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            assert response.status_code == 200, f"Score failed for {txn_id}: {response.text}"
            await asyncio.sleep(0.1)  # 100ms delay between requests
        
        # Now give feedback
        for txn_id in correct_ids:
            await async_client.post(
                f"/alerts/{txn_id}/feedback",
                json={"marked_status": "correct"},
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            await asyncio.sleep(0.01)
        
        for txn_id in incorrect_ids:
            await async_client.post(
                f"/alerts/{txn_id}/feedback",
                json={"marked_status": "incorrect"},
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            await asyncio.sleep(0.01)
        
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
        assert stored_correct == 10, f"Expected 10 correct, got {stored_correct}"
        assert stored_incorrect == 10, f"Expected 10 incorrect, got {stored_incorrect}"
