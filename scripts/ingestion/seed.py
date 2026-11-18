"""Compatibility entrypoint for the stdlib-only shared seed validator."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from apps.locations.seed_format import FIELDS,read_seed  # noqa: E402,F401
