"""
Generate realistic training data for fraud detection model.
Creates imbalanced dataset (99% legitimate, 1% fraud) with realistic patterns.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

print("\n" + "="*80)
print("GENERATING REALISTIC TRAINING DATA")
print("="*80 + "\n")

np.random.seed(42)
random.seed(42)

# Configuration
N_LEGITIMATE = 500000
N_FRAUD = 5000
TOTAL = N_LEGITIMATE + N_FRAUD

print(f"Generating {TOTAL:,} transactions...")
print(f"  Legitimate: {N_LEGITIMATE:,} (99%)")
print(f"  Fraud: {N_FRAUD:,} (1%)")
print()

# Generate legitimate transactions
print("Generating legitimate transactions...")
legitimate_data = []

for i in range(N_LEGITIMATE):
    if (i + 1) % 50000 == 0:
        print(f"  {i+1:,}/{N_LEGITIMATE:,}")
    
    # Normal transaction patterns
    hour = np.random.choice(range(24), p=[0.02]*5 + [0.05]*7 + [0.04]*7 + [0.02]*5)  # More during day
    amount = np.random.lognormal(mean=9.5, sigma=1.5)  # Log-normal distribution
    amount = min(amount, 500000)  # Cap at 500k
    
    legitimate_data.append({
        'amount': amount,
        'amount_log': np.log1p(amount),
        'is_small_amount': 1 if amount < 100 else 0,
        'is_large_amount': 1 if amount > 100000 else 0,
        'is_round_amount': 1 if amount % 1000 == 0 else 0,
        'hour': hour,
        'is_night': 1 if (hour >= 22 or hour <= 5) else 0,
        'is_weekend': np.random.choice([0, 1], p=[0.7, 0.3]),
        'is_fraud': 0
    })

df_legitimate = pd.DataFrame(legitimate_data)

# Generate fraud transactions
print("Generating fraud transactions...")
fraud_data = []

fraud_patterns = [
    'high_amount',      # Large unusual amounts
    'night_time',       # Transactions at odd hours
    'rapid_sequence',   # Multiple transactions quickly
    'unusual_location', # Different location
    'round_amount',     # Suspicious round amounts
]

for i in range(N_FRAUD):
    if (i + 1) % 500 == 0:
        print(f"  {i+1:,}/{N_FRAUD:,}")
    
    pattern = random.choice(fraud_patterns)
    
    if pattern == 'high_amount':
        amount = np.random.uniform(50000, 500000)
        hour = np.random.randint(0, 24)
        is_night = 1 if (hour >= 22 or hour <= 5) else 0
        is_round = 1 if amount % 1000 == 0 else 0
    
    elif pattern == 'night_time':
        hour = np.random.choice([22, 23, 0, 1, 2, 3, 4, 5])
        amount = np.random.lognormal(mean=10, sigma=1.2)
        is_night = 1
        is_round = 0
    
    elif pattern == 'rapid_sequence':
        amount = np.random.uniform(1000, 50000)
        hour = np.random.randint(0, 24)
        is_night = 1 if (hour >= 22 or hour <= 5) else 0
        is_round = 1 if amount % 1000 == 0 else 0
    
    elif pattern == 'unusual_location':
        amount = np.random.uniform(10000, 100000)
        hour = np.random.randint(0, 24)
        is_night = 1 if (hour >= 22 or hour <= 5) else 0
        is_round = 0
    
    else:  # round_amount
        amount = np.random.choice([10000, 25000, 50000, 100000, 250000])
        hour = np.random.randint(0, 24)
        is_night = 1 if (hour >= 22 or hour <= 5) else 0
        is_round = 1
    
    fraud_data.append({
        'amount': min(amount, 500000),
        'amount_log': np.log1p(amount),
        'is_small_amount': 1 if amount < 100 else 0,
        'is_large_amount': 1 if amount > 100000 else 0,
        'is_round_amount': is_round,
        'hour': hour,
        'is_night': is_night,
        'is_weekend': np.random.choice([0, 1], p=[0.5, 0.5]),
        'is_fraud': 1
    })

df_fraud = pd.DataFrame(fraud_data)

# Combine
print("\nCombining datasets...")
df = pd.concat([df_legitimate, df_fraud], ignore_index=True)
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

print(f"Total transactions: {len(df):,}")
print(f"Legitimate: {(df['is_fraud']==0).sum():,} ({(df['is_fraud']==0).sum()/len(df)*100:.2f}%)")
print(f"Fraud: {(df['is_fraud']==1).sum():,} ({(df['is_fraud']==1).sum()/len(df)*100:.2f}%)")

# Save
output_file = 'SentraBE/training_data.csv'
print(f"\nSaving to {output_file}...")
df.to_csv(output_file, index=False)

print(f"✓ Training data saved ({len(df):,} transactions)")
print(f"✓ File size: {pd.io.common.get_filepath_or_buffer(output_file)[0]}")
print("\n" + "="*80 + "\n")
