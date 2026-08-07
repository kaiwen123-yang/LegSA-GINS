// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/kf_gins/gi_engine.hpp"

#include "legsa_v23_port_core/common/earth.hpp"
#include "legsa_v23_port_core/common/rotation.hpp"
#include "legsa_v23_port_core/factors/go2_weak_prior_factor.hpp"
#include "legsa_v23_port_core/factors/raw_doppler_factor.hpp"
#include "legsa_v23_port_core/kf_gins/insmech.hpp"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace legsa_v23_port_core {
namespace {

Vec3 vecFromDx(const std::vector<double>& dx, std::size_t offset) {
  return makeVec3(dx.at(offset), dx.at(offset + 1), dx.at(offset + 2));
}

void setDiagonalBlock(Matrix& matrix, std::size_t offset, const Vec3& std_value) {
  for (std::size_t i = 0; i < 3; ++i) {
    matrix(offset + i, offset + i) = std_value[i] * std_value[i];
  }
}

void setDiagonalBlockValue(Matrix& matrix, std::size_t offset, const Vec3& value) {
  for (std::size_t i = 0; i < 3; ++i) {
    matrix(offset + i, offset + i) = value[i];
  }
}

Matrix3 diag3(const Vec3& value) {
  Matrix3 out = zeroMatrix3();
  out[0][0] = value[0];
  out[1][1] = value[1];
  out[2][2] = value[2];
  return out;
}

Vec3 positiveStd(const Vec3& value, double floor_value) {
  return makeVec3(std::max(std::fabs(value[0]), floor_value),
                  std::max(std::fabs(value[1]), floor_value),
                  std::max(std::fabs(value[2]), floor_value));
}

double matrixTrace(const Matrix& matrix) {
  const std::size_t n = std::min(matrix.rows, matrix.cols);
  double out = 0.0;
  for (std::size_t i = 0; i < n; ++i) {
    out += matrix(i, i);
  }
  return out;
}

double vectorNorm(const std::vector<double>& values) {
  double sum = 0.0;
  for (double value : values) {
    sum += value * value;
  }
  return std::sqrt(sum);
}

double dotVector(const std::vector<double>& lhs, const std::vector<double>& rhs) {
  const std::size_t n = std::min(lhs.size(), rhs.size());
  double out = 0.0;
  for (std::size_t i = 0; i < n; ++i) {
    out += lhs[i] * rhs[i];
  }
  return out;
}

double percentile(std::vector<double> values, double q) {
  if (values.empty()) {
    return 0.0;
  }
  std::sort(values.begin(), values.end());
  const double clamped = std::max(0.0, std::min(1.0, q));
  const std::size_t index = static_cast<std::size_t>(clamped * static_cast<double>(values.size() - 1));
  return values[index];
}

}  // namespace

GIEngine::GIEngine(PortOptions options)
    : options_(std::move(options)),
      Cov_(RANK, RANK, 0.0),
      Qc_(NOISERANK, NOISERANK, 0.0),
      dx_(RANK, 0.0),
      qa_fallback_supervisor_(options_.qa_fallback_config),
      source_aware_policy_(options_.source_aware_policy_config),
      quality_state_manager_(options_.quality_state_manager_config) {
  initializeQc();
}

// 中文说明：初始化 PVA、姿态四元数、IMU 误差和协方差，不读取 final_v23 输出。
void GIEngine::initialize(const NavState& initial_state) {
  pvacur_ = initial_state;
  pvacur_.time = initial_state.time;
  pvacur_.qbn = Rotation::euler2quaternion(pvacur_.euler_rad);
  pvacur_.cbn = Rotation::quaternion2matrix(pvacur_.qbn);
  imuerror_ = options_.init_imu_error;
  pvacur_.imu_error = imuerror_;
  pvapre_ = pvacur_;
  timestamp_ = pvacur_.time;
  initializeCovariance();
  zeroVector(dx_);
  initialized_ = true;
}

// 中文说明：raw Doppler velocity measurements 必须来自 RAWX+satellite-state provider，
// 不能来自 NAV-PVT velocity、.gnss vn/ve/vd、trace 或 final_v23 输出。
void GIEngine::setRawDopplerVelocityMeasurements(const std::vector<RawDopplerVelocityMeasurement>& measurements,
                                                 const RawDopplerFactorStatus& status) {
  raw_doppler_measurements_ = measurements;
  raw_doppler_status_ = status;
  raw_doppler_status_.code_present = true;
  raw_doppler_status_.epoch_count = measurements.size();
  if (raw_doppler_status_.valid_epoch_count == 0) {
    raw_doppler_status_.valid_epoch_count = static_cast<std::size_t>(std::count_if(
        measurements.begin(), measurements.end(), [](const RawDopplerVelocityMeasurement& measurement) {
          return measurement.provider_status == "available";
        }));
  }
  raw_doppler_status_.solver_enabled =
      options_.raw_doppler_config.enable_raw_doppler && status.solver_enabled && status.provider_status == "available";
  if (raw_doppler_status_.factor_source.empty() || raw_doppler_status_.factor_source == "none") {
    raw_doppler_status_.factor_source = options_.raw_doppler_config.raw_doppler_factor_source;
  }
  if (!raw_doppler_status_.solver_enabled && raw_doppler_status_.provider_status.empty()) {
    raw_doppler_status_.provider_status = "provider_missing_sat_state_export";
  }
}

// 中文说明：Go2 attitude weak prior 只接收 builder 生成的 roll/pitch runtime CSV，不读取 by2.txt/raw trace 进 solver。
void GIEngine::setGo2AttitudeWeakPriors(const std::vector<Go2AttitudeWeakPriorMeasurement>& measurements,
                                        const Go2AttitudeWeakPriorStatus& status) {
  go2_attitude_priors_ = measurements;
  go2_attitude_prior_status_ = status;
  go2_attitude_prior_status_.code_present = true;
  go2_attitude_prior_status_.prior_count = measurements.size();
  if (go2_attitude_prior_status_.valid_prior_count == 0) {
    go2_attitude_prior_status_.valid_prior_count = static_cast<std::size_t>(std::count_if(
        measurements.begin(), measurements.end(), [](const Go2AttitudeWeakPriorMeasurement& measurement) {
          return measurement.source_status == "active";
        }));
  }
  go2_attitude_prior_status_.solver_enabled =
      options_.go2_attitude_prior_config.enable_go2_attitude_weak_prior && status.solver_enabled &&
      status.provider_status == "available";
}

// 中文说明：N7B3 Go2 velocity prior 是 diagnostic-only activation，Go2 velocity 不是 truth，也不是正式 proposed result。
void GIEngine::setGo2VelocityDiagnosticPriors(
    const std::vector<Go2VelocityDiagnosticPriorMeasurement>& measurements,
    const Go2VelocityDiagnosticPriorStatus& status) {
  go2_velocity_diagnostic_priors_ = measurements;
  go2_velocity_diagnostic_prior_status_ = status;
  go2_velocity_diagnostic_prior_status_.code_present = true;
  go2_velocity_diagnostic_prior_status_.prior_count = measurements.size();
  if (go2_velocity_diagnostic_prior_status_.valid_prior_count == 0) {
    const bool controlled_horizontal =
        options_.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior;
    go2_velocity_diagnostic_prior_status_.valid_prior_count = static_cast<std::size_t>(std::count_if(
        measurements.begin(), measurements.end(), [controlled_horizontal](const Go2VelocityDiagnosticPriorMeasurement& measurement) {
          return measurement.source_status == "active" && measurement.update_flag && !measurement.go2_velocity_truth_claim &&
                 (measurement.diagnostic_only || controlled_horizontal);
        }));
  }
  go2_velocity_diagnostic_prior_status_.solver_enabled =
      options_.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic &&
      status.solver_enabled && status.provider_status == "available" &&
      (options_.go2_velocity_prior_diagnostic_config.go2_diagnostic_prior_only ||
       options_.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior);
  go2_velocity_diagnostic_prior_status_.horizontal_only =
      std::any_of(measurements.begin(), measurements.end(), [](const Go2VelocityDiagnosticPriorMeasurement& measurement) {
        return measurement.std_ned_mps[2] >= 999.0 ||
               measurement.prior_policy.find("horizontal") != std::string::npos;
      });
  go2_velocity_diagnostic_prior_status_.vertical_disabled = go2_velocity_diagnostic_prior_status_.horizontal_only;
  go2_velocity_diagnostic_prior_status_.controlled_activation =
      options_.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior;
}

void GIEngine::setGo2ReadinessLsimMetadata(
    const std::vector<Go2ReadinessLsimMetadataMeasurement>& measurements,
    const Go2ReadinessLsimMetadataStatus& status) {
  go2_readiness_lsim_metadata_ = measurements;
  go2_readiness_lsim_metadata_status_ = status;
  go2_readiness_lsim_metadata_status_.code_present = true;
  go2_readiness_lsim_metadata_status_.metadata_count = measurements.size();
  if (go2_readiness_lsim_metadata_status_.valid_metadata_count == 0) {
    go2_readiness_lsim_metadata_status_.valid_metadata_count = static_cast<std::size_t>(std::count_if(
        measurements.begin(), measurements.end(), [](const Go2ReadinessLsimMetadataMeasurement& measurement) {
          return measurement.source_status == "active" && measurement.source_valid;
        }));
  }
  go2_readiness_lsim_metadata_status_.solver_enabled =
      options_.go2_readiness_lsim_metadata_config.enable_go2_readiness_lsim_metadata &&
      status.solver_enabled && status.provider_status == "available";
  go2_readiness_lsim_metadata_status_.readiness_metadata_first_class_lsim =
      go2_readiness_lsim_metadata_status_.solver_enabled &&
      options_.source_aware_policy_config.source_aware_go2_readiness_lsim_enabled;
}

// 中文说明：N8G FGO feedback observations 只允许作为 EKF pseudo-measurement，不允许直接覆盖 NAV。
void GIEngine::setFgoFeedbackObservations(
    const std::vector<fgo_feedback::FgoFeedbackObservation>& observations,
    const fgo_feedback::FgoFeedbackStatus& status) {
  fgo_feedback_observations_ = observations;
  fgo_feedback_status_ = status;
  fgo_feedback_status_.code_present = true;
  fgo_feedback_status_.observation_count = observations.size();
  if (fgo_feedback_status_.valid_observation_count == 0) {
    fgo_feedback_status_.valid_observation_count = static_cast<std::size_t>(std::count_if(
        observations.begin(), observations.end(), [](const fgo_feedback::FgoFeedbackObservation& obs) {
          return obs.feedback_valid;
        }));
  }
  fgo_feedback_status_.solver_enabled =
      options_.fgo_feedback_config.enable_fgo_feedback && status.solver_enabled &&
      (!options_.fgo_feedback_config.fgo_feedback_no_future_data_required || status.no_future_data);
}

// 中文说明：addImuData 保持 reference 的 imupre/imucur 滚动缓冲；首帧可选择预补偿。
void GIEngine::addImuData(const ImuData& imu, bool compensate) {
  imupre_ = imucur_;
  imucur_ = imu;
  if (compensate) {
    imuCompensateInPlace(imucur_);
  }
}

// 中文说明：GNSS 是 15 列松组合观测，不是 raw pseudorange/Doppler。
void GIEngine::addGnssData(const GnssData& gnss) {
  gnssdata_ = gnss;
  // 中文说明：legacy 15 列继续视为三类观测均有效；formal validity 则保留自然 dropout，
  // 不得因 velocity/yaw 缺测而删除同一历元的 position，也不得把无效字段恢复为有效。
  if (!gnssdata_.validity_explicit) {
    gnssdata_.has_position = true;
    gnssdata_.has_velocity = true;
    gnssdata_.has_yaw = true;
  }
  gnssdata_.isvalid = gnssdata_.has_position || gnssdata_.has_velocity || gnssdata_.has_yaw;
}

int GIEngine::isToUpdate() const {
  const double updatetime = gnssdata_.isvalid ? gnssdata_.time : -1.0;
  return isToUpdate(imupre_.time, imucur_.time, updatetime);
}

// 中文说明：res=0/1/2/3 与 KF-GINS runtime loop 对齐，控制 update 插入位置。
int GIEngine::isToUpdate(double imutime1, double imutime2, double updatetime) const {
  if (std::fabs(imutime1 - updatetime) < TIME_ALIGN_ERR) {
    return 1;
  }
  if (std::fabs(imutime2 - updatetime) <= TIME_ALIGN_ERR) {
    return 2;
  }
  if (imutime1 < updatetime && updatetime < imutime2) {
    return 3;
  }
  return 0;
}

// 中文说明：IMU 内插只拆分增量，不在这里做补偿；res=3 的补偿由后续传播负责。
ImuData GIEngine::imuInterpolate(const ImuData& previous, ImuData& current, double time) const {
  if (previous.time > time || current.time < time) {
    return current;
  }
  const double lambda = (time - previous.time) / (current.time - previous.time);
  ImuData midimu = current;
  midimu.time = time;
  midimu.dtheta = scale(current.dtheta, lambda);
  midimu.dvel = scale(current.dvel, lambda);
  midimu.dt = time - previous.time;
  midimu.compensated = false;
  current.dtheta = subtract(current.dtheta, midimu.dtheta);
  current.dvel = subtract(current.dvel, midimu.dvel);
  current.dt = current.dt - midimu.dt;
  current.compensated = false;
  return midimu;
}

ImuData GIEngine::imuCompensate(const ImuData& imu) const {
  ImuData out = imu;
  imuCompensateInPlace(out);
  return out;
}

// 中文说明：IMU compensation 按 bias*dt 和 scale 分母补偿；process_data 已完成 FLU->FRD，不能二次转换。
void GIEngine::imuCompensateInPlace(ImuData& imu) const {
  if (imu.compensated) {
    return;
  }
  imu.dtheta = subtract(imu.dtheta, scale(imuerror_.gyrbias, imu.dt));
  imu.dvel = subtract(imu.dvel, scale(imuerror_.accbias, imu.dt));
  imu.dtheta = cwiseDivide(imu.dtheta, add(makeVec3(1.0, 1.0, 1.0), imuerror_.gyrscale));
  imu.dvel = cwiseDivide(imu.dvel, add(makeVec3(1.0, 1.0, 1.0), imuerror_.accscale));
  imu.compensated = true;
}

void GIEngine::insPropagation() {
  insPropagation(imupre_, imucur_);
}

// 中文说明：传播先补偿 imucur，再机械编排，再构造 F/G/Phi/Qd 并 EKFPredict。
void GIEngine::insPropagation(ImuData& imupre, ImuData& imucur) {
  imuCompensateInPlace(imucur);
  INSMech::insMech(pvapre_, pvacur_, imupre, imucur);
  Matrix F(RANK, RANK, 0.0);
  Matrix G(RANK, NOISERANK, 0.0);
  Matrix Phi(RANK, RANK, 0.0);
  Matrix Qd(RANK, RANK, 0.0);
  buildErrorStateMatrices(imucur, F, G, Phi, Qd);
  EKFPredict(Phi, Qd);
  timestamp_ = imucur.time;
  ++propagation_count_;
}

void GIEngine::gnssUpdate() {
  gnssUpdate(gnssdata_);
}

// 中文说明：final_v23 strong 骨架的 GNSS update 顺序为
// position、dual-yaw、receiver-native velocity；N5D velocity stress
// 只用于诊断 raw Doppler 独立约束能力，不代表真实传感器故障模型，也不作为论文性能结果。
void GIEngine::gnssUpdate(GnssData& gnss) {
  if (!gnss.isvalid) {
    return;
  }
  GnssData policy_gnss = gnss;
  bool qa_active = false;
  quality_aware::QADecision qa_decision;
  if (!options_.enable_basic_dual_yaw_baseline && qa_fallback_supervisor_.loggingEnabled()) {
    qa_decision = qa_fallback_supervisor_.evaluate(buildQAObservation(gnss));
    qa_active = qa_decision.active_mode;
    if (qa_active && qa_decision.gnss_position_action == "DOWNWEIGHT") {
      policy_gnss.std_ned_m = scale(policy_gnss.std_ned_m, std::sqrt(std::max(1.0, qa_decision.gnss_pos_R_scale)));
    }
    if (qa_active &&
        (qa_decision.a1_measurement_action == "DOWNWEIGHT" ||
         qa_decision.a1_measurement_action == "RECOVERY_RAMP")) {
      policy_gnss.yaw_std_rad *= std::sqrt(std::max(1.0, qa_decision.yaw_R_scale));
      policy_gnss.yaw_std_deg = policy_gnss.yaw_std_rad * R2D;
    }
  }

  const bool qa_reject_position =
      qa_active && (qa_decision.gnss_position_action == "REJECT" ||
                    qa_decision.gnss_position_action == "HOLD");
  if (policy_gnss.has_position && !qa_reject_position) {
    applyPositionUpdate(policy_gnss);
  }
  if (options_.enable_basic_dual_yaw_baseline) {
    if (policy_gnss.has_yaw && options_.enable_dual_yaw_update) {
      applyBasicDualYawUpdate(policy_gnss);
    }
    gnss.isvalid = false;
    ++update_count_;
    return;
  }
  const bool qa_reject_yaw = qa_active && qa_decision.a1_measurement_action == "REJECT";
  auto apply_yaw = [&]() {
    if (!qa_reject_yaw && policy_gnss.has_yaw && options_.enable_dual_yaw_update &&
        options_.yaw_scheme_C_enabled) {
      applyYawUpdate(policy_gnss);
    }
  };
  auto apply_receiver_velocity = [&]() {
    if (!qa_reject_position && policy_gnss.has_velocity &&
        receiverVelocityUpdateEnabledForTime(policy_gnss.time)) {
      GnssData stressed_gnss = receiverVelocityStressView(policy_gnss);
      applyVelocityUpdate(stressed_gnss);
    }
  };
  if (options_.clean_final_v23_parity_mode) {
    apply_yaw();
    apply_receiver_velocity();
  } else {
    // 旧 CLEAN1/R1C replay 保留原 position→velocity→yaw 语义。
    apply_receiver_velocity();
    apply_yaw();
  }
  // 中文说明：raw Doppler auxiliary velocity factor 与 GNSS epoch 对齐，并在 stateFeedback 前进入 EKF。
  if (!qa_active || qa_decision.raw_doppler_action == "ACCEPT") {
    applyRawDopplerUpdateForTime(policy_gnss.time);
  }
  // 中文说明：N7B3 Go2 velocity diagnostic prior 默认关闭；开启时仍为 diagnostic-only，不构成正式 prior。
  if (!qa_active || qa_decision.go2_aux_action == "ACCEPT") {
    applyGo2VelocityDiagnosticPriorForTime(policy_gnss.time);
  }
  // 中文说明：Go2 roll/pitch weak prior 与 GNSS epoch 对齐进入 EKF；不启用 Go2 position/velocity/yaw prior。
  if (!qa_active || qa_decision.go2_aux_action == "ACCEPT") {
    applyGo2AttitudeWeakPriorForTime(policy_gnss.time);
  }
  // 中文说明：N8G FGO feedback 在 stateFeedback 前作为 EKF pseudo-measurement 进入，不覆盖 NAV 输出。
  if (!qa_active || qa_decision.selected_feedback_action == "ACCEPT") {
    applyFgoFeedbackForTime(policy_gnss.time);
  }
  gnss.isvalid = false;
  ++update_count_;
}

void GIEngine::EKFPredict() {
  Matrix F(RANK, RANK, 0.0);
  Matrix G(RANK, NOISERANK, 0.0);
  Matrix Phi(RANK, RANK, 0.0);
  Matrix Qd(RANK, RANK, 0.0);
  buildErrorStateMatrices(imucur_, F, G, Phi, Qd);
  EKFPredict(Phi, Qd);
}

// 中文说明：EKFPredict: Cov = Phi Cov Phi^T + Qd, dx = Phi dx。
void GIEngine::EKFPredict(const Matrix& Phi, const Matrix& Qd) {
  Cov_ = add(multiply(multiply(Phi, Cov_), transpose(Phi)), Qd);
  dx_ = multiply(Phi, dx_);
}

// 中文说明：EKFUpdate 使用 dx += K(dz-Hdx) 和 Joseph covariance form。
void GIEngine::EKFUpdate(const std::vector<double>& dz, const Matrix& H, const Matrix& R) {
  if (H.cols != RANK || dz.size() != H.rows || R.rows != H.rows || R.cols != H.rows) {
    throw std::runtime_error("EKFUpdate dimension mismatch");
  }
  const Matrix Ht = transpose(H);
  const Matrix S = add(multiply(multiply(H, Cov_), Ht), R);
  const Matrix K = multiply(multiply(Cov_, Ht), inverse(S));
  const std::vector<double> Hdx = multiply(H, dx_);
  std::vector<double> residual(dz.size(), 0.0);
  for (std::size_t i = 0; i < dz.size(); ++i) {
    residual[i] = dz[i] - Hdx[i];
  }
  const std::vector<double> delta = multiply(K, residual);
  for (std::size_t i = 0; i < dx_.size(); ++i) {
    dx_[i] += delta[i];
  }
  const Matrix I = identityMatrix(RANK);
  const Matrix IKH = subtract(I, multiply(K, H));
  Cov_ = add(multiply(multiply(IKH, Cov_), transpose(IKH)), multiply(multiply(K, R), transpose(K)));
}

// 中文说明：stateFeedback 将误差状态反馈到导航状态；位置/速度减，姿态 qpn 左乘，bias/scale 加。
void GIEngine::stateFeedback() {
  const Vec3 dx_pos = vecFromDx(dx_, P_ID);
  const Vec3 dx_vel = vecFromDx(dx_, V_ID);
  Vec3 dx_phi = vecFromDx(dx_, PHI_ID);
  const double requested_yaw_correction_deg = -dx_phi[2] * R2D;
  bool yaw_correction_clipped = false;
  if (qa_fallback_supervisor_.activeMode() && qa_fallback_supervisor_.lastDecisionRecoveryRampActive()) {
    const double max_yaw = qa_fallback_supervisor_.recoveryMaxYawCorrectionDeg() * D2R;
    if (max_yaw > 0.0 && std::fabs(dx_phi[2]) > max_yaw) {
      dx_phi[2] = dx_phi[2] > 0.0 ? max_yaw : -max_yaw;
      yaw_correction_clipped = true;
    }
  }
  pvacur_.pos_blh_rad_m = subtract(pvacur_.pos_blh_rad_m, multiply(Earth::DRi(pvacur_.pos_blh_rad_m), dx_pos));
  pvacur_.vel_ned_mps = subtract(pvacur_.vel_ned_mps, dx_vel);
  const Quaternion qpn = Rotation::rotvec2quaternion(dx_phi);
  pvacur_.qbn = Rotation::multiply(qpn, pvacur_.qbn);
  pvacur_.cbn = Rotation::quaternion2matrix(pvacur_.qbn);
  pvacur_.euler_rad = Rotation::matrix2euler(pvacur_.cbn);
  imuerror_.gyrbias = add(imuerror_.gyrbias, vecFromDx(dx_, BG_ID));
  imuerror_.accbias = add(imuerror_.accbias, vecFromDx(dx_, BA_ID));
  imuerror_.gyrscale = add(imuerror_.gyrscale, vecFromDx(dx_, SG_ID));
  imuerror_.accscale = add(imuerror_.accscale, vecFromDx(dx_, SA_ID));
  pvacur_.imu_error = imuerror_;
  qa_fallback_supervisor_.setYawCorrectionOnLastDecision(requested_yaw_correction_deg,
                                                         -dx_phi[2] * R2D,
                                                         yaw_correction_clipped);
  zeroVector(dx_);
}

// 中文说明：newImuProcess 完整处理 res=0/1/2/3，R2 只做 synthetic smoke，不声明 real clean parity。
void GIEngine::newImuProcess() {
  if (!initialized_) {
    return;
  }
  timestamp_ = imucur_.time;
  const double updatetime = gnssdata_.isvalid ? gnssdata_.time : -1.0;
  const int res = isToUpdate(imupre_.time, imucur_.time, updatetime);
  if (res == 0) {
    insPropagation(imupre_, imucur_);
  } else if (res == 1) {
    gnssUpdate(gnssdata_);
    stateFeedback();
    pvapre_ = pvacur_;
    insPropagation(imupre_, imucur_);
  } else if (res == 2) {
    insPropagation(imupre_, imucur_);
    gnssUpdate(gnssdata_);
    stateFeedback();
  } else {
    ImuData midimu = imuInterpolate(imupre_, imucur_, updatetime);
    insPropagation(imupre_, midimu);
    gnssUpdate(gnssdata_);
    stateFeedback();
    pvapre_ = pvacur_;
    insPropagation(midimu, imucur_);
  }
  if (!checkCov()) {
    ++cov_health_fail_count_;
    if (cov_health_fail_count_ == 1) {
      cov_health_first_failure_time_ = timestamp_;
    }
  }
  pvapre_ = pvacur_;
  imupre_ = imucur_;
}

bool GIEngine::checkCov() const {
  for (std::size_t i = 0; i < RANK; ++i) {
    if (!std::isfinite(Cov_(i, i)) || Cov_(i, i) < 0.0) {
      return false;
    }
  }
  return true;
}

const NavState& GIEngine::navState() const {
  return pvacur_;
}

NavState GIEngine::getNavState() const {
  return pvacur_;
}

const std::vector<double>& GIEngine::getCovariance() const {
  return Cov_.data;
}

double GIEngine::timestamp() const {
  return timestamp_;
}

std::size_t GIEngine::propagationCount() const {
  return propagation_count_;
}

std::size_t GIEngine::covHealthFailCount() const {
  return cov_health_fail_count_;
}

double GIEngine::covHealthFirstFailureTime() const {
  return cov_health_first_failure_time_;
}

std::size_t GIEngine::updateCount() const {
  return update_count_;
}

std::size_t GIEngine::positionUpdateCount() const {
  return position_update_count_;
}

std::size_t GIEngine::velocityUpdateCount() const {
  return velocity_update_count_;
}

std::size_t GIEngine::yawUpdateCount() const {
  return yaw_update_count_;
}

std::size_t GIEngine::yawNormalCount() const {
  return yaw_normal_count_;
}

std::size_t GIEngine::yawDownweightCount() const {
  return yaw_downweight_count_;
}

std::size_t GIEngine::yawRejectCount() const {
  return yaw_reject_count_;
}

std::size_t GIEngine::sourceAwareEvaluationCount() const {
  return source_aware_evaluation_count_;
}

std::size_t GIEngine::sourceAwareWeightChangedCount() const {
  return source_aware_weight_changed_count_;
}

std::size_t GIEngine::rawDopplerUpdateCount() const {
  return raw_doppler_status_.update_count;
}

std::size_t GIEngine::rawDopplerRejectCount() const {
  return raw_doppler_status_.reject_count;
}

std::size_t GIEngine::rawDopplerEpochCount() const {
  return raw_doppler_status_.epoch_count;
}

std::size_t GIEngine::rawDopplerSatCountMin() const {
  return raw_doppler_status_.sat_count_min;
}

std::size_t GIEngine::rawDopplerSatCountMedian() const {
  return raw_doppler_status_.sat_count_median;
}

std::size_t GIEngine::rawDopplerSatCountMax() const {
  return raw_doppler_status_.sat_count_max;
}

double GIEngine::rawDopplerResidualP95() const {
  return raw_doppler_status_.residual_p95_mps;
}

RawDopplerFactorStatus GIEngine::rawDopplerStatus() const {
  return raw_doppler_status_;
}

std::size_t GIEngine::go2AttitudeWeakPriorUpdateCount() const {
  return go2_attitude_prior_status_.update_count;
}

std::size_t GIEngine::go2AttitudeWeakPriorRejectCount() const {
  return go2_attitude_prior_status_.reject_count;
}

Go2AttitudeWeakPriorStatus GIEngine::go2AttitudeWeakPriorStatus() const {
  return go2_attitude_prior_status_;
}

std::size_t GIEngine::go2VelocityDiagnosticPriorUpdateCount() const {
  return go2_velocity_diagnostic_prior_status_.update_count;
}

std::size_t GIEngine::go2VelocityDiagnosticPriorRejectCount() const {
  return go2_velocity_diagnostic_prior_status_.reject_count;
}

Go2VelocityDiagnosticPriorStatus GIEngine::go2VelocityDiagnosticPriorStatus() const {
  return go2_velocity_diagnostic_prior_status_;
}

Go2ReadinessLsimMetadataStatus GIEngine::go2ReadinessLsimMetadataStatus() const {
  return go2_readiness_lsim_metadata_status_;
}

fgo_feedback::FgoFeedbackStatus GIEngine::fgoFeedbackStatus() const {
  return fgo_feedback_status_;
}

std::size_t GIEngine::qaFallbackTraceRowCount() const {
  return qa_fallback_supervisor_.trace().size();
}

void GIEngine::writeFgoFeedbackTrace(const std::string& output_dir) const {
  if (!options_.fgo_feedback_config.enable_fgo_feedback) {
    return;
  }
  std::filesystem::create_directories(output_dir);
  std::ofstream out(std::filesystem::path(output_dir) / "FGO_FEEDBACK_UPDATE_TRACE.csv");
  out << std::fixed << std::setprecision(10);
  out << "update_time,observation_time,accepted,reject_reason,position_norm_m,velocity_norm_mps,"
      << "attitude_norm_deg,yaw_residual_deg,source_window_start,source_window_end,"
      << "trace_solver_input,final_v23_output_solver_input,output_substitution,direct_nav_override\n";
  for (const auto& row : fgo_feedback_trace_) {
    out << row.update_time << "," << row.observation_time << "," << row.accepted << ","
        << row.reject_reason << "," << row.position_norm_m << "," << row.velocity_norm_mps << ","
        << row.attitude_norm_deg << "," << row.yaw_residual_deg << "," << row.source_window_start << ","
        << row.source_window_end << ",0,0,0,0\n";
  }
}

void GIEngine::writeQAFallbackTrace(const std::string& output_dir) const {
  const auto& rows = qa_fallback_supervisor_.trace();
  if (rows.empty()) {
    return;
  }
  std::filesystem::create_directories(output_dir);
  std::ofstream out(std::filesystem::path(output_dir) / "QA_FALLBACK_TRACE.csv");
  out << std::fixed << std::setprecision(10);
  out << "time,dataset_id,case_id,algorithm_id,qa_state,previous_qa_state,state_transition_flag,"
      << "reason_bits,a1_available,a1_valid,a1_baseline_m,a1_baseline_expected_m,"
      << "a1_valid_ratio_window,a1_yaw_std_deg,a1_yaw_residual_deg,a1_yaw_jump_deg,"
      << "time_since_last_trusted_a1_s,consecutive_valid_a1_count,gnss_pos_available,"
      << "gnss_pos_valid,gnss_status_or_fix,gnss_pos_std_h_m,gnss_pos_std_u_m,"
      << "time_since_last_trusted_gnss_s,raw_doppler_available,raw_doppler_count,"
      << "raw_doppler_residual,go2_body_state_available,go2_imu_available,"
      << "selected_feedback_allowed_nominal,passive_only,trace_used_for_QA,active_mode,"
      << "measurement_policy_id,a1_measurement_action,gnss_position_action,raw_doppler_action,"
      << "go2_aux_action,selected_feedback_action,yaw_R_scale,gnss_pos_R_scale,doppler_R_scale,"
      << "recovery_ramp_active,recovery_consecutive_valid_a1_count,requested_yaw_correction_deg,"
      << "yaw_correction_applied_deg,recovery_yaw_correction_cap_deg,yaw_correction_clipped,"
      << "state_transition_reason\n";
  auto optional = [](bool present, double value) -> std::string {
    if (!present) {
      return "";
    }
    std::ostringstream text;
    text << std::fixed << std::setprecision(10) << value;
    return text.str();
  };
  for (const auto& row : rows) {
    out << row.time << "," << row.dataset_id << "," << row.case_id << "," << row.algorithm_id << ","
        << quality_aware::qaStateName(row.qa_state) << ","
        << (row.has_previous_qa_state ? quality_aware::qaStateName(row.previous_qa_state) : "") << ","
        << (row.state_transition_flag ? 1 : 0) << "," << quality_aware::joinReasons(row.reason_bits) << ","
        << (row.a1_available ? 1 : 0) << "," << (row.a1_valid ? 1 : 0) << ","
        << optional(row.a1_baseline_available, row.a1_baseline_m) << ","
        << optional(row.a1_baseline_expected_available, row.a1_baseline_expected_m) << ","
        << optional(row.a1_valid_ratio_available, row.a1_valid_ratio_window) << ","
        << optional(row.a1_yaw_std_available, row.a1_yaw_std_deg) << ","
        << optional(row.a1_yaw_residual_available, row.a1_yaw_residual_deg) << ","
        << optional(row.a1_yaw_jump_available, row.a1_yaw_jump_deg) << ","
        << optional(row.time_since_last_trusted_a1_available, row.time_since_last_trusted_a1_s) << ","
        << row.consecutive_valid_a1_count << "," << (row.gnss_pos_available ? 1 : 0) << ","
        << (row.gnss_pos_valid ? 1 : 0) << "," << row.gnss_status_or_fix << ","
        << optional(row.gnss_pos_std_h_available, row.gnss_pos_std_h_m) << ","
        << optional(row.gnss_pos_std_u_available, row.gnss_pos_std_u_m) << ","
        << optional(row.time_since_last_trusted_gnss_available, row.time_since_last_trusted_gnss_s) << ","
        << (row.raw_doppler_available ? 1 : 0) << "," << row.raw_doppler_count << ","
        << optional(row.raw_doppler_residual_available, row.raw_doppler_residual) << ","
        << (row.go2_body_state_available ? 1 : 0) << "," << (row.go2_imu_available ? 1 : 0) << ","
        << (row.selected_feedback_allowed_nominal ? 1 : 0) << "," << (row.passive_only ? 1 : 0) << ","
        << (row.trace_used_for_QA ? 1 : 0) << "," << (row.active_mode ? 1 : 0) << ","
        << row.measurement_policy_id << "," << row.a1_measurement_action << ","
        << row.gnss_position_action << "," << row.raw_doppler_action << "," << row.go2_aux_action << ","
        << row.selected_feedback_action << "," << row.yaw_R_scale << "," << row.gnss_pos_R_scale << ","
        << row.doppler_R_scale << "," << (row.recovery_ramp_active ? 1 : 0) << ","
        << row.recovery_consecutive_valid_a1_count << "," << row.requested_yaw_correction_deg << ","
        << row.yaw_correction_applied_deg << "," << row.recovery_yaw_correction_cap_deg << ","
        << (row.yaw_correction_clipped ? 1 : 0) << "," << row.state_transition_reason << "\n";
  }
}

source_aware::SourceAwareRuntimeStats GIEngine::sourceAwareStats() const {
  return source_aware_trace_.stats();
}

source_aware::QualityStateRuntimeStats GIEngine::qualityStateStats() const {
  return quality_state_trace_.stats();
}

void GIEngine::writeSourceAwareTrace(const std::string& output_dir) const {
  // 中文说明：SOURCE_AWARE_WEIGHT_TRACE 是 runtime-only 审计文件，不允许作为 solver 输入。
  if (options_.source_aware_policy_config.source_aware_trace_enabled) {
    source_aware_trace_.writeCsv(output_dir);
  }
  if (quality_state_manager_.traceEnabled()) {
    quality_state_trace_.writeCsv(output_dir);
  }
}

void GIEngine::initializeCovariance() {
  Cov_ = Matrix(RANK, RANK, 0.0);
  setDiagonalBlock(Cov_, P_ID, positiveStd(options_.init_pos_std_m, 1.0e-6));
  setDiagonalBlock(Cov_, V_ID, positiveStd(options_.init_vel_std_mps, 1.0e-6));
  setDiagonalBlock(Cov_, PHI_ID, positiveStd(options_.init_att_std_rad, 1.0e-9));
  setDiagonalBlock(Cov_, BG_ID, positiveStd(options_.init_imu_error_std.gyrbias, options_.imunoise.gyrbias_std[0]));
  setDiagonalBlock(Cov_, BA_ID, positiveStd(options_.init_imu_error_std.accbias, options_.imunoise.accbias_std[0]));
  setDiagonalBlock(Cov_, SG_ID, positiveStd(options_.init_imu_error_std.gyrscale, options_.imunoise.gyrscale_std[0]));
  setDiagonalBlock(Cov_, SA_ID, positiveStd(options_.init_imu_error_std.accscale, options_.imunoise.accscale_std[0]));
}

// 中文说明：Qc bias/scale blocks 按 2/corr_time * std^2，corr_time 单位为秒。
void GIEngine::initializeQc() {
  Qc_ = Matrix(NOISERANK, NOISERANK, 0.0);
  const ImuNoise& n = options_.imunoise;
  setDiagonalBlockValue(Qc_, ARW_ID, cwiseProduct(n.gyr_arw, n.gyr_arw));
  setDiagonalBlockValue(Qc_, VRW_ID, cwiseProduct(n.acc_vrw, n.acc_vrw));
  const double corr = std::max(n.corr_time, 1.0);
  setDiagonalBlockValue(Qc_, BGSTD_ID, scale(cwiseProduct(n.gyrbias_std, n.gyrbias_std), 2.0 / corr));
  setDiagonalBlockValue(Qc_, BASTD_ID, scale(cwiseProduct(n.accbias_std, n.accbias_std), 2.0 / corr));
  setDiagonalBlockValue(Qc_, SGSTD_ID, scale(cwiseProduct(n.gyrscale_std, n.gyrscale_std), 2.0 / corr));
  setDiagonalBlockValue(Qc_, SASTD_ID, scale(cwiseProduct(n.accscale_std, n.accscale_std), 2.0 / corr));
}

// 中文说明：F/G/Phi/Qd 采用 KF-GINS error-state 结构；此处保留 key block 以便静态审计。
void GIEngine::buildErrorStateMatrices(const ImuData& imu, Matrix& F, Matrix& G, Matrix& Phi, Matrix& Qd) const {
  const double dt = imu.dt > 0.0 ? imu.dt : 0.01;
  const auto rmn = Earth::meridianPrimeVerticalRadius(pvapre_.pos_blh_rad_m[0]);
  const double rmh = rmn.first + pvapre_.pos_blh_rad_m[2];
  const double rnh = rmn.second + pvapre_.pos_blh_rad_m[2];
  const Vec3 accel = scale(imu.dvel, 1.0 / dt);
  const Vec3 omega = scale(imu.dtheta, 1.0 / dt);
  (void)rmh;
  (void)rnh;

  // F.block(P_ID,V_ID) = I: 位置误差由速度误差积分。
  setBlockIdentity(F, P_ID, V_ID);
  // F.block(V_ID,PHI_ID): 比力投影对姿态误差敏感。
  setBlock(F, V_ID, PHI_ID, Rotation::skewSymmetric(multiply(pvapre_.cbn, accel)));
  setBlock(F, V_ID, BA_ID, pvapre_.cbn);
  setBlock(F, V_ID, SA_ID, multiply(pvapre_.cbn, diag3(accel)));
  setBlock(F, PHI_ID, PHI_ID, scale(Rotation::skewSymmetric(add(Earth::iewn(pvapre_.pos_blh_rad_m),
                                                              Earth::enwn(pvapre_.pos_blh_rad_m,
                                                                          pvapre_.vel_ned_mps))),
                                     -1.0));
  setBlock(F, PHI_ID, BG_ID, scale(pvapre_.cbn, -1.0));
  setBlock(F, PHI_ID, SG_ID, scale(multiply(pvapre_.cbn, diag3(omega)), -1.0));
  const double corr = std::max(options_.imunoise.corr_time, 1.0);
  setBlock(F, BG_ID, BG_ID, scale(identityMatrix3(), -1.0 / corr));
  setBlock(F, BA_ID, BA_ID, scale(identityMatrix3(), -1.0 / corr));
  setBlock(F, SG_ID, SG_ID, scale(identityMatrix3(), -1.0 / corr));
  setBlock(F, SA_ID, SA_ID, scale(identityMatrix3(), -1.0 / corr));

  // G.block(V_ID,VRW_ID) 与 G.block(PHI_ID,ARW_ID) 对齐 reference 噪声驱动矩阵。
  setBlock(G, V_ID, VRW_ID, pvapre_.cbn);
  setBlock(G, PHI_ID, ARW_ID, pvapre_.cbn);
  setBlockIdentity(G, BG_ID, BGSTD_ID);
  setBlockIdentity(G, BA_ID, BASTD_ID);
  setBlockIdentity(G, SG_ID, SGSTD_ID);
  setBlockIdentity(G, SA_ID, SASTD_ID);

  Phi = add(identityMatrix(RANK), scale(F, dt));
  const Matrix GQG = multiply(multiply(G, Qc_), transpose(G));
  Qd = scale(add(multiply(multiply(Phi, GQG), transpose(Phi)), GQG), 0.5 * dt);
}

// 中文说明：position update 使用 predicted antenna position minus GNSS observed position。
void GIEngine::applyPositionUpdate(GnssData& gnss) {
  const Matrix3 dr = Earth::DR(pvacur_.pos_blh_rad_m);
  const Matrix3 dri = Earth::DRi(pvacur_.pos_blh_rad_m);
  const Vec3 lever_n = multiply(pvacur_.cbn, options_.antlever_m);
  const Vec3 antenna_pos = add(pvacur_.pos_blh_rad_m, multiply(dri, lever_n));
  const Vec3 dz_vec = multiply(dr, subtract(antenna_pos, gnss.blh_rad_m));
  Matrix H(3, RANK, 0.0);
  setBlockIdentity(H, 0, P_ID);
  // H_gnsspos / H_pos_phi: reference 使用 +skew(Cbn * antlever)。
  setBlock(H, 0, PHI_ID, Rotation::skewSymmetric(lever_n));
  Matrix R = diagonalMatrix(cwiseProduct(positiveStd(gnss.std_ned_m, 1.0e-3), positiveStd(gnss.std_ned_m, 1.0e-3)));
  const std::vector<double> dz{dz_vec[0], dz_vec[1], dz_vec[2]};
  if (options_.enable_basic_dual_yaw_baseline) {
    // 中文说明：PAPER10E0 Basic 基线保持 KF-GINS 原始 GNSS 位置 3D 更新，
    // 不经过 source-aware/QM R scaling，避免把 LegSA-GINS-Full 模块混入基础对比。
    EKFUpdate(dz, H, R);
    ++position_update_count_;
    return;
  }
  source_aware::SourceMetadata metadata;
  metadata.source = source_aware::MeasurementSource::kReceiverPosition;
  metadata.time = gnss.time;
  metadata.valid = gnss.isvalid;
  metadata.std_xyz = gnss.std_ned_m;
  metadata.quality_flag = gnss.isvalid ? "nominal" : "invalid";
  Matrix scaled_R = R;
  const auto weight = applySourceAwareWeighting(metadata.source, metadata, dz, H, R, scaled_R);
  if (weight.rejected) {
    return;
  }
  EKFUpdate(dz, H, scaled_R);
  ++position_update_count_;
}

bool GIEngine::receiverVelocityUpdateEnabledForTime(double time) const {
  if (!options_.enable_receiver_velocity_update) {
    return false;
  }
  if (options_.receiver_velocity_stress_mode == "disabled") {
    return false;
  }
  if (options_.receiver_velocity_stress_mode == "outage") {
    const double start = options_.receiver_velocity_outage_start_sec;
    const double end = start + std::max(0.0, options_.receiver_velocity_outage_duration_sec);
    return !(time >= start && time <= end);
  }
  return true;
}

double GIEngine::deterministicVelocityNoise(double time, int axis) const {
  const double std_mps = options_.receiver_velocity_additive_noise_std_mps;
  if (std_mps <= 0.0) {
    return 0.0;
  }
  const double seed = static_cast<double>(options_.receiver_velocity_additive_noise_seed + axis * 97);
  const double raw = std::sin(time * 12.9898 + seed * 78.233) * 43758.5453;
  const double frac = raw - std::floor(raw);
  return (2.0 * frac - 1.0) * std_mps;
}

GnssData GIEngine::receiverVelocityStressView(const GnssData& gnss) const {
  GnssData out = gnss;
  if (options_.receiver_velocity_stress_mode == "std_scale") {
    // 中文说明：STD scale 只降低 receiver-native velocity 权重以做诊断筛查，不是调参结论。
    out.vel_std_mps = scale(out.vel_std_mps, std::max(1.0e-6, options_.receiver_velocity_std_scale));
  } else if (options_.receiver_velocity_stress_mode == "additive_noise") {
    // 中文说明：固定 seed 的 additive noise 是 stress protocol，不代表真实传感器故障模型。
    out.vel_ned_mps = add(out.vel_ned_mps,
                          makeVec3(deterministicVelocityNoise(gnss.time, 0),
                                   deterministicVelocityNoise(gnss.time, 1),
                                   deterministicVelocityNoise(gnss.time, 2)));
  }
  return out;
}

// 中文说明：velocity update 使用 antenna velocity - GNSS velocity；若 lever velocity evidence 缺失则保持保守项。
void GIEngine::applyVelocityUpdate(GnssData& gnss) {
  const double dt = imucur_.dt > 0.0 ? imucur_.dt : 0.01;
  const Vec3 omega_b = scale(imucur_.dtheta, 1.0 / dt);
  const Vec3 antenna_vel = add(pvacur_.vel_ned_mps, multiply(pvacur_.cbn, cross(omega_b, options_.antlever_m)));
  const Vec3 dz_vec = subtract(antenna_vel, gnss.vel_ned_mps);
  Matrix H(3, RANK, 0.0);
  setBlockIdentity(H, 0, V_ID);
  setBlock(H, 0, PHI_ID, Rotation::skewSymmetric(multiply(pvacur_.cbn, cross(omega_b, options_.antlever_m))));
  Vec3 stdv = add(positiveStd(gnss.vel_std_mps, 1.0e-3), makeVec3(0.05, 0.05, 0.05));
  Matrix R = diagonalMatrix(cwiseProduct(stdv, stdv));
  const std::vector<double> dz{dz_vec[0], dz_vec[1], dz_vec[2]};
  source_aware::SourceMetadata metadata;
  metadata.source = source_aware::MeasurementSource::kReceiverVelocity;
  metadata.time = gnss.time;
  metadata.valid = gnss.has_velocity;
  metadata.std_xyz = gnss.vel_std_mps;
  metadata.quality_flag = gnss.has_velocity ? "nominal" : "invalid";
  Matrix scaled_R = R;
  const auto weight = applySourceAwareWeighting(metadata.source, metadata, dz, H, R, scaled_R);
  if (weight.rejected) {
    return;
  }
  EKFUpdate(dz, H, scaled_R);
  ++velocity_update_count_;
}

// 中文说明：scheme_C 只对 dual-antenna yaw 观测做鲁棒门控，不放宽 hard=15 deg。
void GIEngine::applyYawUpdate(GnssData& gnss) {
  ++yaw_update_count_;
  const double yaw_obs = gnss.yaw_rad;
  const double yaw_pred = pvacur_.euler_rad[2];
  const double yaw_std = std::max(gnss.yaw_std_rad, options_.yaw_std_min_deg * D2R);
  const double residual = wrapYawResidual(yaw_pred - yaw_obs);
  const double abs_res = std::fabs(residual);
  if (yaw_std >= options_.yaw_std_hard_deg * D2R || abs_res >= options_.yaw_res_hard_deg * D2R) {
    ++yaw_reject_count_;
    return;
  }
  double scale_value = 1.0;
  bool scheme_downweighted = false;
  if (yaw_std >= options_.yaw_std_soft_deg * D2R || abs_res >= options_.yaw_res_soft_deg * D2R) {
    scale_value = options_.yaw_downweight_scale;
    scheme_downweighted = true;
  }
  Matrix H(1, RANK, 0.0);
  H(0, PHI_ID + 2) = -1.0;
  Matrix R(1, 1, scale_value * yaw_std * yaw_std);
  const std::vector<double> dz{residual};
  source_aware::SourceMetadata metadata;
  metadata.source = source_aware::MeasurementSource::kDualAntennaYaw;
  metadata.time = gnss.time;
  metadata.valid = gnss.has_yaw;
  metadata.yaw_std_rad = yaw_std;
  metadata.std_xyz = makeVec3(yaw_std, yaw_std, yaw_std);
  metadata.quality_flag = gnss.has_yaw ? "nominal" : "invalid";
  Matrix scaled_R = R;
  const auto weight = applySourceAwareWeighting(metadata.source, metadata, dz, H, R, scaled_R);
  if (weight.rejected) {
    ++yaw_reject_count_;
    return;
  }
  if (scheme_downweighted ||
      (options_.source_aware_policy_config.enable_source_aware_weighting &&
       weight.combined_R_scale > 1.0)) {
    ++yaw_downweight_count_;
  } else {
    ++yaw_normal_count_;
  }
  EKFUpdate(dz, H, scaled_R);
}

// 中文说明：PAPER10E0 Basic Dual-Yaw EKF 的唯一新增观测。
// 该函数复用 KF-GINS 的 21 维误差状态、EKFUpdate 和 stateFeedback；
// 不改变 INS 机械编排、误差传播或状态反馈机制，也不做 robust gate、downweight、reject、hold 或 fallback。
void GIEngine::applyBasicDualYawUpdate(GnssData& gnss) {
  ++yaw_update_count_;
  const double yaw_obs = gnss.yaw_rad;
  const double yaw_pred = pvacur_.euler_rad[2];
  // 中文说明：残差定义为 pred - obs；结合 H_phi_z=-1 后，EKFUpdate 内部的 dz-Hdx 与
  // stateFeedback 的 qpn 左乘反馈符号一致。该符号由 PAPER10E0 数值扰动测试验证。
  const double residual = wrapYawResidual(yaw_pred - yaw_obs);
  const double yaw_std = std::max(options_.basic_dual_yaw_fixed_std_deg * D2R, 1.0e-6);
  Matrix H(1, RANK, 0.0);
  // 中文说明：H_yaw 只作用于姿态误差状态块的 yaw 分量，列数等于 KF-GINS 21 维误差状态。
  H(0, PHI_ID + 2) = -1.0;
  // 中文说明：R_yaw 使用固定角度标准差，内部单位为 rad^2；不使用 dynamic yaw_std 或 source-aware 放大。
  Matrix R(1, 1, yaw_std * yaw_std);
  const std::vector<double> dz{residual};
  EKFUpdate(dz, H, R);
  ++yaw_normal_count_;
}

void GIEngine::applyRawDopplerUpdateForTime(double update_time) {
  if (!options_.raw_doppler_config.enable_raw_doppler || !raw_doppler_status_.solver_enabled) {
    return;
  }
  const RawDopplerVelocityMeasurement* best = nullptr;
  double best_dt = options_.raw_doppler_config.raw_doppler_time_tolerance_sec;
  for (const auto& measurement : raw_doppler_measurements_) {
    const double dt = std::fabs(measurement.time - update_time);
    if (dt <= best_dt) {
      best = &measurement;
      best_dt = dt;
    }
  }
  if (!best) {
    return;
  }
  if (!RawDopplerFactor::isProviderBacked(*best) || best->sat_count < options_.raw_doppler_config.raw_doppler_min_sat) {
    ++raw_doppler_status_.reject_count;
    return;
  }
  const double imu_dt = imucur_.dt > 0.0 ? imucur_.dt : 0.01;
  const Vec3 omega_b = scale(imucur_.dtheta, 1.0 / imu_dt);
  const Vec3 lever_vel_n = multiply(pvacur_.cbn, cross(omega_b, options_.antlever_m));
  const Vec3 antenna_vel_n = add(pvacur_.vel_ned_mps, lever_vel_n);
  const Vec3 residual_vec = subtract(antenna_vel_n, best->velocity_ned_mps);
  const double residual = norm(residual_vec);
  if (!options_.source_aware_policy_config.enable_source_aware_weighting &&
      residual > options_.raw_doppler_config.raw_doppler_residual_gate_mps) {
    ++raw_doppler_status_.reject_count;
    raw_doppler_residual_norms_.push_back(residual);
    return;
  }
  Matrix H(3, RANK, 0.0);
  setBlockIdentity(H, 0, V_ID);
  setBlock(H, 0, PHI_ID, Rotation::skewSymmetric(lever_vel_n));
  const Vec3 stdv = RawDopplerFactor::positiveStd(*best);
  Matrix R = diagonalMatrix(scale(cwiseProduct(stdv, stdv), options_.raw_doppler_config.raw_doppler_R_scale));
  // 中文说明：dz = GNSS1 天线相位中心速度 - raw Doppler velocity；
  // 杆臂速度与 receiver-native velocity update 使用相同的 antlever_m 及 H_phi 符号。
  const std::vector<double> dz{residual_vec[0], residual_vec[1], residual_vec[2]};
  source_aware::SourceMetadata metadata;
  metadata.source = source_aware::MeasurementSource::kRawDopplerVelocity;
  metadata.time = best->time;
  metadata.valid = RawDopplerFactor::isProviderBacked(*best);
  metadata.std_xyz = stdv;
  metadata.residual_norm = residual;
  metadata.time_diff_sec = best->time - update_time;
  metadata.sat_count = best->sat_count;
  metadata.provider_status = best->provider_status;
  metadata.quality_flag = best->provider_status == "available" ? "nominal" : best->provider_status;
  metadata.covariance_available = true;
  metadata.spike_candidate = residual > options_.raw_doppler_config.raw_doppler_residual_gate_mps;
  Matrix scaled_R = R;
  const auto weight = applySourceAwareWeighting(metadata.source, metadata, dz, H, R, scaled_R);
  if (weight.rejected) {
    ++raw_doppler_status_.reject_count;
    raw_doppler_residual_norms_.push_back(residual);
    return;
  }
  EKFUpdate(dz, H, scaled_R);
  raw_doppler_residual_norms_.push_back(residual);
  ++raw_doppler_status_.update_count;
  if (raw_doppler_status_.sat_count_min == 0 || best->sat_count < raw_doppler_status_.sat_count_min) {
    raw_doppler_status_.sat_count_min = best->sat_count;
  }
  raw_doppler_status_.sat_count_max = std::max(raw_doppler_status_.sat_count_max, best->sat_count);
  std::vector<std::size_t> sat_counts;
  for (const auto& measurement : raw_doppler_measurements_) {
    if (measurement.provider_status == "available" && measurement.sat_count >= options_.raw_doppler_config.raw_doppler_min_sat) {
      sat_counts.push_back(measurement.sat_count);
    }
  }
  if (!sat_counts.empty()) {
    std::sort(sat_counts.begin(), sat_counts.end());
    raw_doppler_status_.sat_count_median = sat_counts[sat_counts.size() / 2];
  }
  if (!raw_doppler_residual_norms_.empty()) {
    std::vector<double> sorted = raw_doppler_residual_norms_;
    std::sort(sorted.begin(), sorted.end());
    const std::size_t index = static_cast<std::size_t>(0.95 * static_cast<double>(sorted.size() - 1));
    raw_doppler_status_.residual_p95_mps = sorted[index];
  }
}

void GIEngine::applyGo2AttitudeWeakPriorForTime(double update_time) {
  if (!options_.go2_attitude_prior_config.enable_go2_attitude_weak_prior ||
      !go2_attitude_prior_status_.solver_enabled) {
    return;
  }
  const Go2AttitudeWeakPriorMeasurement* best = nullptr;
  double best_dt = options_.go2_attitude_prior_config.go2_attitude_prior_time_tolerance_sec;
  for (const auto& measurement : go2_attitude_priors_) {
    const double dt = std::fabs(measurement.time - update_time);
    if (dt <= best_dt) {
      best = &measurement;
      best_dt = dt;
    }
  }
  if (!best) {
    return;
  }
  if (!Go2WeakPriorFactor::isActive(*best)) {
    ++go2_attitude_prior_status_.reject_count;
    return;
  }
  const std::vector<double> dz = Go2WeakPriorFactor::residual(pvacur_, *best);
  Matrix H = Go2WeakPriorFactor::designMatrix(pvacur_);
  Matrix R = Go2WeakPriorFactor::covariance(*best, options_.go2_attitude_prior_config);
  source_aware::SourceMetadata metadata;
  metadata.source = source_aware::MeasurementSource::kGo2AttitudeRollPitch;
  metadata.time = best->time;
  metadata.valid = best->source_status == "active";
  metadata.std_xyz = makeVec3(best->std_roll_rad, best->std_pitch_rad, best->std_pitch_rad);
  metadata.yaw_std_rad = std::max(best->std_roll_rad, best->std_pitch_rad);
  metadata.time_diff_sec = best->time - update_time;
  metadata.provider_status = best->source_status == "active" ? "available" : best->source_status;
  metadata.quality_flag = best->quality_flag;
  metadata.covariance_available = true;
  Matrix scaled_R = R;
  if (options_.go2_attitude_prior_config.go2_attitude_prior_sourceaware) {
    const auto weight = applySourceAwareWeighting(metadata.source, metadata, dz, H, R, scaled_R);
    if (weight.rejected) {
      ++go2_attitude_prior_status_.reject_count;
      return;
    }
  }
  EKFUpdate(dz, H, scaled_R);
  go2_roll_residuals_.push_back(std::fabs(dz[0]));
  go2_pitch_residuals_.push_back(std::fabs(dz[1]));
  ++go2_attitude_prior_status_.update_count;
  auto p95 = [](std::vector<double> values) {
    if (values.empty()) {
      return 0.0;
    }
    std::sort(values.begin(), values.end());
    return values[static_cast<std::size_t>(0.95 * static_cast<double>(values.size() - 1))];
  };
  go2_attitude_prior_status_.residual_roll_p95_rad = p95(go2_roll_residuals_);
  go2_attitude_prior_status_.residual_pitch_p95_rad = p95(go2_pitch_residuals_);
}

void GIEngine::applyGo2VelocityDiagnosticPriorForTime(double update_time) {
  const bool controlled_horizontal =
      options_.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior;
  if (!options_.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic ||
      !go2_velocity_diagnostic_prior_status_.solver_enabled ||
      (!options_.go2_velocity_prior_diagnostic_config.go2_diagnostic_prior_only && !controlled_horizontal)) {
    return;
  }
  const Go2VelocityDiagnosticPriorMeasurement* best = nullptr;
  double best_dt = options_.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_tolerance_sec;
  for (const auto& measurement : go2_velocity_diagnostic_priors_) {
    if (!measurement.update_flag) {
      continue;
    }
    const double dt = std::fabs(measurement.time - update_time);
    if (dt <= best_dt) {
      best = &measurement;
      best_dt = dt;
    }
  }
  if (!best) {
    return;
  }
  if (best->source_status != "active" ||
      (!best->diagnostic_only && !controlled_horizontal) ||
      best->go2_velocity_truth_claim) {
    ++go2_velocity_diagnostic_prior_status_.reject_count;
    return;
  }
  const Vec3 stdv = positiveStd(
      scale(best->std_ned_mps, std::max(1.0e-6, options_.go2_velocity_prior_diagnostic_config.go2_velocity_prior_std_scale)),
      1.0e-3);
  const Vec3 residual_vec = subtract(pvacur_.vel_ned_mps, best->velocity_ned_mps);
  const bool horizontal_2d =
      controlled_horizontal &&
      options_.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_mode == "horizontal_2d";
  Matrix H(horizontal_2d ? 2 : 3, RANK, 0.0);
  Matrix R(horizontal_2d ? 2 : 3, horizontal_2d ? 2 : 3, 0.0);
  std::vector<double> dz;
  if (horizontal_2d) {
    H(0, V_ID + 0) = 1.0;
    H(1, V_ID + 1) = 1.0;
    R(0, 0) = stdv[0] * stdv[0];
    R(1, 1) = stdv[1] * stdv[1];
    dz = {residual_vec[0], residual_vec[1]};
  } else {
    setBlockIdentity(H, 0, V_ID);
    R = diagonalMatrix(cwiseProduct(stdv, stdv));
    dz = {residual_vec[0], residual_vec[1], residual_vec[2]};
  }
  Matrix scaled_R = R;
  if (controlled_horizontal &&
      options_.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_source_aware_enabled) {
    source_aware::SourceMetadata metadata;
    metadata.source = source_aware::MeasurementSource::kGo2HorizontalVelocity;
    metadata.time = best->time;
    metadata.valid = best->source_status == "active";
    metadata.std_xyz = makeVec3(stdv[0], stdv[1], options_.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_prior_vertical_disabled ? 999.0 : stdv[2]);
    metadata.residual_norm = horizontal_2d ? std::sqrt(residual_vec[0] * residual_vec[0] + residual_vec[1] * residual_vec[1])
                                           : norm(residual_vec);
    metadata.time_diff_sec = best->time - update_time;
    metadata.provider_status = best->source_status == "active" ? "available" : best->source_status;
    metadata.quality_flag = best->quality_flag.empty() ? "nominal" : best->quality_flag;
    metadata.covariance_available = true;
    const auto weight = applySourceAwareWeighting(metadata.source, metadata, dz, H, R, scaled_R);
    if (weight.rejected) {
      ++go2_velocity_diagnostic_prior_status_.reject_count;
      return;
    }
  }
  EKFUpdate(dz, H, scaled_R);
  ++go2_velocity_diagnostic_prior_status_.update_count;
  if (horizontal_2d || best->std_ned_mps[2] >= 999.0 ||
      best->prior_policy.find("horizontal") != std::string::npos) {
    go2_velocity_diagnostic_prior_status_.horizontal_only = true;
    go2_velocity_diagnostic_prior_status_.vertical_disabled = true;
    ++go2_velocity_diagnostic_prior_status_.horizontal_update_count;
  }
}

void GIEngine::applyFgoFeedbackForTime(double update_time) {
  if (!options_.fgo_feedback_config.enable_fgo_feedback || !fgo_feedback_status_.solver_enabled) {
    return;
  }
  const fgo_feedback::FgoFeedbackObservation* best = nullptr;
  double best_dt = options_.fgo_feedback_config.fgo_feedback_time_tolerance_sec;
  for (const auto& obs : fgo_feedback_observations_) {
    const double dt = std::fabs(obs.time - update_time);
    if (dt <= best_dt) {
      best = &obs;
      best_dt = dt;
    }
  }
  if (!best) {
    return;
  }
  fgo_feedback::FgoFeedbackTraceRow trace;
  trace.update_time = update_time;
  trace.observation_time = best->time;
  trace.source_window_start = best->source_window_start;
  trace.source_window_end = best->source_window_end;

  const Vec3 current_ned = multiply(Earth::DR(options_.init_pos_blh_rad_m),
                                    subtract(pvacur_.pos_blh_rad_m, options_.init_pos_blh_rad_m));
  const Vec3 position_residual = subtract(current_ned, best->position_ned_m);
  const Vec3 velocity_residual = subtract(pvacur_.vel_ned_mps, best->velocity_ned_mps);
  const Vec3 attitude_residual = makeVec3(
      fgo_feedback::wrapRadians(pvacur_.euler_rad[0] - best->attitude_rad[0]),
      fgo_feedback::wrapRadians(pvacur_.euler_rad[1] - best->attitude_rad[1]),
      fgo_feedback::wrapRadians(pvacur_.euler_rad[2] - best->attitude_rad[2]));
  trace.position_norm_m = norm(position_residual);
  trace.velocity_norm_mps = norm(velocity_residual);
  trace.attitude_norm_deg = R2D * norm(attitude_residual);
  trace.yaw_residual_deg = fgo_feedback::wrapDegrees(R2D * attitude_residual[2]);

  auto reject = [&](const std::string& reason) {
    trace.accepted = 0;
    trace.reject_reason = reason;
    fgo_feedback_trace_.push_back(trace);
    ++fgo_feedback_status_.reject_count;
    if (reason == "future_data") {
      ++fgo_feedback_status_.future_data_reject_count;
      fgo_feedback_status_.no_future_data = false;
    }
  };

  if (!best->feedback_valid) {
    reject("feedback_valid_false");
    return;
  }
  if (options_.fgo_feedback_config.fgo_feedback_no_future_data_required &&
      best->source_window_end > update_time + 1.0e-9) {
    reject("future_data");
    return;
  }
  if (update_time - last_fgo_feedback_time_ <
      options_.fgo_feedback_config.fgo_feedback_min_interval_s - 1.0e-9) {
    reject("min_interval");
    return;
  }
  if (options_.fgo_feedback_config.fgo_feedback_position_enabled &&
      trace.position_norm_m > options_.fgo_feedback_config.fgo_feedback_max_position_correction_m) {
    reject("position_gate");
    return;
  }
  if (options_.fgo_feedback_config.fgo_feedback_velocity_enabled &&
      trace.velocity_norm_mps > options_.fgo_feedback_config.fgo_feedback_max_velocity_correction_mps) {
    reject("velocity_gate");
    return;
  }
  if (options_.fgo_feedback_config.fgo_feedback_attitude_enabled &&
      trace.attitude_norm_deg > options_.fgo_feedback_config.fgo_feedback_max_attitude_correction_deg) {
    reject("attitude_gate");
    return;
  }

  std::size_t rows = 0;
  if (options_.fgo_feedback_config.fgo_feedback_position_enabled) {
    rows += 3;
  }
  if (options_.fgo_feedback_config.fgo_feedback_velocity_enabled) {
    rows += 3;
  }
  if (options_.fgo_feedback_config.fgo_feedback_attitude_enabled) {
    rows += 3;
  }
  if (rows == 0) {
    reject("no_state_block_enabled");
    return;
  }
  Matrix H(rows, RANK, 0.0);
  Matrix R(rows, rows, 0.0);
  std::vector<double> dz(rows, 0.0);
  std::size_t row = 0;
  const double r_scale = std::max(1.0, options_.fgo_feedback_config.fgo_feedback_covariance_scale);
  if (options_.fgo_feedback_config.fgo_feedback_position_enabled) {
    for (std::size_t i = 0; i < 3; ++i) {
      H(row, P_ID + i) = 1.0;
      R(row, row) = best->position_std_m[i] * best->position_std_m[i] * r_scale;
      dz[row] = position_residual[i];
      ++row;
    }
  }
  if (options_.fgo_feedback_config.fgo_feedback_velocity_enabled) {
    for (std::size_t i = 0; i < 3; ++i) {
      H(row, V_ID + i) = 1.0;
      R(row, row) = best->velocity_std_mps[i] * best->velocity_std_mps[i] * r_scale;
      dz[row] = velocity_residual[i];
      ++row;
    }
  }
  if (options_.fgo_feedback_config.fgo_feedback_attitude_enabled) {
    for (std::size_t i = 0; i < 3; ++i) {
      H(row, PHI_ID + i) = -1.0;
      R(row, row) = best->attitude_std_rad[i] * best->attitude_std_rad[i] * r_scale;
      dz[row] = attitude_residual[i];
      ++row;
    }
  }
  // 中文说明：N8G 通过 EKFUpdate 累积误差状态，随后由统一 stateFeedback 生效；这里不直接改 pvacur_。
  EKFUpdate(dz, H, R);
  trace.accepted = 1;
  trace.reject_reason = "";
  fgo_feedback_trace_.push_back(trace);
  last_fgo_feedback_time_ = update_time;
  ++fgo_feedback_status_.update_count;
  ++fgo_feedback_status_.accept_count;
  fgo_feedback_position_norms_.push_back(trace.position_norm_m);
  fgo_feedback_velocity_norms_.push_back(trace.velocity_norm_mps);
  fgo_feedback_attitude_norms_deg_.push_back(trace.attitude_norm_deg);
  fgo_feedback_status_.correction_position_p50_m = percentile(fgo_feedback_position_norms_, 0.50);
  fgo_feedback_status_.correction_position_p95_m = percentile(fgo_feedback_position_norms_, 0.95);
  fgo_feedback_status_.correction_position_max_m =
      fgo_feedback_position_norms_.empty() ? 0.0 : *std::max_element(fgo_feedback_position_norms_.begin(), fgo_feedback_position_norms_.end());
  fgo_feedback_status_.correction_velocity_p50_mps = percentile(fgo_feedback_velocity_norms_, 0.50);
  fgo_feedback_status_.correction_velocity_p95_mps = percentile(fgo_feedback_velocity_norms_, 0.95);
  fgo_feedback_status_.correction_velocity_max_mps =
      fgo_feedback_velocity_norms_.empty() ? 0.0 : *std::max_element(fgo_feedback_velocity_norms_.begin(), fgo_feedback_velocity_norms_.end());
  fgo_feedback_status_.correction_attitude_p50_deg = percentile(fgo_feedback_attitude_norms_deg_, 0.50);
  fgo_feedback_status_.correction_attitude_p95_deg = percentile(fgo_feedback_attitude_norms_deg_, 0.95);
  fgo_feedback_status_.correction_attitude_max_deg =
      fgo_feedback_attitude_norms_deg_.empty() ? 0.0 : *std::max_element(fgo_feedback_attitude_norms_deg_.begin(), fgo_feedback_attitude_norms_deg_.end());
  fgo_feedback_status_.residual_p95 = percentile(fgo_feedback_velocity_norms_, 0.95);
}

quality_aware::QAObservation GIEngine::buildQAObservation(const GnssData& gnss) const {
  quality_aware::QAObservation observation;
  observation.time = gnss.time;
  observation.algorithm_id = options_.algorithm_id.empty() ? options_.run_label : options_.algorithm_id;
  observation.case_id = options_.ablation_variant;
  observation.dataset_id = options_.clean_input_provenance_label;
  observation.a1_available = gnss.has_yaw && std::isfinite(gnss.yaw_rad) && std::isfinite(gnss.yaw_std_rad);
  const bool explicit_a1_quality =
      options_.qa_fallback_config.a1_quality_source.find("relpos_diff") != std::string::npos ||
      options_.qa_fallback_config.a1_quality_source.find("status_yaw") != std::string::npos;
  observation.a1_relpos_diff_valid =
      observation.a1_available && explicit_a1_quality &&
      options_.qa_fallback_config.a1_relpos_diff_valid_default;
  observation.a1_baseline_m = options_.qa_fallback_config.a1_baseline_m_default;
  observation.a1_baseline_available = options_.qa_fallback_config.a1_baseline_default_available;
  observation.a1_baseline_expected_m = options_.qa_fallback_config.expected_a1_baseline_m;
  observation.a1_baseline_expected_available = true;
  observation.a1_valid_ratio_window = options_.qa_fallback_config.a1_valid_ratio_default;
  observation.a1_valid_ratio_available = options_.qa_fallback_config.a1_valid_ratio_default_available;
  observation.a1_yaw_std_deg = std::fabs(gnss.yaw_std_rad) * R2D;
  observation.a1_yaw_std_available = observation.a1_available;
  observation.a1_yaw_residual_deg = wrapYawResidual(pvacur_.euler_rad[2] - gnss.yaw_rad) * R2D;
  observation.a1_yaw_residual_available = observation.a1_available;
  observation.gnss_pos_available = gnss.isvalid;
  observation.gnss_pos_valid = gnss.isvalid;
  observation.gnss_status_or_fix = gnss.isvalid ? "runtime_15col_valid" : "invalid";
  observation.gnss_pos_std_h_m =
      std::hypot(std::fabs(gnss.std_ned_m[0]), std::fabs(gnss.std_ned_m[1]));
  observation.gnss_pos_std_h_available = true;
  observation.gnss_pos_std_u_m = std::fabs(gnss.std_ned_m[2]);
  observation.gnss_pos_std_u_available = true;
  const Matrix3 dr = Earth::DR(pvacur_.pos_blh_rad_m);
  const Matrix3 dri = Earth::DRi(pvacur_.pos_blh_rad_m);
  const Vec3 lever_n = multiply(pvacur_.cbn, options_.antlever_m);
  const Vec3 antenna_pos = add(pvacur_.pos_blh_rad_m, multiply(dri, lever_n));
  const Vec3 pos_residual = multiply(dr, subtract(antenna_pos, gnss.blh_rad_m));
  observation.gnss_pos_innovation_m = std::sqrt(pos_residual[0] * pos_residual[0] +
                                                pos_residual[1] * pos_residual[1] +
                                                pos_residual[2] * pos_residual[2]);
  observation.gnss_pos_innovation_available = true;
  observation.raw_doppler_available = raw_doppler_status_.solver_enabled;
  observation.raw_doppler_count = raw_doppler_status_.valid_epoch_count;
  observation.raw_doppler_residual = raw_doppler_status_.residual_p95_mps;
  observation.raw_doppler_residual_available = raw_doppler_status_.residual_p95_mps > 0.0;
  observation.go2_body_state_available = go2_velocity_diagnostic_prior_status_.solver_enabled ||
                                         go2_attitude_prior_status_.solver_enabled;
  observation.go2_imu_available = go2_attitude_prior_status_.solver_enabled;
  observation.selected_feedback_allowed_nominal = options_.fgo_feedback_config.enable_fgo_feedback &&
                                                  fgo_feedback_status_.solver_enabled;
  observation.filter_output_finite =
      std::isfinite(pvacur_.pos_blh_rad_m[0]) && std::isfinite(pvacur_.pos_blh_rad_m[1]) &&
      std::isfinite(pvacur_.pos_blh_rad_m[2]) && std::isfinite(pvacur_.euler_rad[2]);
  observation.covariance_finite = checkCov();
  return observation;
}

void GIEngine::enrichGo2ReadinessMetadata(source_aware::SourceMetadata& metadata, double update_time) {
  if (!options_.go2_readiness_lsim_metadata_config.enable_go2_readiness_lsim_metadata ||
      !go2_readiness_lsim_metadata_status_.solver_enabled ||
      !options_.source_aware_policy_config.source_aware_go2_readiness_lsim_enabled) {
    return;
  }
  const Go2ReadinessLsimMetadataMeasurement* best = nullptr;
  double best_dt = options_.go2_readiness_lsim_metadata_config.go2_readiness_lsim_time_tolerance_sec;
  for (const auto& measurement : go2_readiness_lsim_metadata_) {
    if (measurement.source_status != "active" || !measurement.source_valid) {
      continue;
    }
    const double dt = std::fabs(measurement.time - update_time);
    if (dt <= best_dt) {
      best = &measurement;
      best_dt = dt;
    }
  }
  if (!best) {
    return;
  }
  metadata.go2_readiness_metadata_available = true;
  metadata.go2_motion_state = best->motion_state.empty() ? "UNKNOWN" : best->motion_state;
  metadata.go2_contact_label = best->contact_label;
  metadata.go2_readiness_score = best->readiness_score;
  metadata.go2_readiness_flag = best->readiness_flag;
  metadata.go2_stance_stable = best->stance_stable;
  metadata.go2_in_place_turn = best->in_place_turn;
  metadata.go2_impact_or_rough = best->impact_or_rough;
  metadata.go2_readiness_low = best->readiness_low;
  ++go2_readiness_lsim_metadata_status_.matched_metadata_count;
}

source_aware::SourceWeightResult GIEngine::applySourceAwareWeighting(
    source_aware::MeasurementSource source,
    const source_aware::SourceMetadata& metadata,
    const std::vector<double>& dz,
    const Matrix& H,
    const Matrix& R,
    Matrix& scaled_R) {
  scaled_R = R;
  source_aware::ObservationInnovation innovation;
  innovation.residual = dz;
  innovation.residual_norm = vectorNorm(dz);
  innovation.base_R_trace = matrixTrace(R);
  const Matrix hph = multiply(multiply(H, Cov_), transpose(H));
  const Matrix innovation_covariance = add(hph, R);
  innovation.hph_trace = matrixTrace(hph);
  innovation.innovation_cov_trace = matrixTrace(innovation_covariance);
  innovation.dof = dz.size();
  // 中文说明：N6B OIM 使用创新协方差 S=H*P*H^T+R 计算 NIS；不从 trace 或评价结果取权重。
  if (options_.source_aware_policy_config.source_aware_use_innovation_covariance && !dz.empty()) {
    try {
      const Matrix s_inv = inverse(innovation_covariance);
      const std::vector<double> weighted_residual = multiply(s_inv, dz);
      innovation.nis = std::max(0.0, dotVector(dz, weighted_residual));
      innovation.normalized_innovation =
          std::sqrt(std::max(0.0, innovation.nis / static_cast<double>(std::max<std::size_t>(1, innovation.dof))));
      innovation.used_innovation_covariance = true;
    } catch (const std::exception&) {
      innovation.used_innovation_covariance = false;
    }
  }
  if (!innovation.used_innovation_covariance) {
    innovation.normalized_innovation =
        innovation.residual_norm / std::sqrt(std::max(1.0e-12, innovation.base_R_trace + innovation.hph_trace));
  }
  source_aware::SourceMetadata metadata_copy = metadata;
  metadata_copy.source = source;
  metadata_copy.residual_norm = innovation.residual_norm;
  enrichGo2ReadinessMetadata(metadata_copy, metadata_copy.time);
  source_aware::SourceWeightResult result = source_aware_policy_.evaluate(metadata_copy, innovation);
  source_aware::QualityStateDecision quality_decision;
  if (quality_state_manager_.enabled()) {
    quality_decision = quality_state_manager_.evaluate(metadata_copy, innovation, result);
    if (quality_decision.action_alters_update) {
      result.accepted = quality_decision.accepted;
      result.rejected = quality_decision.rejected;
      result.combined_R_scale =
          std::min(result.source_cap, std::max(1.0, result.combined_R_scale * quality_decision.r_scale_multiplier));
    }
  }
  const bool source_aware_active = source_aware_policy_.enabledFor(source);
  const bool qm_active_scaling =
      quality_state_manager_.enabled() && quality_decision.action_alters_update && !quality_decision.rejected;
  if (source_aware_active || qm_active_scaling) {
    scaled_R = scale(R, result.combined_R_scale);
    result.scaled_R_trace = matrixTrace(scaled_R);
    if (source_aware_active && options_.source_aware_policy_config.source_aware_trace_enabled) {
      source_aware_trace_.add(metadata_copy.time, update_count_ + 1, result);
    }
  }
  if (source_aware_active) {
    ++source_aware_evaluation_count_;
    if (std::fabs(result.combined_R_scale - 1.0) > 1.0e-12) {
      ++source_aware_weight_changed_count_;
    }
  }
  if (quality_state_manager_.traceEnabled()) {
    quality_state_trace_.add(metadata_copy.time, update_count_ + 1, result, quality_decision);
  }
  return result;
}

double GIEngine::wrapYawResidual(double residual_rad) const {
  return Rotation::wrapRad(residual_rad);
}

Matrix GIEngine::covarianceMatrix() const {
  return Cov_;
}

void GIEngine::setCovarianceMatrix(const Matrix& matrix) {
  Cov_ = matrix;
}

}  // namespace legsa_v23_port_core
