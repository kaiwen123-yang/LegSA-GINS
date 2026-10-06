"""Exact official GINav-2021 SPP/INS-LC reproduction route.

The package owns orchestration and source-explicit adapters only.  It never
vendors or rewrites the pinned MATLAB filter core.
"""

from .constants import (
    CANDIDATE_ID,
    OFFICIAL_COMMIT,
    OFFICIAL_TREE,
    SUCCESS_STATUS,
)

__all__ = [
    "CANDIDATE_ID",
    "OFFICIAL_COMMIT",
    "OFFICIAL_TREE",
    "SUCCESS_STATUS",
]
