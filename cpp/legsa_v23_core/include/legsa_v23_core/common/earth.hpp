#pragma once

#include "legsa_v23_core/common/math_types.hpp"

namespace legsa_v23_core {

// 中文说明：LegSA 自有 Earth 工具，采用 WGS84；BLH 为 lat/lon(rad) 和 height(m)，导航系为 NED。
class Earth {
 public:
  // 中文说明：计算正常重力，返回 NED 下 [0,0,g]，向下为正，单位 m/s^2。
  static Vector3 gravity(const Vector3& blh);

  // 中文说明：返回子午圈半径 RM 和卯酉圈半径 RN，单位 m。
  static Vector3 meridianPrimeVerticalRadius(double lat);

  // 中文说明：返回卯酉圈半径 RN，单位 m。
  static double RN(double lat);

  // 中文说明：DRi 将 NED 小位移(m) 转成 BLH 小增量(rad,rad,m)。
  static Matrix3 DRi(const Vector3& blh);

  // 中文说明：DR 将 BLH 小增量(rad,rad,m) 转成 NED 小位移(m)。
  static Matrix3 DR(const Vector3& blh);

  // 中文说明：从 BLH 构造 ECEF 到 NED 的旋转 qne；四元数顺序为 w,x,y,z。
  static Quaternion qne(const Vector3& blh);

  // 中文说明：从 ECEF 到 NED 四元数和 height 反解近似 BLH，用于边界测试而非性能结论。
  static Vector3 blh(const Quaternion& qne, double height);

  // 中文说明：地球自转在导航系 NED 下的投影，单位 rad/s。
  static Vector3 iewn(double lat);

  // 中文说明：导航系相对地球系的转率，输入 RM/RN、BLH 和 NED 速度，单位 rad/s。
  static Vector3 enwn(const Vector3& rmn, const Vector3& blh, const Vector3& vel);
};

}  // namespace legsa_v23_core
