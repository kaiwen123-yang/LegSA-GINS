// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N5A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: first proposed raw Doppler auxiliary factor path, not final_v23 output substitution.
// Boundary: NAV-PVT velocity and .gnss vn/ve/vd are not raw Doppler.
// 中文说明：raw Doppler 是卫星级 RAWX doMes 经 satellite-state provider 推导的辅助速度因子。

#pragma once

#include "legsa_v23_port_core/types.hpp"

#include <cstddef>
#include <string>

namespace legsa_v23_port_core {

struct RawDopplerVelocityMeasurement {
  double time = 0.0;
  Vec3 velocity_ned_mps = makeVec3(0.0, 0.0, 0.0);
  Vec3 std_ned_mps = makeVec3(1.0, 1.0, 1.0);
  std::size_t sat_count = 0;
  double gdop_like = 0.0;
  std::string provider_status = "provider_missing";
};

struct RawDopplerFactorConfig {
  bool enable_raw_doppler = false;
  bool raw_doppler_solver_enabled = false;
  std::string raw_doppler_factor_path;
  std::string raw_doppler_factor_source = "none";
  double raw_doppler_time_tolerance_sec = 0.05;
  std::size_t raw_doppler_min_sat = 5;
  double raw_doppler_residual_gate_mps = 3.0;
  double raw_doppler_R_scale = 1.0;
  std::string raw_doppler_mode = "doppler_ls_velocity";
};

struct RawDopplerFactorStatus {
  bool code_present = true;
  bool solver_enabled = false;
  bool toy_factor_applied = false;
  std::size_t epoch_count = 0;
  std::size_t valid_epoch_count = 0;
  std::size_t update_count = 0;
  std::size_t reject_count = 0;
  std::size_t sat_count_min = 0;
  std::size_t sat_count_median = 0;
  std::size_t sat_count_max = 0;
  double residual_p95_mps = 0.0;
  std::string provider_status = "provider_missing";
  std::string factor_source = "none";
  bool velocity_not_nav_pvt = true;
  bool velocity_not_gnss_15col = true;
};

}  // namespace legsa_v23_port_core
