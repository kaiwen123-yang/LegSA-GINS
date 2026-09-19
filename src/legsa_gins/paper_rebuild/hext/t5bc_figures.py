"""Independent T5bc publication exports from hash-bound aggregate tables only.

The controller invokes ``render_t5bc`` in its plotting process. No raw input,
provider, NAV, solver, evaluator, or reference trace is opened by this module.
Pure preparation functions expose every plotted and unavailable matrix cell.
"""
from __future__ import annotations

import csv
from decimal import Decimal
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re

from .t5bc_reporting import AVAILABLE, FROZEN, PROFILES, SEQUENCES, T5A_R5, SUBSET_VARIANTS, scalar_delta

VARIANTS = SUBSET_VARIANTS

METRICS = (("yaw_rmse_deg", "Yaw RMSE (deg)", "Yaw difference (deg)"),
           ("h_rmse_m", "H RMSE (m)", "H difference (m)"),
           ("roll_rmse_deg", "Roll RMSE (deg)", "Roll difference (deg)"),
           ("pitch_rmse_deg", "Pitch RMSE (deg)", "Pitch difference (deg)"))
VARIANT_ORDER = (FROZEN, T5A_R5, "R5W", "R5SIGMA", "B3")
LABELS = {"R5": "R5", FROZEN: "Frozen", T5A_R5: "T5a R5", "R5W": "R5W", "R5SIGMA": "R5σ", "B3": "B3"}
# Existing publication colors, now assigned consistently to the five variants.
STYLE_KEYS = {"R5": "F03", FROZEN: "F01", T5A_R5: "F03", "R5W": "F02", "R5SIGMA": "A04", "B3": "F04"}
HATCHES = {"R5": "///", FROZEN: "", T5A_R5: "///", "R5W": "...", "R5SIGMA": "xx", "B3": "++"}
MARKERS = {"R5": "D", "R5W": "o", "R5SIGMA": "s", "B3": "^"}
MISSING_LABELS = {"R5": "R", "R5W": "W", "R5SIGMA": "σ", "B3": "B"}
INPUT_NAMES = ("PILOT_TABLE_V3.csv", "SUBSET61_TABLE_V3.csv", "NIS_SERIES.csv", "CALIBRATION_SUMMARY.csv")
STAGE = "CLEAN7_T5BC_V3_CANDIDATE_PILOT"


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _cell(row, metric):
    token = row.get(metric, "UNAVAILABLE")
    value = _number(token)
    status = row.get("evaluation_status", "NOT_RUN")
    reason = "AVAILABLE" if status in AVAILABLE and value is not None else str(status) if status not in AVAILABLE else "UNAVAILABLE_METRIC"
    return token, value if reason == "AVAILABLE" else None, reason


def _variants(profile):
    return (FROZEN, "B3") if profile == "A04" else (FROZEN, T5A_R5, "B3") if profile == "F02" else VARIANT_ORDER


def sequence_render_data(rows):
    """120 metric cells, including absent rows; shared four metric domains."""
    lookup = {}
    for line, row in enumerate(rows, 2):
        if row.get("evaluator_contract") != "evaluator_contract_v3":
            raise ValueError("Sequence figure input must be the primary v3 table")
        sequence, profile, variant = row.get("sequence_id"), row.get("configuration_id"), row.get("variant")
        if sequence not in SEQUENCES:
            raise ValueError("Unregistered sequence figure identity")
        if variant in ("LC01", "LC01-S") and profile == variant:
            continue  # Literature remains in the pinned full table, not these method panels.
        if profile not in PROFILES or variant not in _variants(profile):
            raise ValueError("Unauthorized sequence figure slot")
        key = sequence, profile, variant
        if key in lookup:
            raise ValueError("Duplicate sequence figure slot")
        lookup[key] = line, row
    cells, maxima = [], {metric: [] for metric, _, _ in METRICS}
    for sequence in SEQUENCES:
        for profile in PROFILES:
            for variant in _variants(profile):
                line, row = lookup.get((sequence, profile, variant), ("UNAVAILABLE", {}))
                for metric, _, _ in METRICS:
                    token, value, reason = _cell(row, metric)
                    if value is not None:
                        if value < 0:
                            raise ValueError("Negative RMSE cannot enter an absolute-magnitude bar chart")
                        maxima[metric].append(value)
                    cells.append({"sequence_id": sequence, "configuration_id": profile, "variant": variant,
                                  "metric": metric, "source_token": token, "plotted_value": value,
                                  "render_status": reason, "source_table": "<T5BC_AGGREGATE>/PILOT_TABLE_V3.csv",
                                  "source_line": line, "evaluation_status": row.get("evaluation_status", "NOT_RUN"),
                                  "failure_classification": row.get("failure_classification", "MISSING_SOURCE_SLOT")})
    limits = {metric: [0., max(values) * 1.12 if values and max(values) > 0 else 1.]
              for metric, values in maxima.items()}
    return {"cells": cells, "metric_limits": limits,
            "available_counts": {metric: len(values) for metric, values in maxima.items()},
            "domain_rule": "Zero baseline; 1.12 times the common three-sequence maximum, or [0,1] when no positive value exists"}


def subset_render_data(rows, *, case_ids):
    """Retain all authorized case IDs and missing pairs without zero imputation."""
    cases = tuple(case_ids)
    if len(set(cases)) != len(cases) or any(not isinstance(case, str) or not case for case in cases):
        raise ValueError("Subset plotting requires a unique explicit case-ID list")
    lookup = {}
    for line, row in enumerate(rows, 2):
        key = row.get("case_id"), row.get("variant")
        if (key[0] not in cases or key[1] not in (FROZEN, *VARIANTS)
                or row.get("sequence_id") != "BY2" or row.get("configuration_id") != "F04"
                or row.get("evaluator_contract") != "evaluator_contract_v3"):
            raise ValueError("Unregistered subset figure slot")
        if key in lookup:
            raise ValueError("Duplicate subset figure slot")
        lookup[key] = line, row
    cells = []
    for case in cases:
        reference_line, reference = lookup.get((case, FROZEN), ("UNAVAILABLE", {}))
        for variant in VARIANTS:
            line, row = lookup.get((case, variant), ("UNAVAILABLE", {}))
            for metric, _, _ in METRICS:
                delta_field = "delta_vs_frozen_" + metric
                token = row.get(delta_field, "UNAVAILABLE")
                left, left_value, left_reason = _cell(row, metric)
                right, right_value, right_reason = _cell(reference, metric)
                value = _number(token)
                if left_value is None or right_value is None:
                    value = None
                    reason = "CANDIDATE_" + left_reason if left_value is None else "FROZEN_" + right_reason
                elif value is None:
                    reason = "UNAVAILABLE_SERIALIZED_DELTA"
                else:
                    if Decimal(str(token)) != Decimal(scalar_delta(left, right)):
                        raise ValueError("Serialized paired delta differs from same-case source tokens")
                    reason = "AVAILABLE"
                cells.append({"case_id": case, "sequence_id": "BY2", "configuration_id": "F04",
                              "variant": variant, "metric": metric, "source_token": token,
                              "candidate_token": left, "frozen_token": right, "plotted_value": value,
                              "render_status": reason, "source_table": "<T5BC_AGGREGATE>/SUBSET61_TABLE_V3.csv",
                              "source_line": line, "frozen_source_line": reference_line,
                              "evaluation_status": row.get("evaluation_status", "NOT_RUN"),
                              "failure_classification": row.get("failure_classification", "MISSING_SOURCE_SLOT")})
    return {"case_ids": list(cases), "cells": cells, "case_count": len(cases),
            "missing_representation": "NA text outside numeric axes at the exact case/variant row; no numeric point"}


def _sequence_figure(plan, sequence):
    from ..publication import style
    from matplotlib.patches import Patch

    fig, axes = style.new_figure(2, 2, 4.45, wspace=.32, hspace=.42)
    lookup = {(r["configuration_id"], r["variant"], r["metric"]): r
              for r in plan["cells"] if r["sequence_id"] == sequence}
    for panel, (metric, label, _) in enumerate(METRICS):
        ax = axes.flat[panel]
        for group, profile in enumerate(PROFILES):
            variants = _variants(profile)
            for index, variant in enumerate(variants):
                position = group + (index - (len(variants) - 1) / 2) * .145
                cell = lookup[profile, variant, metric]
                color = style.COLORS[STYLE_KEYS[variant]]
                if cell["plotted_value"] is None:
                    ax.text(position, .025, "NA", transform=ax.get_xaxis_transform(), ha="center", va="bottom",
                            rotation=90, color=color, fontsize=style.MIN_TEXT_PT)
                else:
                    ax.bar(position, cell["plotted_value"], width=.13, color=color, hatch=HATCHES[variant],
                           edgecolor="#333333", linewidth=.4, zorder=2)
        ax.set_xticks(range(len(PROFILES)), PROFILES)
        ax.set_xlim(-.5, len(PROFILES) - .5)
        ax.set_ylim(plan["metric_limits"][metric])
        ax.set_ylabel((sequence + "\n" if panel == 0 else "") + label)
        ax.set_xlabel("Configuration")
        ax.yaxis.grid(True, zorder=0)
        style.panel_label(ax, chr(97 + panel), x=-.16)
    handles = [Patch(facecolor=style.COLORS[STYLE_KEYS[v]], hatch=HATCHES[v], edgecolor="#333333",
                     linewidth=.4, label=LABELS[v]) for v in VARIANT_ORDER]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.54, .045), ncol=5,
               columnspacing=1.1, handlelength=1.4)
    fig.text(.54, .015, "NA: unavailable", ha="center", fontsize=style.MIN_TEXT_PT)
    fig.subplots_adjust(left=.11, right=.985, top=.94, bottom=.22)
    return fig


def _subset_figure(plan):
    from ..publication import style
    from matplotlib.lines import Line2D

    count = len(plan["case_ids"])
    fig, axes = style.new_figure(1, 4, max(3.4, .21 * count + 1.45), wspace=.48)
    lookup = {(r["case_id"], r["variant"], r["metric"]): r for r in plan["cells"]}
    for panel, (metric, _, label) in enumerate(METRICS):
        ax = axes[0, panel]
        numbers = []
        for position, case in enumerate(plan["case_ids"]):
            missing = []
            for offset, variant in zip((-.30, -.10, .10, .30), VARIANTS):
                cell = lookup[case, variant, metric]
                color = style.COLORS[STYLE_KEYS[variant]]
                if cell["plotted_value"] is None:
                    missing.append(MISSING_LABELS[variant])
                else:
                    numbers.append(cell["plotted_value"])
                    ax.scatter(cell["plotted_value"], position + offset, color=color, marker=MARKERS[variant],
                               s=12, linewidths=.35, edgecolors="#333333", zorder=3)
            if missing:
                # One annotated cell per case avoids stacking three overlapping
                # NA labels. Every missing variant remains named in that cell.
                ax.text(1.025, position, "NA " + "".join(missing), transform=ax.get_yaxis_transform(),
                        va="center", ha="left", color="#333333", fontsize=style.MIN_TEXT_PT, clip_on=False)
        ax.axvline(0., color="#555555", linewidth=.6, zorder=1)
        if numbers:
            low, high = min(0., min(numbers)), max(0., max(numbers))
            margin = max((high - low) * .12, 1e-9)
            ax.set_xlim(low - margin, high + margin)
        else:
            ax.set_xlim(-1., 1.)
        ax.set_ylim(max(count - .5, .5), -.6)
        ax.set_yticks(range(count), plan["case_ids"] if panel == 0 else [""] * count)
        if panel == 0:
            ax.set_ylabel("Degradation case")
        ax.set_xlabel(label)
        ax.xaxis.grid(True, zorder=0)
        style.panel_label(ax, chr(97 + panel), x=-.06)
        if not count:
            ax.text(.5, .5, "No selected cases", transform=ax.transAxes, ha="center", rotation=90)
    handles = [Line2D([], [], color=style.COLORS[STYLE_KEYS[v]], marker=MARKERS[v], linestyle="none",
                      markersize=4, label=LABELS[v]) for v in VARIANTS]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.57, .045), ncol=4)
    fig.text(.57, .012, "Candidate minus frozen; right-margin NA: R = R5, W = R5W, σ = R5σ, B = B3",
             ha="center", fontsize=style.MIN_TEXT_PT)
    fig.subplots_adjust(left=.21, right=.94, top=.95, bottom=.17 if count < 15 else .11)
    return fig


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _path(path):
    value = Path(path).absolute()
    if ".." in value.parts or any(part.is_symlink() for part in (value, *value.parents)):
        raise ValueError("Figure input/output paths must not traverse symlinks or parent components")
    return value


def _write_json(path, document):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def _write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row)) or ["status"]
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def render_t5bc(aggregate_root, output_root, *, code_freeze, aggregate_manifest_sha256, case_ids):
    """Render independently sealed figure groups; never overwrite outputs.

    Required input manifest: ``AGGREGATE_MANIFEST.json`` with ``code_commit``,
    ``files_sha256`` for the two fixed CSV names, ``data_mode`` and both boolean
    synthetic flags. Its SHA-256 must come from the controller's prior seal.
    If present, manifest ``subset_case_ids`` must equal the explicit ordered list.
    Paths must be <T5BC_SCRATCH>/07_AGGREGATE and the sibling 08_FIGURES,
    where the scratch directory basename equals STAGE. The controller owns
    full scratch mount/protected-root validation and launches the independent,
    one-thread plotting process.
    """
    aggregate, output = _path(aggregate_root), _path(output_root)
    if (aggregate.name != "07_AGGREGATE" or aggregate.parent.name != STAGE
            or output != aggregate.parent / "08_FIGURES"):
        raise ValueError("Figure paths must use the registered T5bc 07_AGGREGATE/08_FIGURES slots")
    if output.exists():
        raise FileExistsError("Independent figure output already exists")
    if not re.fullmatch(r"[0-9a-f]{64}", aggregate_manifest_sha256):
        raise ValueError("An explicit aggregate manifest SHA-256 pin is required")
    manifest_path = _path(aggregate / "AGGREGATE_MANIFEST.json")
    manifest_bytes = manifest_path.read_bytes()
    if _sha(manifest_bytes) != aggregate_manifest_sha256:
        raise ValueError("Aggregate manifest SHA-256 mismatch")
    manifest = json.loads(manifest_bytes)
    if manifest.get("code_commit") != code_freeze:
        raise ValueError("Figure code-freeze identity mismatch")
    if (not isinstance(manifest.get("data_mode"), str)
            or any(type(manifest.get(key)) is not bool for key in ("synthetic_data_used", "semisynthetic_data_used"))):
        raise ValueError("Aggregate manifest must declare data mode and synthetic flags")
    case_ids = tuple(case_ids)
    if "subset_case_ids" in manifest and list(case_ids) != manifest["subset_case_ids"]:
        raise ValueError("Ordered subset case IDs differ from the aggregate manifest")
    inputs, payloads = {"AGGREGATE_MANIFEST.json": aggregate_manifest_sha256}, {}
    for name in INPUT_NAMES:
        pin = manifest.get("files_sha256", {}).get(name)
        if not isinstance(pin, str) or not re.fullmatch(r"[0-9a-f]{64}", pin):
            raise ValueError("Figure source is absent from the aggregate seal: " + name)
        payload = _path(aggregate / name).read_bytes()
        if _sha(payload) != pin:
            raise ValueError("Figure source SHA-256 mismatch: " + name)
        inputs[name], payloads[name] = pin, list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
    sequences = sequence_render_data(payloads[INPUT_NAMES[0]])
    subset = subset_render_data(payloads[INPUT_NAMES[1]], case_ids=case_ids)
    output.mkdir(parents=True, exist_ok=False)
    os.environ["MPLCONFIGDIR"] = str(output / ".mplconfig")
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[key] = "1"
    from ..publication import style, qa
    import matplotlib.pyplot as plt

    products, checks = [], []

    def save(fig, figure_id):
        try:
            rows = qa.check_figure(fig, figure_id)
            product = style.save_figure(fig, output / figure_id, figure_id)
            rows.extend(qa.check_png(Path(product["png"]), figure_id))
            product = {key: Path(value).relative_to(output).as_posix() if key in ("png", "pdf", "svg") else value
                       for key, value in product.items()}
            product.update(machine_qa_passed=all(row["pass"] for row in rows), manual_visual_inspection="NOT_PERFORMED")
            products.append(product)
            checks.extend(rows)
        finally:
            plt.close(fig)

    for sequence in SEQUENCES:
        save(_sequence_figure(sequences, sequence), "T5BC_SEQUENCE_" + sequence)
    save(_subset_figure(subset), "T5BC_SUBSET_PAIRED_DELTAS")
    save(_distribution_figure(payloads[INPUT_NAMES[1]]), "T5BC_SUBSET_YAW_DISTRIBUTION")
    for variant in ("R5W", "B3"):
        save(_nis_figure(payloads["NIS_SERIES.csv"], variant), "T5BC_NIS_" + variant)
    save(_calibration_figure(payloads["CALIBRATION_SUMMARY.csv"]), "T5BC_CALIBRATION")
    # Recheck every input, including the manifest, after plotting. A concurrent
    # change leaves this output unsealed rather than falsely recording success.
    for name, pin in inputs.items():
        if _sha(_path(aggregate / name).read_bytes()) != pin:
            raise ValueError("Figure source changed during rendering: " + name)
    _write_csv(output / "SEQUENCE_RENDER_DATA.csv", sequences["cells"])
    _write_csv(output / "SUBSET_RENDER_DATA.csv", subset["cells"])
    _write_csv(output / "FIGURE_QA.csv", checks)
    auxiliary = {name: _sha((output / name).read_bytes())
                 for name in ("SEQUENCE_RENDER_DATA.csv", "SUBSET_RENDER_DATA.csv", "FIGURE_QA.csv")}
    result = {"schema_version": "t5bc.render.v1", "code_commit": code_freeze,
              "status": "PASS_MACHINE_QA" if all(row["pass"] for row in checks) else "FIGURE_QA_ISSUES_RECORDED",
              **{key: manifest[key] for key in ("data_mode", "synthetic_data_used", "semisynthetic_data_used")},
              "aggregate_manifest_sha256": aggregate_manifest_sha256,
              "source_hashes": {"<T5BC_AGGREGATE>/" + name: pin for name, pin in inputs.items()},
              "figures": products, "auxiliary_sha256": auxiliary,
              "variant_order": list(VARIANT_ORDER), "variant_colors": {v: style.COLORS[STYLE_KEYS[v]] for v in VARIANT_ORDER},
              "variant_hatches": HATCHES, "sequence_metric_limits": sequences["metric_limits"],
              "sequence_domain_rule": sequences["domain_rule"], "subset_case_ids": list(case_ids),
              "sequence_metric_cells": len(sequences["cells"]), "subset_metric_cells": len(subset["cells"]),
              "unavailable_sequence_cells": sum(r["plotted_value"] is None for r in sequences["cells"]),
              "unavailable_subset_cells": sum(r["plotted_value"] is None for r in subset["cells"]),
              "missing_values_imputed": False, "subset_missing_representation": subset["missing_representation"],
              "manual_visual_inspection": "NOT_PERFORMED", "original_28_figures_modified": False,
              "native_invocation_count": 0, "evaluator_invocation_count": 0, "trace_open_count": 0,
              "captions": {"sequence_figures": "Primary v3 RMSE; F02/A04/F04 configuration labels refer to frozen counterparts. B3 uses the corresponding primed model. A04 contains only Frozen and B3. Common same-metric axes across all three sequences.",
                           "subset_figure": "Exact authorized cases, F04 class; candidate minus same-case frozen v2.1. All missing or failed pairs remain as NA at the corresponding case and variant row, without numerical imputation."}}
    _write_json(output / "T5BC_RENDER_MANIFEST.json", result)
    return result


def _distribution_figure(rows):
    import numpy as np
    from ..publication import style
    fig,axes=style.new_figure(1,2,3.05,wspace=.38)
    groups=(FROZEN,*VARIANTS);values=[]
    for variant in groups:
        values.append([float(row["yaw_rmse_deg"]) for row in rows if row.get("variant")==variant
                       and row.get("evaluation_status") in AVAILABLE and _number(row.get("yaw_rmse_deg")) is not None])
    for i,(variant,array) in enumerate(zip(groups,values)):
        color=style.COLORS[STYLE_KEYS[variant]]
        if array:
            box=axes[0,0].boxplot([array],positions=[i],widths=.6,patch_artist=True,manage_ticks=False)
            box["boxes"][0].set_facecolor(color)
            axes[0,1].step(np.sort(array),np.arange(1,len(array)+1)/len(array),where="post",label=LABELS[variant],color=color)
        else:axes[0,0].text(i,.03,"NA",transform=axes[0,0].get_xaxis_transform(),ha="center")
    axes[0,0].set_xticks(range(len(groups)),[LABELS[v] for v in groups],rotation=30)
    axes[0,0].set_ylabel("Yaw RMSE (deg)");axes[0,0].set_xlabel("Variant")
    axes[0,1].set_xlabel("Yaw RMSE (deg)");axes[0,1].set_ylabel("Empirical cumulative probability")
    axes[0,1].set_ylim(0,1);axes[0,1].legend(fontsize=style.MIN_TEXT_PT)
    for i,ax in enumerate(axes.flat):style.panel_label(ax,chr(97+i));ax.grid(True,alpha=.25)
    fig.subplots_adjust(left=.11,right=.985,bottom=.25,top=.91)
    return fig


def _nis_figure(rows,variant):
    from ..publication import style
    fig,axes=style.new_figure(3,1,4.85,hspace=.45)
    for i,seq in enumerate(SEQUENCES):
        ax=axes[i,0]; selected=[r for r in rows if r.get("sequence_id")==seq and r.get("variant")==variant
                              and r.get("configuration_id")=="F04" and _number(r.get("nis")) is not None]
        selected.sort(key=lambda r:float(r["time"]))
        if selected:ax.plot([float(r["time"]) for r in selected],[float(r["nis"]) for r in selected],lw=.45,color=style.COLORS[STYLE_KEYS[variant]])
        else:ax.text(.5,.5,"NA",transform=ax.transAxes,ha="center")
        ax.set_ylabel(seq+" NIS");ax.set_xlabel("Relative time (s)")
        if selected and max(float(r["nis"]) for r in selected)>100:ax.set_yscale("symlog",linthresh=1)
        ax.grid(True,alpha=.25);style.panel_label(ax,chr(97+i))
    fig.subplots_adjust(left=.13,right=.985,bottom=.12,top=.96)
    return fig


def _calibration_figure(rows):
    from ..publication import style
    fig,axes=style.new_figure(1,3,2.85,wspace=.48)
    # Summary persistence uses one sequence/lag row with the applied definitions.
    fields=(("sigma_deg","Heading sigma (deg)"),("k","Heading scale k"),("k_b","Baseline scale k_b"))
    for panel,(field,label) in enumerate(fields):
        ax=axes[0,panel]
        for pos,seq in enumerate(SEQUENCES):
            for offset,lag,color in ((-.18,1000,style.COLORS["F04"]),(.18,200,style.COLORS["F02"])):
                candidates=[r for r in rows if r.get("sequence_id")==seq and _number(r.get("lag_ms"))==lag and _number(r.get(field)) is not None]
                if len(candidates)>1:raise ValueError("Ambiguous calibration summary plot row")
                if candidates:ax.bar(pos+offset,float(candidates[0][field]),width=.33,color=color,label=str(lag/1000)+" s" if pos==0 else None)
                else:ax.text(pos+offset,.02,"NA",transform=ax.get_xaxis_transform(),ha="center",rotation=90)
        ax.set_xticks(range(3),SEQUENCES,rotation=25);ax.set_ylabel(label);ax.set_ylim(bottom=0);ax.set_xlabel("Sequence")
        ax.grid(True,axis="y",alpha=.25);style.panel_label(ax,chr(97+panel))
    axes[0,0].legend(fontsize=style.MIN_TEXT_PT)
    fig.subplots_adjust(left=.095,right=.99,bottom=.23,top=.91)
    return fig
