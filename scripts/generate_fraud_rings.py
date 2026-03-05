#!/usr/bin/env python3
"""
Generate synthetic fraud ring data for Phase 3
- 100 accounts
- 10 fraud rings (5 accounts each)
- 1000 transactions connecting them
"""

import json
import random
from datetime import datetime, timedelta
from uuid import uuid4
import os

class FraudRingGenerator:
    def __init__(self):
        self.accounts = []
        self.transactions = []
        self.fraud_rings = []

    def generate_accounts(self):
        """Generate 100 accounts"""
        print("📝 Generating 100 accounts...")

        # 50 fraudulent accounts (in rings)
        fraud_account_ids = []
        for i in range(50):
            account = {
                'id': f'account_{i:03d}',
                'phone_number': f'+254{random.randint(700000000, 799999999)}',
                'name': f'Fraudster_{i}',
                'is_fraudulent': True,
                'ring_id': i // 5,  # 10 rings × 5 accounts
                'created_at': (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(),
                'balance': random.randint(10000, 1000000)
            }
            self.accounts.append(account)
            fraud_account_ids.append(account['id'])

        # 50 legitimate accounts
        for i in range(50, 100):
            account = {
                'id': f'account_{i:03d}',
                'phone_number': f'+254{random.randint(700000000, 799999999)}',
                'name': f'Customer_{i}',
                'is_fraudulent': False,
                'ring_id': None,
                'created_at': (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(),
                'balance': random.randint(10000, 5000000)
            }
            self.accounts.append(account)

        print(f"  ✓ Created 100 accounts (50 fraudulent, 50 legitimate)")
        return fraud_account_ids

    def generate_fraud_rings(self, fraud_accounts):
        """Generate 10 fraud rings with transactions"""
        print("🔀 Generating 10 fraud rings...")

        # Create 10 rings
        for ring_id in range(10):
            ring_accounts = fraud_accounts[ring_id * 5:(ring_id + 1) * 5]  # 5 accounts per ring

            ring_info = {
                'ring_id': ring_id,
                'accounts': ring_accounts,
                'size': len(ring_accounts),
                'pattern': 'circular_money_flow'
            }
            self.fraud_rings.append(ring_info)

            print(f"  ✓ Ring {ring_id}: {len(ring_accounts)} accounts - {ring_accounts}")

        return self.fraud_rings

    def generate_transactions(self, fraud_rings, legitimate_accounts):
        """Generate 1000 transactions"""
        print("💸 Generating 1000 transactions...")

        txn_count = 0

        # Fraud ring transactions (500 txns)
        for ring in fraud_rings:
            accounts = ring['accounts']
            # Create circular pattern: A→B→C→D→E→A
            for round_num in range(10):  # 10 rounds per ring
                for i, account in enumerate(accounts):
                    next_account = accounts[(i + 1) % len(accounts)]

                    txn = {
                        'id': f'txn_{txn_count:04d}',
                        'from_account': account,
                        'to_account': next_account,
                        'amount': random.randint(50000, 200000),
                        'timestamp': (datetime.now() - timedelta(hours=random.randint(1, 168))).isoformat(),
                        'is_fraud': True,
                        'ring_id': ring['ring_id'],
                        'transaction_type': 'money_transfer'
                    }
                    self.transactions.append(txn)
                    txn_count += 1

        # Legitimate transactions (500 txns)
        for _ in range(500):
            from_acc = random.choice(self.accounts)
            to_acc = random.choice([a for a in self.accounts if a['id'] != from_acc['id']])

            txn = {
                'id': f'txn_{txn_count:04d}',
                'from_account': from_acc['id'],
                'to_account': to_acc['id'],
                'amount': random.randint(1000, 100000),
                'timestamp': (datetime.now() - timedelta(hours=random.randint(1, 168))).isoformat(),
                'is_fraud': False,
                'ring_id': None,
                'transaction_type': random.choice(['payment', 'transfer', 'purchase'])
            }
            self.transactions.append(txn)
            txn_count += 1

        print(f"  ✓ Created {txn_count} transactions (500 fraud, 500 legitimate)")

    def save_to_files(self):
        """Save to JSON files"""
        print("💾 Saving to files...")

        output_dir = 'data/fraud_rings'

        # Create directory
        os.makedirs(output_dir, exist_ok=True)

        # Save accounts
        with open(f'{output_dir}/accounts.json', 'w') as f:
            json.dump(self.accounts, f, indent=2)
        print(f"  ✓ Saved {len(self.accounts)} accounts")

        # Save fraud rings
        with open(f'{output_dir}/fraud_rings.json', 'w') as f:
            json.dump(self.fraud_rings, f, indent=2)
        print(f"  ✓ Saved {len(self.fraud_rings)} fraud rings")

        # Save transactions
        with open(f'{output_dir}/transactions.json', 'w') as f:
            json.dump(self.transactions, f, indent=2)
        print(f"  ✓ Saved {len(self.transactions)} transactions")

    def run(self):
        """Run all generation steps"""
        print("═" * 50)
        print("FRAUD RING DATA GENERATION")
        print("═" * 50 + "\n")

        fraud_accounts = self.generate_accounts()
        print()

        fraud_rings = self.generate_fraud_rings(fraud_accounts)
        print()

        legitimate_accounts = [a['id'] for a in self.accounts if not a['is_fraudulent']]
        self.generate_transactions(fraud_rings, legitimate_accounts)
        print()

        self.save_to_files()
        print()

        print("═" * 50)
        print("✅ DATA GENERATION COMPLETE")
        print("═" * 50)

if __name__ == '__main__':
    generator = FraudRingGenerator()
    generator.run()
