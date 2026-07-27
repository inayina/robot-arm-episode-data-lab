#!/usr/bin/env python3
"""Thin CLI for SmolVLA S3 paired open-loop evaluation.

Library implementation: ``training.smolvla_s3.open_loop_eval``.
Re-exports the full library surface (including ``_`` helpers) for historical imports.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from training.smolvla_s3 import open_loop_eval as _lib  # noqa: E402

globals().update({k: getattr(_lib, k) for k in dir(_lib) if k != "__name__"})


if __name__ == "__main__":
    raise SystemExit(_lib.main())
