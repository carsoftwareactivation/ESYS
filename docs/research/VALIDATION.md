> Historical Java-engine research and prototype results. The active BMGARAGE application now uses Python only. These runtime results do not validate the native Python implementation; see [current validation](../VALIDATION.md).

# Executed validation and remaining limits

Validated on 2026-10-26 in the attached Debian Linux cloud machine. The supplied
Windows installation was analyzed, but its Windows executables and native
drivers were not run. These results establish the implemented offline scope,
not complete E-Sys workflow equivalence.

## Results

| Check | Result | Practical meaning |
| --- | --- | --- |
| Seven-volume ZIP reconstruction and CRC | PASS | All 930 archive entries readable |
| Post-test vendor integrity | PASS | All 829 files match the uploaded size/CRC; none added or removed |
| Complete artifact/JAR inventory | PASS | 72 JARs / 30,126 class entries inventoried; not every method behavior reviewed |
| Bridge compilation with full JDK `--release 11` | PASS | Bridge class format 55, Java 11 API target |
| Actual Java 11 bridge suite | **22 passed, 0 failed, 0 skipped** | Real original JARs, no mocked Java responses |
| Actual Tk + Java GUI smoke under Xvfb | **9 checks passed** | Real widgets, file/worker/bridge flows and displayed values |
| Isolated PSdZ data initialization | Expected negative | Missing `psdzdata/mapping/brref.xml`; state rolls back to root unset |
| Windows `.pyw` startup/native behavior | UNRUN | Requires Windows with Python/Tk and supplied Java runtime |
| Data-backed FP/SVT Target/TAL calculation | BLOCKED | Matching PSdZ dataset and representative inputs absent |
| Live VCM, ECU reads, programming/coding and diagnostics | UNRUN | No Windows transport or connected vehicle/bench validated |
| BMW backend authentication/FSC/SFA/KDS/LCS operations | UNRUN | No authorized session/artifacts tested; requirements preserved |

## Verified runtime and service results

- Linux runtime/compiler: checksum-verified Eclipse Temurin **11.0.29+7**.
- E-Sys library reports **24.06.01**.
- PSdZ API reports **24.06.02-2024-09-01T00:00:00Z**.
- Original launcher classpath: 59 JAR entries plus `lib/environment`, in order.
- Real services resolve to `ConfigurationBF`, `LogicBF`, `VCMBF` and
  `connection.ConnectionFactoryBF`.
- `Configuration.isRootDirectorySet()` returns `false` and `getVersion()`
  returns `null` before data initialization. The GUI shows that state, rather
  than treating service resolution as vehicle readiness.

The negative data-root probe was compiled and executed with the same actual
Java 11 toolchain, isolated work/user-home directories and an explicitly empty
fixture. `setRootDirectory` threw a PSdZ runtime/resource exception identifying
the absent mapping file; root, root-set flag and version reverted to their
initial unset values. The fixture remained empty. An expected negative probe
passing means its error/rollback behavior was verified, not that initialization
succeeded.

## Bridge integration coverage

`tests/test_integration.py` exercises the original versions, service locator,
I-Step model, FA parser, E-Sys FAList loader/conversion, SVT parser and TAL parser.
Assertions check semantic fields, SALAPA lists, an ECU's software identifiers,
hexadecimal diagnostic address and stored plan statuses. Multiple FAList entries
require explicit selection. Fixtures are synthetic and cannot demonstrate a
valid real vehicle configuration or programming result.

Negative checks cover invalid FA/I-Step input, missing arguments, unsupported
operations, oversized requests, malformed XML, wrong namespaces/document types,
external DTD/schema references, UTF-8 error text and subsequent-request recovery.
Process shutdown/restart is tested. A deliberately paused actual JVM verifies
that the request deadline covers blocked pipe writes, kills the stalled owned
process, and permits a clean restart. That injection uses POSIX `SIGSTOP` and
is explicitly skipped on Windows. Vendor stdout is isolated from the JSON
protocol. Additional review verified rejection of XInclude and entity-expansion
DOCTYPE inputs.

Review found a TAL root-status adapter bug: the inherited `getStatus()` returned
`null`. It was changed to the original TAL-specific `getExecutionStatus()` and
the final tests assert `Executable`. This remains a **stored document status**;
no TAL was executed.

## Graphical coverage

`tests/gui_smoke.py` runs actual Tk widgets and the real Java process under an
owned local Xvfb display. Nine checks passed: backend versions/services and
missing data status; FA semantic fields/options; FAList metadata; selecting a
second FAList entry with distinct data; SVT ECU/software selection; TAL action
plan/status display; I-Step parsing; I-Step comparison; clean shutdown. The
same loading worker used after the file picker is exercised without mocking
responses. The native operating-system file picker itself is not automated.

Linux graphical testing does not validate Windows file associations, native
theme/layout, Windows paths/process flags, JNI transports or vehicle operations.
The original Java GUI is not embedded or replaced with screenshots.

## Reproduce

From `/workspace/ESYS` on the retained cloud environment:

```sh
sh scripts/cloud_setup.sh
export BMGARAGE_ESYS_HOME=/workspace/vendor/esys2406/E-Sys2406
export BMGARAGE_JAVA=/workspace/toolchains/jdk-11.0.29+7/bin/java
python3 scripts/run_gui_smoke.py
```

Without `BMGARAGE_ESYS_HOME`, unittest discovery explicitly skips the integration
class. Such a run must not be reported as backend validation. Without a display,
run only the bridge suite; GUI smoke requires Xvfb or a real desktop. No
background service is retained or assumed to survive environment publication.

Current-instance logs/evidence are retained outside Git:
`/workspace/analysis/final-setup.log`, `gui-smoke.log`,
`root-probe-java11/result.log`, `bridge-java11-results.json`,
`bridge-falist-results.json`, and the toolchain/signature/bytecode reports.
The final unittest/GUI logs take precedence over earlier exploratory results.

## Required next resources

1. The existing BMGARAGE Python application, if this new frontend should continue
   that codebase rather than start a separate implementation.
2. The matching PSdZ data home, beginning with the real `psdzdata/mapping` and
   its referenced FA2FP/series/KIS resources. The first absent file is only the
   first blocker; supplying an invented mapping file cannot complete setup.
3. Appropriate representative legitimate FA/SVT/I-Step inputs for calculation
   tests, then Windows/bench integration and applicable BMW authorization for
   vehicle/backend workflows.

Do not put credentials or private keys in the source, setup scripts or chat.
