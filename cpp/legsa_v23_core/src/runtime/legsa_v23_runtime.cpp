#include "legsa_v23_core/runtime/legsa_v23_runtime.hpp"

#include "legsa_v23_core/common/constants.hpp"
#include "legsa_v23_core/config/config_loader.hpp"
#include "legsa_v23_core/io/gnss_file_loader.hpp"
#include "legsa_v23_core/io/imu_file_loader.hpp"
#include "legsa_v23_core/runtime/legsa_v23_engine.hpp"
#include "legsa_v23_core/writers/eval_nav_writer.hpp"
#include "legsa_v23_core/writers/nav_writer.hpp"
#include "legsa_v23_core/writers/run_manifest_writer.hpp"
#include "legsa_v23_core/writers/std_writer.hpp"

#include <array>
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <stdexcept>
#include <string>
#include <vector>

namespace legsa_v23_core {
namespace {

// 中文说明：拼接输出文件名，避免在文档或配置中写入本机绝对路径。
std::string outputPath(const std::string& output_dir, const std::string& filename) {
  return (std::filesystem::path(output_dir) / filename).string();
}

// 中文说明：JSON bool 仅用于诊断文件；诊断文件不作为性能证据。
const char* boolText(bool value) { return value ? "true" : "false"; }

// 中文说明：D2 model variant 只允许在 diagnostic_mode 下启用，用来隔离公式符号/反馈侧的问题。
bool isAllowedDiagnosticModelVariant(const std::string& name) {
  static const std::vector<std::string> allowed = {
      "baseline_current",
      "position_residual_sign_flip",
      "position_H_phi_sign_flip",
      "position_no_H_phi",
      "velocity_residual_sign_flip",
      "yaw_residual_sign_flip",
      "yaw_H_sign_flip",
      "state_feedback_pos_vel_add",
      "state_feedback_phi_negative",
      "state_feedback_phi_right_multiply",
      "state_feedback_no_phi",
      "ekf_update_residual_sign_flip",
  };
  return std::find(allowed.begin(), allowed.end(), name) != allowed.end();
}

// 中文说明：D5 diagnostic modes 只在 debug-output-dir 下允许，防止误作正式结果。
bool isAllowedFeedbackMode(const std::string& name) {
  static const std::vector<std::string> allowed = {
      "normal",
      "no_feedback",
      "pos_vel_only",
      "pos_vel_attitude_only",
      "pos_vel_bias_scale_only",
      "attitude_only",
      "no_attitude_feedback",
      "no_bias_scale_feedback",
      "no_bias_feedback",
      "no_scale_feedback",
      "no_gyrbias_feedback",
      "no_accbias_feedback",
      "no_gyrscale_feedback",
      "no_accscale_feedback",
      "no_imu_error_feedback",
      "freeze_imu_error_states",
      "no_imu_error_feedback_but_keep_attitude",
      "no_attitude_no_bias_scale",
      "delayed_feedback_every_5_updates",
      "dx_phi_clamp_5deg_diagnostic",
      "dx_phi_clamp_1deg_diagnostic",
  };
  return std::find(allowed.begin(), allowed.end(), name) != allowed.end();
}

bool isAllowedUpdateBlockMode(const std::string& name) {
  static const std::vector<std::string> allowed = {
      "all",        "position_only", "velocity_only", "yaw_only", "position_velocity",
      "position_yaw", "velocity_yaw", "no_yaw",        "no_velocity", "no_position",
  };
  return std::find(allowed.begin(), allowed.end(), name) != allowed.end();
}

bool isAllowedCovarianceMode(const std::string& name) {
  static const std::vector<std::string> allowed = {
      "normal",
      "inflate_attitude_10x",
      "inflate_attitude_100x",
      "inflate_measurement_R_10x",
      "inflate_yaw_R_10x",
      "inflate_position_R_10x",
      "inflate_velocity_R_10x",
      "zero_bias_scale_cross_cov",
      "zero_phi_bias_scale_cross_cov",
      "shrink_bias_scale_P_10x",
      "shrink_bias_scale_P_100x",
      "inflate_bias_scale_P_10x",
      "inflate_bias_scale_P_100x",
      "zero_bias_scale_process_noise",
      "inflate_bias_scale_process_noise_10x",
  };
  return std::find(allowed.begin(), allowed.end(), name) != allowed.end();
}

// 中文说明：三维向量范数用于输入流快照，不进入求解器状态。
double norm3(const Vector3& values) {
  double sum = 0.0;
  for (double value : values) {
    sum += value * value;
  }
  return std::sqrt(sum);
}

// 中文说明：写 JSON 三维数组；字段单位由调用处中文注释约定。
void writeVector3Json(std::ofstream& output, const std::string& name, const Vector3& values, bool comma = true) {
  output << "  \"" << name << "\": [" << std::setprecision(16) << values[0] << ", " << values[1] << ", "
         << values[2] << "]";
  if (comma) {
    output << ",";
  }
  output << "\n";
}

// 中文说明：CONFIG_INIT_SNAPSHOT 固化 config parser 后的内部单位，用于排查 deg/rad/height/lever/noise 问题。
void writeConfigInitSnapshot(const std::string& path, const GINSOptions& options) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open CONFIG_INIT_SNAPSHOT output: " + path);
  }
  const Vector3 initpos_deg_m = {options.init_state.pos_blh_rad_m[0] * kRadToDeg,
                                 options.init_state.pos_blh_rad_m[1] * kRadToDeg,
                                 options.init_state.pos_blh_rad_m[2]};
  const Vector3 initatt_deg = {options.init_state.euler_rpy_rad[0] * kRadToDeg,
                               options.init_state.euler_rpy_rad[1] * kRadToDeg,
                               options.init_state.euler_rpy_rad[2] * kRadToDeg};
  const Vector3 initattstd_deg = {options.init_att_std[0] * kRadToDeg, options.init_att_std[1] * kRadToDeg,
                                  options.init_att_std[2] * kRadToDeg};
  output << "{\n";
  writeVector3Json(output, "initpos_deg_m_input", initpos_deg_m);
  writeVector3Json(output, "initpos_rad_m_internal", options.init_state.pos_blh_rad_m);
  writeVector3Json(output, "initvel_mps", options.init_state.vel_ned_mps);
  writeVector3Json(output, "initatt_deg_input", initatt_deg);
  writeVector3Json(output, "initatt_rad_internal", options.init_state.euler_rpy_rad);
  writeVector3Json(output, "initatt_deg_internal_backconverted", initatt_deg);
  writeVector3Json(output, "initposstd_m", options.init_pos_std);
  writeVector3Json(output, "initvelstd_mps", options.init_vel_std);
  writeVector3Json(output, "initattstd_deg", initattstd_deg);
  writeVector3Json(output, "antlever_m", options.antlever);
  writeVector3Json(output, "imunoise_raw_units_if_available", options.imu_noise);
  writeVector3Json(output, "imunoise_internal_units", options.imu_noise);
  output << "  \"starttime\": " << std::setprecision(16) << options.start_time << ",\n";
  output << "  \"endtime\": " << std::setprecision(16) << options.end_time << ",\n";
  output << "  \"imudatalen\": " << options.imu_data_len << ",\n";
  output << "  \"imudatarate\": " << std::setprecision(16) << options.imu_data_rate << ",\n";
  output << "  \"clean_noisy_provenance_label\": \"" << options.clean_input_provenance_label << "\",\n";
  output << "  \"trace_solver_input\": false,\n";
  output << "  \"final_v23_output_substitution\": false,\n";
  output << "  \"output_only_correction\": false,\n";
  output << "  \"bad_epoch_deletion_for_metric\": false,\n";
  output << "  \"numerical_performance_claim\": false\n";
  output << "}\n";
}

// 中文说明：INPUT_STREAM_SNAPSHOT 只记录输入计数和首尾时间，不复制 raw 数据进 git。
void writeInputStreamSnapshot(const std::string& path, const std::vector<IMUData>& imu_samples,
                              const std::vector<GNSSData>& gnss_samples) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open INPUT_STREAM_SNAPSHOT output: " + path);
  }
  output << "{\n";
  output << "  \"imu_row_count\": " << imu_samples.size() << ",\n";
  output << "  \"gnss_row_count\": " << gnss_samples.size() << ",\n";
  output << "  \"first_imu_time\": " << (imu_samples.empty() ? 0.0 : imu_samples.front().time) << ",\n";
  output << "  \"first_imu_dt\": "
         << (imu_samples.size() >= 2 ? (imu_samples[1].time - imu_samples[0].time)
                                     : (imu_samples.empty() ? 0.0 : imu_samples.front().dt))
         << ",\n";
  output << "  \"first_gnss_time\": " << (gnss_samples.empty() ? 0.0 : gnss_samples.front().time) << ",\n";
  output << "  \"last_imu_time\": " << (imu_samples.empty() ? 0.0 : imu_samples.back().time) << ",\n";
  output << "  \"last_gnss_time\": " << (gnss_samples.empty() ? 0.0 : gnss_samples.back().time) << ",\n";
  output << "  \"first_imu_dtheta_norm\": " << (imu_samples.empty() ? 0.0 : norm3(imu_samples.front().dtheta))
         << ",\n";
  output << "  \"first_imu_dvel_norm\": " << (imu_samples.empty() ? 0.0 : norm3(imu_samples.front().dvel))
         << ",\n";
  if (!gnss_samples.empty()) {
    const Vector3 first_blh_deg_m = {gnss_samples.front().blh[0] * kRadToDeg,
                                     gnss_samples.front().blh[1] * kRadToDeg, gnss_samples.front().blh[2]};
    writeVector3Json(output, "first_gnss_blh_deg_m", first_blh_deg_m);
    writeVector3Json(output, "first_gnss_vel", gnss_samples.front().vel);
    output << "  \"first_gnss_yaw_deg\": " << gnss_samples.front().yaw_deg << ",\n";
  } else {
    output << "  \"first_gnss_blh_deg_m\": [0, 0, 0],\n";
    output << "  \"first_gnss_vel\": [0, 0, 0],\n";
    output << "  \"first_gnss_yaw_deg\": 0,\n";
  }
  const bool overlap = !imu_samples.empty() && !gnss_samples.empty() && gnss_samples.front().time <= imu_samples.back().time &&
                       gnss_samples.back().time >= imu_samples.front().time;
  output << "  \"time_overlap_status\": \"" << (overlap ? "overlap" : "no_overlap") << "\",\n";
  output << "  \"trace_solver_input\": false,\n";
  output << "  \"final_v23_output_substitution\": false\n";
  output << "}\n";
}

// 中文说明：写 GNSS 首批更新诊断；残差单位是 NED(m)、NED(m/s)、yaw(deg)。
void writeFirstUpdatesCsv(const std::string& path, const std::vector<DiagnosticUpdateRecord>& records) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open FIRST_UPDATES output: " + path);
  }
  output << "update_index,gnss_time,imu_pre_time,imu_cur_time,isToUpdate_res,"
         << "position_residual_n,position_residual_e,position_residual_d,"
         << "velocity_residual_n,velocity_residual_e,velocity_residual_d,"
         << "yaw_obs_deg,yaw_pred_deg,yaw_residual_deg,yaw_scheme_mode,yaw_effective_std_deg,"
         << "position_update_applied,velocity_update_applied,yaw_update_applied,"
         << "dx_norm_before_feedback,dx_pos_norm,dx_vel_norm,dx_phi_norm_deg,state_feedback_applied\n";
  for (const auto& record : records) {
    output << record.update_index << "," << std::setprecision(16) << record.gnss_time << "," << record.imu_pre_time
           << "," << record.imu_cur_time << "," << record.is_to_update_res << "," << record.position_residual[0]
           << "," << record.position_residual[1] << "," << record.position_residual[2] << ","
           << record.velocity_residual[0] << "," << record.velocity_residual[1] << ","
           << record.velocity_residual[2] << "," << record.yaw_obs_deg << "," << record.yaw_pred_deg << ","
           << record.yaw_residual_deg << "," << record.yaw_scheme_mode << "," << record.yaw_effective_std_deg
           << "," << boolText(record.position_update_applied) << "," << boolText(record.velocity_update_applied)
           << "," << boolText(record.yaw_update_applied) << "," << record.dx_norm_before_feedback << ","
           << record.dx_pos_norm << "," << record.dx_vel_norm << "," << record.dx_phi_norm_deg << ","
           << boolText(record.state_feedback_applied) << "\n";
  }
}

// 中文说明：ALL_UPDATES 是 D4 全量更新轨迹；外部 clean NAV 只能用于离线诊断，不能回灌求解器。
void writeAllUpdatesCsv(const std::string& path, const std::vector<DiagnosticUpdateRecord>& records) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open ALL_UPDATES output: " + path);
  }
  output << "update_index,gnss_time,imu_pre_time,imu_cur_time,isToUpdate_res,"
         << "position_residual_n,position_residual_e,position_residual_d,position_residual_norm,"
         << "velocity_residual_n,velocity_residual_e,velocity_residual_d,velocity_residual_norm,"
         << "yaw_obs_deg,yaw_pred_deg,yaw_residual_deg,yaw_scheme_mode,yaw_effective_std_deg,"
         << "H_pos_phi_norm,H_yaw_phi_value_or_norm,R_pos_diag_n,R_pos_diag_e,R_pos_diag_d,"
         << "R_vel_diag_n,R_vel_diag_e,R_vel_diag_d,R_yaw,K_norm_pos,K_norm_vel,K_norm_yaw,"
         << "dx_norm_before_update,dx_norm_after_update,dx_pos_norm,dx_vel_norm,dx_phi_norm_deg,"
         << "cov_trace_before,cov_trace_after,cov_min_diag_before,cov_min_diag_after,"
         << "position_update_applied,velocity_update_applied,yaw_update_applied,state_feedback_applied\n";
  for (const auto& record : records) {
    output << record.update_index << "," << std::setprecision(16) << record.gnss_time << "," << record.imu_pre_time
           << "," << record.imu_cur_time << "," << record.is_to_update_res << "," << record.position_residual[0]
           << "," << record.position_residual[1] << "," << record.position_residual[2] << ","
           << record.position_residual_norm << "," << record.velocity_residual[0] << ","
           << record.velocity_residual[1] << "," << record.velocity_residual[2] << ","
           << record.velocity_residual_norm << "," << record.yaw_obs_deg << "," << record.yaw_pred_deg << ","
           << record.yaw_residual_deg << "," << record.yaw_scheme_mode << "," << record.yaw_effective_std_deg
           << "," << record.h_pos_phi_norm << "," << record.h_yaw_phi_value_or_norm << ","
           << record.r_pos_diag[0] << "," << record.r_pos_diag[1] << "," << record.r_pos_diag[2] << ","
           << record.r_vel_diag[0] << "," << record.r_vel_diag[1] << "," << record.r_vel_diag[2] << ","
           << record.r_yaw << "," << record.k_norm_pos << "," << record.k_norm_vel << "," << record.k_norm_yaw
           << "," << record.dx_norm_before_update << "," << record.dx_norm_after_update << ","
           << record.dx_pos_norm << "," << record.dx_vel_norm << "," << record.dx_phi_norm_deg << ","
           << record.cov_trace_before << "," << record.cov_trace_after << "," << record.cov_min_diag_before
           << "," << record.cov_min_diag_after << "," << boolText(record.position_update_applied) << ","
           << boolText(record.velocity_update_applied) << "," << boolText(record.yaw_update_applied) << ","
           << boolText(record.state_feedback_applied) << "\n";
  }
}

// 中文说明：D5 update-block CSV 记录每个量测块的 dz/H/R/K/dx/P 变化，只用于诊断。
void writeUpdateBlockTraceCsv(const std::string& path, const std::vector<DiagnosticUpdateBlockRecord>& records) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open UPDATE_BLOCK_TRACE output: " + path);
  }
  output << "update_index,block_type,gnss_time,dz_norm,dz_0,dz_1,dz_2,H_norm,R_trace,S_condition_estimate,"
         << "K_norm,dx_before_norm,dx_after_norm,dx_delta_norm,dx_delta_pos_norm,dx_delta_vel_norm,"
         << "dx_delta_phi_norm_deg,cov_trace_before,cov_trace_after,cov_min_diag_before,cov_min_diag_after,"
         << "accepted,yaw_scheme_mode\n";
  for (const auto& record : records) {
    output << record.update_index << "," << record.block_type << "," << std::setprecision(16) << record.gnss_time
           << "," << record.dz_norm << "," << record.dz_0 << "," << record.dz_1 << "," << record.dz_2 << ","
           << record.H_norm << "," << record.R_trace << "," << record.S_condition_estimate << ","
           << record.K_norm << "," << record.dx_before_norm << "," << record.dx_after_norm << ","
           << record.dx_delta_norm << "," << record.dx_delta_pos_norm << "," << record.dx_delta_vel_norm << ","
           << record.dx_delta_phi_norm_deg << "," << record.cov_trace_before << "," << record.cov_trace_after
           << "," << record.cov_min_diag_before << "," << record.cov_min_diag_after << ","
           << boolText(record.accepted) << "," << record.yaw_scheme_mode << "\n";
  }
}

// 中文说明：D5 feedback delta CSV 记录 stateFeedback 前后状态变化；不能作为 output correction。
void writeFeedbackDeltaTraceCsv(const std::string& path, const std::vector<DiagnosticFeedbackDeltaRecord>& records) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open FEEDBACK_DELTA_TRACE output: " + path);
  }
  output << "update_index,gnss_time,dx_pos_norm_before,dx_vel_norm_before,dx_phi_norm_deg_before,"
         << "pos_delta_ned_norm,vel_delta_norm,phi_delta_deg_norm,roll_before,pitch_before,yaw_before,"
         << "roll_after,pitch_after,yaw_after,roll_delta,pitch_delta,yaw_delta,bias_delta_norm,"
         << "scale_delta_norm,dx_reset_after_feedback\n";
  for (const auto& record : records) {
    output << record.update_index << "," << std::setprecision(16) << record.gnss_time << ","
           << record.dx_pos_norm_before << "," << record.dx_vel_norm_before << ","
           << record.dx_phi_norm_deg_before << "," << record.pos_delta_ned_norm << ","
           << record.vel_delta_norm << "," << record.phi_delta_deg_norm << "," << record.roll_before << ","
           << record.pitch_before << "," << record.yaw_before << "," << record.roll_after << ","
           << record.pitch_after << "," << record.yaw_after << "," << record.roll_delta << ","
           << record.pitch_delta << "," << record.yaw_delta << "," << record.bias_delta_norm << ","
           << record.scale_delta_norm << "," << boolText(record.dx_reset_after_feedback) << "\n";
  }
}

// 中文说明：D5 covariance trace CSV 记录 predict/update/feedback 的协方差分块统计。
void writeCovarianceTraceCsv(const std::string& path, const std::vector<DiagnosticCovarianceRecord>& records) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open COVARIANCE_TRACE output: " + path);
  }
  output << "time,event_type,cov_trace,cov_min_diag,cov_max_diag,P_pos_trace,P_vel_trace,P_phi_trace,"
         << "P_bg_trace,P_ba_trace,K_norm_if_update,dx_phi_norm_deg_if_update\n";
  for (const auto& record : records) {
    output << std::setprecision(16) << record.time << "," << record.event_type << "," << record.cov_trace
           << "," << record.cov_min_diag << "," << record.cov_max_diag << "," << record.P_pos_trace << ","
           << record.P_vel_trace << "," << record.P_phi_trace << "," << record.P_bg_trace << ","
           << record.P_ba_trace << "," << record.K_norm_if_update << "," << record.dx_phi_norm_deg_if_update
           << "\n";
  }
}

// 中文说明：D6 IMU compensation trace 只写 runtime-only 目录，用于发现重复补偿或插值补偿遗漏。
void writeImuCompensationTraceCsv(const std::string& path,
                                  const std::vector<DiagnosticImuCompensationRecord>& records) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open IMU_COMPENSATION_TRACE output: " + path);
  }
  output << "propagation_index,imu_time,imu_dt,dtheta_norm_before,dtheta_norm_after,dvel_norm_before,"
         << "dvel_norm_after,gyrbias_norm,accbias_norm,gyrscale_norm,accscale_norm,compensation_applied,"
         << "compensation_count_for_current_imu,repeated_compensation_detected,imupre_compensated,imucur_compensated\n";
  for (const auto& record : records) {
    output << record.propagation_index << "," << std::setprecision(16) << record.imu_time << ","
           << record.imu_dt << "," << record.dtheta_norm_before << "," << record.dtheta_norm_after << ","
           << record.dvel_norm_before << "," << record.dvel_norm_after << "," << record.gyrbias_norm << ","
           << record.accbias_norm << "," << record.gyrscale_norm << "," << record.accscale_norm << ","
           << boolText(record.compensation_applied) << "," << record.compensation_count_for_current_imu << ","
           << boolText(record.repeated_compensation_detected) << "," << boolText(record.imupre_compensated)
           << "," << boolText(record.imucur_compensated) << "\n";
  }
}

// 中文说明：D6 IMU error feedback trace 只记录 bias/scale 反馈量，不是输出修正。
void writeImuErrorFeedbackTraceCsv(const std::string& path,
                                   const std::vector<DiagnosticImuErrorFeedbackRecord>& records) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open IMU_ERROR_FEEDBACK_TRACE output: " + path);
  }
  output << "update_index,gnss_time,dx_bg_norm,dx_ba_norm,dx_sg_norm,dx_sa_norm,"
         << "gyrbias_norm_before,accbias_norm_before,gyrscale_norm_before,accscale_norm_before,"
         << "gyrbias_norm_after,accbias_norm_after,gyrscale_norm_after,accscale_norm_after,"
         << "bias_scale_feedback_applied,attitude_feedback_applied,pos_vel_feedback_applied\n";
  for (const auto& record : records) {
    output << record.update_index << "," << std::setprecision(16) << record.gnss_time << ","
           << record.dx_bg_norm << "," << record.dx_ba_norm << "," << record.dx_sg_norm << ","
           << record.dx_sa_norm << "," << record.gyrbias_norm_before << "," << record.accbias_norm_before
           << "," << record.gyrscale_norm_before << "," << record.accscale_norm_before << ","
           << record.gyrbias_norm_after << "," << record.accbias_norm_after << ","
           << record.gyrscale_norm_after << "," << record.accscale_norm_after << ","
           << boolText(record.bias_scale_feedback_applied) << "," << boolText(record.attitude_feedback_applied)
           << "," << boolText(record.pos_vel_feedback_applied) << "\n";
  }
}

// 中文说明：D6 cross-covariance trace 记录姿态和 IMU 误差状态耦合强度，不能回灌求解器。
void writeCrossCovarianceTraceCsv(const std::string& path,
                                  const std::vector<DiagnosticCrossCovarianceRecord>& records) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open CROSS_COVARIANCE_TRACE output: " + path);
  }
  output << "time,event_type,P_phi_trace,P_bg_trace,P_ba_trace,P_sg_trace,P_sa_trace,"
         << "P_phi_bg_norm,P_phi_ba_norm,P_phi_sg_norm,P_phi_sa_norm,P_pos_phi_norm,P_vel_phi_norm,"
         << "P_pos_ba_norm,P_vel_ba_norm\n";
  for (const auto& record : records) {
    output << std::setprecision(16) << record.time << "," << record.event_type << ","
           << record.P_phi_trace << "," << record.P_bg_trace << "," << record.P_ba_trace << ","
           << record.P_sg_trace << "," << record.P_sa_trace << "," << record.P_phi_bg_norm << ","
           << record.P_phi_ba_norm << "," << record.P_phi_sg_norm << "," << record.P_phi_sa_norm << ","
           << record.P_pos_phi_norm << "," << record.P_vel_phi_norm << "," << record.P_pos_ba_norm << ","
           << record.P_vel_ba_norm << "\n";
  }
}

// 中文说明：D6 unit snapshot 记录当前内部 IMU 噪声/协方差单位线索；缺字段保留 evidence_missing。
void writeImuErrorUnitSnapshot(const std::string& path, const GINSOptions& options, const FilterState& state) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open IMU_ERROR_UNIT_SNAPSHOT output: " + path);
  }
  output << "{\n";
  output << "  \"initbgstd_internal\": " << std::sqrt(matrix21At(state.covariance, BG_ID, BG_ID)) << ",\n";
  output << "  \"initbastd_internal\": " << std::sqrt(matrix21At(state.covariance, BA_ID, BA_ID)) << ",\n";
  output << "  \"initsgstd_internal\": " << std::sqrt(matrix21At(state.covariance, SG_ID, SG_ID)) << ",\n";
  output << "  \"initsastd_internal\": " << std::sqrt(matrix21At(state.covariance, SA_ID, SA_ID)) << ",\n";
  output << "  \"gyr_arw_internal\": 1e-8,\n";
  output << "  \"acc_vrw_internal\": 1e-6,\n";
  output << "  \"gyrbias_std_internal\": 1e-12,\n";
  output << "  \"accbias_std_internal\": 1e-10,\n";
  output << "  \"gyrscale_std_internal\": 1e-14,\n";
  output << "  \"accscale_std_internal\": 1e-14,\n";
  output << "  \"corr_time_internal\": \"evidence_missing_fixed_internal_default\",\n";
  output << "  \"unit_conversion_policy\": \"D6_audit_current_internal_defaults_no_external_source_compiled\",\n";
  output << "  \"source_backed_by_kfgins\": true,\n";
  output << "  \"diagnostic_only\": true,\n";
  output << "  \"trace_solver_input\": false,\n";
  output << "  \"final_v23_output_substitution\": false,\n";
  output << "  \"output_only_correction\": false,\n";
  output << "  \"bad_epoch_deletion_for_metric\": false,\n";
  output << "  \"numerical_performance_claim\": false,\n";
  output << "  \"diagnostic_covariance_mode\": \"" << options.diagnostic_covariance_mode << "\"\n";
  output << "}\n";
}

// 中文说明：写首批传播诊断；姿态输出为 deg，便于和 reference/EVAL_NAV 对照。
void writeFirstPropagationsCsv(const std::string& path, const std::vector<DiagnosticPropagationRecord>& records) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open FIRST_PROPAGATIONS output: " + path);
  }
  output << "propagation_index,time_pre,time_cur,dt,pos_lat_deg,pos_lon_deg,height_m,vel_n,vel_e,vel_d,"
         << "roll_deg,pitch_deg,yaw_deg,dtheta_norm,dvel_norm,cov_trace,cov_min_diag,cov_max_diag\n";
  for (const auto& record : records) {
    output << record.propagation_index << "," << std::setprecision(16) << record.time_pre << ","
           << record.time_cur << "," << record.dt << "," << record.nav_state.pos_blh_rad_m[0] * kRadToDeg
           << "," << record.nav_state.pos_blh_rad_m[1] * kRadToDeg << "," << record.nav_state.pos_blh_rad_m[2]
           << "," << record.nav_state.vel_ned_mps[0] << "," << record.nav_state.vel_ned_mps[1] << ","
           << record.nav_state.vel_ned_mps[2] << "," << record.nav_state.euler_rpy_rad[0] * kRadToDeg << ","
           << record.nav_state.euler_rpy_rad[1] * kRadToDeg << ","
           << record.nav_state.euler_rpy_rad[2] * kRadToDeg << "," << record.dtheta_norm << ","
           << record.dvel_norm << "," << record.cov_trace << "," << record.cov_min_diag << ","
           << record.cov_max_diag << "\n";
  }
}

// 中文说明：STATE_TRACE_1HZ 是稀疏状态轨迹，便于定位发散时间；不做 output-only correction。
void writeStateTraceHeader(std::ofstream& output) {
  output << "time,pos_lat_deg,pos_lon_deg,height_m,vel_n,vel_e,vel_d,roll_deg,pitch_deg,yaw_deg,cov_trace,"
         << "propagation_count,measurement_update_count,position_update_count,velocity_update_count,yaw_update_count\n";
}

// 中文说明：D4 全量/稀疏状态轨迹字段贴合外部 trace parity，不进入 solver 输入。
void writeAllStateTraceHeader(std::ofstream& output) {
  output << "time,pos_lat_deg,pos_lon_deg,height_m,vel_n,vel_e,vel_d,roll_deg,pitch_deg,yaw_deg,cov_trace,"
         << "cov_min_diag,update_count,yaw_reject_count\n";
}

void writeStateTraceRow(std::ofstream& output, double time, const NavState& nav, const FilterState& filter,
                        const GINSOptions& options) {
  double cov_trace = 0.0;
  for (std::size_t i = 0; i < kStateSize; ++i) {
    cov_trace += matrix21At(filter.covariance, i, i);
  }
  output << std::setprecision(16) << time << "," << nav.pos_blh_rad_m[0] * kRadToDeg << ","
         << nav.pos_blh_rad_m[1] * kRadToDeg << "," << nav.pos_blh_rad_m[2] << "," << nav.vel_ned_mps[0]
         << "," << nav.vel_ned_mps[1] << "," << nav.vel_ned_mps[2] << ","
         << nav.euler_rpy_rad[0] * kRadToDeg << "," << nav.euler_rpy_rad[1] * kRadToDeg << ","
         << nav.euler_rpy_rad[2] * kRadToDeg << "," << cov_trace << "," << options.propagation_count << ","
         << options.measurement_update_count << "," << options.position_update_count << ","
         << options.velocity_update_count << "," << options.yaw_update_count << "\n";
}

void writeAllStateTraceRow(std::ofstream& output, double time, const NavState& nav, const FilterState& filter,
                           const GINSOptions& options) {
  double cov_trace = 0.0;
  double cov_min_diag = matrix21At(filter.covariance, 0, 0);
  for (std::size_t i = 0; i < kStateSize; ++i) {
    const double value = matrix21At(filter.covariance, i, i);
    cov_trace += value;
    cov_min_diag = std::min(cov_min_diag, value);
  }
  output << std::setprecision(16) << time << "," << nav.pos_blh_rad_m[0] * kRadToDeg << ","
         << nav.pos_blh_rad_m[1] * kRadToDeg << "," << nav.pos_blh_rad_m[2] << "," << nav.vel_ned_mps[0]
         << "," << nav.vel_ned_mps[1] << "," << nav.vel_ned_mps[2] << ","
         << nav.euler_rpy_rad[0] * kRadToDeg << "," << nav.euler_rpy_rad[1] * kRadToDeg << ","
         << nav.euler_rpy_rad[2] * kRadToDeg << "," << cov_trace << "," << cov_min_diag << ","
         << options.measurement_update_count << "," << options.yaw_reject_count << "\n";
}

// 中文说明：FIRST_DIVERGENCE_MARKERS 只给诊断定位初次异常时间，不能作为调参输入。
void writeFirstDivergenceMarkers(const std::string& path, const std::vector<DiagnosticUpdateRecord>& updates,
                                 const std::vector<DiagnosticPropagationRecord>& propagations) {
  double first_update_time = updates.empty() ? 0.0 : updates.front().gnss_time;
  double first_yaw_reject_time = 0.0;
  double first_cov_warning_time = 0.0;
  double first_attitude_large_time = 0.0;
  double first_position_large_time = 0.0;
  double first_velocity_large_time = 0.0;
  for (const auto& update : updates) {
    if (first_yaw_reject_time == 0.0 && update.yaw_scheme_mode == "REJECT") {
      first_yaw_reject_time = update.gnss_time;
    }
    if (first_cov_warning_time == 0.0 && update.cov_min_diag_after < 0.0) {
      first_cov_warning_time = update.gnss_time;
    }
  }
  for (const auto& propagation : propagations) {
    const double roll = std::abs(propagation.nav_state.euler_rpy_rad[0] * kRadToDeg);
    const double pitch = std::abs(propagation.nav_state.euler_rpy_rad[1] * kRadToDeg);
    const double velocity_norm = norm3(propagation.nav_state.vel_ned_mps);
    if (first_attitude_large_time == 0.0 && std::max(roll, pitch) > 5.0) {
      first_attitude_large_time = propagation.time_cur;
    }
    if (first_position_large_time == 0.0 && std::abs(propagation.nav_state.pos_blh_rad_m[2]) > 1000.0) {
      first_position_large_time = propagation.time_cur;
    }
    if (first_velocity_large_time == 0.0 && velocity_norm > 20.0) {
      first_velocity_large_time = propagation.time_cur;
    }
  }
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open FIRST_DIVERGENCE_MARKERS output: " + path);
  }
  output << "{\n";
  output << "  \"first_update_time\": " << std::setprecision(16) << first_update_time << ",\n";
  output << "  \"first_yaw_reject_time\": " << first_yaw_reject_time << ",\n";
  output << "  \"first_cov_warning_time\": " << first_cov_warning_time << ",\n";
  output << "  \"first_attitude_large_time\": " << first_attitude_large_time << ",\n";
  output << "  \"first_position_large_time\": " << first_position_large_time << ",\n";
  output << "  \"first_velocity_large_time\": " << first_velocity_large_time << ",\n";
  output << "  \"trace_solver_input\": false,\n";
  output << "  \"numerical_performance_claim\": false\n";
  output << "}\n";
}

// 中文说明：runtime loop trace 用于核对 GNSS 行是否被看到/应用；不会读取 external trace 做求解器输入。
void writeRuntimeLoopParityTrace(const std::string& path, const GINSOptions& options,
                                 const std::vector<IMUData>& imu_samples, const std::vector<GNSSData>& gnss_samples,
                                 const std::vector<DiagnosticUpdateRecord>& updates) {
  std::array<int, 4> res_counts{0, 0, 0, 0};
  for (const auto& record : updates) {
    if (record.is_to_update_res >= 0 && record.is_to_update_res < static_cast<int>(res_counts.size())) {
      ++res_counts[static_cast<std::size_t>(record.is_to_update_res)];
    }
  }
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open RUNTIME_LOOP_PARITY_TRACE output: " + path);
  }
  output << "{\n";
  output << "  \"imu_rows_processed\": " << options.propagation_count + 1 << ",\n";
  output << "  \"gnss_rows_seen\": " << gnss_samples.size() << ",\n";
  output << "  \"gnss_updates_applied\": " << options.measurement_update_count << ",\n";
  output << "  \"gnss_rows_missed\": "
         << (gnss_samples.size() > static_cast<std::size_t>(options.measurement_update_count)
                 ? gnss_samples.size() - static_cast<std::size_t>(options.measurement_update_count)
                 : 0)
         << ",\n";
  output << "  \"res_counts\": {\"0\": " << res_counts[0] << ", \"1\": " << res_counts[1] << ", \"2\": "
         << res_counts[2] << ", \"3\": " << res_counts[3] << "},\n";
  output << "  \"time_align_tolerance\": 0.005,\n";
  output << "  \"starttime\": " << std::setprecision(16) << options.start_time << ",\n";
  output << "  \"endtime\": " << options.end_time << ",\n";
  output << "  \"first_imu_time\": " << (imu_samples.empty() ? 0.0 : imu_samples.front().time) << ",\n";
  output << "  \"first_gnss_time\": " << (gnss_samples.empty() ? 0.0 : gnss_samples.front().time) << ",\n";
  output << "  \"last_imu_time\": " << (imu_samples.empty() ? 0.0 : imu_samples.back().time) << ",\n";
  output << "  \"last_gnss_time\": " << (gnss_samples.empty() ? 0.0 : gnss_samples.back().time) << ",\n";
  output << "  \"trace_solver_input\": false,\n";
  output << "  \"shadow_external_nav_solver_input\": false\n";
  output << "}\n";
}

// 中文说明：RUNTIME_DEBUG_MANIFEST 明确诊断开关和 forbidden flags，防止 isolation 被误写成性能结果。
void writeRuntimeDebugManifest(const std::string& path, const GINSOptions& options) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open RUNTIME_DEBUG_MANIFEST output: " + path);
  }
  output << "{\n";
  output << "  \"phase\": \"" << options.phase << "\",\n";
  output << "  \"diagnostic_mode\": " << boolText(options.diagnostic_mode) << ",\n";
  output << "  \"diagnostic_run_label\": \"" << options.diagnostic_run_label << "\",\n";
  output << "  \"diagnostic_model_variant\": \"" << options.diagnostic_model_variant << "\",\n";
  output << "  \"diagnostic_only\": " << boolText(options.diagnostic_only) << ",\n";
  output << "  \"solver_output_changed_by_diagnostic_switches\": "
         << boolText(options.solver_output_changed_by_diagnostic_switches) << ",\n";
  output << "  \"solver_output_changed_by_diagnostic_variant\": "
         << boolText(options.solver_output_changed_by_diagnostic_variant) << ",\n";
  output << "  \"not_for_performance_claim\": true,\n";
  output << "  \"debug_full_update_trace\": " << boolText(options.debug_full_update_trace) << ",\n";
  output << "  \"debug_full_state_trace\": " << boolText(options.debug_full_state_trace) << ",\n";
  output << "  \"debug_measurement_matrix_trace\": " << boolText(options.debug_measurement_matrix_trace) << ",\n";
  output << "  \"debug_gain_trace\": " << boolText(options.debug_gain_trace) << ",\n";
  output << "  \"debug_update_blocks\": " << boolText(options.debug_update_blocks) << ",\n";
  output << "  \"debug_feedback_delta\": " << boolText(options.debug_feedback_delta) << ",\n";
  output << "  \"debug_covariance_gain\": " << boolText(options.debug_covariance_gain) << ",\n";
  output << "  \"debug_imu_error_feedback\": " << boolText(options.debug_imu_error_feedback) << ",\n";
  output << "  \"debug_imu_compensation\": " << boolText(options.debug_imu_compensation) << ",\n";
  output << "  \"debug_cross_covariance\": " << boolText(options.debug_cross_covariance) << ",\n";
  output << "  \"diagnostic_feedback_mode\": \"" << options.diagnostic_feedback_mode << "\",\n";
  output << "  \"diagnostic_update_block_mode\": \"" << options.diagnostic_update_block_mode << "\",\n";
  output << "  \"diagnostic_covariance_mode\": \"" << options.diagnostic_covariance_mode << "\",\n";
  output << "  \"trace_solver_input\": false,\n";
  output << "  \"final_v23_output_substitution\": false,\n";
  output << "  \"shadow_external_nav_solver_input\": false,\n";
  output << "  \"output_only_correction\": false,\n";
  output << "  \"bad_epoch_deletion_for_metric\": false,\n";
  output << "  \"numerical_performance_claim\": false,\n";
  output << "  \"raw_doppler\": false,\n";
  output << "  \"go2_prior\": false,\n";
  output << "  \"lsim_oim\": false,\n";
  output << "  \"fgo\": false\n";
  output << "}\n";
}

}  // namespace

// 中文说明：toy dry-run 只验证 reader-engine-writer 风格链路，不代表导航性能。
void LegSAV23Runtime::runDryToy(const std::string& output_dir) {
  GINSOptions options;
  options.output_path = output_dir;
  options.start_time = 0.0;
  options.end_time = 0.02;
  options.imu_data_rate = 100.0;
  options.clean_input_provenance_label = "toy_skeleton_no_real_data";
  options.init_state.pos_blh_rad_m = {31.0 * kDegToRad, 121.0 * kDegToRad, 10.0};
  options.init_state.vel_ned_mps = {0.0, 0.0, 0.0};
  options.init_state.euler_rpy_rad = {0.0, 0.0, 10.0 * kDegToRad};

  LegSAV23Engine engine(options);
  engine.initialize();

  IMUData imu0;
  imu0.time = 0.0;
  IMUData imu1;
  imu1.time = 0.01;
  imu1.dt = 0.01;

  GNSSData gnss;
  gnss.time = 0.005;
  gnss.blh = options.init_state.pos_blh_rad_m;
  gnss.std = {1.0, 1.0, 1.5};
  gnss.vel = options.init_state.vel_ned_mps;
  gnss.vel_std = {0.1, 0.1, 0.2};
  gnss.yaw_deg = 10.0;
  gnss.yaw_std_deg = 1.5;
  gnss.has_velocity = true;
  gnss.has_yaw = true;
  gnss.isvalid = true;

  engine.addImuData(imu0);
  engine.addImuData(imu1);
  engine.addGnssData(gnss);
  engine.newImuProcess();

  writeOutputs(output_dir, engine.getRunOptions(), engine.timestamp(), engine.getNavState(), engine.getFilterState());
}

// 中文说明：propagation toy 构造 200 条 IMU increment，只验证预测传播，不做量测更新或性能声明。
void LegSAV23Runtime::runDryPropagationToy(const std::string& output_dir) {
  GINSOptions options;
  options.output_path = output_dir;
  options.phase = "N4H4B";
  options.solver_role = "legsa_v23_core_propagation_foundation";
  options.mechanization_predict_implemented = true;
  options.measurement_update_implemented = false;
  options.state_feedback_implemented = false;
  options.start_time = 0.0;
  options.end_time = 2.0;
  options.imu_data_rate = 100.0;
  options.clean_input_provenance_label = "toy_propagation_no_real_data";
  options.init_state.pos_blh_rad_m = {31.0 * kDegToRad, 121.0 * kDegToRad, 10.0};
  options.init_state.vel_ned_mps = {0.0, 0.0, 0.0};
  options.init_state.euler_rpy_rad = {0.0, 0.0, 10.0 * kDegToRad};
  options.init_pos_std = {1.0, 1.0, 1.5};
  options.init_vel_std = {0.1, 0.1, 0.2};
  options.init_att_std = {0.5 * kDegToRad, 0.5 * kDegToRad, 1.0 * kDegToRad};

  LegSAV23Engine engine(options);
  engine.initialize();

  IMUData previous;
  previous.time = 0.0;
  previous.dt = 0.01;
  previous.dvel = {0.0, 0.0, -9.80665 * previous.dt};
  engine.addImuData(previous);
  for (int i = 1; i <= 200; ++i) {
    IMUData current;
    current.time = static_cast<double>(i) * 0.01;
    current.dt = 0.01;
    current.dtheta = {0.0, 0.0, 0.00005};
    current.dvel = {0.001, 0.0, -9.80665 * current.dt};
    engine.addImuData(current, true);
    engine.newImuProcess();
    previous = current;
  }

  writeOutputs(output_dir, engine.getRunOptions(), engine.timestamp(), engine.getNavState(), engine.getFilterState());
}

// 中文说明：update toy 触发 GNSS position/velocity/yaw 量测更新、EKFUpdate 和 stateFeedback；不代表真实性能。
void LegSAV23Runtime::runDryUpdateToy(const std::string& output_dir) {
  GINSOptions options;
  options.output_path = output_dir;
  options.phase = "N4H4C";
  options.solver_role = "legsa_v23_core_update_feedback_foundation";
  options.mechanization_predict_implemented = true;
  options.measurement_update_implemented = true;
  options.state_feedback_implemented = true;
  options.position_update_implemented = true;
  options.velocity_update_implemented = true;
  options.yaw_update_implemented = true;
  options.velocity_lever_correction = false;
  options.yaw_H_mapping_conservative = true;
  options.yaw_residual_sign = "evidence_missing_default_obs_pred";
  options.start_time = 0.0;
  options.end_time = 0.05;
  options.imu_data_rate = 100.0;
  options.clean_input_provenance_label = "toy_update_no_real_data";
  options.init_state.pos_blh_rad_m = {31.0 * kDegToRad, 121.0 * kDegToRad, 10.0};
  options.init_state.vel_ned_mps = {0.0, 0.0, 0.0};
  options.init_state.euler_rpy_rad = {0.0, 0.0, 10.0 * kDegToRad};
  options.init_pos_std = {1.0, 1.0, 1.5};
  options.init_vel_std = {0.2, 0.2, 0.3};
  options.init_att_std = {0.5 * kDegToRad, 0.5 * kDegToRad, 1.0 * kDegToRad};

  LegSAV23Engine engine(options);
  engine.initialize();

  for (int i = 0; i <= 5; ++i) {
    IMUData imu;
    imu.time = static_cast<double>(i) * 0.01;
    imu.dt = 0.01;
    imu.dtheta = {0.0, 0.0, 0.0};
    imu.dvel = {0.0, 0.0, -9.80665 * imu.dt};
    engine.addImuData(imu, true);
  }

  const Vector3 base_blh = options.init_state.pos_blh_rad_m;
  const Vector3 base_vel = options.init_state.vel_ned_mps;
  const double yaw_values[3] = {10.5, 18.0, 40.0};
  const double gnss_times[3] = {0.005, 0.015, 0.025};
  for (std::size_t i = 0; i < 3; ++i) {
    GNSSData gnss;
    gnss.time = gnss_times[i];
    gnss.blh = base_blh;
    gnss.std = {1.0, 1.0, 1.5};
    gnss.vel = base_vel;
    gnss.vel_std = {0.1, 0.1, 0.2};
    gnss.yaw_deg = yaw_values[i];
    gnss.yaw_std_deg = 1.5;
    gnss.has_velocity = true;
    gnss.has_yaw = true;
    gnss.isvalid = true;
    engine.addGnssData(gnss);
  }

  engine.newImuProcess();
  writeOutputs(output_dir, engine.getRunOptions(), engine.timestamp(), engine.getNavState(), engine.getFilterState());
}

// 中文说明：真实配置运行目前只读 process_data-compatible 输入并生成 skeleton 输出，不做 parity claim。
void LegSAV23Runtime::runFromConfig(const std::string& config_path, const std::string& output_dir_override,
                                    const RuntimeDiagnosticOptions& diagnostic_options) {
  GINSOptions options = ConfigLoader::load(config_path);
  if (!output_dir_override.empty()) {
    options.output_path = output_dir_override;
  }
  options.phase = "N4H4D";
  options.solver_role = "legsa_v23_core_clean_replay_gap_screen";
  options.mechanization_predict_implemented = true;
  options.measurement_update_implemented = true;
  options.state_feedback_implemented = true;
  options.position_update_implemented = true;
  options.velocity_update_implemented = true;
  options.yaw_update_implemented = true;
  options.velocity_lever_correction = false;
  options.yaw_H_mapping_conservative = true;
  options.yaw_residual_sign = "evidence_missing_default_obs_pred";
  if (!diagnostic_options.debug_output_dir.empty()) {
    options.diagnostic_mode = true;
    options.diagnostic_debug_max_updates = diagnostic_options.debug_max_updates;
    options.diagnostic_debug_max_rows = diagnostic_options.debug_max_rows;
    options.debug_full_update_trace = diagnostic_options.debug_full_update_trace;
    options.debug_full_state_trace = diagnostic_options.debug_full_state_trace;
    options.debug_measurement_matrix_trace = diagnostic_options.debug_measurement_matrix_trace;
    options.debug_gain_trace = diagnostic_options.debug_gain_trace;
    options.debug_update_blocks = diagnostic_options.debug_update_blocks;
    options.debug_feedback_delta = diagnostic_options.debug_feedback_delta;
    options.debug_covariance_gain = diagnostic_options.debug_covariance_gain;
    options.debug_imu_error_feedback = diagnostic_options.debug_imu_error_feedback;
    options.debug_imu_compensation = diagnostic_options.debug_imu_compensation;
    options.debug_cross_covariance = diagnostic_options.debug_cross_covariance;
    options.disable_position_update = diagnostic_options.disable_position_update;
    options.disable_velocity_update = diagnostic_options.disable_velocity_update;
    options.disable_yaw_update = diagnostic_options.disable_yaw_update;
    options.disable_measurement_update = diagnostic_options.disable_measurement_update;
    options.disable_state_feedback = diagnostic_options.disable_state_feedback;
    options.diagnostic_run_label = diagnostic_options.diagnostic_run_label;
    options.diagnostic_model_variant = diagnostic_options.diagnostic_model_variant.empty()
                                           ? "baseline_current"
                                           : diagnostic_options.diagnostic_model_variant;
    options.diagnostic_feedback_mode =
        diagnostic_options.diagnostic_feedback_mode.empty() ? "normal" : diagnostic_options.diagnostic_feedback_mode;
    options.diagnostic_update_block_mode = diagnostic_options.diagnostic_update_block_mode.empty()
                                               ? "all"
                                               : diagnostic_options.diagnostic_update_block_mode;
    options.diagnostic_covariance_mode = diagnostic_options.diagnostic_covariance_mode.empty()
                                             ? "normal"
                                             : diagnostic_options.diagnostic_covariance_mode;
    if (!isAllowedDiagnosticModelVariant(options.diagnostic_model_variant)) {
      throw std::runtime_error("unknown D2 diagnostic model variant: " + options.diagnostic_model_variant);
    }
    if (!isAllowedFeedbackMode(options.diagnostic_feedback_mode)) {
      throw std::runtime_error("unknown D5/D6 diagnostic feedback mode: " + options.diagnostic_feedback_mode);
    }
    if (!isAllowedUpdateBlockMode(options.diagnostic_update_block_mode)) {
      throw std::runtime_error("unknown D5 diagnostic update block mode: " + options.diagnostic_update_block_mode);
    }
    if (!isAllowedCovarianceMode(options.diagnostic_covariance_mode)) {
      throw std::runtime_error("unknown D5/D6 diagnostic covariance mode: " + options.diagnostic_covariance_mode);
    }
    options.not_for_performance_claim = true;
    options.diagnostic_only = true;
    options.solver_output_changed_by_diagnostic_switches =
        diagnostic_options.disable_position_update || diagnostic_options.disable_velocity_update ||
        diagnostic_options.disable_yaw_update || diagnostic_options.disable_measurement_update ||
        diagnostic_options.disable_state_feedback;
    options.solver_output_changed_by_diagnostic_variant =
        options.diagnostic_model_variant != "baseline_current" || options.diagnostic_feedback_mode != "normal" ||
        options.diagnostic_update_block_mode != "all" || options.diagnostic_covariance_mode != "normal";
  } else if (!diagnostic_options.diagnostic_model_variant.empty() &&
             diagnostic_options.diagnostic_model_variant != "baseline_current") {
    throw std::runtime_error("D2 diagnostic model variants require --debug-output-dir diagnostic mode");
  }
  if (options.clean_input_provenance_label == "evidence_missing") {
    options.clean_input_provenance_label = "clean_status_yaw_runtime_input";
  }
  const auto imu_samples = IMUFileLoader::load(options.imu_path);
  const auto gnss_samples = GNSSFileLoader::load(options.gnss_path);
  if (imu_samples.size() < 2) {
    throw std::runtime_error("N4H4D runtime requires at least two IMU samples");
  }

  if (options.diagnostic_mode) {
    std::filesystem::create_directories(diagnostic_options.debug_output_dir);
  }
  LegSAV23Engine engine(options);
  engine.initialize();
  std::filesystem::create_directories(options.output_path);
  NavWriter nav_writer(outputPath(options.output_path, "LegSA_V23_NAV.nav"));
  StdWriter std_writer(outputPath(options.output_path, "LegSA_V23_STD.csv"));
  EvalNavWriter eval_writer(outputPath(options.output_path, "EVAL_NAV.csv"));
  std::ofstream state_trace;
  std::ofstream all_state_trace;
  double next_state_trace_time = options.start_time;
  if (options.diagnostic_mode) {
    state_trace.open(outputPath(diagnostic_options.debug_output_dir, "STATE_TRACE_1HZ.csv"));
    if (!state_trace) {
      throw std::runtime_error("failed to open STATE_TRACE_1HZ output");
    }
    writeStateTraceHeader(state_trace);
    if (options.debug_full_state_trace) {
      all_state_trace.open(outputPath(diagnostic_options.debug_output_dir, "ALL_STATES_1HZ.csv"));
      if (!all_state_trace) {
        throw std::runtime_error("failed to open ALL_STATES_1HZ output");
      }
      writeAllStateTraceHeader(all_state_trace);
    }
  }

  std::size_t imu_index = 0;
  while (imu_index < imu_samples.size() && imu_samples[imu_index].time < options.start_time) {
    ++imu_index;
  }
  if (imu_index >= imu_samples.size()) {
    throw std::runtime_error("N4H4D runtime starttime is after all IMU samples");
  }

  std::size_t gnss_index = 0;
  while (gnss_index < gnss_samples.size() && gnss_samples[gnss_index].time < options.start_time) {
    ++gnss_index;
  }

  // 中文说明：KF-GINS-style 主循环先对齐 start time，再加入第一帧 IMU；trace 不进入 solver。
  engine.addImuData(imu_samples[imu_index], true);
  const double end_time = options.end_time > options.start_time ? options.end_time : imu_samples.back().time;
  for (++imu_index; imu_index < imu_samples.size(); ++imu_index) {
    const IMUData& imu = imu_samples[imu_index];
    if (imu.time > end_time) {
      break;
    }

    // 中文说明：把不晚于当前 IMU 的 GNSS 高层状态送入 buffer；它是 15 列 .gnss，不是 raw/trace。
    while (gnss_index < gnss_samples.size() && gnss_samples[gnss_index].time <= imu.time) {
      engine.addGnssData(gnss_samples[gnss_index]);
      ++gnss_index;
    }

    // 中文说明：IMU 输入为 process_data-compatible 增量，补偿后进入 newImuProcess 主循环。
    engine.addImuData(imu, true);
    engine.newImuProcess();

    // 中文说明：每个传播后的状态都写 NAV/STD/EVAL_NAV；不做 output-only correction。
    nav_writer.write(engine.timestamp(), engine.getNavState());
    std_writer.write(engine.timestamp(), engine.getFilterState());
    eval_writer.write(engine.timestamp(), engine.getNavState());
    if (options.diagnostic_mode && engine.timestamp() + 1.0e-9 >= next_state_trace_time) {
      writeStateTraceRow(state_trace, engine.timestamp(), engine.getNavState(), engine.getFilterState(),
                         engine.getRunOptions());
      if (options.debug_full_state_trace) {
        writeAllStateTraceRow(all_state_trace, engine.timestamp(), engine.getNavState(), engine.getFilterState(),
                              engine.getRunOptions());
      }
      while (next_state_trace_time <= engine.timestamp() + 1.0e-9) {
        next_state_trace_time += 1.0;
      }
    }
  }

  RunManifestWriter::write(outputPath(options.output_path, "RUN_MANIFEST.json"), engine.getRunOptions());
  if (options.diagnostic_mode) {
    writeConfigInitSnapshot(outputPath(diagnostic_options.debug_output_dir, "CONFIG_INIT_SNAPSHOT.json"), options);
    writeInputStreamSnapshot(outputPath(diagnostic_options.debug_output_dir, "INPUT_STREAM_SNAPSHOT.json"),
                             imu_samples, gnss_samples);
    writeFirstUpdatesCsv(outputPath(diagnostic_options.debug_output_dir, "FIRST_UPDATES.csv"),
                         engine.getDiagnosticUpdateRecords());
    if (options.debug_full_update_trace) {
      writeAllUpdatesCsv(outputPath(diagnostic_options.debug_output_dir, "ALL_UPDATES.csv"),
                         engine.getDiagnosticUpdateRecords());
    }
    writeFirstPropagationsCsv(outputPath(diagnostic_options.debug_output_dir, "FIRST_PROPAGATIONS.csv"),
                              engine.getDiagnosticPropagationRecords());
    writeFirstDivergenceMarkers(outputPath(diagnostic_options.debug_output_dir, "FIRST_DIVERGENCE_MARKERS.json"),
                                engine.getDiagnosticUpdateRecords(), engine.getDiagnosticPropagationRecords());
    writeRuntimeLoopParityTrace(outputPath(diagnostic_options.debug_output_dir, "RUNTIME_LOOP_PARITY_TRACE.json"),
                                engine.getRunOptions(), imu_samples, gnss_samples, engine.getDiagnosticUpdateRecords());
    if (options.debug_update_blocks) {
      writeUpdateBlockTraceCsv(outputPath(diagnostic_options.debug_output_dir, "UPDATE_BLOCK_TRACE.csv"),
                               engine.getDiagnosticUpdateBlockRecords());
    }
    if (options.debug_feedback_delta) {
      writeFeedbackDeltaTraceCsv(outputPath(diagnostic_options.debug_output_dir, "FEEDBACK_DELTA_TRACE.csv"),
                                 engine.getDiagnosticFeedbackDeltaRecords());
    }
    if (options.debug_covariance_gain) {
      writeCovarianceTraceCsv(outputPath(diagnostic_options.debug_output_dir, "COVARIANCE_TRACE.csv"),
                              engine.getDiagnosticCovarianceRecords());
    }
    if (options.debug_imu_compensation) {
      writeImuCompensationTraceCsv(outputPath(diagnostic_options.debug_output_dir, "IMU_COMPENSATION_TRACE.csv"),
                                   engine.getDiagnosticImuCompensationRecords());
    }
    if (options.debug_imu_error_feedback) {
      writeImuErrorFeedbackTraceCsv(outputPath(diagnostic_options.debug_output_dir, "IMU_ERROR_FEEDBACK_TRACE.csv"),
                                    engine.getDiagnosticImuErrorFeedbackRecords());
      writeImuErrorUnitSnapshot(outputPath(diagnostic_options.debug_output_dir, "IMU_ERROR_UNIT_SNAPSHOT.json"),
                                engine.getRunOptions(), engine.getFilterState());
    }
    if (options.debug_cross_covariance) {
      writeCrossCovarianceTraceCsv(outputPath(diagnostic_options.debug_output_dir, "CROSS_COVARIANCE_TRACE.csv"),
                                   engine.getDiagnosticCrossCovarianceRecords());
    }
    writeRuntimeDebugManifest(outputPath(diagnostic_options.debug_output_dir, "RUNTIME_DEBUG_MANIFEST.json"),
                              engine.getRunOptions());
  }
}

// 中文说明：统一写 NAV/STD/EVAL_NAV/RUN_MANIFEST；manifest 固化 forbidden flags=false。
void LegSAV23Runtime::writeOutputs(const std::string& output_dir, const GINSOptions& options, double time,
                                   const NavState& nav_state, const FilterState& filter_state) {
  std::filesystem::create_directories(output_dir);
  NavWriter nav_writer(outputPath(output_dir, "LegSA_V23_NAV.nav"));
  StdWriter std_writer(outputPath(output_dir, "LegSA_V23_STD.csv"));
  EvalNavWriter eval_writer(outputPath(output_dir, "EVAL_NAV.csv"));
  nav_writer.write(time, nav_state);
  std_writer.write(time, filter_state);
  eval_writer.write(time, nav_state);
  RunManifestWriter::write(outputPath(output_dir, "RUN_MANIFEST.json"), options);
}

}  // namespace legsa_v23_core
