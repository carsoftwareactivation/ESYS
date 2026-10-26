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

The XML readers bound byte size, nesting and element count. They reject DTDs,
entities, XML includes, external schema references, conflicting diagnostic
addresses, duplicate supported identities, and unsupported TAL work-item types.
Accepted results report their limited structural-validation scope and never
claim vehicle compatibility. Additional TAL context not inspected is disclosed
in the viewer. Stored status is distinct from execution.

No calculation or vehicle action is faked. Native FA→FP, compatible target
I-Steps, SVT Target, TAL generation/processing, VCM/ECU communication, coding,
FSC, SFA, KDS, LCS and diagnostics remain unimplemented. They require a native
algorithm/protocol implementation and suitable validation. Pointing at a dataset
cannot replace that work or provide BMW authorization.

## Research continuity

The supplied installation was previously inventoried and its service workflows
traced. Those reports are preserved under `docs/research` and explicitly marked
historical. The Java prototype itself is preserved outside the active checkout
at `/workspace/research/bmgarage-java-prototype`. It is not included in the
Python-only distribution. Original supplied vendor files remain separate and
unchanged as research materials.

The archived Java-backed test results do not validate the native Python engine.
Current results are recorded in [VALIDATION.md](VALIDATION.md).
