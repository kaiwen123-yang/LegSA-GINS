// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/runtime/port_runtime.hpp"

#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/fileio/file_saver.hpp"
#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"

#include <stdexcept>
#include <vector>

namespace legsa_v23_port_core {

// 中文说明：R1 dry-run 构造 toy 数据验证 target/writer/manifest，不做真实 clean parity。
void PortRuntime::runDryToy(const std::string& output_dir) {
  PortOptions options;
  options.run_label = "N4H4R1_port_core_dry_run";
  options.init_pos_blh_rad_m = makeVec3(Earth::degToRad(30.0), Earth::degToRad(120.0), 10.0);
  options.init_vel_ned_mps = makeVec3(0.1, 0.0, 0.0);
  options.init_att_rad = makeVec3(0.0, 0.0, Earth::degToRad(5.0));

  NavState initial;
  initial.time = 0.0;
  initial.pos_blh_rad_m = options.init_pos_blh_rad_m;
  initial.vel_ned_mps = options.init_vel_ned_mps;
  initial.euler_rad = options.init_att_rad;

  GIEngine engine(options);
  engine.initialize(initial);
  std::vector<NavState> states{initial};
  std::vector<std::vector<double>> covariances{engine.getCovariance()};

  GnssData gnss;
  gnss.time = 0.01;
  gnss.blh_rad_m = initial.pos_blh_rad_m;
  gnss.yaw_deg = 5.0;
  engine.addGnssData(gnss);

  for (int i = 1; i <= 3; ++i) {
    ImuData imu;
    imu.time = 0.01 * static_cast<double>(i);
    imu.dt = 0.01;
    imu.dtheta = makeVec3(0.0, 0.0, Earth::degToRad(0.01));
    imu.dvel = makeVec3(0.001, 0.0, 0.0);
    engine.addImuData(imu);
    engine.newImuProcess();
    if (!engine.checkCov()) {
      throw std::runtime_error("port core toy covariance check failed");
    }
    states.push_back(engine.navState());
    covariances.push_back(engine.getCovariance());
  }

  FileSaver::writeNav(output_dir, states);
  FileSaver::writeStd(output_dir, covariances);
  FileSaver::writeEvalNav(output_dir, states);
  FileSaver::writeRunManifest(output_dir, options);
}

}  // namespace legsa_v23_port_core

