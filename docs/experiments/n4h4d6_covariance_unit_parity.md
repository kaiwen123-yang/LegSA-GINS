# N4H4D6 Covariance Unit Parity

This audit records IMU noise and covariance unit evidence against KF-GINS-style conventions:

- gyro bias: deg/h to rad/s
- accelerometer bias: mGal to m/s^2
- scale factor: ppm to unitless
- ARW: deg/sqrt(hr) to rad/sqrt(s)
- VRW: m/s/sqrt(hr) to m/s/sqrt(s)
- correlation time: hour to second
- Gauss-Markov bias process noise: `2 / corr_time * std^2`

Missing evidence remains `evidence_missing`; the audit does not invent source-backed units or tune covariance.

