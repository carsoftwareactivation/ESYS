"""Native FAFP mapping algorithms with an explicit, non-bypassable trust boundary.

The parser and evaluator in this module operate on UNTRUSTED cleartext for
algorithm inspection/tests. They do not replace the original mapping signature,
decryption, licensing or provider-trust policy. No result is vehicle-usable or
production-validated. There is deliberately no ``verified=True`` parameter.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, time
import re
import xml.etree.ElementTree as ET

from .models import DocumentError, inspect_fa, parse_document


FAP_NS = "http://bmw.com/2005/psdz.data.fa2fp"
DS_NS = "http://www.w3.org/2000/09/xmldsig#"
SELECTORS = frozenset("TAZLPEHKW")


class FapError(DocumentError):
    pass


class FapAuthenticationRequired(FapError):
    pass


@dataclass(frozen=True)
class FapIdentity:
    identifier: str
    version: tuple[int, int, int]
    main_series: str

    @property
    def sgbmid(self) -> str:
        return "fafp_" + self.identifier.lower() + "-" + "_".join(f"{part:03d}" for part in self.version)


@dataclass(frozen=True)
class FpElement:
    category: int
    criterion: int
    category_name: str = ""
    category_name_en: str = ""
    criterion_name: str = ""
    criterion_name_en: str = ""


@dataclass(frozen=True)
class MappingRule:
    selector: str
    code: str
    elements: tuple[FpElement, ...]
    lower: int | None = None
    upper: int | None = None
    description: str | None = None


@dataclass(frozen=True)
class UntrustedFap:
    identity: FapIdentity
    rules: tuple[MappingRule, ...]
    signature_present: bool
    created_by: str

    @property
    def authenticated(self) -> bool:
        return False


@dataclass(frozen=True)
class MappingEvaluation:
    """An untrusted algorithm result, never a production FP or permission."""

    categories: tuple[tuple[int, tuple[int, ...]], ...]
    missing_mappings: tuple[tuple[str, str], ...]
    matched_rule_count: int

    def as_dict(self) -> dict:
        return {"categories": [{"id": key, "criteria": list(values)} for key, values in self.categories],
                "missingMappings": [{"selector": kind, "code": code} for kind, code in self.missing_mappings],
                "matchedRuleCount": self.matched_rule_count,
                "mappingCoverageComplete": not self.missing_mappings,
                "authenticated": False, "productionValidated": False,
                "faToFpCalculationPerformed": False, "vehicleCompatibilityVerified": False,
                "scope": "untrusted mapping algorithm evaluation only"}


def _q(name: str) -> str:
    return "{" + FAP_NS + "}" + name


def _one(parent: ET.Element, name: str) -> ET.Element:
    children = parent.findall(_q(name))
    if len(children) != 1:
        raise FapError(f"FAFP requires exactly one {name} element.")
    return children[0]


def _allowed(parent: ET.Element, names: set[str], *, signature: bool = False) -> None:
    tags = {_q(name) for name in names}
    if signature:
        tags.add("{" + DS_NS + "}Signature")
    if any(child.tag not in tags for child in parent):
        raise FapError("FAFP contains an unsupported child or namespace.")


def _scalar(parent: ET.Element, name: str) -> str:
    child = _one(parent, name)
    if len(child):
        raise FapError(f"FAFP {name} must contain a scalar value.")
    return (child.text or "").strip()


def _integer(value: str | None, label: str, maximum: int) -> int:
    if value is None or re.fullmatch(r"[0-9]+", value) is None:
        raise FapError(f"FAFP {label} must be an unsigned decimal integer.")
    number = int(value)
    if not 0 <= number <= maximum:
        raise FapError(f"FAFP {label} is outside its supported range.")
    return number


def _bound(value: str | None) -> int | None:
    if value in (None, "", "-1"):
        return None
    if re.fullmatch(r"[0-9]{1,4}", value) is None:
        raise FapError("FAFP time bounds must be numeric MMYY values or the unbounded -1 sentinel.")
    return int(value)


def _time_key(value: int) -> tuple[int, int]:
    # The original value model validates four digits, not calendar months.
    # Its utility compares year (remainder) first, then month (quotient).
    return value % 100, value // 100


def parse_untrusted_fap(xml: str, expected_sgbmid: str | None = None) -> UntrustedFap:
    """Parse cleartext mapping metadata/rules WITHOUT authenticating it.

    Encrypted content is rejected. A present Signature element is recorded,
    never considered proof. The expected complete SGBMID check is an identity
    check, not trust verification, and includes all three version components.
    """
    root = parse_document(xml)
    if root.tag != _q("fa2fp"):
        raise FapError("Expected the supported FAFP document namespace.")
    if root.get("isEncrypted") in ("true", "1"):
        raise FapAuthenticationRequired("FAFP decryption and legitimate trust verification are required.")
    if root.get("isEncrypted") not in ("false", "0"):
        raise FapError("FAFP must declare its isEncrypted boolean.")
    _allowed(root, {"sweHeader", "data"})
    header, data = _one(root, "sweHeader"), _one(root, "data")
    _allowed(header, {"sweIdent"}, signature=True)
    signatures = header.findall("{" + DS_NS + "}Signature")
    if len(signatures) > 1:
        raise FapError("FAFP contains multiple signature elements.")
    main_series = header.get("mainSeries", "")
    if re.fullmatch(r"[A-Z0-9]{4}", main_series) is None:
        raise FapError("FAFP main series must contain four uppercase alphanumeric characters.")
    try:
        date.fromisoformat(header.get("date", ""))
        time.fromisoformat(header.get("time", "").replace("Z", "+00:00"))
    except ValueError as error:
        raise FapError("FAFP creation date/time is missing or invalid.") from error
    if "createdBy" not in header.attrib:
        raise FapError("FAFP createdBy metadata is missing.")
    identification = _one(header, "sweIdent")
    _allowed(identification, {"processClass", "id", "mainVersion", "subVersion", "patchVersion"})
    if _scalar(identification, "processClass") != "FAFP":
        raise FapError("The mapping process class must be FAFP.")
    identifier = _scalar(identification, "id")
    if re.fullmatch(r"[A-Fa-f0-9]{1,8}", identifier) is None:
        raise FapError("FAFP identifier must be hexadecimal and fit in 32 bits.")
    version = tuple(_integer(_scalar(identification, part), part, 999)
                    for part in ("mainVersion", "subVersion", "patchVersion"))
    identity = FapIdentity(identifier.upper().zfill(8), version, main_series)
    if expected_sgbmid is not None:
        if not isinstance(expected_sgbmid, str) or expected_sgbmid.lower() != identity.sgbmid:
            raise FapError("The FAFP document's complete SGBMID does not match the selected resource.")
    _allowed(data, {"fa2fpMappings"})
    mappings = _one(data, "fa2fpMappings")
    _allowed(mappings, {"fa2fpMapping"})
    rules = []
    for entry in mappings:
        _allowed(entry, {"faElement", "fpElement"})
        source = _one(entry, "faElement")
        _allowed(source, set())
        selector, code = source.get("selector"), source.get("code")
        if selector not in SELECTORS or code is None:
            raise FapError("FAFP selector/code is missing or unsupported.")
        elements = []
        for target in entry.findall(_q("fpElement")):
            names = {"criteriaName", "criteriaNameEN", "categoryName", "categoryNameEN"}
            _allowed(target, names)
            labels = {}
            for name in names:
                nodes = target.findall(_q(name))
                if len(nodes) > 1 or any(len(node) for node in nodes):
                    raise FapError("FAFP labels must be unambiguous scalar values.")
                labels[name] = "" if not nodes else (nodes[0].text or "")
            elements.append(FpElement(
                _integer(target.get("categoryVal"), "category value", 255),
                _integer(target.get("criteriaVal"), "criterion value", 65535),
                labels["categoryName"], labels["categoryNameEN"],
                labels["criteriaName"], labels["criteriaNameEN"]))
        if not elements:
            raise FapError("An FAFP mapping must contain at least one FP element.")
        rules.append(MappingRule(selector, code, tuple(elements), _bound(entry.get("from")),
                                 _bound(entry.get("to")), source.get("description")))
    if not rules:
        raise FapError("FAFP contains no mappings.")
    return UntrustedFap(identity, tuple(rules), bool(signatures), header.get("createdBy"))


def lookup_elements(mapping: UntrustedFap, selector: str, code: str,
                    time_criterion: str) -> tuple[FpElement, ...]:
    """Exact selector/code lookup: from inclusive, to exclusive, YY/MM order."""
    if not isinstance(mapping, UntrustedFap):
        raise TypeError("Expected an untrusted FAFP analysis object.")
    if selector not in SELECTORS or not isinstance(code, str):
        raise FapError("Unsupported FA selector/code.")
    if not isinstance(time_criterion, str) or re.fullmatch(r"[0-9]{4}", time_criterion) is None:
        raise FapError("FA time criterion must contain four decimal digits.")
    instant = _time_key(int(time_criterion))
    return tuple(element for rule in mapping.rules
                 if rule.selector == selector and rule.code == code
                 and (rule.lower is None or _time_key(rule.lower) <= instant)
                 and (rule.upper is None or instant < _time_key(rule.upper))
                 for element in rule.elements)


def evaluate_untrusted_mapping(mapping: UntrustedFap, fa_xml: str,
                               entry_index: int | None = None) -> MappingEvaluation:
    """Reproduce native mapping arithmetic on explicitly untrusted input.

    This developer operation does not return a signed/validated vehicle FP.
    Missing type/time/option mappings are retained as explicit failures;
    optional paint/upholstery absence follows the traced fill routine.
    """
    if not isinstance(mapping, UntrustedFap):
        raise TypeError("Expected an untrusted FAFP analysis object.")
    order = inspect_fa(fa_xml, entry_index)
    requests = [("T", order["type"], True), ("A", order["timeCriterion"], True),
                ("L", order["paint"], False), ("P", order["upholstery"], False)]
    requests += [(selector, code, True) for selector, field in
                 (("H", "eWords"), ("K", "hoWords"), ("W", "salapa")) for code in order[field]]
    categories: dict[int, list[int]] = {}
    missing = []
    match_count = 0
    rules_by_source: dict[tuple[str, str], list[MappingRule]] = {}
    for rule in mapping.rules:
        rules_by_source.setdefault((rule.selector, rule.code), []).append(rule)
    instant = _time_key(int(order["timeCriterion"]))
    for selector, code, required in requests:
        matched = [rule for rule in rules_by_source.get((selector, code), ())
                   if (rule.lower is None or _time_key(rule.lower) <= instant)
                   and (rule.upper is None or instant < _time_key(rule.upper))]
        elements = [element for rule in matched for element in rule.elements]
        if required and not elements:
            missing.append((selector, code))
        for element in elements:
            categories.setdefault(element.category, []).append(element.criterion)
        match_count += len(matched)
    return MappingEvaluation(tuple((key, tuple(values)) for key, values in categories.items()),
                             tuple(missing), match_count)


def verify_untrusted_consistency(mapping: UntrustedFap, fa_xml: str,
                                 categories: Mapping[int, Sequence[int]], fp_series: str,
                                 entry_index: int | None = None) -> dict:
    """Independent traced forward/reverse/type-key checks, without trust.

    This deliberately does not regenerate and compare the profile. The source
    validator uses the first mapping containing each pair, and its forward
    checks use the first mapping with a matching code. Those ordering semantics
    are retained; mapping trust and real-dataset parity are not established.
    """
    if not isinstance(mapping, UntrustedFap):
        raise TypeError("Expected an untrusted FAFP analysis object.")
    order = inspect_fa(fa_xml, entry_index)
    if not isinstance(categories, Mapping):
        raise FapError("FP categories must be a mapping.")
    pairs = []
    for category, criteria in categories.items():
        if type(category) is not int or not 0 <= category <= 255:
            raise FapError("Invalid FP category ID.")
        if not isinstance(criteria, Sequence) or isinstance(criteria, (str, bytes, bytearray)):
            raise FapError("FP criteria must be integer sequences.")
        for criterion in criteria:
            if type(criterion) is not int or not 0 <= criterion <= 65535:
                raise FapError("Invalid FP criterion value.")
            pairs.append((category, criterion))
    pair_set = set(pairs)
    first_by_pair = {}
    first_by_code = {}
    for rule in mapping.rules:
        first_by_code.setdefault(rule.code, rule)
        for element in rule.elements:
            first_by_pair.setdefault((element.category, element.criterion), rule)
    issues = []
    if fp_series != order["series"]:
        issues.append({"code": "series_mismatch", "message": "FA and FP development series differ."})
    possible_type_pairs = set()
    memberships = {"A": [order["timeCriterion"]], "W": order["salapa"],
                   "H": order["eWords"], "K": order["hoWords"]}
    reverse_memberships = {selector: set(codes) for selector, codes in memberships.items()}
    for pair in pairs:
        rule = first_by_pair.get(pair)
        if rule is None:
            issues.append({"code": "unmapped_fp_pair", "category": pair[0], "criterion": pair[1]})
        elif rule.selector == "T":
            possible_type_pairs.add(pair)
        elif rule.selector in reverse_memberships and rule.code not in reverse_memberships[rule.selector]:
            issues.append({"code": "fp_element_absent_from_fa", "selector": rule.selector,
                           "value": rule.code, "category": pair[0], "criterion": pair[1]})
    for selector in ("A", "W", "H", "K"):
        for code in memberships[selector]:
            rule = first_by_code.get(code)
            if rule is None:
                issues.append({"code": "missing_fa_mapping", "selector": selector, "value": code})
            elif not any((element.category, element.criterion) in pair_set for element in rule.elements):
                issues.append({"code": "missing_fp_pair_for_fa", "selector": selector, "value": code})
    possible_types = []
    seen_types = set()
    for rule in mapping.rules:
        if rule.selector == "T" and rule.code not in seen_types and any(
                (element.category, element.criterion) in possible_type_pairs for element in rule.elements):
            possible_types.append(rule.code)
            seen_types.add(rule.code)
    if order["type"] not in possible_types:
        issues.append({"code": "type_key_mismatch", "value": order["type"]})
    return {"algorithmChecksPassed": not issues, "issues": issues,
            "possibleTypeKeys": possible_types, "authenticated": False,
            "productionValidated": False, "vehicleCompatibilityVerified": False,
            "scope": "independent checks over untrusted mapping data only"}


def require_production_mapping(mapping: UntrustedFap) -> None:
    """Reject every untrusted analysis object at the production trust boundary."""
    if not isinstance(mapping, UntrustedFap):
        raise TypeError("Expected an untrusted FAFP analysis object.")
    raise FapAuthenticationRequired(
        "Native FAFP decryption, signature, licensing and provider-trust verification are not integrated; "
        "untrusted mapping arithmetic cannot be used as a production FP calculation.")
