# N5D Raw Doppler Visual Stress Protocol Prompt

Goal:
Merge the completed N5C raw Doppler ablation protocol, tag N5C, then create
the N5D branch for raw Doppler visual validation and receiver-native velocity
stress diagnostics.

Runtime inputs use role aliases only:
- clean_root: clean status-yaw replay input root;
- n5b_root: RTKLIB Doppler provider activation output root;
- n5c_root: raw Doppler ablation protocol output root;
- dual_root: dual_final_v23 nominal evaluation reference root;
- output_dir: N5D runtime report root;
- figure_output_dir: N5D runtime figure root.

Required boundaries:
- PR #21 remains open and unmerged.
- Do not delete remote branches.
- Do not force push.
- Do not create an N5D tag.
- Do not commit raw data, generated NAV/STD/reports, or generated figures.
- NAV-PVT velocity is not raw Doppler.
- .gnss vn/ve/vd is not raw Doppler.
- RTKLIB position solution must not be used as LegSA solver input.
- final_v23 output is not proposed solver input.
- trace remains evaluation-only.
- Receiver velocity stress variants are diagnostic-only.
- R-scale and STD-scale screens are not tuning claims.
- No LSIM/OIM, Go2 prior, source-aware weighting, or FGO implementation in N5D.
- paper performance claim: false.
- no outperform final_v23 claim.
