# N4R yaw evaluator decision

Runtime N4R reports provide:

- actual final_v23 official summary;
- direct recompute summary from actual final_v23 NAV;
- best yaw transform candidate;
- replay summary after applying the official evaluator transform;
- recommended_next_stage;
- blocking_issues.

Decision rules:

- If actual final_v23 direct yaw is far from official yaw and a transform
  reproduces official summary/error_series, recommend evaluator convention
  repair before runtime yaw config work.
- If direct official parity already passes but replay remains near 90 deg yaw,
  recommend runtime yaw update/config audit.
- If official artifacts or error_series schema are incomplete, preserve
  evidence_missing and repair recovery/schema first.
- If replay becomes close under the official transform, apply the evaluator
  convention patch before the next baseline/replay stage.

Claim boundary:

- N4R is evaluator-parity diagnostic only.
- N4R metrics are not proposed solver performance.
- Official artifacts are not solver input.
- Trace remains evaluation-only.
- Yaw transform candidates are evaluator diagnostics, not solver tuning.

## N4R2 update

N4R located an official artifact group through role alias
`EXTERNAL_KFGINS_ROOT:10`, but that group is single_antenna-like rather than
dual_final_v23:

- official horizontal_rmse_m: 38.94662393087691
- official up_rmse_m: 1.1006162558688044
- official yaw_rmse_deg: 41.37480109587043
- official roll_rmse_deg: 2.209442169818736
- official pitch_rmse_deg: 3.5118113915966434
- direct recompute yaw_rmse_deg: 106.83508570438205
- best candidate: `est=identity|ref=heading_to_math_yaw`
- best candidate yaw_rmse_deg: 41.37875163371464
- official error_series yaw parity: mismatch
- replay yaw under candidate: about 2.06058 deg

The candidate profile improves N4H2 replay yaw into a near-boundary diagnostic
range, but the strict yaw gate remains false when yaw_rmse_deg is greater than
2.0. This is not a formal pass and does not relax the yaw gate.

N4R2 therefore adds a controlled yaw evaluator convention policy and a directed
dual_final_v23 artifact verification step. No formal evaluator profile patch is
allowed until dual_final_v23 parity confirms the profile. If dual recovery is
missing or if dual artifacts do not confirm the candidate, the next stage is
determined by `N4R2_DECISION_REPORT` rather than by the single_antenna-like
group alone.
