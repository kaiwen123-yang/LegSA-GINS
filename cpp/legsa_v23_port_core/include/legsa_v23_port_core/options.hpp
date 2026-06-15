// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/factors/raw_doppler_types.hpp"
#include "legsa_v23_port_core/factors/go2_weak_prior_types.hpp"
#include "legsa_v23_port_core/fgo_feedback/fgo_feedback.hpp"
#include "legsa_v23_port_core/quality_aware/qa_fallback.hpp"
#include "legsa_v23_port_core/source_aware/measurement_source.hpp"
#include "legsa_v23_port_core/source_aware/quality_state_manager.hpp"
#include "legsa_v23_port_core/types.hpp"

#include <string>

namespace legsa_v23_port_core {

// 中文说明：R1 options 只保存最小 backbone 配置和边界旗标，不读取 trace 或 final_v23 输出。
struct PortOptions {
  std::string phase = "N4H4R2";
  std::string port_role = "source_backed_math_port";
  std::string run_label = "N4H4R2_synthetic_math";
  std::string algorithm_id;
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
  bool enable_receiver_velocity_update = true;
  std::string receiver_velocity_stress_mode = "none";
  double receiver_velocity_std_scale = 1.0;
  double receiver_velocity_outage_start_sec = 0.0;
  double receiver_velocity_outage_duration_sec = 0.0;
  double receiver_velocity_additive_noise_std_mps = 0.0;
  int receiver_velocity_additive_noise_seed = 20260510;
  bool diagnostic_stress_only = false;
  bool diagnostic_only = false;
  bool no_outperform_final_v23_claim = true;
  std::string ablation_variant = "baseline_full";
  bool raw_doppler = false;
  bool raw_doppler_factor_code_present = false;
  bool raw_doppler_toy_factor_applied = false;
  RawDopplerFactorConfig raw_doppler_config;
  RawDopplerFactorStatus raw_doppler_status;
  bool go2_prior = false;
  // 中文说明：N7C6 Go2 joint observation factor 是 roll/pitch + horizontal velocity
  // sequential-equivalent；不启用 Go2 position、yaw 或 vertical velocity prior。
  bool enable_go2_proprioceptive_joint_factor = false;
  std::string go2_proprioceptive_joint_factor_path;
  std::string go2_proprioceptive_joint_factor_mode = "sequential_equivalent";
  std::string go2_proprioceptive_joint_factor_policy;
  bool go2_proprioceptive_source_aware_enabled = true;
  bool go2_vertical_velocity_prior_enabled = false;
  // 中文说明：N7A Go2 roll/pitch weak prior 默认关闭；开启后仍不把 Go2 position/velocity/yaw 当 solver prior。
  Go2AttitudeWeakPriorConfig go2_attitude_prior_config;
  Go2AttitudeWeakPriorStatus go2_attitude_prior_status;
  // 中文说明：N7B3 Go2 velocity/contact 只允许 diagnostic-only activation；默认关闭，且不是正式 proposed result。
  Go2VelocityDiagnosticPriorConfig go2_velocity_prior_diagnostic_config;
  Go2VelocityDiagnosticPriorStatus go2_velocity_prior_diagnostic_status;
  Go2ReadinessLsimMetadataConfig go2_readiness_lsim_metadata_config;
  Go2ReadinessLsimMetadataStatus go2_readiness_lsim_metadata_status;
  Go2YawRateDiagnosticPriorConfig go2_yaw_rate_prior_diagnostic_config;
  Go2YawRateDiagnosticPriorStatus go2_yaw_rate_prior_diagnostic_status;
  bool go2_diagnostic_prior_only = true;
  bool lsim_oim = false;
  // 中文说明：N6A source-aware LSIM/OIM 默认关闭；打开后只基于 solver 可见 metadata/innovation 放大 R。
  source_aware::SourceAwarePolicyConfig source_aware_policy_config;
  source_aware::SourceAwareRuntimeStats source_aware_runtime_stats;
  source_aware::QualityStateManagerConfig quality_state_manager_config;
  source_aware::QualityStateRuntimeStats quality_state_runtime_stats;
  bool multi_state_qm = false;
  bool fgo = false;
  // 中文说明：N8G FGO feedback 默认关闭；开启时只能作为 EKF pseudo-measurement update。
  fgo_feedback::FgoFeedbackConfig fgo_feedback_config;
  fgo_feedback::FgoFeedbackStatus fgo_feedback_status;
  bool performance_claim = false;
  bool paper_performance_claim = false;
  bool proposed_factor_claim = false;
  quality_aware::QAFallbackConfig qa_fallback_config;
  bool qa_fallback_layer_present = false;
  bool qa_fallback_active = false;
  bool qa_passive_logging_enabled = false;
  std::size_t qa_log_row_count = 0;
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
  bool debug_overclose_audit_enabled = false;
  bool debug_measurement_copy_guard_enabled = false;
  bool debug_covariance_gain_enabled = false;
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
