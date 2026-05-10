# N6B LSIM Metadata Policy

LSIM is source metadata only. It does not read residuals, trace files,
final_v23 outputs, evaluation metrics, or paper-facing summaries.

Rules:
- valid source, finite std, and aligned time: scale `1.0`;
- suspicious metadata: mild R inflation;
- invalid metadata: reject or source-capped large scale;
- no blanket receiver-position cap behavior.

LSIM and OIM combine as:

`combined = max(lsim_R_scale, oim_R_scale)`

Then:

`combined = min(combined, source_cap, global_cap)`

`combined >= 1.0`

So N6B remains R-inflation-only and cannot shrink baseline R.
