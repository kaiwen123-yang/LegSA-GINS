"""Diagnostic-only status-baseline provider."""

from __future__ import annotations

from pathlib import Path

from legsa_gins.external_dual.status_dual_yaw_provider import build_status_dual_yaw_provider, summarize_status_provider


def diagnostic_status_summary(gnss1_status: str | Path, gnss2_status: str | Path) -> dict[str, str]:
    epochs = build_status_dual_yaw_provider(Path(gnss1_status), Path(gnss2_status))
    summary = summarize_status_provider(epochs)
    summary["status_fallback_ready"] = "true" if epochs else "false"
    summary["counts_as_full_backend"] = "false"
    return summary
