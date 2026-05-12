# N7B2 Contact State V2 Definition

The contact-state v2 classifier is a diagnostic candidate. It derives
per-foot force thresholds from Go2 field distributions and uses foot-speed
norms only as supporting evidence.

Labels:

- `standing_contact`
- `walking_contact`
- `swing_phase`
- `uncertain`
- `invalid`

Policy:

- Use force percentile thresholds from Go2 foot-force distributions.
- Use low foot-speed as supporting evidence for weak contact rows.
- Use `mode` and `gait_type` only to separate standing and walking context.
- Require standing rows to have multiple feet in contact.
- Require walking rows to have physically plausible contact counts and
  alternating-contact evidence.
- Apply fixed window smoothing and debounce after the raw v2 classification.
- If walking contact rows do not pass the alternating-contact plausibility
  check, the v2 contact candidate remains `not_ready` even when the uncertain
  ratio is low.

The classifier does not use trace, final_v23 output, or navigation metrics to
choose thresholds. It writes readiness reports only and keeps
`go2_velocity_prior_enabled=false`, `go2_yaw_prior_enabled=false`, and
`fgo=false`.
