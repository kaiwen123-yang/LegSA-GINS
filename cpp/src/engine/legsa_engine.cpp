// 中文说明：LegSAEngine 是自主 runtime skeleton；本阶段只保持最小 dry-run 链路，不实现 INS mechanization、EKF、raw Doppler、Go2、weighting 或 FGO。
// English note: comments define module responsibility and safety boundaries only.

#include "legsa_gins/engine/legsa_engine.hpp"

#include <filesystem>
#include <stdexcept>
#include <utility>

#include "legsa_gins/filter/diag_covariance.hpp"
#include "legsa_gins/filter/legsa_filter.hpp"
#include "legsa_gins/io/run_manifest_writer.hpp"
#include "legsa_gins/math/constants.hpp"
#include "legsa_gins/math/rotation.hpp"

namespace legsa_gins::engine {
namespace {

types::NavState navFromFilterState(const types::LegSAFilterState& state) {
  types::NavState nav;
  nav.tow = state.pva.tow;
  nav.lat_deg = state.pva.blh_rad_m.x * math::rad_to_deg;
  nav.lon_deg = state.pva.blh_rad_m.y * math::rad_to_deg;
  nav.height_m = state.pva.blh_rad_m.z;
  nav.vn_mps = state.pva.vel_ned_mps.x;
  nav.ve_mps = state.pva.vel_ned_mps.y;
  nav.vd_mps = state.pva.vel_ned_mps.z;
  nav.roll_deg = state.pva.euler_rad.x * math::rad_to_deg;
  nav.pitch_deg = state.pva.euler_rad.y * math::rad_to_deg;
  nav.yaw_deg = state.pva.euler_rad.z * math::rad_to_deg;
  nav.status = "legsa_filter_core_toy_only";
  nav.source_role = "proposed_filter_core";
  return nav;
}

}  // namespace

LegSAEngine::LegSAEngine(config::RuntimeConfig config) : config_(std::move(config)) {
  applyConfigToRegistry();
}

void LegSAEngine::initialize() {
  const std::filesystem::path output_dir(config_.output_dir);
  // 初始化最小状态容器，保持 skeleton 标记，避免被误读为已验证 solver。
  // Initialize minimal state only; the skeleton status prevents solver overclaiming.
  nav_state_ = types::NavState{};
  nav_state_.status = "cpp_runtime_skeleton_only";
  nav_state_.source_role = "proposed_skeleton";
  std_state_ = types::StdState{};

  nav_writer_ = std::make_unique<io::NavWriter>(output_dir);
  std_writer_ = std::make_unique<io::StdWriter>(output_dir);
  eval_nav_writer_ = std::make_unique<io::EvalNavWriterBridge>(output_dir);
  io::RunManifestWriter::writePlaceholder(config_, registry_, output_dir);
  initialized_ = true;
}

void LegSAEngine::addImuData(const types::ImuSample& imu) { imu_buffer_.push_back(imu); }

void LegSAEngine::addGnssData(const types::GnssNativeMeasurement& gnss) {
  gnss_buffer_.push_back(gnss);
}

void LegSAEngine::processNext() {
  if (!initialized_) {
    throw std::runtime_error("LegSAEngine must be initialized before processing.");
  }
  if (gnss_buffer_.empty()) {
    if (!imu_buffer_.empty()) {
      // 当前不做 INS mechanization，仅保留时间推进合同。
      // No INS mechanization is applied; this only preserves timestamp flow.
      nav_state_.tow = imu_buffer_.front().tow;
      std_state_.tow = nav_state_.tow;
      imu_buffer_.erase(imu_buffer_.begin());
    }
    return;
  }

  const auto gnss = gnss_buffer_.front();
  gnss_buffer_.erase(gnss_buffer_.begin());
  // 最小 receiver-native dry-run：只搬运已有 GNSS 字段，不做 EKF 更新或输出修正。
  // Minimal receiver-native dry-run: copy available GNSS fields without EKF or correction.
  nav_state_.tow = gnss.tow;
  nav_state_.status = "cpp_runtime_skeleton_only";
  nav_state_.source_role = "proposed_skeleton";

  if (gnss.has_position) {
    nav_state_.lat_deg = gnss.lat_deg;
    nav_state_.lon_deg = gnss.lon_deg;
    nav_state_.height_m = gnss.height_m;
  }
  if (gnss.has_velocity) {
    nav_state_.vn_mps = gnss.vn_mps;
    nav_state_.ve_mps = gnss.ve_mps;
    nav_state_.vd_mps = gnss.vd_mps;
  }
  if (gnss.has_yaw) {
    nav_state_.yaw_deg = gnss.yaw_deg;
  }
  std_state_.tow = nav_state_.tow;
}

types::NavState LegSAEngine::getNavState() const { return nav_state_; }

types::StdState LegSAEngine::getStdState() const { return std_state_; }

double LegSAEngine::timestamp() const { return nav_state_.tow; }

void LegSAEngine::writeCurrentOutputs() {
  if (!initialized_ || !nav_writer_ || !std_writer_ || !eval_nav_writer_) {
    throw std::runtime_error("LegSAEngine outputs are not initialized.");
  }
  nav_writer_->write(nav_state_);
  std_writer_->write(std_state_);
  // EVAL_NAV bridge 只服务 evaluator，不回流 solver，也不替代 proposed 输出。
  // EVAL_NAV bridge is evaluator-only and never feeds back into the solver.
  eval_nav_writer_->write(nav_state_);
}

void LegSAEngine::runDryDemo() {
  if (!initialized_) {
    initialize();
  }

  // toy GNSS 样例只用于证明输出文件能写出，不作为轨迹或精度证据。
  // Toy GNSS samples only prove output plumbing, not trajectory quality.
  types::GnssNativeMeasurement first;
  first.tow = 100000.0;
  first.lat_deg = 30.0000001;
  first.lon_deg = 120.0000001;
  first.height_m = 15.0;
  first.vn_mps = 0.10;
  first.ve_mps = 0.20;
  first.vd_mps = -0.05;
  first.yaw_deg = 85.0;
  first.has_position = true;
  first.has_velocity = true;
  first.has_yaw = true;

  types::GnssNativeMeasurement second = first;
  second.tow = 100001.0;
  second.lat_deg = 30.0000011;
  second.lon_deg = 120.0000012;
  second.height_m = 15.1;
  second.vn_mps = 0.12;
  second.ve_mps = 0.22;
  second.vd_mps = -0.04;
  second.yaw_deg = 85.5;

  addGnssData(first);
  processNext();
  writeCurrentOutputs();

  addGnssData(second);
  processNext();
  writeCurrentOutputs();
}

void LegSAEngine::runFilterToyDemo() {
  const std::filesystem::path output_dir(config_.output_dir);

  // N4 toy demo 构造内部 IMU 与 receiver-native 测量，不读取 trace/final_v23/BY2 raw data。
  // The N4 toy demo uses synthetic inputs only and never consumes trace or final_v23 output.
  types::LegSAFilterState initial;
  initial.pva.tow = 100000.0;
  initial.pva.blh_rad_m = {30.0 * math::deg_to_rad, 120.0 * math::deg_to_rad, 15.0};
  initial.pva.vel_ned_mps = {0.10, 0.20, -0.05};
  initial.pva.euler_rad = {0.0, 0.0, 85.0 * math::deg_to_rad};
  initial.pva.qbn = math::eulerRadToQuaternion(
      initial.pva.euler_rad.x, initial.pva.euler_rad.y, initial.pva.euler_rad.z);
  initial.status = "legsa_filter_core_toy_only";

  std::vector<types::LegSAImuSample> imu_samples;
  for (int index = 0; index < 5; ++index) {
    types::LegSAImuSample sample;
    sample.tow = 100000.0 + static_cast<double>(index);
    sample.dt = index == 0 ? 0.0 : 1.0;
    sample.dtheta_rad = {0.0, 0.0, 0.0005};
    sample.dvel_mps = {0.01, 0.00, 0.00};
    imu_samples.push_back(sample);
  }

  std::vector<types::ReceiverNativeMeasurement> receiver_measurements;
  for (int index = 1; index <= 3; ++index) {
    types::ReceiverNativeMeasurement meas;
    meas.tow = 100000.0 + static_cast<double>(index);
    meas.has_position = true;
    meas.has_velocity = true;
    meas.has_heading = true;
    meas.blh_rad_m = {
        (30.0 + 0.000001 * index) * math::deg_to_rad,
        (120.0 + 0.0000015 * index) * math::deg_to_rad,
        15.0 + 0.02 * index,
    };
    meas.pos_std_m = {1.5, 1.5, 2.0};
    meas.vel_ned_mps = {0.10 + 0.01 * index, 0.20 + 0.005 * index, -0.05};
    meas.vel_std_mps = {0.2, 0.2, 0.3};
    meas.yaw_heading_rad = (85.0 + 0.1 * index) * math::deg_to_rad;
    meas.yaw_std_rad = 2.0 * math::deg_to_rad;
    meas.source = "toy_receiver_native";
    receiver_measurements.push_back(meas);
  }

  filter::LegSAFilter filter;
  filter.initialize(initial, filter::makeConservativeDefaultCovariance());
  filter.process(imu_samples, receiver_measurements);

  io::NavWriter nav_writer(output_dir);
  io::StdWriter std_writer(output_dir);
  io::EvalNavWriterBridge eval_writer(output_dir);
  types::StdState std_state = filter.getStdState();
  for (const auto& state : filter.getHistory()) {
    const types::NavState nav_state = navFromFilterState(state);
    std_state.tow = state.pva.tow;
    nav_writer.write(nav_state);
    std_writer.write(std_state);
    eval_writer.write(nav_state);
  }
  io::RunManifestWriter::writeFilterCoreToyManifest(config_, output_dir);
}

void LegSAEngine::applyConfigToRegistry() {
  // ReceiverPosition/Velocity/Heading 是 backbone slot；高级 proposed factor 默认关闭。
  // Receiver slots are backbone placeholders; advanced proposed factors remain disabled by default.
  if (config_.enable_receiver_position) {
    registry_.enable(factors::FactorKind::ReceiverPosition);
  } else {
    registry_.disable(factors::FactorKind::ReceiverPosition);
  }
  if (config_.enable_receiver_velocity) {
    registry_.enable(factors::FactorKind::ReceiverVelocity);
  } else {
    registry_.disable(factors::FactorKind::ReceiverVelocity);
  }
  if (config_.enable_receiver_heading) {
    registry_.enable(factors::FactorKind::ReceiverHeading);
  } else {
    registry_.disable(factors::FactorKind::ReceiverHeading);
  }

  if (config_.enable_raw_doppler) {
    // 注册开关不等于 residual 实现；N4 不启用 raw Doppler 算法。
    // Enabling a registry flag is not a residual implementation; N4 keeps raw Doppler off.
    registry_.enable(factors::FactorKind::RawDoppler);
  }
  if (config_.enable_go2_yawrate_prior) {
    registry_.enable(factors::FactorKind::Go2YawRatePrior);
  }
  if (config_.enable_go2_attitude_prior) {
    registry_.enable(factors::FactorKind::Go2AttitudePrior);
  }
  if (config_.enable_support_integrity) {
    registry_.enable(factors::FactorKind::SupportIntegrity);
  }
  if (config_.enable_source_aware_weighting) {
    registry_.enable(factors::FactorKind::SourceAwareWeighting);
  }
  if (config_.enable_fixed_lag_smoother) {
    registry_.enable(factors::FactorKind::FixedLagSmoother);
  }
}

}  // namespace legsa_gins::engine
