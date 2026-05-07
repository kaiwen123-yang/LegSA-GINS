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

Frame/evaluator utilities must not be described as a solved navigation algorithm.

C++ runtime skeleton must not be described as a validated navigation solver.

Dry-run output must not be used as performance evidence.

External final_v23 / KF-GINS source audit must not be described as proposed algorithm implementation.

External source must not be vendored into LegSA-GINS without explicit decision.

Source audit must not be used as numerical performance evidence.

N3B must not claim final_v23 reproduction before N3C oracle pass.

N3B must not claim improved navigation performance.

## Evidence Rule

If evidence is missing, write:

evidence_missing

Do not invent evidence.
