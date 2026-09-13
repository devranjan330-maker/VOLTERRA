from typing import List, Dict, Any
from app.models import SystemState, CandidateAction, SimulatedOutcome, OutcomeMetrics
from app.utils.config import CONFIG


def simulate_candidate(state: SystemState, candidate: CandidateAction) -> SimulatedOutcome:
    """
    Simulate the effect of a candidate action against the Digital Twin.
    Produces projected SystemState and key performance metrics.
    """
    cid = candidate.id.upper()
    batt_cfg = CONFIG.get("battery_parameters", {})
    max_discharge = batt_cfg.get("max_discharge_kw", 5.0)

    base_demand = state.demand_kw
    solar = state.solar_generation_kw
    battery = state.battery_level_pct

    # Default baseline
    peak_demand = base_demand
    cost = round(base_demand * 0.50, 2)
    battery_reserve = battery
    discharge_kw = 0.0
    shifted_kw = 0.0

    if cid in ("B", "USE_BATTERY"):
        # Discharge battery to mitigate shortfall
        shortfall = max(0.0, base_demand - solar)
        available_battery_kw = (battery / 100.0) * max_discharge
        discharge_kw = min(shortfall, max_discharge, available_battery_kw)
        peak_demand = max(solar, base_demand - discharge_kw)
        # Battery percentage reduced proportional to discharge
        battery_reserve = max(0.0, battery - (discharge_kw / max_discharge) * 45.0)
        cost = round(peak_demand * 0.50, 2)

    elif cid in ("C", "SHIFT_LOADS", "SHIFT_FLEXIBLE_LOADS"):
        # Shift flexible load (approx 12-15% of peak demand)
        shifted_kw = base_demand * 0.12
        peak_demand = max(solar, base_demand - shifted_kw)
        battery_reserve = battery  # Battery untouched
        cost = round(peak_demand * 0.51, 2)

    elif cid in ("D", "HYBRID", "HYBRID_RESPONSE"):
        # Hybrid: moderate battery discharge + moderate load shifting
        shifted_kw = base_demand * 0.08
        remaining_shortfall = max(0.0, (base_demand - shifted_kw) - solar)
        discharge_kw = min(remaining_shortfall, max_discharge * 0.6)
        peak_demand = max(solar, base_demand - shifted_kw - discharge_kw)
        battery_reserve = max(0.0, battery - (discharge_kw / max_discharge) * 25.0)
        cost = round(peak_demand * 0.48, 2)

    else:
        # Action A / "Do nothing"
        peak_demand = base_demand
        battery_reserve = battery
        cost = round(base_demand * 0.55, 2)

    # Renewable utilization calculation
    effective_demand = max(0.1, peak_demand)
    renewable_util = min(100.0, max(0.0, (solar / effective_demand) * 100.0))

    metrics = OutcomeMetrics(
        peak_demand_kw=round(peak_demand, 2),
        cost=round(cost, 2),
        battery_reserve_pct=round(battery_reserve, 2),
        renewable_utilization_pct=round(renewable_util, 2),
    )

    projected_state = {
        "timestamp": state.timestamp,
        "demand_kw": round(peak_demand, 2),
        "solar_generation_kw": round(solar, 2),
        "battery_level_pct": round(battery_reserve, 2),
        "temperature_c": state.temperature_c,
        "occupancy": state.occupancy,
    }

    return SimulatedOutcome(
        candidate_id=candidate.id,
        projected_state=projected_state,
        metrics=metrics,
    )


def simulate_candidates(state: SystemState, candidates: List[CandidateAction]) -> List[SimulatedOutcome]:
    return [simulate_candidate(state, cand) for cand in candidates]
