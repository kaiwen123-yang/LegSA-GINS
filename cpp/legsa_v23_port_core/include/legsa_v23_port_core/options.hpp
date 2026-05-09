// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/types.hpp"

#include <string>

namespace legsa_v23_port_core {

// 中文说明：R1 options 只保存最小 backbone 配置和边界旗标，不读取 trace 或 final_v23 输出。
struct PortOptions {
  std::string phase = "N4H4R2";
  std::string port_role = "source_backed_math_port";
  std::string run_label = "N4H4R2_synthetic_math";
  std::string imu_path;
  std::string gnss_path;
  Vec3 antlever_m = makeVec3(0.0, 0.0, 0.0);
  Vec3 init_pos_blh_rad_m = makeVec3(0.0, 0.0, 0.0);
  Vec3 init_vel_ned_mps = makeVec3(0.0, 0.0, 0.0);
  Vec3 init_att_rad = makeVec3(0.0, 0.0, 0.0);
  Vec3 init_pos_std_m = makeVec3(1.0, 1.0, 1.0);
  Vec3 init_vel_std_mps = makeVec3(0.1, 0.1, 0.1);
  Vec3 init_att_std_rad = makeVec3(1.0 * D2R, 1.0 * D2R, 1.0 * D2R);
  ImuError init_imu_error;
  ImuError init_imu_error_std;
  ImuNoise imunoise;
  double init_cov_diag = 1.0;
  double starttime = 0.0;
  double endtime = 0.0;
  int imudatalen = 7;
  double imudatarate = 100.0;
  bool math_port_completed = true;
  bool parity_attempted = false;
  bool real_clean_replay_attempted = false;
  bool final_v23_output_solver_input = false;
  bool trace_solver_input = false;
  bool output_only_correction = false;
  bool bad_epoch_deletion_for_metric = false;
  bool raw_doppler = false;
  bool go2_prior = false;
  bool lsim_oim = false;
  bool fgo = false;
  bool performance_claim = false;
  bool paper_performance_claim = false;
  bool proposed_factor_claim = false;
  bool engineering_backbone_parity_only = false;
  std::string clean_input_provenance_label;
  std::string config_policy_evidence_status = "source_backed_runtime_config";
  std::size_t propagation_count = 0;
  std::size_t measurement_update_count = 0;
  std::size_t position_update_count = 0;
  std::size_t velocity_update_count = 0;
  std::size_t yaw_update_count = 0;
  std::size_t yaw_normal_count = 0;
  std::size_t yaw_downweight_count = 0;
  std::size_t yaw_reject_count = 0;
  bool debug_update_timeline_enabled = false;
  std::size_t gnss_rows_total = 0;
  std::size_t gnss_rows_in_overlap = 0;
  std::size_t expected_update_count = 0;
  std::size_t actual_update_count = 0;
  double update_count_ratio = 0.0;
  bool update_count_low = false;
  bool gnss_rows_skipped_unexpectedly = false;
  bool runtime_loop_fix_applied = false;
  bool source_backed_runtime_loop_fix = false;
  bool yaw_scheme_C_enabled = true;
  double yaw_std_min_deg = 0.5;
  double yaw_std_soft_deg = 3.0;
  double yaw_std_hard_deg = 6.0;
  double yaw_res_soft_deg = 6.0;
  double yaw_res_hard_deg = 15.0;
  double yaw_downweight_scale = 2.5;
};

}  // namespace legsa_v23_port_core
