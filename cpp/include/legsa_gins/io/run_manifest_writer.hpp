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
};

}  // namespace legsa_gins::io
