"""
VOLTERRA - Engine: Ingestion & Normalization Layer
==================================================
Implements Step 1 of the Implementation Document:
Accepts arbitrary raw telemetry, sensor, and metering input, sanitizes it,
and normalizes it into a valid, strongly-typed SystemState.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union


@dataclass
class SystemState:
    """
    Standard normalized telemetry model representing the operational
    state of an energy node.
    """
    demand_kw: float
    battery_level_pct: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    solar_generation_kw: float = 0.0
    temperature_c: float = 25.0
    occupancy: Union[str, int] = "medium"

    def available_supply_kw(self) -> float:
        """Total on-site renewable generation."""
        return self.solar_generation_kw

    @property
    def supply_kw(self) -> float:
        return self.solar_generation_kw

    @property
    def battery_percent(self) -> float:
        return self.battery_level_pct

    def to_dict(self) -> Dict[str, Any]:
        ts_str = self.timestamp.isoformat() if hasattr(self.timestamp, "isoformat") else str(self.timestamp)
        return {
            "timestamp": ts_str,
            "demand_kw": self.demand_kw,
            "solar_generation_kw": self.solar_generation_kw,
            "battery_level_pct": self.battery_level_pct,
            "temperature_c": self.temperature_c,
            "occupancy": self.occupancy,
        }


def parse_timestamp(val: Any) -> datetime:
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return datetime.now(timezone.utc)
        try:
            if val.endswith("Z"):
                val = val[:-1] + "+00:00"
            return datetime.fromisoformat(val)
        except Exception:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(val, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
    return datetime.now(timezone.utc)


def normalize_system_state(raw_input: Any) -> SystemState:
    """
    Converts arbitrary raw input into a valid SystemState.
    Handles legacy field aliases, missing optional values, and type conversions.
    """
    if isinstance(raw_input, SystemState):
        return raw_input

    if hasattr(raw_input, "model_dump"):
        data = raw_input.model_dump()
    elif hasattr(raw_input, "__dict__"):
        data = dict(raw_input.__dict__)
    elif isinstance(raw_input, dict):
        data = dict(raw_input)
    else:
        raise ValueError(f"Cannot normalize input of type {type(raw_input)}")

    # Handle demand
    demand = data.get("demand_kw")
    if demand is None:
        demand = data.get("demand", data.get("load_kw", data.get("power_kw", 0.0)))
    try:
        demand_kw = max(0.0, float(demand))
    except (ValueError, TypeError):
        demand_kw = 0.0

    # Handle solar/supply
    solar = data.get("solar_generation_kw")
    if solar is None:
        solar = data.get("supply_kw", data.get("solar_kw", data.get("generation_kw", 0.0)))
    try:
        solar_generation_kw = max(0.0, float(solar))
    except (ValueError, TypeError):
        solar_generation_kw = 0.0

    # Handle battery level
    batt = data.get("battery_level_pct")
    if batt is None:
        batt = data.get("battery_percent", data.get("battery_pct", data.get("soc", 50.0)))
    try:
        battery_level_pct = min(100.0, max(0.0, float(batt)))
    except (ValueError, TypeError):
        battery_level_pct = 50.0

    # Handle temperature
    temp = data.get("temperature_c", data.get("temp_c", 25.0))
    try:
        temperature_c = float(temp)
    except (ValueError, TypeError):
        temperature_c = 25.0

    # Handle occupancy
    occupancy = data.get("occupancy", "medium")

    # Handle timestamp
    ts = parse_timestamp(data.get("timestamp"))

    return SystemState(
        demand_kw=round(demand_kw, 2),
        solar_generation_kw=round(solar_generation_kw, 2),
        battery_level_pct=round(battery_level_pct, 2),
        temperature_c=round(temperature_c, 1),
        occupancy=occupancy,
        timestamp=ts,
    )


class IngestionEngine:
    """Ingestion and telemetry sanitation engine."""
    def __init__(self):
        self.total_ingested = 0

    def ingest(self, raw_data: Any) -> SystemState:
        state = normalize_system_state(raw_data)
        self.total_ingested += 1
        return state
