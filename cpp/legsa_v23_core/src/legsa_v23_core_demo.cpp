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
  int debug_max_rows = 100000;
  bool debug_full_update_trace = false;
  bool debug_full_state_trace = false;
  bool debug_measurement_matrix_trace = false;
  bool debug_gain_trace = false;
  bool debug_update_blocks = false;
  bool debug_feedback_delta = false;
  bool debug_covariance_gain = false;
  bool disable_position_update = false;
  bool disable_velocity_update = false;
  bool disable_yaw_update = false;
  bool disable_measurement_update = false;
  bool disable_state_feedback = false;
  std::string diagnostic_run_label;
  std::string diagnostic_model_variant = "baseline_current";
  std::string diagnostic_feedback_mode = "normal";
  std::string diagnostic_update_block_mode = "all";
  std::string diagnostic_covariance_mode = "normal";
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
    } else if (token == "--debug-max-rows" && i + 1 < argc) {
      args.debug_max_rows = std::stoi(argv[++i]);
    } else if (token == "--debug-full-update-trace") {
      args.debug_full_update_trace = true;
    } else if (token == "--debug-full-state-trace") {
      args.debug_full_state_trace = true;
    } else if (token == "--debug-measurement-matrix-trace") {
      args.debug_measurement_matrix_trace = true;
    } else if (token == "--debug-gain-trace") {
      args.debug_gain_trace = true;
    } else if (token == "--debug-update-blocks") {
      args.debug_update_blocks = true;
    } else if (token == "--debug-feedback-delta") {
      args.debug_feedback_delta = true;
    } else if (token == "--debug-covariance-gain") {
      args.debug_covariance_gain = true;
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
    } else if (token == "--diagnostic-model-variant" && i + 1 < argc) {
      args.diagnostic_model_variant = argv[++i];
    } else if (token == "--diagnostic-feedback-mode" && i + 1 < argc) {
      args.diagnostic_feedback_mode = argv[++i];
    } else if (token == "--diagnostic-update-block-mode" && i + 1 < argc) {
      args.diagnostic_update_block_mode = argv[++i];
    } else if (token == "--diagnostic-covariance-mode" && i + 1 < argc) {
      args.diagnostic_covariance_mode = argv[++i];
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
      diagnostic_options.debug_max_rows = args.debug_max_rows;
      diagnostic_options.debug_full_update_trace = args.debug_full_update_trace;
      diagnostic_options.debug_full_state_trace = args.debug_full_state_trace;
      diagnostic_options.debug_measurement_matrix_trace = args.debug_measurement_matrix_trace;
      diagnostic_options.debug_gain_trace = args.debug_gain_trace;
      diagnostic_options.debug_update_blocks = args.debug_update_blocks;
      diagnostic_options.debug_feedback_delta = args.debug_feedback_delta;
      diagnostic_options.debug_covariance_gain = args.debug_covariance_gain;
      diagnostic_options.disable_position_update = args.disable_position_update;
      diagnostic_options.disable_velocity_update = args.disable_velocity_update;
      diagnostic_options.disable_yaw_update = args.disable_yaw_update;
      diagnostic_options.disable_measurement_update = args.disable_measurement_update;
      diagnostic_options.disable_state_feedback = args.disable_state_feedback;
      diagnostic_options.diagnostic_run_label = args.diagnostic_run_label;
      diagnostic_options.diagnostic_model_variant = args.diagnostic_model_variant;
      diagnostic_options.diagnostic_feedback_mode = args.diagnostic_feedback_mode;
      diagnostic_options.diagnostic_update_block_mode = args.diagnostic_update_block_mode;
      diagnostic_options.diagnostic_covariance_mode = args.diagnostic_covariance_mode;
      legsa_v23_core::LegSAV23Runtime::runFromConfig(args.config_path, args.output_dir == "." ? "" : args.output_dir,
                                                     diagnostic_options);
      return 0;
    }
    std::cerr << "usage: legsa_v23_core_demo --dry-run-toy --output-dir <dir>\n"
              << "   or: legsa_v23_core_demo --dry-run-propagation-toy --output-dir <dir>\n"
              << "   or: legsa_v23_core_demo --dry-run-update-toy --output-dir <dir>\n"
              << "   or: legsa_v23_core_demo --config <path> [--debug-output-dir <dir>] "
              << "[--debug-full-update-trace|--debug-full-state-trace|--debug-measurement-matrix-trace|"
              << "--debug-gain-trace|--debug-update-blocks|--debug-feedback-delta|--debug-covariance-gain] "
              << "[--disable-position-update|--disable-velocity-update|--disable-yaw-update|"
              << "--disable-measurement-update|--disable-state-feedback] "
              << "[--diagnostic-model-variant <name>] [--diagnostic-feedback-mode <mode>] "
              << "[--diagnostic-update-block-mode <mode>] [--diagnostic-covariance-mode <mode>]\n";
    return 2;
  } catch (const std::exception& error) {
    std::cerr << "legsa_v23_core_demo failed: " << error.what() << "\n";
    return 1;
  }
}
