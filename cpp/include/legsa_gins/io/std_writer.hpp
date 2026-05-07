#pragma once

#include <filesystem>
#include <fstream>

#include "legsa_gins/types/nav_types.hpp"

namespace legsa_gins::io {

class StdWriter {
 public:
  explicit StdWriter(std::filesystem::path output_dir);
  ~StdWriter();

  void write(const types::StdState& state);
  void close();
  const std::filesystem::path& path() const;

 private:
  std::filesystem::path path_;
  std::ofstream stream_;
  bool has_last_tow_ = false;
  double last_tow_ = 0.0;
};

}  // namespace legsa_gins::io
