#!/usr/bin/env python3
"""Entry point for read-only CLEAN4 horizontal full plotting."""

from __future__ import annotations

import os

for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"
os.environ.setdefault("MPLBACKEND", "Agg")

from legsa_gins.paper_rebuild.horizontal_literature.plotting.runner import main


if __name__ == "__main__":
    raise SystemExit(main())
