// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N6A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: source-aware LSIM/OIM measurement weighting extension, not final_v23 output substitution.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：N6A trace 只作为 runtime-only 审计输出，不进入 solver 调权。
//
// LegSA-GINS N6A source-aware trace writer.
// 中文说明：trace 只写 runtime output，用于审计 R scale 是否真实进入 EKF 前置路径。

#include "legsa_v23_port_core/source_aware/source_aware_trace.hpp"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>

namespace legsa_v23_port_core::source_aware {
namespace {

std::string joinReasons(const std::vector<std::string>& reasons) {
  std::ostringstream stream;
  for (std::size_t i = 0; i < reasons.size(); ++i) {
    if (i > 0) {
      stream << "|";
    }
    stream << reasons[i];
  }
  return stream.str();
}

std::string escapeCsv(std::string value) {
  const bool quote = value.find_first_of(",\"\n") != std::string::npos;
  if (!quote) {
    return value;
  }
  std::string out = "\"";
  for (char ch : value) {
    if (ch == '"') {
      out.push_back('"');
    }
    out.push_back(ch);
  }
  out.push_back('"');
  return out;
}

double percentile(std::vector<double> values, double q) {
  if (values.empty()) {
    return 0.0;
  }
  std::sort(values.begin(), values.end());
  const double raw_index = q * static_cast<double>(values.size() - 1);
  const auto index = static_cast<std::size_t>(raw_index);
  return values[std::min(index, values.size() - 1)];
}

}  // namespace

void SourceAwareTrace::add(double time, std::size_t update_index, const SourceWeightResult& result) {
  rows_.push_back(SourceAwareTraceRow{time, update_index, result});
}

bool SourceAwareTrace::empty() const {
  return rows_.empty();
}

const std::vector<SourceAwareTraceRow>& SourceAwareTrace::rows() const {
  return rows_;
}

SourceAwareRuntimeStats SourceAwareTrace::stats() const {
  SourceAwareRuntimeStats out;
  std::array<std::vector<double>, kMeasurementSourceCount> scales;
  for (const auto& row : rows_) {
    const std::size_t index = sourceIndex(row.result.source);
    ++out.update_count_by_source[index];
    if (row.result.rejected) {
      ++out.reject_count_by_source[index];
    }
    scales[index].push_back(row.result.combined_R_scale);
  }
  for (std::size_t i = 0; i < kMeasurementSourceCount; ++i) {
    out.scale_p50_by_source[i] = percentile(scales[i], 0.50);
    out.scale_p95_by_source[i] = percentile(scales[i], 0.95);
    out.scale_max_by_source[i] = scales[i].empty() ? 0.0 : *std::max_element(scales[i].begin(), scales[i].end());
  }
  return out;
}

void SourceAwareTrace::writeCsv(const std::string& output_dir) const {
  if (rows_.empty()) {
    return;
  }
  std::filesystem::create_directories(output_dir);
  std::ofstream out(std::filesystem::path(output_dir) / "SOURCE_AWARE_WEIGHT_TRACE.csv");
  out << "time,update_index,source_id,mode,lsim_score,oim_score,lsim_R_scale,oim_R_scale,"
      << "combined_R_scale,residual_norm,normalized_innovation,base_R_trace,scaled_R_trace,"
      << "accepted,rejected,reason_codes,metadata_summary\n";
  out << std::fixed << std::setprecision(10);
  for (const auto& row : rows_) {
    const auto& result = row.result;
    out << row.time << "," << row.update_index << "," << toString(result.source) << ","
        << result.mode << "," << result.lsim_score << "," << result.oim_score << ","
        << result.lsim_R_scale << "," << result.oim_R_scale << "," << result.combined_R_scale << ","
        << result.residual_norm << "," << result.normalized_innovation << ","
        << result.base_R_trace << "," << result.scaled_R_trace << ","
        << (result.accepted ? 1 : 0) << "," << (result.rejected ? 1 : 0) << ","
        << escapeCsv(joinReasons(result.reason_codes)) << ","
        << escapeCsv(result.metadata_summary) << "\n";
  }
}

}  // namespace legsa_v23_port_core::source_aware
