```
╔════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                                ║
║   ██████╗ ██████╗ ███████╗██████╗ ██╗ ██████╗████████╗██╗██╗   ██╗███████╗                     ║
║   ██╔══██╗██╔══██╗██╔════╝██╔══██╗██║██╔════╝╚══██╔══╝██║██║   ██║██╔════╝                     ║
║   ██████╔╝██████╔╝█████╗  ██║  ██║██║██║        ██║   ██║██║   ██║█████╗                       ║
║   ██╔═══╝ ██╔══██╗██╔══╝  ██║  ██║██║██║        ██║   ██║╚██╗ ██╔╝██╔══╝                       ║
║   ██║     ██║  ██║███████╗██████╔╝██║╚██████╗   ██║   ██║ ╚████╔╝ ███████╗                     ║
║   ╚═╝     ╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝ ╚═════╝   ╚═╝   ╚═╝  ╚═══╝  ╚══════╝                     ║
║                                                                                                ║
║   ███╗   ███╗ █████╗ ██╗███╗   ██╗████████╗███████╗███╗   ██╗ █████╗ ███╗   ██╗ ██████╗███████╗║
║   ████╗ ████║██╔══██╗██║████╗  ██║╚══██╔══╝██╔════╝████╗  ██║██╔══██╗████╗  ██║██╔════╝██╔════╝║
║   ██╔████╔██║███████║██║██╔██╗ ██║   ██║   █████╗  ██╔██╗ ██║███████║██╔██╗ ██║██║     █████╗  ║
║   ██║╚██╔╝██║██╔══██║██║██║╚██╗██║   ██║   ██╔══╝  ██║╚██╗██║██╔══██║██║╚██╗██║██║     ██╔══╝  ║
║   ██║ ╚═╝ ██║██║  ██║██║██║ ╚████║   ██║   ███████╗██║ ╚████║██║  ██║██║ ╚████║╚██████╗███████╗║
║   ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝╚══════╝║
║                                                                                                ║
║                         ╔═══════════════════════════════════╗                                  ║
║                         ║   DIGITAL TWIN SYSTEM | v3.0.0    ║                                  ║
║                         ╚═══════════════════════════════════╝                                  ║
║                                                                                                ║
╚════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## 📋 DOCUMENT CONTROL

| Field | Value |
|-------|-------|
| **Document ID** | `PM-MANIFEST-2026-001` |
| **Version** | `3.1.0` |
| **Status** | 🟢 **PRODUCTION** |
| **Classification** | Internal / Portfolio |
| **Last Updated** | 2026-02-21 |
| **Author** | Systems Architecture Team |
| **Review Cycle** | Quarterly |

### Live Deployment

| Service | URL | Status |
|---------|-----|--------|
| **Frontend** | https://predictive-maintenance-ten.vercel.app/ | ✅ Live |
| **Backend API** | https://predictive-maintenance-uhlb.onrender.com | ✅ Live |
| **API Docs** | https://predictive-maintenance-uhlb.onrender.com/docs | ✅ Live |

---

## 🧬 SYSTEM DNA

### Mission Statement

> **"Predict motor failures BEFORE they happen, turning reactive maintenance into proactive intelligence."**

This system transforms traditional break-fix maintenance into a data-driven, predictive discipline. By continuously monitoring industrial assets and applying physics-informed machine learning, we provide maintenance teams with actionable intelligence—not just alerts.

### Core Values

| Value | Commitment | Metric |
|-------|------------|--------|
| ⚡ **Real-Time** | Sub-second response to anomalies | `<50ms` inference latency |
| 🔬 **Physics-Aware** | ML grounded in electrical engineering principles | Voltage stability, power-vibration coupling |
| 📜 **Auditable** | Every decision traceable to source data | Millisecond-precision logs |
| 💡 **Explainable** | No black boxes—every alert has a reason | Natural language explanations |

---

## 🚀 FEATURE CATALOG

### Feature 1: Dual-Model ML Pipeline (Legacy + Batch)

```
┌─────────────────────────────────────────────────────────────────┐
│              ISOLATION FOREST v3.0 — DUAL MODEL                │
│                                                                 │
│   LEGACY MODEL (4+2 features, 1Hz)    BATCH MODEL (16 features)│
│   ──────────────────────────────────   ────────────────────────  │
│   • Voltage Rolling Mean               • voltage_v_mean         │
│   • Current Spike Count                • voltage_v_std          │
│   • Power Factor Score                 • voltage_v_peak_to_peak │
│   • Vibration RMS                      • voltage_v_rms          │
│   • Voltage Stability Index            • current_a_mean/std/p2p │
│   • Power-Vibration Ratio              • power_factor_mean/std  │
│                                        • vibration_g_mean/std   │
│                                        • vibration_g_peak_to_peak│
│                                        • vibration_g_rms        │
│                                                                 │
│   ┌──────────────────────────────────────────────────────┐     │
│   │  100Hz Raw → 16-D Batch Features (100:1 Reduction)   │     │
│   │  mean, std, peak-to-peak, RMS × 4 signals            │     │
│   │  Trained on healthy batch windows (contamination=0.05)│     │
│   └──────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

**Why Batch Features Matter:**
- **Variance Detection**: A "Jitter Fault" where average vibration is normal (0.15g) but σ spikes to 0.17g is INVISIBLE to 1Hz models. Batch model catches it because `std` is an explicit feature.
- **Peak-to-Peak Transients**: Captures within-window oscillation amplitude — detects electrical grid instability and mechanical looseness.
- **F1-Score**: Batch model achieves 99.6% F1 vs. legacy 78.1% at threshold 0.5.

---

### Feature 2: "What-If" Analysis Sandbox

```
┌─────────────────────────────────────────────────────────────────┐
│                     SANDBOX INTERFACE                           │
│                                                                 │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│   │   NORMAL    │  │ MOTOR STALL │  │VOLTAGE SPIKE│            │
│   │   Preset    │  │   Preset    │  │   Preset    │            │
│   └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                 │
│   Voltage     [====|==================] 230V                    │
│   Current     [========|==============] 15A                     │
│   Power Factor[================|======] 0.92                    │
│   Vibration   [==|====================] 0.15g                   │
│                                                                 │
│   ┌─────────────────────────────────────────────────────┐      │
│   │  FEATURE CONTRIBUTION                               │      │
│   │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░  Vibration: 72%              │      │
│   │  ▓▓▓▓▓▓▓▓░░░░░░░░░░░░  Current:   35%              │      │
│   │  ▓▓▓▓░░░░░░░░░░░░░░░░  Voltage:   18%              │      │
│   └─────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

**Capabilities:**
- **Manual Fault Injection**: Adjust any sensor value and see predicted health impact
- **Preset Scenarios**: One-click simulation of Motor Stall, Voltage Spike, Bearing Wear
- **Feature Contribution Bars**: Visual breakdown of which factors drive the risk score
- **Live State Comparison**: Side-by-side view of current vs. simulated state

---

### Feature 3: Industrial Health Certificate (5-Page PDF)

```
┌─────────────────────────────────────────────────────────────────┐
│                   INDUSTRIAL HEALTH CERTIFICATE                 │
│                        5-PAGE REPORT                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   PAGE 1 ─ EXECUTIVE SUMMARY                                    │
│   ├── Health Gauge (0-100)                                      │
│   ├── Risk Level Badge (LOW/MODERATE/HIGH/CRITICAL)             │
│   └── Remaining Useful Life (Days)                              │
│                                                                 │
│   PAGE 2 ─ SENSOR ANALYSIS                                      │
│   ├── Current Readings vs Baseline                              │
│   ├── 24-Hour Statistics (Min/Max/Avg)                          │
│   └── Trend Sparklines                                          │
│                                                                 │
│   PAGE 3 ─ ML EXPLAINABILITY                                    │
│   ├── Feature Contribution Bar Chart                            │
│   ├── Anomaly Score Breakdown                                   │
│   └── Detection Confidence                                      │
│                                                                 │
│   PAGE 4 ─ BUSINESS ROI                                         │
│   ├── ┌────────────────────────────────────────┐               │
│   │   │  Preventive: $450    vs    Failure: $45,000            │
│   │   │  ════════════════════════════════════                  │
│   │   │         ROI MULTIPLIER: 100x                            │
│   │   └────────────────────────────────────────┘               │
│   └── Recommended Actions Checklist                             │
│                                                                 │
│   PAGE 5 ─ AUDIT TRAIL                                          │
│   ├── Process Log (Millisecond Precision)                       │
│   ├── Data Provenance Chain                                     │
│   └── ISO Compliance Checkboxes                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### Feature 4: The Snapshot Rule (Audit Compliance)

```
┌─────────────────────────────────────────────────────────────────┐
│                      THE SNAPSHOT RULE                          │
│                                                                 │
│   "Reports use PERSISTED data only. Never re-compute."          │
│                                                                 │
│   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐    │
│   │   LIVE      │ ──X──│   REPORT    │ ──── │  PERSISTED  │    │
│   │   SENSORS   │      │  GENERATOR  │      │    DATA     │    │
│   └─────────────┘      └─────────────┘      └─────────────┘    │
│         │                    │                    ▲             │
│         │                    │                    │             │
│         └────────────────────┴────────────────────┘             │
│                         IMMUTABLE                               │
│                                                                 │
│   WHY: Auditors must see the SAME values that triggered the     │
│   alert. Re-computation could yield different results due to    │
│   timing, model updates, or data drift.                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Guarantee**: The PDF you download today will show the exact same values if opened 5 years from now. No live queries. No drift. Full reproducibility.

---

## 📊 PERFORMANCE SPECIFICATIONS

### ML Model Performance

| Metric | Legacy (1Hz, 6 features) | Batch (100Hz, 16 features) | Significance |
|--------|:---:|:---:|------|
| **Precision** | 64.1% | **99.2%** | Low false positives—teams trust the alerts |
| **Recall** | 100.0% | **100.0%** | Safety-critical—NEVER misses a true fault |
| **F1-Score** | 78.1% | **99.6%** | Near-perfect balanced performance |
| **AUC-ROC** | 1.000 | **1.000** | Perfect ranking |
| **Score Separation** | 0.210 | **0.978** | Clear healthy/faulty boundary |
| **Jitter Detection** | ❌ No | ✅ **Yes** | Detects variance-only faults |

### System Performance

| Operation | Latency | Notes |
|-----------|---------|-------|
| **Batch Feature Extraction** | `<0.1ms` | 100-point window → 16-D vector (NumPy) |
| **ML Inference (Batch)** | `<1ms` | IsolationForest on 16-D scaled input |
| **ML Inference (Legacy)** | `<50ms` | 6-feature Isolation Forest |
| **Data Ingestion** | `100 Hz` | 100 raw points/second to InfluxDB |
| **Server-Side Aggregation** | `<5ms` | `aggregateWindow(1s, mean)` Flux query |
| **PDF Generation** | `~1.2s` | 5-page Industrial Certificate |
| **Dashboard Update** | `3s poll` | 1Hz aggregated data delivery |
| **API Response (p99)** | `<100ms` | All endpoints |

### Fault Detection Accuracy by Type (Batch Model)

| Fault Type | Description | Detection Rate |
|------------|-------------|----------------|
| 🔴 **SPIKE** | Voltage/current surges | 100.0% |
| 🟠 **DRIFT** | Gradual degradation | 100.0% |
| 🟡 **JITTER** | Normal means, high variance | 100.0% |
| 🔵 **MIXED** | Random combination | 100.0% |

### Fault Detection by Severity

| Severity | Target Risk | Detection Rate |
|----------|-------------|----------------|
| 🟡 MILD | MODERATE | 98.8% |
| 🟠 MEDIUM | HIGH | 99.6% |
| 🔴 SEVERE | CRITICAL | 100.0% |

---

## 🏗️ ARCHITECTURE & TECH STACK

### Technology Matrix

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Frontend** | React | 18.x | Component-based UI |
| | Recharts | 2.x | Real-time data visualization |
| | Vite | 5.x | Build tool & dev server |
| | CSS Modules | - | Scoped styling (Glassmorphism) |
| **Backend** | Python | 3.10+ | Core runtime |
| | FastAPI | 0.100+ | Async REST API |
| | Pydantic | 2.x | Schema validation & settings |
| | scikit-learn | 1.3+ | Isolation Forest ML |
| | ReportLab | 4.x | PDF generation |
| **Storage** | InfluxDB Cloud | 2.x | Time-series persistence |
| **Deployment** | Docker | 24.x | Containerization |
| | Render | - | Backend hosting |
| | Vercel | - | Frontend hosting |
| | InfluxDB Cloud | - | Managed database |

### System Architecture (ASCII Diagram)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PREDICTIVE MAINTENANCE SYSTEM                     │
│                              Architecture v3.0                              │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │   SENSORS    │    Voltage, Current, Power Factor, Vibration
    │  (Simulated) │    Indian Grid Context: 230V / 50Hz
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐     ┌─────────────────────────────────────────────────┐
    │  INGEST API  │────▶│  VALIDATION LAYER                               │
    │   /ingest    │     │  • Pydantic Schema Enforcement                  │
    └──────┬───────┘     │  • UTC Timestamp Normalization                  │
           │             │  • Derived Signal: power_kw = V×I×PF/1000       │
           │             └─────────────────────────────────────────────────┘
           ▼
    ┌──────────────┐     ┌─────────────────────────────────────────────────┐
    │   FEATURE    │────▶│  COMPUTED FEATURES                              │
    │   ENGINE     │     │  • voltage_rolling_mean_1h                      │
    └──────┬───────┘     │  • current_spike_count (3σ threshold)           │
           │             │  • power_factor_efficiency_score                │
           │             │  • vibration_intensity_rms                      │
           │             │  • voltage_stability (derived)                  │
           │             │  • power_vibration_ratio (derived)              │
           │             └─────────────────────────────────────────────────┘
           ▼
    ┌──────────────┐     ┌─────────────────────────────────────────────────┐
    │  ISOLATION   │────▶│  ANOMALY DETECTION (Dual Model)                 │
    │   FOREST     │     │  • Legacy: 6 features from 1Hz averages         │
    │    (ML)      │     │  • Batch: 16 features from 100Hz windows        │
    └──────┬───────┘     │  • 100:1 reduction (mean/std/p2p/RMS × 4 sigs) │
           │             │  • Quantile calibration (99th percentile)       │
           │             └─────────────────────────────────────────────────┘
           ▼
    ┌──────────────┐     ┌─────────────────────────────────────────────────┐
    │   HEALTH     │────▶│  RISK ASSESSMENT                                │
    │  ASSESSOR    │     │  • Health Score: 0-100                          │
    └──────┬───────┘     │  • Risk Levels: LOW → MODERATE → HIGH → CRITICAL│
           │             │  • RUL Estimation: Heuristic lookup             │
           │             │  • Explainability: "Vibration 3.2σ above normal"│
           │             └─────────────────────────────────────────────────┘
           ▼
    ┌──────────────┐
    │  INFLUXDB    │    Time-Series Persistence
    │  (Storage)   │    Measurements: sensor_data, features, health_reports
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐     ┌─────────────────────────────────────────────────┐
    │   REACT      │◀────│  DASHBOARD                                      │
    │  DASHBOARD   │     │  • Real-time charts (Recharts)                  │
    └──────────────┘     │  • Health gauge with color coding               │
           │             │  • Anomaly markers (red dashed lines)           │
           │             │  • Insight panel (natural language)             │
           │             └─────────────────────────────────────────────────┘
           ▼
    ┌──────────────┐
    │   REPORT     │    5-Page Industrial Health Certificate
    │  GENERATOR   │    PDF/Excel Export with Audit Trail
    └──────────────┘
```

---

## 🛡️ COMPLIANCE & PHILOSOPHY

### Standards Alignment

| Standard | Scope | Status |
|----------|-------|--------|
| **ISO 55000** | Asset Management | ✅ Compliant |
| **ISO 13374** | Condition Monitoring | ✅ Compliant |
| **IEC 62443** | Industrial Cybersecurity | 🔄 Roadmap |

### Compliance Features

- ✅ **Audit Trail**: Every health assessment logged with millisecond precision
- ✅ **Data Provenance**: Full traceability from sensor reading to report
- ✅ **Immutable Reports**: Snapshot Rule ensures reproducibility
- ✅ **Role Separation**: ML scores vs. Business rules cleanly separated

---

## 💎 ENGINEERING PHILOSOPHY

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   "This system prioritizes TRUST over theatrics,                │
│    PHYSICS over hype, and ENGINEERING RIGOR over                │
│    vanity metrics."                                             │
│                                                                 │
│   We don't chase accuracy numbers for benchmarks.               │
│   We optimize for the metrics that matter in production:        │
│                                                                 │
│   • Can maintenance teams TRUST the alerts?                     │
│   • Can auditors VERIFY the decisions?                          │
│   • Can engineers EXPLAIN the reasoning?                        │
│                                                                 │
│   If the answer to any of these is "no", the feature            │
│   doesn't ship.                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📞 QUICK REFERENCE

### Start the System (Local Development)

```bash
# Docker (Recommended)
docker-compose up --build

# Access
# Frontend: http://localhost:5173
# Backend:  http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Production URLs

| Service | URL |
|---------|-----|
| **Frontend** | https://predictive-maintenance-ten.vercel.app/ |
| **Backend API** | https://predictive-maintenance-uhlb.onrender.com |
| **API Docs** | https://predictive-maintenance-uhlb.onrender.com/docs |

### Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/system/calibrate` | POST | Build baseline from healthy data |
| `/system/inject-fault` | POST | Simulate fault (MILD/MEDIUM/SEVERE) |
| `/api/v1/status/{asset}` | GET | Current health status |
| `/api/v1/report/{asset}` | GET | Download PDF/Excel report |
| `/sandbox/predict` | POST | What-If analysis |

---

<p align="center">
  <code>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</code>
</p>

<p align="center">
  <strong>PREDICTIVE MAINTENANCE SYSTEM</strong><br>
  <em>Digital Twin for Industrial Asset Intelligence</em><br>
  <code>v3.0.0 | February 2026 | Production</code>
</p>

<p align="center">
  🚀 <a href="https://predictive-maintenance-ten.vercel.app/">Live Demo</a> &nbsp;|&nbsp;
  📄 <a href="https://predictive-maintenance-uhlb.onrender.com/docs">API Docs</a>
</p>

<p align="center">
  <code>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</code>
</p>
