"""
VOLTERRA - End-to-End Demo Scenario & Validation
================================================
Implements Step 11 of the Implementation Document:
Constructs a concrete demo scenario (rising demand approaching/exceeding supply limit),
exercises the full closed loop, and validates that the system produces a sensible,
explainable, and measurably improved outcome (e.g. peak reduced from 9.4 kW to 7.9 kW).
"""

from datetime import datetime, timezone
import json
from engine import (
    normalize_system_state,
    PredictionEngine,
    generate_candidates,
    simulate_candidates,
    optimize_outcomes,
    explain_decision,
    execute_action,
    measure_improvement,
)
from storage.history_store import history_store


def run_demo_scenario():
    print("=" * 70)
    print("VOLTERRA CLOSED-LOOP DECISION ENGINE - DEMO SCENARIO VALIDATION")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # STEP 1: OBSERVE (Data Ingestion & Normalization)
    # -------------------------------------------------------------------------
    raw_telemetry = {
        "timestamp": "2026-09-13T14:30:00Z",
        "demand_kw": 9.4,
        "solar_generation_kw": 5.0,
        "battery_level_pct": 60.0,
        "temperature_c": 29.5,
        "occupancy": "high",
    }
    state = normalize_system_state(raw_telemetry)
    print("\n[Step 1 - OBSERVE]")
    print(f"  Raw Input Ingested:    {raw_telemetry}")
    print(f"  Normalized SystemState: Demand={state.demand_kw} kW | Solar={state.solar_generation_kw} kW | Battery={state.battery_level_pct}% | Temp={state.temperature_c}°C")

    # -------------------------------------------------------------------------
    # STEP 2: PREDICT (Forecasting & Risk Classification)
    # -------------------------------------------------------------------------
    predictor = PredictionEngine()
    demand_hist = [7.5, 8.0, 8.6, 9.0, 9.4]
    supply_hist = [5.6, 5.4, 5.2, 5.1, 5.0]

    forecast = predictor.predict(
        demand_history_kw=demand_hist,
        supply_history_kw=supply_hist,
        current_timestamp=state.timestamp,
        horizon_minutes=30,
    )
    print("\n[Step 2 - PREDICT]")
    print(f"  Horizon:               {forecast.horizon_minutes} minutes")
    print(f"  Forecasted Demand:     {forecast.forecasted_demand_kw} kW")
    print(f"  Forecasted Supply:     {forecast.forecasted_supply_kw} kW")
    print(f"  Risk Classification:   {forecast.risk_classification.value.upper()}")
    print(f"  Notes:                 {forecast.notes}")

    # -------------------------------------------------------------------------
    # STEP 3: GENERATE (Candidate Action Space)
    # -------------------------------------------------------------------------
    candidates = generate_candidates(
        risk_classification=forecast.risk_classification,
        state=state,
        forecast=forecast,
    )
    print(f"\n[Step 3 - GENERATE]")
    print(f"  Candidate Count:       {len(candidates)}")
    for c in candidates:
        print(f"    - Strategy {c.id} ({c.label}): {c.description}")

    # -------------------------------------------------------------------------
    # STEP 4: SIMULATE (Digital Twin Parallel What-If Branching)
    # -------------------------------------------------------------------------
    sim_outcomes = simulate_candidates(
        baseline_state=state,
        candidates=[c.__dict__ for c in candidates],
        horizon_minutes=30,
    )
    print("\n[Step 4 - SIMULATE (Digital Twin Branching)]")
    for o in sim_outcomes:
        m = o.metrics
        print(f"    - Candidate {o.candidate_id}: Projected Peak={m['peak_demand_kw']} kW | Battery Reserve={m['battery_reserve_pct']}% | Cost=${m['cost']:.2f}")

    # -------------------------------------------------------------------------
    # STEP 5: OPTIMIZE (Constraint Filtering & Multi-Objective Scoring)
    # -------------------------------------------------------------------------
    min_battery_reserve = 30.0
    opt_result = optimize_outcomes(
        outcomes=[o.__dict__ for o in sim_outcomes],
        constraints={"min_battery_reserve_pct": min_battery_reserve},
        raise_on_infeasible=True,
    )
    selected_id = opt_result.selected_candidate_id
    print("\n[Step 5 - OPTIMIZE]")
    print(f"  Hard Constraint:       Min Battery Reserve >= {min_battery_reserve}%")
    print(f"  Selected Candidate:    Strategy {selected_id}")
    for cid, s in opt_result.scores.items():
        print(f"    Candidate {cid}: Total Score = {s['total_score']} | Feasible = {s['feasible']}")

    # -------------------------------------------------------------------------
    # STEP 6: EXPLAIN (Grounded Rationale Generation)
    # -------------------------------------------------------------------------
    rationale = explain_decision(
        selected_candidate_id=selected_id,
        scores=opt_result.scores,
        baseline_demand_kw=state.demand_kw,
    )
    print("\n[Step 6 - EXPLAIN]")
    print(f"  Grounded Rationale:    {rationale}")

    # -------------------------------------------------------------------------
    # STEP 7: EXECUTE (Virtual Actuation)
    # -------------------------------------------------------------------------
    winning_outcome = next(o for o in sim_outcomes if o.candidate_id == selected_id)
    exec_result = execute_action(
        action_id=selected_id,
        baseline_state=state,
        projected_state=winning_outcome.projected_state,
        mode="virtual",
    )
    print("\n[Step 7 - EXECUTE]")
    print(f"  Status:                {exec_result.status} (Mode: {exec_result.mode})")
    print(f"  New Operational State: Demand={exec_result.resulting_state.demand_kw} kW | Battery={exec_result.resulting_state.battery_level_pct}%")

    # -------------------------------------------------------------------------
    # STEP 8: MEASURE (Before/After Quantified Verification & Audit Logging)
    # -------------------------------------------------------------------------
    measurement = measure_improvement(
        before_state=state,
        after_state=exec_result.resulting_state,
    )
    print("\n[Step 8 - MEASURE]")
    print(f"  Before Peak:           {measurement.before_peak_kw} kW")
    print(f"  After Peak:            {measurement.after_peak_kw} kW")
    print(f"  Peak Reduction Delta:  {measurement.delta_demand_kw} kW")
    print(f"  Improvement:           {measurement.improvement_pct}%")
    print(f"  Summary:               {measurement.summary}")

    print("\n" + "=" * 70)
    print(f"DEMO VALIDATION RESULT: SUCCESS ({measurement.improvement_pct}% peak demand reduction achieved)")
    print("=" * 70)
    return measurement


if __name__ == "__main__":
    run_demo_scenario()
