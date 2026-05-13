# N7C2 Go2 Horizontal Velocity Jacobian Visual Audit Prompt

Run N7C2 on the current N7C PR branch.

Scope:

- Add visual-overlap auditing from source data.
- Add alpha/style and delta/zoom readability figures.
- Add factor Jacobian contract reporting for active measurement factors.
- Add toy finite-difference checks for linear velocity contracts.
- Generate runtime-only N7C2 reports and figures.

Do not:

- Modify solver math.
- Tune Go2 horizontal prior std.
- Delete epochs.
- Apply output-only correction.
- Merge PR #38.
- Create an N7C or N7C2 tag.
- Create a new PR.
- Enter N8A.

Claim boundary:

- Go2 horizontal velocity remains a weak prior, not truth.
- Go2 horizontal velocity touches only horizontal velocity states.
- Go2 vertical velocity, Go2 yaw prior, and Go2 position prior remain disabled.
- No FGO claim.
- No paper performance claim.
- No outperform-final_v23 claim.
