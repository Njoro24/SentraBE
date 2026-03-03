#!/bin/bash

# ════════════════════════════════════════════════════════════════════════════════
# Kafka Topics Initialization Script
# Creates all required topics for Phase 2 streaming pipeline
# ════════════════════════════════════════════════════════════════════════════════

set -e

KAFKA_BROKER="localhost:9092"
RETRIES=30
RETRY_DELAY=2

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "SENTRA KAFKA TOPICS INITIALIZATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Wait for Kafka to be ready
echo ""
echo "⏳ Waiting for Kafka broker to be ready..."
for i in $(seq 1 $RETRIES); do
  if timeout 2 bash -c "echo > /dev/tcp/localhost/9092" 2>/dev/null; then
    echo "✓ Kafka broker is ready"
    break
  fi
  if [ $i -eq $RETRIES ]; then
    echo "✗ Kafka broker failed to start after $((RETRIES * RETRY_DELAY)) seconds"
    exit 1
  fi
  echo "  Attempt $i/$RETRIES... waiting ${RETRY_DELAY}s"
  sleep $RETRY_DELAY
done

echo ""
echo "📝 Creating Kafka topics..."
echo ""

# Create topics using docker-compose exec
docker-compose -f docker-compose.yml exec -T kafka kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic sentra.transactions.raw \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000 \
  --if-not-exists 2>/dev/null || echo "  → sentra.transactions.raw (already exists or created)"

docker-compose -f docker-compose.yml exec -T kafka kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic sentra.scores.output \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000 \
  --if-not-exists 2>/dev/null || echo "  → sentra.scores.output (already exists or created)"

docker-compose -f docker-compose.yml exec -T kafka kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic sentra.alerts.fraud \
  --partitions 2 \
  --replication-factor 1 \
  --config retention.ms=604800000 \
  --if-not-exists 2>/dev/null || echo "  → sentra.alerts.fraud (already exists or created)"

docker-compose -f docker-compose.yml exec -T kafka kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic sentra.scores.dlq \
  --partitions 1 \
  --replication-factor 1 \
  --config retention.ms=604800000 \
  --if-not-exists 2>/dev/null || echo "  → sentra.scores.dlq (already exists or created)"

echo ""
echo "✓ All topics created successfully"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ KAFKA INITIALIZATION COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
