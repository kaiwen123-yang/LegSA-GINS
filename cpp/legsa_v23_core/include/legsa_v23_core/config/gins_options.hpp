#pragma once

#include "legsa_v23_core/common/math_types.hpp"
#include "legsa_v23_core/state/nav_state.hpp"

#include <string>

namespace legsa_v23_core {

// 中文说明：九类未来因子槽位在 N4H4A 全部保持 false，避免把框架骨架写成 factor claim。
struct FactorFlags {
  bool raw_doppler = false;
  bool go2_prior = false;
  bool lsim_oim = false;
  bool source_aware_weighting = false;
  bool fgo = false;
  bool fgo_feedback = false;
  bool output_only_correction = false;
  bool bad_epoch_deletion_for_metric = false;
  bool numerical_performance_claim = false;
};

// 中文说明：GINSOptions 使用 final_v23-style 运行配置字段，但不读取 trace 或 final_v23 输出。
// initpos 为 BLH(deg,deg,m) 输入后转 rad/rad/m；initatt 为 deg 输入后转 rad。
struct GINSOptions {
  std::string imu_path;
  std::string gnss_path;
  std::string output_path = ".";
  double start_time = 0.0;
  double end_time = 0.0;
  int imu_data_len = 0;
  double imu_data_rate = 0.0;
  NavState init_state;
  Vector3 init_pos_std = zeroVector3();
  Vector3 init_vel_std = zeroVector3();
  Vector3 init_att_std = zeroVector3();
  Vector3 imu_noise = zeroVector3();
  Vector3 antlever = zeroVector3();
  std::string clean_input_provenance_label = "evidence_missing";
  std::string phase = "N4H4A";
  std::string solver_role = "legsa_v23_core_skeleton";
  FactorFlags factor_flags;
  bool final_v23_reference_used_as_solver_input = false;
  bool proposed_reads_final_v23_output = false;
  bool trace_solver_input = false;
  bool measurement_update_implemented = false;
  bool state_feedback_implemented = false;
  bool mechanization_predict_implemented = false;
  bool position_update_implemented = false;
  bool velocity_update_implemented = false;
  bool yaw_update_implemented = false;
  bool velocity_lever_correction = false;
  bool yaw_H_mapping_conservative = false;
  std::string yaw_residual_sign = "not_used";
  int yaw_normal_count = 0;
  int yaw_downweight_count = 0;
  int yaw_reject_count = 0;
  int propagation_count = 0;
  int measurement_update_count = 0;
  int position_update_count = 0;
  int velocity_update_count = 0;
  int yaw_update_count = 0;
  int rejected_update_count = 0;
  bool diagnostic_mode = false;
  bool disable_position_update = false;
  bool disable_velocity_update = false;
  bool disable_yaw_update = false;
  bool disable_measurement_update = false;
  bool disable_state_feedback = false;
  int diagnostic_debug_max_updates = 30;
  int diagnostic_debug_max_rows = 100000;
  bool debug_full_update_trace = false;
  bool debug_full_state_trace = false;
  bool debug_measurement_matrix_trace = false;
  bool debug_gain_trace = false;
  bool debug_update_blocks = false;
  bool debug_feedback_delta = false;
  bool debug_covariance_gain = false;
  bool debug_imu_error_feedback = false;
  bool debug_imu_compensation = false;
  bool debug_cross_covariance = false;
  std::string diagnostic_feedback_mode = "normal";
  std::string diagnostic_update_block_mode = "all";
  std::string diagnostic_covariance_mode = "normal";
  std::string diagnostic_run_label;
  std::string diagnostic_model_variant = "baseline_current";
  bool not_for_performance_claim = false;
  bool diagnostic_only = false;
  bool solver_output_changed_by_diagnostic_switches = false;
  bool solver_output_changed_by_diagnostic_variant = false;
};

}  // namespace legsa_v23_core
