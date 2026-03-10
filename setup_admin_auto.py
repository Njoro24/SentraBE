#!/usr/bin/env python3
"""
Auto setup script to initialize admin user and database tables
Run this once after deployment
"""

import sys
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.schema import engine, Base, SessionLocal, init_db, admin_models
from api.admin_auth import hash_password

AdminUser = admin_models['AdminUser']
SystemSettings = admin_models['SystemSettings']

def setup_database():
    """Create all database tables"""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created successfully")

def create_admin_user(username: str, email: str, password: str):
    """Create an admin user"""
    db = SessionLocal()
    try:
        # Check if admin already exists
        existing = db.query(AdminUser).filter(AdminUser.username == username).first()
        if existing:
            print(f"✗ Admin user '{username}' already exists")
            return False
        
        # Create new admin
        hashed_password = hash_password(password)
        admin = AdminUser(
            username=username,
            email=email,
            password_hash=hashed_password,
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add(admin)
        db.commit()
        print(f"✓ Admin user '{username}' created successfully")
        print(f"  Email: {email}")
        return True
    except Exception as e:
        print(f"✗ Error creating admin user: {str(e)}")
        return False
    finally:
        db.close()

def create_default_settings():
    """Create default system settings"""
    db = SessionLocal()
    try:
        # Check if settings already exist
        existing = db.query(SystemSettings).first()
        if existing:
            print("✓ System settings already exist")
            return True
        
        # Create default settings
        settings = SystemSettings(
            fraud_threshold_high=0.7,
            fraud_threshold_medium=0.4,
            model_retrain_schedule="weekly",
            webhook_retries=3,
            webhook_timeout_seconds=30,
            rate_limit_per_client=10000,
            rate_limit_period="monthly",
            email_alerts_enabled=True,
            email_alert_on_uptime_drop=True,
            email_alert_on_error_spike=True,
            email_alert_on_fraud_spike=True,
            slack_enabled=False,
            slack_webhook_url=None
        )
        db.add(settings)
        db.commit()
        print("✓ Default system settings created")
        return True
    except Exception as e:
        print(f"✗ Error creating settings: {str(e)}")
        return False
    finally:
        db.close()

def main():
    """Main setup function"""
    print("\n" + "="*50)
    print("Sentra Admin Setup (Auto)")
    print("="*50 + "\n")
    
    # Get credentials from environment
    username = os.getenv("ADMIN_USERNAME", "admin")
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")
    
    if not email or not password:
        print("✗ Error: ADMIN_EMAIL and ADMIN_PASSWORD environment variables required")
        print("  Set these in your .env file before running this script")
        return
    
    # Create tables
    setup_database()
    
    # Create default settings
    create_default_settings()
    
    # Create admin user
    print("\nCreating admin user...")
    
    if create_admin_user(username, email, password):
        print("\n" + "="*50)
        print("Setup completed successfully!")
        print("="*50)
        print(f"\nYou can now login with:")
        print(f"  Username: {username}")
        print(f"  Email: {email}")
        print(f"\nAPI Endpoint: POST /api/admin/login")
        print("="*50 + "\n")
    else:
        print("\n✗ Setup failed")

if __name__ == "__main__":
    main()
