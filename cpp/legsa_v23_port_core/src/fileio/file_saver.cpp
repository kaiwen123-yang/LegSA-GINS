// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/fileio/file_saver.hpp"

#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/source_aware/source_aware_policy.hpp"

#include <algorithm>
#include <array>
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

void writeVec3Array(std::ostream& out, const Vec3& value, double multiplier = 1.0) {
  out << "[" << value[0] * multiplier << ", " << value[1] * multiplier << ", "
      << value[2] * multiplier << "]";
}

void writeInitializationCovarianceDiagonal(std::ostream& out, const PortOptions& options) {
  const std::array<Vec3, 7> std_groups{{
      options.init_pos_std_m,
      options.init_vel_std_mps,
      options.init_att_std_rad,
      options.init_imu_error_std.gyrbias,
      options.init_imu_error_std.accbias,
      options.init_imu_error_std.gyrscale,
      options.init_imu_error_std.accscale,
  }};
  out << "[";
  bool first = true;
  for (const auto& group : std_groups) {
    for (double value : group) {
      if (!first) {
        out << ", ";
      }
      first = false;
      const double variance = value * value;
      if (std::isfinite(variance)) {
        out << variance;
      } else {
        // A failed covariance-health diagnostic must remain valid JSON.
        // The explicit FAILED status and first-failure time carry the error;
        // null prevents a non-standard inf/NaN token masquerading as evidence.
        out << "null";
      }
    }
  }
  out << "]";
}

void writeSourceAwareSourceConfigs(std::ostream& out,
                                   const source_aware::SourceAwarePolicyConfig& config) {
  out << "{";
  for (std::size_t index = 0; index < source_aware::kMeasurementSourceCount; ++index) {
    if (index > 0) {
      out << ", ";
    }
    const auto source = static_cast<source_aware::MeasurementSource>(index);
    const auto& source_config = config.sources[index];
    out << "\"" << source_aware::toString(source) << "\": {"
        << "\"enabled\": " << (source_config.enabled ? "true" : "false") << ", "
        << "\"lsim_enabled\": " << (source_config.lsim_enabled ? "true" : "false") << ", "
        << "\"oim_enabled\": " << (source_config.oim_enabled ? "true" : "false") << "}";
  }
  out << "}";
}

void writeActualSolverInputPaths(std::ostream& out, const PortOptions& options) {
  out << "{";
  bool first = true;
  auto add = [&](const std::string& role, const std::string& path) {
    if (path.empty()) {
      return;
    }
    if (!first) {
      out << ", ";
    }
    first = false;
    out << "\"" << role << "\": \"" << escapeJson(path) << "\"";
  };
  add("propagation_imu", options.imu_path);
  add("gnss_position_receiver_velocity_dual_yaw", options.gnss_path);
  if (options.raw_doppler_config.enable_raw_doppler) {
    add("raw_doppler_velocity", options.raw_doppler_config.raw_doppler_factor_path);
  }
  if (options.go2_attitude_prior_config.enable_go2_attitude_weak_prior) {
    add("go2_roll_pitch_weak_prior", options.go2_attitude_prior_config.go2_attitude_prior_path);
  }
  if (options.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior) {
    add("go2_horizontal_velocity_weak_prior",
        options.go2_velocity_prior_diagnostic_config.go2_velocity_prior_diagnostic_path);
  }
  if (options.go2_readiness_lsim_metadata_config.enable_go2_readiness_lsim_metadata) {
    add("go2_source_quality_metadata",
        options.go2_readiness_lsim_metadata_config.go2_readiness_lsim_metadata_path);
  }
  if (options.fgo_feedback_config.enable_fgo_feedback) {
    add("selected_fgo_feedback", options.fgo_feedback_config.fgo_feedback_path);
  }
  out << "}";
}

void writeActualSolverInputRoles(std::ostream& out, const PortOptions& options) {
  out << "{\"propagation_imu\": \"source_backed_propagation\", "
      << "\"gnss_position_receiver_velocity_dual_yaw\": \"validity_gated_measurements\"";
  if (options.raw_doppler_config.enable_raw_doppler) {
    out << ", \"raw_doppler_velocity\": \"source_backed_auxiliary_velocity\"";
  }
  if (options.go2_attitude_prior_config.enable_go2_attitude_weak_prior) {
    out << ", \"go2_roll_pitch_weak_prior\": \"weak_prior_not_truth\"";
  }
  if (options.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior) {
    out << ", \"go2_horizontal_velocity_weak_prior\": \"horizontal_weak_prior_not_truth\"";
  }
  if (options.go2_readiness_lsim_metadata_config.enable_go2_readiness_lsim_metadata) {
    out << ", \"go2_source_quality_metadata\": \"solver_visible_quality_metadata_not_truth\"";
  }
  if (options.fgo_feedback_config.enable_fgo_feedback) {
    out << ", \"selected_fgo_feedback\": \"out_of_scope_for_clean1\"";
  }
  out << "}";
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

// CLEAN1R2R1 only: serialize the active state directly with the exact tag's
// 11/22/13-column writer contract.  This is a format view of the same states
// and covariance matrices; it performs no correction, substitution, or epoch
// filtering.
void FileSaver::writeExactCompatible(
    const std::string& output_dir,
    const std::vector<NavState>& states,
    const std::vector<std::vector<double>>& covariances) {
  ensureOutputDir(output_dir);
  if (states.size() != covariances.size()) {
    throw std::runtime_error("exact-compatible writer state/covariance row mismatch");
  }
  std::ofstream nav(std::filesystem::path(output_dir) / "KF_GINS_Navresult.nav");
  std::ofstream stdfile(std::filesystem::path(output_dir) / "KF_GINS_STD.txt");
  std::ofstream imuerr(std::filesystem::path(output_dir) / "KF_GINS_IMU_ERR.txt");
  if (!nav || !stdfile || !imuerr) {
    throw std::runtime_error("failed to open exact-compatible writer outputs");
  }
  auto write_value = [](std::ostream& out, double value) {
    out << std::left << std::setw(15) << std::fixed << std::setprecision(9) << value << ' ';
  };
  for (std::size_t row = 0; row < states.size(); ++row) {
    const auto& state = states[row];
    for (double value : std::array<double, 11>{
             0.0,
             state.time,
             Earth::radToDeg(state.pos_blh_rad_m[0]),
             Earth::radToDeg(state.pos_blh_rad_m[1]),
             state.pos_blh_rad_m[2],
             state.vel_ned_mps[0],
             state.vel_ned_mps[1],
             state.vel_ned_mps[2],
             Earth::radToDeg(state.euler_rad[0]),
             Earth::radToDeg(state.euler_rad[1]),
             Earth::radToDeg(state.euler_rad[2]),
         }) {
      write_value(nav, value);
    }
    nav << '\n';

    write_value(stdfile, state.time);
    for (std::size_t index = 0; index < kErrorStateSize; ++index) {
      const auto& covariance = covariances[row];
      const std::size_t diagonal_index = covariance.size() == kErrorStateSize
                                             ? index
                                             : index * kErrorStateSize + index;
      const double variance = diagonal_index < covariance.size() ? covariance[diagonal_index] : 0.0;
      write_value(stdfile, std::sqrt(std::max(0.0, variance)) * stdOutputScale(index));
    }
    stdfile << '\n';

    write_value(imuerr, state.time);
    for (double value : state.imu_error.gyrbias) {
      write_value(imuerr, value * R2D * 3600.0);
    }
    for (double value : state.imu_error.accbias) {
      write_value(imuerr, value * 1.0e5);
    }
    for (double value : state.imu_error.gyrscale) {
      write_value(imuerr, value * 1.0e6);
    }
    for (double value : state.imu_error.accscale) {
      write_value(imuerr, value * 1.0e6);
    }
    imuerr << '\n';
  }
}

// 中文说明：RUN_MANIFEST 记录 R2/R3 运行边界和计数；reference 输出不进入 solver。
void FileSaver::writeRunManifest(const std::string& output_dir, const PortOptions& options) {
  ensureOutputDir(output_dir);
  std::ofstream out(std::filesystem::path(output_dir) / "RUN_MANIFEST.json");
  if (!out) {
    throw std::runtime_error("failed to write RUN_MANIFEST");
  }
  out << std::setprecision(17);
  out << "{\n"
      << "  \"schema_version\": \"legsa-v23-port-core-run-manifest-v2\",\n"
      << "  \"clean1_formal_mode\": " << (options.clean1_formal_mode ? "true" : "false") << ",\n"
      << "  \"clean_final_v23_parity_mode\": "
      << (options.clean_final_v23_parity_mode ? "true" : "false") << ",\n"
      << "  \"stage_id\": \"" << escapeJson(options.stage_id) << "\",\n"
      << "  \"protocol_id\": \"" << escapeJson(options.protocol_id) << "\",\n"
      << "  \"case_id\": \"" << escapeJson(options.case_id) << "\",\n"
      << "  \"run_id\": \"" << escapeJson(options.run_id) << "\",\n"
      << "  \"data_mode\": \"" << escapeJson(options.data_mode) << "\",\n"
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
      << "  \"LegSA_output_solver_input\": " << (options.LegSA_output_solver_input ? "true" : "false") << ",\n"
      << "  \"trace_solver_input\": " << (options.trace_solver_input ? "true" : "false") << ",\n"
      << "  \"trace_used_online\": " << (options.trace_solver_input ? "true" : "false") << ",\n"
      << "  \"synthetic_data_used\": " << (options.synthetic_data_used ? "true" : "false") << ",\n"
      << "  \"semisynthetic_data_used\": "
      << (options.semisynthetic_data_used ? "true" : "false") << ",\n"
      << "  \"receiver_imu_as_body_imu\": " << (options.receiver_imu_as_body_imu ? "true" : "false") << ",\n"
      << "  \"per_case_tuning\": " << (options.per_case_tuning ? "true" : "false") << ",\n"
      << "  \"output_only_correction\": " << (options.output_only_correction ? "true" : "false") << ",\n"
      << "  \"bad_epoch_deletion_for_metric\": " << (options.bad_epoch_deletion_for_metric ? "true" : "false") << ",\n"
      << "  \"epoch_deleted_for_metric\": " << (options.bad_epoch_deletion_for_metric ? "true" : "false") << ",\n"
      << "  \"old_runtime_input_count\": " << options.old_runtime_input_count << ",\n"
      << "  \"legacy_provider_input_count\": " << options.legacy_provider_input_count << ",\n"
      << "  \"legacy_row_input_count\": " << options.legacy_row_input_count << ",\n"
      << "  \"legacy_aggregate_input_count\": " << options.legacy_aggregate_input_count << ",\n"
      << "  \"status_fallback_used\": " << (options.status_fallback_used ? "true" : "false") << ",\n"
      << "  \"legacy_provider_used\": " << (options.legacy_provider_used ? "true" : "false") << ",\n"
      << "  \"common_initialization\": " << (options.common_initialization ? "true" : "false") << ",\n"
      << "  \"common_initialization_dual_yaw_used\": "
      << (options.common_initialization_dual_yaw_used ? "true" : "false") << ",\n"
      << "  \"trace_used_for_initialization\": "
      << (options.trace_used_for_initialization ? "true" : "false") << ",\n"
      << "  \"method_specific_initialization\": "
      << (options.method_specific_initialization ? "true" : "false") << ",\n"
      << "  \"common_initialization_source\": \""
      << escapeJson(options.common_initialization_source) << "\",\n"
      << "  \"propagation_imu_source\": \"" << escapeJson(options.propagation_imu_source) << "\",\n"
      << "  \"solver_output_reference_point\": \""
      << escapeJson(options.solver_output_reference_point) << "\",\n"
      << "  \"antlever_m\": [" << options.antlever_m[0] << ", " << options.antlever_m[1] << ", "
      << options.antlever_m[2] << "],\n"
      << "  \"starttime\": " << options.starttime << ",\n"
      << "  \"endtime\": " << options.endtime << ",\n"
      << "  \"imudatalen\": " << options.imudatalen << ",\n"
      << "  \"imudatarate\": " << options.imudatarate << ",\n"
      << "  \"init_position_geodetic_deg_m\": ["
      << options.init_pos_blh_rad_m[0] * R2D << ", "
      << options.init_pos_blh_rad_m[1] * R2D << ", "
      << options.init_pos_blh_rad_m[2] << "],\n"
      << "  \"init_velocity_ned_mps\": ";
  writeVec3Array(out, options.init_vel_ned_mps);
  out << ",\n  \"init_attitude_deg\": ";
  writeVec3Array(out, options.init_att_rad, R2D);
  out << ",\n  \"init_gyro_bias_deg_h\": ";
  writeVec3Array(out, options.init_imu_error.gyrbias, R2D * 3600.0);
  out << ",\n  \"init_accel_bias_mgal\": ";
  writeVec3Array(out, options.init_imu_error.accbias, 1.0e5);
  out << ",\n  \"init_gyro_scale_ppm\": ";
  writeVec3Array(out, options.init_imu_error.gyrscale, 1.0e6);
  out << ",\n  \"init_accel_scale_ppm\": ";
  writeVec3Array(out, options.init_imu_error.accscale, 1.0e6);
  out << ",\n  \"init_position_std_m\": ";
  writeVec3Array(out, options.init_pos_std_m);
  out << ",\n  \"init_velocity_std_mps\": ";
  writeVec3Array(out, options.init_vel_std_mps);
  out << ",\n  \"init_attitude_std_deg\": ";
  writeVec3Array(out, options.init_att_std_rad, R2D);
  out << ",\n  \"init_gyro_bias_std_deg_h\": ";
  writeVec3Array(out, options.init_imu_error_std.gyrbias, R2D * 3600.0);
  out << ",\n  \"init_accel_bias_std_mgal\": ";
  writeVec3Array(out, options.init_imu_error_std.accbias, 1.0e5);
  out << ",\n  \"init_gyro_scale_std_ppm\": ";
  writeVec3Array(out, options.init_imu_error_std.gyrscale, 1.0e6);
  out << ",\n  \"init_accel_scale_std_ppm\": ";
  writeVec3Array(out, options.init_imu_error_std.accscale, 1.0e6);
  out << ",\n  \"angle_random_walk_deg_sqrt_h\": ";
  writeVec3Array(out, options.imunoise.gyr_arw, 60.0 * R2D);
  out << ",\n  \"velocity_random_walk_mps_sqrt_h\": ";
  writeVec3Array(out, options.imunoise.acc_vrw, 60.0);
  out << ",\n  \"gyro_bias_std_deg_h\": ";
  writeVec3Array(out, options.imunoise.gyrbias_std, R2D * 3600.0);
  out << ",\n  \"accel_bias_std_mgal\": ";
  writeVec3Array(out, options.imunoise.accbias_std, 1.0e5);
  out << ",\n  \"gyro_scale_std_ppm\": ";
  writeVec3Array(out, options.imunoise.gyrscale_std, 1.0e6);
  out << ",\n  \"accel_scale_std_ppm\": ";
  writeVec3Array(out, options.imunoise.accscale_std, 1.0e6);
  out << ",\n  \"correlation_time_h\": " << options.imunoise.corr_time / 3600.0
      << ",\n  \"common_initialization_covariance_diagonal_internal\": ";
  writeInitializationCovarianceDiagonal(out, options);
  out << ",\n"
      << "  \"antlever_config_source\": \"" << escapeJson(options.antlever_config_source) << "\",\n"
      << "  \"evaluation_reference_point_match_established\": "
      << (options.evaluation_reference_point_match_established ? "true" : "false") << ",\n"
      << "  \"reference_point_compensation_applied\": "
      << (options.reference_point_compensation_applied ? "true" : "false") << ",\n"
      << "  \"algorithm_id\": \"" << escapeJson(options.algorithm_id) << "\",\n"
      << "  \"measurement_update_order\": \""
      << (options.enable_basic_dual_yaw_baseline
              ? "position_then_basic_yaw_then_feedback"
              : (options.enable_dual_yaw_update
                     ? (options.clean_final_v23_parity_mode
                            ? (options.algorithm_id == "LegSA_Paper_V1"
                                   ? "position_then_yaw_then_receiver_velocity_then_auxiliary_then_feedback"
                                   : "position_then_yaw_then_receiver_velocity_then_feedback")
                            : (options.algorithm_id == "LegSA_Paper_V1"
                                   ? "position_then_receiver_velocity_then_yaw_then_auxiliary_then_feedback"
                                   : "position_then_receiver_velocity_then_yaw_then_feedback"))
                     : "position_then_receiver_velocity_then_feedback"))
      << "\",\n"
      << "  \"ablation_variant\": \"" << escapeJson(options.ablation_variant) << "\",\n"
      << "  \"enable_basic_dual_yaw_baseline\": "
      << (options.enable_basic_dual_yaw_baseline ? "true" : "false") << ",\n"
      << "  \"enable_dual_yaw_update\": " << (options.enable_dual_yaw_update ? "true" : "false") << ",\n"
      << "  \"basic_dual_yaw_fixed_std_deg\": " << options.basic_dual_yaw_fixed_std_deg << ",\n"
      << "  \"yaw_std_min_deg\": " << options.yaw_std_min_deg << ",\n"
      << "  \"yaw_std_soft_deg\": " << options.yaw_std_soft_deg << ",\n"
      << "  \"yaw_std_hard_deg\": " << options.yaw_std_hard_deg << ",\n"
      << "  \"yaw_res_soft_deg\": " << options.yaw_res_soft_deg << ",\n"
      << "  \"yaw_res_hard_deg\": " << options.yaw_res_hard_deg << ",\n"
      << "  \"yaw_downweight_scale\": " << options.yaw_downweight_scale << ",\n"
      << "  \"basic_dual_yaw_residual_sign\": \""
      << escapeJson(options.basic_dual_yaw_residual_sign) << "\",\n"
      << "  \"basic_dual_yaw_H_phi_z\": -1,\n"
      << "  \"disable_source_aware\": " << (options.disable_source_aware ? "true" : "false") << ",\n"
      << "  \"disable_go2\": " << (options.disable_go2 ? "true" : "false") << ",\n"
      << "  \"disable_qm\": " << (options.disable_qm ? "true" : "false") << ",\n"
      << "  \"disable_raw_doppler\": " << (options.disable_raw_doppler ? "true" : "false") << ",\n"
      << "  \"disable_fgo_feedback\": " << (options.disable_fgo_feedback ? "true" : "false") << ",\n"
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
      << "  \"raw_doppler_time_tolerance_sec\": "
      << options.raw_doppler_config.raw_doppler_time_tolerance_sec << ",\n"
      << "  \"raw_doppler_min_sat\": " << options.raw_doppler_config.raw_doppler_min_sat << ",\n"
      << "  \"raw_doppler_residual_gate_mps\": "
      << options.raw_doppler_config.raw_doppler_residual_gate_mps << ",\n"
      << "  \"raw_doppler_mode\": \"" << escapeJson(options.raw_doppler_config.raw_doppler_mode) << "\",\n"
      << "  \"raw_doppler_update_count\": " << options.raw_doppler_status.update_count << ",\n"
      << "  \"raw_doppler_reject_count\": " << options.raw_doppler_status.reject_count << ",\n"
      << "  \"raw_doppler_epoch_count\": " << options.raw_doppler_status.epoch_count << ",\n"
      << "  \"raw_doppler_factor_epoch_count\": " << options.raw_doppler_status.epoch_count << ",\n"
      << "  \"raw_doppler_factor_valid_epoch_count\": " << options.raw_doppler_status.valid_epoch_count << ",\n"
      << "  \"raw_doppler_factor_invalid_epoch_count\": " << options.raw_doppler_status.invalid_epoch_count << ",\n"
      << "  \"raw_doppler_factor_source\": \"" << escapeJson(options.raw_doppler_status.factor_source) << "\",\n"
      << "  \"raw_doppler_backend_lineage_required\": "
      << (options.raw_doppler_config.formal_lineage_required ? "true" : "false") << ",\n"
      << "  \"raw_doppler_backend_lineage_proven\": "
      << (options.raw_doppler_status.lineage_proven ? "true" : "false") << ",\n"
      << "  \"raw_doppler_backend_id\": \""
      << escapeJson(options.raw_doppler_status.backend_id) << "\",\n"
      << "  \"raw_doppler_backend_source_files\": \""
      << escapeJson(options.raw_doppler_config.raw_doppler_backend_source_files) << "\",\n"
      << "  \"raw_doppler_backend_source_hashes\": \""
      << escapeJson(options.raw_doppler_config.raw_doppler_backend_source_hashes) << "\",\n"
      << "  \"helper_executable_hash\": \""
      << escapeJson(options.raw_doppler_config.helper_executable_hash) << "\",\n"
      << "  \"obs_source_hash\": \"" << escapeJson(options.raw_doppler_status.obs_source_hash) << "\",\n"
      << "  \"nav_source_hash\": \"" << escapeJson(options.raw_doppler_status.nav_source_hash) << "\",\n"
      << "  \"conversion_config_hash\": \""
      << escapeJson(options.raw_doppler_status.conversion_config_hash) << "\",\n"
      << "  \"covariance_policy\": \""
      << escapeJson(options.raw_doppler_status.covariance_policy) << "\",\n"
      << "  \"rtklib_position_solution_used_as_solver_input\": "
      << (options.raw_doppler_config.rtklib_position_solution_used_as_solver_input ? "true" : "false") << ",\n"
      << "  \"nav_pvt_velocity_used_as_raw_doppler\": "
      << (options.raw_doppler_config.nav_pvt_velocity_used_as_raw_doppler ? "true" : "false") << ",\n"
      << "  \"gnss_velocity_used_as_raw_doppler\": "
      << (options.raw_doppler_config.gnss_velocity_used_as_raw_doppler ? "true" : "false") << ",\n"
      << "  \"raw_doppler_status_fallback_used\": "
      << (options.raw_doppler_status.status_fallback_used ? "true" : "false") << ",\n"
      << "  \"raw_doppler_legacy_provider_used\": "
      << (options.raw_doppler_status.legacy_provider_used ? "true" : "false") << ",\n"
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
      << "  \"go2_attitude_prior_time_tolerance_sec\": "
      << options.go2_attitude_prior_config.go2_attitude_prior_time_tolerance_sec << ",\n"
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
      << "  \"go2_velocity_prior_time_tolerance_sec\": "
      << options.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_tolerance_sec << ",\n"
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
      << "  \"formal_go2_velocity_prior\": "
      << ((options.clean1_formal_mode &&
           options.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior)
              ? "true"
              : "false")
      << ",\n"
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
      << "  \"go2_position_truth_claim\": false,\n"
      << "  \"go2_yaw_truth_claim\": false,\n"
      << "  \"go2_contact_truth_claim\": false,\n"
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
  out << "  \"actual_solver_input_paths\": ";
  writeActualSolverInputPaths(out, options);
  out << ",\n  \"actual_solver_input_roles\": ";
  writeActualSolverInputRoles(out, options);
  out << ",\n";
  out << "  \"source_aware_weighting_enabled\": "
      << (options.source_aware_policy_config.enable_source_aware_weighting ? "true" : "false") << ",\n"
      << "  \"source_aware_policy_version\": \""
      << escapeJson(options.source_aware_policy_config.source_aware_policy_version) << "\",\n"
      << "  \"source_aware_policy_branch_id\": \""
      << escapeJson(source_aware::SourceAwarePolicy(options.source_aware_policy_config).branchId())
      << "\",\n"
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
  out << ",\n  \"source_aware_source_configs\": ";
  writeSourceAwareSourceConfigs(out, options.source_aware_policy_config);
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
      << "  \"multi_state_qm\": " << (options.multi_state_qm ? "true" : "false") << ",\n"
      << "  \"enable_multi_state_qm\": "
      << (options.quality_state_manager_config.enable_multi_state_qm ? "true" : "false") << ",\n"
      << "  \"multi_state_qm_mode\": \""
      << escapeJson(options.quality_state_manager_config.multi_state_qm_mode) << "\",\n"
      << "  \"multi_state_qm_trace_enabled\": "
      << (options.quality_state_manager_config.multi_state_qm_trace_enabled ? "true" : "false") << ",\n"
      << "  \"multi_state_qm_trace_only\": "
      << (options.quality_state_manager_config.multi_state_qm_trace_only ? "true" : "false") << ",\n"
      << "  \"qm_downweight_threshold\": " << options.quality_state_manager_config.qm_downweight_threshold << ",\n"
      << "  \"qm_reject_threshold\": " << options.quality_state_manager_config.qm_reject_threshold << ",\n"
      << "  \"qm_hold_enter_count\": " << options.quality_state_manager_config.qm_hold_enter_count << ",\n"
      << "  \"qm_hold_length\": " << options.quality_state_manager_config.qm_hold_length << ",\n"
      << "  \"qm_recovery_count\": " << options.quality_state_manager_config.qm_recovery_count << ",\n"
      << "  \"qm_fallback_enter_count\": " << options.quality_state_manager_config.qm_fallback_enter_count << ",\n"
      << "  \"qm_fallback_exit_count\": " << options.quality_state_manager_config.qm_fallback_exit_count << ",\n"
      << "  \"qm_fallback_max_duration\": " << options.quality_state_manager_config.qm_fallback_max_duration << ",\n"
      << "  \"qm_timestamp_gap_hold_sec\": " << options.quality_state_manager_config.qm_timestamp_gap_hold_sec << ",\n"
      << "  \"qm_source_cap\": " << options.quality_state_manager_config.qm_source_cap << ",\n"
      << "  \"qm_global_cap\": " << options.quality_state_manager_config.qm_global_cap << ",\n"
      << "  \"qm_go2_motion_state_influence\": "
      << (options.quality_state_manager_config.qm_go2_motion_state_influence ? "true" : "false") << ",\n"
      << "  \"qm_readiness_influence\": "
      << (options.quality_state_manager_config.qm_readiness_influence ? "true" : "false") << ",\n"
      << "  \"qm_trace_rows\": " << options.quality_state_runtime_stats.trace_row_count << ",\n"
      << "  \"qm_state_transition_count\": " << options.quality_state_runtime_stats.state_transition_count << ",\n"
      << "  \"qm_normal_count_by_source\": ";
  writeSourceAwareCountObject(out, options.quality_state_runtime_stats.normal_count_by_source);
  out << ",\n  \"qm_downweight_count_by_source\": ";
  writeSourceAwareCountObject(out, options.quality_state_runtime_stats.downweight_count_by_source);
  out << ",\n  \"qm_reject_count_by_source\": ";
  writeSourceAwareCountObject(out, options.quality_state_runtime_stats.reject_count_by_source);
  out << ",\n  \"qm_hold_count_by_source\": ";
  writeSourceAwareCountObject(out, options.quality_state_runtime_stats.hold_count_by_source);
  out << ",\n  \"qm_recovery_count_by_source\": ";
  writeSourceAwareCountObject(out, options.quality_state_runtime_stats.recovery_count_by_source);
  out << ",\n  \"qm_fallback_count_by_source\": ";
  writeSourceAwareCountObject(out, options.quality_state_runtime_stats.fallback_count_by_source);
  out << ",\n  \"qm_action_count_by_source\": ";
  writeSourceAwareCountObject(out, options.quality_state_runtime_stats.action_count_by_source);
  out << ",\n"
      << "  \"qm_trace_used_online\": false,\n"
      << "  \"qm_final_v23_output_solver_input\": false,\n"
      << "  \"qm_legsa_output_solver_input\": false,\n"
      << "  \"qm_no_per_case_tuning\": true,\n"
      << "  \"fgo\": " << (options.fgo ? "true" : "false") << ",\n"
      << "  \"selected_fgo_feedback\": "
      << (options.fgo_feedback_config.enable_fgo_feedback ? "true" : "false") << ",\n"
      << "  \"no_feedback_fgo\": " << (options.enable_no_feedback_fgo ? "true" : "false") << ",\n"
      << "  \"active_nine_factor_fgo\": "
      << (options.enable_active_nine_factor_fgo ? "true" : "false") << ",\n"
      << "  \"contact_fk_factor\": " << (options.enable_contact_fk_factor ? "true" : "false") << ",\n"
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
      << "  \"cov_health_fail_count\": " << options.cov_health_fail_count << ",\n"
      << "  \"cov_health_status\": \"" << escapeJson(options.cov_health_status) << "\",\n"
      << "  \"cov_health_first_failure_time\": ";
  if (options.cov_health_fail_count == 0) {
    out << "null";
  } else {
    out << options.cov_health_first_failure_time;
  }
  out << ",\n"
      << "  \"measurement_update_count\": " << options.measurement_update_count << ",\n"
      << "  \"position_update_count\": " << options.position_update_count << ",\n"
      << "  \"velocity_update_count\": " << options.velocity_update_count << ",\n"
      << "  \"yaw_update_count\": " << options.yaw_update_count << ",\n"
      << "  \"dual_yaw_attempt_count\": " << options.yaw_update_count << ",\n"
      << "  \"receiver_velocity_update_count\": " << options.receiver_velocity_update_count << ",\n"
      << "  \"dual_yaw_update_count\": " << options.dual_yaw_update_count << ",\n"
      << "  \"dual_yaw_accepted_count\": " << options.dual_yaw_update_count << ",\n"
      << "  \"source_aware_evaluation_count\": " << options.source_aware_evaluation_count << ",\n"
      << "  \"source_aware_weight_changed_count\": "
      << options.source_aware_weight_changed_count << ",\n"
      << "  \"go2_roll_pitch_update_count\": " << options.go2_roll_pitch_update_count << ",\n"
      << "  \"go2_horizontal_velocity_update_count\": "
      << options.go2_horizontal_velocity_update_count << ",\n"
      << "  \"selected_fgo_feedback_update_count\": "
      << options.selected_fgo_feedback_update_count << ",\n"
      << "  \"nine_factor_fgo_update_count\": " << options.nine_factor_fgo_update_count << ",\n"
      << "  \"qa_fallback_count\": " << options.qa_fallback_count << ",\n"
      << "  \"multi_state_qm_update_count\": " << options.multi_state_qm_update_count << ",\n"
      << "  \"contact_fk_update_count\": " << options.contact_fk_update_count << ",\n"
      << "  \"module_update_counts\": {"
      << "\"position_update_count\": " << options.position_update_count << ", "
      << "\"receiver_velocity_update_count\": " << options.receiver_velocity_update_count << ", "
      << "\"dual_yaw_update_count\": " << options.dual_yaw_update_count << ", "
      << "\"raw_doppler_update_count\": " << options.raw_doppler_status.update_count << ", "
      << "\"source_aware_evaluation_count\": " << options.source_aware_evaluation_count << ", "
      << "\"source_aware_weight_changed_count\": " << options.source_aware_weight_changed_count << ", "
      << "\"go2_roll_pitch_update_count\": " << options.go2_roll_pitch_update_count << ", "
      << "\"go2_horizontal_velocity_update_count\": " << options.go2_horizontal_velocity_update_count << ", "
      << "\"selected_fgo_feedback_update_count\": " << options.selected_fgo_feedback_update_count << ", "
      << "\"nine_factor_fgo_update_count\": " << options.nine_factor_fgo_update_count << ", "
      << "\"qa_fallback_count\": " << options.qa_fallback_count << ", "
      << "\"multi_state_qm_update_count\": " << options.multi_state_qm_update_count << ", "
      << "\"contact_fk_update_count\": " << options.contact_fk_update_count << "},\n"
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
