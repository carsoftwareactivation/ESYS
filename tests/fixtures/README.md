The FA, SVT and TAL documents were serialized by the supplied PSdZ Java objects
(`FA.getAsXML`, `SVT.getAsXML`, `TAL.getAsXML`) from deliberately synthetic
test-only inputs. The VIN is synthetic and checksum-valid. The DME/software
identifiers are fixtures, not a supported vehicle combination or programming plan.

The FAList fixture wraps the synthetic FA in the original E-Sys list format and
was loaded and converted using `FalLogic.open` and `FalLogic.getModelAsPsdz`.

`fp.xml` is a separate synthetic native-algorithm fixture, not a vehicle profile
generated from the FA. Its explicitly specified sorted value stream is
`02010002000201000200010201`; appending ASCII `0300LCSW` and applying the
AUTOSAR-P4/BMW wrapper gives the fixed VPC `005B2113`. The fixture tests native
serialization and checksum match/mismatch behavior, never FA→FP generation,
mapping signature/decryption, full FA/FP consistency or vehicle compatibility.

Tests only parse the files. They do not compute a target SVT, generate an FP or
TAL from vehicle data, or connect to/process a vehicle. A stored TAL status of
`Executable` must never be interpreted as a successful execution.
