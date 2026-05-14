# N8F Contact-Aware Weighting Factor

The contact-aware layer is not a state observation factor. It computes
`contact_weight_scale(t)`, `support_confidence(t)`, and `slip_risk(t)` from Go2
contact/support/mode evidence and applies them as conservative R scaling for
legged proprioceptive factors.

Policy:

- High support and low slip reduce R scale.
- Low support, high slip, or high uncertainty increase R scale.
- Contact probability is not hard contact truth.
- The layer has no direct residual and no state Jacobian.
- No trace/final_v23 tuning is allowed.

