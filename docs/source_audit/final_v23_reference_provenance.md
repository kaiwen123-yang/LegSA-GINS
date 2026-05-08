# final_v23 Reference Provenance

## Source Role

KF-GINS/final_v23 is external/reference source.

LegSA-GINS proposed modules must remain separated from the external reference. The submodule is used for framework study, source mapping, and baseline/backbone comparison planning only.

Copied or refactored code in any future stage must be documented with:

- source repository;
- source commit;
- source file/function;
- LegSA-owned target file;
- refactor summary;
- claim boundary;
- license/provenance note.

## License Evidence

The submodule contains `reference/final_v23_repo/LICENSE`.

The submodule also contains third-party license files under:

- `reference/final_v23_repo/ThirdParty/abseil-cpp-20220623.1/LICENSE`
- `reference/final_v23_repo/ThirdParty/yaml-cpp-0.7.0/LICENSE`

Because the reference is a git submodule, the external source is not vendored as copied files in the LegSA-GINS superproject. License and notice tracking is recorded in `THIRD_PARTY_NOTICES.md`.

## Provenance Boundary

final_v23 reference source must not be described as LegSA proposed.

final_v23 outputs must not be used as proposed solver input.

Trace remains evaluation-only.

Generated data artifacts remain out of the repository.
