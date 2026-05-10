// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/nav_state.hpp"
#include "legsa_v23_port_core/options.hpp"

#include <string>
#include <vector>

namespace legsa_v23_port_core {

// 中文说明：writer helper 对应 writeNavResult/writeSTD 合同，只做 common-unit 输出，不做结果修正。
class PortWriters {
 public:
  static void writeAll(const std::string& output_dir,
                       const PortOptions& options,
                       const std::vector<NavState>& states,
                       const std::vector<std::vector<double>>& covariances);
};

}  // namespace legsa_v23_port_core
