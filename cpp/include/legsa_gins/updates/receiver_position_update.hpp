// 中文说明：receiver-native position update 是 N4 backbone update，不使用 trace，不做 output-only correction。
// English note: Raw GNSS and advanced factors remain future work.

#pragma once

#include "legsa_gins/types/filter_types.hpp"

namespace legsa_gins::updates {

void applyReceiverPositionUpdate(
    types::LegSAFilterState& state,
    types::DiagCovariance21& covariance,
    types::ErrorState21& error_state,
    const types::ReceiverNativeMeasurement& meas);

}  // namespace legsa_gins::updates
