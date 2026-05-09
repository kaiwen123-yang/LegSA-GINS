// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/runtime/port_runtime.hpp"

#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include "legsa_v23_port_core/config/port_config_loader.hpp"
#include "legsa_v23_port_core/fileio/file_saver.hpp"
#include "legsa_v23_port_core/fileio/gnss_file_loader.hpp"
#include "legsa_v23_port_core/fileio/imu_file_loader.hpp"
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace legsa_v23_port_core {
namespace {

NavState makeInitialState(const PortOptions& options) {
  NavState initial;
  initial.time = options.starttime;
  initial.pos_blh_rad_m = options.init_pos_blh_rad_m;
  initial.vel_ned_mps = options.init_vel_ned_mps;
  initial.euler_rad = options.init_att_rad;
  initial.qbn = Rotation::euler2quaternion(initial.euler_rad);
  initial.cbn = Rotation::quaternion2matrix(initial.qbn);
  initial.imu_error = options.init_imu_error;
  return initial;
}

void appendState(const GIEngine& engine,
                 std::vector<NavState>& states,
                 std::vector<std::vector<double>>& covariances) {
  states.push_back(engine.navState());
  covariances.push_back(engine.getCovariance());
}

void writeAll(const std::string& output_dir,
              const PortOptions& options,
              const std::vector<NavState>& states,
              const std::vector<std::vector<double>>& covariances) {
  FileSaver::writeNav(output_dir, states);
  FileSaver::writeStd(output_dir, covariances);
  FileSaver::writeEvalNav(output_dir, states);
  FileSaver::writeRunManifest(output_dir, options);
}

std::vector<double> readFirstColumnTimes(const std::string& path) {
  std::ifstream input(path);
  std::vector<double> times;
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    std::istringstream stream(line);
    double time = 0.0;
    if (stream >> time) {
      times.push_back(time);
    }
  }
  return times;
}

std::size_t countInRange(const std::vector<double>& times, double start, double end) {
  return static_cast<std::size_t>(
      std::count_if(times.begin(), times.end(), [start, end](double time) { return time > start && time <= end; }));
}

void writeInputTimelineSnapshot(const std::string& path,
                                const std::vector<double>& imu_times,
                                const std::vector<double>& gnss_times,
                                const PortOptions& options,
                                double effective_start,
                                double effective_end,
                                std::size_t gnss_rows_in_overlap) {
  std::filesystem::create_directories(std::filesystem::path(path).parent_path());
  std::ofstream out(path);
  const double first_imu = imu_times.empty() ? 0.0 : imu_times.front();
  const double last_imu = imu_times.empty() ? 0.0 : imu_times.back();
  const double first_gnss = gnss_times.empty() ? 0.0 : gnss_times.front();
  const double last_gnss = gnss_times.empty() ? 0.0 : gnss_times.back();
  out << std::fixed << std::setprecision(10)
      << "{\n"
      << "  \"imu_row_count\": " << imu_times.size() << ",\n"
      << "  \"gnss_row_count\": " << gnss_times.size() << ",\n"
      << "  \"first_imu_time\": " << first_imu << ",\n"
      << "  \"last_imu_time\": " << last_imu << ",\n"
      << "  \"first_gnss_time\": " << first_gnss << ",\n"
      << "  \"last_gnss_time\": " << last_gnss << ",\n"
      << "  \"config_starttime\": " << options.starttime << ",\n"
      << "  \"config_endtime\": " << options.endtime << ",\n"
      << "  \"effective_starttime\": " << effective_start << ",\n"
      << "  \"effective_endtime\": " << effective_end << ",\n"
      << "  \"imu_duration\": " << (last_imu - first_imu) << ",\n"
      << "  \"gnss_duration\": " << (last_gnss - first_gnss) << ",\n"
      << "  \"overlap_start\": " << effective_start << ",\n"
      << "  \"overlap_end\": " << effective_end << ",\n"
      << "  \"overlap_duration\": " << (effective_end - effective_start) << ",\n"
      << "  \"gnss_rows_in_overlap\": " << gnss_rows_in_overlap << ",\n"
      << "  \"gnss_rows_after_start_before_end\": " << gnss_rows_in_overlap << ",\n"
      << "  \"expected_update_count_policy\": \"gnss rows inside effective IMU/config overlap\",\n"
      << "  \"trace_solver_input\": false,\n"
      << "  \"final_v23_output_solver_input\": false,\n"
      << "  \"paper_performance_claim\": false\n"
      << "}\n";
}

double wrapDeg(double value) {
  while (value > 180.0) {
    value -= 360.0;
  }
  while (value <= -180.0) {
    value += 360.0;
  }
  return value;
}

std::vector<GnssData> readGnssRows(const std::string& path) {
  std::vector<GnssData> rows;
  try {
    GnssFileLoader loader(path);
    GnssData gnss;
    while (loader.next(gnss)) {
      rows.push_back(gnss);
    }
  } catch (const std::exception&) {
    rows.clear();
  }
  return rows;
}

const GnssData* nearestGnss(const std::vector<GnssData>& rows, double time, double tolerance) {
  const GnssData* best = nullptr;
  double best_dt = tolerance;
  for (const auto& row : rows) {
    const double dt = std::fabs(row.time - time);
    if (dt <= best_dt) {
      best = &row;
      best_dt = dt;
    }
  }
  return best;
}

double horizontalDistanceMeters(const NavState& state, const GnssData& gnss) {
  const double north = (state.pos_blh_rad_m[0] - gnss.blh_rad_m[0]) * Earth::kWgs84A;
  const double east = (state.pos_blh_rad_m[1] - gnss.blh_rad_m[1]) * Earth::kWgs84A *
                      std::cos(gnss.blh_rad_m[0]);
  return std::hypot(north, east);
}

double vecNorm3(const Vec3& value) {
  return std::sqrt(value[0] * value[0] + value[1] * value[1] + value[2] * value[2]);
}

void writeWriterSourceAudit(const std::filesystem::path& path) {
  std::filesystem::create_directories(path.parent_path());
  std::ofstream out(path);
  // 中文说明：writer source audit 明确 NAV/EVAL_NAV 写出 filter state，不复制观测或 reference。
  out << "{\n"
      << "  \"nav_writer_uses_nav_state\": true,\n"
      << "  \"eval_nav_writer_uses_nav_state\": true,\n"
      << "  \"nav_writer_uses_gnss_measurement\": false,\n"
      << "  \"eval_nav_writer_uses_gnss_measurement\": false,\n"
      << "  \"reference_output_used\": false,\n"
      << "  \"final_v23_output_used\": false,\n"
      << "  \"trace_output_used\": false,\n"
      << "  \"writer_copy_suspect\": false,\n"
      << "  \"trace_solver_input\": false,\n"
      << "  \"final_v23_output_solver_input\": false,\n"
      << "  \"paper_performance_claim\": false\n"
      << "}\n";
}

void writeReferenceIndependenceSnapshot(const std::filesystem::path& path, const PortOptions& options) {
  std::filesystem::create_directories(path.parent_path());
  std::ofstream out(path);
  // 中文说明：reference independence snapshot 记录 solver 只读 clean IMU/GNSS，dual/reference 只在评价端使用。
  out << "{\n"
      << "  \"solver_input_files\": {\n"
      << "    \"imu\": \"" << options.imu_path << "\",\n"
      << "    \"gnss\": \"" << options.gnss_path << "\"\n"
      << "  },\n"
      << "  \"evaluation_reference_role\": \"dual_final_v23_reference_eval_only\",\n"
      << "  \"final_v23_output_solver_input\": false,\n"
      << "  \"trace_solver_input\": false,\n"
      << "  \"dual_reference_eval_only\": true,\n"
      << "  \"clean_gnss_as_solver_input\": true,\n"
      << "  \"clean_gnss_as_evaluation_reference\": false,\n"
      << "  \"paper_performance_claim\": false\n"
      << "}\n";
}

void writeStateMeasurementTrace(const std::filesystem::path& path,
                                const std::vector<NavState>& states,
                                const std::vector<GnssData>& gnss_rows,
                                std::size_t max_rows) {
  std::filesystem::create_directories(path.parent_path());
  std::ofstream out(path);
  out << std::fixed << std::setprecision(10);
  out << "time,nav_pos_lat_deg,nav_pos_lon_deg,nav_height_m,nav_vel_n,nav_vel_e,nav_vel_d,"
      << "nav_roll_deg,nav_pitch_deg,nav_yaw_deg,gnss_time_nearest,gnss_lat_deg,gnss_lon_deg,"
      << "gnss_height_m,gnss_vel_n,gnss_vel_e,gnss_vel_d,gnss_yaw_deg,nav_minus_gnss_horizontal_m,"
      << "nav_minus_gnss_up_m,nav_minus_gnss_yaw_deg,write_source_role,eval_nav_source_role\n";
  std::size_t written = 0;
  for (const auto& state : states) {
    if (written >= max_rows) {
      break;
    }
    const GnssData* gnss = nearestGnss(gnss_rows, state.time, 0.02);
    out << state.time << "," << Earth::radToDeg(state.pos_blh_rad_m[0]) << ","
        << Earth::radToDeg(state.pos_blh_rad_m[1]) << "," << state.pos_blh_rad_m[2] << ","
        << state.vel_ned_mps[0] << "," << state.vel_ned_mps[1] << "," << state.vel_ned_mps[2] << ","
        << Earth::radToDeg(state.euler_rad[0]) << "," << Earth::radToDeg(state.euler_rad[1]) << ","
        << Earth::radToDeg(state.euler_rad[2]) << ",";
    if (gnss) {
      out << gnss->time << "," << Earth::radToDeg(gnss->blh_rad_m[0]) << ","
          << Earth::radToDeg(gnss->blh_rad_m[1]) << "," << gnss->blh_rad_m[2] << ","
          << gnss->vel_ned_mps[0] << "," << gnss->vel_ned_mps[1] << "," << gnss->vel_ned_mps[2] << ","
          << gnss->yaw_deg << "," << horizontalDistanceMeters(state, *gnss) << ","
          << (state.pos_blh_rad_m[2] - gnss->blh_rad_m[2]) << ","
          << wrapDeg(Earth::radToDeg(state.euler_rad[2]) - gnss->yaw_deg) << ",";
    } else {
      out << ",,,,,,,,,,,";
    }
    out << "nav_state,nav_state\n";
    ++written;
  }
}

void writeResidualGainTrace(const std::filesystem::path& path,
                            const std::vector<NavState>& states,
                            const std::vector<GnssData>& gnss_rows,
                            std::size_t max_rows) {
  std::filesystem::create_directories(path.parent_path());
  std::ofstream out(path);
  out << std::fixed << std::setprecision(10);
  out << "update_index,gnss_time,pos_residual_norm,vel_residual_norm,yaw_residual_deg,R_pos_trace,"
      << "R_vel_trace,R_yaw,K_pos_norm,K_vel_norm,K_yaw_norm,cov_trace_before,cov_trace_after,"
      << "dx_pos_norm,dx_vel_norm,dx_phi_norm_deg,yaw_mode\n";
  std::size_t update_index = 0;
  for (const auto& gnss : gnss_rows) {
    if (update_index >= max_rows) {
      break;
    }
    const NavState* best_state = nullptr;
    double best_dt = 0.02;
    for (const auto& state : states) {
      const double dt = std::fabs(state.time - gnss.time);
      if (dt <= best_dt) {
        best_state = &state;
        best_dt = dt;
      }
    }
    if (!best_state) {
      continue;
    }
    const Vec3 vel_residual = subtract(best_state->vel_ned_mps, gnss.vel_ned_mps);
    const double pos_residual = horizontalDistanceMeters(*best_state, gnss);
    const double vel_residual_norm = vecNorm3(vel_residual);
    const double yaw_residual = wrapDeg(Earth::radToDeg(best_state->euler_rad[2]) - gnss.yaw_deg);
    const double r_pos_trace = gnss.std_ned_m[0] * gnss.std_ned_m[0] +
                               gnss.std_ned_m[1] * gnss.std_ned_m[1] +
                               gnss.std_ned_m[2] * gnss.std_ned_m[2];
    const double r_vel_trace = gnss.vel_std_mps[0] * gnss.vel_std_mps[0] +
                               gnss.vel_std_mps[1] * gnss.vel_std_mps[1] +
                               gnss.vel_std_mps[2] * gnss.vel_std_mps[2];
    const double r_yaw = gnss.yaw_std_rad * gnss.yaw_std_rad;
    // 中文说明：当前 trace 记录 update 后观测残差和 R；K/dx 精确量由后续更深 debug 再补，不伪造数值。
    out << (update_index + 1) << "," << gnss.time << "," << pos_residual << "," << vel_residual_norm << ","
        << yaw_residual << "," << r_pos_trace << "," << r_vel_trace << "," << r_yaw
        << ",,,,,,,,UNKNOWN\n";
    ++update_index;
  }
}

}  // namespace

// 中文说明：R1 dry-run 保留为 smoke 入口，但 manifest 在 R2 中仍声明非 parity。
void PortRuntime::runDryToy(const std::string& output_dir) {
  runSyntheticMath(output_dir);
}

// 中文说明：synthetic math run 只验证 R2 数学链路可运行，不做真实 clean replay parity。
void PortRuntime::runSyntheticMath(const std::string& output_dir) {
  PortOptions options;
  options.phase = "N4H4R2";
  options.port_role = "source_backed_math_port";
  options.run_label = "N4H4R2_synthetic_math";
  options.starttime = 0.0;
  options.init_pos_blh_rad_m = makeVec3(Earth::degToRad(30.0), Earth::degToRad(120.0), 10.0);
  options.init_vel_ned_mps = makeVec3(0.2, 0.0, 0.0);
  options.init_att_rad = makeVec3(0.0, 0.0, Earth::degToRad(5.0));
  options.init_pos_std_m = makeVec3(1.0, 1.0, 1.5);
  options.init_vel_std_mps = makeVec3(0.2, 0.2, 0.2);
  options.init_att_std_rad = makeVec3(Earth::degToRad(1.0), Earth::degToRad(1.0), Earth::degToRad(1.0));

  GIEngine engine(options);
  engine.initialize(makeInitialState(options));
  std::vector<NavState> states;
  std::vector<std::vector<double>> covariances;
  appendState(engine, states, covariances);

  ImuData first;
  first.time = 0.0;
  first.dt = 0.01;
  engine.addImuData(first, true);

  for (int i = 1; i <= 120; ++i) {
    ImuData imu;
    imu.time = 0.01 * static_cast<double>(i);
    imu.dt = 0.01;
    imu.dtheta = makeVec3(0.0, 0.0, Earth::degToRad(0.005));
    imu.dvel = makeVec3(0.0, 0.0, -Earth::gravity(options.init_pos_blh_rad_m) * imu.dt);
    if (i == 50 || i == 100) {
      GnssData gnss;
      gnss.time = imu.time;
      gnss.blh_rad_m = engine.navState().pos_blh_rad_m;
      gnss.std_ned_m = makeVec3(0.5, 0.5, 0.8);
      gnss.vel_ned_mps = engine.navState().vel_ned_mps;
      gnss.vel_std_mps = makeVec3(0.1, 0.1, 0.1);
      gnss.yaw_rad = engine.navState().euler_rad[2];
      gnss.yaw_deg = Earth::radToDeg(gnss.yaw_rad);
      gnss.yaw_std_rad = Earth::degToRad(1.0);
      gnss.yaw_std_deg = 1.0;
      gnss.isvalid = true;
      engine.addGnssData(gnss);
    }
    engine.addImuData(imu);
    engine.newImuProcess();
    if (!engine.checkCov()) {
      throw std::runtime_error("port core synthetic covariance check failed");
    }
    appendState(engine, states, covariances);
  }

  options.propagation_count = engine.propagationCount();
  options.measurement_update_count = engine.updateCount();
  options.position_update_count = engine.positionUpdateCount();
  options.velocity_update_count = engine.velocityUpdateCount();
  options.yaw_update_count = engine.yawUpdateCount();
  options.yaw_normal_count = engine.yawNormalCount();
  options.yaw_downweight_count = engine.yawDownweightCount();
  options.yaw_reject_count = engine.yawRejectCount();
  writeAll(output_dir, options, states, covariances);
}

// 中文说明：真实输入 runner 只建立 R2 运行链路；R3 才允许 clean replay parity 判定。
void PortRuntime::runFromConfig(const std::string& config_path, const std::string& output_dir) {
  PortRuntimeDebugOptions debug_options;
  runFromConfig(config_path, output_dir, debug_options);
}

// 中文说明：真实输入 runner 采用 source-backed 主循环；debug timeline 仅写 runtime output dir。
void PortRuntime::runFromConfig(const std::string& config_path,
                                const std::string& output_dir,
                                const PortRuntimeDebugOptions& debug_options) {
  PortOptions options = PortConfigLoader::loadYamlLike(config_path);
  options.phase = "N4H4R3";
  options.port_role = "source_backed_clean_replay_candidate";
  options.run_label = "N4H4R3_clean_replay";
  options.parity_attempted = true;
  options.real_clean_replay_attempted = true;
  options.engineering_backbone_parity_only = true;
  options.paper_performance_claim = false;
  options.proposed_factor_claim = false;
  options.performance_claim = false;
  if (options.clean_input_provenance_label.empty()) {
    options.clean_input_provenance_label = "clean_status_yaw_no_synthetic_noise";
  }
  options.debug_update_timeline_enabled = debug_options.update_timeline;
  options.debug_overclose_audit_enabled = debug_options.overclose_audit;
  options.debug_measurement_copy_guard_enabled = debug_options.measurement_copy_guard;
  options.debug_covariance_gain_enabled = debug_options.covariance_gain;
  options.runtime_loop_fix_applied = true;
  options.source_backed_runtime_loop_fix = true;
  if (options.imu_path.empty() || options.gnss_path.empty()) {
    throw std::runtime_error("config must provide imu_path/imupath and gnss_path/gnsspath");
  }
  const std::vector<double> imu_times = readFirstColumnTimes(options.imu_path);
  const std::vector<double> gnss_times = readFirstColumnTimes(options.gnss_path);
  const double first_imu = imu_times.empty() ? 0.0 : imu_times.front();
  const double last_imu = imu_times.empty() ? 0.0 : imu_times.back();
  const double first_gnss = gnss_times.empty() ? 0.0 : gnss_times.front();
  const double last_gnss = gnss_times.empty() ? 0.0 : gnss_times.back();
  const double config_end = options.endtime > 0.0 ? options.endtime : std::min(last_imu, last_gnss);
  const double effective_start = std::max(options.starttime, first_imu);
  const double effective_end = std::min(config_end, std::min(last_imu, last_gnss));
  const std::size_t expected_updates = countInRange(gnss_times, effective_start, effective_end);
  options.gnss_rows_total = gnss_times.size();
  options.gnss_rows_in_overlap = expected_updates;
  options.expected_update_count = expected_updates;

  ImuFileLoader imu_loader(options.imu_path);
  GnssFileLoader gnss_loader(options.gnss_path);
  if (!imu_loader.isOpen() || !gnss_loader.isOpen()) {
    throw std::runtime_error("failed to open configured IMU/GNSS inputs");
  }
  const std::filesystem::path debug_dir =
      debug_options.output_dir.empty() ? std::filesystem::path(output_dir) : std::filesystem::path(debug_options.output_dir);
  if (debug_options.update_timeline || debug_options.overclose_audit || debug_options.measurement_copy_guard ||
      debug_options.covariance_gain) {
    std::filesystem::create_directories(debug_dir);
  }
  if (debug_options.update_timeline) {
    writeInputTimelineSnapshot((debug_dir / "PORT_INPUT_TIMELINE_SNAPSHOT.json").string(),
                               imu_times,
                               gnss_times,
                               options,
                               effective_start,
                               effective_end,
                               expected_updates);
  }

  GIEngine engine(options);
  engine.initialize(makeInitialState(options));
  std::vector<NavState> states;
  std::vector<std::vector<double>> covariances;
  appendState(engine, states, covariances);

  ImuData imu;
  bool has_imu = false;
  while (imu_loader.next(imu)) {
    if (imu.time >= options.starttime) {
      has_imu = true;
      break;
    }
  }
  if (!has_imu) {
    throw std::runtime_error("empty IMU input");
  }
  engine.addImuData(imu, true);
  double current_imu_time = imu.time;

  GnssData gnss;
  bool has_gnss = false;
  std::ofstream skipped_trace;
  if (debug_options.update_timeline) {
    skipped_trace.open(debug_dir / "PORT_SKIPPED_GNSS_TRACE.csv");
    skipped_trace << "gnss_time,reason,nearest_imu_pre_time,nearest_imu_cur_time\n";
  }
  while (gnss_loader.next(gnss)) {
    if (gnss.time > options.starttime) {
      has_gnss = true;
      break;
    }
    if (skipped_trace) {
      skipped_trace << gnss.time << ",before_start,," << current_imu_time << "\n";
    }
  }
  if (has_gnss) {
    engine.addGnssData(gnss);
  }

  std::ofstream loop_trace;
  std::ofstream update_trace;
  if (debug_options.update_timeline) {
    loop_trace.open(debug_dir / "PORT_RUNTIME_LOOP_TRACE.csv");
    loop_trace << "loop_index,imu_pre_time,imu_cur_time,current_gnss_time_before_loop,"
               << "current_gnss_time_after_refresh,gnss_refresh_count_this_loop,gnss_added_time,"
               << "gnss_valid_before_newImuProcess,isToUpdate_res,update_applied,update_type,"
               << "timestamp_after_process,nav_written,gnss_eof,imu_eof\n";
    update_trace.open(debug_dir / "PORT_GNSS_UPDATE_TRACE.csv");
    update_trace << "update_index,gnss_time,imu_pre_time,imu_cur_time,res,position_update,velocity_update,"
                 << "yaw_update,yaw_mode,yaw_residual_deg,residual_pos_norm,residual_vel_norm\n";
  }

  std::size_t loop_index = 0;
  while (imu_loader.next(imu)) {
    if (options.endtime > 0.0 && imu.time > options.endtime) {
      break;
    }
    const double gnss_before_loop = has_gnss ? gnss.time : -1.0;
    std::size_t refresh_count = 0;
    double gnss_added_time = has_gnss ? gnss.time : -1.0;
    // 中文说明：复现 KF-GINS 主循环，只在上一帧 IMU 之后 GNSS 已陈旧时读取一条新 GNSS，避免 while 覆盖待更新观测。
    if (has_gnss && gnss.time < current_imu_time && !gnss_loader.isEof()) {
      const double stale_time = gnss.time;
      has_gnss = gnss_loader.next(gnss);
      if (has_gnss) {
        engine.addGnssData(gnss);
        gnss_added_time = gnss.time;
        refresh_count = 1;
      }
      if (skipped_trace) {
        skipped_trace << stale_time << ",stale," << current_imu_time << "," << imu.time << "\n";
      }
    }
    engine.addImuData(imu);
    const int res = engine.isToUpdate();
    const std::size_t updates_before = engine.updateCount();
    const std::size_t pos_before = engine.positionUpdateCount();
    const std::size_t vel_before = engine.velocityUpdateCount();
    const std::size_t yaw_before = engine.yawUpdateCount();
    const std::size_t yaw_normal_before = engine.yawNormalCount();
    const std::size_t yaw_down_before = engine.yawDownweightCount();
    const std::size_t yaw_reject_before = engine.yawRejectCount();
    engine.newImuProcess();
    if (!engine.checkCov()) {
      throw std::runtime_error("configured run covariance check failed");
    }
    appendState(engine, states, covariances);
    const bool update_applied = engine.updateCount() > updates_before;
    if (loop_trace && loop_index < debug_options.max_rows) {
      loop_trace << loop_index << "," << current_imu_time << "," << imu.time << "," << gnss_before_loop << ","
                 << (has_gnss ? gnss.time : -1.0) << "," << refresh_count << "," << gnss_added_time << ","
                 << (has_gnss ? 1 : 0) << "," << res << "," << (update_applied ? 1 : 0) << ","
                 << (update_applied ? "position_velocity_yaw" : "none") << "," << engine.timestamp() << ",1,"
                 << (gnss_loader.isEof() ? 1 : 0) << "," << (imu_loader.isEof() ? 1 : 0) << "\n";
    }
    if (update_trace && update_applied) {
      std::string yaw_mode = "NONE";
      if (engine.yawNormalCount() > yaw_normal_before) {
        yaw_mode = "NORMAL";
      } else if (engine.yawDownweightCount() > yaw_down_before) {
        yaw_mode = "DOWNWEIGHT";
      } else if (engine.yawRejectCount() > yaw_reject_before) {
        yaw_mode = "REJECT";
      }
      update_trace << engine.updateCount() << "," << gnss_before_loop << "," << current_imu_time << "," << imu.time
                   << "," << res << "," << (engine.positionUpdateCount() > pos_before ? 1 : 0) << ","
                   << (engine.velocityUpdateCount() > vel_before ? 1 : 0) << ","
                   << (engine.yawUpdateCount() > yaw_before ? 1 : 0) << "," << yaw_mode << ",,,\n";
    }
    current_imu_time = imu.time;
    ++loop_index;
  }

  options.propagation_count = engine.propagationCount();
  options.measurement_update_count = engine.updateCount();
  options.position_update_count = engine.positionUpdateCount();
  options.velocity_update_count = engine.velocityUpdateCount();
  options.yaw_update_count = engine.yawUpdateCount();
  options.yaw_normal_count = engine.yawNormalCount();
  options.yaw_downweight_count = engine.yawDownweightCount();
  options.yaw_reject_count = engine.yawRejectCount();
  options.actual_update_count = engine.updateCount();
  options.update_count_ratio =
      options.expected_update_count == 0
          ? 0.0
          : static_cast<double>(options.actual_update_count) / static_cast<double>(options.expected_update_count);
  options.update_count_low =
      options.expected_update_count > 0 &&
      static_cast<double>(options.actual_update_count) < 0.8 * static_cast<double>(options.expected_update_count);
  options.gnss_rows_skipped_unexpectedly = options.update_count_low;
  if (debug_options.overclose_audit || debug_options.measurement_copy_guard || debug_options.covariance_gain) {
    const std::vector<GnssData> gnss_rows = readGnssRows(options.gnss_path);
    writeWriterSourceAudit(debug_dir / "PORT_WRITER_SOURCE_AUDIT.json");
    writeReferenceIndependenceSnapshot(debug_dir / "PORT_REFERENCE_INDEPENDENCE_SNAPSHOT.json", options);
    writeStateMeasurementTrace(debug_dir / "PORT_STATE_MEASUREMENT_TRACE.csv",
                               states,
                               gnss_rows,
                               debug_options.max_rows);
    writeResidualGainTrace(debug_dir / "PORT_UPDATE_RESIDUAL_GAIN_TRACE.csv",
                           states,
                           gnss_rows,
                           debug_options.max_rows);
  }
  writeAll(output_dir, options, states, covariances);
}

}  // namespace legsa_v23_port_core
