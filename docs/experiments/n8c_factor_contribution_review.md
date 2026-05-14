# N8C Factor Contribution Review

N8C reviews whether default active factors show visible contribution in N8B/N8C diagnostics.

Factor statuses:

- influential
- weak_but_active
- consistent_no_large_delta
- inactive_diagnostic
- suspicious_no_effect

The review explicitly checks receiver position, receiver velocity, dual yaw, raw Doppler, Go2 joint, smoothness, and diagnostic candidate factors.

If a factor is active but lacks direct residual/update evidence, N8C flags it for follow-up rather than making a performance claim.
