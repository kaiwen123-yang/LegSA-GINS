// 中文说明：因子模块当前只描述开关和槽位；RawDoppler、Go2、SourceAware、FixedLagSmoother 默认关闭，不能代表 residual 已实现。
// English note: comments define module responsibility and safety boundaries only.

#include "legsa_gins/factors/factor_registry.hpp"

#include <stdexcept>

namespace legsa_gins::factors {

std::string toString(FactorKind kind) {
  switch (kind) {
    case FactorKind::ReceiverPosition:
      return "ReceiverPosition";
    case FactorKind::ReceiverVelocity:
      return "ReceiverVelocity";
    case FactorKind::ReceiverHeading:
      return "ReceiverHeading";
    case FactorKind::RawDoppler:
      return "RawDoppler";
    case FactorKind::Go2YawRatePrior:
      return "Go2YawRatePrior";
    case FactorKind::Go2AttitudePrior:
      return "Go2AttitudePrior";
    case FactorKind::SupportIntegrity:
      return "SupportIntegrity";
    case FactorKind::SourceAwareWeighting:
      return "SourceAwareWeighting";
    case FactorKind::FixedLagSmoother:
      return "FixedLagSmoother";
  }
  throw std::invalid_argument("Unknown FactorKind.");
}

FactorRegistry::FactorRegistry()
    : enabled_{
          FactorKind::ReceiverPosition,
          FactorKind::ReceiverVelocity,
          FactorKind::ReceiverHeading,
      } {}

// 因子注册表只管理开关，不计算 residual。
// The registry stores switches only; it does not compute residuals.
void FactorRegistry::enable(FactorKind kind) { enabled_.insert(kind); }

void FactorRegistry::disable(FactorKind kind) { enabled_.erase(kind); }

bool FactorRegistry::isEnabled(FactorKind kind) const {
  return enabled_.find(kind) != enabled_.end();
}

std::vector<FactorKind> FactorRegistry::enabledKinds() const {
  return {enabled_.begin(), enabled_.end()};
}

}  // namespace legsa_gins::factors
