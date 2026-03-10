#!/usr/bin/env python3
"""
Phase 5 Integration Test
Tests T24 API, adapter, and end-to-end scoring pipeline
"""

import sys
import os
import json
import asyncio
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.t24_adapter import T24Adapter, TransactionRequest


class Phase5IntegrationTest:
    """Test Phase 5 integration components"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.test_results = []
    
    def print_header(self, title):
        """Print test section header"""
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)
    
    def print_test(self, name, status, details=""):
        """Print test result"""
        symbol = "✅" if status else "❌"
        print(f"{symbol} {name}")
        if details:
            print(f"   {details}")
        
        if status:
            self.passed += 1
        else:
            self.failed += 1
        
        self.test_results.append({
            "name": name,
            "status": status,
            "details": details
        })
    
    def test_t24_adapter_validation(self):
        """Test T24 transaction validation"""
        self.print_header("TEST 1: T24 Adapter Validation")
        
        # Valid transaction
        valid_txn = {
            "TRANSACTION_ID": "T24001",
            "AMOUNT": 50000,
            "CURRENCY": "KES",
            "ACCOUNT_NUMBER": "1234567890",
            "TIMESTAMP": datetime.now().isoformat()
        }
        
        is_valid = T24Adapter.validate_t24_transaction(valid_txn)
        self.print_test("Valid transaction passes validation", is_valid)
        
        # Invalid transaction (missing required field)
        invalid_txn = {
            "TRANSACTION_ID": "T24002",
            "AMOUNT": 50000,
            # Missing CURRENCY
            "ACCOUNT_NUMBER": "1234567890",
            "TIMESTAMP": datetime.now().isoformat()
        }
        
        is_invalid = not T24Adapter.validate_t24_transaction(invalid_txn)
        self.print_test("Invalid transaction fails validation", is_invalid)
    
    def test_t24_field_normalization(self):
        """Test T24 field normalization"""
        self.print_header("TEST 2: T24 Field Normalization")
        
        # Test channel normalization
        channel = T24Adapter.normalize_channel("MOBILE_BANKING")
        self.print_test(
            "Channel normalization (MOBILE_BANKING → MOBILE)",
            channel == "MOBILE",
            f"Result: {channel}"
        )
        
        # Test merchant category normalization
        category = T24Adapter.normalize_merchant_category("Cryptocurrency")
        self.print_test(
            "Merchant category normalization (Cryptocurrency → CRYPTOCURRENCY)",
            category == "CRYPTOCURRENCY",
            f"Result: {category}"
        )
        
        # Test amount normalization (currency conversion)
        amount_kes = T24Adapter.normalize_amount(100, "KES")
        amount_usd = T24Adapter.normalize_amount(100, "USD")
        
        self.print_test(
            "Amount normalization (100 KES = 100 KES)",
            amount_kes == 100.0,
            f"Result: {amount_kes}"
        )
        
        self.print_test(
            "Amount normalization (100 USD ≈ 13000 KES)",
            12500 < amount_usd < 14000,
            f"Result: {amount_usd}"
        )
    
    def test_t24_transformation(self):
        """Test T24 to internal format transformation"""
        self.print_header("TEST 3: T24 to Internal Transformation")
        
        # Create mock T24 transaction
        t24_txn = {
            "TRANSACTION_ID": "T24TEST001",
            "AMOUNT": 75000,
            "CURRENCY": "KES",
            "MERCHANT_NAME": "SAFARICOM AIRTIME",
            "MERCHANT_CATEGORY": "Retail",
            "MERCHANT_LOCATION": "Nairobi",
            "ACCOUNT_NUMBER": "1234567890",
            "COUNTERPARTY_ACCOUNT": "9876543210",
            "CHANNEL": "MOBILE_BANKING",
            "DEVICE_ID": "DEV123456",
            "IP_ADDRESS": "192.168.1.1",
            "TIMESTAMP": datetime.now().isoformat(),
            "VELOCITY_FLAG": False,
            "GEOGRAPHIC_MISMATCH": False,
            "DEVICE_MISMATCH": False
        }
        
        # Transform
        txn_request = T24Adapter.transform_t24_to_internal(t24_txn)
        
        self.print_test(
            "T24 transformation successful",
            txn_request is not None,
            f"Transformed to: {type(txn_request).__name__}"
        )
        
        if txn_request:
            # Verify transformed fields
            self.print_test(
                "Transaction ID preserved",
                txn_request.transaction_id == "T24TEST001",
                f"ID: {txn_request.transaction_id}"
            )
            
            self.print_test(
                "Amount normalized",
                txn_request.amount == 75000.0,
                f"Amount: {txn_request.amount}"
            )
            
            self.print_test(
                "Merchant category normalized",
                txn_request.merchant_category == "RETAIL",
                f"Category: {txn_request.merchant_category}"
            )
            
            self.print_test(
                "Channel normalized",
                txn_request.channel == "MOBILE",
                f"Channel: {txn_request.channel}"
            )
    
    def test_batch_transformation(self):
        """Test batch transformation"""
        self.print_header("TEST 4: Batch Transformation")
        
        # Create batch of T24 transactions
        batch = []
        for i in range(5):
            txn = {
                "TRANSACTION_ID": f"T24BATCH{i:03d}",
                "AMOUNT": 50000 + (i * 10000),
                "CURRENCY": "KES",
                "MERCHANT_NAME": f"MERCHANT_{i}",
                "MERCHANT_CATEGORY": "Retail",
                "MERCHANT_LOCATION": "Nairobi",
                "ACCOUNT_NUMBER": f"ACC{i:010d}",
                "COUNTERPARTY_ACCOUNT": f"CPTY{i:010d}",
                "CHANNEL": "MOBILE_BANKING",
                "DEVICE_ID": f"DEV{i:06d}",
                "IP_ADDRESS": "192.168.1.1",
                "TIMESTAMP": datetime.now().isoformat()
            }
            batch.append(txn)
        
        # Transform batch
        transformed = T24Adapter.transform_batch(batch)
        
        self.print_test(
            "Batch transformation successful",
            len(transformed) == 5,
            f"Transformed {len(transformed)}/5 transactions"
        )
        
        if len(transformed) > 0:
            self.print_test(
                "All transactions transformed",
                all(isinstance(t, TransactionRequest) for t in transformed),
                f"All items are TransactionRequest objects"
            )
    
    def test_transaction_to_dict(self):
        """Test converting TransactionRequest to dictionary"""
        self.print_header("TEST 5: TransactionRequest to Dictionary")
        
        txn_request = TransactionRequest(
            transaction_id="T24DICT001",
            amount=100000,
            currency="KES",
            merchant_name="TEST MERCHANT",
            merchant_category="RETAIL",
            merchant_location="Nairobi",
            account_number="1234567890",
            counterparty_account="9876543210",
            channel="MOBILE",
            device_id="DEV123456",
            ip_address="192.168.1.1",
            timestamp=datetime.now().isoformat()
        )
        
        txn_dict = T24Adapter.to_dict(txn_request)
        
        self.print_test(
            "Conversion to dictionary successful",
            isinstance(txn_dict, dict),
            f"Result type: {type(txn_dict).__name__}"
        )
        
        self.print_test(
            "Dictionary contains all fields",
            len(txn_dict) >= 15,
            f"Fields: {len(txn_dict)}"
        )
        
        self.print_test(
            "Transaction ID preserved in dict",
            txn_dict.get("transaction_id") == "T24DICT001",
            f"ID: {txn_dict.get('transaction_id')}"
        )
    
    def test_edge_cases(self):
        """Test edge cases and error handling"""
        self.print_header("TEST 6: Edge Cases & Error Handling")
        
        # Test with missing optional fields
        minimal_txn = {
            "TRANSACTION_ID": "T24EDGE001",
            "AMOUNT": 1000,
            "CURRENCY": "KES",
            "ACCOUNT_NUMBER": "1234567890",
            "TIMESTAMP": datetime.now().isoformat()
        }
        
        txn_request = T24Adapter.transform_t24_to_internal(minimal_txn)
        self.print_test(
            "Handles minimal transaction (missing optional fields)",
            txn_request is not None,
            "Successfully transformed minimal transaction"
        )
        
        # Test with very large amount
        large_txn = {
            "TRANSACTION_ID": "T24LARGE001",
            "AMOUNT": 999999999,
            "CURRENCY": "USD",
            "MERCHANT_NAME": "LARGE TRANSACTION",
            "MERCHANT_CATEGORY": "Wire Transfer",
            "MERCHANT_LOCATION": "New York",
            "ACCOUNT_NUMBER": "1234567890",
            "COUNTERPARTY_ACCOUNT": "9876543210",
            "CHANNEL": "BRANCH",
            "DEVICE_ID": "BRANCH001",
            "IP_ADDRESS": "192.168.1.1",
            "TIMESTAMP": datetime.now().isoformat()
        }
        
        large_txn_request = T24Adapter.transform_t24_to_internal(large_txn)
        self.print_test(
            "Handles very large amounts",
            large_txn_request is not None and large_txn_request.amount > 100000000,
            f"Amount: {large_txn_request.amount if large_txn_request else 'N/A'}"
        )
        
        # Test with invalid timestamp
        invalid_ts_txn = {
            "TRANSACTION_ID": "T24TS001",
            "AMOUNT": 50000,
            "CURRENCY": "KES",
            "ACCOUNT_NUMBER": "1234567890",
            "TIMESTAMP": "INVALID_TIMESTAMP"
        }
        
        ts_txn_request = T24Adapter.transform_t24_to_internal(invalid_ts_txn)
        self.print_test(
            "Handles invalid timestamp gracefully",
            ts_txn_request is not None,
            "Successfully transformed with fallback timestamp"
        )
    
    def test_data_integrity(self):
        """Test data integrity through transformation"""
        self.print_header("TEST 7: Data Integrity")
        
        original_txn = {
            "TRANSACTION_ID": "T24INTEGRITY001",
            "AMOUNT": 123456,
            "CURRENCY": "KES",
            "MERCHANT_NAME": "INTEGRITY TEST",
            "MERCHANT_CATEGORY": "Retail",
            "MERCHANT_LOCATION": "Nairobi",
            "ACCOUNT_NUMBER": "1111111111",
            "COUNTERPARTY_ACCOUNT": "2222222222",
            "CHANNEL": "MOBILE_BANKING",
            "DEVICE_ID": "DEV999999",
            "IP_ADDRESS": "10.0.0.1",
            "TIMESTAMP": datetime.now().isoformat(),
            "VELOCITY_FLAG": True,
            "GEOGRAPHIC_MISMATCH": True,
            "DEVICE_MISMATCH": False
        }
        
        # Transform
        txn_request = T24Adapter.transform_t24_to_internal(original_txn)
        
        # Convert back to dict
        result_dict = T24Adapter.to_dict(txn_request)
        
        # Verify key fields match
        self.print_test(
            "Transaction ID integrity",
            result_dict["transaction_id"] == original_txn["TRANSACTION_ID"],
            f"Original: {original_txn['TRANSACTION_ID']}, Result: {result_dict['transaction_id']}"
        )
        
        self.print_test(
            "Amount integrity",
            result_dict["amount"] == original_txn["AMOUNT"],
            f"Original: {original_txn['AMOUNT']}, Result: {result_dict['amount']}"
        )
        
        self.print_test(
            "Account number integrity",
            result_dict["account_number"] == original_txn["ACCOUNT_NUMBER"],
            f"Original: {original_txn['ACCOUNT_NUMBER']}, Result: {result_dict['account_number']}"
        )
        
        self.print_test(
            "Risk flags integrity",
            result_dict["velocity_flag"] == original_txn["VELOCITY_FLAG"],
            f"Original: {original_txn['VELOCITY_FLAG']}, Result: {result_dict['velocity_flag']}"
        )
    
    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "=" * 70)
        print("  PHASE 5 INTEGRATION TEST SUITE")
        print("  T24 API, Adapter, and Scoring Pipeline")
        print("=" * 70)
        
        self.test_t24_adapter_validation()
        self.test_t24_field_normalization()
        self.test_t24_transformation()
        self.test_batch_transformation()
        self.test_transaction_to_dict()
        self.test_edge_cases()
        self.test_data_integrity()
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        total = self.passed + self.failed
        
        print("\n" + "=" * 70)
        print("  TEST SUMMARY")
        print("=" * 70)
        print(f"Total Tests:  {total}")
        print(f"Passed:       {self.passed} ✅")
        print(f"Failed:       {self.failed} ❌")
        print(f"Success Rate: {(self.passed/total*100):.1f}%")
        print("=" * 70)
        
        if self.failed == 0:
            print("\n🎉 ALL TESTS PASSED - PHASE 5 READY FOR DEPLOYMENT\n")
        else:
            print(f"\n⚠️  {self.failed} TEST(S) FAILED - REVIEW REQUIRED\n")
        
        # Save results
        results = {
            "timestamp": datetime.now().isoformat(),
            "total": total,
            "passed": self.passed,
            "failed": self.failed,
            "success_rate": (self.passed/total*100),
            "tests": self.test_results
        }
        
        os.makedirs("data/test_results", exist_ok=True)
        with open("data/test_results/phase5_test_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"Results saved to: data/test_results/phase5_test_results.json\n")


if __name__ == "__main__":
    tester = Phase5IntegrationTest()
    tester.run_all_tests()
