# Native FP processing milestone

This milestone adds actual native saved-profile processing while keeping the
unimplemented full FA→FP path unavailable. All code uses the Python standard
library; no Java execution was used for its implementation or testing.

## Implemented algorithms

`bmgarage.fp.serialize_categories` sorts numeric category IDs and criterion
values, retaining repeated criterion values. Category IDs/counts are one byte;
criterion values are unsigned big-endian 16-bit integers. FP version 1 uses a
one-byte criterion count; versions 2 and 3 use a two-byte count. Unsupported
versions, out-of-range values and count overflows are rejected.

VPC processing serializes these sorted values **without the FP version byte**,
then appends ASCII paint followed by ASCII upholstery from the matching FA.
CRC-32/AUTOSAR-P4 uses polynomial `F4ACFB13`, reflected processing, initial and
final XOR `FFFFFFFF`. The original wrapper reserves `FFFFFFFF` and substitutes
`FFFFFFFE`. The four checksum bytes are represented as big-endian hex.

The standard check vector `123456789 → 1697D06A` and independently specified
binary/vector examples are tested. The synthetic FP fixture's VPC is
`005B2113`. It is algorithm evidence, not an end-to-end vehicle-profile oracle.

## Actual application operation

Open a saved FP in **FP Viewer** to see semantic category/criterion values and
the stored checksum. **Check VPC against FA…** reads a matching FA or the
explicitly selected FAList entry. The result reports an unchecked, matching or
mismatching checksum; mismatch is visibly distinct and reloading clears the
previous verification state. Conflicting supplied VIN/series is rejected.

A checksum match proves only consistency of those checksum inputs. It does
not authenticate an FP, prove the FA→FP transformation, validate every FA/FP
relationship, establish vehicle compatibility, or authorize coding.

## Corrected native resource lookup

The actual supplied BRREF schema stores series as text:

```xml
<brRef xmlns="http://bmw.com/2005/psdz.data.brref">
  <mainSeries name="F020" fa2fpId="00000001">
    <series>F030</series>
    <series fa2fpId="00000002">F031</series>
  </mainSeries>
</brRef>
```

These are synthetic illustrative IDs. The per-series ID overrides the parent;
the traced legacy parser treats an empty override as absent and accepts shorter
hexadecimal IDs, normalized to eight digits. Missing, malformed or ambiguous
mappings are rejected.

Actual current files use
`swe/fafp/fafp_<eight-hex-id>.fap.<major>_<sub>_<patch>`. They do not use the
hyphenated SGBMID display name as a physical filename. The resource tool lists
matching versions and identifies the highest current candidate. Legacy
`mainseries/<mainSeries>/mapping` files are discovery information, not proof of
current PDX retrieval support. Discovered files remain unauthenticated.

## Remaining full-generation gates

The original full calculation performs all of these stages:

1. Resolve the correct mapping and complete SGBMID for the FA series.
2. Verify/decrypt the real FAFP document through the legitimate trust path.
3. Compare its internal process, identifier and every version component with
   the selected SGBMID.
4. Evaluate FA-element and time-criterion mapping rules into an FP.
5. Calculate the canonical VPC.
6. Verify the complete FP against the FA and mapping rules.

Native resource discovery and stage 5 are now implemented. Stages 2–4 and 6
are not completed. They cannot be replaced with an unsigned/synthetic mapping,
a `verified=True` switch or a checksum-only success. The complete native
generation endpoint remains unavailable pending that work and genuine
comparison inputs. TAL planning/processing and vehicle/security workflows are
separate remaining native implementations.

Evidence came from the supplied public schemas and previously captured static
method bytecode: `StandardFP.processCategory2CriteriaMap`,
`LogicImpl.representFpAsSortedByteArray`, the AUTOSAR wrapper,
`SeriesMapping.parseSeriesElement`, `SgbmIDs.buildFileName`, and the normal
`Fa2FpParserImpl → SadBCI.decryptVerifyXML` chain. Detailed current-instance
notes are in `/workspace/analysis/native-fp-algorithm-evidence.md` and
`native-fp-resource-contract.md`.
