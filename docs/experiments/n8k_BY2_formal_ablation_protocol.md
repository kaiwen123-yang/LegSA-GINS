# N8K BY2 Formal Ablation Protocol

The formal ablation matrix contains:

- core additive chain variants `A0` through `A8`;
- feedback sanity and diagnostic variants `B0` through `B4`;
- removal ablations from the selected system `C0` through `C9`;
- no-feedback FGO comparison variants `D0` through `D5`.

Each variant records active modules, feedback mode, gate/covariance policy when
applicable, run status, engineering metrics, gross-degradation flag, caveat,
and claim-boundary booleans.

N8K uses prior stage runtime evidence and N8J selected-policy outputs. It does
not change solver math or retune feedback policy.
