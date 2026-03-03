from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

# ============ AUTH MODELS ============
class AdminLoginRequest(BaseModel):
    username: str
    password: str

class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str
    admin_id: int
    username: str
    email: str

class AdminProfile(BaseModel):
    admin_id: int
    username: str
    email: str
    created_at: datetime
    last_login: Optional[datetime]

# ============ SYSTEM HEALTH MODELS ============
class SystemHealthResponse(BaseModel):
    uptime_percentage: float
    current_response_time_ms: float
    server_status: str
    database_connected: bool
    kafka_status: str
    kafka_lag: int
    storage_used_gb: float
    storage_total_gb: float
    storage_percentage: float
    error_rate_percentage: float
    active_connections: int
    timestamp: datetime

class ErrorLogEntry(BaseModel):
    timestamp: datetime
    level: str
    message: str
    service: str
    error_trace: Optional[str]
    count: int

class ErrorLogsResponse(BaseModel):
    logs: List[ErrorLogEntry]
    total: int
    limit: int

# ============ METRICS MODELS ============
class DailyMetricsResponse(BaseModel):
    date: str
    transactions_today: int
    fraud_detected_today: int
    fraud_percentage: float
    revenue_today: float
    active_clients_today: int
    api_errors_today: int
    avg_response_time_ms: float
    timestamp: datetime

class HistoricalMetricPoint(BaseModel):
    date: str
    transactions: int
    fraud_detected: int
    fraud_percentage: float
    revenue: float

class HistoricalMetricsResponse(BaseModel):
    metrics: List[HistoricalMetricPoint]
    period: str

# ============ CLIENT MODELS ============
class ClientSummary(BaseModel):
    id: int
    name: str
    email: str
    subscription_tier: str
    status: str
    transactions_this_month: int
    api_calls_this_month: int
    quota_limit: int
    usage_percentage: float
    payment_status: str
    last_payment_date: Optional[datetime]
    next_billing_date: Optional[datetime]
    created_at: datetime
    last_login: Optional[datetime]

class ClientsListResponse(BaseModel):
    clients: List[ClientSummary]
    total: int
    page: int
    limit: int

class TeamMember(BaseModel):
    id: int
    email: str
    name: str
    role: str

class RecentTransaction(BaseModel):
    transaction_id: str
    amount: float
    risk_level: str
    timestamp: datetime

class ClientDetailsResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    company: str
    address: Optional[str]
    subscription_tier: str
    status: str
    api_key: str
    transactions_this_month: int
    api_calls_this_month: int
    quota_limit: int
    storage_used_gb: float
    payment_status: str
    invoice_address: Optional[str]
    created_at: datetime
    last_login: Optional[datetime]
    team_members: List[TeamMember]
    recent_transactions: List[RecentTransaction]

class SuspendClientRequest(BaseModel):
    reason: str

class SuspendClientResponse(BaseModel):
    success: bool
    message: str
    client_id: int
    api_key_revoked: bool

class UpdateClientTierRequest(BaseModel):
    tier: str
    effective_date: Optional[str]

class UpdateClientTierResponse(BaseModel):
    success: bool
    message: str
    client_id: int
    new_tier: str
    new_quota: int
    effective_date: str

class ResetAPIKeyResponse(BaseModel):
    success: bool
    message: str
    client_id: int
    new_api_key: str

# ============ REVENUE MODELS ============
class TierBreakdown(BaseModel):
    count: int
    price_per_month: float
    revenue: float

class RevenueSummaryResponse(BaseModel):
    mrr: float
    breakdown: Dict[str, TierBreakdown]
    total_lifetime_revenue: float
    active_subscriptions: int
    overdue_invoices: int
    overdue_amount: float
    this_month_revenue: float
    last_month_revenue: float
    growth_percentage: float

class InvoiceItem(BaseModel):
    description: str
    quantity: int
    unit_price: float
    total: float

class InvoiceSummary(BaseModel):
    id: int
    invoice_number: str
    client_id: int
    client_name: str
    amount: float
    date_issued: datetime
    due_date: datetime
    status: str
    paid_date: Optional[datetime]
    items: List[InvoiceItem]

class InvoicesResponse(BaseModel):
    invoices: List[InvoiceSummary]
    total: int
    page: int
    limit: int

class PaymentRecord(BaseModel):
    id: int
    payment_date: datetime
    client_id: int
    client_name: str
    amount: float
    payment_method: str
    payment_reference: str
    status: str
    invoice_id: Optional[int]

class PaymentsResponse(BaseModel):
    payments: List[PaymentRecord]
    total: int
    page: int

# ============ FRAUD ANALYTICS MODELS ============
class FraudStatsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    model_accuracy: float
    false_positive_rate: float
    false_negative_rate: float
    roc_auc: float
    precision: float
    recall: float
    total_transactions_evaluated: int
    total_fraud_detected: int
    fraud_percentage: float
    average_fraud_amount: float
    largest_fraud: float
    total_fraud_prevented: float
    model_version: str
    last_retrain_date: datetime
    model_performance_trend: str

class ClientFraudData(BaseModel):
    client_id: int
    client_name: str
    transactions: int
    fraud_detected: int
    fraud_rate: float
    fraud_percentage: float

class FraudByClientResponse(BaseModel):
    clients: List[ClientFraudData]

class CountryFraudData(BaseModel):
    country: str
    transactions: int
    fraud_detected: int
    fraud_rate: float
    fraud_percentage: float

class FraudByCountryResponse(BaseModel):
    countries: List[CountryFraudData]

class TopMerchant(BaseModel):
    merchant: str
    fraud_count: int
    fraud_rate: float

class FraudPatternsResponse(BaseModel):
    top_fraud_hours: List[int]
    top_fraud_days: List[str]
    peak_fraud_hour: int
    peak_fraud_day: str
    top_fraud_merchants: List[TopMerchant]

# ============ TRANSACTION MODELS ============
class TransactionRecord(BaseModel):
    transaction_id: str
    client_id: int
    client_name: str
    amount: float
    risk_score: float
    risk_level: str
    recommendation: str
    merchant_category: Optional[str]
    location: Optional[str]
    device_id: Optional[str]
    timestamp: datetime
    processing_time_ms: float
    status: str

class TransactionsResponse(BaseModel):
    transactions: List[TransactionRecord]
    total_in_period: int
    total_high_risk: int

class SignalBreakdown(BaseModel):
    velocity: float
    amount_anomaly: float
    device_new: float
    location_change: float

class TransactionDetailsResponse(BaseModel):
    transaction_id: str
    client_id: int
    client_name: str
    amount: float
    phone_number: Optional[str]
    merchant_category: Optional[str]
    location: Optional[str]
    device_id: Optional[str]
    country: Optional[str]
    risk_score: float
    risk_level: str
    recommendation: str
    signals: SignalBreakdown
    processing_time_ms: float
    timestamp: datetime
    fraud_indicators: List[str]

# ============ SUPPORT TICKET MODELS ============
class TicketSummary(BaseModel):
    id: int
    ticket_number: str
    client_id: int
    client_name: str
    subject: str
    category: str
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    assigned_to: Optional[str]
    last_message_preview: Optional[str]

class TicketsResponse(BaseModel):
    tickets: List[TicketSummary]
    total: int
    page: int

class TicketMessage(BaseModel):
    id: int
    sender_type: str
    sender_name: str
    message: str
    timestamp: datetime

class TicketDetailsResponse(BaseModel):
    id: int
    ticket_number: str
    client_id: int
    client_name: str
    subject: str
    category: str
    priority: str
    status: str
    created_at: datetime
    messages: List[TicketMessage]

class ReplyToTicketRequest(BaseModel):
    message: str

class ReplyToTicketResponse(BaseModel):
    success: bool
    message_id: int
    ticket_id: int
    timestamp: datetime

class UpdateTicketStatusRequest(BaseModel):
    status: str

class UpdateTicketStatusResponse(BaseModel):
    success: bool
    ticket_id: int
    status: str

# ============ SETTINGS MODELS ============
class SettingsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    fraud_threshold_high: float
    fraud_threshold_medium: float
    model_retrain_schedule: str
    model_last_retrain: Optional[datetime]
    model_next_retrain: Optional[datetime]
    webhook_retries: int
    webhook_timeout_seconds: int
    rate_limit_per_client: int
    rate_limit_period: str
    email_alerts_enabled: bool
    email_alert_on_uptime_drop: bool
    email_alert_on_error_spike: bool
    email_alert_on_fraud_spike: bool
    slack_enabled: bool
    slack_webhook_url: Optional[str]

class UpdateSettingsRequest(BaseModel):
    fraud_threshold_high: Optional[float] = None
    fraud_threshold_medium: Optional[float] = None
    model_retrain_schedule: Optional[str] = None
    webhook_retries: Optional[int] = None
    webhook_timeout_seconds: Optional[int] = None
    rate_limit_per_client: Optional[int] = None
    email_alerts_enabled: Optional[bool] = None
    email_alert_on_uptime_drop: Optional[bool] = None
    email_alert_on_error_spike: Optional[bool] = None
    email_alert_on_fraud_spike: Optional[bool] = None
    slack_enabled: Optional[bool] = None
    slack_webhook_url: Optional[str] = None

class UpdateSettingsResponse(BaseModel):
    success: bool
    message: str
    settings: SettingsResponse

# ============ ERROR MODELS ============
class ErrorResponse(BaseModel):
    detail: str
