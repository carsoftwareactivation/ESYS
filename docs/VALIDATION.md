# Python-only validation

Validated 2026-10-26 on the attached Linux machine with Python 3.12 and actual Tk
widgets under Xvfb. These are native Python tests, independent of the earlier
Java prototype. No test requires supplied JARs or a PSdZDATA dataset.

| Check | Result |
| --- | --- |
| Native model, FA editor, FAP, FP, transport, dataset, resources and engine tests | **141 passed, 0 failed, 0 skipped** |
| Actual graphical integration | **30 checks passed** |
| Application process-launch audit | **No subprocess launched**, including no JVM |
| CLI without site packages, Java executable or usable vendor path | PASS |
| Manual dataset selection, clearing and persistence after reopening | PASS |
| Original E-Sys installation required by active application | No |
| Java/JAR/DLL/executable included in Python distribution | No |
| Windows execution | UNRUN |
| Ubuntu/Windows CI on Python 3.10 and 3.12 | Workflow added and linted; remote results not observed |
| Real ENET hardware / BMW F/G vehicle validation | UNRUN |
| Full native E-Sys calculation/vehicle feature parity | Not implemented |

## Native test coverage

`tests/test_models.py` checks FA/FAList fields and explicit list selection; SVT
ECU, software and diagnostic-address consistency; TAL lines/actions and stored
statuses; I-Step values/comparisons; malformed and external XML; parser bounds;
duplicates and unsupported structures. The readers report structural scope,
not complete BMW schema validation or vehicle compatibility.

`tests/test_fa_editor.py` checks actual create/edit/serialize/reopen operations,
option changes, optional VIN clearing, invalid inputs and preservation of the
other FAList entries and metadata. No FA is activated or written to a vehicle.

`tests/test_fap.py` has 21 cleartext mapping-core tests: exact selector order,
time boundaries, duplicate criteria and independent consistency checking.
All mappings remain untrusted, including when a Signature element is present.
The production gate rejects them. These synthetic arithmetic tests do not
establish genuine FAFP authenticity or a completed production FA→FP operation.

`tests/test_diagnostics.py` has 29 native transport tests using bounded local
TCP peers and fixed wire vectors. They check framing, partial reads, routing,
address matching, ACK-versus-response distinctions, response-pending limits,
deadlines, malformed/oversized frames, real security denials and TLS policy
enforcement with no plaintext fallback. They do not establish live ENET or
BMW model compatibility. A successful real TLS handshake is not validated by
the failure/policy tests.

`tests/test_diagnostic_workflow.py` adds 9 engine/CLI integration tests using
actual local TCP peers. Both protocols return only received VIN response data;
denials/malformed replies produce failures, and connections close afterward.
The CLI is also exercised with site packages disabled and an empty executable
search path. Invalid transport/address/TLS options are rejected before network
access. No arbitrary UDS/write operation is exposed.

`tests/test_data.py` checks direct/parent directory selection, case-insensitive
directory discovery, missing/malformed/unrelated mapping data, named-series
inventory, size bounds and external-content rejection, including UTF-16 DTDs.
Its test mapping now follows the supplied BRREF namespace and text-valued
series structure. This fixes the original incorrect `series/@name` assumption.
The synthetic mapping is expressly inventory-only. It never makes a
calculation or vehicle operation available.

`tests/test_fp.py` checks the published CRC-32/AUTOSAR check vector
`123456789 → 1697D06A`, BMW's reserved `FFFFFFFF → FFFFFFFE` behavior,
version-specific serialization widths, numeric sorting, valid maximum counts,
malformed values and genuine checksum match/mismatch processing on synthetic
saved documents. The fixed synthetic profile VPC is `005B2113`; it is not an
expected real-vehicle FP result. No Java oracle/runtime was executed.

`tests/test_resources.py` checks text-valued BRREF mappings, parent inheritance,
per-series override, legacy empty/short IDs, exact FAP filenames, highest current
version discovery, missing/ambiguous mappings and dataset path containment.
Finding a file does not mark it authenticated or enable FA→FP calculation.

`tests/test_engine.py` checks real native dispatch, independence from legacy
Java operations/settings, no-data saved-file processing, selection/recovery and
closed-engine behavior. A separate Python CLI invocation runs with an empty
executable search path, disabled site packages, and unusable legacy Java/vendor
environment variables. It still reports the actual native engine successfully.

## Actual graphical coverage

The smoke test uses real widgets, files, background workers and the native
engine without mocked responses. It checks startup without data; manual parent
and direct-folder selection; clearing; saved settings; native FA, FAList, SVT
and TAL displays; selecting a distinct second order; reopening a standalone FA
after a list selection; limited-version and uninspected-TAL disclosures; saved
FP categories, unchecked VPC, actual matching/mismatching VPC, explicit FAList
input selection and clearing stale checksum state; I-Step
parsing/comparison; clean shutdown and remembered data after a fresh application
instance. The FA New/Edit dialogs, option prefill/parsing, explicit save/reopen,
selected-entry snapshot and invalid-edit recovery use real engine operations.
The ENET panel starts with blank endpoint/target and no connection, rejects
invalid inputs without sending, displays actual HSFZ/DoIP local-peer VIN
responses, and clears stale results when an ECU denies a request. Python audit
hooks check subprocess launches and startup socket activity. No application
subprocess is launched.

The testing harness starts an Xvfb display server and a Python test process.
Those are test infrastructure outside the application. The application itself
starts no external engine. The native OS folder picker and Windows file
associations/theme/paths have not been automated or verified on Windows.

## Package and repeatability

`scripts/package_standalone.py` collects the application, native tests, scripts
and documentation, rejects Java/native runtime artifacts, and writes a SHA256
manifest and dependency declaration. Python/Tk is required to run the `.pyw`;
the ZIP is not a compiled Windows EXE or a bundled Python interpreter.

```sh
python3 -m unittest discover -s tests -v
python3 -m bmgarage info
python3 scripts/run_gui_smoke.py
python3 scripts/package_standalone.py
```

On the retained Debian cloud snapshot, `sh scripts/cloud_setup.sh` performs the
same validation and packaging, using workspace-local Xvfb if necessary. It
contains no JDK download, vendor classpath, bridge compilation or fixed data
path. Current milestone log: `/workspace/analysis/native-0.4.0-setup.log`.

## Remaining functionality

This is a standalone native application foundation, not completed E-Sys parity.
There is no successful production native FP/SVT Target/TAL calculation, coding,
live vehicle operation or FSC/SFA/KDS/LCS validation to report. VIN reads have
local protocol-peer coverage only. The other native implementations remain
unfinished, including all applicable legitimate BMW security and authorization.
The operation-by-operation status is in [OPERATIONS.md](OPERATIONS.md).
The manual PSdZDATA selector is already implemented;
the user can select their data locally without uploading it to start BMGARAGE.
