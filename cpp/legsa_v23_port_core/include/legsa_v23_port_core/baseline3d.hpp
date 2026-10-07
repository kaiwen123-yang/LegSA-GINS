#pragma once

#include "legsa_v23_port_core/types.hpp"

namespace legsa_v23_port_core {

// T5bc: observation coordinates must use the same NED frame as Cbn.
// No calibration, coordinate fitting, or scalar-yaw observation is performed here.
struct Baseline3dMeasurement {
  Vec3 ned_m = makeVec3(0.0, 0.0, 0.0);
  std::string source = "dual_pvt";
  Vec3 ecef_m = makeVec3(0.0, 0.0, 0.0);
  Matrix3 covariance_ecef_m2{};
  double measurement_time = 0.0;
  double decision_available_time = 0.0;
  double pacc1_m = 0.0;
  double pacc2_m = 0.0;
  bool present = false;
  bool valid = false;
  std::string reason = "missing_exact_time";
};

struct Baseline3dModel {
  Vec3 predicted_m;
  Vec3 residual_m;
  Matrix H;
  Matrix R;
  double along_axis_residual_m = 0.0;
  double length_mismatch_m = 0.0;
};

Baseline3dModel buildBaseline3dModel(const Matrix3& cbn,
                                   const Baseline3dMeasurement& observation,
                                   double length_m, double k_b);

// Full SPD covariance is required; no isotropic pAcc substitution or eigenvalue repair.
void validateExternalCarrierCovariance(const Matrix3& covariance);
Baseline3dModel buildExternalCarrierBaseline3dModel(
    const Matrix3& cbn, const Vec3& blh_rad_m,
    const Baseline3dMeasurement& observation, const Vec3& body_vector_m);

struct Baseline3dDiagnostics {
  // Diagnostic snapshot only: current conditional error chart before this carrier.
  std::size_t event_sequence = 0;
  bool prior_available = false;
  double prior_state_time = 0.0;
  Matrix3 prior_nominal_cbn{};
  Vec3 prior_nominal_blh_rad_m{};
  Vec3 prior_body_baseline_m{};
  Vec3 prior_dx_phi_rad{};
  Matrix3 prior_P_phi_phi_rad2{};
  Vec3 prior_dx_p_m{};
  Matrix3 prior_P_p_p_m2{};
  Matrix3 prior_P_p_phi_m_rad{};
  double time = 0.0;
  std::string source = "dual_pvt";
  double measurement_time = 0.0;
  double decision_available_time = 0.0;
  Matrix3 covariance_ned_m2{};
  bool present = false;
  bool valid = false;
  bool model_available = false;
  bool attempted = false;
  bool accepted = false;
  bool nis_available = false;
  Vec3 observed_m = makeVec3(0.0, 0.0, 0.0);
  Vec3 predicted_m = makeVec3(0.0, 0.0, 0.0);
  Vec3 residual_m = makeVec3(0.0, 0.0, 0.0);
  Vec3 innovation_m = makeVec3(0.0, 0.0, 0.0);
  double pacc1_m = 0.0;
  double pacc2_m = 0.0;
  double base_variance_m2 = 0.0;
  double along_axis_residual_m = 0.0;
  double length_mismatch_m = 0.0;
  double nis = 0.0;
  double qa_R_scale = 1.0;
  double sa_R_scale = 1.0;
  std::string qa_action = "INACTIVE";
  std::string reason;
};

struct Baseline3dCounts {
  std::size_t attempts = 0;
  std::size_t accepted = 0;
  std::size_t rejected = 0;
  std::size_t invalid = 0;
  std::size_t missing = 0;
};

}  // namespace legsa_v23_port_core
