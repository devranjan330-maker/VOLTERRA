"""
VOLTERRA - Engine: Execution Layer
==================================
Implements Step 7 of the Implementation Document:
Applies the selected candidate's projected state as the new "actual" system state
in virtual mode. Structures the interface so a future mode: "physical" can be
added without breaking the contract.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from engine.observe import SystemState, normalize_system_state
from engine.digital_twin import DigitalTwin, TwinConfig


@dataclass
class ExecutionResult:
    status: str
    mode: str
    resulting_state: SystemState
    details: Dict[str, Any]


class BaseExecutor(ABC):
    """Abstract base executor interface."""

    @abstractmethod
    def execute(
        self,
        action_id: str,
        baseline_state: SystemState,
        projected_state: Optional[SystemState] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        pass


class VirtualExecutor(BaseExecutor):
    """
    Virtual Actuator: Applies the winning candidate's projected state
    as the new actual operational state in the simulation environment.
    """

    def execute(
        self,
        action_id: str,
        baseline_state: SystemState,
        projected_state: Optional[SystemState] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        if projected_state is not None:
            new_state = normalize_system_state(projected_state)
        else:
            # If not provided, simulate transition
            twin = DigitalTwin(TwinConfig(initial_state=baseline_state))
            new_state, _ = twin.transition(action_id)

        return ExecutionResult(
            status="executed",
            mode="virtual",
            resulting_state=new_state,
            details={
                "action_id": action_id,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "virtual_actuation": True,
            },
        )


class PhysicalExecutor(BaseExecutor):
    """
    Extensible stub for future physical hardware/IoT integration
    (e.g., Modbus/BACnet/MQTT inverter or BMS dispatch).
    """

    def execute(
        self,
        action_id: str,
        baseline_state: SystemState,
        projected_state: Optional[SystemState] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        # Future IoT dispatch protocol
        new_state = projected_state or baseline_state
        return ExecutionResult(
            status="dispatched",
            mode="physical",
            resulting_state=new_state,
            details={
                "action_id": action_id,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "iot_protocol": "modbus_bms",
                "physical_dispatch": True,
            },
        )


def execute_action(
    action_id: str,
    baseline_state: Optional[SystemState] = None,
    projected_state: Optional[SystemState] = None,
    mode: str = "virtual",
) -> ExecutionResult:
    if baseline_state is None:
        baseline_state = SystemState(
            demand_kw=7.2,
            solar_generation_kw=5.1,
            battery_level_pct=62.0,
            temperature_c=29.5,
            occupancy="medium",
        )

    executor: BaseExecutor = PhysicalExecutor() if mode == "physical" else VirtualExecutor()
    return executor.execute(action_id, baseline_state=baseline_state, projected_state=projected_state)
