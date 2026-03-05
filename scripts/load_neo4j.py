#!/usr/bin/env python3
"""
Load synthetic fraud ring data into Neo4j
"""

import json
from neo4j import GraphDatabase
import os

class Neo4jLoader:
    def __init__(self, uri="bolt://localhost:7687", username="neo4j", password="sentra123"):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self):
        self.driver.close()

    def clear_database(self):
        """Delete all nodes and relationships"""
        print("🗑️  Clearing database...")
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("  ✓ Database cleared")

    def load_accounts(self, accounts):
        """Load accounts as nodes"""
        print("📥 Loading accounts...")

        with self.driver.session() as session:
            for account in accounts:
                session.run("""
                    CREATE (a:Account {
                        id: $id,
                        phone_number: $phone,
                        name: $name,
                        is_fraudulent: $is_fraud,
                        ring_id: $ring_id,
                        created_at: $created,
                        balance: $balance
                    })
                """,
                    id=account['id'],
                    phone=account['phone_number'],
                    name=account['name'],
                    is_fraud=account['is_fraudulent'],
                    ring_id=account.get('ring_id'),
                    created=account['created_at'],
                    balance=account['balance']
                )

        print(f"  ✓ Loaded {len(accounts)} accounts")

    def load_transactions(self, transactions):
        """Load transactions as relationships"""
        print("📥 Loading transactions...")

        with self.driver.session() as session:
            for txn in transactions:
                session.run("""
                    MATCH (from:Account {id: $from})
                    MATCH (to:Account {id: $to})
                    CREATE (from)-[t:TRANSFERS_TO {
                        txn_id: $txn_id,
                        amount: $amount,
                        timestamp: $timestamp,
                        is_fraud: $is_fraud,
                        ring_id: $ring_id,
                        type: $type
                    }]->(to)
                """,
                    from_=txn['from_account'],
                    to=txn['to_account'],
                    txn_id=txn['id'],
                    amount=txn['amount'],
                    timestamp=txn['timestamp'],
                    is_fraud=txn['is_fraud'],
                    ring_id=txn.get('ring_id'),
                    type=txn.get('transaction_type', 'transfer')
                )

        print(f"  ✓ Loaded {len(transactions)} transactions")

    def create_indexes(self):
        """Create indexes for performance"""
        print("🔍 Creating indexes...")

        with self.driver.session() as session:
            session.run("CREATE INDEX account_id IF NOT EXISTS FOR (a:Account) ON (a.id)")
            session.run("CREATE INDEX account_fraud IF NOT EXISTS FOR (a:Account) ON (a.is_fraudulent)")
            session.run("CREATE INDEX account_ring IF NOT EXISTS FOR (a:Account) ON (a.ring_id)")

        print("  ✓ Indexes created")

    def verify_load(self):
        """Verify data loaded correctly"""
        print("✔️  Verifying data...")

        with self.driver.session() as session:
            # Count nodes
            result = session.run("MATCH (a:Account) RETURN count(a) as count")
            account_count = result.single()['count']

            # Count relationships
            result = session.run("MATCH (a)-[t:TRANSFERS_TO]->(b) RETURN count(t) as count")
            txn_count = result.single()['count']

            # Count fraud accounts
            result = session.run("MATCH (a:Account {is_fraudulent: true}) RETURN count(a) as count")
            fraud_count = result.single()['count']

        print(f"  ✓ Accounts: {account_count}")
        print(f"  ✓ Transactions: {txn_count}")
        print(f"  ✓ Fraudulent accounts: {fraud_count}")

        if account_count == 100 and txn_count == 1000 and fraud_count == 50:
            print("  ✅ All data loaded correctly")
        else:
            print("  ❌ Data mismatch!")

    def run(self):
        """Run all loading steps"""
        print("═" * 50)
        print("LOADING DATA INTO NEO4J")
        print("═" * 50 + "\n")

        # Load data files
        data_dir = 'data/fraud_rings'

        with open(f'{data_dir}/accounts.json') as f:
            accounts = json.load(f)

        with open(f'{data_dir}/transactions.json') as f:
            transactions = json.load(f)

        print()
        self.clear_database()
        print()
        self.load_accounts(accounts)
        print()
        self.load_transactions(transactions)
        print()
        self.create_indexes()
        print()
        self.verify_load()
        print()

        print("═" * 50)
        print("✅ DATA LOADED SUCCESSFULLY")
        print("═" * 50)

if __name__ == '__main__':
    loader = Neo4jLoader()
    try:
        loader.run()
    finally:
        loader.close()
