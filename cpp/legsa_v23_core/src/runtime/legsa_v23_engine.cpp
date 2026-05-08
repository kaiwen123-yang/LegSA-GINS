#include "legsa_v23_core/runtime/legsa_v23_engine.hpp"

#include "legsa_v23_core/common/constants.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace legsa_v23_core {

// 中文说明：构造函数只接收 LegSA 自有配置，不读取 final_v23 输出，也不绑定 trace。
LegSAV23Engine::LegSAV23Engine(const GINSOptions& options) : options_(options) {}

// 中文说明：初始化状态容器；N4H4A 是 skeleton，完整初始对准和协方差将在 N4H4B/C 补齐。
void LegSAV23Engine::initialize() {
  filter_state_.current_pva = options_.init_state;
  filter_state_.previous_pva = options_.init_state;
  filter_state_.dx = zeroVector21();
  filter_state_.covariance = diagonalMatrix21(1.0);
  current_time_ = options_.start_time;
  initialized_ = true;
}

// 中文说明：加入 IMU 增量并保持时间单调；可选补偿目前只走占位 hook。
void LegSAV23Engine::addImuData(const IMUData& imu, bool compensate) {
  IMUData copied = imu;
  if (!imu_buffer_.empty() && copied.time <= imu_buffer_.back().time) {
    throw std::runtime_error("LegSAV23Engine IMU time is not monotonic");
  }
  if (compensate) {
    imuCompensate(copied);
  }
  imu_buffer_.push_back(copied);
}

// 中文说明：加入 GNSS 高层状态输入；无效样本直接丢弃，避免产生假更新。
void LegSAV23Engine::addGnssData(const GNSSData& gnss) {
  if (!gnss.isvalid) {
    return;
  }
  if (!gnss_buffer_.empty() && gnss.time <= gnss_buffer_.back().time) {
    throw std::runtime_error("LegSAV23Engine GNSS time is not monotonic");
  }
  gnss_buffer_.push_back(gnss);
}

// 中文说明：IMU 主循环框架对齐 KF-GINS-style newImuProcess；N4H4A 只验证链路和 hook。
void LegSAV23Engine::newImuProcess() {
  if (!initialized_) {
    initialize();
  }
  while (imu_buffer_.size() >= 2) {
    IMUData imupre = imu_buffer_[0];
    IMUData imucur = imu_buffer_[1];
    filter_state_.previous_pva = filter_state_.current_pva;

    bool consumed_update = false;
    if (!gnss_buffer_.empty()) {
      const GNSSData gnss = gnss_buffer_.front();
      const int update_status = isToUpdate(imupre.time, imucur.time, gnss.time);
      if (update_status < 0) {
        gnssUpdate(gnss);
        EKFUpdate();
        stateFeedback();
        gnss_buffer_.pop_front();
        consumed_update = true;
      } else if (update_status == 0) {
        IMUData split_cur = imucur;
        IMUData midimu;
        imuInterpolate(imupre, split_cur, gnss.time, midimu);
        insPropagation(imupre, midimu);
        buildFGPhiQd(midimu);
        EKFPredict();
        gnssUpdate(gnss);
        EKFUpdate();
        stateFeedback();
        insPropagation(midimu, split_cur);
        buildFGPhiQd(split_cur);
        EKFPredict();
        gnss_buffer_.pop_front();
        consumed_update = true;
      }
    }

    if (!consumed_update) {
      insPropagation(imupre, imucur);
      buildFGPhiQd(imucur);
      EKFPredict();
    }
    checkCov();
    imu_buffer_.pop_front();
  }
}

// 中文说明：返回当前时间戳，单位秒；toy-run 用它写 NAV/STD/EVAL_NAV。
double LegSAV23Engine::timestamp() const { return current_time_; }

// 中文说明：返回 skeleton 名义状态；不能作为 final_v23 parity 或性能证据。
NavState LegSAV23Engine::getNavState() const { return filter_state_.current_pva; }

// 中文说明：返回 21-state EKF 容器；N4H4A 只有占位 dx/P。
FilterState LegSAV23Engine::getFilterState() const { return filter_state_; }

// 中文说明：更新时间早于、位于、晚于 IMU 区间的三态判定。
int LegSAV23Engine::isToUpdate(double imu_time_1, double imu_time_2, double update_time) const {
  if (update_time <= imu_time_1) {
    return -1;
  }
  if (update_time < imu_time_2) {
    return 0;
  }
  return 1;
}

// 中文说明：按时间比例切分 IMU 增量；这是框架级插值，后续会补齐 KF-GINS 等价细节。
void LegSAV23Engine::imuInterpolate(const IMUData& imu1, IMUData& imu2, double timestamp, IMUData& midimu) {
  const double interval = imu2.time - imu1.time;
  if (interval <= 0.0 || timestamp <= imu1.time || timestamp >= imu2.time) {
    midimu = imu2;
    return;
  }

  const double ratio = (timestamp - imu1.time) / interval;
  midimu = imu2;
  midimu.time = timestamp;
  midimu.dt = timestamp - imu1.time;
  imu2.dt = imu2.time - timestamp;
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    const double original_dtheta = imu2.dtheta[i];
    const double original_dvel = imu2.dvel[i];
    midimu.dtheta[i] = original_dtheta * ratio;
    midimu.dvel[i] = original_dvel * ratio;
    imu2.dtheta[i] = original_dtheta - midimu.dtheta[i];
    imu2.dvel[i] = original_dvel - midimu.dvel[i];
  }
}

// 中文说明：IMU 补偿 hook 暂不改变输入；N4H4B/C 将使用 bias/scale 完成补偿。
void LegSAV23Engine::imuCompensate(IMUData& imu) {
  (void)imu;
}

// 中文说明：INS propagation hook 只推进时间和保留状态；完整 mechanization 后续实现。
void LegSAV23Engine::insPropagation(const IMUData& imupre, const IMUData& imucur) {
  (void)imupre;
  current_time_ = imucur.time;
}

// 中文说明：F/G/Phi/Qd 构建 hook；N4H4A 暂保持单位协方差占位，不进行完整离散化。
void LegSAV23Engine::buildFGPhiQd(const IMUData& imucur) {
  (void)imucur;
}

// 中文说明：EKF predict hook；N4H4A 不传播 P，只保留主框架入口。
void LegSAV23Engine::EKFPredict() {}

// 中文说明：GNSS 更新调度入口；三个子更新仍是 skeleton，不做 factor stacking。
void LegSAV23Engine::gnssUpdate(const GNSSData& gnss) {
  gnssPositionUpdate(gnss);
  if (gnss.has_velocity) {
    gnssVelocityUpdate(gnss);
  }
  if (gnss.has_yaw) {
    gnssYawUpdate(gnss);
  }
}

// 中文说明：位置更新 hook 仅保留 BLH 残差入口，不把观测直接替换成输出状态。
void LegSAV23Engine::gnssPositionUpdate(const GNSSData& gnss) {
  (void)gnss;
  filter_state_.dx[P_ID] = 0.0;
}

// 中文说明：速度更新 hook 仅保留 NED 速度入口，N4H4A 不做 Kalman 增益计算。
void LegSAV23Engine::gnssVelocityUpdate(const GNSSData& gnss) {
  (void)gnss;
  filter_state_.dx[V_ID] = 0.0;
}

// 中文说明：yaw 更新 hook 只保留 deg 输入边界，N4H4A 不声明 yaw parity。
void LegSAV23Engine::gnssYawUpdate(const GNSSData& gnss) {
  (void)gnss;
  filter_state_.dx[PHI_ID + 2] = 0.0;
}

// 中文说明：EKF update hook 暂不修改 dx/P；N4H4C 将填充 H/R/K 和残差更新。
void LegSAV23Engine::EKFUpdate() {}

// 中文说明：状态反馈 hook 暂不改写名义状态，避免 output-only correction。
void LegSAV23Engine::stateFeedback() {
  filter_state_.dx = zeroVector21();
}

// 中文说明：协方差检查保持最小下限；后续阶段补充对称化和正定性修复。
void LegSAV23Engine::checkCov() const {
  for (std::size_t i = 0; i < kStateSize; ++i) {
    const double value = matrix21At(filter_state_.covariance, i, i);
    if (!std::isfinite(value) || value < kDefaultCovarianceFloor) {
      throw std::runtime_error("LegSAV23Engine covariance check failed");
    }
  }
}

}  // namespace legsa_v23_core
