# Native operation status

This is the status of the active Python engine, not the archived Java bridge.
The entire supplied installation was inventoried; selected service call chains,
schemas, resources and manual workflows were traced. It would be inaccurate to
describe that as exhaustive semantic analysis of all 30,126 class entries.
The upload contained no existing Python app or PSdZDATA tree.

| Workflow | Implemented and testable in Python | Required before full operation |
| --- | --- | --- |
| Initialization | In-process engine; manual remembered data selection; no JVM or E-Sys process | Each missing service needs its own native implementation; no Java service bootstrap can supply it |
| FA | Semantic New/Edit/Save as; explicit FAList selection; structural checks | Full dataset compatibility checks and vehicle activation/write paths |
| FA→FP | Saved FP/VPC verification, exact serialization/checksum; untrusted selector/range/consistency core; genuine BRREF resource lookup | Actual FAFP format/trust/decryption support, matching data and genuine FA→expected FP vectors; see TRUST_REQUIREMENTS.md |
| I-Step | Identifier parse, canonicalize, compare | Matching KIS data, allowed/compatible step resolver and VCM step access |
| VCM | No live read/write operation | VCM protocol/data model, Master/Backup separation, integration/readback validation |
| SVT Actual | Saved ECU/software/diagnostic-address inspection | Distinct VCM and ECU inventory read implementations, actual connected-vehicle tests |
| SVT Target | Saved SVT inspection does not calculate a target | Native KIS/construction-strategy algorithms, real data and reference target results |
| TAL calculation | Saved TAL work-item/status inspection | Transaction-planning rules, actual/target SVTs, data, filters and expected TAL vectors; an XML diff is insufficient |
| TAL processing | No execution | Transaction executor, software availability/protection checks, progress/cancel/recovery, validated hardware and required authorization |
| Coding | No encoding/FDL/ECU write | Native CAF/NCD processing, valid data, legitimate signing/authorization where required, vehicle validation |
| FSC | No FSC verification/import/write | Authentic format/key/certificate vectors, native verification/job implementation and authorized ECU interaction |
| SFA | No backend or token application | Native signed-token validation, legitimate backend/session/certificates, authorized vehicle operation/readback |
| KDS | No pairing/refurbishment | Native protocols, legitimate BMW-authorized tokens/backend and connected participants |
| LCS | No read/write/token application | Data-supported ECU protocol, proper token/authorization validation and hardware tests |
| Diagnostics | Explicit read-only VIN over HSFZ/DoIP; local protocol-peer tests | Real ENET and Windows validation; full diagnostic/secure-diagnostic services require separate implementation and applicable authorization |

An operation is not enabled merely because its screen name, data folder,
certificate file or transport socket exists. The GUI contains executable
controls for implemented operations and a status table for remaining work.
It never reports a file's stored TAL status as a completed vehicle operation.

For production FP development, the next missing non-secret inputs are a genuine
matching FAFP resource and an FA with its expected FP from the original tool,
plus the legitimate public trust inputs and documented provider profile needed
to verify that resource. Private keys, credentials and vehicle-specific
authorizations belong in the user's local secure configuration, not Git or chat.
Selecting a local PSdZDATA folder remains supported and does not require uploading
the whole dataset. All-model vehicle support requires validation across actual
F/G architectures; one successful synthetic peer or one chassis cannot prove it.

Original traced workflows and their evidence are retained in
[service research](research/SERVICE_TRACE.md) and
[manual/resource research](research/WORKFLOWS.md). Historical Java test results
are not evidence that any missing native operation works.
