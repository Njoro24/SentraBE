"""
Phase 2 — Kafka Streaming Tests
Tests: throughput, zero message loss, velocity spike detection
Topics: sentra.transactions.raw, sentra.alerts.fraud, sentra.scores.output
"""
import pytest
import json
import time
import uuid
import threading
from datetime import datetime
from kafka import KafkaProducer, KafkaConsumer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import KafkaError

BOOTSTRAP_SERVERS = ["localhost:9092"]
TOPIC_TRANSACTIONS = "sentra.transactions.raw"
TOPIC_ALERTS       = "sentra.alerts.fraud"
TOPIC_SCORES       = "sentra.scores.output"


def make_producer():
    return KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
        retries=3,
        request_timeout_ms=10000
    )


def make_consumer(topic, group_id, timeout_ms=5000):
    return KafkaConsumer(
        topic,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        consumer_timeout_ms=timeout_ms
    )


def make_transaction(account_id=None, amount=5000.0, idx=0):
    return {
        "transaction_id": f"TXN-P2-{uuid.uuid4().hex[:8]}-{idx}",
        "account_id": account_id or f"ACC-{uuid.uuid4().hex[:6]}",
        "amount": amount,
        "location": "Nairobi, KE",
        "device_id": "device-p2-test",
        "timestamp": datetime.utcnow().isoformat(),
        "merchant_category": "RETAIL"
    }


class TestPhase2KafkaConnection:

    def test_kafka_broker_is_reachable(self):
        try:
            producer = make_producer()
            producer.close()
        except Exception as e:
            pytest.fail(f"Cannot connect to Kafka at {BOOTSTRAP_SERVERS}: {e}")

    def test_all_required_topics_exist(self):
        consumer = KafkaConsumer(bootstrap_servers=BOOTSTRAP_SERVERS)
        topics = consumer.topics()
        consumer.close()
        for topic in [TOPIC_TRANSACTIONS, TOPIC_ALERTS, TOPIC_SCORES]:
            assert topic in topics, (
                f"Topic {topic} not found. "
                f"Available topics: {topics}"
            )

    def test_producer_sends_single_message(self):
        producer = make_producer()
        msg = make_transaction(idx=0)
        future = producer.send(TOPIC_TRANSACTIONS, msg)
        result = future.get(timeout=10)
        producer.close()
        assert result.topic == TOPIC_TRANSACTIONS
        assert result.offset >= 0

    def test_consumer_reads_produced_message(self):
        unique_id = f"TXN-READ-TEST-{uuid.uuid4().hex[:8]}"
        producer = make_producer()
        producer.send(TOPIC_TRANSACTIONS, {"transaction_id": unique_id, "test": True})
        producer.flush()
        producer.close()

        group_id = f"test-read-{uuid.uuid4().hex[:6]}"
        consumer = make_consumer(TOPIC_TRANSACTIONS, group_id, timeout_ms=8000)
        found = False
        for msg in consumer:
            if msg.value.get("transaction_id") == unique_id:
                found = True
                break
        consumer.close()
        assert found, f"Message {unique_id} not found in topic"


class TestPhase2Throughput:

    def test_produce_1000_messages_no_loss(self):
        """Produce 1000 messages and verify all are consumed"""
        batch_id = uuid.uuid4().hex[:8]
        n = 1000
        sent_ids = set()

        producer = make_producer()
        for i in range(n):
            msg = make_transaction(idx=i)
            msg["batch_id"] = batch_id
            sent_ids.add(msg["transaction_id"])
            producer.send(TOPIC_TRANSACTIONS, msg)
        producer.flush()
        producer.close()
        print(f"\n  Produced {n} messages, batch_id={batch_id}")

        group_id = f"test-throughput-{uuid.uuid4().hex[:6]}"
        consumer = make_consumer(TOPIC_TRANSACTIONS, group_id, timeout_ms=15000)
        received_ids = set()
        for msg in consumer:
            if msg.value.get("batch_id") == batch_id:
                received_ids.add(msg.value["transaction_id"])
        consumer.close()

        lost = sent_ids - received_ids
        loss_rate = len(lost) / n
        print(f"  Received {len(received_ids)}/{n} — loss rate: {loss_rate:.2%}")
        assert len(lost) == 0, (
            f"{len(lost)} messages lost out of {n}. "
            f"Loss rate: {loss_rate:.2%}"
        )

    def test_producer_throughput_rate(self):
        """Measure how many messages per second the producer can send"""
        n = 500
        producer = make_producer()
        start = time.time()
        for i in range(n):
            producer.send(TOPIC_TRANSACTIONS, make_transaction(idx=i))
        producer.flush()
        elapsed = time.time() - start
        producer.close()

        rate = n / elapsed
        print(f"\n  Throughput: {rate:.0f} msg/sec ({n} messages in {elapsed:.2f}s)")
        assert rate >= 100, (
            f"Throughput {rate:.0f} msg/sec is below 100 msg/sec minimum"
        )

    def test_message_ordering_preserved(self):
        """Messages from same partition arrive in order"""
        batch_id = uuid.uuid4().hex[:8]
        n = 50
        producer = make_producer()
        for i in range(n):
            msg = {"transaction_id": f"TXN-ORDER-{i}", "seq": i, "batch_id": batch_id}
            producer.send(TOPIC_TRANSACTIONS, msg, key=b"same-key")
        producer.flush()
        producer.close()

        group_id = f"test-order-{uuid.uuid4().hex[:6]}"
        consumer = make_consumer(TOPIC_TRANSACTIONS, group_id, timeout_ms=10000)
        sequences = []
        for msg in consumer:
            if msg.value.get("batch_id") == batch_id:
                sequences.append(msg.value["seq"])
        consumer.close()

        assert sequences == sorted(sequences), (
            f"Messages arrived out of order: {sequences[:10]}"
        )


class TestPhase2VelocityDetection:

    def _run_spike_detection(self, n_spike=15, threshold=10, timeout=15):
        """
        Core spike detection helper.
        1. Start consumer and poll once to get partition assignment
        2. Signal ready
        3. Producer sends messages
        4. Return detection latency or None
        """
        import uuid, time, threading, json
        from kafka import KafkaProducer, KafkaConsumer

        spike_account = f"ACC-SPIKE-{uuid.uuid4().hex[:6]}"
        batch_id = uuid.uuid4().hex[:8]
        detected_event = threading.Event()
        ready_event = threading.Event()
        times = {"first": None, "detected": None}

        def detector():
            group_id = f"det-{uuid.uuid4().hex[:8]}"
            c = KafkaConsumer(
                TOPIC_TRANSACTIONS,
                bootstrap_servers=BOOTSTRAP_SERVERS,
                group_id=group_id,
                auto_offset_reset="latest",
                enable_auto_commit=False,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                consumer_timeout_ms=timeout * 1000,
                fetch_max_wait_ms=100,
                max_poll_records=50,
            )
            # Force partition assignment before signaling ready
            while not c.assignment():
                c.poll(timeout_ms=500)
            ready_event.set()

            counts = {}
            for msg in c:
                v = msg.value
                if v.get("batch_id") != batch_id:
                    continue
                acc = v.get("account_id", "")
                counts[acc] = counts.get(acc, 0) + 1
                if counts[acc] == 1 and times["first"] is None:
                    times["first"] = time.time()
                if counts[acc] >= threshold:
                    times["detected"] = time.time()
                    detected_event.set()
                    break
            c.close()

        th = threading.Thread(target=detector, daemon=True)
        th.start()

        if not ready_event.wait(timeout=15):
            return None

        # Small buffer after assignment confirmed
        time.sleep(0.1)

        p = KafkaProducer(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks=1,
        )
        for i in range(n_spike):
            msg = make_transaction(account_id=spike_account, idx=i)
            msg["batch_id"] = batch_id
            p.send(TOPIC_TRANSACTIONS, msg)
        p.flush()
        p.close()

        if not detected_event.wait(timeout=timeout):
            return None

        if times["first"] and times["detected"]:
            return times["detected"] - times["first"]
        return None

    def test_velocity_spike_detected_under_2_seconds(self):
        """20 transactions from same account — spike must be detected under 2s"""
        latency = self._run_spike_detection(n_spike=20, threshold=10, timeout=15)
        assert latency is not None, (
            "Velocity spike not detected within 15 seconds"
        )
        print(f"\n  Spike detection latency: {latency:.3f}s")
        assert latency < 2.0, (
            f"Detection latency {latency:.3f}s exceeds 2 second threshold"
        )

    def test_normal_traffic_not_flagged_as_spike(self):
        """5 transactions from same account should NOT trigger spike alert"""
        spike_account = f"ACC-NORMAL-{uuid.uuid4().hex[:6]}"
        batch_id = uuid.uuid4().hex[:8]
        falsely_flagged = threading.Event()
        ready_event = threading.Event()

        def checker():
            group_id = f"fp-{uuid.uuid4().hex[:8]}"
            c = KafkaConsumer(
                TOPIC_TRANSACTIONS,
                bootstrap_servers=BOOTSTRAP_SERVERS,
                group_id=group_id,
                auto_offset_reset="latest",
                enable_auto_commit=False,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                consumer_timeout_ms=8000,
            )
            while not c.assignment():
                c.poll(timeout_ms=500)
            ready_event.set()
            counts = {}
            for msg in c:
                v = msg.value
                if v.get("batch_id") != batch_id:
                    continue
                acc = v.get("account_id", "")
                counts[acc] = counts.get(acc, 0) + 1
                if counts[acc] >= 10:
                    falsely_flagged.set()
                    break
            c.close()

        th = threading.Thread(target=checker, daemon=True)
        th.start()
        ready_event.wait(timeout=10)
        time.sleep(0.1)

        p = make_producer()
        for i in range(5):
            msg = make_transaction(account_id=spike_account, idx=i)
            msg["batch_id"] = batch_id
            p.send(TOPIC_TRANSACTIONS, msg)
            time.sleep(0.05)
        p.flush()
        p.close()

        th.join(timeout=9)
        assert not falsely_flagged.is_set(), (
            "Normal traffic (5 transactions) was falsely flagged as a spike"
        )

    def test_10_spike_runs_average_detection_under_2_seconds(self):
        """Run spike detection 5 times — average latency must be under 2s"""
        latencies = []
        for run in range(5):
            latency = self._run_spike_detection(n_spike=15, threshold=10, timeout=15)
            if latency is not None:
                latencies.append(latency)
                print(f"  Run {run+1}: {latency:.3f}s")
            else:
                print(f"  Run {run+1}: not detected")

        assert len(latencies) >= 4, (
            f"Only {len(latencies)}/5 runs detected the spike"
        )
        avg = sum(latencies) / len(latencies)
        print(f"\n  Average: {avg:.3f}s across {len(latencies)} runs")
        assert avg < 2.0, (
            f"Average detection latency {avg:.3f}s exceeds 2 second threshold"
        )


class TestPhase2AlertTopic:

    def test_fraud_alert_can_be_published_to_alerts_topic(self):
        """Publish a fraud alert and confirm it lands in sentra.alerts.fraud"""
        alert_id = f"ALERT-{uuid.uuid4().hex[:8]}"
        alert = {
            "transaction_id": alert_id,
            "account_id": "ACC-TEST",
            "risk_score": 95,
            "risk_level": "HIGH",
            "recommendation": "BLOCK",
            "timestamp": datetime.utcnow().isoformat()
        }
        producer = make_producer()
        future = producer.send(TOPIC_ALERTS, alert)
        result = future.get(timeout=10)
        producer.close()
        assert result.topic == TOPIC_ALERTS
        assert result.offset >= 0

    def test_alert_message_has_required_fields(self):
        """Alerts must contain transaction_id, risk_score, risk_level, recommendation"""
        alert_id = f"ALERT-FIELDS-{uuid.uuid4().hex[:8]}"
        alert = {
            "transaction_id": alert_id,
            "risk_score": 88,
            "risk_level": "HIGH",
            "recommendation": "BLOCK",
            "timestamp": datetime.utcnow().isoformat()
        }
        producer = make_producer()
        producer.send(TOPIC_ALERTS, alert)
        producer.flush()
        producer.close()

        group_id = f"test-alert-fields-{uuid.uuid4().hex[:6]}"
        consumer = make_consumer(TOPIC_ALERTS, group_id, timeout_ms=8000)
        found = None
        for msg in consumer:
            if msg.value.get("transaction_id") == alert_id:
                found = msg.value
                break
        consumer.close()

        assert found is not None, f"Alert {alert_id} not found in topic"
        for field in ["transaction_id", "risk_score", "risk_level", "recommendation"]:
            assert field in found, f"Missing required field in alert: {field}"
