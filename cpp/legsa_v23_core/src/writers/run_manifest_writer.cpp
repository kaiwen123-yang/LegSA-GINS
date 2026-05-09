#include "legsa_v23_core/writers/run_manifest_writer.hpp"

#include <fstream>
#include <stdexcept>

namespace legsa_v23_core {

namespace {

// 中文说明：JSON 布尔值统一从 bool 输出，当前 N4H4A 禁用项必须全部为 false。
const char* boolText(bool value) { return value ? "true" : "false"; }

}  // namespace

// 中文说明：RUN_MANIFEST 是 claim-boundary 证据，不包含性能结论或 final_v23 输出替代。
// 中文说明：默认会写出 "phase": "N4H4A" 和 "solver_role": "legsa_v23_core_skeleton"。
void RunManifestWriter::write(const std::string& path, const GINSOptions& options) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open RUN_MANIFEST output: " + path);
  }

  output << "{\n";
  output << "  \"phase\": \"" << options.phase << "\",\n";
  output << "  \"solver_role\": \"" << options.solver_role << "\",\n";
  output << "  \"mechanization_predict_implemented\": " << boolText(options.mechanization_predict_implemented)
         << ",\n";
  output << "  \"measurement_update_implemented\": " << boolText(options.measurement_update_implemented)
         << ",\n";
  output << "  \"state_feedback_implemented\": " << boolText(options.state_feedback_implemented) << ",\n";
  output << "  \"position_update_implemented\": " << boolText(options.position_update_implemented) << ",\n";
  output << "  \"velocity_update_implemented\": " << boolText(options.velocity_update_implemented) << ",\n";
  output << "  \"yaw_update_implemented\": " << boolText(options.yaw_update_implemented) << ",\n";
  output << "  \"velocity_lever_correction\": " << boolText(options.velocity_lever_correction) << ",\n";
  output << "  \"yaw_H_mapping_conservative\": " << boolText(options.yaw_H_mapping_conservative) << ",\n";
  output << "  \"yaw_residual_sign\": \"" << options.yaw_residual_sign << "\",\n";
  output << "  \"yaw_normal_count\": " << options.yaw_normal_count << ",\n";
  output << "  \"yaw_downweight_count\": " << options.yaw_downweight_count << ",\n";
  output << "  \"yaw_reject_count\": " << options.yaw_reject_count << ",\n";
  output << "  \"propagation_count\": " << options.propagation_count << ",\n";
  output << "  \"measurement_update_count\": " << options.measurement_update_count << ",\n";
  output << "  \"position_update_count\": " << options.position_update_count << ",\n";
  output << "  \"velocity_update_count\": " << options.velocity_update_count << ",\n";
  output << "  \"yaw_update_count\": " << options.yaw_update_count << ",\n";
  output << "  \"rejected_update_count\": " << options.rejected_update_count << ",\n";
  output << "  \"diagnostic_mode\": " << boolText(options.diagnostic_mode) << ",\n";
  output << "  \"diagnostic_run_label\": \"" << options.diagnostic_run_label << "\",\n";
  output << "  \"diagnostic_model_variant\": \"" << options.diagnostic_model_variant << "\",\n";
  output << "  \"diagnostic_feedback_mode\": \"" << options.diagnostic_feedback_mode << "\",\n";
  output << "  \"diagnostic_update_block_mode\": \"" << options.diagnostic_update_block_mode << "\",\n";
  output << "  \"diagnostic_covariance_mode\": \"" << options.diagnostic_covariance_mode << "\",\n";
  output << "  \"debug_imu_error_feedback\": " << boolText(options.debug_imu_error_feedback) << ",\n";
  output << "  \"debug_imu_compensation\": " << boolText(options.debug_imu_compensation) << ",\n";
  output << "  \"debug_cross_covariance\": " << boolText(options.debug_cross_covariance) << ",\n";
  output << "  \"diagnostic_only\": " << boolText(options.diagnostic_only) << ",\n";
  output << "  \"diagnostic_update_switches\": {\n";
  output << "    \"disable_position_update\": " << boolText(options.disable_position_update) << ",\n";
  output << "    \"disable_velocity_update\": " << boolText(options.disable_velocity_update) << ",\n";
  output << "    \"disable_yaw_update\": " << boolText(options.disable_yaw_update) << ",\n";
  output << "    \"disable_measurement_update\": " << boolText(options.disable_measurement_update) << ",\n";
  output << "    \"disable_state_feedback\": " << boolText(options.disable_state_feedback) << "\n";
  output << "  },\n";
  output << "  \"not_for_performance_claim\": " << boolText(options.not_for_performance_claim) << ",\n";
  output << "  \"solver_output_changed_by_diagnostic_switches\": "
         << boolText(options.solver_output_changed_by_diagnostic_switches) << ",\n";
  output << "  \"solver_output_changed_by_diagnostic_variant\": "
         << boolText(options.solver_output_changed_by_diagnostic_variant) << ",\n";
  output << "  \"final_v23_reference_used_as_solver_input\": "
         << boolText(options.final_v23_reference_used_as_solver_input) << ",\n";
  output << "  \"proposed_reads_final_v23_output\": " << boolText(options.proposed_reads_final_v23_output)
         << ",\n";
  output << "  \"trace_solver_input\": " << boolText(options.trace_solver_input) << ",\n";
  output << "  \"raw_doppler\": " << boolText(options.factor_flags.raw_doppler) << ",\n";
  output << "  \"go2_prior\": " << boolText(options.factor_flags.go2_prior) << ",\n";
  output << "  \"lsim_oim\": " << boolText(options.factor_flags.lsim_oim) << ",\n";
  output << "  \"fgo\": " << boolText(options.factor_flags.fgo) << ",\n";
  output << "  \"fgo_feedback\": " << boolText(options.factor_flags.fgo_feedback) << ",\n";
  output << "  \"source_aware_weighting\": " << boolText(options.factor_flags.source_aware_weighting)
         << ",\n";
  output << "  \"output_only_correction\": " << boolText(options.factor_flags.output_only_correction)
         << ",\n";
  output << "  \"bad_epoch_deletion_for_metric\": "
         << boolText(options.factor_flags.bad_epoch_deletion_for_metric) << ",\n";
  output << "  \"numerical_performance_claim\": "
         << boolText(options.factor_flags.numerical_performance_claim) << ",\n";
  output << "  \"full_ekf_math_closed\": false,\n";
  output << "  \"final_v23_output_substitution\": false,\n";
  output << "  \"clean_input_provenance_label\": \"" << options.clean_input_provenance_label << "\"\n";
  output << "}\n";
}

}  // namespace legsa_v23_core
