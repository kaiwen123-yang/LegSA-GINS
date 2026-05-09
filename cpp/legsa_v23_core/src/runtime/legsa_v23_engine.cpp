#include "legsa_v23_core/runtime/legsa_v23_engine.hpp"

#include "legsa_v23_core/common/constants.hpp"
#include "legsa_v23_core/common/earth.hpp"
#include "legsa_v23_core/common/rotation.hpp"
#include "legsa_v23_core/filter/ekf_update.hpp"
#include "legsa_v23_core/filter/ekf_predictor.hpp"
#include "legsa_v23_core/filter/state_feedback.hpp"
#include "legsa_v23_core/mechanization/ins_mechanization.hpp"
#include "legsa_v23_core/updates/yaw_scheme_c.hpp"

#include <algorithm>
#include <cmath>
#include <initializer_list>
#include <stdexcept>

namespace legsa_v23_core {
namespace {

// 中文说明：三维向量范数用于诊断残差/IMU 增量大小，不参与滤波更新。
double norm3(const Vector3& values) {
  double sum = 0.0;
  for (double value : values) {
    sum += value * value;
  }
  return std::sqrt(sum);
}

// 中文说明：21 维 dx 范数仅用于 first-epoch/update 诊断，不改变误差状态。
double norm21(const Vector21& values) {
  double sum = 0.0;
  for (double value : values) {
    sum += value * value;
  }
  return std::sqrt(sum);
}

// 中文说明：协方差对角统计用于判断塌缩/爆炸，不伪造 covariance。
void covarianceStats(const Matrix21& covariance, double& trace, double& min_diag, double& max_diag) {
  trace = 0.0;
  min_diag = matrix21At(covariance, 0, 0);
  max_diag = matrix21At(covariance, 0, 0);
  for (std::size_t i = 0; i < kStateSize; ++i) {
    const double value = matrix21At(covariance, i, i);
    trace += value;
    min_diag = std::min(min_diag, value);
    max_diag = std::max(max_diag, value);
  }
}

// 中文说明：量测矩阵局部范数只写入 D4 shadow/gain 诊断，不参与 EKF 数值。
double hBlockNorm(const MeasurementBlock& block, std::size_t col_begin, std::size_t col_end) {
  double sum = 0.0;
  for (std::size_t row = 0; row < block.rows; ++row) {
    for (std::size_t col = col_begin; col < col_end; ++col) {
      const double value = measurementHAt(block, row, col);
      sum += value * value;
    }
  }
  return std::sqrt(sum);
}

// 中文说明：诊断用增益近似只帮助定位 K/dx 尖峰；真实 EKFUpdate 仍使用 filter/ekf_update.cpp。
double diagnosticGainProxy(double dx_norm, double residual_norm) {
  if (residual_norm <= 1.0e-12) {
    return 0.0;
  }
  return dx_norm / residual_norm;
}

// 中文说明：D5 block trace 使用 21 维向量差分定位单块量测的 dx 贡献。
Vector21 vectorDiff(const Vector21& after, const Vector21& before) {
  Vector21 diff{};
  diff.fill(0.0);
  for (std::size_t i = 0; i < kStateSize; ++i) {
    diff[i] = after[i] - before[i];
  }
  return diff;
}

// 中文说明：从 21 维误差状态取三维子块范数，用于 position/velocity/attitude 贡献诊断。
double subVectorNorm3(const Vector21& values, std::size_t offset) {
  Vector3 local = zeroVector3();
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    local[i] = values[offset + i];
  }
  return norm3(local);
}

// 中文说明：从 PVAState 取 IMU bias/scale 子块范数，用于 D6 feedback trace。
double pvaVectorNorm3(const PVAState& state, const std::string& name) {
  if (name == "gyrbias") {
    return norm3(state.gyro_bias);
  }
  if (name == "accbias") {
    return norm3(state.acc_bias);
  }
  if (name == "gyrscale") {
    return norm3(state.gyro_scale);
  }
  if (name == "accscale") {
    return norm3(state.acc_scale);
  }
  return 0.0;
}

bool feedbackModeIs(const GINSOptions& options, const std::initializer_list<const char*> names) {
  if (!options.diagnostic_mode) {
    return false;
  }
  for (const char* name : names) {
    if (options.diagnostic_feedback_mode == name) {
      return true;
    }
  }
  return false;
}

bool posVelFeedbackEnabled(const GINSOptions& options) {
  return !feedbackModeIs(options, {"attitude_only"});
}

bool attitudeFeedbackEnabled(const GINSOptions& options) {
  return !feedbackModeIs(options,
                         {"pos_vel_only", "no_attitude_feedback", "pos_vel_bias_scale_only",
                          "no_attitude_no_bias_scale"});
}

bool biasScaleFeedbackEnabled(const GINSOptions& options) {
  return !feedbackModeIs(options,
                         {"pos_vel_only", "attitude_only", "pos_vel_attitude_only", "no_bias_scale_feedback",
                          "no_imu_error_feedback", "freeze_imu_error_states",
                          "no_imu_error_feedback_but_keep_attitude", "no_attitude_no_bias_scale"});
}

// 中文说明：协方差分块 Frobenius 范数只用于 D6 cross-covariance 诊断。
double covarianceBlockNorm(const Matrix21& covariance, std::size_t row_begin, std::size_t row_count,
                           std::size_t col_begin, std::size_t col_count) {
  double sum = 0.0;
  for (std::size_t row = 0; row < row_count; ++row) {
    for (std::size_t col = 0; col < col_count; ++col) {
      const double value = matrix21At(covariance, row_begin + row, col_begin + col);
      sum += value * value;
    }
  }
  return std::sqrt(sum);
}

double covarianceTrace3(const Matrix21& covariance, std::size_t offset) {
  double trace = 0.0;
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    trace += matrix21At(covariance, offset + i, offset + i);
  }
  return trace;
}

// 中文说明：量测残差/H/R 范数仅用于 D5 block contribution，不进入 EKF 计算。
double measurementResidualNorm(const MeasurementBlock& block) {
  double sum = 0.0;
  for (double value : block.residual) {
    sum += value * value;
  }
  return std::sqrt(sum);
}

double measurementHNorm(const MeasurementBlock& block) {
  double sum = 0.0;
  for (double value : block.H) {
    sum += value * value;
  }
  return std::sqrt(sum);
}

double measurementRTrace(const MeasurementBlock& block) {
  double trace = 0.0;
  for (std::size_t i = 0; i < block.rows; ++i) {
    trace += measurementRAt(block, i, i);
  }
  return trace;
}

// 中文说明：D5 condition estimate 用 R 对角最大/最小近似 S 条件数，避免引入重型矩阵工具。
double measurementConditionEstimate(const MeasurementBlock& block) {
  if (block.rows == 0) {
    return 1.0;
  }
  double min_diag = std::abs(measurementRAt(block, 0, 0));
  double max_diag = min_diag;
  for (std::size_t i = 0; i < block.rows; ++i) {
    const double value = std::abs(measurementRAt(block, i, i));
    min_diag = std::min(min_diag, value);
    max_diag = std::max(max_diag, value);
  }
  return max_diag / std::max(min_diag, 1.0e-18);
}

// 中文说明：D2 yaw residual variant 必须同时影响 yaw gate 计数和 MeasurementBlock，保证诊断记录自洽。
double diagnosticYawResidualDeg(const GINSOptions& options, double obs_yaw_deg, double pred_yaw_deg) {
  if (options.diagnostic_mode && options.diagnostic_model_variant == "yaw_residual_sign_flip") {
    return Rotation::wrapAngleDeg(pred_yaw_deg - obs_yaw_deg);
  }
  return Rotation::wrapAngleDeg(obs_yaw_deg - pred_yaw_deg);
}

// 中文说明：D5 update-block mode 是 diagnostic-only 开关，默认 all 不改变 baseline。
bool updateBlockAllowed(const GINSOptions& options, const std::string& block_name) {
  if (!options.diagnostic_mode) {
    return true;
  }
  const std::string mode = options.diagnostic_update_block_mode;
  if (mode == "all") {
    return true;
  }
  if (mode == "position_only") {
    return block_name == "position";
  }
  if (mode == "velocity_only") {
    return block_name == "velocity";
  }
  if (mode == "yaw_only") {
    return block_name == "yaw";
  }
  if (mode == "position_velocity") {
    return block_name == "position" || block_name == "velocity";
  }
  if (mode == "position_yaw") {
    return block_name == "position" || block_name == "yaw";
  }
  if (mode == "velocity_yaw") {
    return block_name == "velocity" || block_name == "yaw";
  }
  if (mode == "no_yaw") {
    return block_name != "yaw";
  }
  if (mode == "no_velocity") {
    return block_name != "velocity";
  }
  if (mode == "no_position") {
    return block_name != "position";
  }
  return true;
}

// 中文说明：D5 covariance mode 只在诊断中放大量测 R，用于判断 K/dx 是否由噪声尺度驱动。
void applyDiagnosticCovarianceMode(const GINSOptions& options, MeasurementBlock& measurement) {
  if (!options.diagnostic_mode) {
    return;
  }
  double scale = 1.0;
  const std::string mode = options.diagnostic_covariance_mode;
  if (mode == "inflate_measurement_R_10x") {
    scale = 10.0;
  } else if (mode == "inflate_yaw_R_10x" && measurement.name == "gnss_yaw") {
    scale = 10.0;
  } else if (mode == "inflate_position_R_10x" && measurement.name == "gnss_position") {
    scale = 10.0;
  } else if (mode == "inflate_velocity_R_10x" && measurement.name == "gnss_velocity") {
    scale = 10.0;
  }
  if (scale != 1.0) {
    for (double& value : measurement.R) {
      value *= scale;
    }
  }
}

}  // namespace

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
  if (options_.diagnostic_mode && options_.diagnostic_covariance_mode == "inflate_attitude_10x") {
    // 中文说明：D5 诊断：仅放大初始姿态协方差 10 倍，观察 K/dx 敏感性，不作为调参结果。
    for (std::size_t i = 0; i < kVector3Size; ++i) {
      matrix21At(filter_state_.covariance, PHI_ID + i, PHI_ID + i) *= 10.0;
    }
  } else if (options_.diagnostic_mode && options_.diagnostic_covariance_mode == "inflate_attitude_100x") {
    // 中文说明：D5 诊断：仅放大初始姿态协方差 100 倍，定位 covariance/gain 尺度问题。
    for (std::size_t i = 0; i < kVector3Size; ++i) {
      matrix21At(filter_state_.covariance, PHI_ID + i, PHI_ID + i) *= 100.0;
    }
  }
  if (options_.diagnostic_mode) {
    double bias_scale_p_scale = 1.0;
    if (options_.diagnostic_covariance_mode == "shrink_bias_scale_P_10x") {
      bias_scale_p_scale = 0.1;
    } else if (options_.diagnostic_covariance_mode == "shrink_bias_scale_P_100x") {
      bias_scale_p_scale = 0.01;
    } else if (options_.diagnostic_covariance_mode == "inflate_bias_scale_P_10x") {
      bias_scale_p_scale = 10.0;
    } else if (options_.diagnostic_covariance_mode == "inflate_bias_scale_P_100x") {
      bias_scale_p_scale = 100.0;
    }
    if (bias_scale_p_scale != 1.0) {
      // 中文说明：D6 诊断：只缩放 bias/scale 初始 P，用于单位审计，不是调参结果。
      for (std::size_t offset : {BG_ID, BA_ID, SG_ID, SA_ID}) {
        for (std::size_t i = 0; i < kVector3Size; ++i) {
          matrix21At(filter_state_.covariance, offset + i, offset + i) *= bias_scale_p_scale;
        }
      }
    }
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
  if (options_.diagnostic_mode && options_.diagnostic_covariance_mode == "zero_bias_scale_process_noise") {
    // 中文说明：D6 诊断：临时冻结 bias/scale 过程噪声，判断 Qc 单位/耦合是否驱动发散。
    for (std::size_t i = 0; i < kVector3Size; ++i) {
      noiseAt(continuous_noise_, BGSTD_ID + i, BGSTD_ID + i) = 0.0;
      noiseAt(continuous_noise_, BASTD_ID + i, BASTD_ID + i) = 0.0;
      noiseAt(continuous_noise_, SGSTD_ID + i, SGSTD_ID + i) = 0.0;
      noiseAt(continuous_noise_, SASTD_ID + i, SASTD_ID + i) = 0.0;
    }
  } else if (options_.diagnostic_mode &&
             options_.diagnostic_covariance_mode == "inflate_bias_scale_process_noise_10x") {
    // 中文说明：D6 诊断：只放大 bias/scale 过程噪声 10 倍，结果不能作为性能声明。
    for (std::size_t i = 0; i < kVector3Size; ++i) {
      noiseAt(continuous_noise_, BGSTD_ID + i, BGSTD_ID + i) *= 10.0;
      noiseAt(continuous_noise_, BASTD_ID + i, BASTD_ID + i) *= 10.0;
      noiseAt(continuous_noise_, SGSTD_ID + i, SGSTD_ID + i) *= 10.0;
      noiseAt(continuous_noise_, SASTD_ID + i, SASTD_ID + i) *= 10.0;
    }
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
    auto runUpdateAndFeedback = [&](const GNSSData& gnss, int update_status, double imu_pre_time, double imu_cur_time) {
      if (options_.diagnostic_mode) {
        double unused_max_diag = 0.0;
        diagnostic_pre_dx_norm_ = norm21(filter_state_.dx);
        covarianceStats(filter_state_.covariance, diagnostic_pre_cov_trace_, diagnostic_pre_cov_min_diag_,
                        unused_max_diag);
      }
      this->gnssUpdate(gnss);
      if (options_.diagnostic_mode) {
        this->recordDiagnosticUpdate(gnss, update_status, imu_pre_time, imu_cur_time,
                                     options_.measurement_update_implemented &&
                                         !options_.disable_measurement_update);
      }
      if (options_.measurement_update_implemented && options_.state_feedback_implemented &&
          !options_.disable_measurement_update && !options_.disable_state_feedback) {
        if (options_.diagnostic_mode) {
          this->markLatestDiagnosticFeedbackApplied();
        }
        this->stateFeedback();
      }
      gnss_buffer_.pop_front();
    };
    if (!gnss_buffer_.empty()) {
      const GNSSData gnss = gnss_buffer_.front();
      const int update_status = isToUpdate(imupre.time, imucur.time, gnss.time);
      if (update_status == 1) {
        // 中文说明：GNSS 时间在当前 IMU 区间左端，先执行量测更新和误差反馈，再继续 INS propagation。
        runUpdateAndFeedback(gnss, update_status, imupre.time, imucur.time);
        filter_state_.previous_pva = filter_state_.current_pva;
      } else if (update_status == 2) {
        // 中文说明：GNSS 时间在区间右端，先传播到 imucur，再执行量测更新和 stateFeedback。
        insPropagation(imupre, imucur);
        buildFGPhiQd(imucur);
        EKFPredict();
        runUpdateAndFeedback(gnss, update_status, imupre.time, imucur.time);
        consumed_update = true;
      } else if (update_status == 3) {
        // 中文说明：GNSS 落在 IMU 区间内时插值，前半段预测、量测更新反馈、后半段继续预测。
        IMUData split_cur = imucur;
        IMUData midimu;
        imuInterpolate(imupre, split_cur, gnss.time, midimu);
        insPropagation(imupre, midimu);
        buildFGPhiQd(midimu);
        EKFPredict();
        runUpdateAndFeedback(gnss, update_status, imupre.time, imucur.time);
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

// 中文说明：返回前若干 GNSS 更新诊断记录；diagnostic-only，不作为性能依据。
const std::vector<DiagnosticUpdateRecord>& LegSAV23Engine::getDiagnosticUpdateRecords() const {
  return diagnostic_updates_;
}

// 中文说明：返回前若干传播诊断记录；diagnostic-only，不作为性能依据。
const std::vector<DiagnosticPropagationRecord>& LegSAV23Engine::getDiagnosticPropagationRecords() const {
  return diagnostic_propagations_;
}

const std::vector<DiagnosticUpdateBlockRecord>& LegSAV23Engine::getDiagnosticUpdateBlockRecords() const {
  return diagnostic_update_blocks_;
}

const std::vector<DiagnosticFeedbackDeltaRecord>& LegSAV23Engine::getDiagnosticFeedbackDeltaRecords() const {
  return diagnostic_feedback_deltas_;
}

const std::vector<DiagnosticCovarianceRecord>& LegSAV23Engine::getDiagnosticCovarianceRecords() const {
  return diagnostic_covariances_;
}

const std::vector<DiagnosticImuCompensationRecord>& LegSAV23Engine::getDiagnosticImuCompensationRecords() const {
  return diagnostic_imu_compensations_;
}

const std::vector<DiagnosticImuErrorFeedbackRecord>& LegSAV23Engine::getDiagnosticImuErrorFeedbackRecords() const {
  return diagnostic_imu_error_feedbacks_;
}

const std::vector<DiagnosticCrossCovarianceRecord>& LegSAV23Engine::getDiagnosticCrossCovarianceRecords() const {
  return diagnostic_cross_covariances_;
}

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
  const IMUData before = imu;
  const double dt = std::max(imu.dt, 1.0e-6);
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    const double gyro_scale = 1.0 + filter_state_.current_pva.gyro_scale[i];
    const double acc_scale = 1.0 + filter_state_.current_pva.acc_scale[i];
    imu.dtheta[i] = imu.dtheta[i] / gyro_scale - filter_state_.current_pva.gyro_bias[i] * dt;
    imu.dvel[i] = imu.dvel[i] / acc_scale - filter_state_.current_pva.acc_bias[i] * dt;
  }
  ++imu_compensation_counts_[imu.time];
  recordDiagnosticImuCompensation(before, imu, true, false, true);
}

// 中文说明：INS propagation 执行 vel/pos/att 机械编排；GNSS update 和 feedback 留给 N4H4C。
void LegSAV23Engine::insPropagation(const IMUData& imupre, const IMUData& imucur) {
  const PVAState pvapre = filter_state_.current_pva;
  PVAState pvacur = pvapre;
  INSMechanization::insMech(pvapre, pvacur, imupre, imucur);
  filter_state_.previous_pva = pvapre;
  filter_state_.current_pva = pvacur;
  current_time_ = imucur.time;
  ++options_.propagation_count;
  recordDiagnosticPropagation(imupre, imucur);
  recordDiagnosticImuCompensation(imucur, imucur, false, imu_compensation_counts_[imupre.time] > 0,
                                  imu_compensation_counts_[imucur.time] > 0);
}

// 中文说明：F/G/Phi/Qd 构建只服务 EKF predict；N4H4B 不构建量测 H/R/K。
void LegSAV23Engine::buildFGPhiQd(const IMUData& imucur) {
  last_matrices_ = buildErrorStateMatrices(filter_state_.current_pva, imucur, options_, continuous_noise_);
}

// 中文说明：EKF predict 执行 dx/P 预测传播；N4H4B 不做 GNSS update、EKFUpdate 或 stateFeedback。
void LegSAV23Engine::EKFPredict() {
  legsa_v23_core::EKFPredict(filter_state_, last_matrices_.Phi, last_matrices_.Qd);
  applyDiagnosticCovariancePostProcess();
  recordDiagnosticCovariance("predict");
  recordDiagnosticCrossCovariance("predict");
}

// 中文说明：GNSS 更新调度入口；N4H4C 顺序构建 position/velocity/yaw 量测并交给 EKFUpdate。
// 中文说明：历史边界保留：TODO(N4H4C): measurement update not implemented in N4H4B.
void LegSAV23Engine::gnssUpdate(const GNSSData& gnss) {
  pending_measurements_.clear();
  if (options_.diagnostic_mode) {
    diagnostic_current_update_index_ = static_cast<int>(diagnostic_updates_.size()) + 1;
    diagnostic_current_gnss_time_ = gnss.time;
    diagnostic_current_yaw_mode_ = "NONE";
  }
  if (!options_.measurement_update_implemented || options_.disable_measurement_update) {
    (void)gnss;
    return;
  }
  ++options_.measurement_update_count;
  if (!options_.disable_position_update && updateBlockAllowed(options_, "position")) {
    this->gnssPositionUpdate(gnss);
  }
  if (gnss.has_velocity && !options_.disable_velocity_update && updateBlockAllowed(options_, "velocity")) {
    this->gnssVelocityUpdate(gnss);
  }
  if (gnss.has_yaw && !options_.disable_yaw_update && updateBlockAllowed(options_, "yaw")) {
    this->gnssYawUpdate(gnss);
  }
  EKFUpdate();
}

// 中文说明：位置更新构建 predicted antenna minus observed GNSS 的 NED 残差；输入不是 raw GNSS。
// 中文说明：历史边界保留：TODO(N4H4C): GNSS position update not implemented in N4H4B.
void LegSAV23Engine::gnssPositionUpdate(const GNSSData& gnss) {
  ++options_.position_update_count;
  pending_measurements_.push_back(buildGnssPositionMeasurement(filter_state_.current_pva, gnss, options_));
}

// 中文说明：速度更新使用 15 列 .gnss 的 vn/ve/vd，高层状态量测；N4H4C 不实现 raw Doppler。
// 中文说明：历史边界保留：TODO(N4H4C): GNSS velocity update not implemented in N4H4B.
void LegSAV23Engine::gnssVelocityUpdate(const GNSSData& gnss) {
  ++options_.velocity_update_count;
  pending_measurements_.push_back(buildGnssVelocityMeasurement(filter_state_.current_pva, gnss, options_));
}

// 中文说明：yaw 更新采用 scheme_C 规则门控；NORMAL/DOWNWEIGHT/REJECT 只记录求解器量测处理。
// 中文说明：历史边界保留：TODO(N4H4C): GNSS yaw update not implemented in N4H4B.
void LegSAV23Engine::gnssYawUpdate(const GNSSData& gnss) {
  ++options_.yaw_update_count;
  const double pred_yaw_deg = Rotation::wrapAngleDeg(filter_state_.current_pva.euler_rpy_rad[2] * kRadToDeg);
  const double residual_deg = diagnosticYawResidualDeg(options_, gnss.yaw_deg, pred_yaw_deg);
  const YawSchemeCDecision decision = applyYawSchemeC(residual_deg, gnss.yaw_std_deg);
  if (decision.mode == YawSchemeCMode::NORMAL) {
    ++options_.yaw_normal_count;
  } else if (decision.mode == YawSchemeCMode::DOWNWEIGHT) {
    ++options_.yaw_downweight_count;
  } else {
    ++options_.yaw_reject_count;
    ++options_.rejected_update_count;
  }
  if (options_.diagnostic_mode) {
    diagnostic_current_yaw_mode_ = decision.label;
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
    MeasurementBlock effective = measurement;
    applyDiagnosticCovarianceMode(options_, effective);
    const Vector21 dx_before = filter_state_.dx;
    const Matrix21 cov_before = filter_state_.covariance;
    if (options_.diagnostic_mode && options_.diagnostic_model_variant == "ekf_update_residual_sign_flip") {
      // 中文说明：D2 诊断：临时翻转量测 residual 后进入 Joseph form，用来隔离 EKF innovation 符号。
      for (double& value : effective.residual) {
        value = -value;
      }
    }
    legsa_v23_core::EKFUpdate(filter_state_, effective);
    applyDiagnosticCovariancePostProcess();
    recordDiagnosticUpdateBlock(effective, dx_before, cov_before, filter_state_.dx, filter_state_.covariance, true);
    recordDiagnosticCrossCovariance("update");
  }
  pending_measurements_.clear();
}

// 中文说明：stateFeedback 将 dx 反馈到 BLH/NED/姿态/bias/scale；反馈后 dx 清零。
// 中文说明：历史边界保留：TODO(N4H4C): state feedback not implemented in N4H4B.
void LegSAV23Engine::stateFeedback() {
  ++diagnostic_feedback_counter_;
  if (options_.diagnostic_mode) {
    const std::string mode = options_.diagnostic_feedback_mode;
    if (mode == "no_feedback" || (mode == "delayed_feedback_every_5_updates" && diagnostic_feedback_counter_ % 5 != 0)) {
      // 中文说明：D5 诊断：跳过 stateFeedback 只为隔离反馈路径，不是正式 solver 行为。
      recordDiagnosticCovariance("feedback", 0.0, subVectorNorm3(filter_state_.dx, PHI_ID) * kRadToDeg);
      return;
    }
  }
  const FilterState before_state = filter_state_;
  legsa_v23_core::stateFeedback(filter_state_, options_);
  recordDiagnosticFeedbackDelta(before_state, filter_state_);
  recordDiagnosticImuErrorFeedback(before_state, filter_state_, posVelFeedbackEnabled(options_),
                                   attitudeFeedbackEnabled(options_), biasScaleFeedbackEnabled(options_));
  recordDiagnosticCovariance("feedback");
  recordDiagnosticCrossCovariance("feedback");
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

// 中文说明：构造 first-update 诊断记录；残差来自当前名义状态与 GNSS 高层观测，不读取 trace。
void LegSAV23Engine::recordDiagnosticUpdate(const GNSSData& gnss, int update_status, double imu_pre_time,
                                            double imu_cur_time, bool measurement_enabled) {
  if (!options_.diagnostic_mode) {
    return;
  }
  const int limit = options_.debug_full_update_trace ? options_.diagnostic_debug_max_rows
                                                     : options_.diagnostic_debug_max_updates;
  if (diagnostic_updates_.size() >= static_cast<std::size_t>(std::max(0, limit))) {
    return;
  }
  DiagnosticUpdateRecord record;
  record.update_index = static_cast<int>(diagnostic_updates_.size()) + 1;
  record.gnss_time = gnss.time;
  record.imu_pre_time = imu_pre_time;
  record.imu_cur_time = imu_cur_time;
  record.is_to_update_res = update_status;

  const MeasurementBlock position_block = buildGnssPositionMeasurement(filter_state_.current_pva, gnss, options_);
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    record.position_residual[i] = position_block.residual[i];
    record.r_pos_diag[i] = measurementRAt(position_block, i, i);
  }
  record.position_residual_norm = norm3(record.position_residual);
  record.h_pos_phi_norm = hBlockNorm(position_block, PHI_ID, PHI_ID + kVector3Size);
  if (gnss.has_velocity) {
    const MeasurementBlock velocity_block = buildGnssVelocityMeasurement(filter_state_.current_pva, gnss, options_);
    for (std::size_t i = 0; i < kVector3Size; ++i) {
      record.velocity_residual[i] = velocity_block.residual[i];
      record.r_vel_diag[i] = measurementRAt(velocity_block, i, i);
    }
    record.velocity_residual_norm = norm3(record.velocity_residual);
  }
  record.yaw_obs_deg = gnss.yaw_deg;
  record.yaw_pred_deg = Rotation::wrapAngleDeg(filter_state_.current_pva.euler_rpy_rad[2] * kRadToDeg);
  record.yaw_residual_deg = diagnosticYawResidualDeg(options_, gnss.yaw_deg, record.yaw_pred_deg);
  if (gnss.has_yaw) {
    const YawSchemeCDecision decision = applyYawSchemeC(record.yaw_residual_deg, gnss.yaw_std_deg);
    record.yaw_scheme_mode = decision.label;
    record.yaw_effective_std_deg = decision.effective_std_deg;
    record.yaw_update_applied = measurement_enabled && !options_.disable_yaw_update && decision.accepted;
    const auto yaw_block = buildGnssYawMeasurement(filter_state_.current_pva, gnss, options_);
    if (yaw_block.has_value()) {
      record.h_yaw_phi_value_or_norm = hBlockNorm(yaw_block.value(), PHI_ID, PHI_ID + kVector3Size);
      record.r_yaw = measurementRAt(yaw_block.value(), 0, 0);
    }
  }
  record.position_update_applied = measurement_enabled && !options_.disable_position_update;
  record.velocity_update_applied = measurement_enabled && gnss.has_velocity && !options_.disable_velocity_update;
  record.dx_norm_before_update = diagnostic_pre_dx_norm_;
  record.dx_norm_after_update = norm21(filter_state_.dx);
  record.dx_norm_before_feedback = record.dx_norm_after_update;
  record.cov_trace_before = diagnostic_pre_cov_trace_;
  record.cov_min_diag_before = diagnostic_pre_cov_min_diag_;
  double unused_cov_max = 0.0;
  covarianceStats(filter_state_.covariance, record.cov_trace_after, record.cov_min_diag_after, unused_cov_max);
  Vector3 dx_pos = zeroVector3();
  Vector3 dx_vel = zeroVector3();
  Vector3 dx_phi = zeroVector3();
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    dx_pos[i] = filter_state_.dx[P_ID + i];
    dx_vel[i] = filter_state_.dx[V_ID + i];
    dx_phi[i] = filter_state_.dx[PHI_ID + i];
  }
  record.dx_pos_norm = norm3(dx_pos);
  record.dx_vel_norm = norm3(dx_vel);
  record.dx_phi_norm_deg = norm3(dx_phi) * kRadToDeg;
  record.k_norm_pos = diagnosticGainProxy(record.dx_pos_norm, record.position_residual_norm);
  record.k_norm_vel = diagnosticGainProxy(record.dx_vel_norm, record.velocity_residual_norm);
  record.k_norm_yaw = diagnosticGainProxy(norm3(dx_phi), std::abs(record.yaw_residual_deg * kDegToRad));
  diagnostic_updates_.push_back(record);
}

// 中文说明：记录传播后的状态与协方差统计；只保留前 N 条，避免大文件进入运行目录。
void LegSAV23Engine::recordDiagnosticPropagation(const IMUData& imupre, const IMUData& imucur) {
  if (!options_.diagnostic_mode) {
    return;
  }
  const int limit = options_.debug_full_state_trace ? options_.diagnostic_debug_max_rows
                                                    : options_.diagnostic_debug_max_updates;
  if (diagnostic_propagations_.size() >= static_cast<std::size_t>(std::max(0, limit))) {
    return;
  }
  DiagnosticPropagationRecord record;
  record.propagation_index = static_cast<int>(diagnostic_propagations_.size()) + 1;
  record.time_pre = imupre.time;
  record.time_cur = imucur.time;
  record.dt = imucur.time - imupre.time;
  record.nav_state = filter_state_.current_pva;
  record.dtheta_norm = norm3(imucur.dtheta);
  record.dvel_norm = norm3(imucur.dvel);
  covarianceStats(filter_state_.covariance, record.cov_trace, record.cov_min_diag, record.cov_max_diag);
  diagnostic_propagations_.push_back(record);
}

// 中文说明：stateFeedback 是否发生只写入诊断记录；不影响反馈数学和正式输出。
void LegSAV23Engine::markLatestDiagnosticFeedbackApplied() {
  if (!diagnostic_updates_.empty()) {
    diagnostic_updates_.back().state_feedback_applied = true;
  }
}

// 中文说明：D5 量测块贡献记录真实 EKFUpdate 前后差分；只写 debug CSV。
void LegSAV23Engine::recordDiagnosticUpdateBlock(const MeasurementBlock& measurement, const Vector21& dx_before,
                                                 const Matrix21& cov_before, const Vector21& dx_after,
                                                 const Matrix21& cov_after, bool accepted) {
  if (!options_.diagnostic_mode || !options_.debug_update_blocks) {
    return;
  }
  if (diagnostic_update_blocks_.size() >= static_cast<std::size_t>(std::max(0, options_.diagnostic_debug_max_rows))) {
    return;
  }
  DiagnosticUpdateBlockRecord record;
  record.update_index = diagnostic_current_update_index_;
  record.gnss_time = diagnostic_current_gnss_time_;
  record.block_type = measurement.name == "gnss_position" ? "position"
                      : measurement.name == "gnss_velocity" ? "velocity"
                      : measurement.name == "gnss_yaw"      ? "yaw"
                                                            : measurement.name;
  record.dz_norm = measurementResidualNorm(measurement);
  if (!measurement.residual.empty()) {
    record.dz_0 = measurement.residual[0];
  }
  if (measurement.residual.size() > 1) {
    record.dz_1 = measurement.residual[1];
  }
  if (measurement.residual.size() > 2) {
    record.dz_2 = measurement.residual[2];
  }
  record.H_norm = measurementHNorm(measurement);
  record.R_trace = measurementRTrace(measurement);
  record.S_condition_estimate = measurementConditionEstimate(measurement);
  record.dx_before_norm = norm21(dx_before);
  record.dx_after_norm = norm21(dx_after);
  const Vector21 dx_delta = vectorDiff(dx_after, dx_before);
  record.dx_delta_norm = norm21(dx_delta);
  record.dx_delta_pos_norm = subVectorNorm3(dx_delta, P_ID);
  record.dx_delta_vel_norm = subVectorNorm3(dx_delta, V_ID);
  record.dx_delta_phi_norm_deg = subVectorNorm3(dx_delta, PHI_ID) * kRadToDeg;
  double cov_max_before = 0.0;
  double cov_max_after = 0.0;
  covarianceStats(cov_before, record.cov_trace_before, record.cov_min_diag_before, cov_max_before);
  covarianceStats(cov_after, record.cov_trace_after, record.cov_min_diag_after, cov_max_after);
  record.K_norm = diagnosticGainProxy(record.dx_delta_norm, record.dz_norm);
  record.accepted = accepted;
  record.yaw_scheme_mode = record.block_type == "yaw" ? diagnostic_current_yaw_mode_ : "NONE";
  diagnostic_update_blocks_.push_back(record);
  recordDiagnosticCovariance("update_" + record.block_type, record.K_norm, record.dx_delta_phi_norm_deg);
}

// 中文说明：D5 feedback delta 记录反馈前后名义状态差分，帮助判断 dx_phi 是否过修正。
void LegSAV23Engine::recordDiagnosticFeedbackDelta(const FilterState& before_state, const FilterState& after_state) {
  if (!options_.diagnostic_mode || !options_.debug_feedback_delta) {
    return;
  }
  if (diagnostic_feedback_deltas_.size() >= static_cast<std::size_t>(std::max(0, options_.diagnostic_debug_max_rows))) {
    return;
  }
  DiagnosticFeedbackDeltaRecord record;
  record.update_index = diagnostic_current_update_index_;
  record.gnss_time = diagnostic_current_gnss_time_;
  record.dx_pos_norm_before = subVectorNorm3(before_state.dx, P_ID);
  record.dx_vel_norm_before = subVectorNorm3(before_state.dx, V_ID);
  record.dx_phi_norm_deg_before = subVectorNorm3(before_state.dx, PHI_ID) * kRadToDeg;
  Vector3 pos_delta_blh = zeroVector3();
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    pos_delta_blh[i] = after_state.current_pva.pos_blh_rad_m[i] - before_state.current_pva.pos_blh_rad_m[i];
  }
  const Matrix3 dr = Earth::DR(before_state.current_pva.pos_blh_rad_m);
  Vector3 pos_delta_ned = zeroVector3();
  for (std::size_t row = 0; row < kVector3Size; ++row) {
    for (std::size_t col = 0; col < kVector3Size; ++col) {
      pos_delta_ned[row] += matrix3At(dr, row, col) * pos_delta_blh[col];
    }
  }
  record.pos_delta_ned_norm = norm3(pos_delta_ned);
  Vector3 vel_delta = zeroVector3();
  Vector3 bias_delta = zeroVector3();
  Vector3 scale_delta = zeroVector3();
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    vel_delta[i] = after_state.current_pva.vel_ned_mps[i] - before_state.current_pva.vel_ned_mps[i];
    bias_delta[i] = after_state.current_pva.gyro_bias[i] - before_state.current_pva.gyro_bias[i];
    scale_delta[i] = after_state.current_pva.gyro_scale[i] - before_state.current_pva.gyro_scale[i];
  }
  record.vel_delta_norm = norm3(vel_delta);
  record.bias_delta_norm = norm3(bias_delta);
  record.scale_delta_norm = norm3(scale_delta);
  record.roll_before = before_state.current_pva.euler_rpy_rad[0] * kRadToDeg;
  record.pitch_before = before_state.current_pva.euler_rpy_rad[1] * kRadToDeg;
  record.yaw_before = before_state.current_pva.euler_rpy_rad[2] * kRadToDeg;
  record.roll_after = after_state.current_pva.euler_rpy_rad[0] * kRadToDeg;
  record.pitch_after = after_state.current_pva.euler_rpy_rad[1] * kRadToDeg;
  record.yaw_after = after_state.current_pva.euler_rpy_rad[2] * kRadToDeg;
  record.roll_delta = Rotation::wrapAngleDeg(record.roll_after - record.roll_before);
  record.pitch_delta = Rotation::wrapAngleDeg(record.pitch_after - record.pitch_before);
  record.yaw_delta = Rotation::wrapAngleDeg(record.yaw_after - record.yaw_before);
  record.phi_delta_deg_norm =
      std::sqrt(record.roll_delta * record.roll_delta + record.pitch_delta * record.pitch_delta +
                record.yaw_delta * record.yaw_delta);
  record.dx_reset_after_feedback = norm21(after_state.dx) < 1.0e-12;
  diagnostic_feedback_deltas_.push_back(record);
}

// 中文说明：D5 covariance trace 分块统计只用于定位 P/K/dx 尺度，不改变滤波结果。
void LegSAV23Engine::recordDiagnosticCovariance(const std::string& event_type, double k_norm,
                                                double dx_phi_norm_deg) {
  if (!options_.diagnostic_mode || !options_.debug_covariance_gain) {
    return;
  }
  if (diagnostic_covariances_.size() >= static_cast<std::size_t>(std::max(0, options_.diagnostic_debug_max_rows))) {
    return;
  }
  DiagnosticCovarianceRecord record;
  record.time = current_time_;
  record.event_type = event_type;
  covarianceStats(filter_state_.covariance, record.cov_trace, record.cov_min_diag, record.cov_max_diag);
  for (std::size_t i = 0; i < kVector3Size; ++i) {
    record.P_pos_trace += matrix21At(filter_state_.covariance, P_ID + i, P_ID + i);
    record.P_vel_trace += matrix21At(filter_state_.covariance, V_ID + i, V_ID + i);
    record.P_phi_trace += matrix21At(filter_state_.covariance, PHI_ID + i, PHI_ID + i);
    record.P_bg_trace += matrix21At(filter_state_.covariance, BG_ID + i, BG_ID + i);
    record.P_ba_trace += matrix21At(filter_state_.covariance, BA_ID + i, BA_ID + i);
  }
  record.K_norm_if_update = k_norm;
  record.dx_phi_norm_deg_if_update = dx_phi_norm_deg;
  diagnostic_covariances_.push_back(record);
}

// 中文说明：D6 IMU compensation trace 记录补偿次数和前后增量范数；debug CSV 不进入 solver 输入。
void LegSAV23Engine::recordDiagnosticImuCompensation(const IMUData& imu_before, const IMUData& imu_after,
                                                     bool applied, bool imupre_compensated,
                                                     bool imucur_compensated) {
  if (!options_.diagnostic_mode || !options_.debug_imu_compensation) {
    return;
  }
  if (diagnostic_imu_compensations_.size() >=
      static_cast<std::size_t>(std::max(0, options_.diagnostic_debug_max_rows))) {
    return;
  }
  DiagnosticImuCompensationRecord record;
  record.propagation_index = options_.propagation_count;
  record.imu_time = imu_after.time;
  record.imu_dt = imu_after.dt;
  record.dtheta_norm_before = norm3(imu_before.dtheta);
  record.dtheta_norm_after = norm3(imu_after.dtheta);
  record.dvel_norm_before = norm3(imu_before.dvel);
  record.dvel_norm_after = norm3(imu_after.dvel);
  record.gyrbias_norm = norm3(filter_state_.current_pva.gyro_bias);
  record.accbias_norm = norm3(filter_state_.current_pva.acc_bias);
  record.gyrscale_norm = norm3(filter_state_.current_pva.gyro_scale);
  record.accscale_norm = norm3(filter_state_.current_pva.acc_scale);
  record.compensation_applied = applied;
  const auto found = imu_compensation_counts_.find(imu_after.time);
  record.compensation_count_for_current_imu = found == imu_compensation_counts_.end() ? 0 : found->second;
  record.repeated_compensation_detected = record.compensation_count_for_current_imu > 1;
  record.imupre_compensated = imupre_compensated;
  record.imucur_compensated = imucur_compensated;
  diagnostic_imu_compensations_.push_back(record);
}

// 中文说明：D6 IMU error feedback trace 只记录 bias/scale 反馈大小，不能作为性能或调参证据。
void LegSAV23Engine::recordDiagnosticImuErrorFeedback(const FilterState& before_state,
                                                      const FilterState& after_state,
                                                      bool pos_vel_feedback_applied,
                                                      bool attitude_feedback_applied,
                                                      bool bias_scale_feedback_applied) {
  if (!options_.diagnostic_mode || !options_.debug_imu_error_feedback) {
    return;
  }
  if (diagnostic_imu_error_feedbacks_.size() >=
      static_cast<std::size_t>(std::max(0, options_.diagnostic_debug_max_rows))) {
    return;
  }
  DiagnosticImuErrorFeedbackRecord record;
  record.update_index = diagnostic_current_update_index_;
  record.gnss_time = diagnostic_current_gnss_time_;
  record.dx_bg_norm = subVectorNorm3(before_state.dx, BG_ID);
  record.dx_ba_norm = subVectorNorm3(before_state.dx, BA_ID);
  record.dx_sg_norm = subVectorNorm3(before_state.dx, SG_ID);
  record.dx_sa_norm = subVectorNorm3(before_state.dx, SA_ID);
  record.gyrbias_norm_before = pvaVectorNorm3(before_state.current_pva, "gyrbias");
  record.accbias_norm_before = pvaVectorNorm3(before_state.current_pva, "accbias");
  record.gyrscale_norm_before = pvaVectorNorm3(before_state.current_pva, "gyrscale");
  record.accscale_norm_before = pvaVectorNorm3(before_state.current_pva, "accscale");
  record.gyrbias_norm_after = pvaVectorNorm3(after_state.current_pva, "gyrbias");
  record.accbias_norm_after = pvaVectorNorm3(after_state.current_pva, "accbias");
  record.gyrscale_norm_after = pvaVectorNorm3(after_state.current_pva, "gyrscale");
  record.accscale_norm_after = pvaVectorNorm3(after_state.current_pva, "accscale");
  record.bias_scale_feedback_applied = bias_scale_feedback_applied;
  record.attitude_feedback_applied = attitude_feedback_applied;
  record.pos_vel_feedback_applied = pos_vel_feedback_applied;
  diagnostic_imu_error_feedbacks_.push_back(record);
}

// 中文说明：D6 cross covariance trace 记录 P 的耦合强度，external clean reference 不进入 solver。
void LegSAV23Engine::recordDiagnosticCrossCovariance(const std::string& event_type) {
  if (!options_.diagnostic_mode || !options_.debug_cross_covariance) {
    return;
  }
  if (diagnostic_cross_covariances_.size() >=
      static_cast<std::size_t>(std::max(0, options_.diagnostic_debug_max_rows))) {
    return;
  }
  DiagnosticCrossCovarianceRecord record;
  record.time = current_time_;
  record.event_type = event_type;
  record.P_phi_trace = covarianceTrace3(filter_state_.covariance, PHI_ID);
  record.P_bg_trace = covarianceTrace3(filter_state_.covariance, BG_ID);
  record.P_ba_trace = covarianceTrace3(filter_state_.covariance, BA_ID);
  record.P_sg_trace = covarianceTrace3(filter_state_.covariance, SG_ID);
  record.P_sa_trace = covarianceTrace3(filter_state_.covariance, SA_ID);
  record.P_phi_bg_norm = covarianceBlockNorm(filter_state_.covariance, PHI_ID, kVector3Size, BG_ID, kVector3Size);
  record.P_phi_ba_norm = covarianceBlockNorm(filter_state_.covariance, PHI_ID, kVector3Size, BA_ID, kVector3Size);
  record.P_phi_sg_norm = covarianceBlockNorm(filter_state_.covariance, PHI_ID, kVector3Size, SG_ID, kVector3Size);
  record.P_phi_sa_norm = covarianceBlockNorm(filter_state_.covariance, PHI_ID, kVector3Size, SA_ID, kVector3Size);
  record.P_pos_phi_norm = covarianceBlockNorm(filter_state_.covariance, P_ID, kVector3Size, PHI_ID, kVector3Size);
  record.P_vel_phi_norm = covarianceBlockNorm(filter_state_.covariance, V_ID, kVector3Size, PHI_ID, kVector3Size);
  record.P_pos_ba_norm = covarianceBlockNorm(filter_state_.covariance, P_ID, kVector3Size, BA_ID, kVector3Size);
  record.P_vel_ba_norm = covarianceBlockNorm(filter_state_.covariance, V_ID, kVector3Size, BA_ID, kVector3Size);
  diagnostic_cross_covariances_.push_back(record);
}

// 中文说明：D6 covariance variant 在 predict/update 后临时清零交叉项，只用于定位 coupling，不是正式修复。
void LegSAV23Engine::applyDiagnosticCovariancePostProcess() {
  if (!options_.diagnostic_mode) {
    return;
  }
  const std::string mode = options_.diagnostic_covariance_mode;
  if (mode == "zero_phi_bias_scale_cross_cov") {
    for (std::size_t offset : {BG_ID, BA_ID, SG_ID, SA_ID}) {
      for (std::size_t i = 0; i < kVector3Size; ++i) {
        for (std::size_t j = 0; j < kVector3Size; ++j) {
          matrix21At(filter_state_.covariance, PHI_ID + i, offset + j) = 0.0;
          matrix21At(filter_state_.covariance, offset + j, PHI_ID + i) = 0.0;
        }
      }
    }
  } else if (mode == "zero_bias_scale_cross_cov") {
    for (std::size_t offset : {BG_ID, BA_ID, SG_ID, SA_ID}) {
      for (std::size_t i = 0; i < kVector3Size; ++i) {
        const std::size_t index = offset + i;
        for (std::size_t j = 0; j < kStateSize; ++j) {
          if (j == index) {
            continue;
          }
          matrix21At(filter_state_.covariance, index, j) = 0.0;
          matrix21At(filter_state_.covariance, j, index) = 0.0;
        }
      }
    }
  }
}

}  // namespace legsa_v23_core
