# N8G Feedback EKF Plan

N8G is the planned feedback stage after N8F. It is not implemented in N8F.

N8G target:

- Use FGO smoothed results as conservative pseudo-measurements to EKF.
- Do not directly replace EKF NAV.
- Use FGO covariance or conservative fallback covariance.
- Add a feedback residual gate.
- Add a correction norm limit.
- Record `feedback_count`, accepted feedback, and rejected feedback.
- Output NAV / STD / EVAL artifacts for runtime review.
- Check whether the system becomes a true filter plus FGO joint filter.

N8F remains no-feedback. N8F outputs may support N8G design review, but they do
not feed back into EKF and do not substitute EKF navigation output.

