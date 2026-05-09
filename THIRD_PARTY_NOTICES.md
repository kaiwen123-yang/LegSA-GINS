# Third Party Notices

## KF-GINS graduation-design Reference

LegSA-GINS includes `reference/final_v23_repo` as a git submodule reference to:

- repository: `kaiwen123-yang/KF-GINS-graduation-design`
- branch: `feature/v4-raw-gnss`
- commit: `5a4471efd4fcfcdc31e258a677af354c652ff16f`

The submodule is used as an external baseline/backbone reference and framework study source. It is not proposed LegSA-GINS solver code.

License evidence exists at `reference/final_v23_repo/LICENSE`.

The referenced repository also contains third-party license files at:

- `reference/final_v23_repo/ThirdParty/abseil-cpp-20220623.1/LICENSE`
- `reference/final_v23_repo/ThirdParty/yaml-cpp-0.7.0/LICENSE`

No external source files are copied into the LegSA-GINS superproject by N4H3; the tracked entry is a gitlink.

## N4H4R1 Source-Backed Port-Core Foundation

N4H4R1 adds `cpp/legsa_v23_port_core` as a controlled LegSA-owned
source-backed port foundation from the same KF-GINS / KF-GINS-graduation-design
reference.

- source repository: `kaiwen123-yang/KF-GINS-graduation-design`
- source commit: `5a4471efd4fcfcdc31e258a677af354c652ff16f`
- license status: `LICENSE` found, `README.md` found, `COPYING` evidence_missing
- port role: backbone implementation only, not paper novelty
- final_v23 output solver input: false
- trace solver input: false

Ported/refactored core files carry provenance headers and Chinese comments.
Generated data, generated results, raw inputs, and runtime parity artifacts are
not part of the port and must not be committed.
