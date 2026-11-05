#!/usr/bin/env bash
# Build every workspace package's wheel and sdist into a fresh `dist/` at the repository root.
#
# The root `pyproject.toml` is a workspace with no project of its own, so a bare `uv build` there
# fails (setuptools finds seven top-level directories). Each package is built by name instead, and
# the names are read from `[tool.uv.workspace] members`, so a new member needs no edit here.
#
# `dist/` is wiped first: `uv publish` uploads everything in it, so an earlier build's files would
# ride along. Never build into a `dist/` you mean to keep.
#
# The alarm: a wheel over WHEEL_ALARM_BYTES (default 1 MiB) usually means a build exclusion is
# missing and data, a cache or a test fixture went into the wheel. Every wheel is still built; the
# script then lists the largest members of each wheel over the line and exits 3, so a
# `build-dists.sh && uv publish` chain stops before the upload. Read the list: if it is all source,
# raise the line for that run (`WHEEL_ALARM_BYTES=2000000 scripts/build-dists.sh`).
#
# Exit codes: 0 built, nothing over the line; 3 built, at least one wheel over the line; anything
# else, a build failed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALARM="${WHEEL_ALARM_BYTES:-1048576}"
cd "$ROOT"

mapfile -t PACKAGES < <(python3 - <<'EOF'
import tomllib
from pathlib import Path

members = tomllib.loads(Path("pyproject.toml").read_text())["tool"]["uv"]["workspace"]["members"]
for member in members:
    print(tomllib.loads((Path(member) / "pyproject.toml").read_text())["project"]["name"])
EOF
)
if [ "${#PACKAGES[@]}" -eq 0 ]; then
    echo "build-dists: no workspace members found in pyproject.toml" >&2
    exit 1
fi

rm -rf dist
for pkg in "${PACKAGES[@]}"; do
    echo "== building $pkg"
    uv build --package "$pkg" --out-dir dist
done

echo
echo "== dist/ (alarm line: $ALARM bytes per wheel)"
python3 - "$ALARM" <<'EOF'
import sys
import zipfile
from pathlib import Path

alarm = int(sys.argv[1])
over = []
for path in sorted(Path("dist").iterdir()):
    if path.name.startswith("."):
        continue
    size = path.stat().st_size
    flag = ""
    if path.suffix == ".whl" and size > alarm:
        flag = "  <-- OVER THE LINE"
        over.append(path)
    print(f"{size:>12,}  {path.name}{flag}")

for path in over:
    with zipfile.ZipFile(path) as wheel:
        members = sorted(wheel.infolist(), key=lambda info: -info.compress_size)
    non_py = [info for info in members if not info.filename.endswith(".py")]
    print(f"\n!! {path.name}: {path.stat().st_size:,} bytes, {len(members)} members, "
          f"{len(non_py)} of them not .py. Largest (compressed / raw):")
    for info in members[:12]:
        print(f"   {info.compress_size:>10,} / {info.file_size:>10,}  {info.filename}")

if over:
    print(f"\n!! {len(over)} wheel(s) over {alarm:,} bytes: check the build exclusions before "
          "publishing (WHEEL_ALARM_BYTES raises the line).", file=sys.stderr)
    sys.exit(3)
EOF
