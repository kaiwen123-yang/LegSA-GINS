# Independent HV causal-policy execution audit

Status: **PASS_EXECUTION_ACCESS_AND_IDENTITY_WITH_LARGE_PAYLOAD_REHASH_EXCLUDED**.

Registration `531b30860b7c1389e22255ccd1339cb246983049` completed once at `HV_CAUSAL_POLICY_REAL_ATTEMPT01`: rc0, 66.18579878300011 s, no timeout/retry. All six native processes completed in the fixed order—three legacy windows, then three causal windows. No evaluator or phase-information call ran.

## Access and frozen evidence

The parent trace has 462 lines and six child traces have 183 lines: **645 lines fully parsed**, with 618 openat records (611 successful / 7 failed), seven successful exec records, seven exits and 13 signals. No unclassified successful access remains. The parent executes Python; each child executes exactly the registered native binary. Each native opens only its own six scientific input paths plus config/events; IMU opens twice through the existing timestamp prescan and loader, the other five inputs once. No original raw, reference, old NAV or old phase-model payload is used. Scientific writes stay within the new stage.

Parent provider opens are exactly two per registered file, corresponding to PRE and POST. Each receipt matches all **18 files / 120,200,614 bytes**, total 240,401,228 hash bytes. These receipts were verified without rereading the providers.

The three runtime source pins, four metadata pins, new binary hash, registered plan bytes and all **49 execution-evidence pins** match. COMPLETE binds global seal `eec6608b1924a75b8f0e8e20295ef1e04e878e6abe5327108173c4bb9567f1f1`. The output inventory comprises **87 files / 618,145,779 bytes**, with actual names/sizes matching per-run and global seal declarations and no symlinks. Large output payloads were not rehashed by the reviewer.

All three new legacy runs match the old TELEMETRY seal's **14 complete file hash/size declarations**, including old manifest and existing logs. For all three legacy/causal pairs, IMU input segment hashes and NAV/STD/IMUERR time support match. The only added filename is `NED_VELOCITY_SOURCE_EVENTS.csv`; state-dependent output values are allowed to change under the policy.

## Reported policy result and support

|Sequence|Selection invocations|Consumed / accepted|No eligible source|Maximum selected age (s)|END priors|
|---|---:|---:|---:|---:|---:|
|BY2|1369|1369 / 1369|0|0.01494264566|273|
|BY2H|1349|1348 / 1348|1|0.01093769105|269|
|BY2O|1884|1881 / 1881|3|0.05884146727|376|
|All|4602|4598 / 4598|4|—|918|

These are the completed registered field-reader reports, not a new diagnostic run. Causal accepted rows have zero reported-source-after-state and zero repeated vector indices, and the CSV-to-actual-EKF-ledger join passes. All rows use observed generation label 2; a label greater than 1 is consistent with initialization/source loading and is not a mid-run reset. All **921 blocks / 1842 endpoints / 918 END priors** remain, including the three terminal uncovered blocks and missing-model strata.

Legacy accepted updates were 4600; causal accepted updates are 4598. This count change is not an accuracy result. The 76,591 future-candidate skip reports count candidate encounters across selection calls, not 76,591 unique measurements or discarded accepted updates. The four real negative rows are “no eligible source”; no real provider/weight rejection occurred, so these windows do not independently exercise rejection-after-consumption behavior.

## Limits

The parent trace deliberately uses no child following; Git and tracer-setup internals are outside that parent trace, while six inner `-f` traces cover native execution. This audit verifies the stated file/process boundary and receipts, not every system call or numerical computation. No provider or old/new large output payload was read by the reviewer, and no science/test was rerun.

The result establishes the registered reported-trigger/state-time and once-per-generation policy on these windows while preserving the default output identity. Actual arrival, the causality of the original SDK-to-NED construction, physical independence/error/cross qualification, trustworthy heading and navigation benefit remain unqualified.
