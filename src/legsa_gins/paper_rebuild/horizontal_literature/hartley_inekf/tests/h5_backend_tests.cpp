#include "hartley_inekf/backend.hpp"

#include <Eigen/Eigenvalues>

#include <iostream>
#include <stdexcept>

namespace {
using namespace hartley;

void require(bool condition, const char* label) {
  if (!condition) throw std::runtime_error(label);
}

ContinuousNoiseDensity go2() {
  ContinuousNoiseDensity value;
  value.gyro_measurement_rad_per_s_per_sqrt_hz = 2.865130e-4;
  value.accelerometer_measurement_m_per_s2_per_sqrt_hz = 1.285395e-3;
  value.gyro_bias_rw_rad_per_s2_per_sqrt_hz = 2.996871e-5;
  value.accelerometer_bias_rw_m_per_s3_per_sqrt_hz = 1.594412e-4;
  return value;
}

std::vector<ContactMeasurement> contacts() {
  return {{0, Vector3(0.25, 0.15, -0.3), 1.0e-4 * Matrix3::Identity()},
          {1, Vector3(0.25, -0.15, -0.3), 1.0e-4 * Matrix3::Identity()}};
}

void testPolicyAndCounters() {
  ContinuousNoiseDensity illegal = go2();
  illegal.contact_velocity_m_per_s_per_sqrt_hz = 0.05;
  bool rejected = false;
  try {
    static_cast<void>(H5Eq61NoisePolicy::go2ImuPaperContact(illegal));
  } catch (const std::invalid_argument&) {
    rejected = true;
  }
  require(rejected, "nonzero contact ASD must be rejected");

  StateMean state;
  Matrix covariance = 0.01 * Matrix::Identity(15, 15);
  HartleyInEkf filter(state, covariance,
                      H5Eq61NoisePolicy::go2ImuPaperContact(go2()));
  filter.propagate(Vector3(0.01, -0.02, 0.03),
                   Vector3(0.1, -0.2, 9.7), 0.004);
  const auto& diagnostics = filter.h5RuntimeDiagnostics();
  require(diagnostics.propagation_calls == 1, "propagation counter");
  require(diagnostics.eq61_calls == 1, "Eq61 counter");
  require(diagnostics.eq52_calls == 0, "Eq52 unavailable in H5");
  require(diagnostics.last_qbar.rows() == 15, "Qbar exposed");
}

void testFiveProcessHasNoEncoderDependency() {
  StateMean state;
  state.contacts.emplace(0, Vector3(0.2, 0.1, -0.3));
  const PaperTable1ProcessStd five;
  const Matrix direct = HartleyInEkf::eq61MappedQbarPaperTable1Process(state, five);
  require(direct.rows() == 18 && direct.allFinite(), "five-process Qbar");
  // PaperTable1ProcessStd has five doubles exactly and cannot carry encoder noise.
  require(sizeof(PaperTable1ProcessStd) == 5 * sizeof(double),
          "five-process type must have no sixth field");
}

void testInitialContactPriorAndAtomicLifecycle() {
  StateMean state;
  Matrix covariance = Matrix::Zero(15, 15);
  covariance.diagonal() <<
      0.25, 0.25, 0.25, 1, 1, 1, 0.01, 0.01, 0.01,
      2.5e-5, 2.5e-5, 2.5e-5, 0.0025, 0.0025, 0.0025;
  HartleyInEkf base(state, covariance,
                    H5Eq61NoisePolicy::go2ImuPaperContact(go2()));
  HartleyInEkf with_prior(state, covariance,
                          H5Eq61NoisePolicy::go2ImuPaperContact(go2()));
  base.augmentContacts(contacts());
  with_prior.initializeContactsEq32WithIndependentPrior(contacts(), 0.1);
  const Matrix difference = with_prior.stateCovariance() - base.stateCovariance();
  Matrix expected = Matrix::Zero(21, 21);
  expected.block<3, 3>(9, 9) = 0.01 * Matrix3::Identity();
  expected.block<3, 3>(12, 12) = 0.01 * Matrix3::Identity();
  require((difference - expected).cwiseAbs().maxCoeff() < 2.0e-14,
          "initial prior must preserve every Eq32 cross block");

  std::vector<ContactMeasurement> survivor{contacts()[1]};
  std::vector<ContactMeasurement> added{
      {2, Vector3(-0.25, 0.15, -0.3), 1.0e-4 * Matrix3::Identity()}};
  with_prior.processContactLifecycle(survivor, {0}, added);
  require(with_prior.activeContactIdentities() == std::vector<int>({1, 2}),
          "atomic survivor-remove-add lifecycle");
  require(with_prior.h5RuntimeDiagnostics().lifecycle_calls == 1,
          "lifecycle counter");
}
}  // namespace

int main() {
  try {
    testPolicyAndCounters();
    testFiveProcessHasNoEncoderDependency();
    testInitialContactPriorAndAtomicLifecycle();
    std::cout << "PASS_HARTLEY_H5_BACKEND_TESTS\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "FAIL_HARTLEY_H5_BACKEND_TESTS error=" << error.what() << "\n";
    return 1;
  }
}
