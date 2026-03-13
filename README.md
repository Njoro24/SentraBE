# Sentra - Real-Time Fraud Detection API

> Enterprise-grade fraud detection platform with machine learning, real-time streaming, and advanced security

[![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Latest-blue?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Quick Start](#quick-start)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)

---

## Overview

Sentra is a comprehensive fraud detection system that combines:
- **XGBoost Machine Learning** for real-time fraud scoring
- **Apache Kafka** for event streaming and real-time alerts
- **Neo4j Graph Database** for fraud ring detection
- **JWT Authentication** for secure API access
- **AES-256 Encryption** for sensitive data protection
- **Immutable Audit Logs** for compliance and forensics

### Key Capabilities
- Real-time transaction scoring (< 100ms)
- Fraud ring detection using graph algorithms
- Continuous model learning and improvement
- Multi-channel integration (T24, REST API)
- Enterprise-grade security and compliance
- WebSocket live alerts and dashboards  

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLIENT APPLICATIONS                             │
│  (Web Dashboard, Mobile Apps, Banking Systems)                          │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   API Gateway   │
                    │  (FastAPI)      │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐      ┌────────▼────────┐    ┌────▼────┐
   │ Auth    │      │ Scoring Engine  │    │ T24     │
   │ Service │      │ (XGBoost)       │    │ Adapter │
   └────┬────┘      └────────┬────────┘    └────┬────┘
        │                    │                   │
        │            ┌───────▼────────┐         │
        │            │  Kafka Stream  │         │
        │            │  Processing    │         │
        │            └───────┬────────┘         │
        │                    │                   │
   ┌────▼────────────────────▼───────────────────▼────┐
   │         PostgreSQL Database                      │
   │  (Transactions, Scores, Audit Logs)             │
   └──────────────────────────────────────────────────┘
        │
   ┌────▼──────────────┐
   │  Neo4j Graph DB   │
   │  (Fraud Rings)    │
   └───────────────────┘
```

### Request Flow Diagram

```
┌──────────────┐
│   Client     │
│  (Token)     │
└──────┬───────┘
       │
       │ POST /score
       │ Authorization: Bearer <JWT>
       │
       ▼
┌──────────────────────────────────────┐
│  JWT Middleware                      │
│  • Validate signature                │
│  • Check expiration                  │
│  • Extract claims                    │
└──────┬───────────────────────────────┘
       │
       │ ✅ Valid Token
       │
       ▼
┌──────────────────────────────────────┐
│  Score Transaction Endpoint          │
│  • Validate request                  │
│  • Check subscription limits         │
│  • Audit log: SCORE_REQUEST          │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  Feature Engineering                 │
│  • Extract transaction features      │
│  • Normalize values                  │
│  • Scale features                    │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  XGBoost Model                       │
│  • Predict fraud probability         │
│  • Generate risk score (0-100)       │
│  • Determine recommendation          │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  Encrypt Sensitive Fields            │
│  • account_id → encrypted            │
│  • card_number → encrypted           │
│  • device_id → encrypted             │
│  • ip_address → encrypted            │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  Store & Stream                      │
│  • Save to PostgreSQL                │
│  • Audit log: TRANSACTION_STORED     │
│  • Stream to Kafka (if HIGH risk)    │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  Return Response                     │
│  {                                   │
│    "risk_score": 85,                 │
│    "risk_level": "HIGH",             │
│    "recommendation": "BLOCK",        │
│    "signals": {...}                  │
│  }                                   │
└──────────────────────────────────────┘
```

### Data Flow: T24 Integration

```
┌─────────────────┐
│  T24 Banking    │
│  System         │
└────────┬────────┘
         │
         │ T24 Format Transaction
         │
         ▼
┌─────────────────────────────────────┐
│  T24 Adapter                        │
│  • Validate required fields         │
│  • Normalize channels & categories  │
│  • Convert amounts to KES           │
│  • Parse timestamps                 │
└────────┬────────────────────────────┘
         │
         │ Internal Format
         │
         ▼
┌─────────────────────────────────────┐
│  Field Encryption                   │
│  • Encrypt account_id               │
│  • Encrypt card_number              │
│  • Encrypt device_id                │
│  • Encrypt ip_address               │
└────────┬────────────────────────────┘
         │
         │ Encrypted Transaction
         │
         ▼
┌─────────────────────────────────────┐
│  Fraud Scoring                      │
│  • Feature engineering              │
│  • Model prediction                 │
│  • Risk assessment                  │
└────────┬────────────────────────────┘
         │
         │ Scored Transaction
         │
         ▼
┌─────────────────────────────────────┐
│  Audit Log                          │
│  • Log event: TRANSACTION_STORED    │
│  • Chain verification               │
│  • Tamper detection                 │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Database Storage                   │
│  • PostgreSQL: Transaction record   │
│  • SQLite: Audit log entry          │
│  • Neo4j: Fraud ring analysis       │
└─────────────────────────────────────┘
```

---

## Features

### Machine Learning
- **XGBoost Model**: Trained on credit card fraud dataset
- **Real-time Scoring**: < 100ms per transaction
- **Continuous Learning**: Model improves from feedback
- **Feature Engineering**: 28 PCA-transformed features

### Real-Time Streaming
- **Apache Kafka**: Event streaming pipeline
- **Flink Processing**: Stream analytics
- **Velocity Detection**: Identifies rapid-fire transactions
- **Live Alerts**: WebSocket push notifications

### Graph Analysis
- **Neo4j Database**: Fraud ring detection
- **Network Analysis**: Identify connected fraudsters
- **Relationship Mapping**: Account linkages
- **Pattern Recognition**: Suspicious behavior patterns

### Security (Phase 6)
- **JWT Authentication**: HS256 token-based auth
- **AES-256-GCM Encryption**: Sensitive field protection
- **Immutable Audit Logs**: SHA-256 chain verification
- **Role-Based Access**: Admin, Analyst, Client roles

### Analytics & Reporting
- **Real-time Dashboard**: Live fraud metrics
- **Historical Analysis**: Trend identification
- **Client Analytics**: Per-client fraud patterns
- **Feedback System**: Model improvement loop

### Banking Integration
- **T24 Adapter**: Temenos T24 compatibility
- **Mock API**: Testing without live system
- **Batch Processing**: High-volume transaction handling
- **Field Mapping**: Automatic format conversion

---

## Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- Apache Kafka 2.8+
- Neo4j 4.0+
- Docker & Docker Compose (optional)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/sentra.git
cd sentra/SentraBE
```

2. **Create virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Initialize database**
```bash
python -c "from data.schema import init_db; init_db()"
```

6. **Start the API**
```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Compose (Recommended)

```bash
docker-compose up -d
```

This starts:
- FastAPI server (port 8000)
- PostgreSQL (port 5433)
- Kafka (port 9092)
- Neo4j (port 7687)

---

## API Documentation

### Authentication

All endpoints (except `/health` and `/docs`) require JWT authentication.

**Get Token:**
```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your-password"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Score Transaction

**Endpoint:** `POST /score`

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request:**
```json
{
  "transaction_id": "TXN-2024-001",
  "amount": 5000.0,
  "merchant_category": "RETAIL",
  "location": "Nairobi, KE",
  "device_id": "device-123",
  "country": "KE",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Response:**
```json
{
  "transaction_id": "TXN-2024-001",
  "risk_score": 42,
  "risk_level": "MEDIUM",
  "recommendation": "FLAG",
  "signals": {
    "velocity": 0.3,
    "amount_anomaly": 0.5,
    "device_new": 0.1,
    "location_change": 0.2
  },
  "processing_time_ms": 45.2
}
```

### Get Fraud Rings

**Endpoint:** `GET /fraud-rings`

**Response:**
```json
{
  "rings": [
    {
      "ring_id": 1,
      "size": 5,
      "total_fraud_amount": 50000.0,
      "members": ["ACC-001", "ACC-002", "ACC-003"],
      "confidence": 0.95
    }
  ]
}
```

### T24 Integration

**Endpoint:** `GET /integrate/t24/transactions?limit=10`

**Response:**
```json
{
  "status": "success",
  "count": 10,
  "transactions": [
    {
      "transaction_id": "T24-001",
      "amount": 10000.0,
      "fraud_score": 25,
      "risk_level": "LOW",
      "recommendation": "APPROVE"
    }
  ]
}
```

### Interactive API Docs

Visit `http://localhost:8000/docs` for Swagger UI documentation.

---

## Project Structure

```
SentraBE/
├── api/                          # FastAPI endpoints
│   ├── main.py                   # Main application
│   ├── auth.py                   # Authentication logic
│   ├── client_auth.py            # Client authentication
│   ├── admin.py                  # Admin endpoints
│   ├── transactions.py           # Transaction scoring
│   ├── t24_integration.py        # T24 adapter endpoints
│   ├── t24_mock.py               # Mock T24 API
│   ├── feedback.py               # Feedback system
│   ├── learning.py               # Continuous learning
│   ├── fraud_rules.py            # Custom fraud rules
│   ├── subscriptions.py          # Subscription management
│   └── config.py                 # Configuration
│
├── security/                     # Phase 6 Security
│   ├── jwt_handler.py            # JWT token management
│   ├── jwt_middleware.py         # JWT validation middleware
│   ├── encryption.py             # AES-256-GCM encryption
│   ├── field_encryptor.py        # Field-level encryption
│   ├── audit_log.py              # Immutable audit logs
│   └── generate_test_tokens.py   # Test token generator
│
├── services/                     # Business logic
│   ├── auth_service.py           # Authentication service
│   ├── admin_service.py          # Admin operations
│   ├── otp_service.py            # OTP generation
│   ├── t24_adapter.py            # T24 transformation
│   ├── graph_fraud_detector.py   # Graph analysis
│   └── continuous_learning.py    # Model improvement
│
├── models/                       # ML models
│   ├── train.py                  # Model training
│   ├── features.py               # Feature definitions
│   ├── feature_engineer.py       # Feature engineering
│   ├── xgboost_model.pkl         # Trained model
│   └── feature_scaler.pkl        # Feature scaler
│
├── data/                         # Data layer
│   ├── schema.py                 # Database schema
│   ├── admin_schema.py           # Admin schema
│   ├── synthetic_data.py         # Test data generation
│   └── creditcard.csv            # Training dataset
│
├── streaming/                    # Kafka streaming
│   ├── producer.js               # Kafka producer
│   ├── consumer.js               # Kafka consumer
│   ├── velocity-detector.js      # Velocity detection
│   └── websocket-server.js       # WebSocket server
│
├── tests/                        # Test suite
│   ├── test_jwt.py               # JWT tests
│   ├── test_encryption.py        # Encryption tests
│   ├── test_audit_log.py         # Audit log tests
│   ├── test_phase6_integration.py # Integration tests
│   └── phase5_integration_test.py # Phase 5 tests
│
├── requirements.txt              # Python dependencies
├── docker-compose.yml            # Docker configuration
├── .env.example                  # Environment template
└── README.md                     # This file
```

---

## Configuration

### Environment Variables

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=False
ENVIRONMENT=production

# Database
DATABASE_URL=postgresql://postgres:admin123@localhost:5433/sentra_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=admin123
POSTGRES_DB=sentra_db

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_FRAUD_ALERTS=fraud-alerts
KAFKA_TOPIC_TRANSACTIONS=transactions
KAFKA_CONSUMER_GROUP=sentra-fraud-detection

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-neo4j-password

# Security (Phase 6)
JWT_SECRET_KEY=your-secret-key-change-in-production
ENCRYPTION_KEY=base64-encoded-32-byte-key

# T24 Integration
T24_API_BASE_URL=http://localhost:8000/t24
T24_API_TIMEOUT=10

# Admin Setup
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=secure-password

# OTP Configuration
OTP_EXPIRATION_MINUTES=5

# Email (Resend)
RESEND_API_KEY=your-resend-api-key

# SMS (Africa's Talking)
AFRICASTALKING_USERNAME=your-username
AFRICASTALKING_API_KEY=your-api-key
AFRICASTALKING_SENDER_ID=SentraAlert
```

---

## Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test Suite

```bash
# JWT Authentication Tests
pytest tests/test_jwt.py -v

# Encryption Tests
pytest tests/test_encryption.py -v

# Audit Log Tests
pytest tests/test_audit_log.py -v

# Integration Tests
pytest tests/test_phase6_integration.py -v
```

### Test Coverage

```bash
pytest tests/ --cov=api --cov=security --cov=services --cov-report=html
```

### Generate Test Tokens

```bash
python security/generate_test_tokens.py
```

---

## Development

### Code Style

We follow PEP 8 with Black formatter:

```bash
black api/ security/ services/ models/ data/
```

### Type Checking

```bash
mypy api/ security/ services/
```

### Linting

```bash
flake8 api/ security/ services/ --max-line-length=100
```

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

---

## Deployment

### Production Checklist

- [ ] Update `JWT_SECRET_KEY` in production
- [ ] Rotate `ENCRYPTION_KEY` regularly
- [ ] Enable HTTPS/TLS
- [ ] Configure firewall rules
- [ ] Set up monitoring and alerting
- [ ] Enable audit log archival
- [ ] Configure database backups
- [ ] Set up log aggregation

### Docker Deployment

```bash
docker build -t sentra-api:latest .
docker run -d \
  --name sentra-api \
  -p 8000:8000 \
  --env-file .env \
  sentra-api:latest
```

### Kubernetes Deployment

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/configmap.yaml
```

---

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

### Metrics Endpoint

```bash
curl http://localhost:8000/metrics
```

### Logs

```bash
# View application logs
docker logs sentra-api

# View audit logs
sqlite3 audit_log.db "SELECT * FROM audit_log LIMIT 10;"
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Support

- **Documentation**: [Full Docs](./docs)
- **Issues**: [GitHub Issues](https://github.com/yourusername/sentra/issues)
- **Email**: support@sentra.io
- **Slack**: [Join Community](https://sentra-community.slack.com)

---

## Acknowledgments

- XGBoost team for the amazing ML library
- Apache Kafka for streaming infrastructure
- Neo4j for graph database capabilities
- FastAPI for the modern web framework

---

**Made by the Sentra Team**

Last Updated: March 2024 | Version: 1.0.0
