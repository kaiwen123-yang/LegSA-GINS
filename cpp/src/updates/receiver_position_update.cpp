// 中文说明：位置更新只使用 receiver-native position，不使用 trace 或 final_v23 输出。
// English note: The update feeds back error state immediately and resets it.

#include "legsa_gins/updates/receiver_position_update.hpp"

#include <array>

#include "legsa_gins/filter/diag_covariance.hpp"
#include "legsa_gins/math/earth.hpp"

namespace legsa_gins::updates {
namespace {

std::array<double, 3> toArray(const math::Vec3& value) {
  return {value.x, value.y, value.z};
}

}  // namespace

void applyReceiverPositionUpdate(
    types::LegSAFilterState& state,
    types::DiagCovariance21& covariance,
    types::ErrorState21& error_state,
    const types::ReceiverNativeMeasurement& meas) {
  if (!meas.has_position) {
    return;
  }
  filter::ensureCovariancePositive(covariance);

  const math::Vec3 dr = math::DR(state.pva.blh_rad_m);
  const math::Vec3 blh_delta = math::subtract(state.pva.blh_rad_m, meas.blh_rad_m);
  const std::array<double, 3> residual_ned = {
      dr.x * blh_delta.x,
      dr.y * blh_delta.y,
      dr.z * blh_delta.z,
  };
  const auto std_m = toArray(meas.pos_std_m);
  const math::Vec3 dri = math::DRi(state.pva.blh_rad_m);

  for (int axis = 0; axis < 3; ++axis) {
    const int index = types::P_ID + axis;
    const double meas_var = std_m[axis] * std_m[axis];
    const double gain = filter::scalarKalmanGain(covariance.diag[index], meas_var);
    const double correction_ned = -gain * residual_ned[axis];
    error_state.dx[index] = gain * residual_ned[axis];
    covariance.diag[index] =
        filter::posteriorVariance(covariance.diag[index], meas_var);

    if (axis == 0) {
      state.pva.blh_rad_m.x += dri.x * correction_ned;
    } else if (axis == 1) {
      state.pva.blh_rad_m.y += dri.y * correction_ned;
    } else {
      state.pva.blh_rad_m.z += dri.z * correction_ned;
    }
    error_state.dx[index] = 0.0;
  }
  state.status = "legsa_filter_core_toy_only";
}

}  // namespace legsa_gins::updates
