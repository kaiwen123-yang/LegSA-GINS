#include "legsa_v23_core/runtime/legsa_v23_runtime.hpp"

#include <iostream>
#include <string>

namespace {

// 中文说明：demo 参数解析只支持 --dry-run-toy、--config 和 --output-dir，避免隐式读取 trace。
struct DemoArgs {
  bool dry_run_toy = false;
  std::string config_path;
  std::string output_dir = ".";
};

// 中文说明：最小命令行 parser，N4H4A 不引入额外 CLI 依赖。
DemoArgs parseArgs(int argc, char** argv) {
  DemoArgs args;
  for (int i = 1; i < argc; ++i) {
    const std::string token = argv[i];
    if (token == "--dry-run-toy") {
      args.dry_run_toy = true;
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

// 中文说明：LegSA-v23-core demo 只跑框架链路，不实现 raw Doppler/Go2/LSIM/OIM/FGO。
int main(int argc, char** argv) {
  try {
    const DemoArgs args = parseArgs(argc, argv);
    if (args.dry_run_toy) {
      legsa_v23_core::LegSAV23Runtime::runDryToy(args.output_dir);
      return 0;
    }
    if (!args.config_path.empty()) {
      legsa_v23_core::LegSAV23Runtime::runFromConfig(args.config_path);
      return 0;
    }
    std::cerr << "usage: legsa_v23_core_demo --dry-run-toy --output-dir <dir>\n"
              << "   or: legsa_v23_core_demo --config <path>\n";
    return 2;
  } catch (const std::exception& error) {
    std::cerr << "legsa_v23_core_demo failed: " << error.what() << "\n";
    return 1;
  }
}
