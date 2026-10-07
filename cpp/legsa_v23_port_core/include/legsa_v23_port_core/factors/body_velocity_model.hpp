#pragma once
#include "legsa_v23_port_core/nav_state.hpp"
#include "legsa_v23_port_core/factors/pose_clone.hpp"
namespace legsa_v23_port_core {
struct BodyVelocity2dModel { Vec3 prediction; std::vector<double> residual; Matrix H; Matrix R; };
// Input is already FRD velocity at the navigation IMU point. No GNSS/SDK yaw rotation here.
BodyVelocity2dModel buildBodyVelocity2dModel(const NavState& state, const Vec3& body_velocity,
                                            const Vec3& body_std);
// Insert b[21:23] without conditioning the existing current/clone marginal.
// H describes h(x), and b uses additive feedback; unknown source cross N=0.
pose_clone::Gaussian seedBodyVelocityDiscrepancy(const pose_clone::Gaussian& prior,
                                                const Matrix& H, const Matrix& Rseed);
Matrix bodyVelocityDiscrepancyJacobian(const Matrix& H, std::size_t joint_size);
} // namespace legsa_v23_port_core
