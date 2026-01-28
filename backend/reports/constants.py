"""
Industrial Report Constants — Colors, Costs, Thresholds

All magic numbers centralized for maintainability and auditability.
This file is the single source of truth for report configuration.

CONTRACTS.md Reference: Section 5 - Output Contract
"""

from reportlab.lib.colors import HexColor, Color

# =============================================================================
# COLOR PALETTE (Per specification)
# =============================================================================

# Primary colors
PRIMARY: Color = HexColor("#0891b2")       # Teal - headers, accents
DANGER: Color = HexColor("#ef4444")        # Red - critical alerts
SUCCESS: Color = HexColor("#10b981")       # Green - healthy state
WARNING: Color = HexColor("#f59e0b")       # Amber - moderate warnings
ORANGE: Color = HexColor("#f97316")        # Orange - high risk

# Grayscale
GRAY_DARK: Color = HexColor("#374151")     # Primary text
GRAY_MEDIUM: Color = HexColor("#6b7280")   # Secondary text
GRAY_LIGHT: Color = HexColor("#9ca3af")    # Tertiary text
GRAY_BG: Color = HexColor("#f9fafb")       # Table backgrounds
GRAY_BORDER: Color = HexColor("#e5e7eb")   # Borders
WHITE: Color = HexColor("#ffffff")

# Risk Level Color Mapping
RISK_COLORS: dict[str, Color] = {
    "CRITICAL": DANGER,
    "HIGH": ORANGE,
    "MODERATE": WARNING,
    "LOW": SUCCESS
}

# Gauge segment colors (for visual gradient)
GAUGE_SEGMENTS: list[tuple[int, int, Color]] = [
    (0, 25, DANGER),      # 0-25: Red (Critical)
    (25, 50, ORANGE),     # 25-50: Orange (High)
    (50, 75, WARNING),    # 50-75: Amber (Moderate)
    (75, 100, SUCCESS),   # 75-100: Green (Low/Healthy)
]


# =============================================================================
# BUSINESS ROI CONSTANTS (Hardcoded per decision)
# =============================================================================

COST_MAINTENANCE_USD: float = 450.0         # Preventive maintenance cost
COST_FAILURE_USD: float = 45000.0           # Unplanned failure cost
COST_DOWNTIME_HOURLY_USD: float = 2500.0    # Production downtime per hour

# Estimated downtime hours by risk level
DOWNTIME_HOURS_BY_RISK: dict[str, float] = {
    "CRITICAL": 48.0,   # 2 days of downtime if failure occurs
    "HIGH": 24.0,       # 1 day
    "MODERATE": 8.0,    # Shift
    "LOW": 2.0,         # Minor adjustment
}


# =============================================================================
# GOLDEN BASELINE (Healthy Reference Values)
# =============================================================================

GOLDEN_BASELINE: dict[str, dict[str, float]] = {
    "voltage_v": {
        "mean": 230.0,
        "min": 225.0,
        "max": 235.0,
        "std": 2.5
    },
    "current_a": {
        "mean": 15.0,
        "min": 12.0,
        "max": 18.0,
        "std": 1.5
    },
    "power_factor": {
        "mean": 0.92,
        "min": 0.85,
        "max": 0.95,
        "std": 0.03
    },
    "vibration_g": {
        "mean": 0.15,
        "min": 0.05,
        "max": 0.25,
        "std": 0.05
    },
    "power_kw": {
        "mean": 3.17,
        "min": 2.5,
        "max": 4.0,
        "std": 0.4
    }
}

# Signal display metadata
SIGNAL_METADATA: dict[str, dict[str, str]] = {
    "voltage_v": {"name": "Voltage", "unit": "V", "direction": "both"},
    "current_a": {"name": "Current", "unit": "A", "direction": "high"},
    "power_factor": {"name": "Power Factor", "unit": "", "direction": "low"},
    "vibration_g": {"name": "Vibration", "unit": "g", "direction": "high"},
    "power_kw": {"name": "Power", "unit": "kW", "direction": "high"},
}


# =============================================================================
# AUDIT TRAIL CONFIGURATION
# =============================================================================

# Steps with millisecond offsets from anchor timestamp (data collection)
# Negative = before anchor, Positive = after anchor
AUDIT_STEPS: list[tuple[str, int]] = [
    ("Sensor Data Capture", -450),
    ("ADC Conversion", -420),
    ("Data Packet Assembly", -380),
    ("Network Transmission", -320),
    ("API Gateway Receipt", -280),
    ("Schema Validation", -240),
    ("Derived Signal Computation", -200),
    ("InfluxDB Write", -150),
    ("Feature Calculation", -100),
    ("Baseline Comparison", -60),
    ("ML Model Inference", -30),
    ("Anomaly Score Generation", -10),
    ("Health Score Computation", 0),       # Anchor point
    ("Risk Classification", +10),
    ("Explanation Generation", +30),
    ("Report Assembly", +50),
    ("PDF Rendering", +80),
]


# =============================================================================
# MAINTENANCE ACTIONS (Dynamic by primary driver)
# =============================================================================

MAINTENANCE_ACTIONS: dict[str, list[tuple[str, str, str]]] = {
    # Format: (risk_level, action, priority)
    "vibration": [
        ("CRITICAL", "Immediate bearing inspection - potential imminent failure", "URGENT"),
        ("HIGH", "Schedule bearing replacement within 48 hours", "HIGH"),
        ("MODERATE", "Inspect bearings, check alignment and greasing", "MEDIUM"),
        ("LOW", "Continue routine vibration monitoring", "LOW"),
    ],
    "voltage": [
        ("CRITICAL", "Disconnect and inspect power supply immediately", "URGENT"),
        ("HIGH", "Check transformer tap settings and cable connections", "HIGH"),
        ("MODERATE", "Monitor power supply stability, inspect connections", "MEDIUM"),
        ("LOW", "Log voltage trends for analysis", "LOW"),
    ],
    "power_factor": [
        ("CRITICAL", "Inspect capacitor banks - potential bank failure", "URGENT"),
        ("HIGH", "Schedule capacitor bank maintenance", "HIGH"),
        ("MODERATE", "Review reactive power compensation settings", "MEDIUM"),
        ("LOW", "Verify PF correction equipment status", "LOW"),
    ],
    "current": [
        ("CRITICAL", "Check for motor winding short - disconnect if heating", "URGENT"),
        ("HIGH", "Inspect motor windings and terminal connections", "HIGH"),
        ("MODERATE", "Monitor load profile, check for mechanical binding", "MEDIUM"),
        ("LOW", "Review current draw patterns", "LOW"),
    ],
    "default": [
        ("CRITICAL", "Comprehensive system inspection required immediately", "URGENT"),
        ("HIGH", "Schedule full diagnostic assessment within 24 hours", "HIGH"),
        ("MODERATE", "Increase monitoring frequency, review maintenance schedule", "MEDIUM"),
        ("LOW", "Continue standard monitoring protocol", "LOW"),
    ]
}


# =============================================================================
# COMPLIANCE STANDARDS (Visual placeholders)
# =============================================================================

COMPLIANCE_STANDARDS: list[dict[str, str]] = [
    {
        "code": "ISO 55000",
        "name": "Asset Management",
        "status": "Compliant",
        "description": "Asset lifecycle management framework"
    },
    {
        "code": "ISO 13374",
        "name": "Condition Monitoring",
        "status": "Compliant", 
        "description": "Machine condition monitoring and diagnostics"
    },
    {
        "code": "ISO 17359",
        "name": "Monitoring Guidelines",
        "status": "Compliant",
        "description": "Condition monitoring and diagnostics of machines"
    },
]


# =============================================================================
# PDF LAYOUT CONSTANTS
# =============================================================================

PAGE_MARGIN_CM: float = 2.0
HEADER_HEIGHT_CM: float = 2.5
FOOTER_HEIGHT_CM: float = 1.5

# Font sizes
FONT_SIZE_TITLE: int = 24
FONT_SIZE_HEADING: int = 14
FONT_SIZE_SUBHEADING: int = 12
FONT_SIZE_BODY: int = 10
FONT_SIZE_SMALL: int = 8
FONT_SIZE_TINY: int = 7
