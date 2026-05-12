// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include <string>

namespace legsa_v23_port_core {

struct PortRuntimeDebugOptions {
  bool update_timeline = false;
  bool overclose_audit = false;
  bool measurement_copy_guard = false;
  bool covariance_gain = false;
  std::string output_dir;
  std::size_t max_rows = 100000;
};

// 中文说明：PortRuntime 支持 R2 synthetic math 和真实输入形态，但 R2 不运行 clean parity。
class PortRuntime {
 public:
  static void runDryToy(const std::string& output_dir);
  static void runSyntheticMath(const std::string& output_dir);
  static void runRawDopplerToy(const std::string& output_dir);
  static void runSourceAwareToy(const std::string& output_dir);
  static void runGo2WeakPriorToy(const std::string& output_dir);
  static void runFromConfig(const std::string& config_path, const std::string& output_dir);
  static void runFromConfig(const std::string& config_path,
                            const std::string& output_dir,
                            const PortRuntimeDebugOptions& debug_options);
};

}  // namespace legsa_v23_port_core
