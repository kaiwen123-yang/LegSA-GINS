#!/usr/bin/env python3
"""Render the Canonical-541 publication figures (AGENTS section 12b).

Example:
  python scripts/paper_rebuild/render_canonical541_publication_figures.py \
      --attempt-root <CANONICAL541_ATTEMPT> \
      --derived-dir <CLEAN_ROOT>/stages/CLEAN6_PUBLICATION_FIGURES/01_CANONICAL541/00_DERIVED_TABLES \
      --out-dir <CLEAN_ROOT>/stages/CLEAN6_PUBLICATION_FIGURES/01_CANONICAL541/01_FIGURES

Reads frozen and derived tables only.  Writes PNG (>= 4096 px) + PDF + SVG per figure,
FIGURE_INDEX.csv, QA_REPORT.csv, CAPTIONS.md and RENDER_MANIFEST.json.  The identity
gate of the derived tables is re-checked before anything is drawn.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.paper_rebuild.publication import canonical541_figures as figs  # noqa: E402
from legsa_gins.paper_rebuild.publication import derived_tables as dt  # noqa: E402
from legsa_gins.paper_rebuild.publication import qa, style  # noqa: E402
from legsa_gins.paper_rebuild.publication.loaders import load_bundle, load_registry  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--attempt-root", required=True, type=Path)
    ap.add_argument("--derived-dir", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--figures", nargs="*", default=None, help="subset of figure ids (default: every registry row)")
    ap.add_argument("--handoff-subset", action="store_true", help="resolve error series from the c541_handoff layout")
    args = ap.parse_args()

    registry = load_registry()
    wanted = args.figures or registry["figure_id"].tolist()
    unknown = sorted(set(wanted) - set(figs.FIGURES))
    if unknown:
        raise SystemExit(f"no renderer for {unknown}")
    bundle = load_bundle(args.attempt_root, args.derived_dir, handoff_subset=args.handoff_subset)
    gate = dt.identity_gate(bundle.unique)
    if not gate["pass"]:
        raise SystemExit("identity gate FAILED: " + json.dumps([c for c in gate["checks"] if not c["pass"]]))
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    index_rows, qa_rows, captions, hashes = [], [], [], {}
    for fid in wanted:
        fig, caption = figs.FIGURES[fid](bundle)
        qa_rows += qa.check_figure(fig, fid)
        info = style.save_figure(fig, out, fid)
        plt.close(fig)
        qa_rows += qa.check_png(Path(info["png"]), fid)
        hashes[fid] = qa.average_hash(Path(info["png"]))
        reg = registry[registry["figure_id"] == fid].iloc[0]
        info.update({"role": reg["role"], "source_tables": reg["source_tables"], "panels": reg["panels"]})
        index_rows.append(info)
        captions.append((fid, caption))
        print(f"rendered {fid}: {info['png_width_px']} px", flush=True)
    for a, b_, d in qa.duplicate_pairs(hashes):
        qa_rows.append({"figure_id": f"{a}|{b_}", "check": "no_duplicate_figures", "pass": False, "detail": f"hamming {d}"})
    if len(hashes) > 1 and not any(r["check"] == "no_duplicate_figures" for r in qa_rows):
        qa_rows.append({"figure_id": "ALL", "check": "no_duplicate_figures", "pass": True, "detail": f"{len(hashes)} figures"})
    pd.DataFrame(index_rows).to_csv(out / "FIGURE_INDEX.csv", index=False)
    qa_df = pd.DataFrame(qa_rows)
    qa_df.to_csv(out / "QA_REPORT.csv", index=False)
    (out / "CAPTIONS.md").write_text("\n\n".join(f"**{fid}.** {cap}" for fid, cap in captions) + "\n", encoding="utf-8")
    manifest = {
        "task": "AGENTS section 12b publication figures", "git_head": dt.git_head(), "attempt_root": str(args.attempt_root),
        "derived_dir": str(args.derived_dir), "figures": wanted, "identity_gate": gate["pass"],
        "qa_pass": bool(qa_df["pass"].all()), "qa_failures": qa_df[~qa_df["pass"]].to_dict("records"),
        "series_sources": sorted(set(bundle.sources)),
    }
    (out / "RENDER_MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({k: manifest[k] for k in ("identity_gate", "qa_pass", "qa_failures")}, indent=2))
    return 0 if manifest["qa_pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
