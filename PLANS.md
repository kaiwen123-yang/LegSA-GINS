# PLANS.md

## Stage N0: Bootstrap

Goal:
Create clean repository structure, governance files, phase log, claim boundary, Git ignore rules, and placeholder tests.

No algorithm implementation.

## Stage N1: final_v23-style baseline wrapper

Goal:
Add final_v23-style baseline wrapper as strong baseline and evaluator oracle.

final_v23 is not proposed.

N1 only creates baseline wrapper, manifest, oracle audit, and separation tests.

No numerical claim is allowed before real final_v23 output is connected.

Completion note:
N1 is complete as a wrapper, manifest writer, oracle audit, and separation-test stage only. It does not implement the proposed LegSA-GINS solver or any numerical performance claim.

## Stage N2: Frame / Writer / Evaluator Infrastructure

Goal:
Implement frame adapters, writer contracts, evaluator contracts, and manifest schemas.

N2 builds frame utilities, writer contracts, manifest contracts, evaluator utilities, and audits.

N2 does not implement LegSA-ESKF or algorithmic factors.

Hard gates:
- no double FLU-to-FRD transform;
- Go2 body/odom/map separation;
- NED/ENU/ECEF/BLH clarity;
- complete state history writer.

## Stage N3A: C++ Runtime Backbone

Status:
completed.

Goal:
Create the standard-library C++ runtime scaffold, executable entrypoint,
engine shell, state types, writer contracts, config skeleton, factor registry
placeholder, run manifest placeholder, dry-run demo, and CMake smoke path.

N3A does not implement mechanization, EKF filtering, innovation factors,
smoothing, final_v23 numerical reproduction, or numerical performance claims.

## Stage N3B: final_v23 / KF-GINS Source Audit and Reproduction Contract

Goal:
Read-only audit of /home/kaiwen/KF-GINS and define N3C reproduction contract.

No algorithm implementation.

## Stage N3C: final_v23-style Reproduction Connection and BY2 Data Contract

Goal:
Connect final_v23/KF-GINS baseline outputs to LegSA-GINS standardized baseline outputs, and define BY2 source-role/path contract.

No proposed solver implementation.

## Stage N3D: Chinese Code Comments and Readability Pass

Goal:
Add Chinese comments to code modules, clarify module responsibility, data roles, frame conventions, and claim boundaries.

No algorithm implementation.

## Stage N3: LegSA-ESKF

Goal:
Implement a legged state-augmented source-aware error-state filter.

## Stage N4: LegSA-GINS C++ Filter Core

Goal:
Implement the first self-owned LegSA-GINS filter core with IMU propagation foundation and receiver-native position/velocity/heading updates.

No raw Doppler, no Go2 priors, no source-aware weighting, no FGO.

## Stage N4E: BY2 Real-Data Input Adapters

Goal:
Create real-data input adapters and source-role manifests for BY2, including receiver-native GNSS status, raw message summaries, trace reference, and Go2 body-state diagnostic source.

No solver performance evaluation.

## Stage N4F: BY2 Filter-Core Diagnostic Trial

Goal:
Run current LegSA-GINS filter core on BY2 real data and generate case_review-style diagnostic evaluation.

No formal performance claim.

## Stage N4G: BY2 Time-Domain and Heading Diagnostics

Goal:
Audit BY2 GNSS/Go2 time-domain usage, Unitree sportmodestate IMU semantics, event-normalized algorithm time, and transverse dual-antenna heading offset candidates.

No physical clock offset claim. No formal heading offset selection. No raw Doppler, Go2 priors, source-aware weighting, LSIM/OIM, or FGO.

## Stage N4H0: Receiver-Native Measurement Floor and Evaluator Sanity

Goal:
Evaluate direct receiver-native GNSS status against trace reference to distinguish input/evaluator issues from filter-core issues.

No proposed solver implementation.

## Stage N4H1: final_v23 Input Source-Chain and Yaw-Generation Audit

Goal:
Audit the two-layer final_v23 input source chain: runtime 15-column .gnss input and upstream generation fields, including gnss1-status position, gnss1-raw UBX-NAV-PVT velocity, and gnss1/gnss2-status A1_dual_diff yaw.

N4H1P:
Add a process_data-compatible input generator that reconstructs final_v23-style
`.gnss` and `.imu` runtime inputs from BY2 upstream fields for baseline/parity
testing only.

N4H1P2:
Match process_data row-retention behavior by keeping `gnss1-status` as the
`.gnss` main table, treating PVT velocity and status yaw as merge-asof
auxiliary fields, applying fill, and reporting coverage.

## Stage N4H2: process_data-Compatible External KF-GINS Replay

Goal:
Use the N4H1P2 real BY2 `.gnss` / `.imu` reconstruction as runtime input for an
external KF-GINS baseline replay, then parse and evaluate outputs.

No proposed solver implementation. No final_v23 parity claim. No trace as
solver input. No generated real-data artifacts committed.

## Stage N4H2C: final_v23 Deep Source and Yaw Config Parity Audit

Goal:
Audit why N4H2 position replay passed while yaw replay failed. Deep audit of
actual final_v23 `input.gnss`, `process_data.py`, run scripts, GNSS loader,
GIEngine yaw/velocity update support, and LegSA vs KF-GINS framework parity.
The yaw-specific checks include `yaw_sign`, `yaw_install_offset_deg`,
`yaw_std_mode`, A1 dual-difference yaw, `yaw_ned = 90 - yaw_body`, trace yaw
convention, and antlever / antenna order.

N4H2C-2 deepens this with actual final_v23 artifact recovery, process_data
runtime-parameter audit, yaw input variant matrix, runtime yaw update audit, and
replay yaw diagnostics.

No full EKF implementation. No trace solver input. No output-only correction.
No formal offset selection without physical antenna-order evidence.

## Stage N4R: official final_v23 Case-Review Reproduction

Goal:
Reproduce official final_v23 case_review metrics and identify yaw evaluator
convention before full framework transplant or factor stacking.

N4R uses actual official artifacts as runtime-only evaluator evidence. It does
not implement proposed solver logic, does not tune yaw, does not use trace as
solver input, and does not make a formal numerical performance claim.

## Stage N4R2: Yaw Evaluator Convention Policy and dual_final_v23 Verification

Goal:
Add a controlled evaluator yaw convention policy and verify the N4R candidate
against dual_final_v23 artifacts before any formal evaluator patch.

N4R2 performs directed dual_final_v23 artifact recovery, dual evaluator parity,
and N4H2 replay profile re-evaluation. It does not modify solver output, does
not relax the yaw gate, does not use trace as solver input, and does not make a
formal numerical performance claim.

## Stage N4R3: dual_final_v23 Manual Artifact Intake and Official Parity Lock

Goal:
Validate a manually provided dual_final_v23 artifact group outside the
repository and lock the official evaluator profile against its official summary
and error_series.

N4R3 does not commit artifact files, does not modify solver output, does not use
trace as solver input, and does not turn near-gate yaw evidence into a formal
pass.

## Stage N4H2C-runtime: Runtime Yaw Update / Config / Source-Version Parity Audit

Goal:
Audit why actual dual_final_v23 yaw passes under the confirmed direct evaluator
profile while N4H2 replay yaw fails under the same formal evaluator.

N4H2C-runtime compares actual and replay input/NAV yaw paths, recovers runtime
config evidence when available, audits current KF-GINS yaw update logic
read-only, and searches yaw update source history for branch/version mismatch
evidence. It is diagnostic only: no solver output modification, no trace solver
input, no yaw-gate relaxation, and no formal performance claim.

## Stage N4H2D: Replay Reference Mapping and Stale Summary Audit

Goal:
Audit why the old N4H2 replay summary reported yaw near 93 deg even though
actual dual_final_v23 NAV and replay NAV are nearly identical.

N4H2D reconstructs the official dual_final_v23 reference from official NAV plus
official error_series, freshly evaluates replay NAV against that reference, and
compares the old summary to the fresh summary. It is evaluation/reference
mapping only: no solver output modification, no trace solver input, no output
correction, no epoch deletion, and no formal proposed solver performance claim.

## Stage N4H2E: dual_final_v23-only Visual Validation

Goal:
Generate a dual_final_v23-only visual validation bundle for fresh replay parity
before treating the numerical result as ready for the next stage.

N4H2E plots trajectory, position error, velocity, attitude, consistency,
observation quality, and summary panels for manual review. It does not draw pure
INS, single-antenna, or multi-line comparison figures; does not modify solver
output; does not commit generated figures; and does not make a formal
performance claim.

## Stage N4H2F: Startup transient and yaw/noise provenance audit

Goal:
Audit the visible startup transient, yaw observation-STD source, and
process_data yaw-noise provenance before PR #15 is considered ready for human
visual review and any N4H3 transition.

N4H2F distinguishes fixed yaw_std observation columns from actual yaw-value
noise injection, treats run_final_mainline degradation batches as provenance
evidence rather than clean nominal proof, and records whether final_v23 nominal
evidence needs a yaw-noise caveat. It does not modify solver output, crop
startup epochs, relax the yaw gate, or make a formal performance claim.

## Stage N4H2G: Clean status-yaw no-noise replay audit

Goal:
Generate and replay a clean status-yaw no-noise/no-outlier/no-outage
process_data-compatible input variant, then evaluate it against the dual
official reference.

N4H2G compares clean replay with the noisy historical dual_final_v23 artifact
and records clean/noisy provenance policy. The clean replay is a reconstructed
clean variant, not a historical exact final_v23 artifact. It is baseline replay
diagnostic evidence only and does not implement proposed solver logic or make a
formal performance claim.

## Stage N4H2G2: Clean replay independence and yaw sensitivity audit

Goal:
Verify that the clean status-yaw replay is a fresh independent rerun and not a
cache/stale-summary artifact before N4H3.

N4H2G2 hashes clean/noisy inputs and replay outputs, forces a fresh clean replay
in a repository-external output root, recomputes summary directly from clean
NAV, and runs a +30 deg yaw-input sensitivity smoke test. It is diagnostic only:
no solver modification, no output correction, no epoch deletion, no trace solver
input, and no formal performance claim.

## Stage N4H3: Controlled final_v23 Reference Import and Transplant Plan

Goal:
Import final_v23/KF-GINS as a controlled reference submodule or record a blocked
import, document provenance and claim boundaries, codify clean/noisy input
provenance, and create the final_v23 to LegSA-v23-core transplant matrix.

N4H3 is planning and governance only. It does not implement proposed solver
logic, raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting, FGO, full EKF,
or performance claims.

## Stage N4H4: LegSA-v23-core Full EKF / Unified Filter Implementation

Goal:
Implement LegSA-owned full EKF / unified filter code for v23-framework parity on
clean status-yaw replay input.

N4H4 must not be a wrapper, must not perform output substitution, must not use
final_v23 outputs as proposed solver input, and must keep trace evaluation-only.
Chinese comments are required for critical functions.

## Stage N4H4A: LegSA-v23-core full-framework foundation

Goal:
Create the LegSA-owned C++ v23-core framework foundation: types, options,
config loader, 7-column `.imu` reader, 15-column `.gnss` reader, runtime engine
class, KF-GINS-style function skeleton, writers, manifest, demo, audit, and
tests.

N4H4A is framework foundation only. It is not a final_v23 wrapper, not
final_v23 output substitution, not complete EKF parity, not raw Doppler, not Go2
prior integration, not LSIM/OIM, not FGO, and not numerical-performance
evidence. The older N4 toy filter remains diagnostic/foundation code rather
than the final backbone.

## Stage N4H4B: Mechanization and EKF propagation fill-in

Goal:
Fill `insPropagation`, `buildFGPhiQd`, and `EKFPredict` math while preserving
N4H4A input/output and claim-boundary contracts.

Status:
completed as N4H4B propagation foundation.

## Stage N4H4B: INS mechanization and EKF propagation

Goal:
Implement LegSA-owned Earth/Rotation math, process_data-compatible IMU
compensation, INS velocity/position/attitude mechanization, 21-state/18-noise
`F/G/Phi/Qd` prediction matrices, EKF covariance prediction, covariance checks,
STD sqrt output, propagation toy dry-run, audit, and tests.

N4H4B is propagation foundation only. It does not implement GNSS measurement
updates, `EKFUpdate`, `stateFeedback`, raw Doppler, Go2 priors, LSIM/OIM,
source-aware weighting, FGO, final_v23 parity, clean replay parity, or
performance claims.

## Stage N4H4C: GNSS updates, EKFUpdate, and stateFeedback

Goal:
Implement GNSS position/velocity/yaw update, EKF measurement update, and error
state feedback after N4H4B prediction propagation is closed.

Status:
completed as N4H4C update-feedback foundation.

N4H4C implements the LegSA-owned loose-coupled measurement update framework
only. It does not implement raw Doppler, Go2 priors, LSIM/OIM, source-aware
weighting, FGO, final_v23 numerical parity, clean replay parity, or performance
claims. N4H4D is the clean replay parity stage.

## Stage N4H4R0: Route reset and source-backed port readiness

Goal:
Freeze PR #21 as the self-written LegSA-v23-core parity failure evidence
branch, keep it open and unmerged, document the route reset, and add
source-backed controlled port readiness checks.

N4H4R0 does not implement solver code, does not copy final_v23 source files,
does not add factors, and does not make a performance claim. final_v23 is not
proposed; it is a reference/backbone source for a controlled port.

## Stage N4H4R1: Controlled source-backed KF-GINS/final_v23 core port

Goal:
Create `cpp/legsa_v23_port_core` as a provenance-preserving port of the
final_v23/KF-GINS core backbone.

N4H4R1 ports the backbone before factor extensions. It does not implement raw
Doppler, Go2 priors, LSIM/OIM, source-aware weighting, FGO, or paper
performance claims.

## Stage N4H4R1: Source-backed port-core foundation

Goal:
Add the minimal compileable `cpp/legsa_v23_port_core` foundation with
provenance headers, port manifest, CMake targets, toy dry-run, docs, audits,
and tests.

N4H4R1 does not attempt real clean parity and does not claim performance.

## Stage N4H4R2: Complete source-backed mathematical port

Goal:
Complete the source-backed KF-GINS/final_v23 math and runtime port inside
`cpp/legsa_v23_port_core`.

Status:
completed as N4H4R2 math port foundation.

N4H4R2 implements the backbone math and runtime chain only. It does not run real
clean parity, does not implement raw Doppler, Go2 priors, LSIM/OIM,
source-aware weighting, FGO, or performance claims.

## Stage N4H4R3: Clean replay parity

Goal:
Run clean status-yaw replay parity with the source-backed port-core backbone and
write an honest pass/fail gap report.

## Stage N4H4R2: Complete source-backed mathematical port

Goal:
Close the source-backed mathematical backbone in `cpp/legsa_v23_port_core` with
config/unit conversion, readers, INS mechanization, GIEngine update routing,
EKF predict/update, feedback, writers, audits, tests, and synthetic math smoke.

R2 synthetic output is not parity evidence.

## Stage N4H4R3: Clean replay parity for source-backed port

Goal:
Run the clean replay against external clean and dual_final_v23 references and
report pass/fail honestly.

## Stage N4H4R3: Source-backed port clean replay parity

Goal:
Run the source-backed `cpp/legsa_v23_port_core` on clean status-yaw inputs,
freshly evaluate against the dual final_v23 official reference, compare against
external clean replay, and publish an engineering backbone parity or gap-screen
decision.

N4H4R3 is not a proposed factor result and does not make a paper performance
claim.

## Stage N4H4E: Visual validation for source-backed port

Goal:
Generate runtime-only visual validation figures and reports for source-backed
port-core clean replay results.

N4H4E plots only source-backed port, dual_final_v23, and evaluation reference
roles. It does not draw pure INS or single-antenna comparisons, does not commit
generated figures, does not add raw Doppler, Go2, LSIM/OIM, source-aware
weighting, or FGO factors, and does not make a paper performance claim.

## Stage N4H4E1: STD unit consistency and visual plot semantics fix

Goal:
Audit source-backed port and dual_final_v23 STD units, fix common-unit writer
or visual-loader policy if evidence requires it, and regenerate corrected
scatter/error-vector and 3sigma figures.

N4H4E1 is a visual semantics and STD consistency fix only. It does not modify
solver logic, tune by trace, delete epochs, add raw Doppler, Go2, LSIM/OIM,
source-aware weighting, or FGO factors, and does not make a paper performance
claim.

## Stage N4H4R3A: Update timeline and overlap parity audit

Goal:
Audit whether R3 update count should be compared with total GNSS rows or only
effective IMU/GNSS/config overlap rows, and apply a source-backed runtime-loop
compatibility fix only if timeline evidence supports it.

R3A diagnostics are not performance results and do not add proposed factors.

## Stage N4H4R3B: Over-close and reference-independence audit

Goal:
Audit the R3A metric-gate-pass but external-closeness-failed result for
measurement-copy, reference-independence, covariance/config parity, and
residual/gain over-tightness before any visual validation or performance claim.

R3B diagnostics are not performance results and do not add proposed factors.

## Stage N4H4R3C: Metric namespace and parity-vs-absolute evaluation split

Goal:
Split source-backed port metrics into `port_vs_final_v23_nav_parity`,
`port_vs_trace_absolute`, and `final_v23_vs_trace_absolute` before any visual
validation decision.

R3C corrects the R3B external-closeness interpretation by preventing
port-vs-final_v23 parity metrics from being compared directly with absolute
trace/reference metrics. R3C does not modify solver logic, tune, delete epochs,
perform output-only correction, add factors, or make a paper performance claim.

## Stage N5: Raw Doppler factor foundation

Goal:
Begin raw Doppler factor foundation only after N4H4E visual validation and
manual visual review support moving forward.

## Stage N5A: RTKLIB-backed raw Doppler auxiliary factor activation

Goal:
Activate the first proposed factor after backbone parity: a RAWX doMes based
raw-Doppler-derived velocity auxiliary factor with RTKLIB/ephemeris discovery,
provider readiness gates, C++ EKF integration, toy activation, and real
diagnostic trial boundary reporting.

Boundaries:
NAV-PVT velocity is not raw Doppler. `.gnss vn/ve/vd` remains baseline
receiver-native velocity. RAWX plus satellite-state provider is required. If
provider is missing, raw Doppler must not be reported as applied. No trace
solver input, no final_v23 output solver input, no LSIM/OIM, no Go2 prior, no
FGO, and no paper performance claim.

## Stage N5B: RTKLIB Doppler velocity provider and real raw Doppler EKF activation

Goal:
Follow the N5A provider blocker by building a runtime-only RTKLIB Doppler
velocity helper/provider, generating `RAW_DOPPLER_VELOCITY_FACTORS.csv`, and
feeding it into the source-backed EKF as a real auxiliary velocity factor.

Activation requires `raw_doppler_update_count > 0`. RTKLIB position solution,
NAV-PVT velocity, `.gnss vn/ve/vd`, trace, and final_v23 output cannot be solver
input.

## Stage N5C: Raw Doppler ablation protocol

Goal:
After N5B real activation, run a controlled ablation protocol that separates the
baseline receiver-native velocity factor, the raw Doppler auxiliary velocity
factor, diagnostic velocity-isolation variants, and R-scale diagnostic screen.

N5C is diagnostic engineering evidence only. It does not tune from trace, delete
epochs, perform output-only correction, claim paper performance, or claim
outperforming final_v23.

## Stage N5D: Raw Doppler visual validation and velocity-stress protocol

Goal:
Continue from the N5C ablation-ready decision by adding raw Doppler factor
visual validation, receiver-native velocity stress variants, diagnostic-only
stress comparisons, visual sanity checks, and a next-stage decision report.

N5D does not delete epochs, tune from trace, perform output-only correction,
claim paper performance, claim outperforming final_v23, implement Go2 priors,
implement LSIM/OIM, implement source-aware weighting, or implement FGO.

## Stage N5D1: Visual data coverage and raw Doppler spike audit

Goal:
Repair N5D visual validation by requiring plotted sample coverage, regenerating
non-empty clean ablation plots, auditing raw Doppler velocity spikes
epoch-by-epoch, fixing raw-vs-receiver velocity semantics, and de-duplicating
stress evidence pairs.

N5D1 does not change solver math, tune gates, delete epochs, apply output-only
correction, claim paper performance, claim outperforming final_v23, implement
Go2 priors, implement LSIM/OIM, implement source-aware weighting, or implement
FGO.

## Stage N6A: Source-aware LSIM/OIM weighting foundation

Goal:
Implement source-aware LSIM/OIM weighting in the source-backed port-core EKF.
N6A must apply solver-visible source metadata and innovation-based conservative
R scaling for receiver position, receiver velocity, dual-antenna yaw, and raw
Doppler velocity updates.

N6A emits source-aware traces, clean/stress diagnostic ablations, spike-response
sentinel reports, and a decision report. It does not use trace or final_v23
output for weighting, does not shrink R below baseline, does not implement Go2
priors or FGO, and does not make paper performance claims.

## Stage N6B: Source-aware policy refinement

Goal:
Refine N6A over-aggressive LSIM/OIM R scaling while preserving real EKF
activation. OIM must use innovation covariance `S=HPH^T+R`, LSIM must stay
metadata-only, source caps must be conservative, N5D1 spike response must remain
after-run audit only, and no paper performance claim is allowed.

## Stage N6B1: Source-aware visual validation

Goal:
Validate the N6B source-aware LSIM/OIM policy with runtime-only figures and
plotted-data coverage checks. N6B1 checks clean curves, R-scale traces, spike
response, stress variants, and mandatory figure non-emptiness. It does not
modify solver math, tune from trace/final_v23 output, delete epochs, add Go2
priors, add FGO, or make paper performance claims.

## Stage N7A: Go2 body-state weak prior review

Goal:
Parse Go2 body-state / sportmodestate high-level state, verify source integrity,
time alignment, quaternion/rpy consistency, and frame contracts, then activate
one conservative roll/pitch weak attitude prior in the source-backed EKF.

Boundaries:
Go2 body-state is not truth. Go2 position and velocity priors are disabled by
default in N7A. Go2 yaw prior is disabled in N7A. No trace/final_v23 output is
used for Go2 prior construction. N7A does not implement FGO, output-only
correction, paper performance claims, or outperform-final_v23 claims.

## Stage N7B: Go2 velocity/contact readiness

Goal:
Use N7A body-state evidence to audit Go2 contact labels, motion state, velocity
quality, yaw-rate readiness, and cross-source consistency before any later Go2
velocity/contact weak prior.

N7B is readiness only. Go2 position is not truth. Go2 velocity is not truth.
Cross-source velocity comparison is not truth error. Contact thresholds are
diagnostic defaults and do not use trace. N7B does not activate Go2 velocity
prior, does not activate Go2 yaw prior, does not implement FGO, does not delete
epochs, and makes no paper performance or outperform-final_v23 claim.

## Stage N7B2: Go2 contact threshold review

Goal:
Review Go2 foot-force and foot-speed distributions, build a diagnostic
contact-state v2 candidate, apply fixed window smoothing, and evaluate
contact-conditioned velocity source consistency before any N7C activation.

N7B2 is contact threshold readiness only. Thresholds are derived from Go2 field
distributions, not trace, final_v23 output, or navigation metrics. Go2 velocity
is not truth and contact-conditioned velocity comparison is not truth error.
N7B2 does not activate Go2 velocity prior, does not activate Go2 yaw prior,
does not implement FGO, does not delete epochs, and makes no paper performance
or outperform-final_v23 claim.

## Stage N7C: Go2 velocity/contact weak-prior activation or N8A FGO preparation

Goal:
Proceed only from the N7B2 decision report. If contact and velocity readiness
passes, review a future conservative Go2 velocity/contact weak prior. If
yaw-speed is the stronger signal, review a future yaw-rate weak prior. If
extended Go2 priors remain weak, prepare N8A no-feedback FGO foundation instead.

N7C is not started in N7B2.

## Stage N6: Source-Aware Weighting

Goal:
Implement source-aware measurement weighting using GNSS status, Doppler residual, Go2 body-state, and support integrity cues.

## Stage N7: No-Feedback Fixed-Lag Smoother

Goal:
Implement fixed-lag smoothing without feedback to the filter.

## Stage N8: Ablation and Degraded-GNSS Evaluation

Goal:
Run proposed vs pure INS, single-antenna GNSS/INS, final_v23-style baseline, and ablations.

## Stage N9: Paper Package

Goal:
Generate paper-ready figures, tables, manifests, and claim-audit reports.
