# PAPER4A Git Safety Start

Stage: `PAPER4A_WRITE_READY_EVIDENCE_PACKAGE_AND_CONTEXT_SYNC`

Timestamp: `2026-06-07T01:55:43+08:00`

Repository root: `<WSL_REPO_ROOT>`

## Required Initial Commands

### `git status --short`

```text
 M AGENTS.md
 M CLAIM_BOUNDARY.md
 M PHASE_LOG.md
 M PLANS.md
 M README.md
 M docs/codex_context/PATH_POLICY.md
 M docs/codex_context/PROJECT_CONTEXT.md
 M docs/codex_context/WORKFLOW_POLICY.md
 M docs/codex_context/claim_boundary.md
 M docs/codex_context/current_state.md
 M docs/codex_context/data_source_roles.md
?? .legsa_runtime/
?? docs/codex_context/ALGORITHM_IDENTITY_AND_CLAIM_BOUNDARY.md
?? docs/codex_context/DATASET_ROLE_AND_EVIDENCE_BOUNDARY.md
?? docs/codex_context/OBSIDIAN_AND_GDRIVE_OUTPUT_POLICY.md
?? docs/codex_context/PAPER0D_CURRENT_CONTEXT.md
?? docs/codex_context/RUNNER_PROVIDER_LINEAGE.md
?? qa_fallback_review/
```

### `git rev-parse --abbrev-ref HEAD`

```text
stage/QA0-to-QA4-quality-aware-fallback
```

### `git rev-parse HEAD`

```text
15f5465e558ef3617d070d3cc3562b54642ba178
```

## Safety Interpretation

- The repository was already dirty before PAPER4A outputs were created.
- Existing dirty files must be treated as pre-stage user or prior-stage state unless a later PAPER4A diff explicitly adds a PAPER4A section.
- PAPER4A staging must use explicit paths only.
- `_runtime/`, raw data, RINEX, UBX, RTCM, external code snapshots, large binary figures, and unrelated dirty files must not be staged.
- No push is authorized for this stage.
