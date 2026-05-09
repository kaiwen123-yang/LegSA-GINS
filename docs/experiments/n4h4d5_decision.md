# N4H4D5 Decision

N4H4D5 combines one-step propagation, update block contribution, covariance/gain isolation, feedback variants, and external-state shadow update diagnostics.

Decision rules:

- one-step mechanization suspect leads to `N4H4D6_mechanization_step_fix`;
- attitude feedback isolation leads to `N4H4D6_feedback_attitude_covariance_fix`;
- gain/R scaling evidence leads to `N4H4D6_covariance_measurement_noise_fix`;
- block-specific evidence leads to the corresponding update fix;
- coupled state-divergence evidence leads to `N4H4D6_mechanization_feedback_coupled_fix`;
- insufficient evidence leads to extended diagnostics.

N4H4D5 is diagnostic only: no output-only correction, no tuning, no epoch deletion, and no performance claim.
