# N7A decision

Decision states:

- `not_activated`: Go2 roll/pitch weak prior update count is zero.
- `frame_contract_issue`: quaternion/rpy or frame/sign checks block activation.
- `needs_prior_noise_policy_fix`: clean replay grossly degrades.
- `ready_for_extended_go2_priors_or_FGO_preparation`: weak prior activates and remains clean-neutral/stable.
- `ready_with_weak_go2_evidence`: prior activates but evidence is weak.

N7A is engineering evidence only. It does not claim paper performance, does not claim outperform final_v23, does not implement FGO, does not delete epochs, and does not do output-only correction.

PR #21 remains a self-written LegSA-v23-core parity failure evidence branch and is not merged by N7A.
