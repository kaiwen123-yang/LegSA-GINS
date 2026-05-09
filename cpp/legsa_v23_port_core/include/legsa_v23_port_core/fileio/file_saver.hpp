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

// 中文说明：FileSaver 写 R1 toy 合同文件，绝不做 output-only correction。
class FileSaver {
 public:
  static void writeNav(const std::string& output_dir, const std::vector<NavState>& states);
  static void writeStd(const std::string& output_dir, const std::vector<std::vector<double>>& covariances);
  static void writeEvalNav(const std::string& output_dir, const std::vector<NavState>& states);
  static void writeRunManifest(const std::string& output_dir, const PortOptions& options);
};

}  // namespace legsa_v23_port_core

