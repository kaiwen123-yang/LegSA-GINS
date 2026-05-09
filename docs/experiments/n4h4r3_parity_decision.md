# N4H4R3 Parity Decision

The R3 decision has three outcomes: `parity_passed`, `parity_near_gate`, and
`parity_failed`. A pass is only an engineering backbone parity candidate.

Pass requires horizontal RMSE <= 2.0 m, up RMSE <= 3.0 m, yaw RMSE <= 2.0 deg,
roll/pitch relaxed RMSE <= 1.6 deg, and close agreement with the external clean
replay. Roll/pitch relaxed pass is not strict pass. Yaw greater than 2.0 deg
cannot pass.

The decision is not paper performance and not factor evidence. It preserves the
same boundary as R0-R2: final_v23 is not proposed novelty, final_v23 output is
not solver input, and trace remains evaluation-only.
