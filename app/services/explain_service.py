from typing import Dict, Any


def generate_explanation(selected_candidate_id: str, scores: Dict[str, Any]) -> str:
    """
    Generate grounded natural-language rationale referencing the exact optimization scores.
    Adheres to Grounded Explanation principle (Document 2 Section 6.1 & Document 3 Section 4.6).
    """
    cand_score = scores.get(selected_candidate_id, {})
    peak = cand_score.get("peak_demand_kw")
    reserve = cand_score.get("battery_reserve_pct")
    cost = cand_score.get("cost")

    label_map = {
        "A": "Strategy A (Do nothing)",
        "B": "Strategy B (Use battery)",
        "C": "Strategy C (Shift flexible loads)",
        "D": "Strategy D (Hybrid response)",
    }
    name = label_map.get(selected_candidate_id.upper(), f"Strategy {selected_candidate_id}")

    if peak is not None and reserve is not None:
        return (
            f"{name} is preferred because it reduces the predicted peak to {peak:.1f} kW "
            f"while maintaining the required battery reserve at {reserve:.0f}%."
        )
    elif peak is not None:
        return f"{name} is preferred because it achieves the lowest predicted peak demand ({peak:.1f} kW)."
    else:
        return f"{name} is preferred based on the highest aggregate objective score."
