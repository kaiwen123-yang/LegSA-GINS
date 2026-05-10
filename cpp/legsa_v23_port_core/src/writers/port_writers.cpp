// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/writers/port_writers.hpp"

#include "legsa_v23_port_core/fileio/file_saver.hpp"

namespace legsa_v23_port_core {

// 中文说明：统一写 NAV/STD/EVAL_NAV/RUN_MANIFEST；STD 由 FileSaver 转为 KF-GINS common unit。
void PortWriters::writeAll(const std::string& output_dir,
                           const PortOptions& options,
                           const std::vector<NavState>& states,
                           const std::vector<std::vector<double>>& covariances) {
  FileSaver::writeNav(output_dir, states);
  FileSaver::writeStd(output_dir, covariances);
  FileSaver::writeEvalNav(output_dir, states);
  FileSaver::writeRunManifest(output_dir, options);
}

}  // namespace legsa_v23_port_core
