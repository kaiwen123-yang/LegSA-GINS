# N4H4D4 Shadow Measurement Audit

The shadow measurement audit computes LegSA measurement residuals offline using external clean NAV state and clean GNSS observations.

This is not solver input. It is a diagnostic check for whether the measurement model itself is plausible when the state is close to the external clean reference.

If external-state residuals are small but internal residuals are large, the likely issue is state divergence from propagation, feedback, or covariance behavior. If external-state residuals are large, a measurement convention problem remains possible.
