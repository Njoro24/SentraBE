"""
T24 Transaction Adapter
Transforms Temenos T24 format to internal Sentra format
Handles field mapping, validation, and normalization
"""

from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TransactionRequest:
    """Internal transaction format"""
    transaction_id: str
    amount: float
    currency: str
    merchant_name: str
    merchant_category: str
    merchant_location: str
    account_number: str
    counterparty_account: str
    channel: str
    device_id: str
    ip_address: str
    timestamp: str
    velocity_flag: bool = False
    geographic_mismatch: bool = False
    device_mismatch: bool = False
    account_age_days: int = 30
    previous_declines: int = 0
    country: str = "KE"
    phone_number: str = ""
    location: str = ""


class T24Adapter:
    """Adapter for converting T24 transactions to internal format"""
    
    # T24 to internal field mapping
    FIELD_MAPPING = {
        "TRANSACTION_ID": "transaction_id",
        "AMOUNT": "amount",
        "CURRENCY": "currency",
        "MERCHANT_NAME": "merchant_name",
        "MERCHANT_CATEGORY": "merchant_category",
        "MERCHANT_LOCATION": "merchant_location",
        "ACCOUNT_NUMBER": "account_number",
        "COUNTERPARTY_ACCOUNT": "counterparty_account",
        "CHANNEL": "channel",
        "DEVICE_ID": "device_id",
        "IP_ADDRESS": "ip_address",
        "TIMESTAMP": "timestamp",
        "VELOCITY_FLAG": "velocity_flag",
        "GEOGRAPHIC_MISMATCH": "geographic_mismatch",
        "DEVICE_MISMATCH": "device_mismatch"
    }
    
    # Channel normalization
    CHANNEL_MAPPING = {
        "MOBILE_BANKING": "MOBILE",
        "INTERNET_BANKING": "WEB",
        "ATM": "ATM",
        "POS": "POS",
        "BRANCH": "BRANCH",
        "PHONE_BANKING": "PHONE"
    }
    
    # Merchant category normalization
    MERCHANT_CATEGORY_MAPPING = {
        "Retail": "RETAIL",
        "Hospitality": "HOSPITALITY",
        "Transportation": "TRANSPORTATION",
        "Healthcare": "HEALTHCARE",
        "Education": "EDUCATION",
        "Entertainment": "ENTERTAINMENT",
        "Gambling": "GAMBLING",
        "Cryptocurrency": "CRYPTOCURRENCY",
        "Money Transfer": "MONEY_TRANSFER",
        "ATM Withdrawal": "ATM_WITHDRAWAL",
        "Wire Transfer": "WIRE_TRANSFER",
        "Cash Advance": "CASH_ADVANCE"
    }
    
    @staticmethod
    def validate_t24_transaction(t24_txn: Dict) -> bool:
        """Validate T24 transaction has required fields"""
        required_fields = [
            "TRANSACTION_ID",
            "AMOUNT",
            "CURRENCY",
            "ACCOUNT_NUMBER",
            "TIMESTAMP"
        ]
        
        for field in required_fields:
            if field not in t24_txn or t24_txn[field] is None:
                logger.warning(f"Missing required field: {field}")
                return False
        
        return True
    
    @staticmethod
    def normalize_channel(channel: str) -> str:
        """Normalize T24 channel to internal format"""
        return T24Adapter.CHANNEL_MAPPING.get(channel, channel)
    
    @staticmethod
    def normalize_merchant_category(category: str) -> str:
        """Normalize T24 merchant category to internal format"""
        return T24Adapter.MERCHANT_CATEGORY_MAPPING.get(category, category)
    
    @staticmethod
    def normalize_amount(amount, currency: str) -> float:
        """Normalize amount to KES equivalent"""
        # Exchange rates (simplified)
        exchange_rates = {
            "KES": 1.0,
            "USD": 130.0,  # 1 USD = 130 KES (approximate)
            "EUR": 140.0,  # 1 EUR = 140 KES (approximate)
            "GBP": 160.0   # 1 GBP = 160 KES (approximate)
        }
        
        rate = exchange_rates.get(currency, 1.0)
        return float(amount) * rate
    
    @staticmethod
    def parse_timestamp(timestamp_str: str) -> str:
        """Parse and normalize timestamp"""
        try:
            # Try ISO format first
            dt = datetime.fromisoformat(timestamp_str)
            return dt.isoformat()
        except:
            try:
                # Try other common formats
                dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                return dt.isoformat()
            except:
                logger.warning(f"Could not parse timestamp: {timestamp_str}")
                return datetime.now().isoformat()
    
    @staticmethod
    def transform_t24_to_internal(t24_txn: Dict) -> Optional[TransactionRequest]:
        """
        Transform T24 transaction to internal format
        
        Args:
            t24_txn: T24-formatted transaction dictionary
        
        Returns:
            TransactionRequest object or None if validation fails
        """
        # Validate
        if not T24Adapter.validate_t24_transaction(t24_txn):
            return None
        
        try:
            # Extract and normalize fields
            transaction_id = str(t24_txn.get("TRANSACTION_ID", ""))
            amount = T24Adapter.normalize_amount(
                t24_txn.get("AMOUNT", 0),
                t24_txn.get("CURRENCY", "KES")
            )
            currency = t24_txn.get("CURRENCY", "KES")
            merchant_name = str(t24_txn.get("MERCHANT_NAME", "Unknown"))
            merchant_category = T24Adapter.normalize_merchant_category(
                t24_txn.get("MERCHANT_CATEGORY", "RETAIL")
            )
            merchant_location = str(t24_txn.get("MERCHANT_LOCATION", "Unknown"))
            account_number = str(t24_txn.get("ACCOUNT_NUMBER", ""))
            counterparty_account = str(t24_txn.get("COUNTERPARTY_ACCOUNT", ""))
            channel = T24Adapter.normalize_channel(
                t24_txn.get("CHANNEL", "UNKNOWN")
            )
            device_id = str(t24_txn.get("DEVICE_ID", ""))
            ip_address = str(t24_txn.get("IP_ADDRESS", "0.0.0.0"))
            timestamp = T24Adapter.parse_timestamp(
                t24_txn.get("TIMESTAMP", datetime.now().isoformat())
            )
            
            # Risk flags
            velocity_flag = bool(t24_txn.get("VELOCITY_FLAG", False))
            geographic_mismatch = bool(t24_txn.get("GEOGRAPHIC_MISMATCH", False))
            device_mismatch = bool(t24_txn.get("DEVICE_MISMATCH", False))
            
            # Create transaction request
            txn_request = TransactionRequest(
                transaction_id=transaction_id,
                amount=amount,
                currency=currency,
                merchant_name=merchant_name,
                merchant_category=merchant_category,
                merchant_location=merchant_location,
                account_number=account_number,
                counterparty_account=counterparty_account,
                channel=channel,
                device_id=device_id,
                ip_address=ip_address,
                timestamp=timestamp,
                velocity_flag=velocity_flag,
                geographic_mismatch=geographic_mismatch,
                device_mismatch=device_mismatch,
                country="KE",  # Default to Kenya
                phone_number=account_number,  # Use account as phone proxy
                location=merchant_location
            )
            
            logger.info(f"Successfully transformed T24 transaction: {transaction_id}")
            return txn_request
            
        except Exception as e:
            logger.error(f"Error transforming T24 transaction: {str(e)}")
            return None
    
    @staticmethod
    def transform_batch(t24_transactions: List[Dict]) -> List[TransactionRequest]:
        """
        Transform batch of T24 transactions
        
        Args:
            t24_transactions: List of T24-formatted transactions
        
        Returns:
            List of TransactionRequest objects
        """
        transformed = []
        for t24_txn in t24_transactions:
            internal_txn = T24Adapter.transform_t24_to_internal(t24_txn)
            if internal_txn:
                transformed.append(internal_txn)
        
        logger.info(f"Transformed {len(transformed)}/{len(t24_transactions)} transactions")
        return transformed
    
    @staticmethod
    def to_dict(txn_request: TransactionRequest) -> Dict:
        """Convert TransactionRequest to dictionary"""
        return {
            "transaction_id": txn_request.transaction_id,
            "amount": txn_request.amount,
            "currency": txn_request.currency,
            "merchant_name": txn_request.merchant_name,
            "merchant_category": txn_request.merchant_category,
            "merchant_location": txn_request.merchant_location,
            "account_number": txn_request.account_number,
            "counterparty_account": txn_request.counterparty_account,
            "channel": txn_request.channel,
            "device_id": txn_request.device_id,
            "ip_address": txn_request.ip_address,
            "timestamp": txn_request.timestamp,
            "velocity_flag": txn_request.velocity_flag,
            "geographic_mismatch": txn_request.geographic_mismatch,
            "device_mismatch": txn_request.device_mismatch,
            "account_age_days": txn_request.account_age_days,
            "previous_declines": txn_request.previous_declines
        }
