// 中文说明：LegSAFilter 是 N4 首个自主持有的 proposed C++ filter core；只做 toy-run 基础更新。
// English note: No raw Doppler, Go2 priors, source-aware weighting, or FGO are implemented here.

#pragma once

#include <vector>

#include "legsa_gins/types/filter_types.hpp"
#include "legsa_gins/types/imu_types.hpp"
#include "legsa_gins/types/nav_types.hpp"

namespace legsa_gins::filter {

class LegSAFilter {
 public:
  void initialize(
      const types::LegSAFilterState& initial_state,
      const types::DiagCovariance21& initial_covariance);

  void predict(
      const types::LegSAImuSample& imu_previous,
      const types::LegSAImuSample& imu_current);
  void update(const types::ReceiverNativeMeasurement& measurement);
  void process(
      const std::vector<types::LegSAImuSample>& imu_samples,
      const std::vector<types::ReceiverNativeMeasurement>& receiver_measurements);

  types::LegSAFilterState getState() const;
  types::DiagCovariance21 getCovariance() const;
  const std::vector<types::LegSAFilterState>& getHistory() const;
  types::NavState getNavState() const;
  types::StdState getStdState() const;

 private:
  types::LegSAFilterState state_{};
  types::DiagCovariance21 covariance_{};
  types::ErrorState21 error_state_{};
  std::vector<types::LegSAFilterState> history_;
  bool initialized_ = false;
};

}  // namespace legsa_gins::filter
