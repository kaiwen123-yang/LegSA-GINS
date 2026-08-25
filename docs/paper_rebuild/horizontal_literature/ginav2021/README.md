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
over-limit members. A directory filetype may carry exactly one trailing POSIX
slash; its exact decoded archive pathname is retained, while the canonical name
with that slash removed drives collision checks. Both forms remain frozen in
header identity. Regular files and all other trailing-slash or empty-component
forms remain rejected. The inventory positively proves that no serialized `.pos`,
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
normalization is permitted only when every RAWX epoch has exactly one
same-receiver NAV-PVT row with valid date, valid time, and fully resolved GNSS
time, and every derived offset is the same exact integer nanosecond value. The
algorithm never enumerates candidate offsets and does not assume the historical
2 ms observation. The source-explicit probe calls official `ins_align`,
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
