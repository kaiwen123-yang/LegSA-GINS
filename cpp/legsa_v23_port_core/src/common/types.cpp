// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/types.hpp"

#include <cmath>

namespace legsa_v23_port_core {

// 中文说明：构造三维向量，避免在 R1 引入额外线性代数依赖。
Vec3 makeVec3(double x, double y, double z) {
  return Vec3{x, y, z};
}

// 中文说明：R1 toy 和审计统计使用欧氏范数，不作为性能指标。
double norm(const Vec3& value) {
  return std::sqrt(value[0] * value[0] + value[1] * value[1] + value[2] * value[2]);
}

// 中文说明：轻量向量加法仅用于 dry-run skeleton 状态推进。
Vec3 add(const Vec3& lhs, const Vec3& rhs) {
  return makeVec3(lhs[0] + rhs[0], lhs[1] + rhs[1], lhs[2] + rhs[2]);
}

// 中文说明：轻量缩放仅用于 R1 toy，不代表完整 KF-GINS 矩阵实现。
Vec3 scale(const Vec3& value, double factor) {
  return makeVec3(value[0] * factor, value[1] * factor, value[2] * factor);
}

// 中文说明：协方差先以对角向量保存；完整 P 矩阵 parity 留给 R2。
std::vector<double> makeCovarianceDiagonal(double value) {
  return std::vector<double>(kErrorStateSize, value);
}

}  // namespace legsa_v23_port_core

