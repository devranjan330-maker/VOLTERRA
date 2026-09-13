import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"

def load_config():
    """Load configuration from config.yaml.
    Returns a dict with keys: default_risk_thresholds, objective_weights,
    hard_constraints, battery_parameters.
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

CONFIG = load_config()
