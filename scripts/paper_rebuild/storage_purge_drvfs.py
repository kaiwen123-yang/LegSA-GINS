#!/usr/bin/env python3
"""Execute the single-use, fail-closed DrvFS storage continuation."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from legsa_gins.paper_rebuild.storage_purge_drvfs import main


if __name__ == "__main__":
    main()
