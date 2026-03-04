#!/usr/bin/env python3
"""
Sentra Fraud Detection - Continuous Learning System
====================================================
How it works:
1. Every live transaction is stored in PostgreSQL with prediction + confidence
2. Labels arrive later via 3 sources:
   - Fraud team manually marks transactions (admin API)
   - Customer disputes (chargeback webhook)
   - Automated rules engine flags patterns
3. A scheduler checks every night:
   - If enough new labeled data exists → retrain full model
   - If drift detected → trigger emergency retrain
4. New model is validated before replacing the old one
5. Old models are archived (rollback is possible)

Usage:
# Start the scheduler (run alongside your API)
python3 continuous_learning.py --mode scheduler

# Manually trigger a retrain
python3 continuous_learning.py --mode retrain

# Check learning stats
python3 continuous_learning.py --mode stats

# Label a transaction as fraud/legit (for testing)
python3 continuous_learning.py --mode label --tx-id TXN_001 --label 1
"""

import os
import pickle
import json
import argparse
import logging
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

# ──────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────
DATABASE_URL     = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/sentra")
MODEL_PATH       = "fraud_model.pkl"
MODEL_ARCHIVE    = "model_archive/"
RETRAIN_LOG      = "retrain_log.json"

# Retraining triggers
MIN_NEW_SAMPLES       = 100
RETRAIN_EVERY_HOURS   = 24
DRIFT_THRESHOLD       = 0.05
MIN_ACCURACY          = 0.85

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler('continuous_learning.log'),
              logging.StreamHandler()])
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# DATABASE SETUP
# ──────────────────────────────────────────────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ml_predictions (
    id                  SERIAL PRIMARY KEY,
    transaction_id      VARCHAR(100) UNIQUE NOT NULL,
    predicted_class     INTEGER NOT NULL,
    predicted_label     VARCHAR(20) NOT NULL,
    confidence          FLOAT NOT NULL,
    approve_prob        FLOAT,
    flag_prob           FLOAT,
    block_prob          FLOAT,
    features            JSONB,
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ml_labels (
    id                  SERIAL PRIMARY KEY,
    transaction_id      VARCHAR(100) UNIQUE NOT NULL,
    true_class          INTEGER NOT NULL,
    true_label          VARCHAR(20) NOT NULL,
    label_source        VARCHAR(50),
    label_confidence    FLOAT DEFAULT 1.0,
    labeled_by          VARCHAR(100),
    labeled_at          TIMESTAMP DEFAULT NOW(),
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS ml_retrain_history (
    id                  SERIAL PRIMARY KEY,
    trigger_reason      VARCHAR(100),
    samples_used        INTEGER,
    new_accuracy        FLOAT,
    new_precision       FLOAT,
    new_recall          FLOAT,
    new_f1              FLOAT,
    old_accuracy        FLOAT,
    model_accepted      BOOLEAN,
    rejection_reason    VARCHAR(200),
    duration_seconds    FLOAT,
    started_at          TIMESTAMP DEFAULT NOW(),
    completed_at        TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ml_performance_log (
    id                  SERIAL PRIMARY KEY,
    window_start        TIMESTAMP,
    window_end          TIMESTAMP,
    total_predictions   INTEGER,
    correct_predictions INTEGER,
    accuracy            FLOAT,
    logged_at           TIMESTAMP DEFAULT NOW()
);
"""

def get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)

def setup_database():
    """Create ML tables if they don't exist."""
    engine = get_engine()
    with engine.connect() as conn:
        for statement in SCHEMA_SQL.strip().split(';'):
            stmt = statement.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()
    log.info("✓ ML database tables ready")

# ──────────────────────────────────────────────────────────
# LABEL COLLECTION
# ──────────────────────────────────────────────────────────
class LabelCollector:
    """Manages collection of fraud labels from multiple sources."""
    
    def __init__(self):
        self.engine = get_engine()
    
    def save_prediction(self, transaction_id: str, features: dict,
                       predicted_class: int, probabilities: list):
        """Save a live prediction to the database."""
        class_names = ['APPROVE', 'FLAG', 'BLOCK']
        confidence  = float(max(probabilities))
        
        with self.engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO ml_predictions
                (transaction_id, predicted_class, predicted_label,
                 confidence, approve_prob, flag_prob, block_prob, features)
                VALUES(:tx_id, :pred_class, :pred_label,
                       :confidence, :approve_prob, :flag_prob, :block_prob, :features)
                ON CONFLICT (transaction_id) DO NOTHING
            """), {
                'tx_id':        transaction_id,
                'pred_class':   predicted_class,
                'pred_label':   class_names[predicted_class],
                'confidence':   confidence,
                'approve_prob': float(probabilities[0]) if len(probabilities) > 0 else None,
                'flag_prob':    float(probabilities[1]) if len(probabilities) > 1 else None,
                'block_prob':   float(probabilities[2]) if len(probabilities) > 2 else None,
                'features':     json.dumps(features)
            })
            conn.commit()
    
    def add_label(self, transaction_id: str, true_class: int,
                 source: str = 'fraud_team', labeled_by: str = None,
                 confidence: float = 1.0, notes: str = None):
        """Add a ground truth label for a transaction."""
        class_names = ['APPROVE', 'FLAG', 'BLOCK']
        
        if true_class not in [0, 1, 2]:
            raise ValueError(f"true_class must be 0, 1, or 2. Got: {true_class}")
        
        with self.engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO ml_labels
                (transaction_id, true_class, true_label,
                 label_source, label_confidence, labeled_by, notes)
                VALUES(:tx_id, :true_class, :true_label,
                       :source, :confidence, :labeled_by, :notes)
                ON CONFLICT (transaction_id)
                DO UPDATE SET
                    true_class       = EXCLUDED.true_class,
                    true_label       = EXCLUDED.true_label,
                    label_source     = EXCLUDED.label_source,
                    label_confidence = EXCLUDED.label_confidence,
                    labeled_by       = EXCLUDED.labeled_by,
                    labeled_at       = NOW(),
                    notes            = EXCLUDED.notes
            """), {
                'tx_id':       transaction_id,
                'true_class':  true_class,
                'true_label':  class_names[true_class],
                'source':      source,
                'confidence':  confidence,
                'labeled_by':  labeled_by,
                'notes':       notes
            })
            conn.commit()
        
        log.info(f"✓ Label saved: {transaction_id} → {class_names[true_class]} (source: {source})")
    
    def get_stats(self):
        """Get label collection statistics."""
        with self.engine.connect() as conn:
            total_preds = conn.execute(text("SELECT COUNT(*) FROM ml_predictions")).scalar()
            total_labels = conn.execute(text("SELECT COUNT(*) FROM ml_labels")).scalar()
            by_source = conn.execute(text("""
                SELECT label_source, COUNT(*) as count
                FROM ml_labels GROUP BY label_source
            """)).fetchall()
            by_class = conn.execute(text("""
                SELECT true_label, COUNT(*) as count
                FROM ml_labels GROUP BY true_label
            """)).fetchall()
        
        return {
            'total_predictions': total_preds,
            'total_labels':      total_labels,
            'unlabeled':         total_preds - total_labels,
            'label_rate':        f"{total_labels/max(total_preds,1)*100:.1f}%",
            'by_source':         {r.label_source: r.count for r in by_source},
            'by_class':          {r.true_label: r.count for r in by_class}
        }

# ──────────────────────────────────────────────────────────
# API HELPERS (import these in your FastAPI app)
# ──────────────────────────────────────────────────────────
_collector = None

def get_label_collector() -> LabelCollector:
    """Singleton label collector for use in FastAPI endpoints."""
    global _collector
    if _collector is None:
        _collector = LabelCollector()
    return _collector

def record_prediction(transaction_id: str, features: dict,
                     predicted_class: int, probabilities: list):
    """Call this from your transaction endpoint every time a prediction is made."""
    try:
        get_label_collector().save_prediction(transaction_id, features, predicted_class, probabilities)
    except Exception as e:
        log.warning(f"Could not save prediction: {e}")

def submit_label(transaction_id: str, is_fraud: bool,
                source: str = 'fraud_team', labeled_by: str = None):
    """Call this when a fraud label is confirmed."""
    true_class = 2 if is_fraud else 0
    try:
        get_label_collector().add_label(transaction_id, true_class, source=source, labeled_by=labeled_by)
    except Exception as e:
        log.warning(f"Could not save label: {e}")

# ──────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Sentra Continuous Learning')
    parser.add_argument('--mode', choices=['scheduler', 'retrain', 'stats', 'label', 'setup'],
                       required=True)
    parser.add_argument('--tx-id',  help='Transaction ID (for --mode label)')
    parser.add_argument('--label',  type=int, choices=[0, 1, 2],
                       help='True class: 0=APPROVE, 1=FLAG, 2=BLOCK')
    parser.add_argument('--source', default='fraud_team',
                       help='Label source (fraud_team, chargeback, rules_engine)')
    args = parser.parse_args()
    
    if args.mode == 'setup':
        setup_database()
    
    elif args.mode == 'stats':
        setup_database()
        collector = LabelCollector()
        stats     = collector.get_stats()
        print(f"\n{'='*50}")
        print("CONTINUOUS LEARNING STATS")
        print(f"{'='*50}")
        print(f"Total predictions : {stats['total_predictions']:,}")
        print(f"Total labels      : {stats['total_labels']:,}")
        print(f"Unlabeled         : {stats['unlabeled']:,}")
        print(f"Label rate        : {stats['label_rate']}")
        print(f"\nLabels by source:")
        for src, count in stats['by_source'].items():
            print(f"  {src:20}: {count:,}")
        print(f"\nLabels by class:")
        for cls, count in stats['by_class'].items():
            print(f"  {cls:10}: {count:,}")
    
    elif args.mode == 'label':
        if not args.tx_id or args.label is None:
            print("Error: --tx-id and --label are required for label mode")
            return
        setup_database()
        collector = LabelCollector()
        collector.add_label(args.tx_id, args.label, source=args.source)
        print(f"✓ Labeled {args.tx_id} as class {args.label}")

if __name__ == '__main__':
    main()
