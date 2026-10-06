# Exact-search factor caching: paired real-input benchmark

All 9 registered problems and 18 searches completed. Both versions certify 6 paired problems; all such pairs preserve the same two full integer vectors, constrained baselines and objective within the registered tolerance.

| Cap | Start s | Baseline s | Cached s | Certificates old/new | Speedup when both certified |
|---|---:|---:|---:|---|---:|
| 6 | 100 | 3.432859 | 2.685087 | True/True | 1.278 |
| 6 | 110 | 10.247680 | 8.326010 | True/True | 1.231 |
| 6 | 148 | 0.205821 | 0.169024 | True/True | 1.218 |
| 6 | 168 | 7.414082 | 5.872415 | True/True | 1.263 |
| 6 | 182 | 15.587776 | 12.573770 | True/True | 1.240 |
| 6 | 318 | 30.007928 | 29.702340 | False/True | NA (censored) |
| 6 | 330 | 30.012463 | 30.015983 | False/False | NA (censored) |
| 6 | 336 | 30.022134 | 30.028390 | False/False | NA (censored) |
| 8 | 168 | 7.488056 | 5.964366 | True/True | 1.255 |

Median paired speedup among the 6 jointly certified selected problems: 1.248. This is a small diagnostic sample with one execution per version and case, not a general throughput estimate.

Same 100000-node/30-second limits, sequential single-thread numerical libraries, alternating order. Timeouts remain censored and have no measured completion-speed ratio. Solver setup and factor construction are included in whole-solve time. No admission, tracking, navigation or reference evaluation ran here.

The optimization changes factor reuse and preprunes nodes already rejected by a term of the original bound. It does not alter the integer objective, selected subset, noise, validation gates or certificate requirement. Speed alone does not establish online acquisition availability; preparation, scheduling and delayed-candidate handling remain separate.
