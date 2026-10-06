
# Horizontal comparison completeness audit

## Audit result

The current comparison is **algorithmically comprehensive for the stated cross-layer claims**. It registers 11 entities and counts 10 formal methods: 3 raw dual-antenna methods, 2 solution-level LC methods, 1 proprioceptive observability method, and 4 internal methods. EXT04 is the additional supplementary diagnostic module.

## Technical-route coverage

| Required route | Evidence identity | State |
|---|---|---|
| constrained integer least squares / C-LAMBDA | RAW01 / EXT01 | covered, C00 applicability limited by unresolved fractional phase bias |
| wrapped least squares | RAW02 / EXT02 | covered, accepted wrapped outputs but poor physical applicability |
| recursive DD filtering + M-LAMBDA | RAW03 / EXT03 | covered, all ten frozen modes retained |
| solution-level dual-receiver invariant filtering | LC01 Pavlasek | covered, full standalone C00 valid |
| standard single-receiver official LC | LC02 GINav | covered, exact official route with poor availability and accuracy |
| proprioceptive contact-aided state estimation and yaw gauge | LSE01 Hartley | covered structurally; absolute RMSE not legal |
| internal Basic / Strong / Core / Full | F02/F03/A04/F04 | covered by formal C00 and Canonical-541 aggregate |

No claim-required route is currently missing, so the default action is not to add more external algorithms.

## Identity and support checks

- RAW primary count is exactly three: RAW01/RAW02/RAW03. EXT04 is excluded from that count.
- LC01 and GINav formal metrics retain their own legal C00 support. GINav’s 28.0% row coverage is visible alongside its severe errors.
- Hartley absolute position/yaw metrics remain null.
- F02/F03/A04/F04 C00 rows are exact `case_id=C00_clean_normal` UNIQUE rows; 541 means use a separate record type and scope.
- A04/F04 current yaw RMSE is 1.9340756561653565° / 1.9549590248265367°. The 77-epoch 2.2310550147062354° / 2.226266687869817° values are diagnostic only. Legacy 1.813898158169119° is not current Canonical C00.
- Fixposition is a same-source offline evaluation reference, not independent ground truth.

## True remaining evidence gaps

1. Independent ground truth with closed pose-point and attitude-frame lineage.
2. Additional real platform or sequence generalization.
3. A real one-side antenna-occlusion sequence.
4. Cross-platform generalization.
5. Publication-quality plotting and linkage after the separate parallel Canonical plotting task completes.

These are more material than adding another horizontal algorithm. This task did not inspect, wait for, monitor, or modify the plotting task.

## Execution audit

All solvers, external methods, Hartley, MATLAB, the exact evaluator, Canonical runner, Classic-18, and plotting runner have execution count 0 in this task. Only frozen CSV/JSON/MD artifacts were read and synthesized.
