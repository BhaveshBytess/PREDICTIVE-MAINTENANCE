\# CONTRACTS.md



\*\*System Contracts \& Invariants — Authoritative\*\*



---



\## 1. Purpose of This Document

This document defines the \*\*immutable contracts\*\* of the Predictive Maintenance \& Energy Efficiency System.



Any component, agent, or developer interacting with this system \*\*MUST\*\* obey these contracts.

Changes to this file constitute a \*\*breaking redesign\*\* and must not be made casually.



This file defines \*\*meaning\*\*, not implementation.



---



\## 2. Terminology (Canonical Definitions)

These terms have precise and exclusive meanings within this system.



\### Asset

An industrial machine (e.g., motor) whose operational behavior is being monitored.

An asset is uniquely identified within a deployment.



\### Signal

A time‑series measurement derived from the asset’s electrical or mechanical behavior.

\* \*\*Examples:\*\* Voltage, Current, Vibration.

\* Signals are \*\*raw observations\*\*, not interpretations.



\### Sensor Event

A normalized record representing the state of an asset at a specific point in time.

A sensor event is canonical and independent of the hardware protocol.



\### Feature

A derived, time‑windowed metric calculated from one or more signals.

\* \*\*Rules:\*\* Features must be deterministic, physically interpretable, and computed using past-only windows (no future leakage).



\### Anomaly

A statistically significant deviation of signals or features from the learned baseline.

\* \*\*Rule:\*\* An anomaly is \*\*NOT\*\* a failure. It is a mathematical deviation.



\### Health Indicator

A bounded condition score (0–100) representing the current health state of the asset.

\* 100 = Perfect Condition.

\* 0 = Functional Failure.



\### Remaining Useful Life (RUL)

A time-based estimate (in days) indicating the recommended maintenance horizon.



\### Risk Assessment

A rule‑based aggregation of Anomaly Scores + User Context that determines maintenance urgency.



---



\## 3. Input Contract — Canonical Sensor Event Schema

All incoming data MUST be normalized into the following canonical schema before further processing.



\### 3.1 Canonical Sensor Event (V1)

```json

{

&nbsp; "event\_id": "uuid-v4",

&nbsp; "timestamp": "ISO-8601 (UTC)",



&nbsp; "asset": {

&nbsp;   "asset\_id": "string",

&nbsp;   "asset\_type": "induction\_motor"

&nbsp; },



&nbsp; "signals": {

&nbsp;   "voltage\_v": 0.0,      // Indian Context: ~230V base

&nbsp;   "current\_a": 0.0,

&nbsp;   "power\_factor": 0.0,   // Range: 0.0 to 1.0

&nbsp;   "power\_kw": 0.0,       // Derived at ingestion: voltage\_v \* current\_a \* power\_factor

&nbsp;   "vibration\_g": 0.0     // NASA Context: Acceleration in g

&nbsp; },



&nbsp; "context": {

&nbsp;   "operating\_state": "RUNNING | IDLE | OFF",

&nbsp;   "source": "simulator"

&nbsp; }

}



```



\### 3.2 Identity \& Time Rules (Non‑Negotiable)



\* `event\_id` uniquely identifies a single sensor packet.

\* `timestamp` MUST be \*\*UTC\*\* and \*\*ISO‑8601\*\*.

\* Timezone conversion (e.g., to IST) is a \*\*frontend concern only\*\*.



\### 3.3 Signal Constraints



\* \*\*Voltage:\*\* Must reflect Indian Grid standards (fluctuations around 230V, 50Hz).

\* \*\*Power Factor:\*\* Must be strictly bounded (0.0 to 1.0).

\* \*\*Vibration:\*\* Must be present to support the NASA failure signatures.

\* \*\*Derived Signals:\*\* Derived values (e.g., `power\_kw`) are computed deterministically at ingestion and treated as first-class values thereafter.

\* \*\*Missing Data:\*\* Events with missing critical signals (V/I) MUST be rejected at ingestion.



---



\## 4. Feature Contract — Derived Feature Schema



All engineered features MUST conform to the following schema.



```json

{

&nbsp; "feature\_id": "string",

&nbsp; "asset\_id": "string",

&nbsp; "timestamp": "ISO-8601 (UTC)",



&nbsp; "features": {

&nbsp;   "voltage\_rolling\_mean\_1h": 0.0,

&nbsp;   "current\_spike\_count": 0,

&nbsp;   "power\_factor\_efficiency\_score": 0.0,

&nbsp;   "vibration\_intensity\_rms": 0.0

&nbsp; }

}



```



---



\## 5. Output Contract — Health \& Risk Report Schema



All system outputs MUST conform to the following schema.



\### 5.1 Health \& Risk Report (V1)



```json

{

&nbsp; "report\_id": "uuid-v4",

&nbsp; "timestamp": "ISO-8601 (UTC)",

&nbsp; "asset\_id": "string",



&nbsp; "health\_score": 0,                    // 0 (Dead) to 100 (New)

&nbsp; "risk\_level": "LOW | MODERATE | HIGH | CRITICAL",

&nbsp; "maintenance\_window\_days": 0.0,       // Estimated RUL in Days



&nbsp; "explanations": \[

&nbsp;   {

&nbsp;     "reason": "string (e.g. 'PF Drop detected')",

&nbsp;     "related\_features": \["string"],

&nbsp;     "confidence\_score": 0.0

&nbsp;   }

&nbsp; ],



&nbsp; "metadata": {

&nbsp;   "model\_version": "string"

&nbsp; }

}



```



\### 5.2 Output Guarantees



\* Every critical risk level MUST include at least one explanation.

\* Explanations MUST reference concrete features (e.g., "Vibration > 2.5g").

\* Health Score and Risk Level must be monotonic (Risk High = Health Low).



---



\## 6. Core Invariants (Must Always Hold)



\### 6.1 Determinism



Given identical input events and baselines, the output MUST be identical.



\### 6.2 Explainability



Every anomaly or risk assessment must be explainable in plain language.

If it cannot be explained, it must not be emitted.



\### 6.3 Anomaly ≠ Failure



An anomaly represents deviation, not guaranteed failure.

All maintenance recommendations must be framed probabilistically.



\### 6.4 Baseline Respect



No signal or feature is anomalous in isolation.

Anomalies are defined only as deviations from the learned baseline.



---



\## 7. Versioning Discipline



This document defines \*\*Contract V2\*\*.

Any modification requires:



1\. Explicit version bump.

2\. Documented rationale.

3\. Corresponding test updates.



---



\## 8. Batch Feature Contract — 100Hz Statistical Features (V2)



All batch feature extraction from 100Hz raw windows MUST conform to this schema.



\### 8.1 Batch Feature Vector (16 Dimensions)



For each 1-second window of 100 raw sensor points, the following 16 features are extracted:



```json

{

&nbsp; "voltage\_v\_mean": 0.0,

&nbsp; "voltage\_v\_std": 0.0,

&nbsp; "voltage\_v\_peak\_to\_peak": 0.0,

&nbsp; "voltage\_v\_rms": 0.0,

&nbsp; "current\_a\_mean": 0.0,

&nbsp; "current\_a\_std": 0.0,

&nbsp; "current\_a\_peak\_to\_peak": 0.0,

&nbsp; "current\_a\_rms": 0.0,

&nbsp; "power\_factor\_mean": 0.0,

&nbsp; "power\_factor\_std": 0.0,

&nbsp; "power\_factor\_peak\_to\_peak": 0.0,

&nbsp; "power\_factor\_rms": 0.0,

&nbsp; "vibration\_g\_mean": 0.0,

&nbsp; "vibration\_g\_std": 0.0,

&nbsp; "vibration\_g\_peak\_to\_peak": 0.0,

&nbsp; "vibration\_g\_rms": 0.0

}

```



\### 8.2 Batch Feature Rules



\* \*\*Window Size:\*\* Default 100 points (1 second at 100Hz). Minimum 10 points.

\* \*\*Reduction Ratio:\*\* 100:1 (100 raw points → 1 feature vector of 16 values).

\* \*\*Statistical Definitions:\*\*

&nbsp; \- `mean`: Arithmetic mean of the signal within the window.

&nbsp; \- `std`: Population standard deviation of the signal within the window.

&nbsp; \- `peak\_to\_peak`: `max(signal) - min(signal)` within the window.

&nbsp; \- `rms`: Root Mean Square: `sqrt(mean(signal^2))`.

\* \*\*NaN/None Handling:\*\* If any signal column is entirely missing or all NaN, the extraction MUST return None (not zeros).

\* \*\*Determinism:\*\* Given identical raw points, the feature vector MUST be identical.



\### 8.3 Fault Type Enumeration (V2)



```

SPIKE   \- Voltage/current surges above baseline (shifts mean AND variance)

DRIFT   \- Gradual degradation (mean shift, low variance change)

JITTER  \- Normal means, abnormal within-window variance (invisible to 1Hz models)

DEFAULT \- General fault pattern

```



---



\## 9. Degradation Index Contract — Cumulative Prognostics (V2)



All cumulative damage tracking MUST conform to this contract.



\### 9.1 Degradation Index (DI)



A monotonically increasing scalar in \[0.0, 1.0\] representing accumulated asset damage.



\* `0.0` = Factory-new condition (no accumulated damage).

\* `1.0` = Functional failure threshold.



```

DI\_increment = (effective\_severity ^ 2) \* SENSITIVITY\_CONSTANT \* dt

DI\_new = min(DI\_old + DI\_increment, 1.0)

```



\### 9.2 Dead-Zone (HEALTHY\_FLOOR)



```

HEALTHY\_FLOOR = 0.65

```



\* Batch scores \< HEALTHY\_FLOOR produce zero damage (effective\_severity = 0).

\* Batch scores \>= HEALTHY\_FLOOR are remapped: `effective\_severity = (score - 0.65) / 0.35`.

\* \*\*Rationale:\*\* IsolationForest assigns scores 0.1–0.5 to healthy data due to contamination parameter. Without a dead-zone, healthy noise accumulates phantom damage.



\### 9.3 Sensitivity Constant



```

SENSITIVITY\_CONSTANT = 0.005

```



\* Controls the rate of DI accumulation under fault conditions.

\* Tuned so a critical fault (\~0.95 batch score) drives health from 100% \→ 0% in approximately 4-5 minutes.

\* \*\*Units:\*\* DI per second per unit severity-squared.



\### 9.4 Monotonicity Invariant



DI MUST be monotonically non-decreasing during normal operation.



\* DI may only decrease to 0.0 via an explicit system purge (`POST /system/purge`).

\* A quiet minute of healthy data MUST NOT reduce DI.

\* Health is derived: `health\_score = round(100 \* (1.0 - DI))`.



\### 9.5 Remaining Useful Life (RUL)



```

RUL\_hours = (1.0 - DI) / max(damage\_rate, 1e-9)

```



\* `damage\_rate`: Instantaneous DI increment per second at current severity.

\* Returns 99999.0 when damage\_rate \< 1e-9 (effectively infinite RUL).

\* RUL is a \*\*projection\*\*, not a guarantee. It assumes current conditions persist.



\### 9.6 DI Hydration (Persistence)



\* On process restart, DI is recovered from InfluxDB using `|> last()` on the `degradation\_index` field.

\* This ensures DI state survives backend restarts.

\* Purge writes a DI=0.0 data point (not a delete) so `|> last()` returns the reset value.



---



\## 10. Final Statement



This document is \*\*authoritative\*\*.

If implementation, agent behavior, or documentation conflicts with this file, \*\*this file wins\*\*.





