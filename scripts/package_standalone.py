"""Create the Python-only portable source distribution, excluding vendor code."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {".jar", ".class", ".java", ".dll", ".exe", ".bat", ".z01"}


def package() -> Path:
    files = [ROOT / name for name in ("BMGARAGE.pyw", "README.md", ".gitignore")]
    for folder in ("bmgarage", "tests", "scripts", "docs"):
        files.extend(p for p in sorted((ROOT / folder).rglob("*"))
                     if p.is_file() and "__pycache__" not in p.parts
                     and p.suffix not in {".pyc", ".log"})
    for file in files:
        if file.suffix.lower() in FORBIDDEN:
            raise RuntimeError(f"Non-Python runtime artifact would enter the package: {file.name}")
    destination = ROOT / "dist" / "BMGARAGE-Python-Standalone.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    fingerprints = []
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            relative = file.relative_to(ROOT).as_posix()
            content = file.read_bytes()
            fingerprints.append(f"{hashlib.sha256(content).hexdigest()}  {relative}")
            archive.writestr("BMGARAGE/" + relative, content)
        archive.writestr("BMGARAGE/MANIFEST.sha256", "\n".join(fingerprints) + "\n")
        archive.writestr("BMGARAGE/runtime-requirements.json", json.dumps({
            "language": "Python", "minimumVersion": "3.10", "gui": "tkinter",
            "thirdPartyPythonPackages": [], "java": False, "esysInstallation": False,
            "psdzdata": "Selected manually in application settings; optional for file tools",
            "completeEsysFeatureParity": False,
        }, indent=2) + "\n")
    checksum = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(".zip.sha256").write_text(checksum + "  " + destination.name + "\n")
    print(json.dumps({"archive": str(destination), "bytes": destination.stat().st_size,
                      "sha256": checksum, "files": len(files), "javaIncluded": False}, indent=2))
    return destination


if __name__ == "__main__":
    package()
