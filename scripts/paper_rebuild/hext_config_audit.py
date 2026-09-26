#!/usr/bin/env python3
"""Write trace-free H-EXT-01 audit observations to the new audit root only."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def forbid_reference_open(event, args):
    if event == "open" and isinstance(args[0], (str, bytes)):
        name = Path(args[0]).name if isinstance(args[0], str) else Path(args[0].decode()).name
        if name.startswith("trace_"):
            raise RuntimeError("H-EXT-01 forbids all reference-trace payload opens, including hashing")


if __name__ == "__main__":
    sys.addaudithook(forbid_reference_open)
    from legsa_gins.paper_rebuild.hext.config_audit import run_audit
    result = run_audit()
    print(json.dumps({k:v.get("status") for k,v in result.items() if isinstance(v,dict)}, ensure_ascii=False))
