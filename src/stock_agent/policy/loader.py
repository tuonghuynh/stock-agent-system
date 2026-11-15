from pathlib import Path
from typing import Any

import yaml

from stock_agent.policy.models import PolicyDocument


def load_policy(path: str | Path) -> PolicyDocument:
    policy_path = Path(path)
    with policy_path.open(encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise ValueError("policy root must be a mapping")
    return PolicyDocument.model_validate(raw)
