# N5B RTKLIB Helper Build

The RTKLIB helper is generated under the runtime report directory as `tmp_rtklib_helper/legsa_rtklib_doppler_helper.c`.
Tracked source does not copy RTKLIB files and does not modify the RTKLIB root.

The helper build report records:

- source layout and required source files;
- discovered functions including `pntpos`, `estvel`, `resdop`, `satposs`, `eph2pos`, `geph2pos`, `seleph`, and `readrnx`;
- runtime-only patches, including Linux header compatibility and Doppler velocity call restoration when required;
- compile command, stdout/stderr tail, executable path, and precise blockers.

If helper compilation fails, N5B must report `N5B2_rtklib_helper_compile_fix` with the exact compile log tail.
If it compiles but emits no Doppler velocity rows, N5B must report `N5B2_rtklib_velocity_output_fix`.
