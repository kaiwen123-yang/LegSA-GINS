# KF-GINS Output Mapping

Stage N3C standardizes observed final_v23/KF-GINS baseline outputs without
changing numeric values.

## `KF_GINS_Navresult.nav`

Observed contract: 11 columns without a header.

1. `gps_week`
2. `tow`
3. `lat_deg`
4. `lon_deg`
5. `height_m`
6. `vn_mps`
7. `ve_mps`
8. `vd_mps`
9. `roll_deg`
10. `pitch_deg`
11. `yaw_deg`

The standardized output is `FINAL_V23_NAV.csv`. `FINAL_V23_EVAL_NAV.csv` uses
`tow` as `timestamp` and keeps the same navigation values.

## `KF_GINS_STD.txt`

Observed contract: 22 columns without a header.

1. `tow`
2. `std_pos_n_m`
3. `std_pos_e_m`
4. `std_pos_d_m`
5. `std_vel_n_mps`
6. `std_vel_e_mps`
7. `std_vel_d_mps`
8. `std_roll_deg`
9. `std_pitch_deg`
10. `std_yaw_deg`
11. `std_gyrbias_x_dph`
12. `std_gyrbias_y_dph`
13. `std_gyrbias_z_dph`
14. `std_accbias_x_mgal`
15. `std_accbias_y_mgal`
16. `std_accbias_z_mgal`
17. `std_gyrscale_x_ppm`
18. `std_gyrscale_y_ppm`
19. `std_gyrscale_z_ppm`
20. `std_accscale_x_ppm`
21. `std_accscale_y_ppm`
22. `std_accscale_z_ppm`

The standardized output is `FINAL_V23_STD.csv`.

## `KF_GINS_IMU_ERR.txt`

Observed contract: 13 columns without a header.

1. `tow`
2. `gyrbias_x_dph`
3. `gyrbias_y_dph`
4. `gyrbias_z_dph`
5. `accbias_x_mgal`
6. `accbias_y_mgal`
7. `accbias_z_mgal`
8. `gyrscale_x_ppm`
9. `gyrscale_y_ppm`
10. `gyrscale_z_ppm`
11. `accscale_x_ppm`
12. `accscale_y_ppm`
13. `accscale_z_ppm`

The standardized output is `FINAL_V23_IMU_ERR.csv` when the source file is
available.

## Boundary

- baseline evaluation only;
- no numerical correction;
- no output-only correction;
- no bad-epoch deletion for metric passing;
- no trace tuning;
- no numerical claim before an oracle pass.
