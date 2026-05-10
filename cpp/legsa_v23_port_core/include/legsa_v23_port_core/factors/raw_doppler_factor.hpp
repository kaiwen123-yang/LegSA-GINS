// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N5A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: first proposed raw Doppler auxiliary factor path, not final_v23 output substitution.
// 中文说明：该因子不替代 baseline GNSS velocity；只有 satellite-state provider 支撑的
// raw-Doppler-derived velocity CSV 有效时才进入滤波器，不做 output-only correction。

#pragma once

#include "legsa_v23_port_core/factors/raw_doppler_types.hpp"

namespace legsa_v23_port_core {

class RawDopplerFactor {
 public:
  static bool isProviderBacked(const RawDopplerVelocityMeasurement& measurement);
  static Vec3 positiveStd(const RawDopplerVelocityMeasurement& measurement);
  static double residualNorm(const Vec3& nav_velocity_ned_mps,
                             const RawDopplerVelocityMeasurement& measurement);
};

}  // namespace legsa_v23_port_core
