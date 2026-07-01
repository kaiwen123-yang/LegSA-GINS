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

## GEN1 BY2-BY3 Generalization Report And BY3 Figure Organization

Allowed GEN1 evidence: BY2 and BY3 metric inventories with 213 rows each across 71 comparable case units, canonical BY2-BY3 family mapping, cross-dataset three-scheme family/case/delta summaries, cross-dataset metric figures generated from existing metrics only, BY3 figure inventory, copy-only BY3 figure organization under `<BY3_FIGURE_SUMMARY_ROOT>`, export-clean reports/tables, and Obsidian notes.

Allowed GEN1 statements: BY3 already has normal and degradation figure material, but figure classification is only partial for paper-facing use; BY3 yaw figures remain diagnostic-only; original BY3 runtime figures were not moved or deleted; 874 unique nonempty BY3 figure files were copied into the organized view; `ready_for_paper_claims=false`.

Still forbidden after GEN1: paper performance claims, paper yaw claims, final_v23 outperformance claims, comprehensive LegSA superiority claims, treating copied or generated figures as new solver/evaluator evidence, treating export-clean tables as paper approval, running BY3D/mixed/yaw/module/full-matrix/LegSA_9F/nonredundant cases without explicit human approval, or treating PR #52 as merge/closure/tag approved.

## XB1 Poor-GNSS Generalization Bootstrap

Allowed XB1 evidence: literature-backed GNSS quality criteria, receiver/body inventory, GNSS quality profile, kick-event alignment without trace tuning, repaired body IMU generated from `<XB1_BODY_SOURCE>`, Go2 attitude/horizontal velocity/joint priors, A1 short-baseline quality audit, Raw Doppler provider failure report, real GNSS quality figures, case review, and export-clean material under `<XB1_STAGE_ROOT>` and `<XB1_EXPORT_CLEAN_ROOT>`.

Allowed XB1 statements: XB1 / PG1_20260105_122513 is the first poor-GNSS repeated experiment; GNSS quality is classified `severe`; kick-event alignment passed; trace is evaluation-only; receiver `imu-data.csv` is diagnostic-only; status long-baseline `rel_pos_n/e/d` and HDT were rejected as mainline yaw sources; normal solver/evaluator execution did not run because input/provider gates blocked it; a future quality-aware branch may be planned only after human review.

Still forbidden after XB1: paper performance claims, poor-GNSS robustness claims, final_v23 outperformance claims, artificial degradation matrix execution, parameter retuning, trace-tuned thresholds, trace solver input, final_v23 or single-output solver input, receiver IMU as body IMU, long-relpos/HDT yaw fallback, output-only correction, treating blocked normal figures as real result figures, PR #52 merge/closure/tag approval, or treating XB1 as authorization to run PG2/degradation/adaptation without explicit human approval.

## XB1A1 Blocker Triage And Normal Gate

Allowed XB1A1 evidence: Raw Doppler toolchain audit, WSL gcc/helper bridge tests, source-backed XB1 Raw Doppler provider materialization through the accepted RTKLIB/RINEX/helper path, A1 short-baseline yaw gate audit, algorithm applicability decision, single-baseline normal official evaluation, quality-aware branch planning report, figures, case review, and validation reports under `<XB1A1_STAGE_ROOT>` and `<XB1A1_NORMAL_GATE_ROOT>`.

Allowed XB1A1 statements: Raw Doppler provider materialization is repaired for XB1 with a schema-valid 1809-row provider; A1 short-baseline dual yaw remains invalid due GNSS quality/geometry; objective valid A1 epochs are about 1.95 percent; `LegSA_full_EKF` remains blocked because forcing it without valid A1 dual yaw would change the current algorithm identity; `final_v23_dual_antenna_EKF` is not applicable without valid dual yaw; `single_antenna_gnss1_status_KF_GINS` completed normal official evaluation as a diagnostic baseline only; a separate quality-aware diagnostic branch is recommended for planning after human review.

Still forbidden after XB1A1: paper performance claims, poor-GNSS robustness claims, treating the single-baseline result as LegSA_full or final_v23 evidence, artificial degradation matrix execution, parameter retuning, quality-aware execution, trace-tuned thresholds, trace solver input, fabricated Raw Doppler/A1 yaw/provider/evaluator outputs, GNSS receiver velocity substituted as Raw Doppler, receiver IMU as body IMU, long-relpos/HDT yaw fallback, forcing dual-yaw solvers when A1 is invalid, PR #52 merge/closure/tag approval, or treating XB1A1 as authorization to run PG2/degradation/adaptation without explicit human approval.

## XB1A2 A1 Relpos-Difference Reaudit

Allowed XB1A2 evidence: XB1A1 A1 source-provenance review, BY2/process_data-compatible status relpos-difference recovery, BY3A5B absolute-position repair recovery, XB1 candidate baseline source audit, detailed relpos-difference epoch-quality audit, antenna/lateral policy gate, blocked repaired-input report, blocked normal-run gate, quality-aware branch decision update, figures, case review, and validation reports under `<XB1A2_STAGE_ROOT>` and `<XB1A2_RELPOS_DIFF_REPAIR_ROOT>`.

Allowed XB1A2 statements: XB1A1's A1 invalid conclusion is suspended/superseded on source provenance because it did not audit the BY2 status `rel_pos_gnss2-rel_pos_gnss1` dual-difference path; XB1A2 audited that path and still found it nonphysical for XB1, with about 1.97 percent physical-band epochs, median length about 9.18 m, p95 about 50.96 m, and max about 131.70 m. XB1A2 also audited the BY3A5B absolute-position candidate, which remains nonphysical for XB1. Single status `rel_pos_n/e/d` direct remains rejected as a long RTK base-vector source, HDT remains diagnostic-only, no repaired dual-yaw input was generated, and dual-yaw normal algorithms remain blocked/not applicable.

Still forbidden after XB1A2: paper performance claims, poor-GNSS robustness claims, treating XB1A2 as evidence that LegSA_full_EKF or final_v23 ran on XB1, artificial degradation matrix execution, parameter retuning, quality-aware execution, trace-tuned thresholds, trace solver input, fabricated A1 yaw/provider/evaluator outputs, single rel_pos direct yaw, long-relpos/HDT yaw fallback, forcing dual-yaw solvers when A1 is invalid, using absolute LLH difference as BY2 status-yaw evidence, PR #52 merge/closure/tag approval, or treating XB1A2 as authorization to run PG2/degradation/adaptation without explicit human approval.

## PG_MULTI_A0 Poor-GNSS Multi-Repeat Review Boundary

Allowed PG_MULTI_A0 evidence: PG1/XB1 import from XB1A2, PG2/PG3/PG4 receiver-root registration through aliases, PG2/PG3/PG4 user-locked body/high-level source registration through aliases, receiver file inventory and role classification, body/high-level parse and overlap feasibility, GNSS quality profiles, BY2-compatible status relpos-difference A1 availability audit, Raw Doppler provider feasibility audit, runnability classification, recommendation, validation reports, and alias-only Obsidian notes under `<PG_MULTI_A0_STAGE_ROOT>`.

Allowed PG_MULTI_A0 statements: PG1/XB1 remains the imported XB1A2 severe poor-GNSS result; PG2/PG3/PG4 receiver roots and body/high-level sources were registered and parseable; receiver `imu-data.csv` remains diagnostic-only and was not used as body IMU; all future poor-GNSS A1 invalidity decisions must audit `gnss2.rel_pos_interp - gnss1.rel_pos` before rejection; PG2/PG3/PG4 relpos-diff A1 candidates are nonphysical with zero physical-band epochs; Raw Doppler provider feasibility is imported-ready for PG1 and likely-ready for PG2-PG4 without generating full providers; PG1-PG4 are classified as `quality_aware_branch_candidate` with position-only fallback as diagnostic only; `ready_for_paper_claims=false`.

Still forbidden after PG_MULTI_A0: paper performance claims, poor-GNSS robustness claims, frozen dual-yaw mainline execution, solver/evaluator execution, artificial degradation, random array generation, parameter retuning, quality-aware branch implementation or execution, trace-tuned thresholds, trace solver input, final_v23 solver input, receiver IMU as body IMU, single rel_pos direct yaw, absolute LLH fallback as BY2 status-yaw evidence, HDT mainline yaw, forcing dual-yaw solvers when A1 is invalid, PR #52 merge/closure/tag approval, or treating PG_MULTI_A0 as authorization to run a selected PG normal case without a later human decision.

## PG_QA0 Quality-Aware Fallback Design Boundary

Allowed PG_QA0 evidence: BY2/BY3/PG evidence import, `LegSA_full_EKF` frozen-mainline identity lock, separate `LegSA_QA_Fallback_EKF` design identity, quality-state machine S0-S6, measurement ownership policy, R-scale threshold-source policy, Raw Doppler and Go2 bridge policy, logging schema, implementation roadmap, validation protocol, risk register, paper-mainline decision matrix, export-clean package, validation reports, and alias-only Obsidian notes under `<PG_QA0_STAGE_ROOT>`.

Allowed PG_QA0 statements: BY2/BY3 position-up generalization remains the main proven line; BY3 yaw remains diagnostic-only and should not block the near-term paper; PG1-PG4 severe GNSS data motivate a future quality-aware fallback; `LegSA_QA_Fallback_EKF` is design-only, not implemented, not validated, and not a relabeling of `LegSA_full_EKF` or final_v23; the near-term paper recommendation is Option B with QA as design/limitation extension and no QA performance claim; Option C requires later human-approved QA1/QA2/QA3 implementation and validation; `ready_for_paper_claims=false`.

Still forbidden after PG_QA0: paper performance claims, poor-GNSS robustness claims, quality-aware branch implementation or execution, solver/evaluator execution, artificial degradation, random array generation, parameter retuning, trace-tuned thresholds, trace solver input, final_v23 solver input, receiver IMU as body IMU, long-relpos/HDT yaw fallback, forcing A1 yaw when invalid, relabeling `LegSA_full_EKF`, relabeling final_v23, PR #52 merge/closure/tag approval, or treating QA0 as authorization to start QA1 without human review.

## PAPER0 Mainline Evidence Package Boundary

Allowed PAPER0 evidence: paper-facing evidence inventory, BY2 main evidence synthesis, BY3 position/up generalization synthesis with diagnostic-only yaw, BY2-vs-BY3 cross-dataset synthesis, PG severe-GNSS boundary synthesis, QA0 design-extension synthesis, paper table drafts, figure recommendation list, claim-boundary matrix, journal-positioning notes, missing-work report, export-clean package, validation reports, and alias-only Obsidian notes under `<PAPER0_STAGE_ROOT>`.

Allowed PAPER0 statements: BY2 is organized as the full-metric main dataset for near-term manuscript drafting; BY3 is organized as an independent position/up generalization dataset with yaw diagnostic-only; PG1-PG4 are severe-GNSS boundary datasets and motivate QA fallback but do not prove algorithm performance; PG_QA0 remains a design extension, not an implemented contribution; the near-term paper can start manuscript drafting without QA1; QA1 is optional for a stronger secondary-contribution route; `ready_for_manuscript_drafting=true`; `ready_for_QA1=false`; `ready_for_paper_claims=false`.

Still forbidden after PAPER0: final paper performance claims, final paper figure authorization, solver/evaluator execution, artificial degradation, random array generation, QA1 implementation, parameter retuning, metric alteration, fabricated figures/tables, BY3 yaw main claim, PG performance claim, comprehensive final_v23 superiority claim, quality-aware implementation or validation claim, PR #52 merge/closure/tag approval, staging PAPER0 runtime outputs, or staging Obsidian notes.

## PAPER10X Git Context Cleanup And Next Direction Boundary

Allowed PAPER10X work: Git dirty-state audit, tracked and untracked context review, `.gitignore` hardening, alias-safe context-doc updates, lightweight C export, Obsidian project-vault sync, current content summary, next-experiment direction freeze, and local context commit after staged-file safety scan.

Allowed PAPER10X statements: `LegSA_full_EKF` is the verified main algorithm identity; `final_v23_dual_antenna_EKF` is a strong external Dual-Antenna GNSS/INS EKF baseline; Raw Doppler and source-aware LSIM/OIM R scaling are accepted mainline modules; BY2 source-aware 120 x 5 is closed; BY3 source-aware 120 x 5 is closed as position/up and poor-heading-stress evidence with yaw diagnostic-only; default `python3` and conda were repaired in PAPER10B_R2C.

PAPER10X must keep `ready_for_paper_claims=false`. It may recommend PAPER10C, PAPER10B2, PAPER10D, PAPER10E, and PAPER10F, but it does not authorize running any of them.

Still forbidden after PAPER10X unless later reviewed evidence proves otherwise: universal source-aware superiority, comprehensive final_v23 outperform claims, BY3 ordinary yaw generalization, complete nine-factor FGO, completed `LegSA_QA_Fallback_EKF`, full contact-aided InEKF, source-aware as complete multi-state quality management, external DA/LC official-exact reproduction claims, trace online, receiver `imu-data.csv` as Go2 body IMU, per-case tuning, staging runtime outputs, staging raw data, staging generated figures, staging archives, or staging local path manifests.

## PAPER4A Write-Ready Evidence Package Boundary

Allowed PAPER4A evidence: completed-stage final reports, row-level master tables, provider summaries, claim-boundary tables, render QA summaries, export indices, and consolidated PAPER2B secondary proof for PAPER1F if direct PAPER1F paths are missing. PAPER4A outputs are lightweight reports and context updates under `<PAPER4A_STAGE_ROOT>`.

PAPER4A consolidates completed evidence; it does not close body-yaw, exact reproduction, or same-evaluator superiority.

Allowed PAPER4A main-text statements:

- BY2 is the full-metric main dataset, BY3 is poor-heading/position-up stress with diagnostic-only yaw, and XB/PG are poor-GNSS stress and QA-fallback motivation.
- PAPER2A supports quality-aware measurement management behavior with seven recognized GNSS/INS QA methods across BY2/BY3/XB, while preserving `trace_used_online=false` and `receiver_imu_data_as_body_imu=false`.
- PAPER3D-R2 through PAPER3I support provider construction from RTKLIB/RINEX/common epoch/satellite to GPS/BDS DD/LOS/covariance/residual-ready evidence, with non-GPS blockers stated.
- PAPER3E/F/G/H/I external literature modules may be described as PDF-grounded native/proxy/backend-level implementations and DD/LOS-backed literature module diagnostics, not exact reproductions.

Allowed PAPER4A appendix statements:

- PAPER2A row-level QA behavior can be tabulated with common-backend QA-wrapper wording.
- PAPER3E/F/G/H/I native/proxy/backend-level metrics, LAMBDA/MLAMBDA helper integration, provider v4 system/frequency coverage, Pavlasek/Wu diagnostics, RTKLIB moving-base diagnostics, and internal baseline error-series coverage may be shown with implementation-level and diagnostic labels.

Diagnostic-only after PAPER4A:

- yaw transform sensitivity, baseline-heading diagnostics, RTKLIB moving-base output, BY3 yaw, XB/PG severe-GNSS outputs, Pavlasek IEKF provider diagnostics, Wu EQKF/PAR/ADOP diagnostics, and PAPER1F adapter evidence.

Still forbidden after PAPER4A:

- body-yaw RMSE from external methods;
- yaw superiority;
- final_v23, LegSA_QA, or LegSA_full same-evaluator superiority;
- exact reproduction of external algorithms;
- five full faithful external dual-antenna algorithms;
- BY3 ordinary yaw generalization;
- XB severe-GNSS high-precision proof;
- RTKLIB moving-base equals Teunissen/Yang/Liu/Wu reproduction;
- trace online use, trace-tuned thresholds, or trace-derived feedback;
- receiver `imu-data.csv` as Go2 body IMU;
- full contact-aided or joint-foot kinematic constraint claims without backend and ablation proof;
- full Galileo/GLONASS/SBAS provider closure.

PAPER4A does not authorize solver/evaluator execution, degraded-input generation, random array generation, figure rendering, parameter retuning, algorithm changes, RTKLIB source modification, external-code modification, runtime/raw/RINEX/UBX/RTCM staging, Obsidian staging, push, PR merge/closure/tag, final paper figures, or final paper claims.

## PAPER4B_R2 Physical Frame And Offline Body-Yaw Boundary

Allowed PAPER4B_R2 evidence: user-confirmed physical installation facts, official GNSS extrinsics values recorded from the PAPER4B_R2 prompt excerpt, photo/PDF/STEP/STL evidence indices, `FRAME_POLICY_ACCEPTED.yaml`, method yaw semantics audit, fixed-transform derived offline yaw reevaluation summaries, render-QA reports, figure/table indices, and reviewer/supervisor reports under `<PAPER4B_R2_STAGE_ROOT>` and `<PAPER4B_R2_EXPORT_ROOT>`.

Allowed PAPER4B_R2 statements:

- The physical antenna-to-body geometry is closed for the user-confirmed BY2 installation: receiver front faces Go2 forward, GNSS1 is robot-right with negative y, GNSS2 is robot-left with positive y, and GNSS1->GNSS2 points to body `+Y_left` under Go2 FLU.
- The fixed physical transform from a GNSS1->GNSS2 NED baseline heading to Go2 body yaw is `body_yaw_NED_deg = wrap360(baseline_heading_NED_deg + 90 deg)`.
- PAPER3F/PAPER3G/PAPER3H rows whose native heading semantics are explicit `atan2(E,N)` may be reported as derived offline body-yaw reevaluation results, with trace used only by the offline evaluator.
- PAPER3I Wu EQKF DD/LOS row headings and Pavlasek IEKF innovation diagnostics remain diagnostic/blocked for case-level body-yaw metrics unless a later stage provides baseline-state epoch outputs with closed semantics.

Still forbidden after PAPER4B_R2:

- exact reproduction of external algorithms;
- five full faithful external dual-antenna algorithms;
- RTKLIB moving-base equals Teunissen/Yang/Liu/Wu reproduction;
- final_v23, LegSA_QA, LegSA_full, or universal same-evaluator superiority;
- BY3 ordinary yaw generalization unless BY3 frame/reference is separately closed;
- XB severe-GNSS high-precision proof;
- trace online use, trace-tuned thresholds, trace-selected yaw transforms, or per-case RMSE offset selection;
- receiver `imu-data.csv` as Go2 body IMU;
- mutation or replacement of historical `epoch_output.csv`;
- raw/runtime/RINEX/UBX/RTCM/external-code staging;
- final paper claims without later reviewer approval.

## PAPER4G Frozen Yaw Boundary And Native Metrics Route

PAPER4G freezes the post-PAPER4F_R2 yaw claim boundary.

Frozen facts:

- PAPER4B_R2 closes the physical GNSS1-right/GNSS2-left lateral frame.
- PAPER4D/E close trace yaw source to `user_io-out-poi_geodetic.csv:ypr.vector3.x`.
- PAPER4F_R2 applies the user-declared BY2 minimal-export policy `trace_body_yaw_NED_deg = wrap360(trace_yaw_deg + 90 deg)`.
- PAPER4F_R2 reevaluates 2160/2160 vector-closed PAPER3F/PAPER3G/PAPER3H method-case rows.
- The systematic yaw discrepancy remains: median previous-policy RMSE about 94.65 deg, median user-policy RMSE about 106.09 deg, and 90-degree-like systematic case ratio about 0.9875.

Allowed after PAPER4G:

- physical GNSS1-right/GNSS2-left frame closure as an installation/setup fact;
- trace yaw source and minimal-export policy audit as appendix evidence;
- native DD/LOS baseline, residual, ambiguity, provider-readiness, ratio/ADOP, and fix-rate-proxy metrics as external literature method supporting evidence;
- PAPER4F_R2 body-yaw reevaluation tables only as diagnostic-only evidence.

Still forbidden after PAPER4G:

- body-yaw RMSE claim;
- external-method yaw superiority;
- final_v23 / LegSA_QA / LegSA_full superiority;
- same-evaluator superiority unless separately proven;
- BY3 yaw generalization;
- XB severe-GNSS high-precision proof;
- exact/full faithful external reproduction;
- RTKLIB as Teunissen/Yang/Liu/Wu exact reproduction;
- trace online use;
- receiver IMU as Go2 body IMU;
- full Galileo/GLONASS/SBAS provider closure.

## PAPER10C Go2 High-Level Prior Boundary

Allowed after PAPER10C:

- Go2 roll/pitch weak prior code is implemented and can enter EKF update through source-aware `go2_attitude_roll_pitch` when enabled.
- Go2 horizontal velocity weak prior code is implemented and can enter EKF update through source-aware `go2_horizontal_velocity` when controlled horizontal mode is enabled.
- BY2 Go2 weak-prior ablation is closed for runnable modes G00/G01/G02/G04 under fixed `SA04_N6B_POLICY`.
- Go2 can be described as a bounded auxiliary weak-prior cue for the legged platform, with BY2 evidence and explicit boundaries.

Boundary after PAPER10C:

- Go2 readiness/contact/motion-state metadata is diagnostic or future work until first-class LSIM metadata integration is implemented and validated.
- BY3 Go2 weak-prior runtime is blocked by missing BY3 Go2 prior provider evidence in the current workspace; BY3 yaw remains diagnostic-only.
- Performance effects are small and mixed; do not write universal metric improvement.

Still forbidden after PAPER10C:

- Go2 position or Go2 yaw as truth;
- Go2 vertical velocity as a main constraint;
- receiver `imu-data.csv` as Go2 body IMU;
- Go2 weak prior as full contact-aided InEKF, full leg odometry, or support-foot FK;
- BY3 ordinary yaw generalization;
- universal superiority or comprehensive final_v23 outperformance;
- trace online use, final_v23/LegSA output solver input, bad-epoch deletion, or per-case tuning;
- complete nine-factor FGO or completed `LegSA_QA_Fallback_EKF` claims.

## PAPER10C_R1A Interrupted Go2 BY3 Matrix Resume Boundary

Allowed after PAPER10C_R1A:

- PAPER10C_R1A may state that the interrupted PAPER10C_R1 runtime was scanned without overwriting completed rows.
- PAPER10C_R1A may state that BY2 Go2 120x6 is closed at 720/720 completed-evaluable rows.
- PAPER10C_R1A may state that BY3 Go2 providers were recovered from BY3 `by3.txt`, including roll/pitch, horizontal velocity, and readiness/motion-state providers.
- PAPER10C_R1A may state that BY3 readiness/motion-state enters first-class LSIM metadata in completed G03/G05 rows.
- PAPER10C_R1A may state that a resume manifest and missing-only wrapper are ready.

Boundary after PAPER10C_R1A:

- BY3 Go2 120x6 remains partial: 543/720 completed-evaluable, 169 missing, and 8 partial/corrupted rows.
- The missing-only wrapper was not executed because the Windows E free-space gate failed.
- Go2 can be described as bounded weak-prior and LSIM metadata support, not as a closed main paper innovation.
- PAPER10B2 multi-state quality management remains future work.
- BY3 yaw remains diagnostic-only.

Still forbidden after PAPER10C_R1A:

- claiming full BY2/BY3 Go2 full-ablation closure;
- claiming Go2 position or Go2 yaw as truth;
- claiming full contact-aided InEKF, full leg odometry, or support-foot FK;
- claiming BY3 ordinary yaw generalization;
- claiming universal superiority or final_v23 outperformance;
- claiming completed PAPER10B2 multi-state quality management;
- claiming complete nine-factor FGO;
- using trace online, final_v23/LegSA output as solver input, bad-epoch deletion, or per-case tuning.

## PAPER10C_R1B Low-Space BY3 Missing-Only Resume Boundary

Allowed after PAPER10C_R1B:

- PAPER10C_R1B may state that the R1A low-space blocker was resolved by a human-approved E hard-stop of 5 GB and WSL root hard-stop of 20 GB.
- PAPER10C_R1B may state that only BY3 rows marked missing/partial/corrupted were rerun.
- PAPER10C_R1B may state that BY2 Go2 120x6 remains closed at 720/720 and BY3 Go2 120x6 is now closed at 720/720.
- PAPER10C_R1B may state that BY3 Go2 providers are by3.txt-derived and not BY2-provider reuse.
- PAPER10C_R1B may state that readiness/motion-state metadata is first-class LSIM metadata in G03/G05 rows.
- PAPER10C_R1B may describe Go2 roll/pitch, horizontal velocity, and readiness/motion-state metadata as bounded source-aware auxiliary-prior/LSIM metadata support.

Boundary after PAPER10C_R1B:

- Go2 is a supporting or secondary innovation candidate, not a universal performance-superiority claim.
- BY3 yaw remains diagnostic-only.
- Performance effects are mixed, so wording must emphasize mechanism and bounded metadata routing.
- PAPER10B2 multi-state quality management remains separate future work unless explicitly executed.

Still forbidden after PAPER10C_R1B:

- claiming Go2 position or Go2 yaw as truth;
- claiming BY3 ordinary yaw generalization;
- claiming full contact-aided InEKF, full leg odometry, support-foot FK, or complete nine-factor FGO;
- claiming universal superiority or final_v23 outperformance;
- using trace online, final_v23/LegSA output as solver input, bad-epoch deletion, or per-case tuning;
- claiming external DA/LC/GINav/MATLAB/RTKLIB/contact-aided reproduction from this stage.

## PAPER10Y Post-R1B Archive And Cleanup Boundary

Allowed after PAPER10Y:

- PAPER10Y may state that PAPER10C_R1B evidence was rechecked and accepted as the current Go2 closure source.
- PAPER10Y may state that selected completed WSL runtime/worktree material was archived under `<PAPER10Y_ARCHIVE_ROOT>` using tar.xz fallback archives.
- PAPER10Y may state that all selected archives passed integrity verification and SHA256 recording.
- PAPER10Y may state that only verified WSL source directories or clean verified worktrees were removed, releasing about 67.1 GB of WSL internal space.
- PAPER10Y may state that a Windows Administrator PowerShell compact script was generated.
- PAPER10Y may recommend `PAPER10B2_MULTI_STATE_QUALITY_MANAGEMENT_CLOSURE` as the next route if the paper keeps multi-state quality management as a main innovation.

Boundary after PAPER10Y:

- PAPER10Y is maintenance evidence, not algorithm or performance evidence.
- `fstrim` was attempted but not completed because sudo required a password.
- VHDX compact is pending a manual Windows Administrator PowerShell step and was not executed inside WSL.
- Source-aware LSIM/OIM and Go2 evidence remain bounded by prior stages; PAPER10Y does not expand their claims.
- PAPER10B2 remains future work until separately executed.

Still forbidden after PAPER10Y:

- claiming any new solver/evaluator, DA, LC, GINav, MATLAB, RTKLIB, contact-aided, complete FGO, PAPER10B2, or PAPER10E evidence from this stage;
- claiming universal superiority, complete nine-factor FGO, full contact-aided InEKF, full leg odometry, BY3 ordinary yaw generalization, or completed `LegSA_QA_Fallback_EKF`;
- claiming Go2 position or Go2 yaw as truth;
- using trace online, final_v23/LegSA output as solver input, bad-epoch deletion, or per-case tuning;
- treating archive/cleanup success as paper performance evidence.

## PAPER10B2 Multi-State Quality Management Boundary

Allowed after PAPER10B2:

- PAPER10B2 may state that a source-level multi-state QM state machine was implemented above source-aware `SA04_N6B` LSIM/OIM and Go2 `G05_FULL_AUX` readiness/motion-state metadata.
- PAPER10B2 may state that the fixed states are `NORMAL`, `DOWNWEIGHT`, `REJECT`, `HOLD`, `RECOVERY`, and `FALLBACK`.
- PAPER10B2 may state that QM is default-off under `QM00_OFF` / `enable_multi_state_qm=false`.
- PAPER10B2 may state that state/action/recovery traces were generated.
- PAPER10B2 may state that targeted unit/integration tests and `legsa_v23_port_core_demo` build passed.
- PAPER10B2 may state that BY2 QM matrix completed 600/600 rows.
- PAPER10B2 may state that BY3 completed 579/600 rows before the user-defined `E_DRIVE_HARD_STOP=10GB` stopped the runner, with 21 missing-only resume rows preserved.
- PAPER10B2_R1 may state that the 10GB hard-stop was cancelled by human instruction, emergency stops were set to E=2GB and WSL root=20GB, and only the prior BY3 missing-only manifest was processed.
- PAPER10B2_R1 may state that 7 complete-but-unindexed BY3 artifacts were harvested, 14 missing-only rows were executed with jobs=8, BY3 closed at 600/600, and BY2 remained 600/600 without rerun.
- PAPER10B2_R1 may state that the final status is `CONDITIONAL_PASS_QM_FULL_MATRIX_COMPLETED_PERFORMANCE_MIXED`.

Boundary after PAPER10B2:

- The old `CONDITIONAL_PASS_QM_RUNTIME_STOPPED_BY_10GB_HARD_STOP` status is superseded by R1 for matrix completion, but remains historical evidence of why R1 was needed.
- Current QM evidence enum is `QM_MAIN_MECHANISM_READY_AS_BOUNDED_METHOD_NOT_UNIVERSAL_PERFORMANCE_CLAIM`.
- BY3 full-matrix closure may be claimed as 600/600 runtime completion only; final positive paper wording still requires human review because performance remains mixed.
- BY3 yaw remains diagnostic-only and cannot be written as ordinary yaw generalization.
- Performance wording must be bounded by dataset and family; BY2 horizontal behavior and vertical behavior are mixed.
- Fallback means conservative partial-source fusion, not output substitution.
- Source-aware LSIM/OIM and Go2 readiness are inputs/layers, not synonyms for the full multi-state QM mechanism.

Still forbidden after PAPER10B2:

- claiming universal superiority or final_v23 outperformance;
- claiming universal `QM_MAIN_INNOVATION_READY` or all-family performance superiority from R1;
- claiming BY3 ordinary yaw generalization;
- claiming trace online use, final_v23/LegSA output as solver input, output substitution, bad-epoch deletion, or per-case tuning;
- claiming Go2 position or Go2 yaw as truth;
- claiming external DA/LC/GINav/MATLAB/RTKLIB/contact-aided/full InEKF/complete nine-factor FGO reproduction from this stage;
- committing raw data, by2/by3 text, NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, archives, or runtime-heavy outputs.

## PAPER10G Legged Observability Diagnostic Boundary

Allowed after PAPER10G:

- PAPER10G may state that IMU plus legged proprioceptive/contact/high-level sensing alone leaves global translation and gravity-axis yaw unobservable without an external/global reference.
- PAPER10G may state that gravity constrains tilt but does not define absolute heading.
- PAPER10G may state that Go2 high-level roll/pitch is a weak tilt prior, Go2 horizontal velocity is a weak/diagnostic motion constraint, and Go2 readiness/motion-state is LSIM/QM metadata.
- PAPER10G may state that short lateral dual-antenna GNSS yaw is required as the absolute heading source and must be interpreted through body-yaw semantic conversion.
- PAPER10G may state that source-aware weighting and multi-state QM are motivated by heterogeneous source observability and reliability.
- PAPER10G may recommend PAPER10H XB/PG boundary diagnostics for severe-GNSS source-risk and QM state/action/recovery visualization.

Boundary after PAPER10G:

- PAPER10G is a theory/diagnostic and paper-packaging stage, not a new estimator or new algorithm-performance matrix.
- The symmetry/gauge demo and yaw-rate diagnostic are lightweight offline diagnostics; they are not solver inputs and do not use trace online.
- Go2 high-level state is not full contact-aided InEKF, support-foot FK odometry, or complete proprioceptive odometry.
- Literature claims are limited to observability/motivation boundaries; they do not assert that contact-aided InEKF is ineffective.
- BY3 yaw remains diagnostic-only and cannot be converted into ordinary yaw generalization by PAPER10G.

Still forbidden after PAPER10G:

- claiming Go2 yaw or Go2 position as ground truth;
- claiming legged-only sensing provides absolute yaw or global position;
- claiming full contact-aided InEKF, full leg odometry, Hartley full reproduction, or complete nine-factor FGO was completed;
- claiming universal superiority, final_v23 outperformance, BY3 ordinary yaw generalization, trace online use, final_v23/LegSA output solver input, output substitution, bad-epoch deletion, or per-case tuning;
- using receiver `imu-data.csv` as Go2 body IMU;
- staging raw data, by2/by3 text, NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, archives, core dumps, runtime-heavy outputs, or files over 50 MB.

## PAPER10G_R2 Real LSE Reproduction Boundary

Allowed after PAPER10G_R2:

- PAPER10G_R2 may state that initial formula-level/proxy-bounded legged-state-estimation method labels were executed on BY2/BY3 real Go2 high-level sequences, but its original method-distinctness evidence is superseded by PAPER10G_R2A.
- PAPER10G_R2 may state that PDF identity and duplicate decisions were locked for Teng 2104.04238, Rotella 1402.5450, Hartley 1805/1904, Hartley/Mangelson/Gan 1712, and Rotella dissertation support material.
- PAPER10G_R2 may state that BY2/BY3 Go2 providers were built from IMUState, `foot_force`, `foot_position_body`, `foot_speed_body`, velocity, mode/gait, and body-height fields.
- PAPER10G_R2 may state that LSE outputs are local proprioceptive odometry/attitude/velocity support and can motivate Go2 weak priors or QM metadata.
- PAPER10G_R2 may report aligned relative trajectory/drift metrics and relative-yaw-drift diagnostics.
- PAPER10G_R2 may mark absolute yaw RMSE as `NOT_APPLICABLE_WITH_PROOF`.

Boundary after PAPER10G_R2:

- `foot_position_body` is a high-level FK-like proxy, not raw joint encoder FK.
- Hartley official code availability does not imply author-official exact reproduction because no compatible Go2 official adapter was executed.
- Rotella flat-foot rotational constraints are not applicable to Go2 high-level point-foot/quadruped data.
- Teng tracking-camera velocity/angular-velocity branch is blocked; only a camera-off adapted subset ran.
- Trace was used offline for evaluation after initial alignment only, not as a backend input or tuning source.
- LSE methods remain complementary to LegSA-GINS and do not replace short lateral dual-antenna GNSS yaw.

Still forbidden after PAPER10G_R2:

- claiming LSE methods provide absolute yaw or global position without a global reference;
- claiming LegSA-GINS universally outperforms LSE methods;
- claiming author-official exact reproduction, raw joint FK, full contact-aided exact reproduction, or tracking-camera branch execution from PAPER10G_R2;
- claiming Go2 yaw/position truth, BY3 ordinary yaw generalization, trace online use, final_v23/LegSA output as solver input, output substitution, bad-epoch deletion, per-case tuning, complete nine-factor FGO, DA, LC, GINav, MATLAB, RTKLIB, LegSA final matrix, or degradation matrix execution;
- committing raw PDF, by2/by3 text, receiver raw files, NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, archives, core dumps, runtime-heavy outputs, or files over 50 MB.

## PAPER10G_R2A LSE Method Distinctness Audit Boundary

Allowed after PAPER10G_R2A:

- PAPER10G_R2A may state that the user suspicion was partially confirmed: PAPER10G_R2 used one `run_backend(provider, method)` dispatch path and provider-substituted roll/pitch metrics.
- PAPER10G_R2A may state that R2 method-distinctness evidence and R2 method-specific roll/pitch metrics are superseded by R2A.
- PAPER10G_R2A may state that LSE01-LSE05 were repaired and recomputed on BY2/BY3 with separate backend functions, backend hashes, output hashes, update-count summaries, perturbation tests, and short-segment validation.
- PAPER10G_R2A may report repaired/recomputed aligned relative trajectory, relative yaw drift after initial alignment, roll/pitch diagnostics, velocity diagnostics, update counts, and output-provenance evidence.
- PAPER10G_R2A may state that perturbation tests passed: contact/foot-position perturbations changed expected contact/FK methods and LSE05 velocity-disable changed the velocity-update backend.
- PAPER10G_R2A may state final status `PASS_LSE_METHOD_DISTINCTNESS_REPAIRED_AND_RECOMPUTED`.

Boundary after PAPER10G_R2A:

- Repaired LSE methods remain formula-level/proxy/subset implementations, not author-official exact reproductions.
- `foot_position_body` remains a Go2 high-level FK-like proxy, not raw joint encoder FK.
- LSE04 remains a fixed-window contact-factor smoothing proxy, not a full GTSAM/iSAM2 factor graph reproduction.
- LSE05 remains a camera-off velocity-update subset; the tracking-camera branch is blocked.
- Trace is offline evaluation-only and does not enter backend execution, segmentation, thresholds, covariance, or tuning.
- LSE methods remain local proprioceptive odometry/attitude/velocity support and cannot replace short lateral dual-antenna GNSS absolute yaw.

Still forbidden after PAPER10G_R2A:

- claiming R2 pre-repair metrics as method-distinct evidence;
- claiming author-official exact reproduction, raw joint FK, full contact-aided exact reproduction, full GTSAM/iSAM2 graph, or Teng tracking-camera branch execution;
- claiming LSE absolute yaw/global position, LegSA-GINS universal superiority, final_v23 outperformance, BY3 ordinary yaw generalization, Go2 yaw/position truth, GNSS dual-yaw input to LSE, trace online use, final_v23/LegSA output as solver input, output substitution, bad-epoch deletion, per-case tuning, DA, LC, GINav, MATLAB, RTKLIB, LegSA final matrix, degradation matrix, or complete nine-factor FGO;
- committing raw PDF, by2/by3 text, receiver raw files, NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, archives, core dumps, runtime-heavy outputs, or files over 50 MB.

## PAPER10G_R3 LSE Fidelity Upgrade Boundary

Allowed after PAPER10G_R3:

- PAPER10G_R3 may state that the Go2 URDF zip was hash-locked, extracted in runtime-only storage, parsed, and used to lock the four Go2 base-to-foot FK chains.
- PAPER10G_R3 may state that FL/FR/RL/RR each have hip, thigh, calf, and foot fixed-link chain evidence in the parsed URDF.
- PAPER10G_R3 may state that the raw-FK upgrade was attempted but blocked because timestamped BY2/BY3 raw lowstate `motor_state.q/dq` was not found.
- PAPER10G_R3 may state that `sportmodestate.foot_position_body` remains a high-level kinematic proxy and is not raw joint FK.
- PAPER10G_R3 may state that C1-C9 claim repair was generated and that C6-C9 remain forbidden by physics/data contract.

Boundary after PAPER10G_R3:

- URDF/FK-chain identity is upgraded; BY2/BY3 raw FK execution is not upgraded.
- Hartley official code availability does not close author-official exact reproduction because no compatible Go2 official adapter/sample run was executed.
- LSE04 remains below full GTSAM/iSAM2 contact factor graph reproduction because local GTSAM was not available and raw FK is blocked.
- LSE05 tracking-camera branch remains blocked because no synchronized tracking-camera/VIO velocity source was proven.
- R2A repaired proxy metrics remain the numeric LSE comparison source unless a later raw joint data source closes the raw-FK provider.

Still forbidden after PAPER10G_R3:

- claiming author-official exact reproduction, raw joint FK, full Hartley official adapter, full GTSAM/iSAM2 factor graph, or Teng tracking-camera branch execution;
- relabeling high-level `foot_position_body` / `foot_speed_body` as raw joint encoder FK;
- claiming LSE absolute yaw/global position, LegSA-GINS universal superiority over LSE, BY3 ordinary yaw generalization, Go2 yaw/position truth, GNSS dual-yaw input to LSE, trace online use, final_v23/LegSA output as solver input, output substitution, bad-epoch deletion, per-case tuning, DA, LC, GINav, MATLAB, RTKLIB, LegSA final matrix, degradation matrix, or complete nine-factor FGO;
- committing raw PDF, raw lowstate/rosbag, by2/by3 text, Go2 URDF zip, extracted URDF trees, generated images/PDFs, archives, core dumps, runtime-heavy outputs, or files over 50 MB.

## PAPER10X_R2 Git Freeze Boundary

Allowed after PAPER10X_R2:

- PAPER10X_R2 may state that a full local/remote branch, ref, worktree, tag, PR, unpushed-commit, no-upstream, and merge-decision audit was completed.
- PAPER10X_R2 may state that no PR/branch merge was executed because all merge candidates require explicit human approval and safety scans.
- PAPER10X_R2 may state that annotated stage tags were created locally only if they were missing and never overwritten.
- PAPER10X_R2 may state that a post-commit `git bundle --all` was created and verified as the pre-migration Git safety artifact.
- PAPER10X_R2 may state that new-drive Git policy keeps the active repository root as the authority for `AGENTS.md`, `PLANS.md`, `CLAIM_BOUNDARY.md`, and `PHASE_LOG.md`.

Boundary after PAPER10X_R2:

- Bundle path, SHA256, and verify logs are runtime/C-export/archive artifacts, not tracked Git content.
- PR and merge recommendations are decision support only; they do not authorize main push, PR merge, PR closure, branch deletion, tag deletion, or force-push.
- `stage/PAPER10X_R2` marks the local Git-freeze commit and bundle baseline; it is not a paper-performance or experiment tag.

Still forbidden after PAPER10X_R2:

- running solver/evaluator, DA, LC, GINav, MATLAB, RTKLIB, contact-aided reproduction, complete FGO, random/degraded-input generation, or any experiment;
- deleting branches/tags/worktrees/old directories or modifying raw receiver/by2/by3/trace data;
- merging unsafe branches, pushing main, force-pushing, rebasing, resetting, cleaning, stashing, or closing PRs without human approval;
- committing raw/RINEX/UBX/RTCM/bag/NAV/STD/EVAL_NAV/RUN_MANIFEST, generated images/PDFs, archives, bundles, files over 50 MB, local absolute paths, or forbidden claims.

## PAPER10E0 Basic Dual-Yaw EKF Baseline Boundary

Allowed after PAPER10E0:

- PAPER10E0 may state that Basic Dual-Yaw EKF is implemented as a minimal KF-GINS extension: original propagation, original 3D GNSS position update, and one optional 1D dual-antenna body-yaw update.
- PAPER10E0 may state that the dual-yaw update enters the existing `EKFUpdate` path and uses `dz = wrap(yaw_INS - yaw_dual)`, `H(0, PHI_ID + 2) = -1`, and fixed `R_yaw = (1.5 deg)^2` in radians squared.
- PAPER10E0 may state that state dimension, INS mechanization, covariance propagation, and `stateFeedback` were not changed.
- PAPER10E0 may state that source-aware, Go2, QM, Raw Doppler, FGO feedback, QA fallback, and final_v23 robust yaw logic were disabled under the Basic baseline.
- PAPER10E0 may state that BY2 normal smoke completed and that BY3 normal smoke completed as diagnostic-only.

Boundary after PAPER10E0:

- Smoke evidence is runtime closure and update activation, not final performance evidence.
- Official trace RMSE was not run in this stage.
- BY3 yaw remains poor-heading diagnostic-only and cannot support ordinary yaw generalization.
- final_v23 remains a strong external baseline with different robust logic; it is not Basic Dual-Yaw and was not used as solver input.

Still forbidden after PAPER10E0:

- claiming Basic Dual-Yaw is the final proposed method or outperforms final_v23;
- claiming Basic Dual-Yaw uses source-aware, Go2, QM, Raw Doppler, FGO, QA fallback, or final_v23 robust gate/downweight/reject/hold/fallback;
- claiming BY3 ordinary yaw generalization, full degradation matrix completion, paper performance readiness, trace online use, final_v23/LegSA output solver input, output substitution, bad-epoch deletion, or per-case tuning;
- committing raw/by2/by3/trace data, NAV/STD/EVAL_NAV/RUN_MANIFEST, generated images/PDFs/SVGs, archives, runtime-heavy outputs, files over 50 MB, or local absolute paths.
## PAPER10Z3 Migration Claim Boundary

Allowed after PAPER10Z3:

- State that the project uses a dual-root layout: active code under `<LEGSA_CODE_ROOT>` and project assets under `<LEGSA_PROJECT_ROOT>`.
- State that `<LEGSA_OBSIDIAN_ROOT>` is the active Obsidian vault after safe merge/quarantine.
- State that raw-data copies under `<LEGSA_PROJECT_ROOT>/data/raw` are governed as immutable-by-policy copies when the final report records matching file counts, byte counts, and SHA256 manifests.
- State that remote/local code capability status is documented by the PAPER10Z3 capability matrix under `<PAPER10Z3_STAGE_REPORT_ROOT>`.
- State that Git restore is backed by verified bundle artifacts only when `bundle verify` and SHA256 are recorded in the final report.

Boundary after PAPER10Z3:

- Migration/archive evidence is operational provenance, not algorithm performance evidence.
- Obsidian conflicts, dirty worktrees, compression-level fallbacks, full-test failures, or retained legacy paths must remain explicitly reported and cannot be converted into a clean pass.
- New project-root registries and aliases explain historical paths; they do not authorize rewriting immutable historical reports.

Still forbidden after PAPER10Z3:

- claiming any new BY2/BY3/XB/PG algorithm result, degradation-matrix completion, performance improvement, final_v23 outperformance, or paper-ready metric from migration evidence;
- treating raw source observations, Go2 state, trace, final_v23 output, or archived runtime as solver input authorization;
- committing raw data, archives, bundles, generated figures, runtime payloads, local absolute paths, NAV/STD/EVAL_NAV/RUN_MANIFEST, or large artifacts;
- pushing, merging, closing protected PRs, deleting branches, force-pushing, resetting, cleaning, stashing, or deleting legacy directories before the final gate report and human approval.

## PAPER10M1R2A V2 BY2 Degradation Matrix Spec Lock Boundary

Allowed after PAPER10M1R2A V2:

- State that the BY2 controlled-degradation matrix V2 specification is locked as 60 fixed degradation types, 9 seeds per type, 540 degraded cases, 1 clean case, and 541 total cases.
- State that each degradation case is defined by fixed `degradation_type_id`, seed, anchor policy, parameters, affected sources, and effect-validation rule.
- State that module-disable is not a degradation case axis and that internal ablations are separate downstream method queues.
- State that mixed cases D57-D60 have explicit component lists instead of placeholders.
- State that M1R2B/M1R2C/M1R2D queue drafts were generated with `run_allowed_now=false`.

Boundary after PAPER10M1R2A V2:

- BY2 controlled degradation is not independent real-world severe-environment generalization by itself.
- This stage has no provider generation, solver execution, evaluator execution, degraded-provider payloads, runtime metrics, figures, or algorithm performance experiment.
- Trace is evaluation-only and is forbidden for degradation parameter choice, anchor choice, provider generation, solver input, tuning, or feedback.
- Go2 remains a weak-prior/metadata/diagnostic source and is not position, yaw, velocity, or contact truth.
- Raw Doppler and receiver velocity are separate source channels.

Still forbidden after PAPER10M1R2A V2:

- claiming algorithm superiority, universal superiority, final paper readiness, final_v23 comprehensive superiority, BY3 yaw generalization, XB/PG high-precision severe-GNSS proof, exact external reproduction, or complete nine-factor FGO validation;
- treating trace, final_v23 output, LegSA output, benchmark output, or Go2 source fields as solver truth/input authorization;
- modifying or copying raw data, overwriting raw data with degraded providers, running solver/evaluator/full matrix/internal ablation/horizontal benchmark, deleting epochs, tuning per case, or performing output-only correction;
- committing raw data, by2/by3 source files, degraded provider payloads, NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, archives, local absolute paths, or secrets.

## PAPER10M1R2B V2 Provider Generation Claim Boundary

Allowed after PAPER10M1R2B V2, only if the final report records a pass:

- State that degraded provider packages were generated from the M1R2A locked BY2 541-case manifest.
- State that every provider-ready case has seed replay, input SHA256, generated provider SHA256, case spec dump, and effect-validation summary.
- State that effect validation passed for provider-ready cases.
- State that M1R2C and M1R2D queue drafts were refreshed from provider-ready cases with `run_allowed_now=false`.

Boundary after PAPER10M1R2B V2:

- M1R2B has no algorithm performance result, no solver result, no evaluator result, no full algorithm matrix result, and no internal ablation result.
- BY2 controlled degradation is still a controlled provider stress protocol, not independent real-world severe-environment generalization.
- Provider generation/effect validation can support reproducibility and execution readiness only; it cannot support algorithm superiority by itself.
- Algorithm conclusions must wait for M1R2C/M1R2D execution and human review.

Still forbidden after PAPER10M1R2B V2:

- claiming paper performance, universal superiority, final_v23 comprehensive superiority, final paper readiness, BY3 yaw generalization, XB/PG high-precision severe-GNSS proof, exact external reproduction, or complete nine-factor FGO validation;
- treating trace, final_v23 output, LegSA output, benchmark output, or Go2 source fields as provider-generation truth or solver input authorization;
- modifying/copying raw data, overwriting raw data with degraded providers, running solver/evaluator/full algorithm matrix/internal ablation/PAPER10H without a later approved stage, deleting epochs, tuning per case, or performing output-only correction;
- committing raw data, by2/by3 source files, degraded provider payloads, NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, export-clean zips, local absolute paths, or secrets.

## PAPER10M1R2C V2 BY2 Full Algorithm Matrix Claim Boundary

Allowed after PAPER10M1R2C V2, only if the final report records pass or conditional pass:

- State that the BY2 canonical controlled-degradation full-algorithm matrix was executed for the four frozen PAPER10L method modes.
- State that the same 541 M1R2B provider-ready cases were used for all four method modes.
- State that Basic Dual is a baseline comparator, Strong Dual-Yaw is a strong baseline comparator, LegSA without QM is an ablation candidate, and LegSA full candidate with QM is a bounded full candidate.
- State that trace was not used online and remained outside solver input.
- State row/method/family summaries as bounded engineering comparisons under the frozen BY2 controlled-degradation protocol.
- Use QM/source-aware traces as interpretability evidence only if the row-level trace contracts are complete.

Boundary after PAPER10M1R2C V2:

- BY2 controlled degradation is not independent real-world severe-environment generalization by itself.
- M1R2C is not internal ablation completion; M1R2D remains a separate human-authorized stage.
- M1R2C is not horizontal literature algorithm comparison and does not prove exact external reproduction.
- M1R2C results are not final paper claims until human review and downstream claim-boundary checks.
- Go2 high-level/body-state providers remain weak-prior or metadata sources, not truth.

Still forbidden after PAPER10M1R2C V2:

- claiming universal superiority, final paper readiness, final_v23 comprehensive superiority, BY3 yaw generalization, XB/PG high-precision severe-GNSS proof, exact external reproduction, or complete nine-factor FGO validation;
- treating trace, final_v23 output, LegSA output, benchmark output, Go2 source fields, or receiver IMU data as solver truth/input authorization;
- claiming M1R2D internal ablation, horizontal comparison, PAPER10H, BY3/XB/PG, provider regeneration, or severe-GNSS proof was completed;
- modifying/copying raw data, overwriting raw/provider packages, deleting epochs, tuning per case, or performing output-only correction;
- committing raw data, by2/by3 source files, degraded provider payloads, NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, export-clean zips, local absolute paths, or secrets.

## PAPER10M1R2C1 Clean Yaw And QM Semantic Audit Boundary

Allowed after PAPER10M1R2C1:

- State that M1R2C completed 2164 BY2 full-algorithm rows, but that completion is only execution coverage and not a yaw-performance or ablation-readiness claim.
- State that the BY2 clean yaw semantic mismatch was audited against method outputs, provider yaw, trace evaluation reference semantics, transform candidates, and historical clean-yaw context.
- State that no corrected evaluator-only metric tables were generated because the clean yaw issue did not pass the evaluator-only repair gate.
- State that QM trace and `bad_a1_consumed_count` field semantics were audited and require split/renamed summary fields before claim use.
- State that M1R2D is blocked by `BLOCKED_SOLVER_PROVIDER_YAW_SEMANTIC_FAILURE` until a later human-approved repair resolves clean yaw semantics and summary-field contracts.

Boundary after PAPER10M1R2C1:

- M1R2C row completion is not enough for yaw performance claims.
- Clean yaw semantic mismatch blocks paper-level interpretation and M1R2D internal ablation authorization.
- Corrected evaluator-only metrics, if a later stage generates them, must remain labeled as corrected evaluator products and must not replace original solver outputs.
- QM trace/counter fields require semantic audit before use in paper claims, method claims, or source-aware/QM mechanism claims.
- `bad_a1_consumed_count` must not be interpreted as accepted bad A1 consumption unless accepted, rejected, downweighted, and diagnostic counts are explicitly separated.

Still forbidden after PAPER10M1R2C1:

- claiming universal superiority, final paper readiness, final_v23 comprehensive superiority, BY3 yaw generalization, XB/PG high-precision severe-GNSS proof, exact external reproduction, complete nine-factor FGO validation, or a final QM performance claim;
- treating trace, final_v23 output, LegSA output, benchmark output, Go2 source fields, receiver IMU data, corrected evaluator products, or QM diagnostics as solver truth/input authorization;
- starting M1R2D internal ablation, horizontal comparison, PAPER10H, BY3/XB/PG execution, provider regeneration, or degraded-input regeneration without a later explicit human-approved stage;
- modifying raw data, overwriting providers, rerunning solvers to hide the anomaly, deleting epochs, tuning per case, performing output-only correction, or silently replacing original M1R2C metrics;
- committing raw data, by2/by3 source files, degraded provider payloads, NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, export-clean zips, local absolute paths, or secrets.

## PAPER10M1R2C2 Yaw Provider Repair Boundary

Allowed after PAPER10M1R2C2:

- State that M1R2C2 identified deterministic yaw provider lineage bugs and repaired the clean sentinel provider through BY2 source-backed A1 yaw generation.
- State that clean sentinel 4/4 rows passed after repair.
- State that trace was used only as evaluation reference and not as solver input or production yaw-sign selector.
- State that legacy `bad_a1_consumed_count` is deprecated and blocked from claims unless split into explicit accepted/downweighted/rejected fields.

Boundary after PAPER10M1R2C2:

- M1R2C row completion is execution proof, not yaw-valid result proof.
- Original M1R2C yaw tables are not paper-ready and must not be used as final evidence.
- No paper-level yaw claim is allowed until M1R2B2 provider regeneration and M1R2C repaired-provider rerun pass review.
- No QM claim may use legacy `bad_a1_consumed_count`.
- Trace remains evaluation-only; final_v23 and LegSA outputs remain forbidden as solver input.

Still forbidden after PAPER10M1R2C2:

- claiming M1R2C yaw results are paper-ready, M1R2D can start before repaired rerun review, universal superiority, final paper readiness, BY3 yaw generalization, or XB high-precision severe-GNSS proof;
- using trace-tuned yaw signs, final_v23 output as solver input, LegSA output as solver input, output-only correction, or epoch deletion;
- treating the clean sentinel as a replacement for the full 541-case provider regeneration and 2164-row full matrix rerun;
- committing raw data, degraded providers, NAV/STD/EVAL_NAV/RUN_MANIFEST runtime, generated figures, export-clean zips, local absolute paths, or secrets.

## PAPER10M1R2B2 Provider Regeneration Claim Boundary

Allowed after PAPER10M1R2B2:

- State that the old M1R2B provider packages are superseded by M1R2B2 yaw-corrected provider packages.
- State that M1R2B2 regenerated BY2 providers from the M1R2A 541-case manifest and validated provider-generation/effect semantics.
- State that BY2 yaw providers use source-lineage A1 dual-diff GNSS2-GNSS1 with lateral conversion and wrap-safe validation.
- State that M1R2C_R1 and M1R2D_R1 queue drafts exist with `run_allowed_now=false`.
- State that trace remains evaluation-only and was not used to generate providers or select yaw sign.

Boundary after PAPER10M1R2B2:

- M1R2B2 is provider regeneration and effect validation only; it is not solver/evaluator performance evidence.
- Original M1R2C yaw metrics cannot be used for performance claims.
- No paper-level yaw claim is allowed until M1R2C_R1 and M1R2D_R1 pass their own review gates.
- BY3/XB/PG remain out of scope.

Still forbidden after PAPER10M1R2B2:

- claiming M1R2C_R1 performance, M1R2D_R1 ablation conclusions, universal superiority, final paper readiness, BY3 yaw generalization, or XB/PG high-precision severe-GNSS proof;
- treating providers, trace, final_v23 output, LegSA output, Go2 source fields, or receiver IMU data as truth;
- running solvers/evaluators/full matrix/internal ablation/PAPER10H from M1R2B2 without a later approved stage;
- committing raw data, degraded provider payloads, provider runtime, NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, export-clean zips, local absolute paths, or secrets.

## PAPER10M1R2C_R1 Yaw-Corrected Full Matrix Claim Boundary

Allowed after PAPER10M1R2C_R1, only if the final report records pass or conditional pass:

- State that the BY2 canonical controlled-degradation full-algorithm matrix was rerun using yaw-corrected M1R2B2 providers.
- State that four frozen PAPER10L method modes were evaluated on the same 541 provider-ready cases.
- State that Basic Dual is a baseline comparator, Strong Dual-Yaw is a strong baseline comparator, LegSA without QM is an ablation candidate, and LegSA full candidate with QM is a bounded full candidate.
- State that trace was used only as evaluation reference and never as solver input.
- State row/method/family summaries as bounded engineering comparisons under the frozen BY2 controlled-degradation protocol.

Boundary after PAPER10M1R2C_R1:

- M1R2C_R1 is a BY2 controlled degradation full-algorithm rerun with yaw-corrected providers, not an independent severe-GNSS generalization proof.
- M1R2C_R1 is not internal ablation completion; M1R2D_R1 remains a separate human-authorized stage.
- M1R2C_R1 is not a horizontal literature algorithm comparison.
- Old M1R2C yaw metrics remain invalidated and must not be used as paper evidence.
- Later paper-level claims must wait for M1R2D_R1 and result review.

Still forbidden after PAPER10M1R2C_R1:

- claiming universal superiority, comprehensive final_v23 superiority, final paper readiness, BY3 yaw generalization, XB/PG high-precision severe-GNSS proof, exact external reproduction, or complete nine-factor FGO validation;
- treating trace, final_v23 output, LegSA output, benchmark output, Go2 source fields, receiver IMU data, old M1R2B providers, or old M1R2C results as solver input or truth;
- claiming M1R2D_R1 internal ablation, horizontal comparison, PAPER10H, BY3/XB/PG, provider regeneration, or severe-GNSS proof was completed;
- modifying/copying raw data, overwriting raw/provider packages, deleting epochs, tuning per case, or performing output-only correction;
- committing raw data, by2/by3 source files, degraded provider payloads, NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, export-clean zips, local absolute paths, or secrets.

## PAPER10M1R2D_R1 BY2 Internal Ablation Claim Boundary

Allowed after PAPER10M1R2D_R1, only if the final report records pass or conditional pass:

- State that the BY2 canonical controlled degradation internal ablation matrix was executed using yaw-corrected M1R2B2 providers.
- State that nine internal ablation methods were evaluated on the same 541 provider-ready BY2 cases.
- State that the full candidate is compared with module-disabled variants under a frozen protocol.
- State that trace was used only as evaluation reference and never as solver input.
- Interpret module contribution by metric and degradation family, not as universal causality.

Boundary after PAPER10M1R2D_R1:

- M1R2D_R1 is a BY2 controlled-degradation internal ablation matrix, not independent real-world generalization.
- M1R2D_R1 is not an external literature comparison and does not execute PAPER10H.
- M1R2D_R1 does not make paper-ready module-causality claims before M1R2E review.
- M1R2C_R1 is the full-algorithm reference and not a substitute for D_R1 rows.
- Old M1R2B providers and old M1R2C yaw metrics remain forbidden.

Still forbidden after PAPER10M1R2D_R1:

- claiming universal superiority, comprehensive final_v23 superiority, final paper readiness, BY3 yaw generalization, XB/PG high-precision severe-GNSS proof, exact external reproduction, complete nine-factor FGO validation, or paper-ready module causality before M1R2E review;
- treating trace, final_v23 output, LegSA output, benchmark output, Go2 source fields, receiver IMU data, old M1R2B providers, old M1R2C results, or M1R2C_R1 rows as solver input or D_R1 row substitutes;
- claiming horizontal comparison, PAPER10H, BY3, XB, PG, provider regeneration, severe-GNSS proof, or final paper readiness was completed;
- modifying/copying raw data, overwriting raw/provider packages, deleting epochs, tuning per case, performing output-only correction, or committing runtime payloads, generated figures, export-clean zips, local absolute paths, or secrets.

## PAPER10M1R2E BY2 Result Review And Claim Boundary Freeze

Allowed after PAPER10M1R2E, only with the generated M1R2E classification tables and caveats:

- State that the BY2 controlled degradation matrix was reviewed using yaw-corrected M1R2B2 providers.
- State that M1R2C_R1 completed four frozen full-algorithm modes over 541 BY2 cases, for 2164/2164 completed-evaluable rows.
- State that M1R2D_R1 completed nine internal ablation methods over 541 BY2 cases, for 4869/4869 completed-evaluable rows.
- State that trace was evaluation-only and not solver input.
- State that Raw Doppler shows a small bounded auxiliary contribution under the frozen BY2 protocol.
- State that source-aware weighting shows stable bounded contribution in many cases, with small deltas and metric tradeoffs.
- State that multi-state QM provides interpretable state/action traces but has metric tradeoffs and is not a universal performance improvement.
- State that Go2 horizontal velocity is a weak auxiliary prior with limited measured contribution.
- State that the dual-antenna yaw provider lineage is a BY2 source-backed backbone and system foundation.

Conditional or diagnostic-only after PAPER10M1R2E:

- Go2 roll/pitch may be discussed only as weak or not-claimable-as-improvement evidence under current metrics.
- Go2 joint/proprioceptive factor must be diagnostic/no-effect if its delta is zero.
- FGO feedback / EKF-only relation must be diagnostic/alias/no-effect if its delta is zero.
- `legsa_without_qm` and `legsa_no_qm` must not be double-counted as two independent module contributions if their metrics are equivalent.
- Existing review figures may be candidates for main text or appendix, but final manuscript figures require a separate M1R2F formatting/replot gate.

Still forbidden after PAPER10M1R2E:

- universal superiority;
- final paper claim ready;
- BY3 yaw generalization;
- XB/PG high-precision severe-GNSS proof;
- exact external reproduction;
- complete nine-factor FGO validation;
- treating Go2 position, velocity, contact, or yaw as truth;
- using old M1R2C yaw-invalid results as active evidence;
- using legacy bad-A1 consumed counters as claim fields;
- claiming final_v23 comprehensive superiority;
- claiming all modules significantly improve performance;
- claiming Go2 joint or FGO feedback effectiveness when measured delta is zero;
- running or implying PAPER10H, BY3, XB/PG, horizontal comparison, new provider generation, new degraded inputs, solver/evaluator runs, output-only correction, per-case tuning, or deletion of bad epochs from M1R2E.

## PAPER10Q1 QM Evidence And Claim Boundary

Allowed after PAPER10Q1, only with Q1 caveats:

- State that QM/source-aware provides bounded protection under degraded measurement conditions in BY2.
- State that QM provides interpretable state/action/recovery traces from frozen M1R2C_R1/M1R2D_R1 evidence.
- State that source-aware weighting has stable bounded contribution in many cases, with small deltas and metric tradeoffs.
- State that normal-condition QM transparency must be reported with caveats.
- State that Q1 generated review PNG/PDF figures and figure QA outside Git, not new solver/evaluator evidence.

Conditional after PAPER10Q1:

- Multi-state QM may be positioned as a protective and interpretable mechanism only if the manuscript also reports full-QM versus no-QM tradeoffs.
- Full-QM versus no-QM results must include no-QM-better cases and diagnostic caveat figures where relevant.
- Source-aware and QM wording must be degradation-family-specific; do not generalize from BY2 to BY3/XB/PG.

Still forbidden after PAPER10Q1:

- claiming QM universally improves all metrics;
- claiming QM significantly improves normal-condition accuracy;
- claiming full-QM dominates no-QM in all cases;
- using legacy `bad_a1_consumed_count` as a claim field;
- claiming BY3 yaw generalization, XB/PG high-precision severe-GNSS proof, horizontal comparison completion, PAPER10H completion, final paper readiness, universal superiority, or complete 9F FGO validation;
- treating Go2 position, velocity, contact, or yaw as truth;
- running or implying solver/evaluator/provider/degradation/random-generation work from Q1;
- committing generated figure binaries, raw data, providers, NAV/STD/EVAL_NAV/RUN_MANIFEST, export-clean zips, local absolute paths, or secrets.
