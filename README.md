# SKOR Shield - Phase 1: Core Scoring Engine

The foundation of the fraud detection system. This phase validates that the ML scoring engine works correctly with synthetic data.

## What This Phase Does

- ✅ Trains XGBoost model on synthetic fraud data
- ✅ Exposes FastAPI endpoint for transaction scoring
- ✅ Stores scores in PostgreSQL
- ✅ Returns risk scores in <200ms
- ✅ Includes comprehensive unit tests

## Architecture

```
API Request → Validation → Feature Engineering → XGBoost Model → Risk Score → Database
```

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Docker (optional, for PostgreSQL)

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Setup PostgreSQL (Docker)

```bash
docker-compose up -d
```

This starts PostgreSQL on `localhost:5432` with:
- Database: `skor_shield`
- User: `skor_user`
- Password: `skor_password`

### Initialize Database

```bash
python data/schema.py
```

### Generate Synthetic Data

```bash
python data/synthetic_data.py
```

This creates 10,000 synthetic transactions (50% legitimate, 50% fraudulent).

### Train Model

```bash
python models/train.py
```

This trains the XGBoost model and saves it to `models/xgboost_model.pkl`.

### Start API Server

```bash
python api/main.py
```

Server runs on `http://localhost:8000`

## API Endpoints

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
  "timestamp": "2024-01-15T10:30:00Z"
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

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=api --cov=models

# Run specific test
pytest tests/test_scoring.py::test_score_returns_0_to_100
```

## Project Structure

```
phase-1-scoring/
├── api/
│   ├── main.py              # FastAPI app
│   ├── routes.py            # API endpoints
│   ├── config.py            # Configuration
│   └── middleware.py        # Auth, logging, etc
├── models/
│   ├── xgboost_model.pkl    # Trained model (generated)
│   ├── train.py             # Training script
│   └── features.py          # Feature engineering
├── data/
│   ├── schema.sql           # Database schema
│   ├── schema.py            # SQLAlchemy models
│   ├── synthetic_data.py    # Generate fake data
│   └── transactions.csv     # Sample data (generated)
├── tests/
│   ├── test_scoring.py      # Scoring tests
│   ├── test_api.py          # API endpoint tests
│   └── test_model.py        # Model tests
├── docker-compose.yml       # PostgreSQL setup
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Success Criteria

- ✅ Model accuracy >85% on test set
- ✅ API response time <200ms
- ✅ All tests passing
- ✅ Database stores scores correctly
- ✅ Risk scores between 0-100

## Next Steps

Once Phase 1 is complete and tested:
1. Move to Phase 2: Data Pipeline (Kafka + Flink)
2. Add real-time transaction streaming
3. Implement velocity-based detection

## Troubleshooting

### PostgreSQL Connection Error

```
Error: could not connect to server: Connection refused
```

**Solution:** Make sure PostgreSQL is running:
```bash
docker-compose up -d
```

### Model Not Found

```
FileNotFoundError: models/xgboost_model.pkl
```

**Solution:** Train the model first:
```bash
python models/train.py
```

### Port Already in Use

```
Address already in use
```

**Solution:** Change port in `api/config.py` or kill the process using port 8000.

## Performance Metrics

Target metrics for Phase 1:

| Metric | Target | Current |
|--------|--------|---------|
| Model Accuracy | >85% | - |
| API Response Time | <200ms | - |
| Database Query Time | <50ms | - |
| Test Coverage | >90% | - |

## Support

For issues or questions:
- Email: meshacknjorogeg@gmail.com
- Phone: +254 798 779 172
