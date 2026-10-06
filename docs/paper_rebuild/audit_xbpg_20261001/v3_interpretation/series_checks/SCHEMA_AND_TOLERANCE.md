# Retained V3 series validation: fixed schema and tolerance

This is the new, explicitly authorized **validation calculation** phase. It fully
reads the 2,308 retained error-series gzip files and the one retained matched
trajectory, once each, and compares independently calculated values with existing
results. It does not replace any source table, rerun an evaluator, establish
algorithm correctness, or revise the previous collection receipt's historical
`new_performance_statistics=0`. These new calculations are identified separately.

Preparation reads only the existing run index, its explicitly identified registry
and provider-bundle JSON metadata, and static source definitions. The prepared
script/manifest identities are recorded in `PREPARATION_RECEIPT.json`. The
supervisor must publish this description and script before the first payload read.

## Inputs and one-read boundary

- Locator: `../../v3_results/V3_RUN_RESULT_INDEX.csv`; machine roots resolve only
  through ignored `configs/paper_rebuild/V3_RESULTS_ROOTS.local.json`.
- `SCAN_MANIFEST.json` selects exactly the retained indexed files. It does not
  discover files across a disk or treat released files as readable payloads.
- One native identity retains separate v3/v2 evaluation rows. C00/BY2 is CORE;
  it is consumed only in `BY2_NATURAL`, never again in a CORE group.
- Only gzip error series and the exact matched export are scientific payload
  inputs. There are no NAV, STD, raw, reference-trace or provider-payload reads.
  JSON bundle metadata is used only for fixed interval provenance.
- The standalone Python script uses only the standard library, no project
  imports, subprocesses, Context, solver, generator, original evaluator or
  aggregate/report controller.
- The gzip reader reaches EOF and checks its CRC. SHA-256 of decompressed original
  bytes is accumulated during that same read and compared to the existing
  uncompressed-source hash; it is not a second read. Source size/mtime must remain
  unchanged during the scan. Compressed payloads are neither copied nor unpacked.
- At most four processes operate on distinct files; numerical-library thread
  variables are one. Only one file's numeric arrays per worker remain in memory.
  Exact percentiles require bounded per-file sorting; no corpus-wide array is made.
- Each file has an exclusive STARTED checkpoint and a durable COMPLETE checkpoint
  under ignored `.checkpoints/`. Complete checkpoints are reused without opening
  payloads only after contract/file identity checks. An incomplete checkpoint
  prohibits automatic rereading and becomes an explicit unavailable item; other
  files continue. No task resumes itself or proceeds to another group.
- The unique `RUN_00004/v3` matched export is scanned in the same worker while its
  error-series arrays are still in memory, enabling an all-row time/yaw comparison
  without rereading the error series or exporting an epoch-level cache.

## Frozen columns and export precision

Error-series schema S0021 has 13 columns, in this exact order; the original writer
uses UTF-8 with BOM:

```text
time,err_n_m,err_e_m,err_u_m,horizontal_err_m,position_3d_err_m,
roll_err_deg,pitch_err_deg,yaw_err_deg,horizontal_3sigma_m,
roll_3sigma_deg,pitch_3sigma_deg,yaw_3sigma_deg
```

Matched schema S0024 has nine columns:

```text
time,truth_latitude_deg,truth_longitude_deg,truth_height_m,truth_yaw_deg,
estimate_latitude_deg,estimate_longitude_deg,estimate_height_m,estimate_yaw_deg
```

The frozen evaluator's `err_df.to_csv(..., encoding="utf-8-sig")` and the V3
observer's `DataFrame(columns).to_csv(stream, index=False)` have **no float_format**.
No fixed decimal rounding is inferred. The checker parses binary64 values from
these original decimal tokens; recorded JSON floating lexemes are retained as
strings. CSV source comparison cells remain their original strings. Check values
use Python's round-trip float representation; displayed tables may round them
only for reading, never for deciding equality.

Fixed tolerances, chosen before reading series bodies:

- Numeric metric: `abs(check-recorded) <= 1e-10 + 1e-10*abs(recorded)`.
- Timestamps/durations: absolute difference at most `1e-9` seconds.
- Counts and integer indicators: exact equality.
- Null matches null; null never becomes zero. A retained field that cannot support
  a target is `NOT_RECOMPUTABLE_FROM_RETAINED_FIELDS`.

No tolerance is enlarged after inspecting discrepancies. Use of `math.fsum`
instead of NumPy reduction, and normal CSV/binary64 round trips, are reported
implementation precision differences; they do not authorize changing a failure
to a match. The source units remain metres, degrees and seconds. Original fields
named `*_iae_m`, `*_ise_m`, `*_iae_deg`, `*_ise_deg` retain their names, but their
physical dimensions are respectively m·s, m²·s, deg·s and deg²·s.

## Existing numerical definitions independently checked

Static definition chain, never imported/executed:

1. `protocol_v3/runtime.py` calls frozen `window_metrics` after reading retained
   errors and verifies finite, strictly increasing matched time support.
2. `clean5_parity_p04/evaluation.py:metrics` uses the canonical signed/norm helpers.
3. `canonical541/offline_eval_aggregate.py:_axis_stats`, `_norm_stats`, `_integral`
   define 128 full-window fields: six signed axes × 17, two norms × 13.
4. The frozen evaluator is
   `<CLEAN_ROOT>/16_FINAL_V23_ARCHIVE_RECOVERY/ARCHIVE_45953164c53e/selected/MAIN/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py`,
   SHA-256 `aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da`.
5. `scripts/paper_rebuild/v3_evaluator_observer/sitecustomize.py` identifies the
   matched export as existing evaluator arrays with no added interpolation.

The six signed axes are north/east/up/roll/pitch/yaw. Their statistics are signed
mean, bias (same mean), signed median, population standard deviation (`ddof=0`),
RMSE, MAE, median absolute error, absolute p50/p75/p90/p95/p99, maximum absolute
error, last signed error, last absolute error, IAE and ISE. Norms are horizontal
and 3D position: RMSE, mean, median, MAE, p50/p75/p90/p95/p99, maximum, last
absolute error, IAE and ISE. Percentiles use linear interpolation at `(n-1)*q`.
All arithmetic uses the retained matched samples; the original final value is the
last original-order element. IAE/ISE use trapezoids between successive sorted
times (one point gives zero). Strict time ordering is independently required, so
the valid input is already in that sorted order. Existing full-window integrals
bridge timestamp gaps exactly as the source helper does; structural gaps are
reported separately and are not concealed or filled.

Original evaluator summary fields are also checked: position/attitude RMSE,
absolute P95/max, horizontal MAE, threshold pass fractions and retained 3σ
fractions. Thresholds are H≤2 m, |Up|≤3 m, |roll|≤1°, |pitch|≤1°, |yaw|≤2°.
Convergence is the start of the first consecutive valid run with H≤2 m and
|yaw|≤2° lasting at least three seconds, relative to the first retained timestamp.
The original rule does not reset at a timestamp gap; this is preserved and the
gap remains separately visible. A fraction records its actual numerator and
matched denominator.

Retained error series directly support matched count, first/last time and
duration. Original output count, reference count, unmatched count, coverage,
native finite-output claims and process runtime are **not** reconstructed from a
matched-only export. In particular, `coverage_ratio=1` is not proof that this task
has read the original NAV or reference support. The original absolute time origin
and truth-yaw construction are likewise not inferable from error columns.

All 13 fields receive nonnumeric/NaN/+Inf/−Inf/finite/min/max/negative counts.
Any nonfinite cell or invalid chronology prevents numerical comparison; no
finite-only deletion, interpolation or metric-driven repair is permitted.
Duplicate timestamps, backward/nonincreasing steps, positive interval min/median/
max, and counts of intervals >0.01 s, >0.1 s and >1 s are reported. Those three
fixed descriptive thresholds do not classify an outage or authorize dropping an
epoch.

An unreadable/corrupt file produces its own terminal row and reason; it does not
stop unrelated files or require rereading its paired companion. `read_depth` is
`FULL_PAYLOAD_READ` only after actual EOF/CRC completion, with the separate
`eof_receipt`. A partial body read remains `HEADER_READ` (or `INDEXED_ONLY` before
a successful header) and explicitly states `payload_read_completion`, bytes read
and complete rows parsed before failure. An interrupted process has unknown read
extent, not a fabricated zero or full-read count. Numeric results are separately
labelled `NUMERICALLY_CHECKED_WITHIN_SCOPE`; an arithmetic calculation never
changes the depth label. Invalid/unavailable paired time/yaw fields remain
not-comparable; NaN comparisons never count as successful paired epochs.

## Fixed windows and distinct meanings

Every file has its exact registry full window. Natural BY2 and BY2H are not split
at arbitrary or output-selected points.

BY2O uses the existing display contract: full `[3186,3563]`, closed primary
`[3369.94,3411.95]`, closed secondary `[3495.94,3508.94]`, union of the two closed
windows, and full-window complement of that union. These are the fixed rounded
display boundaries actually used in the V3 segment table, not substituted raw
GNSS event timestamps. All 110 existing Protocol V3 table rows (11 configurations
× 2 evaluator versions × 5 windows) are compared field by field. Other protocol
rows in that source table are not folded into this scan.

For CORE/A1/A2, two provenance-distinct families are retained where available:

- `evaluator_event_*`: exact old canonical `_event_window` parameter interpretation.
  If only `duration_s` exists it takes `anchor_time_s` as the start, then adds
  duration. It uses pre `<start`, during `[start,end]`, post `>end`. It does not
  recognize `degradation_duration_s`. These are old helper semantics, **not**
  assumed actual injection intervals and not original V3 full-window row fields.
- `registered_fault_*` / `registered_recovery_*`: the exact component intervals
  from the hash-pinned `PROVIDER_BUNDLE.json`. These use half-open `[start,end)`;
  pre `<start`, post `>=end`. Duplicate component windows share one mask but
  retain all JSON pointers. Explicit A1/A2 metadata supplies its registered
  outage interval if a component interval is absent. No interval is placed from
  outputs, and no unsupported whole-sequence fault gets an invented start/end.

All masks intersect the registered full window. Rows for an empty fixed window
remain with count zero and unavailable metric cells. Window summaries are new
validation/descriptive calculations; where no original target exists they are
not presented as recovered original numbers. They include support endpoints,
selected support-block count and maximum interval, preserving gaps and mask
discontinuities. Window summaries deliberately omit integrals: disconnected
union/complement samples must not acquire an undocumented connecting trapezoid.

The matched check preserves all nine original fields, verifies finite ordered
time and original count, and independently uses
`wrap(estimate_yaw-truth_yaw)=(delta+180)%360-180`. It compares all paired times
and wrapped yaw values against the simultaneously held error-series arrays, then
the 17 existing yaw statistics. It performs no geographic projection, position
reevaluation, new reference interpolation, or roll/pitch reconstruction.

## Outputs and reading order

`SCAN_MANIFEST.json` lists exact inputs, group, original identities, window
definitions and pointers. Each completed group has:

| File | Grain and purpose |
| --- | --- |
| `FILE_CHECKS.csv` | One original payload; openable source paths, read depth, full byte hash, row/column and time/gap counts, comparison status. |
| `METRIC_CHECKS.csv` | One original metric target; original numeric lexeme, independent check, denominator/numerator, difference, fixed tolerance and reason. |
| `WINDOW_SUMMARY.csv` | One run/evaluator/fixed window; support count, endpoints, mask/source and new validation statistics, with original identity/data mode. |
| `FIELD_QUALITY.csv` | One original column; all finite/nonfinite/parse counts and extrema. |
| `RECEIPT.json` | Group counts, all status totals, output hashes, explicit validation/calculation flags and zero forbidden execution counters. |

In metric rows, `@evaluation_result`, `@summary`, `@registry`, `@matched_manifest`
resolve to the corresponding source column in the same `file_id` row of
`FILE_CHECKS.csv`; the pointer is a real JSON pointer. `@companion_error_series`
resolves through the matched row's `companion_error_file_id`. BY2O source-table
checks retain their actual alias path, 1-based source row key and column.
Source values and check values are adjacent; source tables remain untouched.
Exact per-file checkpoints are ignored local state, not thousands of Git files.

Groups stop in order: BY2 natural (22 error files + matched), BY2H natural (22),
BY2O natural (22), CORE by case family, then A1 10/20/30 s and A2 10/20 s (198
error files each). The supervisor reviews, commits and pushes each completed
group before explicitly releasing the next one. A successful arithmetic match
does not prove estimator correctness or resolve previous audit findings.

Preparation command (metadata only):

```bash
python3 scripts/paper_rebuild/check_v3_retained_series.py --prepare
```

First group, only after the supervisor supplies the pushed preparation commit:

```bash
python3 scripts/paper_rebuild/check_v3_retained_series.py \
  --group BY2_NATURAL --workers 4 \
  --preparation-commit <PUSHED_PREPARATION_COMMIT> \
  --group-release SUPERVISOR_RELEASED:BY2_NATURAL
```
