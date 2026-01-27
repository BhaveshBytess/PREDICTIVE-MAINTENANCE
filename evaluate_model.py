"""
ML Model Evaluation Script

Tests the Isolation Forest anomaly detector on:
1. Healthy data - should score LOW (0.0-0.2)
2. Faulty data - should score HIGH (0.6-1.0)

Computes: Accuracy, Precision, Recall, F1-Score
"""

import sys
import random
import math
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

# Direct imports avoiding problematic modules
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


# Feature calculation functions (copied from calculator.py to avoid import issues)
def calculate_voltage_rolling_mean(df, evaluation_idx):
    if df.empty or 'voltage_v' not in df.columns:
        return None
    if evaluation_idx < 0 or evaluation_idx >= len(df):
        return None
    window_start = max(0, evaluation_idx - 59)
    window_data = df['voltage_v'].iloc[window_start:evaluation_idx + 1]
    if len(window_data) < 2:
        return None
    mean_value = window_data.mean()
    return float(mean_value) if not pd.isna(mean_value) else None


def calculate_current_spike_count(df, evaluation_idx, sigma_threshold=2.0):
    if df.empty or 'current_a' not in df.columns:
        return None
    window_start = max(0, evaluation_idx - 60)
    window_data = df['current_a'].iloc[window_start:evaluation_idx + 1]
    if len(window_data) < 3:
        return None
    local_mean = window_data.mean()
    local_std = window_data.std()
    if pd.isna(local_std) or local_std == 0:
        return 0
    threshold = local_mean + (sigma_threshold * local_std)
    spike_count = (window_data > threshold).sum()
    return int(spike_count)


def calculate_power_factor_efficiency_score(power_factor):
    if power_factor is None or math.isnan(power_factor):
        return None
    pf = max(0.0, min(1.0, power_factor))
    return round(pf, 4)


def calculate_vibration_rms(df, evaluation_idx):
    if df.empty or 'vibration_g' not in df.columns:
        return None
    window_start = max(0, evaluation_idx - 60)
    window_data = df['vibration_g'].iloc[window_start:evaluation_idx + 1]
    if len(window_data) < 2:
        return None
    squared = window_data ** 2
    mean_squared = squared.mean()
    if pd.isna(mean_squared):
        return None
    rms = np.sqrt(mean_squared)
    return round(float(rms), 6)


def compute_all_features(df, evaluation_idx, current_power_factor):
    return {
        "voltage_rolling_mean_1h": calculate_voltage_rolling_mean(df, evaluation_idx),
        "current_spike_count": calculate_current_spike_count(df, evaluation_idx),
        "power_factor_efficiency_score": calculate_power_factor_efficiency_score(current_power_factor),
        "vibration_intensity_rms": calculate_vibration_rms(df, evaluation_idx),
    }


FEATURE_COLUMNS = [
    'voltage_rolling_mean_1h',
    'current_spike_count',
    'power_factor_efficiency_score',
    'vibration_intensity_rms',
]


def generate_healthy_data(n_samples: int = 100) -> pd.DataFrame:
    """Generate simulated healthy sensor data."""
    data = []
    base_time = datetime.now(timezone.utc)
    
    for i in range(n_samples):
        data.append({
            'timestamp': base_time + timedelta(minutes=i),
            'voltage_v': random.gauss(230, 2),
            'current_a': random.gauss(15, 1),
            'power_factor': random.gauss(0.92, 0.02),
            'vibration_g': random.gauss(0.15, 0.03),
        })
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    return df


def generate_faulty_data(n_samples: int = 50) -> pd.DataFrame:
    """Generate simulated faulty sensor data."""
    data = []
    base_time = datetime.now(timezone.utc) + timedelta(hours=2)
    
    for i in range(n_samples):
        fault_type = random.choice(['spike', 'drift', 'default'])
        
        if fault_type == 'spike':
            voltage = random.uniform(270, 300)
            current = random.uniform(22, 30)
            power_factor = random.uniform(0.55, 0.70)
            vibration = random.uniform(1.5, 3.0)
        elif fault_type == 'drift':
            voltage = random.uniform(238, 250)
            current = random.uniform(17, 20)
            power_factor = random.uniform(0.78, 0.85)
            vibration = random.uniform(0.25, 0.45)
        else:
            voltage = random.uniform(245, 280)
            current = random.uniform(18, 25)
            power_factor = random.uniform(0.60, 0.80)
            vibration = random.uniform(0.5, 2.5)
        
        data.append({
            'timestamp': base_time + timedelta(minutes=i),
            'voltage_v': voltage,
            'current_a': current,
            'power_factor': power_factor,
            'vibration_g': vibration,
        })
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    return df


def compute_features_for_df(df: pd.DataFrame) -> pd.DataFrame:
    """Compute rolling features for all rows in DataFrame."""
    features_list = []
    
    for i in range(len(df)):
        row = df.iloc[i]
        features = compute_all_features(df, i, row['power_factor'])
        features['timestamp'] = df.index[i]
        features_list.append(features)
    
    features_df = pd.DataFrame(features_list)
    features_df.set_index('timestamp', inplace=True)
    return features_df


def evaluate_model():
    """Run full model evaluation."""
    print("=" * 60)
    print("ML MODEL EVALUATION - Isolation Forest Anomaly Detector")
    print("=" * 60)
    
    # 1. Generate training data (healthy only)
    print("\n1. Generating training data (500 healthy samples)...")
    train_data = generate_healthy_data(500)
    print(f"   Training samples: {len(train_data)}")
    
    # 2. Compute features for training
    print("   Computing training features...")
    train_features = compute_features_for_df(train_data)
    valid_train = train_features.dropna()
    print(f"   Valid feature samples: {len(valid_train)}")
    
    # 3. Train model
    print("\n2. Training Isolation Forest model...")
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(valid_train[FEATURE_COLUMNS])
    
    model = IsolationForest(
        contamination=0.05,
        n_estimators=100,
        random_state=42,
        n_jobs=-1
    )
    model.fit(features_scaled)
    print(f"   Model trained on {len(valid_train)} samples")
    
    # 4. Generate test data
    print("\n3. Generating test data...")
    healthy_test = generate_healthy_data(100)
    faulty_test = generate_faulty_data(50)
    print(f"   Healthy test samples: {len(healthy_test)}")
    print(f"   Faulty test samples: {len(faulty_test)}")
    
    # 5. Compute features for test data
    print("   Computing test features...")
    healthy_features = compute_features_for_df(healthy_test)
    faulty_features = compute_features_for_df(faulty_test)
    
    # 6. Score function
    def get_anomaly_score(row):
        try:
            scaled = scaler.transform([row[FEATURE_COLUMNS].values])
            decision_val = model.decision_function(scaled)[0]
            # Invert: higher decision = more normal, so invert for anomaly score
            sigmoid_input = decision_val * 4
            sigmoid = 1.0 / (1.0 + np.exp(-sigmoid_input))
            return 1.0 - sigmoid
        except:
            return None
    
    # Score test data
    print("\n4. Scoring test data...")
    
    healthy_scores = []
    for idx, row in healthy_features.dropna().iterrows():
        score = get_anomaly_score(row)
        if score is not None:
            healthy_scores.append(score)
    
    faulty_scores = []
    for idx, row in faulty_features.dropna().iterrows():
        score = get_anomaly_score(row)
        if score is not None:
            faulty_scores.append(score)
    
    print(f"   Scored {len(healthy_scores)} healthy samples")
    print(f"   Scored {len(faulty_scores)} faulty samples")
    
    # 7. Compute statistics
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    print("\n--- Healthy Data (should score LOW, < 0.3) ---")
    healthy_arr = np.array(healthy_scores)
    print(f"   Mean score: {healthy_arr.mean():.3f}")
    print(f"   Std dev:    {healthy_arr.std():.3f}")
    print(f"   Min score:  {healthy_arr.min():.3f}")
    print(f"   Max score:  {healthy_arr.max():.3f}")
    
    print("\n--- Faulty Data (should score HIGH, > 0.5) ---")
    faulty_arr = np.array(faulty_scores)
    print(f"   Mean score: {faulty_arr.mean():.3f}")
    print(f"   Std dev:    {faulty_arr.std():.3f}")
    print(f"   Min score:  {faulty_arr.min():.3f}")
    print(f"   Max score:  {faulty_arr.max():.3f}")
    
    # 8. Classification metrics at threshold=0.3
    print("\n--- Classification Metrics (threshold=0.3) ---")
    
    threshold = 0.3
    
    TN = sum(1 for s in healthy_scores if s < threshold)
    FP = sum(1 for s in healthy_scores if s >= threshold)
    TP = sum(1 for s in faulty_scores if s >= threshold)
    FN = sum(1 for s in faulty_scores if s < threshold)
    
    total = TN + FP + TP + FN
    accuracy = (TP + TN) / total if total > 0 else 0
    precision = TP / (TP + FP) if (TP + FP) > 0 else 0
    recall = TP / (TP + FN) if (TP + FN) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"   True Positives (faults detected):  {TP}")
    print(f"   True Negatives (healthy correct):  {TN}")
    print(f"   False Positives (false alarms):    {FP}")
    print(f"   False Negatives (missed faults):   {FN}")
    print()
    print(f"   ACCURACY:  {accuracy:.1%}")
    print(f"   PRECISION: {precision:.1%}")
    print(f"   RECALL:    {recall:.1%}")
    print(f"   F1-SCORE:  {f1:.1%}")
    
    # 9. Overall assessment
    print("\n" + "=" * 60)
    print("ASSESSMENT")
    print("=" * 60)
    
    if f1 >= 0.8:
        print("✅ EXCELLENT: Model has strong fault detection capability")
    elif f1 >= 0.6:
        print("⚠️  GOOD: Model works reasonably well but could improve")
    elif f1 >= 0.4:
        print("⚠️  FAIR: Model needs tuning for better separation")
    else:
        print("❌ POOR: Model is not effectively detecting faults")
    
    separation = faulty_arr.mean() - healthy_arr.mean()
    print(f"\n   Score Separation: {separation:.3f}")
    if separation > 0.3:
        print("   ✅ Good separation between healthy and faulty")
    else:
        print("   ⚠️  Poor separation - scores overlap too much")


if __name__ == "__main__":
    evaluate_model()
