# LSE01 final Hartley claim boundary

Terminal: `BLOCKED_LSE01_H7C_REFERENCE_LINEAGE_CONTRADICTED`.

- The algorithm core is a faithful IJRR2020-reported Hartley backend.
- The BY2 adaptation uses a Go2 high-level FK-like proxy, not raw joint/URDF FK.
- The theoretical and structural comparison is complete.
- Global position and global yaw about gravity are unobservable gauges.
- Full reference performance exists only if the fixed
  `T_FP_POI_from_GO2_BODY_IMU` extrinsic is source-proven. H7C stopped before
  that search because the required exact trace-to-POI lineage identity was
  contradicted.
- The candidate reference is Fixposition-derived same-source FP_POI output,
  not independent ground truth.
- Hartley must not enter a flat absolute-yaw ranking against LegSA.

The trace and `user_io-out-poi_geodetic` each contain 6,040 ordered,
chronological rows under the mapping frozen before numerical comparison.
Their mapped values differ only at tiny CSV serialization scale, but the
required row-wise exact identity is false. The exact parsed-binary diagnostic
and the separately preregistered exact-Decimal serialization-cell diagnostic
both remain failed evidence; no post-result tolerance was introduced.

H2-H5, FP_POI full-pose semantics, the frame graph, the Go2-to-FP_POI
extrinsic search, and every reference-relative metric are
`NOT_EVALUATED_AFTER_H1_LINEAGE_CONTRADICTION`. Absolute-yaw RMSE and absolute
global-position RMSE remain JSON `null`. LSE01 is not complete,
`ready_for_ext06=false`, and EXT06 was not executed.
