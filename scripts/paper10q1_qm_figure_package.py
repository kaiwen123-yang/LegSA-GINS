#!/usr/bin/env python3
"""Figure specification helpers for PAPER10Q1 QM evidence review."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FigureSpec:
    figure_id: str
    bucket: str
    claim_level: str
    paper_candidate: str
    degradation_types: tuple[str, ...]
    notes: str


FOCUSED_QM_TYPES = (
    "D23",
    "D24",
    "D25",
    "D26",
    "D27",
    "D28",
    "D29",
    "D38",
    "D45",
    "D49",
    "D58",
    "D59",
    "D60",
)


FIGURE_SPECS = (
    FigureSpec(
        "qm_normal_vs_degraded_action_overview",
        "main_text_candidate",
        "protective_mechanism_with_caveats",
        "yes",
        ("CLEAN", *FOCUSED_QM_TYPES),
        "Summary-derived action counts for clean versus focused degraded cases.",
    ),
    FigureSpec(
        "qm_state_timeline_representative_D27",
        "main_text_candidate",
        "representative_mechanism_trace",
        "yes",
        ("D27",),
        "Representative trace for bad-position optimistic-std mismatch.",
    ),
    FigureSpec(
        "qm_state_timeline_representative_D38",
        "main_text_candidate",
        "representative_mechanism_trace",
        "yes",
        ("D38",),
        "Representative trace for bad-yaw optimistic-std mismatch.",
    ),
    FigureSpec(
        "qm_state_timeline_representative_D58",
        "main_text_candidate",
        "representative_recovery_trace",
        "yes",
        ("D58",),
        "Representative trace for outage/yaw-spike recovery case.",
    ),
    FigureSpec(
        "qm_state_timeline_representative_D60",
        "main_text_candidate",
        "representative_recovery_trace",
        "yes",
        ("D60",),
        "Representative trace for multisource bad-optimistic recovery case.",
    ),
    FigureSpec(
        "source_action_stack_A1_GNSS_RawDoppler_Go2",
        "main_text_candidate",
        "source_action_interpretability",
        "yes",
        FOCUSED_QM_TYPES,
        "Stacked accepted/downweighted/rejected actions by source family.",
    ),
    FigureSpec(
        "full_QM_vs_no_QM_delta_by_degradation_family",
        "main_text_candidate",
        "metric_tradeoff_caveat",
        "yes",
        FOCUSED_QM_TYPES,
        "Family-level RMSE deltas, positive means full-QM lower RMSE.",
    ),
    FigureSpec(
        "source_aware_vs_no_source_aware_delta_by_family",
        "main_text_candidate",
        "bounded_source_aware_contribution",
        "yes",
        FOCUSED_QM_TYPES,
        "Family-level RMSE deltas for source-aware ablation.",
    ),
    FigureSpec(
        "bad_A1_accept_downweight_reject_bar",
        "main_text_candidate",
        "bad_a1_action_audit_not_legacy_counter",
        "yes",
        FOCUSED_QM_TYPES,
        "Uses accepted/downweighted/rejected audit fields, not legacy consumed count.",
    ),
    FigureSpec(
        "recovery_duration_distribution",
        "main_text_candidate",
        "recovery_mechanism_summary",
        "yes",
        FOCUSED_QM_TYPES,
        "Distribution of recovery counts from frozen traces.",
    ),
    FigureSpec(
        "D23_D29_std_status_mismatch_qm_heatmap",
        "appendix_candidate",
        "family_specific_appendix",
        "appendix",
        ("D23", "D24", "D25", "D26", "D27", "D28", "D29"),
        "STD/status mismatch family QM action heatmap.",
    ),
    FigureSpec(
        "D30_D41_yaw_family_qm_action_heatmap",
        "appendix_candidate",
        "family_specific_appendix",
        "appendix",
        tuple(f"D{i}" for i in range(30, 42)),
        "Yaw-family QM action heatmap.",
    ),
    FigureSpec(
        "D42_D50_velocity_raw_doppler_qm_action_heatmap",
        "appendix_candidate",
        "family_specific_appendix",
        "appendix",
        tuple(f"D{i}" for i in range(42, 51)),
        "Velocity and Raw Doppler family action heatmap.",
    ),
    FigureSpec(
        "D58_D60_mixed_recovery_panel",
        "appendix_candidate",
        "mixed_recovery_appendix",
        "appendix",
        ("D58", "D59", "D60"),
        "Mixed/recovery family summary panel.",
    ),
    FigureSpec(
        "qm_help_hurt_tradeoff_count_by_family",
        "appendix_candidate",
        "metric_tradeoff_appendix",
        "appendix",
        FOCUSED_QM_TYPES,
        "Counts where full-QM helps, hurts, or trades off by family.",
    ),
    FigureSpec(
        "source_aware_R_scale_distribution_by_source",
        "appendix_candidate",
        "source_aware_diagnostic_appendix",
        "appendix",
        FOCUSED_QM_TYPES,
        "Distribution of source-aware R scales from representative traces.",
    ),
    FigureSpec(
        "qm_clean_transparency_panel",
        "appendix_candidate",
        "normal_transparency_caveat",
        "appendix",
        ("CLEAN",),
        "Clean-condition QM action and metric cost panel.",
    ),
    FigureSpec(
        "no_QM_better_case_audit_panel",
        "appendix_candidate",
        "tradeoff_appendix",
        "appendix",
        FOCUSED_QM_TYPES,
        "Cases where no-QM improves metrics over full-QM.",
    ),
    FigureSpec(
        "legacy_bad_a1_consumed_deprecated_explanation",
        "diagnostic_only",
        "diagnostic_only",
        "no",
        FOCUSED_QM_TYPES,
        "Deprecated legacy field explanation; not a claim figure.",
    ),
    FigureSpec(
        "cases_where_QM_hurts",
        "diagnostic_only",
        "diagnostic_only",
        "no",
        FOCUSED_QM_TYPES,
        "Diagnostic panel for cases where full-QM is worse.",
    ),
    FigureSpec(
        "cases_where_QM_is_neutral",
        "diagnostic_only",
        "diagnostic_only",
        "no",
        FOCUSED_QM_TYPES,
        "Diagnostic panel for near-zero deltas.",
    ),
)


def figure_specs() -> tuple[FigureSpec, ...]:
    return FIGURE_SPECS


def bucket_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for spec in FIGURE_SPECS:
        counts[spec.bucket] = counts.get(spec.bucket, 0) + 1
    return counts
