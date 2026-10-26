> Historical Java-engine research and prototype results. The active BMGARAGE application now uses Python only. These runtime results do not validate the native Python implementation; see [current validation](../VALIDATION.md).

# E-Sys 24.06 security, coding and diagnostics trace

> Review scope: the whole supplied archive was inventoried. Analysis below uses public signatures, selected bytecode call chains, configuration/resources, and manual sections; it does not claim exhaustive review of all 30,126 class entries. The current Python-to-Java implementation is limited to offline parsing/model handling and service probes. See [VALIDATION.md](VALIDATION.md) for the implemented operations and measured test results. This is not a full E-Sys port. No supplied Python application, PSdZ data tree, Windows execution, live vehicle operation, or BMW authentication was available for validation.

## Scope and evidence standard

The supplied installation `/workspace/vendor/esys2406/E-Sys2406` was inspected without changing it. This report distinguishes bytecode/API inspection from runtime validation. None of the coding, FSC, SFA, KDS, LCS, certificate-backend or vehicle-diagnostic operations below was executed. Class presence and method signatures do not establish a successful ECU operation or authorization.

Evidence was obtained from the supplied `esysCore.jar`, `esysGui.jar`, `PsdZ/psdz-api.jar`, and `fs/fstool-3.2.1.jar`, using the installed JDK module:

```sh
java --module jdk.jdeps/com.sun.tools.javap.Main -p -c -classpath /workspace/vendor/esys2406/E-Sys2406/lib/esysCore.jar:/workspace/vendor/esys2406/E-Sys2406/lib/PsdZ/psdz-api.jar fully.qualified.ClassName
```

`javap` does not accept the JVM-launcher wildcard expansion in this module invocation; use explicit JAR paths. The classfile major versions and raw descriptors are recorded in `security-signatures.json`. Public declarations and bytecode outputs are retained in the external evidence directory `/workspace/analysis`; short evidence filenames below refer to that directory. The authoritative user-facing workflow descriptions are `doc/online_help.html` sections linked below; those documents are reference data, not authorization to execute their procedures.

## Actual service locations

The E-Sys wrappers lazily obtain the real PSdZ services through `com.bmw.psdz.api.ServiceLocator.locate(Class)`:

| E-Sys wrapper | PSdZ interface | Verified evidence |
|---|---|---|
| `domain.psdz.PsdzSecureCoding` | `com.bmw.psdz.api.SecureCoding` | `security-psdz-bytecode.txt`, `getSecureCoding` and interface calls |
| `domain.psdz.PsdzKds` | `com.bmw.psdz.api.Kds` | `security-psdz-bytecode.txt`, `getKds` |
| `domain.psdz.PsdzSfa` | `com.bmw.psdz.api.SecureEcuModesAndFeatureActivation` | `sfa-bytecode.txt`, accessor and all service calls |
| `domain.psdz.PsdzSecurityManagement` | `com.bmw.psdz.api.SecurityManagement` | public wrapper/API declarations; full behavior not executed |
| `domain.psdz.PsdzSecureDiagnostics` | `com.bmw.psdz.api.SecureDiagnostics` | `security-psdz-bytecode.txt`, private `getService` |
| `domain.psdz.PsdzProgramming` | `com.bmw.psdz.api.Programming` | `security-additional-bytecode.txt`, `getProgramming` |

These are Java services loaded in-process. An API named PSdZ does not imply an external HTTP service which Python can simply call. A backend-specific adapter must preserve service initialization and the actual data types.

## Coding

### Verified call path

`gui.coding.CodingController` / `CodingModuleController` are present. The actual domain entry point is `domain.coding.CodingLogic`, constructed with actual and target `SvtLogic` instances.

- `generateTalBeforeStart(IProgressMonitor, Hashtable<EcuIdentifierCompare,Object>)` checks SGBMID/CAFD files through `PsdzConfiguration.existsFileForSGBMID`, then calls `generateCodingTal`.
- `code(IProgressMonitor,TAL,FalLogic,TalExecutionSettings)` delegates to private `executeTal`.
- `executeTal` creates `ProgrammingControl`, sets TAL settings, FA and TAL, enables events, assigns programming-token logic, optionally assigns MSM and VCM logic, calls `checkNCDsForTal` for FA/shipment coding, then calls `executeTalSync()`.
- `codeAnliefer` generates FP from the active FA, calls `PsdzLogic.fillNCD(...,CodingType.SHIPMENT)`, then the same execution path.
- `readNCD(EcuIdentifier,TPartIdent)` goes to `PsdzEcu.requestNCD`, then `ECU.requestNCD(Connection,ECUIdentifier,SGBMID)`.
- `domain.securecoding.SecureCodingLogic` drives actual NCD calculation, signing requests, signature response analysis and SWL security-permission checking. Its `generateRequestSignatureNcdList` calls `PsdzLogic.generateNCD(Map,FA,FP)`.

Bytecode evidence: `security-logic-bytecode.txt` (`CodingLogic` around lines 60–270, `SecureCodingLogic` around 4600 onward).

### Exact relevant PSdZ API declarations

`SecureCoding` exposes:

- `requestSignatureOnline(List<RequestSignatureNcdEto>, SecureCodingConfigCto, VIN) -> RequestNcdSignatureResponseCto`
- `requestCalculationNcdWithPartialSuccess(List<RequestNcdEto>, FA, SecureCodingConfigCto, CodingType) -> CalculationNcdResultCto`
- `requestCalculationNcdAndSignatureOffline(List<RequestNcdEto>, File, SecureCodingConfigCto, VIN, FA) -> Set<SecurityBackendRequestFailureCto>`
- `checkNcdAvailabilityForGivenTal(TAL, File, VIN) -> CheckNcdResultEto`
- `checkNcdAvailabilityWithoutCarConnection(PotentialCafdsResultCto, File, VIN) -> CheckNcdInfoForBtldCafdCombiResultEto`
- `serializeNcd(NCD) -> String`, `deserializeNcd(String) -> NCD`
- `readNcdFromFile(File,VIN,SGBMID,SGBMID) -> NCD`
- `checkSwlSecurityPermissions(SecureCodingConfigCto,List<SGBMID>,List<VIN>) -> SwlSecurityPermissionResponseCto`

### Required inputs and limits

`online_help.html#em_coding` lines 3485–3492 describes BAT/HAF switch checking and requires the matching I-level container with KIS data plus FA for KIS-based SVT target calculation. `#inst_backend_sec_coding_sfa` lines 8467–8519 states that secure coding uses signed NCDs generated/signed outside E-Sys, with SWL-Sec2 backend access and enrollment, using username/password or certificate authentication. Never replace these with self-signed or fabricated responses. CAFD/SWE/KIS data availability, an actual authorized backend session and vehicle data have not been established by class inspection.

## FSC

### Offline parsing and verification

`domain.fsc.FSCLogic.open(File)` delegates to `FscAdapter.readFrom(File)` which calls `com.bmw.swt.fstool.core.Fsc.readFrom(String)`. It optionally calls `verifyData` according to E-Sys properties. The original `FscAdapter.verifyData(Fsc)` checks supported FSC types and uses `verifyDataClassic()` or `verifyDataShort()`.

`verifySignature(Fsc, File publicKey)` uses `SecurityUtil.readPublicKey`, the configured `FSC_KEY_ALG` / `FSC_SIGN_ALG`, and `Fsc.verifySignature(PublicKey,String)`. This can become a real offline bridge operation given a legitimate sample FSC and authorized verification public key. A successfully parsed FSC is not a signature-valid or activated FSC.

The original JAR also contains signing entry points accepting private keys. Their presence grants no authority to mint entitlement objects. No private keys were read, generated or requested and no FSC was signed.

### Vehicle operations

`gui.fsc.FSCComfortController` invokes `domain.fsc.SwtLogic.callSWTAction(SWTActionType,IProgressMonitor)`. That logic constructs an FSC TAL through `createFSCTAL`, processes it through its existing `executeTal`, and judges success using `ProgrammingControl.isFinishedWithoutError(returnedTal)`. Therefore FSC deployment is an actual programming workflow, not just saving a file.

`FSCCommonController.requestSWTStatus` calls `SwtLogic.requestSwtStatus`, which reaches `PsdzProgramming.requestSWTStatus`. The latter calls `Programming.requestSWTStatus(Connection,...)`. The expert controller's diagnostic operations reach `Programming.callSWTDiagService(Connection,ECUIdentifier,SWTDiagServices,Map)`.

Evidence: `fsc-gui-bytecode.txt` and `security-additional-bytecode.txt`. Documentation: `online_help.html#cm_fsc` lines 1252–1315 and `#em_fsc`. The docs distinguish writing, updating/activation, upgrade and deactivation. A UI must retain that distinction and use legitimately issued FSCs/certificates.

## SFA

`domain.sfa.SfaLogic` and the comfort/expert GUI controllers exist. `PsdzSfa` delegates to `SecureEcuModesAndFeatureActivation` using real `Connection`, `SVT`, `VIN`, ECU identifiers and secure-token DTOs.

Verified calls include:

- `readSecureEcuMode(Connection,Set<ECUIdentifierCto>,SVT)`
- `discoverAllFeatureStatus(Connection,SVT)`
- `readStatus(StatusRequestFeatureTypeEto,Connection,SVT,Set<ECUIdentifierCto>,boolean,int,int)`
- `readShortStatus(Connection,ECUIdentifierCto,FeatureIdCto)`
- `requestSecureTokenPackageForOrder(...) -> SecurityBackendRequestIdEto`
- `requestNewestSecureTokenPackageForVehicle(...) -> SecurityBackendRequestIdEto`
- `requestDirectSecureTokensPackage(...) -> SecurityBackendRequestIdEto`
- `fetchResultOfSecureTokenCalculation(SecurityBackendRequestIdEto)`
- `fetchCalculationOfSecureTokensOffline(File,SVT)`
- `writeSecureToken(Connection,Set<SecureTokenEto>,SVT)`
- `writeSecureTokenToECUs(Connection,SecureTokenForVehicleEto,Set<ECUIdentifierCto>,SVT)`
- `verifySecureTokens(Connection,Set<ECUIdentifierCto>,SVT)`

Backend requests and fetching results are distinct operations; receiving a request handle is not completion. Backend requests accept endpoint lists and authorization inputs supplied by E-Sys configuration/backend login.

Docs `#secure-ecu-modes-comfort` line 1590 requires valid secure tokens to enter Plant/Engineering from Field. `#em_sfa_lcs` lines 5175–5186 requires BMW backend network access, imported valid E-Sys client certificate and configured SFA backend URL for direct-server functionality. `#inst_backend_sec_coding_sfa` lines 8528–8551 states CBB/SFA client certificate requirements and optional BASIC credentials for extended authorization. No backend reachability or entitlement was tested.

## KDS

KDS is component theft protection, not an authorization-free coding helper (`online_help.html#kds-comfort-mode`, line 1808).

High-level domain classes:

- `ReadKdsLogic.performQuickCheck`, `performQuickCheckSp25`, `requestKdsDataSP25`, `readOwnPublicKey`, `readPairedPublicKey`.
- `RequestKdsTokenLogic` constructs backend request files using ECU/KDS selections.
- `KdsLogic` implements operation-mode processing and backend response processing.

`PsdzKds` locates `com.bmw.psdz.api.Kds`; exact relevant API declarations:

- `readPublicKey(Connection,KdsIdCto,Long,Integer,Integer) -> ReadPublicKeyResultCto`
- `performQuickKdsCheck(Connection,KdsIdCto,Integer,Integer) -> PerformQuickKdsCheckResultCto`
- `performQuickKdsCheckSP25(Connection,KdsIdCto,Integer,Integer) -> PerformQuickKdsCheckResultCto`
- `requestKdsDataSP21(...) -> List<RequestKdsDataResultCtoSP21>`
- `requestKdsDataSP25(...) -> List<RequestKdsDataResultCtoSP25>`
- `performChangeOfOperationMode(Connection,KdsIdCto,SecureTokenEto,Integer,Integer) -> KdsActionStatusResultCto`
- `performRefurbishProcess(Connection,KdsIdCto,SecureTokenEto,KdsActionIdEto,Integer,Integer) -> KdsActionStatusResultCto`

The E-Sys wrapper supplies null optional timeout parameters in these overloads. Mutating KDS operations require the real server-issued secure tokens; do not manufacture those tokens, derive private keys from public information or treat a read result as authorization to modify.

Docs lines 1811–1833 require reachable BMW SFA backend, valid imported client certificate and configured URL for direct backend features. Lines 1857–1860 distinguish SP21/KDS2.0 and SP25/KDS2.5. These variants must not be collapsed in Python.

## LCS

`domain.sfa.LcsLogic.readLcs` calls `PsdzSfa.readLcs(Connection,SVT,Set)`; writes use `PsdzSfa.setLcs(Connection,Set<EcuLcsValueCto>)`. The PSdZ interface also has a `setLcs(Connection,Set<EcuLcsValueCto>,SVT)` overload. Actual values and failures arrive in `GenericPsdzResult<ReadLcsResultCto>`.

Docs `#em_sfa_lcs` explains LCS#00 (service-pack switching), LCS#01 (named "SecOC Bypass" in the original documentation), LCS#02 (TimeSupreme), LCS#03 (integrity protection), and LCS#04 (IuK cluster configuration). Lines 5597–5612 describe authorized LCS token files and the required ECU reset after an LCS#01 switch. Do not enable security-state write controls solely because these APIs are present. The frontend must preserve applicable token/authorization checks and model reset as a separate operation.

## Secure diagnostics and general diagnostic limits

`PsdzSecureDiagnostics.registerAuthService29certificate(AuthService29Certificate)` calls `SecureDiagnostics.registerAuthService29Callback(handler, PsdzConnection.getConnection())`. `AuthService29Certificate` implements `SecureDiagnosticsCallbackHandler`:

- `getAuthService29Certificate() -> byte[]` delegates to the certificate helper.
- `signAuthService29Challenge(byte[]) -> byte[]` uses E-Sys certificate administration and its corresponding private key, using Java's signature provider. The bridge should retain this original implementation in Java rather than copying key material to Python.

`SecureDiagnostics.unlockGateway(Connection)` is an authenticated workflow requiring a correctly initialized connection and callback; method presence is not a successful authenticated session.

The original API contains `suppressTlsAndAuthService29(boolean)`. It was inspected only. It must not be used as a bridge recovery mechanism for unavailable authentication. TLS/certificate checks must remain enabled; missing authorization must remain a clear failure.

Documentation `#secure-diagnostics-authenticated-connections` lines 8592–8596 requires a Service29 certificate for the vehicle VIN and tester authentication at the gateway. Lines 8615–8616 requires TIS client certificate for Sec4Diag calls. Lines 8637–8641 enables connection authentication and uses a VIN-matching existing certificate. Lines 8665–8687 requires legitimate Sec4Diag login, tester-profile selection and backend retrieval when no certificate exists. Sec4Diag login section lines 8557–8567 states strong authentication (username, PIN, YubiKey) and token expiry. These are user/operator credentials to be supplied through the proper secure authentication UI, not chat or source files.

FSC's `SWTDiagServices` and `ECU.requestContextInfoFromVehicle` are verified diagnostic APIs. This inspection has not established a general arbitrary-UDS diagnostic client, fault-memory workflow, transport access or connected ECU response. Those capabilities must not be claimed from interface names.

## Result handling required for a truthful bridge

`GenericPsdzResult<T>` supplies `getStatus()`, `getTimeStamp()` and `getResultObject()`. Nested DTOs have separate ECU failure collections:

- `ReadLcsResultCto`: `getEcuLcsValues()` and `getFailures()`.
- `ReadStatusResultCto`: `getFeatureStatusSet()` and `getFailures()`.
- `RequestNcdSignatureResponseCto`: signature list, failures and progress status.
- `KdsActionStatusResultCto`: action status, failure response and action error code.

A bridge must preserve overall status, partial success, per-ECU failures and backend request progress; `exception == none` is not a sufficient success condition. Token request IDs and pending responses are not successful feature activation. TAL success should be evaluated from the returned TAL/transaction states as the original E-Sys logic does.

## Remaining resources and tests

Verified here: classfile/API inspection, exact wrapper delegation and documentation prerequisites. Not run: backend authentication, secure coding signing, FSC deployment, SFA request/token writes, KDS reads or writes, LCS reads or writes, or Service29 vehicle authentication. No simulated success paths were introduced.

Required for meaningful integration beyond offline object processing:

1. Existing BMGARAGE Python source (none is present in this installation archive).
2. Correct PSdZData/I-level/KIS/CAFD/ODX/SWE data required for the chosen workflow, and representative legitimate FA/SVT/TAL/NCD/FSC files. A complete dataset is not needed to test every offline parser, but code-generation and calculation claims require their actual data.
3. Windows native runtime/driver execution and an authorized vehicle or appropriate bench, for operations using the supplied Windows DLLs and actual ECU connections.
4. Legitimate BMW backend access, client certificates, enrolled accounts/roles and issued tokens as required by each selected secure operation. Existing public truststores are not proof those credentials exist.
5. Read-only end-to-end checks first; any live state-changing operation requires a concrete target and operator authorization.

Do not ask for private-key or password values in chat. No credentials were read or requested during this analysis. A file-processing action is not authorization verification, entitlement issuance, deployment or activation.

## Evidence locations and portability

Vendor-relative references (such as `lib/PsdZ/psdz-api.jar`, `doc/online_help.html`, and `E-Sys.bat`) are relative to the supplied E-Sys installation directory, called `ESYS_HOME` by this project. The current cloud copy is `/workspace/vendor/esys2406/E-Sys2406`. Detailed extracted text and bytecode evidence remain outside Git at `/workspace/analysis`; they are analysis artifacts, not part of the Python source distribution. Missing these machine-local artifacts in a new checkout does not change the source manual/class references identified above.
