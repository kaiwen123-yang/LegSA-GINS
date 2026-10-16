#pragma once

#include <Eigen/Dense>

#include <map>
#include <string>
#include <vector>

namespace hartley {

using Matrix = Eigen::MatrixXd;
using Vector = Eigen::VectorXd;
using Matrix3 = Eigen::Matrix3d;
using Vector3 = Eigen::Vector3d;

inline constexpr double kSmallAngleSeriesThresholdRad = 0.1;

enum class BackendIdentity {
  HARTLEY_IJRR2020_REPORTED_BACKEND,
  EXACT_QD_REFERENCE_DIAGNOSTIC,
  OFFICIAL_CPP_EARLY_REGRESSION,
};

std::string backendIdentityName(BackendIdentity identity);

struct ContinuousNoiseDensity {
  // Amplitude spectral densities. These values are never pre-scaled by dt.
  double gyro_measurement_rad_per_s_per_sqrt_hz{0.0};
  double accelerometer_measurement_m_per_s2_per_sqrt_hz{0.0};
  double gyro_bias_rw_rad_per_s2_per_sqrt_hz{0.0};
  double accelerometer_bias_rw_m_per_s3_per_sqrt_hz{0.0};
  double contact_velocity_m_per_s_per_sqrt_hz{0.0};

  void validate() const;
};

struct ContinuousNoisePsd {
  // One-sided continuous PSD intensities, obtained by squaring each density once.
  double gyro_measurement_rad2_per_s{0.0};
  double accelerometer_measurement_m2_per_s3{0.0};
  double gyro_bias_rw_rad2_per_s3{0.0};
  double accelerometer_bias_rw_m2_per_s5{0.0};
  double contact_velocity_m2_per_s{0.0};
};

struct DiscreteSampleStd {
  // Diagnostic conversion only. Production Qc/Qd construction never calls this API.
  double gyro_measurement_rad_per_s{0.0};
  double accelerometer_measurement_m_per_s2{0.0};
  double gyro_bias_increment_rad_per_s{0.0};
  double accelerometer_bias_increment_m_per_s2{0.0};
  double contact_position_increment_m{0.0};
};

struct PaperTable1DiscreteStd {
  // IJRR Table 1 is explicitly "Experiment Discrete Noise Statistics".
  // Five process-side native standard deviations are accepted only by the
  // Eq. 61/Qbar adapter and are never reinterpreted as continuous ASDs.  The
  // sixth, joint-encoder noise, is measurement-side and maps through a
  // supplied foot-position Jacobian to R.
  double angular_velocity_noise_std_rad_per_s{0.002};
  double linear_acceleration_noise_std_m_per_s2{0.04};
  double gyroscope_bias_random_walk_std_rad_per_s2{0.001};
  double accelerometer_bias_random_walk_std_m_per_s3{0.001};
  double contact_linear_velocity_noise_std_m_per_s{0.05};
  // Measurement-side joint-angle standard deviation in degrees.  It is
  // converted to radians only inside the Jacobian-based covariance API.
  double joint_encoder_noise_std_deg{1.0};

  void validate() const;
};

struct PaperTable1ProcessStd {
  // The five process-side IJRR Table-1 values.  This H5 type intentionally
  // cannot represent the measurement-side one-degree encoder statistic.
  double angular_velocity_noise_std_rad_per_s{0.002};
  double linear_acceleration_noise_std_m_per_s2{0.04};
  double gyroscope_bias_random_walk_std_rad_per_s2{0.001};
  double accelerometer_bias_random_walk_std_m_per_s3{0.001};
  double contact_linear_velocity_noise_std_m_per_s{0.05};

  void validate() const;
};

struct H5Eq61NoisePolicy {
  enum class Kind { GO2_CONTINUOUS_IMU_PAPER_CONTACT, PAPER_TABLE1_PROCESS };
  Kind kind{Kind::GO2_CONTINUOUS_IMU_PAPER_CONTACT};
  ContinuousNoiseDensity go2_imu_density{};
  PaperTable1ProcessStd paper_process{};

  static H5Eq61NoisePolicy go2ImuPaperContact(
      ContinuousNoiseDensity imu_density,
      double contact_linear_velocity_noise_std_m_per_s = 0.05);
  static H5Eq61NoisePolicy paperTable1Process(
      PaperTable1ProcessStd process = PaperTable1ProcessStd{});
  void validate() const;
  std::string tag() const;
};

struct MeasurementStdMeters {
  // Forward-kinematics proxy measurement standard deviation; R only, never Qc.
  double value_m{0.0};

  void validate() const;
};

ContinuousNoisePsd continuousPsdFromDensity(const ContinuousNoiseDensity& density);
DiscreteSampleStd discreteSampleStdFromDensity(const ContinuousNoiseDensity& density,
                                               double dt_seconds);
Matrix3 isotropicMeasurementCovariance(MeasurementStdMeters standard_deviation);
Matrix3 contactMeasurementCovarianceFromPaperTable1JointEncoder(
    const Matrix& foot_position_jacobian_m_per_rad,
    const PaperTable1DiscreteStd& paper_parameters);

Matrix3 skew(const Vector3& value);
Vector3 vee(const Matrix3& value);
Matrix3 gamma0(const Vector3& phi);
Matrix3 gamma1(const Vector3& phi);
Matrix3 gamma2(const Vector3& phi);
Matrix3 psi1(const Vector3& phi, const Vector3& vector);
Matrix3 psi2(const Vector3& phi, const Vector3& vector);
Matrix3 expSO3(const Vector3& phi);
Vector3 logSO3(const Matrix3& rotation);

struct GroupState {
  Matrix3 rotation{Matrix3::Identity()};
  Vector3 velocity{Vector3::Zero()};
  Vector3 position{Vector3::Zero()};
  std::map<int, Vector3> contacts;
};

GroupState compose(const GroupState& lhs, const GroupState& rhs);
GroupState inverse(const GroupState& state);
GroupState expSEK3(const Vector& tangent, const std::vector<int>& contact_ids);
Vector logSEK3(const GroupState& state, const std::vector<int>& contact_ids);
Matrix adjointSEK3(const GroupState& state, const std::vector<int>& contact_ids);

struct StateMean : GroupState {
  Vector3 gyro_bias{Vector3::Zero()};
  Vector3 accelerometer_bias{Vector3::Zero()};
};

struct ContactMeasurement {
  int leg_id{0};
  Vector3 foot_position_body{Vector3::Zero()};
  Matrix3 covariance_body_m2{Matrix3::Identity()};
};

struct PropagationLinearization {
  Matrix A;
  Matrix L;
  Matrix Qc;
  Matrix Phi;
  Matrix Qd;
};

struct CorrectionDiagnostics {
  Matrix H;
  Matrix R;
  Vector innovation;
  Matrix innovation_covariance;
  double nis{0.0};
  bool factorization_ok{false};
};

struct BackendDiagnostics {
  BackendIdentity backend_identity{BackendIdentity::HARTLEY_IJRR2020_REPORTED_BACKEND};
  PropagationLinearization propagation;
  CorrectionDiagnostics correction;
};

struct H5RuntimeDiagnostics {
  std::size_t propagation_calls{0};
  std::size_t eq61_calls{0};
  std::size_t eq52_calls{0};
  std::size_t lifecycle_calls{0};
  std::size_t corrected_contacts{0};
  std::size_t removed_contacts{0};
  std::size_t added_contacts{0};
  std::string process_noise_policy_tag{"LEGACY_CONTINUOUS_DENSITY"};
  Matrix last_qbar;
};

class HartleyInEkf {
 public:
  HartleyInEkf(StateMean mean, Matrix covariance,
               ContinuousNoiseDensity noise_density,
               BackendIdentity identity =
                   BackendIdentity::HARTLEY_IJRR2020_REPORTED_BACKEND,
               Vector3 gravity_world = Vector3(0.0, 0.0, -9.81));
  HartleyInEkf(StateMean mean, Matrix covariance,
               H5Eq61NoisePolicy h5_noise_policy,
               Vector3 gravity_world = Vector3(0.0, 0.0, -9.81));

  const StateMean& stateMean() const { return mean_; }
  const Matrix& stateCovariance() const { return covariance_; }
  std::vector<int> activeContactIdentities() const;
  int stateDimension() const;
  BackendIdentity diagnosticBackendIdentity() const { return identity_; }
  const BackendDiagnostics& diagnostics() const { return diagnostics_; }
  const H5RuntimeDiagnostics& h5RuntimeDiagnostics() const {
    return h5_runtime_diagnostics_;
  }

  void propagate(const Vector3& omega_measurement_rad_per_s,
                 const Vector3& acceleration_measurement_m_per_s2,
                 double dt_seconds);
  CorrectionDiagnostics correctContacts(
      const std::vector<ContactMeasurement>& measurements);
  CorrectionDiagnostics correctContactSubsetForOfficialEarlyRegression(
      const std::vector<ContactMeasurement>& measurements);
  void augmentContacts(const std::vector<ContactMeasurement>& measurements);
  void removeContacts(const std::vector<int>& leg_ids);
  void initializeContactsEq32WithIndependentPrior(
      const std::vector<ContactMeasurement>& measurements,
      double independent_contact_prior_std_m = 0.1);
  CorrectionDiagnostics processContactLifecycle(
      const std::vector<ContactMeasurement>& surviving_measurements,
      const std::vector<int>& ended_leg_ids,
      const std::vector<ContactMeasurement>& added_measurements);

  static StateMean exactMeanStep(const StateMean& state,
                                 const Vector3& corrected_omega_rad_per_s,
                                 const Vector3& corrected_acceleration_m_per_s2,
                                 double dt_seconds,
                                 const Vector3& gravity_world);
  static StateMean officialEarlyMeanStep(
      const StateMean& state, const Vector3& corrected_omega_rad_per_s,
      const Vector3& corrected_acceleration_m_per_s2, double dt_seconds,
      const Vector3& gravity_world);
  static Matrix continuousA(const StateMean& state,
                            const Vector3& gravity_world);
  static Matrix continuousL(const StateMean& state);
  static Matrix continuousQc(const StateMean& state,
                             const ContinuousNoiseDensity& density);
  static Matrix analyticalPhi(const StateMean& state,
                              const Vector3& corrected_omega_rad_per_s,
                              const Vector3& corrected_acceleration_m_per_s2,
                              double dt_seconds,
                              const Vector3& gravity_world);
  static Matrix analyticalPhiEq60(const StateMean& state,
                                  const Vector3& corrected_omega_rad_per_s,
                                  const Vector3& corrected_acceleration_m_per_s2,
                                  double dt_seconds,
                                  const Vector3& gravity_world);
  static Matrix eq61ProcessCovariance(
      const StateMean& state, const Vector3& corrected_omega_rad_per_s,
      const Vector3& corrected_acceleration_m_per_s2, double dt_seconds,
      const Vector3& gravity_world, const ContinuousNoiseDensity& density);
  static Matrix eq61MappedQbarPaperTable1(
      const StateMean& state, const PaperTable1DiscreteStd& paper_parameters);
  static Matrix eq61MappedQbarPaperTable1Process(
      const StateMean& state, const PaperTable1ProcessStd& paper_parameters);
  static Matrix eq61MappedQbarGo2ImuPaperContact(
      const StateMean& state, const ContinuousNoiseDensity& go2_imu_density,
      const PaperTable1DiscreteStd& paper_parameters);
  static Matrix eq61ProcessCovariancePaperTable1(
      const StateMean& state, const Vector3& corrected_omega_rad_per_s,
      const Vector3& corrected_acceleration_m_per_s2, double dt_seconds,
      const Vector3& gravity_world,
      const PaperTable1DiscreteStd& paper_parameters);
  static Matrix eq61ProcessCovarianceGo2ImuPaperContact(
      const StateMean& state, const Vector3& corrected_omega_rad_per_s,
      const Vector3& corrected_acceleration_m_per_s2, double dt_seconds,
      const Vector3& gravity_world,
      const ContinuousNoiseDensity& go2_imu_density,
      const PaperTable1DiscreteStd& paper_parameters);
  static Matrix eq52ProcessCovarianceGaussLegendre64(
      const StateMean& state, const Vector3& corrected_omega_rad_per_s,
      const Vector3& corrected_acceleration_m_per_s2, double dt_seconds,
      const Vector3& gravity_world, const ContinuousNoiseDensity& density);

 private:
  StateMean mean_;
  Matrix covariance_;
  ContinuousNoiseDensity noise_density_;
  BackendIdentity identity_;
  Vector3 gravity_world_;
  BackendDiagnostics diagnostics_;
  bool h5_policy_enabled_{false};
  H5Eq61NoisePolicy h5_noise_policy_{};
  H5RuntimeDiagnostics h5_runtime_diagnostics_{};

  void validateStateAndCovariance() const;
  void applyLeftCorrection(const Vector& delta);
  CorrectionDiagnostics correctContactsImpl(
      const std::vector<ContactMeasurement>& measurements,
      bool require_all_active_contacts);
};

}  // namespace hartley
