#!/usr/bin/env python3
"""CLEAN5 evaluator identity, offline evaluation, aggregation and decision inputs."""
from pathlib import Path
import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["GIT_OPTIONAL_LOCKS"] = "0"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.paper_rebuild.clean5_sequence.offline_eval import main

if __name__ == "__main__":
    sys.exit(main(execution_script=Path(__file__)))
