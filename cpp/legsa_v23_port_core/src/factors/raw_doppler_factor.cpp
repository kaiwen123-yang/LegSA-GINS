// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N5A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: first proposed raw Doppler auxiliary factor path, not final_v23 output substitution.
// 中文说明：仅对 provider_status=available 的卫星级 Doppler 衍生速度构造 EKF 残差。

#include "legsa_v23_port_core/factors/raw_doppler_factor.hpp"

#include <algorithm>
#include <cmath>

namespace legsa_v23_port_core {

bool RawDopplerFactor::isProviderBacked(const RawDopplerVelocityMeasurement& measurement) {
  return measurement.provider_status == "available";
}

Vec3 RawDopplerFactor::positiveStd(const RawDopplerVelocityMeasurement& measurement) {
  return makeVec3(std::max(std::fabs(measurement.std_ned_mps[0]), 1.0e-3),
                  std::max(std::fabs(measurement.std_ned_mps[1]), 1.0e-3),
                  std::max(std::fabs(measurement.std_ned_mps[2]), 1.0e-3));
}

double RawDopplerFactor::residualNorm(const Vec3& nav_velocity_ned_mps,
                                      const RawDopplerVelocityMeasurement& measurement) {
  const Vec3 residual = subtract(nav_velocity_ned_mps, measurement.velocity_ned_mps);
  return norm(residual);
}

}  // namespace legsa_v23_port_core
