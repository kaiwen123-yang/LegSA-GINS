#!/usr/bin/env python3
"""Audit that RTKLIB position solutions are not substituted as raw Doppler input."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    # 中文说明：RTKLIB position solution 只能用于诊断，不能替代 raw Doppler velocity factor。
    docs = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in [
            "docs/experiments/n5b_rtklib_doppler_velocity_provider.md",
            "docs/experiments/n5b_raw_doppler_factor_activation_trial.md",
            "docs/codex_prompts/N5B_rtklib_doppler_provider_activation.md",
        ]
    )
    if "position solution" not in docs or "cannot be LegSA solver input" not in docs:
        raise AssertionError("docs must state RTKLIB position solution cannot be solver input")
    provider = (ROOT / "src/legsa_gins/raw_gnss/rtklib_doppler_velocity_provider.py").read_text(encoding="utf-8")
    builder = (ROOT / "src/legsa_gins/raw_gnss/raw_doppler_velocity_factor_builder.py").read_text(encoding="utf-8")
    if "rtklib_position_solution_used_as_solver_input\": False" not in provider + builder:
        raise AssertionError("provider/builder must explicitly reject RTKLIB position solution substitution")
    if "VELOCITY_FACTOR_FIELDS" not in builder:
        raise AssertionError("factor CSV must be velocity-factor schema only")
    if "final_v23_output_solver_input" not in provider + builder or "trace_solver_input" not in builder:
        raise AssertionError("final_v23/trace solver input flags missing")
    print("No RTKLIB position solution substitution audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
