# Clean/Noisy Input Provenance Policy

Historical dual_final_v23 artifact likely includes Gaussian yaw noise provenance.

Clean replay is reconstructed no-noise status-yaw variant.

Clean replay is independently rerun and validated.

Clean replay is not historical exact artifact.

Later experiments must label input provenance with one of:

- `clean_status_yaw_no_noise`
- `noisy_historical_final_v23_artifact`
- `degraded_stress_cases`

Clean replay preferred for N4H4 baseline parity.

The noisy artifact remains useful for stress/provenance evidence.

Noisy artifact not clean nominal.

No performance claim.

The noisy historical artifact must not be called clean nominal, and clean replay metrics remain baseline replay diagnostic evidence only.
