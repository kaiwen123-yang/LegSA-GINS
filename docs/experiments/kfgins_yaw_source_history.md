# KF-GINS Yaw Source History

N4H2C-runtime audits the external KF-GINS source tree in read-only mode to understand whether yaw update behavior may differ between the actual dual_final_v23 run and the current replay runtime.

The source audit searches for:

- `gnssdata.yaw`
- `gnssdata.yaw_std`
- `H_gnssyaw` and `R_gnssyaw`
- yaw residual wrapping
- `scheme_C` downweight or gate evidence
- heading-to-math or 90-degree transform variants
- `stateFeedback` and related filter flow markers

The history audit uses read-only git log and grep commands. It does not checkout historical commits, reset branches, modify source, or copy external code into this repository.

Outputs identify:

- whether the current source appears to load yaw measurement
- whether a yaw update appears enabled
- the residual formula evidence status
- the yaw measurement transform evidence status
- possible source-version mismatch evidence
- candidate commit and branch counts

Boundary:

- `EXTERNAL_KFGINS_ROOT` is read-only
- no external source is copied
- no solver output is modified
- no performance claim is made
