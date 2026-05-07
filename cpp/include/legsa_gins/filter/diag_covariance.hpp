// 中文说明：N4 只实现 diagonal covariance foundation，不声明完整 full covariance EKF。
// English note: Scalar gains are enough for the receiver-native toy filter.

#pragma once

#include "legsa_gins/types/filter_types.hpp"

namespace legsa_gins::filter {

types::DiagCovariance21 makeConservativeDefaultCovariance();
void ensureCovariancePositive(const types::DiagCovariance21& covariance);
double scalarKalmanGain(double prior_var, double measurement_var);
double posteriorVariance(double prior_var, double measurement_var);
void resetErrorState(types::ErrorState21& error_state);

}  // namespace legsa_gins::filter
