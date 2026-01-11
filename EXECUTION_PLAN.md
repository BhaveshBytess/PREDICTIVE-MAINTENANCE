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

## Phase 10 — Reporting Layer
**Objective:** Produce auditable outputs.

* **Allowed Work:**
    * PDF generation (ReportLab).
    * Excel export (Pandas).
* **Deliverables:**
    * Report generation endpoint.
* **Exit Criteria:**
    * Downloaded PDF matches Dashboard values.
    * Timestamps are correct (UTC).

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

## Final Statement
This execution plan is **binding**.
If any step seems inconvenient, it exists to prevent failure later.
**Discipline now prevents disaster later.**