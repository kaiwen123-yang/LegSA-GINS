#pragma once
#include "legsa_v23_port_core/nav_state.hpp"
namespace legsa_v23_port_core {
struct BodyVelocity2dModel { Vec3 prediction; std::vector<double> residual; Matrix H; Matrix R; };
// Input is already FRD velocity at the navigation IMU point. No GNSS/SDK yaw rotation here.
BodyVelocity2dModel buildBodyVelocity2dModel(const NavState& state, const Vec3& body_velocity,
                                            const Vec3& body_std);
} // namespace legsa_v23_port_core
