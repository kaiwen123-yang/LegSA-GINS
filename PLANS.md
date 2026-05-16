# PLANS.md — LegSA-GINS Current Plan and Stage Roadmap

## 0. Purpose of this file

This file records the active project roadmap, completed stages, current blockers, future stages, and Codex multi-agent workflow for the LegSA-GINS project.

This file is not a runtime report.
This file is not an algorithm output.
This file is not a paper claim.
This file is not a place to store local absolute paths.

The goal of this file is to prevent context loss and phase confusion when using Codex App, Codex CLI, ChatGPT, or multi-agent workflows.

---

## 1. Project identity

Project name:

```text
LegSA-GINS

Project direction:

Legged robot GNSS/INS fusion with Raw Doppler, source-aware weighting, Go2 proprioceptive observations, legged FGO candidate factors, no-feedback FGO, and FGO-feedback EKF joint filtering.

Research objective:

Build a robust legged-robot positioning and attitude estimation framework that combines EKF front-end filtering and sliding-window FGO feedback, while preserving strict source roles, evaluation boundaries, and reproducible engineering evidence.

Current data focus:

BY2 normal/clean data first.
After BY2 is fully audited, move to BY3, indoor-outdoor transition, and poor-GNSS data.
2. Global working principles

The project must follow these principles:

Do not confuse source observations with algorithm outputs.
Do not confuse evaluation reference with solver input.
Do not confuse PNG existence with valid plotting.
Do not confuse clean BY2 engineering validation with paper-level performance claims.
Do not proceed to degradation or generalization before the BY2 output/plot/evaluation chain is audited.
Do not change algorithm code during reporting or plot audit stages.
Do not tune using trace or final_v23 output.
Do not make unsupported claims.
Do not merge, tag, close PRs, delete branches, or force push without human approval.
The human user is always the final decision maker.
3. Required multi-agent workflow

Future work should use the following multi-agent structure:

supervisor -> planner -> worker -> reviewer -> human final decision
3.1 supervisor

The supervisor coordinates the task.

Responsibilities:

Read the human task.
Verify the current stage.
Check the hard boundaries.
Spawn planner first.
Review the planner's read-only plan.
Approve or reject the worker scope.
Spawn worker only after the scope is clear.
Spawn reviewer after worker finishes.
Summarize results.
Never self-merge.
Never self-tag.
Never close PRs.
Never delete branches.
Never force push.
Never skip the human final decision.
3.2 planner

Planner is read-only.

Responsibilities:

Inspect branch, PR, git status, docs, reports, runtime roots, and risks.
Identify required files, required reports, validation commands, and forbidden actions.
Return a concrete execution plan.
Never edit files.
Never create runtime outputs.
Never commit.
3.3 worker

Worker executes only the approved plan.

Responsibilities:

Edit only approved tracked files.
Generate runtime outputs only under approved runtime folders.
Do not commit raw data.
Do not commit generated figures.
Do not commit NAV / STD / EVAL_NAV / RUN_MANIFEST runtime artifacts.
Do not change algorithm code unless explicitly approved.
Do not tune using trace or final_v23.
Report exactly what was done.
3.4 reviewer

Reviewer is read-only.

Responsibilities:

Review git diff.
Check hard boundaries.
Check no runtime artifacts were committed.
Check no path leaks exist.
Check claim boundaries.
Check whether generated reports match actual outputs.
For plotting tasks, verify that applicable plots use real data.
Do not edit files.
3.5 human

The human user decides:

whether to merge;
whether to tag;
whether to close PRs;
whether to delete branches;
whether to proceed to the next stage.

No agent may bypass the human final decision.

4. Global hard boundaries

Unless explicitly approved by the human, never do the following:

Do not merge PR #21.
Do not close PR #21.
Do not delete remote branches.
Do not force push.
Do not submit raw data.
Do not submit by2.txt.
Do not submit NAV / STD / EVAL_NAV / RUN_MANIFEST runtime outputs.
Do not submit generated PNG/PDF/SVG/JPG/JPEG figures.
Do not submit FGO_FEEDBACK_OBSERVATIONS.csv.
Do not submit FGO_SMOOTHED_NAV.csv.
Do not submit FGO_FACTOR_TABLE.csv.
Do not submit generated degradation CSV / summary / case review runtime files.
Do not write local absolute paths into tracked docs/config/scripts.
Do not modify /home/kaiwen/KF-GINS.
Do not run git add / commit / checkout / reset / pull / push inside /home/kaiwen/KF-GINS.
Do not compile reference/final_v23_repo itself.
Do not use trace as solver input.
Do not use final_v23 output as solver input.
Do not tune using trace or final_v23.
Do not perform output-only correction.
Do not directly overwrite EKF NAV with FGO output.
Do not delete bad epochs to pass metrics.
Do not treat Go2 position, velocity, contact, or yaw as truth.
Do not treat GNSS source observations as algorithm estimates.
Do not treat placeholder PNG generation as successful plotting.
Do not make paper performance claims unless explicitly approved after sufficient evidence.
Do not claim outperform final_v23.
5. Fixed data source roles
5.1 trace

Role:

evaluation-only reference / truth

Never:

solver input
tuning source
algorithm estimate
5.2 gnss1 / gnss2 raw/status

Role:

GNSS source observations
yaw observation source
Raw Doppler source diagnostics
observation quality diagnostics

Never:

algorithm estimate
trajectory estimate
direct error metric source
5.3 by2.txt

Role:

Go2 body / high-level source data
Go2 IMU/body state
Go2 velocity source
Go2 contact / foot / mode / gait source

Never:

truth
absolute pose reference
absolute yaw truth
5.4 receiver IMU data

Role:

diagnostic source only unless explicitly reviewed and approved

Never:

implicit replacement for Go2 body IMU
5.5 NAV / EVAL_NAV / STD / RUN_MANIFEST

Role:

algorithm output
evaluation chain
plot source for estimates, errors, metrics, and algorithm comparisons

Trajectory, error, metric, and compare figures must be based on verified algorithm outputs.

5.6 final_v23 output

Role:

reference comparison
sanity check
lineage comparison

Never:

solver input
tuning source
hidden target
6. Completed stage summary
6.1 N0 — final_v23 source baseline

N0 established the final_v23 / KF-GINS-style source baseline.

Key conclusions:

final_v23 is the strong baseline and lineage source.
final_v23 outputs can be used for comparison and sanity checks.
final_v23 outputs must not be used as solver input.
The project must not silently modify the original /home/kaiwen/KF-GINS repository.
6.2 N1 — repository and governance setup

N1 established the LegSA-GINS repository direction, phase log, claim boundary, and PR discipline.

Key conclusions:

The repository must track stage decisions.
PR #21 remains open/unmerged as historical evidence.
Branches, tags, PR merges, and scope changes require human final decision.
6.3 N2 — BY2 data source role clarification

N2 clarified BY2 source roles.

Key conclusions:

trace is evaluation-only.
gnss1/gnss2 are source observations.
by2.txt is Go2 source data, not truth.
NAV/EVAL_NAV/STD/RUN_MANIFEST are algorithm output files.
6.4 N3 — audit and source-lineage groundwork

N3 prepared the audit structure.

Key conclusions:

Source availability is not algorithm output.
A figure must not be called complete only because a PNG exists.
Output lineage, frame alignment, time alignment, and metric sanity must be audited before plotting.
6.5 N4 — source-backed EKF port

N4 ported the source-backed EKF backbone.

Key conclusions:

EKF propagation/update structure was established.
final_v23 parity and source-backed lineage were audited.
The source-backed EKF is the base engineering backbone.
6.6 N5 — Raw Doppler EKF factor

N5 activated Raw Doppler in the EKF front-end.

Key conclusions:

Raw Doppler is not NAV-PVT velocity.
Raw Doppler is not .gnss velocity.
Raw Doppler was activated as a real EKF velocity factor.
Raw Doppler EKF contribution is engineering evidence, not a final paper performance claim.
6.7 N6 — source-aware weighting

N6 developed source-aware LSIM/OIM weighting.

Key conclusions:

N6A was too aggressive.
N6B conservative policy stabilized source-aware weighting.
Source-aware weighting is an active R-scaling layer.
Stress evidence remains limited.
6.8 N7 — Go2 proprioceptive observations

N7 developed Go2 proprioceptive observations.

Key conclusions:

Go2 roll/pitch and horizontal velocity were used as proprioceptive observations.
Go2 position, yaw, contact, and velocity are not truth.
Go2 proprioceptive joint factor is active.
Candidate foot/contact/yaw-rate/relative odometry sources require separate review.
6.9 N8A-N8E — no-feedback FGO

N8A-N8E built and audited the no-feedback FGO backend.

Key conclusions:

N8A built the initial no-feedback FGO.
N8A1 found yaw wrap problems.
N8A2 fixed yaw residual wrapping.
N8C2 found Raw Doppler proxy existed but was not in solver residual.
N8C3 fixed Raw Doppler FGO solver injection.
N8D reviewed FGO weight policy.
N8E produced formal engineering ablation with caveats.
Raw Doppler FGO is active but low marginal value in clean BY2.
6.10 N8F-N8F1 — legged candidate factors

N8F formally activated candidate legged factors inside no-feedback FGO.

Activated factors:

contact-aware weighting
foot kinematic velocity factor
Go2 yaw-rate between factor
Go2 relative odometry between factor

Key conclusions:

These factors have rows/residuals/Jacobians/toggles.
N8F1 visual validation passed.
They remain engineering factors/candidates, not truth.
6.11 N8G-N8J — FGO feedback EKF joint filter

N8G introduced controlled FGO feedback into EKF.

Selected N8J policy:

feedback_mode = horizontal_velocity_attitude_feedback
gate = combined_conservative_gate
covariance = inflation_auto_from_residual_proxy
window = 5s / 1s
position_feedback = disabled

Key conclusions:

FGO feedback enters EKF as a controlled update.
It is not output substitution.
It is not direct NAV overwrite.
It uses no future data.
N8J decision: feedback_joint_filter_ready_for_BY2_packaging.
Clean BY2 selected-vs-baseline deltas are tiny, so no performance claim is allowed.
6.12 N8K — BY2 formal ablation and plot audit

N8K ran BY2 formal ablation and ablation plot audit.

Key conclusions:

30 variants completed.
Metrics were generated.
A large plot set was generated.
Follow-up N8K2-N8K6 repairs addressed plot materialization, duplicate, semantic filename, cross-category duplicate, and applicability issues.
The main lesson remains active: PNG existence is not figure validity.
7. Current documentation stage

Current documentation stage:

N9A_R0_MULTI_AGENT_CONTEXT_REBUILD

Purpose:

Rebuild persistent multi-agent context so future Codex work does not lose the project route, data source roles, claim boundaries, and plotting rules.

N9A_R0 does not:

validate algorithm outputs
draw figures
run degradation
grant plot permission
allow N9B
8. Current technical next gate

The next technical gate after N9A_R0 is:

N9A_R3_REAL_OUTPUT_AND_FRAME_ALIGNMENT_GATE

N9A_R3 must audit:

algorithm output lineage
output role classification
frame alignment
time alignment
metric sanity
trace/reference usage
velocity source validity
attitude source validity
feedback source validity
legged source validity
plot permission matrix

N9A_R3 must not draw formal figures.

N9A_R3 must keep:

ready_for_N9B = false

If N9A_R3 passes, the next stage is:

N9A_R4_draw_allowed_BY2_normal_figures

not N9B.

9. N9A_R4 expected role

N9A_R4 will draw BY2 normal-condition figures only for allowed_to_plot=true entries from N9A_R3.

N9A_R4 must:

save algorithm outputs runtime-only;
draw real data figures;
block missing sources;
document not-applicable figures;
avoid placeholders for applicable figures;
avoid degradation matrix execution.

N9A_R4 must not:

modify algorithms;
tune feedback policy;
run full degradation;
make paper claims.
10. N9B expected role

N9B is the full BY2 degradation matrix.

It must wait until:

N9A_R3 passes
N9A_R4 completes allowed normal-condition plotting
N9A final review is accepted
human explicitly approves N9B

N9B degradation families include:

GNSS outage
sampling / timing degradation
GNSS position noise
position spikes / outliers
std inflation
receiver velocity degradation
Raw Doppler degradation
dual yaw degradation
Go2 attitude degradation
Go2 horizontal velocity degradation
contact probability degradation
foot kinematic degradation
yaw-rate / relative odometry degradation
combined degradation

Randomized cases should use seeds:

0..9

and record:

seed
trigger count
mask count
effective observation count
11. N9C expected role

N9C generates degradation plots and case review.

N9C must apply the 01-14 taxonomy to every degradation case.

12. N9D expected role

N9D audits the full technical chain:

mathematical residuals
Jacobians
coordinate frames
time alignment
output evaluation chain
filter construction
feedback update chain
no future data
no output substitution
plot semantics
13. N9E expected role

N9E packages BY2 paper-level results with strict claim boundaries.

N9E must distinguish:

engineering evidence
diagnostic evidence
paper candidate evidence
forbidden claims
future generalization tasks
14. N10 expected role

N10 performs generalization after BY2 is fully audited.

Planned stages:

N10A: BY3 same-scene replication
N10B: indoor-outdoor transition
N10C: poor-GNSS environment

No BY3/indoor-outdoor/poor-GNSS claim is allowed before those stages run.

15. Plot taxonomy

All BY2, degradation, BY3, indoor-outdoor, and poor-GNSS work must use:

01_trajectory
02_position_errors
03_velocity
04_attitude
05_consistency
06_observation_quality
07_compare
08_summary_panels
09_case_review
10_fgo_factors
11_feedback
12_legged_factors
13_degradation_meta or 13_ablation_meta
14_audit_sanity

If applicable=True, the figure must use real data.

If not_applicable=True, a documented placeholder panel is allowed only with a clear reason.

Forbidden figure types:

metadata-only panel marked applicable
duplicate template image with only title changed
fake zero-line plot
availability bar pretending to be contact/feedback data
source observation pretending to be algorithm estimate
unaligned trajectory comparison
16. Claim boundary

Allowed at the current stage:

BY2 FGO-feedback EKF joint filter engineering chain has been validated.
FGO feedback enters EKF as a controlled update.
No output substitution, no direct NAV overwrite, no future-data feedback.
Raw Doppler EKF is active.
Raw Doppler FGO is active but low marginal value in clean BY2.
Go2 proprioceptive joint factor is active.
Legged candidate factors are activated in no-feedback FGO.
N8K formal ablation chain exists, with plot validity requiring real-output gates.

Forbidden:

outperform final_v23
paper performance improvement claim
Go2 truth claim
FGO replaces EKF
trace/final_v23 tuning
source observations as algorithm estimates
placeholder plots as real figures
degradation generalization before N9B/N10 evidence
17. Required plan format

Every future plan must include:

Goal.
Verified current state.
Scope.
Inputs.
Outputs.
Execution steps.
Validation.
Prohibited actions.
Risks.
Completion criteria.
Final report requirements.
18. Completion criteria for N9A_R0

N9A_R0 is complete only when:

AGENTS.md is coherent.
PLANS.md is coherent.
.codex/agents files exist.
docs/codex_context files exist.
No conflict markers exist.
No local path leaks exist.
No runtime artifacts are committed.
No algorithm files are changed.
The current route is clear.
The immediate next technical gate is N9A_R3.

N9A_R0 completion does not authorize N9B.
