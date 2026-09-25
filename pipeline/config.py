"""Explicit configuration and project-contained paths. No network side effects."""
from pathlib import Path
import hashlib
import json
import yaml
from dotenv import load_dotenv

class ConfigError(ValueError):
    pass

class Config(dict):
    def __init__(self, values, root):
        super().__init__(values)
        self.root = Path(root).resolve()

    def path(self, value):
        p = (self.root / value).resolve()
        if not p.is_relative_to(self.root):
            raise ConfigError(f"Path escapes repository: {value}")
        return p

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(self, sort_keys=True).encode()).hexdigest()

def load_config(path="config.yaml"):
    p = Path(path).resolve()
    with p.open(encoding="utf-8") as f:
        values = yaml.safe_load(f)
    if not isinstance(values, dict):
        raise ConfigError("Configuration must be a YAML mapping")
    cfg = Config(values, p.parent)
    load_dotenv(cfg.root / ".env", override=False)
    from .validate import validate_config
    validate_config(cfg)
    return cfg
