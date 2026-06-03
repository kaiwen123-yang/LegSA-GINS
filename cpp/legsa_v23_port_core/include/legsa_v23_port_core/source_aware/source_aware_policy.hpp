// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N6A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: source-aware LSIM/OIM measurement weighting extension, not final_v23 output substitution.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：N6A 在 source-backed port-core 上新增观测权重策略，不把 final_v23 输出作为 proposed 输入。
//
// LegSA-GINS N6A source-aware LSIM/OIM policy.
// 中文说明：策略只根据 solver 可见 metadata 和 innovation 放大 R，不读取 trace 或 final_v23 输出。

#pragma once

#include "legsa_v23_port_core/source_aware/measurement_source.hpp"

#include <array>
#include <deque>

namespace legsa_v23_port_core::source_aware {

class SourceAwarePolicy {
 public:
  explicit SourceAwarePolicy(SourceAwarePolicyConfig config);

  const SourceAwarePolicyConfig& config() const;
  bool enabledFor(MeasurementSource source) const;
  SourceWeightResult evaluate(const SourceMetadata& metadata, const ObservationInnovation& innovation);

 private:
  double sourceCap(MeasurementSource source) const;
  double capScale(double value, MeasurementSource source) const;
  bool n6bPolicyEnabled() const;
  void applyRollingBaseline(MeasurementSource source, double normalized, SourceWeightResult& result);
  double lsimScale(const SourceMetadata& metadata, SourceWeightResult& result) const;
  double methodFamilyOimScale(const SourceMetadata& metadata, double normalized, SourceWeightResult& result) const;
  double oimScale(const SourceMetadata& metadata,
                  const ObservationInnovation& innovation,
                  SourceWeightResult& result) const;

  SourceAwarePolicyConfig config_;
  std::array<std::deque<double>, kMeasurementSourceCount> rolling_normalized_by_source_;
};

}  // namespace legsa_v23_port_core::source_aware
