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

#include <filesystem>
#include <stdexcept>

namespace legsa_v23_core {
namespace {

// 中文说明：拼接输出文件名，避免在文档或配置中写入本机绝对路径。
std::string outputPath(const std::string& output_dir, const std::string& filename) {
  return (std::filesystem::path(output_dir) / filename).string();
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
void LegSAV23Runtime::runFromConfig(const std::string& config_path, const std::string& output_dir_override) {
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
  if (options.clean_input_provenance_label == "evidence_missing") {
    options.clean_input_provenance_label = "clean_status_yaw_runtime_input";
  }
  const auto imu_samples = IMUFileLoader::load(options.imu_path);
  const auto gnss_samples = GNSSFileLoader::load(options.gnss_path);
  if (imu_samples.size() < 2) {
    throw std::runtime_error("N4H4D runtime requires at least two IMU samples");
  }

  LegSAV23Engine engine(options);
  engine.initialize();
  std::filesystem::create_directories(options.output_path);
  NavWriter nav_writer(outputPath(options.output_path, "LegSA_V23_NAV.nav"));
  StdWriter std_writer(outputPath(options.output_path, "LegSA_V23_STD.csv"));
  EvalNavWriter eval_writer(outputPath(options.output_path, "EVAL_NAV.csv"));

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
  }

  RunManifestWriter::write(outputPath(options.output_path, "RUN_MANIFEST.json"), engine.getRunOptions());
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
