#!/usr/bin/env python3
"""
SENTRA FRAUD DETECTION MODEL - PRODUCTION TRAINING
Real-world transaction patterns, advanced feature engineering, ensemble methods
"""

import numpy as np
import pandas as pd
import pickle
import warnings
from datetime import datetime, timedelta
import json
from pathlib import Path

# ML Libraries
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.ensemble import (
    RandomForestClassifier,
    GradientBoostingClassifier,
    IsolationForest,
    VotingClassifier
)
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
    f1_score,
    precision_score,
    recall_score,
    auc
)
from sklearn.calibration import CalibratedClassifierCV

warnings.filterwarnings('ignore')


class FraudDetectionTrainer:
    """Production-grade fraud detection model trainer"""

    def __init__(self, output_dir='./models'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.eval_metrics = {}

    def generate_realistic_transactions(self, n_samples=50000):
        """Generate realistic transaction data with real-world patterns"""
        print(f"\n{'='*60}")
        print("GENERATING REALISTIC TRANSACTION DATA")
        print(f"{'='*60}")

        np.random.seed(42)

        # Real merchant categories (by risk)
        high_risk_merchants = ['Online Gambling', 'Money Transfer', 'Gift Cards', 'Crypto', 'Adult Content', 'Wire Transfer']
        medium_risk_merchants = ['Gas Station', 'ATM Withdrawal', 'Travel', 'Foreign Currency', 'Casino']
        low_risk_merchants = ['Grocery', 'Restaurant', 'Gas', 'Pharmacy', 'Utilities', 'Supermarket', 'Department Store']

        # Real countries and their fraud rates
        countries = {
            'KE': 0.02,  # Kenya - low fraud
            'NG': 0.05,  # Nigeria - medium
            'US': 0.03,  # USA - low-medium
            'CN': 0.08,  # China - high
            'RU': 0.10,  # Russia - very high
            'BR': 0.07,  # Brazil - high
            'IN': 0.04,  # India - medium
            'GB': 0.02,  # UK - low
            'ZA': 0.06,  # South Africa - medium-high
            'PK': 0.09,  # Pakistan - high
        }

        data = []
        fraud_count = 0
        legitimate_count = 0

        for i in range(n_samples):
            # Simulate time-of-day patterns
            hour = np.random.choice(
                [2, 3, 4, 14, 15, 18, 20, 22, 23],
                p=[0.15, 0.15, 0.15, 0.10, 0.10, 0.10, 0.10, 0.10, 0.05]
            ) if np.random.random() < 0.3 else np.random.randint(0, 24)

            day_of_week = np.random.randint(0, 7)

            # Decide if transaction is fraudulent (class imbalance: ~5% fraud)
            is_fraud = np.random.random() < 0.05

            if is_fraud:
                fraud_count += 1
                # Fraudulent patterns
                amount = np.random.exponential(5000) + 100
                distance_from_home = np.random.exponential(500)
                transaction_count_24h = np.random.randint(5, 50)
                merchant_category = np.random.choice(high_risk_merchants)
                country_probs = np.array(list(countries.values())) / sum(countries.values())
                country = np.random.choice(list(countries.keys()), p=country_probs)
                is_foreign = np.random.random() < 0.8
                days_since_last_tx = np.random.randint(0, 2)
                unique_merchants_24h = np.random.randint(3, 15)
                declined_attempts_24h = np.random.randint(0, 5)
            else:
                legitimate_count += 1
                # Legitimate patterns
                amount = np.random.lognormal(5.5, 1.5)
                distance_from_home = np.random.exponential(20)
                transaction_count_24h = np.random.randint(1, 5)
                merchant_category = np.random.choice(low_risk_merchants)
                country = 'KE' if np.random.random() < 0.7 else np.random.choice(list(countries.keys()))
                is_foreign = country != 'KE'
                days_since_last_tx = np.random.randint(1, 30)
                unique_merchants_24h = np.random.randint(1, 4)
                declined_attempts_24h = 0 if np.random.random() < 0.9 else 1

            # Device/IP features
            device_is_new = 1 if is_fraud and np.random.random() < 0.6 else (1 if np.random.random() < 0.1 else 0)
            ip_is_vpn = 1 if is_fraud and np.random.random() < 0.5 else (1 if np.random.random() < 0.05 else 0)

            # Time-based features
            is_weekend = 1 if day_of_week >= 5 else 0
            is_night = 1 if hour < 6 or hour > 22 else 0

            # Transaction velocity features
            transaction_count_7d = transaction_count_24h * np.random.uniform(2, 5)
            amount_sum_24h = amount * transaction_count_24h * np.random.uniform(0.5, 1.5)

            # Merchant risk score
            if merchant_category in high_risk_merchants:
                merchant_risk = np.random.uniform(0.7, 1.0)
            elif merchant_category in medium_risk_merchants:
                merchant_risk = np.random.uniform(0.4, 0.6)
            else:
                merchant_risk = np.random.uniform(0.0, 0.3)

            # Geographic risk
            country_fraud_rate = countries[country]

            # Construct transaction record
            transaction = {
                'transaction_id': f'TXN_{i:06d}',
                'amount': amount,
                'distance_from_home_km': distance_from_home,
                'hours_since_midnight': hour,
                'day_of_week': day_of_week,
                'is_weekend': is_weekend,
                'is_night': is_night,
                'merchant_category': merchant_category,
                'merchant_risk_score': merchant_risk,
                'country': country,
                'is_foreign': is_foreign,
                'country_fraud_rate': country_fraud_rate,
                'transaction_count_24h': transaction_count_24h,
                'transaction_count_7d': transaction_count_7d,
                'amount_sum_24h': amount_sum_24h,
                'days_since_last_transaction': days_since_last_tx,
                'unique_merchants_24h': unique_merchants_24h,
                'declined_attempts_24h': declined_attempts_24h,
                'device_is_new': device_is_new,
                'ip_is_vpn': ip_is_vpn,
                'age_days': np.random.randint(1, 3650),
                'is_fraud': int(is_fraud)
            }
            data.append(transaction)

        df = pd.DataFrame(data)
        print(f"\n✓ Generated {n_samples:,} transactions")
        print(f"  • Fraudulent: {fraud_count:,} ({fraud_count/n_samples*100:.2f}%)")
        print(f"  • Legitimate: {legitimate_count:,} ({legitimate_count/n_samples*100:.2f}%)")
        print(f"  • Features: {len(df.columns) - 1}")
        return df

    def engineer_features(self, df):
        """Advanced feature engineering"""
        print(f"\n{'='*60}")
        print("FEATURE ENGINEERING")
        print(f"{'='*60}")

        df_engineered = df.copy()

        # Logarithmic transformations
        df_engineered['log_amount'] = np.log1p(df_engineered['amount'])
        df_engineered['log_distance'] = np.log1p(df_engineered['distance_from_home_km'])
        df_engineered['log_tx_count_24h'] = np.log1p(df_engineered['transaction_count_24h'])

        # Velocity indicators
        df_engineered['velocity_ratio'] = (df_engineered['transaction_count_24h'] / (df_engineered['days_since_last_transaction'] + 1))

        # Amount anomalies
        df_engineered['amount_per_tx_24h'] = (df_engineered['amount_sum_24h'] / (df_engineered['transaction_count_24h'] + 1))

        # Risk composites
        df_engineered['geographic_risk'] = (df_engineered['country_fraud_rate'] * df_engineered['is_foreign'])
        df_engineered['device_risk'] = (df_engineered['device_is_new'] + df_engineered['ip_is_vpn'])

        # Time-based risk
        df_engineered['time_risk'] = (df_engineered['is_night'] * 0.3 + df_engineered['is_weekend'] * 0.1)

        # Combined merchant & amount risk
        df_engineered['merchant_amount_risk'] = (df_engineered['merchant_risk_score'] * np.log1p(df_engineered['amount']) / 10)

        # Decline history indicator
        df_engineered['has_recent_declines'] = (df_engineered['declined_attempts_24h'] > 0).astype(int)

        engineered_cols = [
            'log_amount', 'log_distance', 'log_tx_count_24h',
            'velocity_ratio', 'amount_per_tx_24h', 'geographic_risk',
            'device_risk', 'time_risk', 'merchant_amount_risk',
            'has_recent_declines'
        ]

        print(f"\n✓ Engineered {len(engineered_cols)} advanced features")
        print(f"  • Log transformations: 3")
        print(f"  • Velocity indicators: 1")
        print(f"  • Risk composites: 5")
        print(f"  • Other: 1")

        return df_engineered, engineered_cols

    def prepare_features(self, df, engineered_cols):
        """Prepare features for modeling"""
        feature_cols = [
            'log_amount', 'log_distance', 'hours_since_midnight', 'day_of_week',
            'is_weekend', 'is_night', 'merchant_risk_score', 'is_foreign',
            'country_fraud_rate', 'log_tx_count_24h', 'transaction_count_7d',
            'days_since_last_transaction', 'unique_merchants_24h',
            'declined_attempts_24h', 'device_is_new', 'ip_is_vpn', 'age_days',
            'velocity_ratio', 'amount_per_tx_24h', 'geographic_risk',
            'device_risk', 'time_risk', 'merchant_amount_risk',
            'has_recent_declines'
        ]

        X = df[feature_cols].fillna(0)
        y = df['is_fraud']
        self.feature_names = feature_cols

        return X, y

    def train_ensemble_model(self, X_train, y_train):
        """Train ensemble model with multiple algorithms"""
        print(f"\n{'='*60}")
        print("TRAINING ENSEMBLE MODEL")
        print(f"{'='*60}")

        # Gradient Boosting (primary model)
        print("\n• Training Gradient Boosting Classifier...")
        gb_model = GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=7,
            min_samples_split=10,
            min_samples_leaf=5,
            subsample=0.8,
            random_state=42,
            verbose=0
        )
        gb_model.fit(X_train, y_train)

        # Random Forest (secondary model)
        print("• Training Random Forest Classifier...")
        rf_model = RandomForestClassifier(
            n_estimators=150,
            max_depth=15,
            min_samples_split=10,
            min_samples_leaf=5,
            max_features='sqrt',
            random_state=42,
            n_jobs=-1
        )
        rf_model.fit(X_train, y_train)

        # Isolation Forest (anomaly detection)
        print("• Training Isolation Forest...")
        iso_model = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=42,
            n_jobs=-1
        )
        iso_model.fit(X_train)

        # Voting Ensemble
        print("• Creating Voting Ensemble...")
        voting_model = VotingClassifier(
            estimators=[('gb', gb_model), ('rf', rf_model)],
            voting='soft',
            weights=[0.6, 0.4]
        )
        voting_model.fit(X_train, y_train)

        # Calibrate probabilities
        print("• Calibrating model probabilities...")
        calibrated_model = CalibratedClassifierCV(
            voting_model,
            method='sigmoid',
            cv=5
        )
        calibrated_model.fit(X_train, y_train)

        self.model = calibrated_model
        self.iso_model = iso_model

        print("\n✓ Ensemble model trained successfully")
        return calibrated_model

    def evaluate_model(self, X_test, y_test, model_name="Final Model"):
        """Comprehensive model evaluation"""
        print(f"\n{'='*60}")
        print(f"MODEL EVALUATION - {model_name}")
        print(f"{'='*60}")

        # Predictions
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)[:, 1]

        # Metrics
        accuracy = (y_pred == y_test).mean()
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        roc_auc = roc_auc_score(y_test, y_pred_proba)

        print(f"\nCLASSIFICATION METRICS:")
        print(f"  • Accuracy:  {accuracy:.4f}")
        print(f"  • Precision: {precision:.4f} (of detected frauds, {precision*100:.1f}% correct)")
        print(f"  • Recall:    {recall:.4f} (catching {recall*100:.1f}% of actual fraud)")
        print(f"  • F1 Score:  {f1:.4f}")
        print(f"  • ROC-AUC:   {roc_auc:.4f}")

        # Confusion matrix
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
        print(f"\nCONFUSION MATRIX:")
        print(f"  • True Negatives:  {tn:,} (legitimate correctly identified)")
        print(f"  • False Positives: {fp:,} (legitimate flagged as fraud)")
        print(f"  • False Negatives: {fn:,} (fraud missed)")
        print(f"  • True Positives:  {tp:,} (fraud correctly detected)")

        # Specificity & Sensitivity
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
        sensitivity = recall

        print(f"\nADDITIONAL METRICS:")
        print(f"  • Sensitivity (True Positive Rate): {sensitivity:.4f}")
        print(f"  • Specificity (True Negative Rate): {specificity:.4f}")
        print(f"  • False Positive Rate: {1-specificity:.4f}")

        # Classification report
        print(f"\nDETAILED CLASSIFICATION REPORT:")
        print(classification_report(y_test, y_pred, target_names=['Legitimate', 'Fraud'], zero_division=0))

        # Feature importance
        try:
            # Access the base estimator from CalibratedClassifierCV
            base_model = self.model.estimator
            if hasattr(base_model, 'estimators_'):
                # It's a VotingClassifier
                importances = base_model.estimators_[0].feature_importances_
            elif hasattr(base_model, 'feature_importances_'):
                # Direct access
                importances = base_model.feature_importances_
            else:
                importances = None

            if importances is not None:
                feature_importance_df = pd.DataFrame({
                    'feature': self.feature_names,
                    'importance': importances
                }).sort_values('importance', ascending=False)

                print(f"\nTOP 10 IMPORTANT FEATURES:")
                for idx, row in feature_importance_df.head(10).iterrows():
                    print(f"  {idx+1}. {row['feature']:<30} {row['importance']:.4f}")
        except Exception as e:
            print(f"\nNote: Could not extract feature importance: {e}")

        # Store evaluation metrics
        self.eval_metrics = {
            'accuracy': float(accuracy),
            'precision': float(precision),
            'recall': float(recall),
            'f1': float(f1),
            'roc_auc': float(roc_auc),
            'specificity': float(specificity),
            'sensitivity': float(sensitivity)
        }

        return self.eval_metrics

    def save_model(self, model_path='fraud_model.pkl'):
        """Save trained model and scaler"""
        print(f"\n{'='*60}")
        print("SAVING MODEL")
        print(f"{'='*60}")

        model_data = {
            'model': self.model,
            'iso_model': self.iso_model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'eval_metrics': self.eval_metrics,
            'trained_at': datetime.now().isoformat()
        }

        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)

        print(f"\n✓ Model saved to: {model_path}")
        print(f"  • File size: {Path(model_path).stat().st_size / 1024:.1f} KB")
        print(f"  • Trained: {model_data['trained_at']}")

        # Save metrics as JSON
        metrics_path = model_path.replace('.pkl', '_metrics.json')
        with open(metrics_path, 'w') as f:
            json.dump(self.eval_metrics, f, indent=2)

        print(f"✓ Metrics saved to: {metrics_path}")

    def train(self):
        """Complete training pipeline"""
        print(f"\n{'#'*60}")
        print("# SENTRA FRAUD DETECTION - MODEL TRAINING")
        print(f"{'#'*60}")
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Generate data
        df = self.generate_realistic_transactions(n_samples=50000)

        # Feature engineering
        df_engineered, engineered_cols = self.engineer_features(df)

        # Prepare features
        X, y = self.prepare_features(df_engineered, engineered_cols)

        # Scale features
        self.scaler = RobustScaler()
        X_scaled = self.scaler.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=self.feature_names)

        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y,
            test_size=0.2,
            random_state=42,
            stratify=y
        )

        print(f"\n{'='*60}")
        print("TRAIN-TEST SPLIT")
        print(f"{'='*60}")
        print(f"Training set: {len(X_train):,} samples")
        print(f"Test set:     {len(X_test):,} samples")
        print(f"Fraud rate (train): {y_train.mean()*100:.2f}%")
        print(f"Fraud rate (test):  {y_test.mean()*100:.2f}%")

        # Train ensemble
        self.train_ensemble_model(X_train, y_train)

        # Evaluate
        self.evaluate_model(X_test, y_test)

        # Cross-validation
        print(f"\n{'='*60}")
        print("CROSS-VALIDATION (5-Fold)")
        print(f"{'='*60}")
        cv_scores = cross_val_score(
            self.model, X_scaled, y,
            cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42),
            scoring='roc_auc'
        )
        print(f"ROC-AUC scores: {[f'{s:.4f}' for s in cv_scores]}")
        print(f"Mean ROC-AUC: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

        # Save
        self.save_model('fraud_model.pkl')

        print(f"\n{'#'*60}")
        print("# TRAINING COMPLETE")
        print(f"{'#'*60}")
        print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return self.model


if __name__ == "__main__":
    trainer = FraudDetectionTrainer()
    model = trainer.train()
