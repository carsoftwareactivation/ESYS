> Historical Java-engine research and prototype results. The active BMGARAGE application now uses Python only. These runtime results do not validate the native Python implementation; see [current validation](../VALIDATION.md).

# E-Sys 24.06 documentation, GUI and runtime assessment

> Review scope: the whole supplied archive was inventoried. Analysis below uses public signatures, selected bytecode call chains, configuration/resources, and manual sections; it does not claim exhaustive review of all 30,126 class entries. The current Python-to-Java implementation is limited to offline parsing/model handling and service probes. See [VALIDATION.md](VALIDATION.md) for the implemented operations and measured test results. This is not a full E-Sys port. No supplied Python application, PSdZ data tree, Windows execution, live vehicle operation, or BMW authentication was available for validation.

Analysis scope: the supplied seven-part `E-Sys2406` ZIP, reconstructed and CRC-checked by the parent agent, extracted at `/workspace/vendor/esys2406/E-Sys2406`. This is analysis of supplied material, not a claim that the installation is authentic or complete for vehicle use. No vendor file was edited. No vehicle was contacted. No backend authorization was bypassed.

## Supplied material and missing project inputs

- The root is an installed Windows E-Sys distribution, not a Python project. It has `E-Sys.bat`, `E-Sys.exe`, configuration, documentation, `jre`, Java libraries, native DLLs and uninstall files.
- No `.py` or `.pyw` file exists anywhere in the archive. There is no existing BMGARAGE Python application to continue or audit in these supplied files.
- There is no `psdzdata` tree. The application libraries are distinct from the main-series/KIS/ODX/CAF/SWE dataset required for profile calculation, target calculation, coding, diagnostic interpretation and flashing.
- No supplied FA, FP, SVT, TAL or NCD project fixture was identified. The loose XML files are application/environment configuration; the `.xsd` files are schemas, not vehicle fixtures.
- The installation contains personalized connection/configuration state and prior log files. Do not publish their contents or copy them into test fixtures. The report intentionally omits vehicle identifiers.

## Documentation evidence

The PDF is `doc/esys_manual.pdf`, title page **User manual, document version 14.0, 2024-07-02, tool version 24.06**. `doc/online_help.html` declares the same version. Extracted text is at:

- `/workspace/analysis/esys-manual.txt` (PDF text with layout)
- `/workspace/analysis/online_help.txt` (HTML text)
- `/workspace/analysis/batch_instructions.txt` (HTML text)
- `/workspace/analysis/RELEASENOTES_24.06.01_eng.txt` (HTML text)

These extracts are analysis outputs outside the checkout; do not distribute the vendor manuals inside the source repository by default.

## Launcher and runtime

`E-Sys.bat` sets its own installation's `jre` as Java home, adds the Java bin and EDIABAS locations to the process path, changes working directory to `lib/environment`, builds an explicit ordered classpath, and launches:

- GUI: `com.bmw.esys.gui.control.Framework`
- Batch, when arguments are supplied: `com.bmw.esys.domain.batch.EsysBatch`

The classpath includes `esysCore.jar`, `esysGen.jar`, `esysGui.jar`, PSdZ API/core/resource, third-party jars, UUID, driver, ProDiaS, PSdZ adaption, ESTCM/security units, FSC tools, ODX checker, XML jars and the environment directory. It deliberately includes multiple similarly named third-party jars; preserve launcher ordering when reproducing its behavior rather than inventing a generic recursive classpath.

Relevant VM defaults: max heap 1024 MiB; thread stack 1024 KiB; G1 GC; JKS truststore from the bundled runtime; AIA issuer retrieval enabled; HTTP throughput setting. An optional GC pause target is applied in batch mode. The launcher uses `javaw` for GUI and `java` for batch. Its working directory matters for environment/config resolution.

`jre/release` establishes the actual shipped runtime: **Azul Zulu 11.0.15, Windows x86_64**, with JavaFX modules in addition to Java desktop/JDK modules. This takes precedence as runtime evidence over `lib/README_SYSTEM.TXT`, which is an old PSdZ note mentioning Java 8 and Windows XP/7. That historical note is not evidence that this E-Sys version should use Java 8.

The Linux host can inspect Java classes and execute platform-independent operations through a separately installed compatible Java. The shipped Windows executables and DLLs cannot be executed natively here. A Linux smoke test cannot establish Windows GUI, driver, EDIABAS, ENET/ICOM, native transport or device programming readiness.

Manual §2.1 states that since E-Sys 22.06 the expected install path is `C:\EC-Apps\E-Sys`, because the firewall rule for HTTP flashing is tied to it. Treat relocating the application and reproducing HTTP flashing as a separate Windows integration check. Manual §5.6 documents HTTP server startup only for certain connection types with `HttpUpdate.Activation=true`; default port 8888, supported alternatives 8000/8080 and 12000–13000. This HTTP server is a programming transport component, not evidence of a general Python-callable REST API.

## Configuration and isolation

Manual §2.3 identifies application settings in `<installation>/config/Esys.properties` and user-specific settings in the user's E-Sys directory. §2.6 lists supported keys:

| Key | Documented purpose |
| --- | --- |
| `User.Home` | Override E-Sys user home; otherwise the E-Sys directory is created in the normal user's home |
| `Path.Home` | E-Sys data directory |
| `Path.PsdzHome` | Parent directory containing `psdzdata` |
| `HttpUpdate.Activation` | Enable/disable HTTP flashing server |
| `HttpUpdate.ServerPort` | HTTP flashing server port |
| `HttpUpdate.MaxHttpThroughput` | Throughput limit |
| `language` | English/German |

§2.3.1 explicitly distinguishes the data directory (FA/FP/SVT/TAL/logs), the **parent** containing `psdzdata`, and the NCD root containing `unsigned`, `signed`, `default`. Do not pass the `psdzdata` child as though it were the documented parent.

The supplied settings point to external Windows data paths that are not included. They also contain nondefault security/verification-related settings. Do not adopt personalized settings as safe bridge defaults, and specifically do not carry over any disabled FSC verification. Inspect bytecode before assuming these property keys can all be overridden by `-D` arguments: the manual describes file settings, not JVM-property semantics.

## Documented functional workflows

| User workflow | Verified document behavior | Missing runtime inputs / validation |
| --- | --- | --- |
| FA load/edit and FP derivation | Manual §§7.1, 18.3: load a list of vehicle orders, select/activate one FA, then derive and display FP. FA mandatory fields: development series, lacquer, upholstery, type key, time criterion. FA metadata includes creation time/VIN; option lists are SALAPA, E-Wort, HO-Wort. §18.3 documents ISTA-P import/export. | A loadable FA can be used for real parser tests. Actual FP content depends on the matching PSdZ/KIS data. Do not manufacture a profile from FA XML fields. |
| I-Step | §§4.2.1, 5.4, 11.2: shipment/target steps feed target-SVT calculation; VCM exposes shipment/current/last steps. Construction values are validated; physical VCM values must be read from vehicle. | Matching main-series/KIS data for selectable steps and target calculation; vehicle session for VCM reads. |
| SVT Actual | §§4.2.1.1, 7.1: load from file; read from VCM; or determine from discrete ECUs, with or without Smart Actuators. These are different operations. | File fixture for parser test; connected vehicle/transport for read paths. |
| SVT Target | §§4.2.1.2, 18.2: load file; derive using KIS and FA/I-Step with Single Flash, Complete Flash or Construction Progress strategy; obtain from SWL-Cockpit; or update via PDA. | KIS data or authorized SWL-Cockpit access; target input fixtures for offline tests. |
| TAL calculate | §4.2: requires SVT Actual and Target; optional TAL filter; optionally limit ECUs to target and include mirror protocol. Difference view marks actual blue, target red. Computed TAL can be saved and transferred to TAL processing. | Real input SVTs and data requirements of the actual PSdZ service; no XML-diff replacement. |
| TAL process | §§6.1–6.6: correct TAL, VIN, tokens where necessary, connected vehicle. Coding transactions additionally require a suitable version-3 FA. SWE availability and programming protection checks precede execution; process exposes pause/stop and monitoring/TALSTATUS. BAT-HAF/S1 check is part of the original workflow. | Windows integration and vehicle/bench; software units; authenticated secure tokens as required. Do not treat successful TAL parsing as successful programming. |
| VCM | Ch.11: top viewers for FA/FP/SVT/VIN and I-Step editor; File, Master, Backup, Info & Status tabs. Master reads/writes FA/FP, steps, actual/target SVT and VIN; backup/restore paths are distinct. | No vehicle available. Reads and writes must not be conflated. VCM version info requires SP25 or later. |
| Coding | Ch.7: connected vehicle; active FA produces FP; read/load SVT; read NCD/CPS; encode using suitable CAF/NCD and TAL processing machinery. FDL editor is a separate semantic feature. | CAF/KIS data, ECU session, legitimate signing/auth for secure coding. Windows/vehicle test required. |
| FSC | Ch.17: Comfort polls status and writes/updates/upgrades/deactivates; Extended reads/checks/signs with corresponding public/private keys and executes selected jobs. FSC editor is separate. | Legitimate FSC/key/certificate fixtures for verification; no invented credentials or generated substitute authorizations. |
| SFA / secure ECU mode | Ch.14: online backend requests or existing signed token-set JSON; status reads; feature and ECU-mode operations; distinct whole-vehicle Comfort and selected-ECU Expert scope. | Authorized backend session/certificate/network or legitimate signed response file; vehicle for application/readback. Parsing a token-set file does not verify its authorization or installation. |
| KDS | Ch.12: status, master/client view, legitimate refurbishment/re-pair, token request/response, public key data. Manual explicitly says every refurbish must be BMW-authorized. | BMW-authorized token/secure backend and connected KDS participants. |
| LCS | §14.2.4: select LCS name/value; read values; write values or apply legitimate LCS token file; optional ECU reset. | Connected ECUs, data-supported capability, proper authorization; no blanket permission to disable protections. |
| Diagnostics | Supported via PSdZ/ProDiaS transport and particular E-Sys workflows, including secure diagnostics in EES25 (§20.26). | Match actual API methods; do not present a generic OBD scanner as verified original E-Sys functionality. Secure diagnostics has tester/backend prerequisites. |

## Authentication requirements from documentation

Manual §§2.3.9–2.3.10 distinguish client certificates for CBB/SFA/SCB/Sec4Diag and SWL-SEC, backend URLs, timeouts/retries and authentication types. Client-certificate import must match the latest locally generated CSR. Ch.12 and Ch.14 describe backend network availability and proper permissions as prerequisites, not optional checks. Do not send requests to personalized configured URLs merely to probe them. Do not transmit supplied vehicle/config/log values in development tests.

## Original GUI structure, not a generic XML browser

`doc/online_help.html` §2 and `esysGui.jar` resource `com/bmw/esys/gui/labels_en.properties` agree on sections:

- Comfort Mode: TAL Calculation, FSC, Certificate Management, SFA, KDS, Anflash, SecOC, Programming Protection.
- Expert Mode: TAL Processing, VCM, Coding, Coding Verification, FSC Extended, NCD Preparation, TSL Update, NAV/ENT Update, OBD-CVN, Certificate Management Extended, SFA/ECU-Mode Extended, KDS Extended.
- Editors & Viewers: FA, TAL, TALFILTER, SVT, SWESEQ, FSC, FDL, Anflash, CAF, Log, TALSTATUS.
- Data Handling: PDX Charger, Update, Delete, ODX Checker; External Applications is separately supported.

The real module factory was disassembled to `/workspace/analysis/gui-module-factory.javap.txt`. `com.bmw.esys.gui.EsysModuleFactory.createModule` maps IDs to concrete controllers, including:

| Module | Controller |
| --- | --- |
| FA/FP | `com.bmw.esys.gui.fa.FalFpController` |
| TAL Calculation | `com.bmw.esys.gui.tal.talcalculation.controller.TalCalculationController` |
| TAL Processing | `com.bmw.esys.gui.tal.talexecution.controller.TalExecutionModuleController` |
| VCM | `com.bmw.esys.gui.vcm.controller.VCMController` |
| Coding | `com.bmw.esys.gui.coding.CodingModuleController` |
| FSC Comfort/Expert | `com.bmw.esys.gui.fsc.FSCComfortController` / `FSCExpertController` |

`com/bmw/esys/gui/names/*.properties` records original control names, e.g. `moduleFalFpController.properties` has LoadFA, TakeOverSalapaElements and CalculateFp; `moduleTalCalculationController.properties` identifies each actual/target load/read/calculation action and I-Step selectors. These and the documented screenshots provide a much stronger frontend reference than inventing screen names or guessing workflows.

Suggested frontend composition after bridge operations are validated: original section navigation, common file/connection/backend menus and status, split FA/FP area, semantic FA fields and SALAPA editing, ECU/SWE tables keyed by diagnostic address, actual/target comparison colors, and structured operation/result/log areas. All visible executable actions must have a tested backend implementation and expose its real errors. Do not fill unimplemented sections with placeholder buttons or generic XML nodes. A semantic hierarchy of real FA/ECU/SWE objects is different from dumping raw XML, but it still needs validated model conversion.

## Validation status and next gates

Performed in this analysis: document extraction, launcher/runtime inspection, archive path/type survey, GUI resource inspection, static bytecode inspection of the real module factory and Framework signatures. No frontend, data calculation, transport, vehicle write or Windows behavior was exercised by this agent. Bridge integration tests are reported separately in [VALIDATION.md](VALIDATION.md).

Independent work available now: statically map services/signatures; test platform-independent Java parsing/serialization and pure calculations on clearly labeled synthetic test inputs; compile and test protocol/error handling; make semantic views of returned verified models. Missing supplied Python source does not prevent building a new bridge, but it prevents claiming to have audited or continued the existing application. Missing PSdZ data prevents a claim of meaningful FA→FP/KIS target calculation. Windows, authorized backend and vehicle checks remain separate gates.

## Evidence locations and portability

Vendor-relative references (such as `lib/PsdZ/psdz-api.jar`, `doc/online_help.html`, and `E-Sys.bat`) are relative to the supplied E-Sys installation directory, called `ESYS_HOME` by this project. The current cloud copy is `/workspace/vendor/esys2406/E-Sys2406`. Detailed extracted text and bytecode evidence remain outside Git at `/workspace/analysis`; they are analysis artifacts, not part of the Python source distribution. Missing these machine-local artifacts in a new checkout does not change the source manual/class references identified above.
