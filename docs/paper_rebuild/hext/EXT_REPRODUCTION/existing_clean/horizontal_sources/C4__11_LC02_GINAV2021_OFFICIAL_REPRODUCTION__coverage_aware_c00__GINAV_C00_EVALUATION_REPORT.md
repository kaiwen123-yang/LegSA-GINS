# GINav C00 coverage-aware offline evaluation

Terminal: `PASS_LC02_GINAV_C00_COVERAGE_AWARE_EVALUATION_COMPLETE`

Scientific applicability conclusion: `EXACT_OFFICIAL_ROUTE_WITH_POOR_BY2_ACCURACY_AND_AVAILABILITY`.

The official solver route was not rerun or tuned. This report evaluates the frozen 80-row native output as-is. The reference is the Fixposition-derived same-source offline evaluation reference, not independent ground truth. It was first opened only after the conversion contract and 80-row standard CSV were fixed.

## Coverage and mechanism facts

- Configured formal GINav span: 295 integer epochs over 294.000 s; official eligible epochs: 116; SPP valid/invalid: 48/68.
- Alignment delay: 113.002 s. Native rows: 80 = 1 alignment + 11 LC updates + 68 INS-only propagation rows.
- Formal window: 66.0..340.0 s, expected duration 274.0 s and 275 inclusive integer epochs. Valid output: 77 rows, first 169.002 s, last 338.999 s, row coverage 0.280000000 (28.000%), temporal-span coverage 0.620427007 (62.043%), max gap 11.000 s, 38 segments (new segment when adjacent gap >1.5 s). The missing leading output remains in the denominator.
- Native support (`GINAV_NATIVE_SUPPORT_ONLY`): 80/80 rows and 180.997/180.997 s = 100% native-relative coverage. Configured-relative coverage is 80/295 = 0.271186441 (27.119%) and 180.997/294 = 0.615636054 (61.564%). Max gap 11.000 s; 41 segments.
- Every main CSV row repeats: configured integer epochs 295, official eligible 116, SPP 48/68, alignment delay 113.002 s, native rows 80, LC updates 11, INS-only 68.

Coverage definitions: row coverage is valid output rows divided by the explicitly named expected epoch set; temporal coverage is first-to-last valid output span divided by the explicitly named expected duration. Gaps are not silently filled; max gap and segment count are reported separately.

## GINav formal-window metrics

| Quantity | RMSE | MAE | P95 | P99 | Max |
|---|---:|---:|---:|---:|---:|
| East (m) | 116.574165 | 95.247756 | 182.993271 | 187.838076 | 188.456765 |
| North (m) | 59.363314 | 51.746476 | 78.552071 | 78.743528 | 78.759907 |
| Up (m) | 176.735133 | 151.289326 | 221.637985 | 221.699559 | 221.746646 |
| Horizontal (m) | 130.818726 | 109.847447 | 199.150085 | 202.580158 | 202.979462 |
| 3D (m) | 219.883711 | 188.203201 | 296.303408 | 298.470178 | 298.704019 |
| Roll (deg) | 14.936207 | 13.588756 | 19.965923 | 21.258122 | 22.129421 |
| Pitch (deg) | 14.107015 | 12.725401 | 18.636966 | 19.352526 | 19.450579 |
| Yaw (deg) | 69.753332 | 56.762013 | 150.935884 | 168.030864 | 172.428354 |

## GINav native-support metrics

| Quantity | RMSE | MAE | P95 | P99 | Max |
|---|---:|---:|---:|---:|---:|
| East (m) | 116.811111 | 96.278444 | 182.698952 | 187.813655 | 188.456765 |
| North (m) | 58.543217 | 50.952031 | 78.535075 | 78.742881 | 78.759907 |
| Up (m) | 178.630415 | 153.933523 | 221.687787 | 221.799803 | 221.867451 |
| Horizontal (m) | 130.660414 | 110.473016 | 198.934204 | 202.564396 | 202.979462 |
| 3D (m) | 221.316446 | 190.721340 | 296.164150 | 298.460948 | 298.704019 |
| Roll (deg) | 15.124126 | 13.802980 | 20.361688 | 21.223729 | 22.129421 |
| Pitch (deg) | 14.217375 | 12.878004 | 18.531411 | 19.348655 | 19.450579 |
| Yaw (deg) | 75.456424 | 60.787680 | 159.707691 | 169.978680 | 172.428354 |

## Mechanism diagnostics

LC-update rows (Q=5), 11 rows:

| Quantity | RMSE | MAE | P95 | P99 | Max |
|---|---:|---:|---:|---:|---:|
| East (m) | 4.985397 | 4.391053 | 8.167979 | 8.963100 | 9.161880 |
| North (m) | 14.829106 | 14.515009 | 17.836559 | 18.008162 | 18.051063 |
| Up (m) | 9.981728 | 8.737683 | 17.561678 | 17.699057 | 17.733402 |
| Horizontal (m) | 15.644698 | 15.342632 | 17.993857 | 18.203478 | 18.255884 |
| 3D (m) | 18.557787 | 18.469675 | 19.994852 | 19.998889 | 19.999899 |
| Roll (deg) | 3.771094 | 3.107063 | 7.144390 | 7.534060 | 7.631477 |
| Pitch (deg) | 8.554417 | 7.791456 | 11.614305 | 11.845506 | 11.903306 |
| Yaw (deg) | 24.597616 | 24.493767 | 27.677234 | 27.712443 | 27.721245 |

INS-only propagation rows (Q=3 excluding the alignment row), 68 rows:

| Quantity | RMSE | MAE | P95 | P99 | Max |
|---|---:|---:|---:|---:|---:|
| East (m) | 126.683056 | 112.514963 | 183.876220 | 187.911334 | 188.456757 |
| North (m) | 63.210494 | 57.472282 | 78.603528 | 78.745934 | 78.760373 |
| Up (m) | 193.702604 | 179.477154 | 221.724876 | 221.810022 | 221.867400 |
| Horizontal (m) | 141.577411 | 127.355459 | 199.797905 | 202.627611 | 202.979627 |
| 3D (m) | 239.926785 | 221.144841 | 296.721181 | 298.497870 | 298.704019 |
| Roll (deg) | 16.333461 | 15.718005 | 20.465957 | 21.361302 | 22.129421 |
| Pitch (deg) | 15.032190 | 13.889505 | 18.953628 | 19.364137 | 19.450579 |
| Yaw (deg) | 81.180584 | 67.163960 | 162.105386 | 170.350782 | 172.428354 |

These two groups are mechanism diagnostics and do not replace the overall native-support result.

## Common-support diagnostic

Raw six-method literal timestamp intersection at 1e-6 s is 0 rows. The reported diagnostic is therefore explicitly `COMMON_SUPPORT_REFERENCE_INDEPENDENT_BRACKET_INTERPOLATION_DIAGNOSTIC`, not a raw-row strict intersection. The target grid is the 77 formal-window GINav epochs that lie inside every comparator's closed support. GINav rows are unchanged. Comparator position is linearly interpolated in ECEF; roll, pitch, and yaw are each unwrapped then linearly interpolated from adjacent legal rows. There is no time shift, nearest search, reference-selected transform, or method rerun.

| Method | H RMSE m | 3D RMSE m | Roll RMSE deg | Pitch RMSE deg | Yaw RMSE deg | Rows |
|---|---:|---:|---:|---:|---:|---:|
| GINAV | 130.818726 | 219.883711 | 14.936207 | 14.107015 | 69.753332 | 77 |
| LC01 | 0.183382 | 0.396799 | 1.327965 | 1.572475 | 3.724302 | 77 |
| F02 | 0.388882 | 0.794818 | 1.090472 | 1.445860 | 2.570997 | 77 |
| F03 | 0.386444 | 0.792490 | 1.089483 | 1.443763 | 2.245774 | 77 |
| A04 | 0.386325 | 0.792306 | 1.089136 | 1.443208 | 2.231055 | 77 |
| F04 | 0.389008 | 0.812469 | 1.090119 | 1.443369 | 2.226267 | 77 |

Full East/North/Up/Horizontal/3D and roll/pitch/yaw RMSE, MAE, P95, P99, and max values for all six methods are in `C00_COMMON_SUPPORT_COMPARISON.csv`.

## Interpretation

The native-support accuracy itself exceeds the exact evaluator's descriptive position/attitude thresholds, while availability is also limited by late alignment and low SPP-fed LC availability. Original errors are preserved without parameter changes or reruns. Accordingly the accurate applicability statement is `EXACT_OFFICIAL_ROUTE_WITH_POOR_BY2_ACCURACY_AND_AVAILABILITY`. The no-output front portion is not deleted and is not presented as full-window superiority.

## Zero-rerun evidence

- GINav, official sample, LC01, F02, F03, A04, F04, and Canonical-541 runner execution counts are all 0. Exact evaluator execution count is 10 and is tracked separately.
- Frozen `REUSED_NOT_EXECUTED.json` states G4 recovery execution count 0; the full-duration status states `rerun_count=0`.
- Exact pre/post `(size, mtime_ns, ctime_ns)` snapshots of all consumed frozen inputs, comparator NAVs, and exact manifests are unchanged: `True`.
- Main and clean3 worktree Git status snapshots have no new change: `True`.
- The offline Python transaction and its exact-evaluator children were recorded under `strace -f -e trace=execve,openat`; the audited transaction contains 16 successful execve calls, limited to `/usr/bin/python3` and `/usr/bin/git`; 10 are exact evaluator calls and 0 are solver/sample/Canonical runner calls. The raw trace is removed after this summary is finalized.
- No MATLAB, GINav solver, official sample, Canonical runner, or other solver binary is invoked. No repo file is modified, staged, committed, pushed, merged, or tagged.
