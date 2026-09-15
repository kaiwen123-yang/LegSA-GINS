#include "hartley_inekf/backend.hpp"

#include <Eigen/Eigenvalues>

#include <cmath>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <string>

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

int checks = 0;

void require(bool condition, const std::string& label) {
  ++checks;
  if (!condition) {
    throw std::runtime_error(label);
  }
}

void requireNear(double value, double expected, double tolerance,
                 const std::string& label) {
  require(std::abs(value - expected) <= tolerance,
          label + ": value=" + std::to_string(value) +
              " expected=" + std::to_string(expected));
}

GroupState groupPart(const StateMean& state) {
  GroupState result;
  result.rotation = state.rotation;
  result.velocity = state.velocity;
  result.position = state.position;
  result.contacts = state.contacts;
  return result;
}

StateMean withGroup(const StateMean& template_state, const GroupState& group) {
  StateMean result = template_state;
  result.rotation = group.rotation;
  result.velocity = group.velocity;
  result.position = group.position;
  result.contacts = group.contacts;
  return result;
}

Vector discreteErrorMap(const StateMean& estimate, const Vector3& omega,
                        const Vector3& acceleration, double dt,
                        const Vector3& gravity, const Vector& initial_error) {
  const std::vector<int> ids = [&]() {
    std::vector<int> result;
    for (const auto& entry : estimate.contacts) result.push_back(entry.first);
    return result;
  }();
  const int group_dimension = 9 + 3 * static_cast<int>(ids.size());
  const GroupState eta = hartley::expSEK3(initial_error.head(group_dimension), ids);
  const GroupState truth_group =
      hartley::compose(hartley::inverse(eta), groupPart(estimate));
  StateMean truth = withGroup(estimate, truth_group);
  truth.gyro_bias = estimate.gyro_bias - initial_error.segment<3>(group_dimension);
  truth.accelerometer_bias =
      estimate.accelerometer_bias - initial_error.segment<3>(group_dimension + 3);

  const StateMean estimate_next = HartleyInEkf::exactMeanStep(
      estimate, omega, acceleration, dt, gravity);
  const StateMean truth_next = HartleyInEkf::exactMeanStep(
      truth, omega + initial_error.segment<3>(group_dimension),
      acceleration + initial_error.segment<3>(group_dimension + 3), dt, gravity);
  const GroupState eta_next =
      hartley::compose(groupPart(estimate_next), hartley::inverse(groupPart(truth_next)));
  Vector result = Vector::Zero(initial_error.size());
  result.head(group_dimension) = hartley::logSEK3(eta_next, ids);
  result.segment<3>(group_dimension) =
      estimate_next.gyro_bias - truth_next.gyro_bias;
  result.segment<3>(group_dimension + 3) =
      estimate_next.accelerometer_bias - truth_next.accelerometer_bias;
  return result;
}

void testLiePrimitives() {
  require((hartley::gamma0(Vector3::Zero()) - Matrix3::Identity()).norm() < 1.0e-15,
          "Gamma0 zero limit");
  require((hartley::gamma1(Vector3::Zero()) - Matrix3::Identity()).norm() < 1.0e-15,
          "Gamma1 zero limit");
  require((hartley::gamma2(Vector3::Zero()) - 0.5 * Matrix3::Identity()).norm() <
              1.0e-15,
          "Gamma2 zero limit");
  const Vector3 vector(0.4, -0.2, 0.7);
  require((hartley::psi1(Vector3::Zero(), vector) + 0.5 * hartley::skew(vector))
                  .norm() <
              1.0e-14,
          "Psi1 zero limit");
  require((hartley::psi2(Vector3::Zero(), vector) +
           (1.0 / 6.0) * hartley::skew(vector))
                  .norm() <
              1.0e-14,
          "Psi2 zero limit");

  const Vector3 phis[] = {Vector3(1.0e-12, -2.0e-12, 3.0e-12),
                          Vector3(0.2, -0.4, 0.7),
                          Vector3(2.1, -1.2, 0.4)};
  for (const Vector3& phi : phis) {
    const Matrix3 rotation = hartley::expSO3(phi);
    require((rotation.transpose() * rotation - Matrix3::Identity()).norm() < 2.0e-13,
            "Exp orthogonality");
    requireNear(rotation.determinant(), 1.0, 2.0e-13, "Exp determinant");
    require((hartley::logSO3(rotation) - phi).norm() < 2.0e-12,
            "Exp/Log round trip");
  }

  GroupState state;
  state.rotation = hartley::expSO3(Vector3(0.2, -0.1, 0.4));
  state.velocity = Vector3(0.7, -1.1, 0.3);
  state.position = Vector3(2.0, -0.5, 1.2);
  state.contacts = {{1, Vector3(2.1, -0.3, 0.1)},
                    {3, Vector3(1.4, 0.8, -0.2)}};
  const std::vector<int> ids{1, 3};
  Vector tangent = Vector::LinSpaced(15, -0.04, 0.05);
  const GroupState reconstructed =
      hartley::expSEK3(hartley::logSEK3(hartley::expSEK3(tangent, ids), ids), ids);
  require((reconstructed.rotation - hartley::expSEK3(tangent, ids).rotation).norm() <
              1.0e-13,
          "SEK Exp/Log rotation");
  require((reconstructed.position - hartley::expSEK3(tangent, ids).position).norm() <
              1.0e-13,
          "SEK Exp/Log position");

  const double epsilon = 1.0e-7;
  const GroupState conjugated = hartley::compose(
      state, hartley::compose(hartley::expSEK3(epsilon * tangent, ids),
                              hartley::inverse(state)));
  const Vector numerical = hartley::logSEK3(conjugated, ids) / epsilon;
  const Vector analytical = hartley::adjointSEK3(state, ids) * tangent;
  require((numerical - analytical).norm() < 2.0e-8, "SEK adjoint identity");
  Vector3 nan_input = Vector3::Zero();
  nan_input.x() = std::numeric_limits<double>::quiet_NaN();
  Vector3 infinity_input = Vector3::Zero();
  infinity_input.y() = std::numeric_limits<double>::infinity();
  const Vector3 overflow_input =
      Vector3::Constant(std::numeric_limits<double>::max());
  for (const Vector3& invalid : {nan_input, infinity_input, overflow_input}) {
    const auto rejects = [&](const auto& operation) {
      try {
        operation();
        return false;
      } catch (const std::exception&) {
        return true;
      }
    };
    require(rejects([&]() { static_cast<void>(hartley::gamma0(invalid)); }),
            "Gamma0 rejects non-finite/overflow input");
    require(rejects([&]() { static_cast<void>(hartley::gamma1(invalid)); }),
            "Gamma1 rejects non-finite/overflow input");
    require(rejects([&]() { static_cast<void>(hartley::gamma2(invalid)); }),
            "Gamma2 rejects non-finite/overflow input");
    require(rejects([&]() { static_cast<void>(hartley::psi1(invalid, vector)); }),
            "Psi1 rejects non-finite/overflow rotation input");
    require(rejects([&]() { static_cast<void>(hartley::psi2(invalid, vector)); }),
            "Psi2 rejects non-finite/overflow rotation input");
    require(rejects([&]() {
              static_cast<void>(hartley::psi1(Vector3(0.4, -0.3, 0.2), invalid));
            }),
            "Psi1 rejects non-finite/overflow vector input");
    require(rejects([&]() {
              static_cast<void>(hartley::psi2(Vector3(0.4, -0.3, 0.2), invalid));
            }),
            "Psi2 rejects non-finite/overflow vector input");
  }
}

StateMean randomState(int contacts, std::mt19937_64& generator) {
  std::normal_distribution<double> normal(0.0, 1.0);
  auto random_vector = [&]() {
    return Vector3(normal(generator), normal(generator), normal(generator));
  };
  StateMean state;
  state.rotation = hartley::expSO3(0.6 * random_vector());
  state.velocity = random_vector();
  state.position = random_vector();
  state.gyro_bias = 0.03 * random_vector();
  state.accelerometer_bias = 0.1 * random_vector();
  const int identities[] = {3, 0, 2, 1};
  for (int index = 0; index < contacts; ++index) {
    state.contacts.emplace(identities[index], random_vector());
  }
  return state;
}

void testExactMean() {
  std::mt19937_64 generator(1203981);
  const Vector3 gravity(0.0, 0.0, -9.81);
  const std::vector<Vector3> angular_rates = {
      Vector3::Zero(), Vector3(1.0e-10, -2.0e-10, 3.0e-10),
      Vector3(0.4, -0.7, 1.1), Vector3(7.0, -4.0, 2.0)};
  for (const double dt : {0.001, 0.004, 0.02, 0.2}) {
    for (const Vector3& omega : angular_rates) {
      StateMean state = randomState(2, generator);
      const Vector3 acceleration(0.7, -1.3, 9.2);
      const StateMean exact =
          HartleyInEkf::exactMeanStep(state, omega, acceleration, dt, gravity);
      StateMean numerical = state;
      const int steps = 20000;
      const double h = dt / steps;
      for (int step = 0; step < steps; ++step) {
        const Matrix3 midpoint_rotation =
            numerical.rotation * hartley::expSO3(0.5 * omega * h);
        const Vector3 midpoint_acceleration = midpoint_rotation * acceleration + gravity;
        numerical.position += numerical.velocity * h +
                              0.5 * midpoint_acceleration * h * h;
        numerical.velocity += midpoint_acceleration * h;
        numerical.rotation = numerical.rotation * hartley::expSO3(omega * h);
      }
      require((hartley::logSO3(exact.rotation * numerical.rotation.transpose())).norm() <
                  2.0e-11,
              "Eq50 rotation numerical oracle");
      require((exact.velocity - numerical.velocity).norm() < 2.0e-9 + 2.0e-9 * dt,
              "Eq50 velocity numerical oracle");
      require((exact.position - numerical.position).norm() < 2.0e-9 + 2.0e-9 * dt,
              "Eq50 position numerical oracle");
      require(exact.contacts == state.contacts, "Eq50 contact constancy");
      require(exact.gyro_bias == state.gyro_bias, "Eq50 gyro bias constancy");
      require(exact.accelerometer_bias == state.accelerometer_bias,
              "Eq50 accelerometer bias constancy");
    }
  }
}

void testAnalyticalPhi() {
  std::mt19937_64 generator(994321);
  std::normal_distribution<double> normal(0.0, 1.0);
  const Vector3 gravity(0.0, 0.0, -9.81);
  for (int contacts = 0; contacts <= 4; ++contacts) {
    for (const double dt : {0.0, 1.0e-5, 0.004, 0.02, 0.15}) {
      StateMean state = randomState(contacts, generator);
      Vector3 omega(normal(generator), normal(generator), normal(generator));
      if (dt < 2.0e-5) omega.setZero();
      const Vector3 acceleration(normal(generator), normal(generator),
                                 9.0 + normal(generator));
      const Matrix analytical =
          HartleyInEkf::analyticalPhi(state, omega, acceleration, dt, gravity);
      const Matrix eq60 =
          HartleyInEkf::analyticalPhiEq60(state, omega, acceleration, dt, gravity);
      Matrix numerical = Matrix::Zero(analytical.rows(), analytical.cols());
      const double epsilon = 2.0e-7;
      for (int column = 0; column < analytical.cols(); ++column) {
        Vector plus = Vector::Zero(analytical.cols());
        plus(column) = epsilon;
        Vector minus = -plus;
        numerical.col(column) =
            (discreteErrorMap(state, omega, acceleration, dt, gravity, plus) -
             discreteErrorMap(state, omega, acceleration, dt, gravity, minus)) /
            (2.0 * epsilon);
      }
      const double maximum = (analytical - numerical).cwiseAbs().maxCoeff();
      const double eq58_eq60_relative =
          (analytical - eq60).norm() / std::max(1.0, analytical.norm());
      const double zero_dt_identity_error =
          dt == 0.0
              ? (analytical - Matrix::Identity(analytical.rows(), analytical.cols()))
                    .cwiseAbs()
                    .maxCoeff()
              : 0.0;
      require(maximum < 2.5e-7 && eq58_eq60_relative < 1.0e-9 &&
                  zero_dt_identity_error < 5.0e-12,
              "analytical Phi finite difference contacts=" + std::to_string(contacts) +
                  " dt=" + std::to_string(dt) + " max=" + std::to_string(maximum) +
                  " eq58_eq60=" + std::to_string(eq58_eq60_relative));
    }
  }
}

ContinuousNoiseDensity go2Noise() {
  return {2.865130e-4, 1.285395e-3, 2.996871e-5, 1.594412e-4, 0.0};
}

void testNoiseAndLifecycle() {
  const ContinuousNoiseDensity density = go2Noise();
  const auto psd = hartley::continuousPsdFromDensity(density);
  requireNear(psd.gyro_measurement_rad2_per_s, 8.2089699169e-8, 1.0e-20,
              "gyro density squared once");
  requireNear(psd.accelerometer_measurement_m2_per_s3, 1.652240306025e-6, 1.0e-18,
              "accel density squared once");
  const auto samples = hartley::discreteSampleStdFromDensity(density, 0.01);
  requireNear(samples.gyro_measurement_rad_per_s, density.gyro_measurement_rad_per_s_per_sqrt_hz / 0.1,
              1.0e-15, "measurement sample std API");
  requireNear(samples.gyro_bias_increment_rad_per_s,
              density.gyro_bias_rw_rad_per_s2_per_sqrt_hz * 0.1, 1.0e-15,
              "bias increment std API");
  const Matrix3 fk_covariance =
      hartley::isotropicMeasurementCovariance(MeasurementStdMeters{0.010});
  require((fk_covariance - 1.0e-4 * Matrix3::Identity()).norm() < 1.0e-18,
          "FK measurement std remains measurement R only");

  StateMean state;
  state.rotation = hartley::expSO3(Vector3(0.3, -0.2, 0.5));
  state.velocity = Vector3(0.4, -0.1, 0.2);
  state.position = Vector3(1.0, 2.0, -0.4);
  Matrix covariance = 0.1 * Matrix::Identity(15, 15);
  HartleyInEkf filter(state, covariance, density);
  const Matrix3 measurement_covariance = 1.0e-4 * Matrix3::Identity();
  filter.augmentContacts({{3, Vector3(-0.3, 0.2, -0.4), measurement_covariance},
                          {1, Vector3(0.3, 0.2, -0.4), measurement_covariance}});
  const PaperTable1DiscreteStd paper_parameters{};
  requireNear(paper_parameters.joint_encoder_noise_std_deg, 1.0, 0.0,
              "paper Table-1 joint encoder standard deviation retained in degrees");
  Matrix foot_jacobian(3, 4);
  foot_jacobian << 0.12, -0.04, 0.02, 0.01,
                   -0.03, 0.10, 0.05, -0.02,
                   0.06, 0.01, -0.11, 0.04;
  const double encoder_sigma_rad =
      3.141592653589793238462643383279502884 / 180.0;
  const Matrix3 encoder_covariance =
      hartley::contactMeasurementCovarianceFromPaperTable1JointEncoder(
          foot_jacobian, paper_parameters);
  const Matrix3 expected_encoder_covariance =
      encoder_sigma_rad * encoder_sigma_rad * foot_jacobian *
      foot_jacobian.transpose();
  require((encoder_covariance - expected_encoder_covariance)
                  .cwiseAbs()
                  .maxCoeff() <
              2.0e-18,
          "paper Table-1 encoder degrees map through m/rad Jacobian to R in m2");
  PaperTable1DiscreteStd invalid_encoder = paper_parameters;
  invalid_encoder.joint_encoder_noise_std_deg = -1.0;
  bool invalid_encoder_rejected = false;
  try {
    static_cast<void>(
        hartley::contactMeasurementCovarianceFromPaperTable1JointEncoder(
            foot_jacobian, invalid_encoder));
  } catch (const std::invalid_argument&) {
    invalid_encoder_rejected = true;
  }
  require(invalid_encoder_rejected,
          "negative paper Table-1 encoder degrees are rejected");
  const Matrix mixed_qbar = HartleyInEkf::eq61MappedQbarGo2ImuPaperContact(
      filter.stateMean(), density, paper_parameters);
  const Matrix table1_qbar = HartleyInEkf::eq61MappedQbarPaperTable1(
      filter.stateMean(), paper_parameters);
  const Matrix table1_L = HartleyInEkf::continuousL(filter.stateMean());
  Matrix table1_native = Matrix::Zero(table1_L.cols(), table1_L.cols());
  table1_native.block<3, 3>(0, 0) = 4.0e-6 * Matrix3::Identity();
  table1_native.block<3, 3>(3, 3) = 1.6e-3 * Matrix3::Identity();
  table1_native.block<3, 3>(6, 6) = 2.5e-3 * Matrix3::Identity();
  table1_native.block<3, 3>(9, 9) = 2.5e-3 * Matrix3::Identity();
  table1_native.block<3, 3>(12, 12) = 1.0e-6 * Matrix3::Identity();
  table1_native.block<3, 3>(15, 15) = 1.0e-6 * Matrix3::Identity();
  const Matrix expected_table1_qbar =
      table1_L * table1_native * table1_L.transpose();
  require((table1_qbar - expected_table1_qbar).cwiseAbs().maxCoeff() < 2.0e-15,
          "typed paper Table-1 all-five-block Qbar mapping");
  const Vector3 table1_omega(0.3, -0.2, 0.1);
  const Vector3 table1_accel(0.4, -0.1, 9.4);
  const Vector3 gravity(0.0, 0.0, -9.81);
  constexpr double table1_dt = 0.004;
  const Matrix table1_phi = HartleyInEkf::analyticalPhi(
      filter.stateMean(), table1_omega, table1_accel, table1_dt, gravity);
  const Matrix table1_qd = HartleyInEkf::eq61ProcessCovariancePaperTable1(
      filter.stateMean(), table1_omega, table1_accel, table1_dt, gravity,
      paper_parameters);
  require((table1_qd - table1_phi * expected_table1_qbar *
                             table1_phi.transpose() * table1_dt)
                  .cwiseAbs()
                  .maxCoeff() <
              2.0e-15,
          "typed paper Table-1 Eq61 Qd mapping");
  PaperTable1DiscreteStd zero_contact = paper_parameters;
  zero_contact.contact_linear_velocity_noise_std_m_per_s = 0.0;
  const Matrix qbar_without_contact =
      HartleyInEkf::eq61MappedQbarGo2ImuPaperContact(
          filter.stateMean(), density, zero_contact);
  const Matrix contact_delta = mixed_qbar - qbar_without_contact;
  require((contact_delta.block<3, 3>(9, 9) -
           0.0025 * Matrix3::Identity())
                  .norm() <
              1.0e-15,
          "paper-native contact std enters Eq61 Qbar adapter only");
  ContinuousNoiseDensity invalid_mixed = density;
  invalid_mixed.contact_velocity_m_per_s_per_sqrt_hz = 0.01;
  bool mixed_contact_rejected = false;
  try {
    HartleyInEkf::eq61MappedQbarGo2ImuPaperContact(
        filter.stateMean(), invalid_mixed, paper_parameters);
  } catch (const std::invalid_argument&) {
    mixed_contact_rejected = true;
  }
  require(mixed_contact_rejected,
          "mixed H5 adapter rejects contact ASD in ContinuousNoiseDensity");
  require(filter.activeContactIdentities() == std::vector<int>({1, 3}),
          "stable sorted contact identities");
  require(filter.stateDimension() == 21, "simultaneous augmentation dimension");
  const Matrix covariance_after_add = filter.stateCovariance();
  require((covariance_after_add.block<3, 3>(9, 6) -
           covariance_after_add.block<3, 3>(12, 6))
                  .norm() <
              1.0e-14,
          "augmentation shared position cross covariance");
  const Vector3 measurement_1 =
      filter.stateMean().rotation.transpose() *
      (filter.stateMean().contacts.at(1) - filter.stateMean().position);
  const Vector3 measurement_3 =
      filter.stateMean().rotation.transpose() *
      (filter.stateMean().contacts.at(3) - filter.stateMean().position);
  bool partial_rejected = false;
  try {
    filter.correctContacts({{1, measurement_1, measurement_covariance}});
  } catch (const std::invalid_argument&) {
    partial_rejected = true;
  }
  require(partial_rejected, "production correction rejects active-contact subset");
  bool unsorted_rejected = false;
  try {
    filter.correctContacts({{3, measurement_3, measurement_covariance},
                            {1, measurement_1, measurement_covariance}});
  } catch (const std::invalid_argument&) {
    unsorted_rejected = true;
  }
  require(unsorted_rejected, "production correction rejects unsorted leg IDs");
  bool early_subset_rejected = false;
  try {
    filter.correctContactSubsetForOfficialEarlyRegression(
        {{1, measurement_1, measurement_covariance}});
  } catch (const std::logic_error&) {
    early_subset_rejected = true;
  }
  require(early_subset_rejected,
          "official subset correction API rejects production backend");
  const auto diagnostics = filter.correctContacts(
      {{1, measurement_1, measurement_covariance},
       {3, measurement_3, measurement_covariance}});
  require(diagnostics.factorization_ok, "contact LLT factorization");
  require(diagnostics.innovation.norm() < 1.0e-14, "zero contact innovation");
  require(diagnostics.H.rows() == 6 && diagnostics.H.cols() == 21,
          "stacked contact H dimension");
  filter.removeContacts({1});
  require(filter.activeContactIdentities() == std::vector<int>({3}),
          "single removal identity");
  require(filter.stateDimension() == 18, "single removal dimension");
  filter.augmentContacts({{0, Vector3(0.2, -0.2, -0.4), measurement_covariance},
                          {2, Vector3(-0.2, -0.2, -0.4), measurement_covariance}});
  filter.removeContacts({3, 0});
  require(filter.activeContactIdentities() == std::vector<int>({2}),
          "mixed epoch remove/add integrity");
  Eigen::SelfAdjointEigenSolver<Matrix> eigensolver(filter.stateCovariance());
  require(eigensolver.eigenvalues().minCoeff() > -1.0e-12,
          "lifecycle covariance PSD");

  StateMean qstate = filter.stateMean();
  const Vector3 omega(0.4, -0.2, 0.3);
  const Vector3 acceleration(0.5, 0.1, 9.4);
  for (const double dt : {1.0e-5, 0.004, 0.02, 0.1}) {
    const Matrix eq61 = HartleyInEkf::eq61ProcessCovariance(
        qstate, omega, acceleration, dt, Vector3(0.0, 0.0, -9.81), density);
    const Matrix eq52 = HartleyInEkf::eq52ProcessCovarianceGaussLegendre64(
        qstate, omega, acceleration, dt, Vector3(0.0, 0.0, -9.81), density);
    require((eq61 - eq61.transpose()).norm() < 1.0e-14, "Eq61 symmetry");
    require((eq52 - eq52.transpose()).norm() < 1.0e-14, "Eq52 symmetry");
    Eigen::SelfAdjointEigenSolver<Matrix> eig61(eq61);
    Eigen::SelfAdjointEigenSolver<Matrix> eig52(eq52);
    require(eig61.eigenvalues().minCoeff() > -1.0e-15, "Eq61 PSD");
    require(eig52.eigenvalues().minCoeff() > -1.0e-15, "Eq52 PSD");
  }
}

void testBackendIdentitySeparation() {
  StateMean state;
  Matrix covariance = 0.01 * Matrix::Identity(15, 15);
  HartleyInEkf reported(state, covariance, go2Noise(),
                        BackendIdentity::HARTLEY_IJRR2020_REPORTED_BACKEND);
  HartleyInEkf exact(state, covariance, go2Noise(),
                     BackendIdentity::EXACT_QD_REFERENCE_DIAGNOSTIC);
  HartleyInEkf early(state, covariance, go2Noise(),
                     BackendIdentity::OFFICIAL_CPP_EARLY_REGRESSION);
  const Vector3 omega(0.5, -0.2, 0.3);
  const Vector3 acceleration(1.0, -0.4, 9.2);
  reported.propagate(omega, acceleration, 0.02);
  exact.propagate(omega, acceleration, 0.02);
  early.propagate(omega, acceleration, 0.02);
  require((reported.stateMean().position - exact.stateMean().position).norm() < 1.0e-15,
          "reported and Eq52 mean identity");
  require((reported.diagnostics().propagation.Phi -
           exact.diagnostics().propagation.Phi)
                  .norm() <
              1.0e-15,
          "reported and Eq52 Phi identity");
  require((reported.diagnostics().propagation.Qd -
           exact.diagnostics().propagation.Qd)
                  .norm() >
              1.0e-14,
          "Eq61 and Eq52 remain distinct");
  require((reported.stateMean().position - early.stateMean().position).norm() > 1.0e-8,
          "official early mean remains distinct");
  require(hartley::backendIdentityName(reported.diagnosticBackendIdentity()) ==
              "HARTLEY_IJRR2020_REPORTED_BACKEND",
          "reported identity label");
}

}  // namespace

int main() {
  try {
    testLiePrimitives();
    testExactMean();
    testAnalyticalPhi();
    testNoiseAndLifecycle();
    testBackendIdentitySeparation();
    std::cout << "PASS_HARTLEY_CPP_BACKEND_TESTS checks=" << checks << '\n';
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "FAIL_HARTLEY_CPP_BACKEND_TESTS checks=" << checks
              << " error=" << error.what() << '\n';
    return 1;
  }
}
