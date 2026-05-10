# LegSA-GINS

Legged State-Augmented Source-Aware GNSS/INS Smoothing.

LegSA-GINS is a clean research repository for a new paper-oriented GNSS/INS fusion framework for high-vibration quadruped robots.

## Project Positioning

This repository is a new project.

It is not a continuation of LegTC-FGO.

LegTC-FGO is treated as a frozen evidence/prototype/failure-boundary project and will be restarted later as a separate paper after new high-quality data collection.

## Backbone

The project uses a final_v23-style mature GNSS/INS backbone as:

- a mature implementation reference;
- a strong baseline;
- an evaluator sanity oracle.

final_v23 is not the proposed method.

## Proposed Direction

LegSA-GINS will be developed as:

- LegSA-ESKF: legged state-augmented source-aware error-state filtering;
- raw Doppler auxiliary factors;
- Go2 yaw-rate and attitude weak priors;
- gait/contact/support integrity features;
- source-aware measurement weighting;
- no-feedback fixed-lag smoothing;
- reference-uncertainty-aware evaluation.

## Phase Status

Current completed phase:

N5B RTKLIB Doppler velocity provider and real activation.

Current working phase:

N5C raw Doppler ablation protocol.

N1 only provides the final_v23-style baseline wrapper, manifest writer, oracle audit, and separation tests. It does not implement the proposed LegSA-GINS solver or any numerical performance claim.

N2 builds frame utilities, writer contracts, manifest contracts, evaluator utilities, and audits. N2 does not implement the proposed solver.

N3A adds a C++ runtime skeleton with dry-run NAV/STD/EVAL_NAV output contracts. It does not implement a validated navigation solver, final_v23 reproduction, or any numerical performance claim.

N3B reads external source only for audit and reproduction planning. N3B does not copy external source into LegSA-GINS. N3B does not implement proposed factors or numerical performance evaluation.

N3C creates baseline output parsers/standardizers and a BY2 data source-role contract only. N3C does not implement proposed factors or numerical performance claims.

N3D improves code readability with Chinese comments only. N3D does not implement new algorithms or make performance claims.

N4 implements a toy-run-capable receiver-native position/velocity/heading filter core only. N4 does not implement raw Doppler, Go2 priors, source-aware weighting, or FGO smoothing.

N4E standardizes BY2 receiver-native GNSS status, raw-message summaries, trace evaluation-only reference, and Go2 body-state diagnostic data. N4E does not implement raw Doppler, Go2 priors, source-aware weighting, or FGO.

N4F runs the current filter core on BY2 real data for diagnostic evaluation only. It does not implement raw Doppler, Go2 priors, source-aware weighting, or FGO.

N4G audits BY2 time-domain usage, Unitree sportmodestate IMU semantics, event-normalized `algo_time_sec`, and transverse dual-antenna heading candidates. N4G does not claim hardware clock sync, physical time offset, formal heading offset, or numerical performance.

N4H0 evaluates direct BY2 receiver-native GNSS status against trace reference to separate input/evaluator issues from filter-core issues. N4H0 does not implement proposed solver logic or make proposed solver performance claims.

N4H1 audits the two-layer final_v23 input source chain: runtime 15-column `.gnss` input and upstream generation fields. N4H1P/N4H1P2 reconstruct process_data-compatible `.gnss` and `.imu` inputs for baseline/parity testing only, with row-retention coverage reporting. N4H1 does not implement proposed solver logic or make performance claims.

N4H2 runs those process_data-compatible BY2 runtime inputs through the external KF-GINS baseline executable, parses NAV/STD/IMU_ERR outputs, and writes an evaluation-only replay report. N4H2 does not claim final_v23 parity or proposed LegSA-GINS performance.

N4H2C is the decision-driven final_v23 deep source and yaw-config parity audit after N4H2: position replay passed, yaw replay failed, so the next work audits the actual final_v23 runtime `input.gnss`, process_data generation logic, run/config evidence, GNSS loader and GIEngine velocity/yaw support, KF-GINS core flow, and the current LegSA vs KF-GINS framework gap before any full EKF stage.

N4R reproduces official final_v23 case-review metrics from runtime-only
artifacts and identifies yaw evaluator convention before runtime yaw-config
repair, full KF-GINS-style EKF reconstruction, or factor stacking. N4R remains
diagnostic evaluator parity only and does not make proposed solver performance
claims.

N4R2 adds a controlled yaw evaluator convention policy, directed
dual_final_v23 artifact recovery, dual artifact evaluator parity, and N4H2
replay profile re-evaluation. The yaw candidate remains diagnostic until
dual_final_v23 parity confirms it, and a yaw result slightly above 2 deg remains
near-boundary rather than a formal pass.

N4R3 intakes a manually provided dual_final_v23 artifact group outside the
repository, confirms its summary envelope, locks the official evaluator profile,
and re-evaluates N4H2 replay under controlled profiles. N4R3 does not commit
artifact files, does not modify solver output, and does not make a performance
claim.

N4H2C-runtime audits why actual dual_final_v23 yaw passes while the N4H2 replay
yaw fails under the confirmed direct evaluator profile. It compares actual and
replay input/NAV yaw paths, runtime config evidence, current yaw update source,
and source history. It is diagnostic only and does not modify solver output.

N4H2D reconstructs the official dual_final_v23 evaluation reference and freshly
evaluates N4H2 replay NAV against it. It audits stale or wrong-reference old
summary evidence and does not modify solver output or make proposed solver
performance claims.

N4H2E generates a dual_final_v23-only visual validation bundle for the fresh
N4H2 replay parity result. It plots trajectory, position errors, velocity,
attitude, consistency, observation quality, and summary panels for manual review.
N4H2E does not modify solver output, does not commit generated figures, and does
not make formal paper performance claims.

N4H2F audits the startup visual transient, distinguishes observation yaw STD
from yaw-noise injection, and checks process_data / final mainline provenance
for the dual_final_v23 replay evidence. It does not crop epochs, relax gates,
modify solver output, or turn visual diagnostics into formal performance claims.

N4H2G reconstructs a clean status-yaw no-noise/no-outlier/no-outage replay
variant and evaluates it against the dual official reference. It compares clean
and noisy provenance while preserving that the historical noisy artifact is not
a clean nominal baseline. N4H2G does not modify solver output or make proposed
solver performance claims.

N4H2G2 checks that the clean replay is an independent fresh rerun rather than a
cache or stale-summary artifact. It hashes clean/noisy inputs and outputs,
recomputes clean summary from NAV, and runs a diagnostic yaw-input sensitivity
probe. N4H2G2 does not modify solver output or make proposed solver performance
claims.

N4H3 imports final_v23/KF-GINS as a controlled reference submodule and creates
the LegSA-v23-core transplant matrix, provenance policy, boundary docs, and
N4H4 implementation contracts. N4H3 does not copy external source into the
superproject, does not implement proposed solver logic, and does not make
performance claims.

N4H4A creates the LegSA-owned v23-core C++ full-framework foundation with
types, options, 7-column `.imu` reader, 15-column `.gnss` reader, config loader,
KF-GINS-style engine function skeleton, writers, manifest, demo, audit, and
tests. N4H4A is not final_v23 reproduction, not final_v23 output substitution,
not full EKF parity, and not performance evidence.

N4H4B implements the LegSA-owned v23-core INS mechanization and EKF prediction
foundation, including Earth/Rotation utilities, IMU compensation, velocity,
position, attitude propagation, `F/G/Phi/Qd`, covariance prediction, covariance
checks, STD sqrt output, propagation toy dry-run, audit, and tests. N4H4B does
not implement GNSS measurement updates, `EKFUpdate`, `stateFeedback`, final_v23
parity, or performance claims.

N4H4C implements the LegSA-owned v23-core GNSS position/velocity/yaw
measurement update framework, scheme_C yaw gate, Joseph-form `EKFUpdate`,
error-state `stateFeedback`, update-branch routing in `newImuProcess`, update
toy dry-run, audit, and tests. N4H4C does not implement raw Doppler, Go2
priors, LSIM/OIM, FGO, final_v23 numerical parity, or performance claims.

N4H4R0 freezes PR #21 as a self-written LegSA-v23-core parity failure evidence
branch, keeps PR #21 open and unmerged, and resets the route toward a
source-backed controlled final_v23/KF-GINS core port. N4H4R0 does not implement
solver code, does not copy final_v23 source files, does not add factors, and
does not make performance claims. final_v23 is not proposed.

N4H4R1 adds `cpp/legsa_v23_port_core` as a controlled source-backed port-core
foundation with provenance headers, manifest, CMake targets, toy dry-run, docs,
audits, and tests. N4H4R1 does not run clean replay parity, does not add
proposed factors, and does not make performance claims. The old
`cpp/legsa_v23_core` remains a diagnostic/self-written attempt.

Current completed phase:
N4H4E1 STD unit and visual validation fix.

Current working phase:
N5A RTKLIB-backed raw Doppler auxiliary factor activation.

N4H4R2 completes the source-backed port-core math surface inside
`cpp/legsa_v23_port_core`: config/unit conversion, loaders, INS mechanization,
GIEngine, GNSS updates, EKF predict/update, feedback, writers, and synthetic
math smoke. N4H4R2 does not run real clean replay parity, does not add proposed
factors, and does not make performance claims.

N4H4R3C splits port-vs-final_v23 NAV parity from trace/reference absolute
evaluation before visual validation. It does not modify solver logic, tune,
delete epochs, add factors, or make paper performance claims.

N4H4E generates source-backed-port visual validation figures and reports for
manual engineering review. It only compares source-backed port, dual_final_v23,
and evaluation reference roles; it does not draw pure INS or single-antenna
comparisons, commit generated figures, add factors, or make paper performance
claims.

N4H4E1 audits STD unit consistency and fixes visual plot semantics before any
N5 transition. It corrects source-backed port STD writer common-unit output,
regenerates scatter/error-vector and 3sigma diagnostic figures, keeps runtime
figures untracked, and does not modify solver logic, tune, delete epochs, or
make performance claims.

N5A is the first proposed factor integration attempt after source-backed
backbone parity. It adds raw GNSS scans, RTKLIB/ephemeris discovery, RAWX
`doMes` parsing, provider-backed Doppler velocity factor gates, and a C++ EKF
auxiliary velocity-factor path. NAV-PVT velocity is not raw Doppler, `.gnss`
`vn/ve/vd` remains baseline receiver-native velocity, and provider-missing
evidence blocks real activation instead of being reported as an applied factor.
N5A makes no paper performance claim and no outperform final_v23 claim.

N4H4 will be the LegSA-owned full EKF / unified filter implementation stage.
It must not use final_v23 outputs as proposed solver input and must keep trace
evaluation-only.

## Strict Phase-I Non-goals

- No RTK fixed claim.
- No carrier ambiguity fixing.
- No self raw heading claim.
- No full raw pseudorange tight coupling claim.
- No Neural Gate formal module.
- No FGO feedback.
- No full pose FGO claim.
- No full leg odometry claim.
- No trace tuning.
- No output-only correction.
- No deletion of bad epochs to pass metrics.
- No final_v23 output substitution.
- No raw data committed to Git.
