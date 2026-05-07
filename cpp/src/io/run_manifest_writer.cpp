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
  writeFactorArray(stream, registry);
  stream << "  \"raw_data_committed\": false,\n";
  stream << "  \"numerical_performance_claim\": false,\n";
  stream << "  \"evidence_status\": \"evidence_missing\",\n";
  stream << "  \"runtime_status\": \"cpp_runtime_skeleton_only\"\n";
  stream << "}\n";
  return path;
}

}  // namespace legsa_gins::io
