"""Native Python command line; no Java or E-Sys installation is required."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .engine import Engine, EngineError
from .settings import load_preferences


def main() -> int:
    parser = argparse.ArgumentParser(description="BMGARAGE standalone Python application")
    parser.add_argument("--psdzdata", type=Path, help="Manually selected psdzdata directory or its parent")
    parser.add_argument("--state-dir", type=Path, help="Application-owned settings directory")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("info", help="Report the native application engine")
    sub.add_parser("data", help="Inspect the manually selected dataset location")
    inspect = sub.add_parser("inspect", help="Inspect a saved document using the Python engine")
    inspect.add_argument("kind", choices=["fa", "svt", "tal"])
    inspect.add_argument("file", type=Path)
    inspect.add_argument("--entry", type=int, help="FAList entry number, starting at 1")
    step = sub.add_parser("istep", help="Parse or compare I-Step identifiers")
    step.add_argument("value")
    step.add_argument("other", nargs="?")
    sub.add_parser("gui", help="Launch BMGARAGE")
    options = parser.parse_args()
    try:
        data_home = options.psdzdata or load_preferences(options.state_dir).get("data_home")
        if options.command in (None, "gui"):
            from .gui import run_gui
            run_gui(data_home=data_home, state_dir=options.state_dir)
            return 0
        with Engine(data_home=data_home, state_dir=options.state_dir) as engine:
            if options.command == "info":
                result = engine.call("system.info")
            elif options.command == "data":
                result = engine.call("data.status")
            elif options.command == "istep":
                if options.other is None:
                    result = engine.call("istep.parse", {"value": options.value})
                else:
                    result = engine.call("istep.compare", {"left": options.value, "right": options.other})
            else:
                with options.file.open("rb") as source:
                    document = source.read(8 * 1024 * 1024 + 1)
                if len(document) > 8 * 1024 * 1024:
                    raise ValueError("Document exceeds 8 MiB.")
                args = {"xml": document.decode("utf-8-sig")}
                if options.entry is not None:
                    if options.entry < 1:
                        raise ValueError("FAList entry numbers start at 1.")
                    args["entryIndex"] = options.entry - 1
                result = engine.call(options.kind + ".inspect", args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (EngineError, OSError, ValueError, UnicodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
