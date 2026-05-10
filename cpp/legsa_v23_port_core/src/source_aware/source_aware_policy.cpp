// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N6A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: source-aware LSIM/OIM measurement weighting extension, not final_v23 output substitution.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：N6A 在 source-backed port-core 上新增观测权重策略，不把 final_v23 输出作为 proposed 输入。
//
// LegSA-GINS N6A source-aware LSIM/OIM policy implementation.
// 中文说明：N6A 默认只做保守 R inflation，不做 R shrink，不用 trace/final_v23 output 调权。

#include "legsa_v23_port_core/source_aware/source_aware_policy.hpp"

#include <algorithm>
#include <cmath>
#include <sstream>
#include <utility>

namespace legsa_v23_port_core::source_aware {
namespace {

bool modeAllowsLsim(const std::string& mode) {
  return mode == "lsim_only" || mode == "lsim_oim";
}

bool modeAllowsOim(const std::string& mode) {
  return mode == "oim_only" || mode == "lsim_oim";
}

void addReason(SourceWeightResult& result, const std::string& reason) {
  result.reason_codes.push_back(reason);
}

double maxStd(const Vec3& std_xyz) {
  return std::max({std::fabs(std_xyz[0]), std::fabs(std_xyz[1]), std::fabs(std_xyz[2])});
}

std::string metadataSummary(const SourceMetadata& metadata) {
  std::ostringstream stream;
  stream << "valid=" << (metadata.valid ? "true" : "false")
         << ";std=(" << metadata.std_xyz[0] << "/" << metadata.std_xyz[1] << "/" << metadata.std_xyz[2] << ")"
         << ";yaw_std_rad=" << metadata.yaw_std_rad
         << ";sat_count=" << metadata.sat_count
         << ";provider_status=" << metadata.provider_status
         << ";quality_flag=" << metadata.quality_flag
         << ";time_diff_sec=" << metadata.time_diff_sec
         << ";covariance_available=" << (metadata.covariance_available ? "true" : "false");
  return stream.str();
}

}  // namespace

const char* toString(MeasurementSource source) {
  switch (source) {
    case MeasurementSource::kReceiverPosition:
      return "receiver_position";
    case MeasurementSource::kReceiverVelocity:
      return "receiver_velocity";
    case MeasurementSource::kDualAntennaYaw:
      return "dual_antenna_yaw";
    case MeasurementSource::kRawDopplerVelocity:
      return "raw_doppler_velocity";
  }
  return "unknown";
}

MeasurementSource measurementSourceFromString(const std::string& value) {
  if (value == "receiver_velocity") {
    return MeasurementSource::kReceiverVelocity;
  }
  if (value == "dual_antenna_yaw" || value == "dual_yaw") {
    return MeasurementSource::kDualAntennaYaw;
  }
  if (value == "raw_doppler_velocity") {
    return MeasurementSource::kRawDopplerVelocity;
  }
  return MeasurementSource::kReceiverPosition;
}

std::size_t sourceIndex(MeasurementSource source) {
  return static_cast<std::size_t>(source);
}

SourceAwarePolicy::SourceAwarePolicy(SourceAwarePolicyConfig config) : config_(std::move(config)) {}

const SourceAwarePolicyConfig& SourceAwarePolicy::config() const {
  return config_;
}

bool SourceAwarePolicy::enabledFor(MeasurementSource source) const {
  if (!config_.enable_source_aware_weighting || config_.source_aware_mode == "off") {
    return false;
  }
  return config_.sources[sourceIndex(source)].enabled;
}

double SourceAwarePolicy::capScale(double value) const {
  double scale_value = std::isfinite(value) ? value : config_.source_aware_max_R_scale;
  if (config_.source_aware_no_R_shrink) {
    scale_value = std::max(1.0, scale_value);
  }
  return std::min(std::max(1.0, scale_value), std::max(1.0, config_.source_aware_max_R_scale));
}

double SourceAwarePolicy::lsimScale(const SourceMetadata& metadata, SourceWeightResult& result) const {
  // 中文说明：LSIM 是来源级质量度量，只使用观测源自身 metadata，不读取评价 trace。
  double scale_value = 1.0;
  const double std_max = maxStd(metadata.std_xyz);
  if (!metadata.valid) {
    result.rejected = true;
    result.accepted = false;
    addReason(result, "lsim_invalid_source");
    return config_.source_aware_max_R_scale;
  }
  if (!metadata.covariance_available) {
    scale_value = std::max(scale_value, 4.0);
    addReason(result, "lsim_covariance_missing");
  }
  if (std::fabs(metadata.time_diff_sec) > 0.08) {
    scale_value = std::max(scale_value, 3.0);
    addReason(result, "lsim_time_alignment_suspicious");
  }
  if (metadata.quality_flag != "nominal" && metadata.quality_flag != "available") {
    scale_value = std::max(scale_value, 2.0);
    addReason(result, "lsim_quality_flag_suspicious");
  }

  switch (metadata.source) {
    case MeasurementSource::kReceiverPosition:
      if (std_max > 5.0) {
        scale_value = std::max(scale_value, std::min(10.0, std_max / 0.5));
        addReason(result, "lsim_receiver_position_std_high");
      }
      break;
    case MeasurementSource::kReceiverVelocity:
      if (std_max > 0.6) {
        scale_value = std::max(scale_value, std::min(10.0, std_max / 0.1));
        addReason(result, "lsim_receiver_velocity_std_high");
      }
      break;
    case MeasurementSource::kDualAntennaYaw:
      if (!metadata.rel_valid || !metadata.ant_valid || metadata.ant_state != "available") {
        scale_value = std::max(scale_value, 6.0);
        addReason(result, "lsim_dual_yaw_antenna_state_suspicious");
      }
      if (metadata.yaw_std_rad > 3.0 * D2R) {
        scale_value = std::max(scale_value, std::min(10.0, metadata.yaw_std_rad / (0.5 * D2R)));
        addReason(result, "lsim_dual_yaw_std_high");
      }
      break;
    case MeasurementSource::kRawDopplerVelocity:
      if (metadata.provider_status != "available") {
        result.rejected = true;
        result.accepted = false;
        addReason(result, "lsim_raw_doppler_provider_unavailable");
        return config_.source_aware_max_R_scale;
      }
      if (metadata.sat_count > 0 && metadata.sat_count < 8) {
        scale_value = std::max(scale_value, 4.0);
        addReason(result, "lsim_raw_doppler_sat_count_low");
      }
      if (std_max > 0.5) {
        scale_value = std::max(scale_value, std::min(10.0, std_max / 0.05));
        addReason(result, "lsim_raw_doppler_std_high");
      }
      if (metadata.spike_candidate) {
        scale_value = std::max(scale_value, 2.0);
        addReason(result, "lsim_solver_visible_spike_candidate");
      }
      break;
  }
  result.lsim_score = std::max(0.0, std::min(1.0, 1.0 / scale_value));
  return capScale(scale_value);
}

double SourceAwarePolicy::oimScale(const SourceMetadata& metadata,
                                   const ObservationInnovation& innovation,
                                   SourceWeightResult& result) const {
  // 中文说明：OIM 是 innovation/R 一致性度量；N5D1 spike 时间只能事后审计，不能写入规则。
  double normalized = innovation.normalized_innovation;
  if (!std::isfinite(normalized) || normalized <= 0.0) {
    const double denom = std::sqrt(std::max(1.0e-12, innovation.base_R_trace + innovation.hph_trace));
    normalized = innovation.residual_norm / denom;
  }
  result.normalized_innovation = normalized;
  if (normalized <= 1.5) {
    result.oim_score = 1.0;
    return 1.0;
  }
  double scale_value = 1.0 + (normalized - 1.5) * (normalized - 1.5);
  if (normalized > 3.0) {
    scale_value = std::max(scale_value, normalized * normalized / 3.0);
    addReason(result, "oim_high_normalized_innovation");
  }
  if (metadata.source == MeasurementSource::kRawDopplerVelocity && normalized > 2.0) {
    addReason(result, "oim_raw_doppler_innovation_suspicious");
  }
  if (config_.source_aware_reject_extreme && normalized > 8.0) {
    result.rejected = true;
    result.accepted = false;
    addReason(result, "oim_extreme_reject");
  }
  result.oim_score = std::max(0.0, std::min(1.0, 1.0 / scale_value));
  return capScale(scale_value);
}

SourceWeightResult SourceAwarePolicy::evaluate(const SourceMetadata& metadata,
                                               const ObservationInnovation& innovation) const {
  SourceWeightResult result;
  result.source = metadata.source;
  result.mode = config_.source_aware_mode;
  result.residual_norm = innovation.residual_norm;
  result.normalized_innovation = innovation.normalized_innovation;
  result.base_R_trace = innovation.base_R_trace;
  result.metadata_summary = metadataSummary(metadata);
  const auto& source_config = config_.sources[sourceIndex(metadata.source)];
  if (!enabledFor(metadata.source)) {
    result.mode = "off";
    result.reason_codes.push_back("source_aware_disabled");
    result.scaled_R_trace = innovation.base_R_trace;
    return result;
  }
  if (modeAllowsLsim(config_.source_aware_mode) && source_config.lsim_enabled) {
    result.lsim_R_scale = lsimScale(metadata, result);
  }
  if (modeAllowsOim(config_.source_aware_mode) && source_config.oim_enabled) {
    result.oim_R_scale = oimScale(metadata, innovation, result);
  }
  result.combined_R_scale = capScale(std::max(result.lsim_R_scale, result.oim_R_scale));
  result.scaled_R_trace = result.base_R_trace * result.combined_R_scale;
  if (result.reason_codes.empty()) {
    result.reason_codes.push_back("nominal");
  }
  return result;
}

}  // namespace legsa_v23_port_core::source_aware
