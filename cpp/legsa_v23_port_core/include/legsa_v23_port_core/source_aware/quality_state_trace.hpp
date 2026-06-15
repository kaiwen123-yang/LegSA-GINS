// LegSA-GINS source-backed port file.
// Port role: PAPER10B2 multi-state QM runtime audit trace.
// Boundary: runtime-only trace; never solver input.

#pragma once

#include "legsa_v23_port_core/source_aware/quality_state_manager.hpp"

#include <string>
#include <vector>

namespace legsa_v23_port_core::source_aware {

struct QualityStateTraceRow {
  double time = 0.0;
  std::size_t update_index = 0;
  SourceWeightResult weight_result;
  QualityStateDecision decision;
};

class QualityStateTrace {
 public:
  void add(double time,
           std::size_t update_index,
           const SourceWeightResult& weight_result,
           const QualityStateDecision& decision);
  bool empty() const;
  std::size_t rowCount() const;
  const std::vector<QualityStateTraceRow>& rows() const;
  QualityStateRuntimeStats stats() const;
  void writeCsv(const std::string& output_dir) const;

 private:
  std::vector<QualityStateTraceRow> rows_;
};

}  // namespace legsa_v23_port_core::source_aware
