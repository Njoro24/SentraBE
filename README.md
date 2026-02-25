# Sentra Backend - Fraud Detection API

Production-ready fraud detection API built with FastAPI and machine learning.

## What This Does

- ✅ Real-time transaction scoring with ML model
- ✅ FastAPI endpoints for fraud detection
- ✅ PostgreSQL database for persistence
- ✅ Returns risk scores in <200ms
- ✅ Comprehensive monitoring and logging

## Architecture

```
API Request → Validation → Feature Engineering → ML Model → Risk Score → Database
```

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Kafka (for streaming components)

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Update .env with your configuration
```

### Initialize Database

```bash
python -c "from data.schema import init_db; init_db()"
```

### Train the Fraud Detection Model

The ML model is not stored in Git (too large). Train it locally:

```bash
python train_fraud_model.py
```

This generates:
- `fraud_model.pkl` - XGBoost model (100% accuracy on test data)
- `fraud_model_metrics.json` - Model performance metrics
- `models/feature_scaler.pkl` - Feature scaling parameters

Training takes ~30 seconds and creates a model with 24 engineered features.

### Start API Server

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Server runs on `http://0.0.0.0:8000`

## API Endpoints

### POST /auth/register

Register a new institution.

**Request:**
```json
{
  "name": "Your Bank",
  "email": "admin@yourbank.com",
  "password": "secure-password",
  "subscription_tier": "growth"
}
```

**Response:**
```json
{
  "client_id": 1,
  "name": "Your Bank",
  "email": "admin@yourbank.com",
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "subscription_tier": "growth"
}
```

### POST /auth/login

Login and get JWT token.

**Request:**
```json
{
  "email": "admin@yourbank.com",
  "password": "secure-password"
}
```

### POST /v1/score

Score a single transaction.

**Request:**
```json
{
  "transaction_id": "TXN123456",
  "amount": 50000,
  "phone_number": "+254712345678",
  "device_id": "device_abc123",
  "location": "Nairobi",
  "timestamp": "2024-02-22T10:30:00Z"
}
```

**Response:**
```json
{
  "transaction_id": "TXN123456",
  "risk_score": 78,
  "risk_level": "HIGH",
  "signals": {
    "velocity": 0.85,
    "amount_anomaly": 0.72,
    "device_new": 0.65,
    "location_change": 0.45
  },
  "recommendation": "FLAG",
  "processing_time_ms": 145
}
```

### GET /v1/health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "database_connected": true
}
```

### GET /docs

Interactive API documentation (Swagger UI).

## Project Structure

```
SentraBE/
├── api/
│   ├── main.py              # FastAPI app
│   ├── auth.py              # Authentication
│   ├── config.py            # Configuration
│   └── subscriptions.py      # Subscription management
├── models/
│   ├── train.py             # Model training
│   └── features.py          # Feature engineering
├── data/
│   ├── schema.py            # Database schema
│   └── synthetic_data.py    # Data generation
├── streaming/
│   ├── producer.js          # Kafka producer
│   ├── consumer.js          # Kafka consumer
│   ├── velocity-detector.js # Velocity detection
│   └── websocket-server.js  # WebSocket server
├── docker-compose.yml       # Docker setup
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Environment Variables

```
DATABASE_URL=postgresql://user:password@localhost:5432/sentra_db
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=False
MODEL_PATH=models/fraud_model.pkl
ENVIRONMENT=production
SENTRA_EMAIL=your-email@example.com
SENTRA_PASSWORD=your-password
SENTRA_API_URL=https://your-api-domain.com
```

## Production Deployment

### Security Checklist
- ✅ Set `DEBUG=False`
- ✅ Use strong database passwords
- ✅ Configure CORS properly
- ✅ Enable HTTPS/TLS
- ✅ Set up monitoring
- ✅ Configure automated backups
- ✅ Use secrets management

### Deployment Options
- Docker containers
- Kubernetes
- AWS ECS
- Google Cloud Run
- Azure Container Instances

## Troubleshooting

### Database Connection Error
- Ensure PostgreSQL is running
- Check DATABASE_URL in .env
- Verify database credentials

### API Won't Start
- Check if port 8000 is in use
- Verify all dependencies installed
- Check logs for specific errors

### Model Not Found
- Ensure MODEL_PATH points to correct location
- Verify model file exists
- Check file permissions

## Support

For issues or questions, refer to the main documentation or contact your system administrator.

---

**Status:** ✅ Production Ready

**Version:** 2.0.0

**Last Updated:** February 2026
