#!/usr/bin/env python3
"""
Phase 3 End-to-End Validation Test
"""

import requests
import json

BASE_URL = "http://localhost:8000"
TOKEN = "YOUR_JWT_TOKEN"  # Get from login

headers = {
    "Authorization": f"Bearer {TOKEN}"
}

def test_fraud_rings_api():
    """Test fraud rings endpoint"""
    print("\n📊 TEST 1: Fraud Rings API")

    response = requests.get(f"{BASE_URL}/admin/fraud-rings", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data['total_rings'] == 10
    assert len(data['rings']) == 10

    print(f"  ✓ Got {data['total_rings']} fraud rings")
    print(f"  ✅ PASS")

def test_ring_details():
    """Test ring details endpoint"""
    print("\n📊 TEST 2: Ring Details API")

    response = requests.get(f"{BASE_URL}/admin/fraud-rings/0", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data['ring_id'] == 0
    assert data['size'] == 5
    assert len(data['members']) == 5

    print(f"  ✓ Ring 0: {data['size']} members")
    print(f"  ✓ Fraud amount: KES {data['total_fraud_amount']:,}")
    print(f"  ✅ PASS")

def test_network_fraud_score():
    """Test network fraud score calculation"""
    print("\n📊 TEST 3: Network Fraud Score API")

    # Test fraudulent account
    response = requests.get(
        f"{BASE_URL}/admin/account/account_000/network-score",
        headers=headers
    )
    assert response.status_code == 200

    data = response.json()
    assert 'network_fraud_score' in data
    assert data['risk_level'] in ['LOW', 'MEDIUM', 'HIGH']

    print(f"  ✓ Account_000: {data['network_fraud_score']} score ({data['risk_level']})")
    print(f"  ✅ PASS")

def test_money_laundering_detection():
    """Test money laundering network detection"""
    print("\n📊 TEST 4: Money Laundering Networks API")

    response = requests.get(
        f"{BASE_URL}/admin/money-laundering-networks",
        headers=headers
    )
    assert response.status_code == 200

    data = response.json()
    assert data['total_networks'] > 0

    print(f"  ✓ Detected {data['total_networks']} suspicious networks")
    print(f"  ✅ PASS")

def test_all_rings_detected():
    """Verify all 10 fraud rings are detected"""
    print("\n📊 TEST 5: All Rings Detected")

    response = requests.get(f"{BASE_URL}/admin/fraud-rings", headers=headers)
    data = response.json()

    ring_ids = [r['ring_id'] for r in data['rings']]
    expected_ids = list(range(10))

    assert ring_ids == expected_ids, f"Missing rings: {set(expected_ids) - set(ring_ids)}"

    print(f"  ✓ All 10 rings detected: {ring_ids}")
    print(f"  ✅ PASS")

def run_all_tests():
    print("═" * 60)
    print("PHASE 3: GRAPH FRAUD DETECTION VALIDATION")
    print("═" * 60)

    try:
        test_fraud_rings_api()
        test_ring_details()
        test_network_fraud_score()
        test_money_laundering_detection()
        test_all_rings_detected()

        print("\n" + "═" * 60)
        print("✅ ALL PHASE 3 TESTS PASSED")
        print("═" * 60)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False

    return True

if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)
