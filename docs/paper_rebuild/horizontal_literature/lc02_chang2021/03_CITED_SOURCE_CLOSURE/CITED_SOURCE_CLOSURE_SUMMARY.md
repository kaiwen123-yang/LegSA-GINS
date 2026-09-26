# Cited-source closure summary

Zhao’s institutional dissertation closes the CKF identity question: for a linear system, the CKF moment recursion collapses through EKF to the ordinary KF printed by Chang. This supports enum A and does not authorize adding cubature-point machinery.

Yang’s cited navigation lineage supplies useful ENU/body context but does not reproduce Chang’s 15-state body-attitude signs, full dynamics, noise discretization, nominal mechanization, feedback/reset, lever arm, or initialization. Its explicit model is materially different.

The strong-tracking chain does not define an inverse of Chang’s rectangular observation matrix. Gao’s observed-only multiple-fading construction demonstrates that a plausible repair exists, while also demonstrating non-uniqueness. The standard TSK normalized weighted average found in the cited fuzzy lineage is likewise only a candidate: Chang does not print firing, normalization, aggregation, or clipping.

Thus cited sources close the base linear-recursion identity but do not close the hard semantics required for a faithful FSTCKF implementation.
