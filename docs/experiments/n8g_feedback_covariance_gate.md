# N8G Feedback Covariance Gate

N8G uses a conservative covariance proxy because early FGO covariance is not a
formal calibrated covariance.

Policy:

- inflate covariance from residual proxy and factor balance;
- enforce floors and caps;
- do not shrink `R`;
- reject or skip feedback when correction norms exceed gates;
- use only solver-visible quantities;
- do not tune from trace/final_v23 outputs.
