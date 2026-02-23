"""
conftest.py for v2 tests.

Ensures repo root is on sys.path so `from lib.X import Y` and
`from services.X import Y` work regardless of how pytest is invoked.
"""
import sys
from pathlib import Path

_repo_root = str(Path(__file__).resolve().parent.parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
