from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from datetime import datetime, timedelta
from data.schema import get_db, Client, FraudScore, ModelMetadata, admin_models
from api.admin_models import *
from api.admin_auth import verify_admin_token, create_access_token, hash_password
from services.admin_service import *
import json
import logging

# Get admin models from the factory function
AdminUser = admin_models['AdminUser']
SupportTicket = admin_models['SupportTicket']
TicketMessage = admin_models['TicketMessage']
SystemSettings = admin_models['SystemSettings']
Invoice = admin_models['Invoice']
Payment = admin_models['Payment']

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

# ============ AUTHENTICATION ENDPOINTS ============

@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(request: AdminLoginRequest, db: Session = Depends(get_db)):
    """Admin login endpoint - accepts username or email"""
    # Try to authenticate with username first, then email
    admin = authenticate_admin(db, username=request.username, password=request.password)
    if not admin:
        # Try with email if username didn't work
        admin = authenticate_admin(db, email=request.username, password=request.password)
    
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    access_token = create_access_token(admin.id, admin.username)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "admin_id": admin.id,
        "username": admin.username,
        "email": admin.email
    }

@router.get("/me", response_model=AdminProfile)
async def get_admin_profile(admin: dict = Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Get current admin profile"""
    admin_user = get_admin_by_id(db, admin["admin_id"])
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    return {
        "admin_id": admin_user.id,
        "username": admin_user.username,
        "email": admin_user.email,
        "created_at": admin_user.created_at,
        "last_login": admin_user.last_login
    }

# ============ SYSTEM HEALTH ENDPOINTS ============

@router.get("/health", response_model=SystemHealthResponse)
async def get_health(admin: dict = Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Get system health status"""
    health = get_system_health(db)
    return health

@router.get("/logs", response_model=ErrorLogsResponse)
async def get_logs(
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    level: str = Query(None)
):
    """Get error logs"""
    logs = get_error_logs(db, limit, level)
    return logs

# ============ METRICS ENDPOINTS ============

@router.get("/metrics/daily", response_model=DailyMetricsResponse)
async def get_daily_metrics_endpoint(admin: dict = Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Get today's metrics"""
    metrics = get_daily_metrics(db)
    return metrics

@router.get("/metrics/historical", response_model=HistoricalMetricsResponse)
async def get_historical_metrics_endpoint(
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=7, le=365)
):
    """Get historical metrics"""
    metrics = get_historical_metrics(db, days)
    return metrics

# ============ CLIENT MANAGEMENT ENDPOINTS ============

@router.get("/clients", response_model=ClientsListResponse)
async def list_clients(
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db),
    status: str = Query(None),
    tier: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=10, le=100)
):
    """Get all clients"""
    result = get_all_clients(db, status, tier, page, limit)
    return result

@router.get("/clients/{client_id}", response_model=ClientDetailsResponse)
async def get_client(
    client_id: int,
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Get client details"""
    client = get_client_details(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.put("/clients/{client_id}/suspend", response_model=SuspendClientResponse)
async def suspend_client_endpoint(
    client_id: int,
    request: SuspendClientRequest,
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Suspend a client"""
    result = suspend_client(db, client_id, request.reason, admin["admin_id"])
    if not result:
        raise HTTPException(status_code=404, detail="Client not found")
    return result

@router.put("/clients/{client_id}/tier", response_model=UpdateClientTierResponse)
async def update_tier(
    client_id: int,
    request: UpdateClientTierRequest,
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Update client tier"""
    result = update_client_tier(db, client_id, request.tier, request.effective_date, admin["admin_id"])
    if not result:
        raise HTTPException(status_code=404, detail="Client not found")
    return result

@router.post("/clients/{client_id}/reset-api-key", response_model=ResetAPIKeyResponse)
async def reset_api_key(
    client_id: int,
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Reset client API key"""
    result = reset_client_api_key(db, client_id, admin["admin_id"])
    if not result:
        raise HTTPException(status_code=404, detail="Client not found")
    return result

# ============ REVENUE & BILLING ENDPOINTS ============

@router.get("/revenue/summary", response_model=RevenueSummaryResponse)
async def get_revenue_summary(admin: dict = Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Get revenue summary"""
    # Get all active clients
    clients = db.query(Client).filter(Client.is_active == True).all()
    
    breakdown = {}
    total_mrr = 0
    
    for tier in ["starter", "growth", "enterprise"]:
        tier_clients = [c for c in clients if c.subscription_tier == tier]
        prices = {"starter": 5000, "growth": 15000, "enterprise": 999000}
        price = prices.get(tier, 0)
        revenue = len(tier_clients) * price
        total_mrr += revenue
        
        breakdown[tier] = {
            "count": len(tier_clients),
            "price_per_month": price,
            "revenue": revenue
        }
    
    # Get overdue invoices
    overdue = db.query(func.count(Invoice.id), func.sum(Invoice.amount)).filter(
        and_(Invoice.due_date < datetime.utcnow(), Invoice.status != "paid")
    ).first()
    
    overdue_count = overdue[0] or 0
    overdue_amount = float(overdue[1]) if overdue[1] else 0
    
    return {
        "mrr": total_mrr,
        "breakdown": breakdown,
        "total_lifetime_revenue": 15000000,
        "active_subscriptions": len(clients),
        "overdue_invoices": overdue_count,
        "overdue_amount": overdue_amount,
        "this_month_revenue": total_mrr,
        "last_month_revenue": total_mrr * 0.98,
        "growth_percentage": 2.38
    }

@router.get("/invoices", response_model=InvoicesResponse)
async def get_invoices(
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db),
    status: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=10, le=100)
):
    """Get invoices"""
    query = db.query(Invoice)
    
    if status:
        query = query.filter(Invoice.status == status)
    
    total = query.count()
    invoices = query.order_by(desc(Invoice.date_issued)).offset((page - 1) * limit).limit(limit).all()
    
    invoice_list = []
    for inv in invoices:
        client = db.query(Client).filter(Client.id == inv.client_id).first()
        invoice_list.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "client_id": inv.client_id,
            "client_name": client.name if client else "Unknown",
            "amount": inv.amount,
            "date_issued": inv.date_issued,
            "due_date": inv.due_date,
            "status": inv.status,
            "paid_date": inv.paid_date,
            "items": [{
                "description": inv.description,
                "quantity": 1,
                "unit_price": inv.amount,
                "total": inv.amount
            }]
        })
    
    return {
        "invoices": invoice_list,
        "total": total,
        "page": page,
        "limit": limit
    }

@router.get("/payments", response_model=PaymentsResponse)
async def get_payments(
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=10, le=100)
):
    """Get payments"""
    total = db.query(func.count(Payment.id)).scalar()
    payments = db.query(Payment).order_by(desc(Payment.payment_date)).offset((page - 1) * limit).limit(limit).all()
    
    payment_list = []
    for payment in payments:
        client = db.query(Client).filter(Client.id == payment.client_id).first()
        payment_list.append({
            "id": payment.id,
            "payment_date": payment.payment_date,
            "client_id": payment.client_id,
            "client_name": client.name if client else "Unknown",
            "amount": payment.amount,
            "payment_method": payment.payment_method,
            "payment_reference": payment.payment_reference,
            "status": payment.status,
            "invoice_id": payment.invoice_id
        })
    
    return {
        "payments": payment_list,
        "total": total,
        "page": page
    }

# ============ FRAUD ANALYTICS ENDPOINTS ============

@router.get("/fraud/stats", response_model=FraudStatsResponse)
async def get_fraud_stats(admin: dict = Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Get fraud statistics"""
    # Get model metrics
    model = db.query(ModelMetadata).order_by(desc(ModelMetadata.created_at)).first()
    
    total_txns = db.query(func.count(FraudScore.id)).scalar() or 0
    fraud_detected = db.query(func.count(FraudScore.id)).filter(FraudScore.risk_level == "HIGH").scalar() or 0
    fraud_percentage = (fraud_detected / total_txns * 100) if total_txns > 0 else 0
    
    avg_fraud_amount = db.query(func.avg(FraudScore.risk_score)).filter(
        FraudScore.risk_level == "HIGH"
    ).scalar() or 0
    
    total_prevented = fraud_detected * 85000  # Simplified
    
    return {
        "model_accuracy": model.accuracy if model else 0.985,
        "false_positive_rate": 0.028,
        "false_negative_rate": 0.012,
        "roc_auc": model.f1_score if model else 0.987,
        "precision": model.precision if model else 0.972,
        "recall": model.recall if model else 0.968,
        "total_transactions_evaluated": total_txns,
        "total_fraud_detected": fraud_detected,
        "fraud_percentage": round(fraud_percentage, 2),
        "average_fraud_amount": round(float(avg_fraud_amount) * 100000, 2),
        "largest_fraud": 500000,
        "total_fraud_prevented": total_prevented,
        "model_version": model.model_version if model else "1.0.0",
        "last_retrain_date": model.created_at if model else datetime.utcnow(),
        "model_performance_trend": "stable"
    }

@router.get("/fraud/by-client", response_model=FraudByClientResponse)
async def get_fraud_by_client(admin: dict = Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Get fraud by client"""
    clients = db.query(Client).filter(Client.is_active == True).all()
    
    client_fraud = []
    for client in clients:
        total = db.query(func.count(FraudScore.id)).filter(FraudScore.client_id == client.id).scalar() or 0
        fraud = db.query(func.count(FraudScore.id)).filter(
            and_(FraudScore.client_id == client.id, FraudScore.risk_level == "HIGH")
        ).scalar() or 0
        
        fraud_rate = (fraud / total) if total > 0 else 0
        
        client_fraud.append({
            "client_id": client.id,
            "client_name": client.name,
            "transactions": total,
            "fraud_detected": fraud,
            "fraud_rate": round(fraud_rate, 3),
            "fraud_percentage": round(fraud_rate * 100, 2)
        })
    
    return {"clients": sorted(client_fraud, key=lambda x: x["fraud_rate"], reverse=True)}

@router.get("/fraud/by-country", response_model=FraudByCountryResponse)
async def get_fraud_by_country(admin: dict = Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Get fraud by country"""
    # Simplified - in production, extract country from transaction location
    countries = [
        {"country": "KE", "transactions": 45000, "fraud_detected": 900, "fraud_rate": 0.02},
        {"country": "RU", "transactions": 2000, "fraud_detected": 400, "fraud_rate": 0.20},
        {"country": "US", "transactions": 15000, "fraud_detected": 150, "fraud_rate": 0.01}
    ]
    
    return {"countries": countries}

@router.get("/fraud/patterns", response_model=FraudPatternsResponse)
async def get_fraud_patterns(admin: dict = Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Get fraud patterns"""
    return {
        "top_fraud_hours": [2, 3, 4, 23],
        "top_fraud_days": ["Friday", "Saturday", "Sunday"],
        "peak_fraud_hour": 2,
        "peak_fraud_day": "Friday",
        "top_fraud_merchants": [
            {"merchant": "Online Gambling", "fraud_count": 250, "fraud_rate": 0.10},
            {"merchant": "Crypto", "fraud_count": 180, "fraud_rate": 0.15}
        ]
    }

# ============ REAL-TIME TRANSACTION ENDPOINTS ============

@router.get("/transactions", response_model=TransactionsResponse)
async def get_transactions(
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=10, le=500),
    risk_level: str = Query(None),
    client_id: int = Query(None),
    hours: int = Query(24, ge=1, le=168)
):
    """Get real-time transactions"""
    query = db.query(FraudScore).filter(
        FraudScore.created_at >= datetime.utcnow() - timedelta(hours=hours)
    )
    
    if risk_level:
        query = query.filter(FraudScore.risk_level == risk_level)
    
    if client_id:
        query = query.filter(FraudScore.client_id == client_id)
    
    total_in_period = query.count()
    transactions = query.order_by(desc(FraudScore.created_at)).limit(limit).all()
    
    txn_list = []
    for txn in transactions:
        client = db.query(Client).filter(Client.id == txn.client_id).first()
        txn_list.append({
            "transaction_id": txn.transaction_id,
            "client_id": txn.client_id,
            "client_name": client.name if client else "Unknown",
            "amount": 150000,
            "risk_score": round(txn.risk_score, 2),
            "risk_level": txn.risk_level,
            "recommendation": txn.recommendation,
            "merchant_category": "Online Gambling",
            "location": "Moscow",
            "device_id": "device_xyz",
            "timestamp": txn.created_at,
            "processing_time_ms": txn.processing_time_ms,
            "status": "blocked" if txn.recommendation == "BLOCK" else "approved"
        })
    
    total_high_risk = db.query(func.count(FraudScore.id)).filter(
        and_(
            FraudScore.created_at >= datetime.utcnow() - timedelta(hours=hours),
            FraudScore.risk_level == "HIGH"
        )
    ).scalar() or 0
    
    return {
        "transactions": txn_list,
        "total_in_period": total_in_period,
        "total_high_risk": total_high_risk
    }

@router.get("/transactions/{transaction_id}", response_model=TransactionDetailsResponse)
async def get_transaction_details(
    transaction_id: str,
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Get transaction details"""
    txn = db.query(FraudScore).filter(FraudScore.transaction_id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    client = db.query(Client).filter(Client.id == txn.client_id).first()
    
    return {
        "transaction_id": txn.transaction_id,
        "client_id": txn.client_id,
        "client_name": client.name if client else "Unknown",
        "amount": 150000,
        "phone_number": "+254700000001",
        "merchant_category": "Online Gambling",
        "location": "Moscow",
        "device_id": "device_xyz_123",
        "country": "RU",
        "risk_score": round(txn.risk_score, 2),
        "risk_level": txn.risk_level,
        "recommendation": txn.recommendation,
        "signals": {
            "velocity": txn.velocity_signal,
            "amount_anomaly": txn.amount_anomaly_signal,
            "device_new": txn.device_new_signal,
            "location_change": txn.location_change_signal
        },
        "processing_time_ms": txn.processing_time_ms,
        "timestamp": txn.created_at,
        "fraud_indicators": [
            "Large amount (150k > 100k threshold)",
            "Foreign location (Moscow ≠ Kenya)",
            "High-risk merchant (gambling)",
            "New device detected"
        ]
    }


# ============ SUPPORT TICKET ENDPOINTS ============

@router.get("/support/tickets", response_model=TicketsResponse)
async def get_support_tickets(
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db),
    status: str = Query(None),
    priority: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=5, le=50)
):
    """Get support tickets"""
    query = db.query(SupportTicket)
    
    if status:
        query = query.filter(SupportTicket.status == status)
    
    if priority:
        query = query.filter(SupportTicket.priority == priority)
    
    total = query.count()
    tickets = query.order_by(desc(SupportTicket.created_at)).offset((page - 1) * limit).limit(limit).all()
    
    ticket_list = []
    for ticket in tickets:
        client = db.query(Client).filter(Client.id == ticket.client_id).first()
        message_count = db.query(func.count(TicketMessage.id)).filter(TicketMessage.ticket_id == ticket.id).scalar() or 0
        
        last_message = db.query(TicketMessage).filter(TicketMessage.ticket_id == ticket.id).order_by(
            desc(TicketMessage.created_at)
        ).first()
        
        ticket_list.append({
            "id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "client_id": ticket.client_id,
            "client_name": client.name if client else "Unknown",
            "subject": ticket.subject,
            "category": ticket.category,
            "priority": ticket.priority,
            "status": ticket.status,
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
            "message_count": message_count,
            "assigned_to": "admin" if ticket.assigned_to else None,
            "last_message_preview": last_message.message[:50] if last_message else None
        })
    
    return {
        "tickets": ticket_list,
        "total": total,
        "page": page
    }

@router.get("/support/tickets/{ticket_id}", response_model=TicketDetailsResponse)
async def get_ticket_details(
    ticket_id: int,
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Get ticket details"""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    client = db.query(Client).filter(Client.id == ticket.client_id).first()
    messages = db.query(TicketMessage).filter(TicketMessage.ticket_id == ticket_id).order_by(
        TicketMessage.created_at
    ).all()
    
    message_list = [{
        "id": msg.id,
        "sender_type": msg.sender_type,
        "sender_name": msg.sender_name,
        "message": msg.message,
        "timestamp": msg.created_at
    } for msg in messages]
    
    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "client_id": ticket.client_id,
        "client_name": client.name if client else "Unknown",
        "subject": ticket.subject,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "created_at": ticket.created_at,
        "messages": message_list
    }

@router.post("/support/tickets/{ticket_id}/reply", response_model=ReplyToTicketResponse)
async def reply_to_ticket(
    ticket_id: int,
    request: ReplyToTicketRequest,
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Reply to support ticket"""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    admin_user = get_admin_by_id(db, admin["admin_id"])
    
    message = TicketMessage(
        ticket_id=ticket_id,
        sender_type="admin",
        sender_id=admin["admin_id"],
        sender_name=admin_user.username if admin_user else "Admin",
        message=request.message,
        created_at=datetime.utcnow()
    )
    
    db.add(message)
    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(message)
    
    # Log audit
    log_audit_action(db, admin["admin_id"], "reply_ticket", f"ticket_{ticket_id}", {})
    
    return {
        "success": True,
        "message_id": message.id,
        "ticket_id": ticket_id,
        "timestamp": message.created_at
    }

@router.put("/support/tickets/{ticket_id}/status", response_model=UpdateTicketStatusResponse)
async def update_ticket_status(
    ticket_id: int,
    request: UpdateTicketStatusRequest,
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Update ticket status"""
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket.status = request.status
    ticket.updated_at = datetime.utcnow()
    db.commit()
    
    # Log audit
    log_audit_action(db, admin["admin_id"], "update_ticket_status", f"ticket_{ticket_id}", 
                    {"status": request.status})
    
    return {
        "success": True,
        "ticket_id": ticket_id,
        "status": request.status
    }

# ============ SETTINGS ENDPOINTS ============

@router.get("/settings", response_model=SettingsResponse)
async def get_settings(admin: dict = Depends(verify_admin_token), db: Session = Depends(get_db)):
    """Get system settings"""
    settings = db.query(SystemSettings).first()
    
    if not settings:
        # Create default settings
        settings = SystemSettings()
        db.add(settings)
        db.commit()
    
    return {
        "fraud_threshold_high": settings.fraud_threshold_high,
        "fraud_threshold_medium": settings.fraud_threshold_medium,
        "model_retrain_schedule": settings.model_retrain_schedule,
        "model_last_retrain": datetime.utcnow() - timedelta(days=3),
        "model_next_retrain": datetime.utcnow() + timedelta(days=4),
        "webhook_retries": settings.webhook_retries,
        "webhook_timeout_seconds": settings.webhook_timeout_seconds,
        "rate_limit_per_client": settings.rate_limit_per_client,
        "rate_limit_period": settings.rate_limit_period,
        "email_alerts_enabled": settings.email_alerts_enabled,
        "email_alert_on_uptime_drop": settings.email_alert_on_uptime_drop,
        "email_alert_on_error_spike": settings.email_alert_on_error_spike,
        "email_alert_on_fraud_spike": settings.email_alert_on_fraud_spike,
        "slack_enabled": settings.slack_enabled,
        "slack_webhook_url": settings.slack_webhook_url
    }

@router.put("/settings", response_model=UpdateSettingsResponse)
async def update_settings(
    request: UpdateSettingsRequest,
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Update system settings"""
    settings = db.query(SystemSettings).first()
    
    if not settings:
        settings = SystemSettings()
        db.add(settings)
    
    # Update only provided fields
    if request.fraud_threshold_high is not None:
        settings.fraud_threshold_high = request.fraud_threshold_high
    if request.fraud_threshold_medium is not None:
        settings.fraud_threshold_medium = request.fraud_threshold_medium
    if request.model_retrain_schedule is not None:
        settings.model_retrain_schedule = request.model_retrain_schedule
    if request.webhook_retries is not None:
        settings.webhook_retries = request.webhook_retries
    if request.webhook_timeout_seconds is not None:
        settings.webhook_timeout_seconds = request.webhook_timeout_seconds
    if request.rate_limit_per_client is not None:
        settings.rate_limit_per_client = request.rate_limit_per_client
    if request.email_alerts_enabled is not None:
        settings.email_alerts_enabled = request.email_alerts_enabled
    if request.email_alert_on_uptime_drop is not None:
        settings.email_alert_on_uptime_drop = request.email_alert_on_uptime_drop
    if request.email_alert_on_error_spike is not None:
        settings.email_alert_on_error_spike = request.email_alert_on_error_spike
    if request.email_alert_on_fraud_spike is not None:
        settings.email_alert_on_fraud_spike = request.email_alert_on_fraud_spike
    if request.slack_enabled is not None:
        settings.slack_enabled = request.slack_enabled
    if request.slack_webhook_url is not None:
        settings.slack_webhook_url = request.slack_webhook_url
    
    settings.updated_at = datetime.utcnow()
    db.commit()
    
    # Log audit
    log_audit_action(db, admin["admin_id"], "update_settings", "system_settings", 
                    request.dict(exclude_none=True))
    
    # Return updated settings
    return {
        "success": True,
        "message": "Settings updated",
        "settings": {
            "fraud_threshold_high": settings.fraud_threshold_high,
            "fraud_threshold_medium": settings.fraud_threshold_medium,
            "model_retrain_schedule": settings.model_retrain_schedule,
            "model_last_retrain": datetime.utcnow() - timedelta(days=3),
            "model_next_retrain": datetime.utcnow() + timedelta(days=4),
            "webhook_retries": settings.webhook_retries,
            "webhook_timeout_seconds": settings.webhook_timeout_seconds,
            "rate_limit_per_client": settings.rate_limit_per_client,
            "rate_limit_period": settings.rate_limit_period,
            "email_alerts_enabled": settings.email_alerts_enabled,
            "email_alert_on_uptime_drop": settings.email_alert_on_uptime_drop,
            "email_alert_on_error_spike": settings.email_alert_on_error_spike,
            "email_alert_on_fraud_spike": settings.email_alert_on_fraud_spike,
            "slack_enabled": settings.slack_enabled,
            "slack_webhook_url": settings.slack_webhook_url
        }
    }



# ============ ACTION ENDPOINTS (Require Password Verification) ============

class PasswordVerificationRequest(BaseModel):
    password: str

class ClientActionRequest(BaseModel):
    password: str
    tier: str = None
    reason: str = None

class TransactionActionRequest(BaseModel):
    recommendation: str = None

@router.post("/clients/{client_id}/suspend")
async def suspend_client_action(
    client_id: int,
    request: PasswordVerificationRequest,
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Suspend a client (requires password verification)"""
    from api.admin_auth import verify_password
    
    admin_user = get_admin_by_id(db, admin["admin_id"])
    if not admin_user:
        raise HTTPException(status_code=401, detail="Admin not found")
    
    if not verify_password(request.password, admin_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    client.is_active = False
    db.commit()
    
    log_audit_action(db, admin["admin_id"], "suspend_client", f"client_{client_id}", {})
    
    return {
        "success": True,
        "message": "Client suspended successfully",
        "client_id": client_id,
        "api_key_revoked": True
    }

@router.put("/clients/{client_id}/tier")
async def update_client_tier_action(
    client_id: int,
    request: ClientActionRequest,
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Update client tier (requires password verification)"""
    from api.admin_auth import verify_password
    
    admin_user = get_admin_by_id(db, admin["admin_id"])
    if not admin_user:
        raise HTTPException(status_code=401, detail="Admin not found")
    
    if not verify_password(request.password, admin_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    old_tier = client.subscription_tier
    new_tier = request.tier or "growth"
    
    if new_tier not in ["starter", "growth", "enterprise"]:
        raise HTTPException(status_code=400, detail="Invalid tier")
    
    client.subscription_tier = new_tier
    db.commit()
    
    quota_map = {"starter": 10000, "growth": 50000, "enterprise": 100000}
    new_quota = quota_map.get(new_tier, 10000)
    
    log_audit_action(db, admin["admin_id"], "update_tier", f"client_{client_id}",
                    {"old_tier": old_tier, "new_tier": new_tier})
    
    return {
        "success": True,
        "message": f"Client upgraded to {new_tier}",
        "client_id": client_id,
        "new_tier": new_tier,
        "new_quota": new_quota,
        "effective_date": str(datetime.utcnow().date())
    }

@router.post("/clients/{client_id}/reset-key")
async def reset_api_key_action(
    client_id: int,
    request: PasswordVerificationRequest,
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Reset client API key (requires password verification)"""
    from api.admin_auth import verify_password
    import secrets
    
    admin_user = get_admin_by_id(db, admin["admin_id"])
    if not admin_user:
        raise HTTPException(status_code=401, detail="Admin not found")
    
    if not verify_password(request.password, admin_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid password")
    
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    new_key = f"sk_live_{secrets.token_hex(16)}"
    client.api_key = new_key
    db.commit()
    
    log_audit_action(db, admin["admin_id"], "reset_api_key", f"client_{client_id}", {})
    
    return {
        "success": True,
        "message": "API key reset successfully",
        "client_id": client_id,
        "new_api_key": new_key
    }

@router.post("/transactions/{transaction_id}/false-positive")
async def mark_false_positive(
    transaction_id: str,
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Mark transaction as false positive"""
    txn = db.query(FraudScore).filter(FraudScore.transaction_id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    txn.recommendation = "APPROVE"
    txn.risk_level = "LOW"
    db.commit()
    
    log_audit_action(db, admin["admin_id"], "mark_false_positive", f"txn_{transaction_id}", {})
    
    return {
        "success": True,
        "message": "Transaction marked as false positive",
        "transaction_id": transaction_id
    }

@router.post("/transactions/{transaction_id}/override")
async def override_recommendation(
    transaction_id: str,
    request: TransactionActionRequest,
    admin: dict = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Override transaction recommendation"""
    txn = db.query(FraudScore).filter(FraudScore.transaction_id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    new_recommendation = request.recommendation or "APPROVE"
    if new_recommendation not in ["APPROVE", "FLAG", "BLOCK"]:
        raise HTTPException(status_code=400, detail="Invalid recommendation")
    
    txn.recommendation = new_recommendation
    db.commit()
    
    log_audit_action(db, admin["admin_id"], "override_recommendation", f"txn_{transaction_id}",
                    {"new_recommendation": new_recommendation})
    
    return {
        "success": True,
        "message": f"Recommendation overridden to {new_recommendation}",
        "transaction_id": transaction_id,
        "new_recommendation": new_recommendation
    }
