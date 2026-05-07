// 中文说明：这是 LegSA-GINS C++ runtime 入口；当前 dry-run 只验证输出链路，不是性能证据，也不读取 final_v23 输出作为 proposed input。
// English note: comments define module responsibility and safety boundaries only.

#include <iostream>
#include <string>

#include "legsa_gins/config/runtime_config.hpp"
#include "legsa_gins/engine/legsa_engine.hpp"

namespace {

void printUsage(const char* program) {
  std::cerr << "Usage: " << program
            << " (--dry-run | --dry-filter-demo) [--output-dir PATH]\n";
}

}  // namespace

int main(int argc, char** argv) {
  auto config = legsa_gins::config::defaultRuntimeConfig();
  bool dry_run_requested = false;
  bool dry_filter_demo_requested = false;

  // 参数只允许 dry-run / dry-filter-demo 链路。
  // Arguments only expose dry-run and toy filter demo paths.
  for (int index = 1; index < argc; ++index) {
    const std::string arg = argv[index];
    if (arg == "--dry-run") {
      dry_run_requested = true;
      config.dry_run = true;
    } else if (arg == "--dry-filter-demo") {
      dry_filter_demo_requested = true;
      config.dry_run = true;
      config.dataset_name = "n4_filter_toy_demo";
      config.algorithm_role = "proposed";
      config.algorithm_name = "LegSA-GINS-filter-core";
    } else if (arg == "--output-dir") {
      if (index + 1 >= argc) {
        printUsage(argv[0]);
        return 2;
      }
      config.output_dir = argv[++index];
    } else {
      printUsage(argv[0]);
      return 2;
    }
  }

  if (dry_run_requested && dry_filter_demo_requested) {
    std::cerr << "--dry-run and --dry-filter-demo are mutually exclusive.\n";
    return 2;
  }

  if (!dry_run_requested && !dry_filter_demo_requested) {
    // 非 dry-run 真数据入口留给后续 N4/N5；这里不读取 final_v23 输出作为 proposed input。
    // Real-data runtime is deferred to later stages; final_v23 outputs are not proposed inputs.
    std::cerr << "Real data runtime is not implemented. Use --dry-run or --dry-filter-demo.\n";
    return 1;
  }

  try {
    // dry-run 只验证 writer 和 manifest 合同，不是 numerical performance evidence。
    // Dry-run validates writer/manifest contracts only, not performance.
    legsa_gins::engine::LegSAEngine engine(config);
    if (dry_filter_demo_requested) {
      engine.runFilterToyDemo();
    } else {
      engine.initialize();
      engine.runDryDemo();
    }
    std::cout << "Generated dry-run outputs in: " << config.output_dir << '\n';
  } catch (const std::exception& exc) {
    std::cerr << "legsa_gins failed: " << exc.what() << '\n';
    return 1;
  }

  return 0;
}
