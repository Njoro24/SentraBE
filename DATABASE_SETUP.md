# Database & Kafka Setup Guide

## Quick Start - Start Everything

```bash
docker-compose up -d
```

This starts:
- PostgreSQL (port 5433)
- Zookeeper (port 2181)
- Kafka (port 9092)

## Individual Service Startup

### Start PostgreSQL Only

```bash
docker-compose up -d postgres
```

**Connection Details:**
- Host: localhost
- Port: 5433
- User: postgres
- Password: changeme (from .env)
- Database: sentra_db

### Start Kafka & Zookeeper

```bash
docker-compose up -d zookeeper kafka
```

**Kafka Details:**
- Bootstrap Server: localhost:9092
- Zookeeper: localhost:2181

## Initialize Database Tables

After PostgreSQL is running, initialize the schema:

```bash
python SentraBE/data/schema.py
```

Or from Python:

```python
from data.schema import init_db
init_db()
```

## Database Tables

### Core Tables

**clients** - Client institutions
- id, institution_name, email, password_hash, subscription_tier, api_key, is_active, created_at

**transactions** - Transaction records
- id, client_id, transaction_id, amount, device_id, location, timestamp

**fraud_scores** - Fraud detection results
- id, client_id, transaction_id, risk_score, risk_level, velocity_signal, amount_anomaly_signal, device_new_signal, location_change_signal, recommendation, processing_time_ms

**model_metadata** - ML model info
- id, model_version, accuracy, precision, recall, f1_score, training_samples

### Security Tables

**sessions** - User sessions
- id, client_id, token, expires_at

**otp_records** - One-time passwords
- id, client_id, otp_code, otp_type, delivery_method, is_verified, expires_at

**password_history** - Password audit trail
- id, client_id, password_hash, created_at

**trusted_devices** - Trusted device registry
- id, client_id, device_fingerprint, device_name, trusted_until

### Analytics Tables

**alert_feedback** - Fraud alert feedback
- id, client_id, alert_id, transaction_id, marked_status, analyst_notes, original_risk_level, analyst_recommendation

**subscriptions** - Subscription tiers
- id, name, monthly_price, max_transactions, features

## Kafka Topics

Auto-created topics (if enabled):

- `fraud-alerts` - High-risk transaction alerts
- `transactions` - All transaction events
- `velocity-spikes` - Rapid transaction detection

## Environment Variables

Create `.env` in SentraBE:

```bash
# Database
DATABASE_URL=postgresql://postgres:changeme@localhost:5433/sentra_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=changeme
POSTGRES_DB=sentra_db

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_FRAUD_ALERTS=fraud-alerts
KAFKA_TOPIC_TRANSACTIONS=transactions
KAFKA_CONSUMER_GROUP=sentra-fraud-detection

# JWT
JWT_SECRET_KEY=your-secret-key-change-in-production

# Encryption
ENCRYPTION_KEY=base64-encoded-32-byte-key
```

## Verify Services

### Check PostgreSQL

```bash
docker exec sentra-postgres pg_isready -U postgres
```

### Check Kafka

```bash
docker exec sentra-kafka kafka-broker-api-versions.sh --bootstrap-server localhost:9092
```

### Check Zookeeper

```bash
docker exec sentra-zookeeper echo ruok | nc localhost 2181
```

## Stop Services

```bash
# Stop all
docker-compose down

# Stop specific service
docker-compose down postgres
docker-compose down kafka zookeeper

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

## View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f postgres
docker-compose logs -f kafka
docker-compose logs -f zookeeper
```

## Database Backup

```bash
# Backup
docker exec sentra-postgres pg_dump -U postgres sentra_db > backup.sql

# Restore
docker exec -i sentra-postgres psql -U postgres sentra_db < backup.sql
```

## Troubleshooting

### PostgreSQL won't start

```bash
# Check if port 5433 is in use
lsof -i :5433

# Remove old container
docker rm sentra-postgres
docker-compose up -d postgres
```

### Kafka connection refused

```bash
# Ensure Zookeeper is healthy first
docker-compose logs zookeeper

# Restart Kafka
docker-compose restart kafka
```

### Database connection error

```bash
# Verify credentials in .env
# Check PostgreSQL is running
docker ps | grep postgres

# Test connection
psql -h localhost -p 5433 -U postgres -d sentra_db
```

## Full Stack Startup Sequence

1. Start Docker services:
   ```bash
   docker-compose up -d
   ```

2. Wait for services to be healthy (30 seconds):
   ```bash
   docker-compose ps
   ```

3. Initialize database:
   ```bash
   python SentraBE/data/schema.py
   ```

4. Start backend:
   ```bash
   python3 -m uvicorn api.main:app --reload --port 8000
   ```

5. Start frontend (in SentraFE):
   ```bash
   npm run dev
   ```

6. Access:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
