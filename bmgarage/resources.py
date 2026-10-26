"""Locate real FA-to-FP resources without decrypting or trusting their content."""

from __future__ import annotations

from pathlib import Path
import re

from .data import BRREF_NAMESPACE, _read_mapping, normalize_data_home


class FpResourceError(ValueError):
    pass


def find_fafp_resources(data_home: Path | str | None, series: str) -> dict:
    """Resolve brref text/override rules and inventory matching FAP files.

    Discovering a file does not authenticate/decrypt it, execute a mapping, or
    establish that the selected dataset supports a complete FP calculation.
    """
    if not data_home:
        raise FpResourceError("Select a PSdZDATA directory before locating FA-to-FP data.")
    if not isinstance(series, str) or re.fullmatch(r"[A-Z0-9_]+", series) is None:
        raise FpResourceError("Supply the exact development-series identifier from the FA.")
    data = normalize_data_home(data_home)
    mapping_path = data / "mapping" / "brref.xml"
    if not mapping_path.resolve().is_relative_to(data):
        raise FpResourceError("The series mapping resolves outside the selected dataset.")
    root, _size = _read_mapping(mapping_path)
    if root.tag not in {"brRef", "{" + BRREF_NAMESPACE + "}brRef"}:
        raise FpResourceError("Expected a brRef series-mapping document.")
    prefix = "{" + BRREF_NAMESPACE + "}" if root.tag.startswith("{") else ""
    matches = []
    for group in root.findall(prefix + "mainSeries"):
        for item in group.findall(prefix + "series"):
            if (item.text or "").strip() == series:
                main_series = group.get("name", "")
                if re.fullmatch(r"[A-Z0-9]{4}", main_series) is None:
                    raise FpResourceError("The mapped main-series identifier has invalid syntax.")
                # The traced legacy parser treats an empty override as absent.
                identifier = item.get("fa2fpId") or group.get("fa2fpId")
                if identifier is None or re.fullmatch(r"[A-Fa-f0-9]{1,8}", identifier) is None:
                    raise FpResourceError("The selected series has no valid FA2FP mapping identifier.")
                matches.append((main_series, identifier.upper().zfill(8)))
    if not matches:
        raise FpResourceError(f"No FA2FP mapping exists for development series {series}.")
    if len(matches) != 1:
        raise FpResourceError(f"Ambiguous FA2FP mapping for development series {series}.")
    main_series, identifier = matches[0]
    filename = re.compile(r"fafp_([a-f0-9]{8})\.fap\.([0-9]{3})_([0-9]{3})_([0-9]{3})", re.I)
    candidates = []
    for location, directory in (("swe", data / "swe" / "fafp"),
                                ("mainseries", data / "mainseries" / main_series / "mapping")):
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            match = filename.fullmatch(path.name)
            if match is None or match[1].upper() != identifier or not path.is_file():
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(data):
                raise FpResourceError("An FA2FP resource resolves outside the selected dataset.")
            version = tuple(int(match[index]) for index in (2, 3, 4))
            candidates.append({"path": str(resolved), "version": list(version),
                               "versionString": "_".join(match[index] for index in (2, 3, 4)),
                               "bytes": resolved.stat().st_size, "location": location})
    candidates.sort(key=lambda item: (item["location"] == "swe", item["version"], item["path"]), reverse=True)
    # Legacy directories establish discovery only. Do not imply that a file
    # found there is a proven substitute for current PDX/SWE retrieval.
    current = [item for item in candidates if item["location"] == "swe"]
    preferred = current[0] if current else None
    if preferred and sum(item["location"] == preferred["location"] and
                         item["version"] == preferred["version"] for item in candidates) != 1:
        raise FpResourceError("More than one FA2FP file matches the preferred resource version.")
    return {"series": series, "mainSeries": main_series, "fa2fpId": identifier,
            "mappingPath": str(mapping_path), "mappingVersion": root.get("version"),
            "candidates": candidates, "preferredCandidate": preferred,
            "fapPresent": bool(current), "legacyFilesFound": len(candidates) - len(current),
            "legacyRetrievalVerified": False, "authenticated": False,
            "calculationAvailable": False,
            "missing": [] if current else [f"No current swe/fafp/fafp_{identifier.lower()}.fap.<version> file found."],
            "limitations": ["FAP decryption, signature verification, mapping evaluation and final FP validation are not implemented."]}
