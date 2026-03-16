"""
Kafka topic initialization script.
Run once on startup or after wiping Docker volumes.
Safe to run multiple times — skips existing topics.
"""
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
import os, sys, time
from dotenv import load_dotenv
load_dotenv()

KAFKA_SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
KAFKA_SASL_MECHANISM    = os.getenv("KAFKA_SASL_MECHANISM", "PLAIN")
KAFKA_SASL_USERNAME     = os.getenv("KAFKA_SASL_USERNAME", "")
KAFKA_SASL_PASSWORD     = os.getenv("KAFKA_SASL_PASSWORD", "")

def kafka_sasl_config():
    if KAFKA_SECURITY_PROTOCOL == "SASL_PLAINTEXT":
        return {
            "security_protocol": KAFKA_SECURITY_PROTOCOL,
            "sasl_mechanism":    KAFKA_SASL_MECHANISM,
            "sasl_plain_username": KAFKA_SASL_USERNAME,
            "sasl_plain_password": KAFKA_SASL_PASSWORD,
        }
    return {}


BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(",")
TOPICS = [
    NewTopic("sentra.transactions.raw", num_partitions=3, replication_factor=1),
    NewTopic("sentra.alerts.fraud",     num_partitions=1, replication_factor=1),
    NewTopic("sentra.scores.output",    num_partitions=1, replication_factor=1),
    NewTopic("sentra.dlq",              num_partitions=1, replication_factor=1),
]

def init_topics(retries=5):
    for attempt in range(retries):
        try:
            admin = KafkaAdminClient(bootstrap_servers=BOOTSTRAP if isinstance(BOOTSTRAP, list) else [BOOTSTRAP])
            existing = admin.list_topics()
            to_create = [t for t in TOPICS if t.name not in existing]
            if not to_create:
                print("All topics already exist")
                admin.close()
                return
            admin.create_topics(to_create)
            for t in to_create:
                print(f"Created topic: {t.name}")
            admin.close()
            return
        except TopicAlreadyExistsError:
            print("Topics already exist")
            return
        except Exception as e:
            print(f"Attempt {attempt+1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(3)
    print("Failed to initialize topics after all retries")
    sys.exit(1)

if __name__ == "__main__":
    init_topics()
    print("Kafka topics initialized successfully")
