# AGENTS.md - LegSA-GINS Windows audit workspace

Version: 2026-05-16 N9A_R0_MULTI_AGENT_CONTEXT_REBUILD.

This repository checkout is the Windows audit workspace for LegSA-GINS. It is used to organize audit rules, context files, reports, plans, and lightweight review material. It is not the default place to edit algorithm source code.

## Project Goal

LegSA-GINS is a staged engineering and audit project for source-backed GNSS/INS/legged fusion on BY2 first, then broader datasets and environments. The long-term objective is not to maximize figure count. The objective is to maintain a defensible chain from source observations, through algorithm outputs, through evaluation, through plots, and finally to paper claims.

Every stage must preserve these invariants:

- Solver inputs are declared and auditable.
- Truth/reference data remains evaluation-only.
- Algorithm outputs are separated from source observations and diagnostic proxies.
- Figures are allowed only when source role, alignment, metric sanity, and semantic sanity are established.
- Paper claims are weaker than or equal to what the audits prove.

## Current Verified State

- Current context rebuild branch: `stage/N9A-R0-multi-agent-context-rebuild`.
- PR #48: closed and merged on 2026-05-15, merge commit `02f2aa30e8255bffd4a1f0a5781b868535eef6e1`.
- PR #21: open and unmerged historical evidence branch. Do not touch.
- PR #49: open and unmerged, head `stage/N9A-BY2-full-plot-audit` at `d5dd6ee5cce9f93827c93c27ae0a88c44a7a3c13`.
- N8K formal ablation plot audit is merged and tagged as `N8K-v0.1-BY2-formal-ablation-plot-audit`.
- N9A_R2 is incomplete/failure. It must not be treated as plotting completion.
- Current next recommended stage after this context rebuild: `N9A_R3_REAL_OUTPUT_AND_FRAME_ALIGNMENT_GATE`.
- N9B has not started and must not start without explicit user approval after N9A final review.

Older user prompts may say PR #48 is open or N8K2 is next. Treat those as historical blocker/resolution context only, not current state.

## Path Aliases

Tracked docs should use aliases, not local absolute machine paths.

- `<WINDOWS_AUDIT_ROOT>`: Windows audit workspace.
- `<WSL_AUDIT_ROOT>`: WSL path to the Windows audit workspace.
- `<WSL_ALGO_REPO>`: WSL algorithm source repository.
- `<BY2_PLOT_AUDIT_ROOT>`: BY2 plot audit output area under the audit workspace.
- `<BY2_FIXPOSITION_ROOT>`: BY2 Fixposition / GNSS receiver minimal data root.
- `<GNSS1_RAW>`, `<GNSS2_RAW>`: dual antenna GNSS raw data.
- `<GNSS1_STATUS>`, `<GNSS2_STATUS>`: GNSS receiver status / quality / possible yaw or velocity status.
- `<TRACE_TRUTH>`: trace reference, evaluation-only.
- `<FIXPOSITION_IMU_DATA>`, `<FIXPOSITION_IMU_BIASES>`, `<FIXPOSITION_IMU_TEMP>`: Fixposition receiver IMU diagnostics only.
- `<GO2_BODY_IMU_HIGHLEVEL>`: fused Go2 body IMU / high-level source, usually `by2.txt`.

Real local paths belong only in `docs/codex_context/DATA_PATHS.local.md`. Do not stage or commit that file unless the user explicitly asks.

## Data Roles

- GNSS raw/status can support observation quality, Raw Doppler lineage, satellite count, yaw/status audit, and receiver velocity only if explicit velocity columns exist.
- `trace` is truth/reference/evaluation-only. It must never be solver input and must not be used for tuning, gating, weighting, covariance adjustment, or algorithm feedback.
- Fixposition receiver IMU is diagnostic only. It is not the fused Go2 body IMU.
- `by2.txt` is the Go2 body IMU / high-level source. It can support body attitude, horizontal velocity, contact, foot, and legged source audits only when fields are explicitly parsed. It is not truth and must not be used as algorithm NAV.
- final_v23 / KF-GINS can be a reference, sanity oracle, or evaluation boundary. It must not become hidden solver input for the LegSA-GINS chain.

## Multi-Agent Roles

### supervisor

- Reads `AGENTS.md`, `PLANS.md`, and `docs/codex_context/*`.
- Asks planner for read-only planning.
- Approves exact worker scope.
- Asks reviewer for read-only review.
- Does not commit, push, open PRs, merge, or tag without explicit user confirmation.

### planner

- Read-only.
- May inspect the Windows audit workspace.
- May run status-only WSL bridge checks through `scripts/run_wsl_legsa.ps1`.
- May read `DATA_PATHS.local.md` for local path location, but must not recommend staging it unless the user asks.
- Must output scope, forbidden areas, commands, validation, risks, and worker recommendation.

### worker

- Executes only supervisor-approved planner scope.
- May edit approved Windows audit workspace documentation/context files.
- May call WSL only through `scripts/run_wsl_legsa.ps1` if approved.
- Must not edit `<WSL_ALGO_REPO>` source by default.
- Must not edit final_v23 by default.
- Must not delete original data, existing outputs, or historical results.
- Must not run degradation matrices unless explicitly approved.
- Must not commit, push, open PRs, merge, tag, force push, or stage `DATA_PATHS.local.md`.

### reviewer

- Read-only.
- Checks planner scope, worker execution, changed files, validation commands, path policy, data role boundaries, generated artifact leakage, and Git readiness.
- Separately states whether the Windows audit workspace and WSL algorithm repo should commit / push / PR / merge.
- Does not modify files and does not perform Git operations.

## Forbidden Actions

- Do not merge PR #49.
- Do not tag N9A.
- Do not enter N9B.
- Do not treat N8K formal ablation variants as BY2_normal_clean normal cases.
- Do not treat N9A_R1 source lineage as plotting completion.
- Do not treat N9A_R2 partial outputs as real plotting completion.
- Do not accept "PNG exists" as "figure valid".
- Do not skip frame alignment or metric sanity.
- Do not let trace/final_v23 enter solver input or tuning.
- Do not use `by2.txt` as truth.
- Do not use receiver IMU as fused body IMU.
- Do not use availability bars as feedback/contact probability timelines.
- Do not commit raw data, runtime outputs, generated figures, archives, or local path files.

## PR, Branch, And Tag Rules

- PR #21 is historical evidence and must remain open/unmerged unless the user explicitly decides otherwise.
- PR #48 is already merged and is the verified N8K formal ablation plot audit merge.
- PR #49 remains open/unmerged and must not be merged or tagged during N9A_R0 or N9A_R3.
- New documentation-only work should use a dedicated stage branch such as `stage/N9A-R0-multi-agent-context-rebuild`.
- Worker and reviewer never commit, push, open PRs, merge, or tag.
- Supervisor may run Git write operations only after explicit user instruction for that operation.
- N9A tags are not allowed before N9A final review passes.

## Plot Taxonomy 01-14

All later BY2, N9B/N9C degradation, BY3, indoor-outdoor, and poor-GNSS work uses the same plot taxonomy:

1. `01_trajectory`: ENU/local/global trajectory, truth/reference/estimate overlays, zooms, delta vectors. Requires frame alignment.
2. `02_position_errors`: NEU/horizontal/up errors, RMSE, P95, max, CDF, recovery. Requires EVAL or recomputed aligned errors.
3. `03_velocity`: estimate, receiver, Raw Doppler, Go2, foot velocity, residuals. Requires real source-specific velocity data.
4. `04_attitude`: roll/pitch/yaw estimates, references, observations, wrap checks, yaw-rate residuals. Requires unit and convention clarity.
5. `05_consistency`: error plus 3 sigma, innovations, residuals, NIS proxy, covariance, coverage. Requires STD/covariance/residual source.
6. `06_observation_quality`: GNSS, yaw, Raw Doppler, Go2, foot, feedback, and source-aware quality signals. Must be labeled as source data, not estimate.
7. `07_compare`: real algorithm series comparison. Requires at least two aligned real algorithm outputs and sane metrics.
8. `08_summary_panels`: normal-case metric/source/lineage summaries; degradation heatmaps only after N9B/N9C.
9. `09_case_review`: case-level narrative, anomalies, pass/fail, and relevant figures.
10. `10_fgo_factors`: FGO/factor material only when reports exist; otherwise documented not-applicable.
11. `11_feedback`: feedback runtime material only for feedback-capable cases.
12. `12_legged_factors`: Go2/contact/foot/legged factor material only from real parsed data.
13. `13_degradation_meta`: normal cases are documented not-applicable; degradation cases record injection inputs.
14. `14_audit_sanity`: row counts, monotonic time, NaN/Inf, input/output alignment, manifests, no future data, no substitution, path leak checks.

For every figure, a permission matrix must record data availability, source role, row/time overlap counts, alignment, metric sanity, semantic sanity, `allowed_to_plot`, missing/not-applicable reason, redraw need, and claim boundary.

## Stage Route

- N0-N3: project boundary, data-role policy, source-backed direction, trace/final_v23 solver boundary.
- N4: source-backed EKF backbone.
- N5: Raw Doppler EKF factor.
- N6: source-aware LSIM/OIM weighting.
- N7: Go2 proprioceptive joint factor.
- N8A-N8E: no-feedback FGO backend and factor registry.
- N8F: legged candidate factors.
- N8G-N8J: FGO feedback EKF.
- N8K-N8K6: formal ablation plot audit and placeholder/duplicate/applicability repair. Merged in PR #48.
- N9A_R0: current multi-agent context rebuild.
- N9A_R3: next real output and frame alignment gate.
- N9A_R4: draw only figures allowed by the gate.
- N9A final review: decide whether N9A can merge/tag and whether N9B can be proposed.
- N9B: degradation matrix, only after explicit user approval.
- N9C: degradation figure/case review.
- N9D: math/output/filter-chain audit.
- N9E: BY2 paper-grade result packaging.
- N10A/B/C: BY3, indoor-outdoor transition, and poor-GNSS environment replication.

## N8K Placeholder Lesson

N8K initially exposed a critical documentation and audit failure mode: some `applicable=True` figures were placeholder, low-information, duplicate-template, semantically mismatched, or incorrectly marked applicable. The required immediate fix at that time was N8K2 real plot materialization repair, followed by N8K3-N8K6 duplicate, naming, cross-category, and feedback-applicability repairs.

Current verified state: that N8K2-N8K6 repair chain has completed and PR #48 is merged. Keep the lesson active for N9A: a figure is not complete because a file exists, and `applicable=True` is invalid unless the plotted content is real and semantically authorized.

## N9A_R3 Gate

N9A_R3 must be a gate, not a formal plotting run. It should audit:

- N9A_R2 failure causes.
- Real algorithm output lineage.
- Output role classification.
- NAV / STD / EVAL / summary self-consistency.
- Frame alignment: ENU/NED/BLH/local origin/time overlap.
- Time alignment.
- Metric sanity, especially final_v23 sanity scale.
- Velocity, attitude, feedback, and legged sources.
- Trace reference usage.
- Plot permission matrix.

Required decision remains `ready_for_N9B=false`.

## Claim Boundary

Allowed claims must stay engineering-audit scoped:

- source-backed EKF backbone exists and has auditable NAV/STD/EVAL output concepts.
- Raw Doppler, source-aware weighting, Go2 joint factors, FGO, and feedback EKF have staged evidence described in the history docs.
- N8K formal ablation plot audit was repaired and merged.
- N9A_R2 failed and needs N9A_R3 gate before any further plotting.

Not allowed:

- N9A plotting completion.
- N9B degradation results.
- broad BY2 performance improvement.
- outperforming final_v23.
- claims based on unaligned outputs, proxy observations, zero-line placeholders, availability bars, or trace/final_v23 leakage.

## Git Boundary

Worker must not run Git write operations. Reviewer only recommends. User owns final commit / push / PR / merge / tag decisions.

Potentially committable Windows audit files include `AGENTS.md`, `PLANS.md`, `.codex` agent definitions, non-local `docs/codex_context/*.md`, `.gitignore`, `scripts/run_wsl_legsa.ps1`, and small text audit reports.

Not committable by default: `DATA_PATHS.local.md`, logs, raw data, `by2.txt`, runtime NAV/STD/EVAL/RUN_MANIFEST, FGO runtime CSVs, generated figures, archives, and large sensor files.
