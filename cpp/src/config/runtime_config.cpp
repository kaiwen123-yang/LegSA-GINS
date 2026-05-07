// 中文说明：RuntimeConfig 是配置骨架；final_v23_is_proposed 与 proposed_reads_final_v23_output 必须保持 false，高级因子默认关闭。
// English note: comments define module responsibility and safety boundaries only.

#include "legsa_gins/config/runtime_config.hpp"

namespace legsa_gins::config {

RuntimeConfig defaultRuntimeConfig() { return RuntimeConfig{}; }

RuntimeConfig loadRuntimeConfigPlaceholder(const std::string& /*config_path*/) {
  // 配置加载器仍是占位实现，不能把高级因子或 final_v23 读取路径偷偷打开。
  // Placeholder loading must not silently enable advanced factors or final_v23 reads.
  return defaultRuntimeConfig();
}

}  // namespace legsa_gins::config
