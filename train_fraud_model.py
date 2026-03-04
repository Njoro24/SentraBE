#!/usr/bin/env python3
"""
Sentra Fraud Detection - Improved Training Script
- Loads real Kaggle Credit Card Fraud data (data/creditcard.csv)
- Falls back to synthetic data if not found
- XGBoost added to ensemble
- SMOTE for class imbalance
- Better feature engineering
- 3-class: APPROVE | FLAG | BLOCK
"""

import numpy as np
import pandas as pd
import pickle
import json
import os
from datetime import datetime
from pathlib import Path

from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, VotingClassifier, IsolationForest
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import RobustScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, confusion_matrix,
    precision_score, recall_score, f1_score
)

try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("⚠ XGBoost not installed. Run: pip install xgboost")

try:
    import lightgbm as lgb
    from lightgbm import LGBMClassifier
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    print("⚠ LightGBM not installed. Run: pip install lightgbm")

try:
    from imblearn.over_sampling import SMOTE
    SMOTE_AVAILABLE = True
except ImportError:
    SMOTE_AVAILABLE = False
    print("⚠ imbalanced-learn not installed. Run: pip install imbalanced-learn")


# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
CREDITCARD_FILE         = "data/creditcard.csv"          # Kaggle mlg-ulb/creditcardfraud
KAGGLE_TRANSACTION_FILE = "data/train_transaction.csv"   # IEEE-CIS (alternative)
KAGGLE_IDENTITY_FILE    = "data/train_identity.csv"
OUTPUT_MODEL_PATH       = "fraud_model.pkl"
N_SYNTHETIC_SAMPLES     = 50_000


class FraudDetectionTrainer:

    def __init__(self):
        self.model = None
        self.iso_model = None
        self.scaler = None
        self.feature_names = []
        self.class_names = ['APPROVE', 'FLAG', 'BLOCK']
        self.eval_metrics = {}

    # ──────────────────────────────────────────
    # 1. DATA LOADING
    # ──────────────────────────────────────────
    def load_data(self):
        """Load Kaggle data if available, else generate synthetic data."""
        if os.path.exists(CREDITCARD_FILE):
            return self._load_creditcard_data()
        elif os.path.exists(KAGGLE_TRANSACTION_FILE):
            return self._load_ieee_data()
        else:
            print("⚠  No Kaggle data found. Using synthetic data.")
            print(f"   Place real data at: {CREDITCARD_FILE}")
            return self._generate_synthetic_data(N_SYNTHETIC_SAMPLES)

    def _load_creditcard_data(self):
        """Load Kaggle Credit Card Fraud dataset.
        Columns: Time, V1-V28 (PCA anonymized), Amount, Class
        Class: 0 = legit, 1 = fraud
        Maps to 3 classes using amount threshold:
          Class=0            -> APPROVE
          Class=1, Amt < 200 -> FLAG   (low-value fraud)
          Class=1, Amt >= 200-> BLOCK  (high-value fraud)
        """
        print(f"\n{'='*60}")
        print("LOADING KAGGLE CREDIT CARD FRAUD DATA")
        print(f"{'='*60}")

        df = pd.read_csv(CREDITCARD_FILE)
        print(f"✓ Loaded: {len(df):,} rows, {df.shape[1]} columns")
        print(f"  Fraud rate: {df['Class'].mean()*100:.3f}%")

        def assign_class(row):
            if row['Class'] == 0:
                return 0
            elif row['Amount'] < 200:
                return 1
            else:
                return 2

        df['tx_class'] = df.apply(assign_class, axis=1)
        df['amount']   = df['Amount']

        counts = df['tx_class'].value_counts().sort_index()
        total  = len(df)
        print(f"\n✓ 3-class distribution:")
        for i, name in enumerate(self.class_names):
            n = counts.get(i, 0)
            print(f"  • {name:8}: {n:,} ({n/total*100:.3f}%)")

        return df

    def _load_ieee_data(self):
        """Load IEEE-CIS Fraud Detection dataset."""
        print(f"\n{'='*60}")
        print("LOADING KAGGLE IEEE-CIS DATA")
        print(f"{'='*60}")

        df_tx = pd.read_csv(KAGGLE_TRANSACTION_FILE)
        print(f"✓ Transactions loaded: {len(df_tx):,} rows")

        if os.path.exists(KAGGLE_IDENTITY_FILE):
            df_id = pd.read_csv(KAGGLE_IDENTITY_FILE)
            df = df_tx.merge(df_id, on='TransactionID', how='left')
            print(f"✓ Identity merged: {df.shape[1]} total columns")
        else:
            df = df_tx

        df = df.dropna(subset=['isFraud', 'TransactionAmt'])
        df['amount'] = pd.to_numeric(df['TransactionAmt'], errors='coerce').fillna(0)

        def assign_class(row):
            if row['isFraud'] == 0:
                return 0
            elif row['amount'] < 500:
                return 1
            else:
                return 2

        df['tx_class'] = df.apply(assign_class, axis=1)
        counts = df['tx_class'].value_counts().sort_index()
        total  = len(df)
        print(f"\n✓ 3-class distribution:")
        for i, name in enumerate(self.class_names):
            n = counts.get(i, 0)
            print(f"  • {name:8}: {n:,} ({n/total*100:.3f}%)")
        return df

    def _generate_synthetic_data(self, n_samples):
        """Fallback: generate realistic synthetic transactions."""
        print(f"\n{'='*60}")
        print("GENERATING SYNTHETIC TRANSACTION DATA (3-CLASS)")
        print(f"{'='*60}")

        np.random.seed(42)
        high_risk   = ['Online Gambling', 'Money Transfer', 'Gift Cards', 'Crypto', 'Wire Transfer']
        medium_risk = ['Gas Station', 'ATM Withdrawal', 'Travel', 'Foreign Currency', 'Casino']
        low_risk    = ['Grocery', 'Restaurant', 'Gas', 'Pharmacy', 'Utilities', 'Supermarket']
        countries   = {'KE':0.02,'NG':0.05,'US':0.03,'CN':0.08,'RU':0.10,
                       'BR':0.07,'IN':0.04,'GB':0.02,'ZA':0.06,'PK':0.09}

        data = []
        for i in range(n_samples):
            hour        = np.random.randint(0, 24)
            day_of_week = np.random.randint(0, 7)
            rand        = np.random.random()

            if rand < 0.70:
                tx_class = 0
                amount   = np.random.lognormal(5.5, 1.5)
                distance = np.random.exponential(20)
                tx24h    = np.random.randint(1, 5)
                merchant = np.random.choice(low_risk)
                country  = 'KE' if np.random.random() < 0.7 else np.random.choice(list(countries.keys()))
                declined = 0
            elif rand < 0.85:
                tx_class = 1
                amount   = np.random.uniform(5000, 120000)
                distance = np.random.exponential(200)
                tx24h    = np.random.randint(3, 8)
                merchant = np.random.choice(medium_risk + high_risk[:2])
                country  = 'KE' if np.random.random() < 0.3 else np.random.choice(list(countries.keys()))
                declined = np.random.randint(0, 3)
            else:
                tx_class = 2
                amount   = np.random.uniform(100000, 500000)
                distance = np.random.exponential(500)
                tx24h    = np.random.randint(5, 50)
                merchant = np.random.choice(high_risk)
                probs    = np.array(list(countries.values()))
                probs    = probs / probs.sum()
                country  = np.random.choice(list(countries.keys()), p=probs)
                declined = np.random.randint(1, 5)

            is_foreign    = int(country != 'KE')
            merchant_risk = (0.85 if merchant in high_risk else 0.50 if merchant in medium_risk else 0.15)
            data.append({
                'amount': amount,
                'distance_from_home_km': distance,
                'hours_since_midnight': hour,
                'day_of_week': day_of_week,
                'is_weekend': int(day_of_week >= 5),
                'is_night': int(hour < 6 or hour > 22),
                'merchant_risk_score': merchant_risk + np.random.uniform(-0.1, 0.1),
                'is_foreign': is_foreign,
                'country_fraud_rate': countries[country],
                'transaction_count_24h': tx24h,
                'transaction_count_7d': tx24h * np.random.uniform(2, 5),
                'amount_sum_24h': amount * tx24h * np.random.uniform(0.5, 1.5),
                'days_since_last_transaction': np.random.randint(0, 30),
                'unique_merchants_24h': np.random.randint(1, 10),
                'declined_attempts_24h': declined,
                'device_is_new': int(tx_class > 0 and np.random.random() < 0.6),
                'ip_is_vpn': int(tx_class > 0 and np.random.random() < 0.5),
                'age_days': np.random.randint(1, 3650),
                'tx_class': tx_class
            })

        df = pd.DataFrame(data)
        counts = df['tx_class'].value_counts().sort_index()
        print(f"✓ Generated {n_samples:,} transactions")
        for i, name in enumerate(self.class_names):
            n = counts.get(i, 0)
            print(f"  • {name:8}: {n:,} ({n/n_samples*100:.2f}%)")
        return df

    # ──────────────────────────────────────────
    # 2. FEATURE ENGINEERING
    # ──────────────────────────────────────────
    def engineer_features(self, df):
        print(f"\n{'='*60}")
        print("FEATURE ENGINEERING")
        print(f"{'='*60}")

        df = df.copy()

        # Amount features
        if 'amount' not in df.columns and 'Amount' in df.columns:
            df['amount'] = df['Amount']

        df['log_amount'] = np.log1p(df['amount'].clip(lower=0))
        df['amount_bin'] = pd.cut(df['amount'], bins=[0,100,1000,10000,np.inf], labels=[0,1,2,3]).astype(float)
        df['amount_sqrt']= df['amount'].clip(lower=0) ** 0.5

        # Time features (creditcard.csv: Time in seconds from first transaction)
        if 'Time' in df.columns:
            df['hours_since_midnight'] = (df['Time'] // 3600) % 24
            df['day_of_week']          = (df['Time'] // 86400) % 7
            df['is_night']             = ((df['hours_since_midnight'] < 6) | (df['hours_since_midnight'] > 22)).astype(int)
            df['is_weekend']           = (df['day_of_week'] >= 5).astype(int)

        # V-columns: aggregate PCA features (creditcard.csv has V1-V28)
        v_cols = [c for c in df.columns if c.startswith('V') and pd.api.types.is_numeric_dtype(df[c])]
        if v_cols:
            df['v_sum']     = df[v_cols].sum(axis=1)
            df['v_mean']    = df[v_cols].mean(axis=1)
            df['v_std']     = df[v_cols].std(axis=1)
            df['v_min']     = df[v_cols].min(axis=1)
            df['v_max']     = df[v_cols].max(axis=1)
            df['v_nonzero'] = (df[v_cols] != 0).sum(axis=1)
            print(f"  ✓ Aggregated {len(v_cols)} PCA V-features → 6 summary stats")

        # Synthetic data features
        if 'distance_from_home_km' in df.columns:
            df['log_distance'] = np.log1p(df['distance_from_home_km'].clip(lower=0))

        if 'transaction_count_24h' in df.columns:
            df['log_tx_count_24h'] = np.log1p(df['transaction_count_24h'])

        if all(c in df.columns for c in ['transaction_count_24h', 'days_since_last_transaction']):
            df['velocity_ratio'] = df['transaction_count_24h'] / (df['days_since_last_transaction'] + 1)

        if all(c in df.columns for c in ['merchant_risk_score', 'log_amount']):
            df['merchant_amount_risk'] = df['merchant_risk_score'] * df['log_amount']

        if all(c in df.columns for c in ['country_fraud_rate', 'is_foreign']):
            df['geographic_risk'] = df['country_fraud_rate'] * df['is_foreign']

        if all(c in df.columns for c in ['device_is_new', 'ip_is_vpn']):
            df['device_risk'] = df['device_is_new'] * df['ip_is_vpn']

        if all(c in df.columns for c in ['declined_attempts_24h', 'transaction_count_24h']):
            df['decline_rate'] = df['declined_attempts_24h'] / (df['transaction_count_24h'] + 1)

        # Drop non-feature columns
        drop_cols = ['tx_class', 'Class', 'TransactionID', 'isFraud',
                     'TransactionAmt', 'Time', 'Amount']
        drop_cols += [c for c in df.columns if df[c].dtype == object]

        feature_df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors='ignore')
        feature_df = feature_df.select_dtypes(include=[np.number])
        feature_df = feature_df.fillna(feature_df.median())

        self.feature_names = list(feature_df.columns)
        print(f"✓ Total features: {len(self.feature_names)}")

        return feature_df, df['tx_class']

    # ──────────────────────────────────────────
    # 3. SMOTE
    # ──────────────────────────────────────────
    def apply_smote(self, X_train, y_train):
        if not SMOTE_AVAILABLE:
            print("⚠  SMOTE skipped")
            return X_train, y_train

        print(f"\n{'='*60}")
        print("APPLYING SMOTE (Class Balancing)")
        print(f"{'='*60}")

        print("Before SMOTE:")
        for i, name in enumerate(self.class_names):
            n = (y_train == i).sum()
            print(f"  • {name}: {n:,}")

        min_samples = min((y_train == i).sum() for i in range(3))
        k = min(5, min_samples - 1)
        if k < 1:
            print("⚠  Not enough minority samples. Skipping SMOTE.")
            return X_train, y_train

        # Cap target to avoid blowing up training time on real imbalanced data
        majority_count = max((y_train == i).sum() for i in range(3))
        target = min(min_samples * 10, majority_count // 10)
        target = max(target, min_samples)
        sampling_strategy = {i: target for i in range(3) if (y_train == i).sum() < target}
        print(f"  (Capped SMOTE target per minority class: {target:,})")

        sm = SMOTE(random_state=42, k_neighbors=k, sampling_strategy=sampling_strategy)
        X_res, y_res = sm.fit_resample(X_train, y_train)

        print("After SMOTE:")
        for i, name in enumerate(self.class_names):
            n = (y_res == i).sum()
            print(f"  • {name}: {n:,}")

        return X_res, y_res

    # ──────────────────────────────────────────
    # 4. MODEL TRAINING
    # ──────────────────────────────────────────
    def train_ensemble_model(self, X_train, y_train):
        print(f"\n{'='*60}")
        print("TRAINING ENSEMBLE MODEL (3-CLASS)")
        print(f"{'='*60}")

        estimators = []
        weights     = []

        if LIGHTGBM_AVAILABLE:
            print("• Training LightGBM (fast gradient boosting)...")
            lgbm = LGBMClassifier(
                n_estimators=200, learning_rate=0.05, max_depth=6,
                num_leaves=31, subsample=0.8, colsample_bytree=0.8,
                min_child_samples=20, random_state=42, n_jobs=8,
                verbose=-1
            )
            lgbm.fit(X_train, y_train)
            estimators.append(('lgbm', lgbm))
            weights.append(0.4)
            print("  ✓ LightGBM trained")
        else:
            print("• Training Gradient Boosting (slow fallback)...")
            gb = GradientBoostingClassifier(
                n_estimators=50, learning_rate=0.05, max_depth=3,
                min_samples_split=10, subsample=0.8, random_state=42
            )
            gb.fit(X_train, y_train)
            estimators.append(('gb', gb))
            weights.append(0.4)

        print("• Training Random Forest...")
        rf = RandomForestClassifier(
            n_estimators=100, max_depth=8, min_samples_split=10,
            max_features='sqrt', random_state=42, n_jobs=8
        )
        rf.fit(X_train, y_train)
        estimators.append(('rf', rf))
        weights.append(0.3)

        if XGBOOST_AVAILABLE:
            print("• Training XGBoost...")
            xgb = XGBClassifier(
                n_estimators=100, max_depth=4, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8,
                eval_metric='mlogloss', random_state=42, n_jobs=8
            )
            xgb.fit(X_train, y_train)
            estimators.append(('xgb', xgb))
            weights.append(0.3)

        print("• Training Isolation Forest...")
        self.iso_model = IsolationForest(
            n_estimators=50, contamination=0.015, random_state=42, n_jobs=-1
        )
        self.iso_model.fit(X_train)

        print("• Creating Voting Ensemble...")
        voting = VotingClassifier(estimators=estimators, voting='soft', weights=weights)
        voting.fit(X_train, y_train)

        print("• Calibrating probabilities (cv=2)...")
        calibrated = CalibratedClassifierCV(voting, method='sigmoid', cv=2)
        calibrated.fit(X_train, y_train)

        self.model = calibrated
        print(f"✓ Ensemble trained: {[e[0] for e in estimators]} + calibration")
        return calibrated

    # ──────────────────────────────────────────
    # 5. EVALUATION
    # ──────────────────────────────────────────
    def evaluate_model(self, X_test, y_test):
        print(f"\n{'='*60}")
        print("MODEL EVALUATION (3-CLASS)")
        print(f"{'='*60}")

        y_pred    = self.model.predict(X_test)
        accuracy  = float((y_pred == y_test).mean())
        precision = float(precision_score(y_test, y_pred, average='macro', zero_division=0))
        recall    = float(recall_score(y_test, y_pred, average='macro', zero_division=0))
        f1        = float(f1_score(y_test, y_pred, average='macro', zero_division=0))

        print(f"\nOVERALL ACCURACY : {accuracy:.4f}")
        print(f"MACRO PRECISION  : {precision:.4f}")
        print(f"MACRO RECALL     : {recall:.4f}")
        print(f"MACRO F1         : {f1:.4f}")

        print(f"\nPER-CLASS METRICS:")
        for i, name in enumerate(self.class_names):
            mask = y_test == i
            if mask.sum() > 0:
                prec = float(precision_score(y_test == i, y_pred == i, zero_division=0))
                rec  = float(recall_score(y_test == i, y_pred == i, zero_division=0))
                f1c  = float(f1_score(y_test == i, y_pred == i, zero_division=0))
                print(f"  {name:8} — Precision: {prec:.4f}  Recall: {rec:.4f}  F1: {f1c:.4f}")

        print(f"\nCONFUSION MATRIX:")
        cm = confusion_matrix(y_test, y_pred)
        print(f"{'':12} {'APPROVE':>8} {'FLAG':>8} {'BLOCK':>8}")
        for i, name in enumerate(self.class_names):
            row  = cm[i] if i < len(cm) else [0, 0, 0]
            vals = [int(row[j]) if j < len(row) else 0 for j in range(3)]
            print(f"  {name:10} {vals[0]:>8} {vals[1]:>8} {vals[2]:>8}")

        print(f"\nDETAILED REPORT:")
        print(classification_report(y_test, y_pred, target_names=self.class_names, zero_division=0))

        self.eval_metrics = {
            'overall_accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_macro': f1,
            'class_names': self.class_names,
            'confusion_matrix': cm.tolist(),
            'trained_at': datetime.now().isoformat()
        }

    # ──────────────────────────────────────────
    # 6. SAVE
    # ──────────────────────────────────────────
    def save_model(self, path=OUTPUT_MODEL_PATH):
        print(f"\n{'='*60}")
        print("SAVING MODEL")
        print(f"{'='*60}")

        model_data = {
            'model': self.model,
            'iso_model': self.iso_model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'class_names': self.class_names,
            'eval_metrics': self.eval_metrics,
            'trained_at': datetime.now().isoformat()
        }

        with open(path, 'wb') as f:
            pickle.dump(model_data, f)

        size_kb = Path(path).stat().st_size / 1024
        print(f"✓ Model saved  : {path}  ({size_kb:.1f} KB)")

        metrics_path = path.replace('.pkl', '_metrics.json')
        with open(metrics_path, 'w') as f:
            json.dump(self.eval_metrics, f, indent=2)
        print(f"✓ Metrics saved: {metrics_path}")

    # ──────────────────────────────────────────
    # MAIN PIPELINE
    # ──────────────────────────────────────────
    def train(self):
        print(f"\n{'#'*60}")
        print("# SENTRA FRAUD DETECTION - IMPROVED TRAINING")
        print("# Classes: APPROVE | FLAG | BLOCK")
        print(f"{'#'*60}")
        print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        df               = self.load_data()
        X, y             = self.engineer_features(df)
        y                = y.values if hasattr(y, 'values') else np.array(y)

        self.scaler      = RobustScaler()
        X_scaled         = self.scaler.fit_transform(X)

        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42, stratify=y
        )
        print(f"\nTrain: {len(X_train):,}  |  Test: {len(X_test):,}")

        X_train, y_train = self.apply_smote(X_train, y_train)
        self.train_ensemble_model(X_train, y_train)
        self.evaluate_model(X_test, y_test)
        self.save_model()

        print(f"\n{'#'*60}")
        print("# TRAINING COMPLETE")
        print(f"{'#'*60}")
        print(f"End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return self.model


if __name__ == "__main__":
    trainer = FraudDetectionTrainer()
    trainer.train()