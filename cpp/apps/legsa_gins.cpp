// 中文说明：这是 LegSA-GINS C++ runtime 入口；当前 dry-run 只验证输出链路，不是性能证据，也不读取 final_v23 输出作为 proposed input。
// English note: comments define module responsibility and safety boundaries only.

#include <iostream>
#include <cstddef>
#include <filesystem>
#include <string>

#include "legsa_gins/config/runtime_config.hpp"
#include "legsa_gins/engine/legsa_engine.hpp"

namespace {

void printUsage(const char* program) {
  std::cerr << "Usage: " << program
            << " (--dry-run | --dry-filter-demo | --run-filter-csv) [--output-dir PATH] "
               "[--imu-csv PATH --receiver-csv PATH --max-epochs N "
               "--imu-propagation-mode MODE --heading-offset-mode MODE]\n";
}

}  // namespace

int main(int argc, char** argv) {
  auto config = legsa_gins::config::defaultRuntimeConfig();
  bool dry_run_requested = false;
  bool dry_filter_demo_requested = false;
  bool run_filter_csv_requested = false;
  std::filesystem::path imu_csv;
  std::filesystem::path receiver_csv;
  std::size_t max_epochs = 0;

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
    } else if (arg == "--run-filter-csv") {
      run_filter_csv_requested = true;
      config.dry_run = false;
      config.dataset_name = "by2_filter_core_trial";
      config.algorithm_role = "proposed";
      config.algorithm_name = "LegSA-GINS-filter-core-BY2-trial";
    } else if (arg == "--imu-csv") {
      if (index + 1 >= argc) {
        printUsage(argv[0]);
        return 2;
      }
      imu_csv = argv[++index];
    } else if (arg == "--receiver-csv") {
      if (index + 1 >= argc) {
        printUsage(argv[0]);
        return 2;
      }
      receiver_csv = argv[++index];
    } else if (arg == "--max-epochs") {
      if (index + 1 >= argc) {
        printUsage(argv[0]);
        return 2;
      }
      max_epochs = static_cast<std::size_t>(std::stoull(argv[++index]));
    } else if (arg == "--imu-propagation-mode") {
      if (index + 1 >= argc) {
        printUsage(argv[0]);
        return 2;
      }
      config.imu_propagation_mode = argv[++index];
    } else if (arg == "--heading-offset-mode") {
      if (index + 1 >= argc) {
        printUsage(argv[0]);
        return 2;
      }
      config.heading_offset_mode = argv[++index];
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

  const int mode_count = static_cast<int>(dry_run_requested) +
                         static_cast<int>(dry_filter_demo_requested) +
                         static_cast<int>(run_filter_csv_requested);
  if (mode_count > 1) {
    std::cerr << "Runtime modes are mutually exclusive.\n";
    return 2;
  }

  if (mode_count == 0) {
    std::cerr << "Select one runtime mode.\n";
    printUsage(argv[0]);
    return 1;
  }
  if (run_filter_csv_requested && (imu_csv.empty() || receiver_csv.empty())) {
    std::cerr << "--run-filter-csv requires --imu-csv and --receiver-csv.\n";
    return 1;
  }

  try {
    // dry-run 只验证 writer 和 manifest 合同，不是 numerical performance evidence。
    // Dry-run validates writer/manifest contracts only, not performance.
    legsa_gins::engine::LegSAEngine engine(config);
    if (dry_filter_demo_requested) {
      engine.runFilterToyDemo();
    } else if (run_filter_csv_requested) {
      engine.runFilterCsvTrial(imu_csv, receiver_csv, max_epochs);
    } else {
      engine.initialize();
      engine.runDryDemo();
    }
    std::cout << "Generated outputs in: " << config.output_dir << '\n';
  } catch (const std::exception& exc) {
    std::cerr << "legsa_gins failed: " << exc.what() << '\n';
    return 1;
  }

  return 0;
}
