"""Non-overwriting publication export and source-row provenance."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import multiprocessing
import os
import time
import html
import json
from pathlib import Path
import re
import subprocess
import traceback

import matplotlib.pyplot as plt
from matplotlib.text import Text
import numpy as np
import pandas as pd

from . import qa, style
from .protocol_v2_data import Bundle, EvidenceUnavailable, sha256_file
from .protocol_v2_figures import FIGURES


def figure_checks(fig, figure_id):
    fig.canvas.draw()
    texts = [t for t in fig.findobj(Text) if t.get_visible() and t.get_text().strip()]
    banned = [text.get_text() for text in texts if re.search(
        r"same.source|同源|/mnt/|/home/|RUN_\d+|\.csv|\bPASS\b|\bFAIL\b", text.get_text(), re.I)]
    result = [{"figure_id": figure_id, "check": "no_forbidden_figure_text", "pass": not banned, "detail": banned},
              {"figure_id": figure_id, "check": "no_figure_wide_title", "pass": fig._suptitle is None, "detail": ""},
              {"figure_id": figure_id, "check": "minimum_type_7pt", "pass": all(t.get_fontsize() >= 7 for t in texts), "detail": ""}]
    return result


def write_json(path, payload):
    def scalar(value):
        if isinstance(value, np.generic):
            return value.item()
        raise TypeError("Unsupported manifest object: " + type(value).__name__)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False,
                                    default=scalar) + "\n", encoding="utf-8")


def source_summary(entry):
    names = set()
    for source in entry["sources"]:
        member = source["package_member"]
        if "error_series" in member and "MANIFEST" not in member:
            names.add("frozen v3 error-series samples")
        elif "/FAILURE_SERIES/" in member and "MANIFEST" not in member:
            names.add("native yaw-action timelines")
        elif "MANIFEST" not in member:
            names.add(Path(member).name.replace(".csv.gz", "" ).replace(".csv", ""))
    if entry.get("reference_trace"):
        names.add("hash-locked Truth trace")
    return "; ".join(sorted(names))


_WORKER_STATE = {}


def _worker_init(package, identity, out, trace_path, trace_sha256, head, source_files, replace, repair_manifests):
    # Spawned processes inherit thread limits before importing numerical libraries.
    _WORKER_STATE.update(bundle=Bundle(package, trace_path, trace_sha256,
        _verified_package_identity=identity), out=Path(out), trace_sha256=trace_sha256,
        head=head, source_files=source_files, replace=replace, repair_manifests=repair_manifests)


def _worker_figure(figure_id):
    return _render_figure(figure_id=figure_id, **_WORKER_STATE)


def _render_figure(bundle, out, figure_id, trace_sha256, head, source_files, replace, repair_manifests=False):
    title, drawer, kind, gps, tim = FIGURES[figure_id]
    directory = out / figure_id
    if directory.exists() and not replace:
        raise FileExistsError(directory)
    directory.mkdir(exist_ok=True)
    bundle.p.begin_figure(); bundle.notes = []; bundle.trace_used = False
    bundle.controlled_degradation_used = False; bundle.frozen_source_flags = []
    entry = {"figure_id": figure_id, "title": title, "kind": kind,
             "edition_origin": "Reissued" if kind == "Reissued" or figure_id == "SFIG01" else "New",
             "publication_role": "Supplementary" if figure_id.startswith("SFIG") else "Main",
             "gps_solutions_section": gps, "tim_section": tim,
             "evaluator": "NOT_APPLICABLE_NATIVE_DIAGNOSTIC" if figure_id in {"FIG01", "FIG03", "FIG04"} else "v3",
             "proposed_method": "F04", "ablation_order": ["F01", "F02", "F03", "A04", "F04"],
             "package_sha256": bundle.p.sha256, "code_commit": head, "renderer_files": source_files,
             "data_mode": "frozen_result_visualization", "synthetic_data_used": False,
             "semisynthetic_data_used": False,
             "metric_recomputation_performed": False,
             "metric_recomputation_scope": "No NAV/error-series trajectory evaluation metric is recomputed; display summaries of frozen case metrics and diagnostic event counts are permitted.",
             "trajectory_metrics_recomputed": False,
             "display_summary_statistics_computed": figure_id in {
                 "MFIG01", "MFIG02", "MFIG04", "MFIG06", "MFIG07", "MFIG08",
                 "MFIG09", "MFIG10", "MFIG11", "MFIG12", "MFIG13", "MFIG14", "SFIG01"},
             "solver_invocations": 0,
             "provider_invocations": 0, "evaluator_invocations": 0}
    if figure_id in {"MFIG10", "MFIG11", "MFIG12", "MFIG13"}:
        entry["addendum_disclosure"] = ("ADDENDUM_FAMILIES_A1_A2 — pre-registered 2026-09-13, "
            "added after the 541-core results were seen, to cover a scenario absent from the library")
    fig = None
    try:
        fig, caption = drawer(bundle)
        if entry.get("addendum_disclosure"):
            caption += " " + entry["addendum_disclosure"] + "."
        checks = figure_checks(fig, figure_id)
        if not all(c["pass"] for c in checks):
            raise ValueError("Figure semantic QA: " + json.dumps(checks))
        if repair_manifests:
            from PIL import Image
            paths = {ext: directory / (figure_id+"."+ext) for ext in ("png", "pdf", "svg")}
            if not all(p.is_file() for p in paths.values()) or (directory / "FIGURE_MANIFEST.json").exists():
                raise ValueError("Manifest-only repair requires three existing exports and a missing manifest")
            with Image.open(paths["png"]) as im:
                width, height = im.size
            saved = {**{ext: str(path) for ext, path in paths.items()},
                     **{ext+"_sha256": sha256_file(path) for ext, path in paths.items()},
                     "png_width_px": width, "png_height_px": height}
            entry["manifest_repair"] = "Initial NumPy-bool metadata serialization failure; source selection and semantic QA reconstructed; all existing exports preserved byte-for-byte."
        else:
            saved = style.save_figure(fig, directory, figure_id)
        png_checks = qa.check_png(Path(saved["png"]), figure_id)
        if not all(c["pass"] for c in png_checks):
            raise ValueError("Raster QA: " + json.dumps(png_checks))
        entry.update(status="RENDERED", caption=caption, qa=checks+png_checks,
                     outputs={ext: {"path": str(Path(figure_id)/(figure_id+"."+ext)),
                                    "sha256": saved[ext+"_sha256"]} for ext in ("png", "pdf", "svg")},
                     png_width_px=saved["png_width_px"], png_height_px=saved["png_height_px"])
    except EvidenceUnavailable as exc:
        entry.update(status="UNAVAILABLE_REQUIRED_SOURCE", reason=str(exc))
    except Exception as exc:
        entry.update(status="FAILED_RENDER_OR_QA", reason=str(exc), traceback=traceback.format_exc())
    finally:
        if fig is not None:
            plt.close(fig)
        else:
            plt.close("all")
    entry["sources"] = bundle.p.sources()
    entry["notes"] = bundle.notes
    entry["controlled_degradation_used"] = bundle.controlled_degradation_used
    entry["semisynthetic_data_used"] = bundle.controlled_degradation_used
    entry["frozen_source_flags"] = bundle.frozen_source_flags
    entry["effective_source_semantics"] = ("Controlled input masking or corruption applied to real observations; frozen result display."
        if bundle.controlled_degradation_used else "Frozen real-sequence results or physical/structural metadata; no observation injection.")
    entry["source_flag_policy"] = "Frozen source flags are preserved separately; new outer flags disclose controlled observation degradation as semisynthetic."
    if bundle.trace_used:
        entry["reference_trace"] = {"alias": "<RAW_ROOT>/BY2/hash_locked_receiver_trace", "sha256": trace_sha256,
                                    "role": "evaluation_only_plotting", "solver_access": False,
                                    "time_origin_unix_s": 1772784000.0,
                                    "csv_rows_including_header": bundle.reference_rows}
    write_json(directory / "FIGURE_MANIFEST.json", entry)
    return {"figure_id": figure_id, "status": entry["status"], "reason": entry.get("reason")}


def render(package, out_dir, *, trace_path=None, trace_sha256=None, figures=None, replace=False, workers=16, repair_manifests=False):
    if not 1 <= workers <= 24:
        raise ValueError("Plotting process count must be 1..24")
    out = Path(out_dir).absolute()
    if "v1_prereg" in out.parts:
        raise ValueError("The v1 figure archive is immutable")
    wanted = list(figures) if figures else list(FIGURES)
    if set(wanted) - set(FIGURES):
        raise ValueError("Unregistered figure requested")
    if out.is_symlink() or any(p.is_symlink() for p in out.parents):
        raise ValueError("Figure output cannot follow a symlink")
    if out.exists() and any(out.iterdir()) and not replace:
        raise FileExistsError("Output already contains artifacts; use --replace only for identified figure repairs")
    if replace and not figures:
        raise ValueError("Repair mode requires an explicit figure list")
    if repair_manifests and not replace:
        raise ValueError("Manifest-only repair requires explicit --replace and --figures")
    bundle = Bundle(package, trace_path, trace_sha256)
    out.mkdir(parents=True, exist_ok=True)
    code_root = Path(__file__).resolve().parents[4]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=code_root, check=True, capture_output=True, text=True).stdout.strip()
    source_files = {"publication/"+p.name: sha256_file(p) for p in Path(__file__).parent.glob("protocol_v2_*.py")}
    for figure_id in wanted:
        directory = out / figure_id
        if directory.exists() and not replace:
            raise FileExistsError(directory)
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                     "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
        os.environ[variable] = "1"
    started = time.monotonic()
    statuses = []
    identity = bundle.p.verified_identity
    worker_count = min(workers, len(wanted))
    print(json.dumps({"event": "PLOTTING_STARTED", "requested": len(wanted),
                      "processes": worker_count, "numerical_threads_per_process": 1,
                      "whole_archive_validation_count": 1}), flush=True)
    with ProcessPoolExecutor(max_workers=worker_count, mp_context=multiprocessing.get_context("spawn"),
            initializer=_worker_init,
            initargs=(str(package), identity, str(out), trace_path, trace_sha256, head, source_files, replace, repair_manifests)) as executor:
        pending = {executor.submit(_worker_figure, fid): fid for fid in wanted}
        next_heartbeat = started + 10
        while pending:
            completed, _ = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
            for future in completed:
                fid = pending.pop(future)
                result = future.result()
                statuses.append(result)
                print(json.dumps(result), flush=True)
            now = time.monotonic()
            if now >= next_heartbeat:
                print(json.dumps({"event": "PLOTTING_HEARTBEAT", "elapsed_s": round(now-started, 1),
                    "completed": len(statuses), "pending": len(pending),
                    "rendered": sum(s["status"] == "RENDERED" for s in statuses)}), flush=True)
                next_heartbeat = now + 10
    # Targeted repair retains all other exact manifests and exports.
    all_entries = []
    for figure_id in FIGURES:
        path = out / figure_id / "FIGURE_MANIFEST.json"
        if path.exists():
            entry = json.loads(path.read_text())
            if entry["package_sha256"] != bundle.p.sha256:
                raise ValueError("Cannot mix source package identities in a figure directory")
            all_entries.append(entry)
    rows = []
    markdown = ["# Protocol v2 figure index", "", "Proposed method: F04. Primary evaluation point: v3.", "",
                "| Number | Title | Origin / role | Data source | GPS Solutions section | TIM section | Status |",
                "|---|---|---|---|---|---|---|"]
    captions = []
    cards = []
    for entry in all_entries:
        sources = "; ".join(source["package_member"] for source in entry["sources"])
        fid = entry["figure_id"]
        rows.append({"figure_id": fid, "title": entry["title"], "kind": entry["kind"],
                     "edition_origin": entry["edition_origin"], "publication_role": entry["publication_role"],
                     "data_source": sources, "gps_solutions_section": entry["gps_solutions_section"],
                     "tim_section": entry["tim_section"], "status": entry["status"]})
        summary = source_summary(entry)
        markdown.append(f"| {fid} | {entry['title']} | {entry['edition_origin']} / {entry['publication_role']} | {summary}; [rows/hashes]({fid}/FIGURE_MANIFEST.json) | {entry['gps_solutions_section']} | {entry['tim_section']} | {entry['status']} |")
        if entry["status"] == "RENDERED":
            captions.append(f"**{fid}. {entry['title']}.** {entry['caption']}")
            cards.append(f'<article><h2>{html.escape(fid+" — "+entry["title"])}</h2><a href="{fid}/{fid}.png"><img src="{fid}/{fid}.png" alt="{html.escape(entry["title"])}"></a><p>{html.escape(entry["caption"])}</p><a href="{fid}/FIGURE_MANIFEST.json">Sources and hashes</a></article>')
    (out / "FIGURE_INDEX.md").write_text("\n".join(markdown)+"\n", encoding="utf-8")
    pd.DataFrame(rows).to_csv(out / "FIGURE_INDEX.csv", index=False)
    (out / "CAPTIONS.md").write_text("\n\n".join(captions)+"\n", encoding="utf-8")
    (out / "GALLERY.html").write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Protocol v2 figures</title><style>body{font:16px sans-serif;margin:2rem auto;max-width:1100px;color:#222}article{margin-bottom:3rem}img{max-width:100%;height:auto}p{line-height:1.5}</style><h1>Protocol v2 figures</h1>'+"".join(cards)+"</html>", encoding="utf-8")
    failures = [{k: e.get(k, "") for k in ("figure_id", "status", "reason")} for e in all_entries if e["status"] != "RENDERED"]
    pd.DataFrame(failures, columns=["figure_id", "status", "reason"]).to_csv(out / "UNAVAILABLE_REQUIRED_FIGURES.csv", index=False)
    image_hashes = {e["figure_id"]: qa.average_hash(out/e["outputs"]["png"]["path"])
                    for e in all_entries if e["status"] == "RENDERED"}
    duplicate_candidates = [{"left": left, "right": right, "hamming_distance": distance}
                            for left, right, distance in qa.duplicate_pairs(image_hashes)]
    result = {"status": "COMPLETE" if len(all_entries) == len(FIGURES) and not failures else "INCOMPLETE",
              "data_mode": "mixed_frozen_core_and_preregistered_addendum_visualization",
              "synthetic_data_used": any(e["synthetic_data_used"] for e in all_entries),
              "semisynthetic_data_used": any(e["semisynthetic_data_used"] for e in all_entries),
              "trajectory_metrics_recomputed": False,
              "display_summary_statistics_computed": any(e["display_summary_statistics_computed"] for e in all_entries),
              "requested_figure_count": len(FIGURES), "rendered_count": sum(e["status"] == "RENDERED" for e in all_entries),
              "reissued_count": sum(e["status"] == "RENDERED" and e["edition_origin"] == "Reissued" for e in all_entries),
              "new_count": sum(e["status"] == "RENDERED" and e["edition_origin"] == "New" for e in all_entries),
              "reissued_main_count": sum(e["status"] == "RENDERED" and e["kind"] == "Reissued" for e in all_entries),
              "new_matrix_count": sum(e["status"] == "RENDERED" and e["kind"] == "New" for e in all_entries),
              "new_horizontal_count": sum(e["status"] == "RENDERED" and e["kind"] == "New horizontal" for e in all_entries),
              "supplementary_count": sum(e["status"] == "RENDERED" and e["kind"] == "Supplementary" for e in all_entries),
              "count_semantics": "Edition origins partition all composites: reissued + new = rendered. Supplementary is an overlapping publication role: SFIG01 reissued, SFIG02 new.",
              "failures": failures, "package_sha256": bundle.p.sha256, "code_commit": head,
              "perceptual_duplicate_candidates": duplicate_candidates,
              "worker_processes": worker_count, "numerical_threads_per_process": 1,
              "whole_archive_validation_count": 1, "heartbeat_seconds": 10,
              "controlled_degradation_used": any(e["controlled_degradation_used"] for e in all_entries),
              "visual_review_status": "PENDING_HUMAN_OR_AGENT_RASTER_REVIEW"}
    write_json(out / "RENDER_MANIFEST.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--trace-path", type=Path)
    parser.add_argument("--trace-sha256")
    parser.add_argument("--figures", nargs="+")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--repair-manifests", action="store_true")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args(argv)
    result = render(args.package, args.out_dir, trace_path=args.trace_path, trace_sha256=args.trace_sha256,
                    figures=args.figures, replace=args.replace, workers=args.workers, repair_manifests=args.repair_manifests)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["status"] == "COMPLETE" else 2
