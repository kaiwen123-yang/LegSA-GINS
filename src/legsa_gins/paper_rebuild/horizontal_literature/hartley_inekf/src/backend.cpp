#include "hartley_inekf/backend.hpp"

#include <Eigen/Eigenvalues>
#include <unsupported/Eigen/MatrixFunctions>

#include <algorithm>
#include <cmath>
#include <set>
#include <stdexcept>
#include <utility>

namespace hartley {
namespace {

constexpr int kSeriesTerms = 64;

void requireFinite(double value, const char* name) {
  if (!std::isfinite(value)) {
    throw std::invalid_argument(std::string(name) + " must be finite");
  }
}

double requireFiniteNorm(const Vector3& value, const char* name) {
  if (!value.allFinite()) {
    throw std::invalid_argument(std::string(name) + " must be finite");
  }
  const double norm = value.norm();
  if (!std::isfinite(norm)) {
    throw std::invalid_argument(std::string(name) + " norm must be finite");
  }
  return norm;
}

Matrix3 requireFiniteLieResult(Matrix3 result, const char* name) {
  if (!result.allFinite()) {
    throw std::overflow_error(std::string(name) + " result is non-finite");
  }
  return result;
}

void requirePositiveDt(double dt) {
  requireFinite(dt, "dt_seconds");
  if (!(dt > 0.0)) {
    throw std::invalid_argument("dt_seconds must be positive");
  }
}

void requireNonnegativeDt(double dt) {
  requireFinite(dt, "dt_seconds");
  if (dt < 0.0) {
    throw std::invalid_argument("dt_seconds must be nonnegative");
  }
}

Matrix3 gammaSeries(const Vector3& phi, int order) {
  if (!phi.allFinite() || order < 0 || order > 2) {
    throw std::invalid_argument("invalid Gamma input");
  }
  const Matrix3 A = skew(phi);
  Matrix3 power = Matrix3::Identity();
  long double denominator = 1.0L;
  for (int index = 2; index <= order; ++index) {
    denominator *= static_cast<long double>(index);
  }
  Matrix3 result = power / static_cast<double>(denominator);
  for (int n = 1; n < kSeriesTerms; ++n) {
    power *= A;
    denominator *= static_cast<long double>(n + order);
    const Matrix3 term = power / static_cast<double>(denominator);
    result += term;
    if (term.cwiseAbs().maxCoeff() < 2.0e-16) {
      break;
    }
  }
  return result;
}

Matrix3 gammaClosedForm(const Vector3& phi, int order) {
  const double theta = phi.norm();
  const double theta2 = theta * theta;
  const Matrix3 K = skew(phi / theta);
  const Matrix3 K2 = K * K;
  const double sine = std::sin(theta);
  const double one_minus_cosine =
      2.0 * std::sin(0.5 * theta) * std::sin(0.5 * theta);
  if (order == 0) {
    return Matrix3::Identity() + sine * K + one_minus_cosine * K2;
  }
  if (order == 1) {
    return Matrix3::Identity() + (one_minus_cosine / theta) * K +
           (1.0 - sine / theta) * K2;
  }
  return 0.5 * Matrix3::Identity() +
         ((1.0 - sine / theta) / theta) * K +
         (0.5 - one_minus_cosine / theta2) * K2;
}

Matrix3 psiSeries(const Vector3& phi, const Vector3& vector, int order) {
  if (!phi.allFinite() || !vector.allFinite() || order < 1 || order > 2) {
    throw std::invalid_argument("invalid Psi input");
  }
  const Matrix3 A = skew(phi);
  std::vector<Matrix3> powers(kSeriesTerms, Matrix3::Identity());
  for (int n = 1; n < kSeriesTerms; ++n) {
    powers[n] = powers[n - 1] * A;
  }
  Matrix3 result = Matrix3::Zero();
  long double denominator = 1.0L;
  for (int index = 2; index <= order; ++index) {
    denominator *= static_cast<long double>(index);
  }
  for (int n = 1; n < kSeriesTerms; ++n) {
    denominator *= static_cast<long double>(n + order);
    Matrix3 derivative = Matrix3::Zero();
    for (int column = 0; column < 3; ++column) {
      const Matrix3 basis_skew = skew(Vector3::Unit(column));
      Matrix3 d_power = Matrix3::Zero();
      for (int k = 0; k < n; ++k) {
        d_power += powers[k] * basis_skew * powers[n - 1 - k];
      }
      derivative.col(column) = d_power * vector;
    }
    const Matrix3 term = derivative / static_cast<double>(denominator);
    result += term;
    if (term.cwiseAbs().maxCoeff() < 2.0e-16) {
      break;
    }
  }
  return result;
}

Matrix3 psiClosedFormDerivative(const Vector3& phi, const Vector3& vector,
                                int order) {
  const double theta = phi.norm();
  const double theta2 = theta * theta;
  const double theta3 = theta2 * theta;
  const double theta4 = theta2 * theta2;
  const double theta5 = theta4 * theta;
  const double sine = std::sin(theta);
  const double cosine = std::cos(theta);
  const Matrix3 A = skew(phi);
  const Vector3 Av = A * vector;
  const Vector3 A2v = A * Av;

  double c1 = 0.0;
  double c2 = 0.0;
  double dc1 = 0.0;
  double dc2 = 0.0;
  if (order == 1) {
    c1 = (1.0 - cosine) / theta2;
    c2 = (theta - sine) / theta3;
    dc1 = (theta * sine - 2.0 * (1.0 - cosine)) / theta3;
    dc2 = (theta * (1.0 - cosine) - 3.0 * (theta - sine)) / theta4;
  } else {
    c1 = (theta - sine) / theta3;
    c2 = (theta2 + 2.0 * cosine - 2.0) / (2.0 * theta4);
    dc1 = (theta * (1.0 - cosine) - 3.0 * (theta - sine)) / theta4;
    dc2 = (4.0 - 4.0 * cosine - theta2 - theta * sine) / theta5;
  }

  Matrix3 derivative =
      -c1 * skew(vector) - c2 * (skew(Av) + A * skew(vector));
  derivative += (dc1 / theta) * Av * phi.transpose();
  derivative += (dc2 / theta) * A2v * phi.transpose();
  return derivative;
}

std::vector<int> sortedContactIds(const GroupState& state) {
  std::vector<int> ids;
  ids.reserve(state.contacts.size());
  for (const auto& entry : state.contacts) {
    ids.push_back(entry.first);
  }
  return ids;
}

int groupDimension(const GroupState& state) {
  return 9 + 3 * static_cast<int>(state.contacts.size());
}

int contactOffset(const std::vector<int>& ids, int id) {
  const auto iterator = std::lower_bound(ids.begin(), ids.end(), id);
  if (iterator == ids.end() || *iterator != id) {
    throw std::invalid_argument("contact identity is not active");
  }
  return 9 + 3 * static_cast<int>(std::distance(ids.begin(), iterator));
}

std::pair<std::vector<double>, std::vector<double>> gaussLegendre64() {
  constexpr int n = 64;
  constexpr double pi = 3.141592653589793238462643383279502884;
  std::vector<double> nodes(n);
  std::vector<double> weights(n);
  for (int index = 0; index < n / 2; ++index) {
    double x = std::cos(pi * (static_cast<double>(index) + 0.75) /
                        (static_cast<double>(n) + 0.5));
    for (int iteration = 0; iteration < 20; ++iteration) {
      double p0 = 1.0;
      double p1 = x;
      for (int degree = 2; degree <= n; ++degree) {
        const double p2 = ((2.0 * degree - 1.0) * x * p1 -
                           (degree - 1.0) * p0) /
                          degree;
        p0 = p1;
        p1 = p2;
      }
      const double derivative = n * (x * p1 - p0) / (x * x - 1.0);
      const double step = p1 / derivative;
      x -= step;
      if (std::abs(step) < 2.0e-16) {
        break;
      }
    }
    double p0 = 1.0;
    double p1 = x;
    for (int degree = 2; degree <= n; ++degree) {
      const double p2 = ((2.0 * degree - 1.0) * x * p1 -
                         (degree - 1.0) * p0) /
                        degree;
      p0 = p1;
      p1 = p2;
    }
    const double derivative = n * (x * p1 - p0) / (x * x - 1.0);
    const double weight = 2.0 / ((1.0 - x * x) * derivative * derivative);
    nodes[index] = -x;
    nodes[n - 1 - index] = x;
    weights[index] = weight;
    weights[n - 1 - index] = weight;
  }
  return {nodes, weights};
}

Matrix symmetrized(const Matrix& value) { return 0.5 * (value + value.transpose()); }

void requireCovariance(const Matrix3& covariance, const char* label) {
  if (!covariance.allFinite()) {
    throw std::invalid_argument(std::string(label) + " must be finite");
  }
  if ((covariance - covariance.transpose()).cwiseAbs().maxCoeff() > 1.0e-12) {
    throw std::invalid_argument(std::string(label) + " must be symmetric");
  }
  Eigen::LLT<Matrix3> factorization(covariance);
  if (factorization.info() != Eigen::Success) {
    throw std::invalid_argument(std::string(label) + " must be positive definite");
  }
}

}  // namespace

std::string backendIdentityName(BackendIdentity identity) {
  switch (identity) {
    case BackendIdentity::HARTLEY_IJRR2020_REPORTED_BACKEND:
      return "HARTLEY_IJRR2020_REPORTED_BACKEND";
    case BackendIdentity::EXACT_QD_REFERENCE_DIAGNOSTIC:
      return "EXACT_QD_REFERENCE_DIAGNOSTIC";
    case BackendIdentity::OFFICIAL_CPP_EARLY_REGRESSION:
      return "OFFICIAL_CPP_EARLY_REGRESSION";
  }
  throw std::invalid_argument("unknown backend identity");
}

void ContinuousNoiseDensity::validate() const {
  const double values[] = {
      gyro_measurement_rad_per_s_per_sqrt_hz,
      accelerometer_measurement_m_per_s2_per_sqrt_hz,
      gyro_bias_rw_rad_per_s2_per_sqrt_hz,
      accelerometer_bias_rw_m_per_s3_per_sqrt_hz,
      contact_velocity_m_per_s_per_sqrt_hz,
  };
  for (const double value : values) {
    requireFinite(value, "continuous noise density");
    if (value < 0.0) {
      throw std::invalid_argument("continuous noise densities must be nonnegative");
    }
  }
}

ContinuousNoisePsd continuousPsdFromDensity(const ContinuousNoiseDensity& density) {
  density.validate();
  return {
      density.gyro_measurement_rad_per_s_per_sqrt_hz *
          density.gyro_measurement_rad_per_s_per_sqrt_hz,
      density.accelerometer_measurement_m_per_s2_per_sqrt_hz *
          density.accelerometer_measurement_m_per_s2_per_sqrt_hz,
      density.gyro_bias_rw_rad_per_s2_per_sqrt_hz *
          density.gyro_bias_rw_rad_per_s2_per_sqrt_hz,
      density.accelerometer_bias_rw_m_per_s3_per_sqrt_hz *
          density.accelerometer_bias_rw_m_per_s3_per_sqrt_hz,
      density.contact_velocity_m_per_s_per_sqrt_hz *
          density.contact_velocity_m_per_s_per_sqrt_hz,
  };
}

DiscreteSampleStd discreteSampleStdFromDensity(const ContinuousNoiseDensity& density,
                                               double dt_seconds) {
  density.validate();
  requirePositiveDt(dt_seconds);
  const double sqrt_dt = std::sqrt(dt_seconds);
  return {
      density.gyro_measurement_rad_per_s_per_sqrt_hz / sqrt_dt,
      density.accelerometer_measurement_m_per_s2_per_sqrt_hz / sqrt_dt,
      density.gyro_bias_rw_rad_per_s2_per_sqrt_hz * sqrt_dt,
      density.accelerometer_bias_rw_m_per_s3_per_sqrt_hz * sqrt_dt,
      density.contact_velocity_m_per_s_per_sqrt_hz * sqrt_dt,
  };
}

void PaperTable1DiscreteStd::validate() const {
  const double values[] = {
      angular_velocity_noise_std_rad_per_s,
      linear_acceleration_noise_std_m_per_s2,
      gyroscope_bias_random_walk_std_rad_per_s2,
      accelerometer_bias_random_walk_std_m_per_s3,
      contact_linear_velocity_noise_std_m_per_s,
      joint_encoder_noise_std_deg,
  };
  for (const double value : values) {
    requireFinite(value, "paper Table-1 discrete standard deviation");
    if (value < 0.0) {
      throw std::invalid_argument(
          "paper Table-1 discrete standard deviations must be nonnegative");
    }
  }
}

void MeasurementStdMeters::validate() const {
  requireFinite(value_m, "measurement standard deviation meters");
  if (!(value_m > 0.0)) {
    throw std::invalid_argument(
        "measurement standard deviation meters must be positive");
  }
}

Matrix3 isotropicMeasurementCovariance(
    MeasurementStdMeters standard_deviation) {
  standard_deviation.validate();
  return standard_deviation.value_m * standard_deviation.value_m *
         Matrix3::Identity();
}

Matrix3 contactMeasurementCovarianceFromPaperTable1JointEncoder(
    const Matrix& foot_position_jacobian_m_per_rad,
    const PaperTable1DiscreteStd& paper_parameters) {
  paper_parameters.validate();
  if (foot_position_jacobian_m_per_rad.rows() != 3 ||
      foot_position_jacobian_m_per_rad.cols() <= 0 ||
      !foot_position_jacobian_m_per_rad.allFinite()) {
    throw std::invalid_argument(
        "foot-position Jacobian must be finite 3xN in m/rad");
  }
  constexpr double kPi = 3.141592653589793238462643383279502884;
  const double sigma_rad =
      paper_parameters.joint_encoder_noise_std_deg * kPi / 180.0;
  const Matrix3 covariance =
      sigma_rad * sigma_rad * foot_position_jacobian_m_per_rad *
      foot_position_jacobian_m_per_rad.transpose();
  return requireFiniteLieResult(symmetrized(covariance),
                                "joint-encoder contact covariance");
}

Matrix3 skew(const Vector3& value) {
  Matrix3 result;
  result << 0.0, -value.z(), value.y(), value.z(), 0.0, -value.x(), -value.y(),
      value.x(), 0.0;
  return result;
}

Vector3 vee(const Matrix3& value) {
  return Vector3(value(2, 1), value(0, 2), value(1, 0));
}

Matrix3 gamma0(const Vector3& phi) {
  const double theta = requireFiniteNorm(phi, "Gamma input");
  return requireFiniteLieResult(
      theta < kSmallAngleSeriesThresholdRad ? gammaSeries(phi, 0)
                                             : gammaClosedForm(phi, 0),
      "Gamma0");
}
Matrix3 gamma1(const Vector3& phi) {
  const double theta = requireFiniteNorm(phi, "Gamma input");
  return requireFiniteLieResult(
      theta < kSmallAngleSeriesThresholdRad ? gammaSeries(phi, 1)
                                             : gammaClosedForm(phi, 1),
      "Gamma1");
}
Matrix3 gamma2(const Vector3& phi) {
  const double theta = requireFiniteNorm(phi, "Gamma input");
  return requireFiniteLieResult(
      theta < kSmallAngleSeriesThresholdRad ? gammaSeries(phi, 2)
                                             : gammaClosedForm(phi, 2),
      "Gamma2");
}
Matrix3 psi1(const Vector3& phi, const Vector3& vector) {
  const double theta = requireFiniteNorm(phi, "Psi rotation input");
  static_cast<void>(requireFiniteNorm(vector, "Psi vector input"));
  return requireFiniteLieResult(
      theta < kSmallAngleSeriesThresholdRad
          ? psiSeries(phi, vector, 1)
          : psiClosedFormDerivative(phi, vector, 1),
      "Psi1");
}
Matrix3 psi2(const Vector3& phi, const Vector3& vector) {
  const double theta = requireFiniteNorm(phi, "Psi rotation input");
  static_cast<void>(requireFiniteNorm(vector, "Psi vector input"));
  return requireFiniteLieResult(
      theta < kSmallAngleSeriesThresholdRad
          ? psiSeries(phi, vector, 2)
          : psiClosedFormDerivative(phi, vector, 2),
      "Psi2");
}
Matrix3 expSO3(const Vector3& phi) { return gamma0(phi); }

Vector3 logSO3(const Matrix3& rotation) {
  if (!rotation.allFinite()) {
    throw std::invalid_argument("SO(3) logarithm input must be finite");
  }
  Eigen::Quaterniond quaternion(rotation);
  quaternion.normalize();
  if (quaternion.w() < 0.0) {
    quaternion.coeffs() *= -1.0;
  }
  const Vector3 vector = quaternion.vec();
  const double norm = vector.norm();
  const double w = quaternion.w();
  if (norm < 1.0e-8) {
    const double ratio2 = (norm * norm) / (w * w);
    const double scale = (2.0 / w) * (1.0 - ratio2 / 3.0 + ratio2 * ratio2 / 5.0);
    return scale * vector;
  }
  return (2.0 * std::atan2(norm, w) / norm) * vector;
}

GroupState compose(const GroupState& lhs, const GroupState& rhs) {
  if (lhs.contacts.size() != rhs.contacts.size()) {
    throw std::invalid_argument("SE_K(3) contact dimensions differ in composition");
  }
  GroupState result;
  result.rotation = lhs.rotation * rhs.rotation;
  result.velocity = lhs.velocity + lhs.rotation * rhs.velocity;
  result.position = lhs.position + lhs.rotation * rhs.position;
  for (const auto& entry : rhs.contacts) {
    const auto lhs_entry = lhs.contacts.find(entry.first);
    if (lhs_entry == lhs.contacts.end()) {
      throw std::invalid_argument("SE_K(3) contact identities differ in composition");
    }
    result.contacts.emplace(entry.first,
                            lhs_entry->second + lhs.rotation * entry.second);
  }
  return result;
}

GroupState inverse(const GroupState& state) {
  GroupState result;
  result.rotation = state.rotation.transpose();
  result.velocity = -result.rotation * state.velocity;
  result.position = -result.rotation * state.position;
  for (const auto& entry : state.contacts) {
    result.contacts.emplace(entry.first, -result.rotation * entry.second);
  }
  return result;
}

GroupState expSEK3(const Vector& tangent, const std::vector<int>& contact_ids) {
  if (tangent.size() != 9 + 3 * static_cast<int>(contact_ids.size()) ||
      !tangent.allFinite() || !std::is_sorted(contact_ids.begin(), contact_ids.end()) ||
      std::adjacent_find(contact_ids.begin(), contact_ids.end()) != contact_ids.end()) {
    throw std::invalid_argument("invalid SE_K(3) exponential arguments");
  }
  GroupState result;
  const Vector3 phi = tangent.segment<3>(0);
  result.rotation = expSO3(phi);
  const Matrix3 jacobian = gamma1(phi);
  result.velocity = jacobian * tangent.segment<3>(3);
  result.position = jacobian * tangent.segment<3>(6);
  for (std::size_t index = 0; index < contact_ids.size(); ++index) {
    result.contacts.emplace(contact_ids[index],
                            jacobian * tangent.segment<3>(9 + 3 * index));
  }
  return result;
}

Vector logSEK3(const GroupState& state, const std::vector<int>& contact_ids) {
  if (contact_ids != sortedContactIds(state)) {
    throw std::invalid_argument("SE_K(3) logarithm contact identities differ");
  }
  Vector tangent = Vector::Zero(groupDimension(state));
  const Vector3 phi = logSO3(state.rotation);
  const Matrix3 inverse_jacobian = gamma1(phi).inverse();
  tangent.segment<3>(0) = phi;
  tangent.segment<3>(3) = inverse_jacobian * state.velocity;
  tangent.segment<3>(6) = inverse_jacobian * state.position;
  for (std::size_t index = 0; index < contact_ids.size(); ++index) {
    tangent.segment<3>(9 + 3 * index) =
        inverse_jacobian * state.contacts.at(contact_ids[index]);
  }
  return tangent;
}

Matrix adjointSEK3(const GroupState& state, const std::vector<int>& contact_ids) {
  if (contact_ids != sortedContactIds(state)) {
    throw std::invalid_argument("SE_K(3) adjoint contact identities differ");
  }
  const int dimension = groupDimension(state);
  Matrix result = Matrix::Zero(dimension, dimension);
  result.block<3, 3>(0, 0) = state.rotation;
  const std::vector<Vector3> columns = [&]() {
    std::vector<Vector3> values{state.velocity, state.position};
    for (const int id : contact_ids) {
      values.push_back(state.contacts.at(id));
    }
    return values;
  }();
  for (std::size_t index = 0; index < columns.size(); ++index) {
    const int row = 3 + 3 * static_cast<int>(index);
    result.block<3, 3>(row, 0) = skew(columns[index]) * state.rotation;
    result.block<3, 3>(row, row) = state.rotation;
  }
  return result;
}

HartleyInEkf::HartleyInEkf(StateMean mean, Matrix covariance,
                           ContinuousNoiseDensity noise_density,
                           BackendIdentity identity, Vector3 gravity_world)
    : mean_(std::move(mean)),
      covariance_(std::move(covariance)),
      noise_density_(noise_density),
      identity_(identity),
      gravity_world_(gravity_world) {
  noise_density_.validate();
  diagnostics_.backend_identity = identity_;
  validateStateAndCovariance();
}

std::vector<int> HartleyInEkf::activeContactIdentities() const {
  return sortedContactIds(mean_);
}

int HartleyInEkf::stateDimension() const {
  return 15 + 3 * static_cast<int>(mean_.contacts.size());
}

void HartleyInEkf::validateStateAndCovariance() const {
  if (!mean_.rotation.allFinite() || !mean_.velocity.allFinite() ||
      !mean_.position.allFinite() || !mean_.gyro_bias.allFinite() ||
      !mean_.accelerometer_bias.allFinite() || !gravity_world_.allFinite()) {
    throw std::invalid_argument("Hartley state must be finite");
  }
  for (const auto& contact : mean_.contacts) {
    if (!contact.second.allFinite()) {
      throw std::invalid_argument("Hartley contact state must be finite");
    }
  }
  if (covariance_.rows() != stateDimension() || covariance_.cols() != stateDimension() ||
      !covariance_.allFinite()) {
    throw std::invalid_argument("Hartley covariance dimension or finiteness failed");
  }
  if ((covariance_ - covariance_.transpose()).cwiseAbs().maxCoeff() > 1.0e-10) {
    throw std::invalid_argument("Hartley covariance must be symmetric");
  }
}

StateMean HartleyInEkf::exactMeanStep(
    const StateMean& state, const Vector3& corrected_omega_rad_per_s,
    const Vector3& corrected_acceleration_m_per_s2, double dt_seconds,
    const Vector3& gravity_world) {
  requireNonnegativeDt(dt_seconds);
  const Vector3 phi = corrected_omega_rad_per_s * dt_seconds;
  const Matrix3 G0 = gamma0(phi);
  const Matrix3 G1 = gamma1(phi);
  const Matrix3 G2 = gamma2(phi);
  StateMean result = state;
  result.rotation = state.rotation * G0;
  result.velocity = state.velocity + gravity_world * dt_seconds +
                    state.rotation * G1 * corrected_acceleration_m_per_s2 *
                        dt_seconds;
  result.position = state.position + state.velocity * dt_seconds +
                    0.5 * gravity_world * dt_seconds * dt_seconds +
                    state.rotation * G2 * corrected_acceleration_m_per_s2 *
                        dt_seconds * dt_seconds;
  return result;
}

StateMean HartleyInEkf::officialEarlyMeanStep(
    const StateMean& state, const Vector3& corrected_omega_rad_per_s,
    const Vector3& corrected_acceleration_m_per_s2, double dt_seconds,
    const Vector3& gravity_world) {
  requirePositiveDt(dt_seconds);
  StateMean result = state;
  const Vector3 acceleration_world =
      state.rotation * corrected_acceleration_m_per_s2 + gravity_world;
  result.rotation = state.rotation * expSO3(corrected_omega_rad_per_s * dt_seconds);
  result.velocity = state.velocity + acceleration_world * dt_seconds;
  result.position = state.position + state.velocity * dt_seconds +
                    0.5 * acceleration_world * dt_seconds * dt_seconds;
  return result;
}

Matrix HartleyInEkf::continuousA(const StateMean& state,
                                 const Vector3& gravity_world) {
  const int dimension = 15 + 3 * static_cast<int>(state.contacts.size());
  const int gyro_bias = dimension - 6;
  const int accel_bias = dimension - 3;
  Matrix A = Matrix::Zero(dimension, dimension);
  A.block<3, 3>(0, gyro_bias) = -state.rotation;
  A.block<3, 3>(3, 0) = skew(gravity_world);
  A.block<3, 3>(3, gyro_bias) = -skew(state.velocity) * state.rotation;
  A.block<3, 3>(3, accel_bias) = -state.rotation;
  A.block<3, 3>(6, 3) = Matrix3::Identity();
  A.block<3, 3>(6, gyro_bias) = -skew(state.position) * state.rotation;
  const std::vector<int> ids = sortedContactIds(state);
  for (std::size_t index = 0; index < ids.size(); ++index) {
    A.block<3, 3>(9 + 3 * index, gyro_bias) =
        -skew(state.contacts.at(ids[index])) * state.rotation;
  }
  return A;
}

Matrix HartleyInEkf::continuousL(const StateMean& state) {
  const int contact_count = static_cast<int>(state.contacts.size());
  const int state_dimension = 15 + 3 * contact_count;
  const int noise_dimension = 12 + 3 * contact_count;
  const int noise_bg = 6 + 3 * contact_count;
  const int noise_ba = noise_bg + 3;
  const int state_bg = state_dimension - 6;
  const int state_ba = state_dimension - 3;
  Matrix L = Matrix::Zero(state_dimension, noise_dimension);
  L.block<3, 3>(0, 0) = state.rotation;
  L.block<3, 3>(3, 0) = skew(state.velocity) * state.rotation;
  L.block<3, 3>(3, 3) = state.rotation;
  L.block<3, 3>(6, 0) = skew(state.position) * state.rotation;
  const std::vector<int> ids = sortedContactIds(state);
  for (int index = 0; index < contact_count; ++index) {
    const int row = 9 + 3 * index;
    L.block<3, 3>(row, 0) = skew(state.contacts.at(ids[index])) * state.rotation;
    L.block<3, 3>(row, 6 + 3 * index) = state.rotation;
  }
  L.block<3, 3>(state_bg, noise_bg) = -Matrix3::Identity();
  L.block<3, 3>(state_ba, noise_ba) = -Matrix3::Identity();
  return L;
}

Matrix HartleyInEkf::continuousQc(const StateMean& state,
                                  const ContinuousNoiseDensity& density) {
  const ContinuousNoisePsd psd = continuousPsdFromDensity(density);
  const int contact_count = static_cast<int>(state.contacts.size());
  const int dimension = 12 + 3 * contact_count;
  Matrix Qc = Matrix::Zero(dimension, dimension);
  Qc.block<3, 3>(0, 0) = psd.gyro_measurement_rad2_per_s * Matrix3::Identity();
  Qc.block<3, 3>(3, 3) =
      psd.accelerometer_measurement_m2_per_s3 * Matrix3::Identity();
  for (int index = 0; index < contact_count; ++index) {
    Qc.block<3, 3>(6 + 3 * index, 6 + 3 * index) =
        psd.contact_velocity_m2_per_s * Matrix3::Identity();
  }
  const int bias = 6 + 3 * contact_count;
  Qc.block<3, 3>(bias, bias) = psd.gyro_bias_rw_rad2_per_s3 * Matrix3::Identity();
  Qc.block<3, 3>(bias + 3, bias + 3) =
      psd.accelerometer_bias_rw_m2_per_s5 * Matrix3::Identity();
  return Qc;
}

Matrix HartleyInEkf::analyticalPhi(
    const StateMean& state, const Vector3& corrected_omega_rad_per_s,
    const Vector3& corrected_acceleration_m_per_s2, double dt_seconds,
    const Vector3& gravity_world) {
  requireNonnegativeDt(dt_seconds);
  const int dimension = 15 + 3 * static_cast<int>(state.contacts.size());
  const int gyro_bias = dimension - 6;
  const int accel_bias = dimension - 3;
  const Vector3 phi = corrected_omega_rad_per_s * dt_seconds;
  const Matrix3 G1 = gamma1(phi);
  const Matrix3 G2 = gamma2(phi);
  const Matrix3 P1 = psi1(phi, corrected_acceleration_m_per_s2);
  const Matrix3 P2 = psi2(phi, corrected_acceleration_m_per_s2);
  const StateMean final_state = exactMeanStep(
      state, corrected_omega_rad_per_s, corrected_acceleration_m_per_s2,
      dt_seconds, gravity_world);
  const Matrix3 rotation_bias = -state.rotation * G1 * dt_seconds;

  Matrix Phi = Matrix::Identity(dimension, dimension);
  Phi.block<3, 3>(0, gyro_bias) = rotation_bias;
  Phi.block<3, 3>(3, 0) = skew(gravity_world) * dt_seconds;
  Phi.block<3, 3>(3, gyro_bias) =
      -state.rotation * P1 * dt_seconds * dt_seconds +
      skew(final_state.velocity) * rotation_bias;
  Phi.block<3, 3>(3, accel_bias) = -state.rotation * G1 * dt_seconds;
  Phi.block<3, 3>(6, 0) =
      0.5 * skew(gravity_world) * dt_seconds * dt_seconds;
  Phi.block<3, 3>(6, 3) = Matrix3::Identity() * dt_seconds;
  Phi.block<3, 3>(6, gyro_bias) =
      -state.rotation * P2 * dt_seconds * dt_seconds * dt_seconds +
      skew(final_state.position) * rotation_bias;
  Phi.block<3, 3>(6, accel_bias) =
      -state.rotation * G2 * dt_seconds * dt_seconds;
  const std::vector<int> ids = sortedContactIds(state);
  for (std::size_t index = 0; index < ids.size(); ++index) {
    Phi.block<3, 3>(9 + 3 * index, gyro_bias) =
        skew(state.contacts.at(ids[index])) * rotation_bias;
  }
  return Phi;
}

Matrix HartleyInEkf::analyticalPhiEq60(
    const StateMean& state, const Vector3& corrected_omega_rad_per_s,
    const Vector3& corrected_acceleration_m_per_s2, double dt_seconds,
    const Vector3& gravity_world) {
  requireNonnegativeDt(dt_seconds);
  const std::vector<int> ids = sortedContactIds(state);
  const int group_dimension = 9 + 3 * static_cast<int>(ids.size());
  const int dimension = group_dimension + 6;
  const int gyro_bias = group_dimension;
  const int accel_bias = group_dimension + 3;

  // World-centric left-invariant continuous error matrix from Table 2.
  Matrix left_A = Matrix::Zero(dimension, dimension);
  const Matrix3 omega_skew = skew(corrected_omega_rad_per_s);
  left_A.block<3, 3>(0, 0) = -omega_skew;
  left_A.block<3, 3>(0, gyro_bias) = -Matrix3::Identity();
  left_A.block<3, 3>(3, 0) = -skew(corrected_acceleration_m_per_s2);
  left_A.block<3, 3>(3, 3) = -omega_skew;
  left_A.block<3, 3>(3, accel_bias) = -Matrix3::Identity();
  left_A.block<3, 3>(6, 3) = Matrix3::Identity();
  left_A.block<3, 3>(6, 6) = -omega_skew;
  for (std::size_t index = 0; index < ids.size(); ++index) {
    const int contact = 9 + 3 * static_cast<int>(index);
    left_A.block<3, 3>(contact, contact) = -omega_skew;
  }

  const StateMean final_state = exactMeanStep(
      state, corrected_omega_rad_per_s, corrected_acceleration_m_per_s2,
      dt_seconds, gravity_world);
  GroupState initial_group;
  initial_group.rotation = state.rotation;
  initial_group.velocity = state.velocity;
  initial_group.position = state.position;
  initial_group.contacts = state.contacts;
  GroupState final_group;
  final_group.rotation = final_state.rotation;
  final_group.velocity = final_state.velocity;
  final_group.position = final_state.position;
  final_group.contacts = final_state.contacts;

  Matrix adjoint_final = Matrix::Identity(dimension, dimension);
  Matrix adjoint_initial_inverse = Matrix::Identity(dimension, dimension);
  adjoint_final.topLeftCorner(group_dimension, group_dimension) =
      adjointSEK3(final_group, ids);
  adjoint_initial_inverse.topLeftCorner(group_dimension, group_dimension) =
      adjointSEK3(inverse(initial_group), ids);
  return adjoint_final * (left_A * dt_seconds).exp() *
         adjoint_initial_inverse;
}

Matrix HartleyInEkf::eq61ProcessCovariance(
    const StateMean& state, const Vector3& corrected_omega_rad_per_s,
    const Vector3& corrected_acceleration_m_per_s2, double dt_seconds,
    const Vector3& gravity_world, const ContinuousNoiseDensity& density) {
  requirePositiveDt(dt_seconds);
  const Matrix Phi = analyticalPhi(state, corrected_omega_rad_per_s,
                                   corrected_acceleration_m_per_s2, dt_seconds,
                                   gravity_world);
  const Matrix L = continuousL(state);
  const Matrix Qc = continuousQc(state, density);
  return symmetrized(Phi * L * Qc * L.transpose() * Phi.transpose() * dt_seconds);
}

Matrix HartleyInEkf::eq61MappedQbarPaperTable1(
    const StateMean& state,
    const PaperTable1DiscreteStd& paper_parameters) {
  paper_parameters.validate();
  const int contact_count = static_cast<int>(state.contacts.size());
  const int noise_dimension = 12 + 3 * contact_count;
  Matrix paper_native_statistics = Matrix::Zero(noise_dimension, noise_dimension);
  paper_native_statistics.block<3, 3>(0, 0) =
      std::pow(paper_parameters.angular_velocity_noise_std_rad_per_s, 2) *
      Matrix3::Identity();
  paper_native_statistics.block<3, 3>(3, 3) =
      std::pow(paper_parameters.linear_acceleration_noise_std_m_per_s2, 2) *
      Matrix3::Identity();
  for (int index = 0; index < contact_count; ++index) {
    paper_native_statistics.block<3, 3>(6 + 3 * index, 6 + 3 * index) =
        std::pow(paper_parameters.contact_linear_velocity_noise_std_m_per_s, 2) *
        Matrix3::Identity();
  }
  const int bias = 6 + 3 * contact_count;
  paper_native_statistics.block<3, 3>(bias, bias) =
      std::pow(paper_parameters.gyroscope_bias_random_walk_std_rad_per_s2, 2) *
      Matrix3::Identity();
  paper_native_statistics.block<3, 3>(bias + 3, bias + 3) =
      std::pow(paper_parameters.accelerometer_bias_random_walk_std_m_per_s3, 2) *
      Matrix3::Identity();
  const Matrix L = continuousL(state);
  return symmetrized(L * paper_native_statistics * L.transpose());
}

Matrix HartleyInEkf::eq61MappedQbarGo2ImuPaperContact(
    const StateMean& state, const ContinuousNoiseDensity& go2_imu_density,
    const PaperTable1DiscreteStd& paper_parameters) {
  go2_imu_density.validate();
  paper_parameters.validate();
  if (go2_imu_density.contact_velocity_m_per_s_per_sqrt_hz != 0.0) {
    throw std::invalid_argument(
        "Go2 IMU Eq61 adapter requires contact ASD excluded from ContinuousNoiseDensity");
  }
  Matrix mixed_native_statistics = continuousQc(state, go2_imu_density);
  for (int index = 0; index < static_cast<int>(state.contacts.size()); ++index) {
    mixed_native_statistics.block<3, 3>(6 + 3 * index, 6 + 3 * index) =
        std::pow(paper_parameters.contact_linear_velocity_noise_std_m_per_s, 2) *
        Matrix3::Identity();
  }
  const Matrix L = continuousL(state);
  return symmetrized(L * mixed_native_statistics * L.transpose());
}

Matrix HartleyInEkf::eq61ProcessCovariancePaperTable1(
    const StateMean& state, const Vector3& corrected_omega_rad_per_s,
    const Vector3& corrected_acceleration_m_per_s2, double dt_seconds,
    const Vector3& gravity_world,
    const PaperTable1DiscreteStd& paper_parameters) {
  requirePositiveDt(dt_seconds);
  const Matrix Phi = analyticalPhi(state, corrected_omega_rad_per_s,
                                   corrected_acceleration_m_per_s2, dt_seconds,
                                   gravity_world);
  const Matrix qbar = eq61MappedQbarPaperTable1(state, paper_parameters);
  return symmetrized(Phi * qbar * Phi.transpose() * dt_seconds);
}

Matrix HartleyInEkf::eq61ProcessCovarianceGo2ImuPaperContact(
    const StateMean& state, const Vector3& corrected_omega_rad_per_s,
    const Vector3& corrected_acceleration_m_per_s2, double dt_seconds,
    const Vector3& gravity_world,
    const ContinuousNoiseDensity& go2_imu_density,
    const PaperTable1DiscreteStd& paper_parameters) {
  requirePositiveDt(dt_seconds);
  const Matrix Phi = analyticalPhi(state, corrected_omega_rad_per_s,
                                   corrected_acceleration_m_per_s2, dt_seconds,
                                   gravity_world);
  const Matrix qbar = eq61MappedQbarGo2ImuPaperContact(
      state, go2_imu_density, paper_parameters);
  return symmetrized(Phi * qbar * Phi.transpose() * dt_seconds);
}

Matrix HartleyInEkf::eq52ProcessCovarianceGaussLegendre64(
    const StateMean& state, const Vector3& corrected_omega_rad_per_s,
    const Vector3& corrected_acceleration_m_per_s2, double dt_seconds,
    const Vector3& gravity_world, const ContinuousNoiseDensity& density) {
  requirePositiveDt(dt_seconds);
  const auto quadrature = gaussLegendre64();
  Matrix result = Matrix::Zero(15 + 3 * static_cast<int>(state.contacts.size()),
                               15 + 3 * static_cast<int>(state.contacts.size()));
  for (std::size_t index = 0; index < quadrature.first.size(); ++index) {
    const double tau = 0.5 * dt_seconds * (quadrature.first[index] + 1.0);
    const double remaining = dt_seconds - tau;
    const StateMean state_tau = exactMeanStep(
        state, corrected_omega_rad_per_s, corrected_acceleration_m_per_s2,
        tau, gravity_world);
    // Gauss--Legendre nodes are strictly interior, so remaining is positive.
    // Evaluate the analytical transition continuously at every node; do not
    // introduce a hard identity branch near zero.
    const Matrix transition = analyticalPhi(
        state_tau, corrected_omega_rad_per_s,
        corrected_acceleration_m_per_s2, remaining, gravity_world);
    const Matrix L = continuousL(state_tau);
    const Matrix Qc = continuousQc(state_tau, density);
    result += quadrature.second[index] * transition * L * Qc * L.transpose() *
              transition.transpose();
  }
  result *= 0.5 * dt_seconds;
  return symmetrized(result);
}

void HartleyInEkf::propagate(const Vector3& omega_measurement_rad_per_s,
                             const Vector3& acceleration_measurement_m_per_s2,
                             double dt_seconds) {
  requirePositiveDt(dt_seconds);
  const Vector3 omega = omega_measurement_rad_per_s - mean_.gyro_bias;
  const Vector3 acceleration =
      acceleration_measurement_m_per_s2 - mean_.accelerometer_bias;
  const StateMean initial = mean_;
  diagnostics_.propagation.A = continuousA(initial, gravity_world_);
  diagnostics_.propagation.L = continuousL(initial);
  diagnostics_.propagation.Qc = continuousQc(initial, noise_density_);

  if (identity_ == BackendIdentity::OFFICIAL_CPP_EARLY_REGRESSION) {
    diagnostics_.propagation.Phi =
        Matrix::Identity(stateDimension(), stateDimension()) +
        diagnostics_.propagation.A * dt_seconds;
    const Matrix mapped = diagnostics_.propagation.L * diagnostics_.propagation.Qc *
                          diagnostics_.propagation.L.transpose();
    diagnostics_.propagation.Qd = symmetrized(
        diagnostics_.propagation.Phi * mapped *
        diagnostics_.propagation.Phi.transpose() * dt_seconds);
    mean_ = officialEarlyMeanStep(initial, omega, acceleration, dt_seconds, gravity_world_);
  } else {
    diagnostics_.propagation.Phi =
        analyticalPhi(initial, omega, acceleration, dt_seconds, gravity_world_);
    if (identity_ == BackendIdentity::HARTLEY_IJRR2020_REPORTED_BACKEND) {
      diagnostics_.propagation.Qd = eq61ProcessCovariance(
          initial, omega, acceleration, dt_seconds, gravity_world_, noise_density_);
    } else {
      diagnostics_.propagation.Qd = eq52ProcessCovarianceGaussLegendre64(
          initial, omega, acceleration, dt_seconds, gravity_world_, noise_density_);
    }
    mean_ = exactMeanStep(initial, omega, acceleration, dt_seconds, gravity_world_);
  }
  covariance_ = symmetrized(diagnostics_.propagation.Phi * covariance_ *
                                diagnostics_.propagation.Phi.transpose() +
                            diagnostics_.propagation.Qd);
  validateStateAndCovariance();
}

CorrectionDiagnostics HartleyInEkf::correctContacts(
    const std::vector<ContactMeasurement>& measurements) {
  return correctContactsImpl(measurements, true);
}

CorrectionDiagnostics HartleyInEkf::correctContactSubsetForOfficialEarlyRegression(
    const std::vector<ContactMeasurement>& measurements) {
  if (identity_ != BackendIdentity::OFFICIAL_CPP_EARLY_REGRESSION) {
    throw std::logic_error(
        "subset contact correction is restricted to official early regression");
  }
  return correctContactsImpl(measurements, false);
}

CorrectionDiagnostics HartleyInEkf::correctContactsImpl(
    const std::vector<ContactMeasurement>& measurements,
    bool require_all_active_contacts) {
  if (measurements.empty()) {
    throw std::invalid_argument("contact correction requires at least one measurement");
  }
  const std::vector<int> active_ids = activeContactIdentities();
  std::vector<int> supplied_ids;
  supplied_ids.reserve(measurements.size());
  for (std::size_t index = 0; index < measurements.size(); ++index) {
    if (index > 0 &&
        measurements[index - 1].leg_id >= measurements[index].leg_id) {
      throw std::invalid_argument(
          "contact corrections must use strict stable sorted leg-ID order");
    }
    supplied_ids.push_back(measurements[index].leg_id);
    if (!std::binary_search(active_ids.begin(), active_ids.end(),
                            measurements[index].leg_id)) {
      throw std::invalid_argument("contact correction identity is not active");
    }
    requireCovariance(measurements[index].covariance_body_m2,
                      "contact measurement covariance");
  }
  if (require_all_active_contacts && supplied_ids != active_ids) {
    throw std::invalid_argument(
        "contact correction must stack every active contact exactly once");
  }

  const int rows = 3 * static_cast<int>(measurements.size());
  Matrix H = Matrix::Zero(rows, stateDimension());
  Matrix R = Matrix::Zero(rows, rows);
  Vector innovation = Vector::Zero(rows);
  const std::vector<int>& ids = active_ids;
  for (std::size_t index = 0; index < measurements.size(); ++index) {
    const int row = 3 * static_cast<int>(index);
    H.block<3, 3>(row, 6) = -Matrix3::Identity();
    H.block<3, 3>(row, contactOffset(ids, measurements[index].leg_id)) =
        Matrix3::Identity();
    R.block<3, 3>(row, row) = mean_.rotation * measurements[index].covariance_body_m2 *
                              mean_.rotation.transpose();
    innovation.segment<3>(row) =
        mean_.position + mean_.rotation * measurements[index].foot_position_body -
        mean_.contacts.at(measurements[index].leg_id);
  }
  const Matrix S = symmetrized(H * covariance_ * H.transpose() + R);
  Eigen::LLT<Matrix> factorization(S);
  if (factorization.info() != Eigen::Success) {
    throw std::runtime_error("contact innovation covariance factorization failed");
  }
  const Matrix PHt = covariance_ * H.transpose();
  const Matrix gain = factorization.solve(PHt.transpose()).transpose();
  const Vector solved_innovation = factorization.solve(innovation);
  const Vector delta = gain * innovation;
  applyLeftCorrection(delta);
  const Matrix identity = Matrix::Identity(stateDimension(), stateDimension());
  const Matrix left = identity - gain * H;
  covariance_ = symmetrized(left * covariance_ * left.transpose() +
                            gain * R * gain.transpose());

  diagnostics_.correction = {
      H, R, innovation, S, innovation.dot(solved_innovation), true,
  };
  validateStateAndCovariance();
  return diagnostics_.correction;
}

void HartleyInEkf::applyLeftCorrection(const Vector& delta) {
  if (delta.size() != stateDimension() || !delta.allFinite()) {
    throw std::invalid_argument("invalid Hartley correction vector");
  }
  const std::vector<int> ids = activeContactIdentities();
  const int group_dimension = 9 + 3 * static_cast<int>(ids.size());
  const GroupState correction = expSEK3(delta.head(group_dimension), ids);
  const GroupState current = mean_;
  const GroupState corrected = compose(correction, current);
  mean_.rotation = corrected.rotation;
  mean_.velocity = corrected.velocity;
  mean_.position = corrected.position;
  mean_.contacts = corrected.contacts;
  mean_.gyro_bias += delta.segment<3>(group_dimension);
  mean_.accelerometer_bias += delta.segment<3>(group_dimension + 3);
}

void HartleyInEkf::augmentContacts(
    const std::vector<ContactMeasurement>& measurements) {
  if (measurements.empty()) {
    return;
  }
  std::vector<ContactMeasurement> ordered = measurements;
  std::sort(ordered.begin(), ordered.end(),
            [](const auto& lhs, const auto& rhs) { return lhs.leg_id < rhs.leg_id; });
  for (std::size_t index = 0; index < ordered.size(); ++index) {
    if (mean_.contacts.count(ordered[index].leg_id) != 0 ||
        (index > 0 && ordered[index - 1].leg_id == ordered[index].leg_id)) {
      throw std::invalid_argument("contact augmentation identity already exists");
    }
    requireCovariance(ordered[index].covariance_body_m2,
                      "contact augmentation covariance");
  }

  const std::vector<int> old_ids = activeContactIdentities();
  std::map<int, Vector3> new_contacts = mean_.contacts;
  for (const auto& measurement : ordered) {
    new_contacts.emplace(measurement.leg_id,
                         mean_.position + mean_.rotation * measurement.foot_position_body);
  }
  StateMean new_mean = mean_;
  new_mean.contacts = new_contacts;
  const std::vector<int> new_ids = sortedContactIds(new_mean);
  const int old_dimension = stateDimension();
  const int new_dimension = 15 + 3 * static_cast<int>(new_ids.size());
  Matrix F = Matrix::Zero(new_dimension, old_dimension);
  F.block(0, 0, 9, 9).setIdentity();
  for (const int id : old_ids) {
    F.block<3, 3>(contactOffset(new_ids, id), contactOffset(old_ids, id)) =
        Matrix3::Identity();
  }
  F.block<6, 6>(new_dimension - 6, old_dimension - 6) =
      Eigen::Matrix<double, 6, 6>::Identity();
  Matrix G = Matrix::Zero(new_dimension, 3 * static_cast<int>(ordered.size()));
  Matrix measurement_covariance =
      Matrix::Zero(3 * static_cast<int>(ordered.size()),
                   3 * static_cast<int>(ordered.size()));
  for (std::size_t index = 0; index < ordered.size(); ++index) {
    const int row = contactOffset(new_ids, ordered[index].leg_id);
    F.block<3, 3>(row, 6) = Matrix3::Identity();
    G.block<3, 3>(row, 3 * index) = mean_.rotation;
    measurement_covariance.block<3, 3>(3 * index, 3 * index) =
        ordered[index].covariance_body_m2;
  }
  covariance_ = symmetrized(F * covariance_ * F.transpose() +
                            G * measurement_covariance * G.transpose());
  mean_ = std::move(new_mean);
  validateStateAndCovariance();
}

void HartleyInEkf::removeContacts(const std::vector<int>& leg_ids) {
  if (leg_ids.empty()) {
    return;
  }
  std::set<int> removal(leg_ids.begin(), leg_ids.end());
  if (removal.size() != leg_ids.size()) {
    throw std::invalid_argument("duplicate contact removal identity");
  }
  const std::vector<int> old_ids = activeContactIdentities();
  for (const int id : removal) {
    if (mean_.contacts.count(id) == 0) {
      throw std::invalid_argument("contact removal identity is not active");
    }
  }
  StateMean new_mean = mean_;
  for (const int id : removal) {
    new_mean.contacts.erase(id);
  }
  const std::vector<int> new_ids = sortedContactIds(new_mean);
  const int old_dimension = stateDimension();
  const int new_dimension = 15 + 3 * static_cast<int>(new_ids.size());
  Matrix M = Matrix::Zero(new_dimension, old_dimension);
  M.block(0, 0, 9, 9).setIdentity();
  for (const int id : new_ids) {
    M.block<3, 3>(contactOffset(new_ids, id), contactOffset(old_ids, id)) =
        Matrix3::Identity();
  }
  M.block<6, 6>(new_dimension - 6, old_dimension - 6) =
      Eigen::Matrix<double, 6, 6>::Identity();
  covariance_ = symmetrized(M * covariance_ * M.transpose());
  mean_ = std::move(new_mean);
  validateStateAndCovariance();
}

}  // namespace hartley
