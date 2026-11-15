from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class ReleaseManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    release_version: str = Field(min_length=1)
    workflow_version: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    policy_version: int = Field(gt=0)
    prompt_versions: dict[str, str]
    tool_versions: dict[str, str]


def load_release_manifest(path: str | Path) -> ReleaseManifest:
    with Path(path).open(encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise ValueError("release manifest root must be a mapping")
    return ReleaseManifest.model_validate(raw)
