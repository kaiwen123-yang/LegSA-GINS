// 中文说明：writer 只写合同化输出给后续验证或 evaluator；不做 output-only correction，不删除 bad epochs，也不参与 solver。
// English note: comments define module responsibility and safety boundaries only.

#include "legsa_gins/io/run_manifest_writer.hpp"

#include <fstream>
#include <stdexcept>

namespace legsa_gins::io {
namespace {

std::string jsonBool(bool value) { return value ? "true" : "false"; }

std::string jsonEscape(const std::string& value) {
  std::string escaped;
  escaped.reserve(value.size());
  for (const char ch : value) {
    if (ch == '"' || ch == '\\') {
      escaped.push_back('\\');
    }
    escaped.push_back(ch);
  }
  return escaped;
}

void writeFactorArray(std::ofstream& stream, const factors::FactorRegistry& registry) {
  // Manifest 只记录开关状态，不声明任何因子 residual 已经完成。
  // The manifest records registry flags only, not implemented residuals.
  const auto kinds = registry.enabledKinds();
  stream << "  \"enabled_factors\": [";
  for (std::size_t index = 0; index < kinds.size(); ++index) {
    if (index > 0) {
      stream << ", ";
    }
    stream << '"' << factors::toString(kinds[index]) << '"';
  }
  stream << "],\n";
}

}  // namespace

std::filesystem::path RunManifestWriter::writePlaceholder(
    const config::RuntimeConfig& config,
    const factors::FactorRegistry& registry,
    const std::filesystem::path& output_dir) {
  std::filesystem::create_directories(output_dir);
  const auto path = output_dir / "RUN_MANIFEST.json";
  std::ofstream stream(path);
  if (!stream) {
    throw std::runtime_error("Failed to open RUN_MANIFEST output: " + path.string());
  }

  stream << "{\n";
  stream << "  \"phase\": \"N3A\",\n";
  stream << "  \"algorithm_role\": \"" << jsonEscape(config.algorithm_role) << "\",\n";
  stream << "  \"algorithm_name\": \"" << jsonEscape(config.algorithm_name) << "\",\n";
  stream << "  \"dataset_name\": \"" << jsonEscape(config.dataset_name) << "\",\n";
  stream << "  \"output_dir\": \"" << jsonEscape(output_dir.string()) << "\",\n";
  stream << "  \"dry_run\": " << jsonBool(config.dry_run) << ",\n";
  stream << "  \"final_v23_is_proposed\": "
         << jsonBool(config.final_v23_is_proposed) << ",\n";
  stream << "  \"proposed_reads_final_v23_output\": "
         << jsonBool(config.proposed_reads_final_v23_output) << ",\n";
  // final_v23 边界必须在 manifest 中显式保留，防止 baseline 污染 proposed。
  // Keep final_v23 boundary flags explicit to avoid baseline/proposed contamination.
  writeFactorArray(stream, registry);
  stream << "  \"raw_data_committed\": false,\n";
  stream << "  \"numerical_performance_claim\": false,\n";
  stream << "  \"evidence_status\": \"evidence_missing\",\n";
  stream << "  \"runtime_status\": \"cpp_runtime_skeleton_only\"\n";
  stream << "}\n";
  return path;
}

std::filesystem::path RunManifestWriter::writeFilterCoreToyManifest(
    const config::RuntimeConfig& config,
    const std::filesystem::path& output_dir) {
  std::filesystem::create_directories(output_dir);
  const auto path = output_dir / "RUN_MANIFEST.json";
  std::ofstream stream(path);
  if (!stream) {
    throw std::runtime_error("Failed to open RUN_MANIFEST output: " + path.string());
  }

  // N4 toy filter manifest 明确禁止高级因子和性能 claim，避免 demo 输出被过度解释。
  // The N4 toy manifest keeps all advanced-factor and performance flags false.
  stream << "{\n";
  stream << "  \"phase\": \"N4\",\n";
  stream << "  \"algorithm_role\": \"proposed\",\n";
  stream << "  \"algorithm_name\": \"LegSA-GINS-filter-core\",\n";
  stream << "  \"dataset_name\": \"" << jsonEscape(config.dataset_name) << "\",\n";
  stream << "  \"output_dir\": \"" << jsonEscape(output_dir.string()) << "\",\n";
  stream << "  \"dry_filter_demo\": true,\n";
  stream << "  \"final_v23_is_proposed\": false,\n";
  stream << "  \"proposed_reads_final_v23_output\": false,\n";
  stream << "  \"final_v23_output_substitution\": false,\n";
  stream << "  \"trace_solver_input\": false,\n";
  stream << "  \"trace_used_for_tuning\": false,\n";
  stream << "  \"output_only_correction\": false,\n";
  stream << "  \"bad_epoch_deletion_for_metric\": false,\n";
  stream << "  \"raw_data_committed\": false,\n";
  stream << "  \"raw_doppler_claim\": false,\n";
  stream << "  \"go2_prior_claim\": false,\n";
  stream << "  \"source_aware_weighting_claim\": false,\n";
  stream << "  \"fgo_smoother_claim\": false,\n";
  stream << "  \"numerical_performance_claim\": false,\n";
  stream << "  \"evidence_status\": \"filter_core_toy_only_no_performance_claim\"\n";
  stream << "}\n";
  return path;
}

}  // namespace legsa_gins::io
