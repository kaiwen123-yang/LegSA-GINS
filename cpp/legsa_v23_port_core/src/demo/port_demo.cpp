// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/runtime/port_runtime.hpp"

#include <cstddef>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

struct Args {
  bool dry_run_toy = false;
  bool dry_run_synthetic_math = false;
  bool dry_run_raw_doppler_toy = false;
  bool dry_run_source_aware_toy = false;
  bool dry_run_go2_weak_prior_toy = false;
  bool debug_update_timeline = false;
  bool debug_overclose_audit = false;
  bool debug_measurement_copy_guard = false;
  bool debug_covariance_gain = false;
  std::string config_path;
  std::string output_dir = ".";
  std::string debug_output_dir;
  std::size_t debug_max_rows = 100000;
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
    } else if (token == "--dry-run-raw-doppler-toy") {
      args.dry_run_raw_doppler_toy = true;
    } else if (token == "--dry-run-source-aware-toy") {
      args.dry_run_source_aware_toy = true;
    } else if (token == "--dry-run-go2-weak-prior-toy") {
      args.dry_run_go2_weak_prior_toy = true;
    } else if (token == "--config" && i + 1 < argc) {
      args.config_path = argv[++i];
    } else if (token == "--output-dir" && i + 1 < argc) {
      args.output_dir = argv[++i];
    } else if (token == "--debug-update-timeline") {
      args.debug_update_timeline = true;
    } else if (token == "--debug-overclose-audit") {
      args.debug_overclose_audit = true;
    } else if (token == "--debug-measurement-copy-guard") {
      args.debug_measurement_copy_guard = true;
    } else if (token == "--debug-covariance-gain") {
      args.debug_covariance_gain = true;
    } else if (token == "--debug-output-dir" && i + 1 < argc) {
      args.debug_output_dir = argv[++i];
    } else if (token == "--debug-max-rows" && i + 1 < argc) {
      args.debug_max_rows = static_cast<std::size_t>(std::stoull(argv[++i]));
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
    if (args.dry_run_raw_doppler_toy) {
      legsa_v23_port_core::PortRuntime::runRawDopplerToy(args.output_dir);
      return 0;
    }
    if (args.dry_run_source_aware_toy) {
      legsa_v23_port_core::PortRuntime::runSourceAwareToy(args.output_dir);
      return 0;
    }
    if (args.dry_run_go2_weak_prior_toy) {
      legsa_v23_port_core::PortRuntime::runGo2WeakPriorToy(args.output_dir);
      return 0;
    }
    if (!args.config_path.empty()) {
      legsa_v23_port_core::PortRuntimeDebugOptions debug_options;
      debug_options.update_timeline = args.debug_update_timeline;
      debug_options.overclose_audit = args.debug_overclose_audit;
      debug_options.measurement_copy_guard = args.debug_measurement_copy_guard;
      debug_options.covariance_gain = args.debug_covariance_gain;
      debug_options.output_dir = args.debug_output_dir.empty() ? args.output_dir : args.debug_output_dir;
      debug_options.max_rows = args.debug_max_rows;
      legsa_v23_port_core::PortRuntime::runFromConfig(args.config_path, args.output_dir, debug_options);
      return 0;
    }
    std::cerr << "usage: legsa_v23_port_core_demo "
              << "--dry-run-toy|--dry-run-synthetic-math|--dry-run-raw-doppler-toy|"
              << "--dry-run-source-aware-toy|--dry-run-go2-weak-prior-toy|--config <path> --output-dir <dir> "
              << "[--debug-update-timeline --debug-overclose-audit --debug-measurement-copy-guard "
              << "--debug-covariance-gain --debug-output-dir <dir> --debug-max-rows <N>]\n";
    return 2;
  } catch (const std::exception& error) {
    std::cerr << "legsa_v23_port_core_demo failed: " << error.what() << "\n";
    return 1;
  }
}
