"""
Test script for sandbox heuristic scoring.
Verifies that all 4 risk levels are produced with different inputs.

Standalone version - doesn't import from backend to avoid dependency issues.
"""

from pydantic import BaseModel, Field

# Copy of the sandbox logic for testing
class ManualTestInput(BaseModel):
    voltage_v: float = Field(..., ge=150, le=300)
    current_a: float = Field(..., ge=1, le=50)
    power_factor: float = Field(..., ge=0.3, le=1.0)
    vibration_g: float = Field(..., ge=0.01, le=10.0)

def _heuristic_scoring(input_data: ManualTestInput) -> float:
    """
    Fallback heuristic scoring when ML detector is not available.
    """
    HEALTHY_VOLTAGE = 230.0
    HEALTHY_CURRENT = 15.0
    HEALTHY_PF = 0.92
    HEALTHY_VIBRATION = 0.15
    
    VOLTAGE_TOLERANCE = 15.0
    CURRENT_TOLERANCE = 8.0
    PF_TOLERANCE = 0.12
    VIBRATION_TOLERANCE = 0.35
    
    voltage_dev = abs(input_data.voltage_v - HEALTHY_VOLTAGE) / VOLTAGE_TOLERANCE
    current_dev = max(0, input_data.current_a - HEALTHY_CURRENT) / CURRENT_TOLERANCE
    pf_dev = max(0, HEALTHY_PF - input_data.power_factor) / PF_TOLERANCE
    vibration_dev = max(0, input_data.vibration_g - HEALTHY_VIBRATION) / VIBRATION_TOLERANCE
    
    weighted_dev = (
        voltage_dev * 0.2 +
        current_dev * 0.2 +
        pf_dev * 0.3 +
        vibration_dev * 0.3
    )
    
    if weighted_dev <= 0.3:
        anomaly_score = weighted_dev * 0.25 / 0.3
    elif weighted_dev <= 0.7:
        anomaly_score = 0.25 + (weighted_dev - 0.3) * 0.25 / 0.4
    elif weighted_dev <= 1.2:
        anomaly_score = 0.50 + (weighted_dev - 0.7) * 0.25 / 0.5
    else:
        anomaly_score = 0.75 + min(0.24, (weighted_dev - 1.2) * 0.12)
    
    return min(0.99, max(0.0, anomaly_score))


# Test cases
test_cases = [
    # LOW (health 75-100)
    {"name": "Normal", "voltage": 230, "current": 15, "pf": 0.92, "vibration": 0.15},
    {"name": "Slight variation", "voltage": 235, "current": 16, "pf": 0.90, "vibration": 0.18},
    
    # MODERATE (health 50-75)
    {"name": "Elevated vibration", "voltage": 228, "current": 18, "pf": 0.85, "vibration": 0.4},
    {"name": "Lower PF", "voltage": 232, "current": 20, "pf": 0.80, "vibration": 0.25},
    
    # HIGH (health 25-50)
    {"name": "High vibration", "voltage": 225, "current": 22, "pf": 0.75, "vibration": 0.7},
    {"name": "Multiple issues", "voltage": 245, "current": 25, "pf": 0.72, "vibration": 0.5},
    
    # CRITICAL (health 0-25)
    {"name": "Motor Stall", "voltage": 210, "current": 35, "pf": 0.55, "vibration": 2.5},
    {"name": "Bearing Failure", "voltage": 228, "current": 16, "pf": 0.88, "vibration": 3.8},
]

print("=" * 70)
print("SANDBOX HEURISTIC SCORING TEST")
print("=" * 70)
print()

risk_counts = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "CRITICAL": 0}

for tc in test_cases:
    input_data = ManualTestInput(
        voltage_v=tc["voltage"],
        current_a=tc["current"],
        power_factor=tc["pf"],
        vibration_g=tc["vibration"]
    )
    
    score = _heuristic_scoring(input_data)
    health = int(100 * (1.0 - score))
    
    if health >= 75:
        risk = "LOW"
    elif health >= 50:
        risk = "MODERATE"
    elif health >= 25:
        risk = "HIGH"
    else:
        risk = "CRITICAL"
    
    risk_counts[risk] += 1
    
    print(f"{tc['name']:30} | Score: {score:.3f} | Health: {health:3d} | Risk: {risk}")

print()
print("-" * 70)
print("RISK LEVEL DISTRIBUTION:")
for level, count in risk_counts.items():
    status = "✅" if count > 0 else "❌"
    print(f"  {status} {level}: {count} cases")

print()
if all(c > 0 for c in risk_counts.values()):
    print("✅ ALL RISK LEVELS COVERED!")
else:
    missing = [k for k, v in risk_counts.items() if v == 0]
    print(f"❌ MISSING RISK LEVELS: {missing}")
