#pragma once

#include "legsa_v23_core/common/math_types.hpp"

namespace legsa_v23_core {

// 中文说明：LegSA 自有 Rotation 工具，body 为 FRD，导航系为 NED；yaw/heading 以 rad/deg 包裹。
class Rotation {
 public:
  // 中文说明：三维向量反对称矩阵，用于叉乘、coning/sculling 和 F 矩阵块。
  static Matrix3 skewSymmetric(const Vector3& vector);

  // 中文说明：旋转向量转四元数，输入 rad，输出 w,x,y,z。
  static Quaternion rotvec2quaternion(const Vector3& rotvec);

  // 中文说明：四元数转方向余弦矩阵，矩阵按行优先存储。
  static Matrix3 quaternion2matrix(const Quaternion& quaternion);

  // 中文说明：方向余弦矩阵转四元数，输出 w,x,y,z。
  static Quaternion matrix2quaternion(const Matrix3& matrix);

  // 中文说明：方向余弦矩阵转 roll/pitch/yaw(rad)，yaw 输出包裹到 [-pi,pi)。
  static Vector3 matrix2euler(const Matrix3& matrix);

  // 中文说明：roll/pitch/yaw(rad) 转 body-to-nav 方向余弦矩阵。
  static Matrix3 euler2matrix(const Vector3& euler);

  // 中文说明：roll/pitch/yaw(rad) 转四元数。
  static Quaternion euler2quaternion(const Vector3& euler);

  // 中文说明：四元数转近似旋转向量，单位 rad。
  static Vector3 quaternion2vector(const Quaternion& quaternion);

  // 中文说明：角度 rad 包裹到 [-pi,pi)，用于 yaw/heading 边界。
  static double wrapAngleRad(double angle);

  // 中文说明：角度 deg 包裹到 [-180,180)，用于报告层 heading。
  static double wrapAngleDeg(double angle);

  // 中文说明：四元数乘法，顺序为左乘右，w,x,y,z。
  static Quaternion multiply(const Quaternion& lhs, const Quaternion& rhs);

  // 中文说明：四元数归一化，避免传播中姿态数值漂移。
  static Quaternion normalize(const Quaternion& quaternion);
};

}  // namespace legsa_v23_core
