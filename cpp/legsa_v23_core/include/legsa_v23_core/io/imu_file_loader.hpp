#pragma once

#include "legsa_v23_core/state/imu_types.hpp"

#include <string>
#include <vector>

namespace legsa_v23_core {

// 中文说明：读取 7 列 process_data-compatible IMU 增量；输入已完成 FLU->FRD，不允许重复转换。
class IMUFileLoader {
 public:
  // 中文说明：从文本文件读取 time dtheta_x dtheta_y dtheta_z dvel_x dvel_y dvel_z，单位为 s/rad/mps。
  static std::vector<IMUData> load(const std::string& path);
};

}  // namespace legsa_v23_core
