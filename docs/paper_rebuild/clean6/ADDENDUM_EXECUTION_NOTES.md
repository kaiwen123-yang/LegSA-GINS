# Addendum execution bookkeeping notes

These records distinguish controller bookkeeping from native algorithm/evaluator outcomes. They do not recompute metrics or change the preregistered hypothesis decisions.

| Event | Preserved scene | Resolution |
|---|---|---|
| UTF-8 BOM reader failure after the first completed v3 evaluator | 99 completed native outputs; 1 completed v3 evaluator; original stop and current post-stop evaluator snapshot retained | `3a61d157ef82af4bfb12f3d1f5c6491742da592c`; decode the BOM, finish sidecars from the existing evaluator output, then evaluate only previously unstarted identities |
| Intentional SIGINT during repeated storage-directory accounting | 99 completed native records; 198 completed evaluator identities; 54 matching verified archive receipt pairs; no partial archive, cleanup or batch 2 | `9802311754fdc49f151ff36b4ffbff715085dfd9`; separate I/O controller with immutable-subtree accounting and unchanged scientific modules |
| First I/O service launch lacked the package search path | Python failed to import `legsa_gins` before entering the controller; provider/native/evaluator/archive calls all zero; continuation directory had not been created | Set `PYTHONPATH=<CODE_ROOT>/src`; entry `--help` passed; start a new service and log with the same frozen code |

The native and evaluator invocation identities are not repeated by these resolutions. The initial BOM event is a derived-output reader failure; the SIGINT is an intentional bookkeeping interruption; the import error is a launcher-environment failure. None is relabelled as `ALGORITHM_FAILURE_ALL_YAW_REJECTED`.

The I/O service is invoked with `scripts/paper_rebuild/clean6_continue_addendum_archive_io.py`, the ignored local config, unchanged addendum contract, and `<HANDOFF_ROOT>/P09D_P10_AUDIT/ARCHIVE_IO_INTERRUPT_TERMINAL.json`. The service explicitly sets `PYTHONPATH=<CODE_ROOT>/src`, `PYTHONDONTWRITEBYTECODE=1`, and the registered numerical thread limits. The standalone I/O entry requires that package search path in an environment without an installed editable package.

External launcher evidence remains at `<HANDOFF_ROOT>/P09D_P10_AUDIT/ARCHIVE_IO_LAUNCH_ENVIRONMENT_FAILURE.json`; the failed log `ARCHIVE_IO_EXECUTION.log` has SHA-256 `0682f37bc90c2717e905eb3c8e556bb3d7deac837e2ed351de5dab9703435f9d`. The environment-corrected service writes `ARCHIVE_IO_ENV_EXECUTION.log`. These external launcher records are distinct from the sealed scientific results.

The final 495-run counts, both evaluator partitions, hypotheses and all favorable/unfavorable pairings belong to [ADDENDUM_FAMILIES_A1_A2_RESULTS.md](../ADDENDUM_FAMILIES_A1_A2_RESULTS.md), generated only after terminal and seal validation. This execution-note file does not itself assert final completion.
