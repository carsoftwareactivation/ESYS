#!/bin/sh
# Native Python development setup; no Java or vendor installation is used.
set -eu
cd /workspace/ESYS
python3 -c 'import sys, tkinter; assert sys.version_info >= (3, 10), "Python 3.10+ is required"'
# The cloud snapshot is Debian 13. Keep the display server and APT metadata
# inside the workspace; signatures, package hashes and TLS remain enabled.
if [ ! -x /workspace/toolchains/xvfb/usr/bin/Xvfb ]; then
    aptroot=/workspace/toolchains/apt
    mkdir -p "$aptroot/etc" "$aptroot/state/lists/partial" "$aptroot/cache/archives/partial" "$aptroot/log" "$aptroot/downloads"
    cat > "$aptroot/apt.conf" <<'APTCONF'
Dir "/workspace/toolchains/apt";
Dir::State "state";
Dir::State::status "/var/lib/dpkg/status";
Dir::Cache "cache";
Dir::Log "log";
Dir::Etc "etc";
Dir::Etc::SourceList "sources.list";
Dir::Etc::SourceParts "-";
Dir::Etc::Parts "-";
Dir::Etc::main "-";
Dir::Etc::Trusted "/usr/share/keyrings/debian-archive-keyring.gpg";
Dir::Etc::TrustedParts "-";
Acquire::Languages "none";
APTCONF
    cat > "$aptroot/etc/sources.list" <<'SOURCES'
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian-security trixie-security main
SOURCES
    APT_CONFIG="$aptroot/apt.conf" apt-get update
    packages=$(mktemp -d "$aptroot/downloads/setup.XXXXXX")
    (
        cd "$packages"
        APT_CONFIG="$aptroot/apt.conf" apt-get download xvfb xserver-common
        for package in ./*.deb; do
            dpkg-deb -x "$package" /workspace/toolchains/xvfb
        done
    )
fi
python3 -m unittest discover -s tests -v
python3 -m bmgarage info
python3 scripts/run_gui_smoke.py
python3 scripts/package_standalone.py
