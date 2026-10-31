"""Job roles and the equipment each one must wear, read from an editable config file (config/ppe_rules.json).

Nothing about which equipment a role needs is hard-coded here: the site's safety officer owns that file.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .types import ITEMS

DEFAULT_PATH = Path("config/ppe_rules.json")


@dataclass(frozen=True)
class Role:
    key: str
    label: str
    required: tuple[str, ...]
    standards: tuple[str, ...] = field(default_factory=tuple)


def load_roles(path: str | Path = DEFAULT_PATH) -> dict[str, Role]:
    """Read and check the roles file. Raises ValueError with a plain message if it is wrong."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ValueError(f"Rules file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Rules file is not valid JSON ({exc}).") from exc

    roles: dict[str, Role] = {}
    for key, spec in data.get("roles", {}).items():
        required = tuple(spec.get("required", []))
        unknown = [item for item in required if item not in ITEMS]
        if unknown:
            raise ValueError(f"Role '{key}' lists unknown equipment {unknown}. Allowed: {', '.join(ITEMS)}.")
        if not required:
            raise ValueError(f"Role '{key}' must require at least one item.")
        roles[key] = Role(key, spec.get("label", key), required, tuple(spec.get("standards", [])))
    if not roles:
        raise ValueError("The rules file defines no roles.")
    return roles


def usable_items(role: Role, available: list[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split a role's required items into (checkable now, not checkable with the loaded models)."""
    ok = tuple(item for item in role.required if item in available)
    return ok, tuple(item for item in role.required if item not in available)
