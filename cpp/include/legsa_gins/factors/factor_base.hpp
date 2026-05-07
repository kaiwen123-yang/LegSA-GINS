// 中文说明：因子模块当前只描述开关和槽位；RawDoppler、Go2、SourceAware、FixedLagSmoother 默认关闭，不能代表 residual 已实现。
// English note: comments define module responsibility and safety boundaries only.

#pragma once

#include <string>

namespace legsa_gins::factors {

enum class FactorKind {
  ReceiverPosition,
  ReceiverVelocity,
  ReceiverHeading,
  RawDoppler,
  Go2YawRatePrior,
  Go2AttitudePrior,
  SupportIntegrity,
  SourceAwareWeighting,
  FixedLagSmoother,
};

std::string toString(FactorKind kind);

class FactorBase {
 public:
  virtual ~FactorBase() = default;
  virtual FactorKind kind() const = 0;
  virtual std::string name() const = 0;
};

}  // namespace legsa_gins::factors
