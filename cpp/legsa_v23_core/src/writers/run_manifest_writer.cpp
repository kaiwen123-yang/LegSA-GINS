#include "legsa_v23_core/writers/run_manifest_writer.hpp"

#include <fstream>
#include <stdexcept>

namespace legsa_v23_core {

namespace {

// 中文说明：JSON 布尔值统一从 bool 输出，当前 N4H4A 禁用项必须全部为 false。
const char* boolText(bool value) { return value ? "true" : "false"; }

}  // namespace

// 中文说明：RUN_MANIFEST 是 claim-boundary 证据，不包含性能结论或 final_v23 输出替代。
void RunManifestWriter::write(const std::string& path, const GINSOptions& options) {
  std::ofstream output(path);
  if (!output) {
    throw std::runtime_error("failed to open RUN_MANIFEST output: " + path);
  }

  output << "{\n";
  output << "  \"phase\": \"N4H4A\",\n";
  output << "  \"solver_role\": \"legsa_v23_core_skeleton\",\n";
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
