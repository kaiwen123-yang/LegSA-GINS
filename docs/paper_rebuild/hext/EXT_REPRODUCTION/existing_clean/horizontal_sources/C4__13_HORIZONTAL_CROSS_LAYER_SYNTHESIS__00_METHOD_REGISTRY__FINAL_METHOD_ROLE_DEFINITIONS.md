
# Final method role definitions

## Frozen count

- Registered entities: **11**.
- Formal methods: **10** = 3 Layer-A raw methods + 2 Layer-B solution-level LC methods + 1 Layer-C proprioceptive method + 4 internal methods.
- `EXT04` is the eleventh registered entity but is not counted as a formal method.

## Layers

- `LAYER_A_RAW_DUAL_ANTENNA`: RAW01/EXT01, RAW02/EXT02, RAW03/EXT03. These are the three formal raw-carrier ambiguity/heading methods. Their native state vocabularies remain distinct; none provides a full navigation trajectory.
- `LAYER_B_SOLUTION_LEVEL_LC`: LC01 Pavlasek and LC02 GINav. Both provide full navigation output, but they do not use the same information: LC01 directly uses two receiver position solutions and their rigid relative vector; GINav uses a single raw rover stream and official internal SPP.
- `LAYER_C_PROPRIOCEPTIVE_OBSERVABILITY`: Hartley contact-aided InEKF. Its admissible evidence is native state execution, gauge equivalence, numerical observability, and topology-conditioned NIS—not absolute position/yaw RMSE.
- `INTERNAL_LEGSA_METHOD`: F02, F03, A04, F04. Their formal C00 rows share the Canonical contract and their robustness evidence comes from the completed Canonical-541 aggregate.

## EXT04

`EXT04_WU2025` is simultaneously `SUPPLEMENTARY_DIAGNOSTIC_MODULE`, `PAPER_DERIVED_POLICY_BASELINE`, and `NOT_COUNTED_IN_THE_THREE_PRIMARY_RAW_METHODS`. Only Section II-A / Eqs. (1)–(4) ambiguity-module logic is closed; the exact PAR policy is under-specified, and every declared C00 policy branch has zero accepted epochs.

## Primary-table meaning

`primary_table_eligible=true` means the method has a legal absolute full-navigation C00 evaluation. It does not assert identical time support or identical online information. Cross-layer evidence must not be interpreted as a flat ranking of filter equations.
