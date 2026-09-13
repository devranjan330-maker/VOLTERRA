"""
VOLTERRA - Engine: Candidate Action Generation
==============================================
Implements Step 3 of the Implementation Document:
Given a risk classification and system state, generates the candidate action
space containing at least 2 distinct, labeled candidates (e.g. Do nothing,
Use battery, Shift loads, Hybrid response).
"""

from dataclasses import dataclass
from typing import List, Optional, Union
from engine.observe import SystemState
from engine.predict import RiskLevel, Forecast


@dataclass
class CandidateAction:
    id: str
    label: str
    description: str


# Predefined candidate action templates
CANDIDATE_A = CandidateAction(
    id="A",
    label="Do nothing",
    description="Maintain baseline operation without intervention.",
)
CANDIDATE_B = CandidateAction(
    id="B",
    label="Use battery",
    description="Discharge on-site battery storage to shave the anticipated peak.",
)
CANDIDATE_C = CandidateAction(
    id="C",
    label="Shift flexible loads",
    description="Defer non-critical deferrable equipment/HVAC loads.",
)
CANDIDATE_D = CandidateAction(
    id="D",
    label="Hybrid response",
    description="Combine moderate load shifting with conservative battery discharge.",
)


class CandidateGenerator:
    """Generates candidate actions based on operational risk and state."""

    def generate(
        self,
        risk_classification: Optional[Union[RiskLevel, str]] = None,
        state: Optional[SystemState] = None,
        forecast: Optional[Forecast] = None,
    ) -> List[CandidateAction]:
        """
        Returns a list of candidate actions. Guaranteed to return >= 2 distinct,
        labeled candidates under any risk condition.
        """
        if isinstance(risk_classification, str):
            try:
                risk_classification = RiskLevel(risk_classification.lower())
            except ValueError:
                risk_classification = RiskLevel.NORMAL

        if risk_classification is None and forecast is not None:
            risk_classification = forecast.risk_classification

        # Under normal conditions: do nothing, eco-preserve battery, and flexible shift
        if risk_classification == RiskLevel.NORMAL:
            return [
                CANDIDATE_A,
                CandidateAction(
                    id="B",
                    label="Eco battery charge",
                    description="Absorb surplus solar into battery storage.",
                ),
                CANDIDATE_C,
            ]

        # Under at_risk or critical conditions: full strategic action space
        return [CANDIDATE_A, CANDIDATE_B, CANDIDATE_C, CANDIDATE_D]


def generate_candidates(
    risk_classification: Optional[Union[RiskLevel, str]] = None,
    state: Optional[SystemState] = None,
    forecast: Optional[Forecast] = None,
) -> List[CandidateAction]:
    """Helper function to generate candidate action space."""
    gen = CandidateGenerator()
    return gen.generate(risk_classification=risk_classification, state=state, forecast=forecast)
