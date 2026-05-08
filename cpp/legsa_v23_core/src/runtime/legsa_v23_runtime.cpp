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

  writeOutputs(output_dir, options, engine.timestamp(), engine.getNavState(), engine.getFilterState());
}

// 中文说明：真实配置运行目前只读 process_data-compatible 输入并生成 skeleton 输出，不做 parity claim。
void LegSAV23Runtime::runFromConfig(const std::string& config_path) {
  GINSOptions options = ConfigLoader::load(config_path);
  const auto imu_samples = IMUFileLoader::load(options.imu_path);
  const auto gnss_samples = GNSSFileLoader::load(options.gnss_path);
  if (imu_samples.size() < 2) {
    throw std::runtime_error("N4H4A runtime requires at least two IMU samples");
  }

  LegSAV23Engine engine(options);
  engine.initialize();
  for (const auto& gnss : gnss_samples) {
    engine.addGnssData(gnss);
  }
  for (const auto& imu : imu_samples) {
    engine.addImuData(imu);
    engine.newImuProcess();
  }

  writeOutputs(options.output_path, options, engine.timestamp(), engine.getNavState(), engine.getFilterState());
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
