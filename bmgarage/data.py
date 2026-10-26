"""Read-only PSdZDATA selection and inventory, implemented in Python only.

These checks do not initialize a processing engine or establish that any
calculation, programming, coding, or vehicle operation is available.
"""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


MAX_MAPPING_BYTES = 8 * 1024 * 1024
XINCLUDE_NAMESPACE = "http://www.w3.org/2001/XInclude"
BRREF_NAMESPACE = "http://bmw.com/2005/psdz.data.brref"


class DataSelectionError(ValueError):
    """A selected directory or mapping document cannot be inspected."""


def _resolved_path(value: Path | str) -> Path:
    if not str(value).strip():
        raise DataSelectionError("Choose a PSdZDATA directory.")
    try:
        return Path(value).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as error:
        raise DataSelectionError("The selected directory cannot be resolved.") from error


def normalize_data_home(value: Path | str) -> Path:
    """Return the actual data directory, accepting it or its containing folder.

    The returned path is the ``psdzdata`` directory itself, rather than the
    containing directory expected by the former Java API. No Java is used.
    Empty directories named psdzdata are accepted as selections, but their
    inventory will explicitly report the missing mapping file.
    """
    selected = _resolved_path(value)
    if not selected.is_dir():
        raise DataSelectionError("The selected directory does not exist or is not a directory.")
    if selected.name.casefold() == "psdzdata" or (selected / "mapping").is_dir():
        return selected
    try:
        children = [p for p in selected.iterdir()
                    if p.name.casefold() == "psdzdata" and p.is_dir()]
    except OSError as error:
        raise DataSelectionError("The selected directory cannot be read.") from error
    if len(children) == 1:
        return children[0].resolve()
    if len(children) > 1:
        raise DataSelectionError("More than one PSdZDATA directory was found; select the intended directory directly.")
    raise DataSelectionError("Select the psdzdata directory or its containing folder.")


class _MappingTreeBuilder(ET.TreeBuilder):
    def doctype(self, _name: str, _public_id: str | None,
                _system_id: str | None) -> None:
        # The parser callback also covers UTF-16 input; scanning UTF-8 byte
        # sequences alone would miss a declaration in another XML encoding.
        raise DataSelectionError("DTD and entity declarations are not allowed in mapping XML.")


def _read_mapping(path: Path) -> tuple[ET.Element, int]:
    try:
        with path.open("rb") as source:
            content = source.read(MAX_MAPPING_BYTES + 1)
    except OSError as error:
        raise DataSelectionError("The mapping file could not be read.") from error
    if len(content) > MAX_MAPPING_BYTES:
        raise DataSelectionError("The mapping file exceeds the 8 MiB inventory limit.")
    try:
        parser = ET.XMLParser(target=_MappingTreeBuilder())
        root = ET.fromstring(content, parser=parser)
    except (ET.ParseError, UnicodeError, ValueError) as error:
        if isinstance(error, DataSelectionError):
            raise
        raise DataSelectionError("The mapping file is not well-formed XML.") from error
    for element in root.iter():
        if element.tag.startswith("{" + XINCLUDE_NAMESPACE + "}"):
            raise DataSelectionError("XML includes are not allowed in mapping XML.")
    return root, len(content)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def inspect_data(value: Path | str | None = None) -> dict:
    """Inspect a user-selected dataset without writing or loading an engine.

    ``mappingReadable`` means that the file was read and parsed as XML, not
    that its BMW schema, referenced artifacts, or dataset compatibility were
    validated. ``usableForInventory`` additionally requires named series
    entries. ``calculationsAvailable`` remains false for this native build.
    """
    result = {
        "selected": value is not None and bool(str(value).strip()),
        "path": None,
        "exists": False,
        "mappingPresent": False,
        "mappingReadable": False,
        "seriesCount": None,
        "mainSeriesCount": None,
        "mappingBytes": None,
        "directories": {},
        "errors": [],
        "usableForInventory": False,
        "calculationsAvailable": False,
        "inventoryOnly": True,
    }
    if not result["selected"]:
        return result
    try:
        candidate = _resolved_path(value)
        result["path"] = str(candidate)
        result["exists"] = candidate.is_dir()
        data = normalize_data_home(value)
    except DataSelectionError as error:
        result["errors"].append(str(error))
        return result
    result["path"] = str(data)
    result["exists"] = True
    result["directories"] = {name: (data / name).is_dir()
                             for name in ("mapping", "mainseries", "kiswb", "swe")}
    mapping = data / "mapping" / "brref.xml"
    result["mappingPresent"] = mapping.is_file()
    if not result["mappingPresent"]:
        result["errors"].append("The selected dataset has no mapping/brref.xml file.")
        return result
    try:
        root, byte_count = _read_mapping(mapping)
    except DataSelectionError as error:
        result["errors"].append(str(error))
        return result
    result["mappingReadable"] = True
    result["mappingBytes"] = byte_count
    # brref.xsd uses <series>F030</series>; only mainSeries has a name
    # attribute. The former name-attribute assumption rejected real datasets.
    # This is still inventory, not full schema/authenticity validation.
    if root.tag not in {"brRef", "{" + BRREF_NAMESPACE + "}brRef"}:
        result["seriesCount"] = 0
        result["mainSeriesCount"] = 0
        result["errors"].append("Expected a brRef series-mapping document.")
        return result
    prefix = "{" + BRREF_NAMESPACE + "}" if root.tag.startswith("{") else ""
    groups = root.findall(prefix + "mainSeries")
    series = {(e.text or "").strip() for group in groups
              for e in group.findall(prefix + "series") if (e.text or "").strip()}
    main_series = {e.get("name", "").strip() for e in groups if e.get("name", "").strip()}
    result["seriesCount"] = len(series)
    result["mainSeriesCount"] = len(main_series)
    if not series:
        result["errors"].append("No named series entries were found in mapping/brref.xml.")
        return result
    result["usableForInventory"] = True
    return result
