# LSE01 Hartley H5 BY2 Native Report

Terminal status: `PASS_LSE01_H5_BY2_NATIVE_RUN_COMPLETE`.

The production backend was `HARTLEY_IJRR2020_REPORTED_BACKEND`: Eq. 50 exact ZOH mean, analytical right-invariant Phi from Eqs. 58/60, and paper-reported Eq. 61 process covariance. No real-data Eq. 52 or official-early-backend run occurred.

## Storage and provider

The read-only Windows query reported G: as exFAT, `Warning`, `Full Repair Needed`. No repair was invoked. Execution and native freeze therefore used Linux-local ext4 scratch; only the final compact evidence was copied to the existing LSE01 stage and verified byte-for-byte.

The immutable provider contains 63,277 complete records. Raw SHA-256 is `95859de46925416f0a094f8986ef4f8cb452cab71b264702705a9f9aff95a278`; complete-prefix SHA-256 is `03cd96cd65d7f5af30f6a0c78d37f07ae4d32c65e78531807db7192454dff097`; cache SHA-256 is `c169e26d66f35fe200bb17a695353cd2d751482df1cd97996a7a8afff8662065`; contact-event-ledger SHA-256 is `8e80cde9b90ade49753d8fd97e554af3c032c664d1d336f663838cbb68204358`. One trailing incomplete record was excluded in full. The successful provider audit decoded zero forbidden values and opened the raw file read-only.

## Initialization

The exact first `[t0,t0+5 s)` window contained 1,031 rows. Median gyro norm was `0.015289419 rad/s`; median accelerometer norm was `9.507909327 m/s^2`. Initial roll/pitch/yaw were `[0.015716258, 0.013862286, 0] rad`; gyro bias was `[-0.007665563, 0.002694814, 0.001109327] rad/s`; accelerometer bias was `[0.004183978, -0.004743054, -0.301767962] m/s^2`. The stationary world-frame acceleration residual norm was `1.78e-15 m/s^2`.

## Native execution

All four preregistered runs completed in order. Each produced 63,277 state/covariance/NIS rows, 63,276 propagations and Eq. 61 calls, 63,177 stacked survivor updates, 136,327 maintained-contact measurements, 4,706 add/remove events excluding the four initial additions, and 3,654 deterministic full-covariance checkpoints. Every state dimension equalled `15 + 3N`; all rotations, states, covariance diagonals, factorizations, checkpoint symmetries, and checkpoint PSD gates passed. Dropped, nonfinite, Eq. 52, encoder-adapter, reference, and trace counts were zero.

| Branch | Final position m | Final velocity m/s | Final gyro bias rad/s | Final accel bias m/s^2 | Innovation p50/p95 m | NIS p50/p95 | Runtime s |
|---|---|---|---|---|---|---|---:|
| Primary Go2 Allan, FK 10 mm | `[22.9409,54.0283,-2.3472]` | `[-0.172728,0.476158,0.213000]` | `[-0.009125,0.002512,-0.038614]` | `[-0.671895,0.202804,-0.354799]` | `0.007578/0.019657` | `0.909752/5.578896` | 3.44060 |
| FK 5 mm sensitivity | `[19.7237,55.6464,-3.1768]` | `[-0.325484,0.391484,0.189079]` | `[-0.009189,0.002602,-0.039821]` | `[-0.678632,0.233811,-0.353531]` | `0.004775/0.012300` | `1.03105/6.150152` | 3.63222 |
| FK 20 mm sensitivity | `[30.9351,49.2431,-1.3844]` | `[0.163058,0.473086,0.252655]` | `[-0.008963,0.002421,-0.036235]` | `[-0.658166,0.165297,-0.357370]` | `0.012570/0.034272` | `0.755901/5.102616` | 3.45874 |
| Paper process regression, Go2 FK proxy | `[-111.5505,36.0632,-8.0403]` | `[0.016399,0.079723,0.000824]` | `[-0.005096,-0.000085,0.008438]` | `[0.101189,-0.097677,-0.383923]` | `0.002194/0.006124` | `0.078806/0.565209` | 3.62831 |

The paper branch is `PAPER_PROCESS_PARAMETER_REGRESSION` with `WITH_NONPAPER_GO2_FK_PROXY_MEASUREMENT_ADAPTER`. Its five process parameters use the typed Eq. 61 adapter; the one-degree encoder parameter is excluded. Native-only RMS differences from primary `(rotation rad, velocity m/s, position m, gyro-bias rad/s, accel-bias m/s^2)` were FK05 `(0.248101,0.337410,12.5747,0.00112153,0.0231624)`, FK20 `(0.430822,0.547796,22.5508,0.00189795,0.0324017)`, and paper-process `(1.52482,1.45249,111.869,0.0313690,0.821926)`. These are non-ranked self-comparisons, not accuracy results.

## Closure

The committed H5 implementation is `4b25fa6337f4760557f501f102a38a1ac65c766e` from task-start HEAD `b1b3b0ec5e5d811c1658541a98b660f326500ac3`. Focused Hartley tests passed `88/88`; CTest passed `2/2`; the full paper-rebuild suite reported `936 passed, 10 skipped, 2 unchanged unrelated failures`. The final runtime payload is 63 files / 464,203,138 bytes and is hash-identical between scratch and G:.

No reference, trajectory trace, EXT01-EXT06 solver, HORIZONTAL18, Canonical-541, official-early real-data branch, H6 ensemble, or H7 evaluation was executed. H6 remains unauthorized.
