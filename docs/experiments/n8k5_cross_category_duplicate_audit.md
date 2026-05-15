# N8K5 Cross-Category Duplicate Audit

The N8K5 audit extends the N8K3 same-category duplicate detector and the N8K4
semantic filename validator.

The audit checks exact SHA256 duplicates within the same variant even when the
files are in different plot categories. Blocking pairs are:

- velocity residual time series versus velocity comparison;
- feedback observation quality timeline versus feedback delta comparison.

Passing N8K5 requires:

- blocking cross-category duplicates after fix equal zero;
- same-category duplicate regression equal zero;
- applicable placeholder regression equal zero;
- semantic filename mismatch after fix equal zero;
- derived/surrogate data labels preserved.

Non-feedback variants must use documented not-applicable panels for feedback
figures that require feedback rows. Empty accepted/rejected axes are not valid.
