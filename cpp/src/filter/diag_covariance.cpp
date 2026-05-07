// 中文说明：对角协方差工具用于 N4 可运行骨架，不代表 full EKF matrix 已完成。
// English note: Variances must remain positive and finite.

#include "legsa_gins/filter/diag_covariance.hpp"

#include <cmath>
#include <stdexcept>

namespace legsa_gins::filter {

types::DiagCovariance21 makeConservativeDefaultCovariance() {
  types::DiagCovariance21 covariance;
  covariance.diag.fill(1.0);
  covariance.diag[types::P_ID + 0] = 25.0;
  covariance.diag[types::P_ID + 1] = 25.0;
  covariance.diag[types::P_ID + 2] = 36.0;
  covariance.diag[types::V_ID + 0] = 1.0;
  covariance.diag[types::V_ID + 1] = 1.0;
  covariance.diag[types::V_ID + 2] = 1.0;
  covariance.diag[types::PHI_ID + 0] = 0.05 * 0.05;
  covariance.diag[types::PHI_ID + 1] = 0.05 * 0.05;
  covariance.diag[types::PHI_ID + 2] = 0.10 * 0.10;
  return covariance;
}

void ensureCovariancePositive(const types::DiagCovariance21& covariance) {
  for (double value : covariance.diag) {
    if (value <= 0.0 || !std::isfinite(value)) {
      throw std::runtime_error("Diagonal covariance variance must be positive.");
    }
  }
}

double scalarKalmanGain(double prior_var, double measurement_var) {
  if (prior_var <= 0.0 || measurement_var <= 0.0 || !std::isfinite(prior_var) ||
      !std::isfinite(measurement_var)) {
    throw std::runtime_error("Kalman gain requires positive finite variances.");
  }
  return prior_var / (prior_var + measurement_var);
}

double posteriorVariance(double prior_var, double measurement_var) {
  const double gain = scalarKalmanGain(prior_var, measurement_var);
  return (1.0 - gain) * prior_var;
}

void resetErrorState(types::ErrorState21& error_state) { error_state.dx.fill(0.0); }

}  // namespace legsa_gins::filter
