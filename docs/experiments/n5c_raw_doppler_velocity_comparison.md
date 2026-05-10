# N5C Raw Doppler Velocity Comparison

N5C compares the RTKLIB-derived raw Doppler velocity factor against receiver-native `.gnss` velocity only to inspect source integrity and observation relationship.

- NAV-PVT velocity is not raw Doppler.
- .gnss vn/ve/vd is not raw Doppler.
- `.gnss` velocity remains the baseline receiver-native velocity factor.
- A near-identical raw Doppler velocity and `.gnss` velocity sequence is flagged as `possible_pvt_velocity_copy_suspect`.
- The comparison is not an instruction to replace one observation source with the other.
- paper performance claim: false.
