// 中文说明：writer 只写合同化输出给后续验证或 evaluator；不做 output-only correction，不删除 bad epochs，也不参与 solver。
// English note: comments define module responsibility and safety boundaries only.

#pragma once

#include <filesystem>
#include <fstream>

#include "legsa_gins/types/nav_types.hpp"

namespace legsa_gins::io {

class NavWriter {
 public:
  explicit NavWriter(std::filesystem::path output_dir, int gps_week = 0);
  ~NavWriter();

  void write(const types::NavState& state);
  void close();
  const std::filesystem::path& path() const;

 private:
  std::filesystem::path path_;
  std::ofstream stream_;
  int gps_week_ = 0;
  bool has_last_tow_ = false;
  double last_tow_ = 0.0;
};

}  // namespace legsa_gins::io
