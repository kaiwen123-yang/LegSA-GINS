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

// 中文说明：RUNTIME_DEBUG_MANIFEST 明确诊断开关和 forbidden flags，防止 isolation 被误写成性能结果。
void writeRuntimeDebugManifest(const std::string& path, const GINSOptions& options) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open RUNTIME_DEBUG_MANIFEST output: " + path);
  }
  output << "{\n";
  output << "  \"phase\": \"N4H4D1\",\n";
  output << "  \"diagnostic_mode\": " << boolText(options.diagnostic_mode) << ",\n";
  output << "  \"diagnostic_run_label\": \"" << options.diagnostic_run_label << "\",\n";
  output << "  \"solver_output_changed_by_diagnostic_switches\": "
         << boolText(options.solver_output_changed_by_diagnostic_switches) << ",\n";
  output << "  \"not_for_performance_claim\": true,\n";
  output << "  \"trace_solver_input\": false,\n";
  output << "  \"final_v23_output_substitution\": false,\n";
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
    options.disable_position_update = diagnostic_options.disable_position_update;
    options.disable_velocity_update = diagnostic_options.disable_velocity_update;
    options.disable_yaw_update = diagnostic_options.disable_yaw_update;
    options.disable_measurement_update = diagnostic_options.disable_measurement_update;
    options.disable_state_feedback = diagnostic_options.disable_state_feedback;
    options.diagnostic_run_label = diagnostic_options.diagnostic_run_label;
    options.not_for_performance_claim = true;
    options.solver_output_changed_by_diagnostic_switches =
        diagnostic_options.disable_position_update || diagnostic_options.disable_velocity_update ||
        diagnostic_options.disable_yaw_update || diagnostic_options.disable_measurement_update ||
        diagnostic_options.disable_state_feedback;
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
  double next_state_trace_time = options.start_time;
  if (options.diagnostic_mode) {
    state_trace.open(outputPath(diagnostic_options.debug_output_dir, "STATE_TRACE_1HZ.csv"));
    if (!state_trace) {
      throw std::runtime_error("failed to open STATE_TRACE_1HZ output");
    }
    writeStateTraceHeader(state_trace);
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
    writeFirstPropagationsCsv(outputPath(diagnostic_options.debug_output_dir, "FIRST_PROPAGATIONS.csv"),
                              engine.getDiagnosticPropagationRecords());
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
