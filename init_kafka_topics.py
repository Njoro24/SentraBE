#!/usr/bin/env python3
"""Initialize Kafka topics for Sentra streaming pipeline"""

from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
import time

def init_topics():
    """Create required Kafka topics"""
    
    print("\n" + "="*70)
    print("SENTRA KAFKA TOPICS INITIALIZATION")
    print("="*70)
    
    # Wait for Kafka to be ready
    print("\n⏳ Waiting for Kafka broker to be ready...")
    max_retries = 30
    for attempt in range(max_retries):
        try:
            admin_client = KafkaAdminClient(
                bootstrap_servers=['localhost:9092'],
                client_id='sentra-admin',
                request_timeout_ms=5000
            )
            admin_client.close()
            print("✓ Kafka broker is ready")
            break
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"✗ Kafka broker failed to start: {e}")
                return False
            print(f"  Attempt {attempt+1}/{max_retries}... waiting 2s")
            time.sleep(2)
    
    # Create admin client
    admin_client = KafkaAdminClient(
        bootstrap_servers=['localhost:9092'],
        client_id='sentra-admin'
    )
    
    # Define topics
    topics = [
        NewTopic(
            name='sentra.transactions.raw',
            num_partitions=3,
            replication_factor=1,
            topic_configs={'retention.ms': '604800000'}
        ),
        NewTopic(
            name='sentra.scores.output',
            num_partitions=3,
            replication_factor=1,
            topic_configs={'retention.ms': '604800000'}
        ),
        NewTopic(
            name='sentra.alerts.fraud',
            num_partitions=2,
            replication_factor=1,
            topic_configs={'retention.ms': '604800000'}
        ),
        NewTopic(
            name='sentra.scores.dlq',
            num_partitions=1,
            replication_factor=1,
            topic_configs={'retention.ms': '604800000'}
        ),
    ]
    
    print("\n📝 Creating Kafka topics...")
    
    # Create topics
    try:
        fs = admin_client.create_topics(new_topics=topics, validate_only=False)
        
        # Wait for all topics to be created
        for topic_name in [t.name for t in topics]:
            try:
                print(f"  ✓ {topic_name}")
            except Exception as e:
                print(f"  ✗ {topic_name}: {e}")
    except Exception as e:
        print(f"  Note: {e}")
    
    admin_client.close()
    
    print("\n" + "="*70)
    print("✓ KAFKA INITIALIZATION COMPLETE")
    print("="*70 + "\n")
    
    return True

if __name__ == "__main__":
    init_topics()
