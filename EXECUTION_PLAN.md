# EXECUTION_PLAN.md

**Execution Plan & Phase Lock — Authoritative**

---

## 0. Purpose
This document defines the **only allowed execution sequence** for the Predictive Maintenance & Energy Efficiency System.

Its role is to:
* Prevent premature implementation.
* Enforce phase discipline.
* Guarantee traceability between design, data, logic, and UI.

* **No phase may be skipped.**
* **No phase may be parallelized.**

This document works in conjunction with:
* `agent.md` (How the system must be built)
* `CONTRACTS.md` (What the system is allowed to mean)

---

## 1. Global Execution Rules (Non‑Negotiable)
1. **One phase at a time** — no overlap.
2. A phase is complete **only** when its Exit Criteria are satisfied.
3. **No UI work** before backend logic is stable.
4. **No ML work** before Features and Baseline are validated.
5. **Mandatory Testing:** Every phase with logic MUST include passing Unit Tests.

---

## Phase 0 — Project Skeleton & Environment Lock
**Objective:** Establish a clean, reproducible foundation.

* **Allowed Work:**
    * Repository initialization & Directory structure.
    * Python virtual environment setup (`venv`).
    * Dependency pinning (`requirements.txt`).
    * Git initialization.
* **Deliverables:**
    * Deterministic folder structure.
    * `requirements.txt` (pinned versions).
    * Empty service modules.
* **Exit Criteria:**
    * Project installs cleanly on a fresh machine.
    * No runtime errors on imports.

---

## Phase 1 — Hybrid Data Generator (Digital Twin)
**Objective:** Simulate realistic sensor data according to the contracts.

* **Allowed Work:**
    * Python data generator (`generator.py`).
    * Indian grid baseline simulation (230V/50Hz).
    * NASA vibration signature injection logic.
    * JSON output matching `CONTRACTS.md`.
* **Deliverables:**
    * `generator.py` script.
    * Unit Tests verifying schema compliance.
* **Exit Criteria:**
    * Generated events validate against Canonical Sensor Event schema.
    * Vibration and Failure modes trigger correctly.
    * Output is deterministic with fixed seeds.

---

## Phase 2 — Time‑Series Storage Layer
**Objective:** Prepare the persistence layer *before* ingestion.

* **Allowed Work:**
    * InfluxDB installation & setup (Local/Docker).
    * Bucket & Organization creation.
    * Measurement schema definition.
    * Python Client verification.
* **Deliverables:**
    * Running InfluxDB instance.
    * Connection verification script.
* **Exit Criteria:**
    * Python can successfully write and read a dummy record.
    * Retention policies are active.

---

## Phase 3 — Ingestion & Validation API
**Objective:** Gate all data through strict contracts.

* **Allowed Work:**
    * FastAPI application structure.
    * Pydantic schema validation (Strict).
    * Derived signal computation (e.g., `power_kw`).
    * Write pipeline to InfluxDB (connecting Phase 2).
* **Deliverables:**
    * `/ingest` endpoint.
    * API Unit Tests (Valid vs Invalid payloads).
* **Exit Criteria:**
    * Invalid events are rejected with 422 errors.
    * Valid events are written to InfluxDB immediately.

---

## Phase 4 — Feature Engineering Layer
**Objective:** Produce interpretable, contract-compliant features.

* **Allowed Work:**
    * Feature computation logic (e.g., Rolling Means, Spikes).
    * **Past-only** windowing logic (No future leakage).
    * Feature persistence.
* **Deliverables:**
    * Feature calculation module.
    * Unit Tests for math correctness.
* **Exit Criteria:**
    * Features match `CONTRACTS.md`.
    * Traceability: Signal $\to$ Feature is clear.

---

## Phase 5 — Baseline Construction
**Objective:** Learn "Normal" behavior based on signals and features.

* **Allowed Work:**
    * Statistical profiling (Mean/Std Dev) of "Healthy" data.
    * Rolling-window threshold definition.
* **Deliverables:**
    * Baseline profile artifacts (JSON/Pickle).
    * Validation script.
* **Exit Criteria:**
    * Baseline is stable under normal data.
    * "Healthy" data does not trigger false anomalies.

---

## Phase 6 — Anomaly Detection (ML‑Assisted)
**Objective:** Assign anomaly scores without making decisions.

* **Allowed Work:**
    * Scikit-Learn Isolation Forest implementation.
    * Anomaly scoring pipeline.
    * Score persistence to InfluxDB.
* **Deliverables:**
    * Trained Model (or retraining logic).
    * Scoring function.
* **Exit Criteria:**
    * Scores correlate with injected NASA anomalies (from Phase 1).
    * **Rule:** ML outputs a Score only. No decision logic here.

---

## Phase 7 — Health & Risk Assessment Logic
**Objective:** Convert signals + scores into human decisions.

* **Allowed Work:**
    * Rule-based aggregation (Score + Context).
    * Health Score (0-100) computation.
    * RUL (Days) estimation logic.
* **Deliverables:**
    * Assessment Logic Module.
    * Unit Tests for edge cases (e.g., "Critical Risk").
* **Exit Criteria:**
    * Outputs match `CONTRACTS.md`.
    * Risk monotonicity holds (More Anomalies = Higher Risk).

---

## Phase 8 — Explainability Engine
**Objective:** Surface understandable reasoning.

* **Allowed Work:**
    * Explanation generation logic ("Why is risk high?").
    * Feature contribution mapping.
* **Deliverables:**
    * Explanation generator function.
* **Exit Criteria:**
    * Every alert includes a text explanation.
    * Text matches the data values.

---

## Phase 9 — Frontend Dashboard
**Objective:** Visualize without altering meaning.

* **Input Requirement (MANDATORY):**
    * **STOP** and explicitly request the `dashboard_wireframe.png` file from the user.
    * You MUST NOT start coding the UI until you have received and analyzed this image.
* **Allowed Work:**
    * React project setup (Vite).
    * Charts for Signals, Features, Anomalies.
    * Health & Risk panels matching the wireframe layout.
* **Deliverables:**
    * UI matching approved wireframe (Pixel-level adherence not required, but layout structure is mandatory).
* **Exit Criteria:**
    * UI values match backend outputs exactly (No local math).
    * "Download Report" button is visible and placed according to wireframe.

---

## Phase 10 — Reporting Layer ✅ COMPLETE
**Objective:** Produce auditable outputs.

* **Allowed Work:**
    * PDF generation (ReportLab).
    * Excel export (Pandas).
* **Deliverables:**
    * Report generation endpoint.
    * 5-Page Industrial Asset Health Certificate
* **Exit Criteria:**
    * ✅ Downloaded PDF matches Dashboard values.
    * ✅ Timestamps are correct (UTC).
    * ✅ Page 1: Executive Summary with health gauge
    * ✅ Page 2: Sensor Analysis with baseline comparison
    * ✅ Page 3: ML Explainability with contribution chart
    * ✅ Page 4: Business ROI with cost analysis
    * ✅ Page 5: Audit Trail with compliance checkboxes

---

## Phase 11 — Deployment & Verification
**Objective:** Validate real‑world readiness.

* **Allowed Work:**
    * Systemd service creation (`.service` files).
    * End‑to‑end system test.
* **Deliverables:**
    * Running system on bare‑metal Linux (or Local Simulation).
* **Exit Criteria:**
    * System survives a reboot.
    * Full pipeline (Generator $\to$ Report) works without intervention.

---

## Phase 12 — End-to-End Verification ✅ COMPLETE
**Objective:** Validate complete system functionality across all risk levels.

* **Allowed Work:**
    * Full pipeline testing (Generator → API → ML → Dashboard)
    * All risk level verification (LOW, MODERATE, HIGH, CRITICAL)
    * UI component validation
    * Anomaly visualization testing
* **Deliverables:**
    * E2E verification walkthrough with screenshots
    * All risk states documented with test data
* **Exit Criteria:**
    * ✅ LOW risk: Health 75+, NO red lines shown
    * ✅ MODERATE risk: Health 50-74, red lines + ⚠️ emoji
    * ✅ HIGH risk: Health 25-49, red lines + ⚠️ emoji
    * ✅ CRITICAL risk: Health 0-24, red lines + ⚠️ emoji
    * ✅ STATUS: LIVE badge working correctly
    * ✅ Explanations showing specific values

---

## Phase 13 — Backend Event Engine & Operator Log ✅ COMPLETE
**Objective:** Introduce a state-machine event engine and real-time operator log.

* **Deliverables:**
    * `backend/events/engine.py` — Transition-based event engine (HEALTHY ↔ ANOMALY_DETECTED ↔ RECOVERING)
    * Operator log endpoints for maintenance event capture
    * Frontend `LogWatcher` component — real-time event feed
* **Exit Criteria:**
    * ✅ Event engine fires transition events on state changes
    * ✅ Log Watcher displays events with type badges
    * ✅ Operator logs persisted to InfluxDB

---

## Phase 14 — High-Frequency Ingestion Pipeline ✅ COMPLETE
**Objective:** Upgrade from 1Hz polling to 100Hz raw ingestion with server-side aggregation.

* **Deliverables:**
    * 100Hz data generator producing 100 raw points per second
    * InfluxDB batch writer (100-point bursts)
    * Server-side `aggregateWindow(1s, mean)` for 1Hz frontend delivery
    * Glanceable Status Cards & UI refinement
* **Exit Criteria:**
    * ✅ 100Hz raw data written to InfluxDB
    * ✅ Frontend receives 1Hz aggregated data (no change to polling)
    * ✅ Status cards show health, risk, RUL at a glance
    * ✅ 60 FPS maintained on dashboard

---

## Phase 15 — ML Retraining on Batch Features (100Hz) ✅ COMPLETE
**Objective:** Retrain the Isolation Forest on statistical features extracted from 100Hz windows instead of 1Hz averages.

* **Allowed Work:**
    * Batch feature extraction (100:1 reduction: mean, std, peak-to-peak, RMS per signal = 16-D feature vector)
    * New `BatchAnomalyDetector` (Isolation Forest on 16 features)
    * Updated inference path in all monitoring loops
    * Enhanced narrated explainability (variance/peak-to-peak descriptions)
    * New `JITTER` fault type (normal averages, abnormal variance)
* **Deliverables:**
    * `backend/ml/batch_features.py` — 16-D feature extraction
    * `backend/ml/batch_detector.py` — Batch Isolation Forest
    * `scripts/retrain_batch_model.py` — Standalone retraining script
    * Updated `system_routes.py` — Calibration trains both legacy + batch models
    * Updated `events/engine.py` — Variance/peak-to-peak narration
* **Exit Criteria:**
    * ✅ Jitter fault detected (is_faulty=True with normal averages V=231.7V, A=14.5A, Vib=0.219g)
    * ✅ Log Watcher shows descriptive narration: "High vibration variance (mechanical jitter): σ=0.1728g"
    * ✅ 60 FPS maintained (all computation server-side in NumPy, ~0.05ms per batch)
    * ✅ Batch model F1-Score: 99.6% (vs legacy 78.1%)
    * ✅ AUC-ROC: 1.000

---

## Phase 16 — Temporal Anchoring & Axis Stability ✅ COMPLETE
**Objective:** Stabilize the streaming chart to eliminate visual noise and provide a consistent frame of reference.

* **Deliverables:**
    * Right-anchored 60s sliding window (XAxis domain `[now - 60s, now]`)
    * Three fixed-domain Y-axes: Voltage [0, 300] V, Current [0, 40] A (hidden), Vibration [0, 2.0] g
    * Multi-signal chart overlay (Voltage + Current + Vibration)
    * `connectNulls=false` + minimum 2-point guard to prevent plunge/floating bugs
    * `SYSTEM_INIT` warm-up narrative in LogWatcher
* **Exit Criteria:**
    * ✅ First data point appears at far-right edge of 60s window
    * ✅ No diagonal line connecting first point to bottom-left corner
    * ✅ Normal sensor noise stays visually flat within fixed Y-axis bounds

---

## Phase 17 — Noise Suppression ✅ COMPLETE
**Objective:** Eliminate false-positive "thin red strips" cluttering the chart during healthy monitoring.

* **Deliverables:**
    * Fallback range-check tolerance widened from 10% → 25% (3 sites)
    * "Majority Rules" aggregation: `is_faulty >= 0.15` (≥15/100 points must be flagged)
    * EventEngine 2-second debounce (consecutive tick counters)
* **Exit Criteria:**
    * ✅ Healthy monitoring mode produces a completely clean chart (no thin red strips)
    * ✅ Injected SEVERE fault still produces immediate red anomaly block
    * ✅ EventEngine only fires after 2 consecutive seconds of confirmed transition

---

## Phase 18 — Cloud Deployment Recovery ✅ COMPLETE
**Objective:** Resolve Render free-tier 503 cold-start failures and stabilize cloud deployment.

* **Deliverables:**
    * Lazy-loaded all heavy ML imports (`sklearn`, `numpy`, `pandas`, `joblib`) in 6 backend modules
    * Lightweight `/ping` endpoint for health checks (no ML imports)
    * Frontend 10-minute keep-alive heartbeat to `/ping`
    * Fixed Vite proxy config (was incorrectly stripping `/api` prefix)
    * Added `from __future__ import annotations` (PEP 563) to all 5 ML files to prevent `NameError` from lazy-loaded modules referenced in type hints
* **Exit Criteria:**
    * ✅ Backend starts successfully on Render free tier (no 503)
    * ✅ `/ping` returns `{"status": "ok"}` within 200ms
    * ✅ All 5 ML modules import without NameError
    * ✅ Keep-alive prevents cold starts during active browser sessions

---

## Phase 19 — Final Refinements (Directives A/B/C) ✅ COMPLETE
**Objective:** Polish the system with baseline benchmarking, system purge, and report quality improvements.

* **Deliverables:**
    * **Directive A — Baseline Benchmarking:** StatusCard components display calibrated baseline targets (e.g., "Target: 230.0 V") below live readings
    * **Directive B — Deep System Purge:** `POST /system/purge` endpoint wipes InfluxDB data + in-memory state; purple "Purge & Re-Calibrate" button in SystemControlPanel with confirmation dialog
    * **Directive C — Report Refinement:** Excel `Anomaly_Score` populated with real range-check scores; operator log notes sanitized across all 3 report formats; Basic PDF `critical_alerts` checks `is_faulty`, `is_anomaly`, and `anomaly_score > 0.7`
* **Exit Criteria:**
    * ✅ Status cards show baseline target alongside live value after calibration
    * ✅ Purge button resets system to IDLE and clears all data
    * ✅ Excel Anomaly_Score column is populated (not null/empty)
    * ✅ Reports show "Maintenance event recorded" instead of gibberish test notes

---

## Final Statement
This execution plan is **binding**.
If any step seems inconvenient, it exists to prevent failure later.
**Discipline now prevents disaster later.**