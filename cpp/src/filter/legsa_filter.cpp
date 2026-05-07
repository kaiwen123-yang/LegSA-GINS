// 中文说明：N4 filter core 只实现 receiver-native P/V/heading toy update，不做 final_v23 数值复现。
// English note: The history is for writer verification, not a performance claim.

#include "legsa_gins/filter/legsa_filter.hpp"

#include <cmath>
#include <stdexcept>

#include "legsa_gins/filter/diag_covariance.hpp"
#include "legsa_gins/math/constants.hpp"
#include "legsa_gins/mechanization/ins_mechanization.hpp"
#include "legsa_gins/updates/receiver_heading_update.hpp"
#include "legsa_gins/updates/receiver_position_update.hpp"
#include "legsa_gins/updates/receiver_velocity_update.hpp"

namespace legsa_gins::filter {

void LegSAFilter::initialize(
    const types::LegSAFilterState& initial_state,
    const types::DiagCovariance21& initial_covariance) {
  ensureCovariancePositive(initial_covariance);
  state_ = initial_state;
  state_.status = "legsa_filter_core_toy_only";
  covariance_ = initial_covariance;
  resetErrorState(error_state_);
  history_.clear();
  history_.push_back(state_);
  initialized_ = true;
}

void LegSAFilter::predict(
    const types::LegSAImuSample& imu_previous,
    const types::LegSAImuSample& imu_current) {
  if (!initialized_) {
    throw std::runtime_error("LegSAFilter must be initialized before predict.");
  }
  state_ = mechanization::InsMechanization::propagate(
      state_, imu_previous, imu_current);
  state_.status = "legsa_filter_core_toy_only";
}

void LegSAFilter::update(const types::ReceiverNativeMeasurement& measurement) {
  if (!initialized_) {
    throw std::runtime_error("LegSAFilter must be initialized before update.");
  }
  updates::applyReceiverPositionUpdate(state_, covariance_, error_state_, measurement);
  updates::applyReceiverVelocityUpdate(state_, covariance_, error_state_, measurement);
  updates::applyReceiverHeadingUpdate(state_, covariance_, error_state_, measurement);
  state_.status = "legsa_filter_core_toy_only";
}

void LegSAFilter::process(
    const std::vector<types::LegSAImuSample>& imu_samples,
    const std::vector<types::ReceiverNativeMeasurement>& receiver_measurements) {
  if (!initialized_) {
    throw std::runtime_error("LegSAFilter must be initialized before process.");
  }
  if (imu_samples.empty()) {
    throw std::runtime_error("LegSAFilter process requires at least one IMU sample.");
  }

  std::size_t receiver_index = 0;
  while (receiver_index < receiver_measurements.size() &&
         receiver_measurements[receiver_index].tow <= imu_samples.front().tow) {
    update(receiver_measurements[receiver_index++]);
  }
  history_.push_back(state_);

  for (std::size_t imu_index = 1; imu_index < imu_samples.size(); ++imu_index) {
    predict(imu_samples[imu_index - 1], imu_samples[imu_index]);
    while (receiver_index < receiver_measurements.size() &&
           receiver_measurements[receiver_index].tow <= imu_samples[imu_index].tow) {
      update(receiver_measurements[receiver_index++]);
    }
    history_.push_back(state_);
  }

  while (receiver_index < receiver_measurements.size()) {
    update(receiver_measurements[receiver_index++]);
    history_.push_back(state_);
  }
}

types::LegSAFilterState LegSAFilter::getState() const { return state_; }

types::DiagCovariance21 LegSAFilter::getCovariance() const { return covariance_; }

const std::vector<types::LegSAFilterState>& LegSAFilter::getHistory() const {
  return history_;
}

types::NavState LegSAFilter::getNavState() const {
  types::NavState nav;
  nav.tow = state_.pva.tow;
  nav.lat_deg = state_.pva.blh_rad_m.x * math::rad_to_deg;
  nav.lon_deg = state_.pva.blh_rad_m.y * math::rad_to_deg;
  nav.height_m = state_.pva.blh_rad_m.z;
  nav.vn_mps = state_.pva.vel_ned_mps.x;
  nav.ve_mps = state_.pva.vel_ned_mps.y;
  nav.vd_mps = state_.pva.vel_ned_mps.z;
  nav.roll_deg = state_.pva.euler_rad.x * math::rad_to_deg;
  nav.pitch_deg = state_.pva.euler_rad.y * math::rad_to_deg;
  nav.yaw_deg = state_.pva.euler_rad.z * math::rad_to_deg;
  nav.status = "legsa_filter_core_toy_only";
  nav.source_role = "proposed_filter_core";
  return nav;
}

types::StdState LegSAFilter::getStdState() const {
  auto std_from_var = [](double value) { return std::sqrt(value); };
  types::StdState std_state;
  std_state.tow = state_.pva.tow;
  std_state.std_pos_n_m = std_from_var(covariance_.diag[types::P_ID + 0]);
  std_state.std_pos_e_m = std_from_var(covariance_.diag[types::P_ID + 1]);
  std_state.std_pos_d_m = std_from_var(covariance_.diag[types::P_ID + 2]);
  std_state.std_vel_n_mps = std_from_var(covariance_.diag[types::V_ID + 0]);
  std_state.std_vel_e_mps = std_from_var(covariance_.diag[types::V_ID + 1]);
  std_state.std_vel_d_mps = std_from_var(covariance_.diag[types::V_ID + 2]);
  std_state.std_roll_deg = std_from_var(covariance_.diag[types::PHI_ID + 0]) * math::rad_to_deg;
  std_state.std_pitch_deg = std_from_var(covariance_.diag[types::PHI_ID + 1]) * math::rad_to_deg;
  std_state.std_yaw_deg = std_from_var(covariance_.diag[types::PHI_ID + 2]) * math::rad_to_deg;
  std_state.std_gyrbias_x_dph = std_from_var(covariance_.diag[types::BG_ID + 0]);
  std_state.std_gyrbias_y_dph = std_from_var(covariance_.diag[types::BG_ID + 1]);
  std_state.std_gyrbias_z_dph = std_from_var(covariance_.diag[types::BG_ID + 2]);
  std_state.std_accbias_x_mgal = std_from_var(covariance_.diag[types::BA_ID + 0]);
  std_state.std_accbias_y_mgal = std_from_var(covariance_.diag[types::BA_ID + 1]);
  std_state.std_accbias_z_mgal = std_from_var(covariance_.diag[types::BA_ID + 2]);
  std_state.std_gyrscale_x_ppm = std_from_var(covariance_.diag[types::SG_ID + 0]);
  std_state.std_gyrscale_y_ppm = std_from_var(covariance_.diag[types::SG_ID + 1]);
  std_state.std_gyrscale_z_ppm = std_from_var(covariance_.diag[types::SG_ID + 2]);
  std_state.std_accscale_x_ppm = std_from_var(covariance_.diag[types::SA_ID + 0]);
  std_state.std_accscale_y_ppm = std_from_var(covariance_.diag[types::SA_ID + 1]);
  std_state.std_accscale_z_ppm = std_from_var(covariance_.diag[types::SA_ID + 2]);
  return std_state;
}

}  // namespace legsa_gins::filter
