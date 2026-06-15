// LegSA-GINS source-backed port file.
// Port role: PAPER10B2 multi-state QM runtime audit trace.
// Boundary: trace is runtime-only and not fed back into the solver.

#include "legsa_v23_port_core/source_aware/quality_state_trace.hpp"

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

void incrementState(QualityStateRuntimeStats& stats, MeasurementSource source, QualityState state) {
  const std::size_t index = sourceIndex(source);
  switch (state) {
    case QualityState::kNormal:
      ++stats.normal_count_by_source[index];
      break;
    case QualityState::kDownweight:
      ++stats.downweight_count_by_source[index];
      break;
    case QualityState::kReject:
      ++stats.reject_count_by_source[index];
      break;
    case QualityState::kHold:
      ++stats.hold_count_by_source[index];
      break;
    case QualityState::kRecovery:
      ++stats.recovery_count_by_source[index];
      break;
    case QualityState::kFallback:
      ++stats.fallback_count_by_source[index];
      break;
    default:
      break;
  }
}

}  // namespace

void QualityStateTrace::add(double time,
                            std::size_t update_index,
                            const SourceWeightResult& weight_result,
                            const QualityStateDecision& decision) {
  rows_.push_back(QualityStateTraceRow{time, update_index, weight_result, decision});
}

bool QualityStateTrace::empty() const {
  return rows_.empty();
}

std::size_t QualityStateTrace::rowCount() const {
  return rows_.size();
}

const std::vector<QualityStateTraceRow>& QualityStateTrace::rows() const {
  return rows_;
}

QualityStateRuntimeStats QualityStateTrace::stats() const {
  QualityStateRuntimeStats stats;
  stats.trace_row_count = rows_.size();
  for (const auto& row : rows_) {
    const std::size_t index = sourceIndex(row.decision.source);
    incrementState(stats, row.decision.source, row.decision.state);
    ++stats.action_count_by_source[index];
    if (row.decision.state_changed) {
      ++stats.state_transition_count;
    }
  }
  return stats;
}

void QualityStateTrace::writeCsv(const std::string& output_dir) const {
  if (rows_.empty()) {
    return;
  }
  std::filesystem::create_directories(output_dir);
  std::ofstream out(std::filesystem::path(output_dir) / "QM_STATE_ACTION_TRACE.csv");
  out << "time,update_index,source_id,previous_state,state,action,state_changed,action_alters_update,"
      << "accepted,rejected,r_scale_multiplier,source_aware_combined_R_scale,source_aware_lsim_R_scale,"
      << "source_aware_oim_R_scale,normalized_innovation,nis,dof,base_R_trace,scaled_R_trace,"
      << "anomaly_count,recovery_count,invalid_count,hold_remaining,fallback_remaining,source_health_score,"
      << "residual_category,go2_readiness_metadata_available,go2_motion_state,go2_readiness_score,"
      << "go2_readiness_flag,reason_codes,trace_used_online,final_v23_output_solver_input,"
      << "legsa_output_solver_input,no_per_case_tuning\n";
  out << std::fixed << std::setprecision(10);
  for (const auto& row : rows_) {
    const auto& weight = row.weight_result;
    const auto& decision = row.decision;
    out << row.time << "," << row.update_index << "," << toString(decision.source) << ","
        << toString(decision.previous_state) << "," << toString(decision.state) << ","
        << toString(decision.action) << "," << (decision.state_changed ? 1 : 0) << ","
        << (decision.action_alters_update ? 1 : 0) << "," << (decision.accepted ? 1 : 0) << ","
        << (decision.rejected ? 1 : 0) << "," << decision.r_scale_multiplier << ","
        << weight.combined_R_scale << "," << weight.lsim_R_scale << "," << weight.oim_R_scale << ","
        << weight.normalized_innovation << "," << weight.nis << "," << weight.dof << ","
        << weight.base_R_trace << "," << weight.scaled_R_trace << "," << decision.anomaly_count << ","
        << decision.recovery_count << "," << decision.invalid_count << "," << decision.hold_remaining << ","
        << decision.fallback_remaining << "," << decision.source_health_score << ","
        << escapeCsv(decision.residual_category) << ","
        << (weight.go2_readiness_metadata_available ? 1 : 0) << ","
        << escapeCsv(weight.go2_motion_state) << "," << weight.go2_readiness_score << ","
        << (weight.go2_readiness_flag ? 1 : 0) << ","
        << escapeCsv(joinReasons(decision.reason_codes)) << ","
        << (decision.trace_used_online ? 1 : 0) << ","
        << (decision.final_v23_output_solver_input ? 1 : 0) << ","
        << (decision.legsa_output_solver_input ? 1 : 0) << ","
        << (decision.no_per_case_tuning ? 1 : 0) << "\n";
  }
}

}  // namespace legsa_v23_port_core::source_aware
