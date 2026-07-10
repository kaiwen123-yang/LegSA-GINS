# Clean Rebuild Next Actions

## Finish CLEAN0

- Complete raw hash lock and verify no raw modification.
- Validate the paper-rebuild code/config/tests and build the active core.
- Complete a BY2 `basic_dual_yaw_EKF` smoke from freshly generated raw-derived inputs.
- Confirm `old_runtime_input_count=0` and all forbidden manifest flags are false.
- Complete guarded legacy deletion, storage accounting, and clean GPT-context export.
- Publish the lightweight clean-rebuild branch and PR without merging or creating a clean-release tag.

## CLEAN1 Candidate Scope

After a passing CLEAN0 supervisor/reviewer gate and explicit human approval:

1. Freeze the exact BY2 clean experiment window and evaluator contract.
2. Run clean normal BY2 for the four methods in `methods.yaml`.
3. Review manifests, provider lineage, final-output metric cross-checks, and figures.
4. Decide whether the classic-18 pilot is authorized.

CLEAN1 must not silently expand into the 60x9 matrix, DA03/DA05, selected feedback, active 9F FGO, QA fallback, or paper performance claims.
