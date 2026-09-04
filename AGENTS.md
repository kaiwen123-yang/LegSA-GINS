# AGENTS.md — LegSA-GINS Active Project Rules

Last updated: 2026-09-04  
Canonical-541 numerical evidence completed: 2026-08-09 22:18 UTC+8  
Horizontal literature comparison, cross-layer synthesis, and exploratory plotting completed: 2026-09-04

## 0. Authority and reading order

Every agent must read this file before inspecting, changing, executing, plotting, or interpreting the project.

Then read, as applicable:

1. `docs/paper_rebuild/ACTIVE_CONTEXT.md`;
2. `docs/paper_rebuild/DATA_ROLES.md`;
3. `docs/paper_rebuild/METHOD_SCOPE.md`;
4. `docs/paper_rebuild/EXPERIMENT_PROTOCOL.md`;
5. `docs/paper_rebuild/LEGACY_DENYLIST.md`;
6. `docs/paper_rebuild/CLAIM_BOUNDARY.md`;
7. `docs/paper_rebuild/NEXT_ACTIONS.md`.

This file supersedes stale CLEAN0/CLEAN1/CLEAN2 text that still describes Canonical-541 or the horizontal comparison as unauthorized, unexecuted, or future work.

Do not silently reconcile a historical conflict that changes scientific meaning. Stale stage wording, log paths, timestamps, or archival metadata must not block current work when the completed terminal artifacts below are present.

---

## 1. Current program state

Completed program chain:

```text
CLEAN0
→ CLEAN1R2R1
→ CLEAN2R2A1
→ CLEAN3 mathematical/runtime repair
→ Canonical-541 full execution
→ Canonical-541 offline evaluation and aggregate completion
→ real-literature horizontal comparison
→ horizontal result-identity correction
→ horizontal cross-layer synthesis
→ horizontal exploratory full plotting
→ Canonical-541 paper-focused plotting
```

Authoritative completed terminal states:

```text
PASS_CANONICAL541_OFFLINE_EVALUATION_AND_AGGREGATE_READY_FOR_SEPARATE_PLOTTING
PASS_CLEAN4_HORIZONTAL_RESULT_IDENTITY_CORRECTED_AND_FINAL_EVIDENCE_INTEGRATED
PASS_CLEAN4_HORIZONTAL_CROSS_LAYER_DATA_ORGANIZED_AND_COMPLETENESS_AUDITED
PASS_CLEAN4_HORIZONTAL_FULL_PLOTTING_COMPLETE
PASS_PAPER_FOCUSED_PLOTTING_COMPLETE
```

Canonical-541 counts:

```text
cases:                         541 / 541
unique solver runs:           5951 / 5951
unique offline evaluations:   5951 / 5951
logical evaluation rows:      7033 / 7033
evaluation failures:             0
aggregate outputs:              15 / 15
paper-focused figures:         483 / 483
paper-focused PNG / PDF:       483 / 18
```

Horizontal exploratory plotting counts:

```text
families:                       66 / 66
PNG / PDF / SVG:          213 / 198 / 198
minimum PNG long edge:          >= 4096 px
```

The numerical stages are closed. Do not restart them for publication-figure construction, manuscript organization, generalization planning, storage inspection, or ordinary reporting.

The 66-family horizontal atlas and 483-figure Canonical gallery are exploratory evidence libraries. File-generation PASS does not make every image a publication figure.

---

## 2. Repository, branch, and local paths

```text
GitHub:
kaiwen123-yang/LegSA-GINS

Active local worktree:
/home/kaiwen/research/LegSA-GINS-WORKTREES/clean3-math-repair

Active local branch:
stage/clean3-math-repair

Ignored local path configuration:
/home/kaiwen/research/LegSA-GINS-WORKTREES/clean3-math-repair/
configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml
```

The local branch may be ahead of GitHub. Never reset the local worktree to `main` or a stale remote branch because recent commits are not visible remotely.

Machine-local absolute paths belong in the ignored local YAML. Do not hard-code them into shared Python or C++ source.

If the local active branch contains unpushed commits and the remote branch is stale, do not add an unrelated documentation commit directly to that stale remote branch. Use a separate documentation branch or let the human push the complete local history.

---

## 3. Authoritative Canonical-541 roots and solver identity

```text
<CANONICAL541_ATTEMPT> =
/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/
CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/
.attempt_20260808T200855P0800
```

Formal solver identity:

```text
scientific solver freeze:
64c81965b17ef1bf8ae2ce3e4dd7b1ae35110b00

executable:
/home/kaiwen/research/LegSA-GINS-WORKTREES/clean3-math-repair/
build/canonical541_cpp/legsa_v23_port_core_demo

executable SHA-256:
9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f
```

Authoritative result roots:

```text
<CANONICAL541_ATTEMPT>/08_FULL_ALGORITHM_RUNS/
<CANONICAL541_ATTEMPT>/10_INTERNAL_ABLATION_RUNS/
<CANONICAL541_ATTEMPT>/12_OFFLINE_EVALUATION/
<CANONICAL541_ATTEMPT>/13_AGGREGATE/
<CANONICAL541_ATTEMPT>/14_PAPER_FOCUSED_PLOTTING/
```

Default numerical sources:

```text
12_OFFLINE_EVALUATION/UNIQUE_EVALUATION_RESULTS.csv
12_OFFLINE_EVALUATION/LOGICAL_EVALUATION_RESULTS.csv
13_AGGREGATE/PAIRWISE_CASE_LEVEL.csv
13_AGGREGATE/PAIRWISE_SUMMARY.csv
13_AGGREGATE/FAMILY_SUMMARY.csv
13_AGGREGATE/DEGRADATION_TYPE_SUMMARY.csv
13_AGGREGATE/SEED_SUMMARY.csv
13_AGGREGATE/CASE_SUMMARY.csv
13_AGGREGATE/MODULE_ACTION_SUMMARY.csv
13_AGGREGATE/UNCERTAINTY_CALIBRATION_SUMMARY.csv
13_AGGREGATE/RECOVERY_SUMMARY.csv
13_AGGREGATE/RUNTIME_SUMMARY.csv
13_AGGREGATE/METRIC_COVERAGE_REPORT.csv
```

Do not reconstruct current metrics from screenshots, legacy tables, or old summaries.

---

## 4. Clean source and evidence boundary

Active tracked material may come from:

```text
docs/paper_rebuild/
configs/paper_rebuild/
scripts/paper_rebuild/
tests/paper_rebuild/
src/legsa_gins/paper_rebuild/
cpp/legsa_v23_port_core/
current horizontal-literature code under the clean namespace
```

Active external material may include immutable raw data under `<RAW_ROOT>`, the ignored local path configuration, the authoritative Canonical attempt, and current horizontal/generalization stage roots.

Legacy runtime, providers, row-level results, figures, aggregates, and performance numbers are not active evidence. Historical files may be read only for formula/source recovery, provenance, implementation lessons, or claim-boundary history.

Synthetic and semi-synthetic results must never be inserted into real-data result tables. Every method/run registry must state its data mode.

---

## 5. Canonical-541 scientific contract

```text
60 degradation types × 9 fixed seeds = 540 degraded cases
+ 1 clean case = 541 cases
```

The exact D01–D60 parameters are authoritative only in the tracked degradation specification and attempt case manifest. Do not redesign them from memory.

Logical aliases:

```text
F03 = A02 = AB0000
F04 = A01 = AB1111
```

Unique effective configurations:

```text
single_antenna_EKF
basic_dual_yaw_EKF
AB0000
AB1111
AB0111
AB1011
AB1101
AB1110
AB1100
AB1000
AB0100
```

Therefore:

```text
541 × 11 = 5951 unique solver/evaluation identities
7033 logical rows after alias expansion
```

Never double-count logical aliases as independent runs.

---

## 6. Fixed data, frame, and evaluation contracts

Core BY2 physical contract:

```text
GNSS1 = right
GNSS2 = left
baseline = GNSS2 - GNSS1
baseline direction = body +Y_left
nominal separation = 0.350 m
body/IMU preprocessing = FLU → FRD
imu_install = [-1, 0, 0] deg
lever arm = [+0.03, +0.03, -0.30] m in FRD
base_time = 1772784000.0
evaluation window = 66.0 .. 340.0 s
```

Trace is evaluation-only. Never use it for solver input, provider selection, frame/sign/time search, tuning, feedback, or correction.

Use wrap-safe yaw residuals. Never choose antenna order, ±90 deg transform, yaw sign, frame, time offset, or constant bias from RMSE.

The reference is Fixposition-derived and not independent ground truth. This limitation belongs in manuscript prose and claim boundaries. For publication graphics, the human requires visible labels `Truth` or `Truth Trajectory`; do not place “same-source reference” wording inside the figure itself.

---

## 7. Internal method identities and current interpretation

```text
F01 = single-antenna EKF
F02 = basic dual-yaw EKF
F03 = strong dual-yaw EKF = AB0000
A04 = AB1011 = no Source-Aware; current core candidate
F04 = AB1111 = Full; current quality-mismatch/tail-protection extension
```

Current manuscript role:

```text
A04:
core and leading main-method candidate

F04:
quality-mismatch and tail-protection extension

final manuscript identity:
PROVISIONAL_PENDING_GENERALIZATION
```

Do not claim Full universally dominates Strong or A04. Do not claim Source-Aware is nominal-silent/fault-active; clean touch rate is about 84.8%.

Current formal full-C00 anchors:

```text
F02: H / 3D / yaw = 0.355526 m / 0.893102 m / 2.338427 deg
F03: H / 3D / yaw = 0.352517 m / 0.890581 m / 1.962413 deg
A04: H / 3D / yaw = 0.352386 m / 0.890358 m / 1.934076 deg
F04: H / 3D / yaw = 0.354803 m / 0.926378 m / 1.954959 deg
```

The 77-epoch common-support values A04 2.231055 deg and F04 2.226267 deg are diagnostic-only. They must never replace the formal C00 values.

The historical 1.813898 deg final_v23 result is a legacy identity, not the current Canonical C00 result.

---

## 8. Horizontal comparison registry

Horizontal root:

```text
/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/
CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/
```

Completed evidence roots:

```text
12_FINAL_EVIDENCE_INTEGRATION/
13_HORIZONTAL_CROSS_LAYER_SYNTHESIS/
14_HORIZONTAL_FULL_PLOTTING/
```

Active cross-layer structure:

```text
Layer A — raw dual-antenna carrier/ambiguity methods:
EXT01 C-LAMBDA
EXT02 C-WLS
EXT03 Yang 2024 DD-KF + M-LAMBDA

Supplementary raw diagnostic:
EXT04 constrained FAR/PAR module only

Layer B — solution-level LC:
LC01 Pavlasek two-receiver IEKF
LC02 GINav official SPP/INS LC

Layer C — proprioceptive structural evidence:
Hartley contact-aided InEKF

Internal:
F02 Basic
F03 Strong
A04 Core
F04 Full
```

Do not add another horizontal method by default. The present technical-route coverage is sufficient for the active claim set.

---

## 9. Raw dual-antenna evidence boundaries

Use method-native state names. Do not flatten them into a shared “fix success” rate.

```text
EXT01 C-LAMBDA:
1077 / 1509 globally certified integer solutions;
no ambiguity acceptance test;
do not call them successful or correct fixes;
unresolved fractional-DD phase-bias applicability boundary.

EXT02 C-WLS:
1057 / 1509 accepted wrapped solutions;
ambiguity correctness unknown;
poor physical heading applicability on BY2.

EXT03 Yang 2024 primary mode:
609 / 1509 valid;
105 paper-ratio-fixed;
900 invalid;
101 / 105 ratio-fixed rows are proxy-inconsistent.

EXT04:
module-only diagnostic;
exact PAR policy not closed;
all declared policy/mode accepted counts are zero;
not a fourth complete raw method.
```

Hard-constrained 0.350 m baseline lengths in EXT01/EXT02 are not independent accuracy evidence.

---

## 10. Solution-level LC and Hartley boundaries

Formal C00 anchors:

```text
LC01 Pavlasek:
coverage             100%
horizontal RMSE      0.169139 m
3D RMSE              0.379009 m
roll / pitch / yaw   1.209563 / 1.567624 / 2.994827 deg

GINav official SPP/INS LC:
row coverage         28.0%
time-span coverage   62.043%
horizontal RMSE      130.818726 m
3D RMSE              219.883711 m
roll / pitch / yaw   14.936207 / 14.107015 / 69.753332 deg
alignment delay      113.002 s
configured/eligible  295 / 116
SPP valid/invalid    48 / 68
native rows          80
LC updates           11
INS-only rows        68
max gap / segments   11 s / 38
```

GINav label:

```text
EXACT_OFFICIAL_ROUTE_WITH_POOR_BY2_ACCURACY_AND_AVAILABILITY
```

LC01 and GINav have different information structures and legal supports. Their numerical gap is not a pure filter-formula comparison.

Hartley is complete for its intended structural role:

```text
63,277 real native state rows;
3 global translations + 1 gravity-axis yaw gauge;
full-precision real-data gauge equivalence;
4-contact bias-augmented rank/nullity = 23 / 4;
2-contact bias-augmented rank/nullity = 17 / 4;
rank/nullity stable across 0.1× / 1× / 10× thresholds.
```

Hartley does not provide legal absolute yaw RMSE or absolute position RMSE and must not appear in a flat accuracy ranking.

---

## 11. Corrected Classic-18 and generalization

Corrected Classic-18 is not required by default.

It becomes conditionally necessary only if the manuscript claims systematic degradation superiority over external solution-level methods. In that case, the only allowed set is:

```text
LC01
F02
F03
A04
F04
```

Do not include GINav, EXT01–EXT04, or Hartley. Do not start without explicit human authorization.

Priority remaining evidence gaps:

```text
independent or more independent reference;
additional real sequences/platforms;
real single-antenna obstruction or one-side quality degradation;
cross-sequence/cross-platform generalization;
final A04/F04 role selection.
```

Do not automatically repeat the full 541 × 11 matrix on another dataset.

---

## 12. Current publication-figure task

The active horizontal publication task contains exactly four composite figures:

```text
FIG01 — horizontal comparison information hierarchy
FIG02 — formal C00 solution-level navigation comparison
FIG03 — raw dual-antenna BY2 applicability
FIG04 — Hartley yaw unobservability
```

Output root:

```text
/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/
CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/
15_HORIZONTAL_PUBLICATION_FIGURES/
```

Out of scope:

```text
Canonical-541 overall robustness;
D01–D60 atlases;
541-case heatmaps;
ablation matrices;
selected degradation time series;
P01–P18;
EXT04 publication figures;
77-epoch diagnostic figures;
full 66-family atlas cleanup;
TIM figure ranking.
```

Keep these existing roots unchanged as exploratory evidence libraries:

```text
14_HORIZONTAL_FULL_PLOTTING/
<CANONICAL541_ATTEMPT>/14_PAPER_FOCUSED_PLOTTING/
```

Do not spend time globally cleaning their automatic dashboard templates as part of the four-figure task.

---

## 13. Publication visual contract

Publication figures are not engineering dashboards.

Every publication composite must:

```text
use only panel labels (a), (b), (c), (d);
contain no figure-wide machine title;
contain no right-top scope badge;
contain no “ONLY” badge;
contain no field-coverage panel;
contain no absolute source path;
contain no PASS/FAIL or management state;
separate metres, degrees, counts, rates, and time onto legal axes;
keep legends clear and non-overlapping;
remain readable at about 174 mm double-column width.
```

Visible reference labels, when needed:

```text
Truth
Truth Trajectory
```

Do not place `same-source reference`, `Fixposition-derived reference`, `not independent ground truth`, or their Chinese equivalents inside the figure. The human controls that explanation in manuscript prose.

Figure-specific boundaries:

```text
FIG01:
clean information-flow diagram only; no registry bars, claim ceilings, field completeness, or method PASS/FAIL.

FIG02:
LC01, GINav, F02, F03, A04, F04 formal C00 only;
position, attitude, and support separated;
use logarithmic overview plus readable low-error inset or facets;
never use 77-epoch diagnostic values.

FIG03:
EXT01, EXT02, EXT03 only;
use method-native outcome semantics;
show availability, yaw consistency, baseline-direction consistency, and failure composition;
never label certified/accepted outputs as correct fixes.

FIG04:
Hartley gauge ensemble, normalized gauge residuals, rank/nullity, and singular-value spectrum;
no absolute RMSE and no flat comparison with other methods.
```

Use consistent method colors and line styles/markers/hatching so grayscale printing remains interpretable.

---

## 14. Plotting execution contract

```text
default plotting workers: 16
hard maximum workers:     24
progress heartbeat:       every 10 seconds
minimum PNG width:        4096 px
outputs:                  PNG + vector PDF + SVG
```

Use independent plotting processes. Each worker must use one numerical-library thread.

Render only from frozen results. Do not run a solver, evaluator, MATLAB, provider, Canonical runner, or Canonical robustness plotter.

Do not create ZIPs, hash manifests, seals, evidence packages, contact-sheet atlases, large galleries, or reviewer chains for the four-figure task. A short figure index, captions file, and plotting summary are sufficient.

---

## 15. Runtime provenance: proportionate requirements

Formal numerical runs must record enough to identify:

```text
data mode;
case and method identity;
scientific solver commit;
executable identity;
runtime configuration;
input paths/roles;
synthetic/semi-synthetic flags;
trace-used-online flag;
forbidden solver-input flags;
terminal status.
```

Do not require repeated whole-payload SHA-256 calculations for plotting, literature reading, monitoring, routine adapters, or reuse of completed evaluations.

Hashing, seals, sidecars, ZIPs, and publication-parity packages are not default requirements. Use them only when the human explicitly requests archival closure or a concrete integrity problem exists.

---

## 16. Engineering and anti-overengineering rules

Simple bounded tasks should be executed directly by one agent. Do not automatically create planner/worker/reviewer chains.

Keep checks that protect scientific meaning:

```text
formula and frame correctness;
input availability;
method/case identity;
finite outputs;
no trace-driven tuning;
no result substitution.
```

Do not block work for:

```text
directory-size metadata;
timestamps;
absolute log-path differences;
report-only fields;
repeated hashes of unchanged files;
missing optional archival metadata.
```

Forbidden process patterns:

```text
idle “waiting for agents” loops;
long model sessions that only tail an OS job;
front-loaded full-matrix preflight before useful output;
multiple full validation passes over the same payload;
a new stage for every metadata correction.
```

Long computations should use `systemd-run --user`, `tmux`, or `nohup` with visible progress counts.

Generic code must not hard-code old stage IDs, old roles, old method allowlists, one historical attempt path, or a paper baseline length in place of current physical geometry.

---

## 17. Filesystem and Git safety

- Raw data are immutable and must never be overwritten, moved, or deleted by an experiment worker.
- Preserve the Canonical attempt, NAV, STD, evaluation, aggregate, and time-series assets needed for figures and manuscript evidence.
- Runtime outputs and large generated artifacts remain untracked unless the human explicitly authorizes a small tracked report.
- Preserve unrelated user changes. Never reset, stash, clean, or overwrite them automatically.
- Never rewrite Git history or force-push.
- Do not merge, tag, push, delete branches, or create a new worktree without explicit human authorization.
- Tracked files use portable paths/aliases; machine-local absolute paths remain in ignored local configuration.

---

## 18. Current next actions

Current allowed sequence:

```text
1. build the four publication figures in Section 12;
2. preserve the exploratory atlases as read-only evidence libraries;
3. run explicitly authorized real generalization experiments;
4. use generalization evidence to freeze the final A04/F04 manuscript role.
```

Do not restart Canonical-541, reselect horizontal literature algorithms, rerun GINav, reopen Hartley absolute-reference evaluation, or run corrected Classic-18 by default.
