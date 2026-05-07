// 中文说明：因子模块当前只描述开关和槽位；RawDoppler、Go2、SourceAware、FixedLagSmoother 默认关闭，不能代表 residual 已实现。
// English note: comments define module responsibility and safety boundaries only.

#pragma once

#include <set>
#include <vector>

#include "legsa_gins/factors/factor_base.hpp"

namespace legsa_gins::factors {

class FactorRegistry {
 public:
  FactorRegistry();

  void enable(FactorKind kind);
  void disable(FactorKind kind);
  bool isEnabled(FactorKind kind) const;
  std::vector<FactorKind> enabledKinds() const;

 private:
  std::set<FactorKind> enabled_;
};

}  // namespace legsa_gins::factors
