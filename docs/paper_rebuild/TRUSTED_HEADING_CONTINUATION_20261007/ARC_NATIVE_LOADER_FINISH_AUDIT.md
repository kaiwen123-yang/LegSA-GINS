# Independent loader finish audit

Status: PASS_WITH_STATED_TRACE_SCOPE. Registration b13e2e7615488f68ab6234fc7fb3491c939c12de; output ARC_NATIVE_TELEMETRY_REPAIR01/LOADER_COMPLETION01. The finish exited0 without timeout after1.066617926s. No scientific module, checker, test, navigation run or evaluator was executed by this reviewer.

This finish executed exactly two new checker processes, BY2H and BY2O, and reused the sealed BY2 result without rerunning it. It performed compile0/prepare0/native0/evaluator0. Across the preserved stages there is one actual checker compilation and three actual CSV parser calls. The earlier nested-strace wrapper failed before a compiler started. The c74a52c repair actually compiled and ran BY2 successfully, then failed only at the phase metadata validator; both failures remain preserved and are not rewritten as first-attempt success.

| Sequence | Evidence used | Parsed endpoints / blocks | Equal scientific fields |
|---|---|---:|---:|
| BY2 | Stored c74 successful checker process, no rerun | 548 / 274 | 53 |
| BY2H | New checker process | 540 / 270 | 53 |
| BY2O | New checker process | 754 / 377 | 53 |

Independent checks bind each invocation to the exact checker/config/echo destination, match its zero-exit/no-timeout/no-retry receipt and parsed counts, and verify echo hashes. In all three cases the53 scientific/init fields match the old echo, phase equals that echo's own stage_id, fixed ARC metadata match the prepared schedule, and provider path declarations match the inherited inputs. BY2_STORED_VALIDATION equals the corresponding COMPLETE record and its preserved original echo; there is no BY2 process trace in the new completion stage. Actual arrival remains null, state/phase cross UNKNOWN and event_execution_qualified false.

All70 registered source hashes match both the frozen Git registration and current files. The registered plan bytes match Git. All40 preserved artifact pins match. INPUT_PINS and COMPLETE contain identical55-file metadata/preserved maps, and every current hash matches. These checks include the prepared PLAN seal and the same454,008-byte checker (SHA2562b08995da6025abf0ea7464422f990434d24aab387b2c5a55fc798d67e021f85). Scientific provider payload hashes were inherited and were not recomputed.

The outer invocation explicitly omits -f and follows only the Python parent. Its601 trace lines contain456 openat calls (450 successful,6 failed), one Python exec and144 process records. Each inner -f checker trace contains10 lines: one checker exec, eight successful openat calls and one process-exit record. All621 lines parse, with zero unclassified successful opens. Each child opens only its config and metadata CSV as scientific inputs, then writes its own echo; the rest are system libraries. Parent scientific accesses are exact registered source, metadata/build/preserved pins and completion outputs. All scientific writes remain in LOADER_COMPLETION01. No raw, reference, original phase report, provider payload, native solver or evaluator access/execution was observed in this captured scope.

The outer trace does not claim to capture internals of the Git verification subprocesses or tracer setup. Those parent-launched Git show calls are identified by the inspected frozen source; separate inner traces cover the actual H/O checkers. Consequently this is a bounded openat/execve audit, not an all-process/all-syscall proof. The companion JSON records exact counters, classifications, failed-open names, current pin checks and audit-artifact hashes.

The cumulative compile1/parser3 statement uses the preserved c74 inner traces and ARC_NATIVE_LOADER_REPAIR01_FAILURE_SUMMARY, while the earlier prepare and nested-trace boundaries remain in ARC_NATIVE_PREPARE_REPAIR_AUDIT. No original OPPORTUNITIES or detail gzip was reopened. This completes loader/metadata-parser qualification only: it supplies no native trajectory, event-conditioning/covariance result, trusted heading coverage or navigation benefit. The next six matched native runs and any information readout require separate registration.
