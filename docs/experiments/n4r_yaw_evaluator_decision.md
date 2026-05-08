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
