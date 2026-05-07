// 中文说明：writer 只写合同化输出给后续验证或 evaluator；不做 output-only correction，不删除 bad epochs，也不参与 solver。
// English note: comments define module responsibility and safety boundaries only.

#pragma once

#include <filesystem>

#include "legsa_gins/config/runtime_config.hpp"
#include "legsa_gins/factors/factor_registry.hpp"

namespace legsa_gins::io {

class RunManifestWriter {
 public:
  static std::filesystem::path writePlaceholder(
      const config::RuntimeConfig& config,
      const factors::FactorRegistry& registry,
      const std::filesystem::path& output_dir);
  static std::filesystem::path writeFilterCoreToyManifest(
      const config::RuntimeConfig& config,
      const std::filesystem::path& output_dir);
};

}  // namespace legsa_gins::io
