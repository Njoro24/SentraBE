import pandas as pd
import numpy as np
import random

np.random.seed(42)
random.seed(42)

NUM_TRANSACTIONS = 10000
FRAUD_RATIO = 0.02

def generate_transactions():
    transactions = []
    
    for i in range(NUM_TRANSACTIONS):
        is_fraud = random.random() < FRAUD_RATIO
        
        if is_fraud:
            amount = random.uniform(5000, 200000)
            hour = random.choice([0, 1, 2, 3, 23, 8, 14])
            is_new_receiver = 1 if random.random() < 0.75 else 0
            velocity = random.randint(8, 30)
        else:
            amount = random.uniform(50, 180000)
            hour = random.randint(0, 23)
            is_new_receiver = 1 if random.random() < 0.20 else 0
            velocity = random.randint(1, 15)

        # Add noise to all features
        amount = max(50, amount + random.gauss(0, 2000))
        velocity = max(1, velocity + random.randint(-2, 2))

        transactions.append({
            "amount": round(amount, 2),
            "sender_id": f"2547{random.randint(10000000, 99999999)}",
            "receiver_id": f"2547{random.randint(10000000, 99999999)}",
            "channel": random.choice(["mpesa", "bank", "atm"]),
            "location": random.choice(["Nairobi", "Mombasa", "Kisumu", "Nakuru"]),
            "hour_of_day": hour,
            "is_new_receiver": is_new_receiver,
            "velocity": velocity,
            "is_fraud": int(is_fraud)
        })
    
    return pd.DataFrame(transactions)

df = generate_transactions()
df.to_csv("transactions.csv", index=False)

print(f"Total transactions: {len(df)}")
print(f"Fraud cases: {df['is_fraud'].sum()}")
print(f"Legitimate: {(df['is_fraud'] == 0).sum()}")
print("Saved to transactions.csv")
