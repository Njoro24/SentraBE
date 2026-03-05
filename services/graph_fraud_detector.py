#!/usr/bin/env python3
"""
Graph-based fraud detection algorithms
- Fraud ring detection (circular patterns)
- Network fraud scoring
- Community detection
"""

from neo4j import GraphDatabase
from collections import defaultdict
import json

class GraphFraudDetector:
    def __init__(self, uri="bolt://localhost:7687", username="neo4j", password="sentra123"):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self):
        self.driver.close()

    def detect_circular_patterns(self):
        """Detect circular money flow (characteristic of fraud rings)"""
        print("🔄 Detecting circular patterns (fraud rings)...")

        fraud_rings = []

        with self.driver.session() as session:
            # Find all cycles of length 2-10
            result = session.run("""
                MATCH cycle = (a:Account)-[*2..10]->(a)
                WHERE all(rel in relationships(cycle) | rel.is_fraud = true)
                RETURN [n in nodes(cycle) | n.id] as accounts, length(cycle) as cycle_length
                LIMIT 20
            """)

            for record in result:
                accounts = record['accounts']
                cycle_length = record['cycle_length']

                # Remove duplicates (same cycle detected multiple times)
                account_set = frozenset(accounts)
                if account_set not in [frozenset(r['accounts']) for r in fraud_rings]:
                    fraud_rings.append({
                        'accounts': accounts,
                        'cycle_length': cycle_length,
                        'confidence': 0.95,
                        'pattern': 'circular_flow'
                    })

        print(f"  ✓ Detected {len(fraud_rings)} fraud rings")
        return fraud_rings

    def detect_money_laundering_networks(self):
        """Detect suspicious networks (many transactions to/from same accounts)"""
        print("💰 Detecting money laundering networks...")

        suspicious_networks = []

        with self.driver.session() as session:
            # Find accounts with many connections to fraudulent accounts
            result = session.run("""
                MATCH (a:Account)-[t:TRANSFERS_TO]->(b:Account)
                WHERE t.is_fraud = true
                WITH a, count(distinct b) as outgoing_fraud_count,
                      sum(t.amount) as total_amount
                WHERE outgoing_fraud_count >= 3
                RETURN a.id as account, outgoing_fraud_count, total_amount
                ORDER BY outgoing_fraud_count DESC
            """)

            for record in result:
                suspicious_networks.append({
                    'hub_account': record['account'],
                    'fraud_connections': record['outgoing_fraud_count'],
                    'total_amount': record['total_amount'],
                    'suspicious_level': 'HIGH' if record['outgoing_fraud_count'] >= 5 else 'MEDIUM'
                })

        print(f"  ✓ Detected {len(suspicious_networks)} suspicious networks")
        return suspicious_networks

    def calculate_network_fraud_score(self, account_id):
        """Calculate fraud risk score based on network position"""
        print(f"📊 Calculating network fraud score for {account_id}...")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (a:Account {id: $account_id})-[t:TRANSFERS_TO]->(b)
                RETURN
                     count(t) as outgoing_count,
                    count(distinct case when b.is_fraudulent then b.id end) as fraud_connections,
                    avg(t.amount) as avg_amount,
                    sum(t.amount) as total_amount
            """, account_id=account_id)

            record = result.single()

            if not record:
                return 0.0

            outgoing = record['outgoing_count']
            fraud_conn = record['fraud_connections'] or 0
            avg_amt = record['avg_amount'] or 0

            # Calculate fraud score (0.0-1.0)
            score = 0.0

            # Factor 1: Percentage of connections to fraudulent accounts
            if outgoing > 0:
                fraud_ratio = fraud_conn / outgoing
                score += fraud_ratio * 0.5

            # Factor 2: Number of transactions (velocity)
            if outgoing >= 10:
                score += 0.3
            elif outgoing >= 5:
                score += 0.15

            # Factor 3: Average transaction amount
            if avg_amt > 100000:
                score += 0.2
            elif avg_amt > 50000:
                score += 0.1

            return min(score, 1.0)

    def detect_all_rings(self):
        """Detect all fraud ring members"""
        print("🔍 Detecting all fraud ring members...")

        rings_by_id = defaultdict(list)

        with self.driver.session() as session:
            result = session.run("""
                MATCH (a:Account)
                WHERE a.ring_id IS NOT NULL
                RETURN a.id as account, a.ring_id as ring_id
            """)

            for record in result:
                rings_by_id[record['ring_id']].append(record['account'])

        rings_list = []
        for ring_id, accounts in sorted(rings_by_id.items()):
            rings_list.append({
                'ring_id': ring_id,
                'accounts': accounts,
                'size': len(accounts),
                'detection_method': 'ring_id_matching'
            })

        print(f"  ✓ Detected {len(rings_list)} fraud rings")
        return rings_list

    def get_ring_details(self, ring_id):
        """Get detailed information about a fraud ring"""
        print(f"📋 Getting details for ring {ring_id}...")

        with self.driver.session() as session:
            # Get all members
            result = session.run("""
                MATCH (a:Account {ring_id: $ring_id})
                RETURN a.id as account, a.phone_number as phone, a.balance as balance
            """, ring_id=ring_id)

            members = [dict(record) for record in result]

            # Get all transactions within ring
            result = session.run("""
                MATCH (a:Account {ring_id: $ring_id})-[t:TRANSFERS_TO]->(b:Account {ring_id: $ring_id})
                RETURN
                     a.id as from_account,
                    b.id as to_account,
                    count(t) as count,
                    sum(t.amount) as total_amount
            """, ring_id=ring_id)

            transactions = [dict(record) for record in result]

            # Calculate total fraud amount
            total_amount = sum(t['total_amount'] or 0 for t in transactions)

        return {
            'ring_id': ring_id,
            'members': members,
            'size': len(members),
            'internal_transactions': transactions,
            'total_fraud_amount': total_amount
        }

    def run_all_detections(self):
        """Run all fraud detection algorithms"""
        print("═" * 60)
        print("GRAPH-BASED FRAUD DETECTION")
        print("═" * 60 + "\n")

        results = {}

        # Detection 1: Fraud rings
        results['fraud_rings_circular'] = self.detect_circular_patterns()
        print()

        # Detection 2: Money laundering
        results['money_laundering_networks'] = self.detect_money_laundering_networks()
        print()

        # Detection 3: All rings by ID
        results['fraud_rings_by_id'] = self.detect_all_rings()
        print()

        # Detection 4: Ring details
        print("📋 Getting detailed ring information...")
        results['ring_details'] = {}
        for ring in results['fraud_rings_by_id']:
            ring_id = ring['ring_id']
            details = self.get_ring_details(ring_id)
            results['ring_details'][ring_id] = details
            print(f"  ✓ Ring {ring_id}: {len(details['members'])} members, "
                  f"KES {details['total_fraud_amount']:,} total")
        print()

        # Save results
        output_file = 'data/fraud_rings/detection_results.json'
        os.makedirs('data/fraud_rings', exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print("═" * 60)
        print("✅ FRAUD DETECTION COMPLETE")
        print(f"Results saved to: {output_file}")
        print("═" * 60)

        return results

if __name__ == '__main__':
    import os
    detector = GraphFraudDetector()
    try:
        detector.run_all_detections()
    finally:
        detector.close()
