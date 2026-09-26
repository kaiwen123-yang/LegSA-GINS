"""Supplementary tables for the publication package (AGENTS section 12b).

STAB01 maps every degradation type identifier used in the figures (D01..D60) to a
human-readable description, its family, injection window, affected sources and
claim level, so that identifiers in figures resolve to the manuscript's Table S1.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

REGISTRY_YAML = Path(__file__).resolve().parents[4] / "configs" / "paper_rebuild" / "degradation_60types_9seeds.yaml"

_WORDS = {
    "GNSS": "GNSS", "position": "position", "velocity": "velocity", "outage": "outage", "dropout": "dropout",
    "std": "std", "yaw": "yaw", "spike": "spike", "bias": "bias", "drift": "drift", "noise": "noise",
    "optimistic": "over-optimistic", "pessimistic": "over-pessimistic", "recovery": "recovery",
}


def humanize(name: str) -> str:
    """'bad_position_optimistic_std' -> 'bad position over-optimistic std'."""
    parts = [_WORDS.get(p, p) for p in name.split("_")]
    text = " ".join(parts)
    return text[0].upper() + text[1:]


def degradation_type_table(case_manifest: pd.DataFrame, registry_yaml: Path = REGISTRY_YAML) -> pd.DataFrame:
    reg = {t["id"]: t for t in yaml.safe_load(Path(registry_yaml).read_text(encoding="utf-8"))["degradation_types"]}
    rows = []
    m = case_manifest[case_manifest["degradation_type_id"] != "CLEAN"]
    for tid, grp in m.groupby("degradation_type_id", sort=True):
        r = grp.iloc[0]
        try:
            params = json.loads(r["degradation_parameters_json"])
        except (TypeError, ValueError):
            params = {}
        window = "whole sequence" if str(r["duration_s"]) == "full_sequence" else f"{float(r['anchor_time_s']):.1f} s + {float(r['duration_s']):g} s"
        rows.append({
            "type_id": tid,
            "description": humanize(r["degradation_type_name"]),
            "family": r["case_family"],
            "injection_window": window,
            "affected_sources": str(r["affected_sources"]).replace(";", ", "),
            "parameters": ", ".join(f"{k}={v}" for k, v in params.items() if k not in {"operation", "sources", "components"}),
            "seeds": int(grp["case_id"].nunique()),
            "claim_level": reg.get(tid, {}).get("claim_level", ""),
        })
    return pd.DataFrame(rows)


def write_degradation_type_table(case_manifest: pd.DataFrame, out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = degradation_type_table(case_manifest)
    df.to_csv(out_dir / "STAB01_degradation_types.csv", index=False)
    lines = ["| ID | Description | Family | Injection window | Affected sources | Parameters | Seeds | Claim level |", "|---|---|---|---|---|---|---|---|"]
    for r in df.itertuples(index=False):
        lines.append(f"| {r.type_id} | {r.description} | {r.family} | {r.injection_window} | {r.affected_sources} | {r.parameters} | {r.seeds} | {r.claim_level} |")
    (out_dir / "STAB01_degradation_types.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_dir / "STAB01_degradation_types.csv"
