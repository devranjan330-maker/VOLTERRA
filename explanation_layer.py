"""
VOLTERRA - Explainability Layer
================================
Implements the explainability layer described in the VOLTERRA PRD (Section 5.6).

Translates optimization outcomes and digital twin simulation results into
grounded, plain-language justifications for operators.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from prediction_engine import SystemState, Forecast
from decision_engine import Decision


@dataclass
class Explanation:
    """Human-readable explanation of an optimized decision."""
    text: str
    decision: Optional[Decision] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


STRATEGY_DISPLAY_NAMES = {
    "a": "Strategy A (Do nothing)",
    "do_nothing": "Strategy A (Do nothing)",
    "b": "Strategy B (Use battery)",
    "use_battery": "Strategy B (Use battery)",
    "c": "Strategy C (Shift flexible loads)",
    "shift_load": "Strategy C (Shift flexible loads)",
    "shift_loads": "Strategy C (Shift flexible loads)",
    "shift_flexible_loads": "Strategy C (Shift flexible loads)",
    "d": "Strategy D (Hybrid response)",
    "hybrid": "Strategy D (Hybrid response)",
    "hybrid_response": "Strategy D (Hybrid response)",
}


class ExplanationLayer:
    """
    Generates plain-language, audit-ready justifications for selected actions.
    Adheres to the 100% decision explainability requirement (PRD Section 8).
    """

    def explain(
        self,
        decision: Decision,
        forecast: Optional[Forecast] = None,
        simulated_state: Optional[SystemState] = None,
        scores: Optional[Dict[str, Any]] = None,
    ) -> Explanation:
        """
        Generate a human-readable justification for the chosen strategy.

        Args:
            decision: The recommended Decision object.
            forecast: Forecast object generated prior to decision.
            simulated_state: Resulting state of the system if action is executed.
            scores: Detailed multi-objective scoring breakdown.

        Returns:
            An Explanation dataclass instance.
        """
        action_key = str(decision.action).lower().replace(" ", "_").replace("-", "_")
        display_name = STRATEGY_DISPLAY_NAMES.get(
            action_key,
            f"Strategy {decision.action.title().replace('_', ' ')}",
        )

        state = simulated_state or decision.simulated_state
        scores_dict = scores or decision.scores or {}
        cand_score = scores_dict.get(decision.action, {})

        peak = state.demand_kw if state else cand_score.get("peak_demand_kw")
        reserve = state.battery_level_pct if state else cand_score.get("battery_reserve_pct")

        # Grounded text generation per PRD Section 5.6
        if action_key in ("d", "hybrid", "hybrid_response"):
            if peak is not None and reserve is not None:
                text = (
                    f"{display_name} is preferred because it reduces the predicted peak to {peak:.1f} kW "
                    f"while maintaining the required battery reserve at {reserve:.0f}%."
                )
            else:
                text = f"{display_name} is preferred because it balances peak shaving with battery reserve retention."

        elif action_key in ("b", "use_battery", "battery"):
            if peak is not None and reserve is not None:
                text = (
                    f"{display_name} is preferred because it aggressively shaves peak grid demand to {peak:.1f} kW "
                    f"with remaining battery reserve at {reserve:.0f}%."
                )
            else:
                text = f"{display_name} is preferred because on-site battery storage eliminates the forecast grid deficit."

        elif action_key in ("c", "shift_load", "shift_loads", "shift_flexible_loads"):
            if peak is not None:
                text = (
                    f"{display_name} is preferred because it lowers peak demand to {peak:.1f} kW "
                    f"by shedding deferrable loads without consuming battery reserves."
                )
            else:
                text = f"{display_name} is preferred because shifting flexible loads relieves strain without battery draw."

        else:
            if forecast and forecast.risk_classification.value == "normal":
                text = f"{display_name} is preferred because forecasted demand remains safely within available supply."
            else:
                text = f"{display_name} is maintained as baseline operational stance."

        return Explanation(
            text=text,
            decision=decision,
            metrics={
                "action": decision.action,
                "peak_demand_kw": peak,
                "battery_reserve_pct": reserve,
            },
        )
