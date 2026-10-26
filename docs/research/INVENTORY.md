> Historical Java-engine research and prototype results. The active BMGARAGE application now uses Python only. These runtime results do not validate the native Python implementation; see [current validation](../VALIDATION.md).

# Supplied E-Sys 24.06 inventory

The seven uploaded ZIP volumes were downloaded, reconstructed with `zip -s 0`, checked using Python's `ZipFile.testzip()`, and extracted outside the source checkout on 2026-10-26. All archive entries passed CRC validation. Extraction rejected absolute paths, parent traversal, backslash path ambiguity and symbolic-link entries before writing files. No supplied vendor file was edited.

This inventory covers the complete archive. Behavioral analysis covers public signatures, selected service/controller bytecode, configuration/resources and manual sections; it is **not** exhaustive review of every class. The current bridge is limited to offline parsing/model operations and service probes. No preexisting Python frontend was supplied, and this project must not be described as a full E-Sys port.

## Locations

| Material | Current cloud location |
| --- | --- |
| Source project | `/workspace/ESYS` |
| Extracted installation (`ESYS_HOME`) | `/workspace/vendor/esys2406/E-Sys2406` |
| Uploaded-volume links | `/workspace/artifacts/esys2406/volumes` |
| Reconstructed ZIP | `/workspace/artifacts/esys2406/E-Sys2406-complete.zip` |
| Complete entry inventory (path, bytes, CRC32) | `/workspace/artifacts/esys2406/archive-inventory.json` |
| Uploaded-volume SHA256 manifest | `/workspace/artifacts/esys2406/volumes.sha256.json` |
| Complete JAR inventory, class names/versions and JAR SHA256 | `/workspace/analysis/jar-inventory.json` |
| Detailed API/bytecode/manual analysis evidence | `/workspace/analysis` |

Large vendor binaries and detailed extracted manual/bytecode evidence remain separate from the Git source tree. The source does not contain the uploaded installation or personalized configuration/log contents.

## Complete archive counts

| Measurement | Observed count |
| --- | ---: |
| ZIP entries | 930 |
| Files | 829 |
| Directory entries | 101 |
| Expanded file bytes | 339,768,128 |
| Reconstructed ZIP bytes | 172,321,379 |
| JAR files | 72 |
| Class entries across those JARs | 30,126 |
| Distinct class names across those JARs | 29,142 |
| Windows DLL files | 104 |
| Windows EXE files | 19 |
| Python `.py` / `.pyw` files | 0 |

Class counts include third-party dependencies, inner classes, duplicate class names in multiple JARs, the separate `fat` application, and bundled runtime helper JARs. Of the 72 JARs, 59 are under `lib`, 11 under `fat`, and two under `jre`. The original E-Sys launcher uses its explicit 59-JAR dependency set plus `lib/environment`, not every JAR recursively found in the installation.

The root files are `E-Sys.bat`, `E-Sys.exe`, the application release notes, and uninstall files. Material also includes configuration, one PDF manual, HTML manual/help and batch instructions, screenshots, schemas, environment XSL transformations, original GUI resources, Windows runtime files, prior logs and license notices. The archive does not contain a `psdzdata` directory or a supplied BMGARAGE Python application.

## Uploaded-volume fingerprints

These SHA256 hashes identify the exact supplied bytes; CRC success establishes internal ZIP integrity, not independent upstream provenance.

| Volume | Bytes | SHA256 |
| --- | ---: | --- |
| `E-Sys2406.z01` | 26,214,400 | `f047e547fba88feb882bac7bd98e979bd0b6ecab512683c15adf4392ca14fedb` |
| `E-Sys2406.z02` | 26,214,400 | `abf2cb365df0ef999eb65677826cbf43ef7ce29a270e9d7d17bbf18240cd72f1` |
| `E-Sys2406.z03` | 26,214,400 | `dc2f3c6fa0c7d23f3b79b332c3917ea0964a9ff1fed16adcea3175bc7914d1eb` |
| `E-Sys2406.z04` | 26,214,400 | `0e93ff31582e59426f78ade69f02f5a6ff42660a2d6d8ee7d88472fccfe5fa33` |
| `E-Sys2406.z05` | 26,214,400 | `f073e1c0767e2322a96cf15fcbb4936039c028688a0d0be397a64ecf2ff2e66c` |
| `E-Sys2406.z06` | 26,214,400 | `4395fc19bfb8b0c78fb894964ffde4ebaa74c3078679b7dc3620614c8bc7b20a` |
| `E-Sys2406.zip` | 15,034,983 | `8cf833ef134d45e05b56d3fa63e08c276448a8e5a1763cb0f4e8f76092127d96` |

Reconstructed ZIP SHA256: `38d821b89c18766386751774e886929363f9d6d89270cc883634a485f57b6123`.

## Principal application/backend JARs

| Installation-relative JAR | Bytes | Class entries | SHA256 |
| --- | ---: | ---: | --- |
| `lib/esysCore.jar` | 2,003,582 | 852 | `3222cc103f83630c14ce3369afc66a513d4327b74626259c683efec6fe84a37f` |
| `lib/esysGen.jar` | 1,081,274 | 846 | `7d5a05df43fa494dbfeb781b5f7be0a0577c45803627279bbecb54a06b7e8690` |
| `lib/esysGui.jar` | 3,813,623 | 1,884 | `8bceff8bd6ad877bfb59fedd5aad750706c0f3f1f023527a0ca4f73de535f8bd` |
| `lib/PsdZ/psdz-api.jar` | 936,973 | 594 | `3fe14550d14662fc6f879cb5b0abe08fbea1015b9e139428f7ed82cb50c6380c` |
| `lib/PsdZ/psdz-core.jar` | 5,382,425 | 3,125 | `f9ada4fce39765cb44a2b61bd82c788d01b4798cb05fe43dc53cf7856d700c86` |
| `lib/PsdZ/resource.jar` | 260,987 | 0 | `6f916dd80f509f9835e59d6e40665f1d109a26d5ab297181148e0a2e4241290f` |

Other dependencies include ProDiaS/driver/adaption libraries, KIS API, JAXB, XML/Xalan/Xerces, cryptographic providers, Log4j, FSC tools, security units and the ODX checker. Presence of an API JAR does not establish presence of its runtime dataset or an authorized backend session.

## Versions and runtime evidence

* Application: E-Sys `24.06.01`.
* PSdZ/API build marker observed in real service initialization logs: `24.06.02`, timestamp `2024-09-01T00:00:00Z`.
* Manual: document version `14.0`, 2024-07-02, tool version `24.06`.
* Supplied Windows runtime: Azul Zulu `11.0.15`, Windows x86_64, with JavaFX modules (`jre/release`).
* Cloud exploratory service probes initially used Linux Java `21.0.12.1`. A separately installed, checksum-verified Linux Temurin Java `11.0.29+7` toolchain is retained for compatibility tests; see `/workspace/analysis/java11-toolchain.md` and the project's [VALIDATION.md](VALIDATION.md) for actual test runtime results.

The supplied Windows EXEs/DLLs/runtime were not executed in this Linux environment. Windows GUI, JavaFX, ENET/ICOM/EDIABAS/driver integration, live vehicle operations and BMW authentication remain separate unverified capabilities.

## Confirmed missing inputs

1. **Existing BMGARAGE Python application.** No `.py` or `.pyw` files were in the supplied archive. New source in this checkout is a new implementation, not an audit or completion of an existing frontend.
2. **Matching PSdZ data home.** Real `Configuration.setRootDirectory` initialization against a clearly labeled empty fixture failed at `<data-home>/psdzdata/mapping/brref.xml`; PSdZ rolled back to root unset. The data-home argument is the parent of `psdzdata`. The mapping file is the first confirmed missing prerequisite, not the whole dependency list: referenced FA2FP `.fap`, series/KIS/ODX/CAF/security data and relevant SWE software units are required by their workflows.
3. **Representative legitimate workflow inputs.** No supplied FA/FP/SVT/TAL/NCD/FSC project fixtures were identified. Synthetic parser fixtures must remain labeled as tests and cannot validate real FA→FP, target SVT, coding or TAL execution.
4. **Windows and authorized runtime targets.** No connected vehicle/bench, native transport validation, authorized BMW backend session or issued operation tokens were established. Credentials and private keys must remain in appropriate secure operator tooling and must not be added to chat or source.

Detailed behavior and limitations: [SERVICE_TRACE.md](SERVICE_TRACE.md), [SECURITY_FEATURES.md](SECURITY_FEATURES.md), [WORKFLOWS.md](WORKFLOWS.md). Executed project tests and enabled bridge operations: [VALIDATION.md](VALIDATION.md).
