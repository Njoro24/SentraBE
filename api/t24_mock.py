"""
Mock T24 API - Simulates Temenos T24 banking system
Returns fake transactions in T24 format for testing
"""

from fastapi import APIRouter, Query
from datetime import datetime, timedelta
import random
import json

router = APIRouter(prefix="/t24", tags=["t24"])

# Mock T24 transaction data
MOCK_MERCHANTS = [
    "SAFARICOM AIRTIME",
    "EQUITY BANK ATM",
    "NAKUMATT SUPERMARKET",
    "SHELL PETROL STATION",
    "AIRBNB ACCOMMODATION",
    "AMAZON PURCHASE",
    "UBER RIDE",
    "MPESA TRANSFER",
    "WESTERN UNION",
    "BETTING SITE",
    "ONLINE CASINO",
    "CRYPTOCURRENCY EXCHANGE",
    "WIRE TRANSFER INTL",
    "HOSPITAL PAYMENT",
    "SCHOOL FEES",
    "INSURANCE PREMIUM"
]

MOCK_LOCATIONS = [
    "Nairobi",
    "Mombasa",
    "Kisumu",
    "Nakuru",
    "Eldoret",
    "London",
    "New York",
    "Singapore",
    "Dubai",
    "Hong Kong"
]

MOCK_CHANNELS = [
    "MOBILE_BANKING",
    "INTERNET_BANKING",
    "ATM",
    "POS",
    "BRANCH",
    "PHONE_BANKING"
]

MOCK_CURRENCIES = ["KES", "USD", "EUR", "GBP"]

def generate_mock_t24_transaction(transaction_id: str = None):
    """Generate a single mock T24 transaction"""
    if not transaction_id:
        transaction_id = f"T24{random.randint(100000, 999999)}"
    
    amount = random.choice([
        random.randint(1000, 10000),      # Small transactions
        random.randint(10000, 100000),    # Medium transactions
        random.randint(100000, 500000),   # Large transactions
        random.randint(500000, 2000000)   # Very large transactions
    ])
    
    timestamp = datetime.now() - timedelta(minutes=random.randint(0, 1440))
    
    return {
        # T24 Standard Fields
        "TRANSACTION_ID": transaction_id,
        "TRANSACTION_TYPE": random.choice(["DEBIT", "CREDIT"]),
        "AMOUNT": amount,
        "CURRENCY": random.choice(MOCK_CURRENCIES),
        "TIMESTAMP": timestamp.isoformat(),
        "POSTING_DATE": timestamp.strftime("%Y-%m-%d"),
        
        # Account Information
        "ACCOUNT_NUMBER": f"{random.randint(1000000000, 9999999999)}",
        "ACCOUNT_NAME": f"Customer_{random.randint(1000, 9999)}",
        "ACCOUNT_TYPE": random.choice(["SAVINGS", "CURRENT", "INVESTMENT"]),
        
        # Counterparty Information
        "COUNTERPARTY_ACCOUNT": f"{random.randint(1000000000, 9999999999)}",
        "COUNTERPARTY_NAME": f"Merchant_{random.randint(100, 999)}",
        "COUNTERPARTY_BANK": random.choice(["EQUITY", "KCB", "STANDARD", "BARCLAYS", "INTL_BANK"]),
        
        # Transaction Details
        "MERCHANT_NAME": random.choice(MOCK_MERCHANTS),
        "MERCHANT_CATEGORY": random.choice([
            "Retail",
            "Hospitality",
            "Transportation",
            "Healthcare",
            "Education",
            "Entertainment",
            "Gambling",
            "Cryptocurrency",
            "Money Transfer",
            "ATM Withdrawal"
        ]),
        "MERCHANT_LOCATION": random.choice(MOCK_LOCATIONS),
        
        # Channel & Device
        "CHANNEL": random.choice(MOCK_CHANNELS),
        "DEVICE_ID": f"DEV{random.randint(100000, 999999)}",
        "IP_ADDRESS": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
        
        # Risk Indicators
        "VELOCITY_FLAG": random.choice([True, False]),
        "GEOGRAPHIC_MISMATCH": random.choice([True, False]),
        "DEVICE_MISMATCH": random.choice([True, False]),
        
        # Status
        "STATUS": random.choice(["POSTED", "PENDING", "CLEARED"]),
        "REFERENCE": f"REF{random.randint(100000, 999999)}",
        
        # Additional T24 Fields
        "NARRATIVE": f"Transaction for {random.choice(MOCK_MERCHANTS)}",
        "VALUE_DATE": timestamp.strftime("%Y-%m-%d"),
        "SETTLEMENT_DATE": (timestamp + timedelta(days=1)).strftime("%Y-%m-%d"),
        "BATCH_ID": f"BATCH{random.randint(1000, 9999)}",
        "SEQUENCE_NUMBER": random.randint(1, 1000)
    }


@router.get("/transactions")
async def get_t24_transactions(
    limit: int = Query(10, ge=1, le=100),
    account_number: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None)
):
    """
    Get mock T24 transactions
    
    Args:
        limit: Number of transactions to return (1-100)
        account_number: Filter by account number (optional)
        start_date: Filter by start date YYYY-MM-DD (optional)
        end_date: Filter by end date YYYY-MM-DD (optional)
    
    Returns:
        List of T24-formatted transactions
    """
    transactions = []
    for i in range(limit):
        txn = generate_mock_t24_transaction(f"T24{i:06d}")
        transactions.append(txn)
    
    return {
        "status": "success",
        "count": len(transactions),
        "transactions": transactions,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/transactions/{transaction_id}")
async def get_t24_transaction(transaction_id: str):
    """Get a specific T24 transaction by ID"""
    txn = generate_mock_t24_transaction(transaction_id)
    
    return {
        "status": "success",
        "transaction": txn,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/transactions/batch")
async def get_t24_batch_transactions(batch_size: int = 50):
    """Get a batch of T24 transactions for bulk processing"""
    transactions = []
    for i in range(batch_size):
        txn = generate_mock_t24_transaction(f"T24BATCH{i:06d}")
        transactions.append(txn)
    
    return {
        "status": "success",
        "batch_id": f"BATCH{random.randint(10000, 99999)}",
        "count": len(transactions),
        "transactions": transactions,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/accounts/{account_number}/balance")
async def get_account_balance(account_number: str):
    """Get mock account balance"""
    return {
        "status": "success",
        "account_number": account_number,
        "balance": random.randint(10000, 10000000),
        "currency": "KES",
        "last_updated": datetime.now().isoformat()
    }


@router.get("/health")
async def t24_health():
    """Health check for T24 mock API"""
    return {
        "status": "healthy",
        "service": "T24 Mock API",
        "timestamp": datetime.now().isoformat()
    }
