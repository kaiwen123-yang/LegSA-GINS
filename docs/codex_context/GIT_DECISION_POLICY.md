# GIT_DECISION_POLICY.md

## Authority

- Worker must not run Git write operations.
- Reviewer only recommends.
- Supervisor can perform Git write operations only after explicit user confirmation.
- User is the final decision maker.

## Current PR/Tag Boundary

- PR #48 is already merged.
- PR #21 remains open/unmerged and must not be touched.
- PR #49 remains open/unmerged and must not be merged or tagged during N9A_R0/N9A_R3.
- No N9A tag until N9A final review passes and the user explicitly approves.
- No N9B branch/run/PR until N9A final review passes and the user explicitly approves.

## Usually Committable Windows Audit Files

- `AGENTS.md`
- `PLANS.md`
- `.codex/agents/*`
- non-local `docs/codex_context/*.md`
- `.gitignore`
- `scripts/run_wsl_legsa.ps1`
- small text audit reports and result lists

## Not Committable By Default

- `docs/codex_context/DATA_PATHS.local.md`
- logs and temporary WSL bridge scripts
- raw data and `by2.txt`
- runtime NAV / STD / EVAL_NAV / RUN_MANIFEST
- `FGO_FEEDBACK_OBSERVATIONS.csv`
- `FGO_SMOOTHED_NAV.csv`
- `FGO_FACTOR_TABLE.csv`
- summary/error series
- generated PNG/PDF/SVG/JPG/JPEG figures
- zip/7z/rar/bag/db3/ubx/raw files

## WSL Algorithm Repository

`<WSL_ALGO_REPO>` is read-only by default. Only discuss WSL commit/push/PR after the user explicitly allows source modifications.
