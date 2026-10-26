# Native Python architecture

The active application is implemented in Python and runs independently of an
E-Sys installation. It does not start a JVM, load JARs, call a vendor executable,
embed the Java GUI, or communicate with the superseded Java bridge.

| Component | Responsibility |
| --- | --- |
| `BMGARAGE.pyw` | Windows graphical entry point |
| `bmgarage/gui.py` | Application screens, native file loading, worker queue and manual settings |
| `bmgarage/engine.py` | In-process operation dispatch and selected data location |
| `bmgarage/models.py` | Native saved FA/FAList, SVT, TAL and I-Step processing |
| `bmgarage/fa_editor.py` | In-memory FA creation and selected-entry edits, validated before return |
| `bmgarage/fp.py` | Saved FP semantics, canonical profile bytes and VPC checksum comparison |
| `bmgarage/fap.py` | Untrusted cleartext mapping algorithms, with production trust gate closed |
| `bmgarage/diagnostics.py` | Bounded read-only HSFZ/DoIP VIN clients, with optional verifying DoIP TLS |
| `bmgarage/diagnostic_ui.py` | Explicit endpoint settings and genuine VIN request/result UI |
| `bmgarage/resources.py` | Actual BRREF lookup and FA2FP file discovery without trusting mapping contents |
| `bmgarage/data.py` | Read-only inspection of the selected PSdZDATA directory |
| `bmgarage/settings.py` | Application-owned preferences location and CLI preferences loading |
| `bmgarage/__main__.py` | Independent command-line access to the same Python engine |

The interface calls an ordinary Python object on a background thread. No IPC
protocol or external processing service is required. Python and Tkinter are
the application runtime; the distribution contains no Java runtime or engine.

## PSdZDATA selection

The user selects either a `psdzdata` directory or its parent in the settings
dialog. The application records the normalized actual data-directory path in
`gui-settings.json` under its own BMGARAGE user-settings directory. Windows uses
LocalAppData, falling back to AppData. The source cloud environment uses the
ignored project-local `.bmgarage` directory.

Selection can be changed or cleared. The last path is restored when the
application reopens. No dataset is required at startup or to use saved-file
readers. A missing remembered path is reported in System & Data and does not
disable the rest of the application. The CLI accepts `--psdzdata` and otherwise
uses the saved selection.

Data inspection checks folder presence, known data-directory names, readable
mapping XML and named series counts. It does not initialize the former Java
services. It does not claim BMW schema validity, complete dependencies or
calculation availability. A well-formed mapping file is inventory information.
The application never creates, modifies or substitutes files in a selected
dataset.

## Supported native processing

Saved documents are parsed into semantic dictionaries and displayed as domain
fields/tables. FAList entries require explicit selection. I-Step canonicalization
and comparison implement the value behavior identified during research.

The FA editor creates a document or edits a snapshot of the loaded FAList entry.
It validates the resulting serialization before replacing the in-memory result.
Save as is explicit and writes atomically; original files are not automatically
overwritten. File editing does not activate an FA, derive an FP or modify VCM.

The native FP module inspects stored categories/criteria and implements sorted
binary serialization and AUTOSAR CRC32/P4. A matching FA supplies the paint and
upholstery bytes required to compare a stored VPC. The viewer distinguishes
unchecked, matched and mismatched checksums. A match is not FAP authentication,
complete FA/FP consistency validation or evidence of profile generation.

Real BRREF uses development-series element text, with per-series mapping-ID
override or parent inheritance. Current resources are discovered using
`swe/fafp/fafp_<id>.fap.<major>_<sub>_<patch>`. Legacy main-series files are
listed for discovery only; their retrieval is not assumed supported.

The XML readers bound byte size, nesting and element count. They reject DTDs,
entities, XML includes, external schema references, conflicting diagnostic
addresses, duplicate supported identities, and unsupported TAL work-item types.
Accepted results report their limited structural-validation scope and never
claim vehicle compatibility. Additional TAL context not inspected is disclosed
in the viewer. Stored status is distinct from execution.

The FAFP module implements selector/range/consistency algorithms on cleartext
explicitly typed as untrusted. Its production gate always raises; a signature's
presence is not verification. Missing trust/decryption support and genuine
reference vectors prevent production generation. See [trust requirements](TRUST_REQUIREMENTS.md).

`diagnostics.vin` creates a short-lived native TCP client only after an explicit
request. It requires a numeric endpoint and physical target; it performs no
discovery or automatic startup probes. HSFZ uses one-byte addresses; DoIP uses
two-byte addresses and routing activation. Only UDS `22 F190` is sent. Delivery
ACKs are not successful diagnostic results. Wrong addresses, malformed frames,
denials, oversized responses and bounded deadlines produce errors. TLS verifies
certificate chains and hostnames without fallback. Local peer tests are not
vehicle or all-model compatibility validation.

Native authenticated FA→FP, compatible target I-Steps, SVT Target, TAL
generation/processing, VCM/SVT reads/writes, coding, FSC, SFA, KDS, LCS and
general/secure diagnostics remain unimplemented. Pointing at a dataset cannot
replace those implementations or provide BMW authorization. No calculation or
vehicle action is faked.

## Research continuity

The supplied installation was previously inventoried and its service workflows
traced. Those reports are preserved under `docs/research` and explicitly marked
historical. The Java prototype itself is preserved outside the active checkout
at `/workspace/research/bmgarage-java-prototype`. It is not included in the
Python-only distribution. Original supplied vendor files remain separate and
unchanged as research materials.

The archived Java-backed test results do not validate the native Python engine.
Current results are recorded in [VALIDATION.md](VALIDATION.md).
