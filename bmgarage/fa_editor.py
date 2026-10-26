"""Native file-only FA creation/editing; never activates or writes a vehicle."""

from __future__ import annotations

from datetime import datetime, timezone
import xml.etree.ElementTree as ET

from .models import DocumentError, FA_NS, inspect_fa, parse_document


ATTRIBUTES = {"version": "faVersion", "series": "series", "type": "typeKey",
              "timeCriterion": "timeCriteria", "paint": "colourCode", "upholstery": "fabricCode"}
OPTIONS = {"eWords": ("eCodes", "eCode"), "salapa": ("saCodes", "saCode"),
           "hoWords": ("hoCodes", "hoCode")}
FIELDS = frozenset(ATTRIBUTES) | frozenset(OPTIONS) | {"vin"}


def _q(name: str) -> str:
    return "{" + FA_NS + "}" + name


def _validate_changes(changes: dict) -> None:
    if not isinstance(changes, dict):
        raise DocumentError("FA fields must be a dictionary.")
    unknown = set(changes) - FIELDS
    if unknown:
        raise DocumentError("Unsupported FA field: " + ", ".join(sorted(map(str, unknown))))
    for key, value in changes.items():
        if key in OPTIONS:
            if not isinstance(value, list) or any(not isinstance(code, str) for code in value):
                raise DocumentError(f"{key} must be a list of option-code strings.")
        elif key == "version":
            if type(value) is not int:
                raise DocumentError("FA version must be an integer.")
        elif key == "vin":
            if value is not None and not isinstance(value, str):
                raise DocumentError("VIN must be text or empty.")
        elif not isinstance(value, str):
            raise DocumentError(f"{key} must be text.")


def _apply(order: ET.Element, fields: dict) -> None:
    header, standard = order.find(_q("header")), order.find(_q("standardFA"))
    if header is None or standard is None:
        raise DocumentError("FA header or standardFA is missing.")
    for key, attribute in ATTRIBUTES.items():
        if key in fields:
            standard.set(attribute, str(fields[key]))
    if "vin" in fields:
        if fields["vin"] in (None, ""):
            header.attrib.pop("vinLong", None)
        else:
            header.set("vinLong", fields["vin"])
    for key, (container, item_name) in OPTIONS.items():
        if key not in fields:
            continue
        group = standard.find(_q(container))
        if group is None:
            raise DocumentError(f"FA {container} container is missing.")
        for item in list(group):
            group.remove(item)
        for code in fields[key]:
            ET.SubElement(group, _q(item_name)).text = code


def _result(root: ET.Element, entry_index: int | None) -> dict:
    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    # Validate the actual serialized output before returning anything to save.
    summary = inspect_fa(xml, entry_index)
    return {"xml": xml, "summary": summary, "vehicleWritten": False,
            "fpCalculated": False, "validationScope": summary["validationScope"]}


def create_fa(fields: dict) -> dict:
    """Create a supported saved FA document; all option lists default to empty."""
    _validate_changes(fields)
    required = {"series", "type", "timeCriterion", "paint", "upholstery"}
    if not required.issubset(fields):
        raise DocumentError("Missing FA fields: " + ", ".join(sorted(required - fields.keys())))
    values = {"version": 3, "eWords": [], "hoWords": [], "salapa": [], **fields}
    root = ET.Element(_q("fa"))
    created = datetime.now(timezone.utc)
    ET.SubElement(root, _q("header"), {"date": created.strftime("%Y-%m-%d"),
                  "time": created.strftime("%H:%M:%S"), "createdBy": "BMGARAGE"})
    standard = ET.SubElement(root, _q("standardFA"))
    for container, _item in OPTIONS.values():
        ET.SubElement(standard, _q(container))
    _apply(root, values)
    return _result(root, None)


def update_fa(xml: str, changes: dict, entry_index: int | None = None) -> dict:
    """Edit only the selected FA, preserving other FAList entries and metadata."""
    _validate_changes(changes)
    current = inspect_fa(xml, entry_index)
    root = parse_document(xml)
    if root.tag == "faList":
        order = root.findall("id")[current["entryIndex"]].find(_q("fa"))
    else:
        order = root
    if order is None:
        raise DocumentError("The selected FAList entry has no FA.")
    _apply(order, changes)
    return _result(root, entry_index)
