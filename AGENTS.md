# AGENTS.md  LegSA-GINS Multi-Agent Working Rules

## 0. Purpose

This repository is used for the LegSA-GINS project: a legged-robot GNSS/INS fusion system with Raw Doppler, source-aware weighting, Go2 proprioceptive observations, legged candidate FGO factors, no-feedback FGO, and FGO-feedback EKF joint filtering.

This file is the persistent project context for Codex multi-agent work. It must prevent repeated context loss, phase confusion, false plot completion, unsafe merges, unsupported claims, and accidental algorithm changes.

The project should be developed with a supervised multi-agent workflow:

- supervisor
- planner
- worker
- reviewer
- human final decision

The human user is the final decision maker for merge, tag, branch deletion, PR closure, and stage transitions.

---

## 1. Required multi-agent workflow

All future Codex work should use the following workflow.

### 1.1 supervisor

The supervisor is the main coordinator.

Responsibilities:

- Read the human task.
- Check current stage and boundaries.
- Spawn planner first.
- Review planner output.
- Approve or reject worker scope.
- Spawn worker only after the scope is clear.
- Spawn reviewer after worker finishes.
- Summarize the final result.
- Never self-merge, self-tag, force push, close PRs, or delete branches without explicit human approval.

The supervisor must prevent phase confusion.

Important examples:

- N8K is BY2 formal ablation and ablation plot audit.
- N8K2 fixes real plot materialization for N8K placeholder plots.
- N9A is BY2 full plot audit.
- N9B is the BY2 full degradation matrix.
- N9C is degradation plotting and case review.
- N9D is mathematical / evaluation / filter construction full-chain audit.
- N9E is BY2 paper-level packaging.

### 1.2 planner

Planner is read-only.

Responsibilities:

- Inspect branch, PR, git status, reports, docs, runtime roots, and risks.
- Create an execution plan.
- Identify required files, expected outputs, blockers, validation commands, and forbidden actions.
- Never edit files.
- Never create runtime outputs.
- Never commit.

### 1.3 worker

Worker executes only the supervisor-approved plan.

Responsibilities:

- Edit only approved tracked files.
- Generate runtime outputs only in approved runtime folders.
- Never commit raw data, figures, NAV/STD/EVAL, RUN_MANIFEST, FGO tables, or generated runtime artifacts.
- Never change algorithms unless the task explicitly permits it.
- Never tune using trace/final_v23.
- Report exactly what was done.

### 1.4 reviewer

Reviewer is read-only.

Responsibilities:

- Review git diff.
- Check hard boundaries.
- Check runtime artifacts were not committed.
- Check no local path leaks exist.
- Check claim boundaries.
- Check whether reports match actual outputs.
- For plotting tasks, verify applicable=True plots are real data, not placeholders.
- Never edit files.

### 1.5 human

The human user decides:

- whether to merge;
- whether to tag;
- whether to close PRs;
- whether to delete branches;
- whether to proceed to the next stage.

No agent may bypass human final decision.

---

## 2. Global hard boundaries

Unless explicitly requested by the human, never do the following:

- Do not merge PR #21.
- Do not close PR #21.
- Do not delete remote branches.
- Do not force push.
- Do not commit raw data.
- Do not commit by2.txt.
- Do not commit NAV / STD / EVAL_NAV / RUN_MANIFEST runtime outputs.
- Do not commit generated figures.
- Do not commit FGO_FEEDBACK_OBSERVATIONS.csv.
- Do not commit FGO_SMOOTHED_NAV.csv.
- Do not commit FGO_FACTOR_TABLE.csv.
- Do not commit generated degradation CSV / summary / case review runtime files.
- Do not write local absolute paths into tracked docs/config/scripts.
- Do not modify <WSL_ALGO_REPO>.
- Do not run git add / commit / checkout / reset / pull / push inside <WSL_ALGO_REPO>.
- Do not compile reference/final_v23_repo itself.
- Do not use trace as solver input.
- Do not use final_v23 output as solver input.
- Do not tune using trace or final_v23.
- Do not perform output-only correction.
- Do not directly overwrite EKF NAV with FGO output.
- Do not delete bad epochs to pass metrics.
- Do not make paper performance claims unless explicitly approved after multi-dataset evidence.
- Do not claim outperform final_v23.
- Do not treat Go2 position, velocity, contact, or yaw as truth.
- Do not treat GNSS source observations as algorithm estimates.
- Do not treat placeholder PNG generation as successful plotting.

---

## 3. Data source roles

These source roles are fixed.

### 3.1 trace

Role:

- evaluation-only reference/truth.

Never:

- solver input;
- tuning source;
- algorithm estimate.

### 3.2 gnss1 / gnss2 raw/status

Role:

- source observations;
- GNSS observation quality;
- yaw observation;
- Raw Doppler source diagnostics.

Never:

- algorithm estimate;
- trajectory estimate;
- direct metric source.

### 3.3 by2.txt

Role:

- Go2 body/high-level source data;
- Go2 IMU/body state;
- Go2 velocity, contact, foot, mode/gait diagnostic source.

Never:

- truth;
- absolute pose reference.

### 3.4 receiver IMU data

Role:

- diagnostic source unless explicitly approved.

Never:

- replacement for Go2 body IMU without explicit review.

### 3.5 NAV / EVAL_NAV / STD / RUN_MANIFEST

Role:

- algorithm outputs;
- evaluation chain;
- plot source for estimates, errors, metrics, and comparisons.

Trajectory/error/metric plots must use verified algorithm outputs, not source observations.

### 3.6 final_v23 output

Role:

- reference comparison / sanity check only.

Never:

- solver input;
- tuning source.

---

## 4. Current route

The current route is:

N8J: feedback joint filter BY2 final validation
N8K: BY2 paper-required formal ablation and ablation plot audit
N8K2: real plot materialization fix for N8K placeholder plots
N9A: BY2 full plot audit
N9B: BY2 full degradation matrix
N9C: BY2 degradation plot and case review
N9D: mathematical / output evaluation / filter construction full-chain audit
N9E: BY2 paper-level result packaging
N10A: BY3 same-scene replication
N10B: indoor-outdoor transition
N10C: poor-GNSS environment

Do not mix these stages.

Important:

- N8K is formal ablation and ablation plot audit.
- N8K is not degradation.
- N9B is degradation.
- N8K2 is required before N9A because N8K plots were found to include placeholder-like applicable figures.

---

## 5. Stage history summary

### N0

Original final_v23 / KF-GINS-style thesis mainline was the source-backed algorithm base.

Key facts:

- final_v23 is the strong EKF baseline.
- It uses GNSS position, velocity, dual-yaw, IMU propagation, and error-state feedback.
- It is reference lineage, not something to silently modify.
- Its outputs may be used for comparison only, not as solver input.

### N1

LegSA-GINS repository and engineering boundaries were established.

Key facts:

- The repo must track phase logs, claim boundaries, audits, and reproducibility.
- PR #21 remains an old open/unmerged branch and must not be touched.

### N2

BY2 data source roles were clarified.

Key facts:

- trace is evaluation-only.
- gnss1/gnss2 are source observations.
- by2.txt is Go2 body/high-level data.
- NAV/EVAL/STD/RUN_MANIFEST are algorithm outputs.

### N3

Audit framework and source-lineage checks were prepared.

Key facts:

- The project must not rely on source/proxy availability bars as algorithm output.
- Plotting must be gated by real algorithm output and frame/time alignment.

### N4

Source-backed EKF port and final_v23 parity were established.

### N5

Raw Doppler EKF factor was activated and audited.

### N6

Source-aware LSIM/OIM weighting was activated as an R-scaling layer.

### N7

Go2 roll/pitch and horizontal velocity were developed into a Go2 proprioceptive joint observation factor.

### N8A-N8E

No-feedback FGO backend was built, yaw wrap was fixed, Raw Doppler FGO activation was fixed, and formal engineering ablation with caveats was produced.

### N8F-N8F1

Legged candidate FGO factors were formally activated and visually validated:

- contact-aware weighting;
- foot kinematic velocity;
- yaw-rate between factor;
- relative odometry between factor.

### N8G-N8J

FGO feedback EKF joint filter was implemented and validated.

Selected policy:

- horizontal_velocity_attitude_feedback;
- combined_conservative_gate;
- inflation_auto_from_residual_proxy;
- 5s window / 1s stride;
- primary position feedback disabled.

N8J decision:

- feedback_joint_filter_ready_for_BY2_packaging.

### N8K

BY2 formal ablation and ablation plot audit was run.

Reported:

- 30 variants complete;
- 2850 PNGs generated;
- categories 01-14 covered.

Manual inspection found a serious issue:

- Some applicable=True figures were placeholder-like templates rather than real plots.

### N8K2

Immediate next stage.

Goal:

- Fix N8K placeholder-like applicable plots by materializing real plots from real algorithm outputs.

---

## 6. Current blocker

N8K generated many PNGs and reported 01-14 coverage, but manual inspection found that some applicable=True figures are not real plots.

Problem examples:

- baseline_vs_variant_trajectory.png
- local_trajectory_overlay.png
- start_end_marker_trajectory.png
- trajectory_delta_vector.png
- zoomed_trajectory_key_region.png

Observed issue:

- Figures are nearly identical.
- Only figure names/titles change.
- They contain metadata text and a small template line.
- They do not plot real baseline, variant, reference, start/end markers, delta vectors, or zoomed regions.

Required fix:

- N8K2 must materialize real plots from real algorithm outputs.
- PR #48 must not be merged before N8K2 passes.
- N9A must not start before N8K2 passes.

---

## 7. Plot taxonomy

All BY2 / degradation / BY3 / indoor-outdoor / poor-GNSS figures must follow the 01-14 taxonomy.

### 01_trajectory

- local trajectory ENU
- baseline vs selected feedback
- EKF only vs no-feedback FGO vs feedback EKF
- truth/reference/estimate overlay
- start-end marker
- zoomed key region
- trajectory delta vector
- global compare figure

### 02_position_errors

- North/East/Up error
- horizontal error
- RMSE / P95 / max
- CDF / ECDF
- outage shaded error if applicable
- recovery time if applicable

### 03_velocity

- vN/vE/vD estimate
- receiver velocity
- Raw Doppler velocity
- Go2 horizontal velocity
- foot kinematic velocity
- residuals
- source deltas
- Doppler residual

### 04_attitude

- roll/pitch/yaw estimate
- yaw observation/reference
- yaw residual
- yaw wrap check
- yaw-rate between residual
- attitude RMSE/P95

### 05_consistency

- error + 3sigma
- innovation/residual
- whitened residual
- NIS proxy
- coverage ratio
- covariance diagonal
- feedback covariance inflation

### 06_observation_quality

- GNSS position/velocity observations
- GNSS std
- yaw observation/yaw_std
- Raw Doppler quality
- Go2 contact weight
- foot kinematic quality
- feedback accept/reject
- source-aware R scale

### 07_compare

- baseline EKF
- Raw Doppler EKF
- source-aware EKF
- Go2 joint EKF
- no-feedback FGO
- feedback EKF
- reject-all sanity
- selected feedback

### 08_summary_panels

- horizontal RMSE heatmap
- yaw RMSE heatmap
- up RMSE heatmap
- pass/fail boundary
- degradation strength curve
- algorithm rank summary
- contribution stack summary

### 09_case_review

- case summary
- key metrics
- worst segment
- degradation input explanation
- anomalies
- pass/fail
- recommended figures
- conclusion suggestions

### 10_fgo_factors

- factor residual by type
- whitened residual
- factor contribution
- factor rows
- Jacobian nonzero
- FGO cost
- smoothness residual
- Raw Doppler FGO residual
- Go2 joint FGO residual
- candidate factor residual

### 11_feedback

- feedback window timeline
- accept/reject timeline
- correction norm
- covariance
- gate threshold
- reject reason
- selected feedback vs baseline
- reject-all sanity

### 12_legged_factors

- contact probability
- slip risk
- foot kinematic velocity
- yaw-rate between residual
- relative odometry residual
- Go2 joint residual
- contact-aware weight scale

### 13_degradation_meta / 13_ablation_meta

- degradation mask
- degradation interval
- injected noise
- spike triggers
- sampling drop points
- std inflation
- yaw degradation meta
- active module list
- variant configuration
- factor enable/disable panel

### 14_audit_sanity

- row count
- time monotonic
- NaN/Inf check
- input/output alignment
- runtime manifest
- no future data
- no output substitution
- path leak check

---

## 8. Plot rules

If applicable=True:

- plot must use real data;
- must have real rows;
- must not be metadata-only;
- must not be a repeated template with only title changed;
- must not use fake zero lines;
- must not use source/proxy availability as algorithm output;
- must be blocked if real data is missing.

If not_applicable=True:

- placeholder panel is allowed;
- reason must be documented.

---

## 9. N9B degradation plan

N9B will run the full BY2 degradation matrix.

N8K2 and N9A must not run the degradation matrix.

N9B degradation families include:

- GNSS outage
- sampling / timing degradation
- GNSS position noise
- position spikes/outliers
- std inflation
- receiver velocity degradation
- Raw Doppler degradation
- dual yaw degradation
- Go2 attitude degradation
- Go2 horizontal velocity degradation
- contact probability degradation
- foot kinematic degradation
- yaw-rate and relative odometry degradation
- combined degradation

Randomized degradations use seeds 0..9 and must record:

- seed
- trigger count
- mask count
- effective observation count

---

## 10. Claim boundary

Allowed at the current stage:

- BY2 FGO-feedback EKF joint filter engineering chain has been validated.
- FGO feedback enters EKF as a controlled update.
- No output substitution, no direct NAV overwrite, no future-data feedback.
- Raw Doppler EKF is active.
- Raw Doppler FGO is active but low marginal value in clean BY2.
- Go2 proprioceptive joint factor is active.
- Legged candidate factors are activated in no-feedback FGO.
- N8K formal ablation has runtime outputs, but plot materialization needs N8K2.

Forbidden:

- outperform final_v23
- paper performance improvement claim
- Go2 truth claim
- FGO replaces EKF
- trace/final_v23 tuning
- source observations as algorithm estimates
- placeholder plots as real figures
- degradation generalization before N9B/N10 evidence

---

## 11. Immediate next stage

The immediate next stage is:

N8K2_BY2_formal_ablation_real_plot_fix

N8K2 must:

- detect placeholder and duplicate-template plots;
- load real algorithm outputs;
- re-render applicable=True plots using real data;
- keep documented placeholders only for not-applicable plots;
- ensure applicable_placeholder_count = 0;
- ensure duplicate_template_suspect_count = 0 or resolved;
- ensure fake_zero_line_suspect_count = 0;
- not run degradation matrix;
- not change algorithms;
- not tune feedback or FGO policies;
- not make paper claims.

