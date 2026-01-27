"""
ML Model Benchmark Script

Tests the upgraded Isolation Forest detector with:
- Derived features (voltage_stability, power_vibration_ratio)
- Quantile calibration

Computes: Accuracy, Precision, Recall, F1-Score, Healthy Stability
"""

import sys
import random
import math
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

sys.path.insert(0, r'c:\Users\oumme\OneDrive\Desktop\Predictive Maintenance')

from backend.ml.detector import AnomalyDetector, BASE_FEATURE_COLUMNS


def generate_healthy_data(n_samples: int = 500) -> pd.DataFrame:
    """Generate simulated healthy sensor data with features."""
    data = []
    base_time = datetime.now(timezone.utc)
    
    for i in range(n_samples):
        # Healthy readings (Indian Grid context)
        voltage = random.gauss(230, 2)
        current = random.gauss(15, 1)
        power_factor = random.gauss(0.92, 0.02)
        vibration = random.gauss(0.15, 0.03)
        
        # Compute features
        data.append({
            'timestamp': base_time + timedelta(minutes=i),
            'voltage_rolling_mean_1h': voltage,
            'current_spike_count': random.randint(0, 2),
            'power_factor_efficiency_score': max(0.0, min(1.0, power_factor)),
            'vibration_intensity_rms': max(0.01, vibration),
        })
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    return df


def generate_faulty_data(n_samples: int = 100) -> pd.DataFrame:
    """Generate simulated faulty sensor data with features."""
    data = []
    base_time = datetime.now(timezone.utc) + timedelta(hours=10)
    
    for i in range(n_samples):
        fault_type = random.choice(['spike', 'drift', 'default'])
        
        if fault_type == 'spike':
            voltage = random.uniform(270, 300)
            power_factor = random.uniform(0.55, 0.70)
            vibration = random.uniform(1.5, 3.0)
            spikes = random.randint(5, 15)
        elif fault_type == 'drift':
            voltage = random.uniform(238, 250)
            power_factor = random.uniform(0.78, 0.85)
            vibration = random.uniform(0.25, 0.45)
            spikes = random.randint(2, 5)
        else:
            voltage = random.uniform(245, 280)
            power_factor = random.uniform(0.60, 0.80)
            vibration = random.uniform(0.5, 2.5)
            spikes = random.randint(3, 10)
        
        data.append({
            'timestamp': base_time + timedelta(minutes=i),
            'voltage_rolling_mean_1h': voltage,
            'current_spike_count': spikes,
            'power_factor_efficiency_score': max(0.0, min(1.0, power_factor)),
            'vibration_intensity_rms': vibration,
        })
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    return df


def run_benchmark():
    """Run full model benchmark."""
    print("=" * 60)
    print("ML MODEL BENCHMARK - Upgraded Isolation Forest Detector")
    print("=" * 60)
    
    # 1. Generate training data
    print("\n1. Generating training data (500 healthy samples)...")
    train_data = generate_healthy_data(500)
    print(f"   Training samples: {len(train_data)}")
    
    # 2. Train model
    print("\n2. Training model with derived features + calibration...")
    detector = AnomalyDetector(asset_id="benchmark-test")
    detector.train(train_data)
    print(f"   Model trained on {detector._training_sample_count} samples")
    print(f"   Calibration threshold: {detector._threshold_score:.4f}")
    
    # 3. Generate test data
    print("\n3. Generating test data...")
    healthy_test = generate_healthy_data(200)
    faulty_test = generate_faulty_data(100)
    print(f"   Healthy test samples: {len(healthy_test)}")
    print(f"   Faulty test samples: {len(faulty_test)}")
    
    # 4. Score test data
    print("\n4. Scoring test data...")
    
    healthy_scores = []
    for idx, row in healthy_test.iterrows():
        try:
            features = row.to_dict()
            score = detector.score_single(features)
            healthy_scores.append(score)
        except Exception as e:
            print(f"   Error scoring healthy: {e}")
    
    faulty_scores = []
    for idx, row in faulty_test.iterrows():
        try:
            features = row.to_dict()
            score = detector.score_single(features)
            faulty_scores.append(score)
        except Exception as e:
            print(f"   Error scoring faulty: {e}")
    
    print(f"   Scored {len(healthy_scores)} healthy samples")
    print(f"   Scored {len(faulty_scores)} faulty samples")
    
    # 5. Compute statistics
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    print("\n--- Healthy Data (TARGET: mean < 0.15) ---")
    healthy_arr = np.array(healthy_scores)
    print(f"   Mean score: {healthy_arr.mean():.3f}")
    print(f"   Std dev:    {healthy_arr.std():.3f}")
    print(f"   Min score:  {healthy_arr.min():.3f}")
    print(f"   Max score:  {healthy_arr.max():.3f}")
    
    print("\n--- Faulty Data (TARGET: mean > 0.6) ---")
    faulty_arr = np.array(faulty_scores)
    print(f"   Mean score: {faulty_arr.mean():.3f}")
    print(f"   Std dev:    {faulty_arr.std():.3f}")
    print(f"   Min score:  {faulty_arr.min():.3f}")
    print(f"   Max score:  {faulty_arr.max():.3f}")
    
    # 6. Classification metrics
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
    
    # Healthy stability = % of healthy samples scoring < threshold
    healthy_stability = TN / len(healthy_scores) if healthy_scores else 0
    
    print(f"   True Positives (faults detected):  {TP}")
    print(f"   True Negatives (healthy correct):  {TN}")
    print(f"   False Positives (false alarms):    {FP}")
    print(f"   False Negatives (missed faults):   {FN}")
    print()
    print(f"   ACCURACY:         {accuracy:.1%}")
    print(f"   PRECISION:        {precision:.1%}")
    print(f"   RECALL:           {recall:.1%}")
    print(f"   F1-SCORE:         {f1:.1%}")
    print(f"   HEALTHY STABILITY: {healthy_stability:.1%}")
    
    # 7. Success criteria check
    print("\n" + "=" * 60)
    print("SUCCESS CRITERIA CHECK")
    print("=" * 60)
    
    success = True
    
    if healthy_stability >= 0.95:
        print(f"   [PASS] Healthy Stability: {healthy_stability:.1%} >= 95%")
    else:
        print(f"   [FAIL] Healthy Stability: {healthy_stability:.1%} < 95%")
        success = False
    
    if precision >= 0.80:
        print(f"   [PASS] Precision: {precision:.1%} >= 80%")
    else:
        print(f"   [FAIL] Precision: {precision:.1%} < 80%")
        success = False
    
    if healthy_arr.mean() < 0.15:
        print(f"   [PASS] Healthy Mean Score: {healthy_arr.mean():.3f} < 0.15")
    else:
        print(f"   [FAIL] Healthy Mean Score: {healthy_arr.mean():.3f} >= 0.15")
        success = False
    
    print()
    separation = faulty_arr.mean() - healthy_arr.mean()
    print(f"   Score Separation: {separation:.3f}")
    
    if success:
        print("\n   === ALL CRITERIA PASSED ===")
    else:
        print("\n   === SOME CRITERIA FAILED ===")
    
    return success


if __name__ == "__main__":
    run_benchmark()
