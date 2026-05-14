# N8C2 RawDopplerVelocityFactor review

N8C2 reviews the RawDopplerVelocityFactor before any formal performance claim.

The report separates:

- raw Doppler source availability;
- epoch alignment evidence;
- direct solver residual evidence;
- proxy residual evidence;
- Jacobian/nonzero proxy evidence;
- raw_doppler_off toggle evidence;
- diagnostic weight-sensitivity reruns.

If RawDopplerVelocityFactor is registered but no direct solver residual evidence
is found, the decision must report activation missing or suspicious no-effect
instead of treating the factor as formally active.
