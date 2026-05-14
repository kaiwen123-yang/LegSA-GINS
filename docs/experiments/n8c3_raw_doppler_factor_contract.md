# N8C3 Raw Doppler factor contract

RawDopplerVelocityFactor uses:

- observation: `z = [vN_rawdoppler, vE_rawdoppler, vD_rawdoppler]`;
- prediction: `h(x) = [vN_state, vE_state, vD_state]`;
- residual: `r = h(x) - z`;
- Jacobian: identity with respect to velocity north/east/down only;
- no position, attitude, yaw, or bias block.

R comes from Raw Doppler std/covariance policy and must not be zero.  Weight
sensitivity scales this factor for diagnostics only and does not use
trace/final_v23 output.
