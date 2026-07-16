# Clean Paper Method Scope

## Proposed Method

The fixed clean-rebuild paper method is `LegSA_Paper_V1`:

- source-backed EKF propagation and measurement updates;
- lateral short-baseline dual-antenna body-yaw modeling with GNSS2-GNSS1, fixed physical `+90 deg` conversion, and wrap-safe residuals;
- Raw Doppler auxiliary velocity from a freshly generated, lineage-locked provider;
- source-aware measurement weighting;
- Go2 roll/pitch weak prior;
- Go2 horizontal-velocity weak prior.

Go2 inputs remain weak auxiliary observations. They are not truth. Source-aware weighting is a bounded protection and interpretability mechanism; it is not presumed to improve every metric or dataset.

## Comparison Methods

- `single_antenna_EKF`: source-backed EKF without dual-yaw, Raw Doppler, source-aware weighting, Go2 priors, QM, or FGO feedback.
- `basic_dual_yaw_EKF`: the same basic backbone plus the fixed source-backed dual-yaw update; proposed modules remain disabled.
- `strong_dual_yaw_EKF`: source-backed position/velocity/dual-yaw EKF reference without proposed source-aware, Raw Doppler, Go2, QM, or FGO features.
- `LegSA_Paper_V1`: the proposed bounded combination listed above.

The machine-readable mode contract is `configs/paper_rebuild/methods.yaml`.

## CLEAN2 ablation identity

The 16 `AB0000..AB1111` entries are
`role=ablation_configuration` on the frozen `strong_dual_yaw_EKF` / clean
final_v23 backbone. They are not additional paper methods. Their left-to-right
bit order is `RD,SA,RP,HV`; `AB0000` aliases canonical strong and `AB1111`
aliases canonical `LegSA_Paper_V1` without launching duplicate processes.

## Explicitly Out Of Scope

- selected FGO feedback;
- active or complete nine-factor FGO;
- multi-state QM as the paper's main innovation;
- QA fallback;
- complete contact or forward-kinematics factor;
- no-feedback FGO as a final method;
- Go2 position, velocity, yaw, contact, or pose as truth;
- final_v23 output, LegSA output, benchmark output, or trace as solver input;
- per-case tuning, output-only correction, or metric-driven epoch deletion.

The excluded components may appear in legacy history or future design notes. They are not part of `LegSA_Paper_V1` and cannot be enabled silently.
