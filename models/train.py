import pandas as pd
import numpy as np
import xgboost as xgb
import joblib
import os
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from features import FeatureEngineer
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.synthetic_data import generate_synthetic_transactions

def train_model():
    """
    Train XGBoost model on synthetic fraud data.
    """
    
    print("=" * 60)
    print("SENTRA - MODEL TRAINING")
    print("=" * 60)
    
    # 1. Generate synthetic data
    print("\n[1/5] Generating synthetic transaction data...")
    df = generate_synthetic_transactions(n_samples=10000, fraud_ratio=0.5)
    print(f"✓ Generated {len(df)} transactions")
    
    # 2. Engineer features
    print("\n[2/5] Engineering features...")
    engineer = FeatureEngineer()
    X = engineer.engineer_features(df)
    y = df['is_fraud']
    print(f"✓ Created {X.shape[1]} features")
    print(f"  Features: {', '.join(engineer.feature_names)}")
    
    # 3. Split data
    print("\n[3/5] Splitting data (80/20 train/test)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"✓ Training set: {len(X_train)} samples")
    print(f"✓ Test set: {len(X_test)} samples")
    
    # 4. Scale features
    print("\n[4/5] Scaling features...")
    X_train_scaled = engineer.fit_transform(X_train)
    X_test_scaled = engineer.transform(X_test)
    print("✓ Features scaled")
    
    # 5. Train XGBoost model
    print("\n[5/5] Training XGBoost model...")
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric='logloss',
        verbosity=0
    )
    
    model.fit(
        X_train_scaled, y_train,
        eval_set=[(X_test_scaled, y_test)],
        verbose=False
    )
    print("✓ Model trained")
    
    # 6. Evaluate
    print("\n" + "=" * 60)
    print("MODEL EVALUATION")
    print("=" * 60)
    
    y_pred = model.predict(X_test_scaled)
    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
    
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_pred_proba)
    
    print(f"\nAccuracy:  {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print(f"AUC-ROC:   {auc:.4f}")
    
    # 7. Feature importance
    print("\n" + "=" * 60)
    print("FEATURE IMPORTANCE")
    print("=" * 60)
    
    feature_importance = pd.DataFrame({
        'feature': engineer.feature_names,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nTop 5 features:")
    for idx, row in feature_importance.head(5).iterrows():
        print(f"  {row['feature']:25s} {row['importance']:.4f}")
    
    # 8. Save model and scaler
    print("\n" + "=" * 60)
    print("SAVING MODEL")
    print("=" * 60)
    
    os.makedirs('models', exist_ok=True)
    
    model_path = 'models/xgboost_model.pkl'
    scaler_path = 'models/feature_scaler.pkl'
    
    joblib.dump(model, model_path)
    joblib.dump(engineer.scaler, scaler_path)
    
    print(f"\n✓ Model saved to {model_path}")
    print(f"✓ Scaler saved to {scaler_path}")
    
    # 9. Save metadata
    metadata = {
        'accuracy': float(accuracy),
        'precision': float(precision),
        'recall': float(recall),
        'f1_score': float(f1),
        'auc_roc': float(auc),
        'training_samples': len(X_train),
        'test_samples': len(X_test),
        'feature_names': engineer.feature_names,
        'model_type': 'XGBoost',
        'n_estimators': 100,
        'max_depth': 6,
    }
    
    import json
    metadata_path = 'models/model_metadata.json'
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✓ Metadata saved to {metadata_path}")
    
    print("\n" + "=" * 60)
    print("✓ TRAINING COMPLETE")
    print("=" * 60)
    
    return model, engineer

if __name__ == "__main__":
    train_model()
