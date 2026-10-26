# Python-only validation

Validated 2026-10-26 on the attached Linux machine with Python 3.12 and actual Tk
widgets under Xvfb. These are native Python tests, independent of the earlier
Java prototype. No test requires supplied JARs or a PSdZDATA dataset.

| Check | Result |
| --- | --- |
| Native model, FP, dataset, resources and engine tests | **74 passed, 0 failed, 0 skipped** |
| Actual graphical integration | **21 checks passed** |
| Application process-launch audit | **No subprocess launched**, including no JVM |
| CLI without site packages, Java executable or usable vendor path | PASS |
| Manual dataset selection, clearing and persistence after reopening | PASS |
| Original E-Sys installation required by active application | No |
| Java/JAR/DLL/executable included in Python distribution | No |
| Windows execution | UNRUN |
| Full native E-Sys calculation/vehicle feature parity | Not implemented |

## Native test coverage

`tests/test_models.py` checks FA/FAList fields and explicit list selection; SVT
ECU, software and diagnostic-address consistency; TAL lines/actions and stored
statuses; I-Step values/comparisons; malformed and external XML; parser bounds;
duplicates and unsupported structures. The readers report structural scope,
not complete BMW schema validation or vehicle compatibility.

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
instance. A Python audit hook records subprocess launches and asserts none.

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
path. Current milestone logs: `/workspace/analysis/native-fp-tests.log`,
`native-fp-gui-smoke.log` and `native-fp-setup.log`.

## Remaining functionality

This is a standalone native application foundation, not completed E-Sys parity.
There is no successful native FP/SVT Target/TAL calculation, coding, live
communication or FSC/SFA/KDS/LCS/diagnostic validation to report. Those native
implementations remain future work, including all applicable legitimate BMW
security and authorization. The manual PSdZDATA selector is already implemented;
the user can select their data locally without uploading it to start BMGARAGE.
