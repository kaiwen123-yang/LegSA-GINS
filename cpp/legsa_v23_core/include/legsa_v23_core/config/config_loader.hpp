#pragma once

#include "legsa_v23_core/config/gins_options.hpp"

#include <string>

namespace legsa_v23_core {

// 中文说明：轻量 YAML-like/key-value 配置读取器；N4H4A 不引入 yaml-cpp 强依赖。
class ConfigLoader {
 public:
  // 中文说明：读取 imupath/gnsspath/outputpath 等运行字段，并完成 deg->rad 的单位转换。
  static GINSOptions load(const std::string& path);
};

}  // namespace legsa_v23_core
