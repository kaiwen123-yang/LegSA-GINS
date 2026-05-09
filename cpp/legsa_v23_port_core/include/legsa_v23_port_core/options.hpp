// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/types.hpp"

#include <string>

namespace legsa_v23_port_core {

// 中文说明：R1 options 只保存最小 backbone 配置和边界旗标，不读取 trace 或 final_v23 输出。
struct PortOptions {
  std::string run_label = "N4H4R1_dry_run";
  Vec3 antlever_m = makeVec3(0.0, 0.0, 0.0);
  Vec3 init_pos_blh_rad_m = makeVec3(0.0, 0.0, 0.0);
  Vec3 init_vel_ned_mps = makeVec3(0.0, 0.0, 0.0);
  Vec3 init_att_rad = makeVec3(0.0, 0.0, 0.0);
  double init_cov_diag = 1.0;
  bool parity_attempted = false;
  bool final_v23_output_solver_input = false;
  bool trace_solver_input = false;
  bool raw_doppler = false;
  bool go2_prior = false;
  bool lsim_oim = false;
  bool fgo = false;
  bool performance_claim = false;
};

}  // namespace legsa_v23_port_core

