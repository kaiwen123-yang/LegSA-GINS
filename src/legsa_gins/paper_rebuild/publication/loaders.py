"""Read-only loaders for the publication figures.

Everything comes from the frozen Canonical-541 attempt and the derived tables of
AGENTS section 12b; nothing here recomputes a metric.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import derived_tables as dt

CONFIG_ROOT = Path(__file__).resolve().parents[4] / "configs" / "paper_rebuild" / "publication"
DISPLAY_NAMES_PATH = CONFIG_ROOT / "canonical541_display_names.yaml"
REGISTRY_PATH = CONFIG_ROOT / "CANONICAL541_PUBLICATION_FIGURE_REGISTRY.csv"

NUMERIC_AGG_COLUMNS = ["count", "mean", "std", "median", "iqr", "p10", "p25", "p75", "p90", "p95", "p99", "min", "max"]
PARITY_CONTRACT_PATH = Path(__file__).resolve().parents[4] / "configs" / "paper_rebuild" / "final_v23_parity_contract.yaml"


def evaluation_time_origin(path: Path = PARITY_CONTRACT_PATH) -> float:
    """Absolute UNIX origin of the solver's relative time axis (frozen contract value)."""
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))

    def find(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "base_time_unix_seconds":
                    return float(v)
                hit = find(v)
                if hit is not None:
                    return hit
        elif isinstance(node, list):
            for v in node:
                hit = find(v)
                if hit is not None:
                    return hit
        return None

    value = find(doc)
    if value is None:
        raise KeyError("base_time_unix_seconds not found in final_v23_parity_contract.yaml")
    return value


def load_reference_trace(trace_path: Path, time_origin: float) -> pd.DataFrame:
    """Hash-locked Fixposition trace as the evaluator sees it: relative time = time - origin,
    yaw converted with the frozen formula wrap360(90 deg - yaw_ENU) into the solver's NED convention.
    Evaluation-only use (plotting); no time-offset, sign or frame search."""
    tr = pd.read_csv(trace_path, usecols=["time", "lat", "lon", "height", "yaw", "pitch", "roll"])
    tr = tr.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    tr["t"] = tr["time"].astype(float) - float(time_origin)
    tr["yaw_ned_deg"] = np.mod(90.0 - tr["yaw"].astype(float), 360.0)
    return tr


def load_display_names(path: Path = DISPLAY_NAMES_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def load_registry(path: Path = REGISTRY_PATH) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str)


def _numeric(df: pd.DataFrame, cols) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _read_any(candidates) -> pd.DataFrame:
    for p in candidates:
        p = Path(p)
        if p.is_file():
            return pd.read_csv(p, dtype=str, low_memory=False)
        if p.with_suffix(p.suffix + ".gz").is_file():
            return pd.read_csv(p.with_suffix(p.suffix + ".gz"), dtype=str, low_memory=False)
    raise FileNotFoundError(f"none of {list(map(str, candidates))} exists")


@dataclass
class Bundle:
    attempt_root: Path
    derived_dir: Path
    names: dict
    unique: pd.DataFrame
    method_summary: pd.DataFrame
    pairwise_frozen: pd.DataFrame
    module_action: pd.DataFrame
    type_summary: pd.DataFrame
    derived_summary: pd.DataFrame
    derived_family: pd.DataFrame
    derived_type: pd.DataFrame
    tail: pd.DataFrame
    case_manifest: pd.DataFrame
    series_resolver: object
    sources: list[str] = field(default_factory=list)
    trace_path: Path | None = None
    time_origin: float = 0.0
    _trace: pd.DataFrame | None = None

    def reference_trace(self) -> pd.DataFrame | None:
        """Reference trace restricted to nothing (full file); None when no trace path was given."""
        if self.trace_path is None:
            return None
        if self._trace is None:
            self._trace = load_reference_trace(self.trace_path, self.time_origin)
            self.sources.append(str(self.trace_path))
        return self._trace

    # ---- helpers used by several figures --------------------------------------
    def config_of(self, method_id: str) -> str:
        return self.names["methods"][method_id]["configuration"]

    def label_of(self, method_id: str) -> str:
        return self.names["methods"][method_id]["label"]

    def metric_values(self, metric: str, config: str) -> pd.Series:
        sub = self.unique[self.unique["effective_configuration_id"] == config]
        return pd.to_numeric(sub.set_index("case_id")[metric], errors="coerce").dropna()

    def method_stat(self, config: str, metric: str, stat: str) -> float:
        ms = self.method_summary
        row = ms[(ms["effective_configuration_id"] == config) & (ms["metric_name"] == metric)]
        return float(row[stat].iloc[0]) if len(row) else float("nan")

    def series_for(self, case_id: str, config: str) -> pd.DataFrame | None:
        rows = self.unique[(self.unique["case_id"] == case_id) & (self.unique["effective_configuration_id"] == config)]
        if rows.empty:
            return None
        series_path, _ = self.series_resolver(rows.iloc[0])
        if series_path is None:
            return None
        self.sources.append(str(series_path))
        return pd.read_csv(series_path, usecols=lambda c: c in {"time", "err_n_m", "err_e_m", "err_u_m", "horizontal_err_m", "yaw_err_deg"})

    def window_for(self, case_id: str) -> dict:
        row = self.case_manifest[self.case_manifest["case_id"] == case_id]
        if row.empty:
            return {}
        r = row.iloc[0]
        try:
            t0 = float(r["anchor_time_s"])
            dur = float(r["duration_s"])
        except (TypeError, ValueError):
            return {}
        out = {"t0": t0, "t1": t0 + dur}
        import json

        try:
            params = json.loads(r["degradation_parameters_json"])
            if "recovery_duration_s" in params:
                out["t_rec"] = out["t1"] + float(params["recovery_duration_s"])
        except (TypeError, ValueError):
            pass
        return out


def load_bundle(attempt_root: Path, derived_dir: Path, handoff_subset: bool = False, trace_path: Path | None = None) -> Bundle:
    attempt_root, derived_dir = Path(attempt_root), Path(derived_dir)
    names = load_display_names()
    agg = attempt_root / "13_AGGREGATE"
    unique = dt.load_unique(attempt_root)
    method_summary = _numeric(_read_any([agg / "UNIQUE_METHOD_SUMMARY.csv"]), NUMERIC_AGG_COLUMNS)
    pairwise_frozen = _numeric(_read_any([agg / "PAIRWISE_SUMMARY.csv"]),
                               ["paired_sample_count", "mean_delta_candidate_minus_reference", "median_delta_candidate_minus_reference",
                                "std_delta", "p10_delta", "p90_delta", "mean_relative_change_percent", "median_relative_change_percent",
                                "win_count", "tie_count", "loss_count", "win_rate", "seed_direction_consistency"])
    module_action = _numeric(_read_any([agg / "MODULE_ACTION_SUMMARY.csv"]), NUMERIC_AGG_COLUMNS)
    type_summary = _numeric(_read_any([agg / "DEGRADATION_TYPE_SUMMARY.csv"]), NUMERIC_AGG_COLUMNS)
    num = lambda df: _numeric(df, [c for c in df.columns if c not in {"comparison", "metric_name", "case_family", "degradation_id", "delta_definition", "method_id", "display_name", "effective_configuration_id", "types_json"}])  # noqa: E731
    derived_summary = num(_read_any([derived_dir / "PAIRWISE_DERIVED_SUMMARY.csv"]))
    derived_family = num(_read_any([derived_dir / "PAIRWISE_DERIVED_FAMILY.csv"]))
    derived_type = num(_read_any([derived_dir / "PAIRWISE_DERIVED_TYPE.csv"]))
    tail = num(_read_any([derived_dir / "TAIL_CASES.csv"]))
    case_manifest = _read_any([
        attempt_root / "02_MATRIX_SPEC_LOCK" / "CANONICAL541_CASE_MANIFEST.csv",
        attempt_root / "found" / "02_MATRIX_SPEC_LOCK__CANONICAL541_CASE_MANIFEST.csv",
    ])
    resolver = dt.handoff_subset_resolver(attempt_root) if handoff_subset else dt.attempt_series_resolver(attempt_root)
    return Bundle(attempt_root, derived_dir, names, unique, method_summary, pairwise_frozen, module_action, type_summary,
                  derived_summary, derived_family, derived_type, tail, case_manifest, resolver,
                  trace_path=Path(trace_path) if trace_path else None, time_origin=evaluation_time_origin())
