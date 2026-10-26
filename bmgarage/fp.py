"""Native saved-FP inspection, canonical serialization and VPC consistency.

The binary layout is traced from StandardFP.processCategory2CriteriaMap;
LogicImpl.representFpAsSortedByteArray excludes the FP version and appends the
FA's paint/upholstery ASCII bytes before AUTOSAR CRC32/P4. The original wrapper
reserves FFFFFFFF and returns FFFFFFFE for that value.

These operations do not generate FP from FA, verify a mapping's signature,
reverse-check an FP against FA, authorize coding or communicate with a vehicle.
No Java runtime, vendor executable, external process or optional package is used.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
import xml.etree.ElementTree as ET

from .models import DocumentError, inspect_fa, parse_document


FP_NS = "http://bmw.com/2005/psdz.data.fp"
SUPPORTED_FP_VERSIONS = (1, 2, 3)
_REFLECTED_AUTOSAR_POLYNOMIAL = 0xC8DF352F


def _crc_table() -> tuple[int, ...]:
    table = []
    for value in range(256):
        remainder = value
        for _ in range(8):
            remainder = (remainder >> 1) ^ (_REFLECTED_AUTOSAR_POLYNOMIAL if remainder & 1 else 0)
        table.append(remainder)
    return tuple(table)


_AUTOSAR_TABLE = _crc_table()


def crc32_autosar(data: bytes | bytearray | memoryview) -> int:
    """CRC-32/AUTOSAR (P4): polynomial F4ACFB13, init/xorout FFFFFFFF.

    Reflection is enabled for input/output. The standard check value for ASCII
    ``123456789`` is 1697D06A. This function returns the standard CRC, without
    the BMW wrapper's reserved-value substitution.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("CRC input must be bytes.")
    value = 0xFFFFFFFF
    for byte in bytes(data):
        value = (value >> 8) ^ _AUTOSAR_TABLE[(value ^ byte) & 0xFF]
    return value ^ 0xFFFFFFFF


def bmw_crc32_autosar(data: bytes | bytearray | memoryview) -> int:
    """Apply the original wrapper's FFFFFFFF -> FFFFFFFE reservation."""
    value = crc32_autosar(data)
    return 0xFFFFFFFE if value == 0xFFFFFFFF else value


def _unsigned(value: object, label: str, maximum: int) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise DocumentError(f"{label} must be an unsigned integer no greater than {maximum}.")
    return value


def serialize_categories(categories: Mapping[int, Sequence[int]], version: int,
                         include_version: bool = False) -> bytes:
    """Serialize sorted FP category/criterion values using the traced layout.

    Version 1 uses a one-byte criterion count; versions 2/3 use a two-byte
    big-endian count. Categories and criterion values are sorted numerically.
    Repeated criterion values are retained, as in StandardFP's list semantics.
    This encodes values only; it does not prove that the profile matches an FA.
    """
    if type(version) is not int or version not in SUPPORTED_FP_VERSIONS:
        raise DocumentError("Only FP binary versions 1, 2 and 3 are implemented.")
    if type(include_version) is not bool:
        raise TypeError("include_version must be a boolean.")
    if not isinstance(categories, Mapping):
        raise TypeError("FP categories must be a mapping of category IDs to criterion values.")
    if len(categories) > 255:
        raise DocumentError("The FP binary format supports at most 255 categories.")
    checked = []
    maximum_count = 255 if version == 1 else 65535
    for identifier, criteria in categories.items():
        category = _unsigned(identifier, "Category ID", 255)
        if not isinstance(criteria, Sequence) or isinstance(criteria, (str, bytes, bytearray)):
            raise TypeError("FP criterion values must be an integer sequence.")
        if not criteria:
            raise DocumentError("An FP category must contain at least one criterion.")
        if len(criteria) > maximum_count:
            raise DocumentError(f"FP version {version} supports at most {maximum_count} criteria per category.")
        values = [_unsigned(value, "Criterion value", 65535) for value in criteria]
        checked.append((category, sorted(values)))
    output = bytearray([version] if include_version else [])
    output.append(len(checked))
    for identifier, values in sorted(checked):
        output.append(identifier)
        output.extend(len(values).to_bytes(1 if version == 1 else 2, "big"))
        for value in values:
            output.extend(value.to_bytes(2, "big"))
    return bytes(output)


def calculate_vpc(categories: Mapping[int, Sequence[int]], version: int,
                  paint: str, upholstery: str) -> str:
    """Calculate VPC over profile bytes + paint + upholstery, without FP generation."""
    for label, value in (("Paint", paint), ("Upholstery", upholstery)):
        if not isinstance(value, str) or re.fullmatch(r"[A-Z0-9]{4}", value) is None:
            raise DocumentError(f"{label} must be four uppercase alphanumeric characters.")
    payload = serialize_categories(categories, version) + paint.encode("ascii") + upholstery.encode("ascii")
    return bmw_crc32_autosar(payload).to_bytes(4, "big").hex().upper()


def _q(name: str) -> str:
    return "{" + FP_NS + "}" + name


def _one(parent: ET.Element, name: str) -> ET.Element:
    found = parent.findall(_q(name))
    if len(found) != 1:
        raise DocumentError(f"FP requires exactly one {name} element.")
    return found[0]


def _allowed(parent: ET.Element, names: set[str]) -> None:
    if any(child.tag not in {_q(name) for name in names} for child in parent):
        raise DocumentError("FP contains an unsupported element or namespace.")


def _decimal(value: str | None, label: str, maximum: int) -> int:
    if value is None or re.fullmatch(r"[0-9]+", value) is None:
        raise DocumentError(f"FP {label} must be an unsigned decimal integer.")
    return _unsigned(int(value), label, maximum)


def inspect_fp(xml: str, fa_xml: str | None = None, entry_index: int | None = None) -> dict:
    """Inspect a saved FP and optionally compare its VPC using a matching FA.

    A checksum match proves consistency of the represented checksum inputs
    only. It does not establish a correct FA-to-FP transformation, signed FAP
    authenticity, BMW authorization or vehicle compatibility.
    """
    root = parse_document(xml)
    if root.tag != _q("fp"):
        raise DocumentError("Expected a saved FP in the supported BMW FP namespace.")
    _allowed(root, {"header", "standardFP"})
    header, standard = _one(root, "header"), _one(root, "standardFP")
    _allowed(header, set())
    _allowed(standard, {"cat"})
    version = _decimal(standard.get("fpVersion"), "version", 255)
    if version not in SUPPORTED_FP_VERSIONS:
        raise DocumentError("Only FP binary versions 1, 2 and 3 are implemented.")
    vin, series = header.get("vinLong"), header.get("series")
    if vin is not None and re.fullmatch(r"[A-Z0-9]{17}", vin) is None:
        raise DocumentError("Invalid FP VIN field syntax.")
    if series is not None and re.fullmatch(r"[A-Z0-9_]+", series) is None:
        raise DocumentError("Invalid FP series field syntax.")
    stored = header.get("vpc")
    if stored is not None and re.fullmatch(r"[A-Fa-f0-9]{8}", stored) is None:
        raise DocumentError("The stored FP VPC must contain exactly eight hexadecimal digits.")
    stored = stored.upper() if stored is not None else None
    categories = []
    values = {}
    for category in standard:
        _allowed(category, {"crit"})
        identifier = _decimal(category.get("val"), "category ID", 255)
        if identifier in values:
            raise DocumentError("A saved FP contains duplicate category IDs.")
        criteria = []
        for criterion in category:
            _allowed(criterion, set())
            value = _decimal(criterion.get("val"), "criterion value", 65535)
            criteria.append({"value": value, "name": criterion.get("name"),
                             "nameEN": criterion.get("nameEN"), "text": (criterion.text or "").strip()})
        values[identifier] = [criterion["value"] for criterion in criteria]
        categories.append({"id": identifier, "name": category.get("name"),
                           "nameEN": category.get("nameEN"), "criteria": criteria})
    canonical = serialize_categories(values, version)
    calculated, matches = None, None
    status = "not_present" if stored is None else "requires_fa"
    if fa_xml is not None:
        order = inspect_fa(fa_xml, entry_index)
        if vin and order.get("vin") and vin != order["vin"]:
            raise DocumentError("FP and selected FA have different VINs; checksum comparison rejected.")
        if series and order.get("series") and series != order["series"]:
            raise DocumentError("FP and selected FA have different series; checksum comparison rejected.")
        calculated = calculate_vpc(values, version, order["paint"], order["upholstery"])
        if stored is not None:
            matches = stored == calculated
            status = "match" if matches else "mismatch"
    return {
        "version": version, "vin": vin, "series": series, "mainSeries": header.get("mainSeries"),
        "categories": categories, "categoryCount": len(categories),
        "criterionCount": sum(len(category["criteria"]) for category in categories),
        "canonicalByteLength": len(canonical), "storedVpc": stored, "calculatedVpc": calculated,
        "checksumMatches": matches, "checksumStatus": status,
        "checksumScope": "Sorted FP values without version, followed by FA paint and upholstery; not authentication or FA-to-FP validation",
        "structurallyValid": True, "vehicleCompatibilityVerified": False,
        "faToFpCalculationPerformed": False, "faConsistencyVerified": False,
        "warnings": [],
    }
