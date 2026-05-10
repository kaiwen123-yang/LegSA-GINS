# N5D1 Plot Semantics Fix

The original N5D `velocity_error_vs_raw_doppler_3sigma.png` name was too strong
when the plotted quantity was raw Doppler velocity minus receiver-native
velocity. Receiver-native velocity is not truth, so N5D1 replaces this with:

`raw_minus_receiver_velocity_consistency_vs_raw_doppler_3sigma.png`

The corrected y-axis is:

`raw Doppler minus receiver velocity norm (m/s)`

The 3-sigma label is:

`raw Doppler velocity 3sigma norm (m/s)`

N5D1 also de-duplicates stress evidence pairs so an isolation pair and an
equivalent disabled receiver-velocity pair are not counted twice. Stress plot
labels are shortened to `isolation`, `disabled`, `stdx5`, `outage30`, and
`noise0.5` for readability. These plots remain diagnostic-only and are not
tuning claims.
