import yaml
from pathlib import Path

# config.yaml resides in the project root (two levels up from utils folder)
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"

DEFAULT_CONFIG = {
    "default_risk_thresholds": {
        "at_risk_gap_percent": 10,
        "critical_gap_percent": 20,
    },
    "objective_weights": {
        "peak_demand_kw": -1.0,
        "cost": -0.5,
        "renewable_utilization_pct": 0.8,
        "battery_reserve_pct": 0.3,
    },
    "constraints": {
        "min_battery_reserve_pct": 30,
    },
    "battery_parameters": {
        "max_charge_kw": 5.0,
        "max_discharge_kw": 5.0,
        "efficiency": 0.95,
        "capacity_kwh": 13.5,
    },
}

def load_config():
    """Load configuration from config.yaml with fallback to defaults."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    cfg = DEFAULT_CONFIG.copy()
                    cfg.update(loaded)
                    return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG

CONFIG = load_config()
