"""Run the native Python/Tk smoke under an owned local Xvfb server."""

from __future__ import annotations

import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile


def main() -> int:
    executable = os.environ.get("BMGARAGE_XVFB") or shutil.which("Xvfb")
    if not executable:
        retained = Path("/workspace/toolchains/xvfb/usr/bin/Xvfb")
        if retained.is_file():
            executable = str(retained)
    if not executable:
        raise SystemExit("Xvfb is unavailable. Run tests/gui_smoke.py on a real desktop display instead.")
    project = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryFile() as log:
        server = subprocess.Popen([executable, "-displayfd", "1", "-screen", "0", "1280x900x24",
                                   "-nolisten", "tcp"], stdout=subprocess.PIPE, stderr=log)
        try:
            readable, _, _ = select.select([server.stdout], [], [], 15)
            if not readable:
                raise RuntimeError("Xvfb did not report a display before the readiness timeout.")
            display = server.stdout.readline(32).decode("ascii").strip()
            if not display.isdigit() or server.poll() is not None:
                raise RuntimeError("Xvfb could not allocate a local display.")
            environment = os.environ.copy()
            environment["DISPLAY"] = ":" + display
            result = subprocess.run([sys.executable, str(project / "tests" / "gui_smoke.py")],
                                    cwd=project, env=environment, timeout=90)
            return result.returncode
        finally:
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
            server.stdout.close()


if __name__ == "__main__":
    raise SystemExit(main())
