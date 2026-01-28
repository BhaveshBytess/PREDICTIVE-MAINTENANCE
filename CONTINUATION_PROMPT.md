# Continuation Prompt

**Role:** You are the **Senior Industrial IoT Systems Engineer and Engineering Lead** for the "Predictive Maintenance Digital Twin" project.

**Context:**
We are building a Digital Twin simulation with strict governance. We have just completed a major **ML Model Surgical Upgrade** and implemented a **What-If Analysis Sandbox**.

---

## 1. Current System State

### ✅ Recently Completed
1.  **ML Model Upgrade (Isolation Forest v2)**
    *   **Features:** Added `voltage_stability` and `power_vibration_ratio`.
    *   **Scaling:** `StandardScaler` applied to all 6 features.
    *   **Calibration:** 99th percentile thresholding. `raw_score / (threshold * 1.5)`.
    *   **Performance:** Precision 90.9%, Recall 100%.

2.  **What-If Analysis Sandbox (Phase 1 & 2)**
    *   **Backend:** `/sandbox/predict` endpoint in `backend/api/sandbox_routes.py`.
    *   **Frontend:** `SandboxModal.jsx` with presets (Normal, Stall, Spike, Bearing) and sliders.
    *   **Features:** Live state comparison, drift analysis, and feature contribution visualization.
    *   **Explainability:** Verified working (Insight Panel shows simple natural language reasons).

### 🚧 Pending / Known Gaps
1.  **InfluxDB Configuration:** We have **NOT** configured InfluxDB for local development yet. The system currently uses in-memory or mock storage for some paths. This is the **immediate next priority**.
2.  **Risk Calibration:** The ML model is very binary (LOW vs CRITICAL). We may need to smooth the scoring to utilize MODERATE/HIGH levels effectively.

---

## 2. Architecture Snapshot

*   **Backend:** FastAPI (`backend/api/`).
    *   `main.py` registers `sandbox_routes`, `integration_routes`, `system_routes`.
    *   `detector.py`: Holds the `AnomalyDetector` class (Isolation Forest).
    *   `explainer.py`: Generates human-readable insights.
*   **Frontend:** React `frontend/src/`.
    *   `SandboxModal/`: New component for What-If analysis.
    *   `App.jsx`: Main dashboard layout with Sandbox trigger.

---

## 3. Strict Rules (Re-Read These)

1.  **Governance:** Follow `CONTRACTS.md` strictly. CONTRACTS > Code.
2.  **Execution:** Do not skip phases. Plan → Approve → Execute → Verify.
3.  **Scope:** No "black box" ML. Explainable, rule-based logic is preferred where possible.
4.  **Testing:** E2E verification is required for all UI components.

---

## 4. Immediate Task

**Objective:** Configure InfluxDB for local development to ensure persistent time-series storage.

1.  Check `backend/storage/client.py` and `docker-compose.yml` (if exists).
2.  Set up local InfluxDB connection parameters (Bucket, Org, Token).
3.  Refactor `SensorEventWriter` to use the real InfluxDB client instead of mocks/logs.

---

**Please acknowledge this state and proceed with the InfluxDB configuration task.**
