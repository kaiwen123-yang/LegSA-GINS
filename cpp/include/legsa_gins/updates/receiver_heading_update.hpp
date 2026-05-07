// 中文说明：receiver-native heading update 不是 self raw heading；raw dual-antenna heading 留给 future。
// English note: Heading update does not use final_v23 yaw output or trace tuning.

#pragma once

#include "legsa_gins/types/filter_types.hpp"

namespace legsa_gins::updates {

void applyReceiverHeadingUpdate(
    types::LegSAFilterState& state,
    types::DiagCovariance21& covariance,
    types::ErrorState21& error_state,
    const types::ReceiverNativeMeasurement& meas);

}  // namespace legsa_gins::updates
