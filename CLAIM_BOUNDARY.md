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
- reference-limited yaw boundary.

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
