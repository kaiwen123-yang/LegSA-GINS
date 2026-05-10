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
#include "legsa_v23_port_core/factors/raw_doppler_types.hpp"

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
  void EKFUpdate(const std::vector<double>& dz, const Matrix& H, const Matrix& R);
  void stateFeedback();
  void newImuProcess();
  bool checkCov() const;

  const NavState& navState() const;
  NavState getNavState() const;
  const std::vector<double>& getCovariance() const;
  double timestamp() const;
  std::size_t propagationCount() const;
  std::size_t updateCount() const;
  std::size_t positionUpdateCount() const;
  std::size_t velocityUpdateCount() const;
  std::size_t yawUpdateCount() const;
  std::size_t yawNormalCount() const;
  std::size_t yawDownweightCount() const;
  std::size_t yawRejectCount() const;
  std::size_t rawDopplerUpdateCount() const;
  std::size_t rawDopplerRejectCount() const;
  std::size_t rawDopplerEpochCount() const;
  std::size_t rawDopplerSatCountMin() const;
  std::size_t rawDopplerSatCountMedian() const;
  std::size_t rawDopplerSatCountMax() const;
  double rawDopplerResidualP95() const;
  RawDopplerFactorStatus rawDopplerStatus() const;

 private:
  void initializeCovariance();
  void initializeQc();
  void buildErrorStateMatrices(const ImuData& imu, Matrix& F, Matrix& G, Matrix& Phi, Matrix& Qd) const;
  void applyPositionUpdate(GnssData& gnss);
  bool receiverVelocityUpdateEnabledForTime(double time) const;
  GnssData receiverVelocityStressView(const GnssData& gnss) const;
  double deterministicVelocityNoise(double time, int axis) const;
  void applyVelocityUpdate(GnssData& gnss);
  void applyYawUpdate(GnssData& gnss);
  void applyRawDopplerUpdateForTime(double update_time);
  double wrapYawResidual(double residual_rad) const;
  Matrix covarianceMatrix() const;
  void setCovarianceMatrix(const Matrix& matrix);

  PortOptions options_;
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
  std::size_t update_count_ = 0;
  std::size_t position_update_count_ = 0;
  std::size_t velocity_update_count_ = 0;
  std::size_t yaw_update_count_ = 0;
  std::size_t yaw_normal_count_ = 0;
  std::size_t yaw_downweight_count_ = 0;
  std::size_t yaw_reject_count_ = 0;
  std::vector<RawDopplerVelocityMeasurement> raw_doppler_measurements_;
  RawDopplerFactorStatus raw_doppler_status_;
  std::vector<double> raw_doppler_residual_norms_;
  bool initialized_ = false;
};

}  // namespace legsa_v23_port_core
