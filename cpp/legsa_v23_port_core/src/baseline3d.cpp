#include "legsa_v23_port_core/baseline3d.hpp"
#include "legsa_v23_port_core/common/earth.hpp"

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

void validateExternalCarrierCovariance(const Matrix3& covariance) {
  double max_abs = 0.0;
  for (const auto& row : covariance) for (double value : row) {
    if (!std::isfinite(value)) throw std::runtime_error("EXTERNAL_CARRIER_NONFINITE_COVARIANCE");
    max_abs = std::max(max_abs, std::fabs(value));
  }
  if (!(max_abs > 0.0)) throw std::runtime_error("EXTERNAL_CARRIER_COVARIANCE_NOT_SPD");
  Matrix3 lower{};
  for (std::size_t i = 0; i < 3; ++i) for (std::size_t j = 0; j <= i; ++j) {
    if (std::fabs(covariance[i][j] - covariance[j][i]) > 1e-12 * max_abs)
      throw std::runtime_error("EXTERNAL_CARRIER_COVARIANCE_NOT_SYMMETRIC");
    double value = covariance[i][j];
    for (std::size_t k = 0; k < j; ++k) value -= lower[i][k] * lower[j][k];
    if (i == j) {
      if (!(value > 0.0)) throw std::runtime_error("EXTERNAL_CARRIER_COVARIANCE_NOT_SPD");
      lower[i][j] = std::sqrt(value);
    } else lower[i][j] = value / lower[j][j];
  }
}

Baseline3dModel buildExternalCarrierBaseline3dModel(
    const Matrix3& cbn, const Vec3& blh_rad_m,
    const Baseline3dMeasurement& observation, const Vec3& body_vector_m) {
  if (!observation.valid || observation.source != "external_carrier")
    throw std::runtime_error("EXTERNAL_CARRIER_INVALID_MODEL_SOURCE");
  for (const auto& vector : {observation.ecef_m, body_vector_m, blh_rad_m})
    for (double value : vector) if (!std::isfinite(value))
      throw std::runtime_error("EXTERNAL_CARRIER_NONFINITE_MODEL_INPUT");
  if (!(norm(body_vector_m) > 0.0) || !(norm(observation.ecef_m) > 0.0))
    throw std::runtime_error("EXTERNAL_CARRIER_ZERO_BASELINE");
  validateExternalCarrierCovariance(observation.covariance_ecef_m2);
  // Earth::cne maps NED -> ECEF; vectors need rotation, not translation.
  const auto cen = transpose(Earth::cne(blh_rad_m));
  const Vec3 observed_ned = multiply(cen, observation.ecef_m);
  const auto covariance_ned = multiply(multiply(cen, observation.covariance_ecef_m2), transpose(cen));
  Baseline3dModel model;
  model.predicted_m = multiply(cbn, body_vector_m);
  model.residual_m = subtract(model.predicted_m, observed_ned);
  model.H = Matrix(3, RANK, 0.0);
  setBlock(model.H, 0, PHI_ID, skew(model.predicted_m));
  model.R = Matrix(3, 3, 0.0);
  setBlock(model.R, 0, 0, covariance_ned);
  model.along_axis_residual_m = dot(model.predicted_m, model.residual_m) / norm(model.predicted_m);
  model.length_mismatch_m = norm(model.predicted_m) - norm(observed_ned);
  return model;
}

}  // namespace legsa_v23_port_core
