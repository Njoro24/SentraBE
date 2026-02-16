import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def generate_synthetic_transactions(n_samples=10000, fraud_ratio=0.5):
    """
    Generate synthetic transaction data for training.
    
    Args:
        n_samples: Total number of transactions to generate
        fraud_ratio: Proportion of fraudulent transactions (0.5 = 50%)
    
    Returns:
        DataFrame with synthetic transactions
    """
    
    np.random.seed(42)
    
    n_fraud = int(n_samples * fraud_ratio)
    n_legitimate = n_samples - n_fraud
    
    # Legitimate transactions
    legitimate_data = {
        'transaction_id': [f'TXN_LEG_{i:06d}' for i in range(n_legitimate)],
        'amount': np.random.lognormal(10, 1.5, n_legitimate),  # Log-normal distribution
        'phone_number': [f'+254{np.random.randint(700000000, 799999999)}' for _ in range(n_legitimate)],
        'device_id': [f'DEV_{np.random.randint(1000, 9999)}' for _ in range(n_legitimate)],
        'location': np.random.choice(['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Eldoret'], n_legitimate),
        'hour_of_day': np.random.randint(6, 22, n_legitimate),  # Business hours
        'day_of_week': np.random.randint(0, 7, n_legitimate),
        'transactions_today': np.random.poisson(3, n_legitimate),  # Few transactions
        'avg_transaction_amount': np.random.lognormal(10, 1, n_legitimate),
        'is_fraud': 0
    }
    
    # Fraudulent transactions
    fraud_data = {
        'transaction_id': [f'TXN_FRD_{i:06d}' for i in range(n_fraud)],
        'amount': np.random.lognormal(11, 2, n_fraud),  # Higher amounts
        'phone_number': [f'+254{np.random.randint(700000000, 799999999)}' for _ in range(n_fraud)],
        'device_id': [f'DEV_{np.random.randint(1000, 9999)}' for _ in range(n_fraud)],
        'location': np.random.choice(['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Eldoret'], n_fraud),
        'hour_of_day': np.random.randint(0, 24, n_fraud),  # Any time
        'day_of_week': np.random.randint(0, 7, n_fraud),
        'transactions_today': np.random.poisson(15, n_fraud),  # Many transactions
        'avg_transaction_amount': np.random.lognormal(9, 1.5, n_fraud),
        'is_fraud': 1
    }
    
    # Combine
    df_legitimate = pd.DataFrame(legitimate_data)
    df_fraud = pd.DataFrame(fraud_data)
    df = pd.concat([df_legitimate, df_fraud], ignore_index=True)
    
    # Shuffle
    df = df.sample(frac=1).reset_index(drop=True)
    
    # Add timestamp
    base_date = datetime.now() - timedelta(days=30)
    df['timestamp'] = [base_date + timedelta(hours=int(h), days=int(d)) 
                       for h, d in zip(df['hour_of_day'], np.random.randint(0, 30, len(df)))]
    
    return df

def save_synthetic_data(df, output_path='data/synthetic_transactions.csv'):
    """Save synthetic data to CSV"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"✓ Synthetic data saved to {output_path}")
    print(f"  - Total transactions: {len(df)}")
    print(f"  - Fraudulent: {df['is_fraud'].sum()} ({df['is_fraud'].mean()*100:.1f}%)")
    print(f"  - Legitimate: {(1-df['is_fraud']).sum()} ({(1-df['is_fraud']).mean()*100:.1f}%)")
    return df

if __name__ == "__main__":
    print("Generating synthetic transaction data...")
    df = generate_synthetic_transactions(n_samples=10000, fraud_ratio=0.5)
    df = save_synthetic_data(df)
    print("\nFirst 5 rows:")
    print(df.head())
    print("\nData statistics:")
    print(df.describe())
