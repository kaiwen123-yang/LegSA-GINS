# N4R2 dual_final_v23 artifact recovery

N4R2 performs a directed runtime-only recovery for dual_final_v23 artifacts
before formalizing any yaw evaluator convention.

Search evidence uses role roots only in tracked documentation:

- `EXTERNAL_KFGINS_ROOT`
- `HOME_ROOT`
- `WINDOWS_YKW_ROOT`
- `WINDOWS_86187_ROOT`

Candidate scoring prefers groups with:

- summary horizontal_rmse_m in the dual_final_v23 reference window around 0.353;
- summary yaw_rmse_deg in the dual_final_v23 reference window around 1.814;
- final_v23 or dual path evidence;
- input/nav/std/error_series/summary co-location;
- case_review evidence mentioning `dual_final_v23`.

Groups with horizontal/yaw metrics around the single_antenna-like N4R recovery
case are penalized. Runtime JSON may contain full paths for local diagnosis, but
tracked docs must use role aliases and must not commit actual input, NAV, STD,
summary, or error_series artifacts.

If dual artifacts are missing or incomplete, the required next step is artifact
recovery/schema repair, not a formal evaluator patch.
