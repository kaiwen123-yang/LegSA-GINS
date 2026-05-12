# N7B2A Contact V2 Physical Sanity

N7B2A audits whether the diagnostic contact-state v2 candidate is physically
plausible before any future Go2 velocity/contact activation.

Checks:

- `contact_ratio_all_feet`
- `per_foot_contact_ratios`
- `swing_ratio`
- `uncertain_ratio`
- `alternating_contact_ratio`
- `foot_speed_during_contact`
- `walking_contact_plausibility`
- `all_contact_suspect`
- `contact_too_permissive`
- `contact_too_conservative`
- `physical_plausibility_status`

Rules:

- If contact ratio is effectively all-contact while walking ratio is high,
  `all_contact_suspect=true`.
- If `alternating_contact_ratio < 0.3`, physical plausibility is
  `review_or_not_ready`.
- If foot speed during contact remains high, `contact_too_permissive=true`.
- If uncertain ratio is above 0.5, `contact_too_conservative=true`.

N7B2A must not mark contact ready for Go2 velocity/contact weak prior activation
when physical plausibility is review or not-ready.

The audit does not use trace or final_v23 output to tune contact thresholds.
