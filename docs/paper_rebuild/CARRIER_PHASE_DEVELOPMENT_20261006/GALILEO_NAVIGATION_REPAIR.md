# Galileo navigation repair and qualification

Date: 2026-10-06. Execution: Ubuntu 22.04 WSL. Scope: a separate navigation converter and read-only input qualification; no CILS or reference evaluation was run for this repair.

## Failure and minimal repair

The first real trial requested GPS/Galileo/BeiDou but contained only GPS and BeiDou groups. Original RAWX had eligible Galileo observations, while both original navigation files contained no Galileo ephemerides. The pinned RTKLIB UBX decoder retained an obsolete nine-word Galileo guard: with SFRBX offset 8, an eight-word message has total length 48 and passed the necessary 40 + off bounds check, but was dropped by raw->len < 44 + off.

The actual Galileo SFRBX messages have version 2 and eight words. The u-blox ZED-F9P Integration Manual, UBX-18010802 R16, sections 3.15.1.5.1 and 3.15.1.5.2 / Table 37, documents eight words for E1B and E5b I/NAV. The repair removes only the obsolete second guard in an external overlay. It preserves the eight-word memory bounds check, even/odd and alert handling, CRC24Q check, IOD consistency, satellite identity and health decoding. The original RTKLIB tree and its satellite-state library are unchanged.

The exact one-line delta is [GAL_E1B_8WORD.patch](GAL_E1B_8WORD.patch). The converter is scripts/paper_rebuild/carrier_phase/prepare_navigation.py; its execution hash and all linked source hashes are in [NAVIGATION_RECEIPT.json](NAVIGATION_RECEIPT.json).

Sources inspected:
- [u-blox ZED-F9P Integration Manual](https://content.u-blox.com/sites/default/files/ZED-F9P_IntegrationManual_UBX-18010802.pdf).
- [Pinned RTKLIB UBX decoder](https://github.com/tomojitakasu/RTKLIB/blob/180043ee24b6d2b168f98b64be15f69d50046b1a/src/rcv/ublox.c).

## Causal navigation input

GAL_NAV_QUALIFICATION_V2 retains all original non-Galileo SFRBX messages and RAWX time frames through the last RAWX at 99.998 s, under the explicit cutoff of 100 s. For Galileo it retains only E1B SFRBX to avoid mixing E1 and E5b page banks. Both new NAV files contain GPS, Galileo and BeiDou records, as well as some other decoded systems; availability in a NAV file does not grant integer-model support to those systems.

The converter receives original code/phase frames only to establish their original time. Its generated OBS files are unused by the solver. The runner continues to use original RAWX carrier observations. Both original full-history NAV files are hash-checked for provenance but never loaded into V2. No orbit was downloaded or fabricated.

CRC-passing, consistent IOD word 1-5 chains for E02/E10/E11/E36 are available by approximately 99.198 s, with receiver 1 E36 available by 99.398 s. Native NAV records match these eligible page chains. The subsequent 100-102 s window was chosen using this availability audit and is explicitly a development window. Full-file inventory was used to locate availability; conversion itself contains only the closed prefix.

The local runnable NAVIGATION_MANIFEST.json lists the two new files with hashes. The Git receipt replaces machine-specific roots with aliases and records the same content and hashes; it is not a replacement runnable manifest. The earlier Galileo-only exploratory conversion remains a separate historical attempt and is not loaded by V2.

## Qualification actually performed

| Check | Result | Interpretation |
|---|---:|---|
| Native decoded Galileo NAV records matched to independent CRC/IOD/SV/health/toe/week page chains | 8/8 | Four satellites, two receiver files; all health fields zero |
| Unchanged RTKLIB satellite-state backend plus checked provider at first RAWX inside 100-102 s | 16/16 qualified | E1C and E5bQ for four satellites and two receivers; finite state/clock, eligible age, correct frequency and healthy ephemeris |
| Independent Python page audit: a covered-bit flip | Rejected for both receiver examples | CRC failure in the independent audit |
| Independent Python page audit: truncation to seven words | Rejected for both receiver examples | Word-count failure in the independent audit |
| Native decoder corruption / unhealthy-orbit negative executions | Not performed | No stronger native negative-test coverage is claimed |

Navigation messages here are **E1B SFRBX**, whereas the actual carrier observations are **E1C RAWX (2,0,0)** and **E5bQ RAWX (2,6,0)**. These roles must not be conflated. Positive native-state checks are stored in BROADCAST_QUALIFICATION.json; the receipt preserves those checks and their hashes.

The decoder's native health/CRC checks were not relaxed. Actual native outputs have health zero, and native decoding agrees with the independent page fields. Corruption controls were executed in the independent Python page audit only, not through a separately corrupted convbin stream. No new native negative execution or additional scientific run was added after the real V2 run.

## Outcome and limits

The repair supplies real, causally available Galileo broadcast states to the existing grouped multi-frequency observation model. It does not establish that any real integer vector is correct, calibrate an integer acceptance threshold, or validate heading against independent truth. The real V2 solver and future-epoch checks have their own receipts; their objective certificates concern the stated optimization problem, not integer truth.

Maintained synthetic group-model tests remain in tests/paper_rebuild/test_carrier_multignss.py (30 passing in the recorded WSL check). No new decoder unit test or native negative-test suite is claimed in this checkpoint. The frozen execution snapshot, source pins, page-audit records, positive native checks and two Python negative-control examples trace the present repair while keeping that testing boundary explicit.
