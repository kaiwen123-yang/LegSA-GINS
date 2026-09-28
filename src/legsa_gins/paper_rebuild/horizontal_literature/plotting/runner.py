"""Multiprocess read-only atlas runner with ten-second progress heartbeats."""

from __future__ import annotations

import argparse
import csv
import importlib
import importlib.util
import json
import math
import os
import shutil
import sys
import time
import traceback
from concurrent.futures import (
    FIRST_COMPLETED,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeoutError,
    wait,
)
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .common import expected_artifacts, validate_artifact
from .gallery import write_contact_sheets, write_gallery
from .loaders import PlotSourceError, load_frozen_table
from .registry import PlotFamily, load_registry, resolve_source, validate_worker_count
from .style import LAYOUT_PIXELS, pixels_for_layout

OUTPUT_GROUPS = (
    "00_PLOT_CONTRACT",
    "00_OVERVIEW",
    "01_RAW_LAYER_OVERVIEW",
    "02_EXT01_CLAMBDA",
    "03_EXT02_CWLS",
    "04_EXT03_YANG2024",
    "05_EXT04_DIAGNOSTIC",
    "06_SOLUTION_LC_OVERVIEW",
    "07_LC01_PAVLASEK",
    "08_LC02_GINAV",
    "09_HARTLEY_OBSERVABILITY",
    "10_INTERNAL_C00",
    "11_CANONICAL541",
    "12_CROSS_LAYER_SYNTHESIS",
    "13_DIAGNOSTIC_ONLY",
    "98_LOGS",
    "99_GALLERY",
)

FORBIDDEN_FIGURE_TEXT = (
    "same-source reference",
    "同源参考",
    "fixposition-derived reference",
    "非独立真值",
    "not independent ground truth",
)

RENDER_MODULES = {
    "cross": "cross_layer_plots",
    "raw": "raw_plots",
    "lc": "lc_plots",
    "hartley": "hartley_plots",
    "internal": "internal_plots",
    "canonical": "canonical_plots",
}


def _dependency_preflight() -> None:
    missing = [
        module
        for module in ("matplotlib", "numpy", "PIL")
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        raise RuntimeError(f"missing plotting dependency: {', '.join(missing)}")


def _set_worker_environment() -> None:
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[name] = "1"
    os.environ.setdefault("MPLBACKEND", "Agg")


def _worker(task: dict[str, Any]) -> dict[str, Any]:
    _set_worker_environment()
    started = time.monotonic()
    family = PlotFamily(**task["family"])
    output_dir = Path(task["output_root"]) / family.output_group
    source = resolve_source(
        family,
        comparison_root=Path(task["comparison_root"]),
        canonical_attempt=Path(task["canonical_attempt"]),
    )
    result: dict[str, Any] = {
        "plot_id": family.plot_id,
        "title": family.title,
        "output_group": family.output_group,
        "scope_label": family.scope_label,
        "source_file": str(source),
        "output_dir": str(output_dir),
        "status": "FAILED_UNCLASSIFIED",
        "reason": "",
        "duration_s": 0.0,
        "worker_pid": os.getpid(),
        "artifacts": [],
    }
    try:
        formats = tuple(task["formats"])
        expected = expected_artifacts(output_dir, family, formats)
        validation = [validate_artifact(path) for path in expected]
        force_rewrite = bool(task.get("force_rewrite", False))
        if expected and not force_rewrite and all(valid for valid, _ in validation):
            result["status"] = "COMPLETE_RESUMED_VALID"
            result["artifacts"] = [str(path) for path in expected]
            return result
        table = load_frozen_table(source, family.required_fields)
        import matplotlib

        matplotlib.use("Agg", force=True)
        from .style import apply_style

        apply_style(matplotlib)
        module_name = RENDER_MODULES[family.renderer]
        module = importlib.import_module(
            f"legsa_gins.paper_rebuild.horizontal_literature.plotting.{module_name}"
        )
        composite_pixels = pixels_for_layout(
            family.layout,
            default_width=task["default_width"],
            default_height=task["default_height"],
            dense_width=task["dense_width"],
            dense_height=task["dense_height"],
        )
        module.render(
            family,
            table,
            output_dir,
            formats=formats,
            dpi=task["dpi"],
            composite_pixels=composite_pixels,
            panel_pixels=LAYOUT_PIXELS["panel"],
            force_rewrite=force_rewrite,
        )
        qa_failures: list[str] = []
        for path in expected:
            valid, reason = validate_artifact(path)
            if not valid:
                qa_failures.append(f"{path.name}:{reason}")
        if qa_failures:
            result["status"] = "FAILED_OUTPUT_QA"
            result["reason"] = "; ".join(qa_failures)
        else:
            result["status"] = "COMPLETE"
            result["artifacts"] = [str(path) for path in expected]
    except PlotSourceError as exc:
        result["status"] = exc.status
        result["reason"] = str(exc)
    except Exception as exc:  # one family never terminates the atlas.
        result["status"] = "FAILED_RENDER_EXCEPTION"
        result["reason"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
    finally:
        result["duration_s"] = time.monotonic() - started
    return result


def validate_sources(
    families: list[PlotFamily], *, comparison_root: Path, canonical_attempt: Path
) -> list[dict[str, str]]:
    """Read-only schema preflight; it creates no runtime output."""

    records: list[dict[str, str]] = []
    for family in families:
        source = resolve_source(
            family,
            comparison_root=comparison_root,
            canonical_attempt=canonical_attempt,
        )
        status = "SOURCE_READY"
        reason = ""
        try:
            load_frozen_table(source, family.required_fields)
        except PlotSourceError as exc:
            status = exc.status
            reason = str(exc)
        records.append(
            {
                "plot_id": family.plot_id,
                "status": status,
                "source_file": str(source),
                "reason": reason,
            }
        )
    return records


def _duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def _output_counts(output_root: Path) -> dict[str, int]:
    return {fmt.upper(): sum(1 for _ in output_root.rglob(f"*.{fmt}")) for fmt in ("png", "pdf", "svg")}


def _heartbeat(
    *,
    started: float,
    total: int,
    records: list[dict[str, Any]],
    active: dict[Any, tuple[str, float]],
    queued: int,
    last_done: list[str],
    output_root: Path,
    worker_limit: int,
    phase: str = "render",
) -> None:
    elapsed = time.monotonic() - started
    completed = len(records)
    failures = sum(str(row["status"]).startswith("FAILED") or str(row["status"]).startswith("BLOCKED") for row in records)
    reused = sum(str(row["status"]) == "COMPLETE_RESUMED_VALID" for row in records)
    running = ", ".join(f"{plot_id}({int(time.monotonic()-when)}s)" for plot_id, when in (value for value in active.values())) or "none"
    successful_durations = [float(row["duration_s"]) for row in records if str(row["status"]).startswith("COMPLETE")]
    eta = "unknown"
    if successful_durations and completed:
        rate = completed / max(elapsed, 1e-9)
        eta = _duration((total - completed) / max(rate, 1e-9))
    counts = _output_counts(output_root)
    print(f"[{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')}] elapsed={_duration(elapsed)}", flush=True)
    print(
        f"phase={phase} done={completed}/{total} active={len(active)}/{worker_limit} "
        f"queued={queued} failed={failures} reused={reused}",
        flush=True,
    )
    print(f"running: {running}", flush=True)
    print(f"last_done: {', '.join(last_done[-5:]) if last_done else 'none'}", flush=True)
    print(f"outputs: PNG={counts['PNG']} PDF={counts['PDF']} SVG={counts['SVG']}", flush=True)
    print(f"ETA≈{eta}", flush=True)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _write_status_csv(output_root: Path, records: list[dict[str, Any]]) -> None:
    fields = ["plot_id", "output_group", "scope_label", "status", "reason", "source_file", "output_dir", "duration_s", "worker_pid"]
    lines: list[str] = []
    from io import StringIO

    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(sorted(records, key=lambda row: row["plot_id"]))
    _atomic_text(output_root / "00_PLOT_CONTRACT" / "PLOT_FAMILY_STATUS.csv", stream.getvalue())


def _write_plot_catalog(output_root: Path, records: list[dict[str, Any]]) -> tuple[Path, int]:
    """Write one deterministic row per family with explicit component assets."""

    from io import StringIO

    fields = [
        "plot_id", "output_group", "scope_label", "title", "status", "source_file",
        "composite_png", "composite_pdf", "composite_svg",
        "panel_png_assets", "panel_pdf_assets", "panel_svg_assets",
    ]
    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for record in sorted(records, key=lambda row: row["plot_id"]):
        artifacts = [Path(path) for path in record.get("artifacts", [])]
        relative = {
            path: str(path.relative_to(output_root))
            for path in artifacts
            if path.is_relative_to(output_root)
        }
        def one(component: str, suffix: str) -> str:
            return next((rel for path, rel in relative.items() if path.name.endswith(f"_{component}.{suffix}")), "")
        def panels(suffix: str) -> str:
            return ";".join(
                rel for path, rel in sorted(relative.items(), key=lambda item: item[1])
                if path.suffix.lower() == f".{suffix}"
                and path.stem.endswith(("_PANEL_A", "_PANEL_B"))
            )
        writer.writerow({
            "plot_id": record["plot_id"],
            "output_group": record["output_group"],
            "scope_label": record["scope_label"],
            "title": record.get("title", ""),
            "status": record["status"],
            "source_file": record["source_file"],
            "composite_png": one("COMPOSITE", "png"),
            "composite_pdf": one("COMPOSITE", "pdf"),
            "composite_svg": one("COMPOSITE", "svg"),
            "panel_png_assets": panels("png"),
            "panel_pdf_assets": panels("pdf"),
            "panel_svg_assets": panels("svg"),
        })
    path = output_root / "PLOT_CATALOG.csv"
    _atomic_text(path, stream.getvalue())
    return path, len(records)


def _write_plot_qa(output_root: Path, records: list[dict[str, Any]]) -> tuple[Path, dict[str, int]]:
    """Record decode, 4K, and forbidden-metadata checks for every delivered PNG."""

    from io import StringIO
    from PIL import Image

    family_by_png: dict[Path, dict[str, Any]] = {}
    for record in records:
        for asset in record.get("artifacts", []):
            path = Path(asset)
            if path.suffix.lower() == ".png":
                family_by_png[path.resolve()] = record
    fields = [
        "asset", "asset_type", "plot_id", "output_group", "openable",
        "width_px", "height_px", "long_edge_px", "long_edge_ge_4096",
        "forbidden_text_contract", "forbidden_text_status", "status",
    ]
    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    failures = 0
    pngs = sorted(output_root.rglob("*.png"))
    for path in pngs:
        openable = False
        width = height = long_edge = 0
        forbidden_status = "PASS"
        try:
            with Image.open(path) as image:
                image.load()
                width, height = image.size
                metadata = " ".join(f"{key}={value}" for key, value in image.info.items()).lower()
            openable = True
            long_edge = max(width, height)
            if any(term.lower() in metadata for term in FORBIDDEN_FIGURE_TEXT):
                forbidden_status = "FAIL"
        except Exception:
            openable = False
        long_edge_ok = long_edge >= 4096
        status = "PASS" if openable and long_edge_ok and forbidden_status == "PASS" else "FAIL"
        failures += int(status == "FAIL")
        record = family_by_png.get(path.resolve())
        writer.writerow({
            "asset": str(path.relative_to(output_root)),
            "asset_type": "PLOT_FAMILY" if record else "CONTACT_SHEET",
            "plot_id": record["plot_id"] if record else "",
            "output_group": record["output_group"] if record else "99_GALLERY",
            "openable": str(openable).lower(),
            "width_px": width,
            "height_px": height,
            "long_edge_px": long_edge,
            "long_edge_ge_4096": str(long_edge_ok).lower(),
            "forbidden_text_contract": "no banned reference-provenance wording in PNG metadata",
            "forbidden_text_status": forbidden_status,
            "status": status,
        })
    qa_path = output_root / "PLOT_QA.csv"
    _atomic_text(qa_path, stream.getvalue())
    return qa_path, {"png_rows": len(pngs), "failed_rows": failures}


def _write_gallery_outputs(
    output_root: Path, records: list[dict[str, Any]]
) -> tuple[Path, list[Path]]:
    gallery_path = write_gallery(output_root, records)
    contact_sheets = write_contact_sheets(output_root, records)
    return gallery_path, contact_sheets


def _summaries(
    output_root: Path,
    records: list[dict[str, Any]],
    *,
    started: float,
    requested_workers: int,
    effective_workers: int,
    peak_workers: int,
    progress_interval: float,
    contact_sheets: list[Path],
    gallery_path: Path,
    force_plot_ids: set[str],
    catalog_path: Path,
    catalog_rows: int,
    qa_path: Path,
    qa_counts: dict[str, int],
) -> dict[str, Any]:
    counts = _output_counts(output_root)
    complete = [row for row in records if str(row["status"]).startswith("COMPLETE")]
    skipped = [row for row in records if str(row["status"]).startswith("SKIPPED")]
    failed = [row for row in records if str(row["status"]).startswith(("FAILED", "BLOCKED"))]
    current_redrawn = {
        row["plot_id"] for row in complete
        if row["plot_id"] in force_plot_ids and row["status"] == "COMPLETE"
    }
    previous_redrawn: set[str] = set()
    prior_status_path = output_root / "PLOTTING_STATUS.json"
    if prior_status_path.is_file():
        try:
            previous_redrawn = set(json.loads(prior_status_path.read_text(encoding="utf-8")).get("redrawn_families", []))
        except (OSError, ValueError, TypeError):
            previous_redrawn = set()
    completed_ids = {row["plot_id"] for row in complete}
    redrawn = sorted((previous_redrawn | current_redrawn) & completed_ids)
    reused = sorted(completed_ids - set(redrawn))
    png_4k = 0
    png_8k = 0
    for path in output_root.rglob("*.png"):
        try:
            from PIL import Image

            with Image.open(path) as image:
                edge = max(image.size)
            png_4k += int(edge >= 3840)
            png_8k += int(edge >= 7680)
        except Exception:
            pass
    terminal = (
        "PASS_CLEAN4_HORIZONTAL_FULL_PLOTTING_COMPLETE"
        if len(complete) + len(skipped) == len(records) and not failed
        else "PARTIAL_CLEAN4_HORIZONTAL_FULL_PLOTTING_WITH_RECORDED_FAILURES"
    )
    status: dict[str, Any] = {
        "terminal_status": terminal,
        "total_families": len(records),
        "completed_families": len(complete),
        "skipped_missing_source_field": len(skipped),
        "failed_families": len(failed),
        "output_counts": counts,
        "png_4k_or_larger": png_4k,
        "png_8k_or_larger": png_8k,
        "requested_workers": requested_workers,
        "effective_workers": effective_workers,
        "actual_peak_workers": peak_workers,
        "refinement_mode": bool(redrawn),
        "redrawn_families": redrawn,
        "reused_families": reused,
        "progress_interval_seconds": progress_interval,
        "progress_heartbeat_enabled": True,
        "elapsed_seconds": time.monotonic() - started,
        "gallery": str(gallery_path),
        "contact_sheets": [str(path) for path in contact_sheets],
        "plot_catalog": str(catalog_path),
        "plot_catalog_rows": catalog_rows,
        "plot_qa": str(qa_path),
        "plot_qa_png_rows": qa_counts["png_rows"],
        "plot_qa_failed_rows": qa_counts["failed_rows"],
        "families": sorted(records, key=lambda row: row["plot_id"]),
        "execution_counts": {
            "all_solvers": 0,
            "all_external_methods": 0,
            "provider_generation": 0,
            "Hartley_filter": 0,
            "MATLAB_GINav": 0,
            "exact_evaluator": 0,
            "Canonical_runner": 0,
            "Canonical_plotting_runner": 0,
            "aggregate_rerun": 0,
            "Classic_18": 0,
        },
        "tim_candidate_selection_performed": False,
        "zip_created": False,
        "hash_manifest_created": False,
        "seal_created": False,
    }
    _atomic_text(output_root / "PLOTTING_STATUS.json", json.dumps(status, indent=2, sort_keys=True) + "\n")
    by_group: dict[str, int] = {}
    for row in complete:
        by_group[row["output_group"]] = by_group.get(row["output_group"], 0) + 1
    lines = [
        "# CLEAN4 Horizontal Full Plotting Summary",
        "",
        f"Terminal status: `{terminal}`",
        "",
        f"Families: total={len(records)}, complete={len(complete)}, skipped={len(skipped)}, failed={len(failed)}.",
        f"Outputs: PNG={counts['PNG']}, PDF={counts['PDF']}, SVG={counts['SVG']}; PNG >=4K={png_4k}, PNG >=8K={png_8k}.",
        f"Workers: requested={requested_workers}, effective={effective_workers}, actual peak={peak_workers}; progress interval={progress_interval:g} s.",
        f"Refinement: mode={'targeted' if redrawn else 'none'}, redrawn={len(redrawn)}, reused={len(reused)}.",
        f"Redrawn families: {', '.join(redrawn) if redrawn else 'None'}.",
        f"Catalog: `{catalog_path.name}` with {catalog_rows} family rows.",
        f"PNG QA: `{qa_path.name}` with {qa_counts['png_rows']} rows and {qa_counts['failed_rows']} failures.",
        "",
        "## Completed families by output directory",
        "",
        *[f"- `{group}`: {count}" for group, count in sorted(by_group.items())],
        "",
        "## Skipped or failed families",
        "",
        *([f"- `{row['plot_id']}` — `{row['status']}`: {row['reason']}" for row in skipped + failed] or ["- None."]),
        "",
        "## Execution and selection boundary",
        "",
        "All solver, external-method, Hartley-filter, MATLAB/GINav, exact-evaluator, Canonical-runner, Canonical-plotting-runner, and Classic-18 execution counts are zero.",
        "No TIM main-text candidate screening or ranking was performed.",
        "No ZIP, hash manifest, seal, evidence inventory, or certification report was created.",
    ]
    _atomic_text(output_root / "PLOTTING_SUMMARY.md", "\n".join(lines) + "\n")
    return status


def _memory_safe_workers(requested: int) -> int:
    try:
        available_kib = 0
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                available_kib = int(line.split()[1])
                break
        if available_kib:
            reserve_kib = 3 * 1024 * 1024
            per_worker_kib = 1200 * 1024
            safe = max(1, (available_kib - reserve_kib) // per_worker_kib)
            return min(requested, int(safe))
    except Exception:
        pass
    return requested


def run(args: argparse.Namespace) -> int:
    requested_workers = validate_worker_count(args.workers)
    if args.progress_interval != 10:
        raise ValueError("formal horizontal plotting requires --progress-interval 10")
    if args.dpi != 300:
        raise ValueError("formal horizontal plotting requires --dpi 300")
    formats = tuple(item.strip().lower() for item in args.formats.split(",") if item.strip())
    if formats != ("png", "pdf", "svg"):
        raise ValueError("formal formats must be exactly png,pdf,svg")
    registry_path = Path(args.registry).resolve()
    families = load_registry(registry_path)
    force_plot_ids = set(args.force_plot_id)
    unknown_force_ids = force_plot_ids - {family.plot_id for family in families}
    if unknown_force_ids:
        raise ValueError(
            f"unknown --force-plot-id value(s): {', '.join(sorted(unknown_force_ids))}"
        )
    comparison_root = Path(args.input_root).resolve()
    canonical_attempt = Path(args.canonical_attempt).resolve()
    output_root = Path(args.output_root).resolve()
    if args.validate_only:
        records = validate_sources(
            families,
            comparison_root=comparison_root,
            canonical_attempt=canonical_attempt,
        )
        for record in records:
            suffix = f" — {record['reason']}" if record["reason"] else ""
            print(f"{record['plot_id']}: {record['status']}{suffix}", flush=True)
        failures = [
            record
            for record in records
            if record["status"].startswith(("FAILED", "BLOCKED"))
        ]
        print(
            f"SOURCE_PREFLIGHT total={len(records)} ready={sum(record['status'] == 'SOURCE_READY' for record in records)} "
            f"skipped={sum(record['status'].startswith('SKIPPED') for record in records)} failed={len(failures)}",
            flush=True,
        )
        return 0 if not failures else 2
    _dependency_preflight()
    if output_root.name != "14_HORIZONTAL_FULL_PLOTTING":
        raise ValueError("output root must be the dedicated 14_HORIZONTAL_FULL_PLOTTING directory")
    if output_root == comparison_root or output_root == canonical_attempt:
        raise ValueError("output root cannot equal an evidence root")
    for group in OUTPUT_GROUPS:
        (output_root / group).mkdir(parents=True, exist_ok=True)
    snapshot = output_root / "00_PLOT_CONTRACT" / "PLOT_REGISTRY.csv"
    if not snapshot.exists():
        _atomic_text(snapshot, registry_path.read_text(encoding="utf-8"))
    elif snapshot.read_text(encoding="utf-8") != registry_path.read_text(encoding="utf-8"):
        raise ValueError("resume registry differs from frozen output snapshot")
    effective_workers = _memory_safe_workers(requested_workers)
    print(
        f"CLEAN4 horizontal full plotting: families={len(families)} requested_workers={requested_workers} effective_workers={effective_workers} progress_interval={args.progress_interval}s",
        flush=True,
    )
    tasks = [
        {
            "family": asdict(family),
            "comparison_root": str(comparison_root),
            "canonical_attempt": str(canonical_attempt),
            "output_root": str(output_root),
            "formats": formats,
            "dpi": args.dpi,
            "default_width": args.default_width,
            "default_height": args.default_height,
            "dense_width": args.dense_width,
            "dense_height": args.dense_height,
            "force_rewrite": family.plot_id in force_plot_ids,
        }
        for family in families
    ]
    started = time.monotonic()
    records: list[dict[str, Any]] = []
    active: dict[Any, tuple[str, float]] = {}
    next_task = 0
    peak_workers = 0
    last_done: list[str] = []
    next_heartbeat = started + args.progress_interval
    _heartbeat(
        started=started,
        total=len(tasks),
        records=records,
        active={},
        queued=len(tasks),
        last_done=last_done,
        output_root=output_root,
        worker_limit=effective_workers,
        phase="starting",
    )
    with ProcessPoolExecutor(max_workers=effective_workers) as pool:
        while next_task < len(tasks) and len(active) < effective_workers:
            task = tasks[next_task]
            future = pool.submit(_worker, task)
            active[future] = (task["family"]["plot_id"], time.monotonic())
            next_task += 1
        peak_workers = max(peak_workers, len(active))
        while active:
            timeout = max(0.0, next_heartbeat - time.monotonic())
            done, _ = wait(active, timeout=timeout, return_when=FIRST_COMPLETED)
            for future in done:
                plot_id, _ = active.pop(future)
                try:
                    record = future.result()
                except Exception as exc:
                    record = {
                        "plot_id": plot_id,
                        "output_group": "UNKNOWN",
                        "scope_label": "UNKNOWN",
                        "source_file": "UNKNOWN",
                        "output_dir": "UNKNOWN",
                        "status": "FAILED_WORKER_FUTURE",
                        "reason": f"{type(exc).__name__}: {exc}",
                        "duration_s": 0.0,
                        "worker_pid": None,
                        "artifacts": [],
                    }
                records.append(record)
                last_done.append(plot_id)
                if next_task < len(tasks):
                    task = tasks[next_task]
                    replacement = pool.submit(_worker, task)
                    active[replacement] = (task["family"]["plot_id"], time.monotonic())
                    next_task += 1
            peak_workers = max(peak_workers, len(active))
            now = time.monotonic()
            if now >= next_heartbeat:
                _heartbeat(
                    started=started,
                    total=len(tasks),
                    records=records,
                    active=active,
                    queued=len(tasks) - next_task,
                    last_done=last_done,
                    output_root=output_root,
                    worker_limit=effective_workers,
                )
                while next_heartbeat <= now:
                    next_heartbeat += args.progress_interval
    _heartbeat(
        started=started,
        total=len(tasks),
        records=records,
        active={},
        queued=0,
        last_done=last_done,
        output_root=output_root,
        worker_limit=effective_workers,
        phase="render-complete",
    )
    _write_status_csv(output_root, records)
    postprocess_started = time.monotonic()
    with ThreadPoolExecutor(max_workers=1) as postprocess_pool:
        postprocess = postprocess_pool.submit(_write_gallery_outputs, output_root, records)
        while True:
            try:
                gallery_path, contact_sheets = postprocess.result(
                    timeout=args.progress_interval
                )
                break
            except FuturesTimeoutError:
                counts = _output_counts(output_root)
                print(
                    f"[{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"elapsed={_duration(time.monotonic() - started)} "
                    f"postprocess=gallery_and_contact_sheets "
                    f"postprocess_elapsed={_duration(time.monotonic() - postprocess_started)} "
                    f"outputs: PNG={counts['PNG']} PDF={counts['PDF']} SVG={counts['SVG']}",
                    flush=True,
                )
    catalog_path, catalog_rows = _write_plot_catalog(output_root, records)
    qa_path, qa_counts = _write_plot_qa(output_root, records)
    status = _summaries(
        output_root,
        records,
        started=started,
        requested_workers=requested_workers,
        effective_workers=effective_workers,
        peak_workers=peak_workers,
        progress_interval=args.progress_interval,
        contact_sheets=contact_sheets,
        gallery_path=gallery_path,
        force_plot_ids=force_plot_ids,
        catalog_path=catalog_path,
        catalog_rows=catalog_rows,
        qa_path=qa_path,
        qa_counts=qa_counts,
    )
    print(status["terminal_status"], flush=True)
    return 0 if status["failed_families"] == 0 else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--canonical-attempt", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--progress-interval", type=float, default=10)
    parser.add_argument("--default-width", type=int, default=5120)
    parser.add_argument("--default-height", type=int, default=2880)
    parser.add_argument("--dense-width", type=int, default=7680)
    parser.add_argument("--dense-height", type=int, default=4320)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--formats", default="png,pdf,svg")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--force-plot-id", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
