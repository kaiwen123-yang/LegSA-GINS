# N4H4E Source-Backed Port Visual Validation

N4H4E is engineering visual validation for the source-backed port-core
backbone. It checks whether the N4H4R3C numerical parity result is visually
reasonable before any next-stage factor work.

This stage only plots:

- source-backed port-core output;
- dual_final_v23 reference baseline output;
- evaluation-only reference/trace trajectory.

It does not plot pure INS or single antenna comparisons.

Boundary:

- visual validation is not a paper performance claim;
- visual validation is not a proposed factor result;
- ported final_v23/KF-GINS backbone is not proposed novelty;
- final_v23 output is not proposed solver input;
- trace/reference remains evaluation-only;
- generated figures are runtime-only and are not committed;
- no raw Doppler, Go2 prior, LSIM/OIM, source-aware weighting, or FGO is
  implemented in this stage.

The Windows figure output directory is referred to by the role alias
`VISUAL_OUTPUT_DIR`; tracked docs and config must not contain local absolute
paths.
