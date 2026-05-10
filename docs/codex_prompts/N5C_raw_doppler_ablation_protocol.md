# N5C Raw Doppler Ablation Protocol Prompt

Role aliases used by this tracked prompt:

- `CLEAN_REPLAY_ROOT`: clean source-backed replay input root.
- `N5B_REPORT_ROOT`: runtime-only N5B raw Doppler provider output root.
- `DUAL_REFERENCE_ROOT`: runtime-only dual/final_v23 evaluation reference root.
- `N5C_REPORT_ROOT`: runtime-only N5C report output root.
- `N5C_FIGURE_ROOT`: runtime-only N5C figure output root.

Task:

Merge PR #28, tag N5B, then start `stage/N5C-raw-doppler-ablation-protocol`.

N5C must build a strict raw Doppler ablation protocol using the already activated N5B RTKLIB-backed raw Doppler velocity factor. It must run the baseline source-backed port replay, baseline plus raw Doppler replay, velocity-isolation diagnostic variants, and R-scale screen. It must report factor consistency, residual/update-count evidence, time alignment, velocity-source comparison, ablation deltas, and a next-stage decision.

Boundaries:

- NAV-PVT velocity is not raw Doppler.
- .gnss vn/ve/vd is not raw Doppler.
- RTKLIB position solution must not be used as LegSA solver input.
- velocity-isolation variants are diagnostic-only.
- R_scale screen is diagnostic-only.
- paper performance claim: false.
- no outperform final_v23 claim: true.
- No LSIM/OIM, Go2 prior, source-aware weighting, FGO, output-only correction, trace tuning, or epoch deletion.
