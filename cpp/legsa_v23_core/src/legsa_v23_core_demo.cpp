#include "legsa_v23_core/runtime/legsa_v23_runtime.hpp"

#include <iostream>
#include <stdexcept>
#include <string>

namespace {

// 中文说明：demo 参数解析支持 skeleton toy、propagation toy、config 和 output-dir，避免隐式读取 trace。
struct DemoArgs {
  bool dry_run_toy = false;
  bool dry_run_propagation_toy = false;
  bool dry_run_update_toy = false;
  std::string config_path;
  std::string output_dir = ".";
  std::string debug_output_dir;
  int debug_max_updates = 30;
  bool disable_position_update = false;
  bool disable_velocity_update = false;
  bool disable_yaw_update = false;
  bool disable_measurement_update = false;
  bool disable_state_feedback = false;
  std::string diagnostic_run_label;
};

// 中文说明：最小命令行 parser，N4H4A 不引入额外 CLI 依赖。
DemoArgs parseArgs(int argc, char** argv) {
  DemoArgs args;
  for (int i = 1; i < argc; ++i) {
    const std::string token = argv[i];
    if (token == "--dry-run-toy") {
      args.dry_run_toy = true;
    } else if (token == "--dry-run-propagation-toy") {
      args.dry_run_propagation_toy = true;
    } else if (token == "--dry-run-update-toy") {
      args.dry_run_update_toy = true;
    } else if (token == "--config" && i + 1 < argc) {
      args.config_path = argv[++i];
    } else if (token == "--output-dir" && i + 1 < argc) {
      args.output_dir = argv[++i];
    } else if (token == "--debug-output-dir" && i + 1 < argc) {
      args.debug_output_dir = argv[++i];
    } else if (token == "--debug-max-updates" && i + 1 < argc) {
      args.debug_max_updates = std::stoi(argv[++i]);
    } else if (token == "--disable-position-update") {
      args.disable_position_update = true;
    } else if (token == "--disable-velocity-update") {
      args.disable_velocity_update = true;
    } else if (token == "--disable-yaw-update") {
      args.disable_yaw_update = true;
    } else if (token == "--disable-measurement-update") {
      args.disable_measurement_update = true;
    } else if (token == "--disable-state-feedback") {
      args.disable_state_feedback = true;
    } else if (token == "--diagnostic-run-label" && i + 1 < argc) {
      args.diagnostic_run_label = argv[++i];
    } else {
      throw std::runtime_error("unknown or incomplete argument: " + token);
    }
  }
  return args;
}

}  // namespace

// 中文说明：LegSA-v23-core demo 只跑框架或预测传播链路，不实现 raw Doppler/Go2/LSIM/OIM/FGO。
int main(int argc, char** argv) {
  try {
    const DemoArgs args = parseArgs(argc, argv);
    if (args.dry_run_toy) {
      legsa_v23_core::LegSAV23Runtime::runDryToy(args.output_dir);
      return 0;
    }
    if (args.dry_run_propagation_toy) {
      legsa_v23_core::LegSAV23Runtime::runDryPropagationToy(args.output_dir);
      return 0;
    }
    if (args.dry_run_update_toy) {
      legsa_v23_core::LegSAV23Runtime::runDryUpdateToy(args.output_dir);
      return 0;
    }
    if (!args.config_path.empty()) {
      legsa_v23_core::RuntimeDiagnosticOptions diagnostic_options;
      diagnostic_options.debug_output_dir = args.debug_output_dir;
      diagnostic_options.debug_max_updates = args.debug_max_updates;
      diagnostic_options.disable_position_update = args.disable_position_update;
      diagnostic_options.disable_velocity_update = args.disable_velocity_update;
      diagnostic_options.disable_yaw_update = args.disable_yaw_update;
      diagnostic_options.disable_measurement_update = args.disable_measurement_update;
      diagnostic_options.disable_state_feedback = args.disable_state_feedback;
      diagnostic_options.diagnostic_run_label = args.diagnostic_run_label;
      legsa_v23_core::LegSAV23Runtime::runFromConfig(args.config_path, args.output_dir == "." ? "" : args.output_dir,
                                                     diagnostic_options);
      return 0;
    }
    std::cerr << "usage: legsa_v23_core_demo --dry-run-toy --output-dir <dir>\n"
              << "   or: legsa_v23_core_demo --dry-run-propagation-toy --output-dir <dir>\n"
              << "   or: legsa_v23_core_demo --dry-run-update-toy --output-dir <dir>\n"
              << "   or: legsa_v23_core_demo --config <path> [--debug-output-dir <dir>] "
              << "[--disable-position-update|--disable-velocity-update|--disable-yaw-update|"
              << "--disable-measurement-update|--disable-state-feedback]\n";
    return 2;
  } catch (const std::exception& error) {
    std::cerr << "legsa_v23_core_demo failed: " << error.what() << "\n";
    return 1;
  }
}
