// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/runtime/port_runtime.hpp"

#include <iostream>
#include <stdexcept>
#include <string>

namespace {

struct Args {
  bool dry_run_toy = false;
  bool dry_run_synthetic_math = false;
  std::string config_path;
  std::string output_dir = ".";
};

// 中文说明：命令行只接受 toy/synthetic/config 和 output-dir，不接受 trace 或 final_v23 输出作为输入。
Args parseArgs(int argc, char** argv) {
  Args args;
  for (int i = 1; i < argc; ++i) {
    const std::string token = argv[i];
    if (token == "--dry-run-toy") {
      args.dry_run_toy = true;
    } else if (token == "--dry-run-synthetic-math") {
      args.dry_run_synthetic_math = true;
    } else if (token == "--config" && i + 1 < argc) {
      args.config_path = argv[++i];
    } else if (token == "--output-dir" && i + 1 < argc) {
      args.output_dir = argv[++i];
    } else {
      throw std::runtime_error("unknown or incomplete argument: " + token);
    }
  }
  return args;
}

}  // namespace

// 中文说明：R2 demo 只证明 source-backed math port 可运行；clean replay parity 留给 N4H4R3。
int main(int argc, char** argv) {
  try {
    const Args args = parseArgs(argc, argv);
    if (args.dry_run_toy) {
      legsa_v23_port_core::PortRuntime::runDryToy(args.output_dir);
      return 0;
    }
    if (args.dry_run_synthetic_math) {
      legsa_v23_port_core::PortRuntime::runSyntheticMath(args.output_dir);
      return 0;
    }
    if (!args.config_path.empty()) {
      legsa_v23_port_core::PortRuntime::runFromConfig(args.config_path, args.output_dir);
      return 0;
    }
    std::cerr << "usage: legsa_v23_port_core_demo "
              << "--dry-run-toy|--dry-run-synthetic-math|--config <path> --output-dir <dir>\n";
    return 2;
  } catch (const std::exception& error) {
    std::cerr << "legsa_v23_port_core_demo failed: " << error.what() << "\n";
    return 1;
  }
}
