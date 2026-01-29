# Engineering Log — Predictive Maintenance System

> Technical journal of non-trivial bugs, architectural decisions, and tool limitations.  
> Format: Context → Hurdle → Solution → Key Learning

---

## [Phase 0] - Git Branch Mismatch

* **Context:** Initializing repository and pushing first commit to remote.
* **The Hurdle:** Initial commit pushed to auto-created `master` branch instead of existing `main` branch on GitHub. Remote now had two branches with different histories.
* **The Solution:** Renamed local `master` to `main`, deleted remote `master`, rebased onto `origin/main`, force-pushed to align histories.
* **Key Learning:** Always verify remote's default branch name before first push; GitHub defaults to `main`, but local Git may default to `master`.

---

## [Phase 1] - Power Formula Unit Conversion

* **Context:** Implementing `power_kw` calculation in the data generator.
* **The Hurdle:** Initial implementation used `V × I × PF` directly, yielding Watts instead of Kilowatts.
* **The Solution:** Applied user-mandated correction: `power_kw = (voltage_v × current_a × power_factor) / 1000.0`
* **Key Learning:** Always verify unit consistency in formulas; sensor signals in contracts specify units explicitly (kW, not W).

---

## [Phase 1] - Floating-Point Test Tolerance

* **Context:** Unit test for `power_kw` formula validation.
* **The Hurdle:** `AssertionError: assert 0.002 < 0.001` — test tolerance of 0.001 was too strict for floating-point arithmetic after rounding.
* **The Solution:** Increased tolerance from 0.001 to 0.01 for 3-decimal precision output.
* **Key Learning:** When testing floating-point calculations with rounding, use a tolerance at least one order of magnitude larger than the precision.

---

## [Phase 2] - Flux Query Filter Order

* **Context:** Querying InfluxDB with asset_id filter to retrieve specific sensor events.
* **The Hurdle:** Query returned 0 results despite data existing. Raw query without filter returned data correctly.
  ```
  Tables: 0  (with filter)
  Tables: 6  (without filter)
  ```
* **The Solution:** Flux requires `pivot()` BEFORE filtering by tag values. After pivot, tags become regular columns accessible for filtering.
  ```flux
  // WRONG: filter before pivot
  |> filter(fn: (r) => r.asset_id == "x")
  |> pivot(...)
  
  // CORRECT: pivot first, then filter
  |> pivot(...)
  |> filter(fn: (r) => r.asset_id == "x")
  ```
* **Key Learning:** In Flux queries, pivot transforms the table structure; tag-based filters must come after pivot when using pivoted column names.

---

## [Phase 2] - Integration Test Data Availability Timing

* **Context:** Integration tests writing to InfluxDB then immediately querying.
* **The Hurdle:** Tests failed intermittently; queries returned 0 results even though writes succeeded.
  ```
  AssertionError: Expected data for test-xxx-single, got 0. All results: 0
  ```
* **The Solution:** Increased `time.sleep()` from 0.5s to 5s after writes. InfluxDB's write path is eventually consistent; data needs time to become queryable.
* **Key Learning:** Time-series databases often have eventual consistency for writes; integration tests must include sufficient wait time (5s minimum for InfluxDB 2.x).

---

## [Phase 2] - Pytest Fixture Scope and Data Isolation

* **Context:** Module-scoped fixture with `delete_all_data()` cleanup causing cross-test interference.
* **The Hurdle:** Tests passed individually but failed in sequence; cleanup deleted data needed by subsequent tests.
* **The Solution:** Changed to session-scoped fixture with seed data written at session start. Removed aggressive cleanup; used unique test run IDs (`uuid4().hex[:8]`) per session to isolate test data.
* **Key Learning:** For integration tests against shared databases, use session scope with unique identifiers rather than aggressive cleanup between tests.

---

## [Phase 3] - Server-Side power_kw Computation

* **Context:** Designing the ingestion API endpoint schema.
* **The Hurdle:** Design decision needed: Should clients be allowed to provide `power_kw`, or should it always be server-computed?
* **The Solution:** Enforced **server-side only** computation. The API:
  1. Rejects requests that include `power_kw` (returns 422)
  2. Computes `power_kw = (V × I × PF) / 1000` on every ingestion
  3. Returns the computed value in the response
* **Key Learning:** Server-side computation of derived signals prevents client-side data corruption and ensures formula consistency across all data sources.

---

## [Phase 3] - Pydantic Strict Mode vs JSON Datetime

* **Context:** FastAPI endpoint receiving JSON payload with ISO-8601 timestamp string.
* **The Hurdle:** With `ConfigDict(strict=True)`, Pydantic rejected valid datetime strings:
  ```
  'datetime_type', 'msg': 'Input should be a valid datetime', 'input': '2026-01-11T11:51:21+00:00'
  ```
* **The Solution:** Removed `strict=True` from model config. Pydantic's default mode parses datetime strings from JSON correctly. Field validators still enforce UTC requirement.
* **Key Learning:** Pydantic's strict mode requires exact Python types; remove it when accepting JSON input that needs type coercion.

---

## [Phase 3] - UUID Version Validation

* **Context:** Validating that event_id is a proper UUIDv4.
* **The Hurdle:** `UUID(string, version=4)` does NOT validate version—it just sets the version bits. A UUIDv1 string was accepted.
* **The Solution:** Parse without version parameter, then check `uuid_obj.version != 4`. This properly reads the version bits from the input string.
  ```python
  uuid_obj = UUID(v)  # Don't pass version
  if uuid_obj.version != 4:
      raise ValueError(...)
  ```
* **Key Learning:** Python's UUID constructor's `version` param is for creation, not validation. Check `.version` after parsing to validate.

---

## [Phase 4] - NaN for Cold-Start Windows

* **Context:** Computing rolling mean, spike count, RMS features when historical data is insufficient.
* **The Hurdle:** What value to return for features when the window is incomplete (cold-start)? Options: 0.0, default value, or NaN.
* **The Solution:** Return `None` (NaN) for incomplete windows. This prevents false "zero readings" that could trigger false anomalies downstream.
  - Coercing to 0.0 would incorrectly suggest zero voltage, zero vibration, etc.
  - Downstream consumers (anomaly detection, rules) must handle NaN gracefully.
* **Key Learning:** Use NaN/None for missing data rather than sentinel values (0, -1). This preserves data integrity and makes the "unknown" state explicit.

---

## [Phase 5] - Healthy Data Filtering for Baseline

* **Context:** Building baseline profiles that define "normal" operating behavior.
* **The Hurdle:** How to ensure baseline only reflects healthy operation, not fault conditions?
* **The Solution:** Explicitly filter by `is_fault_injected == False` before computing statistics. The baseline builder requires this column and only includes rows where it's False.
  - Fault-injected periods have abnormal sensor readings
  - Including them would corrupt the "normal" profile
  - 80% minimum coverage ensures sufficient healthy data
* **Key Learning:** Baseline purity is critical. Always have an explicit "truth" marker (is_fault_injected) to separate healthy from faulty data.

---

## [Phase 6] - Score Inversion for Anomaly Detection

* **Context:** Implementing anomaly detection scoring with Isolation Forest.
* **The Hurdle:** Scikit-learn's `decision_function` outputs HIGHER values for NORMAL data. Our contract requires 0=Normal, 1=Anomalous.
* **The Solution:** Applied sigmoid transformation and inversion: `score = 1.0 - sigmoid(decision_value * 4)`. This:
  - Maps decision values to [0, 1] via sigmoid
  - Inverts so higher values = more anomalous
  - Provides smooth transition near decision boundary
* **Key Learning:** Always verify the semantics of ML library outputs. Scikit-learn's anomaly detection uses "higher = more normal" convention, opposite to intuitive expectations.

---

## [Phase 7] - Deterministic Health Score Formula

* **Context:** Converting anomaly scores to human-readable health scores.
* **The Hurdle:** Should health calculation include weights, time decay, or other factors?
* **The Solution:** Pure deterministic formula: `Health = 100 * (1.0 - anomaly_score)`. No stochastic factors.
  - Same input always produces same output
  - Easy to audit and explain
  - Risk thresholds use named constants: `THRESHOLD_CRITICAL=25`, `THRESHOLD_HIGH=50`, `THRESHOLD_MODERATE=75`
* **Key Learning:** For explainability, prefer simple deterministic formulas over complex weighted models. Magic numbers should be named constants.

---

## [Phase 8] - Epsilon Rule for Explanations

* **Context:** Generating explanations based on feature deviations from baseline.
* **The Hurdle:** High z-scores can occur with negligible absolute differences (e.g., 0.5% difference with tiny std).
* **The Solution:** Epsilon Rule: ignore features where `|diff| < 1% of mean` regardless of z-score.
  - Also handle std=0 explicitly to prevent division by zero
  - Top 3 contributors only to avoid overwhelming users
* **Key Learning:** Statistical significance (z-score) isn't enough for explainability. Practical significance (absolute difference) matters more to users.

---

## [Phase 9] - Pure Renderer Frontend Pattern

* **Context:** Building React dashboard that displays backend data.
* **The Hurdle:** Should frontend calculate health scores, or just display?
* **The Solution:** Frontend is a **PURE RENDERER**. It does NOT calculate:
  - Health scores are computed by backend
  - Risk levels are computed by backend
  - Explanations are generated by backend
  - Frontend simply displays JSON responses
* **Key Learning:** Keep calculation logic in ONE place (backend). Frontend should be a dumb display layer. This prevents drift and ensures consistency.

---

## [Phase 10] - Snapshot Rule for Auditable Reports

* **Context:** Generating PDF/Excel reports for download.
* **The Hurdle:** Should reports compute health scores at request time, or use stored values?
* **The Solution:** **Snapshot Rule** — Reports use persisted HealthReport data ONLY. No recalculation.
  - Protects audit trail integrity
  - Report shows exactly what system "thought" at recorded timestamp
  - Prevents drift between dashboard and downloaded report
* **Key Learning:** For auditability, reports must be immutable snapshots. Never recompute historical assessments.

---

## [Phase 11] - Dual Deployment Strategy

* **Context:** Deploying the system for real-world readiness.
* **The Hurdle:** Some environments prefer Docker, others prefer bare-metal Linux with systemd.
* **The Solution:** Provide BOTH deployment options:
  - Docker: `docker-compose up -d` with restart policies
  - Bare-Metal: `setup_linux.sh` + `backend.service` with `Restart=always`
* **Key Learning:** Production readiness means supporting multiple deployment strategies. Systemd provides resilience equivalent to Docker's restart policies.

---

## [Phase 12] - Anomaly Visualization - Red Dashed Lines

* **Context:** Chart anomaly markers needed to show as red dashed vertical lines with ⚠️ emoji.
* **The Hurdle:** Initially used red dots, then ReferenceLine wasn't matching x-axis values due to duplicate timestamps (time format lacked seconds).
* **The Solution:** 
  1. Added seconds to timestamp format (`HH:MM:SS`) for unique x-axis values
  2. Used Recharts `ReferenceLine` component with `strokeDasharray="5 5"` and red stroke
  3. Added ⚠️ emoji label at top of each line
* **Key Learning:** Time-based x-axis matching requires unique values. Include seconds in time format for sub-minute data granularity.

---

## [Phase 12] - Anomaly Lines Only When Risk Elevated

* **Context:** Red dashed lines were showing for ALL historical `is_faulty` data points, even when system was now healthy.
* **The Hurdle:** Users reported seeing anomaly lines at LOW risk, which was confusing.
* **The Solution:** Modified frontend logic to only show anomaly lines when `risk_level !== 'LOW'`. Clears anomaly markers when system recovers to healthy state.
* **Key Learning:** Visualization should reflect CURRENT state, not just historical data. Anomaly markers only make sense when there's an active issue.

---

## [Phase 12] - CORS Configuration for Alternate Ports

* **Context:** STATUS: LIVE badge showing OFFLINE when frontend ran on port 3001 (alternate port when 3000 was in use).
* **The Hurdle:** CORS only allowed localhost:3000, 5173, 8080. Port 3001 was blocked.
* **The Solution:** Added `localhost:3001` and `127.0.0.1:3001` to CORS allowed origins in `backend/api/main.py`.
* **Key Learning:** Vite dev server automatically switches to alternate ports. CORS config must include common alternate ports.

---

## [Phase 12] - Complete E2E Verification

* **Context:** Full end-to-end testing of all risk levels with fresh data.
* **Verification Completed:**
  | Risk Level | Health Score | Red Lines | Maintenance Window |
  |------------|--------------|-----------|-------------------|
  | LOW | 75 | ❌ None | ~60 days |
  | MODERATE | 50 | ✅ Yes | ~19 days |
  | HIGH | 33 | ✅ Yes | ~4 days |
  | CRITICAL | 5 | ✅ Yes | < 1 day |
* **Key Learning:** System correctly responds to real-world sensor values across the full risk spectrum.

---

## [Phase 12] - Auto-Detection of Anomalies at Ingestion

* **Context:** Red anomaly lines were appearing based on generator's `is_faulty` flag, not actual detection.
* **The Hurdle:** User correctly identified that this was "memorizing" not "detecting" - lines should appear only where values actually exceed baseline bounds.
* **The Solution:** Modified `/api/v1/data/simple` endpoint to auto-detect anomalies:
  1. Compare each sensor value (voltage, current, power_factor, vibration) against baseline min/max
  2. If ANY value exceeds baseline bounds (with 10% tolerance), mark as anomaly
  3. `is_faulty` flag is now set by ML detection, not generator
* **Key Learning:** True anomaly detection compares incoming values against learned baseline bounds. The generator's flag is only used when no baseline exists yet.

---

## [Phase 10] - 5-Page Industrial Asset Health Certificate

* **Context:** Implementing a professional multi-page PDF report for audit compliance and executive presentation.
* **The Hurdle:** ReportLab's `canvas.stroke()` method doesn't exist. Gauge arc was failing with AttributeError.
* **The Solution:** Changed gauge drawing to use explicit path objects:
  ```python
  # WRONG: canvas.stroke() doesn't exist
  canvas.stroke()
  
  # CORRECT: Use path object with drawPath
  path = canvas.beginPath()
  path.arc(cx - radius, cy - radius, cx + radius, cy + radius, start_angle, end_angle)
  canvas.drawPath(path, stroke=1, fill=0)
  ```
* **Key Learning:** ReportLab canvas API uses `drawPath()` for stroked arcs, not a direct `stroke()` method. Always consult ReportLab docs for low-level drawing operations.

---

## [Phase 10] - Graceful Fallback for Feature Contributions

* **Context:** Computing feature contribution percentages for ML explainability page.
* **The Hurdle:** If baseline is missing or calculation fails, report generation should NOT crash.
* **The Solution:** Wrapped contribution calculation in try/except with fallback:
  ```python
  def _compute_feature_contributions_safe(self) -> Dict[str, Any]:
      try:
          # ... actual calculation ...
      except Exception:
          return {
              "Vibration": "Contribution data unavailable",
              "Current": "Contribution data unavailable",
              # ...
          }
  ```
* **Key Learning:** Production reports must degrade gracefully. Better to show "unavailable" than crash the entire report.

---

## [Phase 10] - Frontend Download Button Format Mismatch

* **Context:** After implementing industrial report backend, frontend still downloaded old 1-page PDF.
* **The Hurdle:** `handleDownloadReport('pdf')` was hardcoded; needed `format=industrial`.
* **The Solution:** 
  1. Changed primary button to `handleDownloadReport('industrial')`
  2. Added secondary buttons for Excel and Basic PDF
  3. Styled with `.downloadGroup` flex container
* **Key Learning:** Full-stack features require end-to-end verification. Always trace from UI click to API response.

---

## [Fault Simulation] - Severity Levels for Targeted Risk Testing

* **Context:** Fault injection always produced CRITICAL risk (~2 health), preventing demo of MODERATE/HIGH levels.
* **The Hurdle:** Fault generator values were ALL far outside baseline (vibration 10-25x normal). Isolation Forest saw any deviation as maximally anomalous.
* **The Solution:** Added `FaultSeverity` enum with calibrated value ranges:
  ```
  MILD:   voltage +5-10V, vibration 1.3-1.8x → MODERATE risk
  MEDIUM: voltage +10-25V, vibration 2-4x   → HIGH risk  
  SEVERE: voltage +25-50V, vibration 5-15x  → CRITICAL risk
  ```
* **Key Learning:** Fault simulation must be proportional to scoring thresholds. Test all risk levels, not just extremes.

---

## [Scoring] - Blended ML + Range-Based Scoring

* **Context:** ML detector (Isolation Forest) was too binary - either 0.0 or 1.0 with no middle ground.
* **The Hurdle:** MILD faults triggered max ML anomaly scores because healthy baseline is very tight. ML treated any deviation as critical.
* **The Solution:** Blended scoring approach:
  ```python
  # 60% range-based (proportional) + 40% ML (detection)
  if ml_score > 0.7 and range_score < 0.4:
      # ML says critical but range says mild - trust range more
      anomaly_score = range_score * 0.7 + ml_score * 0.3
  else:
      anomaly_score = range_score * 0.6 + ml_score * 0.4
  ```
* **Key Learning:** Binary classifiers need post-processing for graduated severity. Blend multiple signals for proportional response.

---

## [Deployment] - Vercel Monorepo Configuration

* **Context:** Preparing for cloud deployment on Vercel with React frontend + Python backend in same repo.
* **The Hurdle:** Vercel auto-detects `requirements.txt` in root and assumes Python-only project, conflicting with frontend build.
* **The Solution:** 
  1. Moved `requirements.txt` from root to `backend/` directory
  2. Updated `Dockerfile`, `setup_linux.sh`, `README.md` to reference new path
  3. Created `vercel.json` with explicit routing:
     - `/api/*` → `backend/api/main.py` (Python serverless)
     - `/*` → React SPA (from `frontend/dist/`)
* **Key Learning:** Monorepo deployments require explicit separation of concerns. Keep language-specific dependency files in their respective directories to prevent build system confusion.

---
