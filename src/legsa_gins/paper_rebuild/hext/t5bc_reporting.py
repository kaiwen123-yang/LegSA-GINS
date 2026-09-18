"""Pure T5bc aggregation over caller-verified rows and sealed error frames.

There is no file access, native execution, evaluator invocation, or reference
trace access in this module. The caller owns pin/seal verification. Comparator
CSV tokens are retained verbatim; missing matrix slots never disappear.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import math

import numpy as np
import pandas as pd

from .aggregate import AVAILABLE, METRIC_FIELDS, TABLE_FIELDS, normalize_row, validate_evaluation_payload
from .readonly_closeout import region_masks
from .t5a_reporting import (ERROR_COLUMNS, NUMERIC_FIELDS, REGIONS, derive_segments, scalar_delta,
                            unavailable_segments)

UNAVAILABLE = "UNAVAILABLE"
FROZEN = "FROZEN_V21"
T5A_R5 = "T5A_R5"
SEQUENCES = ("BY2", "BY2H", "BY2O")
PROFILES = ("F02", "A04", "F04")
VARIANTS = ("R5W", "R5SIGMA", "B3")
SUBSET_VARIANTS = ("R5", *VARIANTS)
EXTRA_FIELDS = (
    "nis_mean", "nis_coverage_95", "nis_selection_coverage",
    "configuration_id", "variant", "role", "data_mode", "synthetic_data_used",
    "semisynthetic_data_used", "frozen_source_table", "frozen_source_line",
    "t5a_r5_source_table", "t5a_r5_source_line",
    *("delta_vs_frozen_" + field for field in NUMERIC_FIELDS),
    *("delta_vs_t5a_r5_" + field for field in NUMERIC_FIELDS),
)
PILOT_FIELDS = (*TABLE_FIELDS, *EXTRA_FIELDS)


def sequence_slots():
    """The 15 authorized new sequence runs; scalar weights are F04 only."""
    return tuple((sequence, profile, variant) for sequence in SEQUENCES
                 for profile in PROFILES for variant in VARIANTS
                 if profile == "F04" or variant == "B3")


def _version(version):
    if version not in ("v2", "v3"):
        raise ValueError("Only preregistered evaluator versions v3/v2 are allowed")
    return "evaluator_contract_" + version


def _mode(data_mode):
    if data_mode not in ("real_raw", "real_clean", "real", "semisynthetic", "synthetic"):
        raise ValueError("Explicit supported data_mode is required")
    return {"data_mode": data_mode, "synthetic_data_used": data_mode == "synthetic",
            "semisynthetic_data_used": data_mode == "semisynthetic"}


def _checked_role(source, data_mode, *, required=False, csv_source=False):
    """Do not relabel observed data to match the destination table's cohort."""
    expected = _mode(data_mode)
    result = {}
    for field, target in expected.items():
        value = source.get(field)
        if value in (None, "", UNAVAILABLE):
            if required:
                raise ValueError("Admitted evaluation data role must be explicit: " + field)
            result[field] = UNAVAILABLE
            continue
        if csv_source and field != "data_mode" and value in ("True", "False", "true", "false"):
            value = value.lower() == "true"
        if (field != "data_mode" and type(value) is not bool) or value != target:
            raise ValueError("Data role conflicts with destination cohort: " + field)
        result[field] = value
    return result


def _case_identity(row):
    """Runtime uses subset_case_id; frozen aggregates historically use case_id."""
    case, subset = row.get("case_id"), row.get("subset_case_id")
    if "case_id" in row and "subset_case_id" in row and case != subset:
        raise ValueError("case_id and subset_case_id identities disagree")
    return subset if "subset_case_id" in row else case


def _profile(row):
    return row.get("configuration_id", row.get("method_id"))


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _records(rows):
    """Accept CSV rows, or (source_line, CSV row) without changing any token."""
    for item in rows:
        if isinstance(item, tuple) and len(item) == 2:
            line, row = item
        else:
            line, row = item.get("frozen_source_line", UNAVAILABLE), item
        yield line, row


def _reference_index(rows, *, version, profiles, variant=None):
    expected = {(s, p) for s in SEQUENCES for p in profiles}
    result = {}
    for line, row in _records(rows):
        key = (row.get("sequence_id"), _profile(row))
        if key not in expected or row.get("evaluator_contract") != _version(version):
            continue
        if variant is not None and row.get("variant") not in (variant, T5A_R5):
            continue
        if key in result:
            raise ValueError("Duplicate same-sequence/configuration comparator")
        if any(field not in row for field in TABLE_FIELDS):
            raise ValueError("Frozen comparator table schema changed")
        result[key] = (line, row)
    if set(result) != expected:
        raise ValueError("Missing same-sequence/configuration frozen comparator")
    return result


def _deltas(row, reference, prefix):
    admitted = row.get("evaluation_status", row.get("status")) in AVAILABLE
    comparable = reference is not None and reference.get(
        "evaluation_status", reference.get("status")) in AVAILABLE
    return {prefix + field: scalar_delta(row.get(field), reference.get(field))
            if admitted and comparable else UNAVAILABLE for field in NUMERIC_FIELDS}


def _candidate(payload, *, sequence, profile, variant, version, data_mode):
    source = dict(payload.get("row", {}))
    admitted = source.get("evaluation_status") in AVAILABLE
    role = _checked_role(source, data_mode, required=admitted)
    if admitted:
        validate_evaluation_payload(payload, version=version, continuation_v11=True)
        if source.get("metrics_admitted") is False or payload["audit"].get("consistency_passed") is False:
            raise ValueError("Rejected evaluator capture cannot contribute pilot metrics")
    if not admitted:
        source.update({field: UNAVAILABLE for field in NUMERIC_FIELDS})
        source.update(error_series_source=UNAVAILABLE,
                      evaluation_status=source.get("evaluation_status", "NOT_RUN"),
                      failure_classification=source.get("failure_classification", "NOT_EXECUTED"))
    row = normalize_row(source, sequence_id=sequence, method_id=profile, config=profile,
                        start="FROZEN_V21_RUNTIME_CONFIG", geometric_status="NOT_APPLICABLE",
                        body_bias=payload.get("body_frame_bias", {}) if admitted else {},
                        notes=source.get("notes", "T5bc sensitivity outside frozen chain; no v2.1 row replaced"))
    row.update(configuration_id=profile, variant=variant,
               evaluator_contract=_version(version), role="SENSITIVITY_OUTSIDE_FROZEN_CHAIN", **role)
    for field in ("gap_events_in_window", "gnss2_pacc_inflated_epochs", "gnss2_float_epochs"):
        row[field] = source.get(field, "NOT_APPLICABLE") if admitted else UNAVAILABLE
    # Check after alias/body-bias normalization: runtime emits
    # horizontal_rmse_m and a separate body_frame_bias mapping.
    nonfinite = []
    if admitted:
        for field in NUMERIC_FIELDS:
            try:
                value = float(row.get(field))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(value):
                nonfinite.append(field)
    if nonfinite:
        admitted = False
        row.update({field: UNAVAILABLE for field in NUMERIC_FIELDS})
        row.update(evaluation_status="UNAVAILABLE_NONFINITE_METRICS", failure_classification="NONFINITE_METRICS",
                   error_series_source=UNAVAILABLE,
                   notes="Nonfinite normalized metrics: " + ",".join(nonfinite))
    return row


def pilot_rows(frozen_rows, t5a_rows, evaluations, literature_rows, *, version,
               data_mode="real_raw"):
    """Return 36 rows: 9 frozen, 6 T5a R5, 15 new slots, and 6 literature.

    New evaluation entries have the existing sealed ``{row, audit,
    body_frame_bias}`` shape. Frozen/T5a/literature arguments are already pinned
    CSV rows. Literature rows must be the six caller-selected primary rows;
    this function never chooses a start convention using performance.
    """
    if data_mode == "semisynthetic":
        raise ValueError("Semisynthetic cases belong only in the separate subset table")
    mode = _mode(data_mode)
    frozen = _reference_index(frozen_rows, version=version, profiles=PROFILES)
    t5a = _reference_index(t5a_rows, version=version, profiles=("F02", "F04"), variant="R5")
    expected = set(sequence_slots())
    lookup = {}
    for payload in evaluations:
        source = payload["row"]
        if source.get("evaluator_contract") != _version(version):
            continue
        key = (source.get("sequence_id"), _profile(source), source.get("variant"))
        if key not in expected or key in lookup:
            raise ValueError("Duplicate or unauthorized pilot evaluation slot")
        if _case_identity(source) is not None:
            raise ValueError("A subset evaluation cannot enter a sequence pilot table")
        if source.get("semisynthetic_data_used") is True or source.get("data_mode") == "semisynthetic":
            raise ValueError("Semisynthetic evaluation cannot enter a sequence pilot table")
        lookup[key] = payload
    result = []
    for sequence in SEQUENCES:
        for profile in PROFILES:
            line, reference = frozen[sequence, profile]
            r5_line, r5 = t5a.get((sequence, profile), (UNAVAILABLE, None))
            _checked_role(reference, data_mode, csv_source=True)
            if r5 is not None:
                _checked_role(r5, data_mode, csv_source=True)
            refs = {"frozen_source_table": reference.get("frozen_source_table", UNAVAILABLE),
                    "frozen_source_line": line,
                    "t5a_r5_source_table": r5.get("frozen_source_table", UNAVAILABLE) if r5 else UNAVAILABLE,
                    "t5a_r5_source_line": r5_line}
            baseline = {field: reference[field] for field in TABLE_FIELDS}
            baseline.update(configuration_id=profile, variant=FROZEN, role="FROZEN_COMPARATOR_UNCHANGED", **mode)
            rows = [baseline]
            if r5 is not None:
                rows.append({**{field: r5[field] for field in TABLE_FIELDS},
                             "configuration_id": profile, "variant": T5A_R5,
                             "role": "T5A_R5_COMPARATOR_UNCHANGED", **mode})
            for variant in VARIANTS:
                key = (sequence, profile, variant)
                if key in expected:
                    rows.append(_candidate(lookup.get(key, {}), sequence=sequence, profile=profile,
                                           variant=variant, version=version, data_mode=data_mode))
            for row in rows:
                row.update(refs)
                row.update(_deltas(row, reference, "delta_vs_frozen_"))
                row.update(_deltas(row, r5, "delta_vs_t5a_r5_"))
                result.append(row)
    literature = {}
    for line, original in _records(literature_rows):
        if original.get("evaluator_contract") != _version(version):
            continue
        key = original.get("sequence_id"), original.get("method_id")
        if key not in {(s, p) for s in SEQUENCES for p in ("LC01", "LC01-S")} or key in literature:
            raise ValueError("Literature comparison requires one selected LC01/LC01-S row per sequence")
        if any(field not in original for field in TABLE_FIELDS):
            raise ValueError("Frozen literature schema changed")
        _checked_role(original, data_mode, csv_source=True)
        row = {field: original[field] for field in TABLE_FIELDS}
        row.update(configuration_id=original["method_id"], variant=original["method_id"],
                   role="FROZEN_LITERATURE_COMPARATOR_UNCHANGED", **mode,
                   frozen_source_table=original.get("frozen_source_table", UNAVAILABLE),
                   frozen_source_line=line, t5a_r5_source_table=UNAVAILABLE,
                   t5a_r5_source_line=UNAVAILABLE)
        row.update(_deltas(row, None, "delta_vs_frozen_"))
        row.update(_deltas(row, None, "delta_vs_t5a_r5_"))
        literature[key] = row
    if len(literature) != 6:
        raise ValueError("Six pinned literature comparison rows required")
    result.extend(literature[s, p] for s in SEQUENCES for p in ("LC01", "LC01-S"))
    for row in result:
        for key in ("nis_mean", "nis_coverage_95", "nis_selection_coverage"):
            row.setdefault(key, UNAVAILABLE)
    return result


def derive_by2o_segments(errors, *, profile, variant, version, window, source,
                         evaluation_status="AVAILABLE", data_mode="real_raw"):
    """Five closed-region summaries; one nonfinite epoch invalidates the series.

    ``errors`` must be the same-run sealed full-rate evaluator error frame.
    No missing/failed frame is replaced by a frozen or thinned frame.
    """
    _version(version)
    if errors is None or evaluation_status not in AVAILABLE:
        rows = unavailable_segments(profile, variant, version, evaluation_status)
    else:
        try:
            if any(column not in errors for column in ERROR_COLUMNS):
                raise ValueError("Sealed evaluator error-series schema changed")
            if not np.isfinite(errors[list(ERROR_COLUMNS)].to_numpy(float)).all():
                raise ValueError("Nonfinite error series; epoch deletion forbidden")
            rows = derive_segments(errors, profile=profile, variant=variant, version=version,
                                   window=window, source=source)
        except ValueError as error:
            if "Nonfinite" not in str(error):
                raise
            rows = unavailable_segments(profile, variant, version, "NONFINITE_ERROR_SERIES")
    for row in rows:
        row.update(_mode(data_mode))
    return rows


def by2o_segment_rows(frozen_rows, t5a_rows, new_rows, *, version, data_mode="real_raw"):
    """Align the 12 BY2O variant/configuration combinations across five regions.

    Comparator rows are copied without recalculation. Absent region rows stay
    explicit UNAVAILABLE; A04 never obtains a fabricated T5a R5 comparator.
    """
    slots = [(p, FROZEN) for p in PROFILES] + [(p, T5A_R5) for p in ("F02", "F04")]
    slots += [(p, v) for s, p, v in sequence_slots() if s == "BY2O"]
    lookup = {}
    for category, inputs in ((FROZEN, frozen_rows), (T5A_R5, t5a_rows), (None, new_rows)):
        for _, original in _records(inputs):
            if original.get("evaluator_contract") != _version(version) or original.get("sequence_id") != "BY2O":
                continue
            if category == T5A_R5 and original.get("variant") not in ("R5", T5A_R5):
                continue
            variant = category or original.get("variant")
            key = (_profile(original), variant, original.get("segment_id"))
            if key[:2] not in slots or key[2] not in REGIONS:
                if category is None:
                    raise ValueError("Unregistered new BY2O segment slot")
                continue
            if key in lookup:
                raise ValueError("Duplicate BY2O segment identity")
            role = _checked_role(original, data_mode, required=category is None and original.get("status") in AVAILABLE,
                                 csv_source=True)
            row = deepcopy(original)
            row.update(configuration_id=key[0], variant=variant, **(_mode(data_mode) if category else role))
            lookup[key] = row
    result = []
    for profile, variant in slots:
        for region in REGIONS:
            row = deepcopy(lookup.get((profile, variant, region)))
            if row is None:
                row = next(r for r in unavailable_segments(profile, variant, version,
                                                           "NO_SEALED_SEGMENT_SLOT") if r["segment_id"] == region)
                row.update(_mode(data_mode))
            for prefix, ref_variant in (("delta_vs_frozen_", FROZEN), ("delta_vs_t5a_r5_", T5A_R5)):
                row.update(_deltas(row, lookup.get((profile, ref_variant, region)), prefix))
            result.append(row)
    return result


def subset_rows(frozen_rows, evaluations, *, case_ids, pending_rows=(), version="v3",
                case_data_modes=None):
    """Return explicit 5*N F04 rows and an unchanged copy of pending records.

    The caller supplies the authorized case list; no 42/61-case interpretation
    is embedded here. C00 is labelled real_raw; injected cases semisynthetic.
    Synthetic fixtures can override per-case modes explicitly.
    """
    cases = tuple(case_ids)
    if len(set(cases)) != len(cases):
        raise ValueError("Duplicate authorized subset case")
    frozen = {}
    for line, row in _records(frozen_rows):
        case = _case_identity(row)
        if case not in cases or _profile(row) != "F04" or row.get("evaluator_contract") != _version(version):
            continue
        if row.get("sequence_id", "BY2") != "BY2" or case in frozen:
            raise ValueError("Duplicate or non-BY2 frozen subset comparator")
        frozen[case] = (line, row)
    if set(frozen) != set(cases):
        raise ValueError("Every authorized subset case requires its frozen v2.1 F04 row")
    lookup = {}
    for payload in evaluations:
        row = payload["row"]
        if row.get("evaluator_contract") != _version(version):
            continue
        key = _case_identity(row), row.get("variant")
        if (key[0] not in cases or key[1] not in SUBSET_VARIANTS or key in lookup
                or row.get("sequence_id") != "BY2" or _profile(row) != "F04"):
            raise ValueError("Duplicate or unauthorized subset evaluation slot")
        lookup[key] = payload
    result = []
    for case in cases:
        line, original = frozen[case]
        # Core-541 frozen sources need not have the horizontal table schema;
        # normalization maps metric aliases but keeps original scalar tokens.
        reference = normalize_row(original, sequence_id="BY2", method_id="F04", config="F04",
                                  start=FROZEN, geometric_status="NOT_APPLICABLE",
                                  notes=original.get("notes", "Frozen v2.1 subset row, unchanged"))
        # Retain every original core-matrix column and token in addition to aliases.
        reference = {**original, **reference}
        reference.update({field: original[field] for field in TABLE_FIELDS if field in original})
        data_mode = (case_data_modes or {}).get(case, original.get("data_mode", "real_raw") if case == "C00_clean_normal" else "semisynthetic")
        _checked_role(original, data_mode, csv_source=True)
        reference.update(_mode(data_mode))
        for variant in (FROZEN, *SUBSET_VARIANTS):
            row = dict(reference) if variant == FROZEN else _candidate(
                lookup.get((case, variant), {}), sequence="BY2", profile="F04", variant=variant,
                version=version, data_mode=data_mode)
            if variant != FROZEN:
                payload = lookup.get((case, variant), {})
                full = payload.get("subset_metrics", payload.get("row", {}))
                # Preserve case-window, recovery, consistency and runtime metrics.
                if row.get("evaluation_status") not in AVAILABLE:
                    full = {key: UNAVAILABLE if _is_metric(key) else value for key, value in full.items()}
                row = {**full, **row}
            row.update(case_id=case, configuration_id="F04", variant=variant,
                       role="FROZEN_SUBSET_COMPARATOR_UNCHANGED" if variant == FROZEN else "SUBSET_SENSITIVITY_OUTSIDE_FROZEN_CHAIN",
                       table_cohort="DEGRADATION_SUBSET",
                       frozen_source_table=original.get("frozen_source_table", UNAVAILABLE),
                       frozen_source_line=line)
            row.update(_deltas(row, reference, "delta_vs_frozen_"))
            # Full canonical metrics are paired as well, excluding identity/provenance.
            for field in original:
                if _is_metric(field):
                    row["delta_vs_frozen_" + field] = scalar_delta(row.get(field), original.get(field)) if row.get("evaluation_status") in AVAILABLE and reference.get("evaluation_status") in AVAILABLE else UNAVAILABLE
            result.append(row)
    pending = deepcopy(list(pending_rows))
    if any(_case_identity(row) in cases for row in pending):
        raise ValueError("A pending injection case cannot also be an executed subset case")
    return result, pending


def subset_distributions(rows, *, case_ids, metrics=METRIC_FIELDS):
    """Paired candidate-minus-frozen distributions; no directional decision.

    ``worst_5pct_mean`` is the mean of the largest ceil(0.05*n) paired
    differences. ``p95`` uses NumPy's linear sample quantile. Missing/nonfinite
    pairs are counted separately and never replaced with zero or frozen data.
    Failure count means an explicitly present non-available, non-NOT_RUN row.
    """
    cases = tuple(case_ids)
    if len(set(cases)) != len(cases):
        raise ValueError("Duplicate distribution case")
    lookup = {}
    for row in rows:
        key = _case_identity(row), row.get("variant")
        if key[0] not in cases or key[1] not in (FROZEN, *SUBSET_VARIANTS) or key in lookup:
            raise ValueError("Duplicate or unregistered subset distribution row")
        lookup[key] = row
    result = []
    for variant in SUBSET_VARIANTS:
        cohort_rows = [row for (case, item_variant), row in lookup.items()
                       if item_variant in (FROZEN, variant)]
        data_modes = sorted({str(row.get("data_mode", UNAVAILABLE)) for row in cohort_rows})
        cohort_mode = {"data_modes": data_modes,
                       "data_mode": data_modes[0] if len(data_modes) == 1 else "MIXED_DATA_MODES" if data_modes else "UNAVAILABLE_NO_CASES",
                       "synthetic_data_used": any(row.get("synthetic_data_used") is True for row in cohort_rows),
                       "semisynthetic_data_used": any(row.get("semisynthetic_data_used") is True for row in cohort_rows)}
        for metric in metrics:
            values, failed, not_run, unpaired = [], 0, 0, 0
            for case in cases:
                candidate = lookup.get((case, variant), {})
                reference = lookup.get((case, FROZEN), {})
                status = candidate.get("evaluation_status", "NOT_RUN")
                if str(status).startswith("NOT_RUN"):
                    not_run += 1
                elif status not in AVAILABLE:
                    failed += 1
                delta = scalar_delta(candidate.get(metric), reference.get(metric))
                value = _number(delta)
                if status in AVAILABLE and reference.get("evaluation_status") in AVAILABLE and value is not None:
                    values.append(value)
                else:
                    unpaired += 1
            array = np.asarray(values, float)
            tail_count = math.ceil(.05 * len(array))
            result.append({"variant": variant, "configuration_id": "F04", "metric": metric,
                           "case_count": len(cases), "valid_paired_count": len(array),
                           "unpaired_count": unpaired, "failure_count": failed, "not_run_count": not_run,
                           "paired_delta_mean": float(np.mean(array)) if len(array) else UNAVAILABLE,
                           "paired_delta_median": float(np.median(array)) if len(array) else UNAVAILABLE,
                           "paired_delta_p95": float(np.percentile(array, 95)) if len(array) else UNAVAILABLE,
                           "paired_delta_worst_5pct_mean": float(np.mean(np.sort(array)[-tail_count:])) if len(array) else UNAVAILABLE,
                           "worst_5pct_count": tail_count,
                           "tail_definition": "Largest ceil(0.05 * valid_paired_count) candidate-minus-frozen differences",
                           "quantile_method": "LINEAR", "status": "AVAILABLE" if len(array) else UNAVAILABLE,
                           "table_cohort": "DEGRADATION_SUBSET", "directional_decision": "NOT_DEFINED", **cohort_mode})
    return result


def _flags(frame, column):
    values = pd.to_numeric(frame[column], errors="raise").to_numpy(float)
    if not np.isfinite(values).all() or not np.isin(values, (0., 1.)).all():
        raise ValueError("Diagnostic flags must be finite binary values: " + column)
    return values == 1


def _diagnostic_statistics(values, prefix, *, absolute_p95=False):
    """Statistics over available cells, with every missing cell accounted for."""
    numeric, missing, nonfinite = [], 0, 0
    for value in values:
        if value is None or value == "" or pd.isna(value):
            missing += 1
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            nonfinite += 1
            continue
        if not math.isfinite(number):
            nonfinite += 1
        else:
            numeric.append(number)
    array = np.asarray(numeric, float)
    usable = bool(len(array)) and nonfinite == 0
    stats = {"count": len(values), "available_count": len(array), "missing_count": missing,
             "nonfinite_count": nonfinite, "mean": float(array.mean()) if usable else UNAVAILABLE,
             "std_ddof1": float(array.std(ddof=1)) if usable and len(array) > 1 else UNAVAILABLE,
             "p50": float(np.percentile(array, 50)) if usable else UNAVAILABLE,
             "p95": float(np.percentile(array, 95)) if usable else UNAVAILABLE,
             "p99": float(np.percentile(array, 99)) if usable else UNAVAILABLE,
             "min": float(array.min()) if usable else UNAVAILABLE,
             "max": float(array.max()) if usable else UNAVAILABLE,
             "status": "AVAILABLE" if usable else "UNAVAILABLE_NONFINITE" if nonfinite else UNAVAILABLE}
    if absolute_p95:
        stats["p95_absolute"] = float(np.percentile(np.abs(array), 95)) if usable else UNAVAILABLE
    return {prefix + "_" + key: value for key, value in stats.items()}


def gating_nis_rows(log, *, identity, window, source, baseline3d=None):
    """Reduce actual scalar/B3 diagnostics, retaining all attempts/dispositions.

    ``baseline3d`` has the candidate binary's BASELINE3D_DIAGNOSTICS schema.
    B3 ``invalid`` includes ``missing``; these overlapping counters are not
    added together. Scalar logs cannot establish missing/invalid source counts.
    A missing B3 diagnostic never silently falls back to the scalar trace.
    """
    sequence = identity["sequence_id"]
    b3 = identity["variant"] == "B3"
    frame = baseline3d if b3 else log
    time_column = "time" if b3 else "gnss_time"
    regions = REGIONS if sequence == "BY2O" else ("full", "outside")
    role = _checked_role(identity, identity.get("data_mode", "real_raw"), required=frame is not None)
    common = {**identity, **role, "source": source,
              "measurement_model": "baseline3d" if b3 else "scalar_yaw"}
    if frame is None:
        return [{**common, "segment_id": region, "status": "UNAVAILABLE_DIAGNOSTICS",
                 **{key: UNAVAILABLE for key in ("epochs", "attempted", "accepted", "rejected",
                                                 "not_attempted", "invalid", "missing", "accounting_consistent")}}
                for region in regions]
    required = (("time", "present", "valid", "attempt", "accepted", "rejected", "reason",
                 "nis_actual_innovation", "along_axis_residual_m", "length_mismatch_m") if b3 else
                ("gnss_time", "yaw_update", "yaw_mode"))
    if any(column not in frame for column in required):
        raise ValueError("Required measurement diagnostic columns missing")
    if b3 and "model" in frame and not (frame["model"] == "baseline3d").all():
        raise ValueError("B3 diagnostic measurement-model identity mismatch")
    times = pd.to_numeric(frame[time_column], errors="raise").to_numpy(float)
    if not np.isfinite(times).all():
        raise ValueError("Nonfinite diagnostic timestamps")
    result = []
    for region, mask in region_masks(times, sequence, window).items():
        part = frame.loc[mask]
        if b3:
            attempted, accepted, rejected, present, valid = (
                _flags(part, column) for column in ("attempt", "accepted", "rejected", "present", "valid"))
            consistent = (np.array_equal(attempted, accepted | rejected)
                          and not np.any(accepted & rejected) and np.array_equal(attempted, valid)
                          and not np.any(valid & ~present))
            invalid, missing = int((~valid).sum()), int((~present).sum())
        else:
            attempted = _flags(part, "yaw_update")
            modes = part["yaw_mode"].astype(str)
            accepted = modes.isin(("NORMAL", "DOWNWEIGHT")).to_numpy()
            rejected = (modes == "REJECT").to_numpy()
            consistent = np.array_equal(attempted, accepted | rejected)
            invalid = missing = UNAVAILABLE
        row = {**common, "segment_id": region, "epochs": len(part),
               "attempted": int(attempted.sum()), "accepted": int(accepted.sum()),
               "rejected": int(rejected.sum()), "not_attempted": int((~attempted).sum()),
               "invalid": invalid, "missing": missing, "accounting_consistent": bool(consistent),
               "status": "AVAILABLE" if consistent else "UNAVAILABLE_ACCOUNTING_MISMATCH",
               "invalid_count_definition": "Includes missing sidecar epochs" if b3 else "UNAVAILABLE_FROM_SCALAR_TRACE"}
        if b3:
            row.update(_diagnostic_statistics(part["nis_actual_innovation"].tolist(), "nis"))
            for column in ("along_axis_residual_m", "length_mismatch_m"):
                row.update(_diagnostic_statistics(part[column].tolist(), column, absolute_p95=True))
            row["reason_counts"] = {str(key): int(value) for key, value in part["reason"].value_counts(dropna=False).items()}
        else:
            row.update(nis_status="NOT_APPLICABLE_SCALAR_TRACE", along_axis_residual_m_status="NOT_APPLICABLE",
                       length_mismatch_m_status="NOT_APPLICABLE")
        result.append(row)
    return result


def attitude_rows(rows):
    """Every input row remains visible, including literature and unavailable RP."""
    fields = ("sequence_id", "case_id", "configuration_id", "method_id", "variant", "role",
              "evaluator_contract", "evaluation_status", "failure_classification", "data_mode",
              "synthetic_data_used", "semisynthetic_data_used", "roll_rmse_deg", "pitch_rmse_deg",
              "delta_vs_frozen_roll_rmse_deg", "delta_vs_frozen_pitch_rmse_deg",
              "delta_vs_t5a_r5_roll_rmse_deg", "delta_vs_t5a_r5_pitch_rmse_deg",
              "frozen_source_table", "frozen_source_line", "source_nav_sha256", "error_series_source")
    result = []
    for row in rows:
        selected = {field: row.get(field, UNAVAILABLE) for field in fields}
        if row.get("evaluation_status") not in AVAILABLE:
            for field in fields:
                if "roll_rmse_deg" in field or "pitch_rmse_deg" in field:
                    selected[field] = UNAVAILABLE
        selected["baseline3d_observability"] = ("Two rotation directions; rotation about the baseline axis unobservable"
                                                 if row.get("variant") == "B3" else "NOT_APPLICABLE")
        result.append(selected)
    return result


@lru_cache(maxsize=None)
def _is_metric(field):
    # Canonical AXIS/NORM/WINDOW/SIGMA schema plus native counters and
    # supplemental frozen consistency columns. Identity/config fields excluded.
    from ..canonical541 import offline_eval_aggregate as canonical
    axes=(("east","m"),("north","m"),("up","m"),("down","m"),
          ("roll","deg"),("pitch","deg"),("yaw","deg"),
          ("velocity_east","mps"),("velocity_north","mps"),("velocity_up","mps"))
    norms=(("horizontal","m"),("position_3d","m"),("attitude_norm","deg"),
           ("horizontal_velocity","mps"),("velocity_3d","mps"))
    fields={f"{axis}_{stat}_{unit}" for axis,unit in axes for stat in (*canonical.AXIS_STAT_NAMES,*canonical.SIGMA_STAT_NAMES)}
    fields.update(f"{axis}_{stat}_{unit}" for axis,unit in norms for stat in canonical.NORM_STAT_NAMES)
    fields.update(f"{window}_{axis}_{stat}_{unit}" for window in ("pre","during","post")
                  for axis,unit in (("horizontal","m"),("position_3d","m"),("yaw","deg")) for stat in canonical.WINDOW_STAT_NAMES)
    fields.update(canonical.MODULE_SCALARS)
    fields.update(NUMERIC_FIELDS)
    return field in fields or (field not in {"v3_baseline_median_m","sequence_window_start_s","sequence_window_end_s","degradation_window_start_s","degradation_window_end_s"}
            and not field.startswith(("delta_","v3_")) and field.endswith(("_m","_deg","_mps","_rad","_count","_ratio","_sec","_median","_seconds")))


def subset_absolute_summary(rows, *, case_ids):
    """All five groups, absolute metrics and paired deltas, including failures."""
    from collections import Counter
    result = []
    for variant in (FROZEN, *SUBSET_VARIANTS):
        selected = [row for row in rows if row.get("variant") == variant]
        if {row.get("case_id") for row in selected} != set(case_ids) or len(selected) != len(case_ids):
            raise ValueError("Subset summary requires exactly one row per registered case")
        failures = Counter(str(row.get("failure_classification", "UNAVAILABLE")) for row in selected
                           if row.get("evaluation_status") not in AVAILABLE)
        for metric in ("yaw_rmse_deg", "h_rmse_m"):
            values = [float(row[metric]) for row in selected if row.get("evaluation_status") in AVAILABLE and _number(row.get(metric)) is not None]
            deltas = [float(row["delta_vs_frozen_" + metric]) for row in selected if _number(row.get("delta_vs_frozen_" + metric)) is not None]
            result.append({"variant": variant, "metric": metric, "case_count": len(case_ids),
                           "available_count": len(values), "unavailable_count": len(case_ids)-len(values),
                           "mean": float(np.mean(values)) if values else UNAVAILABLE,
                           "median": float(np.median(values)) if values else UNAVAILABLE,
                           "worst_5pct_threshold_p95": float(np.percentile(values,95)) if values else UNAVAILABLE,
                           "paired_count": len(deltas), "paired_delta_mean": float(np.mean(deltas)) if deltas else UNAVAILABLE,
                           "paired_delta_median": float(np.median(deltas)) if deltas else UNAVAILABLE,
                           "paired_delta_p95": float(np.percentile(deltas,95)) if deltas else UNAVAILABLE,
                           "failure_count": sum(failures.values()), "failure_classifications": dict(sorted(failures.items())),
                           "data_mode": "real_clean_and_semisynthetic_separate_cases", "synthetic_data_used": False,
                           "semisynthetic_data_used": any(row.get("semisynthetic_data_used") is True for row in selected),
                           "quantile_method": "LINEAR", "directional_decision": "NOT_DEFINED"})
    return result


def lc01_crosscheck(pilot):
    rows=[]
    for sequence in SEQUENCES:
        candidate=next(row for row in pilot if row["sequence_id"]==sequence and row["configuration_id"]=="F02" and row["variant"]=="B3")
        for variant in ("LC01-S","LC01"):
            reference=next(row for row in pilot if row["sequence_id"]==sequence and row["variant"]==variant)
            row={"sequence_id":sequence,"candidate":"F02_prime_B3","reference":variant,
                 "evaluator_contract":candidate["evaluator_contract"],"candidate_status":candidate["evaluation_status"],
                 "reference_status":reference["evaluation_status"], "reference_start_convention":reference["start_convention"],
                 "interpretation":"Descriptive implementation crosscheck, no correctness criterion"}
            for metric in NUMERIC_FIELDS:
                row["B3_"+metric]=candidate.get(metric,UNAVAILABLE)
                row["reference_"+metric]=reference.get(metric,UNAVAILABLE)
            row.update(_deltas(candidate,reference,"delta_"));rows.append(row)
    return rows


def nis_consistency(frame, *, identity, window, attempts=None):
    """Descriptive actual-covariance NIS, never fallback normalized residuals."""
    from scipy.stats import chi2
    b3=identity["variant"]=="B3"; dof=3 if b3 else 1
    column="nis_actual_innovation" if b3 else "nis"
    common={**identity,"dof":dof,"coverage_definition":"Central 95 percent chi-square interval; no new gate",
            "selection":"Before B3 NIS gate and SA: (dz-Hdx)^T (HPH^T+R_QA)^-1 (dz-Hdx)" if b3 else "After scheme-C, before SA scaling: dz^T (HPH^T+R_schemeC)^-1 dz, used_innovation_covariance=1 and dof=1"}
    if frame is None:
        return [{**common,"segment_id":"full","status":"UNAVAILABLE_DIAGNOSTICS","count":0,
                 "nis_mean":UNAVAILABLE,"nis_coverage_95":UNAVAILABLE,"nis_selection_coverage":UNAVAILABLE}],[]
    source=frame.copy()
    if not b3:
        source=source.loc[(source["source_id"].astype(str).isin(("2","A1","dual_antenna_yaw","DUAL_ANTENNA_YAW"))) &
                          (pd.to_numeric(source["used_innovation_covariance"])==1) & (pd.to_numeric(source["dof"])==1)]
    else:
        source=source.loc[pd.to_numeric(source["attempt"])==1]
    numbers=pd.to_numeric(source[column],errors="coerce").to_numpy(float)
    times=pd.to_numeric(source["time"],errors="raise").to_numpy(float)
    if not np.isfinite(times).all():raise ValueError("Nonfinite NIS timestamp")
    low,high=map(float,chi2.ppf([.025,.975],dof)); result=[]; series=[]
    for region,mask in region_masks(times,identity["sequence_id"],window).items():
        vals=numbers[mask]; finite=np.isfinite(vals) & (vals>=0); available=vals[finite]
        denom=(attempts or {}).get(region)
        result.append({**common,"segment_id":region,"count":len(available),"missing_nonfinite_or_negative_count":int((~finite).sum()),"negative_count":int((vals<0).sum()),
                       "nis_mean":float(available.mean()) if len(available) else UNAVAILABLE,
                       "nis_p95":float(np.percentile(available,95)) if len(available) else UNAVAILABLE,
                       "nis_coverage_95":float(np.mean((available>=low)&(available<=high))) if len(available) else UNAVAILABLE,
                       "nis_selection_coverage":len(available)/denom if isinstance(denom,(int,float)) and denom>0 else UNAVAILABLE,
                       "chi2_lower":low,"chi2_upper":high,"status":"AVAILABLE" if len(available) else "UNAVAILABLE"})
    for time,value in zip(times,numbers):
        if window[0]<=time<=window[1]:series.append({**identity,"time":float(time),"nis":float(value) if math.isfinite(value) and value>=0 else UNAVAILABLE,"dof":dof})
    return result,series
