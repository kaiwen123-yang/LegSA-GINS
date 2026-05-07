// 中文说明：receiver-native velocity update 是 N4 基础更新，不实现 source-aware weighting。
// English note: Velocity residuals use predicted minus measured velocity.

#pragma once

#include "legsa_gins/types/filter_types.hpp"

namespace legsa_gins::updates {

void applyReceiverVelocityUpdate(
    types::LegSAFilterState& state,
    types::DiagCovariance21& covariance,
    types::ErrorState21& error_state,
    const types::ReceiverNativeMeasurement& meas);

}  // namespace legsa_gins::updates
