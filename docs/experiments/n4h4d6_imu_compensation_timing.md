# N4H4D6 IMU Compensation Timing

The compensation timing audit checks whether each process-data-compatible IMU increment is compensated exactly once before propagation.

The input IMU has already been converted from Go2 FLU to FRD during process-data generation, so LegSA-v23-core must not perform a second frame conversion. The diagnostic also marks res=3 interpolation paths where split IMU increments may need closer review.

This is diagnostic-only and is not a solver fix.

