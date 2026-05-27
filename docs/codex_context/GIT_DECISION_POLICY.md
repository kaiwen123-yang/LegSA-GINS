# GIT_DECISION_POLICY.md

## Authority

- Worker must not run Git write operations.
- Reviewer only recommends.
- Supervisor can perform Git write operations only after explicit user confirmation.
- User is the final decision maker.

## Current PR/Tag Boundary

- PR #21 remains open/unmerged and must not be touched.
- PR #52 remains open/unmerged unless the human explicitly approves merge/tag/closure.
- N9G0A resolved the earlier PR #52 push boundary; PR #52 head is synced to `9ceba928`.
- PR #52 head sync is not merge, tag, closure, or paper-claim authorization.
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

## N9F7A/N9G0 Git Boundary

N9F7A/N9G0 recorded the historical publish block and produced the manual design review package. N9G0A later resolved the Git boundary and synced PR #52 head to `9ceba928`.

## N9G1A Git Boundary

N9G1A worker must not stage, commit, push, merge, tag, checkout, reset, or pull. It may run read-only git status/diff validation. It must not stage runtime roots, Obsidian roots, `DATA_PATHS.local.md`, generated outputs, raw data, figures, or archives.
