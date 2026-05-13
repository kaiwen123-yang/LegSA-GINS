"""N7B5 horizontal Go2 velocity diagnostic activation wrapper.

中文说明：本模块只暴露 N7B5 horizontal/full-frame diagnostic variants；
所有 variant 都沿用 diagnostic-only C++ prior path，不启用 formal Go2 prior。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .go2_frame_sensitivity_runner import VARIANT_IDS, run_n7b5_frame_sensitivity_variants


HORIZONTAL_DIAGNOSTIC_VARIANTS = VARIANT_IDS


def run_horizontal_diagnostic_activation_variants(
    *,
    clean_root: str | Path,
    output_dir: str | Path,
    exe: str | Path,
    raw_doppler_factor_path: str | Path | None,
    prior_paths: dict[str, Path],
    allow_run: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return run_n7b5_frame_sensitivity_variants(
        clean_root=clean_root,
        output_dir=output_dir,
        exe=exe,
        raw_doppler_factor_path=raw_doppler_factor_path,
        prior_paths=prior_paths,
        allow_run=allow_run,
    )
