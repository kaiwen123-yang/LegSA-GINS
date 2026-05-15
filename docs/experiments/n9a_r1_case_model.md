# N9A R1 Case Model

Corrected main case:

- `BY2_normal_clean`

The following names are comparison series, not cases:

- `pure_INS`
- `single_antenna_original_KF_GINS`
- `final_v23_dual_antenna_EKF`
- `source_backed_EKF`
- `Raw_Doppler_EKF`
- `source_aware_EKF`
- `Go2_joint_EKF`
- `no_feedback_FGO`
- `selected_feedback_EKF`
- `reject_all_sanity`

The initial N9A run counted 30 N8K formal ablation variants as 30 cases. N9A_R1
keeps those variants only as archive context and does not use them as
`BY2_normal_clean` cases.

This model is required before any later N9B planning. N9A_R1 itself does not run
N9B and does not make paper performance claims.
