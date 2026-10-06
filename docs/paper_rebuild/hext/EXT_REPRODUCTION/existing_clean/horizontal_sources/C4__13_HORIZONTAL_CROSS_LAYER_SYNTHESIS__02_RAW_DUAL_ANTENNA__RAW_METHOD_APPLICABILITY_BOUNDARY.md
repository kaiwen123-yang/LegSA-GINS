
# Raw dual-antenna applicability boundary

## The three primary methods

1. **RAW01 / EXT01 C-LAMBDA** is an exact strict constrained-integer mathematical core. It returned 1,077 integer solutions from 1,509 paired epochs and certified the search optimum, but the frozen method defines no ambiguity-acceptance test. Eight persistent fractional-DD offset groups were detected and no calibration was applied. Terminal applicability: `UNSUPPORTED_EXT01_ON_BY2_WITHOUT_PHASE_BIAS_CALIBRATION`.
2. **RAW02 / EXT02 C-WLS** is a faithful independent clean-room reproduction. It produced 1,057 accepted wrapped solutions from 1,509 epochs (70.046388%), with 452 invalid rows. “Accepted wrapped solution” does not establish correct ambiguity, and the physical heading applicability is poor.
3. **RAW03 / EXT03 Yang 2024** is a faithful recursive DD-KF reproduction with a declared unspecified stochastic instantiation and no official code. All ten frozen modes are retained. The preregistered primary applicability mode `GPS_BDS_DUAL_FREQUENCY/CONSTRAINED/sigma=0.01` has 609 valid rows, including 105 paper-ratio-fixed states, and 900 invalid rows; 101/105 ratio-fixed rows are proxy-inconsistent. The existing trace diagnostic reports 84.3438229670° RMSE on its ALL_VALID support and 40.6308462423° on its ratio-fixed support. These diagnostics were not used to select a mode.

## Non-unifiable state semantics

`integer solution returned`, `accepted wrapped solution`, `paper-ratio-fixed`, `ambiguity accepted`, and `correct ambiguity` are not synonyms. The CSV tables retain each method’s native vocabulary and explicitly mark ambiguity correctness as unknown where appropriate. No common “fix success rate” is produced.

## EXT04

EXT04 is not a fourth primary raw method. It is a `SUPPLEMENTARY_DIAGNOSTIC_MODULE` and `PAPER_DERIVED_POLICY_BASELINE`. The exact PAR policy is under-specified; all 27 frozen policy/mode rows have zero accepted epochs. Aggregate row states are FAR rejected=187, PAR exhausted=4368, invalid=36188. It supports only a failure-mechanism/applicability claim.

## Metric boundary

These methods produce raw-carrier baseline/heading backends, not full navigation trajectories. Native heading summaries are descriptive only and cannot be placed in a flat position/attitude RMSE ranking against solution-level or internal full-navigation methods.
