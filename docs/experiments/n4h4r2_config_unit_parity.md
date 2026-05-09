# N4H4R2 Config Unit Parity

The R2 config loader supports a source-backed subset of the final_v23/KF-GINS
configuration contract. It is sufficient for R2 synthetic and real-input-capable
runtime plumbing; full YAML parity can be tightened in R3 if needed.

Unit conversions:

- `initpos` latitude/longitude: degrees to radians.
- `initpos` height: meters, unchanged.
- `initvel`: meters per second.
- `initatt`: degrees to radians.
- gyro bias: deg/hour to rad/second using `D2R / 3600`.
- accelerometer bias: mGal to m/s^2 using `1e-5`.
- scale factors: ppm to unitless using `1e-6`.
- attitude standard deviation: degrees to radians.
- ARW: deg/sqrt(hour) to rad/sqrt(second) using `D2R / 60`.
- VRW: m/s/sqrt(hour) to m/s/sqrt(second) using `/ 60`.
- bias process standard deviations follow the same bias conversions.
- correlation time (`corrtime`): hours to seconds using `* 3600`.
- bias process noise model: `2 / corr_time * std^2`.

The loader does not read trace files and does not read final_v23 outputs as solver input.
Clean/noisy input provenance remains mandatory for later replay stages.
