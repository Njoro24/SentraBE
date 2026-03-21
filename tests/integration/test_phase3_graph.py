"""
Phase 3 — Graph Fraud Ring Detection Tests
Tests: ring detection recall, false positives, network scoring, performance
"""
import pytest
import time
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.graph_fraud_detector import GraphFraudDetector


def get_detector():
    try:
        d = GraphFraudDetector()
        return d
    except Exception as e:
        pytest.skip(f"Neo4j not available: {e}")


class TestPhase3RingDetection:

    def test_all_10_fraud_rings_detected(self):
        """100% recall — all 10 known rings must be found"""
        d = get_detector()
        try:
            rings = d.detect_all_rings()
            assert len(rings) == 10, (
                f"Expected 10 fraud rings, detected {len(rings)}"
            )
        finally:
            d.close()

    def test_each_ring_has_correct_size(self):
        """Each ring must have exactly 5 accounts"""
        d = get_detector()
        try:
            rings = d.detect_all_rings()
            for ring in rings:
                assert ring["size"] == 5, (
                    f"Ring {ring['ring_id']} has {ring['size']} accounts, expected 5"
                )
        finally:
            d.close()

    def test_ring_ids_are_0_through_9(self):
        """Ring IDs must be 0-9"""
        d = get_detector()
        try:
            rings = d.detect_all_rings()
            ring_ids = sorted([r["ring_id"] for r in rings])
            assert ring_ids == list(range(10)), (
                f"Expected ring IDs 0-9, got {ring_ids}"
            )
        finally:
            d.close()

    def test_ring_accounts_are_unique(self):
        """No account should appear in more than one ring"""
        d = get_detector()
        try:
            rings = d.detect_all_rings()
            all_accounts = []
            for ring in rings:
                all_accounts.extend(ring["accounts"])
            assert len(all_accounts) == len(set(all_accounts)), (
                "Duplicate accounts found across rings"
            )
        finally:
            d.close()

    def test_total_ring_members_is_50(self):
        """10 rings × 5 accounts = 50 total fraud accounts"""
        d = get_detector()
        try:
            rings = d.detect_all_rings()
            total = sum(r["size"] for r in rings)
            assert total == 50, (
                f"Expected 50 total ring members, got {total}"
            )
        finally:
            d.close()


class TestPhase3FalsePositives:

    def test_clean_accounts_not_in_any_ring(self):
        """Accounts 050-099 are legitimate — must not appear in any ring"""
        d = get_detector()
        try:
            rings = d.detect_all_rings()
            ring_accounts = set()
            for ring in rings:
                ring_accounts.update(ring["accounts"])

            clean_accounts = [f"account_{i:03d}" for i in range(50, 100)]
            falsely_flagged = [a for a in clean_accounts if a in ring_accounts]

            assert len(falsely_flagged) == 0, (
                f"Clean accounts incorrectly flagged as ring members: {falsely_flagged}"
            )
        finally:
            d.close()

    def test_fraud_accounts_are_all_in_rings(self):
        """Accounts 000-049 are fraudulent — all must appear in rings"""
        d = get_detector()
        try:
            rings = d.detect_all_rings()
            ring_accounts = set()
            for ring in rings:
                ring_accounts.update(ring["accounts"])

            fraud_accounts = [f"account_{i:03d}" for i in range(50)]
            missed = [a for a in fraud_accounts if a not in ring_accounts]

            assert len(missed) == 0, (
                f"Fraud accounts not detected in any ring: {missed}"
            )
        finally:
            d.close()


class TestPhase3NetworkScoring:

    def test_fraud_account_has_high_network_score(self):
        """Known fraud account should score above 0.3"""
        d = get_detector()
        try:
            score = d.calculate_network_fraud_score("account_000")
            assert score > 0.3, (
                f"Fraud account_000 scored {score:.3f} — expected > 0.3"
            )
        finally:
            d.close()

    def test_clean_account_has_lower_network_score(self):
        """Legitimate account should score lower than fraud accounts"""
        d = get_detector()
        try:
            fraud_score = d.calculate_network_fraud_score("account_000")
            clean_score = d.calculate_network_fraud_score("account_099")
            assert fraud_score >= clean_score, (
                f"Fraud score {fraud_score:.3f} should be >= clean score {clean_score:.3f}"
            )
        finally:
            d.close()

    def test_network_score_is_between_0_and_1(self):
        """Network score must be in valid range"""
        d = get_detector()
        try:
            for account_id in ["account_000", "account_025", "account_099"]:
                score = d.calculate_network_fraud_score(account_id)
                assert 0.0 <= score <= 1.0, (
                    f"{account_id} score {score} is outside 0-1 range"
                )
        finally:
            d.close()


class TestPhase3RingDetails:

    def test_ring_details_returns_correct_members(self):
        """Ring 0 must have exactly 5 members"""
        d = get_detector()
        try:
            details = d.get_ring_details(0)
            assert len(details["members"]) == 5, (
                f"Ring 0 has {len(details['members'])} members, expected 5"
            )
        finally:
            d.close()

    def test_ring_details_has_internal_transactions(self):
        """Ring must have internal transactions between members"""
        d = get_detector()
        try:
            details = d.get_ring_details(0)
            assert len(details["internal_transactions"]) > 0, (
                "Ring 0 has no internal transactions"
            )
        finally:
            d.close()

    def test_ring_details_total_amount_is_positive(self):
        """Total fraud amount must be positive"""
        d = get_detector()
        try:
            details = d.get_ring_details(0)
            assert details["total_fraud_amount"] > 0, (
                f"Ring 0 total fraud amount is {details['total_fraud_amount']}"
            )
        finally:
            d.close()

    def test_all_10_ring_details_retrievable(self):
        """Must be able to get details for all 10 rings"""
        d = get_detector()
        try:
            for ring_id in range(10):
                details = d.get_ring_details(ring_id)
                assert details["ring_id"] == ring_id
                assert len(details["members"]) == 5
        finally:
            d.close()


class TestPhase3Performance:

    def test_ring_detection_completes_under_30_seconds(self):
        """Full ring detection must complete under 30 seconds"""
        d = get_detector()
        try:
            start = time.time()
            rings = d.detect_all_rings()
            elapsed = time.time() - start
            print(f"\n  Detection time: {elapsed:.2f}s")
            assert elapsed < 30, (
                f"Detection took {elapsed:.2f}s — exceeds 30 second threshold"
            )
            assert len(rings) == 10
        finally:
            d.close()

    def test_money_laundering_detection_runs(self):
        """Money laundering detection must complete without error"""
        d = get_detector()
        try:
            networks = d.detect_money_laundering_networks()
            assert isinstance(networks, list)
            print(f"\n  Suspicious networks found: {len(networks)}")
        finally:
            d.close()

    def test_circular_pattern_detection_runs(self):
        """Circular pattern detection must complete without error"""
        d = get_detector()
        try:
            rings = d.detect_circular_patterns()
            assert isinstance(rings, list)
            print(f"\n  Circular patterns found: {len(rings)}")
        finally:
            d.close()
