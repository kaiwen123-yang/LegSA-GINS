#include "legsa_v23_port_core/baseline3d.hpp"

#include <cmath>
#include <stdexcept>

namespace legsa_v23_port_core {

Baseline3dModel buildBaseline3dModel(const Matrix3& cbn,
                                   const Baseline3dMeasurement& observation,
                                   double length_m, double k_b) {
  if (!observation.valid || !std::isfinite(length_m) || length_m <= 0.0 ||
      !std::isfinite(k_b) || k_b <= 0.0) {
    throw std::runtime_error("BASELINE3D_INVALID_MODEL_INPUT");
  }
  const double variance = k_b * k_b *
      (observation.pacc1_m * observation.pacc1_m + observation.pacc2_m * observation.pacc2_m);
  if (!std::isfinite(variance) || variance <= 0.0) {
    throw std::runtime_error("BASELINE3D_INVALID_VARIANCE");
  }
  Baseline3dModel model;
  model.predicted_m = multiply(cbn, makeVec3(0.0, -length_m, 0.0));
  model.residual_m = subtract(model.predicted_m, observation.ned_m);
  model.H = Matrix(3, RANK, 0.0);
  // stateFeedback left-multiplies Exp(phi); h-z = +[h]x phi to first order.
  setBlock(model.H, 0, PHI_ID, skew(model.predicted_m));
  model.R = scale(identityMatrix(3), variance);
  model.along_axis_residual_m = dot(model.predicted_m, model.residual_m) / norm(model.predicted_m);
  model.length_mismatch_m = norm(model.predicted_m) - norm(observation.ned_m);
  return model;
}

}  // namespace legsa_v23_port_core
