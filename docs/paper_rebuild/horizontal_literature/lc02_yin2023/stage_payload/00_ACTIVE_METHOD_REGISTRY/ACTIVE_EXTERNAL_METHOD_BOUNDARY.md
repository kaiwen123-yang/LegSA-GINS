# Active solution-level loosely coupled method boundary

Registry freeze time: 2026-08-24 Asia/Shanghai. This is an identity and evidence-role freeze, not an execution result.

The active solution-level literature set has exactly two intended paper identities:

- `LC01_PAVLASEK2021_TWO_RECEIVER_IEKF` (legacy `EXT05A_PAVLASEK_TWO_RECEIVER_IEKF`) is the completed Pavlasek–Walsh–Forbes ICRA 2021 two-position-receiver IEKF. Its method/C00 identity remains active. It is not rerun in LC02 Y0–Y3.
- `LC02_YIN2023_RAEKF` (compatibility alias `EXT06_YIN2023_RAEKF_LC`) is the selected Yin et al. Remote Sensing 2023 robust-adaptive LC-EKF family. `YIN2023_EKF`, `YIN2023_AKF`, `YIN2023_RKF`, and `YIN2023_RAEKF` are one paper family and one external method; RAEKF remains the intended formal primary, but is not formally admitted because its reproducible level is only `PAPER_DERIVED_POLICY_BASELINE`.

Y0–Y3 audit closure is `PASS_LC02_YIN2023_Y0_Y3_METHOD_NON_DUPLICATION_AND_BY2_CONTRACT_READY`. This PASS certifies paper/source/identity/input-contract completion only; it does not authorize implementation or admit RAEKF as a faithful comparator.

The abandoned `EXT06_HAO2018_TWO_ANTENNA_LC_EKF` identity is forbidden and obsolete.

`LSE01_HARTLEY_CONTACT_AIDED_INEKF` is a completed observability/state-estimation layer. It is not LC01, LC02, or a GNSS/INS solution-level comparator and is not reopened here.

`EXT01`–`EXT04` remain raw-carrier, ambiguity, or dual-antenna-attitude methods. They are not solution-level LC identities and are not rerun here.

The old `HORIZONTAL18_V2` internal-method ranking is inactive for final scientific comparison because a later review found an internal-provider/method-identity mismatch. This does not deactivate the LC01 paper/method/C00 identity.

No historical performance number, legacy provider, legacy runtime output, trace/reference, or current project-method output is admitted by this registry.
