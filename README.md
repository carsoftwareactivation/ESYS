# BMGARAGE — Python standalone

BMGARAGE runs as a native Python application, with its own in-process engine.
**No Java engine, Java runtime, E-Sys installation or E-Sys process is required.**
The runtime uses Python's standard library and Tkinter. The Python engine can
also be used without the graphical interface through its API or command line.

## Launch on Windows

1. Install Python 3.10 or newer with Tcl/Tk support.
2. Extract `BMGARAGE-Python-Standalone.zip`.
3. Double-click `BMGARAGE.pyw` inside the extracted `BMGARAGE` folder.
4. Choose **Options → PSdZDATA settings → Browse** when you want to select data.

Select your `psdzdata` folder or the folder containing it. BMGARAGE saves the
selection in its own user settings and restores it on the next launch. You can
clear the selection or change it whenever needed. Saved-file tools work without
selecting a dataset, so no dataset upload is required to start the application.

The archive is a Python application distribution, not a compiled Windows EXE.
Python/Tk must be available on the computer. No third-party Python packages are
required. Windows native execution is still untested; actual graphical checks
were run on Linux using Tk under Xvfb.

## Implemented natively

- Read supported saved FA and E-Sys FAList documents into semantic fields and
  option-code lists; select entries explicitly in multi-order lists.
- Read supported saved SVT ECU/software information and TAL work items/statuses.
- Parse and compare I-Step identifiers using native Python value logic.
- Select, remember and inspect a PSdZDATA location without writing to that data.
- Inspect mapping XML and count named series for inventory purposes.

These readers perform supported structural and field-syntax checks. They do not
claim BMW schema completeness, vehicle compatibility or successful calculation.
TAL statuses are stored document values, not programming results. Additional
TAL context that was not inspected is disclosed by the viewer.

## Native engine still to implement

A Python-only implementation must reproduce the algorithms and protocols that
previously lived in the Java engine. This version does **not** implement native
FA→FP calculation, compatible/installed target-I-Step resolution, SVT Target,
TAL calculation/processing, live VCM/ECU access, coding, FSC, SFA, KDS, LCS or
vehicle diagnostics. Selecting PSdZDATA does not enable these algorithms.
There are no action buttons that report fabricated completion for them.

The original service analysis remains useful research for further native
implementation. It documents data relationships, checksums, validation and
legitimate BMW authorization requirements. Its former Java-backed tests do not
validate this Python engine. Windows vehicle/bench integration and authorized
backend workflows require separate implementation and verification.

## Command line

From the extracted source folder:

```powershell
py -3 -m bmgarage info
py -3 -m bmgarage --psdzdata "D:\BMW\psdzdata" data
py -3 -m bmgarage inspect fa "D:\FA.xml"
py -3 -m bmgarage inspect fa "D:\FAList.xml" --entry 2
py -3 -m bmgarage istep F020-24-07-500 F020-24-11-500
```

`--psdzdata` is optional. The command line reuses the saved selection when no
explicit path is given. No Java or E-Sys environment variables are read.

## Develop and test

```sh
python3 -m unittest discover -s tests -v
python3 -m bmgarage info
python3 scripts/run_gui_smoke.py
python3 scripts/package_standalone.py
```

The graphical smoke runner needs a real display or Xvfb; it starts and stops
only its own display server. On this prepared Debian cloud environment,
`sh scripts/cloud_setup.sh` performs the tests and builds the Python-only ZIP.
No JVM or vendor-library build is involved.

[Current validation](docs/VALIDATION.md) ·
[Native architecture](docs/ARCHITECTURE.md) ·
[Historical service research](docs/research/SERVICE_TRACE.md)
