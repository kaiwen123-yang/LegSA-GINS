// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include "legsa_v23_port_core/gnss.hpp"

#include <string>
#include <vector>

namespace legsa_v23_port_core {

// 中文说明：GNSS loader 面向高层 loose-coupled 输入；R1 不实现 raw Doppler/raw pseudorange。
class GnssFileLoader {
 public:
  GnssFileLoader() = default;
  explicit GnssFileLoader(const std::string& path);
  static std::vector<GnssData> loadFifteenColumn(const std::string& path);
  bool next(GnssData& gnss);
  bool isEof() const;
  bool isOpen() const;
  bool allValidityExplicit() const;

 private:
  std::vector<GnssData> rows_;
  std::size_t index_ = 0;
};

}  // namespace legsa_v23_port_core
