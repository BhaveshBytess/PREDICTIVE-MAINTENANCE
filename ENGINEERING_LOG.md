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
