# CLAIM_BOUNDARY.md

## Allowed Phase-I Claims

The project may claim, if supported by experiments:

- a final_v23-style mature GNSS/INS backbone is used as the baseline/backbone reference;
- final_v23-style baseline wrapper may be used as strong baseline and evaluator oracle;
- a new LegSA-ESKF framework is developed for legged-state augmented source-aware filtering;
- raw Doppler auxiliary factors are used;
- Go2 yaw-rate and attitude can be used as weak priors through frame-safe adapters;
- gait/contact/support indicators can be used for source-aware integrity weighting;
- no-feedback fixed-lag smoothing is used;
- reference-uncertainty-aware evaluation is used;
- no trace tuning;
- no output-only correction;
- no deletion of bad epochs for passing metrics.

Allowed N2 infrastructure statement:

- Frame, writer, manifest, and evaluator utilities may be implemented in N2.

Allowed N3A infrastructure statement:

- A C++ runtime skeleton may be implemented in N3A.
- N3A may write dry-run NAV, STD, EVAL_NAV, and RUN_MANIFEST contract artifacts.

Allowed N3B source-audit statement:

- External final_v23 / KF-GINS source may be audited for baseline reproduction planning.
- N3B may document source maps, runtime flow, output contracts, and reproduction requirements.

Allowed N3C reproduction-connection statement:

- final_v23/KF-GINS baseline outputs may be parsed and standardized for baseline evaluation.
- BY2 local data paths may be probed through ignored local config for source-role validation.

Allowed N3D readability statement:

- N3D may add Chinese comments and readability documentation.

Allowed N9C0 global consolidation statement:

- N9B staged execution is complete through N9C0 global consolidated precheck.
- N9C0 may be cited as the current consolidation source of truth for staged BY2 degradation evidence.
- The N9C0 active final-only metrics table contains 825 rows.
- Batch 6 selected mixed cases completed.
- Batch 5 core module-disable completed while module-stress remains deferred.
- final_v23 is integrated only as `external_reference_baseline`.
- N9C1 consolidated figure generation readiness passed.
- N9C0A may update context docs after N9C0, but it must not run N9C1 or make paper claims.

Allowed N9E logging-blocked statement:

- N9E may state that active nine-factor FGO/legged logger review completed.
- N9E may state that current `LegSA_full_EKF` lacks accepted row-level active FGO residual/cost evidence for all nine factors.
- N9E must keep `complete_nine_factor_FGO_claim=false` and `ready_for_paper_claims=false`.

Allowed N9F design materialization statement:

- N9F may state that the active nine-factor FGO design package is complete.
- N9F may state that current evidence requires a new active nine-factor FGO algorithm design before representative runs.
- N9F may state that current `LegSA_full_EKF` evidence is provider/update-level or candidate/no-feedback diagnostic evidence, not accepted current active nine-factor FGO residual/cost evidence for all nine factors.
- N9F may create export-clean design material under `<BY2_N9B2_FULL_MATRIX_ROOT>/N9F_EXPORT_CLEAN_DESIGN_PACKAGE`.
- N9F may set `ready_for_implementation_review=true`.
- N9F must keep `ready_for_paper_claims=false`, `ready_for_N9B2_execution=false`, and `ready_for_full_N9B_execution=false`.

Allowed N9F6A/N9F7 source-audit and design-package statement:

- N9F6A may state that a source-code forensic audit found robot kinematics/contact/legged modeling in provider, diagnostic, offline no-feedback, and candidate factor code.
- N9F6A may state that active `LegSA_full_EKF` uses provider-dependent Go2 weak attitude / horizontal velocity EKF updates and selected-feedback EKF pseudo-measurements, but not a complete active nine-factor FGO solver.
- N9F7 may state that Path C was taken and a data-provider / substantial algorithm design package was produced.
- N9F7 may set `ready_for_algorithm_design_review=true`.
- N9F7 must set `ready_for_implementation_review=false` unless a later human-approved design review explicitly authorizes implementation.
- N9F7 must keep `ready_for_paper_claims=false`, `ready_for_N9B2_execution=false`, and `ready_for_full_N9B_execution=false`.
- N9F7 must not claim active row-level nine-factor FGO residual, Jacobian, or cost evidence from provider/update counts or candidate no-feedback logs.

Allowed N9F7A/N9G0 Git-boundary and manual-design-review statement:

- N9F7A may state historically that local publish was blocked until the existing non-doc ahead commit boundary was reviewed by the human.
- N9G0 may state that a manual design review package exists for a future, separate `LegSA_9F_FGO_EKF` candidate.
- N9G0 may define state/window, nine-factor, residual/matrix, provider, logger, roadmap, validation, and risk requirements.
- N9G0 must state that `LegSA_9F_FGO_EKF` remains design-only and is not implemented in this stage.
- N9G0 must state that `LegSA_full_EKF` remains the verified EKF/feedback algorithm and is not relabeled.
- N9G0 must keep `complete_nine_factor_FGO_claim=false`, `ready_for_paper_claims=false`, `ready_for_N9B2_execution=false`, and `ready_for_full_N9B_execution=false`.
- N9G0 must not claim active factor residual, Jacobian, cost, normal-equation, or feedback-producer evidence until a later implementation and validation stage produces real logs.

Allowed N9G0A/N9G1A context-lock statement:

- N9G0A may state that the Git boundary was resolved and PR #52 head is synced to `9ceba928`.
- N9G0A must not treat PR #52 head sync as merge, closure, tag, or paper-claim authorization.
- N9G1A may state that N9G1 is split into `N9G1A_CONTEXT_LOCK_BEFORE_LEGSA_9F_IMPLEMENTATION` and later `N9G1B_PHASE1_PROVIDER_FACTOR_LOGGER_NORMAL_SMOKE_ONLY`.
- N9G1A may state that `LegSA_full_EKF` remains the current verified EKF/feedback algorithm.
- N9G1A may state that `LegSA_9F_FGO_EKF` is a separate new candidate.
- N9G1A must keep `complete_nine_factor_FGO_claim=false`, `ready_for_paper_claims=false`, `ready_for_N9B2_execution=false`, and `ready_for_full_N9B_execution=false`.
- N9G1B may state that the separate `LegSA_9F_FGO_EKF` candidate identity/config, provider/factor audit helper, active-FGO logger schema, legged diagnostic logger schema, and normal-smoke safety gate exist.
- N9G1B may state that normal smoke was not run because provider contracts are blocked, the active nine-factor FGO backend is unavailable, and candidate solver execution is disabled.
- N9G1B must keep `complete_nine_factor_FGO_claim=false`, `ready_for_N9G2_representative_validation=false`, `ready_for_paper_claims=false`, `ready_for_N9B2_execution=false`, and `ready_for_full_N9B_execution=false`.
- N9G1C-E may state that the locked normal clean source and core provider contracts were resolved for the separate `LegSA_9F_FGO_EKF` candidate.
- N9G1C-E may state that provider contracts are partial accepted: GNSS position/velocity/yaw, Raw Doppler, Go2 joint/attitude/horizontal velocity, and same-case feedback observations are resolved, while candidate legged providers remain candidate-only or aggregate evidence.
- N9G1C-E may state that the active nine-factor FGO backend remains unavailable, candidate solver execution remains disabled, and normal smoke was not run.
- N9G1C-E must keep `complete_nine_factor_FGO_claim=false`, `ready_for_N9G2_representative_validation=false`, `ready_for_paper_claims=false`, `ready_for_N9B2_execution=false`, and `ready_for_full_N9B_execution=false`.
- N9G2 may be described as the later representative validation stage.
- N9G3/N9G4 may be described as later full matrix/replot/report stages if applicable.
- N9G1A and N9G1B must not claim representative degradation/full-matrix validation.
- N9G1C-E must not claim representative degradation/full-matrix validation or normal-smoke success.

Allowed N4 filter-core statement:

- N4 may implement LegSA-GINS C++ filter core with receiver-native position, velocity, and heading updates.

Allowed N4E input-adapter statement:

- N4E may create BY2 input adapters and source-role manifests.
- N4E may standardize receiver-native GNSS status and Go2 body-state diagnostic data.

Allowed N4F diagnostic-trial statement:

- N4F may generate diagnostic BY2 filter-core trial metrics.

Allowed N4G diagnostic statement:

- N4G may generate event-normalized BY2 diagnostic candidates for time-domain, Unitree IMU semantics, and transverse dual-antenna heading review.

Allowed N4H0 diagnostic statement:

- N4H0 may generate diagnostic receiver-native measurement-floor metrics for BY2.

Allowed N4H1 diagnostic statement:

- N4H1 may audit the final_v23 runtime `.gnss` input source chain and yaw generation chain.
- N4H1P may reconstruct process_data-compatible `.gnss` and `.imu` runtime inputs for baseline/parity testing only.
- N4H1P2 may report row-retention coverage for process_data-compatible input reconstruction.

Allowed N4H2C diagnostic statement:

- N4H2C may audit actual final_v23 runtime input, process_data generation evidence, external KF-GINS runtime source support, and LegSA vs KF-GINS framework parity.
- N4H2C is diagnostic source/input/runtime audit only.
- N4H2C must not be described as proposed solver implementation.
- N4H2C must not use trace as solver input.
- N4H2C must not formal-select yaw offset without physical or actual-input evidence.
- N4H2C yaw variant matrix is diagnostic-only.
- Trace yaw must not become formal solver input.
- Auto-best install based on trace is diagnostic-only unless supported by physical or actual final_v23 input evidence.
- Missing actual final_v23 artifacts must be reported as evidence_missing.

Allowed N4R diagnostic statement:

- N4R may reproduce official final_v23 case-review summary and error_series
  definitions for evaluator parity.
- N4R is evaluator-parity diagnostic only.
- N4R metrics are not proposed solver performance.
- Official artifacts are not solver input.
- Trace remains evaluation-only.
- Yaw transform candidates are evaluator diagnostics, not solver tuning.

Allowed N4H4A framework statement:

- N4H4A may create the LegSA-owned v23-core C++ full-framework foundation.
- N4H4A may define types, options, config loader, 7-column `.imu` reader,
  15-column `.gnss` reader, runtime engine skeleton, writers, manifest, audit,
  tests, and toy dry-run.
- N4H4A may expose KF-GINS-style function names as skeleton hooks only.
- Critical C++ functions require Chinese comments.
- Factor flags remain false in N4H4A.

Allowed N4H4B propagation statement:

- N4H4B may implement LegSA-owned Earth/Rotation math, IMU compensation, INS
  mechanization, `F/G/Phi/Qd`, EKF prediction, covariance checks, STD sqrt
  output, propagation toy dry-run, audit, and tests.
- N4H4B is propagation foundation only.
- N4H4B does not implement GNSS measurement updates.
- N4H4B does not implement `EKFUpdate` or `stateFeedback`.
- N4H4B factor flags remain false.

Allowed N4H4C update-feedback statement:

- N4H4C may implement LegSA-owned GNSS position/velocity/yaw measurement
  updates, scheme_C yaw gate, Joseph-form `EKFUpdate`, error-state
  `stateFeedback`, update-branch routing in `newImuProcess`, update toy
  dry-run, audit, and tests.
- N4H4C implements measurement update framework but not parity claim.
- N4H4C toy update is not performance evidence.
- Raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting, FGO, and FGO
  feedback remain disabled.
- final_v23 outputs are not solver input.
- Clean replay parity remains N4H4D.

Allowed N4H4R0 route-reset statement:

- N4H4R0 may freeze PR #21 as self-written v23-core parity failure evidence.
- PR #21 may remain open and unmerged as an evidence branch.
- N4H4R0 may select a source-backed controlled final_v23/KF-GINS core port as
  the next route.
- Source-backed port readiness, provenance, license, and module-manifest
  checks may be added.
- The ported final_v23/KF-GINS backbone is not paper novelty.
- final_v23 is not proposed.
- Factor claims start only after backbone parity.

Allowed N4H4R1 source-backed port-core statement:

- N4H4R1 may create `cpp/legsa_v23_port_core` as a controlled source-backed
  port-core foundation.
- N4H4R1 may add CMake targets, toy dry-run, provenance headers, port manifest,
  docs, audits, and tests.
- Source-backed port-core is backbone, not novelty.
- Ported core must preserve provenance.
- N4H4R1 toy run is not performance evidence.
- The old `cpp/legsa_v23_core` remains a diagnostic attempt.
- No factor claims until port parity.

Allowed N4H4R3C metric namespace statement:

- N4H4R3C may split source-backed port metrics into parity and absolute
  namespaces for decision safety.
- Port-vs-final_v23 parity metrics are not absolute performance metrics.
- Absolute trace/reference evaluation must be separated from parity-to-baseline
  evaluation.
- Metric gate pass alone is insufficient without namespace clarity.
- N4H4R3C reports are engineering backbone diagnostics only.

Allowed N4H4E visual validation statement:

- N4H4E may generate source-backed-port visual validation figures and reports
  for engineering review only.
- N4H4E visual validation is engineering evidence only.
- N4H4E may compare source-backed port, dual_final_v23, and evaluation
  reference roles.
- Figures are runtime-only and are not committed.
- Manual visual review is required before N5.
- No paper performance claim.
- No outperform final_v23 claim.
- No proposed factor claim.
- No raw Doppler, Go2 prior, LSIM/OIM, source-aware weighting, or FGO claim.

Allowed N4H4E1 STD/plot fix statement:

- N4H4E1 may fix STD writer common-unit output and visual-loader/plot
  semantics when unit evidence requires it.
- N4H4E1 visual fixes are not solver performance improvements.
- STD/3sigma figures require unit consistency.
- Vector error clouds must not be misread as trajectories.
- Figures and runtime reports are not committed.
- Manual visual review is required before N5.
- No paper performance claim.
- No outperform final_v23 claim.
- No proposed factor claim.

Allowed N5A raw Doppler activation statement:

- N5A is the first proposed factor integration attempt after backbone parity.
- Raw Doppler must be satellite-level Doppler, not NAV-PVT velocity.
- `.gnss vn/ve/vd` remains baseline receiver-native velocity.
- Raw Doppler solver activation requires RAWX and satellite-state provider.
- RTKLIB is allowed as mature provider/tool but must be runtime-only.
- If provider is missing, raw Doppler must not be reported as applied.
- No trace solver input.
- No final_v23 output solver input.
- No output-only correction, no tuning, no epoch deletion.
- No LSIM/OIM, Go2 prior, or FGO claim in N5A.
- No paper performance claim.
- Diagnostic trial is not paper performance.

Allowed N6A source-aware LSIM/OIM weighting statement:

- N6A source-aware LSIM/OIM weighting is diagnostic engineering evidence.
- LSIM/OIM uses solver-visible metadata and innovations only.
- No trace or final_v23 output is used for weighting.
- N6A default policy only inflates R; it does not shrink R below baseline.
- N5D1 spike epochs are evaluation sentinels only, not tuning inputs.
- Stress variants are diagnostic-only.
- No paper performance claim.
- No outperform final_v23 claim.
- No Go2 prior, FGO, or smoothing claim in N6A.
- Source-aware weighting changes EKF measurement R, not output.

Allowed N6B source-aware policy refinement statement:

- N6B refines source-aware policy after N6A over-aggressive R scaling.
- N6B uses innovation covariance `S=HPH^T+R` for OIM.
- N6B does not use trace or final_v23 output for weights.
- N6B does not hardcode spike times into solver policy.
- N6B does not shrink R below baseline.
- Stress variants are diagnostic-only.
- No paper performance claim.
- No outperform final_v23 claim.
- No Go2 prior, FGO, or smoothing claim in N6B.

Allowed N8C2 FGO factor activation review statement:

- N8C2 checks factor activation, whitening, and contribution.
- Raw Doppler no-effect is reviewed before claim.
- Smoothness dominance is reviewed component-wise.
- Weight sensitivity is diagnostic only.
- No trace/final_v23 tuning.
- No FGO feedback/substitution.
- No paper performance claim.

Allowed N8C3 Raw Doppler FGO factor activation fix statement:

- N8C3 fixes Raw Doppler FGO factor activation.
- Proxy residual is not sufficient; solver residual vector inclusion is required.
- Raw Doppler weight sensitivity is diagnostic only.
- No trace/final_v23 tuning.
- No FGO feedback/substitution.
- No paper performance claim.

Allowed N6B1 source-aware visual validation statement:

- N6B1 is visual validation only.
- Figure existence is not sufficient; plotted data coverage is required.
- N6B1 may generate runtime-only figures and reports for clean curves,
  source-aware R-scale traces, spike response, stress variants, and policy
  diagnostics.
- N6B1 does not modify solver math.
- N6B1 does not use trace or final_v23 output for tuning.
- N6B1 does not delete epochs or apply output-only correction.
- N6B1 does not implement Go2 prior, FGO, or smoothing.
- No paper performance claim.
- No outperform final_v23 claim.

Allowed N7A Go2 body-state weak prior statement:

- N7A activates only Go2 roll/pitch weak prior by default.
- Go2 body-state is not truth.
- Go2 position is not truth.
- Go2 velocity is not truth.
- Go2 position and velocity priors are disabled by default in N7A.
- Go2 yaw prior is disabled in N7A.
- No trace/final_v23 output is used for Go2 prior construction.
- No paper performance claim.
- No outperform final_v23 claim.
- No FGO claim in N7A.
- Go2 weak prior changes EKF measurement update through conservative R, not output-only correction.

Allowed N7B Go2 velocity/contact readiness statement:

- N7B is readiness only.
- Go2 position is not truth.
- Go2 velocity is not truth.
- Cross-source velocity comparison is not truth error.
- Contact state thresholds use diagnostic defaults and do not use trace.
- N7B may compare Go2 velocity with receiver-native velocity and raw Doppler
  velocity for source-consistency review only.
- N7B may classify contact, motion state, and yaw-rate readiness.
- No Go2 velocity prior activation in N7B.
- No Go2 yaw prior activation in N7B.
- No FGO claim in N7B.
- No paper performance claim in N7B.
- No outperform final_v23 claim in N7B.
- No output-only correction.
- No epoch deletion.

Allowed N7B2 Go2 contact threshold review statement:

- N7B2 is contact threshold readiness only.
- Go2 contact thresholds are derived from Go2 field distributions, not trace.
- Threshold candidates are diagnostic and must not be tuned to navigation
  metrics.
- Go2 velocity is not truth.
- Contact-conditioned velocity comparison is not truth error.
- N7B2 may build a diagnostic contact-state v2 candidate and fixed window
  smoother for readiness review only.
- N7B2 may compare contact-conditioned Go2 velocity with receiver-native
  velocity and raw Doppler velocity for source-consistency review only.
- No Go2 velocity prior activation in N7B2.
- No Go2 yaw prior activation in N7B2.
- No FGO claim in N7B2.
- No paper performance claim in N7B2.
- No outperform final_v23 claim in N7B2.
- No output-only correction.
- No epoch deletion.

Allowed N7B2A Go2 metric namespace and contact physical sanity statement:

- 5deg Go2 attitude prior std is weak-prior measurement uncertainty, not gate
  threshold.
- Go2 RPY/quaternion consistency is internal consistency, not absolute truth.
- N7A parity metrics must not be read as absolute accuracy.
- Go2 velocity is not truth.
- Contact-conditioned velocity comparison is not truth error.
- Contact v2 physical sanity is required before any future Go2 velocity/contact
  activation review.
- N7B2A does not activate Go2 velocity prior.
- N7B2A does not activate Go2 yaw prior.
- No trace/final_v23 threshold tuning in N7B2A.
- No FGO claim in N7B2A.
- No paper performance claim in N7B2A.
- No outperform final_v23 claim in N7B2A.
- No output-only correction.
- No epoch deletion.

Allowed N7B3 Go2 contact/velocity diagnostic activation statement:

- N7B3 diagnostic Go2 velocity/yaw-rate activation is not a formal prior.
- Go2 position is not truth.
- Go2 velocity is not truth.
- Cross-source velocity comparison is not truth error.
- Contact model candidates are derived from Go2 fields only.
- Trace/final_v23 are not used for thresholds or frame selection.
- Diagnostic activation results are not paper performance.
- N7B3 may attempt diagnostic-only Go2 velocity/contact EKF updates through
  runtime-only CSVs.
- N7B3 does not enable a formal Go2 velocity prior.
- N7B3 does not enable a formal Go2 yaw prior.
- The current state model has no yaw-rate state, so yaw-rate remains
  diagnostic unless a future state model explicitly supports it.
- No output-only correction.
- No FGO claim.
- No paper performance claim.
- No outperform final_v23 claim.

## Diagnostic / Exploratory Only

The following can only be diagnostic unless future evidence is available:

- Go2 velocity prior;
- support-foot pseudo factor;
- raw pseudorange;
- Neural Gate;
- FGO feedback;
- BY3-only generalization;
- BY3A0_TO_BY3E source inventory, alignment, candidate input generation, BY2 text summary, and BY2 copy-only archive reporting, with no BY3 solver/evaluator performance claim;
- BY3A1 input-chain parity repair and BY3 Go2 prior materialization, with no BY3 solver/evaluator performance claim;
- BY3A3 normal-only solver/evaluator completion as runtime evidence for BY3 generalization review, not as a paper claim or final_v23 outperformance claim;
- reference-limited yaw boundary.
- N9C0 global comparison classifications until N9C visual review and N9D claim-boundary review complete.

## Forbidden Phase-I Claims

Do not claim:

- RTK fixed;
- carrier ambiguity fixed;
- self raw heading;
- full raw GNSS tight coupling;
- full raw pseudorange tight coupling;
- full pose FGO;
- full leg odometry;
- joint-level leg factor;
- outperforming final_v23 unless independently proven;
- independent ground truth unless independently collected;
- formal closure of old LegTC-FGO;
- final_v23 output substitution as proposed result;
- output-only correction;
- trace-tuned performance;
- metric passing by bad-epoch deletion.
- N9C0 readiness as paper-claim authorization.
- N9F design readiness as paper-claim authorization.
- Relabeling `LegSA_full_EKF` as active nine-factor FGO.
- Treating provider/update counts as active FGO residual/cost evidence.
- Treating historical candidate no-feedback rows as current active `LegSA_full_EKF` nine-factor evidence.
- Treating N9G1C-E provider resolution as active nine-factor FGO residual/Jacobian/cost evidence.
- Treating N9G1E as normal-smoke pass evidence.
- Treating BY3A/B source inventory, BY3B alignment reports, or BY3C candidate inputs as BY3 solver/evaluator validation.
- Treating BY3A1 repaired inputs or materialized BY3 Go2 priors as BY3 solver/evaluator validation, metric evidence, or paper evidence.
- Treating BY3A3 normal-only metrics as BY3 degradation/full-matrix completion, active nine-factor FGO evidence, paper evidence, or final_v23 outperformance evidence.
- Claiming BY3 degradation/full-matrix completion from the BY3 full-matrix placeholder root.
- Representative active-nine-factor FGO runs before human-approved implementation review.
- full monolithic N9B2 execution.
- additional N9B2 execution without a later human-defined follow-up.
- active conclusions from superseded rows, `historical_nominal_none`, or `B_gnss_downsample_2Hz`.
- frame/evaluator utilities as a solved navigation algorithm.
- C++ runtime skeleton as a validated navigation solver.
- dry-run output as performance evidence.
- External final_v23 / KF-GINS source audit as proposed algorithm implementation.
- Vendoring external source into LegSA-GINS without explicit decision.
- Source audit as numerical performance evidence.
- final_v23 reproduction before N3C oracle pass.
- improved navigation performance in N3B.
- N3C standardized final_v23 outputs as proposed output.
- N3C parser output-only correction.
- N3C numerical reproduction before oracle pass.
- Proposed solver reading final_v23 baseline outputs.
- Trace reference as solver input.
- Receiver internal IMU treated as Go2 body-state IMU.
- Code comments introducing unsupported performance claims.
- Code comments describing dry-run outputs as numerical evidence.
- Code comments describing baseline parsers as proposed solver implementation.
- Code comments weakening trace_evaluation_only or receiver_imu_as_body_imu=false rules.
- N4 toy filter output as numerical performance evidence.
- N4 final_v23 parity.
- N4 raw Doppler.
- N4 Go2 priors.
- N4 source-aware weighting.
- N4 FGO smoothing.
- N4 trace solver input.
- N4 final_v23 output as proposed solver input.
- N4E must not use trace as solver input.
- N4E must not treat receiver internal IMU as Go2 body IMU.
- N4E must not claim raw Doppler extraction.
- N4E must not claim Go2 prior integration.
- N4E must not claim source-aware weighting.
- N4E must not claim FGO smoothing.
- N4E standardized data must not be used as performance evidence.
- N4F metrics must not be written as formal performance claim.
- N4F must not tune to final_v23.
- N4F must not delete bad epochs to pass metrics.
- N4F must not use trace as solver input.
- N4F must not claim final_v23 parity.
- N4G must not claim hardware clock synchronization.
- N4G must not claim a physical Go2-to-GNSS clock offset.
- N4G must not use trace for solver time alignment.
- N4G must not select a formal heading offset without antenna order evidence.
- N4G must not write diagnostic candidates as numerical performance claims.
- N4H0 metrics are diagnostic measurement-floor metrics only.
- N4H0 must not be described as proposed solver performance.
- N4H0 must not use trace as solver input.
- final_v23 input source-chain audit is diagnostic only.
- final_v23 runtime .gnss input must not be confused with raw GNSS observations.
- final_v23 input audit must not be described as proposed solver implementation.
- trace remains evaluation-only.
- process_data-compatible input generation is input reconstruction only.
- generated `.gnss` / `.imu` files must not be described as proposed algorithm output.
- trace yaw mode is diagnostic-only.
- nominal process_data-compatible generation must not inject artificial outage, outlier, or noise by default.
- process_data-compatible coverage reports are input-construction diagnostics, not performance evidence.
- N4H2C deep source/input/runtime parity audit is diagnostic only.
- N4H2C must not be described as proposed solver implementation.
- N4H2C must not use trace as solver input.
- N4H2C must not formal-select yaw offset without physical or actual-input evidence.
- N4H2C yaw variant matrix must remain diagnostic-only.
- Trace yaw must not become formal solver input.
- Auto-best install based on trace must remain diagnostic-only unless supported by physical or actual final_v23 input evidence.
- Missing actual final_v23 artifacts must be reported as evidence_missing.
- N4R metrics as proposed solver performance.
- N4R official artifacts as solver input.
- N4R yaw transform candidates as solver tuning.
- N4H4A as EKF parity.
- N4H4A as final_v23 reproduction.
- N4H4A as proposed numerical performance evidence.
- N4H4A reading final_v23 output as solver input.
- N4H4A compiling `reference/final_v23_repo` source into proposed code.
- N4H4A enabling raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting,
  FGO, FGO feedback, output-only correction, or bad-epoch deletion.
- N4H4A factor flags set to true.
- N4H4B as complete EKF parity.
- N4H4B as final_v23 parity.
- N4H4B as numerical performance evidence.
- N4H4B implementing GNSS measurement updates.
- N4H4B implementing `EKFUpdate` or `stateFeedback`.
- N4H4C as final_v23 numerical parity.
- N4H4C toy update as numerical performance evidence.
- N4H4C reading final_v23 outputs as solver input.
- N4H4C enabling raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting,
  FGO, FGO feedback, or Neural Gate.
- N4H4C using trace as solver input.
- N5A treating NAV-PVT velocity as raw Doppler.
- N5A treating `.gnss vn/ve/vd` as raw Doppler.
- N5A reporting raw Doppler applied when satellite-state provider is missing.
- N5A using rnx2rtkp final positioning output as LegSA solver input.
- N5A using trace or final_v23 output as solver input.
- N5A making LSIM/OIM, Go2 prior, FGO, paper performance, or outperform final_v23 claims.
- N4H4C relaxing yaw evaluator gates or deleting epochs to pass metrics.
- N4H4B enabling raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting,
  FGO, FGO feedback, output-only correction, bad-epoch deletion, or trace
  solver input.
- PR #21 self-written v23-core failure evidence as proposed performance claim.
- PR #21 self-written v23-core failure evidence as a clean parity pass.
- Source-backed port as paper novelty.
- final_v23/KF-GINS reference described as proposed.
- final_v23 source copied without provenance and license controls.
- final_v23 output used as proposed solver input.
- Factor claims before backbone parity.
- Nine-factor claims before ablation evidence.
- N4H4R0 implementing solver code or factor logic.
- N4H4R1 toy run as numerical performance evidence.
- N4H4R1 source-backed port-core as proposed novelty.
- N4H4R1 enabling raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting, or FGO.
- Port-vs-final_v23 parity metrics as absolute performance metrics.
- Metric gate pass as a paper performance claim.
- Direct comparison of parity-to-baseline metrics with absolute trace metrics.
- N4H4R3C as outperforming final_v23.
- N4H4R3C as a proposed factor claim.
- N4H4R3C output-only correction, tuning, or epoch deletion.
- N4H4E visual validation as a paper performance claim.
- N4H4E visual validation as outperforming final_v23.
- N4H4E visual validation as a proposed factor claim.
- N4H4E figures as committed repository artifacts.
- N4H4E pure INS or single-antenna comparison plots.
- N4H4E enabling raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting,
  FGO, output-only correction, tuning, or epoch deletion.
- N4H4E1 visual fixes as solver performance improvements.
- N4H4E1 corrected STD/3sigma figures as paper performance claims.
- N4H4E1 vector error clouds as trajectories.
- N4H4E1 as outperforming final_v23.
- N4H4E1 as a proposed factor claim.
- N4H4E1 committed generated figures or runtime reports.

Frame/evaluator utilities must not be described as a solved navigation algorithm.

C++ runtime skeleton must not be described as a validated navigation solver.

Dry-run output must not be used as performance evidence.

External final_v23 / KF-GINS source audit must not be described as proposed algorithm implementation.

External source must not be vendored into LegSA-GINS without explicit decision.

Source audit must not be used as numerical performance evidence.

N3B must not claim final_v23 reproduction before N3C oracle pass.

N3B must not claim improved navigation performance.

N3C standardized final_v23 outputs must not be used as proposed output.

N3C parsers must not perform output-only correction.

N3C must not claim numerical reproduction before oracle pass.

N3C must not allow proposed solver to read final_v23 baseline outputs.

Trace reference must not be used as solver input.

Receiver internal IMU must not be treated as Go2 body-state IMU.

Code comments must not introduce unsupported performance claims.

Code comments must not describe dry-run outputs as numerical evidence.

Code comments must not describe baseline parsers as proposed solver implementation.

Code comments must not weaken trace_evaluation_only or receiver_imu_as_body_imu=false rules.

N4 toy filter output must not be used as numerical performance evidence.

N4 must not claim final_v23 parity.

N4 must not claim raw Doppler.

N4 must not claim Go2 priors.

N4 must not claim source-aware weighting.

N4 must not claim FGO smoothing.

N4 must not use trace as solver input.

N4 must not use final_v23 output as proposed solver input.

N4E must not use trace as solver input.

N4E must not treat receiver internal IMU as Go2 body IMU.

N4E must not claim raw Doppler extraction.

N4E must not claim Go2 prior integration.

N4E must not claim source-aware weighting.

N4E must not claim FGO smoothing.

N4E standardized data must not be used as performance evidence.

N4F metrics must not be written as formal performance claim.

N4F must not tune to final_v23.

N4F must not delete bad epochs to pass metrics.

N4F must not use trace as solver input.

N4F must not claim final_v23 parity.

N4G must not claim hardware clock synchronization.

N4G must not claim a physical Go2-to-GNSS clock offset.

N4G must not use trace for solver time alignment.

N4G must not select a formal heading offset without antenna order evidence.

N4G must not write diagnostic candidates as numerical performance claims.

N4H0 metrics are diagnostic measurement-floor metrics only.

N4H0 must not be described as proposed solver performance.

N4H0 must not use trace as solver input.

final_v23 input source-chain audit is diagnostic only.

final_v23 runtime .gnss input must not be confused with raw GNSS observations.

final_v23 input audit must not be described as proposed solver implementation.

trace remains evaluation-only.

process_data-compatible input generation is input reconstruction only.

generated `.gnss` / `.imu` files must not be described as proposed algorithm output.

trace yaw mode is diagnostic-only.

nominal process_data-compatible generation must not inject artificial outage, outlier, or noise by default.

process_data-compatible coverage reports are input-construction diagnostics, not performance evidence.

N4H2 external KF-GINS replay is baseline replay evidence only.

N4H2 parsed NAV/STD/IMU_ERR outputs must not be used as proposed solver input.

N4H2 trace alignment is evaluation-only and must not be used for replay tuning.

N4H2 position/yaw metrics must not be described as final_v23 parity or proposed-method performance.

N4R is evaluator-parity diagnostic only.

N4R metrics are not proposed solver performance.

Official artifacts are not solver input.

N4R yaw transform candidates are evaluator diagnostics, not solver tuning.

N4R2 evaluator yaw convention profile is diagnostic until dual_final_v23 parity confirms it.

A yaw result slightly above 2 deg is near-boundary, not pass.

No solver output is modified by evaluator profile re-evaluation.

Trace remains evaluation-only.

dual_final_v23 artifact must be confirmed before formal evaluator yaw profile patch.

yaw=2.06058 is near-gate evidence, not yaw pass.

evaluator profile re-evaluation does not modify solver output.

no artifact files may be committed.

trace remains evaluation-only.

Runtime yaw audit is diagnostic only.

Runtime yaw audit must not modify solver output.

Runtime yaw audit must not modify external KF-GINS source.

Runtime yaw audit must not claim performance.

Runtime yaw audit must not relax yaw > 2 deg.

Full KF-GINS-style framework remains future work until runtime/config parity is resolved.

N4H2D is evaluation/reference-mapping audit only.

Fresh replay metrics are baseline replay diagnostics, not proposed solver performance.

Solver output is not modified by N4H2D.

Old stale summary must not be used as formal evidence.

Yaw gate remains <= 2.0.

N4H2E visual validation figures are diagnostic baseline replay evidence only.

N4H2E generated figures are not proposed solver performance.

N4H2E visual validation does not modify solver output.

N4H2E requires manual visual review.

N4H2E roll/pitch relaxed pass is not strict pass.

N4H2E yaw near-boundary evidence must be reported honestly.

Generated figures under the visual output role must not be committed.

yaw_std=1.5 is measurement standard deviation unless actual yaw-noise injection is proven.

process_data yaw_noise injection must be distinguished from yaw_std.

run_final_mainline degradation batch must not be treated as clean nominal evidence.

If actual input matches an injected-noise variant, final_v23 nominal claims must carry a provenance caveat.

Roll/pitch relaxed pass is not strict pass.

Generated figures and reports under the visual output role must not be committed.

Historical final_v23 artifact likely includes Gaussian yaw-noise provenance.

Clean replay is reconstructed clean variant, not historical exact final_v23 artifact.

Clean/noisy input provenance must be labeled in later experiments.

N4H2G clean replay metrics are baseline replay diagnostics only.

N4H2G clean replay metrics are not proposed solver performance.

Clean replay must be independently rerun before it can support next-stage decisions.

Exact metric equality must be checked for cache/stale summary risk.

Yaw sensitivity probe is diagnostic only and not a factor experiment.

N4H2G2 does not modify solver output or make a performance claim.

N4H3 final_v23 reference import is not proposed solver implementation.

N4H3 final_v23 source must not be described as novelty.

N4H3 future port/refactor must preserve provenance.

N4H3 final_v23 outputs must not be used as proposed solver input.

N4H3 raw data/results must not be committed.

N4H3 clean replay is reconstructed clean variant, not historical exact artifact.

N4H3 noisy historical artifact must not be called clean nominal.

N4H4 must implement LegSA-owned code and Chinese comments for critical functions.

N4H4 must not be a wrapper.

N4H4 must not use final_v23 output as proposed solver input.

N4H4 must not use trace as solver input.

N4H4 must not make a performance claim before validation.

PR #21 self-written v23-core parity failure is an evidence branch only.

PR #21 must not be used for proposed performance claim.

Source-backed port is a backbone implementation, not novelty.

final_v23/KF-GINS reference must not be described as proposed.

Ported backbone must preserve provenance.

Clean/noisy input provenance remains mandatory.

Factor claims start only after backbone parity.

No nine-factor claim before ablation evidence.

Source-backed port-core is backbone, not novelty.

Ported core must preserve provenance.

No factor claims until port parity.

N4H4R1 toy run is not performance evidence.

final_v23 output cannot be solver input.

old cpp/legsa_v23_core remains diagnostic attempt.

N4H4R2 completes backbone math port but does not claim performance.

R2 synthetic run is not parity.

R3 required for clean replay parity.

No factor claims before R3.

Ported backbone is not novelty.

N4H4R3 is engineering backbone parity only.

N4H4R3 is not a proposed factor result.

No paper performance claim.

## BY3A3 Normal Generalization Execution Boundary

BY3A3 may state that BY3 same-case selected feedback was generated from BY3 stage1 official-eval state/estimate columns only.

BY3A3 may state that `LegSA_full_EKF`, `single_antenna_gnss1_status_KF_GINS`, and `final_v23_dual_antenna_EKF` normal-only BY3 solver/evaluator runs completed if the BY3A3 runtime decision report says so.

BY3A3 may report normal BY3 metrics as runtime evidence for human review and BY3 degradation planning.

BY3A3's degradation-planning readiness is superseded by BY3A4A.

BY3A3 may not claim paper performance readiness, final_v23 outperformance, BY3 degradation/full-matrix completion, complete nine-factor FGO, or active LegSA_9F_FGO_EKF evidence.

BY3A3 keeps `ready_for_paper_claims=false`.

No raw Doppler/Go2/LSIM/OIM/FGO claims.

Trace evaluation-only.

final_v23 output not solver input.

Roll/pitch relaxed pass is not strict pass.

If parity fails, gap screen controls next work.

R3A timeline diagnostics are not performance results.

GNSS total row count must not be treated as expected update count without overlap audit.

No output-only correction, no tuning, no epoch deletion.

Runtime loop fixes must be source-backed.

No proposed factor claim.

## BY3A4A Lateral Dual-Antenna Yaw Policy Boundary

BY3A4A may state that BY2 lateral dual-antenna yaw policy evidence was recovered as partial.

BY3A4A may state that the dual antennas are mounted laterally, perpendicular to the robot forward/head direction, so antenna-baseline heading is not body heading.

BY3A4A may state that body heading requires a plus/minus 90 degree correction from antenna-baseline heading depending on antenna order and coordinate/frame convention.

BY3A4A may state that +90/-90 selection must not be made by yaw RMSE minimization alone.

BY3A4A may state that existing BY3A3 solver outputs were used to audit current, BY2-recovered lateral, plus/minus 90, and baseline-reversal yaw candidates, and that no policy was accepted because the tested candidates did not pass yaw sanity across the three normal algorithms.

BY3A4A may state that common-overlap metrics, diagnostic figures, seed0-9 explanation, context updates, and Obsidian notes were generated.

BY3A4A may not claim repaired BY3 yaw metrics, BY3 degradation readiness, paper performance readiness, final_v23 outperformance, solver rerun, degradation matrix completion, parameter retuning, or trace/final_v23/algorithm output use as solver input.

BY3A4A keeps `ready_for_BY3_degradation_matrix_planning=false` and `ready_for_paper_claims=false`.

## BY3A4C Git-History Yaw Reference Boundary

BY3A4C may state that the historical BY2/N4 yaw-reference repair was recovered from git history, tracked docs/source, PR metadata, and runtime evidence.

BY3A4C may state that N4H2 old yaw around 93 deg was invalidated by N4H2D, that N4H2D selected `official_ref_sign_minus`, and that fresh replay yaw was about 1.98 deg under the reconstructed dual official reference.

BY3A4C may state that recovered and diagnostic yaw profiles were applied to existing BY3A3 outputs only, with no solver rerun, no degradation run, no retuning, no output correction, and no RMSE-only policy selection.

BY3A4C may state that no BY3 yaw truth/reference profile was accepted, so BY3 yaw is `not_evaluable` and BY3A3/BY3A4A yaw metrics are preserved as historical invalid-reference evidence.

BY3A4C may state that BY3 position/up metrics can support position/up-only planning, with `yaw_degradation_claims=false`.

BY3A4C may not claim repaired BY3 yaw metrics, BY3 yaw degradation readiness, paper performance readiness, final_v23 outperformance, solver rerun, degradation matrix completion, parameter retuning, or trace/final_v23/algorithm output use as solver input.

BY3A4C keeps `ready_for_BY3_degradation_matrix_planning=true` only for `position_up_only`, `yaw_degradation_claims=false`, and `ready_for_paper_claims=false`.

## BY3A5B A1 Dual-Diff Yaw Input Repair Boundary

BY3A5B may state that BY3A5 correctly confirmed the old BY3 15-column yaw input was wrong-source, but BY3A5's HDT repair is diagnostic/rejected/superseded for mainline BY3.

BY3A5B may state that BY3 dual yaw was regenerated from GNSS1/GNSS2 A1_dual_diff short-baseline absolute positions, using BY2 accepted `gnss2_minus_gnss1`, lateral conversion equivalent to `baseline_heading+90`, and fixed_1p5 yaw_std.

BY3A5B may state that the reconstructed GNSS1/GNSS2 baseline is physically plausible for a short dual-antenna baseline, while GNSS status `rel_pos_n/e/d` is a long-baseline/base-vector source and rejected.

BY3A5B may state that the BY3 normal-only rerun completed for LegSA_full_EKF, single_antenna_gnss1_status_KF_GINS, and final_v23_dual_antenna_EKF with no degradation, no trace/final_v23/solver-output input, no HDT solver input, and no parameter retuning.

BY3A5B may state that A1 input repair completed but yaw remained unresolved before BY3A6.

BY3A5B may not claim repaired official BY3 yaw metrics, BY3 yaw degradation readiness, final_v23 outperformance, paper performance readiness, HDT mainline acceptance, trace/final_v23/output tuning, or BY3 degradation/full-matrix completion.

## BY3A6 Trace Truth Initatt Yaw Gate Boundary

BY3A6 may state that the BY3 trace file is the evaluation truth reference and that trace is evaluation-only, never solver input, tuning input, or initatt source.

BY3A6 may state that the evaluator selects raw numeric `lat`, `lon`, `height`, `yaw`, `pitch`, and `roll` for the current trace, while `processed_lat` and `processed_lon` are unsafe/string-like or swapped and must not be used blindly.

BY3A6 may state that base_time alignment is valid for the current BY3 normal chain, with first trace-relative time matching first A1 dual-diff GNSS time within milliseconds.

BY3A6 may state that BY3A5B A1_dual_diff remains the mainline dual-yaw input with caution: source/schema/start coverage are valid, but A1-vs-trace heading and yaw-gate behavior remain unresolved.

BY3A6 may state that stage1 and LegSA_full_EKF initatt had a confirmed stale first-row yaw bug before repair, and that the safe repair uses the first dual GNSS/A1 yaw row at or after the requested starttime without using trace or output metrics.

BY3A6 may state that BY3 normal-only rerun completed after initatt repair for LegSA_full_EKF, single_antenna_gnss1_status_KF_GINS, and final_v23_dual_antenna_EKF, with no degradation, no trace/final_v23/solver-output input, no HDT solver input, and no parameter retuning.

BY3A6 may state that position/up sanity remains acceptable but yaw still fails after initatt repair, with likely yaw-gate/A1-dynamics follow-up required. `ready_for_BY3_degradation_matrix_planning=false`, `yaw_degradation_claims=false`, and `ready_for_paper_claims=false`.

BY3A6 may not claim repaired BY3 yaw, BY3 degradation readiness, final_v23 outperformance, paper readiness, trace invalidity, A1 invalidity, evaluator invalidity, or yaw-gate repair without a later evidence-backed stage.

## BY3A7 A1 Yaw Dynamic Quality IMU Gate Boundary

BY3A7 may state that A1_dual_diff remains the mainline short-baseline yaw source with dynamic-quality caution and that invalid epoch criteria are based on source baseline/jump quality, not RMSE.

BY3A7 may state that the remaining BY3 yaw failure after BY3A6 was dominated by a BY3 Go2 IMU preprocessing bug: gyro bias was estimated from a moving segment after selected Go2 start. The BY3A7 repair uses a BY3A7-local IMU input with pre-motion source gyro bias and preserves FLU-to-FRD conversion, A1 yaw source, fixed_1p5 yaw_std, yaw gate thresholds, and solver parameters.

BY3A7 may state that normal-only yaw sanity passed for dual-yaw algorithms after the repair: LegSA_full_EKF yaw RMSE about 5.26 deg and final_v23_dual_antenna_EKF yaw RMSE about 4.30 deg.

BY3A7 may set `ready_for_BY3_degradation_matrix_planning=true` only with `scope=full_after_human_review`. BY3A7 may not claim paper readiness, final_v23 outperformance, completed BY3 degradation/full-matrix execution, trace tuning, gate relaxation, HDT mainline acceptance, or PR #52 merge/tag/closure authorization.

## BY3A8 Yaw Error Budget Boundary

BY3A8 may state that the remaining BY3 dual-yaw normal error is limited by A1 observation quality. The evaluation-only A1 lower-bound audit found A1-vs-trace heading RMSE about 24.06 deg, p95 about 31.78 deg, max about 167.29 deg, circular mean about -15.06 deg, and circular std about 17.17 deg.

BY3A8 may state that source-quality-only A1 checks found 6 objective invalid solver-candidate epochs, but an objective mask is insufficient for the broad observation error. BY3A8 may state that BY3A7 IMU bias remains accepted, time-lag diagnostics do not support a metadata-backed repair, yaw-gate behavior is acceptable under unchanged thresholds, and feedback worsens yaw relative to stage1 but requires a separate human-approved review.

BY3A8 may set `ready_for_BY3_degradation_matrix_planning=true` only with `scope=position_up_with_diagnostic_yaw`; `yaw_claim_scope=diagnostic_only` and `ready_for_paper_claims=false`. BY3A8 may not claim paper yaw success, final_v23 outperformance, completed BY3 degradation/full-matrix execution, trace-based correction, yaw-gate relaxation, HDT/long-relpos fallback, feedback-policy authorization, or RMSE-selected epoch deletion.

Metric-gate pass is not sufficient if external-clean closeness fails.

Too-good results require over-close audit.

Measurement-copy and reference-independence checks are mandatory.

No outperform final_v23 claim before evidence-backed paper evaluation.

No proposed factor claim.

No output-only correction, no tuning, no epoch deletion.

## Evidence Rule

If evidence is missing, write:

evidence_missing

Do not invent evidence.

## N5B Raw Doppler Boundary

N5B aims to activate raw Doppler in EKF using RTKLIB-derived Doppler velocity factors.

RTKLIB position solution must not be used as LegSA solver input.

`raw_doppler_update_count > 0` is required for activation.

Diagnostic delta is not paper performance.

No final_v23 output solver input.

No trace solver input.

No NAV-PVT velocity as raw Doppler.

No `.gnss vn/ve/vd` as raw Doppler.

No LSIM/OIM, Go2 prior, or FGO claim in N5B.

## N5C Raw Doppler Ablation Boundary

N5C ablation is diagnostic engineering evidence, not paper performance.

Raw Doppler beneficial, neutral, or degraded labels are diagnostic only.

R_scale screen is diagnostic-only and not tuning.

Velocity-isolation variants are diagnostic-only.

No RTKLIB position solution as solver input.

No NAV-PVT velocity as raw Doppler.

No `.gnss vn/ve/vd` as raw Doppler.

No final_v23 output solver input.

No trace solver input.

No output-only correction, no tuning, no epoch deletion.

No LSIM/OIM, Go2 prior, or FGO claim in N5C.

## N5D Raw Doppler Visual/Stress Boundary

N5D visual/stress protocol is diagnostic engineering evidence.

Receiver velocity stress variants are diagnostic-only.

R-scale and STD-scale screens are not tuning claims.

NAV-PVT velocity is not raw Doppler.

.gnss vn/ve/vd is not raw Doppler.

RTKLIB position solution must not be used as LegSA solver input.

No final_v23 output solver input.

No trace solver input.

No output-only correction, no tuning, no epoch deletion.

No LSIM/OIM, Go2 prior, or FGO claim in N5D.

No paper performance claim.

No outperform final_v23 claim.

## BY3A2 Historical Pipeline Recovery Boundary

BY3A2 may state only that the historical BY2 WSL chains were recovered and applied as gate checks for BY3.

BY3A2 may state that BY3 raw receiver CSVs can rebuild UBX/RAWX evidence and that Raw Doppler provider materialization succeeded only if the reviewed BY3A2 runtime report contains fresh accepted RINEX/nav/provider factor CSV evidence.

BY3A2 may state that BY3 Go2 priors were validated as proprioceptive observations, not truth.

BY3A2 may state that single-baseline and final_v23 handoff configs were generated for review if the BY3A2 handoff reports say so. This is not solver output.

BY3A2 may not claim BY3 normal generalization success.

BY3A2 may not claim Raw Doppler was supplied by GNSS receiver velocity, NAV-PVT velocity, RTKLIB position solution, trace, final_v23 output, or LegSA output.

BY3A2 may not claim selected-feedback readiness until same-case BY3 stage1 official EVAL_NAV exists and the feedback file is generated from state/estimate columns only.

No BY3 degradation claim.

No paper performance claim.

## N8K4 Semantic Filename Plot Fix Boundary

N8K2 eliminated the original placeholder-like formal ablation figures.

N8K3 eliminated same-category exact duplicate plots.

N8K4 fixes semantic filename mismatches left by N8K3.

Exact duplicate equals zero does not prove figure semantics are correct.

Figure filename, title, semantic_role, data_source, and not-applicable reason
must agree.

compare_horizontal_error must remain a horizontal error comparison and must not
be occupied by reject-all not-applicable content.

reject_all_sanity_compare handles reject-all sanity semantics.

yaw_residual_time and yaw_wrap_check must be distinct semantic products.

feedback_accept_reject_timeline and reject_all_sanity must be distinct semantic
products.

derived_from_n8k_metrics_and_baseline_nav is derived/surrogate visualization
data, not complete runtime variant NAV.

N8K4 does not change algorithm math or feedback policy.

N8K4 does not run the degradation matrix.

No trace/final_v23 tuning.

No paper performance claim.

No outperform final_v23 claim.

## N8K3 Duplicate Plot Fix Boundary

N8K2 eliminated the original placeholder-like formal ablation figures.

N8K3 fixes same-category exact duplicate plots missed by the N8K2 detector.

Duplicate hashes across different figure names in the same category are not
acceptable unless documented as not-applicable or allowed with reason.

The focus categories are 01_trajectory, 04_attitude, 07_compare, and
11_feedback.

derived_from_n8k_metrics_and_baseline_nav is derived/surrogate visualization
data, not complete runtime variant NAV.

N8K3 does not change algorithm math or feedback policy.

N8K3 does not run the degradation matrix.

No trace/final_v23 tuning.

No paper performance claim.

No outperform final_v23 claim.

## N8K2 BY2 Formal Ablation Real Plot Fix Boundary

N8K2 fixes formal ablation plots that were placeholder-like.

Applicable plots must use real or runtime-derived data rows.

Placeholder panels are allowed only for documented not-applicable cases.

N8K2 does not change algorithm math or feedback policy.

N8K2 does not run the degradation matrix.

No trace/final_v23 tuning.

No paper performance claim.

No outperform final_v23 claim.

## N8G FGO Feedback EKF Boundary

N8G introduces controlled FGO feedback to EKF.

FGO feedback is an EKF update / pseudo-measurement, not output substitution.

FGO output does not directly replace NAV.

Feedback uses no future data.

Feedback covariance and gates are conservative and not trace/final_v23 tuned.

N8G is engineering diagnostic evidence, not paper performance claim.

No direct NAV overwrite.

No trace solver input.

No final_v23 output solver input.

No output-only correction.

No epoch deletion for metric.

No outperform final_v23 claim.

## N8F1 Legged Candidate Factor Visual Validation Boundary

N8F1 visually validates legged candidate FGO factors.

Visual validation is diagnostic engineering evidence only.

Foot kinematic velocity, yaw-rate, and relative odometry factors are not truth.

Contact probability is a weighting signal, not truth.

No FGO feedback/substitution in N8F1.

No trace/final_v23 tuning.

No trace solver input.

No final_v23 output solver input.

No Go2 contact, velocity, yaw, or position truth claim.

No output-only correction, no tuning, no epoch deletion.

No paper performance claim.

No outperform final_v23 claim.

## N8F Legged Candidate Factor Activation Boundary

N8F formally activates legged candidate factors in no-feedback FGO.

Contact probability is a weighting layer, not truth.

Foot kinematic velocity is a proprioceptive factor, not truth.

Yaw-rate and relative odometry are between factors, not absolute truth.

No Go2 absolute position factor.

No Go2 absolute yaw factor.

No Go2 vertical velocity factor by default.

No hard contact truth.

No FGO feedback/substitution in N8F.

No trace/final_v23 tuning.

No trace solver input.

No final_v23 output solver input.

No output-only correction, no tuning, no epoch deletion.

No paper performance claim.

No outperform final_v23 claim.

## N8E Formal Engineering Ablation Boundary

N8E is formal engineering ablation with caveats.

N8E is not a paper performance claim.

Raw Doppler FGO factor is active but low marginal value in current no-feedback
FGO.

Raw Doppler low marginal value is a caveat, not an activation failure.

Candidate factors remain diagnostic unless explicitly promoted later.

No FGO feedback/substitution.

FGO output is not fed back into EKF.

FGO output does not replace EKF NAV.

No trace/final_v23 tuning.

No trace solver input.

No final_v23 output solver input.

No outperform final_v23 claim.

## N8D FGO Factor Weight Policy Boundary

N8D reviews FGO factor weights using solver-visible diagnostics only.

Trace/final_v23 are not used for weight tuning.

Smoothness is not deleted as a final shortcut.

Weight sensitivity and ablation are engineering diagnostics.

Raw Doppler, receiver velocity, Go2 joint, dual yaw, and smoothness balance is
reviewed without feeding FGO output back into EKF.

No FGO feedback/substitution.

No paper performance claim.

No outperform final_v23 claim.

## N8A No-Feedback FGO Foundation Boundary

N8A FGO is no-feedback.

FGO output is not fed back into EKF.

FGO output does not replace EKF NAV.

Trace and final_v23 outputs are evaluation-only.

Trace is not used as an FGO factor.

final_v23 output is not used as an FGO factor.

Go2 proprioceptive joint factor is allowed.

Go2 foot kinematic velocity, yaw-rate, and relative odometry are diagnostic FGO candidate factors.

Go2 contact probability is weighting-only unless a later stage formally reopens it.

Go2 vertical velocity factor is not used as default.

Go2 yaw factor is not used as default.

Go2 absolute position factor is not used as default.

N8A is diagnostic engineering evidence, not paper performance.

No output-only correction.

No paper performance claim.

No outperform final_v23 claim.

## N8A1 FGO Yaw-Delta Policy Review Boundary

N8A1 diagnoses FGO yaw delta before merging N8A.

Large FGO-vs-EKF yaw delta is not a performance claim.

FGO output remains no-feedback and non-substitution.

Trace/final_v23 are not solver inputs.

Trace/final_v23 are not used to tune FGO weights.

Diagnostic ablations are engineering probes only.

Runtime figures and reports are not committed.

No EKF modification.

No output-only correction.

No paper performance claim.

No outperform final_v23 claim.

## N8A2 FGO Yaw Convention Fix Boundary

N8A2 fixes FGO yaw residual wrapping.

Dual-yaw, yaw smoothness, and yaw-rate diagnostic residuals use shortest-angle wrapping.

N8A2 does not use output-only yaw correction.

Smoothness factor is not deleted to pass metrics.

Trace/final_v23 are not solver inputs.

Trace/final_v23 are not used to tune FGO weights.

FGO remains no-feedback.

FGO output does not replace EKF NAV.

No EKF modification.

No paper performance claim.

No outperform final_v23 claim.

## N8B FGO Factor Graph Policy Review Boundary

N8B reviews FGO factor policies without trace/final_v23 tuning.

Smoothness is not deleted as a final shortcut.

Candidate factors remain diagnostic unless promoted in a later stage.

FGO remains no-feedback and non-substitution.

Trace/final_v23 are not solver inputs.

Runtime figures and reports are not committed.

No paper performance claim.

No outperform final_v23 claim.

## N8C No-Feedback FGO Visual Validation Boundary

N8C is no-feedback FGO visual validation.

FGO visual improvements are diagnostic engineering evidence only.

Candidate factor contribution is reviewed but not formalized.

No FGO output feedback or substitution.

Trace/final_v23 are not solver inputs.

Runtime figures and reports are not committed.

No paper performance claim.

No outperform final_v23 claim.

## N7C6A Go2 Proprioceptive Joint Factor Final Review Boundary

N7C6A is final visual/metric sanity review.

N7C6A does not change solver math.

N7C6A does not tune weights, delete epochs, or alter N7C6 results.

N7C6A clarifies metric semantics and plot readability.

Go2 proprioceptive joint factor remains observation, not truth.

Go2 position prior remains disabled.

Go2 yaw prior remains disabled.

Go2 vertical velocity prior remains disabled.

No trace/final_v23 tuning.

No trace solver input.

No final_v23 output solver input.

No output-only correction.

No FGO claim in N7C6A.

No paper performance claim.

No outperform final_v23 claim.

## N7C5A / N7C6 Go2 Proprioceptive Joint Observation Boundary

N7C5A reviews N7C5 Go2 full-field mining figures before any additional
activation.

N7C5A does not change solver math.

N7C6 tests Go2 roll/pitch + horizontal velocity joint proprioceptive
observation factors.

The current N7C6 implementation may use sequential-equivalent roll/pitch and
horizontal velocity EKF updates while documenting the combined 4D observation
contract.

Go2 body-state is proprioceptive observation, not truth.

Go2 roll/pitch are not truth.

Go2 horizontal velocity is not truth.

Go2 contact probability is not truth.

Go2 position prior remains disabled.

Go2 yaw prior remains disabled.

Go2 vertical velocity prior remains disabled.

No trace/final_v23 tuning.

No trace solver input.

No final_v23 output solver input.

No output-only correction, no epoch deletion.

No FGO claim.

No paper performance claim.

No outperform final_v23 claim.

## N7C5 Go2 Full Proprioceptive Factor Mining Boundary

N7C5 mines Go2 proprioceptive fields for candidate factors.

Foot kinematic velocity candidate is diagnostic unless later activated.

Go2 position, velocity, contact, roll, and pitch are not truth.

Go2 position prior remains disabled.

Go2 yaw prior remains disabled.

Go2 vertical velocity prior remains disabled.

No trace/final_v23 tuning.

No trace solver input.

No final_v23 output solver input.

No output-only correction.

No formal new factor activation in N7C5 except existing validated factors.

No FGO claim.

No paper performance claim.

No outperform final_v23 claim.

## N7C4 Go2 Horizontal Velocity Prior Strength Boundary

N7C4 scans Go2 horizontal velocity prior strength.

Stronger std policies are diagnostic unless selected by non-trace consistency gates.

Go2 velocity remains not truth.

Vertical Go2 velocity remains disabled.

Go2 yaw prior remains disabled.

Go2 position prior remains disabled.

No trace/final_v23 tuning.

No trace solver input.

No final_v23 output solver input.

No output-only correction, no tuning, no epoch deletion.

No FGO claim.

No paper performance claim.

No outperform final_v23 claim.

## N7C Go2 Horizontal Velocity Weak-Prior Boundary

N7C uses Go2 horizontal velocity weak prior only.

Only `vn` and `ve` are valid Go2 velocity measurement components.

Go2 vertical velocity remains disabled.

Go2 position prior remains disabled.

Go2 yaw prior remains disabled.

Go2 velocity is not truth.

N7C is engineering diagnostic evidence, not paper performance evidence.

No trace tuning.

No final_v23 output tuning.

No trace solver input.

No final_v23 output solver input.

No output-only correction, no tuning, no epoch deletion.

No FGO claim.

No paper performance claim.

No outperform final_v23 claim.

## N7C1 Go2 Horizontal Velocity Visual Validation Boundary

N7C1 is visual validation only.

Figure existence is not sufficient; plotted data coverage is required.

Mandatory figures must report plotted row counts, time-axis coverage, source
roles, and reason codes for suspected empty plots.

Go2 horizontal velocity weak prior remains engineering diagnostic evidence.

Go2 velocity is not truth.

Go2 vertical velocity, Go2 position prior, and Go2 yaw prior remain disabled.

N7C1 does not change solver math.

N7C1 does not tune from trace or final_v23 output.

N7C1 does not delete epochs.

N7C1 does not apply output-only correction.

No FGO claim in N7C1.

No paper performance claim.

No outperform final_v23 claim.

## N7C2 Go2 Horizontal Velocity Visual Readability and Jacobian Boundary

N7C2 does not change solver math.

N7C2 does not tune Go2 horizontal velocity prior std.

N7C2 clarifies curve overlap in plots using source-data metrics, alpha/style
overlays, and delta/zoom figures.

N7C2 documents Jacobian contracts for active measurement/update factors.

Go2 horizontal velocity touches only horizontal velocity states.

Go2 vertical velocity remains disabled.

Go2 position prior remains disabled.

Go2 yaw prior remains disabled.

Go2 velocity is not truth.

No trace solver input.

No final_v23 output solver input.

No output-only correction, no tuning, no epoch deletion.

No FGO claim.

No paper performance claim.

No outperform final_v23 claim.

## N6B1 Source-Aware Visual Validation Boundary

N6B1 is visual validation only.

Figure existence is not sufficient; plotted data coverage is required.

Mandatory figures must be non-empty and must report plotted row counts, time
axis coverage, source IDs, and reason codes for suspected empty plots.

N6B1 does not change solver math.

N6B1 does not tune from trace or final_v23 output.

N6B1 does not delete epochs.

N6B1 does not apply output-only correction.

No Go2 prior in N6B1.

No FGO claim in N6B1.

No paper performance claim.

No outperform final_v23 claim.

## N5D1 Visual Coverage and Spike-Audit Boundary

N5D1 fixes visual validation and plot semantics only.

N5D1 does not change solver math.

Mandatory figures must be non-empty before visual validation passes.

Raw Doppler spikes are audited, not removed or tuned away.

Raw-vs-receiver velocity consistency is not truth error.

Receiver-native velocity is not raw Doppler truth.

No NAV-PVT velocity as raw Doppler.

No `.gnss vn/ve/vd` as raw Doppler.

No RTKLIB position solution as solver input.

No final_v23 output solver input.

No trace solver input.

No output-only correction, no tuning, no epoch deletion.

No LSIM/OIM, Go2 prior, or FGO claim in N5D1.

No paper performance claim.

No outperform final_v23 claim.

## N8H FGO Feedback EKF Visual Validation Boundary

N8H visually validates FGO feedback EKF behavior.

FGO feedback remains an EKF update, not output substitution.

FGO feedback is not a direct NAV overwrite.

Position feedback remains disabled for the primary feedback variant unless a
diagnostic PVA variant is explicitly labeled.

Reject-all sanity must match the no-feedback baseline.

No trace/final_v23 tuning.

No trace solver input.

No final_v23 output solver input.

No output-only correction.

No future-data feedback.

No paper performance claim.

No outperform final_v23 claim.

## N8I Feedback Ablation Gate/Covariance Boundary

N8I reviews feedback gate, covariance, window, and mode policies.

Feedback tuning uses solver-visible diagnostics only.

Trace/final_v23 are not used for feedback tuning.

FGO feedback remains an EKF update, not output substitution.

FGO feedback is not a direct NAV overwrite.

Primary position feedback remains disabled unless a diagnostic PVA variant is
explicitly labeled.

Reject-all sanity must match the no-feedback baseline.

No trace solver input.

No final_v23 output solver input.

No output-only correction.

No future-data feedback.

No paper performance claim.

No outperform final_v23 claim.

## N8J Feedback Final Validation Boundary

N8J validates the selected FGO feedback EKF policy.

The selected feedback policy is locked from N8I.

N8J does not tune feedback using trace/final_v23.

FGO feedback remains an EKF update, not output substitution.

FGO feedback is not a direct NAV overwrite.

Runtime NAV/STD/EVAL/RUN_MANIFEST artifacts may be generated but are not
committed.

Primary position feedback remains disabled unless a diagnostic PVA reference is
explicitly labeled.

Reject-all sanity must match the no-feedback baseline.

No trace solver input.

No final_v23 output solver input.

No output-only correction.

No future-data feedback.

N8J is BY2 engineering validation only.

No paper performance claim.

No outperform final_v23 claim.

## N8K BY2 Formal Ablation Plot Audit Boundary

N8K is BY2 formal ablation and ablation plot audit.

N8K does not run the full degradation matrix.

N8K does not modify algorithm math or feedback policy.

N8K figures are engineering audit figures, not paper performance claims.

All BY2 plotting outputs are generated under the BY2 plot audit root.

N8K only generates the N9B degradation plan; it does not run N9B degradation
runtime outputs.

No trace/final_v23 tuning.

No trace solver input.

No final_v23 output solver input.

No output substitution.

No output-only correction.

No future-data feedback.

No paper performance claim.

No outperform final_v23 claim.

## N8K5 BY2 Formal Ablation Cross-Category Plot Semantic Fix Boundary

N8K2 fixed placeholder-like applicable plots.

N8K3 fixed same-category exact duplicate plots.

N8K4 fixed semantic filename mismatches.

N8K5 fixes same-variant cross-category exact duplicate and semantic leakage.

Exact duplicate checks must include same-variant cross-category blocking pairs,
not only same-category groups.

`compare_velocity_error` must not copy `velocity_residual_time`.

`compare_feedback_delta` must not copy `feedback_accept_reject_time`.

For non-feedback variants, feedback observation and feedback delta plots must be
documented not-applicable instead of empty accepted/rejected axes.

`derived_from_n8k_metrics_and_baseline_nav` is derived/surrogate visualization
data, not complete runtime variant NAV.

N8K5 does not modify algorithm math or feedback policy.

N8K5 does not run the full degradation matrix.

No trace/final_v23 tuning.

No trace solver input.

No final_v23 output solver input.

No paper performance claim.

No outperform final_v23 claim.

## N8K Final Merge Review Boundary

N8K final merge review is a pre-merge gate for PR #48.

It does not merge PR #48.

It does not create an N8K tag.

It does not start N9A or N9B.

It does not run the full degradation matrix.

It does not modify algorithm math or feedback policy.

The review must re-scan the current N8K review figure root instead of trusting
only report fields. After N8K6, this means the N8K6 figure root.

The review must treat no-feedback baseline variants as merge blockers if they
are incorrectly classified as feedback-applicable.

Ready-to-merge and ready-to-tag are explicit booleans and may be false even
when lower-level plot audits pass.

After the N8K6 rerun, the final merge review status is
`N8K_final_merge_review_passed`, with `ready_to_merge=true` and
`ready_to_tag=true`. That status authorizes only the next explicit merge/tag
stage; it does not merge PR #48 or create a tag by itself.

No trace/final_v23 tuning.

No paper performance claim.

No outperform final_v23 claim.

## N8K6 A0 Feedback Applicability Boundary

N8K6 is a targeted reporting and plot-classification fix for the A0 feedback
applicability blocker found by the N8K final merge review.

`A0_source_backed_ekf_baseline` remains `baseline_no_feedback`.

A0 feedback accept/reject remains `0/0`.

Raw detected feedback rows for A0 are audit evidence only; they do not make A0
feedback-applicable.

A0 effective feedback rows for plotting must be zero.

A0 feedback-specific plots must be documented not-applicable and must record
the ignored raw-row reason.

N8K6 does not modify algorithm math or feedback policy.

N8K6 does not run the full degradation matrix.

N8K6 does not use trace/final_v23 for tuning.

N8K6 makes no paper performance claim and no outperform final_v23 claim.

## N7B4 Literature-Informed Go2 Contact/Velocity Boundary

N7B4 contact probability is diagnostic.

Go2 velocity diagnostic activation is not a formal prior.

Literature-inspired contact probability uses Go2 fields only and does not use
trace/final_v23 output for threshold, frame, or prior tuning.

Go2 velocity is not truth.

Go2 contact probability is not truth.

No formal Go2 velocity prior.

No formal Go2 yaw prior.

No trace solver input.

No final_v23 output solver input.

No output-only correction, no tuning, no epoch deletion.

No FGO claim.

No paper performance claim.

No outperform final_v23 claim.

## N7B5 Go2 Velocity Frame Horizontal Diagnostic Boundary

N7B5 horizontal-only Go2 velocity diagnostic is not a formal prior.

Vertical Go2 velocity is not activated in horizontal-only diagnostic priors.

Go2 velocity is not truth.

Frame equivalence uses Go2/internal and receiver/raw cross-source consistency
only.

No trace/final_v23 frame tuning.

No formal Go2 velocity prior.

No formal Go2 yaw prior.

No trace solver input.

No final_v23 output solver input.

No output-only correction, no tuning, no epoch deletion.

No FGO claim.

No paper performance claim.

No outperform final_v23 claim.

## N7C3 Bounded Adaptive Go2 Horizontal Velocity Std Boundary

N7C3 adaptive std is bounded by robot-appropriate diagnostic limits.

std is measurement uncertainty, not speed command.

No std > 5 m/s in bounded policy.

Go2 velocity is not truth.

Vertical Go2 velocity remains disabled.

Go2 yaw prior remains disabled.

Go2 position prior remains disabled.

No trace/final_v23 tuning.

No trace solver input.

No final_v23 output solver input.

No output-only correction, no tuning, no epoch deletion.

No FGO claim.

No paper performance claim.

No outperform final_v23 claim.
## BY3A5/BY3A5B Dual Yaw Input Source Repair

BY3A5 audits the BY3 dual-yaw input source and correctly confirms the old BY3 15-column yaw was wrong-source. BY3A5's HDT replacement policy is diagnostic/rejected/superseded for mainline BY3 and must not be used as solver yaw input.

BY3A5B repairs the mainline yaw input with A1_dual_diff short-baseline yaw from GNSS1/GNSS2 absolute positions, BY2 sign/lateral conversion, and fixed_1p5 yaw_std. GNSS status long-baseline `rel_pos_n/e/d` and NMEA HDT are rejected as mainline solver yaw sources. BY3A6 superseded the BY3A5B readiness decision by validating trace/evaluator/base_time and repairing stale first-row initatt. BY3A7 then repaired the remaining BY3 Go2 IMU preprocessing issue. BY3A8 found the residual yaw error is limited by A1 observation quality; `ready_for_BY3_degradation_matrix_planning=true` only with `scope=position_up_with_diagnostic_yaw`, and `ready_for_paper_claims=false`.

## BY3A7 A1 Yaw Dynamic Quality IMU Gate Repair

BY3A7 may state that A1_dual_diff remains the mainline short-baseline yaw source with dynamic-quality caution, and that BY3 yaw failure after BY3A6 was dominated by a BY3 Go2 IMU preprocessing bug: gyro bias was estimated from a moving segment after selected Go2 start. BY3A7 repaired only a BY3A7-local IMU input using pre-motion source gyro bias, preserved FLU-to-FRD conversion, A1 yaw source, fixed_1p5 yaw_std, and yaw gate thresholds, and reran BY3 normal only.

Allowed BY3A7 runtime evidence: LegSA_full_EKF yaw RMSE about 5.26 deg and final_v23_dual_antenna_EKF yaw RMSE about 4.30 deg after the BY3A7 IMU preprocessing repair. This supports `ready_for_BY3_degradation_matrix_planning=true` only with `scope=full_after_human_review`.

Still forbidden: paper performance claims, final_v23 outperformance claims, PR #52 merge/tag/closure authorization, HDT or long-baseline rel_pos mainline yaw input, yaw-gate relaxation, trace solver input, RMSE-selected epoch deletion, and treating BY3A7 normal-only evidence as completed BY3 degradation/full-matrix execution.

## BY3A8 Yaw Error Budget Safe Repair

Allowed BY3A8 runtime evidence: A1-vs-trace heading lower-bound RMSE about 24.06 deg and p95 about 31.78 deg, A1 objective invalid epoch count of 6, no safe additional repair, no BY3A8 normal rerun, and planning scope `position_up_with_diagnostic_yaw`.

Still forbidden after BY3A8: paper yaw claims, final_v23 outperformance claims, full yaw degradation readiness without human review, HDT or long-baseline rel_pos fallback, trace-based yaw correction, metadata-free time shifting, yaw-gate relaxation, feedback-policy changes, RMSE-selected masks, and treating BY3A8 as completed BY3 degradation/full-matrix execution.

## BY3B Position Up With Diagnostic Yaw Planning

Allowed BY3B evidence: BY3A8 scope import, accepted-source lock, position/up family scope, case matrix, seed plan, provider/feedback dependency plan, dry-run command templates, evaluator/metric policy, figure/case-review plan, batch plan, and validation reports under `<BY3B_STAGE_ROOT>`.

Allowed BY3B planning counts: 118 planned case-seed units, including 75 position/up-primary units and 43 diagnostic-yaw units, with 311 future solver rows planned if later human-approved.

Still forbidden after BY3B: treating planning artifacts as generated degraded inputs, random arrays, solver/evaluator execution, generated figures, BY3 degradation completion, yaw robustness evidence, paper claims, final_v23 outperformance, HDT or long-baseline rel_pos fallback, old BY3 IMU use, BY2 feedback reuse, BY3 normal feedback reuse for degraded cases, PR #52 merge/closure/tag authorization, or automatic BY3C execution without human review.

## BY3C Position Up Degradation Batch0-Batch3 Execution

Allowed BY3C evidence: accepted-source lock, Batch 0 normal parity, Batch 1 deterministic A_outage/B_ratio_downsample/E_position_std_inflation, Batch 2 C_position_noise seeds 0..9, Batch 3 D_position_spike seeds 0..9, official evaluations, same-case feedback generated from each case's stage1 official EVAL_NAV state/estimate columns, figures, case reviews, consolidated metrics, and validation reports under `<BY3C_STAGE_ROOT>` and `<BY3_FULL_MATRIX_ROOT>/BY3C_POSITION_UP_DEGRADATION_EXECUTION`.

Allowed BY3C counts: 71 executed case units, 213 final metric rows across `LegSA_full_EKF`, `single_antenna_gnss1_status_KF_GINS`, and `final_v23_dual_antenna_EKF`, 30 Batch 2 case reviews, 30 Batch 3 case reviews, and 12 consolidated figure rows.

BY3C keeps horizontal/up metrics primary and yaw diagnostic-only. BY3C may state `ready_for_BY3D_diagnostic_yaw_or_mixed_planning=true` only as a human-review-gated planning readiness flag, not as authorization to execute yaw, mixed, module-disable, LegSA_9F_FGO_EKF, nonredundant-FGO, or full monolithic BY3 matrix cases.

Still forbidden after BY3C: paper performance claims, paper yaw claims, final_v23 outperformance claims, full BY3 matrix completion claims, yaw robustness claims, treating diagnostic yaw columns as primary metrics, using BY3C outputs as solver inputs, reusing BY3 normal feedback for degraded cases, or treating PR #52 as merge/closure/tag approved.

## BY3C1/BY3Y1 Position/Up Review And Yaw Diagnostic Explanation

Allowed BY3C1/BY3Y1 evidence: result-integrity audit, BY3 three-scheme position/up comparison tables, family reviews, overlapping BY2-vs-BY3 generalization summaries, review figures generated from existing metrics only, export-clean summaries, and BY3Y1 yaw diagnostic explanation under `<BY3C1_STAGE_ROOT>`, `<BY3C1_REVIEW_PACKAGE_ROOT>`, `<BY3Y1_STAGE_ROOT>`, and `<BY3C1_EXPORT_CLEAN_ROOT>`.

Allowed BY3C1/BY3Y1 statements: 71 BY3 case units and 213 final metric rows were reviewed; BY3 position/up behavior is family-dependent; B downsample is classified as `generalizes_consistently` in the review package; normal, A outage, E position std, C position noise, and D position spike are same-order or mixed and do not support paper-ready advantage claims; BY3 yaw remains diagnostic-only.

Allowed BY3Y1 yaw explanation: wrong-source yaw, stale first-row initatt, and BY3 Go2 IMU moving-segment gyro-bias issues were repaired before BY3C; BY3A8 shows A1 observation quality remains the limiting factor, with A1-vs-trace heading RMSE about 24.06 deg and p95 about 31.78 deg; selected feedback worsened normal diagnostic yaw relative to stage1 by about 1.03 deg.

Still forbidden after BY3C1/BY3Y1: paper performance claims, paper yaw claims, final_v23 outperformance claims, BY3 yaw robustness claims, treating review figures as new solver/evaluator evidence, treating BY3C1/BY3Y1 as authorization for BY3D execution, running H_dual_yaw_noise/E_yaw_std/mixed/module/full-matrix/LegSA_9F/nonredundant cases without explicit human approval, or treating PR #52 as merge/closure/tag approved.
