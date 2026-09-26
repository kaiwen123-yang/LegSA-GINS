# LC02 Final Candidate Admission Triage Protocol

This stage is a static formal-reproduction triage. It does not implement or run a filter, generate candidate code, open reference or trace data, or produce a performance comparison.

The twelve gates in `LC02_FINAL_CANDIDATE_ADMISSION_RUBRIC.yaml` were frozen before candidate-specific artifacts. Every gate is mandatory. A source-unavailable algorithm detail is recorded as `NOT_EVALUATED_SOURCE_UNAVAILABLE`; it is never reconstructed from a title, abstract, generic filter literature, historical output, or reported accuracy.

Candidate identity and non-duplication are structural. The audit compares sensors, receiver count, state and measurement structure, information source, and mechanism. Accuracy, prestige, novelty, and historical RMSE are prohibited selection factors.

The tie-break order is fixed: attributable official implementation, fewer adapters, clearer physical point and frame, lower source ambiguity, then lower runtime and dependency risk. The closed candidate set contains Jiang 2021, Taghizadeh 2023, and the official GINav 2021 SPP/INS loosely coupled route. No fourth candidate is authorized.

Online-input classification permits Go2 body gyroscope and accelerometer and, for paper-defined solution-level candidates, GNSS1 solution PVT and covariance. The GINav official-system route may instead consume RINEX observation/navigation data and a source-explicit Go2 body-IMU CSV adapter, because its official internal GNSS solver produces the SPP solution used by its official loosely coupled INS path. It must not be replaced with an invented external PVT interface.

Go2 quaternion/RPY/onboard PVT/yaw, GNSS2 or dual-antenna products, EXT carriers, LC01/Hartley/LegSA/final-v23 outputs, trace, reference, and error series are forbidden for online use or candidate selection. Any future threshold behavior remains a validation obligation, not a current performance gate.
