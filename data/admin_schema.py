from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

def create_admin_models(Base):
    """Create admin models with the provided Base"""
    
    class AdminUser(Base):
        __tablename__ = "admin_users"
        
        id = Column(Integer, primary_key=True, index=True)
        username = Column(String, unique=True, index=True)
        email = Column(String, unique=True, index=True)
        password_hash = Column(String)
        is_active = Column(Boolean, default=True)
        created_at = Column(DateTime, default=datetime.utcnow)
        last_login = Column(DateTime, nullable=True)
        
        audit_logs = relationship("AdminAuditLog", back_populates="admin")
        assigned_tickets = relationship("SupportTicket", back_populates="assigned_admin")

    class AdminAuditLog(Base):
        __tablename__ = "admin_audit_logs"
        
        id = Column(Integer, primary_key=True, index=True)
        admin_id = Column(Integer, ForeignKey("admin_users.id"))
        action = Column(String)
        resource = Column(String)
        details = Column(Text)
        timestamp = Column(DateTime, default=datetime.utcnow)
        ip_address = Column(String, nullable=True)
        
        admin = relationship("AdminUser", back_populates="audit_logs")

    class SupportTicket(Base):
        __tablename__ = "support_tickets"
        
        id = Column(Integer, primary_key=True, index=True)
        ticket_number = Column(String, unique=True, index=True)
        client_id = Column(Integer, ForeignKey("clients.id"))
        subject = Column(String)
        category = Column(String)
        priority = Column(String)
        status = Column(String, default="open")
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        assigned_to = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
        
        messages = relationship("TicketMessage", back_populates="ticket")
        assigned_admin = relationship("AdminUser", back_populates="assigned_tickets")

    class TicketMessage(Base):
        __tablename__ = "ticket_messages"
        
        id = Column(Integer, primary_key=True, index=True)
        ticket_id = Column(Integer, ForeignKey("support_tickets.id"))
        sender_type = Column(String)
        sender_id = Column(Integer)
        sender_name = Column(String)
        message = Column(Text)
        created_at = Column(DateTime, default=datetime.utcnow)
        
        ticket = relationship("SupportTicket", back_populates="messages")

    class SystemSettings(Base):
        __tablename__ = "system_settings"
        
        id = Column(Integer, primary_key=True, index=True)
        fraud_threshold_high = Column(Float, default=0.7)
        fraud_threshold_medium = Column(Float, default=0.4)
        model_retrain_schedule = Column(String, default="weekly")
        webhook_retries = Column(Integer, default=3)
        webhook_timeout_seconds = Column(Integer, default=30)
        rate_limit_per_client = Column(Integer, default=10000)
        rate_limit_period = Column(String, default="monthly")
        email_alerts_enabled = Column(Boolean, default=True)
        email_alert_on_uptime_drop = Column(Boolean, default=True)
        email_alert_on_error_spike = Column(Boolean, default=True)
        email_alert_on_fraud_spike = Column(Boolean, default=True)
        slack_enabled = Column(Boolean, default=False)
        slack_webhook_url = Column(String, nullable=True)
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    class ErrorLog(Base):
        __tablename__ = "error_logs"
        
        id = Column(Integer, primary_key=True, index=True)
        timestamp = Column(DateTime, default=datetime.utcnow, index=True)
        level = Column(String)
        message = Column(Text)
        service = Column(String)
        error_trace = Column(Text, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)

    class Invoice(Base):
        __tablename__ = "invoices"
        
        id = Column(Integer, primary_key=True, index=True)
        invoice_number = Column(String, unique=True, index=True)
        client_id = Column(Integer, ForeignKey("clients.id"))
        amount = Column(Float)
        date_issued = Column(DateTime, default=datetime.utcnow)
        due_date = Column(DateTime)
        status = Column(String, default="unpaid")
        paid_date = Column(DateTime, nullable=True)
        description = Column(Text)
        created_at = Column(DateTime, default=datetime.utcnow)

    class Payment(Base):
        __tablename__ = "payments"
        
        id = Column(Integer, primary_key=True, index=True)
        payment_date = Column(DateTime, default=datetime.utcnow)
        client_id = Column(Integer, ForeignKey("clients.id"))
        amount = Column(Float)
        payment_method = Column(String)
        payment_reference = Column(String, unique=True)
        status = Column(String, default="confirmed")
        invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)
    
    return {
        'AdminUser': AdminUser,
        'AdminAuditLog': AdminAuditLog,
        'SupportTicket': SupportTicket,
        'TicketMessage': TicketMessage,
        'SystemSettings': SystemSettings,
        'ErrorLog': ErrorLog,
        'Invoice': Invoice,
        'Payment': Payment
    }
