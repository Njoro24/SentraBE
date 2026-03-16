"""
Velocity Spike Detector — Production Service
Consumes sentra.transactions.raw and emits alerts to sentra.alerts.fraud
when an account exceeds SPIKE_THRESHOLD transactions within WINDOW_SECONDS.

Run: python3 streaming/velocity_detector.py
"""
import json
import os
import time
import logging
from collections import defaultdict
from datetime import datetime
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BOOTSTRAP        = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INPUT_TOPIC      = "sentra.transactions.raw"
ALERT_TOPIC      = "sentra.alerts.fraud"
DLQ_TOPIC        = "sentra.dlq"
CONSUMER_GROUP   = "sentra-velocity-detector"
SPIKE_THRESHOLD  = 10       # transactions
WINDOW_SECONDS   = 60       # sliding window
CHECK_INTERVAL   = 1        # seconds between window purges


class VelocityDetector:
    def __init__(self):
        self.consumer = KafkaConsumer(
            INPUT_TOPIC,
            bootstrap_servers=BOOTSTRAP,
            group_id=CONSUMER_GROUP,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            consumer_timeout_ms=-1,      # run forever
            fetch_max_wait_ms=100,
            max_poll_records=100,
        )
        self.producer = KafkaProducer(
            bootstrap_servers=BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            retries=3,
        )
        # account_id -> list of timestamps within window
        self.window: dict = defaultdict(list)
        self.alerted: set = set()   # accounts already alerted in this window
        self.last_purge = time.time()

    def purge_old_entries(self):
        """Remove timestamps outside the sliding window"""
        cutoff = time.time() - WINDOW_SECONDS
        for acc in list(self.window.keys()):
            self.window[acc] = [t for t in self.window[acc] if t > cutoff]
            if not self.window[acc]:
                del self.window[acc]
                self.alerted.discard(acc)

    def emit_alert(self, account_id: str, count: int, sample_msg: dict):
        alert = {
            "alert_type":     "VELOCITY_SPIKE",
            "account_id":     account_id,
            "transaction_count": count,
            "window_seconds": WINDOW_SECONDS,
            "threshold":      SPIKE_THRESHOLD,
            "risk_level":     "HIGH",
            "recommendation": "BLOCK",
            "risk_score":     95,
            "transaction_id": sample_msg.get("transaction_id", ""),
            "timestamp":      datetime.utcnow().isoformat(),
        }
        try:
            self.producer.send(ALERT_TOPIC, alert)
            self.producer.flush()
            log.warning(f"VELOCITY SPIKE: account={account_id} count={count} in {WINDOW_SECONDS}s")
        except KafkaError as e:
            log.error(f"Failed to emit alert: {e}")
            try:
                self.producer.send(DLQ_TOPIC, {"error": str(e), "alert": alert})
            except Exception:
                pass

    def run(self):
        log.info(f"Velocity detector started — threshold={SPIKE_THRESHOLD} in {WINDOW_SECONDS}s")
        for msg in self.consumer:
            try:
                data = msg.value
                account_id = data.get("account_id", data.get("client_id", "unknown"))
                now = time.time()

                self.window[account_id].append(now)

                count = len(self.window[account_id])
                if count >= SPIKE_THRESHOLD and account_id not in self.alerted:
                    self.emit_alert(account_id, count, data)
                    self.alerted.add(account_id)

                # Purge old entries periodically
                if now - self.last_purge > CHECK_INTERVAL:
                    self.purge_old_entries()
                    self.last_purge = now

            except Exception as e:
                log.error(f"Error processing message: {e}")
                try:
                    self.producer.send(DLQ_TOPIC, {"error": str(e), "raw": str(msg.value)})
                except Exception:
                    pass


if __name__ == "__main__":
    detector = VelocityDetector()
    detector.run()
