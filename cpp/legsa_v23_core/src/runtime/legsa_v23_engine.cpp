#include "legsa_v23_core/runtime/legsa_v23_engine.hpp"

#include "legsa_v23_core/common/constants.hpp"
#include "legsa_v23_core/common/rotation.hpp"
#include "legsa_v23_core/filter/ekf_update.hpp"
#include "legsa_v23_core/filter/ekf_predictor.hpp"
#include "legsa_v23_core/filter/state_feedback.hpp"
#include "legsa_v23_core/mechanization/ins_mechanization.hpp"
#include "legsa_v23_core/updates/yaw_scheme_c.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace legsa_v23_core {

// 中文说明：构造函数只接收 LegSA 自有配置，不读取 final_v23 输出，也不绑定 trace。
LegSAV23Engine::LegSAV23Engine(const GINSOptions& options) : options_(options) {}

// 中文说明：初始化状态容器；N4H4B 初始化预测协方差，量测相关初始化留给 N4H4C。
void LegSAV23Engine::initialize() {
  filter_state_.current_pva = options_.init_state;
  filter_state_.previous_pva = options_.init_state;
  filter_state_.dx = zeroVector21();
  filter_state_.covariance = diagonalMatrix21(1.0e-4);
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    matrix21At(filter_state_.covariance, P_ID + i, P_ID + i) = options_.init_pos_std[i] * options_.init_pos_std[i];
    matrix21At(filter_state_.covariance, V_ID + i, V_ID + i) = options_.init_vel_std[i] * options_.init_vel_std[i];
    matrix21At(filter_state_.covariance, PHI_ID + i, PHI_ID + i) = options_.init_att_std[i] * options_.init_att_std[i];
  }
  continuous_noise_ = diagonalNoiseMatrix(1.0e-6);
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    noiseAt(continuous_noise_, ARW_ID + i, ARW_ID + i) = 1.0e-8;
    noiseAt(continuous_noise_, VRW_ID + i, VRW_ID + i) = 1.0e-6;
    noiseAt(continuous_noise_, BGSTD_ID + i, BGSTD_ID + i) = 1.0e-12;
    noiseAt(continuous_noise_, BASTD_ID + i, BASTD_ID + i) = 1.0e-10;
    noiseAt(continuous_noise_, SGSTD_ID + i, SGSTD_ID + i) = 1.0e-14;
    noiseAt(continuous_noise_, SASTD_ID + i, SASTD_ID + i) = 1.0e-14;
  }
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

// 中文说明：IMU 主循环对齐 KF-GINS-style newImuProcess；N4H4C 打通 GNSS update + feedback。
// 中文说明：res=0 只传播，res=1 先更新再传播，res=2 先传播再更新，res=3 插值后夹在两段传播中更新。
void LegSAV23Engine::newImuProcess() {
  if (!initialized_) {
    initialize();
  }
  while (imu_buffer_.size() >= 2) {
    IMUData imupre = imu_buffer_[0];
    IMUData imucur = imu_buffer_[1];
    filter_state_.previous_pva = filter_state_.current_pva;

    bool consumed_update = false;
    auto runUpdateAndFeedback = [&](const GNSSData& gnss) {
      this->gnssUpdate(gnss);
      if (options_.measurement_update_implemented && options_.state_feedback_implemented) {
        this->stateFeedback ();
      }
      gnss_buffer_.pop_front();
    };
    if (!gnss_buffer_.empty()) {
      const GNSSData gnss = gnss_buffer_.front();
      const int update_status = isToUpdate(imupre.time, imucur.time, gnss.time);
      if (update_status == 1) {
        // 中文说明：GNSS 时间在当前 IMU 区间左端，先执行量测更新和误差反馈，再继续 INS propagation。
        runUpdateAndFeedback(gnss);
        filter_state_.previous_pva = filter_state_.current_pva;
      } else if (update_status == 2) {
        // 中文说明：GNSS 时间在区间右端，先传播到 imucur，再执行量测更新和 stateFeedback。
        insPropagation(imupre, imucur);
        buildFGPhiQd(imucur);
        EKFPredict();
        runUpdateAndFeedback(gnss);
        consumed_update = true;
      } else if (update_status == 3) {
        // 中文说明：GNSS 落在 IMU 区间内时插值，前半段预测、量测更新反馈、后半段继续预测。
        IMUData split_cur = imucur;
        IMUData midimu;
        imuInterpolate(imupre, split_cur, gnss.time, midimu);
        insPropagation(imupre, midimu);
        buildFGPhiQd(midimu);
        EKFPredict();
        runUpdateAndFeedback(gnss);
        insPropagation(midimu, split_cur);
        buildFGPhiQd(split_cur);
        EKFPredict();
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

// 中文说明：返回 propagation foundation 名义状态；不能作为 final_v23 parity 或性能证据。
NavState LegSAV23Engine::getNavState() const { return filter_state_.current_pva; }

// 中文说明：返回 21-state EKF 容器；N4H4B 只有预测传播，无量测更新。
FilterState LegSAV23Engine::getFilterState() const { return filter_state_; }

// 中文说明：返回 manifest 运行证据；包含 N4H4C yaw gate 计数，不包含性能指标。
GINSOptions LegSAV23Engine::getRunOptions() const { return options_; }

// 中文说明：更新时间与 IMU 区间的四态判定；NED/BLH 状态在对应分支中保持 KF-GINS-style 顺序。
int LegSAV23Engine::isToUpdate(double imu_time_1, double imu_time_2, double update_time) const {
  const double eps = 1.0e-10;
  if (update_time <= imu_time_1 + eps) {
    return 1;
  }
  if (update_time < imu_time_2 - eps) {
    return 3;
  }
  if (std::abs(update_time - imu_time_2) <= eps) {
    return 2;
  }
  return 0;
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

// 中文说明：IMU 补偿使用当前 bias/scale；输入是 process_data-compatible FRD 增量，不做二次坐标转换。
void LegSAV23Engine::imuCompensate(IMUData& imu) {
  const double dt = std::max(imu.dt, 1.0e-6);
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    const double gyro_scale = 1.0 + filter_state_.current_pva.gyro_scale[i];
    const double acc_scale = 1.0 + filter_state_.current_pva.acc_scale[i];
    imu.dtheta[i] = imu.dtheta[i] / gyro_scale - filter_state_.current_pva.gyro_bias[i] * dt;
    imu.dvel[i] = imu.dvel[i] / acc_scale - filter_state_.current_pva.acc_bias[i] * dt;
  }
}

// 中文说明：INS propagation 执行 vel/pos/att 机械编排；GNSS update 和 feedback 留给 N4H4C。
void LegSAV23Engine::insPropagation(const IMUData& imupre, const IMUData& imucur) {
  const PVAState pvapre = filter_state_.current_pva;
  PVAState pvacur = pvapre;
  INSMechanization::insMech(pvapre, pvacur, imupre, imucur);
  filter_state_.previous_pva = pvapre;
  filter_state_.current_pva = pvacur;
  current_time_ = imucur.time;
}

// 中文说明：F/G/Phi/Qd 构建只服务 EKF predict；N4H4B 不构建量测 H/R/K。
void LegSAV23Engine::buildFGPhiQd(const IMUData& imucur) {
  last_matrices_ = buildErrorStateMatrices(filter_state_.current_pva, imucur, options_, continuous_noise_);
}

// 中文说明：EKF predict 执行 dx/P 预测传播；N4H4B 不做 GNSS update、EKFUpdate 或 stateFeedback。
void LegSAV23Engine::EKFPredict() {
  legsa_v23_core::EKFPredict(filter_state_, last_matrices_.Phi, last_matrices_.Qd);
}

// 中文说明：GNSS 更新调度入口；N4H4C 顺序构建 position/velocity/yaw 量测并交给 EKFUpdate。
// 中文说明：历史边界保留：TODO(N4H4C): measurement update not implemented in N4H4B.
void LegSAV23Engine::gnssUpdate(const GNSSData& gnss) {
  pending_measurements_.clear();
  if (!options_.measurement_update_implemented) {
    (void)gnss;
    return;
  }
  this->gnssPositionUpdate (gnss);
  if (gnss.has_velocity) {
    this->gnssVelocityUpdate (gnss);
  }
  if (gnss.has_yaw) {
    this->gnssYawUpdate (gnss);
  }
  EKFUpdate ();
}

// 中文说明：位置更新构建 predicted antenna minus observed GNSS 的 NED 残差；输入不是 raw GNSS。
// 中文说明：历史边界保留：TODO(N4H4C): GNSS position update not implemented in N4H4B.
void LegSAV23Engine::gnssPositionUpdate(const GNSSData& gnss) {
  pending_measurements_.push_back(buildGnssPositionMeasurement(filter_state_.current_pva, gnss, options_));
}

// 中文说明：速度更新使用 15 列 .gnss 的 vn/ve/vd，高层状态量测；N4H4C 不实现 raw Doppler。
// 中文说明：历史边界保留：TODO(N4H4C): GNSS velocity update not implemented in N4H4B.
void LegSAV23Engine::gnssVelocityUpdate(const GNSSData& gnss) {
  pending_measurements_.push_back(buildGnssVelocityMeasurement(filter_state_.current_pva, gnss, options_));
}

// 中文说明：yaw 更新采用 scheme_C 规则门控；NORMAL/DOWNWEIGHT/REJECT 只记录求解器量测处理。
// 中文说明：历史边界保留：TODO(N4H4C): GNSS yaw update not implemented in N4H4B.
void LegSAV23Engine::gnssYawUpdate(const GNSSData& gnss) {
  const double pred_yaw_deg = Rotation::wrapAngleDeg(filter_state_.current_pva.euler_rpy_rad[2] * kRadToDeg);
  const double residual_deg = Rotation::wrapAngleDeg(gnss.yaw_deg - pred_yaw_deg);
  const YawSchemeCDecision decision = applyYawSchemeC(residual_deg, gnss.yaw_std_deg);
  if (decision.mode == YawSchemeCMode::NORMAL) {
    ++options_.yaw_normal_count;
  } else if (decision.mode == YawSchemeCMode::DOWNWEIGHT) {
    ++options_.yaw_downweight_count;
  } else {
    ++options_.yaw_reject_count;
  }
  const auto block = buildGnssYawMeasurement(filter_state_.current_pva, gnss, options_);
  if (block.has_value()) {
    pending_measurements_.push_back(block.value());
  }
}

// 中文说明：EKFUpdate wrapper 逐块执行 Joseph form；这里只更新 dx/P，不直接改名义状态。
// 中文说明：历史边界保留：TODO(N4H4C): EKF measurement update not implemented in N4H4B.
void LegSAV23Engine::EKFUpdate() {
  for (const auto& measurement : pending_measurements_) {
    legsa_v23_core::EKFUpdate(filter_state_, measurement);
  }
  pending_measurements_.clear();
}

// 中文说明：stateFeedback 将 dx 反馈到 BLH/NED/姿态/bias/scale；反馈后 dx 清零。
// 中文说明：历史边界保留：TODO(N4H4C): state feedback not implemented in N4H4B.
void LegSAV23Engine::stateFeedback() {
  legsa_v23_core::stateFeedback(filter_state_);
}

// 中文说明：协方差检查保持有限、近似对称、对角非负；不伪造量测约束。
void LegSAV23Engine::checkCov() const {
  for (std::size_t i = 0; i < kStateSize; ++i) {
    const double value = matrix21At(filter_state_.covariance, i, i);
    if (!std::isfinite(value) || value < -kDefaultCovarianceFloor) {
      throw std::runtime_error("LegSAV23Engine covariance check failed");
    }
    for (std::size_t j = i + 1; j < kStateSize; ++j) {
      if (!std::isfinite(matrix21At(filter_state_.covariance, i, j)) ||
          std::abs(matrix21At(filter_state_.covariance, i, j) - matrix21At(filter_state_.covariance, j, i)) >
              1.0e-8) {
        throw std::runtime_error("LegSAV23Engine covariance symmetry check failed");
      }
    }
  }
}

}  // namespace legsa_v23_core
