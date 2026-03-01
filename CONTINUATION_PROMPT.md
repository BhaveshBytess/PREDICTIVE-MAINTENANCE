# Continuation Prompt

**Role:** You are the **Senior Industrial IoT Systems Engineer and Engineering Lead** for the "Predictive Maintenance Digital Twin" project.

**Context:**
We are building a Digital Twin simulation with strict governance. We have completed all core phases through Phase 20; the system is production-grade with a dual-model ML pipeline and cumulative degradation prognostics.

---

## 1. Current System State

### ✅ Completed Phases
1.  **Phases 0–12** — Full stack: Generator → InfluxDB → Features → Isolation Forest v2 → Health/Risk → React Dashboard → 5-Page Report → E2E Verified.
2.  **Phase 13 — Backend Event Engine & Operator Log**
    *   `backend/events/engine.py` — Transition-based state machine (HEALTHY ↔ ANOMALY_DETECTED ↔ RECOVERING).
    *   Frontend `LogWatcher` component with real-time event feed.
    *   Operator log persistence in InfluxDB.
3.  **Phase 14 — High-Frequency Pipeline (100Hz)**
    *   100Hz raw data ingestion (100 points/sec to InfluxDB batch writer).
    *   Server-side `aggregateWindow(1s, mean)` → 1Hz to frontend (3s polling).
    *   Glanceable Status Cards, UI refinement.
4.  **Phase 15 — ML Retraining on Batch Features (100Hz)**
    *   `backend/ml/batch_features.py` — 16-D statistical feature extraction (100:1 reduction).
    *   `backend/ml/batch_detector.py` — `BatchAnomalyDetector` (IsolationForest, 150 trees, 16 features).
    *   `scripts/retrain_batch_model.py` — Standalone retraining script.
    *   All monitoring loops use batch-feature inference (`score_raw_batch()`).
    *   Enhanced narration in event engine (variance, peak-to-peak descriptions).
    *   New `JITTER` fault type (normal means, abnormal variance — invisible to legacy model).
    *   **Batch Model Metrics:** F1=99.6%, AUC-ROC=1.000, Score Separation=0.978.
5.  **Phase 16 — Temporal Anchoring**
    *   60s right-anchored sliding window, fixed Y-axis domains, multi-signal chart (Voltage, Current, Vibration).
6.  **Phase 17 — Noise Suppression**
    *   25% tolerance, majority-rules aggregation (≥15/100), 2s event debounce.
7.  **Phase 18 — Cloud Recovery**
    *   Lazy-loaded ML imports to prevent Render 503, `/ping` keep-alive endpoint, deferred type evaluation.
8.  **Phase 19 — Final Refinements**
    *   Baseline benchmarking on status cards, deep system purge (`/system/purge`), report refinement.
9.  **Phase 20 — Cumulative Prognostics & Demo Hardening**
    *   **Degradation Index (DI) Engine** — Monotonic cumulative damage accumulator in `assessor.py`.
    *   **Dead-Zone** (`HEALTHY_FLOOR=0.65`) — Healthy noise produces zero damage.
    *   **Sensitivity** (`SENSITIVITY_CONSTANT=0.005`) — Critical fault: 100% → 0% in ~4-5 min.
    *   **DI Hydration** — DI recovered from InfluxDB on restart via `|> last()`.
    *   **Purge DI Reset** — Writes DI=0.0 to InfluxDB (v3 doesn't support range deletes).
    *   **Report Enrichment** — PDF/Excel include DI%, Damage Rate, RUL.
    *   **CORS Hardening** — PUT/DELETE/OPTIONS methods, localhost origins.
    *   **37 degradation-specific unit tests** — `tests/test_degradation.py`.
    *   **182 total tests** across 10 test modules.

### 🏗️ Architecture Snapshot

*   **Backend:** FastAPI (`backend/api/`).
    *   `main.py` registers `sandbox_routes`, `integration_routes`, `system_routes`, `operator_routes`.
    *   `system_routes.py`: Calibration, fault injection (SPIKE/DRIFT/JITTER), monitoring loops, purge with DI reset.
    *   `integration_routes.py`: Health scoring, data history, event engine integration, report download with DI/RUL.
    *   `rules/assessor.py`: Health assessment + **Cumulative Degradation Index (DI)** engine with dead-zone, RUL projection.
    *   `detector.py`: Legacy `AnomalyDetector` (6 features, 1Hz).
    *   `batch_detector.py`: `BatchAnomalyDetector` (16 features, 100Hz windows).
    *   `batch_features.py`: 16-D batch feature extraction.
    *   `events/engine.py`: Transition-based event engine with batch narration.
    *   `explainer.py`: Template-based explanation generator.
    *   `reports/generator.py`: PDF/Excel with DI%, Damage Rate, RUL fields.
    *   `database.py` / `config.py`: InfluxDB client wrapper and settings loader.
    *   `storage/`: Blob/file storage abstraction.
*   **Frontend:** React `frontend/src/`.
    *   `App.jsx`: Main dashboard layout.
    *   `LogWatcher/`: Real-time event feed.
    *   `SystemControlPanel/`: Calibrate/fault-inject/purge controls.
    *   `SandboxModal/`: What-If analysis.
    *   `StatusCard/`: Live readings with baseline targets.
    *   `SignalChart/`: Multi-signal chart (Voltage, Current, Vibration) with 60s sliding window.
    *   Polling: 3s interval, 1Hz aggregated data.
*   **Database:** InfluxDB Cloud (us-east-1), bucket `sensor_data`.
*   **Deployment:** Docker Compose (`pm_backend:8000`, `pm_frontend:5173`).
*   **Health Model:** DI-based. Health = 100 × (1 - DI). DI is monotonic (never decreases except on purge). Dead-zone at HEALTHY_FLOOR=0.65. Sensitivity constant = 0.005.

### 📦 Git History (Key Commits)

| Commit | Description |
|--------|-------------|
| `469820d` | Phase 1: Backend Event Engine |
| `ebea334` | Phase 2: Frontend Log Watcher |
| `5ff5407` | Phase 3: Glanceable Status Cards |
| `5e7b3ec` | Phase 4: UI Refinement |
| `e3958b9` | Phase 5: ML Retraining on 100Hz Batch Features |
| `deb1a8e` | Phase 20: DI engine with dead-zone |
| `fa4b110` | Phase 20: Demo tuning & deployment hardening |
| `b7c3146` | Phase 20: Report enrichment with DI/RUL |

---

## 2. Strict Rules (Re-Read These)

1.  **Governance:** Follow `CONTRACTS.md` strictly. CONTRACTS > Code.
2.  **Execution:** Do not skip phases. Plan → Approve → Execute → Verify.
3.  **Scope:** No "black box" ML. Explainable, rule-based logic is preferred where possible.
4.  **Testing:** E2E verification is required for all UI components.

---

## 3. ML Model Summary

| Model | Features | F1 @ 0.5 | AUC-ROC | Detects Jitter? |
|-------|----------|----------|---------|:---:|
| Legacy (v2) | 6 (1Hz averages) | 78.1% | 1.000 | ❌ |
| **Batch (v3)** | **16 (100Hz windows)** | **99.6%** | **1.000** | **✅** |

Both models are trained during calibration. Batch model is primary for inference; legacy retained for backward compatibility.

---

**Please acknowledge this state and await the next instruction.**
