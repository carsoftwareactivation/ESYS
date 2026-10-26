> Historical Java-engine research and prototype results. The active BMGARAGE application now uses Python only. These runtime results do not validate the native Python implementation; see [current validation](../VALIDATION.md).

# E-Sys / PSdZ service trace

> Review scope: the whole supplied archive was inventoried. Analysis below uses public signatures, selected bytecode call chains, configuration/resources, and manual sections; it does not claim exhaustive review of all 30,126 class entries. The current Python-to-Java implementation is limited to offline parsing/model handling and service probes. See [VALIDATION.md](VALIDATION.md) for the implemented operations and measured test results. This is not a full E-Sys port. No supplied Python application, PSdZ data tree, Windows execution, live vehicle operation, or BMW authentication was available for validation.

Evidence scope: supplied `E-Sys2406` installation, inspected 2026-10-26. This report records class declarations, bytecode call edges, and the explicitly identified runtime probes. A traced method is **not** a verified successful vehicle operation. No vehicle connection, programming, coding write, security-token request, or external BMW backend request was performed.

## Evidence and reproducibility

* Vendor installation: `/workspace/vendor/esys2406/E-Sys2406` (unchanged).
* Public declarations: `/workspace/analysis/service-api-signatures.txt`.
* Detailed `javap -p -c` output: `/workspace/analysis/service-bytecode/<fully-qualified-class>.javap.txt`.
* Classpath: reconstructed **in order** from the supplied `E-Sys.bat`, including its environment directory and XML wildcard expansion; all 60 entries exist. `/workspace/analysis/official-classpath.json` records the resolved paths. Do not add the separate `fat` application or bundled Windows runtime JARs to this classpath.
* The initial exploratory probes used the host Java 21.0.12.1. A separately installed Linux Java 11 toolchain is described in `/workspace/analysis/java11-toolchain.md`; current bridge test runtime evidence is in [VALIDATION.md](VALIDATION.md). Although `javap`/`javac` executables are absent, the installed JDK modules work: `java --module jdk.jdeps/com.sun.tools.javap.Main` and `java --module jdk.compiler/com.sun.tools.javac.Main`. The shipped Windows JRE is a separate runtime and was not executed here.

## Real service initialization

Bytecode chain:

`ServiceLocator.locate(Interface.class)` → `Registry.getInstance()` → a `ServiceContainer` created with `ServiceConfiguration("psdz.properties")` → registered implementation factory → the corresponding facade.

The shipped root `psdz.properties` includes `psdz/registry/dsystem.properties`, `psdz/registry/security.properties`, and `psdz/registry/noHttpServer.properties`. Do not replace this service graph with dummy implementations. `ServiceLocator` initially locates `Log` in its static initializer.

These service resolutions ran successfully on the cloud Linux JVM, without opening a vehicle connection:

| Public interface | Runtime implementation observed |
| --- | --- |
| `com.bmw.psdz.api.Configuration` | `com.bmw.psdz.facade.ConfigurationBF` |
| `com.bmw.psdz.api.Logic` | `com.bmw.psdz.facade.LogicBF` |
| `com.bmw.psdz.api.VCM` | `com.bmw.psdz.facade.VCMBF` |
| `com.bmw.psdz.api.ConnectionFactory` | `com.bmw.psdz.facade.connection.ConnectionFactoryBF` |

`ServiceProbe.java` and `service-probe.log` record that first probe. It initially used every shipped JAR; the root-directory negative test was subsequently repeated with only the exact launcher classpath, eliminating the unrelated `fat`/JRE entries, and produced the same blocker.

The application wrapper `AbstractPsdz` initializes PSdZ logging and applies E-Sys coding properties. `PsdzConfiguration.setPsdzRoot()` obtains `Path.PsdzHome`, falling back to `Path.Home`, sets the caller application, then calls `Configuration.setRootDirectory(File)`. Direct API clients must explicitly configure their own data location and logging; they must not accidentally load the supplied personalized `Esys.properties`.

The **data home is the parent of `psdzdata`**, consistent with the observed required path below. `ConfigurationBF` delegates to `com.bmw.psdz.configuration.facade.ConfigurationImpl`. Its `setRootDirectory` establishes the PDX root, prepares KIS dynamic classloaders, initializes FA2FP/base-variant/SWT/security mappings, checks project files, configures the diagnostic server's flash/project roots, starts the KIS manager, and caches version information. This is substantially more than starting a JVM or locating a class.

### Initialization negative test — runtime verified

`RootProbe.java` ran with an isolated work directory and `user.home`, and an empty directory expressly labeled `empty-data-fixture`. It did not construct fake `psdzdata`, fabricate mapping files, or use the supplied saved user configuration.

* Before initialization: `isRootDirectorySet() == false`, root `null`, version `null`.
* `setCallerApplication("BMGARAGE-analysis")` completed.
* `setRootDirectory(empty-data-fixture)` failed with `PSdZRuntimeException`, caused by `PSdZResourceException`: `.../psdzdata/mapping/brref.xml file is missing in psdzdata directory`.
* PSdZ reported rollback. Afterwards: `isRootDirectorySet() == false`, root `null`, version `null`.
* `shutdownPsdz()` completed; the probe process exited 0 because the expected negative result was observed. This exit status does **not** mean data initialization succeeded.
* The fixture remained empty; only `psdz.log` appeared in the isolated work directory.

Evidence: `/workspace/analysis/root-probe-official.log`. The captured log identifies PSdZ and API version `24.06.02` (build marker `2024-09-01T00:00:00Z`), whereas the application installation is E-Sys `24.06.01`.

`Configuration.getVersion()` returning `null` before data initialization is expected observed behavior; do not present it as an unknown successful version or use it to claim backend readiness.

## FA → FP

Real E-Sys call chain, verified statically:

1. `FpLogic.generateFp(TFaList.Id)` converts the selected E-Sys FA using `FalLogic.getModelAsPsdz(id)`.
2. `PsdzLogic.generateFP(FA, String)` calls `Logic.generateFP(FA)` through the located `LogicBF`.
3. `LogicBF` delegates to `LogicInternal`, implemented by `com.bmw.psdz.logic.facade.LogicImpl`.
4. `LogicImpl.generateFP` checks `FA.isStandardValid()` and rejects invalid input with `FA_IS_NOT_VALID`.
5. It resolves the series-specific FA2FP SGBMID using `ConfigurationBCI.getFA2FP(FA.getEntwicklungsbaureihe())`. Initialization populated this mapping from `brref.xml` and associated data; merely constructing an FA object does not populate it.
6. It resolves the actual `.fap` file with `ConfigurationBCI.getFile(sgbmid,"fap")`. Missing mappings and files produce explicit PSdZ exceptions.
7. It parses the file into `FA2FP`, validates that the file's internal SGBMID matches the expected SGBMID, and calls `FP.fillByFA(FA2FP,FA)`.
8. It computes a sorted representation, calculates AUTOSAR CRC32, and stores the vehicle profile checksum using `FP.setVpc(byte[])`.
9. It calls `ValidateFpBCI.verifyFpAgainstFa(FA, FP, fapFile)` and rejects a failed verification (`COULD_NOT_VERIFY_FP_AGAINST_FA`).
10. The E-Sys wrapper optionally generates an FP interpretation for display, then converts the backend FP XML into its JAXB display model.

Consequences: Python XML transformation, copying FA fields into an FP-shaped document, or simply invoking `FP.fillByFA` without the checksum/verification path would not reproduce the original calculation. Full calculation is blocked here by missing PSdZ data; its API and downstream checks have been traced, not executed successfully.

Direct public API: `FP Logic.generateFP(FA)`. FA syntax/serialization and I-Step value validation are independent offline operations and can be exposed when genuinely tested. Their success must not imply FA→FP success.

## I-Step handling

These distinct operations have different prerequisites:

* Syntax/value model: `IStufe.isValid(String)`, `IStufe.valueOf(String)`, `getBaureihenverbund()`, `getSerieneinsatztermin()`, `getNumber()`, comparison and serialization. No vehicle/data presence is implied by syntactic validity.
* Shipment/last/current triple: `new IStufenTriple(shipment,last,current)`; getters are `getIStufeShipment()`, `getIStufeLast()`, `getIStufeCurrent()`.
* Installed/programming targets: `Configuration.requestInstalledIStufen()`, `Configuration.getProgrammierbareIStufenBezeichner(String)` require initialized data.
* FA-dependent candidate levels: `Logic.getPossibleIStufe(FA)`, `Logic.getErkennbareIStufen(FA)` and series-based `Logic.getErkennbareIStufen(String)` rely on PSdZ/KIS data, not on a hard-coded list.
* Live state: `VCM.requestIStufen(Connection)` or `requestIStufenFromBackup(Connection)` returns a `GenericPsdzResult<GenericFailureResponse<IStufenTriple>>`.
* Live writes: `VCM.writeIStufen(Connection,String,String,String)` and `writeIStufenToBackup(...)` return structured status/failures and must not be inferred successful from a nonthrowing call.

Batch manual sections explicitly document the text-file order as **current, last, shipment**. That differs from the `IStufenTriple` constructor's **shipment, last, current** order. A bridge must map by field name rather than forward the three strings blindly.

## VCM and SVT Actual

`VCM` is a real public PSdZ service; current APIs wrap operations in `GenericPsdzResult`, commonly containing `GenericFailureResponse`. Correct evaluation requires the outer `getStatus()`, inner `getFailures()`, and `getResultObject()`; catching exceptions alone loses partial/failed results.

Relevant signatures include:

* `requestFA(Connection)` / `requestFAFromBackup(Connection)`;
* `requestFP(Connection)`;
* `requestIStufen(Connection)` / `requestIStufenFromBackup(Connection)`;
* `requestSVT(Connection,SVTVersion)` / `writeSVT(Connection,StandardSVT)`;
* `generateSVTIst(Connection)`;
* `requestVINFromMaster(Connection)` / `requestVINFromBackup(Connection)`;
* `requestVCMStatusInfo(Connection)`, `requestVCMBStatusInfoFromBackup(Connection)`, versions and VPC queries.

`SvtLogic.readSvtActual()` optionally calls `PsdzVcm.generateSvtIst()`, then requests `SVTVersion.SVT_IST`; `readSvtTarget()` requests `SVTVersion.SVT_SOLL` from VCM. These are **stored vehicle VCM variants**.

The separate **Read ECU** path is `SvtLogic.readSvtActualEcu(boolean)`: it checks the live connection, registers an EventManager listener for warnings, calls `PsdzEcu.requestECUSVT()` (or `requestSVTwithSmAc()`), determines default ECU entries, converts to a display model, and removes the listener. These paths are not interchangeable with parsing a saved SVT file.

`FalLogic.readFA()` checks the connection, reads the FA with backup fallback, obtains the vehicle VIN through VCM, and assigns it to the PSdZ FA before display conversion. Therefore reading a saved FA document and reading the vehicle FA must have separately described outcomes.

## SVT Target calculation

`PsdzLogic.generateSvtSoll(...)` calls `Logic.generateSVTSoll(FA,FA,SVT,String,String,String)`; a separate overload takes `Connection` first. Internally `LogicImpl.generateSVTSollIntern` delegates to the KIS `SollverbauungsGeneratorBCI` with FA, actual SVT, I-Step arguments, optional second FA, connection context and software logistics.

For full-flash calculation the public path includes `Logic.generateSollverbauungGesamtflash(Connection,SVT,FA,SollverbauungGenerateConfig)`; configuration contains shipment and target I-Steps and a TAL filter. Different generation strategies exist for individual flash, assembly progress, RSU and matching. One must not arbitrarily substitute one strategy for another because both return an SVT-shaped result.

Status: traced in bytecode. Successful calculation requires appropriate KIS/series data and representative user inputs, neither supplied as a PSdZ data tree in this archive.

## TAL calculation

Real E-Sys wrapper sequence:

`TalLogic.generateTal(TalCalcConfig)` → parse/convert actual and target SVTs, load/filter inputs, register events → `PsdzLogic.generateTAL(actual,target,filter,VIN,useMirror)` → connection check → construct `Sollverbauung` carrying target SVT and an empty `Bestelliste`, construct `SWTAction`, build `TALGenerationConfig`, then call `Logic.generateTAL(Connection,SVT,Sollverbauung,SWTAction,TALFilter,List,List,VIN,TALGenerationConfig)`.

The direct API also declares a `TargetSelector`-based overload:

`TAL generateTAL(TargetSelector,SVT,Sollverbauung,SWTAction,TALFilter,TALGenerationConfigParams,VIN)`.

This declaration may allow a data-based calculation context; it was not runtime verified here and must not be presented as an offline alternative known to work.

The batch path `TalCalculationCommand` delegates to `TalBatchLogic.calculateTal(needsPsdzConnection,configurationFile)`. Shipped manual (`doc/batch_instructions.html`, "TAL Calculation") documents `-talcalculation <config file>` with required `SVT_IST`, `SVT_SOLL`, `GENERATED_TAL`; optional `TAL_FILTER`, `TAL_TYPE`, `IDR_BACKUP_PATH`, `USE_MIRROR_PROTOKOLL`. Standalone requires connection parameters; client/server mode requires an open server PSdZ connection. Running the CLI without those prerequisites and reporting a file-open error would not validate the calculation.

## TAL processing

This is asynchronous programming, not a synchronous success button:

`Programming.executeAsync(...)`, or `executeAsyncNcdProvided(...)`, returns a string execution handle. It must be followed by event/status tracking, `requestExecutionStatus(handle)` and/or `join(handle[,timeout])`; cancellation, cleanup and final TAL state have explicit APIs (`cancel`, `cancelAsync`, `release`).

`PsdzProgramming` constructs `TALExecutionConfig` from settings, including programming-counter checks, mode switches, specific ECUs, programming protection data/token lists and other options; then delegates to the appropriate original `Programming` overload. It also exposes the status/cancel/release wrapper methods.

An execution handle or open port does not establish success. No processing was run here. Requires a valid connected vehicle/bench, matching complete software data, preserved programming protection/security requirements, and suitable Windows interface/runtime testing.

## Bridge guidance supported by the evidence

1. Keep the original service graph and shipped dependency versions. Build against PSdZ API where possible; runtime includes core, resource and exact dependencies.
2. Launch Java with its own isolated work/log directory. Vendor libraries log to stdout by default; redirect logs to stderr or a log file before emitting a JSON-lines bridge protocol. Preserve the complete structured exception cause chain.
3. Resolve services and report their actual initialization state. Treat root-initialization failure as a failed operation, not degraded success.
4. Expose genuine offline model validation/parsing and serialization separately from data-dependent calculations and live vehicle actions.
5. Add only operations verified with runtime fixtures to enabled GUI actions. Document traced but untested operations as limitations without presenting placeholder execution buttons.
6. Use real BMW authorization callbacks and result handling for secure operations. Do not port unsafe saved setting values or fabricate success from an empty object/list.

## Remaining resource requirement

The archive supplies the **application** and Java libraries, but successful root initialization requires the matching **PSdZ data home**, including `psdzdata/mapping/brref.xml`, its referenced FA2FP `.fap` data and the appropriate series/KIS/project/security data. Full programming additionally needs the relevant SWE/firmware artifacts. Supplying only a single `brref.xml` is not sufficient; it is merely the first confirmed missing prerequisite.

Windows runtime/vehicle functionality remains untested in this Linux environment. An existing Python frontend was not present in this installation archive. See [WORKFLOWS.md](WORKFLOWS.md) for manual/GUI structure and [SECURITY_FEATURES.md](SECURITY_FEATURES.md) for coding, FSC, SFA, KDS, LCS and diagnostics.

## Evidence locations and portability

Vendor-relative references (such as `lib/PsdZ/psdz-api.jar`, `doc/online_help.html`, and `E-Sys.bat`) are relative to the supplied E-Sys installation directory, called `ESYS_HOME` by this project. The current cloud copy is `/workspace/vendor/esys2406/E-Sys2406`. Detailed extracted text and bytecode evidence remain outside Git at `/workspace/analysis`; they are analysis artifacts, not part of the Python source distribution. Missing these machine-local artifacts in a new checkout does not change the source manual/class references identified above.
