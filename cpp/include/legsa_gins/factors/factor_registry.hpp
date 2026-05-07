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
