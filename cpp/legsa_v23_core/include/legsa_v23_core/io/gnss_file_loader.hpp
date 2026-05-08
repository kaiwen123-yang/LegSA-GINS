#pragma once

#include "legsa_v23_core/state/gnss_types.hpp"

#include <string>
#include <vector>

namespace legsa_v23_core {

// 中文说明：读取 15 列 final_v23-style GNSS 高层状态输入；不是 raw GNSS solver。
class GNSSFileLoader {
 public:
  // 中文说明：lat/lon 从 deg 转 rad，高度/速度/标准差保持 m 或 m/s，yaw 保留 deg。
  static std::vector<GNSSData> load(const std::string& path);
};

}  // namespace legsa_v23_core
