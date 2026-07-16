# LegSA-GINS Clean Rebuild Plan

## Current Stage

`CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18`

CLEAN1R2R1 closed exact-source final_v23 parity, strong-baseline identity, and
fresh four-method BY2 clean-normal execution. PR #59 was guarded-merged with a
merge commit and tagged as the CLEAN1 milestone before this branch was created.

## CLEAN2 Gates

1. Freeze and test the 16-entry RD/SA/RP/HV matrix, current-provider Classic-18
   mapping, deterministic case policies, 110-run registry, and offline formulas.
2. Form a clean code-freeze commit before provider generation or formal runs.
3. Verify raw 22/22 before provider generation, after provider generation, and
   after formal execution, with mutation zero.
4. Freshly regenerate the five C00 inputs/providers and require exact CLEAN1
   content-hash parity.
5. Pass the four-role C00 structural gate without opening trace or inspecting
   error metrics.
6. Run exactly 110 unique processes and seal every output before offline trace
   evaluation.
7. Cross-check clean factorial, controlled canonical, sentinel LOO, action, and
   finite-output aggregates; render diagnostic-only figures with machine QA.
8. Obtain read-only review, publish one Draft PR, and create only one terminal
   export ZIP. Do not merge or tag CLEAN2.

Classic-18 is a real-data-based controlled dual-yaw degradation pilot, not 18
real scenarios. Neither a pass nor a favorable metric establishes universal
superiority.

## Next Stage

No next stage is authorized. BY3/XB and the D01-D60 x 9 matrix remain
unexecuted and require separate human approval.

Detailed rules live in `docs/paper_rebuild/`.
