#!/usr/bin/env python3
"""Run and seal five frozen CLEAN5 profiles without trace parsing or evaluation."""
from pathlib import Path
import os
import sys

sys.dont_write_bytecode = True
os.environ["GIT_OPTIONAL_LOCKS"] = "0"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.paper_rebuild.clean5_sequence.solver_runner import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(execution_script=Path(__file__)))
