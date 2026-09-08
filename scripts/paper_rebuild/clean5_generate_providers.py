#!/usr/bin/env python3
"""Generate frozen CLEAN5 providers and render runtime configs without executing them."""
from pathlib import Path
import os
import sys

# Prevent even the initial package import from writing into the frozen snapshot.
sys.dont_write_bytecode = True
os.environ["GIT_OPTIONAL_LOCKS"] = "0"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.paper_rebuild.clean5_sequence.generate import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(execution_script=Path(__file__)))
