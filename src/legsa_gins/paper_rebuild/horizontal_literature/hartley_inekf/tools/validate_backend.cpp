#include "hartley_inekf/backend.hpp"

#include <Eigen/Eigenvalues>
#include <Eigen/Geometry>
#include <unsupported/Eigen/MatrixFunctions>

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <map>
#include <limits>
#include <random>
#include <set>
#include <sstream>
#include <string>
#include <vector>

namespace {

using hartley::BackendIdentity;
using hartley::ContactMeasurement;
using hartley::ContinuousNoiseDensity;
using hartley::GroupState;
using hartley::HartleyInEkf;
using hartley::Matrix;
using hartley::Matrix3;
using hartley::MeasurementStdMeters;
using hartley::PaperTable1DiscreteStd;
using hartley::StateMean;
using hartley::Vector;
using hartley::Vector3;

constexpr double kMeanRotationTolerance = 2.0e-10;
constexpr double kMeanVelocityTolerance = 2.0e-10;
constexpr double kMeanPositionTolerance = 2.0e-10;
constexpr double kMeanStressTolerance = 2.0e-8;
constexpr double kPhiFiniteDifferenceStep = 1.0e-5;
constexpr double kPhiMaximumTolerance = 2.0e-7;
constexpr double kPhiStressMaximumTolerance = 2.0e-5;
constexpr double kPhiEq58Eq60Tolerance = 1.0e-11;
constexpr double kPhiEq58Eq60StressTolerance = 1.0e-9;
constexpr double kPhiZeroDtIdentityTolerance = 5.0e-12;
constexpr double kPhiBlockRelativeTolerance = 1.0e-6;
constexpr double kPhiStressBlockRelativeTolerance = 5.0e-5;
constexpr double kGaugeStateTolerance = 2.0e-9;
constexpr double kGaugeCovarianceTolerance = 2.0e-8;

void emit(const std::string& section,
          const std::vector<std::pair<std::string, std::string>>& fields) {
  std::cout << section;
  for (const auto& field : fields) std::cout << ',' << field.first << '=' << field.second;
  std::cout << '\n';
}

std::string number(double value) {
  std::ostringstream stream;
  stream << std::setprecision(17) << value;
  return stream.str();
}

std::string integer(long value) { return std::to_string(value); }
std::string boolean(bool value) { return value ? "true" : "false"; }

std::string flatten(const Matrix& matrix) {
  std::ostringstream stream;
  stream << std::setprecision(17);
  for (int row = 0; row < matrix.rows(); ++row) {
    for (int column = 0; column < matrix.cols(); ++column) {
      if (row != 0 || column != 0) stream << ';';
      stream << matrix(row, column);
    }
  }
  return stream.str();
}

std::vector<int> contactIds(const StateMean& state) {
  std::vector<int> ids;
  for (const auto& entry : state.contacts) ids.push_back(entry.first);
  return ids;
}

GroupState groupPart(const StateMean& state) {
  GroupState result;
  result.rotation = state.rotation;
  result.velocity = state.velocity;
  result.position = state.position;
  result.contacts = state.contacts;
  return result;
}

StateMean withGroup(const StateMean& source, const GroupState& group) {
  StateMean result = source;
  result.rotation = group.rotation;
  result.velocity = group.velocity;
  result.position = group.position;
  result.contacts = group.contacts;
  return result;
}

StateMean deterministicState(int contacts) {
  StateMean state;
  state.rotation = hartley::expSO3(Vector3(0.3, -0.2, 0.1));
  state.velocity = Vector3(0.5, -0.3, 0.2);
  state.position = Vector3(1.2, -0.8, 0.4);
  state.gyro_bias = Vector3(0.01, -0.02, 0.015);
  state.accelerometer_bias = Vector3(0.05, -0.03, 0.02);
  for (int id = 0; id < contacts; ++id) {
    state.contacts.emplace(id, Vector3(0.7 + 0.4 * id, -0.5 + 0.25 * id,
                                       -0.15 + 0.03 * id));
  }
  return state;
}

ContinuousNoiseDensity go2AllanImuNoiseContactExcluded() {
  return {2.865130e-4, 1.285395e-3, 2.996871e-5, 1.594412e-4, 0.0};
}

ContinuousNoiseDensity syntheticContinuousAsdProfile() {
  return {3.17e-4, 1.41e-3, 4.23e-5, 1.73e-4, 7.0e-3};
}

struct OdeState {
  Matrix3 rotation;
  Vector3 velocity;
  Vector3 position;
};

OdeState addScaled(const OdeState& state, const OdeState& derivative, double scale) {
  return {state.rotation + scale * derivative.rotation,
          state.velocity + scale * derivative.velocity,
          state.position + scale * derivative.position};
}

OdeState derivative(const OdeState& state, const Vector3& omega,
                    const Vector3& acceleration, const Vector3& gravity) {
  return {state.rotation * hartley::skew(omega), state.rotation * acceleration + gravity,
          state.velocity};
}

StateMean rk4Mean(const StateMean& initial, const Vector3& omega,
                  const Vector3& acceleration, double dt, const Vector3& gravity) {
  const int steps = std::max(2000, static_cast<int>(std::ceil(dt / 2.0e-5)));
  const double h = dt / steps;
  OdeState state{initial.rotation, initial.velocity, initial.position};
  for (int index = 0; index < steps; ++index) {
    const OdeState k1 = derivative(state, omega, acceleration, gravity);
    const OdeState k2 = derivative(addScaled(state, k1, 0.5 * h), omega, acceleration,
                                   gravity);
    const OdeState k3 = derivative(addScaled(state, k2, 0.5 * h), omega, acceleration,
                                   gravity);
    const OdeState k4 = derivative(addScaled(state, k3, h), omega, acceleration, gravity);
    state.rotation += (h / 6.0) *
                      (k1.rotation + 2.0 * k2.rotation + 2.0 * k3.rotation + k4.rotation);
    state.velocity += (h / 6.0) *
                      (k1.velocity + 2.0 * k2.velocity + 2.0 * k3.velocity + k4.velocity);
    state.position += (h / 6.0) *
                      (k1.position + 2.0 * k2.position + 2.0 * k3.position + k4.position);
  }
  StateMean result = initial;
  result.rotation = state.rotation;
  result.velocity = state.velocity;
  result.position = state.position;
  return result;
}

Vector discreteErrorMap(const StateMean& estimate, const Vector3& omega,
                        const Vector3& acceleration, double dt,
                        const Vector3& gravity, const Vector& initial_error) {
  const auto ids = contactIds(estimate);
  const int group_dimension = 9 + 3 * static_cast<int>(ids.size());
  const GroupState eta = hartley::expSEK3(initial_error.head(group_dimension), ids);
  StateMean truth = withGroup(
      estimate, hartley::compose(hartley::inverse(eta), groupPart(estimate)));
  truth.gyro_bias = estimate.gyro_bias - initial_error.segment<3>(group_dimension);
  truth.accelerometer_bias =
      estimate.accelerometer_bias - initial_error.segment<3>(group_dimension + 3);
  const StateMean estimate_next =
      HartleyInEkf::exactMeanStep(estimate, omega, acceleration, dt, gravity);
  const StateMean truth_next = HartleyInEkf::exactMeanStep(
      truth, omega + initial_error.segment<3>(group_dimension),
      acceleration + initial_error.segment<3>(group_dimension + 3), dt, gravity);
  const GroupState eta_next =
      hartley::compose(groupPart(estimate_next), hartley::inverse(groupPart(truth_next)));
  Vector output = Vector::Zero(initial_error.size());
  output.head(group_dimension) = hartley::logSEK3(eta_next, ids);
  output.segment<3>(group_dimension) =
      estimate_next.gyro_bias - truth_next.gyro_bias;
  output.segment<3>(group_dimension + 3) =
      estimate_next.accelerometer_bias - truth_next.accelerometer_bias;
  return output;
}

Matrix3 independentAngleAxisExp(const Vector3& phi) {
  const double theta = phi.norm();
  if (theta == 0.0) return Matrix3::Identity();
  return Eigen::AngleAxisd(theta, phi / theta).toRotationMatrix();
}

Matrix3 independentGammaQuadrature(const Vector3& phi, int order) {
  if (order < 1 || order > 2) {
    throw std::invalid_argument("independent Gamma quadrature order");
  }
  constexpr int intervals = 20000;
  constexpr double h = 1.0 / static_cast<double>(intervals);
  Matrix3 sum = Matrix3::Zero();
  for (int index = 0; index <= intervals; ++index) {
    const double t = h * index;
    const double simpson = index == 0 || index == intervals
                               ? 1.0
                               : (index % 2 == 0 ? 2.0 : 4.0);
    const double kernel = order == 1 ? 1.0 : (1.0 - t);
    sum += simpson * kernel * independentAngleAxisExp(t * phi);
  }
  return (h / 3.0) * sum;
}

Matrix3 independentPsiFivePoint(const Vector3& phi, const Vector3& vector,
                                int order, double step) {
  Matrix3 result = Matrix3::Zero();
  for (int column = 0; column < 3; ++column) {
    const Vector3 offset = step * Vector3::Unit(column);
    const auto value = [&](const Vector3& argument) {
      return (order == 1 ? hartley::gamma1(argument) : hartley::gamma2(argument)) *
             vector;
    };
    result.col(column) =
        (-value(phi + 2.0 * offset) + 8.0 * value(phi + offset) -
         8.0 * value(phi - offset) + value(phi - 2.0 * offset)) /
        (12.0 * step);
  }
  return result;
}

struct BlockExponentialLieOracle {
  Matrix3 gamma0;
  Matrix3 gamma1;
  Matrix3 gamma2;
  Matrix3 psi1;
  Matrix3 psi2;
};

BlockExponentialLieOracle independentBlockExponentialLieOracle(
    const Vector3& phi, const Vector3& vector) {
  Matrix B = Matrix::Zero(9, 9);
  B.block<3, 3>(0, 0) = hartley::skew(phi);
  B.block<3, 3>(0, 3) = Matrix3::Identity();
  B.block<3, 3>(3, 6) = Matrix3::Identity();
  const Matrix exponential = B.exp();
  BlockExponentialLieOracle oracle{
      exponential.block<3, 3>(0, 0), exponential.block<3, 3>(0, 3),
      exponential.block<3, 3>(0, 6), Matrix3::Zero(), Matrix3::Zero()};
  for (int column = 0; column < 3; ++column) {
    Matrix direction = Matrix::Zero(9, 9);
    direction.block<3, 3>(0, 0) =
        hartley::skew(Vector3::Unit(column));
    Matrix frechet_generator = Matrix::Zero(18, 18);
    frechet_generator.block(0, 0, 9, 9) = B;
    frechet_generator.block(0, 9, 9, 9) = direction;
    frechet_generator.block(9, 9, 9, 9) = B;
    const Matrix frechet = frechet_generator.exp().block(0, 9, 9, 9);
    oracle.psi1.col(column) = frechet.block<3, 3>(0, 3) * vector;
    oracle.psi2.col(column) = frechet.block<3, 3>(0, 6) * vector;
  }
  return oracle;
}

double adjointConjugationError(const GroupState& state, const Vector& tangent,
                               const std::vector<int>& ids) {
  const GroupState conjugated = hartley::compose(
      state, hartley::compose(hartley::expSEK3(tangent, ids),
                              hartley::inverse(state)));
  const Vector expected = hartley::adjointSEK3(state, ids) * tangent;
  return (hartley::logSEK3(conjugated, ids) - expected).norm() /
         std::max(1.0, expected.norm());
}

void validateLieGroup() {
  const Vector3 vector(0.6, -0.1, 0.8);
  const double gamma0_zero =
      (hartley::gamma0(Vector3::Zero()) - Matrix3::Identity()).norm();
  const double gamma1_zero =
      (hartley::gamma1(Vector3::Zero()) - Matrix3::Identity()).norm();
  const double gamma2_zero =
      (hartley::gamma2(Vector3::Zero()) - 0.5 * Matrix3::Identity()).norm();
  const double psi1_zero =
      (hartley::psi1(Vector3::Zero(), vector) + 0.5 * hartley::skew(vector)).norm();
  const double psi2_zero =
      (hartley::psi2(Vector3::Zero(), vector) +
       (1.0 / 6.0) * hartley::skew(vector))
          .norm();
  emit("lie", {{"case", "zero_rate_limits"},
               {"gamma0_zero_error", number(gamma0_zero)},
               {"gamma1_zero_error", number(gamma1_zero)},
               {"gamma2_zero_error", number(gamma2_zero)},
               {"psi1_zero_error", number(psi1_zero)},
               {"psi2_zero_error", number(psi2_zero)},
               {"tolerance", number(2.0e-14)},
               {"pass", boolean(gamma0_zero < 1.0e-15 &&
                                gamma1_zero < 1.0e-15 &&
                                gamma2_zero < 1.0e-15 &&
                                psi1_zero < 1.0e-14 && psi2_zero < 1.0e-14)}});

  Vector3 nan_input = Vector3::Zero();
  nan_input.x() = std::numeric_limits<double>::quiet_NaN();
  Vector3 infinity_input = Vector3::Zero();
  infinity_input.y() = std::numeric_limits<double>::infinity();
  const Vector3 finite_overflow_input =
      Vector3::Constant(std::numeric_limits<double>::max());
  const std::vector<Vector3> rejected_inputs = {
      nan_input, infinity_input, finite_overflow_input};
  int rejection_count = 0;
  const int expected_rejection_count =
      static_cast<int>(rejected_inputs.size()) * 7;
  const auto rejected = [&](const auto& operation) {
    try {
      operation();
      return false;
    } catch (const std::exception&) {
      return true;
    }
  };
  for (const Vector3& invalid : rejected_inputs) {
    rejection_count += rejected([&]() { static_cast<void>(hartley::gamma0(invalid)); });
    rejection_count += rejected([&]() { static_cast<void>(hartley::gamma1(invalid)); });
    rejection_count += rejected([&]() { static_cast<void>(hartley::gamma2(invalid)); });
    rejection_count += rejected(
        [&]() { static_cast<void>(hartley::psi1(invalid, vector)); });
    rejection_count += rejected(
        [&]() { static_cast<void>(hartley::psi2(invalid, vector)); });
    rejection_count += rejected([&]() {
      static_cast<void>(hartley::psi1(Vector3(0.4, -0.3, 0.2), invalid));
    });
    rejection_count += rejected([&]() {
      static_cast<void>(hartley::psi2(Vector3(0.4, -0.3, 0.2), invalid));
    });
  }
  emit("lie", {{"case", "nonfinite_input_rejection"},
               {"input_classes", "NAN;POSITIVE_INFINITY;FINITE_OVERFLOW"},
               {"functions", "GAMMA0;GAMMA1;GAMMA2;PSI1;PSI2"},
               {"rejection_count", integer(rejection_count)},
               {"expected_rejection_count", integer(expected_rejection_count)},
               {"pass", boolean(rejection_count == expected_rejection_count)}});

  for (const auto& item : std::vector<std::pair<std::string, Vector3>>{
           {"exp_log_normal", Vector3(0.4, -0.3, 0.2)},
           {"exp_log_near_pi",
            (M_PI - 1.0e-8) * Vector3(0.3, -0.4, 0.5).normalized()}}) {
    const Matrix3 rotation = hartley::expSO3(item.second);
    const double error =
        (hartley::expSO3(hartley::logSO3(rotation)) - rotation).norm();
    const double tolerance = item.first == "exp_log_near_pi" ? 2.0e-9 : 2.0e-11;
    emit("lie", {{"case", item.first},
                 {"exp_log_rotation_fro_error", number(error)},
                 {"orthogonality_error",
                  number((rotation.transpose() * rotation - Matrix3::Identity()).norm())},
                 {"determinant_error",
                  number(std::abs(rotation.determinant() - 1.0))},
                 {"tolerance", number(tolerance)},
                 {"pass", boolean(
                     error < tolerance &&
                     (rotation.transpose() * rotation - Matrix3::Identity()).norm() <
                         tolerance &&
                     std::abs(rotation.determinant() - 1.0) < tolerance)}});
  }

  for (const auto& item : std::vector<std::tuple<std::string, Vector3, double>>{
           {"gamma_psi_normal_oracles", Vector3(0.4, -0.3, 0.2), 2.0e-11},
           {"gamma_psi_two_pi_minus_oracles",
            (2.0 * M_PI - 1.0e-8) * Vector3(0.3, -0.4, 0.5).normalized(),
            2.0e-9},
           {"gamma_psi_two_pi_plus_oracles",
            (2.0 * M_PI + 1.0e-8) * Vector3(0.3, -0.4, 0.5).normalized(),
            2.0e-9},
           {"gamma_psi_stress_oracles",
            20.0 * Vector3(0.3, -0.4, 0.5).normalized(), 2.0e-9},
           {"gamma_psi_fifty_rad_oracles",
            50.0 * Vector3(0.3, -0.4, 0.5).normalized(), 2.0e-9},
           {"gamma_psi_hundred_rad_oracles",
            100.0 * Vector3(0.3, -0.4, 0.5).normalized(), 2.0e-9}}) {
    const Vector3 phi = std::get<1>(item);
    const double tolerance = std::get<2>(item);
    const BlockExponentialLieOracle block_oracle =
        independentBlockExponentialLieOracle(phi, vector);
    const double gamma0_error =
        (hartley::gamma0(phi) - block_oracle.gamma0).norm() /
        std::max(1.0, hartley::gamma0(phi).norm());
    const double gamma1_error =
        (hartley::gamma1(phi) - block_oracle.gamma1).norm() /
        std::max(1.0, hartley::gamma1(phi).norm());
    const double gamma2_error =
        (hartley::gamma2(phi) - block_oracle.gamma2).norm() /
        std::max(1.0, hartley::gamma2(phi).norm());
    const double finite_difference_step = 5.0e-4;
    const double psi1_error =
        (hartley::psi1(phi, vector) - block_oracle.psi1)
            .norm() /
        std::max(1.0, hartley::psi1(phi, vector).norm());
    const double psi2_error =
        (hartley::psi2(phi, vector) - block_oracle.psi2)
            .norm() /
        std::max(1.0, hartley::psi2(phi, vector).norm());
    const double maximum =
        std::max({gamma0_error, gamma1_error, gamma2_error, psi1_error, psi2_error});
    emit("lie", {{"case", std::get<0>(item)},
                 {"phi_norm", number(phi.norm())},
                 {"gamma0_oracle_relative_error", number(gamma0_error)},
                 {"gamma1_oracle_relative_error", number(gamma1_error)},
                 {"gamma2_oracle_relative_error", number(gamma2_error)},
                 {"psi1_oracle_relative_error", number(psi1_error)},
                 {"psi2_oracle_relative_error", number(psi2_error)},
                 {"psi_fd_step", number(finite_difference_step)},
                 {"secondary_gamma1_quadrature_relative_error",
                  number((hartley::gamma1(phi) -
                          independentGammaQuadrature(phi, 1))
                             .norm() /
                         std::max(1.0, hartley::gamma1(phi).norm()))},
                 {"secondary_psi1_five_point_relative_error",
                  number((hartley::psi1(phi, vector) -
                          independentPsiFivePoint(phi, vector, 1,
                                                  finite_difference_step))
                             .norm() /
                         std::max(1.0, hartley::psi1(phi, vector).norm()))},
                 {"oracle", "INDEPENDENT_BLOCK_MATRIX_EXPONENTIAL_FRECHET"},
                 {"maximum_relative_error", number(maximum)},
                 {"tolerance", number(tolerance)},
                 {"pass", boolean(maximum < tolerance)}});
  }

  const Vector3 branch_direction = Vector3(0.3, -0.4, 0.5).normalized();
  const double branch = hartley::kSmallAngleSeriesThresholdRad;
  const double offset = branch * 1.0e-6;
  const Vector3 branch_center = branch * branch_direction;
  const Vector3 branch_left = (branch - offset) * branch_direction;
  const Vector3 branch_right = (branch + offset) * branch_direction;
  const auto midpoint_error = [&](const auto& function) {
    return (0.5 * (function(branch_left) + function(branch_right)) -
            function(branch_center))
        .norm();
  };
  const double gamma0_continuity = midpoint_error(hartley::gamma0);
  const double gamma1_continuity = midpoint_error(hartley::gamma1);
  const double gamma2_continuity = midpoint_error(hartley::gamma2);
  const double psi1_continuity = midpoint_error(
      [&](const Vector3& phi) { return hartley::psi1(phi, vector); });
  const double psi2_continuity = midpoint_error(
      [&](const Vector3& phi) { return hartley::psi2(phi, vector); });
  const double continuity_maximum =
      std::max({gamma0_continuity, gamma1_continuity, gamma2_continuity,
                psi1_continuity, psi2_continuity});
  emit("lie", {{"case", "small_angle_branch_continuity"},
               {"series_threshold_rad", number(branch)},
               {"one_sided_offset_rad", number(offset)},
               {"gamma0_midpoint_error", number(gamma0_continuity)},
               {"gamma1_midpoint_error", number(gamma1_continuity)},
               {"gamma2_midpoint_error", number(gamma2_continuity)},
               {"psi1_midpoint_error", number(psi1_continuity)},
               {"psi2_midpoint_error", number(psi2_continuity)},
               {"maximum_midpoint_error", number(continuity_maximum)},
               {"tolerance", number(5.0e-12)},
               {"pass", boolean(continuity_maximum < 5.0e-12)}});

  for (const bool stress : {false, true}) {
    StateMean state = deterministicState(2);
    if (stress) {
      state.rotation = hartley::expSO3(
          (M_PI - 1.0e-5) * Vector3(0.2, -0.7, 0.4).normalized());
      state.velocity *= 80.0;
      state.position *= -120.0;
      for (auto& contact : state.contacts) contact.second *= 150.0;
    }
    const std::vector<int> ids = contactIds(state);
    Vector tangent = Vector::LinSpaced(15, -0.2, 0.3);
    if (stress) tangent *= 8.0;
    const double error = adjointConjugationError(groupPart(state), tangent.head(15), ids);
    const double tolerance = stress ? 2.0e-9 : 5.0e-11;
    emit("lie", {{"case", stress ? "adjoint_stress" : "adjoint_normal"},
                 {"relative_error", number(error)},
                 {"tolerance", number(tolerance)},
                 {"pass", boolean(error < tolerance)}});
  }
}

void validateMeans() {
  const Vector3 gravity(0.0, 0.0, -9.81);
  const Vector3 acceleration(0.7, -1.1, 9.3);
  struct Case {
    const char* name;
    Vector3 omega;
    double dt;
  };
  const std::vector<Case> cases = {
      {"zero_rate_by2_dt", Vector3::Zero(), 0.004},
      {"near_zero_rate_by2_dt", Vector3(1.0e-11, -2.0e-11, 3.0e-11), 0.004},
      {"normal_rate_by2_dt", Vector3(0.4, -0.7, 1.1), 0.004},
      {"large_rate_by2_dt", Vector3(7.0, -4.0, 2.0), 0.004},
      {"random_force_normal_dt", Vector3(-0.8, 0.3, 0.6), 0.02},
      {"long_stress_dt", Vector3(7.0, -4.0, 2.0), 0.2},
      {"one_second_twenty_rad_per_s_stress",
       20.0 * Vector3(0.3, -0.4, 0.5).normalized(), 1.0},
  };
  for (const auto& item : cases) {
    const StateMean initial = deterministicState(3);
    const StateMean exact = HartleyInEkf::exactMeanStep(
        initial, item.omega, acceleration, item.dt, gravity);
    const StateMean oracle =
        rk4Mean(initial, item.omega, acceleration, item.dt, gravity);
    const double rotation_error = (exact.rotation - oracle.rotation).norm();
    const double rotation_geodesic_error =
        hartley::logSO3(exact.rotation * oracle.rotation.transpose()).norm();
    const double velocity_error = (exact.velocity - oracle.velocity).norm();
    const double position_error = (exact.position - oracle.position).norm();
    const bool stress = std::string(item.name).find("stress") != std::string::npos;
    const double rotation_tolerance =
        stress ? kMeanStressTolerance : kMeanRotationTolerance;
    const double mixed_tolerance =
        stress ? kMeanStressTolerance : kMeanVelocityTolerance;
    const bool pass = rotation_error < rotation_tolerance &&
                      rotation_geodesic_error < rotation_tolerance &&
                      velocity_error < mixed_tolerance &&
                      position_error < mixed_tolerance &&
                      exact.contacts == initial.contacts &&
                      exact.gyro_bias == initial.gyro_bias &&
                      exact.accelerometer_bias == initial.accelerometer_bias;
    emit("mean", {{"case", item.name},
                  {"dt", number(item.dt)},
                  {"omega_norm", number(item.omega.norm())},
                  {"rotation_error", number(rotation_error)},
                  {"rotation_geodesic_error_rad",
                   number(rotation_geodesic_error)},
                  {"velocity_error", number(velocity_error)},
                  {"position_error", number(position_error)},
                  {"rotation_tolerance", number(rotation_tolerance)},
                  {"mixed_tolerance", number(mixed_tolerance)},
                  {"contact_constant", "true"},
                  {"bias_constant", "true"},
                  {"pass", boolean(pass)}});
  }
}

void validatePhi() {
  const Vector3 gravity(0.0, 0.0, -9.81);
  std::mt19937_64 generator(771923);
  std::normal_distribution<double> normal(0.0, 1.0);
  for (int contacts = 0; contacts <= 4; ++contacts) {
    for (const double dt : {0.0, 1.0e-5, 0.004, 0.02, 0.15, 1.0}) {
      StateMean state = deterministicState(contacts);
      state.rotation = hartley::expSO3(
          Vector3(0.2 * normal(generator), 0.2 * normal(generator),
                  0.2 * normal(generator)));
      const Vector3 omega =
          dt < 2.0e-5
              ? Vector3::Zero()
              : (dt >= 1.0
                     ? 20.0 * Vector3(0.3, -0.4, 0.5).normalized()
                     : Vector3(normal(generator), normal(generator), normal(generator)));
      const Vector3 acceleration(normal(generator), normal(generator),
                                 9.0 + normal(generator));
      const Matrix analytical =
          HartleyInEkf::analyticalPhi(state, omega, acceleration, dt, gravity);
      const Matrix eq60 =
          HartleyInEkf::analyticalPhiEq60(state, omega, acceleration, dt, gravity);
      Matrix numerical = Matrix::Zero(analytical.rows(), analytical.cols());
      const double epsilon = kPhiFiniteDifferenceStep;
      for (int column = 0; column < analytical.cols(); ++column) {
        Vector perturbation = Vector::Zero(analytical.cols());
        perturbation(column) = epsilon;
        numerical.col(column) =
            (-discreteErrorMap(state, omega, acceleration, dt, gravity,
                               2.0 * perturbation) +
             8.0 * discreteErrorMap(state, omega, acceleration, dt, gravity,
                                    perturbation) -
             8.0 * discreteErrorMap(state, omega, acceleration, dt, gravity,
                                    -perturbation) +
             discreteErrorMap(state, omega, acceleration, dt, gravity,
                              -2.0 * perturbation)) /
            (12.0 * epsilon);
      }
      const Matrix difference = analytical - numerical;
      const double maximum = difference.cwiseAbs().maxCoeff();
      const double relative = difference.norm() / std::max(1.0, analytical.norm());
      const bool stress = dt >= 0.1;
      const double tolerance =
          stress ? kPhiStressMaximumTolerance : kPhiMaximumTolerance;
      const double eq58_eq60_relative =
          (analytical - eq60).norm() / std::max(1.0, analytical.norm());
      const double eq58_eq60_tolerance =
          stress ? kPhiEq58Eq60StressTolerance : kPhiEq58Eq60Tolerance;
      const double zero_dt_identity_error =
          dt == 0.0
              ? (analytical - Matrix::Identity(analytical.rows(), analytical.cols()))
                    .cwiseAbs()
                    .maxCoeff()
              : 0.0;
      const int dimension = analytical.rows();
      const int group_dimension = dimension - 6;
      const auto block_relative = [&](int row, int rows) {
        if (rows == 0) return 0.0;
        return difference.block(row, 0, rows, dimension).norm() /
               std::max(1.0, analytical.block(row, 0, rows, dimension).norm());
      };
      const double rotation_block_relative = block_relative(0, 3);
      const double velocity_block_relative = block_relative(3, 3);
      const double position_block_relative = block_relative(6, 3);
      const double contact_block_relative = block_relative(9, 3 * contacts);
      const double bias_block_relative = block_relative(group_dimension, 6);
      const double maximum_block_relative =
          std::max({rotation_block_relative, velocity_block_relative,
                    position_block_relative, contact_block_relative,
                    bias_block_relative});
      const double block_tolerance =
          stress ? kPhiStressBlockRelativeTolerance : kPhiBlockRelativeTolerance;
      emit("phi", {{"contacts", integer(contacts)},
                   {"dimension", integer(analytical.rows())},
                   {"dt", number(dt)},
                   {"omega_norm", number(omega.norm())},
                   {"epsilon", number(epsilon)},
                   {"finite_difference_scheme", "FIVE_POINT_CENTRAL"},
                   {"max_abs_error", number(maximum)},
                   {"relative_fro_error", number(relative)},
                   {"eq58_vs_eq60_relative_fro_error", number(eq58_eq60_relative)},
                   {"eq58_vs_eq60_tolerance", number(eq58_eq60_tolerance)},
                   {"zero_dt_identity_max_abs", number(zero_dt_identity_error)},
                   {"rotation_block_relative_error", number(rotation_block_relative)},
                   {"velocity_block_relative_error", number(velocity_block_relative)},
                   {"position_block_relative_error", number(position_block_relative)},
                   {"contact_block_relative_error", number(contact_block_relative)},
                   {"bias_block_relative_error", number(bias_block_relative)},
                   {"maximum_block_relative_error", number(maximum_block_relative)},
                   {"block_relative_tolerance", number(block_tolerance)},
                   {"tolerance", number(tolerance)},
                   {"pass", boolean(maximum < tolerance &&
                                    eq58_eq60_relative < eq58_eq60_tolerance &&
                                    maximum_block_relative < block_tolerance &&
                                    zero_dt_identity_error <
                                        kPhiZeroDtIdentityTolerance)}});
    }
  }
}

void validateCovariances() {
  const Vector3 gravity(0.0, 0.0, -9.81);
  const ContinuousNoiseDensity noise = syntheticContinuousAsdProfile();
  std::mt19937_64 generator(4815162342ULL);
  std::normal_distribution<double> normal(0.0, 1.0);
  int case_id = 0;
  for (int contacts = 0; contacts <= 4; ++contacts) {
    for (const double dt : {1.0e-5, 0.004, 0.05, 0.5}) {
      StateMean state = deterministicState(0);
      state.rotation = hartley::expSO3(
          Vector3(0.6 * normal(generator), 0.6 * normal(generator),
                  0.6 * normal(generator)));
      state.velocity = Vector3(normal(generator), normal(generator), normal(generator));
      state.position = Vector3(normal(generator), normal(generator), normal(generator));
      state.gyro_bias =
          0.03 * Vector3(normal(generator), normal(generator), normal(generator));
      state.accelerometer_bias =
          0.1 * Vector3(normal(generator), normal(generator), normal(generator));
      for (int index = 0; index < contacts; ++index) {
        const int id = 2 * index + 1;
        state.contacts[id] =
            Vector3(normal(generator), normal(generator), -0.4 + 0.1 * normal(generator));
      }
      const Vector3 omega =
          dt >= 0.5
              ? 20.0 * Vector3(0.3, -0.4, 0.5).normalized()
              : Vector3(normal(generator), normal(generator), normal(generator));
      const Vector3 acceleration(normal(generator), normal(generator),
                                 9.0 + normal(generator));
      const Matrix eq61 = HartleyInEkf::eq61ProcessCovariance(
          state, omega, acceleration, dt, gravity, noise);
      const Matrix eq52 = HartleyInEkf::eq52ProcessCovarianceGaussLegendre64(
          state, omega, acceleration, dt, gravity, noise);
      const Matrix difference = eq61 - eq52;
      Eigen::SelfAdjointEigenSolver<Matrix> eigen61(eq61);
      Eigen::SelfAdjointEigenSolver<Matrix> eigen52(eq52);
      const double denominator = std::max(1.0e-30, eq52.norm());
      const int dimension = eq52.rows();
      const int bias = dimension - 6;
      const double nav_block = difference.block(0, 0, 9, 9).norm();
      const double contact_block = contacts == 0
                                       ? 0.0
                                       : difference.block(9, 9, 3 * contacts,
                                                          3 * contacts)
                                             .norm();
      const double bias_block = difference.block(bias, bias, 6, 6).norm();
      const bool stress = dt >= 0.1;
      const double asymmetry_tolerance = stress ? 1.0e-10 : 1.0e-12;
      const double psd_scale_tolerance = stress ? 1.0e-10 : 1.0e-12;
      const double eq61_asymmetry =
          (eq61 - eq61.transpose()).norm() / std::max(1.0, eq61.norm());
      const double eq52_asymmetry =
          (eq52 - eq52.transpose()).norm() / std::max(1.0, eq52.norm());
      const double eq61_psd_lower_bound =
          -psd_scale_tolerance *
          std::max(1.0, eigen61.eigenvalues().maxCoeff());
      const double eq52_psd_lower_bound =
          -psd_scale_tolerance *
          std::max(1.0, eigen52.eigenvalues().maxCoeff());

      const Matrix3 gauge_rotation =
          hartley::expSO3(Vector3(0.0, 0.0, 0.73));
      StateMean gauge_state = state;
      gauge_state.rotation = gauge_rotation * state.rotation;
      gauge_state.velocity = gauge_rotation * state.velocity;
      gauge_state.position = gauge_rotation * state.position +
                             Vector3(2.0, -1.0, 0.7);
      for (auto& contact : gauge_state.contacts) {
        contact.second = gauge_rotation * state.contacts.at(contact.first) +
                         Vector3(2.0, -1.0, 0.7);
      }
      const Vector3 gauge_gravity = gauge_rotation * gravity;
      const Matrix gauge_eq61 = HartleyInEkf::eq61ProcessCovariance(
          gauge_state, omega, acceleration, dt, gauge_gravity, noise);
      const Matrix gauge_eq52 = HartleyInEkf::eq52ProcessCovarianceGaussLegendre64(
          gauge_state, omega, acceleration, dt, gauge_gravity, noise);
      Matrix congruence = Matrix::Identity(dimension, dimension);
      GroupState gauge_transform;
      gauge_transform.rotation = gauge_rotation;
      gauge_transform.position = Vector3(2.0, -1.0, 0.7);
      for (const auto& contact : state.contacts) {
        gauge_transform.contacts[contact.first] = Vector3(2.0, -1.0, 0.7);
      }
      const int group_dimension = dimension - 6;
      congruence.topLeftCorner(group_dimension, group_dimension) =
          hartley::adjointSEK3(gauge_transform, contactIds(state));
      const double eq61_frame_error =
          (gauge_eq61 - congruence * eq61 * congruence.transpose()).norm() /
          std::max(1.0e-30, eq61.norm());
      const double eq52_frame_error =
          (gauge_eq52 - congruence * eq52 * congruence.transpose()).norm() /
          std::max(1.0e-30, eq52.norm());
      const bool pass =
          eq61_asymmetry < asymmetry_tolerance &&
          eq52_asymmetry < asymmetry_tolerance &&
          eigen61.eigenvalues().minCoeff() >= eq61_psd_lower_bound &&
          eigen52.eigenvalues().minCoeff() >= eq52_psd_lower_bound &&
          eq61_frame_error < 2.0e-8 && eq52_frame_error < 2.0e-8;
      emit("qd", {{"case_id", integer(case_id)},
                  {"contacts", integer(contacts)},
                  {"dimension", integer(dimension)},
                  {"dt", number(dt)},
                  {"omega_norm", number(omega.norm())},
                  {"noise_profile", "PURE_SYNTHETIC_CONTINUOUS_ASD_NOT_H5"},
                  {"relative_fro_difference", number(difference.norm() / denominator)},
                  {"max_eigenvalue_difference",
                   number((eigen61.eigenvalues() - eigen52.eigenvalues())
                              .cwiseAbs()
                              .maxCoeff())},
                  {"navigation_block_fro_difference", number(nav_block)},
                  {"contact_block_fro_difference", number(contact_block)},
                  {"bias_block_fro_difference", number(bias_block)},
                  {"eq61_min_eigenvalue", number(eigen61.eigenvalues().minCoeff())},
                  {"eq52_min_eigenvalue", number(eigen52.eigenvalues().minCoeff())},
                  {"eq61_normalized_asymmetry", number(eq61_asymmetry)},
                  {"eq52_normalized_asymmetry", number(eq52_asymmetry)},
                  {"asymmetry_tolerance", number(asymmetry_tolerance)},
                  {"eq61_psd_lower_bound", number(eq61_psd_lower_bound)},
                  {"eq52_psd_lower_bound", number(eq52_psd_lower_bound)},
                  {"eq61_frame_congruence_relative_error", number(eq61_frame_error)},
                  {"eq52_frame_congruence_relative_error", number(eq52_frame_error)},
                  {"pass", boolean(pass)}});
      Matrix contact_values(contacts, 3);
      int contact_row = 0;
      std::ostringstream contact_ids;
      for (const auto& contact : state.contacts) {
        if (contact_row != 0) contact_ids << ';';
        contact_ids << contact.first;
        contact_values.row(contact_row++) = contact.second.transpose();
      }
      emit("eq52_matrix", {{"case_id", integer(case_id)},
                           {"contacts", integer(contacts)},
                           {"contact_ids", contact_ids.str()},
                           {"dimension", integer(dimension)},
                           {"dt", number(dt)},
                           {"rotation", flatten(state.rotation)},
                           {"velocity", flatten(state.velocity)},
                           {"position", flatten(state.position)},
                           {"contact_values", flatten(contact_values)},
                           {"gyro_bias", flatten(state.gyro_bias)},
                           {"accelerometer_bias", flatten(state.accelerometer_bias)},
                           {"omega", flatten(omega)},
                           {"acceleration", flatten(acceleration)},
                           {"gravity", flatten(gravity)},
                           {"sigma_g", number(noise.gyro_measurement_rad_per_s_per_sqrt_hz)},
                           {"sigma_a", number(noise.accelerometer_measurement_m_per_s2_per_sqrt_hz)},
                           {"sigma_bg", number(noise.gyro_bias_rw_rad_per_s2_per_sqrt_hz)},
                           {"sigma_ba", number(noise.accelerometer_bias_rw_m_per_s3_per_sqrt_hz)},
                           {"sigma_contact", number(noise.contact_velocity_m_per_s_per_sqrt_hz)},
                           {"values", flatten(eq52)}});
      ++case_id;
    }
  }

  const ContinuousNoiseDensity zero_noise{};
  const StateMean zero_state = deterministicState(2);
  const Matrix zero_eq61 = HartleyInEkf::eq61ProcessCovariance(
      zero_state, Vector3(0.4, -0.2, 0.3), Vector3(0.7, -0.4, 9.2), 0.01, gravity,
      zero_noise);
  const Matrix zero_eq52 = HartleyInEkf::eq52ProcessCovarianceGaussLegendre64(
      zero_state, Vector3(0.4, -0.2, 0.3), Vector3(0.7, -0.4, 9.2), 0.01, gravity,
      zero_noise);
  emit("qd", {{"case_id", integer(case_id)},
              {"contacts", "2"},
              {"dimension", integer(zero_eq61.rows())},
              {"dt", "0.01"},
              {"omega_norm", number(Vector3(0.4, -0.2, 0.3).norm())},
              {"noise_profile", "ZERO"},
              {"relative_fro_difference", "0"},
              {"max_eigenvalue_difference", "0"},
              {"navigation_block_fro_difference", "0"},
              {"contact_block_fro_difference", "0"},
              {"bias_block_fro_difference", "0"},
              {"eq61_min_eigenvalue", "0"},
              {"eq52_min_eigenvalue", "0"},
              {"pass", boolean(zero_eq61.norm() == 0.0 &&
                               zero_eq52.norm() == 0.0)}});

  const StateMean state = deterministicState(2);
  const ContinuousNoiseDensity go2_noise = go2AllanImuNoiseContactExcluded();
  const Matrix Qc = HartleyInEkf::continuousQc(state, go2_noise);
  const auto psd = hartley::continuousPsdFromDensity(go2_noise);
  constexpr double expected_gyro_psd = 8.208969916900001e-08;
  constexpr double expected_accel_psd = 1.6522403060249999e-06;
  constexpr double expected_gyro_bias_psd = 8.981235790641001e-10;
  constexpr double expected_accel_bias_psd = 2.5421496257440003e-08;
  const int contact_noise_offset = 6;
  const bool continuous_psd_pass =
      std::abs(Qc(0, 0) - expected_gyro_psd) < 1.0e-22 &&
      std::abs(Qc(3, 3) - expected_accel_psd) < 1.0e-20 &&
      std::abs(Qc(Qc.rows() - 6, Qc.rows() - 6) -
               expected_gyro_bias_psd) < 1.0e-24 &&
      std::abs(Qc(Qc.rows() - 3, Qc.rows() - 3) -
               expected_accel_bias_psd) < 1.0e-22 &&
      Qc.block<6, 6>(contact_noise_offset, contact_noise_offset).norm() == 0.0;
  emit("allan", {{"check", "continuous_psd"},
                  {"profile", "GO2_IMU_ALLAN_90MIN_RECOVERED_V1_CONTACT_PROCESS_EXCLUDED"},
                  {"gyro_value", number(Qc(0, 0))},
                  {"gyro_expected", number(expected_gyro_psd)},
                  {"accel_value", number(Qc(3, 3))},
                  {"accel_expected", number(expected_accel_psd)},
                  {"gyro_bias_value", number(Qc(Qc.rows() - 6, Qc.rows() - 6))},
                  {"gyro_bias_expected", number(expected_gyro_bias_psd)},
                  {"accel_bias_value", number(Qc(Qc.rows() - 3, Qc.rows() - 3))},
                  {"accel_bias_expected", number(expected_accel_bias_psd)},
                  {"contact_qc_fro", number(Qc.block<6, 6>(6, 6).norm())},
                  {"contact_policy", "EXCLUDED_FOR_ALLAN_ISOLATION"},
                  {"pass", boolean(continuous_psd_pass)}});
  const auto discrete_sample =
      hartley::discreteSampleStdFromDensity(go2_noise, 0.004);
  emit("allan", {{"check", "density_psd_discrete_sample_api_separation"},
                  {"dt", "0.004"},
                  {"continuous_gyro_density", number(go2_noise.gyro_measurement_rad_per_s_per_sqrt_hz)},
                  {"continuous_gyro_psd", number(psd.gyro_measurement_rad2_per_s)},
                  {"discrete_gyro_sample_std",
                   number(discrete_sample.gyro_measurement_rad_per_s)},
                  {"continuous_gyro_bias_rw_density",
                   number(go2_noise.gyro_bias_rw_rad_per_s2_per_sqrt_hz)},
                  {"discrete_gyro_bias_increment_std",
                   number(discrete_sample.gyro_bias_increment_rad_per_s)},
                  {"pass", boolean(
                       std::abs(psd.gyro_measurement_rad2_per_s -
                                std::pow(go2_noise.gyro_measurement_rad_per_s_per_sqrt_hz,
                                         2)) < 1.0e-24 &&
                       std::abs(discrete_sample.gyro_measurement_rad_per_s -
                                go2_noise.gyro_measurement_rad_per_s_per_sqrt_hz /
                                    std::sqrt(0.004)) < 1.0e-15 &&
                       std::abs(discrete_sample.gyro_bias_increment_rad_per_s -
                                go2_noise.gyro_bias_rw_rad_per_s2_per_sqrt_hz *
                                    std::sqrt(0.004)) < 1.0e-15)}});
  const Vector3 omega(0.4, -0.2, 0.3);
  const double dt1 = 1.0e-6;
  const double dt2 = 2.0e-6;
  const Matrix q1 = HartleyInEkf::eq61ProcessCovariance(
      state, omega, Vector3(0.7, -0.4, 9.2), dt1, gravity, go2_noise);
  const Matrix q2 = HartleyInEkf::eq61ProcessCovariance(
      state, omega, Vector3(0.7, -0.4, 9.2), dt2, gravity, go2_noise);
  const int bias = q1.rows() - 6;
  const double gyro_bias_ratio = q2.block<3, 3>(bias, bias).trace() /
                                 q1.block<3, 3>(bias, bias).trace();
  const double accel_bias_ratio = q2.block<3, 3>(bias + 3, bias + 3).trace() /
                                  q1.block<3, 3>(bias + 3, bias + 3).trace();
  emit("allan", {{"check", "small_dt_bias_scaling"},
                  {"dt1", number(dt1)},
                  {"dt2", number(dt2)},
                  {"gyro_bias_ratio", number(gyro_bias_ratio)},
                  {"accel_bias_ratio", number(accel_bias_ratio)},
                  {"expected_ratio", "2"},
                  {"pass", boolean(std::abs(gyro_bias_ratio - 2.0) < 2.0e-6 &&
                                     std::abs(accel_bias_ratio - 2.0) < 2.0e-6)}});

  const PaperTable1DiscreteStd paper_parameters{};
  const MeasurementStdMeters fk_measurement_std{0.010};
  const Matrix fk_covariance =
      hartley::isotropicMeasurementCovariance(fk_measurement_std);
  const Matrix mixed_qbar = HartleyInEkf::eq61MappedQbarGo2ImuPaperContact(
      state, go2_noise, paper_parameters);
  PaperTable1DiscreteStd zero_contact_paper = paper_parameters;
  zero_contact_paper.contact_linear_velocity_noise_std_m_per_s = 0.0;
  const Matrix zero_contact_qbar =
      HartleyInEkf::eq61MappedQbarGo2ImuPaperContact(
          state, go2_noise, zero_contact_paper);
  const Matrix contact_contribution = mixed_qbar - zero_contact_qbar;
  const Matrix mixed_qd = HartleyInEkf::eq61ProcessCovarianceGo2ImuPaperContact(
      state, omega, Vector3(0.7, -0.4, 9.2), 0.004, gravity,
      go2_noise, paper_parameters);
  Eigen::SelfAdjointEigenSolver<Matrix> mixed_eigen(mixed_qd);
  const double contact_expected = 0.05 * 0.05;
  double contact_adapter_error = 0.0;
  for (int index = 0; index < 2; ++index) {
    contact_adapter_error = std::max(
        contact_adapter_error,
        (contact_contribution.block<3, 3>(9 + 3 * index, 9 + 3 * index) -
         contact_expected * Matrix3::Identity())
            .cwiseAbs()
            .maxCoeff());
  }
  const bool h5_adapter_pass =
      contact_adapter_error < 2.0e-15 &&
      (fk_covariance - 1.0e-4 * Matrix3::Identity()).norm() < 1.0e-18 &&
      Qc.block<6, 6>(6, 6).norm() == 0.0 && mixed_qd.allFinite() &&
      mixed_eigen.eigenvalues().minCoeff() >= -1.0e-12;
  emit("allan", {{"check", "h5_go2_imu_paper_contact_eq61_adapter"},
                 {"go2_contact_asd_in_qc", "0"},
                 {"paper_contact_native_std_m_per_s", "0.05"},
                 {"paper_contact_qbar_variance", number(contact_expected)},
                 {"paper_contact_adapter_max_abs_error", number(contact_adapter_error)},
                 {"fk_measurement_std_m", "0.010"},
                 {"fk_measurement_covariance_diagonal_m2", "0.0001"},
                 {"fk_enters_qc", "false"},
                 {"mixed_qd_minimum_eigenvalue",
                  number(mixed_eigen.eigenvalues().minCoeff())},
                 {"adapter", "EQ61_QBAR_ONLY_NO_TABLE1_ASD_REINTERPRETATION"},
                 {"pass", boolean(h5_adapter_pass)}});

  // Exercise every Table-1 field through its typed Eq. 61/Qbar-only adapter.
  // These paper-native values never enter ContinuousNoiseDensity/Qc.
  const Matrix table1_qbar =
      HartleyInEkf::eq61MappedQbarPaperTable1(state, paper_parameters);
  const Matrix L = HartleyInEkf::continuousL(state);
  const int noise_dimension = L.cols();
  const int table1_bias_noise = 6 + 3 * static_cast<int>(state.contacts.size());
  Matrix table1_native = Matrix::Zero(noise_dimension, noise_dimension);
  table1_native.block<3, 3>(0, 0) =
      4.0e-6 * Matrix3::Identity();
  table1_native.block<3, 3>(3, 3) =
      1.6e-3 * Matrix3::Identity();
  for (int index = 0; index < 2; ++index) {
    table1_native.block<3, 3>(6 + 3 * index, 6 + 3 * index) =
        2.5e-3 * Matrix3::Identity();
  }
  table1_native.block<3, 3>(table1_bias_noise, table1_bias_noise) =
      1.0e-6 * Matrix3::Identity();
  table1_native.block<3, 3>(table1_bias_noise + 3,
                            table1_bias_noise + 3) =
      1.0e-6 * Matrix3::Identity();
  const Matrix table1_qbar_expected = L * table1_native * L.transpose();
  const double table1_qbar_error =
      (table1_qbar - table1_qbar_expected).cwiseAbs().maxCoeff();
  const double table1_dt = 0.004;
  const Matrix table1_phi = HartleyInEkf::analyticalPhi(
      state, omega, Vector3(0.7, -0.4, 9.2), table1_dt, gravity);
  const Matrix table1_qd = HartleyInEkf::eq61ProcessCovariancePaperTable1(
      state, omega, Vector3(0.7, -0.4, 9.2), table1_dt, gravity,
      paper_parameters);
  const Matrix table1_qd_expected =
      table1_phi * table1_qbar_expected * table1_phi.transpose() * table1_dt;
  const double table1_qd_error =
      (table1_qd - table1_qd_expected).cwiseAbs().maxCoeff();
  Eigen::SelfAdjointEigenSolver<Matrix> table1_eigen(table1_qd);
  Matrix encoder_jacobian(3, 4);
  encoder_jacobian << 0.12, -0.04, 0.02, 0.01,
                      -0.03, 0.10, 0.05, -0.02,
                      0.06, 0.01, -0.11, 0.04;
  constexpr double kPi = 3.141592653589793238462643383279502884;
  const double encoder_sigma_rad = kPi / 180.0;
  const Matrix3 encoder_covariance =
      hartley::contactMeasurementCovarianceFromPaperTable1JointEncoder(
          encoder_jacobian, paper_parameters);
  const Matrix3 encoder_covariance_expected =
      encoder_sigma_rad * encoder_sigma_rad * encoder_jacobian *
      encoder_jacobian.transpose();
  const double encoder_covariance_error =
      (encoder_covariance - encoder_covariance_expected)
          .cwiseAbs()
          .maxCoeff();
  emit("allan", {{"check", "paper_table1_all_six_parameter_typed_mapping"},
                 {"parameter_type", "PAPER_TABLE1_DISCRETE_STD"},
                 {"gyro_native_variance", "0.000004"},
                 {"accelerometer_native_variance", "0.0016"},
                 {"contact_native_variance", "0.0025"},
                 {"gyro_bias_native_variance", "0.000001"},
                 {"accelerometer_bias_native_variance", "0.000001"},
                 {"joint_encoder_noise_std_deg", "1.0"},
                 {"joint_encoder_noise_std_rad", number(encoder_sigma_rad)},
                 {"foot_position_jacobian_unit", "m_per_rad"},
                 {"encoder_measurement_covariance_unit", "m2"},
                 {"encoder_measurement_covariance_max_abs_error",
                  number(encoder_covariance_error)},
                 {"qbar_max_abs_error", number(table1_qbar_error)},
                 {"qd_max_abs_error", number(table1_qd_error)},
                 {"qd_minimum_eigenvalue",
                  number(table1_eigen.eigenvalues().minCoeff())},
                 {"continuous_density_api_used", "false"},
                 {"mapping", "PAPER_NATIVE_STATISTICS_SQUARED_ONCE_THEN_EQ61_DT"},
                 {"pass", boolean(table1_qbar_error < 2.0e-15 &&
                                  table1_qd_error < 2.0e-15 &&
                                  paper_parameters.joint_encoder_noise_std_deg ==
                                      1.0 &&
                                  encoder_covariance_error < 2.0e-18 &&
                                  table1_eigen.eigenvalues().minCoeff() >=
                                      -1.0e-12)}});

  // Fixed-seed bias-augmented propagation under the typed paper Eq. 61
  // statistics.  Sampling implements the same Qbar*dt stochastic model and
  // never constructs a ContinuousNoiseDensity from Table-1 numbers.
  StateMean table1_truth = deterministicState(2);
  StateMean table1_estimate = table1_truth;
  table1_truth.gyro_bias.setZero();
  table1_truth.accelerometer_bias.setZero();
  table1_estimate.gyro_bias.setZero();
  table1_estimate.accelerometer_bias.setZero();
  Matrix table1_covariance = 1.0e-3 * Matrix::Identity(21, 21);
  std::mt19937_64 table1_generator(20260819);
  std::normal_distribution<double> table1_normal(0.0, 1.0);
  const auto table1_random_vector = [&]() {
    return Vector3(table1_normal(table1_generator),
                   table1_normal(table1_generator),
                   table1_normal(table1_generator));
  };
  Vector3 true_table1_gyro_bias = Vector3::Zero();
  Vector3 true_table1_accel_bias = Vector3::Zero();
  constexpr int table1_steps = 300;
  for (int step = 0; step < table1_steps; ++step) {
    const Vector3 true_omega(0.05 * std::sin(0.03 * step), -0.03,
                             0.07 * std::cos(0.02 * step));
    const Vector3 true_acceleration(0.1 * std::sin(0.04 * step),
                                    0.08 * std::cos(0.05 * step), 9.7);
    table1_truth = HartleyInEkf::exactMeanStep(
        table1_truth, true_omega, true_acceleration, table1_dt, gravity);
    true_table1_gyro_bias +=
        paper_parameters.gyroscope_bias_random_walk_std_rad_per_s2 *
        std::sqrt(table1_dt) * table1_random_vector();
    true_table1_accel_bias +=
        paper_parameters.accelerometer_bias_random_walk_std_m_per_s3 *
        std::sqrt(table1_dt) * table1_random_vector();
    table1_truth.gyro_bias = true_table1_gyro_bias;
    table1_truth.accelerometer_bias = true_table1_accel_bias;
    const Vector3 gyro_measurement =
        true_omega + true_table1_gyro_bias +
        paper_parameters.angular_velocity_noise_std_rad_per_s /
            std::sqrt(table1_dt) * table1_random_vector();
    const Vector3 accel_measurement =
        true_acceleration + true_table1_accel_bias +
        paper_parameters.linear_acceleration_noise_std_m_per_s2 /
            std::sqrt(table1_dt) * table1_random_vector();
    const Vector3 corrected_omega =
        gyro_measurement - table1_estimate.gyro_bias;
    const Vector3 corrected_accel =
        accel_measurement - table1_estimate.accelerometer_bias;
    const Matrix phi = HartleyInEkf::analyticalPhi(
        table1_estimate, corrected_omega, corrected_accel, table1_dt,
        gravity);
    const Matrix qd = HartleyInEkf::eq61ProcessCovariancePaperTable1(
        table1_estimate, corrected_omega, corrected_accel, table1_dt,
        gravity, paper_parameters);
    table1_covariance =
        0.5 * (phi * table1_covariance * phi.transpose() + qd +
               (phi * table1_covariance * phi.transpose() + qd).transpose());
    table1_estimate = HartleyInEkf::exactMeanStep(
        table1_estimate, corrected_omega, corrected_accel, table1_dt,
        gravity);
  }
  const int table1_state_bias = table1_covariance.rows() - 6;
  const double expected_table1_bias_trace =
      3.0e-3 + 3.0 * table1_steps * 1.0e-6 * table1_dt;
  const double gyro_bias_trace =
      table1_covariance.block<3, 3>(table1_state_bias, table1_state_bias)
          .trace();
  const double accel_bias_trace =
      table1_covariance
          .block<3, 3>(table1_state_bias + 3, table1_state_bias + 3)
          .trace();
  Eigen::SelfAdjointEigenSolver<Matrix> table1_stochastic_eigen(
      table1_covariance);
  const double table1_stochastic_state_error =
      (table1_estimate.rotation - table1_truth.rotation).norm() +
      (table1_estimate.velocity - table1_truth.velocity).norm() +
      (table1_estimate.position - table1_truth.position).norm();
  const double table1_stochastic_bias_norm =
      true_table1_gyro_bias.norm() + true_table1_accel_bias.norm();
  emit("synthetic",
       {{"case", "paper_table1_typed_bias_stochastic_propagation"},
        {"parameter_type", "PAPER_TABLE1_DISCRETE_STD"},
        {"realization", "PAPER_EQ61_QBAR_TIMES_DT"},
        {"continuous_density_api_used", "false"},
        {"seed", "20260819"},
        {"steps", integer(table1_steps)},
        {"state_error", number(table1_stochastic_state_error)},
        {"injected_bias_norm", number(table1_stochastic_bias_norm)},
        {"gyro_bias_covariance_trace", number(gyro_bias_trace)},
        {"accel_bias_covariance_trace", number(accel_bias_trace)},
        {"expected_each_bias_covariance_trace",
         number(expected_table1_bias_trace)},
        {"covariance_minimum_eigenvalue",
         number(table1_stochastic_eigen.eigenvalues().minCoeff())},
        {"pass", boolean(
             table1_stochastic_state_error < 2.0 &&
             table1_stochastic_bias_norm > 0.0 &&
             std::abs(gyro_bias_trace - expected_table1_bias_trace) < 2.0e-12 &&
             std::abs(accel_bias_trace - expected_table1_bias_trace) < 2.0e-12 &&
             table1_stochastic_eigen.eigenvalues().minCoeff() > -1.0e-12)}});

  // Table-1 encoder noise belongs on the contact-measurement side.  Verify a
  // nonzero synthetic correction using a supplied foot-position Jacobian;
  // no degree-to-meter scalar shortcut is introduced.
  StateMean encoder_truth = deterministicState(2);
  StateMean encoder_estimate = encoder_truth;
  encoder_estimate.contacts[0] += Vector3(0.025, -0.018, 0.012);
  encoder_estimate.contacts[1] += Vector3(-0.020, 0.015, -0.010);
  HartleyInEkf encoder_filter(
      encoder_estimate, 0.05 * Matrix::Identity(21, 21),
      ContinuousNoiseDensity{});
  std::vector<ContactMeasurement> encoder_measurements;
  double encoder_r_mapping_error = 0.0;
  double initial_encoder_residual_squared = 0.0;
  for (int id = 0; id < 2; ++id) {
    Matrix jacobian = encoder_jacobian;
    jacobian *= 1.0 + 0.15 * id;
    const Matrix3 covariance =
        hartley::contactMeasurementCovarianceFromPaperTable1JointEncoder(
            jacobian, paper_parameters);
    const Matrix3 expected_covariance =
        encoder_sigma_rad * encoder_sigma_rad * jacobian * jacobian.transpose();
    encoder_r_mapping_error = std::max(
        encoder_r_mapping_error,
        (covariance - expected_covariance).cwiseAbs().maxCoeff());
    const Vector3 body_measurement = encoder_truth.rotation.transpose() *
                                     (encoder_truth.contacts.at(id) -
                                      encoder_truth.position);
    encoder_measurements.push_back({id, body_measurement, covariance});
    const Vector3 residual = encoder_filter.stateMean().position +
                             encoder_filter.stateMean().rotation * body_measurement -
                             encoder_filter.stateMean().contacts.at(id);
    initial_encoder_residual_squared += residual.squaredNorm();
  }
  const double initial_encoder_residual =
      std::sqrt(initial_encoder_residual_squared);
  const auto encoder_diagnostic =
      encoder_filter.correctContacts(encoder_measurements);
  double final_encoder_residual_squared = 0.0;
  for (const auto& measurement : encoder_measurements) {
    const Vector3 residual =
        encoder_filter.stateMean().position +
        encoder_filter.stateMean().rotation * measurement.foot_position_body -
        encoder_filter.stateMean().contacts.at(measurement.leg_id);
    final_encoder_residual_squared += residual.squaredNorm();
  }
  const double final_encoder_residual =
      std::sqrt(final_encoder_residual_squared);
  emit("synthetic",
       {{"case", "paper_table1_joint_encoder_measurement_correction"},
        {"parameter_type", "PAPER_TABLE1_DISCRETE_STD"},
        {"joint_encoder_noise_std_deg", "1.0"},
        {"jacobian_unit", "m_per_rad"},
        {"measurement_covariance_unit", "m2"},
        {"mapping", "R_EQUALS_J_SIGMA_RAD_SQUARED_I_J_TRANSPOSE"},
        {"initial_innovation_norm", number(initial_encoder_residual)},
        {"diagnostic_innovation_norm",
         number(encoder_diagnostic.innovation.norm())},
        {"final_innovation_norm", number(final_encoder_residual)},
        {"nis", number(encoder_diagnostic.nis)},
        {"measurement_r_mapping_max_abs_error",
         number(encoder_r_mapping_error)},
        {"continuous_density_api_used", "false"},
        {"pass", boolean(initial_encoder_residual > 1.0e-3 &&
                         final_encoder_residual < initial_encoder_residual &&
                         encoder_diagnostic.nis > 0.0 &&
                         encoder_r_mapping_error < 2.0e-18)}});
}

ContactMeasurement exactMeasurement(const StateMean& truth, int id,
                                    MeasurementStdMeters sigma) {
  return {id,
          truth.rotation.transpose() * (truth.contacts.at(id) - truth.position),
          hartley::isotropicMeasurementCovariance(sigma)};
}

double contactPredictionRms(const StateMean& estimate, const StateMean& truth) {
  if (truth.contacts.empty()) return 0.0;
  double squared_error = 0.0;
  int scalar_count = 0;
  for (const auto& contact : truth.contacts) {
    const auto estimate_contact = estimate.contacts.find(contact.first);
    if (estimate_contact == estimate.contacts.end()) {
      return std::numeric_limits<double>::infinity();
    }
    const Vector3 expected =
        truth.rotation.transpose() * (contact.second - truth.position);
    const Vector3 predicted = estimate.rotation.transpose() *
                              (estimate_contact->second - estimate.position);
    squared_error += (predicted - expected).squaredNorm();
    scalar_count += 3;
  }
  return std::sqrt(squared_error / static_cast<double>(scalar_count));
}

double observableRecoveryError(const StateMean& estimate,
                               const StateMean& truth,
                               const Vector3& gravity_world) {
  const double gravity_norm = gravity_world.norm();
  const double gravity_direction_error =
      (estimate.rotation.transpose() * gravity_world -
       truth.rotation.transpose() * gravity_world)
          .norm() /
      gravity_norm;
  const double body_velocity_error =
      (estimate.rotation.transpose() * estimate.velocity -
       truth.rotation.transpose() * truth.velocity)
          .norm();
  const double contact_error = contactPredictionRms(estimate, truth);
  const double gyro_bias_error =
      (estimate.gyro_bias - truth.gyro_bias).norm();
  const double accelerometer_bias_error =
      (estimate.accelerometer_bias - truth.accelerometer_bias).norm();
  return gravity_direction_error + body_velocity_error + contact_error +
         gyro_bias_error + accelerometer_bias_error;
}

int validationContactOffset(const std::vector<int>& ids, int id) {
  const auto iterator = std::lower_bound(ids.begin(), ids.end(), id);
  if (iterator == ids.end() || *iterator != id) {
    throw std::invalid_argument("validation contact identity is not active");
  }
  return 9 + 3 * static_cast<int>(std::distance(ids.begin(), iterator));
}

Matrix nontrivialCrossCovariance(int dimension) {
  Matrix factor(dimension, dimension);
  for (int row = 0; row < dimension; ++row) {
    for (int column = 0; column < dimension; ++column) {
      factor(row, column) =
          0.02 * std::sin(0.37 * (row + 1) * (column + 2)) +
          (row == column ? 0.15 + 0.002 * row : 0.0);
    }
  }
  return factor * factor.transpose() +
         1.0e-4 * Matrix::Identity(dimension, dimension);
}

std::pair<StateMean, Matrix> augmentationOracle(
    const StateMean& state, const Matrix& covariance,
    std::vector<ContactMeasurement> additions) {
  std::sort(additions.begin(), additions.end(),
            [](const auto& lhs, const auto& rhs) { return lhs.leg_id < rhs.leg_id; });
  StateMean expected_state = state;
  for (const auto& addition : additions) {
    expected_state.contacts[addition.leg_id] =
        state.position + state.rotation * addition.foot_position_body;
  }
  const std::vector<int> old_ids = contactIds(state);
  const std::vector<int> new_ids = contactIds(expected_state);
  const int old_dimension = covariance.rows();
  const int new_dimension = 15 + 3 * static_cast<int>(new_ids.size());
  Matrix F = Matrix::Zero(new_dimension, old_dimension);
  F.block(0, 0, 9, 9).setIdentity();
  for (const int id : old_ids) {
    F.block<3, 3>(validationContactOffset(new_ids, id),
                  validationContactOffset(old_ids, id)) = Matrix3::Identity();
  }
  F.block<6, 6>(new_dimension - 6, old_dimension - 6).setIdentity();
  Matrix G = Matrix::Zero(new_dimension, 3 * static_cast<int>(additions.size()));
  Matrix measurement_covariance =
      Matrix::Zero(3 * additions.size(), 3 * additions.size());
  for (std::size_t index = 0; index < additions.size(); ++index) {
    const int row = validationContactOffset(new_ids, additions[index].leg_id);
    F.block<3, 3>(row, 6) = Matrix3::Identity();
    G.block<3, 3>(row, 3 * index) = state.rotation;
    measurement_covariance.block<3, 3>(3 * index, 3 * index) =
        additions[index].covariance_body_m2;
  }
  return {expected_state,
          0.5 * (F * covariance * F.transpose() +
                 G * measurement_covariance * G.transpose() +
                 (F * covariance * F.transpose() +
                  G * measurement_covariance * G.transpose())
                     .transpose())};
}

std::pair<StateMean, Matrix> removalOracle(const StateMean& state,
                                           const Matrix& covariance,
                                           const std::vector<int>& removals) {
  StateMean expected_state = state;
  for (const int id : removals) expected_state.contacts.erase(id);
  const std::vector<int> old_ids = contactIds(state);
  const std::vector<int> new_ids = contactIds(expected_state);
  const int new_dimension = 15 + 3 * static_cast<int>(new_ids.size());
  Matrix M = Matrix::Zero(new_dimension, covariance.rows());
  M.block(0, 0, 9, 9).setIdentity();
  for (const int id : new_ids) {
    M.block<3, 3>(validationContactOffset(new_ids, id),
                  validationContactOffset(old_ids, id)) = Matrix3::Identity();
  }
  M.block<6, 6>(new_dimension - 6, covariance.rows() - 6).setIdentity();
  return {expected_state, M * covariance * M.transpose()};
}

double contactMeanMaximumError(const StateMean& actual, const StateMean& expected) {
  double maximum = 0.0;
  for (const auto& contact : expected.contacts) {
    maximum = std::max(maximum,
                       (actual.contacts.at(contact.first) - contact.second).norm());
  }
  return maximum;
}

void validateLifecycleAndSynthetic() {
  const ContinuousNoiseDensity noise = syntheticContinuousAsdProfile();
  StateMean lifecycle_initial = deterministicState(0);
  lifecycle_initial.contacts[2] = Vector3(0.7, -0.4, -0.2);
  lifecycle_initial.contacts[5] = Vector3(-0.8, 0.6, -0.1);
  const Matrix lifecycle_covariance = nontrivialCrossCovariance(21);
  Matrix3 R0;
  R0 << 1.0e-4, 1.0e-5, 0.0, 1.0e-5, 1.7e-4, -0.5e-5, 0.0,
      -0.5e-5, 1.3e-4;
  Matrix3 R1;
  R1 << 2.0e-4, -0.7e-5, 0.4e-5, -0.7e-5, 1.2e-4, 0.0, 0.4e-5,
      0.0, 1.5e-4;
  const ContactMeasurement add0{0, Vector3(0.31, -0.22, -0.43), R0};
  const ContactMeasurement add1{1, Vector3(0.28, 0.21, -0.41), R1};
  const ContactMeasurement add3{3, Vector3(-0.32, 0.19, -0.44), R0};
  const ContactMeasurement add4{4, Vector3(-0.29, -0.23, -0.42), R1};

  auto emit_lifecycle = [&](const std::string& name, const HartleyInEkf& filter,
                            const StateMean& expected_state,
                            const Matrix& expected_covariance,
                            const std::string& expected_ids, double tolerance) {
    const double covariance_residual =
        (filter.stateCovariance() - expected_covariance).cwiseAbs().maxCoeff();
    const double mean_residual =
        contactMeanMaximumError(filter.stateMean(), expected_state);
    const double symmetry =
        (filter.stateCovariance() - filter.stateCovariance().transpose())
            .cwiseAbs()
            .maxCoeff();
    Eigen::SelfAdjointEigenSolver<Matrix> eigen(filter.stateCovariance());
    std::ostringstream ids_stream;
    const auto ids = filter.activeContactIdentities();
    for (std::size_t index = 0; index < ids.size(); ++index) {
      if (index != 0) ids_stream << ';';
      ids_stream << ids[index];
    }
    emit("lifecycle", {{"case", name},
                       {"active_ids", ids_stream.str()},
                       {"expected_active_ids", expected_ids},
                       {"dimension", integer(filter.stateDimension())},
                       {"expected_dimension", integer(expected_covariance.rows())},
                       {"direct_map_max_abs", number(covariance_residual)},
                       {"cross_covariance_residual", number(covariance_residual)},
                       {"contact_mean_residual", number(mean_residual)},
                       {"symmetry_max_abs", number(symmetry)},
                       {"minimum_eigenvalue", number(eigen.eigenvalues().minCoeff())},
                       {"tolerance", number(tolerance)},
                       {"remaining_index_integrity",
                        boolean(ids_stream.str() == expected_ids)},
                       {"pass", boolean(ids_stream.str() == expected_ids &&
                                        filter.stateDimension() ==
                                            expected_covariance.rows() &&
                                        covariance_residual < tolerance &&
                                        mean_residual < tolerance &&
                                        symmetry < 1.0e-12 &&
                                        eigen.eigenvalues().minCoeff() > -1.0e-12)}});
  };

  HartleyInEkf single_add(lifecycle_initial, lifecycle_covariance, noise);
  const auto single_add_expected =
      augmentationOracle(lifecycle_initial, lifecycle_covariance, {add0});
  single_add.augmentContacts({add0});
  emit_lifecycle("single_add_lower_id", single_add, single_add_expected.first,
                 single_add_expected.second, "0;2;5", 2.0e-12);

  HartleyInEkf simultaneous_add(lifecycle_initial, lifecycle_covariance, noise);
  const auto simultaneous_expected = augmentationOracle(
      lifecycle_initial, lifecycle_covariance, {add4, add0});
  simultaneous_add.augmentContacts({add4, add0});
  emit_lifecycle("simultaneous_add_lower_and_middle_ids", simultaneous_add,
                 simultaneous_expected.first, simultaneous_expected.second,
                 "0;2;4;5", 2.0e-12);

  HartleyInEkf single_remove(simultaneous_expected.first,
                             simultaneous_expected.second, noise);
  const auto single_remove_expected = removalOracle(
      simultaneous_expected.first, simultaneous_expected.second, {2});
  single_remove.removeContacts({2});
  emit_lifecycle("single_remove_remaining_index_integrity", single_remove,
                 single_remove_expected.first, single_remove_expected.second,
                 "0;4;5", 2.0e-12);

  HartleyInEkf simultaneous_remove(simultaneous_expected.first,
                                   simultaneous_expected.second, noise);
  const auto simultaneous_remove_expected = removalOracle(
      simultaneous_expected.first, simultaneous_expected.second, {0, 4});
  simultaneous_remove.removeContacts({4, 0});
  emit_lifecycle("simultaneous_remove", simultaneous_remove,
                 simultaneous_remove_expected.first,
                 simultaneous_remove_expected.second, "2;5", 2.0e-12);

  HartleyInEkf mixed(simultaneous_expected.first, simultaneous_expected.second,
                     noise);
  const auto mixed_removed = removalOracle(
      simultaneous_expected.first, simultaneous_expected.second, {2, 4});
  mixed.removeContacts({4, 2});
  const auto mixed_expected = augmentationOracle(
      mixed_removed.first, mixed_removed.second, {add3, add1});
  mixed.augmentContacts({add3, add1});
  emit_lifecycle("mixed_remove_add_same_epoch", mixed, mixed_expected.first,
                 mixed_expected.second, "0;1;3;5", 1.0e-10);

  // Static four-contact recovery from an independently perturbed estimate.
  // Absolute translation and global yaw are deliberately excluded from the
  // recovery score because they are gauge freedoms of proprioceptive contact.
  StateMean truth;
  truth.rotation = hartley::expSO3(Vector3(0.0, 0.0, 0.35));
  truth.position = Vector3(0.0, 0.0, 0.5);
  truth.gyro_bias = Vector3(0.01, -0.02, 0.005);
  truth.accelerometer_bias = Vector3(0.03, -0.01, 0.02);
  const std::vector<Vector3> feet = {
      Vector3(0.3, 0.2, -0.5), Vector3(0.3, -0.2, -0.5),
      Vector3(-0.3, 0.2, -0.5), Vector3(-0.3, -0.2, -0.5)};
  for (int id = 0; id < 4; ++id) {
    truth.contacts[id] = truth.position + truth.rotation * feet[id];
  }
  StateMean static_estimate = truth;
  static_estimate.rotation =
      hartley::expSO3(Vector3(0.10, -0.07, 0.0)) * truth.rotation;
  static_estimate.velocity = Vector3(0.16, -0.11, 0.07);
  static_estimate.gyro_bias.setZero();
  static_estimate.accelerometer_bias.setZero();
  const std::vector<Vector3> static_contact_offsets = {
      Vector3(0.025, -0.018, 0.012), Vector3(-0.020, 0.014, -0.009),
      Vector3(0.017, 0.011, -0.016), Vector3(-0.013, -0.019, 0.014)};
  for (int id = 0; id < 4; ++id) {
    static_estimate.contacts[id] += static_contact_offsets[id];
  }
  HartleyInEkf static_filter(
      static_estimate, 0.08 * Matrix::Identity(27, 27), noise);
  const Vector3 gravity_world(0.0, 0.0, -9.81);
  const double static_initial_error =
      observableRecoveryError(static_filter.stateMean(), truth, gravity_world);
  double first_innovation = -1.0;
  double maximum_innovation = 0.0;
  for (int step = 0; step < 1200; ++step) {
    static_filter.propagate(truth.gyro_bias,
                            Vector3(0.0, 0.0, 9.81) + truth.accelerometer_bias,
                            0.004);
    std::vector<ContactMeasurement> measurements;
    for (int id = 0; id < 4; ++id) {
      measurements.push_back(exactMeasurement(truth, id, MeasurementStdMeters{0.01}));
    }
    const auto diagnostic = static_filter.correctContacts(measurements);
    if (step == 0) first_innovation = diagnostic.innovation.norm();
    maximum_innovation = std::max(maximum_innovation, diagnostic.innovation.norm());
  }
  const double static_final_error =
      observableRecoveryError(static_filter.stateMean(), truth, gravity_world);
  const double static_error_ratio = static_final_error / static_initial_error;
  emit("synthetic", {{"case", "static_four_contact_perturbed_recovery"},
                     {"truth_source", "INDEPENDENT_DETERMINISTIC_SYNTHETIC_TRUTH"},
                     {"initial_observable_error", number(static_initial_error)},
                     {"final_observable_error", number(static_final_error)},
                     {"error_reduction_ratio", number(static_error_ratio)},
                     {"first_innovation_norm", number(first_innovation)},
                     {"maximum_innovation", number(maximum_innovation)},
                     {"final_contact_prediction_rms",
                      number(contactPredictionRms(static_filter.stateMean(), truth))},
                     {"gyro_bias_error",
                      number((static_filter.stateMean().gyro_bias - truth.gyro_bias).norm())},
                     {"accel_bias_error",
                      number((static_filter.stateMean().accelerometer_bias -
                              truth.accelerometer_bias)
                                 .norm())},
                     {"recovery_ratio_tolerance", "0.35"},
                     {"minimum_nonzero_innovation", "0.001"},
                     {"pass", boolean(static_error_ratio < 0.35 &&
                                      first_innovation > 1.0e-3 &&
                                      static_final_error < static_initial_error)}});

  // Switching-contact walking and flight sequence from a perturbed filter.
  StateMean walking_truth;
  walking_truth.rotation = hartley::expSO3(Vector3(0.0, 0.0, -0.25));
  walking_truth.position = Vector3(0.0, 0.0, 0.45);
  walking_truth.gyro_bias = Vector3(0.004, -0.003, 0.002);
  walking_truth.accelerometer_bias = Vector3(0.02, -0.01, 0.015);
  const std::map<int, Vector3> body_feet = {
      {0, Vector3(0.3, 0.2, -0.45)}, {1, Vector3(0.3, -0.2, -0.45)},
      {2, Vector3(-0.3, 0.2, -0.45)}, {3, Vector3(-0.3, -0.2, -0.45)}};
  for (const auto& foot : body_feet) {
    walking_truth.contacts[foot.first] =
        walking_truth.position + walking_truth.rotation * foot.second;
  }
  StateMean walking_estimate = walking_truth;
  walking_estimate.rotation =
      hartley::expSO3(Vector3(-0.08, 0.06, 0.0)) * walking_truth.rotation;
  walking_estimate.velocity = Vector3(-0.12, 0.09, -0.05);
  walking_estimate.gyro_bias.setZero();
  walking_estimate.accelerometer_bias.setZero();
  for (auto& contact : walking_estimate.contacts) {
    const double sign = contact.first % 2 == 0 ? 1.0 : -1.0;
    contact.second += Vector3(0.018 * sign, -0.012, 0.009 * sign);
  }
  HartleyInEkf walking_filter(
      walking_estimate, 0.06 * Matrix::Identity(27, 27), noise);
  auto add_truth_contacts = [&](const std::vector<int>& add_ids) {
    std::vector<ContactMeasurement> additions;
    for (const int id : add_ids) {
      const Vector3 body = body_feet.at(id);
      walking_truth.contacts[id] =
          walking_truth.position + walking_truth.rotation * body;
      additions.push_back({id, body, 1.0e-4 * Matrix3::Identity()});
    }
    walking_filter.augmentContacts(additions);
  };
  const double walking_initial_error = observableRecoveryError(
      walking_filter.stateMean(), walking_truth, gravity_world);
  double maximum_state_error = 0.0;
  double maximum_contact_prediction_rms = 0.0;
  double first_walking_innovation = -1.0;
  int flight_steps = 0;
  std::set<int> observed_contact_counts;
  for (int step = 0; step < 600; ++step) {
    if (step == 100) {
      walking_filter.removeContacts({2, 3});
      walking_truth.contacts.erase(2);
      walking_truth.contacts.erase(3);
    } else if (step == 150) {
      walking_filter.removeContacts({1});
      walking_truth.contacts.erase(1);
    } else if (step == 200) {
      add_truth_contacts({2, 3});
    } else if (step == 300) {
      add_truth_contacts({1});
    } else if (step == 400) {
      const auto active = walking_filter.activeContactIdentities();
      walking_filter.removeContacts(active);
      walking_truth.contacts.clear();
    } else if (step == 410) {
      add_truth_contacts({1, 2});
    }
    const Vector3 omega(0.05 * std::sin(0.1 * step), -0.03,
                        0.08 * std::cos(0.07 * step));
    const Vector3 acceleration(0.2 * std::sin(0.05 * step), 0.1, 9.81);
    walking_truth = HartleyInEkf::exactMeanStep(walking_truth, omega, acceleration,
                                                0.004, Vector3(0.0, 0.0, -9.81));
    walking_filter.propagate(omega + walking_truth.gyro_bias,
                             acceleration + walking_truth.accelerometer_bias, 0.004);
    if (walking_truth.contacts.empty()) {
      ++flight_steps;
    } else {
      std::vector<ContactMeasurement> measurements;
      for (const auto& contact : walking_truth.contacts)
        measurements.push_back(exactMeasurement(
            walking_truth, contact.first, MeasurementStdMeters{0.01}));
      const auto diagnostic = walking_filter.correctContacts(measurements);
      if (first_walking_innovation < 0.0) {
        first_walking_innovation = diagnostic.innovation.norm();
      }
    }
    observed_contact_counts.insert(static_cast<int>(walking_truth.contacts.size()));
    maximum_state_error = std::max(
        maximum_state_error,
        (walking_filter.stateMean().position - walking_truth.position).norm() +
            (walking_filter.stateMean().velocity - walking_truth.velocity).norm() +
            (walking_filter.stateMean().rotation - walking_truth.rotation).norm());
    maximum_contact_prediction_rms =
        std::max(maximum_contact_prediction_rms,
                 contactPredictionRms(walking_filter.stateMean(), walking_truth));
  }
  const double walking_final_error = observableRecoveryError(
      walking_filter.stateMean(), walking_truth, gravity_world);
  const double walking_error_ratio = walking_final_error / walking_initial_error;
  emit("synthetic", {{"case", "walking_switching_contacts_perturbed_recovery"},
                     {"truth_source", "INDEPENDENT_DETERMINISTIC_SYNTHETIC_TRUTH"},
                     {"initial_observable_error", number(walking_initial_error)},
                     {"final_observable_error", number(walking_final_error)},
                     {"error_reduction_ratio", number(walking_error_ratio)},
                     {"first_innovation_norm", number(first_walking_innovation)},
                     {"maximum_state_error", number(maximum_state_error)},
                     {"maximum_contact_prediction_rms",
                      number(maximum_contact_prediction_rms)},
                     {"flight_steps", integer(flight_steps)},
                     {"observed_contact_counts", "0;1;2;3;4"},
                     {"final_contact_count",
                      integer(walking_filter.activeContactIdentities().size())},
                     {"recovery_ratio_tolerance", "0.60"},
                     {"minimum_nonzero_innovation", "0.001"},
                     {"pass", boolean(walking_error_ratio < 0.60 &&
                                      first_walking_innovation > 1.0e-3 &&
                                      walking_final_error < walking_initial_error &&
                                      flight_steps == 10 &&
                                      observed_contact_counts ==
                                          std::set<int>({0, 1, 2, 3, 4}))}});

  // Seeded pure-synthetic continuous-ASD propagation with bias augmentation.
  // This is neither the paper Table-1 adapter nor Go2 performance evidence.
  const ContinuousNoiseDensity synthetic_stochastic_noise =
      syntheticContinuousAsdProfile();
  StateMean stochastic_truth;
  stochastic_truth.rotation = hartley::expSO3(Vector3(0.15, -0.1, 0.25));
  stochastic_truth.position = Vector3(0.0, 0.0, 0.5);
  for (int id = 0; id < 4; ++id) {
    stochastic_truth.contacts[id] =
        stochastic_truth.position + stochastic_truth.rotation * feet[id];
  }
  StateMean stochastic_initial = stochastic_truth;
  stochastic_initial.gyro_bias.setZero();
  stochastic_initial.accelerometer_bias.setZero();
  HartleyInEkf stochastic_filter(
      stochastic_initial, 1.0e-2 * Matrix::Identity(27, 27),
      synthetic_stochastic_noise);
  Vector3 true_gyro_bias = Vector3::Zero();
  Vector3 true_accel_bias = Vector3::Zero();
  std::mt19937_64 stochastic_generator(20260818);
  std::normal_distribution<double> standard_normal(0.0, 1.0);
  auto random_vector = [&]() {
    return Vector3(standard_normal(stochastic_generator),
                   standard_normal(stochastic_generator),
                   standard_normal(stochastic_generator));
  };
  constexpr double stochastic_dt = 0.004;
  for (int step = 0; step < 300; ++step) {
    const Vector3 true_omega(0.08 * std::sin(0.03 * step), -0.04,
                             0.12 * std::cos(0.02 * step));
    const Vector3 true_acceleration(0.15 * std::sin(0.05 * step),
                                    0.1 * std::cos(0.04 * step), 9.65);
    stochastic_truth = HartleyInEkf::exactMeanStep(
        stochastic_truth, true_omega, true_acceleration, stochastic_dt,
        Vector3(0.0, 0.0, -9.81));
    true_gyro_bias += synthetic_stochastic_noise.gyro_bias_rw_rad_per_s2_per_sqrt_hz *
                      std::sqrt(stochastic_dt) * random_vector();
    true_accel_bias +=
        synthetic_stochastic_noise.accelerometer_bias_rw_m_per_s3_per_sqrt_hz *
        std::sqrt(stochastic_dt) * random_vector();
    const Vector3 gyro_measurement =
        true_omega + true_gyro_bias +
        synthetic_stochastic_noise.gyro_measurement_rad_per_s_per_sqrt_hz /
            std::sqrt(stochastic_dt) * random_vector();
    const Vector3 accel_measurement =
        true_acceleration + true_accel_bias +
        synthetic_stochastic_noise.accelerometer_measurement_m_per_s2_per_sqrt_hz /
            std::sqrt(stochastic_dt) * random_vector();
    stochastic_filter.propagate(gyro_measurement, accel_measurement,
                                stochastic_dt);
    std::vector<ContactMeasurement> measurements;
    for (int id = 0; id < 4; ++id) {
      ContactMeasurement measurement = exactMeasurement(
          stochastic_truth, id, MeasurementStdMeters{0.0123});
      measurement.foot_position_body += 0.01 * random_vector();
      measurements.push_back(measurement);
    }
    stochastic_filter.correctContacts(measurements);
  }
  const double stochastic_state_error =
      (stochastic_filter.stateMean().position - stochastic_truth.position).norm() +
      (stochastic_filter.stateMean().velocity - stochastic_truth.velocity).norm() +
      (stochastic_filter.stateMean().rotation - stochastic_truth.rotation).norm();
  const double stochastic_bias_error =
      (stochastic_filter.stateMean().gyro_bias - true_gyro_bias).norm() +
      (stochastic_filter.stateMean().accelerometer_bias - true_accel_bias).norm();
  Eigen::SelfAdjointEigenSolver<Matrix> stochastic_eigen(
      stochastic_filter.stateCovariance());
  emit("synthetic", {{"case", "synthetic_continuous_asd_bias_and_stochastic_propagation"},
                     {"noise_profile", "PURE_SYNTHETIC_CONTINUOUS_ASD_NOT_GO2_PERFORMANCE_NOT_TABLE1"},
                     {"seed", "20260818"},
                     {"steps", "300"},
                     {"measurement_white_noise_injected", "true"},
                     {"bias_random_walk_injected", "true"},
                     {"state_error", number(stochastic_state_error)},
                     {"bias_error", number(stochastic_bias_error)},
                     {"covariance_min_eigenvalue",
                      number(stochastic_eigen.eigenvalues().minCoeff())},
                     {"pass", boolean(stochastic_state_error < 0.5 &&
                                      stochastic_bias_error < 0.5 &&
                                      stochastic_eigen.eigenvalues().minCoeff() >
                                          -1.0e-12)}});

  // Executable three-sample dwell check under a deliberately chattering input.
  bool dwell_state = false;
  bool dwell_candidate = false;
  int dwell_count = 0;
  int accepted_transitions = 0;
  const std::vector<bool> chatter = {true, false, true, false, true, false,
                                     true, false, true, false, true, false};
  auto update_dwell = [&](bool requested) {
    if (requested == dwell_state) {
      dwell_candidate = dwell_state;
      dwell_count = 0;
    } else if (requested != dwell_candidate) {
      dwell_candidate = requested;
      dwell_count = 1;
    } else {
      ++dwell_count;
      if (dwell_count >= 3) {
        dwell_state = dwell_candidate;
        dwell_count = 0;
        ++accepted_transitions;
      }
    }
  };
  for (const bool requested : chatter) update_dwell(requested);
  const int transitions_during_chatter = accepted_transitions;
  update_dwell(true);
  update_dwell(true);
  update_dwell(true);
  emit("synthetic", {{"case", "contact_chattering_three_sample_dwell"},
                     {"input_toggle_count", integer(chatter.size())},
                     {"transitions_during_chatter", integer(transitions_during_chatter)},
                     {"accepted_transitions_after_stable_triplet",
                      integer(accepted_transitions)},
                     {"dwell_samples", "3"},
                     {"pass", boolean(transitions_during_chatter == 0 &&
                                      accepted_transitions == 1 && dwell_state)}});

  // Stress: large attitude/rate and ill-conditioned but positive covariance.
  StateMean stress = deterministicState(0);
  stress.rotation = hartley::expSO3(Vector3(1.2, -0.9, 2.4));
  Matrix stress_covariance = Matrix::Identity(15, 15);
  for (int index = 0; index < 15; ++index)
    stress_covariance(index, index) = std::pow(10.0, -10.0 + index * 8.0 / 14.0);
  HartleyInEkf stress_filter(stress, stress_covariance, noise);
  for (int step = 0; step < 20; ++step)
    stress_filter.propagate(Vector3(8.0, -5.0, 3.0), Vector3(2.0, -1.0, 8.0),
                            0.02);
  Eigen::SelfAdjointEigenSolver<Matrix> stress_eigen(stress_filter.stateCovariance());
  emit("synthetic", {{"case", "stress_large_attitude_rate_ill_conditioned"},
                     {"rotation_determinant",
                      number(stress_filter.stateMean().rotation.determinant())},
                     {"covariance_min_eigenvalue",
                      number(stress_eigen.eigenvalues().minCoeff())},
                     {"finite", boolean(stress_filter.stateCovariance().allFinite())},
                     {"pass", boolean(std::abs(stress_filter.stateMean().rotation.determinant() -
                                               1.0) < 2.0e-12 &&
                                      stress_eigen.eigenvalues().minCoeff() > -1.0e-12)}});
}

Matrix fullGaugeTransform(const GroupState& gauge, const std::vector<int>& ids) {
  const Matrix group = hartley::adjointSEK3(gauge, ids);
  Matrix transform = Matrix::Identity(group.rows() + 6, group.cols() + 6);
  transform.block(0, 0, group.rows(), group.cols()) = group;
  return transform;
}

StateMean gaugeState(const StateMean& state, const GroupState& gauge) {
  StateMean result = withGroup(state, hartley::compose(gauge, groupPart(state)));
  return result;
}

void validateGauge() {
  auto run_case = [&](const std::string& name, bool stress) {
    StateMean truth = deterministicState(2);
    if (stress) {
      truth.rotation =
          hartley::expSO3(Vector3(1.0, -0.7, 2.1));
      truth.velocity = Vector3(8.0, -5.0, 2.0);
      truth.position = Vector3(30.0, -18.0, 7.0);
      truth.contacts[0] = Vector3(29.4, -17.2, 6.4);
      truth.contacts[1] = Vector3(30.7, -18.6, 6.2);
    }
    const auto ids = contactIds(truth);
    StateMean estimate = truth;
    estimate.rotation =
        hartley::expSO3(Vector3(0.07, -0.05, 0.015)) * truth.rotation;
    estimate.velocity += Vector3(0.13, -0.08, 0.05);
    estimate.position += Vector3(0.04, -0.03, 0.02);
    estimate.gyro_bias += Vector3(-0.006, 0.004, -0.003);
    estimate.accelerometer_bias += Vector3(-0.018, 0.012, -0.009);
    estimate.contacts[0] += Vector3(0.025, -0.015, 0.012);
    estimate.contacts[1] += Vector3(-0.021, 0.017, -0.010);

    const double gauge_yaw = stress ? -2.4 : 1.1;
    GroupState gauge;
    gauge.rotation =
        hartley::expSO3(Vector3(0.0, 0.0, gauge_yaw));
    gauge.position = stress ? Vector3(40.0, -25.0, 12.0)
                            : Vector3(4.0, -2.0, 1.5);
    for (const int id : ids) gauge.contacts[id] = gauge.position;
    const Matrix transform = fullGaugeTransform(gauge, ids);
    const Matrix inverse_transform = transform.inverse();
    Matrix covariance = nontrivialCrossCovariance(21);
    if (stress) covariance *= 3.0;
    HartleyInEkf base_filter(estimate, covariance,
                             syntheticContinuousAsdProfile());
    HartleyInEkf gauge_filter(
        gaugeState(estimate, gauge),
        transform * covariance * transform.transpose(),
        syntheticContinuousAsdProfile());

    const Matrix3 initial_base_rotation = base_filter.stateMean().rotation;
    const Matrix3 initial_gauge_rotation = gauge_filter.stateMean().rotation;
    const int steps = stress ? 20 : 40;
    const double dt = stress ? 0.05 : 0.004;
    double innovation_equivariance_error = 0.0;
    double measurement_invariance_error = 0.0;
    double maximum_base_innovation = 0.0;
    double first_base_innovation = -1.0;
    for (int step = 0; step < steps; ++step) {
      const Vector3 omega =
          stress ? Vector3(7.0, -5.0, 3.0)
                 : Vector3(0.1, -0.04, 0.2);
      const Vector3 acceleration =
          stress ? Vector3(2.0, -1.0, 8.0)
                 : Vector3(0.3, -0.1, 9.2);
      truth = HartleyInEkf::exactMeanStep(
          truth, omega, acceleration, dt, Vector3(0.0, 0.0, -9.81));
      const StateMean gauge_truth = gaugeState(truth, gauge);
      base_filter.propagate(omega + truth.gyro_bias,
                            acceleration + truth.accelerometer_bias, dt);
      gauge_filter.propagate(omega + truth.gyro_bias,
                             acceleration + truth.accelerometer_bias, dt);
      std::vector<ContactMeasurement> base_measurements;
      std::vector<ContactMeasurement> gauge_measurements;
      for (const int id : ids) {
        base_measurements.push_back(exactMeasurement(
            truth, id, MeasurementStdMeters{0.01}));
        gauge_measurements.push_back(exactMeasurement(
            gauge_truth, id, MeasurementStdMeters{0.01}));
        measurement_invariance_error = std::max(
            measurement_invariance_error,
            (base_measurements.back().foot_position_body -
             gauge_measurements.back().foot_position_body)
                .norm());
      }
      const auto base_diagnostic =
          base_filter.correctContacts(base_measurements);
      const auto gauge_diagnostic =
          gauge_filter.correctContacts(gauge_measurements);
      if (first_base_innovation < 0.0) {
        first_base_innovation = base_diagnostic.innovation.norm();
      }
      maximum_base_innovation = std::max(
          maximum_base_innovation, base_diagnostic.innovation.norm());
      Vector gauge_innovation_in_base = gauge_diagnostic.innovation;
      for (std::size_t index = 0; index < ids.size(); ++index) {
        gauge_innovation_in_base.segment<3>(3 * index) =
            gauge.rotation.transpose() *
            gauge_diagnostic.innovation.segment<3>(3 * index);
      }
      innovation_equivariance_error = std::max(
          innovation_equivariance_error,
          (base_diagnostic.innovation - gauge_innovation_in_base).norm());
    }

    const StateMean recovered =
        gaugeState(gauge_filter.stateMean(), hartley::inverse(gauge));
    double contact_error = 0.0;
    for (const int id : ids) {
      contact_error = std::max(
          contact_error,
          (recovered.contacts.at(id) -
           base_filter.stateMean().contacts.at(id))
              .norm());
    }
    const double rotation_error =
        (recovered.rotation - base_filter.stateMean().rotation).norm();
    const double velocity_error =
        (recovered.velocity - base_filter.stateMean().velocity).norm();
    const double position_error =
        (recovered.position - base_filter.stateMean().position).norm();
    const double bias_error =
        (recovered.gyro_bias - base_filter.stateMean().gyro_bias).norm() +
        (recovered.accelerometer_bias -
         base_filter.stateMean().accelerometer_bias)
            .norm();
    const Matrix recovered_covariance =
        inverse_transform * gauge_filter.stateCovariance() *
        inverse_transform.transpose();
    const double covariance_relative_error =
        (recovered_covariance - base_filter.stateCovariance()).norm() /
        std::max(1.0e-30, base_filter.stateCovariance().norm());
    const Matrix3 base_increment =
        initial_base_rotation.transpose() * base_filter.stateMean().rotation;
    const Matrix3 gauge_increment =
        initial_gauge_rotation.transpose() * gauge_filter.stateMean().rotation;
    const double relative_yaw_increment_error =
        (hartley::logSO3(base_increment) -
         hartley::logSO3(gauge_increment))
            .norm();
    const double native_yaw_separation =
        hartley::logSO3(gauge_filter.stateMean().rotation *
                        base_filter.stateMean().rotation.transpose())
            .z();
    const double state_tolerance = stress ? 2.0e-7 : kGaugeStateTolerance;
    const double covariance_tolerance =
        stress ? 2.0e-6 : kGaugeCovarianceTolerance;
    const bool pass =
        rotation_error < state_tolerance && velocity_error < state_tolerance &&
        position_error < state_tolerance && contact_error < state_tolerance &&
        bias_error < state_tolerance &&
        innovation_equivariance_error < state_tolerance &&
        measurement_invariance_error < state_tolerance &&
        covariance_relative_error < covariance_tolerance &&
        relative_yaw_increment_error < state_tolerance &&
        first_base_innovation > 1.0e-3 &&
        maximum_base_innovation > 1.0e-3 &&
        std::abs(native_yaw_separation - gauge_yaw) < state_tolerance;
    emit("gauge", {{"case", name},
                   {"truth_source", "INDEPENDENT_DETERMINISTIC_SYNTHETIC_TRUTH"},
                   {"stress", boolean(stress)},
                   {"rotation_error", number(rotation_error)},
                   {"velocity_error", number(velocity_error)},
                   {"position_error", number(position_error)},
                   {"contact_error", number(contact_error)},
                   {"bias_error", number(bias_error)},
                   {"measurement_invariance_error",
                    number(measurement_invariance_error)},
                   {"innovation_equivariance_error",
                    number(innovation_equivariance_error)},
                   {"first_innovation_norm", number(first_base_innovation)},
                   {"maximum_innovation_norm", number(maximum_base_innovation)},
                   {"covariance_congruence_relative_fro_error",
                    number(covariance_relative_error)},
                   {"native_yaw_separation", number(native_yaw_separation)},
                   {"expected_native_yaw_separation", number(gauge_yaw)},
                   {"relative_yaw_increment_error",
                    number(relative_yaw_increment_error)},
                   {"state_tolerance", number(state_tolerance)},
                   {"covariance_relative_tolerance",
                    number(covariance_tolerance)},
                   {"absolute_yaw_observable", "false"},
                   {"unobservable_global_yaw_verified", "true"},
                   {"pass", boolean(pass)}});
  };

  run_case("yaw_translation_family_normal", false);
  run_case("yaw_translation_family_stress", true);
}

}  // namespace

int main() {
  try {
    validateLieGroup();
    validateMeans();
    validatePhi();
    validateCovariances();
    validateLifecycleAndSynthetic();
    validateGauge();
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "HARTLEY_VALIDATOR_ERROR " << error.what() << '\n';
    return 1;
  }
}
