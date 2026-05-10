# N5A Raw Doppler Measurement Model

N5A converts UBX-RXM-RAWX satellite-level Doppler `doMes` to observed range rate only when the wavelength is known. Wavelength-missing signals are reported explicitly and are not silently used.

The provider-backed LS model estimates receiver ECEF velocity and receiver clock drift:

`observed_range_rate_i = los_i dot (receiver_velocity - satellite_velocity_i) + receiver_clock_drift_mps + corrections`

The exported EKF auxiliary factor is `time, vn, ve, vd, std_vn, std_ve, std_vd, sat_count, gdop_like, provider_status`.

NAV-PVT velocity is not raw Doppler. `.gnss vn/ve/vd` remains baseline receiver-native velocity. Without satellite position and velocity from a mature provider, N5A cannot activate the solver factor.

No trace solver input. No final_v23 output solver input. No paper performance claim.
