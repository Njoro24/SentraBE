import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score
)
from sklearn.preprocessing import LabelEncoder
import joblib

print("Loading PaySim dataset...")
paysim = pd.read_csv("PS_20174392719_1491204439457_log.csv")

print("Loading Credit Card dataset...")
creditcard = pd.read_csv("creditcard.csv")

# ── Process PaySim ──────────────────────────────
print("Processing PaySim...")
le = LabelEncoder()
paysim['type_encoded'] = le.fit_transform(paysim['type'])

paysim['balance_diff_orig'] = paysim['newbalanceOrig'] - paysim['oldbalanceOrg']
paysim['balance_diff_dest'] = paysim['newbalanceDest'] - paysim['oldbalanceDest']
paysim['is_new_receiver'] = (paysim['oldbalanceDest'] == 0).astype(int)
paysim['amount_to_balance_ratio'] = paysim['amount'] / (paysim['oldbalanceOrg'] + 1)
paysim['balance_drained'] = (paysim['newbalanceOrig'] == 0).astype(int)
paysim['exact_amount_transfer'] = (
    paysim['amount'] == paysim['oldbalanceOrg']
).astype(int)
paysim['receiver_balance_unchanged'] = (
    paysim['newbalanceDest'] == paysim['oldbalanceDest']
).astype(int)
paysim['hour'] = paysim['step'] % 24
paysim['is_night'] = paysim['hour'].apply(
    lambda x: 1 if x >= 22 or x <= 5 else 0
)
paysim['is_round_amount'] = (paysim['amount'] % 1000 == 0).astype(int)
paysim['orig_to_dest_ratio'] = paysim['amount'] / (paysim['oldbalanceDest'] + 1)

paysim_features = paysim[[
    'amount',
    'type_encoded',
    'oldbalanceOrg',
    'newbalanceOrig',
    'oldbalanceDest',
    'newbalanceDest',
    'balance_diff_orig',
    'balance_diff_dest',
    'is_new_receiver',
    'amount_to_balance_ratio',
    'balance_drained',
    'exact_amount_transfer',
    'receiver_balance_unchanged',
    'hour',
    'is_night',
    'is_round_amount',
    'orig_to_dest_ratio',
    'isFraud'
]].copy()

paysim_features.columns = [
    'amount', 'type_encoded', 'old_balance_orig',
    'new_balance_orig', 'old_balance_dest', 'new_balance_dest',
    'balance_diff_orig', 'balance_diff_dest',
    'is_new_receiver', 'amount_to_balance_ratio',
    'balance_drained', 'exact_amount_transfer',
    'receiver_balance_unchanged', 'hour', 'is_night',
    'is_round_amount', 'orig_to_dest_ratio', 'is_fraud'
]

# ── Process Credit Card ─────────────────────────
print("Processing Credit Card data...")
creditcard_aligned = pd.DataFrame({
    'amount': creditcard['Amount'],
    'type_encoded': 0,
    'old_balance_orig': creditcard['V1'],
    'new_balance_orig': creditcard['V2'],
    'old_balance_dest': creditcard['V3'],
    'new_balance_dest': creditcard['V4'],
    'balance_diff_orig': creditcard['V5'],
    'balance_diff_dest': creditcard['V6'],
    'is_new_receiver': creditcard['V7'].apply(lambda x: 1 if x < 0 else 0),
    'amount_to_balance_ratio': creditcard['V8'],
    'balance_drained': creditcard['V9'].apply(lambda x: 1 if x < -1 else 0),
    'exact_amount_transfer': creditcard['V10'].apply(lambda x: 1 if x < -1 else 0),
    'receiver_balance_unchanged': creditcard['V11'].apply(lambda x: 1 if x < 0 else 0),
    'hour': creditcard['Time'].apply(lambda x: int(x / 3600) % 24),
    'is_night': creditcard['Time'].apply(
        lambda x: 1 if int(x / 3600) % 24 >= 22 or int(x / 3600) % 24 <= 5 else 0
    ),
    'is_round_amount': creditcard['Amount'].apply(lambda x: 1 if x % 10 == 0 else 0),
    'orig_to_dest_ratio': creditcard['V12'],
    'is_fraud': creditcard['Class']
})

# ── Combine Datasets ────────────────────────────
print("Combining datasets...")
combined = pd.concat([paysim_features, creditcard_aligned], ignore_index=True)
combined = combined.fillna(0)

print(f"\nTotal records:     {len(combined):,}")
print(f"Fraud cases:       {combined['is_fraud'].sum():,}")
print(f"Legitimate cases:  {(combined['is_fraud']==0).sum():,}")

# ── Split Data ──────────────────────────────────
X = combined.drop('is_fraud', axis=1)
y = combined['is_fraud']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# ── Train Model ─────────────────────────────────
print("\nTraining XGBoost...")
model = XGBClassifier(
    n_estimators=500,
    max_depth=8,
    learning_rate=0.03,
    scale_pos_weight=len(y[y==0]) / len(y[y==1]),
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=5,
    gamma=1,
    reg_alpha=0.1,
    reg_lambda=1.5,
    random_state=42,
    eval_metric='aucpr',
    early_stopping_rounds=30
)

model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    verbose=50
)

# ── Find Optimal Threshold ──────────────────────
print("\nFinding optimal threshold to reduce false positives...")
y_pred_proba = model.predict_proba(X_test)[:, 1]

best_threshold = 0.5
best_score = 0

for thresh in np.arange(0.1, 0.95, 0.01):
    y_pred_thresh = (y_pred_proba >= thresh).astype(int)
    prec = precision_score(y_test, y_pred_thresh, zero_division=0)
    rec = recall_score(y_test, y_pred_thresh, zero_division=0)
    f1 = f1_score(y_test, y_pred_thresh, zero_division=0)
    # We want precision above 85% AND recall above 90%
    if prec >= 0.85 and rec >= 0.90 and f1 > best_score:
        best_score = f1
        best_threshold = thresh

print(f"Optimal threshold: {best_threshold:.2f}")

# ── Final Evaluation ────────────────────────────
y_pred_final = (y_pred_proba >= best_threshold).astype(int)

print("\nClassification Report:")
print(classification_report(y_test, y_pred_final))

print("Confusion Matrix:")
cm = confusion_matrix(y_test, y_pred_final)
print(cm)
print(f"\nTrue Positives  (Fraud caught):        {cm[1][1]:,}")
print(f"False Negatives (Fraud missed):        {cm[1][0]:,}")
print(f"False Positives (Legit wrongly flagged): {cm[0][1]:,}")
print(f"True Negatives  (Legit correctly passed): {cm[0][0]:,}")

print(f"\nROC AUC Score: {roc_auc_score(y_test, y_pred_proba):.4f}")

print("\nFeature Importances:")
for feat, imp in sorted(
    zip(X.columns, model.feature_importances_),
    key=lambda x: x[1], reverse=True
):
    print(f"  {feat}: {round(imp, 4)}")

# ── Save Model + Threshold ──────────────────────
joblib.dump(model, "fraud_model.pkl")
joblib.dump(le, "label_encoder.pkl")
joblib.dump(best_threshold, "threshold.pkl")

print(f"\nModel saved:     fraud_model.pkl")
print(f"Encoder saved:   label_encoder.pkl")
print(f"Threshold saved: threshold.pkl ({best_threshold:.2f})")
