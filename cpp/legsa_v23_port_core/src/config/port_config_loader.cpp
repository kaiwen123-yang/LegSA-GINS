// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/config/port_config_loader.hpp"

#include <fstream>
#include <sstream>
#include <stdexcept>

namespace legsa_v23_port_core {

// 中文说明：最小 key=value 配置读取；R1 不引入 YAML-cpp，也不读取 trace/final_v23 输出。
PortOptions PortConfigLoader::loadKeyValue(const std::string& path) {
  std::ifstream input(path);
  if (!input) {
    throw std::runtime_error("failed to open config: " + path);
  }
  PortOptions options;
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    const auto pos = line.find('=');
    if (pos == std::string::npos) {
      continue;
    }
    const std::string key = line.substr(0, pos);
    const std::string value = line.substr(pos + 1);
    if (key == "run_label") {
      options.run_label = value;
    }
  }
  return options;
}

}  // namespace legsa_v23_port_core

