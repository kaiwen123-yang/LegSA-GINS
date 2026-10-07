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

#include "legsa_v23_port_core/factors/body_velocity_model.hpp"
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
  if (options_.dual_antenna_measurement_model == "baseline3d") {
    if (!std::isfinite(options_.baseline3d_length_m) || options_.baseline3d_length_m <= 0.0 ||
        (options_.baseline3d_source == "dual_pvt" &&
         (!std::isfinite(options_.baseline3d_k_b) || options_.baseline3d_k_b <= 0.0))) {
      throw std::runtime_error("BASELINE3D_REQUIRED_POSITIVE_CONFIG");
    }
    if (options_.quality_state_manager_config.enable_multi_state_qm ||
        options_.qa_fallback_config.enable_qa_fallback || options_.qa_fallback_config.qa_active_mode ||
        options_.algorithm_id == quality_aware::kLegsaQaFallbackEkf) {
      throw std::runtime_error("BASELINE3D_SCOPE_REQUIRES_QA_QM_OFF");
    }
  }
  if (options_.heading_source_policy != "configured") {
    if ((options_.heading_source_policy != "pvt_priority_control" &&
         options_.heading_source_policy != "pvt_priority_fallback") ||
        options_.runtime_contract != "research_experiment" ||
        options_.baseline3d_source != "external_carrier" ||
        options_.dual_antenna_measurement_model != "baseline3d" ||
        options_.dual_yaw_prediction_model == "legacy" ||
        options_.enable_basic_dual_yaw_baseline ||
        !options_.enable_dual_yaw_update || !options_.yaw_scheme_C_enabled)
      throw std::runtime_error("PVT_PRIORITY_INVALID_ENGINE_CONTRACT");
  }
  validateSupportPoseConfig(options_.support_pose_config, options_.runtime_contract);
  if(supportPoseEnabled() && jointCloneEnabled()) throw std::runtime_error("SUPPORT_POSE_SEPARATE_JOINT_STATE");
  validateAttitudeCloneConfig(options_.attitude_clone_config, options_.runtime_contract);
  validateArcCloneConfig(options_.arc_clone_config, options_.runtime_contract);
  if (options_.arc_clone_config.mode!="off" && options_.attitude_clone_config.mode!="off")
    throw std::runtime_error("ARC_AND_FOOT_CLONE_MODES_ARE_EXCLUSIVE");
  if (jointCloneEnabled() &&
      (options_.qa_fallback_config.enable_qa_fallback || options_.qa_fallback_config.qa_active_mode ||
       options_.algorithm_id == quality_aware::kLegsaQaFallbackEkf ||
       options_.quality_state_manager_config.enable_multi_state_qm))
    throw std::runtime_error("ATTITUDE_CLONE_REQUIRES_FULL_UNCLIPPED_FEEDBACK_QA_QM_OFF");
  const auto& body_cfg = options_.go2_velocity_prior_diagnostic_config;
  if (body_cfg.go2_velocity_prior_time_policy != "legacy_absolute_nearest" &&
      body_cfg.go2_velocity_prior_time_policy != "causal_unique_latest" &&
      body_cfg.go2_velocity_prior_time_policy != "causal_recorded_dependencies_unique_latest")
    throw std::runtime_error("NED_HV_UNKNOWN_TIME_POLICY");
  if ((body_cfg.go2_velocity_prior_time_policy == "causal_unique_latest" ||
       body_cfg.go2_velocity_prior_time_policy == "causal_recorded_dependencies_unique_latest") &&
      (options_.runtime_contract != "research_experiment" ||
       !body_cfg.enable_go2_horizontal_velocity_prior ||
       !body_cfg.enable_go2_velocity_prior_diagnostic ||
       body_cfg.go2_horizontal_velocity_frame != "ned" ||
       body_cfg.go2_horizontal_velocity_prior_mode != "horizontal_2d" ||
       !body_cfg.go2_horizontal_velocity_prior_vertical_disabled ||
       !std::isfinite(body_cfg.go2_velocity_prior_time_tolerance_sec) ||
       body_cfg.go2_velocity_prior_time_tolerance_sec < 0.0))
    throw std::runtime_error("NED_HV_CAUSAL_POLICY_REQUIRES_RESEARCH_HORIZONTAL_NED");
  if (body_cfg.enable_go2_horizontal_velocity_prior && body_cfg.go2_horizontal_velocity_frame == "body_frd") {
    if (options_.runtime_contract != "research_experiment" ||
        body_cfg.go2_horizontal_velocity_prior_mode != "horizontal_2d" ||
        !body_cfg.go2_horizontal_velocity_prior_vertical_disabled ||
        !std::isfinite(body_cfg.go2_body_velocity_update_period_s) || !(body_cfg.go2_body_velocity_update_period_s > 0.0) ||
        !std::isfinite(body_cfg.go2_velocity_prior_time_tolerance_sec) || body_cfg.go2_velocity_prior_time_tolerance_sec < 0.0 ||
        !std::isfinite(body_cfg.go2_velocity_prior_std_scale) || !(body_cfg.go2_velocity_prior_std_scale > 0.0))
      throw std::runtime_error("BODY_HV_INVALID_ENGINE_CONTRACT");
  }
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
  research_next_body_hv_tick_ = options_.starttime +
      options_.go2_velocity_prior_diagnostic_config.go2_body_velocity_update_period_s;
  research_last_body_hv_attempt_time_ = -1.0e100;
  body_velocity_events_.clear();
  resetNedVelocitySourceGeneration("initialize");
  heading_source_policy_ = HeadingSourcePolicy{};
  heading_source_counts_ = HeadingSourceCounts{};
  heading_source_events_.clear();
  support_pose_active_=false;support_pose_stream_started_=false;next_support_pose_event_=0;
  support_pose_counts_=SupportPoseCounts{};support_pose_counts_.source_rows=support_pose_events_.size();
  support_pose_diagnostics_.clear();support_pose_applied_ids_.clear();support_pose_revocations_.clear();
  support_pose_revoked_.clear();
  attitude_clone_active_=false;
  attitude_clone_owner_="NONE";
  initializeArcDiagnostics();
  attitude_clone_cross_=Matrix(RANK,3,0.0);
  attitude_clone_cov_=Matrix(3,3,0.0);
  attitude_clone_error_={0.0,0.0,0.0};
  attitude_clone_used_ids_.clear();foot_used_endpoint_ids_.clear();
  next_foot_event_=0;foot_stream_started_=false;foot_event_diagnostics_.clear();
  attitude_clone_counts_=AttitudeCloneCounts{};
  attitude_clone_counts_.source_rows=foot_events_.size();
  if (jointCloneEnabled())
    attitude_clone_weights_=attitude_clone::fixedCurrentWeights(Cov_);

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
  const auto& policy = options_.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_policy;
  const bool dependencies = policy == "causal_recorded_dependencies_unique_latest";
  if (policy == "causal_unique_latest" || dependencies) {
    for (std::size_t i = 0; i < measurements.size(); ++i) {
      const auto& row = measurements[i];
      if (row.observation_frame != "ned") throw std::runtime_error("NED_HV_SOURCE_FRAME_MISMATCH");
      if (dependencies) {
        const bool known = row.dependency_schema == "HV_CALIBRATED_GNSS18_TIME_V1";
        if (known != row.dependency_metadata_available)
          throw std::runtime_error("NED_HV_DEPENDENCY_SCHEMA_STATE_MISMATCH");
        if (!known) continue;
        if (row.dependency_source_row_index != i)
          throw std::runtime_error("NED_HV_DEPENDENCY_ROW_INDEX_MISMATCH");
        if (!std::isfinite(row.time) || row.dependency_source_time_bits_hex != arcSourceTimeBits(row.time))
          throw std::runtime_error("NED_HV_DEPENDENCY_SOURCE_TIME_BITS_MISMATCH");
        if (row.dependency_supported && (!std::isfinite(row.dependency_ready_source_time_s) ||
            row.dependency_ready_source_time_s < row.time))
          throw std::runtime_error("NED_HV_DEPENDENCY_READY_INVALID");
      }
    }
  }
  go2_velocity_diagnostic_priors_ = measurements;
  resetNedVelocitySourceGeneration("source_vector_replacement");
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
      options_.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_frame == "body_frd" ||
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
  // Suppressing only the scalar heading must not remove the original PVT
  // auxiliary trigger, even for a source row with no P/RV measurements.
  if (options_.heading_source_policy != "configured" &&
      gnssdata_.pvt_heading_source_present && gnssdata_.auxiliary_updates_allowed)
    gnssdata_.isvalid = true;
  if (options_.dual_antenna_measurement_model == "baseline3d" && !gnssdata_.use_scalar_heading) {
    // A valid baseline remains an A1 observation during position/RV outages.
    gnssdata_.isvalid = gnssdata_.isvalid || gnssdata_.baseline3d.valid ||
        (options_.baseline3d_source == "external_carrier" && gnssdata_.baseline3d.present);
  }
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
  if (options_.heading_source_policy != "configured" && !gnss.heading_source_arbitrated)
    throw std::runtime_error("PVT_PRIORITY_REQUIRES_EXACT_EVENT_ARBITRATION");
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
    if (options_.dual_antenna_measurement_model != "baseline3d" && qa_active &&
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
    if (options_.dual_antenna_measurement_model == "baseline3d" && options_.enable_dual_yaw_update) {
      applyBaseline3dUpdate(policy_gnss, true, "INACTIVE", 1.0);
    } else if (policy_gnss.has_yaw && options_.enable_dual_yaw_update) {
      applyBasicDualYawUpdate(policy_gnss);
    }
    gnss.isvalid = false;
    ++update_count_;
    return;
  }
  const bool qa_reject_yaw = qa_active && qa_decision.a1_measurement_action == "REJECT";
  auto apply_yaw = [&]() {
    if (options_.dual_antenna_measurement_model == "baseline3d" && !policy_gnss.use_scalar_heading) {
      if (options_.enable_dual_yaw_update && options_.yaw_scheme_C_enabled) {
        applyBaseline3dUpdate(policy_gnss, false,
                             qa_active ? qa_decision.a1_measurement_action : "INACTIVE",
                             qa_active ? qa_decision.yaw_R_scale : 1.0);
      }
      return;
    }
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
  if (!policy_gnss.auxiliary_updates_allowed) {
    gnss.isvalid = false;
    ++update_count_;
    return;
  }
  // 中文说明：raw Doppler auxiliary velocity factor 与 GNSS epoch 对齐，并在 stateFeedback 前进入 EKF。
  if (!qa_active || qa_decision.raw_doppler_action == "ACCEPT") {
    applyRawDopplerUpdateForTime(policy_gnss.time);
  }
  // 中文说明：N7B3 Go2 velocity diagnostic prior 默认关闭；开启时仍为 diagnostic-only，不构成正式 prior。
  if (!qa_active || qa_decision.go2_aux_action == "ACCEPT") {
    if (options_.go2_velocity_prior_diagnostic_config.go2_horizontal_velocity_frame != "body_frd")
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
  if (attitude_clone_active_) attitude_clone_cross_=multiply(Phi,attitude_clone_cross_);
  if (support_pose_active_) support_pose_cross_=multiply(Phi,support_pose_cross_);
  if (jointCloneEnabled()) requireFrozenCloneBlocks();
}

// 中文说明：EKFUpdate 使用 dx += K(dz-Hdx) 和 Joseph covariance form。
void GIEngine::EKFUpdate(const std::vector<double>& dz, const Matrix& H, const Matrix& R,
                         const std::string& source_tag, const std::string& provider_measurement_identity) {
  if (H.cols != RANK || dz.size() != H.rows || R.rows != H.rows || R.cols != H.rows) {
    throw std::runtime_error("EKFUpdate dimension mismatch");
  }
  if(support_pose_active_) {
    Matrix full_h(H.rows,pose_clone::kJoint,0.0);
    for(std::size_t i=0;i<H.rows;++i) for(std::size_t j=0;j<RANK;++j) full_h(i,j)=H(i,j);
    setSupportPoseJointState(pose_clone::ordinaryUpdate(supportPoseJointState(),dz,full_h,R));
    ++support_pose_counts_.ordinary_joint_updates;return;
  }
  if (attitude_clone_active_) {
    Matrix full_h(H.rows,attitude_clone::kJoint,0.0);
    for(std::size_t i=0;i<H.rows;++i) for(std::size_t j=0;j<RANK;++j) full_h(i,j)=H(i,j);
    setAttitudeJointState(attitude_clone::ordinaryUpdate(attitudeJointState(),dz,full_h,R));
    if(attitude_clone_owner_=="ARC") ++arc_clone_counts_.ordinary_joint_updates;
    else ++attitude_clone_counts_.ordinary_joint_updates;
    if(options_.arc_clone_config.mode!="off") ++arc_clone_counts_.ordinary_updates;
    recordArcConditioning("ORDINARY_UPDATE",source_tag,provider_measurement_identity);
    requireFrozenCloneBlocks();
    return;
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
  if(options_.arc_clone_config.mode!="off") ++arc_clone_counts_.ordinary_updates;
  recordArcConditioning("ORDINARY_UPDATE",source_tag,provider_measurement_identity);
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
  const Vec3 old_blh = pvacur_.pos_blh_rad_m;
  const Vec3 new_blh = subtract(old_blh, multiply(Earth::DRi(old_blh), dx_pos));
  pose_clone::Gaussian support_reset;
  Matrix3 support_reset_rotation=support_pose_cbe_;
  Vec3 support_reset_position=support_pose_position_ecef_;
  if(supportPoseEnabled()) {
    if(yaw_correction_clipped) throw std::runtime_error("SUPPORT_POSE_FULL_FEEDBACK_REQUIRED");
    support_reset=pose_clone::reset(supportPoseJointState(),multiply(Earth::DR(new_blh),Earth::DRi(old_blh)));
    if(support_pose_active_) {
      support_reset_position=subtract(support_pose_position_ecef_,Vec3{support_pose_error_[0],support_pose_error_[1],support_pose_error_[2]});
      support_reset_rotation=multiply(Rotation::quaternion2matrix(Rotation::rotvec2quaternion(
        {support_pose_error_[3],support_pose_error_[4],support_pose_error_[5]})),support_pose_cbe_);
    }
  }
  attitude_clone::Gaussian reset_state;
  Matrix3 reset_clone=attitude_clone_cbe_;
  if(jointCloneEnabled()) {
    if(yaw_correction_clipped) throw std::runtime_error("ATTITUDE_CLONE_PARTIAL_FEEDBACK_FORBIDDEN");
    reset_state=attitude_clone::reset(attitudeJointState(),multiply(Earth::DR(new_blh),Earth::DRi(old_blh)));
    if(attitude_clone_active_) {
      reset_clone=multiply(Rotation::quaternion2matrix(Rotation::rotvec2quaternion(attitude_clone_error_)),
                           attitude_clone_cbe_);
      attitude_clone::requireRotation(reset_clone,"FEEDBACK_CLONE_CBE");
    }
  }
  pvacur_.pos_blh_rad_m = new_blh;
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
  if(supportPoseEnabled()) {
    setSupportPoseJointState(support_reset);
    if(support_pose_active_) {support_pose_position_ecef_=support_reset_position;support_pose_cbe_=support_reset_rotation;}
    ++support_pose_counts_.full_resets;
  }
  if(jointCloneEnabled()) {
    setAttitudeJointState(reset_state);
    if(attitude_clone_active_) attitude_clone_cbe_=reset_clone;
    if(options_.arc_clone_config.mode!="off") ++arc_clone_counts_.full_resets;
    else ++attitude_clone_counts_.full_resets;
    recordArcConditioning("FULL_RESET","FULL_FEEDBACK_JOINT_G_P_Gt");
    requireFrozenCloneBlocks();
  }
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

void GIEngine::processExactJointEvents(const std::vector<JointTimedEvent>& events) {
  if (options_.baseline3d_source != "external_carrier" && options_.runtime_contract != "research_experiment")
    throw std::runtime_error("EXACT_EVENT_LOOP_REQUIRES_OPT_IN");
  if (!initialized_) return;
  const double end = imucur_.time;
  if (!std::isfinite(end) || !(end > imupre_.time) ||
      !std::isfinite(imucur_.dt) || !(imucur_.dt > 0.0))
    throw std::runtime_error("EXACT_EVENT_INVALID_IMU_INTERVAL");
  double previous_time = imupre_.time;
  for (const auto& event : events) {
    if (!std::isfinite(event.time) || event.time < previous_time || event.time > end)
      throw std::runtime_error("EXTERNAL_CARRIER_EVENT_OUTSIDE_IMU_INTERVAL");
    if (event.time == previous_time && &event != &events.front())
      throw std::runtime_error("EXTERNAL_CARRIER_DUPLICATE_EVENT");
    previous_time = event.time;
  }
  ImuData previous = imupre_;
  ImuData remaining = imucur_;
  std::vector<ArcSourceEvent> end_arcs;
  for (const auto& input_event : events) {
    GnssData event = input_event.gnss;
    bool execute_gnss = input_event.has_gnss;
    const bool priority = options_.heading_source_policy != "configured";
    HeadingSourceDecision decision;
    if (priority && execute_gnss) {
      if (event.auxiliary_updates_allowed != event.pvt_heading_source_present || !event.validity_explicit)
        throw std::runtime_error("PVT_PRIORITY_EVENT_SOURCE_IDENTITY_REQUIRED");
      decision = heading_source_policy_.arrive(event.time, event.pvt_heading_source_present,
          event.has_yaw, event.baseline3d.present, event.baseline3d.valid,
          options_.heading_source_policy == "pvt_priority_control");
      event.heading_source_arbitrated = true;
      event.has_yaw = decision.use_pvt;
      event.use_scalar_heading = !decision.use_carrier;
      // A coincident carrier cannot activate aids on an otherwise wholly invalid
      // PVT row. Suppressed *valid* PVT retains its original auxiliary schedule.
      event.auxiliary_updates_allowed = event.auxiliary_updates_allowed &&
          (input_event.gnss.has_position || input_event.gnss.has_velocity || input_event.gnss.has_yaw);
      if (decision.pvt_present && decision.pvt_source_valid && !decision.use_pvt)
        ++heading_source_counts_.pvt_suppressed;
      if (decision.carrier_present && !decision.use_carrier)
        ++heading_source_counts_.carrier_bypassed;
      if (!event.pvt_heading_source_present && !decision.use_carrier) {
        // Even valid but suppressed carrier events are diagnostics only.
        heading_source_events_.push_back(decision);
        execute_gnss=false;
      }
    }
    if (execute_gnss && !priority && !event.auxiliary_updates_allowed && !event.baseline3d.valid) {
      // Invalid carrier availability is a diagnostic, not a propagation boundary.
      // This must be numerically identical to an absent observation.
      applyBaseline3dUpdate(event, options_.enable_basic_dual_yaw_baseline, "INACTIVE", 1.0);
      execute_gnss=false;
    }
    if(!execute_gnss && input_event.feet.empty() && input_event.arcs.empty() && input_event.support.empty()) continue;
    const double event_time=input_event.time;
    if (event_time > previous.time) {
      ImuData segment = remaining;
      if (event_time != end) {
        const double fraction = (event_time - previous.time) / (end - previous.time);
        segment.time = event_time;
        segment.dtheta = scale(remaining.dtheta, fraction);
        segment.dvel = scale(remaining.dvel, fraction);
        // Split measured dt, not rounded timestamp elapsed; conserve all three increments.
        segment.dt = remaining.dt * fraction;
        segment.compensated = false;
        remaining.dtheta = subtract(remaining.dtheta, segment.dtheta);
        remaining.dvel = subtract(remaining.dvel, segment.dvel);
        remaining.dt -= segment.dt;
        remaining.compensated = false;
      }
      recordArcImuSegment(previous,segment);
      insPropagation(previous, segment);
      previous = segment;
      pvapre_ = pvacur_;
    }
    // No TIME_ALIGN_ERR snapping: dispatch at the registered event timestamp.
    // ARC is source-time replay only; actual sensor/model availability remains unknown.
    timestamp_ = event_time;
    if(execute_gnss) {
    addGnssData(event);
    const auto heading_accepted_before = yaw_normal_count_ + yaw_downweight_count_;
    gnssUpdate();
    if (priority) {
      if (decision.use_pvt) ++heading_source_counts_.pvt_attempts;
      if (decision.use_carrier) ++heading_source_counts_.carrier_attempts;
      decision.accepted = yaw_normal_count_ + yaw_downweight_count_ > heading_accepted_before;
      if (decision.accepted) {
        heading_source_policy_.accepted(decision);
        if (decision.use_pvt) ++heading_source_counts_.pvt_accepted;
        if (decision.use_carrier) ++heading_source_counts_.carrier_accepted;
      }
      heading_source_events_.push_back(decision);
    }
    stateFeedback();
    pvapre_ = pvacur_;
    }
    for(const auto& support : input_event.support) processSupportPoseEvent(support);
    for(const auto& foot : input_event.feet) processFootPairEvent(foot);
    for(const auto& arc:input_event.arcs) {
      if(event_time==end) end_arcs.push_back(arc);
      else processArcSourceEvent(arc);
    }
    pvapre_=pvacur_;
  }
  if (previous.time < end) {
    recordArcImuSegment(previous,remaining);
    insPropagation(previous, remaining);
    previous = remaining;
  }
  imucur_ = previous;
  imupre_ = imucur_;
  timestamp_ = end;
  const auto& body_cfg = options_.go2_velocity_prior_diagnostic_config;
  if (body_cfg.enable_go2_horizontal_velocity_prior && body_cfg.go2_horizontal_velocity_frame == "body_frd" &&
      end >= research_next_body_hv_tick_) {
    // At most one fresh update after a gap; never replay missed timer ticks or stale source rows.
    do { research_next_body_hv_tick_ += body_cfg.go2_body_velocity_update_period_s; }
    while (research_next_body_hv_tick_ <= end);
    const auto before = go2_velocity_diagnostic_prior_status_.update_count;
    if(support_pose_active_ && options_.support_pose_config.mode!="SDK_NULL") {
      ++support_pose_counts_.sdk_ticks_suppressed;
      body_velocity_events_.push_back({end,0,false,false,false,"SUPPORT_INTERVAL_SDK_REPLACED"});
    } else applyBodyVelocityPriorForTime(end);
    if (go2_velocity_diagnostic_prior_status_.update_count > before) stateFeedback();
  }
  if(options_.arc_clone_config.mode!="off") ++arc_state_sample_count_;
  for(const auto& arc:end_arcs) processArcSourceEvent(arc);
  pvapre_ = pvacur_;
  if (!checkCov()) {
    ++cov_health_fail_count_;
    if (cov_health_fail_count_ == 1) cov_health_first_failure_time_ = timestamp_;
  }
}

bool GIEngine::checkCov() const {
  if(support_pose_active_) {
    for(double v:support_pose_cross_.data) if(!std::isfinite(v)) return false;
    for(double v:support_pose_cov_.data) if(!std::isfinite(v)) return false;
    for(std::size_t i=0;i<6;++i) if(support_pose_cov_(i,i)<0.0) return false;
  }
  if(attitude_clone_active_) {
    for(double v:attitude_clone_cross_.data) if(!std::isfinite(v)) return false;
    for(double v:attitude_clone_cov_.data) if(!std::isfinite(v)) return false;
    for(std::size_t i=0;i<3;++i) if(attitude_clone_cov_(i,i)<0.0) return false;
  }
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
  auto status = go2_velocity_diagnostic_prior_status_;
  status.ned_time_policy_counts = ned_velocity_source_counts_;
  return status;
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
    EKFUpdate(dz, H, R, "GNSS_POSITION_BASIC",
      options_.arc_clone_config.mode!="off" ? "GNSS_EVENT_TIME_BITS:"+arcSourceTimeBits(gnss.time) + ":RAW_ROW_ID_UNKNOWN" : "UNKNOWN");
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
  EKFUpdate(dz, H, scaled_R, "GNSS_POSITION_SOURCE_AWARE",
      options_.arc_clone_config.mode!="off" ? "GNSS_EVENT_TIME_BITS:"+arcSourceTimeBits(gnss.time) + ":RAW_ROW_ID_UNKNOWN" : "UNKNOWN");
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

Vec3 GIEngine::compensatedAngularRate() const {
  // res=1 and res=3 can update before the current buffer is compensated.
  // A copy keeps propagation's exactly-once compensation flag unchanged.
  const ImuData compensated = imuCompensate(imucur_);
  if (compensated.dt <= 0.0) throw std::runtime_error("VELOCITY_UPDATE_NO_SUPPORTED_IMU_DURATION");
  return scale(compensated.dtheta, 1.0 / compensated.dt);
}

Matrix GIEngine::antennaVelocityJacobian(const Vec3& omega_b) const {
  Matrix H(3, RANK, 0.0);
  setBlockIdentity(H, 0, V_ID);
  const Vec3 lever_velocity = multiply(pvacur_.cbn, cross(omega_b, options_.antlever_m));
  setBlock(H, 0, PHI_ID, Rotation::skewSymmetric(lever_velocity));
  const Matrix3 bias = scale(multiply(pvacur_.cbn, Rotation::skewSymmetric(options_.antlever_m)), -1.0);
  setBlock(H, 0, BG_ID, bias);
  setBlock(H, 0, SG_ID, multiply(bias, diag3(cwiseDivide(omega_b, add(makeVec3(1.,1.,1.), imuerror_.gyrscale)))));
  return H;
}

// Velocity observation is evaluated at the GNSS1 antenna with compensated rate.
void GIEngine::applyVelocityUpdate(GnssData& gnss) {
  const Vec3 omega_b = compensatedAngularRate();
  const Vec3 antenna_vel = add(pvacur_.vel_ned_mps, multiply(pvacur_.cbn, cross(omega_b, options_.antlever_m)));
  const Vec3 dz_vec = subtract(antenna_vel, gnss.vel_ned_mps);
  Matrix H = antennaVelocityJacobian(omega_b);
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
  EKFUpdate(dz, H, scaled_R, "RECEIVER_VELOCITY",
      options_.arc_clone_config.mode!="off" ? "GNSS_EVENT_TIME_BITS:"+arcSourceTimeBits(gnss.time) + ":RAW_ROW_ID_UNKNOWN" : "UNKNOWN");
  ++velocity_update_count_;
}

double GIEngine::dualAntennaYawPrediction() const {
  const bool projected = options_.dual_yaw_prediction_model == "lateral_projection" ||
      (options_.dual_yaw_prediction_model == "legacy" && options_.stage_id == "IMU_V3_TIME_CONTRACT_FIX_20261004");
  if (!projected) return pvacur_.euler_rad[2];
  // The frozen provider's heading is azimuth of body -y plus pi/2.
  // At nonzero roll/pitch this is not the ZYX Euler yaw.
  const Vec3 baseline = multiply(pvacur_.cbn, makeVec3(0., -1., 0.));
  const double horizontal_squared = baseline[0]*baseline[0] + baseline[1]*baseline[1];
  if (!(horizontal_squared > 1.e-12)) throw std::runtime_error("DUAL_YAW_HORIZONTAL_PROJECTION_UNSUPPORTED");
  return wrapYawResidual(std::atan2(baseline[1], baseline[0]) + 0.5 * M_PI);
}

Matrix GIEngine::dualAntennaYawJacobian() const {
  Matrix H(1, RANK, 0.0);
  H(0, PHI_ID + 2) = -1.0;
  if (options_.dual_yaw_prediction_model == "lateral_projection" ||
      (options_.dual_yaw_prediction_model == "legacy" && options_.stage_id == "IMU_V3_TIME_CONTRACT_FIX_20261004")) {
    const Vec3 baseline = multiply(pvacur_.cbn, makeVec3(0., -1., 0.));
    const double horizontal_squared = baseline[0]*baseline[0] + baseline[1]*baseline[1];
    if (!(horizontal_squared > 1.e-12)) throw std::runtime_error("DUAL_YAW_HORIZONTAL_PROJECTION_UNSUPPORTED");
    // Error convention: C_true=Exp(phi) C_nominal; residual=predicted-observed.
    H(0, PHI_ID) = baseline[0]*baseline[2]/horizontal_squared;
    H(0, PHI_ID + 1) = baseline[1]*baseline[2]/horizontal_squared;
  }
  return H;
}

// 中文说明：scheme_C 只对 dual-antenna yaw 观测做鲁棒门控，不放宽 hard=15 deg。
void GIEngine::applyYawUpdate(GnssData& gnss) {
  ++yaw_update_count_;
  const double yaw_obs = gnss.yaw_rad;
  const double yaw_pred = dualAntennaYawPrediction();
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
  Matrix H = dualAntennaYawJacobian();
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
  EKFUpdate(dz, H, scaled_R, "DUAL_YAW_SOURCE_AWARE",
      options_.arc_clone_config.mode!="off" ? "GNSS_EVENT_TIME_BITS:"+arcSourceTimeBits(gnss.time) + ":RAW_ROW_ID_UNKNOWN" : "UNKNOWN");
}

// 中文说明：PAPER10E0 Basic Dual-Yaw EKF 的唯一新增观测。
// 该函数复用 KF-GINS 的 21 维误差状态、EKFUpdate 和 stateFeedback；
// 不改变 INS 机械编排、误差传播或状态反馈机制，也不做 robust gate、downweight、reject、hold 或 fallback。
void GIEngine::applyBasicDualYawUpdate(GnssData& gnss) {
  ++yaw_update_count_;
  const double yaw_obs = gnss.yaw_rad;
  const double yaw_pred = dualAntennaYawPrediction();
  // 中文说明：残差定义为 pred - obs；结合 H_phi_z=-1 后，EKFUpdate 内部的 dz-Hdx 与
  // stateFeedback 的 qpn 左乘反馈符号一致。该符号由 PAPER10E0 数值扰动测试验证。
  const double residual = wrapYawResidual(yaw_pred - yaw_obs);
  const double yaw_std = std::max(options_.basic_dual_yaw_fixed_std_deg * D2R, 1.0e-6);
  // Frozen stages retain their scalar approximation; correction stage uses
  // derivatives of the actual tilted lateral-baseline horizontal projection.
  Matrix H = dualAntennaYawJacobian();
  // 中文说明：R_yaw 使用固定角度标准差，内部单位为 rad^2；不使用 dynamic yaw_std 或 source-aware 放大。
  Matrix R(1, 1, yaw_std * yaw_std);
  const std::vector<double> dz{residual};
  EKFUpdate(dz, H, R, "DUAL_YAW_BASIC",
      options_.arc_clone_config.mode!="off" ? "GNSS_EVENT_TIME_BITS:"+arcSourceTimeBits(gnss.time) + ":RAW_ROW_ID_UNKNOWN" : "UNKNOWN");
  ++yaw_normal_count_;
}

void GIEngine::applyBaseline3dUpdate(const GnssData& gnss, bool basic,
                                    const std::string& qa_action, double qa_R_scale) {
  Baseline3dDiagnostics row;
  row.time = gnss.time;
  row.source = options_.baseline3d_source;
  row.measurement_time = gnss.baseline3d.measurement_time;
  row.decision_available_time = gnss.baseline3d.decision_available_time;
  row.present = gnss.baseline3d.present;
  row.valid = gnss.baseline3d.valid;
  row.qa_action = qa_action;
  if (!gnss.baseline3d.valid) {
    ++baseline3d_counts_.invalid;
    if (!gnss.baseline3d.present) ++baseline3d_counts_.missing;
    row.reason = gnss.baseline3d.reason;
    baseline3d_diagnostics_.push_back(row);
    return;
  }
  ++baseline3d_counts_.attempts;
  ++yaw_update_count_;  // Existing formal A1 slot; separate B3 counters identify its model.
  row.attempted = true;
  row.observed_m = gnss.baseline3d.ned_m;
  row.pacc1_m = gnss.baseline3d.pacc1_m;
  row.pacc2_m = gnss.baseline3d.pacc2_m;
  const double variance = options_.baseline3d_k_b * options_.baseline3d_k_b *
      (row.pacc1_m * row.pacc1_m + row.pacc2_m * row.pacc2_m);
  const bool external = options_.baseline3d_source == "external_carrier";
  if (!external && (!std::isfinite(variance) || variance <= 0.0)) {
    ++baseline3d_counts_.rejected;
    ++yaw_reject_count_;
    row.reason = "REJECT_INVALID_COVARIANCE";
    baseline3d_diagnostics_.push_back(row);
    return;
  }
  if (external && (gnss.baseline3d.measurement_time != gnss.time ||
                   gnss.baseline3d.decision_available_time != gnss.time))
    throw std::runtime_error("EXTERNAL_CARRIER_EVENT_TIME_MISMATCH");
  const auto model = external
      ? buildExternalCarrierBaseline3dModel(pvacur_.cbn, pvacur_.pos_blh_rad_m,
                                            gnss.baseline3d, options_.baseline3d_body_vector_m)
      : buildBaseline3dModel(pvacur_.cbn, gnss.baseline3d,
                            options_.baseline3d_length_m, options_.baseline3d_k_b);
  row.model_available = true;
  row.observed_m = external ? subtract(model.predicted_m, model.residual_m) : gnss.baseline3d.ned_m;
  for (std::size_t i = 0; i < 3; ++i) for (std::size_t j = 0; j < 3; ++j)
    row.covariance_ned_m2[i][j] = model.R(i, j);
  row.predicted_m = model.predicted_m;
  row.residual_m = model.residual_m;
  row.pacc1_m = gnss.baseline3d.pacc1_m;
  row.pacc2_m = gnss.baseline3d.pacc2_m;
  row.base_variance_m2 = model.R(0, 0);
  row.along_axis_residual_m = model.along_axis_residual_m;
  row.length_mismatch_m = model.length_mismatch_m;
  const std::vector<double> dz(model.residual_m.begin(), model.residual_m.end());
  const auto hdx = multiply(model.H, dx_);
  std::vector<double> innovation = dz;
  for (std::size_t i = 0; i < 3; ++i) {
    innovation[i] -= hdx[i];
    row.innovation_m[i] = innovation[i];
  }
  // Retain the A1 action contract even though T5bc permits only QA/QM off.
  if (!basic && (qa_action == "DOWNWEIGHT" || qa_action == "RECOVERY_RAMP")) {
    row.qa_R_scale = std::max(1.0, qa_R_scale);
  }
  Matrix R = scale(model.R, row.qa_R_scale);
  const Matrix S = add(multiply(multiply(model.H, Cov_), transpose(model.H)), R);
  row.nis = dotVector(innovation, multiply(inverse(S), innovation));
  row.nis_available = std::isfinite(row.nis);
  auto reject = [&](const std::string& reason) {
    ++baseline3d_counts_.rejected;
    ++yaw_reject_count_;
    row.reason = reason;
    baseline3d_diagnostics_.push_back(row);
  };
  if (!row.nis_available) throw std::runtime_error("BASELINE3D_NONFINITE_NIS");
  if (!basic && qa_action == "REJECT") { reject("QA_REJECT"); return; }
  // Only the opt-in 3D nonbasic scheme-C slot uses this 3-DOF threshold.
  if (!basic && row.nis > 11.34) { reject("NIS_3DOF_REJECT"); return; }
  Matrix scaled_R = R;
  if (!basic) {
    source_aware::SourceMetadata metadata;
    metadata.source = source_aware::MeasurementSource::kDualAntennaYaw;
    metadata.time = gnss.time;
    metadata.valid = true;
    metadata.baseline_length_m = norm(row.observed_m);
    metadata.rel_acc_m = std::sqrt(model.R(0, 0));
    metadata.yaw_std_rad = metadata.rel_acc_m / options_.baseline3d_length_m;
    metadata.std_xyz = external ? makeVec3(std::sqrt(model.R(0, 0)), std::sqrt(model.R(1, 1)), std::sqrt(model.R(2, 2)))
                                : makeVec3(metadata.rel_acc_m, metadata.rel_acc_m, metadata.rel_acc_m);
    metadata.provider_status = external ? "external_carrier_experimental" : "baseline3d";
    metadata.quality_flag = "nominal";
    // Preserve existing SA semantics: its helper uses dz, while the B3 hard NIS
    // above uses dz-Hdx at this sequential update slot. Neither changes scalar SA.
    const auto weight = applySourceAwareWeighting(metadata.source, metadata, dz,
                                                  model.H, R, scaled_R);
    row.sa_R_scale = weight.combined_R_scale;
    if (weight.rejected) { reject("SOURCE_AWARE_REJECT"); return; }
  }
  EKFUpdate(dz, model.H, scaled_R, "BASELINE3D",
      options_.arc_clone_config.mode!="off" ? "GNSS_EVENT_TIME_BITS:"+arcSourceTimeBits(gnss.time) + ":RAW_ROW_ID_UNKNOWN" : "UNKNOWN");
  row.accepted = true;
  row.reason = basic ? "BASIC_ACCEPT" : "ACCEPT";
  ++baseline3d_counts_.accepted;
  if (row.qa_R_scale > 1.0 || (!basic &&
      options_.source_aware_policy_config.enable_source_aware_weighting && row.sa_R_scale > 1.0)) {
    ++yaw_downweight_count_;
  } else {
    ++yaw_normal_count_;
  }
  baseline3d_diagnostics_.push_back(row);
}

void GIEngine::writeHeadingSourceDiagnostics(const std::string& output_dir) const {
  if (options_.heading_source_policy == "configured") return;
  std::filesystem::create_directories(output_dir);
  std::ofstream out(std::filesystem::path(output_dir) / "HEADING_SOURCE_EVENTS.csv");
  if (!out) throw std::runtime_error("HEADING_SOURCE_DIAGNOSTIC_WRITE_FAILED");
  out << "time,pvt_present,pvt_known,pvt_source_time,pvt_age_s,pvt_source_valid,carrier_present,carrier_valid,pvt_attempted,carrier_attempted,accepted,pvt_reason,carrier_reason\n";
  out << std::setprecision(17);
  for (const auto& d : heading_source_events_) {
    out << d.time << ',' << d.pvt_present << ',' << d.pvt_known << ',';
    if (d.pvt_known) out << d.pvt_time;
    out << ',';
    if (d.pvt_known) out << d.pvt_age_s;
    out << ',' << d.pvt_source_valid << ',' << d.carrier_present << ',' << d.carrier_valid
        << ',' << d.use_pvt << ',' << d.use_carrier << ',' << d.accepted << ','
        << d.pvt_reason << ',' << d.carrier_reason << '\n';
  }
}

void GIEngine::writeBaseline3dDiagnostics(const std::string& output_dir) const {
  if (options_.dual_antenna_measurement_model != "baseline3d") return;
  std::filesystem::create_directories(output_dir);
  std::ofstream out(std::filesystem::path(output_dir) / "BASELINE3D_DIAGNOSTICS.csv");
  if (!out) throw std::runtime_error("BASELINE3D_DIAGNOSTICS_OPEN_FAILED");
  out << std::setprecision(17);
  out << "time,model,present,valid,attempt,accepted,rejected,reason,"
         "z_n_m,z_e_m,z_d_m,h_n_m,h_e_m,h_d_m,dz_n_m,dz_e_m,dz_d_m,"
         "innovation_n_m,innovation_e_m,innovation_d_m,pAcc1_m,pAcc2_m,base_variance_m2,"
         "along_axis_residual_m,length_mismatch_m,nis_actual_innovation,dof,qa_action,qa_R_scale,sa_R_scale";
  const bool external = options_.baseline3d_source == "external_carrier";
  if (external) out << ",source,measurement_time,decision_available_time,R_nn,R_ne,R_nd,R_en,R_ee,R_ed,R_dn,R_de,R_dd";
  out << '\n';
  for (const auto& row : baseline3d_diagnostics_) {
    out << row.time << ",baseline3d," << row.present << ',' << row.valid << ','
        << row.attempted << ',' << row.accepted << ','
        << (row.attempted && !row.accepted) << ',' << row.reason;
    auto cell = [&](double value, bool available) {
      out << ',';
      if (available) out << value;
    };
    for (double value : row.observed_m) cell(value, row.valid);
    for (const auto& vector : {row.predicted_m, row.residual_m, row.innovation_m}) {
      for (double value : vector) cell(value, row.model_available);
    }
    cell(row.pacc1_m, row.valid && !external);
    cell(row.pacc2_m, row.valid && !external);
    cell(row.base_variance_m2, row.model_available);
    cell(row.along_axis_residual_m, row.model_available);
    cell(row.length_mismatch_m, row.model_available);
    cell(row.nis, row.nis_available);
    out << ",3," << row.qa_action << ',' << row.qa_R_scale << ',' << row.sa_R_scale;
    if (external) {
      out << ',' << row.source;
      cell(row.measurement_time, row.present);
      cell(row.decision_available_time, row.present);
      for (const auto& values : row.covariance_ned_m2)
        for (double value : values) cell(value, row.model_available);
    }
    out << '\n';
  }
  if (!out) throw std::runtime_error("BASELINE3D_DIAGNOSTICS_WRITE_FAILED");
}

void GIEngine::applyRawDopplerUpdateForTime(double update_time) {
  if (!options_.raw_doppler_config.enable_raw_doppler || !raw_doppler_status_.solver_enabled) {
    return;
  }
  const RawDopplerVelocityMeasurement* best = nullptr;
  double best_dt = options_.raw_doppler_config.raw_doppler_time_tolerance_sec;
  for (const auto& measurement : raw_doppler_measurements_) {
    if (options_.runtime_contract == "research_experiment" &&
        (measurement.time > update_time || measurement.time <= research_last_rd_attempt_time_)) continue;
    const double dt = std::fabs(measurement.time - update_time);
    if (dt <= best_dt) {
      best = &measurement;
      best_dt = dt;
    }
  }
  if (!best) {
    return;
  }
  if (options_.runtime_contract == "research_experiment") research_last_rd_attempt_time_ = best->time;
  if (!RawDopplerFactor::isProviderBacked(*best) || best->sat_count < options_.raw_doppler_config.raw_doppler_min_sat) {
    ++raw_doppler_status_.reject_count;
    return;
  }
  const Vec3 omega_b = compensatedAngularRate();
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
  Matrix H = antennaVelocityJacobian(omega_b);
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
  EKFUpdate(dz, H, scaled_R, "RAW_DOPPLER",
      options_.arc_clone_config.mode!="off" ? "SOURCE_TIME_BITS:"+arcSourceTimeBits(best->time) + ":VECTOR_INDEX:" + std::to_string(static_cast<std::size_t>(best-raw_doppler_measurements_.data())) : "UNKNOWN");
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
    if (options_.runtime_contract == "research_experiment" &&
        (measurement.time > update_time || measurement.time <= research_last_rp_attempt_time_)) continue;
    const double dt = std::fabs(measurement.time - update_time);
    if (dt <= best_dt) {
      best = &measurement;
      best_dt = dt;
    }
  }
  if (!best) {
    return;
  }
  if (options_.runtime_contract == "research_experiment") research_last_rp_attempt_time_ = best->time;
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
  EKFUpdate(dz, H, scaled_R, "GO2_ATTITUDE_RP",
      options_.arc_clone_config.mode!="off" ? "SOURCE_TIME_BITS:"+arcSourceTimeBits(best->time) + ":VECTOR_INDEX:" + std::to_string(static_cast<std::size_t>(best-go2_attitude_priors_.data())) : "UNKNOWN");
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

void GIEngine::applyBodyVelocityPriorForTime(double update_time) {
  const auto& config = options_.go2_velocity_prior_diagnostic_config;
  if (!config.enable_go2_horizontal_velocity_prior || config.go2_horizontal_velocity_frame != "body_frd") return;
  BodyVelocityEvent event;
  event.time=update_time;
  auto finish = [&](const std::string& reason) { event.reason=reason; body_velocity_events_.push_back(event); };
  if (!go2_velocity_diagnostic_prior_status_.solver_enabled) { finish("provider_unavailable"); return; }
  const Go2VelocityDiagnosticPriorMeasurement* best=nullptr;
  for (const auto& row : go2_velocity_diagnostic_priors_) {
    if (row.time<=update_time && row.time>research_last_body_hv_attempt_time_ &&
        update_time-row.time<=config.go2_velocity_prior_time_tolerance_sec &&
        (!best || row.time>best->time)) best=&row;
  }
  if (!best) { finish("no_new_past_sample_within_age"); return; }
  event.source_present=true;event.source_time=best->time;
  research_last_body_hv_attempt_time_=best->time; // Invalid/rejected samples also consumed once.
  event.valid=best->update_flag && best->source_status=="active" && !best->go2_velocity_truth_claim;
  if (best->observation_frame!="body_frd") throw std::runtime_error("BODY_HV_MEASUREMENT_FRAME_MISMATCH");
  if (!event.valid) { ++go2_velocity_diagnostic_prior_status_.reject_count; finish("provider_invalid"); return; }
  const Vec3 stddev=scale(best->std_body_frd_mps,config.go2_velocity_prior_std_scale);
  const auto model=buildBodyVelocity2dModel(pvacur_,best->velocity_body_frd_mps,stddev);
  Matrix scaled_R=model.R;
  if (config.go2_horizontal_velocity_prior_source_aware_enabled) {
    source_aware::SourceMetadata metadata;
    metadata.source=source_aware::MeasurementSource::kGo2HorizontalVelocity;
    metadata.time=best->time;metadata.valid=true;
    metadata.std_xyz=makeVec3(stddev[0],stddev[1],999.0);
    metadata.active_dimensions=2;
    metadata.residual_norm=std::sqrt(model.residual[0]*model.residual[0]+model.residual[1]*model.residual[1]);
    metadata.time_diff_sec=best->time-update_time;
    metadata.provider_status="available";
    metadata.quality_flag=best->quality_flag;
    metadata.covariance_available=true;
    const auto weight=applySourceAwareWeighting(metadata.source,metadata,model.residual,model.H,model.R,scaled_R);
    if(weight.rejected) { ++go2_velocity_diagnostic_prior_status_.reject_count; finish("source_aware_reject"); return; }
  }
  EKFUpdate(model.residual,model.H,scaled_R, "BODY_HORIZONTAL_VELOCITY",
      options_.arc_clone_config.mode!="off" ? "SOURCE_TIME_BITS:"+arcSourceTimeBits(best->time) + ":VECTOR_INDEX:" + std::to_string(static_cast<std::size_t>(best-go2_velocity_diagnostic_priors_.data())) : "UNKNOWN");
  ++go2_velocity_diagnostic_prior_status_.update_count;
  ++go2_velocity_diagnostic_prior_status_.horizontal_update_count;
  go2_velocity_diagnostic_prior_status_.horizontal_only=true;
  go2_velocity_diagnostic_prior_status_.vertical_disabled=true;
  event.accepted=true;finish("accept_body_forward_right_2d");
}

void GIEngine::writeBodyVelocityDiagnostics(const std::string& output_dir) const {
  const auto& config=options_.go2_velocity_prior_diagnostic_config;
  if(!config.enable_go2_horizontal_velocity_prior || config.go2_horizontal_velocity_frame!="body_frd") return;
  std::filesystem::create_directories(output_dir);
  std::ofstream out(std::filesystem::path(output_dir)/"BODY_VELOCITY_EVENTS.csv");
  if(!out)throw std::runtime_error("BODY_HV_DIAGNOSTICS_OPEN_FAILED");
  out<<std::setprecision(17)<<"state_time,source_time,age_s,source_present,valid,accepted,reason,frame,observed_axes\n";
  for(const auto& row:body_velocity_events_) {
    out<<row.time<<',';if(row.source_present)out<<row.source_time;
    out<<',';if(row.source_present)out<<row.time-row.source_time;
    out<<','<<row.source_present<<','<<row.valid<<','<<row.accepted<<','<<row.reason<<",body_frd,forward_right\n";
  }
  if(!out)throw std::runtime_error("BODY_HV_DIAGNOSTICS_WRITE_FAILED");
}

void GIEngine::resetNedVelocitySourceGeneration(const std::string& reason) {
  const auto& policy = options_.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_policy;
  if (policy != "causal_unique_latest" && policy != "causal_recorded_dependencies_unique_latest") return;
  ned_velocity_source_has_attempt_=false;
  ned_velocity_source_last_attempt_time_=0.0;
  ned_velocity_generation_reset_reason_=reason;
  ++ned_velocity_source_counts_.generations;
}

void GIEngine::writeNedVelocitySourceDiagnostics(const std::string& output_dir) const {
  const auto& policy = options_.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_policy;
  const bool dependencies = policy == "causal_recorded_dependencies_unique_latest";
  if (policy != "causal_unique_latest" && !dependencies) return;
  std::filesystem::create_directories(output_dir);
  std::ofstream out(std::filesystem::path(output_dir)/"NED_VELOCITY_SOURCE_EVENTS.csv");
  if(!out) throw std::runtime_error("NED_HV_SOURCE_DIAGNOSTICS_OPEN_FAILED");
  out<<std::setprecision(17)
     <<"trigger_time,state_time,source_time,trigger_age_s,state_age_s,source_time_bits_hex,vector_index,generation,generation_reset_reason,source_present,consumed,accepted,reason,future_candidate_skips,future_trigger_candidate_skips,future_state_candidate_skips,used_or_older_candidate_skips,nonfinite_time_skips,actual_available_time_s,frame";
  if (dependencies)
    out<<",selected_dependency_schema,selected_dependency_ready_source_time_s,dependency_missing_candidate_skips,dependency_unsupported_candidate_skips,dependency_future_candidate_skips,dependency_future_trigger_candidate_skips,dependency_future_state_candidate_skips";
  out<<'\n';
  for(const auto& e:ned_velocity_source_events_) {
    out<<e.trigger_time<<','<<e.state_time<<',';if(e.source_present)out<<e.source_time;
    out<<',';if(e.source_present)out<<e.trigger_time-e.source_time;
    out<<',';if(e.source_present)out<<e.state_time-e.source_time;
    out<<',';if(e.source_present)out<<arcSourceTimeBits(e.source_time);
    out<<',';if(e.source_present)out<<e.vector_index;
    out<<','<<e.generation<<','<<e.generation_reset_reason<<','<<e.source_present<<','<<e.consumed
       <<','<<e.accepted<<','<<e.reason<<','<<e.future_candidate_skips
       <<','<<e.future_trigger_candidate_skips<<','<<e.future_state_candidate_skips<<','<<e.used_or_older_candidate_skips
       <<','<<e.nonfinite_time_skips<<",,ned";
    if (dependencies) {
      out<<',';if(e.source_present)out<<e.selected_dependency_schema;
      out<<',';if(e.source_present)out<<e.selected_dependency_ready_source_time_s;
      out<<','<<e.dependency_missing_candidate_skips<<','<<e.dependency_unsupported_candidate_skips
         <<','<<e.dependency_future_candidate_skips<<','<<e.dependency_future_trigger_candidate_skips
         <<','<<e.dependency_future_state_candidate_skips;
    }
    out<<'\n';
  }
  if(!out) throw std::runtime_error("NED_HV_SOURCE_DIAGNOSTICS_WRITE_FAILED");
}

void GIEngine::applyGo2VelocityDiagnosticPriorForTime(double update_time) {
  const bool controlled_horizontal =
      options_.go2_velocity_prior_diagnostic_config.enable_go2_horizontal_velocity_prior;
  const auto& policy = options_.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_policy;
  const bool dependencies = policy == "causal_recorded_dependencies_unique_latest";
  const bool causal = policy == "causal_unique_latest" || dependencies;
  NedVelocitySourceEvent event;
  if (causal) {
    if(!std::isfinite(update_time) || !std::isfinite(pvacur_.time)) throw std::runtime_error("NED_HV_NONFINITE_UPDATE_TIME");
    event.trigger_time=update_time;event.state_time=pvacur_.time;
    event.generation=ned_velocity_source_counts_.generations;
    event.generation_reset_reason=ned_velocity_generation_reset_reason_;
  }
  auto finish=[&](const std::string& reason) {
    if(causal) {event.reason=reason;ned_velocity_source_events_.push_back(event);}
  };
  if (!options_.go2_velocity_prior_diagnostic_config.enable_go2_velocity_prior_diagnostic ||
      !go2_velocity_diagnostic_prior_status_.solver_enabled ||
      (!options_.go2_velocity_prior_diagnostic_config.go2_diagnostic_prior_only && !controlled_horizontal)) {
    finish("provider_unavailable");
    return;
  }
  const Go2VelocityDiagnosticPriorMeasurement* best = nullptr;
  if (causal) {
    const double tolerance=options_.go2_velocity_prior_diagnostic_config.go2_velocity_prior_time_tolerance_sec;
    for (const auto& measurement : go2_velocity_diagnostic_priors_) {
      if(!measurement.update_flag) continue;
      if(!std::isfinite(measurement.time)) {++event.nonfinite_time_skips;continue;}
      // Count competing rows only inside the unchanged absolute tolerance.
      if(std::fabs(measurement.time-update_time)>tolerance) continue;
      const bool future_trigger=measurement.time>update_time;
      const bool future_state=measurement.time>pvacur_.time;
      if(future_trigger || future_state) {
        ++event.future_candidate_skips;
        event.future_trigger_candidate_skips+=static_cast<std::size_t>(future_trigger);
        event.future_state_candidate_skips+=static_cast<std::size_t>(future_state);
        continue;
      }
      if (dependencies) {
        if (!measurement.dependency_metadata_available ||
            measurement.dependency_schema != "HV_CALIBRATED_GNSS18_TIME_V1") {
          ++event.dependency_missing_candidate_skips;continue;
        }
        if (!measurement.dependency_supported) {
          ++event.dependency_unsupported_candidate_skips;continue;
        }
        const bool future_dependency_trigger = measurement.dependency_ready_source_time_s > update_time;
        const bool future_dependency_state = measurement.dependency_ready_source_time_s > pvacur_.time;
        if (future_dependency_trigger || future_dependency_state) {
          ++event.dependency_future_candidate_skips;
          event.dependency_future_trigger_candidate_skips += static_cast<std::size_t>(future_dependency_trigger);
          event.dependency_future_state_candidate_skips += static_cast<std::size_t>(future_dependency_state);
          continue;
        }
      }
      if(ned_velocity_source_has_attempt_ && measurement.time<=ned_velocity_source_last_attempt_time_) {
        ++event.used_or_older_candidate_skips;continue;
      }
      // Iteration order makes an exact-time tie choose the last vector index.
      if(!best || measurement.time>=best->time) best=&measurement;
    }
    ned_velocity_source_counts_.future_candidate_skips+=event.future_candidate_skips;
    ned_velocity_source_counts_.used_or_older_candidate_skips+=event.used_or_older_candidate_skips;
    if (dependencies) {
      ned_velocity_source_counts_.dependency_missing_candidate_skips += event.dependency_missing_candidate_skips;
      ned_velocity_source_counts_.dependency_unsupported_candidate_skips += event.dependency_unsupported_candidate_skips;
      ned_velocity_source_counts_.dependency_future_candidate_skips += event.dependency_future_candidate_skips;
      ned_velocity_source_counts_.dependency_future_trigger_candidate_skips += event.dependency_future_trigger_candidate_skips;
      ned_velocity_source_counts_.dependency_future_state_candidate_skips += event.dependency_future_state_candidate_skips;
    }
    if(!best) {++ned_velocity_source_counts_.no_eligible_calls;finish("no_eligible_source");return;}
    event.source_present=true;event.source_time=best->time;
    event.vector_index=static_cast<std::size_t>(best-go2_velocity_diagnostic_priors_.data());
    if (dependencies) {
      event.selected_dependency_schema = best->dependency_schema;
      event.selected_dependency_ready_source_time_s = best->dependency_ready_source_time_s;
    }
    // Dependency-ineligible rows were not attempted; selection may use an older
    // ready row above the watermark. After selection there is no fallback.
    // Consume the entire source timestamp BEFORE provider/weight gates. No refund,
    // retry of duplicates, or older backfill; guarantee is per explicit generation.
    ned_velocity_source_last_attempt_time_=best->time;ned_velocity_source_has_attempt_=true;
    ++ned_velocity_source_counts_.selected_attempts;event.consumed=true;
  } else {
    // Legacy branch retains its exact selection loop and floating-point order.
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
  }
  if (best->source_status != "active" ||
      (!best->diagnostic_only && !controlled_horizontal) ||
      best->go2_velocity_truth_claim) {
    ++go2_velocity_diagnostic_prior_status_.reject_count;
    finish("provider_invalid");
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
    metadata.active_dimensions = horizontal_2d ? 2 : 3;
    metadata.residual_norm = horizontal_2d ? std::sqrt(residual_vec[0] * residual_vec[0] + residual_vec[1] * residual_vec[1])
                                           : norm(residual_vec);
    metadata.time_diff_sec = best->time - update_time;
    metadata.provider_status = best->source_status == "active" ? "available" : best->source_status;
    metadata.quality_flag = best->quality_flag.empty() ? "nominal" : best->quality_flag;
    metadata.covariance_available = true;
    const auto weight = applySourceAwareWeighting(metadata.source, metadata, dz, H, R, scaled_R);
    if (weight.rejected) {
      ++go2_velocity_diagnostic_prior_status_.reject_count;
      finish("source_aware_reject");
      return;
    }
  }
  EKFUpdate(dz, H, scaled_R, "GO2_VELOCITY_DIAGNOSTIC",
      options_.arc_clone_config.mode!="off" ? "SOURCE_TIME_BITS:"+arcSourceTimeBits(best->time) + ":VECTOR_INDEX:" + std::to_string(static_cast<std::size_t>(best-go2_velocity_diagnostic_priors_.data())) : "UNKNOWN");
  ++go2_velocity_diagnostic_prior_status_.update_count;
  if (horizontal_2d || best->std_ned_mps[2] >= 999.0 ||
      best->prior_policy.find("horizontal") != std::string::npos) {
    go2_velocity_diagnostic_prior_status_.horizontal_only = true;
    go2_velocity_diagnostic_prior_status_.vertical_disabled = true;
    ++go2_velocity_diagnostic_prior_status_.horizontal_update_count;
  }
  if(causal) event.accepted=true;
  finish("accept_ned_horizontal_2d");
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
  EKFUpdate(dz, H, R, "FGO_FEEDBACK",
      options_.arc_clone_config.mode!="off" ? "SOURCE_TIME_BITS:"+arcSourceTimeBits(best->time) + ":VECTOR_INDEX:" + std::to_string(static_cast<std::size_t>(best-fgo_feedback_observations_.data())) : "UNKNOWN");
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
  const bool baseline3d = options_.dual_antenna_measurement_model == "baseline3d" && !gnss.use_scalar_heading;
  observation.a1_available = baseline3d ? gnss.baseline3d.valid :
      gnss.has_yaw && std::isfinite(gnss.yaw_rad) && std::isfinite(gnss.yaw_std_rad);
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
  if (baseline3d) {
    observation.a1_baseline_m = gnss.baseline3d.valid ? norm(gnss.baseline3d.ned_m) : 0.0;
    observation.a1_baseline_available = gnss.baseline3d.valid;
    observation.a1_baseline_expected_m = options_.baseline3d_length_m;
    // Passive QA explicitly marks scalar-yaw diagnostics unavailable.
    observation.a1_yaw_std_available = false;
    observation.a1_yaw_residual_available = false;
  } else {
    observation.a1_yaw_std_deg = std::fabs(gnss.yaw_std_rad) * R2D;
    observation.a1_yaw_std_available = observation.a1_available;
    observation.a1_yaw_residual_deg = wrapYawResidual(dualAntennaYawPrediction() - gnss.yaw_rad) * R2D;
    observation.a1_yaw_residual_available = observation.a1_available;
  }
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
    if (options_.runtime_contract == "research_experiment" && measurement.time > update_time) continue;
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
  // Sequential updates retain a nonzero dx until stateFeedback. Use the same
  // conditional innovation as EKFUpdate, with the current conditional covariance.
  const std::vector<double> hdx = multiply(H, dx_);
  std::vector<double> conditional_residual = dz;
  for (std::size_t i = 0; i < dz.size(); ++i) conditional_residual[i] -= hdx[i];
  innovation.residual = conditional_residual;
  innovation.residual_norm = vectorNorm(conditional_residual);
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
      const std::vector<double> weighted_residual = multiply(s_inv, conditional_residual);
      innovation.nis = std::max(0.0, dotVector(conditional_residual, weighted_residual));
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
  if(jointCloneEnabled())
    throw std::runtime_error("ATTITUDE_CLONE_CURRENT_ONLY_COV_REPLACEMENT_FORBIDDEN");
  Cov_ = matrix;
}

}  // namespace legsa_v23_port_core
