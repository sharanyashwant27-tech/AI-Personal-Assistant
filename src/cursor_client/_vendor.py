"""Load reverse-engineered Cursor protocol modules from vendor/eisbaw."""

from __future__ import annotations

import sys
from pathlib import Path

_VENDOR_ROOT = Path(__file__).resolve().parent.parent.parent / "vendor" / "eisbaw"
_GRPC_ROOT = _VENDOR_ROOT / "cursor-grpc"


def ensure_vendor_path() -> Path:
    """Add eisbaw vendor paths for protocol engine imports."""
    if not _VENDOR_ROOT.is_dir():
        raise RuntimeError(
            "Missing vendor/eisbaw. Clone it with:\n"
            "  git clone --depth 1 https://github.com/eisbaw/cursor_api_demo.git vendor/eisbaw"
        )

    for path in (_GRPC_ROOT, _VENDOR_ROOT):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    return _VENDOR_ROOT
