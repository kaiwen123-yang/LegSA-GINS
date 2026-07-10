# AGENTS.md - LegSA-GINS Clean Rebuild Rules

## CLEAN REBUILD HARD RULES

Every agent must read `docs/paper_rebuild/ACTIVE_CONTEXT.md` before inspecting or changing the project.

For active work, agents must not read old `reports/stages`, old `experiments`, legacy-freeze performance results, or old PAPER/N/QA stage metrics. Historical files may be opened only for an explicitly assigned freeze/provenance task and can never become active performance evidence.

Only paths in the `CLEAN_ACTIVE_ALLOWLIST` below may support active evidence. All performance results must originate under `<CLEAN_ROOT>` from hash-locked raw data. Old stage names are allowed only in `docs/legacy/202607/` or frozen external history.

The active runner namespace is `src/legsa_gins/paper_rebuild/`, invoked through `scripts/paper_rebuild/`. Legacy runners may remain in Git history/source but the clean rebuild must not call them.

`src/legsa_gins/reporting/by2_algorithm_runner.py` is explicitly a legacy runner. Do not delete it, rewrite it into the clean runner, or invoke it from clean-rebuild code.

Synthetic or semi-synthetic results must never be written into a real-data result table. Every manifest must state `data_mode`, `synthetic_data_used`, and `semisynthetic_data_used`.

## CLEAN_ACTIVE_ALLOWLIST

Tracked active material:

- `docs/paper_rebuild/`
- `configs/paper_rebuild/`
- `scripts/paper_rebuild/`
- `tests/paper_rebuild/`
- `src/legsa_gins/paper_rebuild/`
- maintained shared source explicitly imported by the clean runner and recorded by commit SHA

Active external material:

- immutable source files under `<RAW_ROOT>`;
- raw hash locks under `<CLEAN_ROOT>/01_RAW_HASH_LOCK/`;
- fresh providers under `<CLEAN_ROOT>/04_PROVIDER_FREEZE/`;
- fresh clean runtime/evaluation artifacts under `<CLEAN_ROOT>` whose manifests and dependency audits pass.

`<LEGACY_FREEZE_ROOT>` is allowed only for Git recovery, selected specification provenance, selected lessons, claim-boundary history, and unique-file human review. Its performance content is denied.

## Project Scope

The clean paper method is `LegSA_Paper_V1`:

- source-backed EKF;
- GNSS2-GNSS1 lateral short-baseline body-yaw model with the fixed physical transform and wrap-safe residual;
- Raw Doppler auxiliary velocity;
- source-aware measurement weighting;
- Go2 roll/pitch weak prior;
- Go2 horizontal-velocity weak prior.

Out of scope: selected FGO feedback, active/complete nine-factor FGO, multi-state QM as the main innovation, QA fallback, complete contact/FK factors, Go2 truth, and final_v23/LegSA output input.

## Data And Claim Boundaries

- Trace is evaluation-only. Never use it for solver input, sign/offset selection, provider selection, tuning, feedback, or correction.
- GNSS raw/status and Raw Doppler are observations, not algorithm estimates or truth.
- Receiver IMU is not Go2 body IMU.
- Go2 position, velocity, yaw, contact, foot, mode, and gait data are weak-prior or diagnostic sources only, never truth.
- Baseline heading is not body yaw. Use the fixed physical antenna order/transform; never select a transform by RMSE.
- No per-case tuning, output substitution, direct NAV overwrite, output-only correction, or metric-driven epoch deletion.
- No old aggregate, reconstructed summary, row result, provider, figure, or runtime output may support a new claim.
- Source-aware and Go2 mechanisms may be described only as bounded/protective/auxiliary until fresh clean multi-dataset evidence supports more.
- There is no active complete nine-factor FGO claim.

## Required Runtime Provenance

Every clean run must record at least:

- `data_mode`;
- raw source hashes and provider hashes;
- `synthetic_data_used` and `semisynthetic_data_used`;
- `trace_used_online`;
- `receiver_imu_as_body_imu`;
- `final_v23_output_solver_input`;
- `LegSA_output_solver_input`;
- `per_case_tuning`;
- `output_only_correction`;
- `epoch_deleted_for_metric`;
- `old_runtime_input_count`;
- `code_commit` and `config_hash`.

Forbidden booleans must be false and `old_runtime_input_count` must be zero for a clean raw run.

## Multi-Agent Workflow

### Supervisor

The supervisor reads the active context, freezes task scope, spawns a read-only planner first, approves a bounded worker plan, spawns a read-only reviewer after implementation, and reports exact gate status. The supervisor alone coordinates explicitly authorized GitHub or physical-deletion operations.

### Planner

The planner is read-only. It identifies inputs, outputs, blockers, safety gates, validation, and forbidden actions. It never edits files or creates runtime output.

### Worker

The worker changes only supervisor-approved paths and performs only approved execution. It never stages, commits, pushes, merges, tags, closes PRs, deletes branches, or deletes external assets unless the supervisor assigned that exact authorized operation.

### Reviewer

The reviewer is read-only. It checks diff scope, path leaks, runtime/large-file staging, data roles, manifests, clean dependency isolation, tests, deletion guards, and claim wording. It never edits.

### Human

The human is the final authority for stage transition, merge, release tag, force push, branch/PR deletion outside an explicit stage authorization, and any expansion of algorithm or experiment scope.

## Filesystem And Git Safety

- Tracked files use aliases only; local paths belong in ignored local config.
- Raw data are immutable and must never be overwritten, moved, or deleted by an experiment worker.
- `<PAPER_ROOT>`, `<CLEAN_ROOT>`, `<LEGACY_FREEZE_ROOT>`, and `<CODE_ROOT>` are protected cleanup roots; exact-manifest deletion must never target them.
- Runtime, provider payload, NAV, STD, EVAL_NAV, manifests, figures, archives, PDFs, and GPT-context zips remain untracked.
- Preserve unrelated user changes in a dirty worktree. Do not reset, stash, clean, or overwrite them.
- External deletion is exact-manifest only: no shell glob, no protected root, no symlink following, and checkpoint after each item.
- Never rewrite Git history or force push.
- Do not merge the clean-rebuild PR or create a clean-rebuild release tag during CLEAN0.

## Current Stage Boundary

CLEAN0 authorizes a BY2 clean smoke only as the required runtime gate. It does not authorize continuing old experiments, DA03, DA05, the 541-case matrix, paper figures, or performance claims. `CLEAN1` requires separate human approval after CLEAN0 closes.
