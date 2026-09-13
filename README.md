# VOLTERRA — Closed-Loop Decision Intelligence Engine

> **"Turn future uncertainty into an optimized decision."**

VOLTERRA is a closed-loop decision intelligence platform built in Python (FastAPI). It implements the complete 8-stage operational pipeline:

```
SYSTEM STATE  ──▶  PREDICTION  ──▶  POSSIBLE ACTIONS  ──▶  SIMULATION
                                                               │
                                                               ▼
LEARNING  ◀──  OUTCOME  ◀──  BEST ACTION  ◀──  OPTIMIZATION
```

---

## Architecture & Module Structure

As specified in the **VOLTERRA Implementation Document (v1.0)**, the codebase is organized into clean, decoupled layers:

```text
volterra/
├── api/
│   ├── main.py            # FastAPI application entrypoint & error handlers
│   ├── routes/
│   │   ├── state.py       # POST /v1/state (Ingestion & normalization)
│   │   ├── predict.py     # POST /v1/predict (Forecasting & risk)
│   │   ├── generate.py    # POST /v1/generate (Candidate action space)
│   │   ├── simulate.py    # POST /v1/simulate (Digital twin branching)
│   │   ├── optimize.py    # POST /v1/optimize (Scoring & hard constraints)
│   │   ├── explain.py     # POST /v1/explain (Grounded rationale)
│   │   ├── execute.py     # POST /v1/execute (Virtual/physical actuation)
│   │   ├── measure.py     # POST /v1/measure (Pre/post improvement)
│   │   ├── decide.py      # POST /v1/decide (Orchestrated single-call loop)
│   │   └── history.py     # GET /v1/history (Audit trail & learning)
│   └── schemas.py         # Canonical Pydantic data contracts
│
├── engine/
│   ├── observe.py         # Step 1: Telemetry ingestion & SystemState
│   ├── predict.py         # Step 2: Exponential smoothing & risk classification
│   ├── generate.py        # Step 3: Candidate space generation (>=2 candidates)
│   ├── digital_twin.py    # Step 4: Physical dynamics & state-transition model
│   ├── simulate.py        # Step 4: Parallel candidate branching with baseline isolation
│   ├── optimize.py        # Step 5: Multi-objective optimization & constraint filtering
│   ├── explain.py         # Step 6: Grounded rationale generator
│   ├── execute.py         # Step 7: Virtual & physical execution interface
│   └── measure.py         # Step 8: Quantified before/after measurement
│
├── storage/
│   └── history_store.py   # Decision cycle persistence (In-memory + SQLite)
│
├── tests/
│   ├── test_predict.py     # Prediction & risk classification unit tests
│   ├── test_simulate.py    # Digital twin & branching simulation unit tests
│   ├── test_optimize.py    # Objective scoring & constraint violation tests
│   ├── test_end_to_end.py  # Full closed-loop & Definition of Done tests
│   ├── test_api.py         # Comprehensive FastAPI endpoint test suite
│   ├── test_architecture_spec.py
│   └── test_closed_loop_engines.py
│
├── frontend/              # Step 12: Interactive Decision Studio Dashboard
│   ├── index.html
│   ├── style.css
│   └── app.js
│
└── demo_scenario.py       # Step 11: End-to-end demo scenario validation script
```

---

## 1. Quick Start: Demo Scenario Validation (Step 11)

Run the end-to-end demo scenario (rising demand approaching supply limit, exercising the full 8-step closed loop):

```bash
python demo_scenario.py
```

### Expected Output:
```text
======================================================================
VOLTERRA CLOSED-LOOP DECISION ENGINE - DEMO SCENARIO VALIDATION
======================================================================

[Step 1 - OBSERVE]
  Raw Input Ingested:    {'demand_kw': 9.4, 'solar_generation_kw': 5.0, ...}
  Normalized SystemState: Demand=9.4 kW | Solar=5.0 kW | Battery=60.0%

[Step 2 - PREDICT]
  Horizon:               30 minutes
  Forecasted Demand:     11.84 kW | Supply: 4.21 kW
  Risk Classification:   CRITICAL

[Step 3 - GENERATE]
  Candidate Actions:     Strategy A (Do nothing), Strategy B (Use battery),
                         Strategy C (Shift loads), Strategy D (Hybrid response)

[Step 4 - SIMULATE (Digital Twin Branching)]
  Strategy A: Peak=9.4 kW | Battery=60% | Cost=$5.17
  Strategy B: Peak=6.4 kW | Battery=39% | Cost=$3.20
  Strategy C: Peak=8.08 kW | Battery=60% | Cost=$4.12
  Strategy D: Peak=5.9 kW | Battery=49% | Cost=$2.83

[Step 5 - OPTIMIZE]
  Selected Candidate:    Strategy D (Total Score: +0.94, Feasible: True)

[Step 6 - EXPLAIN]
  Grounded Rationale:    Strategy D is preferred because it achieves the highest
                         composite score of 0.94, reducing peak from 9.4 to 5.9 kW
                         while preserving 49% battery reserve.

[Step 7 - EXECUTE]
  Status:                executed (Mode: virtual)

[Step 8 - MEASURE]
  Before Peak: 9.4 kW | After Peak: 5.9 kW
  Peak Reduction Delta: -3.5 kW (37.23% improvement)
======================================================================
DEMO VALIDATION RESULT: SUCCESS (37.23% peak demand reduction achieved)
======================================================================
```

---

## 2. Running the API & Interactive Dashboard (Step 10 & Step 12)

### Start Server
```bash
uvicorn api.main:app --reload --port 8000
```
*(or `uvicorn app.main:app --reload --port 8000`)*

### Access Endpoints
- **Interactive Dashboard UI**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard) or [http://localhost:8000/](http://localhost:8000/)
- **Swagger Interactive API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc API Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 3. Running Automated Tests

Run the full pytest suite:

```bash
pytest -v
```

All 52 tests pass:
- `tests/test_predict.py` (Forecasting, exponential smoothing, risk classification)
- `tests/test_simulate.py` (Digital twin dynamics, branching isolation, metrics)
- `tests/test_optimize.py` (Multi-objective scoring, constraint violation 409)
- `tests/test_end_to_end.py` (Closed loop cycle, Definition of Done, /v1/decide)
- `tests/test_api.py` (All REST endpoints and error codes)
- `tests/test_architecture_spec.py`
- `tests/test_closed_loop_engines.py`
- `tests/test_prediction_engine.py`

---

## 4. Definition of Done (MVP) Compliance

In a single run, the system:
1. Accepts a `SystemState` (`/v1/state`).
2. Predicts a future risk condition (`/v1/predict`).
3. Generates multiple candidate responses (`/v1/generate`).
4. Simulates each candidate via the digital twin (`/v1/simulate`).
5. Optimizes and selects the best candidate (`/v1/optimize`).
6. Explains the selection using real scoring data (`/v1/explain`).
7. Executes the decision virtually (`/v1/execute`).
8. Measures and reports a real, quantified improvement (`/v1/measure`, `/v1/history`).
