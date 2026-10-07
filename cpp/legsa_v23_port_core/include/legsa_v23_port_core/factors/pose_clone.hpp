#pragma once

#include "legsa_v23_port_core/types.hpp"
#include <vector>

namespace legsa_v23_port_core::pose_clone {

constexpr std::size_t kCurrent = 21;
constexpr std::size_t kClonePosition = 21;
constexpr std::size_t kCloneAttitude = 24;
constexpr std::size_t kJoint = 27;

// Current errors follow GIEngine: position is nominal-minus-true NED metres,
// attitude is a left correction in NED. Clone position is nominal-minus-true
// ECEF metres; clone attitude is a left correction in ECEF.
struct Gaussian {
  Matrix covariance;
  std::vector<double> mean;
};

struct FootModel {
  std::vector<double> residual;  // Clone-body FRD metres, stacked by foot (XY by default).
  Matrix H;                    // residual = H * joint error + measurement error.
  Matrix R;
  Matrix foot_error_map;
};

Matrix augmentationJacobian(const Vec3& current_blh);
Gaussian augment(const Matrix& current_covariance, const std::vector<double>& current_mean,
                 const Matrix& clone_jacobian);
Gaussian propagate(const Gaussian& state, const Matrix& current_transition,
                   const Matrix& current_process_covariance);
Gaussian ordinaryUpdate(const Gaussian& state, const std::vector<double>& residual,
                        const Matrix& H, const Matrix& R);
Gaussian footUpdate(const Gaussian& state, const FootModel& model);
// Apply nominal feedback first: current as GIEngine, clone p -= mean[21:24],
// clone R <- Exp(mean[24:27]) R. This transports ALL covariance blocks and
// zeros the complete error mean. Clone ECEF position needs no frame reset.
Gaussian reset(const Gaussian& state, const Matrix3& current_position_reset);
Gaussian marginalCurrent(const Gaussian& state);

// The first n xyz triples of Sigma describe raw foot0 errors, the next n
// describe foot1 errors. Keep endpoint/foot cross terms; no independent gyro
// noise is added because both poses already belong to the joint state.
// p0 is the saved IMU position in ECEF; blh1 is current IMU BLH (rad,rad,m).
// Body points and body_origin_to_imu are expressed in the same engine frame.
// horizontal_only selects body0 XY, never ECEF XY. The clone-attitude H block
// includes rotation of the residual frame even for a nonzero residual.
FootModel footModel(const std::vector<Vec3>& foot0, const std::vector<Vec3>& foot1,
                    const Vec3& clone_position_ecef, const Matrix3& clone_body_to_ecef,
                    const Matrix3& current_body_to_ned, const Vec3& current_blh,
                    const Matrix& complete_foot_covariance,
                    const Vec3& body_origin_to_imu = Vec3{0.0, 0.0, 0.0},
                    bool horizontal_only = true);

}  // namespace legsa_v23_port_core::pose_clone
