"""Native Python readers for saved E-Sys documents and I-Step values.

These readers check the supported document structure and field syntax. They do
not calculate a vehicle profile, resolve software logistics, validate BMW
authorization, or process a TAL. No JVM or vendor executable is used.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET


MAX_XML_BYTES = 8 * 1024 * 1024
MAX_XML_DEPTH = 64
MAX_XML_ELEMENTS = 100_000
FA_NS = "http://bmw.com/2005/psdz.data.fa"
SVT_NS = "http://bmw.com/2005/psdz.data.svt"
TAL_NS = "http://bmw.com/2005/psdz.data.tal"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
VALIDATION_SCOPE = "supported document structure and field syntax"


class DocumentError(ValueError):
    """A document cannot be represented faithfully by the supported reader."""


def _q(namespace: str, name: str) -> str:
    return "{" + namespace + "}" + name if namespace else name


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_document(xml: str) -> ET.Element:
    """Parse a bounded XML document without external content or DTDs."""
    if not isinstance(xml, str):
        raise DocumentError("XML input must be text.")
    try:
        size = len(xml.encode("utf-8"))
    except UnicodeError as error:
        raise DocumentError("XML input contains invalid Unicode.") from error
    if size > MAX_XML_BYTES:
        raise DocumentError("XML document exceeds the 8 MiB limit.")
    if "\x00" in xml:
        raise DocumentError("XML input contains a null character.")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", xml, re.IGNORECASE):
        raise DocumentError("DTD and entity declarations are not supported.")
    parser = ET.XMLPullParser(events=("start", "end"))
    depth = 0
    count = 0
    root = None
    try:
        for position in range(0, len(xml), 65536):
            parser.feed(xml[position:position + 65536])
            for event, element in parser.read_events():
                if event == "start":
                    depth += 1
                    count += 1
                    if depth > MAX_XML_DEPTH:
                        raise DocumentError("XML nesting exceeds the supported depth.")
                    if count > MAX_XML_ELEMENTS:
                        raise DocumentError("XML contains too many elements.")
                    if root is None:
                        root = element
                    if element.tag.startswith("{http://www.w3.org/2001/XInclude}"):
                        raise DocumentError("XML includes are not supported.")
                    for attribute in ("schemaLocation", "noNamespaceSchemaLocation"):
                        if _q(XSI_NS, attribute) in element.attrib:
                            raise DocumentError("External schema references are not supported.")
                    reference = element.get("refSchemaFile")
                    if reference is not None and reference != "tal.xsd":
                        raise DocumentError("Only the TAL schema name tal.xsd is supported.")
                else:
                    depth -= 1
        parser.close()
    except ET.ParseError as error:
        raise DocumentError(f"Malformed XML: {error}") from error
    if root is None:
        raise DocumentError("XML document is empty.")
    return root


def _root(xml: str, namespace: str, name: str) -> ET.Element:
    root = parse_document(xml)
    if root.tag != _q(namespace, name):
        raise DocumentError(f"Expected a {name} document in the supported BMW namespace.")
    return root


def _one(element: ET.Element, namespace: str, name: str, *, required: bool = True) -> ET.Element | None:
    items = element.findall(_q(namespace, name))
    if len(items) > 1:
        raise DocumentError(f"Duplicate {name} element.")
    if not items:
        if required:
            raise DocumentError(f"Required {name} element is missing.")
        return None
    return items[0]


def _allowed(element: ET.Element, tags: set[str]) -> None:
    for child in element:
        if child.tag not in tags:
            raise DocumentError(f"Unsupported {_local(element.tag)} child: {_local(child.tag)}.")


def _attribute(element: ET.Element, name: str, pattern: str | None = None) -> str:
    value = element.get(name)
    if value is None or value == "":
        raise DocumentError(f"Required {name} attribute is missing or empty.")
    if pattern and re.fullmatch(pattern, value) is None:
        raise DocumentError(f"Invalid {name} field syntax.")
    return value


def _integer(value: str, name: str, minimum: int, maximum: int) -> int:
    if re.fullmatch(r"[0-9]+", value) is None:
        raise DocumentError(f"{name} must be an unsigned decimal integer.")
    number = int(value)
    if not minimum <= number <= maximum:
        raise DocumentError(f"{name} is outside the supported range.")
    return number


def _text(element: ET.Element, namespace: str, name: str) -> str:
    child = _one(element, namespace, name)
    if len(child):
        raise DocumentError(f"{name} must contain a scalar value.")
    return (child.text or "").strip()


def _metadata() -> dict:
    return {"structurallyValid": True, "validationScope": VALIDATION_SCOPE,
            "vehicleCompatibilityVerified": False}


def _vin(header: ET.Element, *, minimum: int = 17) -> str | None:
    value = header.get("vinLong")
    if value is not None and re.fullmatch(r"[A-Z0-9]{" + str(minimum) + r",17}", value) is None:
        raise DocumentError("Invalid VIN field syntax.")
    return value


def _codes(standard: ET.Element, container: str, item_name: str, length: int) -> list[str]:
    group = _one(standard, FA_NS, container)
    _allowed(group, {_q(FA_NS, item_name)})
    values = []
    for item in group:
        value = (item.text or "").strip()
        if len(item) or re.fullmatch(r"[A-Z0-9]{" + str(length) + "}", value) is None:
            raise DocumentError(f"Invalid {item_name} field syntax.")
        if value in values:
            raise DocumentError(f"Duplicate {item_name}: {value}.")
        values.append(value)
    return values


def inspect_fa(xml: str, entry_index: int | None = None) -> dict:
    root = parse_document(xml)
    entry_count, entry_name, chosen = 1, None, 0
    if root.tag == "faList":
        _allowed(root, {"id"})
        entries = root.findall("id")
        entry_count = len(entries)
        if not entry_count:
            raise DocumentError("FAList contains no vehicle orders.")
        if entry_count > 1 and entry_index is None:
            raise DocumentError("Multiple FAList entries require an explicit entry index.")
        chosen = 0 if entry_index is None else entry_index
        if isinstance(chosen, bool) or not isinstance(chosen, int) or not 0 <= chosen < entry_count:
            raise DocumentError("FAList entry index is outside the list.")
        for entry in entries:
            _allowed(entry, {"comment", "obdCvnSaLaPa", _q(FA_NS, "fa")})
            _one(entry, "", "comment")
            _one(entry, FA_NS, "fa")
        entry = entries[chosen]
        entry_name = entry.get("name", "0001")
        order = _one(entry, FA_NS, "fa")
        source_format = "E-Sys FAList"
    elif root.tag == _q(FA_NS, "fa"):
        if entry_index is not None and (isinstance(entry_index, bool) or
                                         not isinstance(entry_index, int) or entry_index < 0):
            raise DocumentError("FAList entry index must be a nonnegative integer.")
        # The viewer's FAList selector does not select entries in a standalone
        # FA. Keeping a previous list selection must not prevent opening it.
        order = root
        source_format = "PSdZ FA"
    else:
        raise DocumentError("Expected a PSdZ FA or unqualified E-Sys FAList document.")
    _allowed(order, {_q(FA_NS, "header"), _q(FA_NS, "standardFA")})
    header = _one(order, FA_NS, "header")
    _allowed(header, set())
    standard = _one(order, FA_NS, "standardFA")
    _allowed(standard, {_q(FA_NS, name) for name in ("eCodes", "saCodes", "hoCodes")})
    version = _integer(_attribute(standard, "faVersion"), "FA version", 0, 255)
    result = {
        "version": version,
        "series": _attribute(standard, "series", r"[A-Z0-9_]+"),
        "type": _attribute(standard, "typeKey", r"[A-Z0-9]{4}"),
        "timeCriterion": _attribute(standard, "timeCriteria", r"[0-9]{4}"),
        "vin": _vin(header),
        "paint": _attribute(standard, "colourCode", r"[A-Z0-9]{4}"),
        "upholstery": _attribute(standard, "fabricCode", r"[A-Z0-9]{4}"),
        "eWords": _codes(standard, "eCodes", "eCode", 4),
        "hoWords": _codes(standard, "hoCodes", "hoCode", 4),
        "salapa": _codes(standard, "saCodes", "saCode", 3),
        "format": source_format, "entryCount": entry_count, "entryIndex": chosen,
        "entryName": entry_name,
        "warnings": [] if version in (3, 4) else ["FA version is outside the analyzed versions 3 and 4."],
    }
    return {**result, **_metadata()}


def _sgbm(element: ET.Element, namespace: str) -> dict:
    process = _text(element, namespace, "processClass")
    identifier = _text(element, namespace, "id")
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", process) is None:
        raise DocumentError("Invalid software process class.")
    if re.fullmatch(r"[A-F0-9]{8}", identifier) is None:
        raise DocumentError("Invalid software identifier; expected eight hexadecimal digits.")
    parts = []
    for name in ("mainVersion", "subVersion", "patchVersion"):
        value = _text(element, namespace, name)
        if re.fullmatch(r"[0-9]{1,3}", value) is None:
            raise DocumentError(f"Invalid software {name}.")
        parts.append(int(value))
    version = "_".join(f"{part:03d}" for part in parts)
    return {"name": f"{process.lower()}_{identifier}-{version}", "processClass": process,
            "id": identifier, "version": version}


def _address(value: str, *, hexadecimal: bool = False) -> tuple[int, str]:
    pattern = r"[A-Fa-f0-9]+" if hexadecimal else r"[0-9]+"
    if re.fullmatch(pattern, value) is None:
        raise DocumentError("Invalid diagnostic address syntax.")
    number = int(value, 16 if hexadecimal else 10)
    if not (0 <= number <= 255 or 65536 <= number <= 16777215):
        raise DocumentError("Diagnostic address is outside the supported document range.")
    return number, f"{number:02X}"


def inspect_svt(xml: str) -> dict:
    root = _root(xml, SVT_NS, "svt")
    _allowed(root, {_q(SVT_NS, name) for name in ("header", "standardSVT")})
    header = _one(root, SVT_NS, "header")
    standard = _one(root, SVT_NS, "standardSVT")
    _allowed(header, set())
    _allowed(standard, {_q(SVT_NS, name) for name in ("ecu", "identifierHO")})
    version = _integer(_attribute(standard, "svtVersion"), "SVT version", 0, 255)
    ecus = []
    identities = set()
    for item in standard.findall(_q(SVT_NS, "ecu")):
        _allowed(item, {_q(SVT_NS, name) for name in (
            "diagnosticAddresses", "ecuDetailInfo", "standardSVK", "smartActuatorMasterSVK",
            "ecuStatusInfo", "pdxInfos", "ecuComparisonInfo", "ecuBusConnectionInfos",
            "ecuDiagBusConnectionInfo", "gatewayDiagnosticAddress")})
        address_group = _one(item, SVT_NS, "diagnosticAddresses")
        _allowed(address_group, {_q(SVT_NS, "diagnosticAddress")})
        addresses = []
        for address in address_group.findall(_q(SVT_NS, "diagnosticAddress")):
            number, canonical = _address(_attribute(address, "physicalOffset"))
            if address.get("physicalOffsetAsHex") is not None:
                hexadecimal, _ = _address(address.get("physicalOffsetAsHex"), hexadecimal=True)
                if hexadecimal != number:
                    raise DocumentError("Decimal and hexadecimal diagnostic addresses disagree.")
            if canonical in addresses:
                raise DocumentError("Duplicate diagnostic address within an ECU.")
            addresses.append(canonical)
        if not addresses:
            raise DocumentError("An ECU must contain a diagnostic address.")
        base = item.get("baseVariant", "")
        identity = (base, tuple(addresses))
        if identity in identities:
            raise DocumentError("Duplicate ECU identity in the SVT.")
        identities.add(identity)
        svk = _one(item, SVT_NS, "standardSVK")
        _allowed(svk, {_q(SVT_NS, name) for name in ("partIdentification", "fingerprint")})
        software = [_sgbm(part, SVT_NS) for part in svk.findall(_q(SVT_NS, "partIdentification"))]
        if len({part["name"] for part in software}) != len(software):
            raise DocumentError("Duplicate software identifier in an ECU SVK.")
        master = _one(item, SVT_NS, "smartActuatorMasterSVK", required=False)
        smart_software = [] if master is None else [_sgbm(part, SVT_NS) for part in master.findall(_q(SVT_NS, "partIdentification"))]
        connection = _one(item, SVT_NS, "ecuDiagBusConnectionInfo", required=False)
        bus = None if connection is None else connection.get("busType") or connection.get("busID")
        ecus.append({"baseVariant": base, "diagnosticAddress": addresses[0], "diagnosticAddresses": addresses,
                     "variant": item.get("ecuVariant"), "bus": bus, "sgbm": software,
                     "smartActuatorSgbm": smart_software})
    return {"version": version, "vin": _vin(header, minimum=7), "ecus": ecus,
            "svtTypeInfo": header.get("svtTypeInfo"), **_metadata()}


_TAL_CATEGORIES = frozenset(("idBackup", "idRestore", "hwDeinstall", "hwInstall", "blFlash",
                             "IBADeploy", "HDDUpdate", "sfaDeploy", "swDeploy", "gatewayTableDeploy",
                             "cdDeploy", "fscBackup", "fscDeploy", "ecuActivate", "ecuPoll",
                             "ecuMirrorDeploy", "smacTransferStart", "smacTransferStatus"))
_TAL_ACTIONS = {
    "idBackup": {"idBackupTA", "idBackupLightTA"},
    "idRestore": {"idRestoreTA", "idRestoreLightTA"},
    "sfaDeploy": {"sfaWriteTA", "sfaDeleteTA"},
    "swDeploy": {"swDeleteTA", "swDeployTA", "smacSwDeployOnMasterTA"},
    "ecuMirrorDeploy": {"ecuMirrorDeployTA", "smacEcuMirrorDeployOnMasterTA"},
}
_LINE_STATUSES = frozenset(("ANY", "Executable", "NotExecutable", "Inactive", "Running", "Finished",
                           "FinishedWithWarnings", "FinishedWithError", "AbortedByUser", "AbortedByError",
                           "Processing", "Processed", "ProcessedWithError", "ProcessedWithIgnoredError",
                           "Repeat", "notRequired"))
_TAL_STATUSES = frozenset(("Executable", "Inactive", "Running", "Finished",
                          "FinishedForHWTransactionsWithWarnings", "FinishedForHWTransactionsWithError",
                          "FinishedForHWTransactions", "FinishedWithError", "FinishedWithWarnings",
                          "AbortedByError", "AbortedByUser", "ANY", "FinishedWithErrorInTransaction",
                          "FinishedWithErrorInDependencies", "FinishedForHWTransactions_BackupOK",
                          "FinishedForHWTransactions_BackupError", "FinishedWithErrorInPreparation",
                          "FinishedWithErrorInFinalization", "FinishedWithErrorInPowerSupply"))


def inspect_tal(xml: str) -> dict:
    root = _root(xml, TAL_NS, "tal")
    _allowed(root, {_q(TAL_NS, name) for name in (
        "ExecProperties", "generationContext", "executionContext", "talLine", "TechnicalTALExecutionAction",
        "TaskDependencies", "Topologies", "EthernetTopologies", "Throwable", "WarnEvent", "MCDDiagServiceEvent",
        "executionTime", "installedECUList_Ist", "installedECUList_Soll", "TalGenerationReport")})
    schema = _attribute(root, "schemaVersion")
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+){2}", schema) is None:
        raise DocumentError("Unsupported TAL schema version syntax.")
    if root.get("status") is not None and root.get("status") not in _TAL_STATUSES:
        raise DocumentError("Unsupported stored TAL status.")
    lines = []
    identifiers = set()
    for item in root.findall(_q(TAL_NS, "talLine")):
        _allowed(item, {_q(TAL_NS, name) for name in _TAL_CATEGORIES | {
            "prerequisite", "postBLUpdateFlashRoutineInfo", "preBLUpdateFlashRoutineInfo", "flashPreReqs",
            "codingPreReqs", "preparation", "authentication", "finalization", "Throwable", "WarnEvent",
            "MCDDiagServiceEvent", "executionTime"}})
        identifier = _attribute(item, "id")
        if identifier in identifiers:
            raise DocumentError("Duplicate TAL line identifier.")
        identifiers.add(identifier)
        stored_status = _attribute(item, "status")
        if stored_status not in _LINE_STATUSES:
            raise DocumentError("Unsupported stored TAL line status.")
        _, address = _address(_attribute(item, "diagAddress"), hexadecimal=True)
        categories = [child for child in item if _local(child.tag) in _TAL_CATEGORIES and child.tag == _q(TAL_NS, _local(child.tag))]
        if len(categories) != 1:
            raise DocumentError("A supported TAL line must contain exactly one transaction category.")
        category = categories[0]
        category_name = _local(category.tag)
        if _attribute(category, "status") not in _LINE_STATUSES:
            raise DocumentError("Unsupported stored TAL category status.")
        action_names = _TAL_ACTIONS.get(category_name, {category_name + "TA"})
        _allowed(category, {_q(TAL_NS, name) for name in action_names | {"executionTime", "aifContents", "expectedSGBMIDs"}})
        actions = []
        for action in category:
            name = _local(action.tag)
            if name not in action_names:
                continue
            if action.get("status") is not None and action.get("status") not in _LINE_STATUSES:
                raise DocumentError("Unsupported stored TAL action status.")
            software = _one(action, TAL_NS, "sgbmid", required=False)
            actions.append({"category": name, "sgbm": None if software is None else _sgbm(software, TAL_NS)["name"],
                            "status": action.get("status")})
        numeric_id = int(identifier[3:]) if re.fullmatch(r"tl_[0-9]+", identifier) else identifier
        lines.append({"id": numeric_id, "documentId": identifier,
                      "ecu": _attribute(item, "baseVariant"), "diagnosticAddress": address,
                      "category": category_name, "status": stored_status, "actions": actions})
    uninspected = sorted({_local(item.tag) for item in root if _local(item.tag) not in
                          {"talLine", "ExecProperties", "executionTime", "installedECUList_Ist", "installedECUList_Soll"}})
    return {"id": None, "schemaVersion": schema, "status": root.get("status"), "lines": lines,
            "executionPerformed": False, "uninspectedSections": uninspected, **_metadata()}


_ISTEP = re.compile(r"([A-Z0-9]{4})[-_]([0-9]{2})[-_](0[1-9]|1[0-2])[-_]([0-9]{3})")


def parse_istep(value: str) -> dict:
    """Parse the documented value format; this does not check vehicle support."""
    match = _ISTEP.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ValueError("Invalid I-Step identifier; expected a value such as F020-24-07-500.")
    series, year, month, number = match.groups()
    canonical = f"{series}-{year}-{month}-{number}"
    return {"canonical": canonical, "mainSeries": series, "year": int(year), "month": int(month), "number": int(number)}


def compare_isteps(left: str, right: str) -> dict:
    """Match the traced value comparator, including its main-series ordering."""
    first, second = parse_istep(left)["canonical"], parse_istep(right)["canonical"]
    return {"left": first, "right": second, "comparison": (first > second) - (first < second)}
