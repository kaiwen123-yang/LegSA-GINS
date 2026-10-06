# Carrier phase and moving-baseline ambiguity development

Latest author instruction, 2026-10-06: work on carrier phase and ambiguity resolution directly; manuscript work is out of scope. Routine research and implementation choices are delegated. This stage supersedes earlier completed-trial stop wording for new carrier work, while preserving earlier observations and V3.

## Implementation sequence

1. Single satellite/signal: units, receiver sign, phase/Doppler continuity, tracking and half-cycle events, explicit arc identity. A single satellite is not a complete three-dimensional baseline solution.
2. Single-constellation multiple satellites: shared arc integers and independent length-constrained baseline at every epoch, with exact within-epoch DD covariance.
3. Multiple constellation/frequency groups: GPS L1/L2, Galileo E1/E5b and BeiDou B1I/B2I where source ephemeris and phase metadata qualify. Each exact signal group has its own pivot and integer basis. GLONASS FDMA is excluded without an inter-frequency bias model.
4. Separate integer candidate search from measurement admission. A global objective certificate is not true-integer knowledge or a calibrated false-fix probability.

All algorithm edits, numerical tests and real executions use the E-drive Ubuntu-22.04 WSL. Raw observations are immutable. Code-only SPP anchors and broadcast orbits are permitted; receiver solved baselines and fused references do not enter this stage. Original V3 and frozen prior-stage outputs remain unchanged.

## First real development trial

Use the previously metadata-inspected BY2 80–82 s window, all ten independently paired RAWX epochs; it is development data, not new held-out validation. Begin arcs inside the window and retain left-censoring. Start with all qualified observations, freeze each group pivot on first usable causal epoch, and never select pivots or epochs by solver performance. Arc labels contain both receiver identities and pivot arcs, so a reset creates a new integer.

Families: GPS L1; GPS L1/L2; GPS+Galileo+BeiDou supported L1/E1/B1 and L2/E5b/B2 signal groups. For each family solve prefixes 1, 5 and 10. Every included epoch has its own 3D baseline of nominal length 0.350 m. Initial code-only SPP is recomputed cold per epoch. Within-epoch covariance includes DD shared pivots; cross-frequency correlation can be supplied explicitly. Default cross-time independence is an engineering model, not measured calibration.

Metadata plus an explicit phase-minus-integrated-Doppler diagnostic defines candidate continuity. Its first fixed bound is 0.5 cycle per 0.2 s interval and maximum gap is 0.21 s. These are development screening choices, not tuned or calibrated integrity thresholds. Retain all reset and unavailable events. A diagnostic-only metadata continuation must not be labelled validated continuity.

Each search has 60 s and 100000 nodes initially; preserve timeout and unsupported geometry outcomes. Candidate count, residuals and causal endpoint times are reported. Multi-frequency gain and temporal gain are distinguished; no real integer truth or navigation improvement is inferred.

## Git and continuation

Commit and push completed source/test and real-execution milestones using feat(ar-research), fix(ar-research) and experiment(ar-validation). Continue implementation when a technical issue is found; do not turn an unpromising initial test into an automatic end to the authorized carrier direction. Keep draft PR 65 updated with the actual scope and evidence.
