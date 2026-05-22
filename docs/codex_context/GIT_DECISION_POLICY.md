# GIT_DECISION_POLICY.md

## Authority

- Worker must not run Git write operations.
- Reviewer only recommends.
- Supervisor can perform Git write operations only after explicit user confirmation.
- User is the final decision maker.

## Current PR/Tag Boundary

- PR #21 remains open/unmerged and must not be touched.
- PR #52 remains open/unmerged unless the human explicitly approves merge/tag/closure.
- No N9B2 tag until staged reviews pass and the human explicitly approves.
- No N9B2 execution branch/run/PR action may be treated as authorized by N9B2B1.

## Usually Committable Windows Audit Files

- `AGENTS.md`
- `PLANS.md`
- non-local `docs/codex_context/*.md`
- `.gitignore`
- `scripts/run_wsl_legsa.ps1`
- small text audit reports and result lists when explicitly approved

## Not Committable By Default

- `docs/codex_context/DATA_PATHS.local.md`
- logs and temporary WSL bridge scripts.
- raw data and `by2.txt`.
- runtime NAV / STD / EVAL_NAV / RUN_MANIFEST.
- `FGO_FEEDBACK_OBSERVATIONS.csv`.
- `FGO_SMOOTHED_NAV.csv`.
- `FGO_FACTOR_TABLE.csv`.
- summary/error series.
- generated PNG/PDF/SVG/JPG/JPEG figures.
- generated degradation CSV / summary / case review runtime files.
- zip/7z/rar/bag/db3/ubx/raw files.

## WSL Algorithm Repository

`<WSL_ALGO_REPO>` is read-only by default. Only discuss WSL commit/push/PR after the user explicitly allows source modifications.

## N9B2B1 Git Boundary

N9B2B1 must not stage, commit, push, merge, tag, checkout, reset, or pull. It may run read-only git status/diff validation.
