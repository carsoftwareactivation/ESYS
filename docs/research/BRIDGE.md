> Historical Java-engine research and prototype results. The active BMGARAGE application now uses Python only. These runtime results do not validate the native Python implementation; see [current validation](../VALIDATION.md).

# Java bridge contract

The Python client starts an owned Java subprocess with the original launcher's
ordered classpath and an isolated working directory/user home. It does not
execute `E-Sys.bat` or load its saved personal settings. The Java process uses
explicit adapters over the original public APIs, not a generic reflection or
arbitrary-method gateway.

UTF-8 JSON lines on stdin/stdout:

```json
{"id":1,"op":"istep.parse","args":{"value":"F020-24-07-500"}}
{"id":1,"ok":true,"result":{"canonical":"F020-24-07-500","mainSeries":"F020","year":24,"month":7,"number":500}}
```

A rejected request returns `ok:false` and `error:{type,message}`. Python raises
`BridgeError`, retaining the Java type in `java_type`. Operation errors do not
mean success and do not discard subsequent requests. A transport mismatch or
timeout stops the owned process; a later call can start a fresh session.
Vendor output is redirected to stderr before vendor initialization. Python
drains it into a bounded in-memory diagnostic buffer rather than mixing it
with results or copying personal state to disk.

| Operation | Arguments | Result scope |
| --- | --- | --- |
| `versions` | none | Actual E-Sys, PSdZ API, Java, OS version strings |
| `services` | none | Actual implementation class names, data-root flag/version |
| `istep.parse` | `value` string | Original I-Step canonical value and components |
| `istep.compare` | `left`, `right` strings | Original comparator sign and canonical values |
| `fa.inspect` | `xml`, optional zero-based `entryIndex` | Validated FA semantic fields/options; format/entry metadata |
| `svt.inspect` | `xml` | Saved SVT semantic ECU and SGBM rows |
| `tal.inspect` | `xml` | Saved TAL lines/actions and separately stored statuses |

The GUI presents FAList entry numbers starting at one and translates them to
the explicit zero-based API index. The bridge rejects a multiple-entry FAList
without an explicit index. For E-Sys FAList files the original
`FalLogic.open`/`getModelAsPsdz` path is used; for PSdZ documents the original
FA/SVT/TAL parsers are used after secure XML checks. No raw XML tree is used as
the GUI's functional substitute.

Requests are bounded to 8 MiB (the Python UTF-8 byte limit includes JSON
overhead). Response lines are bounded to 16 MiB. The viewers accept UTF-8 XML
with an optional UTF-8 BOM. External DTDs, entities, XInclude and external
schema references are rejected. Only the supplied TAL schema name is accepted
in `refSchemaFile`. Documents in other formats need an explicitly implemented
and tested vendor-backed import path.

No vehicle connection, FA activation/write, FP or target/TAL calculation,
coding, authentication, FSC/SFA/KDS/LCS operation, or diagnostic operation is
exposed by this bridge version. Calling an unsupported name returns an error.
The service trace documents the real next API paths and prerequisites; it
must not be mistaken for implementation or successful execution.
