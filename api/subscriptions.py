"""
════════════════════════════════════════════════════════════════════════════════
SUBSCRIPTION MANAGEMENT
════════════════════════════════════════════════════════════════════════════════

Handles subscription tier enforcement, usage tracking, and billing logic.

Subscription Tiers:
  • Starter: 50,000 tx/month - KES 2.4M/yr
  • Growth: 500,000 tx/month - KES 7.2M/yr
  • Enterprise: Unlimited - KES 18M+/yr

════════════════════════════════════════════════════════════════════════════════
"""

from datetime import datetime, date
from typing import Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from data.schema import Client, FraudScore
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────────────────────
# SUBSCRIPTION CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

SUBSCRIPTION_TIERS = {
    "starter": {
        "name": "Starter",
        "monthly_price": 200000,  # KES 2.4M/yr = 200K/month
        "max_transactions": 50000,
        "features": [
            "VelocityWatch scoring",
            "PhantomID detection",
            "Basic dashboard",
            "Email alerts",
            "Standard support"
        ]
    },
    "growth": {
        "name": "Growth",
        "monthly_price": 600000,  # KES 7.2M/yr = 600K/month
        "max_transactions": 500000,
        "features": [
            "All Starter features",
            "Real-time Kafka streaming",
            "Velocity spike detection",
            "Live WebSocket dashboard",
            "SocialGraph ring detection",
            "Monthly compliance reports"
        ]
    },
    "enterprise": {
        "name": "Enterprise",
        "monthly_price": 1500000,  # KES 18M+/yr = 1.5M+/month
        "max_transactions": float('inf'),
        "features": [
            "All Growth features",
            "Custom ML model training",
            "Dedicated infrastructure",
            "CBK reporting templates",
            "Priority support SLA",
            "Regional expansion support"
        ]
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────────────────────────────────────────

class SubscriptionInfo(BaseModel):
    """Subscription details for a client"""
    plan: str
    monthly_price: int
    max_transactions: int
    transactions_used: int
    transactions_remaining: int
    usage_percentage: float
    renewal_date: str
    is_over_limit: bool
    features: list

class UsageWarning(BaseModel):
    """Usage warning when approaching limit"""
    level: str  # "normal", "warning", "critical"
    message: str
    transactions_used: int
    transactions_remaining: int
    usage_percentage: float

# ─────────────────────────────────────────────────────────────────────────────
# SUBSCRIPTION MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

class SubscriptionManager:
    """Manages subscription tiers and usage tracking"""

    @staticmethod
    def get_tier_info(tier: str) -> dict:
        """Get subscription tier information"""
        return SUBSCRIPTION_TIERS.get(tier, SUBSCRIPTION_TIERS["starter"])

    @staticmethod
    def get_current_month_usage(client_id: int, db: Session) -> int:
        """
        Get transaction count for current month
        
        Args:
            client_id: Client ID
            db: Database session
        
        Returns:
            Number of transactions scored this month
        """
        today = date.today()
        first_day = today.replace(day=1)

        count = db.query(func.count(FraudScore.id)).filter(
            and_(
                FraudScore.client_id == client_id,
                FraudScore.created_at >= datetime.combine(first_day, datetime.min.time())
            )
        ).scalar()

        return count or 0

    @staticmethod
    def check_usage_limit(client: Client, db: Session) -> dict:
        """
        Check if client has exceeded usage limit
        
        Args:
            client: Client object
            db: Database session
        
        Returns:
            Dictionary with usage info and limit status
        """
        tier_info = SUBSCRIPTION_TIERS.get(client.subscription_tier, SUBSCRIPTION_TIERS["starter"])
        max_transactions = tier_info["max_transactions"]
        
        # Get current month usage
        usage = SubscriptionManager.get_current_month_usage(client.id, db)
        
        # Calculate remaining
        if max_transactions == float('inf'):
            remaining = float('inf')
            is_over_limit = False
        else:
            remaining = max(0, max_transactions - usage)
            is_over_limit = usage >= max_transactions

        return {
            "tier": client.subscription_tier,
            "max_transactions": max_transactions,
            "transactions_used": usage,
            "transactions_remaining": remaining,
            "is_over_limit": is_over_limit,
            "usage_percentage": (usage / max_transactions * 100) if max_transactions != float('inf') else 0
        }

    @staticmethod
    def get_usage_warning(client: Client, db: Session) -> UsageWarning:
        """
        Get usage warning level
        
        Args:
            client: Client object
            db: Database session
        
        Returns:
            UsageWarning with level and message
        """
        usage_info = SubscriptionManager.check_usage_limit(client, db)
        usage_pct = usage_info["usage_percentage"]

        if usage_info["is_over_limit"]:
            level = "critical"
            message = f"Usage limit exceeded. Upgrade to continue."
        elif usage_pct >= 90:
            level = "critical"
            message = f"90% of monthly limit used ({usage_info['transactions_used']}/{usage_info['max_transactions']}). Upgrade soon."
        elif usage_pct >= 80:
            level = "warning"
            message = f"80% of monthly limit used ({usage_info['transactions_used']}/{usage_info['max_transactions']}). Consider upgrading."
        elif usage_pct >= 50:
            level = "warning"
            message = f"50% of monthly limit used ({usage_info['transactions_used']}/{usage_info['max_transactions']})."
        else:
            level = "normal"
            message = f"Usage: {usage_info['transactions_used']}/{usage_info['max_transactions']} transactions."

        return UsageWarning(
            level=level,
            message=message,
            transactions_used=usage_info["transactions_used"],
            transactions_remaining=usage_info["transactions_remaining"],
            usage_percentage=usage_pct
        )

    @staticmethod
    def get_subscription_info(client: Client, db: Session) -> SubscriptionInfo:
        """
        Get complete subscription information for client
        
        Args:
            client: Client object
            db: Database session
        
        Returns:
            SubscriptionInfo with all details
        """
        tier_info = SUBSCRIPTION_TIERS.get(client.subscription_tier, SUBSCRIPTION_TIERS["starter"])
        usage_info = SubscriptionManager.check_usage_limit(client, db)

        # Calculate renewal date (first day of next month)
        today = date.today()
        if today.month == 12:
            renewal_date = date(today.year + 1, 1, 1)
        else:
            renewal_date = date(today.year, today.month + 1, 1)

        return SubscriptionInfo(
            plan=client.subscription_tier,
            monthly_price=tier_info["monthly_price"],
            max_transactions=tier_info["max_transactions"],
            transactions_used=usage_info["transactions_used"],
            transactions_remaining=usage_info["transactions_remaining"],
            usage_percentage=usage_info["usage_percentage"],
            renewal_date=renewal_date.isoformat(),
            is_over_limit=usage_info["is_over_limit"],
            features=tier_info["features"]
        )

    @staticmethod
    def can_process_transaction(client: Client, db: Session) -> Tuple[bool, str]:
        """
        Check if client can process another transaction
        
        Args:
            client: Client object
            db: Database session
        
        Returns:
            Tuple of (can_process, message)
        """
        usage_info = SubscriptionManager.check_usage_limit(client, db)

        if usage_info["is_over_limit"]:
            return False, f"Monthly limit exceeded. Upgrade to {client.subscription_tier} plan."

        return True, "OK"

    @staticmethod
    def upgrade_subscription(client: Client, new_tier: str, db: Session) -> bool:
        """
        Upgrade client subscription tier
        
        Args:
            client: Client object
            new_tier: New subscription tier
            db: Database session
        
        Returns:
            True if upgrade successful
        """
        if new_tier not in SUBSCRIPTION_TIERS:
            return False

        client.subscription_tier = new_tier
        db.commit()
        return True

    @staticmethod
    def get_all_tiers() -> dict:
        """Get all available subscription tiers"""
        return SUBSCRIPTION_TIERS
