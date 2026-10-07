// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/gnss.hpp"
#include "legsa_v23_port_core/imu.hpp"
#include "legsa_v23_port_core/nav_state.hpp"
#include "legsa_v23_port_core/options.hpp"
#include "legsa_v23_port_core/factors/go2_weak_prior_types.hpp"
#include "legsa_v23_port_core/factors/raw_doppler_types.hpp"
#include "legsa_v23_port_core/fgo_feedback/fgo_feedback.hpp"
#include "legsa_v23_port_core/source_aware/source_aware_policy.hpp"
#include "legsa_v23_port_core/source_aware/quality_state_manager.hpp"
#include "legsa_v23_port_core/source_aware/quality_state_trace.hpp"
#include "legsa_v23_port_core/source_aware/source_aware_trace.hpp"

#include "legsa_v23_port_core/factors/attitude_clone.hpp"
#include "legsa_v23_port_core/factors/pose_clone.hpp"
#include <set>
#include <cstddef>
#include <string>
#include <vector>

namespace legsa_v23_port_core {

// 中文说明：GIEngine 是 source-backed loose-coupled GNSS/INS EKF backbone，不包含九类创新因子。
class GIEngine {
 public:
  explicit GIEngine(PortOptions options);

  void initialize(const NavState& initial_state);
  void setRawDopplerVelocityMeasurements(const std::vector<RawDopplerVelocityMeasurement>& measurements,
                                         const RawDopplerFactorStatus& status);
  void setGo2AttitudeWeakPriors(const std::vector<Go2AttitudeWeakPriorMeasurement>& measurements,
                                const Go2AttitudeWeakPriorStatus& status);
  void setGo2VelocityDiagnosticPriors(const std::vector<Go2VelocityDiagnosticPriorMeasurement>& measurements,
                                      const Go2VelocityDiagnosticPriorStatus& status);
  void setGo2ReadinessLsimMetadata(const std::vector<Go2ReadinessLsimMetadataMeasurement>& measurements,
                                   const Go2ReadinessLsimMetadataStatus& status);
  void setFgoFeedbackObservations(const std::vector<fgo_feedback::FgoFeedbackObservation>& observations,
                                  const fgo_feedback::FgoFeedbackStatus& status);
  void addImuData(const ImuData& imu, bool compensate = false);
  void addGnssData(const GnssData& gnss);
  int isToUpdate() const;
  int isToUpdate(double imutime1, double imutime2, double updatetime) const;
  ImuData imuInterpolate(const ImuData& previous, ImuData& current, double time) const;
  ImuData imuCompensate(const ImuData& imu) const;
  void imuCompensateInPlace(ImuData& imu) const;
  void insPropagation();
  void insPropagation(ImuData& imupre, ImuData& imucur);
  void gnssUpdate();
  void gnssUpdate(GnssData& gnss);
  void EKFPredict();
  void EKFPredict(const Matrix& Phi, const Matrix& Qd);
  void EKFUpdate(const std::vector<double>& dz, const Matrix& H, const Matrix& R,
                 const std::string& source_tag="UNSPECIFIED_INTERNAL_SOURCE",
                 const std::string& provider_measurement_identity="UNKNOWN");
  void stateFeedback();
  void newImuProcess();
  // Exact-time event queue for the opt-in carrier source; consumes every event once.
  void newImuProcessWithEvents(const std::vector<GnssData>& events);
  bool checkCov() const;

  const NavState& navState() const;
  NavState getNavState() const;
  const std::vector<double>& getCovariance() const;
  double timestamp() const;
  std::size_t propagationCount() const;
  std::size_t covHealthFailCount() const;
  double covHealthFirstFailureTime() const;
  std::size_t updateCount() const;
  std::size_t positionUpdateCount() const;
  std::size_t velocityUpdateCount() const;
  std::size_t yawUpdateCount() const;
  std::size_t yawNormalCount() const;
  std::size_t yawDownweightCount() const;
  std::size_t yawRejectCount() const;
  std::size_t sourceAwareEvaluationCount() const;
  std::size_t sourceAwareWeightChangedCount() const;
  std::size_t rawDopplerUpdateCount() const;
  std::size_t rawDopplerRejectCount() const;
  std::size_t rawDopplerEpochCount() const;
  std::size_t rawDopplerSatCountMin() const;
  std::size_t rawDopplerSatCountMedian() const;
  std::size_t rawDopplerSatCountMax() const;
  double rawDopplerResidualP95() const;
  RawDopplerFactorStatus rawDopplerStatus() const;
  std::size_t go2AttitudeWeakPriorUpdateCount() const;
  std::size_t go2AttitudeWeakPriorRejectCount() const;
  Go2AttitudeWeakPriorStatus go2AttitudeWeakPriorStatus() const;
  std::size_t go2VelocityDiagnosticPriorUpdateCount() const;
  std::size_t go2VelocityDiagnosticPriorRejectCount() const;
  Go2VelocityDiagnosticPriorStatus go2VelocityDiagnosticPriorStatus() const;
  Go2ReadinessLsimMetadataStatus go2ReadinessLsimMetadataStatus() const;
  fgo_feedback::FgoFeedbackStatus fgoFeedbackStatus() const;
  std::size_t qaFallbackTraceRowCount() const;
  void writeFgoFeedbackTrace(const std::string& output_dir) const;
  void writeQAFallbackTrace(const std::string& output_dir) const;
  source_aware::SourceAwareRuntimeStats sourceAwareStats() const;
  source_aware::QualityStateRuntimeStats qualityStateStats() const;
  void writeSourceAwareTrace(const std::string& output_dir) const;
  const Baseline3dCounts& baseline3dCounts() const { return baseline3d_counts_; }
  const std::vector<Baseline3dDiagnostics>& baseline3dDiagnostics() const { return baseline3d_diagnostics_; }
  void writeBaseline3dDiagnostics(const std::string& output_dir) const;
  void writeBodyVelocityDiagnostics(const std::string& output_dir) const;
  void writeNedVelocitySourceDiagnostics(const std::string& output_dir) const;
  const std::vector<NedVelocitySourceEvent>& nedVelocitySourceEvents() const { return ned_velocity_source_events_; }
  const HeadingSourceCounts& headingSourceCounts() const { return heading_source_counts_; }
  const std::vector<HeadingSourceDecision>& headingSourceEvents() const { return heading_source_events_; }
  void writeHeadingSourceDiagnostics(const std::string& output_dir) const;
  void setSupportPoseEvents(const std::vector<SupportPoseEvent>& events);
  void finalizeSupportPoseStream();
  void writeSupportPoseDiagnostics(const std::string& output_dir) const;
  const SupportPoseCounts& supportPoseCounts() const {return support_pose_counts_;}
  bool hasSupportPoseStartBetween(double after_time,double through_time) const;
  double supportPoseFactorStartTime(const std::string& clone_id) const;
  const std::vector<SupportPoseRevocation>& pendingSupportRevocations() const {return support_pose_revocations_;}
  void setRevokedSupportFactorIds(const std::set<std::string>& ids) {support_pose_revoked_=ids;}
  void setFootPairEvents(const std::vector<FootPairEvent>& events);
  void finalizeFootPairStream();
  void writeAttitudeCloneDiagnostics(const std::string& output_dir) const;
  const AttitudeCloneCounts& attitudeCloneCounts() const { return attitude_clone_counts_; }
  Matrix jointAttitudeCovariance() const;
  bool attitudeCloneActive() const { return attitude_clone_active_; }
  void setArcSourceEvents(const std::vector<ArcSourceEvent>& events);
  void finalizeArcSourceStream();
  void writeArcCloneDiagnostics(const std::string& output_dir) const;
  const ArcCloneCounts& arcCloneCounts() const { return arc_clone_counts_; }
  const std::vector<ArcJointPrior>& arcJointPriors() const { return arc_joint_priors_; }
  const std::vector<ArcLifecycleEvent>& arcLifecycleEvents() const { return arc_lifecycle_events_; }
  const std::vector<ArcConditioningEvent>& arcConditioningEvents() const { return arc_conditioning_events_; }
  const std::vector<ArcImuSegment>& arcImuSegments() const { return arc_imu_segments_; }
  bool arcNativeTelemetryEnabled() const { return arc_native_telemetry_enabled_; }


 private:
  friend struct ArcNativeTestAccess;  // Synthetic harness: no production setter is exposed.
  friend struct NedHvSourceTestAccess;  // Isolate synthetic selection/gating probes only.
  struct JointTimedEvent {
    double time=0.0;
    bool has_gnss=false;
    GnssData gnss;
    std::vector<FootPairEvent> feet;
    std::vector<ArcSourceEvent> arcs;
    std::vector<SupportPoseEvent> support;
  };
  void processExactJointEvents(const std::vector<JointTimedEvent>& events);
  bool jointCloneEnabled() const;
  void initializeArcDiagnostics();
  void appendArcTimedEvents(std::vector<JointTimedEvent>& events);
  void processArcSourceEvent(const ArcSourceEvent& event);
  void recordArcConditioning(const std::string& kind, const std::string& source_tag,
                             const std::string& provider_measurement_identity="UNKNOWN");
  void recordArcImuSegment(const ImuData& previous, const ImuData& segment);
  std::string arcConditioningInformationId() const;
  attitude_clone::Gaussian attitudeJointState() const;
  void setAttitudeJointState(const attitude_clone::Gaussian& state);
  void processFootPairEvent(const FootPairEvent& event);
  void retireAttitudeClone();
  void requireFrozenCloneBlocks() const;
  void recordFootEvent(const FootPairEvent& event, const std::string& action,
                       bool applied=false, double epsilon=0.0,
                       double prior_score=0.0, double bound_score=0.0,
                       double safe_innovation=-1.0);
  bool supportPoseEnabled() const {return options_.support_pose_config.mode!="off";}
  pose_clone::Gaussian supportPoseJointState() const;
  void setSupportPoseJointState(const pose_clone::Gaussian& state);
  void appendSupportPoseEvents(std::vector<JointTimedEvent>& events);
  void processSupportPoseEvent(const SupportPoseEvent& event);
  void retireSupportPose();
  void recordSupportPose(const SupportPoseEvent&,const std::string&,bool attempted=false,bool accepted=false,double statistic=0.0);
  void initializeCovariance();
  void initializeQc();
  void buildErrorStateMatrices(const ImuData& imu, Matrix& F, Matrix& G, Matrix& Phi, Matrix& Qd) const;
  void applyPositionUpdate(GnssData& gnss);
  bool receiverVelocityUpdateEnabledForTime(double time) const;
  GnssData receiverVelocityStressView(const GnssData& gnss) const;
  double deterministicVelocityNoise(double time, int axis) const;
  void applyVelocityUpdate(GnssData& gnss);
  Vec3 compensatedAngularRate() const;
  Matrix antennaVelocityJacobian(const Vec3& omega_b) const;
  double dualAntennaYawPrediction() const;
  Matrix dualAntennaYawJacobian() const;
  void applyYawUpdate(GnssData& gnss);
  void applyBasicDualYawUpdate(GnssData& gnss);
  void applyBaseline3dUpdate(const GnssData& gnss, bool basic,
                             const std::string& qa_action, double qa_R_scale);
  void applyRawDopplerUpdateForTime(double update_time);
  void applyGo2AttitudeWeakPriorForTime(double update_time);
  void applyGo2VelocityDiagnosticPriorForTime(double update_time);
  void resetNedVelocitySourceGeneration(const std::string& reason);
  void applyBodyVelocityPriorForTime(double update_time);
  void applyFgoFeedbackForTime(double update_time);
  quality_aware::QAObservation buildQAObservation(const GnssData& gnss) const;
  void enrichGo2ReadinessMetadata(source_aware::SourceMetadata& metadata, double update_time);
  source_aware::SourceWeightResult applySourceAwareWeighting(
      source_aware::MeasurementSource source,
      const source_aware::SourceMetadata& metadata,
      const std::vector<double>& dz,
      const Matrix& H,
      const Matrix& R,
      Matrix& scaled_R);
  double wrapYawResidual(double residual_rad) const;
  Matrix covarianceMatrix() const;
  void setCovarianceMatrix(const Matrix& matrix);

  PortOptions options_;
  bool support_pose_active_=false,support_pose_stream_started_=false;
  Matrix support_pose_cross_{21,6,0.0},support_pose_cov_{6,6,0.0};
  std::vector<double> support_pose_error_=std::vector<double>(6,0.0);
  Vec3 support_pose_position_ecef_{};
  Matrix3 support_pose_cbe_{};
  SupportPoseEvent support_pose_start_;
  std::vector<SupportPoseEvent> support_pose_events_;
  std::size_t next_support_pose_event_=0;
  SupportPoseCounts support_pose_counts_;
  std::set<std::string> support_pose_revoked_,support_pose_applied_ids_;
  std::vector<SupportPoseRevocation> support_pose_revocations_;
  struct SupportPoseDiagnostic {
    double time=0,state_time=0,statistic=0;
    std::string type,clone_id,reason;
    bool attempted=false,accepted=false;
  };
  std::vector<SupportPoseDiagnostic> support_pose_diagnostics_;
  bool attitude_clone_active_=false;
  std::string attitude_clone_owner_="NONE";
  std::vector<ArcSourceEvent> arc_events_;
  std::size_t next_arc_event_=0, arc_dispatch_ordinal_=0, arc_state_sample_count_=0;
  bool arc_stream_started_=false, arc_stream_finalized_=false, arc_native_telemetry_enabled_=false;
  ArcCloneCounts arc_clone_counts_;
  std::vector<ArcLifecycleEvent> arc_lifecycle_events_;
  std::vector<ArcConditioningEvent> arc_conditioning_events_;
  std::vector<ArcImuSegment> arc_imu_segments_;
  std::vector<ArcJointPrior> arc_joint_priors_;
  ArcJointPrior arc_active_prior_;
  std::size_t arc_active_lifecycle_=0;
  Matrix attitude_clone_cross_{RANK,3,0.0};
  Matrix attitude_clone_cov_{3,3,0.0};
  Vec3 attitude_clone_error_{};
  Matrix3 attitude_clone_cbe_{};
  FootPairEvent attitude_clone_start_;
  std::set<std::string> attitude_clone_used_ids_, foot_used_endpoint_ids_;
  std::vector<double> attitude_clone_weights_;
  std::vector<FootPairEvent> foot_events_;
  std::size_t next_foot_event_=0;
  bool foot_stream_started_=false;
  AttitudeCloneCounts attitude_clone_counts_;
  struct FootEventDiagnostic {
    double event_time=0, state_time=0, source_time=0;
    std::string type, clone_id, endpoint_id, action;
    bool applied=false;
    double epsilon=0, prior_score=0, bound_score=0, safe_innovation=-1;
  };
  std::vector<FootEventDiagnostic> foot_event_diagnostics_;
  bool foot_information_diagnostics_enabled_=false;
  struct FootInformationDiagnostic {
    double event_time=0.0;
    attitude_clone::Gaussian prior;
    attitude_clone::PairModel model;
    attitude_clone::YoungDiagnostics young;
    bool applied=false;
    double selected_epsilon=0.0;
  };
  std::vector<FootInformationDiagnostic> foot_information_diagnostics_;

  HeadingSourcePolicy heading_source_policy_;
  HeadingSourceCounts heading_source_counts_;
  std::vector<HeadingSourceDecision> heading_source_events_;
  NavState pvapre_;
  NavState pvacur_;
  ImuError imuerror_;
  ImuData imupre_;
  ImuData imucur_;
  GnssData gnssdata_;
  Matrix Cov_;
  Matrix Qc_;
  std::vector<double> dx_;
  double timestamp_ = 0.0;
  std::size_t propagation_count_ = 0;
  std::size_t cov_health_fail_count_ = 0;
  double cov_health_first_failure_time_ = -1.0;
  std::size_t update_count_ = 0;
  std::size_t position_update_count_ = 0;
  std::size_t velocity_update_count_ = 0;
  std::size_t yaw_update_count_ = 0;
  std::size_t yaw_normal_count_ = 0;
  std::size_t yaw_downweight_count_ = 0;
  std::size_t yaw_reject_count_ = 0;
  Baseline3dCounts baseline3d_counts_;
  std::vector<Baseline3dDiagnostics> baseline3d_diagnostics_;
  std::size_t source_aware_evaluation_count_ = 0;
  std::size_t source_aware_weight_changed_count_ = 0;
  std::vector<RawDopplerVelocityMeasurement> raw_doppler_measurements_;
  RawDopplerFactorStatus raw_doppler_status_;
  std::vector<double> raw_doppler_residual_norms_;
  std::vector<Go2AttitudeWeakPriorMeasurement> go2_attitude_priors_;
  Go2AttitudeWeakPriorStatus go2_attitude_prior_status_;
  std::vector<double> go2_roll_residuals_;
  std::vector<double> go2_pitch_residuals_;
  std::vector<Go2VelocityDiagnosticPriorMeasurement> go2_velocity_diagnostic_priors_;
  Go2VelocityDiagnosticPriorStatus go2_velocity_diagnostic_prior_status_;
  bool ned_velocity_source_has_attempt_ = false;
  double ned_velocity_source_last_attempt_time_ = 0.0;
  std::string ned_velocity_generation_reset_reason_;
  NedVelocitySourceCounts ned_velocity_source_counts_;
  std::vector<NedVelocitySourceEvent> ned_velocity_source_events_;
  std::vector<Go2ReadinessLsimMetadataMeasurement> go2_readiness_lsim_metadata_;
  Go2ReadinessLsimMetadataStatus go2_readiness_lsim_metadata_status_;
  std::vector<fgo_feedback::FgoFeedbackObservation> fgo_feedback_observations_;
  fgo_feedback::FgoFeedbackStatus fgo_feedback_status_;
  std::vector<fgo_feedback::FgoFeedbackTraceRow> fgo_feedback_trace_;
  std::vector<double> fgo_feedback_position_norms_;
  std::vector<double> fgo_feedback_velocity_norms_;
  std::vector<double> fgo_feedback_attitude_norms_deg_;
  double last_fgo_feedback_time_ = -1.0e100;
  double research_last_rp_attempt_time_ = -1.0e100;
  double research_last_rd_attempt_time_ = -1.0e100;
  double research_last_body_hv_attempt_time_ = -1.0e100;
  double research_next_body_hv_tick_ = 0.0;
  struct BodyVelocityEvent {
    double time=0.0, source_time=0.0;
    bool source_present=false, valid=false, accepted=false;
    std::string reason;
  };
  std::vector<BodyVelocityEvent> body_velocity_events_;
  quality_aware::QAFallbackSupervisor qa_fallback_supervisor_;
  source_aware::SourceAwarePolicy source_aware_policy_;
  source_aware::QualityStateManager quality_state_manager_;
  source_aware::SourceAwareTrace source_aware_trace_;
  source_aware::QualityStateTrace quality_state_trace_;
  bool initialized_ = false;
};

}  // namespace legsa_v23_port_core
