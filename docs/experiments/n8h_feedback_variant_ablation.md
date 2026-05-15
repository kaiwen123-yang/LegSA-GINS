# N8H Feedback Variant Ablation

N8H reviews the seven N8G variants:

- baseline no feedback;
- velocity plus attitude feedback;
- horizontal velocity plus attitude primary feedback;
- diagnostic position/velocity/attitude feedback;
- velocity-only feedback;
- attitude-only feedback;
- reject-all sanity.

For each variant, the review records observation rows, EKF update/accept/reject
counts, correction norms by state block, evaluation namespace, baseline delta,
gross-degradation flag, largest correction epochs, gate status, and
substitution/override boundary flags.

The reject-all sanity variant must have zero accepted EKF feedback updates and
must match the no-feedback baseline within the runtime comparison tolerance.
