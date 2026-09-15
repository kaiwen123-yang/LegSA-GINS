# GINav 2021 exact LC02 runtime route

This package implements only the source-explicit adapters and orchestration for
`LC02C_GINAV2021_OFFICIAL_SPP_INS_LC`. It does not vendor, port, or modify the
pinned GINav filter core. The scientific identity remains an exact official
software reproduction and a standard literature baseline, not a novel filter.

The runner is deliberately explicit:

```text
python3 scripts/paper_rebuild/run_lc02_ginav2021.py verify-source --ginav-root <GINAV_ROOT>
python3 scripts/paper_rebuild/run_lc02_ginav2021.py execute \
  --ginav-root <GINAV_ROOT> --matlab-executable <MATLAB_EXECUTABLE> \
  --libarchive-path <PINNED_RESOLVED_LIBARCHIVE_FILE> \
  --scratch-root <FRESH_EXT4_SCRATCH> --stage-root <EXACT_STAGE_ROOT> \
  --paper-root <PAPER_ROOT> --legacy-freeze-root <LEGACY_FREEZE_ROOT>
```

`verify-source` is read-only. `execute` is the only command that can launch the
authorized gate sequence. It first proves the detached commit, whole-tree OID,
named hashes, and clean tracked tree. It then discovers a licensed,
display-capable MATLAB route and tries candidates in order. Every official run
uses a fresh tracked-source mirror with official `data/` and historical
`result/` excluded, asserts MATLAB resolves named core functions inside that
mirror, requires an explicit read-path ledger, and proves the official checkout
and mirror clean before and after the process.

All machine roots are caller- or ignored-local-config supplied. The runtime
contains no tracked host path default. Scratch is rejected if it is inside the
code, clean, raw, paper, or legacy-freeze protected roots, or if any path
component is a symlink. Publication sources are subject to the same RAW_ROOT
protection. MATLAB R2016a compatibility is explicit: generated harnesses are
function files with subfunctions, Windows execution uses `-wait -nosplash -r`,
Linux uses `-nosplash -r`, and environment evidence is deterministic TSV. The
route does not rely on `-batch`, `jsonencode`, `isstring`, or script-local
functions.

G1 requires an explicit resolved regular libarchive shared-object file. The
backend accepts only the pinned file SHA-256 and public libarchive 3.6.0 ABI,
enables only the NONE filter and 7zip format, and never searches `PATH`, invokes
an archive subprocess, installs software, or uses a general extract API. A
header-only `archive_read_next_header` pass rejects unsafe, non-NFC,
case/prefix-colliding, linked, encrypted, sparse, special, unset/negative, or
over-limit regular-file members. A regular file must have set, nonnegative size
metadata within the member cap and carries the stable
`REQUIRED_SET_NONNEGATIVE_WITHIN_CAP_FOR_REGULAR_FILE` contract. Directory size
metadata is not applicable: unset metadata is valid and normalized to zero with
`NOT_APPLICABLE_FOR_DIRECTORY`; when directory size metadata is set, its value
must be zero. A directory filetype may carry exactly one trailing POSIX
slash; its exact decoded archive pathname is retained, while the canonical name
with that slash removed drives collision checks. Both forms remain frozen in
header identity. The size contract is also frozen in the header digest,
inventory binding, and extraction header comparison. Regular files and all other
trailing-slash or empty-component forms remain rejected. The inventory positively
proves that no serialized `.pos`,
`.sol`, or `.out` is bundled. Inventory calls no payload API; this does not
claim that a solid archive implementation performs no internal decoding.

The G1 inventory SHA-256 must first equal the pinned official source-lock sample
SHA-256. One relocation-safe frozen binding then covers the archive hash/size,
ordered headers, and exact selected roles. Each of the two fresh archive readers
must reproduce that hash/size identity before any header or payload API is used,
and both pristine extractions must report the same frozen binding.
Only the selected observation, broadcast navigation, and IMU files are streamed
through `archive_read_data_block` into dirfd/no-follow, exclusive leaves with
offset, size, fsync, and readback-hash conservation. Every unselected member is
handled with `archive_read_data_skip`. `cpt_pva_ref.mat` and bundled UBX have
literal zero payload-read calls and are never materialized. The tracked
historical GINav result is never copied or read. A missing or incompatible
backend is recorded as a technical pre-sample backend failure with zero sample
runs under the existing official-sample blocker terminal; it is not described
as an observed official-sample regression.
Only `data_dir` changes in the sample configuration. The new runs are compared
by row count, source status sequence/transitions, finite state/covariance fields,
and a digest of the serialized official 33-column schema.

G2 reconstructs only the locked GNSS1 RAWX/SFRBX stream and invokes the pinned
RTKLIB `convbin` without interval, constellation, or signal filtering. The
pre-navigation inventory reproduces the pinned `decode_obsh` → `set_index` →
`decode_data` → `adjobs` path, including BDS2 `[1,3,2]` and BDS3 `[1,3,4]`
output-slot remaps. It selects every GINav-supported constellation with the
decoder-selected tracking family present as same-epoch P(1)/L(1), a prior
L(1) for TDCP, an observation/navigation-matched satellite, and broadcast
records under GINav's source `MAXDTOE` limits. Coverage uses the same broadcast Toe
quantity as official `searcheph`/`searchgeph`, including the source's BDS time
conversion, Galileo code selection, and GLONASS rounded-UTC-Toe rule; Toc is
not substituted for Toe. Every usable contiguous output slot is inventoried,
but `nfreq=1` is frozen from the selected official SPP-LC configuration and its
literal consumers `prange` P(1) and TDCP current/previous L(1); it is not chosen
from the audited maximum, which is diagnostic only, or from output accuracy.
Every checksum-valid UBX message class, discarded byte, and checksum failure
receives an explicit inclusion/exclusion role and reason.
External PVT is not a GINav measurement interface.

The IMU projection materializes only timestamp, gyro, and accelerometer from
`REAL_BY2_COMPLETE_RECORD_PREFIX_63277`. It reuses the clean project's frozen
current-sample interval convention, including its invalid-interval rule, and
writes official format-2 increments. Adjacent intervals with `dt<=0` or
`dt>0.1 s` are dropped and counted with interval-outcome conservation. FLU
vectors map to RFU as
`[R,F,U]=[-L,F,U]`. The runtime CSV remains untracked and unpublished.

G3 inventories the literal RINEX fractional seconds without navigation. A
normalization is permitted only by causal same-receiver stream order. RAWX row
`i` owns NAV-PVT messages strictly after its message sequence and strictly
before the next RAWX sequence; the last window ends at EOF, and pre-first-RAWX
NAV-PVT is ignored. Candidates require `validDate`, `validTime`, and
`fullyResolved`. The only consumed semantic signature is `iTOW` plus those
three validity bits. Message sequence, window membership, and candidate count
are audit/transport fields. One signature is canonicalized deterministically to
its minimum message sequence even if repeated; zero signatures are MISSING and
multiple signatures are CONFLICT, both fail closed. Every selected row must
also prove one constant signed modulo-week `NAV-PVT iTOW - RAWX rcvTow`
relation. The algorithm never enumerates or scores candidate offsets and does
not use RMSE. The five phases RAWX, literal RINEX, association ledger,
normalized RINEX, and selected RINEX must conserve retained-row count and order
with zero deletion or merge. The official integer-second predicate partitions
those retained rows into eligible and rejected counts; it never filters the
normalized file. The source-explicit probe calls official `ins_align`,
`gnss_solver`, and `tdcp2vel` over every official-match-eligible integer epoch;
the literal activation condition is `dot(vn,vn)>3`. It supplies no alternative
yaw. Each eligible row records `alignment_attempted=true` exactly when official
`ins_align` is invoked, separately from prior/current/pairwise SPP availability.
Zero or pairwise-insufficient internal SPP routes to the dedicated SPP
non-applicability terminal. Pairwise SPP with no literal TDCP threshold pass
routes to the TDCP-condition terminal. Observed SPP and TDCP prerequisites with
no official alignment fail closed as a configuration-contract blocker.

Only a successful G0-G3 transaction can enter G4. G4 launches one MATLAB
process, one recursive official run, and no epoch-level parallelism. Native
output is frozen before normalization. A nonzero or missing MATLAB return code
cannot admit. Formal admission requires at least one Q=5 SPP-fed LC row whose
state and covariance are finite. A Q=5-initialized but wholly nonfinite result
is preserved as the poor/divergent applicability PASS with formal admission
false, rather than mislabeled as insufficient SPP. No trace/reference or
performance comparison is part of this transaction.

Runtime works on a fresh Linux-local ext4 scratch root. Publication uses an
outcome-specific exact evidence filename allowlist, rejects source/destination
symlinks and protected-root or destination-identity ambiguity, and prepares a
complete temporary destination whose status, consolidated provenance, and
parity ledger already describe the final state. It then performs an atomic
no-replace rename. Publication failure never invents a terminal: the underlying
allowed scientific terminal is retained, `artifact_publication=FAILED`, the
transaction remains incomplete, formal admission is withheld, and the CLI
returns nonzero. Source
mirrors, sample trees, RINEX, UBX, IMU CSV, MATLAB harnesses, archives, and ZIP
files cannot enter the published evidence set.

Terminal, consolidated, native-summary, and native-freeze evidence carry the
clean provenance fields: dataset role/data mode, raw/provider hashes as
available, code commit, config hash, and literal false/zero values for
synthetic/semi-synthetic data, online trace, receiver-IMU substitution,
final-v23/LegSA output inputs, per-case tuning, output-only correction,
metric-driven deletion, and old-runtime inputs. Official-sample evidence is
explicitly not BY2 evidence; BY2 adapters and C00 are `real_by2_raw`.

The tracked runtime contract is
[`GINAV2021_RUNTIME_CONTRACT.yaml`](../../../../../configs/paper_rebuild/horizontal_literature/ginav2021/GINAV2021_RUNTIME_CONTRACT.yaml).
Phase-1 implementation and tests do not themselves authorize or claim a MATLAB,
sample, BY2, stage-publication, trace-evaluation, representative-case, or
comparison execution.

The separately gated r4c recovery authenticates the exact sealed production
r4b and its source r4, repairs only the known CSV transport split of the
`dot(vn,vn)>3` literal, and never reruns G0--G3. Future probe CSV writes quote
that literal. Recovery accepts the legacy transport only for the exact
28-column header/29-column row/index-17-and-18 fragment shape, records raw and
canonical hashes, and preserves all scientific values. Its recovered G3 rows
must dynamically equal the independently recomputed configured-run inventory
in both count and exact time set; no 302-row rule remains. The fresh r4c root is
non-overwriting, G4-only, uses the same `_g4_scientific_run_and_freeze` helper
as the full transaction, permits at most one G4 invocation, publishes nothing,
and seals only after current-code and immutable r4/r4b reauthentication.

The dedicated `resume-existing-r4-from-g3c` runner entry only prepares a fresh,
non-overwriting, single-level continuation root. It content-hash-locks the
exact frozen r4 full tree plus its G0, G1, GNSS-adapter, and IMU-adapter trees.
Preparation also requires the user-supplied absolute MATLAB executable and
binds its resolved path and SHA-256 to frozen r4 G0; execution must present the
same path and content identity.
It also requires the fixed status, provenance, resume summary, archived driver,
pre-execution-control hashes, exact short layout, prior noninteger-policy
terminal, G0/G3/G4 zero counts, official-sample PASS, formal admission false,
and BY2 C00 unexecuted. Arbitrary self-binding is rejected. The new root records
all four prior gates as reused with zero execution in the continuation, caps
later G3 and G4 at one execution each, and performs no MATLAB launch or RINEX
generation during the preparation call.

The separate `execute-resume-existing-r4-from-g3c` entry consumes only that
authenticated prepared root and uses the same internal G3c-to-G4 scientific
suffix implementation as the full transaction. Before creating `r4b/s`, its
read-only preflight revalidates frozen r4, the reused G2 payload hashes, the
hash-locked raw CSV reconstruction against the frozen UBX, and an explicitly
supplied absolute MATLAB executable whose SHA-256 must equal frozen r4 G0's
`GINAV_MATLAB_ENVIRONMENT.json`; PATH fallback is forbidden. Runtime paths use
the short `r4b/s/{g0,g1,g2n,g2i,g3c,g3p,g4,n,r}` layout and must pass the exact
`/usr/bin/wslpath -w --` 239-character budget ledger. G0/G1/G2 directories are
control-only `REUSED_NOT_EXECUTED` records, and this-continuation execution
counts remain zero for all three gates.

Runtime source mirrors and native `.pos` freezes copy file contents only and
then verify SHA-256 parity; source timestamps, modes, and other metadata are not
preserved. Suffix provenance is constructed fresh from an allowlist of source
r4 identity, official-sample reuse, and G2 evidence. Old terminal, admission,
blocker, transaction, and file-access fields are not inherited; the access
ledger is fresh. Raw-path identity is explicitly local-path configuration plus
the raw hash lock plus reconstructed-UBX equality to frozen r4.
Before stage creation, the suffix also binds the current repository HEAD,
tracked dirty status and binary-diff hash restricted to the approved LC02
implementation paths, every implementation-file SHA-256, the runtime-contract
hash, and one aggregate binding. Unrelated untracked paths are neither listed
nor hashed. The same identity is recomputed at finalization and must match
exactly. Preparation writes that identity into its authentication lock;
execution must reproduce it before creating any stage directory and then uses
that exact prepared object in PRE_EXEC and provenance. Fresh consolidated
provenance is updated before writing with this
continuation's terminal, completion/admission state, actual blocker when
applicable, fresh access audit, G4 execution/result state, and gate counts.

G3c persists `RAWX_NAVPVT_ASSOCIATION_SEMANTIC_DIAGNOSIS.json` and
`RAWX_NAVPVT_ASSOCIATION_CANDIDATES.csv`. The CSV inventories every one of the
1,509 RAWX causal windows and every authoritative candidate, including explicit
missing, duplicate, and conflict classifications. Index 1508 separately records
the superseded exact-key miss and its actual B-window NAV-PVT candidate with
raw row/timestamp, UTC, fix, position, velocity, accuracy, heading, and flag
fields. Only iTOW and `validDate`/`validTime`/`fullyResolved` are scientifically
consumed; all other decoded NAV-PVT fields are audit-only. G4 is eligible only
after recovered G3 eligibility matches the independently recomputed configured
run inventory in both dynamic count and exact GPS time set. Every
terminal writes its audit/provenance/status/parity/summary/manifest set and then
writes the seal last; publication remains false.
The Windows-path ledger covers both complete tracked non-`data`/`result`
source-mirror inventories, every generated harness file, and all principal
MATLAB input/output paths. The final artifact manifest is rooted at the whole
continuation, so it directly includes the prepared lock,
`PRE_EXECUTION_CONTROL.json`, and root WSL-path ledger/budget; it excludes only
itself and the subsequently written final seal.
