// 中文说明：N4 mechanization 是基础可运行版本，不复制 KF-GINS，也不声明 final_v23 parity。
// English note: Propagation follows a simplified velocity -> position -> attitude order.

#pragma once

#include "legsa_gins/types/filter_types.hpp"
#include "legsa_gins/types/imu_types.hpp"

namespace legsa_gins::mechanization {

class InsMechanization {
 public:
  static types::LegSAFilterState compensateImuError(
      const types::LegSAFilterState& state,
      const types::LegSAImuSample& imu);

  static types::LegSAFilterState propagate(
      const types::LegSAFilterState& previous_state,
      const types::LegSAImuSample& imu_previous,
      const types::LegSAImuSample& imu_current);
};

}  // namespace legsa_gins::mechanization
