# Windows and Linux native checks

The `Native Python checks` workflow runs the native test suite and actual Tk
graphical smoke on Windows and Ubuntu with Python 3.10 and 3.12. It runs on
pushes to `bmgarage/python-standalone` or `main`, pull requests, and manual
workflow dispatch. It requires no Java, E-Sys installation, vehicle dataset,
BMW credentials or connected vehicle.

The workflow is configuration, not proof of a completed Windows run. Check the
actual run outcomes before describing Windows behavior as verified:

1. Open the repository's **Actions** tab and select **Native Python checks**.
2. Inspect all four OS/Python jobs. Each runs unit/component tests, the actual
   graphical smoke, and distribution packaging as separate failing steps.
3. Read the job summary and `native-tests.json` artifact for test counts,
   failures, errors, expected failures and skipped tests. A zero-test or entirely
   skipped run fails.
4. Check the graphical smoke log separately. Passing unit tests alone does not
   establish that the Tk application opened and processed its file/settings
   workflows successfully.

Windows runs `python tests/gui_smoke.py` against real Tk widgets on the hosted
runner desktop. Linux runs that same test under Xvfb. The smoke uses the native
engine and records process launches; it must not start a Java or external
processing engine. These checks use synthetic saved-file/protocol fixtures,
not simulated successful vehicle operations.

The workflow sets UTF-8 mode explicitly so fixture and diagnostic text is not
dependent on the Windows system code page. Python/Tk comes from `setup-python`;
Linux installs Xvfb, xauth and Tk libraries through the normal signed package
manager. If `requirements.txt` is present, its declared Python dependencies are
installed normally with TLS verification.

Filesystem tests that need symlink-creation privilege may explicitly skip on a
Windows host without that privilege. Such outcomes remain visible in the test
summary; they must not be counted as passed tests. The workflow never skips the
whole graphical smoke merely because a desktop is unavailable: an unavailable
display is a failed graphical check to investigate.

Each job uploads its exact native test outcomes when that step executed. A
distribution ZIP and SHA256 file are uploaded only if that job's packaging step
completed successfully; a committed older ZIP is not relabeled as a fresh build
after a failed test step. For a release, use artifacts from a fully passing run of
the intended commit. Downloading Actions artifacts may require signing in to
GitHub. The committed ZIP remains an independent delivery route through the
repository's **Download raw file** control.

To repeat Windows checks locally from the source folder:

```powershell
py -3.12 -m unittest discover -s tests -v
py -3.12 tests/gui_smoke.py
py -3.12 scripts/package_standalone.py
pyw -3.12 BMGARAGE.pyw
```

Use Python installed with Tcl/Tk support. Select PSdZDATA manually inside the
application when needed; it is optional for the saved-file smoke checks.

Even successful Windows CI does not verify a complete E-Sys replacement, vehicle
transport/drivers, real target/TAL calculation, programming/coding, or authorized
BMW backend workflows. Those require their own genuine inputs and Windows
vehicle/bench tests. Do not infer them from a hosted runner or a built ZIP.
