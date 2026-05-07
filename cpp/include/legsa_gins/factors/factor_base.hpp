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
