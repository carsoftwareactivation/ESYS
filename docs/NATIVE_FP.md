# Native FP processing milestone

This milestone adds native saved-profile processing and an explicitly untrusted
FAFP mapping algorithm core. The authenticated full FA→FP path remains
unavailable. All code uses the Python standard library; no Java execution was
used for its implementation or testing.

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

## Untrusted FAFP algorithm core

`bmgarage.fap` provides developer-facing algorithms over cleartext mapping
documents. These functions are not connected to a production generation button
or engine operation:

- `parse_untrusted_fap` reads the supported namespace, complete FAFP identity,
  metadata, rules and category/criterion labels. An expected SGBMID comparison
  includes the process class, ID and all three version components. Encrypted
  documents are rejected. A signature element is recorded as present and is
  never treated as authenticated.
- `lookup_elements` matches selector and code exactly. Time ranges use MMYY
  values compared by year, then month: `from` is inclusive and `to` is exclusive.
  Absent/empty bounds and `-1` mean unbounded. The original value model checks
  numeric shape rather than calendar-month validity; this core does not invent
  a stronger calendar check or normalize selector aliases.
- `evaluate_untrusted_mapping` evaluates type (`T`), time criterion (`A`), paint
  (`L`), upholstery (`P`), E-Words (`H`), HO-Words (`K`) and SALAPA (`W`) in that
  order. All active matching rules contribute, retaining repeated criterion
  occurrences. Missing type, time or option mappings are reported explicitly.
  Paint/upholstery mappings are optional in the traced fill routine. Although
  the schema also allows `Z` and `E`, the traced generator requests `A` and `H`;
  this implementation does not guess alias equivalence.
- `verify_untrusted_consistency` separately checks FA/FP series, reverse FP
  pair membership, forward time/option coverage and possible type keys. It
  preserves the original validator's first matching pair/code ordering and its
  requirement for at least one corresponding pair in forward coverage checks.
  It does not replace these checks with an exact regenerated-profile comparison.

Parsed objects have `authenticated == False`. Evaluation/check results explicitly
report `productionValidated: false` and `vehicleCompatibilityVerified: false`.
`require_production_mapping` rejects every untrusted object, including one with
a signature element. There is no caller-provided `verified=True` escape hatch.
The core does not return a signed or production-validated FP.

`tests/test_fap.py` executes **21 tests**, all passed in this Linux environment.
They cover complete identity matching, encrypted/unsigned rejection at the
production boundary, signature presence without trust, malformed/unsafe XML,
selector order, date boundaries, chronological range comparison, unbounded
sentinels, duplicate criteria, optional paint/upholstery mappings, and independent
forward/reverse/series/type checks. These fixtures are synthetic; no genuine
FAFP file, BMW signer or vehicle-profile result was validated by those tests.

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

Native resource discovery and stage 5 are implemented. Stages 3, 4 and the
traced consistency arithmetic of stage 6 are implemented only over explicitly
untrusted analysis objects. Stage 2 and the authenticated, integrated full
pipeline remain incomplete. An unsigned/synthetic mapping, a `verified=True`
switch or a checksum-only success cannot replace those steps.

Enabling production generation requires the following inputs and verification:

- A genuine selected FAFP resource with its matching BRREF/SGBMID, plus a
  corresponding real FA and independently obtained expected FP. These must
  establish actual dataset behavior, not just agreement with synthetic rules.
- The document's legitimate signer/trust chain and supported recipient
  configuration when encryption is used. The supplied installation does not
  include a genuine FAFP or the selected provider's security resource set.
  [TRUST_REQUIREMENTS.md](TRUST_REQUIREMENTS.md) identifies the exact detected
  filenames and distinguishes provider policy from vehicle/backend authority.
  Private keys, credentials and entitlement contents must remain in secure
  local configuration, never source or chat.
- Native compatibility tests for the original signed-byte/canonicalization and
  decryption conventions, including altered-document rejection, followed by
  complete identity checks, mapping evaluation, VPC calculation and independent
  consistency checks on the authenticated result.

The complete generation endpoint stays unavailable until that evidence and
implementation exist. Manual PSdZDATA selection already works; choosing a
folder does not establish these conditions. TAL planning/processing and
vehicle/security workflows remain separate native implementations.

Evidence came from the supplied public schemas and previously captured static
method bytecode: `StandardFP.processCategory2CriteriaMap`,
`LogicImpl.representFpAsSortedByteArray`, the AUTOSAR wrapper,
`SeriesMapping.parseSeriesElement`, `SgbmIDs.buildFileName`, and the normal
`Fa2FpParserImpl → SadBCI.decryptVerifyXML` chain. Mapping-core evidence also
includes `StandardFP.fillByStandardFA`, `Fa2FpUtilityImpl.getFPElements` and
`ValidateFpBA.verifyFpAgainstFaWithFa2FpObject`. Detailed current-instance
notes are in `/workspace/analysis/native-fp-algorithm-evidence.md` and
`native-fp-resource-contract.md`.
