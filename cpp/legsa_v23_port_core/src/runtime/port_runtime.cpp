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

#include <stdexcept>
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
  if (options.imu_path.empty() || options.gnss_path.empty()) {
    throw std::runtime_error("config must provide imu_path/imupath and gnss_path/gnsspath");
  }
  ImuFileLoader imu_loader(options.imu_path);
  GnssFileLoader gnss_loader(options.gnss_path);
  if (!imu_loader.isOpen() || !gnss_loader.isOpen()) {
    throw std::runtime_error("failed to open configured IMU/GNSS inputs");
  }

  GIEngine engine(options);
  engine.initialize(makeInitialState(options));
  std::vector<NavState> states;
  std::vector<std::vector<double>> covariances;
  appendState(engine, states, covariances);

  ImuData imu;
  if (!imu_loader.next(imu)) {
    throw std::runtime_error("empty IMU input");
  }
  engine.addImuData(imu, true);

  GnssData gnss;
  bool has_gnss = gnss_loader.next(gnss);
  if (has_gnss) {
    engine.addGnssData(gnss);
  }

  while (imu_loader.next(imu)) {
    while (has_gnss && gnss.time < imu.time && !gnss_loader.isEof()) {
      has_gnss = gnss_loader.next(gnss);
      if (has_gnss) {
        engine.addGnssData(gnss);
      }
    }
    engine.addImuData(imu);
    engine.newImuProcess();
    if (!engine.checkCov()) {
      throw std::runtime_error("configured run covariance check failed");
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

}  // namespace legsa_v23_port_core
