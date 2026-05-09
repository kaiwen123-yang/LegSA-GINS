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

Allowed N4H4D clean replay statement:

- N4H4D may run LegSA-owned v23-core on clean status-yaw runtime input and
  evaluate against the dual official reference.
- N4H4D may compare engineering metrics to external clean replay and produce a
  parity/gap-screen decision.
- N4H4D is engineering baseline parity, not paper performance.
- N4H4D makes no proposed factor claim.
- Trace remains evaluation-only and must not enter solver input.
- No output-only correction and no bad epoch deletion are allowed.
- If parity fails, the gap screen controls the next work.

Allowed N4H4D1 diagnostic statement:

- N4H4D1 may add first-epoch, config/init, residual, runtime trace, and
  update-isolation diagnostics for the failed N4H4D replay.
- N4H4D1 is diagnostic only.
- Isolation variants are not performance results.
- No tuning, no epoch deletion, and no output correction are allowed.
- Failed parity must not be hidden.

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
- N4H4C relaxing yaw evaluator gates or deleting epochs to pass metrics.
- N4H4D as paper performance evidence.
- N4H4D as proposed factor evidence.
- N4H4D using trace as solver input.
- N4H4D using final_v23 outputs as proposed solver input.
- N4H4D applying output-only correction or deleting epochs to pass metrics.
- N4H4D relaxing yaw above 2 deg or reporting relaxed roll/pitch as strict pass.
- N4H4D1 diagnostic isolation variants as performance results.
- N4H4D1 hiding failed parity, tuning parameters, deleting epochs, or applying
  output-only correction.
- N4H4B enabling raw Doppler, Go2 priors, LSIM/OIM, source-aware weighting,
  FGO, FGO feedback, output-only correction, bad-epoch deletion, or trace
  solver input.

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

## Evidence Rule

If evidence is missing, write:

evidence_missing

Do not invent evidence.

N4H4D2 diagnostic variants are not performance results.

N4H4D2 formula parity audit does not modify solver by default.

N4H4D2 must not use output-only correction, tuning, or epoch deletion.

Any future fix must be evidence-backed by N4H4D2.

N4H4D3 applies evidence-backed engineering fixes only.

N4H4D3 is not a factor contribution.

N4H4D3 guarded fix replay is not paper performance.

N4H4D3 must not use output-only correction, tuning, or epoch deletion.

N4H4D3 keeps yaw_H_mapping as a secondary issue unless a later source-backed
stage fixes it.

N4H4D4 external clean NAV is diagnostic/evaluation reference only.

N4H4D4 shadow measurement audit must not feed the solver.

N4H4D4 trace parity diagnostics are not performance results.

N4H4D4 must not use output correction, tuning, or epoch deletion.

N4H4D5 uses external clean state only as a diagnostic shadow reference.

N4H4D5 diagnostic feedback/covariance variants are not performance results.

N4H4D5 must not use output-only correction, tuning, or epoch deletion.

Any D6 fix must be evidence-backed by N4H4D5.

N4H4D6 diagnostic variants are not performance results.

N4H4D6 bias/scale feedback variants are diagnostic only.

N4H4D6 external clean reference must not enter the solver.

N4H4D6 must not use output-only correction, tuning, or epoch deletion.

Any D7 fix must be evidence-backed by N4H4D6.
