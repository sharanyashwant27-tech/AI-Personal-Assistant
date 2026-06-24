"""Safe path resolution inside the agent workspace root."""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", str(_DEFAULT_ROOT))).resolve()


def resolve_workspace_path(relative_path: str) -> Path:
    """Resolve a user path and ensure it stays inside the workspace."""
    cleaned = relative_path.strip().replace("\\", "/").lstrip("/")
    target = (WORKSPACE_ROOT / cleaned).resolve()

    if target != WORKSPACE_ROOT and WORKSPACE_ROOT not in target.parents:
        raise ValueError(f"Path escapes workspace: {relative_path}")

    return target
