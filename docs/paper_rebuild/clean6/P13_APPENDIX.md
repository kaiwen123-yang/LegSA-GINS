# P13 appendix

## 2026-09-14 human adjudication

All five draft conflicts B01-B05 are resolved in SENSOR_MODEL_V21_CONTRACT.yaml. The old binary, v1/v2 outputs, original decision rules and Outcome remain preserved. The new native binary changes only the F02 fixed-yaw-standard-deviation guard to also accept 2.933193 degrees. This value is below the unchanged scheme-C soft threshold of 3.0 degrees.

The identity bridge uses unchanged CAL C00 inputs and std=1.5 with both binaries across all eleven profiles, comparing the four NAV/STD files byte-for-byte. It precedes all v2.1 use of the new binary.

## Validation definitions fixed before providers

- HV residual reproduction uses the inverse-scaled new provider, retaining exact P-11b samples and statistics; final scaled residuals are reported separately.
- GNSS source hashes remain fixed. New nominal and case tables preserve non-yaw_std tokens against their corresponding unchanged/injected reference. Every nominal yaw_std token is 2.933193. Frozen fault handlers are then applied in their original order: a registered yaw_std multiplier (including D28) multiplies this new nominal value in the actual injected yaw_std column. The gate compares against the same frozen handler applied to the nominal v2.1 table, rather than erasing the registered fault to enforce a constant injected column.
  The final document generator explicitly limits the constant-column gate wording to the three nominal base tables and states the preserved injected multipliers; this is a wording clarification of the same gate, with no provider or result change.
- Existing frozen_parameter_hash is unchanged. SENSOR_MODEL_V21 is separately hashed as three correction groups; runtime/provider diffs remain explicit.
- Case-specific injected A1 determines HV rotation/support. Fully absent A1 makes all HV invalid; missing source Go2 validity is never promoted.
- F01 sampling is C00 plus 49 non-C00 core cases ordered by SHA256 of P13_F01|case_id; the contract contains all fifty identities. Its seven scientific output files are compared to the original full-file seals, never to downsampled substitutes.
- H7 uses the existing evaluator yaw_abs_error_over_std_median. H7-H11 are reported by applicable profile/sequence/seed and evaluator; no post-hoc pooling changes a failed or missing component. Definitions are recorded in the contract.
- BY2 clean sequence and core C00 are the same ten rerun identities: 5890 requested entries, 5880 unique main-chain reruns, 50 F01 audit runs and 22 bridge runs; downstream diagnostics are recorded separately.

## Stop policy

Only non-preregistered native solver failure, evaluator failure/nonfinite results, F01/bridge/HV-RP reproduction failure, or batch archive failure above one percent stops this task. Validation mechanism, bookkeeping and wording conflicts are resolved by preserving science and recording the exact disposition here. No completed solver/evaluator run is silently repeated.

## Execution records

Contract preparation only at this entry: provider, solver, evaluator and plotting calls are zero. Subsequent entries record exact commands, identities, gates, bookkeeping adjustments and terminal states.

## Binary build implementation

The implementation stores BINARY_FREEZE.json beside the bridge evidence at 01_BINARY_BRIDGE/BINARY_FREEZE.json; the controller resolves this path instead of the initial 00_PREREGISTRATION label. This changes bookkeeping only. Independent read-only review passed the sole native source change and bridge implementation before launch.

## Binary bridge and provider implementation freeze

At code commit ca73cb1fb48a020fd2a450d79e520562c34eeb24, the bridge completed 22 native calls and passed all 44 full NAV/STD comparisons across C00 and eleven profiles. The old executable SHA256 is 9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f; the new executable SHA256 is 96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c. Provider and evaluator calls in the bridge are zero.

The provider implementation passed independent read-only review and 17 focused tests before real provider generation. Eight downstream adapter tests also passed without provider, native or evaluator execution. These implementation checks do not replace the pending real three-sequence residual gates.

## Three-sequence real provider gate
Provider commit: d01f2be8fb0ef1633d4871ec57b0e6d4e9de44a7. Raw PRE checkpoint: 22/22 PASS. Provider access audit: zero forbidden opens, zero raw writes, zero writes outside the owned output root.
| Sequence | HV matched n | Inverse-k sigma (m/s) | Final scaled sigma (m/s) | Corrected static pitch mean (deg) | Statistics compared | Maximum absolute difference |
|---|---:|---:|---:|---:|---:|---:|
| BY2 | 16968 | 0.13283767493317 | 0.131450299108858 | -0.444112110441446 | 183 | 8.3266726846886741e-17 |
| BY2H | 17558 | 0.210120538793595 | 0.211255196456088 | -0.420844093009067 | 183 | 2.7755575615628914e-17 |
| BY2O | 23022 | 0.106398459795671 | 0.103633801029819 | -0.412028739877216 | 233 | 1.1102230246251565e-16 |

All three residual gates pass 1e-6. Nominal 15/18-column GNSS non-yaw_std token equality and all-2.933193 yaw_std gates pass for 1510/1483/2231 rows. All three IMU and RD hashes match their frozen V2s pins. Scaled residuals are reported separately from the inverse-k reproduction gate.

## F01 invariant gate and main execution bookkeeping

At cea410a21068edbaaa73691eb9669527ae6b3e08, all 50 preregistered F01 audits completed: 350/350 full-file comparisons passed, 50 lossless archives verified, exact scratch cleanup completed, zero repeat native calls and zero evaluator calls. Formal F01 remains the byte-exact v2 result. Six original reference records reside in the authorized v2 batch-8 I/O recovery ledger; their original seven-file seals match the retained archive receipts.

The main registry contains 5880 unique native identities: 5410 core, 20 additional natural-sequence and 450 addendum runs. There are 23 batches (22 of 256, then 248), with 11760 primary/parallel evaluator terminal slots. BY2 C00 is counted once. F01 bridge/audit and the 21 downstream native jobs are separate ledgers.

The P09c archive-only recovery functions are reused for every batch, including the first archive attempt, to preserve durable receipts and resume partial exact cleanup without repeating native/evaluator calls. Their inherited internal v2 scientific-commit and 5973-denominator labels are retained as pre-correction bookkeeping; P13 wrappers report the actual frozen P13 commit and 5880 main-run denominator. A complete delivery requires zero pending archives and actual two-version/receipt identity closure, not only a batch-controller exit.

Natural-sequence consistency, window segments and body-frame bias are computed from the completed full-rate evaluator errors and original full NAV/STD before rolling cleanup, using the unchanged P05/parity/sequence functions. Frozen evaluator JSON stays intact; P13 diagnostic and evaluation sidecars identify the corrected protocol and semisynthetic case roles. The existing frozen_parameter_hash function is unchanged and is applied to the final YAML including sequence transport. A same-CAL/variant reference separately shows the sole native sensor-field difference, basic_dual_yaw_fixed_std_deg; HV/RP corrections remain provider changes in the separately locked SENSOR_MODEL_V21 group.

Provider, F01, evaluator scheduling, downstream adapter, aggregation and diagnostic unit checks total 60 passing tests before the main run. Main-controller registry and recovery interfaces passed independent read-only review. Real-data gates are reported separately above.

## First main batch: completed execution evidence

`<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21/BATCHES/BATCH_001/BATCH_COMPLETE.json`
has SHA-256 `4d81be9255ef998e29c778c84900a1778b32dcb55931520a807598231d2177da`.
It records 256 completed native runs, 512 completed evaluator terminals, zero
algorithm failures, 256 verified archives, and zero pending archives. The
evaluator pool was 22 and evaluator repeat calls were zero. This is one completed
batch out of 23; it is not a main-matrix completion statement.

The first-batch resource log contains 1,067 samples over 3,126.36970731 seconds.
Its sampled owned-process RSS peak is 4,897,312,768 bytes. Sampled filesystem
growth peaks are 34,722,717,696 bytes for scratch and 7,247,495,168 bytes for G;
the final sampled scratch growth is 29,401,088 bytes. Filesystem figures measure
whole-filesystem changes from this batch's baseline, not exclusive process I/O.
These measurements do not include the preceding binary bridge or F01 audit.

`NATURAL_DIAGNOSTICS_ARCHIVE_CHECK.json` in the same batch directory has SHA-256
`5a34012e53c7440bcd1c3532e805cd4a35dacb5ced167a851034c13590073133`.
After cleanup, all 30 natural-run diagnostic payloads matched their archived
producer seals: 60 evaluation rows, 240 consistency rows, 560 window rows and
60 body-frame rows across v3/v2. This check performed no provider, native,
evaluator or metric-recomputation call.

Before v2.1 rendering, all 124 v2 figure files and all 30 v1 preserved files
matched the original figure-package member pins, including the three MFIG21
exports. The evidence is
`<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21/FIGURE_PREPARATION/PRESERVED_EDITIONS_PRE.json`.
The v2.1 figure packer separately requires exactly 28 registered figures and
84 exports, rejects an MFIG21 subtree, and rechecks the preserved editions.

## Failure-time-series presentation adapter

Before any real v2.1 packaging or rendering, code review found that the new
failure-series manifest did not expose the evaluation-status column consumed
by the nonzero-failure plot branch. The unexecuted packaging/presentation
adapter now records the native-to-evaluation terminal mapping, domain and
source identity. MFIG14 selects the first current CORE F04 failure by the
existing sorted-case rule and binds its same-case new F02 control by run,
dataset, case, method, effective configuration, status and protocol. Both
archive members must come from the corrected chain. No old native timeline is
used. A missing selected timeline is shown as `UNAVAILABLE` with the sealed
failure count; it does not authorize selecting a different case. The zero-
failure statement is explicitly limited to the 541-case core. This validation
and presentation repair changes no scientific run, evaluator, decision rule or
Outcome. Fifteen publication tests and thirteen pack tests passed, including
nonzero and mixed-domain failures, recovered old cases, stale control sources
and missing first-case timelines. Independent read-only review passed.

## Batch-3 cleanup accounting audit

Read-only inspection of the existing batch-3 records found 22,582 deleted
files: 11,931 original files and 10,651 prepared files. Their ledger contains
45,164 durable DELETE_INTENT/DELETED entries. The existing per-item hash,
intent, deletion and completion checkpoints continue unchanged. This audit
performed no new timing experiment, ptrace, scientific call or cleanup action.

## Real failure-timeline metadata check

Within sealed batch 5, BY2/D14_seed_04 has F04 RUN_01346/AB1111 with
ALGORITHM_FAILURE_ALL_YAW_REJECTED and F02 RUN_01344/basic_dual_yaw_EKF with
COMPLETED. Both v2/v3 evaluation terminals follow those native classifications.
Each retained PORT_GNSS_UPDATE_TRACE.csv.gz has 1,369 finite, monotonic time
rows. F02 has NORMAL=273 and NONE=1,096; F04 has REJECT=273 and NONE=1,096.
The compressed SHA-256 values are respectively
`b30890b4abb95c0ee0f66745dcda78e3bce40117ac8da63fab4dc28bcc8b650f`
and `a1928fa3484b73addfb2f1fccea2725a067e01e5b1b5884a63f0bec5366119d3`.
Producer rows, independent receipt references, compressed pins and decompressed
native seals matched. This check is scoped to batch 5 and does not declare the
final matrix's first failure. It generated no figure, package or aggregate and
invoked no provider, native solver or evaluator.

## Checkpoint-export validation

The execution-record exporter uses canonical JSON comparison after indexing
run and evaluator identities, preserving the distinction between boolean,
integer and floating-point values. It binds every native record and batch's
v2.1 execution identity to the independently hashed EXECUTION_FREEZE at
`521901f0347e367281abed23b46686b84df86055`. Inherited archival and mathematical
source commits remain separately labeled. Cleanup accounting requires both
complete INTENT and DELETED inventories to equal receipt-original plus
prepared-plan inventories by path, size and SHA-256. Optional accounting that
cannot be proven is explicitly UNAVAILABLE.

These three bookkeeping checks were tightened during source review before the
first formal checkpoint export. They change no scientific call or stopping
condition. The exporter writes only after the requested batch checkpoint is
closed; its source SHA and complete metadata input pins accompany each export.

## Live evaluator-count display correction

During batch 9, a read-only progress command counted the two evaluator-version
directories as two terminal records. The progress display was corrected to
count JSON records inside both v2 and v3 directories (44 each at the correction).
This affected only the interim message, not the controller, checkpoint exporter,
scientific records, evaluator calls or archived counts.

## Finalization metadata I/O continuation 01

The first finalization process used commit
`e7634926bdfd8b4ee850f5053f250499708405fc`. Its observed systemd interval was
2,204 seconds, with 161.115 seconds of reported CPU time. Receipt registration
performed full filesystem ancestor checks for every retained reference,
including payloads never consumed by aggregation or packaging; metadata
capture also calculated the same hash twice. No aggregate directory or new
handoff ZIP existed when this metadata-only process was ended for continuation.
This was not a native/evaluator failure or a new scientific stopping condition.

Under the human bookkeeping authorization and AGENTS sections 15/16, the
continuation first verifies the receipt and its independent reference, checks
member names lexically, and registers unchanged producer hashes for unconsumed
members without reopening them. Every consumed file still passes the original
regular-file/no-symlink-ancestor check and SHA-256 verification; package checks
remain unchanged. Metadata capture hashes once, and source/index and receipt
loops publish progress counts. No selector, metric, hypothesis, scientific
configuration, provider, solver, evaluator, decision rule, or Outcome changes.

The original freeze remains at
`<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21/00_PREREGISTRATION/FINALIZATION_CODE_FREEZE.json`.
The PRE continuation record has SHA-256
`a9cb68cb0e44d1d806caadbfc6187cdb62b4ad2bd5dfebda4dfc0f618361e80b`.
The compatibility record is the adjacent
`FINALIZATION_IO_CONTINUATION_01_COMPATIBILITY.json`: MAIN `ADD_RUN_00002`
and downstream `P13_LADDER_V0_A04` have exactly equal original/continued
pin and role mappings (47 and 51 pins). Path-check calls are 50 to 4 and
54 to 4 respectively. The bounded audit invokes zero providers, native
solvers or evaluators. The focused finalization/package/document tests pass
39/39, including missing/symlinked consumed-file rejection, malformed member
rejection, conflicting-pin rejection, and changed consumed-payload detection.

## Finalization V-CHK bookkeeping continuation 02

The metadata continuation at `eb70c2a30c45fd3146633dc932eb24a0cbecd5ca`
completed the 5880 final/source record comparisons and receipt catalogues
(5880 new, 21 downstream, 6468 baseline), then raised a KeyError before
V-CHK statistics or aggregation. The three frozen INPUT_DIAGNOSTICS tables
are derived outputs: their hashes belong to OUTPUT_SHA256.csv, not to the
raw/input INPUT_HASH_LEDGER.csv. The adapter now checks those exact producer
output rows, member paths, sizes and SHA-256 values. The four previously
frozen V-CHK definition pins remain unchanged.

OUTPUT_SHA256.csv is newly pinned for P-13 at
`90c20b32cbf8d6e9d607ddaa33777faf94a94bf17ed62f9821561a9c6658f0e2`.
This is a newly locked existing producer ledger, not a claimed previously
published historical hash. No diagnostic value or historical file is changed.
The frozen V-CHK manifest reader uses plain JSON; compressed retained native
manifests are therefore copied losslessly to the finalization metadata child,
requiring the original native manifest SHA-256 and byte size. Existing
identical copies are reused; differing copies are preserved and rejected.

Focused finalization/package/document tests pass 41/41. The actual three
natural A04 inputs (RUN_00006, SEQUENCE_BY2H_A04, SEQUENCE_BY2O_A04) pass
source seals, exact manifest decompression and the unchanged counter reader.
The bounded proof is FINALIZATION_VCHK_ADAPTER_VALIDATION.json alongside
the prior finalization freezes. Provider/native/evaluator calls are zero;
the scientific source freeze, figures, rules and Outcome remain unchanged.
Prior process records and partial diagnostic outputs are retained. This
bookkeeping continuation is covered by the human conflict authorization.

## Final-report projection scope

The document generator's C00/three-sequence subsection originally selected
every CASE row from the complete comparison CSV, including injected matrix
cases. Its document-only selector now retains C00/BY2, BY2H and BY2O there;
family and duration subsections retain their existing selectors. The complete
comparison CSV, all scientific rows, metrics, deltas and hypotheses remain
unchanged. Original CSV tokens and row references are preserved. The bounded
document tests pass 12/12, including a controlled-case exclusion and a BY2H
inclusion check. This affects only the later report generator; it is not
imported by the running finalizer, solver or evaluator.

## Package-only continuation after UTF-8 BOM handling

The finalizer at `f9e3d82f614a803a20cb4934f36687fa3e1ffdc6` completed
all aggregate tables and their full seal, V-CHK and robustness statistics,
and the final source-pin ledger. Its handoff writer then rejected the first
new display curve because the frozen evaluator's UTF-8 BOM was interpreted
as part of the `time` header. This is a display-reader encoding error; the
completed evaluator files and scientific metrics are unchanged.

The package reader now uses UTF-8-SIG, consuming only an optional leading
encoding marker. It retains every data column and selected numeric token,
with the same first-existing-epoch 0.1 s bins and original CSV row mapping.
Six actual v2/v3 streams (ADD_RUN_00002, RUN_00006, SEQUENCE_BY2H_A04)
pass complete selected-token and row-map comparison. Full/kept row counts
are 56642/2740 for each BY2 stream and 58580/2700 for each BY2H stream.
Focused tests pass 45/45. Package progress is reported every 100 curves.

The incomplete handoff is preserved byte-for-byte as
`<HANDOFF_ROOT>/c541_v21_handoff.incomplete_bom_attempt01.zip`; its hash,
size and member count are recorded in
`<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21/30_PACKAGE_CONTINUATION/PRE.json`.
The continuation consumes the explicitly SHA-pinned completed source ledger
and aggregate seal, verifies consumed inputs and formal identity, and invokes
only the exclusive ZIP builder. It does not repeat source-record catalogue
scans, diagnostics, bootstrap aggregation, providers, solvers or evaluators.
Native batch archive failures remain zero; the failed handoff attempt is
recorded separately. The aggregate code commit and later package code commit
are retained as separate identities. This is a human-authorized bookkeeping
continuation, with no new scientific stopping condition.

## Figure export resources

The v2.1 figure export uses eight worker processes and one numerical thread
per process on the observed 25197436928-byte-memory host. This is a plotting
resource setting only; all 28 registered figures, source selectors, scales,
frozen values and visual checks are retained. The completed data ZIP is
validated once by the plotting parent, with its verified identity passed to
workers. Only the MFIG00 plotting child may read the hash-locked Truth trace.

## Two-figure availability repair

The initial export retained 26 successful figures and two failed figure
records. MFIG02 required a finite paired result for every degradation type;
the sealed v2.1 A04-versus-F03 table has 514 finite pairs including C00 for
each displayed metric, with zero finite pairs for D37. The v2.1 drawing now
retains all 60 registered type positions, leaves D37's metric value missing,
and marks availability in axes coordinates. Family labels disclose finite
and registered pair counts. No failed native run receives a fabricated
metric, and no case or pair is replaced.

MFIG20 encountered the frozen IMU table's literal UNAVAILABLE variance at
1.5 seconds for all three axes (zero exact pairs and zero samples). The
drawing preserves those missing variances, marks their availability without
assigning a variance, and retains all six finite lags and the frozen q/c
coefficients. No fit, data table, residual statistic or metric changes.

Focused publication/package tests pass 23/23. The initial root metadata and
two failed figure directories are preserved under
`<CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21/FIGURE_PREPARATION/REPAIR01/`.
Its PRE ledger pins all 104 files belonging to the 26 successful figures.
Only MFIG02 and MFIG20 are re-exported, using two plotting workers with one
numerical thread each; all other figure files must remain byte-identical.
This is the authorized figure-reader/coverage correction, with zero
provider, native solver, evaluator or aggregate reruns.

The actual raster review then identified crowded MFIG20 static-window tick
labels. A final MFIG20-only export splits "first 1000" across two lines;
all plotted coordinates, values, units and window identities remain unchanged.
The preceding MFIG20 exports and root metadata are retained under
`FIGURE_PREPARATION/REPAIR02/`, outside the final figure root. The other
27 figures are pinned before and verified after this layout-only repair.

The complete raster pass also identified the MFIG22 shared legend touching
panel label (b). Its legend is moved into the empty upper-left area of
panel (a), without changing data or axes. Only MFIG22 is re-exported;
`FIGURE_PREPARATION/REPAIR03/` retains the preceding exports/root metadata
and the before/after byte ledger for the other 27 figures.

## Final documentation review scope

The first document review applied the local-path check to the entire
preserved AGENTS text and detected its existing historical local paths.
No document was written. The corrected review checks newly inserted lines
for local paths and separately requires exact preservation of all original
section bodies and every section outside 7/11/18. Newly inserted local-path
lines are zero. Existing frozen text is retained under its pre-correction
markers; the numerical sources and document generator are unchanged.
