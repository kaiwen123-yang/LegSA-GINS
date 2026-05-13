# N7C5A Go2 Full Proprioceptive Visual Review

N7C5A reviews the N7C5 Go2 full-field mining outputs before any additional
activation step. It generates a structured figure catalog for field inventory,
contact probability, foot kinematic velocity, mode/gait phase, yaw-rate,
relative odometry, and factor ranking.

The review is diagnostic engineering evidence only. It does not activate a new
factor, does not tune from trace/final_v23 output, and does not treat Go2
body-state, contact, roll/pitch, velocity, or position as truth.

Required runtime outputs:

- `N7C5A_VISUAL_SANITY_REPORT.json`
- `N7C5A_PLOT_DATA_COVERAGE_REPORT.json`
- `N7C5A_VISUAL_DECISION_REPORT.json`
- `N7C5A_FIGURE_MANIFEST.json`
- `n7c5a_visual_case_review.md`

If the decision status is `n7c5_visual_blocker`, N7C6 must not run. If the
status is `n7c5_visual_review_passed`, N7C6 may evaluate the joint
proprioceptive observation factor.
