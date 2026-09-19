"""Explicit, non-overwriting C-04b continuation-2 report locations."""
from pathlib import Path
import re


def attempt_name(code_commit):
    if not re.fullmatch(r"[0-9a-f]{40}", code_commit):
        raise ValueError("Event attempt requires a full committed source identity")
    return "C04B_CONTINUATION_2_" + code_commit[:12]


def event_locations(stage, code_commit):
    stage = Path(stage)
    name = attempt_name(code_commit)
    return {"attempt": name,
        "event": stage / "01_SEQUENCE_CONTRACT" / name / "EVENT_WINDOW_V2.json",
        "diagnostics": stage / "06_ALIGNMENT_DIAGNOSTICS" / name}
