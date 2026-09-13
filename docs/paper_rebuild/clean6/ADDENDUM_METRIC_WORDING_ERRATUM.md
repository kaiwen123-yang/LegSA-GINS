# Addendum metric wording erratum

The contract committed at `98c1d42eeabe707115f9e67c21ed993572e4d0d1` remains byte-identical. A pre-commit text replacement did not match its YAML line wrapping; the earlier progress message saying both wording corrections had been applied was inaccurate. This companion records the correction without rewriting the pre-registration or changing any numerical operation.

The human instruction and contract require the existing P-09c fault-window horizontal RMSE definition to be inherited unchanged. The frozen implementation includes `start <= t <= end`; the contract's description of that existing RMSE as half-open is a wording error. Post-window RMSE retains `t > end`. The newly registered `outage_end_horizontal_error_m` and `max_horizontal_error_in_window_m` use `start <= t < end`, exactly as registered. No metric is redefined or reevaluated by this erratum.

For H3, the implementation frozen at `f93cb84c2e67432873362fe00324d1c2c28fd899`, before the first provider or solver, reports `INCOMPLETE` when there is missing required sign evidence and no observed positive full-versus-no-Go2 delta. It does not turn incomplete evidence into an unconditional `NOT_OBSERVED`. A positive observed delta yields `OBSERVED_SOME_SEED_HARM`, with missing counts still reported. This is the explicit missing-evidence interpretation of the contract's instruction to disclose missing evidence separately; all per-seed signs remain available.

The subsequent UTF-8 BOM parser repair changes text decoding only. The first completed evaluator output is consumed without invoking the evaluator again. The original stop, original evaluator bytes and a clearly labelled current post-stop snapshot are preserved.
