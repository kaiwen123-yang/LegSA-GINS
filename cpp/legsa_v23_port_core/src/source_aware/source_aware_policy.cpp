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
#include <deque>
#include <sstream>
#include <utility>
#include <vector>

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

bool finiteStd(const Vec3& std_xyz) {
  return std::isfinite(std_xyz[0]) && std::isfinite(std_xyz[1]) && std::isfinite(std_xyz[2]) &&
         std_xyz[0] > 0.0 && std_xyz[1] > 0.0 && std_xyz[2] > 0.0;
}

double medianOf(std::vector<double> values) {
  if (values.empty()) {
    return 0.0;
  }
  std::sort(values.begin(), values.end());
  return values[values.size() / 2];
}

double medianAbsDeviation(const std::vector<double>& values, double center) {
  std::vector<double> deviations;
  deviations.reserve(values.size());
  for (double value : values) {
    deviations.push_back(std::fabs(value - center));
  }
  return medianOf(std::move(deviations));
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

double SourceAwarePolicy::sourceCap(MeasurementSource source) const {
  if (!n6bPolicyEnabled()) {
    return std::max(1.0, config_.source_aware_global_cap);
  }
  switch (source) {
    case MeasurementSource::kReceiverPosition:
      return std::max(1.0, config_.source_aware_receiver_position_cap);
    case MeasurementSource::kReceiverVelocity:
      return std::max(1.0, config_.source_aware_receiver_velocity_cap);
    case MeasurementSource::kDualAntennaYaw:
      return std::max(1.0, config_.source_aware_dual_yaw_cap);
    case MeasurementSource::kRawDopplerVelocity:
      return std::max(1.0, config_.source_aware_raw_doppler_cap);
  }
  return std::max(1.0, config_.source_aware_global_cap);
}

double SourceAwarePolicy::capScale(double value, MeasurementSource source) const {
  const double cap = std::min(std::max(1.0, config_.source_aware_global_cap), sourceCap(source));
  double scale_value = std::isfinite(value) ? value : cap;
  if (config_.source_aware_no_R_shrink) {
    scale_value = std::max(1.0, scale_value);
  }
  return std::min(std::max(1.0, scale_value), cap);
}

bool SourceAwarePolicy::n6bPolicyEnabled() const {
  return config_.source_aware_policy_version == "n6b_conservative_innovation_covariance";
}

void SourceAwarePolicy::applyRollingBaseline(MeasurementSource source,
                                             double normalized,
                                             SourceWeightResult& result) {
  if (!config_.source_aware_enable_rolling_innovation_baseline || !std::isfinite(normalized) || normalized <= 0.0) {
    return;
  }
  auto& history = rolling_normalized_by_source_[sourceIndex(source)];
  std::vector<double> values(history.begin(), history.end());
  if (!values.empty()) {
    const double med = medianOf(values);
    const double mad = std::max(config_.source_aware_rolling_mad_floor, medianAbsDeviation(values, med));
    result.rolling_normalized_median = med;
    result.rolling_normalized_mad = mad;
    result.relative_anomaly_score = std::max(0.0, (normalized - med) / mad);
    if (result.relative_anomaly_score > 3.0) {
      addReason(result, "oim_solver_visible_rolling_anomaly");
    }
  }
  history.push_back(normalized);
  const std::size_t window = std::max<std::size_t>(1, config_.source_aware_rolling_window_size);
  while (history.size() > window) {
    history.pop_front();
  }
}

double SourceAwarePolicy::lsimScale(const SourceMetadata& metadata, SourceWeightResult& result) const {
  // 中文说明：LSIM 是来源级质量度量，只使用观测源自身 metadata，不读取 residual、评价 trace 或输出误差。
  double scale_value = 1.0;
  const double std_max = maxStd(metadata.std_xyz);
  if (!n6bPolicyEnabled()) {
    if (!metadata.valid) {
      result.rejected = true;
      result.accepted = false;
      addReason(result, "lsim_invalid_source");
      return capScale(config_.source_aware_global_cap, metadata.source);
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
    if (metadata.source == MeasurementSource::kReceiverPosition && std_max > 5.0) {
      scale_value = std::max(scale_value, std::min(10.0, std_max / 0.5));
      addReason(result, "lsim_receiver_position_std_high");
    } else if (metadata.source == MeasurementSource::kReceiverVelocity && std_max > 0.6) {
      scale_value = std::max(scale_value, std::min(10.0, std_max / 0.1));
      addReason(result, "lsim_receiver_velocity_std_high");
    } else if (metadata.source == MeasurementSource::kDualAntennaYaw) {
      if (!metadata.rel_valid || !metadata.ant_valid || metadata.ant_state != "available") {
        scale_value = std::max(scale_value, 6.0);
        addReason(result, "lsim_dual_yaw_antenna_state_suspicious");
      }
      if (metadata.yaw_std_rad > 3.0 * D2R) {
        scale_value = std::max(scale_value, std::min(10.0, metadata.yaw_std_rad / (0.5 * D2R)));
        addReason(result, "lsim_dual_yaw_std_high");
      }
    } else if (metadata.source == MeasurementSource::kRawDopplerVelocity) {
      if (metadata.provider_status != "available") {
        result.rejected = true;
        result.accepted = false;
        addReason(result, "lsim_raw_doppler_provider_unavailable");
        return capScale(config_.source_aware_global_cap, metadata.source);
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
    }
    result.lsim_score = std::max(0.0, std::min(1.0, 1.0 / scale_value));
    return capScale(scale_value, metadata.source);
  }

  if (!metadata.valid) {
    result.accepted = false;
    result.rejected = true;
    addReason(result, "lsim_invalid_source");
    return capScale(sourceCap(metadata.source), metadata.source);
  }
  if (!metadata.covariance_available) {
    scale_value = std::max(scale_value, 1.5);
    addReason(result, "lsim_covariance_missing");
  }
  if (!finiteStd(metadata.std_xyz)) {
    scale_value = std::max(scale_value, 1.5);
    addReason(result, "lsim_std_nonfinite_or_missing");
  }
  if (std::fabs(metadata.time_diff_sec) > 0.08) {
    scale_value = std::max(scale_value, std::fabs(metadata.time_diff_sec) > 0.25 ? 2.5 : 1.5);
    addReason(result, "lsim_time_alignment_suspicious");
  }
  if (metadata.quality_flag != "nominal" && metadata.quality_flag != "available") {
    scale_value = std::max(scale_value, 1.5);
    addReason(result, "lsim_quality_flag_suspicious");
  }

  switch (metadata.source) {
    case MeasurementSource::kReceiverPosition:
      if (std_max > 50.0) {
        scale_value = std::max(scale_value, 5.0);
        addReason(result, "lsim_receiver_position_std_extreme");
      } else if (std_max > 25.0) {
        scale_value = std::max(scale_value, 2.0);
        addReason(result, "lsim_receiver_position_std_high");
      }
      break;
    case MeasurementSource::kReceiverVelocity:
      if (std_max > 6.0) {
        scale_value = std::max(scale_value, 4.0);
        addReason(result, "lsim_receiver_velocity_std_extreme");
      } else if (std_max > 3.0) {
        scale_value = std::max(scale_value, 2.0);
        addReason(result, "lsim_receiver_velocity_std_high");
      }
      break;
    case MeasurementSource::kDualAntennaYaw:
      if (!metadata.rel_valid || !metadata.ant_valid || metadata.ant_state != "available") {
        scale_value = std::max(scale_value, 2.0);
        addReason(result, "lsim_dual_yaw_antenna_state_suspicious");
      }
      if (metadata.yaw_std_rad > 30.0 * D2R) {
        scale_value = std::max(scale_value, 6.0);
        addReason(result, "lsim_dual_yaw_std_extreme");
      } else if (metadata.yaw_std_rad > 15.0 * D2R) {
        scale_value = std::max(scale_value, 2.0);
        addReason(result, "lsim_dual_yaw_std_high");
      }
      break;
    case MeasurementSource::kRawDopplerVelocity:
      if (metadata.provider_status != "available") {
        result.rejected = true;
        result.accepted = false;
        addReason(result, "lsim_raw_doppler_provider_unavailable");
        return capScale(sourceCap(metadata.source), metadata.source);
      }
      if (metadata.sat_count > 0 && metadata.sat_count < 5) {
        scale_value = std::max(scale_value, 3.0);
        addReason(result, "lsim_raw_doppler_sat_count_very_low");
      } else if (metadata.sat_count > 0 && metadata.sat_count < 8) {
        scale_value = std::max(scale_value, 1.5);
        addReason(result, "lsim_raw_doppler_sat_count_low");
      }
      if (std_max > 2.0) {
        scale_value = std::max(scale_value, 4.0);
        addReason(result, "lsim_raw_doppler_std_extreme");
      } else if (std_max > 1.0) {
        scale_value = std::max(scale_value, 2.0);
        addReason(result, "lsim_raw_doppler_std_high");
      }
      if (metadata.spike_candidate) {
        scale_value = std::max(scale_value, 1.25);
        addReason(result, "lsim_solver_visible_spike_candidate");
      }
      break;
  }
  result.lsim_score = std::max(0.0, std::min(1.0, 1.0 / scale_value));
  return capScale(scale_value, metadata.source);
}

double SourceAwarePolicy::oimScale(const SourceMetadata& metadata,
                                   const ObservationInnovation& innovation,
                                   SourceWeightResult& result) const {
  // 中文说明：N6B OIM 使用创新协方差 S=H*P*H^T+R 的 NIS，而不是直接 residual/R。
  // deadband 防止正常小残差被过度降权；N5D1 spike 时间只能事后审计，不能写入规则。
  double normalized = innovation.normalized_innovation;
  if (!std::isfinite(normalized) || normalized <= 0.0) {
    const double denom = std::sqrt(std::max(1.0e-12, innovation.base_R_trace + innovation.hph_trace));
    normalized = innovation.residual_norm / denom;
  }
  result.normalized_innovation = normalized;
  result.nis = innovation.nis;
  result.dof = innovation.dof;
  result.innovation_cov_trace = innovation.innovation_cov_trace;
  result.used_innovation_covariance = innovation.used_innovation_covariance;
  if (!n6bPolicyEnabled()) {
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
    return capScale(scale_value, metadata.source);
  }

  if (normalized <= config_.source_aware_deadband_normalized) {
    result.oim_score = 1.0;
    return 1.0;
  }
  const double delta = normalized - config_.source_aware_deadband_normalized;
  double alpha = 0.18;
  if (metadata.source == MeasurementSource::kRawDopplerVelocity) {
    alpha = 0.35;
  } else if (metadata.source == MeasurementSource::kDualAntennaYaw) {
    alpha = 0.25;
  }
  if (metadata.source == MeasurementSource::kReceiverPosition) {
    alpha = 0.00003;
  } else if (metadata.source == MeasurementSource::kReceiverVelocity) {
    alpha = 0.04;
  } else if (metadata.source == MeasurementSource::kDualAntennaYaw) {
    alpha = 0.03;
  }
  double scale_value = 1.0 + alpha * delta * delta;
  if (normalized > config_.source_aware_strong_normalized) {
    scale_value = std::max(scale_value, 1.0 + (alpha * 1.6) * delta * delta);
    addReason(result, "oim_strong_normalized_innovation");
  } else if (normalized > config_.source_aware_moderate_normalized) {
    scale_value = std::max(scale_value, 1.0 + (alpha * 1.2) * delta * delta);
    addReason(result, "oim_moderate_normalized_innovation");
  } else {
    addReason(result, "oim_mild_normalized_innovation");
  }
  if (metadata.source == MeasurementSource::kRawDopplerVelocity && normalized > 2.0) {
    addReason(result, "oim_raw_doppler_innovation_suspicious");
  }
  if (config_.source_aware_reject_extreme && normalized > 10.0) {
    result.rejected = true;
    result.accepted = false;
    addReason(result, "oim_extreme_reject");
  }
  result.oim_score = std::max(0.0, std::min(1.0, 1.0 / scale_value));
  return capScale(scale_value, metadata.source);
}

SourceWeightResult SourceAwarePolicy::evaluate(const SourceMetadata& metadata,
                                               const ObservationInnovation& innovation) {
  SourceWeightResult result;
  result.source = metadata.source;
  result.policy_version = config_.source_aware_policy_version;
  result.mode = config_.source_aware_mode;
  result.residual_norm = innovation.residual_norm;
  result.normalized_innovation = innovation.normalized_innovation;
  result.nis = innovation.nis;
  result.dof = innovation.dof;
  result.innovation_cov_trace = innovation.innovation_cov_trace;
  result.used_innovation_covariance = innovation.used_innovation_covariance;
  result.source_cap = sourceCap(metadata.source);
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
    applyRollingBaseline(metadata.source, result.normalized_innovation, result);
    // 中文说明：rolling baseline 只用 solver-visible 历史创新，不读取 trace；N6B 默认只记录相对异常诊断。
  }
  // 中文说明：source cap 防止正常源全部被打到 25；combined 只允许 R inflation，不允许 R shrink。
  result.combined_R_scale = capScale(std::max(result.lsim_R_scale, result.oim_R_scale), metadata.source);
  result.scaled_R_trace = result.base_R_trace * result.combined_R_scale;
  if (result.reason_codes.empty()) {
    result.reason_codes.push_back("nominal");
  }
  return result;
}

}  // namespace legsa_v23_port_core::source_aware
