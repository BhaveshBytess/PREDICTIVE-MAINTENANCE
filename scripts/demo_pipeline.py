"""
Predictive Maintenance - End-to-End Pipeline Demo

This script demonstrates the full data flow:
1. Feature Engineering
2. Baseline Construction
3. Anomaly Detection
4. Health Assessment
5. Explainability
6. Report Generation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from datetime import datetime, timezone

print('='*60)
print('PREDICTIVE MAINTENANCE - END-TO-END PIPELINE DEMO')
print('='*60)

# Step 1: Feature Engineering
print('\n[1] FEATURE ENGINEERING')
from backend.features.calculator import (
    calculate_voltage_rolling_mean,
    calculate_current_spike_count,
    calculate_power_factor_efficiency_score,
    calculate_vibration_rms,
    compute_all_features
)

# Simulate sensor data
np.random.seed(42)
data = pd.DataFrame({
    'timestamp': pd.date_range('2026-01-12', periods=100, freq='1min'),
    'voltage_v': np.random.normal(230, 5, 100),
    'current_a': np.random.normal(15, 1.5, 100),
    'power_factor': np.random.uniform(0.85, 0.95, 100),
    'vibration_g': np.random.normal(0.15, 0.03, 100)
})
data.set_index('timestamp', inplace=True)

# Add one anomaly spike
data.loc[data.index[50], 'vibration_g'] = 0.8  # Anomaly!

# Compute features for last point
eval_idx = len(data) - 1
features = compute_all_features(data, eval_idx, data['power_factor'].iloc[-1])

print(f'   [OK] Computed features for {len(data)} samples')
print(f'   - voltage_rolling_mean_1h: {features["voltage_rolling_mean_1h"]:.2f}')
print(f'   - vibration_intensity_rms: {features["vibration_intensity_rms"]:.4f}')

# Step 2: Baseline Construction
print('\n[2] BASELINE CONSTRUCTION')
from backend.ml.baseline import BaselineBuilder

builder = BaselineBuilder()

# Train on 'healthy' data (excluding the spike)
healthy_df = data[data['vibration_g'] < 0.5].copy()
healthy_df['is_fault_injected'] = False
baseline = builder.build(healthy_df, asset_id='Motor-01')
print(f'   [OK] Built baseline from {len(healthy_df)} healthy samples')
print(f'   - Vibration mean: {baseline.signal_profiles["vibration_g"].mean:.4f}')
print(f'   - Vibration std: {baseline.signal_profiles["vibration_g"].std:.4f}')

# Step 3: Anomaly Detection
print('\n[3] ANOMALY DETECTION (Isolation Forest)')
from backend.ml.detector import AnomalyDetector

detector = AnomalyDetector(asset_id='Motor-01')

# Create feature DataFrame for training
feature_data = []
for idx in range(10, len(data)):  # Start after warmup
    f = compute_all_features(data, idx, data['power_factor'].iloc[idx])
    f['idx'] = idx
    feature_data.append(f)

feature_df = pd.DataFrame(feature_data)
feature_cols = ['voltage_rolling_mean_1h', 'current_spike_count', 
                'power_factor_efficiency_score', 'vibration_intensity_rms']
train_features = feature_df[feature_cols].dropna()

detector.train(train_features)

# Score normal vs anomalous
normal_sample = train_features.iloc[:5]
normal_scores = detector.score(normal_sample)
print(f'   [OK] Model trained on {len(train_features)} samples')
print(f'   - Normal data scores: {[f"{s.score:.3f}" for s in normal_scores]}')

# Step 4: Health Assessment
print('\n[4] HEALTH ASSESSMENT')
from backend.rules.assessor import HealthAssessor

assessor = HealthAssessor(
    detector_version='1.0.0',
    baseline_id=baseline.baseline_id
)

# Simulate different anomaly levels
print('   [OK] Risk classification by anomaly score:')
for anomaly_score in [0.1, 0.4, 0.7, 0.95]:
    report = assessor.assess('Motor-01', anomaly_score)
    print(f'     Anomaly={anomaly_score:.2f} -> Health={report.health_score:3.0f}, Risk={report.risk_level.value}')

# Step 5: Explainability
print('\n[5] EXPLAINABILITY ENGINE')
from backend.rules.explainer import ExplanationGenerator
from backend.rules.assessor import RiskLevel

generator = ExplanationGenerator(baseline)

# Simulate anomalous readings
anomalous_readings = {
    'voltage_v': 255.0,  # High
    'vibration_g': 0.45  # High
}

explanations = generator.generate(anomalous_readings, RiskLevel.HIGH, baseline)
print('   [OK] Generated explanations for HIGH risk:')
for exp in explanations:
    print(f'     * {exp.reason}')

# Step 6: Report Generation
print('\n[6] REPORT GENERATION')
from backend.reports.generator import generate_pdf_report, generate_excel_report, generate_filename

# Generate report from assessment
test_report = assessor.assess('Motor-01', 0.35)
pdf_bytes = generate_pdf_report(test_report)
excel_bytes = generate_excel_report(test_report)
filename = generate_filename(test_report.asset_id, test_report.timestamp, 'pdf')

print(f'   [OK] PDF generated: {len(pdf_bytes):,} bytes')
print(f'   [OK] Excel generated: {len(excel_bytes):,} bytes')
print(f'   [OK] Filename: {filename}')

print('\n' + '='*60)
print('[SUCCESS] ALL PIPELINE STAGES VERIFIED SUCCESSFULLY!')
print('='*60)
