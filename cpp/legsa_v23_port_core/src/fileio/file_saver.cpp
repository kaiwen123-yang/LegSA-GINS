// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/fileio/file_saver.hpp"

#include "legsa_v23_port_core/common/earth.hpp"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <stdexcept>
#include <string>

namespace legsa_v23_port_core {
namespace {

// 中文说明：统一创建输出目录；toy 输出只写 runtime output dir，不进入 Git。
void ensureOutputDir(const std::string& output_dir) {
  std::filesystem::create_directories(output_dir);
}

std::string escapeJson(const std::string& value) {
  std::string out;
  for (char ch : value) {
    if (ch == '\\' || ch == '"') {
      out.push_back('\\');
    }
    out.push_back(ch);
  }
  return out;
}

double stdOutputScale(std::size_t index) {
  if (index >= PHI_ID && index < PHI_ID + 3) {
    return R2D;
  }
  if (index >= BG_ID && index < BG_ID + 3) {
    return R2D * 3600.0;
  }
  if (index >= BA_ID && index < BA_ID + 3) {
    return 1.0e5;
  }
  if (index >= SG_ID && index < SG_ID + 3) {
    return 1.0e6;
  }
  if (index >= SA_ID && index < SA_ID + 3) {
    return 1.0e6;
  }
  return 1.0;
}

void writeSourceAwareCountObject(std::ostream& out, const std::array<std::size_t, source_aware::kMeasurementSourceCount>& counts) {
  out << "{";
  for (std::size_t i = 0; i < source_aware::kMeasurementSourceCount; ++i) {
    if (i > 0) {
      out << ", ";
    }
    out << "\"" << source_aware::toString(static_cast<source_aware::MeasurementSource>(i)) << "\": " << counts[i];
  }
  out << "}";
}

void writeSourceAwareScaleStats(std::ostream& out, const source_aware::SourceAwareRuntimeStats& stats) {
  out << "{";
  for (std::size_t i = 0; i < source_aware::kMeasurementSourceCount; ++i) {
    if (i > 0) {
      out << ", ";
    }
    const auto source = static_cast<source_aware::MeasurementSource>(i);
    out << "\"" << source_aware::toString(source) << "\": {"
        << "\"p50\": " << stats.scale_p50_by_source[i] << ", "
        << "\"p95\": " << stats.scale_p95_by_source[i] << ", "
        << "\"max\": " << stats.scale_max_by_source[i] << "}";
  }
  out << "}";
}

void writeSourceCaps(std::ostream& out, const source_aware::SourceAwarePolicyConfig& config) {
  out << "{"
      << "\"receiver_position\": " << config.source_aware_receiver_position_cap << ", "
      << "\"receiver_velocity\": " << config.source_aware_receiver_velocity_cap << ", "
      << "\"dual_antenna_yaw\": " << config.source_aware_dual_yaw_cap << ", "
      << "\"raw_doppler_velocity\": " << config.source_aware_raw_doppler_cap << ", "
      << "\"go2_attitude_roll_pitch\": " << config.source_aware_go2_attitude_cap << ", "
      << "\"go2_horizontal_velocity\": " << config.source_aware_go2_horizontal_velocity_cap << ", "
      << "\"global\": " << config.source_aware_global_cap << "}";
}

const char* stdOutputName(std::size_t index) {
  static constexpr const char* kNames[kErrorStateSize] = {
      "std_pos_n_m",        "std_pos_e_m",        "std_pos_d_m",
      "std_vel_n_mps",      "std_vel_e_mps",      "std_vel_d_mps",
      "std_roll_deg",       "std_pitch_deg",      "std_yaw_deg",
      "std_gyrbias_x_dph",  "std_gyrbias_y_dph",  "std_gyrbias_z_dph",
      "std_accbias_x_mgal", "std_accbias_y_mgal", "std_accbias_z_mgal",
      "std_gyrscale_x_ppm", "std_gyrscale_y_ppm", "std_gyrscale_z_ppm",
      "std_accscale_x_ppm", "std_accscale_y_ppm", "std_accscale_z_ppm",
  };
  return kNames[index];
}

}  // namespace

// 中文说明：NAV writer 输出 toy 状态，不做 output-only correction。
void FileSaver::writeNav(const std::string& output_dir, const std::vector<NavState>& states) {
  ensureOutputDir(output_dir);
  std::ofstream out(std::filesystem::path(output_dir) / "LegSA_PORT_NAV.nav");
  out << std::fixed << std::setprecision(10);
  out << "# time lat_deg lon_deg height_m vn ve vd roll_deg pitch_deg yaw_deg\n";
  for (const auto& state : states) {
    out << state.time << ' ' << Earth::radToDeg(state.pos_blh_rad_m[0]) << ' '
        << Earth::radToDeg(state.pos_blh_rad_m[1]) << ' ' << state.pos_blh_rad_m[2] << ' '
        << state.vel_ned_mps[0] << ' ' << state.vel_ned_mps[1] << ' ' << state.vel_ned_mps[2]
        << ' ' << Earth::radToDeg(state.euler_rad[0]) << ' ' << Earth::radToDeg(state.euler_rad[1])
        << ' ' << Earth::radToDeg(state.euler_rad[2]) << '\n';
  }
}

// 中文说明：STD writer 只写协方差对角 sqrt 的 common-unit 输出，R2 synthetic 仍不声明 parity/performance。
void FileSaver::writeStd(const std::string& output_dir, const std::vector<std::vector<double>>& covariances) {
  ensureOutputDir(output_dir);
  std::ofstream out(std::filesystem::path(output_dir) / "LegSA_PORT_STD.csv");
  out << "row";
  for (std::size_t i = 0; i < kErrorStateSize; ++i) {
    out << ',' << stdOutputName(i);
  }
  out << '\n';
  for (std::size_t row = 0; row < covariances.size(); ++row) {
    out << row;
    for (std::size_t i = 0; i < kErrorStateSize; ++i) {
      const std::size_t diagonal_index = covariances[row].size() == kErrorStateSize
                                             ? i
                                             : i * kErrorStateSize + i;
      const double value = diagonal_index < covariances[row].size() ? covariances[row][diagonal_index] : 0.0;
      // 中文说明：姿态协方差内部单位为 rad²，输出 STD 转为 deg，便于与 KF-GINS_STD.txt 对齐。
      out << ',' << std::sqrt(std::max(0.0, value)) * stdOutputScale(i);
    }
    out << '\n';
  }
}

// 中文说明：EVAL_NAV 使用 Python evaluator 可读字段；R1 toy 不是 performance。
void FileSaver::writeEvalNav(const std::string& output_dir, const std::vector<NavState>& states) {
  ensureOutputDir(output_dir);
  std::ofstream out(std::filesystem::path(output_dir) / "EVAL_NAV.csv");
  out << "time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg\n";
  out << std::fixed << std::setprecision(10);
  for (const auto& state : states) {
    out << state.time << ',' << Earth::radToDeg(state.pos_blh_rad_m[0]) << ','
        << Earth::radToDeg(state.pos_blh_rad_m[1]) << ',' << state.pos_blh_rad_m[2] << ','
        << state.vel_ned_mps[0] << ',' << state.vel_ned_mps[1] << ',' << state.vel_ned_mps[2]
        << ',' << Earth::radToDeg(state.euler_rad[0]) << ',' << Earth::radToDeg(state.euler_rad[1])
        << ',' << Earth::radToDeg(state.euler_rad[2]) << '\n';
  }
}

// 中文说明：RUN_MANIFEST 记录 R2/R3 运行边界和计数；reference 输出不进入 solver。
void FileSaver::writeRunManifest(const std::string& output_dir, const PortOptions& options) {
  ensureOutputDir(output_dir);
  std::ofstream out(std::filesystem::path(output_dir) / "RUN_MANIFEST.json");
  if (!out) {
    throw std::runtime_error("failed to write RUN_MANIFEST");
  }
  out << "{\n"
      << "  \"phase\": \"" << escapeJson(options.phase) << "\",\n"
      << "  \"port_role\": \"" << escapeJson(options.port_role) << "\",\n"
      << "  \"math_port_completed\": " << (options.math_port_completed ? "true" : "false") << ",\n"
      << "  \"parity_attempted\": " << (options.parity_attempted ? "true" : "false") << ",\n"
      << "  \"real_clean_replay_attempted\": " << (options.real_clean_replay_attempted ? "true" : "false") << ",\n"
      << "  \"engineering_backbone_parity_only\": "
      << (options.engineering_backbone_parity_only ? "true" : "false") << ",\n"
      << "  \"paper_performance_claim\": " << (options.paper_performance_claim ? "true" : "false") << ",\n"
      << "  \"proposed_factor_claim\": " << (options.proposed_factor_claim ? "true" : "false") << ",\n"
      << "  \"final_v23_output_solver_input\": " << (options.final_v23_output_solver_input ? "true" : "false") << ",\n"
      << "  \"trace_solver_input\": " << (options.trace_solver_input ? "true" : "false") << ",\n"
      << "  \"output_only_correction\": " << (options.output_only_correction ? "true" : "false") << ",\n"
      << "  \"bad_epoch_deletion_for_metric\": " << (options.bad_epoch_deletion_for_metric ? "true" : "false") << ",\n"
      << "  \"algorithm_id\": \"" << escapeJson(options.algorithm_id) << "\",\n"
      << "  \"ablation_variant\": \"" << escapeJson(options.ablation_variant) << "\",\n"
      << "  \"qa_fallback_layer_present\": " << (options.qa_fallback_layer_present ? "true" : "false") << ",\n"
      << "  \"qa_passive_logging_enabled\": " << (options.qa_passive_logging_enabled ? "true" : "false") << ",\n"
      << "  \"enable_qa_fallback\": "
      << (options.qa_fallback_config.enable_qa_fallback ? "true" : "false") << ",\n"
      << "  \"qa_active_mode\": " << (options.qa_fallback_active ? "true" : "false") << ",\n"
      << "  \"qa_log_row_count\": " << options.qa_log_row_count << ",\n"
      << "  \"qa_trace_used_for_QA\": false,\n"
      << "  \"qa_a1_quality_source\": \""
      << escapeJson(options.qa_fallback_config.a1_quality_source) << "\",\n"
      << "  \"qa_a1_relpos_diff_valid_default\": "
      << (options.qa_fallback_config.a1_relpos_diff_valid_default ? "true" : "false") << ",\n"
      << "  \"qa_recovery_max_yaw_correction_deg\": "
      << options.qa_fallback_config.recovery_max_yaw_correction_deg << ",\n"
      << "  \"enable_receiver_velocity_update\": "
      << (options.enable_receiver_velocity_update ? "true" : "false") << ",\n"
      << "  \"receiver_velocity_stress_mode\": \""
      << escapeJson(options.receiver_velocity_stress_mode) << "\",\n"
      << "  \"receiver_velocity_std_scale\": " << options.receiver_velocity_std_scale << ",\n"
      << "  \"receiver_velocity_outage_start_sec\": "
      << options.receiver_velocity_outage_start_sec << ",\n"
      << "  \"receiver_velocity_outage_duration_sec\": "
      << options.receiver_velocity_outage_duration_sec << ",\n"
      << "  \"receiver_velocity_additive_noise_std_mps\": "
      << options.receiver_velocity_additive_noise_std_mps << ",\n"
      << "  \"receiver_velocity_additive_noise_seed\": "
      << options.receiver_velocity_additive_noise_seed << ",\n"
      << "  \"diagnostic_stress_only\": " << (options.diagnostic_stress_only ? "true" : "false") << ",\n"
      << "  \"diagnostic_only\": " << (options.diagnostic_only ? "true" : "false") << ",\n"
      << "  \"no_outperform_final_v23_claim\": "
      << (options.no_outperform_final_v23_claim ? "true" : "false") << ",\n"
      << "  \"raw_doppler\": " << (options.raw_doppler ? "true" : "false") << ",\n"
      << "  \"raw_doppler_factor_code_present\": "
      << (options.raw_doppler_factor_code_present ? "true" : "false") << ",\n"
      << "  \"raw_doppler_toy_factor_applied\": "
      << (options.raw_doppler_toy_factor_applied ? "true" : "false") << ",\n"
      << "  \"enable_raw_doppler\": "
      << (options.raw_doppler_config.enable_raw_doppler ? "true" : "false") << ",\n"
      << "  \"raw_doppler_solver_enabled\": "
      << (options.raw_doppler_config.raw_doppler_solver_enabled ? "true" : "false") << ",\n"
      << "  \"raw_doppler_R_scale\": " << options.raw_doppler_config.raw_doppler_R_scale << ",\n"
      << "  \"raw_doppler_mode\": \"" << escapeJson(options.raw_doppler_config.raw_doppler_mode) << "\",\n"
      << "  \"raw_doppler_update_count\": " << options.raw_doppler_status.update_count << ",\n"
      << "  \"raw_doppler_reject_count\": " << options.raw_doppler_status.reject_count << ",\n"
      << "  \"raw_doppler_epoch_count\": " << options.raw_doppler_status.epoch_count << ",\n"
      << "  \"raw_doppler_factor_epoch_count\": " << options.raw_doppler_status.epoch_count << ",\n"
      << "  \"raw_doppler_factor_valid_epoch_count\": " << options.raw_doppler_status.valid_epoch_count << ",\n"
      << "  \"raw_doppler_factor_source\": \"" << escapeJson(options.raw_doppler_status.factor_source) << "\",\n"
      << "  \"raw_doppler_velocity_not_nav_pvt\": "
      << (options.raw_doppler_status.velocity_not_nav_pvt ? "true" : "false") << ",\n"
      << "  \"raw_doppler_velocity_not_gnss_15col\": "
      << (options.raw_doppler_status.velocity_not_gnss_15col ? "true" : "false") << ",\n"
      << "  \"raw_doppler_sat_count_min\": " << options.raw_doppler_status.sat_count_min << ",\n"
      << "  \"raw_doppler_sat_count_median\": " << options.raw_doppler_status.sat_count_median << ",\n"
      << "  \"raw_doppler_sat_count_max\": " << options.raw_doppler_status.sat_count_max << ",\n"
      << "  \"raw_doppler_residual_p95\": " << options.raw_doppler_status.residual_p95_mps << ",\n"
      << "  \"raw_doppler_provider_status\": \""
      << escapeJson(options.raw_doppler_status.provider_status) << "\",\n"
      << "  \"go2_prior\": " << (options.go2_prior ? "true" : "false") << ",\n"
      << "  \"go2_proprioceptive_joint_factor_enabled\": "
      << (options.enable_go2_proprioceptive_joint_factor ? "true" : "false") << ",\n"
      << "  \"go2_proprioceptive_joint_factor_update_count\": "
      << (options.enable_go2_proprioceptive_joint_factor
              ? std::min(options.go2_attitude_prior_status.update_count,
                         options.go2_velocity_prior_diagnostic_status.horizontal_update_count)
              : 0)
      << ",\n"
      << "  \"go2_proprioceptive_joint_factor_reject_count\": "
      << (options.enable_go2_proprioceptive_joint_factor
              ? options.go2_attitude_prior_status.reject_count + options.go2_velocity_prior_diagnostic_status.reject_count
              : 0)
      << ",\n"
      << "  \"go2_proprioceptive_joint_factor_mode\": \""
      << escapeJson(options.go2_proprioceptive_joint_factor_mode) << "\",\n"
      << "  \"go2_proprioceptive_joint_factor_policy\": \""
      << escapeJson(options.go2_proprioceptive_joint_factor_policy) << "\",\n"
      << "  \"go2_proprioceptive_joint_factor_path_role\": \""
      << (options.go2_proprioceptive_joint_factor_path.empty() ? "" : "runtime_joint_prior_csv") << "\",\n"
      << "  \"go2_proprioceptive_joint_factor_sequential_equivalent\": "
      << ((options.enable_go2_proprioceptive_joint_factor &&
           options.go2_proprioceptive_joint_factor_mode == "sequential_equivalent")
              ? "true"
              : "false")
      << ",\n"
      << "  \"go2_proprioceptive_source_aware_enabled\": "
      << (options.go2_proprioceptive_source_aware_enabled ? "true" : "false") << ",\n"
      << "  \"go2_attitude_weak_prior_enabled\": "
      << (options.go2_attitude_prior_config.enable_go2_attitude_weak_prior ? "true" : "false") << ",\n"
      << "  \"go2_attitude_weak_prior_update_count\": "
      << options.go2_attitude_prior_status.update_count << ",\n"
      << "  \"go2_attitude_weak_prior_reject_count\": "
      << options.go2_attitude_prior_status.reject_count << ",\n"
      << "  \"go2_attitude_weak_prior_prior_count\": "
      << options.go2_attitude_prior_status.prior_count << ",\n"
      << "  \"go2_attitude_weak_prior_valid_prior_count\": "
      << options.go2_attitude_prior_status.valid_prior_count << ",\n"
      << "  \"go2_attitude_prior_provider_status\": \""
      << escapeJson(options.go2_attitude_prior_status.provider_status) << "\",\n"
      << "  \"go2_attitude_prior_sourceaware_enabled\": "
      << (options.go2_attitude_prior_config.go2_attitude_prior_sourceaware ? "true" : "false") << ",\n"
      << "  \"go2_attitude_prior_diagnostic_only\": "
      << (options.go2_attitude_prior_config.go2_attitude_prior_diagnostic_only ? "true" : "false") << ",\n"
      << "  \"go2_attitude_prior_std_roll_deg\": "
      << options.go2_attitude_prior_config.go2_attitude_prior_std_roll_deg << ",\n"
      << "  \"go2_attitude_prior_std_pitch_deg\": "
      << options.go2_attitude_prior_config.go2_attitude_prior_std_pitch_deg << ",\n"
      << "  \"go2_attitude_prior_residual_roll_p95_rad\": "
      << options.go2_attitude_prior_status.residual_roll_p95_rad << ",\n"
      << "  \"go2_attitude_prior_residual_pitch_p95_rad\": "
      << options.go2_attitude_prior_status.residual_pitch_p95_rad << ",\n"
      << "  \"go2_position_prior_enabled\": false,\n"
      << "  \"go2_velocity_prior_enabled\": false,\n"
      << "  \"go2_yaw_prior_enabled\": false,\n"
      << "  \"go2_vertical_velocity_prior_enabled\": false,\n"
      << "  \"go2_velocity_prior_diagnostic_enabled\": "
      << (options.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic ? "true" : "false") << ",\n"
      << "  \"go2_horizontal_velocity_prior_enabled\": "
      << (options.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior ? "true" : "false") << ",\n"
      << "  \"go2_velocity_prior_update_count\": "
      << options.go2_velocity_prior_diagnostic_status.update_count << ",\n"
      << "  \"go2_velocity_prior_reject_count\": "
      << options.go2_velocity_prior_diagnostic_status.reject_count << ",\n"
      << "  \"go2_velocity_prior_diagnostic_prior_count\": "
      << options.go2_velocity_prior_diagnostic_status.prior_count << ",\n"
      << "  \"go2_velocity_prior_diagnostic_valid_prior_count\": "
      << options.go2_velocity_prior_diagnostic_status.valid_prior_count << ",\n"
      << "  \"go2_velocity_prior_diagnostic_provider_status\": \""
      << escapeJson(options.go2_velocity_prior_diagnostic_status.provider_status) << "\",\n"
      << "  \"go2_velocity_prior_std_scale\": "
      << options.go2_velocity_prior_diagnostic_config.go2_velocity_prior_std_scale << ",\n"
      << "  \"go2_horizontal_velocity_prior_std_scale\": "
      << options.go2_velocity_prior_diagnostic_config.go2_velocity_prior_std_scale << ",\n"
      << "  \"go2_horizontal_velocity_prior_mode\": \""
      << escapeJson(options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_mode) << "\",\n"
      << "  \"go2_horizontal_velocity_adaptive_std_enabled\": "
      << (options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_adaptive_std_enabled ? "true" : "false") << ",\n"
      << "  \"go2_horizontal_velocity_bounded_std_policy\": \""
      << escapeJson(options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_bounded_std_policy) << "\",\n"
      << "  \"go2_horizontal_velocity_strength_policy\": \""
      << escapeJson(options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_strength_policy) << "\",\n"
      << "  \"go2_horizontal_velocity_prior_source_aware_enabled\": "
      << (options.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_source_aware_enabled ? "true" : "false") << ",\n"
      << "  \"go2_horizontal_velocity_prior_diagnostic_enabled\": "
      << ((options.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic &&
           options.go2_velocity_prior_diagnostic_status.horizontal_only)
              ? "true"
              : "false")
      << ",\n"
      << "  \"go2_horizontal_velocity_prior_update_count\": "
      << options.go2_velocity_prior_diagnostic_status.horizontal_update_count << ",\n"
      << "  \"go2_horizontal_velocity_prior_skip_count\": "
      << options.go2_velocity_prior_diagnostic_status.skip_count << ",\n"
      << "  \"go2_horizontal_velocity_prior_vertical_disabled\": "
      << (options.go2_velocity_prior_diagnostic_status.vertical_disabled ? "true" : "false") << ",\n"
      << "  \"go2_horizontal_velocity_prior_std_vn_p50\": "
      << options.go2_velocity_prior_diagnostic_status.std_vn_p50 << ",\n"
      << "  \"go2_horizontal_velocity_prior_std_vn_p95\": "
      << options.go2_velocity_prior_diagnostic_status.std_vn_p95 << ",\n"
      << "  \"go2_horizontal_velocity_prior_std_vn_max\": "
      << options.go2_velocity_prior_diagnostic_status.std_vn_max << ",\n"
      << "  \"go2_horizontal_velocity_prior_std_ve_p50\": "
      << options.go2_velocity_prior_diagnostic_status.std_ve_p50 << ",\n"
      << "  \"go2_horizontal_velocity_prior_std_ve_p95\": "
      << options.go2_velocity_prior_diagnostic_status.std_ve_p95 << ",\n"
      << "  \"go2_horizontal_velocity_prior_std_ve_max\": "
      << options.go2_velocity_prior_diagnostic_status.std_ve_max << ",\n"
      << "  \"go2_horizontal_velocity_prior_max_std_le_5\": "
      << (options.go2_velocity_prior_diagnostic_status.max_std_le_5 ? "true" : "false") << ",\n"
      << "  \"go2_horizontal_velocity_prior_confidence_counts\": {"
      << "\"high\": " << options.go2_velocity_prior_diagnostic_status.confidence_high_count << ", "
      << "\"medium\": " << options.go2_velocity_prior_diagnostic_status.confidence_medium_count << ", "
      << "\"low\": " << options.go2_velocity_prior_diagnostic_status.confidence_low_count << ", "
      << "\"invalid\": " << options.go2_velocity_prior_diagnostic_status.confidence_invalid_count << "},\n"
      << "  \"go2_horizontal_velocity_prior_controlled_activation\": "
      << (options.go2_velocity_prior_diagnostic_status.controlled_activation ? "true" : "false") << ",\n"
      << "  \"formal_go2_velocity_prior\": false,\n"
      << "  \"go2_yaw_rate_prior_diagnostic_enabled\": "
      << (options.go2_yaw_rate_prior_diagnostic_config.enable_go2_yaw_rate_prior_diagnostic ? "true" : "false") << ",\n"
      << "  \"go2_yaw_rate_prior_update_count\": "
      << options.go2_yaw_rate_prior_diagnostic_status.update_count << ",\n"
      << "  \"go2_yaw_rate_prior_reject_count\": "
      << options.go2_yaw_rate_prior_diagnostic_status.reject_count << ",\n"
      << "  \"go2_yaw_rate_prior_activation_status\": \""
      << escapeJson(options.go2_yaw_rate_prior_diagnostic_status.activation_status) << "\",\n"
      << "  \"go2_diagnostic_prior_only\": " << (options.go2_diagnostic_prior_only ? "true" : "false") << ",\n"
      << "  \"go2_velocity_truth_claim\": false,\n"
      << "  \"go2_body_state_not_truth\": true,\n"
      << "  \"go2_readiness_lsim_metadata_enabled\": "
      << (options.go2_readiness_lsim_metadata_config.enable_go2_readiness_lsim_metadata ? "true" : "false") << ",\n"
      << "  \"go2_readiness_lsim_provider_status\": \""
      << escapeJson(options.go2_readiness_lsim_metadata_status.provider_status) << "\",\n"
      << "  \"go2_readiness_lsim_metadata_count\": "
      << options.go2_readiness_lsim_metadata_status.metadata_count << ",\n"
      << "  \"go2_readiness_lsim_valid_metadata_count\": "
      << options.go2_readiness_lsim_metadata_status.valid_metadata_count << ",\n"
      << "  \"go2_readiness_lsim_matched_metadata_count\": "
      << options.go2_readiness_lsim_metadata_status.matched_metadata_count << ",\n"
      << "  \"go2_readiness_first_class_lsim\": "
      << (options.go2_readiness_lsim_metadata_status.readiness_metadata_first_class_lsim ? "true" : "false") << ",\n"
      << "  \"go2_readiness_lsim_time_tolerance_sec\": "
      << options.go2_readiness_lsim_metadata_config.go2_readiness_lsim_time_tolerance_sec << ",\n"
      << "  \"go2_readiness_trace_solver_input\": false,\n"
      << "  \"go2_readiness_final_v23_output_solver_input\": false,\n"
      << "  \"go2_readiness_go2_position_truth_claim\": false,\n"
      << "  \"go2_readiness_go2_yaw_truth_claim\": false,\n"
      << "  \"lsim_oim\": " << (options.lsim_oim ? "true" : "false") << ",\n";
  out << "  \"source_aware_weighting_enabled\": "
      << (options.source_aware_policy_config.enable_source_aware_weighting ? "true" : "false") << ",\n"
      << "  \"source_aware_policy_version\": \""
      << escapeJson(options.source_aware_policy_config.source_aware_policy_version) << "\",\n"
      << "  \"source_aware_use_innovation_covariance\": "
      << (options.source_aware_policy_config.source_aware_use_innovation_covariance ? "true" : "false") << ",\n"
      << "  \"source_aware_mode\": \""
      << escapeJson(options.source_aware_policy_config.source_aware_mode) << "\",\n"
      << "  \"source_aware_max_R_scale\": "
      << options.source_aware_policy_config.source_aware_max_R_scale << ",\n"
      << "  \"source_aware_global_cap\": "
      << options.source_aware_policy_config.source_aware_global_cap << ",\n"
      << "  \"source_aware_deadband_normalized\": "
      << options.source_aware_policy_config.source_aware_deadband_normalized << ",\n"
      << "  \"source_aware_moderate_normalized\": "
      << options.source_aware_policy_config.source_aware_moderate_normalized << ",\n"
      << "  \"source_aware_strong_normalized\": "
      << options.source_aware_policy_config.source_aware_strong_normalized << ",\n"
      << "  \"source_aware_reject_extreme\": "
      << (options.source_aware_policy_config.source_aware_reject_extreme ? "true" : "false") << ",\n"
      << "  \"source_aware_no_R_shrink\": "
      << (options.source_aware_policy_config.source_aware_no_R_shrink ? "true" : "false") << ",\n"
      << "  \"source_aware_trace_enabled\": "
      << (options.source_aware_policy_config.source_aware_trace_enabled ? "true" : "false") << ",\n"
      << "  \"source_aware_enable_rolling_innovation_baseline\": "
      << (options.source_aware_policy_config.source_aware_enable_rolling_innovation_baseline ? "true" : "false") << ",\n"
      << "  \"source_aware_rolling_window_size\": "
      << options.source_aware_policy_config.source_aware_rolling_window_size << ",\n"
      << "  \"source_aware_rolling_mad_floor\": "
      << options.source_aware_policy_config.source_aware_rolling_mad_floor << ",\n"
      << "  \"source_aware_method_family\": \""
      << escapeJson(options.source_aware_policy_config.source_aware_method_family) << "\",\n"
      << "  \"source_aware_method_k0\": "
      << options.source_aware_policy_config.source_aware_method_k0 << ",\n"
      << "  \"source_aware_method_k1\": "
      << options.source_aware_policy_config.source_aware_method_k1 << ",\n"
      << "  \"source_aware_method_c\": "
      << options.source_aware_policy_config.source_aware_method_c << ",\n"
      << "  \"source_aware_method_alpha\": "
      << options.source_aware_policy_config.source_aware_method_alpha << ",\n"
      << "  \"source_aware_method_phi\": "
      << options.source_aware_policy_config.source_aware_method_phi << ",\n"
      << "  \"source_aware_method_base_gain\": "
      << options.source_aware_policy_config.source_aware_method_base_gain << ",\n"
      << "  \"source_aware_go2_readiness_lsim_enabled\": "
      << (options.source_aware_policy_config.source_aware_go2_readiness_lsim_enabled ? "true" : "false") << ",\n"
      << "  \"source_aware_go2_readiness_low_scale\": "
      << options.source_aware_policy_config.source_aware_go2_readiness_low_scale << ",\n"
      << "  \"source_aware_go2_impact_or_rough_scale\": "
      << options.source_aware_policy_config.source_aware_go2_impact_or_rough_scale << ",\n"
      << "  \"source_aware_go2_motion_unknown_scale\": "
      << options.source_aware_policy_config.source_aware_go2_motion_unknown_scale << ",\n"
      << "  \"source_aware_go2_in_place_turn_scale\": "
      << options.source_aware_policy_config.source_aware_go2_in_place_turn_scale << ",\n"
      << "  \"source_caps\": ";
  writeSourceCaps(out, options.source_aware_policy_config);
  out << ",\n"
      << "  \"source_aware_clean_neutral_gate\": {"
      << "\"horizontal_delta_m_max\": 0.10, \"up_delta_m_max\": 0.20, "
      << "\"yaw_delta_deg_max\": 0.30, \"roll_delta_deg_max\": 0.15, "
      << "\"pitch_delta_deg_max\": 0.15},\n"
      << "  \"source_aware_trace_rows\": " << options.source_aware_runtime_stats.trace_row_count << ",\n"
      << "  \"source_aware_update_count_by_source\": ";
  writeSourceAwareCountObject(out, options.source_aware_runtime_stats.update_count_by_source);
  out << ",\n  \"source_aware_reject_count_by_source\": ";
  writeSourceAwareCountObject(out, options.source_aware_runtime_stats.reject_count_by_source);
  out << ",\n  \"source_aware_R_scale_p50_p95_max_by_source\": ";
  writeSourceAwareScaleStats(out, options.source_aware_runtime_stats);
  out << ",\n  \"source_aware_R_scale_stats_by_source\": ";
  writeSourceAwareScaleStats(out, options.source_aware_runtime_stats);
  out << ",\n"
      << "  \"source_aware_spike_response_evaluated\": "
      << (options.source_aware_runtime_stats.spike_response_evaluated ? "true" : "false") << ",\n"
      << "  \"fgo\": " << (options.fgo ? "true" : "false") << ",\n"
      << "  \"fgo_feedback_enabled\": "
      << (options.fgo_feedback_config.enable_fgo_feedback ? "true" : "false") << ",\n"
      << "  \"fgo_feedback_mode\": \"" << escapeJson(options.fgo_feedback_config.fgo_feedback_mode) << "\",\n"
      << "  \"feedback_observation_count\": " << options.fgo_feedback_status.observation_count << ",\n"
      << "  \"feedback_update_count\": " << options.fgo_feedback_status.update_count << ",\n"
      << "  \"feedback_accept_count\": " << options.fgo_feedback_status.accept_count << ",\n"
      << "  \"feedback_reject_count\": " << options.fgo_feedback_status.reject_count << ",\n"
      << "  \"feedback_position_enabled\": "
      << (options.fgo_feedback_config.fgo_feedback_position_enabled ? "true" : "false") << ",\n"
      << "  \"feedback_velocity_enabled\": "
      << (options.fgo_feedback_config.fgo_feedback_velocity_enabled ? "true" : "false") << ",\n"
      << "  \"feedback_attitude_enabled\": "
      << (options.fgo_feedback_config.fgo_feedback_attitude_enabled ? "true" : "false") << ",\n"
      << "  \"fgo_feedback_output_substitution\": false,\n"
      << "  \"fgo_feedback_direct_nav_override\": false,\n"
      << "  \"fgo_feedback_no_future_data\": "
      << (options.fgo_feedback_status.no_future_data ? "true" : "false") << ",\n"
      << "  \"fgo_feedback_position_correction_p50_m\": "
      << options.fgo_feedback_status.correction_position_p50_m << ",\n"
      << "  \"fgo_feedback_position_correction_p95_m\": "
      << options.fgo_feedback_status.correction_position_p95_m << ",\n"
      << "  \"fgo_feedback_position_correction_max_m\": "
      << options.fgo_feedback_status.correction_position_max_m << ",\n"
      << "  \"fgo_feedback_velocity_correction_p50_mps\": "
      << options.fgo_feedback_status.correction_velocity_p50_mps << ",\n"
      << "  \"fgo_feedback_velocity_correction_p95_mps\": "
      << options.fgo_feedback_status.correction_velocity_p95_mps << ",\n"
      << "  \"fgo_feedback_velocity_correction_max_mps\": "
      << options.fgo_feedback_status.correction_velocity_max_mps << ",\n"
      << "  \"fgo_feedback_attitude_correction_p50_deg\": "
      << options.fgo_feedback_status.correction_attitude_p50_deg << ",\n"
      << "  \"fgo_feedback_attitude_correction_p95_deg\": "
      << options.fgo_feedback_status.correction_attitude_p95_deg << ",\n"
      << "  \"fgo_feedback_attitude_correction_max_deg\": "
      << options.fgo_feedback_status.correction_attitude_max_deg << ",\n"
      << "  \"fgo_feedback_provider_status\": \""
      << escapeJson(options.fgo_feedback_status.provider_status) << "\",\n"
      << "  \"performance_claim\": " << (options.performance_claim ? "true" : "false") << ",\n"
      << "  \"yaw_scheme_C_enabled\": " << (options.yaw_scheme_C_enabled ? "true" : "false") << ",\n"
      << "  \"clean_input_provenance_label\": \"" << escapeJson(options.clean_input_provenance_label) << "\",\n"
      << "  \"config_policy_evidence_status\": \"" << escapeJson(options.config_policy_evidence_status) << "\",\n"
      << "  \"propagation_count\": " << options.propagation_count << ",\n"
      << "  \"measurement_update_count\": " << options.measurement_update_count << ",\n"
      << "  \"position_update_count\": " << options.position_update_count << ",\n"
      << "  \"velocity_update_count\": " << options.velocity_update_count << ",\n"
      << "  \"yaw_update_count\": " << options.yaw_update_count << ",\n"
      << "  \"yaw_NORMAL\": " << options.yaw_normal_count << ",\n"
      << "  \"yaw_DOWNWEIGHT\": " << options.yaw_downweight_count << ",\n"
      << "  \"yaw_REJECT\": " << options.yaw_reject_count << ",\n"
      << "  \"debug_update_timeline_enabled\": "
      << (options.debug_update_timeline_enabled ? "true" : "false") << ",\n"
      << "  \"debug_overclose_audit_enabled\": "
      << (options.debug_overclose_audit_enabled ? "true" : "false") << ",\n"
      << "  \"debug_measurement_copy_guard_enabled\": "
      << (options.debug_measurement_copy_guard_enabled ? "true" : "false") << ",\n"
      << "  \"debug_covariance_gain_enabled\": "
      << (options.debug_covariance_gain_enabled ? "true" : "false") << ",\n"
      << "  \"gnss_rows_total\": " << options.gnss_rows_total << ",\n"
      << "  \"gnss_rows_in_overlap\": " << options.gnss_rows_in_overlap << ",\n"
      << "  \"expected_update_count\": " << options.expected_update_count << ",\n"
      << "  \"actual_update_count\": " << options.actual_update_count << ",\n"
      << "  \"update_count_ratio\": " << options.update_count_ratio << ",\n"
      << "  \"update_count_low\": " << (options.update_count_low ? "true" : "false") << ",\n"
      << "  \"gnss_rows_skipped_unexpectedly\": "
      << (options.gnss_rows_skipped_unexpectedly ? "true" : "false") << ",\n"
      << "  \"runtime_loop_fix_applied\": " << (options.runtime_loop_fix_applied ? "true" : "false") << ",\n"
      << "  \"source_backed_runtime_loop_fix\": " << (options.source_backed_runtime_loop_fix ? "true" : "false") << ",\n"
      << "  \"source_commit\": \"5a4471efd4fcfcdc31e258a677af354c652ff16f\",\n"
      << "  \"final_v23_is_proposed\": false,\n"
      << "  \"run_label\": \"" << escapeJson(options.run_label) << "\"\n"
      << "}\n";
}

}  // namespace legsa_v23_port_core
