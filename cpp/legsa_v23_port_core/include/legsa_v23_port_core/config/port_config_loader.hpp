// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/options.hpp"

#include <string>

namespace legsa_v23_port_core {

// 中文说明：R2 config reader 支持 KF-GINS 常用单位转换；完整 YAML parity 留给 R3。
class PortConfigLoader {
 public:
  static PortOptions loadKeyValue(const std::string& path);
  static PortOptions loadYamlLike(const std::string& path);
};

}  // namespace legsa_v23_port_core
