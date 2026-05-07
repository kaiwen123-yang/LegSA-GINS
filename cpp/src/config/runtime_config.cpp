#include "legsa_gins/config/runtime_config.hpp"

namespace legsa_gins::config {

RuntimeConfig defaultRuntimeConfig() { return RuntimeConfig{}; }

RuntimeConfig loadRuntimeConfigPlaceholder(const std::string& /*config_path*/) {
  return defaultRuntimeConfig();
}

}  // namespace legsa_gins::config
