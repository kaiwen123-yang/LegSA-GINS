#pragma once

#include "legsa_v23_core/config/gins_options.hpp"

#include <string>

namespace legsa_v23_core {

// 中文说明：写 RUN_MANIFEST.json，固定记录 N4H4A 禁用项和输入来源边界。
class RunManifestWriter {
 public:
  // 中文说明：manifest 只写审计布尔值，不写本地绝对路径或性能指标。
  static void write(const std::string& path, const GINSOptions& options);
};

}  // namespace legsa_v23_core
