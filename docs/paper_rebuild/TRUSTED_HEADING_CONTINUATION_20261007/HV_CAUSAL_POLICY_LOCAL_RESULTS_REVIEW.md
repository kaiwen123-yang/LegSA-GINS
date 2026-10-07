# NED-HV causal source policy: independent local results review

Status: PASS_LOCAL_IMPLEMENTATION_QUALIFICATION_ONLY. Registration cc7ae040a3693ccde80a4c7fa72f4d0fc35889f0; scratch stage HV_CAUSAL_POLICY_LOCAL_ATTEMPT01. This review read result metadata, six small source-event tables, the synthetic exact-event ledger/lifecycle, and the passive openat/execve trace. It did not rerun a test/native process, read real providers/reference, inspect synthetic joint-matrix values, change production/harness source, or rehash the new binary.

## Result and budget

One configure, one build, one harness compile, and six fixed modes all returned zero on their first execution; timeout=false for every recorded call and the outer wrapper. Six stdout JSON records agree with COMPLETE.case_results: guards, selection, consumption, generation, legacy_body and integration all PASS. COMPLETE source pins equal the registered plan source pins. Original local inputs are synthetic; real-native/evaluator/real-input calls and retries remain zero.

| Count | Observed total |
|---|---:|
| Config loader calls | 4 |
| Engine initializes | 14 |
| Source vector setters | 14 |
| Direct production NED calls | 20 |
| Exact-event steps | 41 |
| Legacy IMU steps | 2 |
| Manual production feedback calls | 5 |

The result means six registered modes, not ten tests from the earlier recommendation table. Calls rejected by guard tests remain counted.

## Direct result checks

- Selection selected the final equal-time index 3 at source 1.04, skipped reuse/older candidates on the next opportunity, later accepted index 1 at source 1.06, and left stale candidates unavailable. The diagnostic preserved the nonfinite-row skip.
- Provider rejection at source 1.04 is consumed=true/accepted=false; the next opportunity is no_eligible_source, and a strictly newer 1.06 source is accepted. The actual source-aware rejection table likewise records consumption followed by no eligible source, with no second acceptance/weighting attempt under the harness assertions.
- Feedback leaves generation 2 and its watermark intact. Initialize and explicit vector replacement allow the declared fresh generations 3 and 4. This is per-generation uniqueness, not a physical-source uniqueness claim across resets.
- The exact queue emits three NED opportunities: source 1.004 accepted at state/trigger 1.005; source 1.006 accepted at 1.007; no reuse at 1.008. Its ledger contains three GNSS position updates, two GO2_VELOCITY_DIAGNOSTIC updates with matching source/index identities, three full feedback resets, and then ARC_END at 1.009. Lifecycle is COVERED_END_PRIOR with end update/reset ordinals 5/3. No phase update is present.
- The legacy res=1 fixture records trigger 1.0004999999999999, actual state 1, future-to-state count 1 and future-to-trigger count 0, consumed=false. The source 1.0002500000000001 is then accepted at state/trigger 1.01. This directly verifies the extra actual-state gate and non-consumption of a currently future source.
- legacy_body passed byte comparisons of default versus explicit legacy configuration within the same newly built binary. This is not a comparison against historic frozen binary outputs. Actual arrival remains empty/NA in source-event rows and false for qualification in COMPLETE.

## Passive input-closure audit

The full compilation-wide trace was parsed with unfinished/resumed calls joined: 47,401 openat calls and 900 execve calls; 20,147 and 366 succeeded respectively. No parse failure or unmatched pending call remained. Successful executions comprise toolchain/Git/Python commands and exactly six harness executions; the built real-navigation demo was not executed.

Successful opens classify as system/toolchain (14,716), Python runtime (4), Git user configuration (423), Git object/config metadata (3,508), repository source/registration (787), this synthetic/build stage (533), and relative build filenames (176). The relative names are CMake/object/archive/compiler temporary outputs, not scientific input filenames; their working-directory transitions were not separately traced. No provider/raw/reference payload path or older scientific stage appears among successful opens. No absolute write outside the synthetic stage, system paths or relative build names was observed.

This audit is limited to the recorded openat/execve paths and invocation/result closure; it does not claim all-system-call or physical-arrival certification. Compilation of raw/provider loader source files is not a read of real provider payload.

## Decision

No blocking discrepancy was found. The new binary is eligible for a separately registered fixed real passive comparison of reported-time source selection. This local result does not establish a physical causal filtration, calibrated covariance/cross bounds, trusted heading, or navigation improvement. The prior Young-family negative result and historical V3 outputs remain unchanged.

COMPLETE SHA256: de2bc9f3bd0e7ea6b221aab2ef3aeaad75228c2ea51d75aa78d0f643d5a61681.
New demo binary identity, inherited from COMPLETE without another binary hash pass: b5bdf4451b94e45dc91df3a7bcd37da7338b2dc712d58b4160999a78979747ac.
