# N4H4E Source-Backed Port Visual Validation Prompt

Goal:
Generate runtime-only visual validation figures for source-backed port-core
backbone parity using port, dual_final_v23, and evaluation-reference
trajectories.

Do not plot pure INS or single antenna comparisons.

Required reports:

- `VISUAL_INPUT_MANIFEST.json`
- `FIGURE_MANIFEST.json`
- `VISUAL_SANITY_REPORT.json`
- `VISUAL_VALIDATION_REPORT.json`
- `visual_case_review.md`

Hard boundaries:

- no raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting, FGO, or Neural
  Gate implementation;
- no output-only correction;
- no tuning;
- no epoch deletion;
- no paper performance claim;
- no outperform final_v23 claim;
- no generated figures committed;
- no local absolute paths in tracked docs/config.
