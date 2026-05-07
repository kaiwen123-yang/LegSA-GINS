// 中文说明：ZYX 欧拉角和 qbn 转换工具；yaw 输出 wrap 到 [0, 2pi)。
// English note: Future real-data work still needs final_v23 yaw-convention oracle checks.

#pragma once

#include "legsa_gins/math/quaternion.hpp"
#include "legsa_gins/math/vec3.hpp"

namespace legsa_gins::math {

Quaternion eulerRadToQuaternion(double roll_rad, double pitch_rad, double yaw_rad);
Vec3 quaternionToEulerRad(const Quaternion& q);

}  // namespace legsa_gins::math
