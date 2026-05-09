// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"

#include "legsa_v23_port_core/kf_gins/insmech.hpp"

#include <algorithm>
#include <utility>

namespace legsa_v23_port_core {

// 中文说明：构造 source-backed engine skeleton；完整 KF-GINS GIEngine port 留给 R2。
GIEngine::GIEngine(PortOptions options)
    : options_(std::move(options)),
      covariance_(makeCovarianceDiagonal(options_.init_cov_diag)),
      dx_(kErrorStateSize, 0.0) {}

// 中文说明：初始化只使用 config/toy 初值，不读取 final_v23 输出。
void GIEngine::initialize(const NavState& initial_state) {
  state_ = initial_state;
  initialized_ = true;
}

// 中文说明：IMU 缓冲合同保留 addImuData 函数名，后续对齐 reference buffering。
void GIEngine::addImuData(const ImuData& imu) {
  imu_buffer_.push_back(imu);
}

// 中文说明：GNSS 缓冲合同保留 addGnssData 函数名，R1 不实现 raw GNSS 因子。
void GIEngine::addGnssData(const GnssData& gnss) {
  gnss_buffer_.push_back(gnss);
}

// 中文说明：R1 toy 中有 GNSS 即返回 3，真实 isToUpdate timing parity 留给 R2。
int GIEngine::isToUpdate() const {
  if (!gnss_buffer_.empty() && imu_buffer_.size() >= 2) {
    return 3;
  }
  return 0;
}

// 中文说明：线性插值仅用于函数合同占位，不能作为 clean parity 证据。
ImuData GIEngine::imuInterpolate(const ImuData& previous, const ImuData& current, double time) const {
  const double denom = current.time - previous.time;
  const double ratio = denom > 0.0 ? (time - previous.time) / denom : 0.0;
  ImuData mid = current;
  mid.time = time;
  mid.dt = time - previous.time;
  mid.dtheta = add(previous.dtheta, scale(add(current.dtheta, scale(previous.dtheta, -1.0)), ratio));
  mid.dvel = add(previous.dvel, scale(add(current.dvel, scale(previous.dvel, -1.0)), ratio));
  return mid;
}

// 中文说明：R1 不反馈 IMU error states，补偿函数保持恒等并标记 TODO_R2_SOURCE_PORT。
ImuData GIEngine::imuCompensate(const ImuData& imu) const {
  return imu;
}

// 中文说明：预测传播调用 INSMech skeleton；完整 F/G/Phi/Qd 和 mechanization parity 留给 R2。
void GIEngine::insPropagation() {
  if (!initialized_ || imu_buffer_.empty()) {
    return;
  }
  const ImuData compensated = imuCompensate(imu_buffer_.back());
  state_ = INSMech::propagateOneStep(state_, compensated);
  ++propagation_count_;
}

// 中文说明：GNSS update 仅增加 toy 计数，不进行真实 measurement update 或性能宣称。
void GIEngine::gnssUpdate() {
  if (!gnss_buffer_.empty()) {
    ++update_count_;
    gnss_buffer_.erase(gnss_buffer_.begin());
  }
}

// 中文说明：R1 EKFPredict 只轻微扩展对角协方差；完整 source-backed P/Q parity 留给 R2。
void GIEngine::EKFPredict() {
  for (double& value : covariance_) {
    value += 1.0e-6;
  }
}

// 中文说明：R1 EKFUpdate 不做正式量测更新，避免伪造 clean replay parity。
void GIEngine::EKFUpdate() {
  std::fill(dx_.begin(), dx_.end(), 0.0);
}

// 中文说明：R1 stateFeedback 只清零误差状态；完整反馈移植留给 R2。
void GIEngine::stateFeedback() {
  std::fill(dx_.begin(), dx_.end(), 0.0);
}

// 中文说明：newImuProcess 保留 KF-GINS 风格入口，但 R1 只跑 toy skeleton 分支。
void GIEngine::newImuProcess() {
  if (!initialized_ || imu_buffer_.empty()) {
    return;
  }
  insPropagation();
  EKFPredict();
  if (isToUpdate() != 0) {
    gnssUpdate();
    EKFUpdate();
    stateFeedback();
  }
}

// 中文说明：协方差检查只确认对角非负，R1 不声明统计一致性。
bool GIEngine::checkCov() const {
  return std::all_of(covariance_.begin(), covariance_.end(), [](double value) { return value >= 0.0; });
}

const NavState& GIEngine::navState() const {
  return state_;
}

const std::vector<double>& GIEngine::getCovariance() const {
  return covariance_;
}

std::size_t GIEngine::propagationCount() const {
  return propagation_count_;
}

std::size_t GIEngine::updateCount() const {
  return update_count_;
}

}  // namespace legsa_v23_port_core
