// 中文说明：航向更新只处理 receiver-native yaw/heading，不实现 self raw heading。
// English note: Yaw residuals are wrapped to [-pi, pi), output yaw to [0, 2pi).

#include "legsa_gins/updates/receiver_heading_update.hpp"

#include "legsa_gins/filter/diag_covariance.hpp"
#include "legsa_gins/math/angle.hpp"
#include "legsa_gins/math/rotation.hpp"

namespace legsa_gins::updates {

void applyReceiverHeadingUpdate(
    types::LegSAFilterState& state,
    types::DiagCovariance21& covariance,
    types::ErrorState21& error_state,
    const types::ReceiverNativeMeasurement& meas) {
  if (!meas.has_heading) {
    return;
  }
  filter::ensureCovariancePositive(covariance);

  const int index = types::PHI_ID + 2;
  const double residual = math::wrapRadPi(state.pva.euler_rad.z - meas.yaw_heading_rad);
  const double meas_var = meas.yaw_std_rad * meas.yaw_std_rad;
  const double gain = filter::scalarKalmanGain(covariance.diag[index], meas_var);
  const double yaw_correction = -gain * residual;

  error_state.dx[index] = gain * residual;
  covariance.diag[index] = filter::posteriorVariance(covariance.diag[index], meas_var);
  state.pva.euler_rad.z = math::wrapRad2Pi(state.pva.euler_rad.z + yaw_correction);
  state.pva.qbn = math::eulerRadToQuaternion(
      state.pva.euler_rad.x, state.pva.euler_rad.y, state.pva.euler_rad.z);
  error_state.dx[index] = 0.0;
  state.status = "legsa_filter_core_toy_only";
}

}  // namespace legsa_gins::updates
