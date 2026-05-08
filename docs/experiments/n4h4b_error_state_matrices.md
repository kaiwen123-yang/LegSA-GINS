# N4H4B Error-State Matrices

The N4H4B predictor uses a 21-state error vector:

- `P_ID`: position error
- `V_ID`: velocity error
- `PHI_ID`: attitude error
- `BG_ID`: gyro bias error
- `BA_ID`: accelerometer bias error
- `SG_ID`: gyro scale error
- `SA_ID`: accelerometer scale error

The noise vector has 18 components:

- `ARW_ID`
- `VRW_ID`
- `BGSTD_ID`
- `BASTD_ID`
- `SGSTD_ID`
- `SASTD_ID`

`buildErrorStateMatrices` constructs the required prediction blocks:

- `P/P`, `P/V`
- `V/P`, `V/V`, `V/Phi`, `V/BA`, `V/SA`
- `Phi/P`, `Phi/V`, `Phi/Phi`, `Phi/BG`, `Phi/SG`
- `BG/BG`, `BA/BA`, `SG/SG`, `SA/SA`
- `G` blocks for `V/VRW`, `Phi/ARW`, `BG/BGSTD`, `BA/BASTD`, `SG/SGSTD`,
  and `SA/SASTD`

The stage uses `Phi = I + F * dt` and `Qd = (Phi * (G * Qc * G^T * dt) *
Phi^T + G * Qc * G^T * dt) / 2`. This is a propagation foundation, not a
validated final_v23 parity claim.
