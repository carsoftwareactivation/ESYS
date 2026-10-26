# Native FAFP trust and decryption requirements

This report traces the supplied installation's actual security implementation.
It is not an implemented verifier, proof of a valid BMW entitlement, or evidence
that a native FA-to-FP calculation completed. Analysis used Python ZIP/class-file
readers and static method evidence; no Java or external BMW service was run.

## Observed implementation path

The original FAFP parser calls the PSdZ security facade before interpreting
mapping data. The configured service is:

`Fa2FpParserImpl → SadBF → XMLSecurity → XMLCrypto/XMLLogic`.

`XMLLogic` first checks an initialized `LicenseValidator`. In the cryptographic
provider it uses that validator to obtain the appropriate coding-signing
certificate and any authorized recipient/decryption key. A native signature
check alone does not recreate that provider's trust/decryption behavior.

The original implementation is not simply a call to a generic XMLDSIG verifier:

- It handles original `isEncrypted`, `isNormalized` and `isCompressed` flags.
- Its unnormalized path preprocesses whitespace and performs Canonical XML 1.0
  without comments before further processing.
- It removes the single signature element from the document to form digest
  input, compares the stored digest, then verifies the signed `SignedInfo`.
- It derives a signing-certificate fingerprint from the original
  `SignedInfo/@Id` convention `SHA1-<fingerprint>-SHA1` and resolves that
  fingerprint through `getCodingSignCert`.
- Static algorithm mappings include the original RSA/DSA SHA-1 and SHA-1/MD5
  digest URI profiles. This identifies legacy behavior; it is not permission to
  replace a failed verification with a weaker algorithm or skip it.
- Encrypted content is a Base64-encoded PKCS#7 `EnvelopedData` structure. It
  matches a recipient's issuer/serial to the legitimate provider's recipient
  identity, obtains the corresponding decryption capability, and optionally
  GZIP-decompresses the plaintext before signature validation.

Without actual supported document vectors, a new generic XMLDSIG or CMS library
passing its own generated fixtures would not establish compatibility with this
complete format. No generic replacement has been wired into production FAFP
generation as a substitute.

## Provider policy is distinct from vehicle/backend authorization

The observed `LicenseValidator.isLicenseValid()` check is part of this
particular supplied PSdZ provider implementation. It must not be represented as
proof that every independent native FP operation universally requires an
E-Sys license or online BMW session.

`ServiceFactory` selects a provider mode from actual security resources:

| Observed mode | Resource detection in the supplied implementation |
| --- | --- |
| `CRYPTO` | Both the entitlement/certificate/key-reference set and the translation-key set below are present |
| `TRANS_KEYS_ONLY` | Translation-key set is present and the entitlement/certificate/key-reference set is absent |
| `UNDEFINED` | Neither supported combination is detected |

The original plain validator's `isLicenseValid()` returns `true`, while its
`getCodingSignCert()` rejects the call as invalid. Thus the name of the method
alone does not describe universal authorization or establish usable signer
trust. Native implementation must determine the legitimate required behavior
for the actual data/provider profile instead of inventing an entitlement check
or bypassing a genuine one.

FAP authenticity/decryption, vehicle diagnostic authorization, backend session
authorization, secure coding and security-token authorization are separate
requirements. Success in one does not authorize the others.

## Concrete local resources referenced

The supplied security provider's filesystem detection refers to these names:

| Resource group | Names |
| --- | --- |
| Entitlement/certificate/key-reference detection | `sec_security.lic`, `sec_certificates.pem`, `sec_keyreference.xml` |
| Translation-key detection | `sec_auth_l3.xml`, `sec_auth_l4.xml`, `sec_transkeys.xml` |

Their names and detection rules were inspected. Their private/key/entitlement
contents were not extracted or printed. These data files were not included in
the uploaded E-Sys installation. Where required for an authorized operation,
they belong in appropriate local secure configuration; their values must not
be embedded in source, setup scripts, logs or chat.

The archive does contain `config/security/esys_truststore.jks`. Its presence is
not evidence that it supplies the FAFP coding-sign trust anchors, entitled
recipient keys or license policy above. The application must not silently use
the general TLS trust store as a substitute FAFP authority.

No real FAFP document, its legitimate signer/trust chain, supported encryption
recipient configuration, or matched FA/expected-FP verification vector has been
provided to establish native trust compatibility. This is distinct from the
user selecting PSdZDATA manually: the selector already works, and choosing a
folder does not create missing algorithms, trust configuration or evidence.

## Conditions before enabling authenticated native generation

1. Support the actual FAFP serialization/canonicalization and signed-byte
   conventions with genuine positive and deliberately altered negative vectors.
2. Resolve signer trust through documented legitimate public trust inputs;
   do not trust an arbitrary certificate merely because it is embedded in XML.
3. Verify all required digest/signature bindings, rejecting duplicate/wrapped
   signatures, conflicting IDs, external resources and signature substitution.
4. Support the actual authorized encrypted-recipient path when the document
   requires it. Unsupported encryption or entitlement must produce a real
   error, not an unsigned/decrypted-looking fallback.
5. Preserve applicable provider/entitlement requirements without confusing them
   with universal vehicle/backend authorization.
6. After trust/decryption, compare the complete internal FAFP SGBMID with the
   selected resource identity, evaluate mappings, compute VPC and independently
   validate the generated FP against the FA.

A caller-supplied `verified=True`, checksum match, synthetic signature fixture,
or readable data directory cannot replace these conditions.

## Evidence

Supplied `psdz-core.jar` public/static class evidence:

- `psdz/registry/security.properties`
- `security.impl.ServiceFactory`, `security.impl.g`
- `security.impl.c` provider-resource detection methods
- `security.impl.XMLCrypto`, `XMLPlain`, `XMLLogic`
- `security.impl.LicenseValidator` and the plain-provider policy methods
- `security.utils.BasicUtils.doCN14XMLomitComments`
- `security.utils.BasicCrypto`, `api.SecurityLibraryInitiator`

Current-instance decoded method evidence is retained outside the source tree in
`/workspace/analysis/native-fp-static`, including
`security-provider-selection-methods.txt` and
`plain-provider-policy-methods.txt`. Those evidence files contain no extracted
private key or credential values.
