"""Make backend/ importable as top-level package root (app.*) for pytest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
