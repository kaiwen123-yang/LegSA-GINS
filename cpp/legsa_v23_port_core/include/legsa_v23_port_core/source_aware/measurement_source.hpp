// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N6A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: source-aware LSIM/OIM measurement weighting extension, not final_v23 output substitution.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：N6A 在 source-backed port-core 上新增观测权重策略，不把 final_v23 输出作为 proposed 输入。
//
// LegSA-GINS N6A source-aware weighting support.
// Boundary: solver-visible metadata and innovation only; no trace/final_v23 output tuning.
// 中文说明：本文件定义 N6A source-aware LSIM/OIM 的观测源、元数据和结果结构。

#pragma once

#include "legsa_v23_port_core/types.hpp"

#include <array>
#include <cstddef>
#include <string>
#include <vector>

namespace legsa_v23_port_core::source_aware {

enum class MeasurementSource : std::size_t {
  kReceiverPosition = 0,
  kReceiverVelocity = 1,
  kDualAntennaYaw = 2,
  kRawDopplerVelocity = 3,
};

constexpr std::size_t kMeasurementSourceCount = 4;

const char* toString(MeasurementSource source);
MeasurementSource measurementSourceFromString(const std::string& value);
std::size_t sourceIndex(MeasurementSource source);

struct SourceMetadata {
  MeasurementSource source = MeasurementSource::kReceiverPosition;
  double time = 0.0;
  bool valid = true;
  Vec3 std_xyz = makeVec3(1.0, 1.0, 1.0);
  double yaw_std_rad = D2R;
  double residual_norm = 0.0;
  double time_diff_sec = 0.0;
  std::size_t sat_count = 0;
  std::string provider_status = "available";
  std::string quality_flag = "nominal";
  bool covariance_available = true;
  bool rel_valid = true;
  bool ant_valid = true;
  std::string ant_state = "available";
  double baseline_length_m = 0.0;
  double rel_acc_m = 0.0;
  bool spike_candidate = false;
};

struct ObservationInnovation {
  std::vector<double> residual;
  double residual_norm = 0.0;
  double base_R_trace = 0.0;
  double hph_trace = 0.0;
  double normalized_innovation = 0.0;
};

struct SourceWeightResult {
  MeasurementSource source = MeasurementSource::kReceiverPosition;
  std::string mode = "off";
  double lsim_score = 1.0;
  double oim_score = 1.0;
  double lsim_R_scale = 1.0;
  double oim_R_scale = 1.0;
  double combined_R_scale = 1.0;
  double residual_norm = 0.0;
  double normalized_innovation = 0.0;
  double base_R_trace = 0.0;
  double scaled_R_trace = 0.0;
  bool accepted = true;
  bool rejected = false;
  std::vector<std::string> reason_codes;
  std::string metadata_summary;
};

struct SourceAwareSourceConfig {
  bool enabled = true;
  bool lsim_enabled = true;
  bool oim_enabled = true;
};

struct SourceAwarePolicyConfig {
  bool enable_source_aware_weighting = false;
  std::string source_aware_mode = "off";
  double source_aware_max_R_scale = 25.0;
  bool source_aware_reject_extreme = false;
  bool source_aware_no_R_shrink = true;
  bool source_aware_trace_enabled = true;
  std::array<SourceAwareSourceConfig, kMeasurementSourceCount> sources{};
};

struct SourceAwareRuntimeStats {
  std::array<std::size_t, kMeasurementSourceCount> update_count_by_source{};
  std::array<std::size_t, kMeasurementSourceCount> reject_count_by_source{};
  std::array<double, kMeasurementSourceCount> scale_p50_by_source{};
  std::array<double, kMeasurementSourceCount> scale_p95_by_source{};
  std::array<double, kMeasurementSourceCount> scale_max_by_source{};
  bool spike_response_evaluated = false;
};

}  // namespace legsa_v23_port_core::source_aware
