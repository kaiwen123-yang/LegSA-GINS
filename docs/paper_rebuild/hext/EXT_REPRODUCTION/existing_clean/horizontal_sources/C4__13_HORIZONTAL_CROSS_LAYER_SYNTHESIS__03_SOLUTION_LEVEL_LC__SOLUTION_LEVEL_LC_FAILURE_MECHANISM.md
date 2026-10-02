
# Solution-level LC failure and applicability mechanism

## LC01 Pavlasek

LC01 is a valid dual-receiver solution-level comparator. It uses two receiver position solutions, preserves the correlated measurement covariance, and obtains direct attitude information from the rigid relative vector `P2-P1`. Its standalone C00 output has 58,014/58,014 matched rows and 100% coverage. Formal RMSE is H=0.1691391165921043 m, 3D=0.3790089605253968 m, roll/pitch/yaw=1.2095627529559005/1.5676244070222305/2.9948274600591076°.

## LC02 GINav

GINav is an `EXACT_OFFICIAL_SOFTWARE_REPRODUCTION`, a `STANDARD_LC_LITERATURE_BASELINE`, and `NOT_A_NOVEL_FILTER_METHOD`. The entire configured input was processed, but official alignment occurred 113.002 s late and only 48/116 eligible epochs had valid SPP (68 invalid). The native stream contains 80 rows, only 11 LC updates and 68 INS-only rows.

Formal C00 availability is 77/275 rows = **28.0%**, temporal-span coverage 169.997/274 = **62.043%**, with maximum gap 11 s and 38 segments. Formal RMSE is H=130.8187259110151 m, 3D=219.88371098234956 m, roll/pitch/yaw=14.936207000465183/14.107014661009151/69.75333248293973°. Its correct conclusion is `EXACT_OFFICIAL_ROUTE_WITH_POOR_BY2_ACCURACY_AND_AVAILABILITY`—low availability and poor accuracy are both part of the result.

The 11 LC-update rows have H/3D/yaw RMSE 15.644697806807114/18.55778716774372/24.597615890465157; the 68 INS-only rows have 141.5774109905707/239.92678457284555/81.180584431906. These are mechanism diagnostics only.

## Common-support boundary

The 77-epoch common-support table is `COMMON_SUPPORT_REFERENCE_INDEPENDENT_BRACKET_INTERPOLATION_DIAGNOSTIC_ONLY`. Its raw six-way literal intersection is zero; comparators were bracket-interpolated on GINav target epochs. It does not replace either method’s formal C00 result and cannot decide A04/F04 identity.
