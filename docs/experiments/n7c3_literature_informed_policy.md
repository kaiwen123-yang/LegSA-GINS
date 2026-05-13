# N7C3 Literature-Informed Policy

N7C3 follows the N7B4 literature review principles already recorded in the
repository: probabilistic contact is preferred to brittle hard thresholding,
contact-aided estimation must not silently treat contact as truth, and foot/body
velocity consistency should remain a weak diagnostic source when non-slip
assumptions are uncertain.

The bounded adaptive std policy is not a copied paper formula. It is a local
engineering policy that uses those principles to keep Go2 horizontal velocity
constraints weak, bounded, and explainable for low-speed Go2 experiments.

The policy also uses robot-appropriate diagnostic limits: N7C3 does not emit
`8 m/s` or `10 m/s` horizontal velocity std values. The extreme diagnostic cap
is `5 m/s`.

Boundary:

- Go2 velocity is not truth.
- No trace/final_v23 tuning.
- No paper performance claim.
- No outperform-final_v23 claim.
