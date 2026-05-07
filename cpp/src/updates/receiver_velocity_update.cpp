// 中文说明：速度更新只反馈 V_ID 三维误差，不实现 Go2 prior 或 LSIM/OIM。
// English note: Diagonal scalar gains keep the N4 filter foundation simple.

#include "legsa_gins/updates/receiver_velocity_update.hpp"

#include <array>

#include "legsa_gins/filter/diag_covariance.hpp"
#include "legsa_gins/math/vec3.hpp"

namespace legsa_gins::updates {
namespace {

std::array<double, 3> toArray(const math::Vec3& value) {
  return {value.x, value.y, value.z};
}

}  // namespace

void applyReceiverVelocityUpdate(
    types::LegSAFilterState& state,
    types::DiagCovariance21& covariance,
    types::ErrorState21& error_state,
    const types::ReceiverNativeMeasurement& meas) {
  if (!meas.has_velocity) {
    return;
  }
  filter::ensureCovariancePositive(covariance);

  const std::array<double, 3> predicted = toArray(state.pva.vel_ned_mps);
  const std::array<double, 3> measured = toArray(meas.vel_ned_mps);
  const std::array<double, 3> std_mps = toArray(meas.vel_std_mps);

  for (int axis = 0; axis < 3; ++axis) {
    const int index = types::V_ID + axis;
    const double residual = predicted[axis] - measured[axis];
    const double meas_var = std_mps[axis] * std_mps[axis];
    const double gain = filter::scalarKalmanGain(covariance.diag[index], meas_var);
    const double correction = -gain * residual;
    error_state.dx[index] = gain * residual;
    covariance.diag[index] =
        filter::posteriorVariance(covariance.diag[index], meas_var);

    if (axis == 0) {
      state.pva.vel_ned_mps.x += correction;
    } else if (axis == 1) {
      state.pva.vel_ned_mps.y += correction;
    } else {
      state.pva.vel_ned_mps.z += correction;
    }
    error_state.dx[index] = 0.0;
  }
  state.status = "legsa_filter_core_toy_only";
}

}  // namespace legsa_gins::updates
