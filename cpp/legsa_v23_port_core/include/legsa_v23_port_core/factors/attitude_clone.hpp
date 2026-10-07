#pragma once

#include "legsa_v23_port_core/types.hpp"
#include <string>
#include <vector>

namespace legsa_v23_port_core::attitude_clone {

constexpr std::size_t kCurrent = 21;
constexpr std::size_t kJoint = 24;

struct Gaussian {
  Matrix covariance;
  std::vector<double> mean;
};

struct PairModel {
  std::vector<double> residual;
  Matrix H;
  Matrix R;
};

struct SafeInnovation { double statistic=0.0; bool passed=false; };
constexpr double kSafeInnovationThreshold = 16.26623619623813;

// Passive telemetry. It never selects or applies a different covariance update.
struct YoungCandidateDiagnostic {
  double epsilon=0.0, score=0.0, comparison_score=0.0, tie=0.0;
  bool selected_at_step=false;
};
struct YoungDiagnostics {
  double T=0.0, J=0.0;
  bool J_available=false;  // Singular R may be legal for the old grid; no diagnostic jitter.
  std::vector<YoungCandidateDiagnostic> candidates;
};
struct YoungResult {
  Gaussian state;
  bool applied = false;
  double epsilon = 0.0;  // Zero is the explicit SKIP action, not a limiting gain.
  double prior_score = 0.0;
  double bound_score = 0.0;
};

// Fixed-linearization working covariance only; no physical calibration claim.
Matrix symmetricPsd(const Matrix& value, std::size_t size, const char* name);
Matrix3 leftResetJacobian(const Vec3& correction);
Matrix3 nedFrameConnection(const Vec3& blh);
Matrix augmentationJacobian(const Vec3& blh);
Gaussian augment(const Matrix& current_covariance, const std::vector<double>& current_mean,
                 const Matrix& J);
Gaussian ordinaryUpdate(const Gaussian& state, const std::vector<double>& dz,
                        const Matrix& H, const Matrix& R);
Gaussian reset(const Gaussian& state, const Matrix3& position_reset);
std::vector<double> fixedCurrentWeights(const Matrix& initial_covariance);
SafeInnovation safeInnovation(const Gaussian& state, const std::vector<double>& dz,
                              const Matrix& H, const Matrix& R);
YoungResult youngUpdate(const Gaussian& state, const std::vector<double>& dz,
                        const Matrix& H, const Matrix& R,
                        const std::vector<double>& fixed_current_weights, YoungDiagnostics* diagnostics=nullptr);
PairModel pairModel(const Vec3& d0, const Vec3& d1, const Matrix3& clone_body_to_ecef,
                    const Matrix3& current_body_to_ned, const Vec3& current_blh,
                    const Matrix& complete_difference_covariance);
void requireRotation(const Matrix3& rotation, const char* name);

}  // namespace legsa_v23_port_core::attitude_clone
