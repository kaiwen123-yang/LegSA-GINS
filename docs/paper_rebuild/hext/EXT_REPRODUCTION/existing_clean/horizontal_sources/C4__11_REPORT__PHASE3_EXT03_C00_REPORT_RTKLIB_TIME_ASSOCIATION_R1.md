# Phase 3 EXT03 C00 RTKLIB time-association recovery R1

Terminal status: `PASS_PHASE3_EXT03_IMPLEMENTATION_VALIDATED_BY2_C00_APPLICABILITY_RESULT`

This recovery supersedes the frozen primary post-native output only for the
RTKLIB-to-native timestamp association. It used the frozen RTKLIB `.pos` and
native heading table, selected no native mode or row by solution value, and
left native plus primary `POST_NATIVE` evidence byte-identical.

Associated RTKLIB rows: `660`; finite native comparisons: `608`;
associated native-invalid rows: `52`. Overlap keys are
`RTKLIB_STOCK_STATE__NATIVE_EXT03_STATE`.

The frozen primary mode has `609/1509` valid rows, `105` ratio-fixed rows,
and `900` invalid rows. The frozen proxy marks `101/105` ratio-fixed rows
inconsistent at the preregistered 30-degree threshold. Frozen trace ALL_VALID
coverage is `541/1370`; its RMSE is `84.3438 deg`. The ratio-fixed trace RMSE
is `40.6308 deg`. These hash-linked facts establish `PASS_PHASE3_EXT03_IMPLEMENTATION_VALIDATED_BY2_C00_APPLICABILITY_RESULT` without
changing or selecting any native output.
