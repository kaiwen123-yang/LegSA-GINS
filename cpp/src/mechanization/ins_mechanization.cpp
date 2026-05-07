// 中文说明：简化机械编排只服务 N4 toy filter，不使用 trace 修正，不复现双子样 final_v23 机制。
// English note: This is a runnable mechanization foundation, not oracle-level mechanization.

#include "legsa_gins/mechanization/ins_mechanization.hpp"

#include <algorithm>

#include "legsa_gins/math/earth.hpp"
#include "legsa_gins/math/quaternion.hpp"
#include "legsa_gins/math/rotation.hpp"

namespace legsa_gins::mechanization {
namespace {

math::Vec3 compensateDelta(
    const math::Vec3& delta,
    const math::Vec3& bias_rate,
    const math::Vec3& scale_error,
    double dt) {
  auto axis = [dt](double value, double bias, double scale) {
    const double denom = std::max(1.0e-9, 1.0 + scale);
    return (value - bias * dt) / denom;
  };
  return {
      axis(delta.x, bias_rate.x, scale_error.x),
      axis(delta.y, bias_rate.y, scale_error.y),
      axis(delta.z, bias_rate.z, scale_error.z),
  };
}

}  // namespace

types::LegSAFilterState InsMechanization::compensateImuError(
    const types::LegSAFilterState& state,
    const types::LegSAImuSample& /*imu*/) {
  // 当前函数保留为显式边界：补偿参数属于 state，不读取 receiver IMU 或 Go2 body-state。
  // The compensation contract is explicit; receiver IMU is not Go2 body-state.
  return state;
}

types::LegSAFilterState InsMechanization::propagate(
    const types::LegSAFilterState& previous_state,
    const types::LegSAImuSample& imu_previous,
    const types::LegSAImuSample& imu_current) {
  types::LegSAFilterState next = compensateImuError(previous_state, imu_current);
  const double dt = imu_current.dt > 0.0 ? imu_current.dt
                                        : std::max(0.0, imu_current.tow - imu_previous.tow);

  const math::Vec3 corrected_dtheta = compensateDelta(
      imu_current.dtheta_rad,
      previous_state.imu_error.gyro_bias_radps,
      previous_state.imu_error.gyro_scale,
      dt);
  const math::Vec3 corrected_dvel = compensateDelta(
      imu_current.dvel_mps,
      previous_state.imu_error.accel_bias_mps2,
      previous_state.imu_error.accel_scale,
      dt);

  // velocity update -> position update -> attitude update
  // 速度更新 -> 位置更新 -> 姿态更新：N4 只做可运行基础，不做 final_v23 parity。
  const math::Vec3 dvel_ned = math::rotateVector(previous_state.pva.qbn, corrected_dvel);
  next.pva.vel_ned_mps = math::add(previous_state.pva.vel_ned_mps, dvel_ned);

  const math::Vec3 delta_ned = math::scale(next.pva.vel_ned_mps, dt);
  const math::Vec3 dri = math::DRi(previous_state.pva.blh_rad_m);
  next.pva.blh_rad_m = math::add(
      previous_state.pva.blh_rad_m,
      {dri.x * delta_ned.x, dri.y * delta_ned.y, dri.z * delta_ned.z});

  next.pva.qbn = math::normalize(
      math::multiply(previous_state.pva.qbn, math::fromRotVec(corrected_dtheta)));
  next.pva.euler_rad = math::quaternionToEulerRad(next.pva.qbn);
  next.pva.tow = imu_current.tow;
  next.status = "legsa_filter_core_toy_only";
  return next;
}

}  // namespace legsa_gins::mechanization
