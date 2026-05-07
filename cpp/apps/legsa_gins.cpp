#include <iostream>
#include <string>

#include "legsa_gins/config/runtime_config.hpp"
#include "legsa_gins/engine/legsa_engine.hpp"

namespace {

void printUsage(const char* program) {
  std::cerr << "Usage: " << program << " --dry-run [--output-dir PATH]\n";
}

}  // namespace

int main(int argc, char** argv) {
  auto config = legsa_gins::config::defaultRuntimeConfig();
  bool dry_run_requested = false;

  for (int index = 1; index < argc; ++index) {
    const std::string arg = argv[index];
    if (arg == "--dry-run") {
      dry_run_requested = true;
      config.dry_run = true;
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

  if (!dry_run_requested) {
    std::cerr << "Real data runtime is not implemented in N3A. Use --dry-run.\n";
    return 1;
  }

  try {
    legsa_gins::engine::LegSAEngine engine(config);
    engine.initialize();
    engine.runDryDemo();
    std::cout << "Generated dry-run outputs in: " << config.output_dir << '\n';
  } catch (const std::exception& exc) {
    std::cerr << "legsa_gins failed: " << exc.what() << '\n';
    return 1;
  }

  return 0;
}
