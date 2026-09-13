"""
VOLTERRA - Engine: Explainability Layer (Explainable Decision Intelligence)
===========================================================================
Implements Stage 3 (Explain) of the Decision Engine Design Document:
- Communicates why the selected strategy was chosen over the alternatives.
- Grounded in actual optimization scoring data (the specific objectives that drove the decision).
- Follows the correct pattern:
    "Strategy D is preferred because it reduces the predicted peak while maintaining the required battery reserve."
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional

ACTION_LABELS = {
    "A": "Strategy A (Do nothing)",
    "B": "Strategy B (Use battery)",
    "C": "Strategy C (Shift flexible loads)",
    "D": "Strategy D (Hybrid response)",
    "do_nothing": "Strategy A (Do nothing)",
    "use_battery": "Strategy B (Use battery)",
    "shift_load": "Strategy C (Shift flexible loads)",
    "hybrid": "Strategy D (Hybrid response)",
}


@dataclass
class ExplanationOutput:
    selected_strategy: str
    score_basis: str
    rationale: str


class ExplanationEngine:
    """Generates grounded explanations from real optimization scoring data."""

    def explain_structured(
        self,
        selected_candidate_id: str,
        scores: Dict[str, Any],
        baseline_demand_kw: Optional[float] = None,
    ) -> ExplanationOutput:
        cand_score = scores.get(selected_candidate_id, {})
        label = ACTION_LABELS.get(selected_candidate_id, f"Strategy {selected_candidate_id}")

        peak = cand_score.get("peak_demand_kw")
        batt = cand_score.get("battery_reserve_pct")
        cost = cand_score.get("cost")
        total = cand_score.get("total_score")

        # Formulate concise score basis (Section 5 example):
        # "Score basis: Reduces predicted peak demand while preserving required battery reserve"
        if peak is not None and batt is not None:
            score_basis = f"Reduces predicted peak demand to {peak} kW while preserving {batt}% battery reserve"
        else:
            score_basis = "Maximizes multi-objective score while satisfying all hard operational constraints"

        # Correct pattern (Section 6):
        # "Strategy D is preferred because it reduces the predicted peak while maintaining the required battery reserve."
        if peak is not None and batt is not None and baseline_demand_kw and baseline_demand_kw > peak:
            savings = round(baseline_demand_kw - peak, 2)
            main_sentence = (
                f"{label} is preferred because it reduces the predicted peak from {baseline_demand_kw} kW to {peak} kW "
                f"(saving {savings} kW) while maintaining the required battery reserve at {batt}%."
            )
        elif peak is not None and batt is not None:
            main_sentence = (
                f"{label} is preferred because it reduces the predicted peak to {peak} kW "
                f"while maintaining the required battery reserve at {batt}%."
            )
        else:
            main_sentence = f"{label} is preferred based on superior composite multi-objective evaluation."

        additional_details = []
        if total is not None:
            additional_details.append(f"It achieved the highest composite optimization score of {total}.")
        if cost is not None:
            additional_details.append(f"Projected energy cost is ${cost:.2f}.")

        infeasible = [cid for cid, s in scores.items() if not s.get("feasible", True)]
        if infeasible:
            disqualified = [ACTION_LABELS.get(cid, cid) for cid in infeasible]
            additional_details.append(
                f"Alternative strategies ({', '.join(disqualified)}) were disqualified due to safety constraint violations."
            )

        full_rationale = " ".join([main_sentence] + additional_details)

        return ExplanationOutput(
            selected_strategy=label,
            score_basis=score_basis,
            rationale=full_rationale,
        )

    def explain(
        self,
        selected_candidate_id: str,
        scores: Dict[str, Any],
        baseline_demand_kw: Optional[float] = None,
    ) -> str:
        """Returns the complete grounded rationale string."""
        return self.explain_structured(selected_candidate_id, scores, baseline_demand_kw).rationale


def explain_decision(
    selected_candidate_id: str,
    scores: Dict[str, Any],
    baseline_demand_kw: Optional[float] = None,
) -> str:
    engine = ExplanationEngine()
    return engine.explain(selected_candidate_id, scores, baseline_demand_kw)
