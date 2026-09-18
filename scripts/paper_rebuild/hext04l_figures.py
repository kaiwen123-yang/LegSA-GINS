#!/usr/bin/env python3
"""H-EXT-04L: render only pinned evaluated tables; no numerical execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from legsa_gins.paper_rebuild.hext.readonly_figures import render_closeout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("main-table", "summary-path", "segment-table", "main-sha256",
                 "summary-sha256", "segment-sha256", "output-root", "publication-root", "code-commit"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--publish", action="store_true",
                        help="Preserve previous H-EXT extension, then apply authorized replacement")
    args = vars(parser.parse_args())
    actual_head = subprocess.check_output(
        ["git", "-C", str(Path(__file__).resolve().parents[2]), "rev-parse", "HEAD"],
        text=True).strip()
    if args["code_commit"] != actual_head:
        parser.error("--code-commit must equal the verified current full HEAD")
    result = render_closeout(**args)
    print(json.dumps({"status": result["status"], "original_v21_files_byte_unchanged":
                      result["original_v21_files_byte_unchanged"],
                      "figures": {key: {"qa_pass": all(row["pass"] for row in value["qa"]),
                                        "png_width_px": value["png_width_px"],
                                        "png_height_px": value["png_height_px"]}
                                  for key, value in result["figures"].items()}}, indent=2))


if __name__ == "__main__":
    main()
