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
# The alarm: a wheel whose non-`.py` files are more than WHEEL_NONPY_ALARM_PCT percent of its
# uncompressed bytes (default 3) usually means a build exclusion is missing and data, a cache or a
# test fixture went into the wheel. A share, not a total size: source grows with the code and must
# never trip it. The line sits just above the highest share at 0.8.0 (the enricher, 2.6%: its
# AlphaGenome protos and their licence text; format and compiler ship under 1%). Every wheel is
# still built; the script then lists the largest non-`.py` members of each wheel over the line and
# exits 3, so a `build-dists.sh && uv publish` chain stops before the upload. If the list is all
# intended, raise the line for that run (`WHEEL_NONPY_ALARM_PCT=5 scripts/build-dists.sh`) or here.
#
# A second alarm needs no knob: a wheel holding the same bytes under two names (RM397: 0.8.0 shipped
# the Atlas protos and their notice twice) is listed and exits 3 too.
#
# Exit codes: 0 built, no alarm; 3 built, at least one wheel over the line or holding duplicates;
# anything else, a build failed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALARM="${WHEEL_NONPY_ALARM_PCT:-3}"
cd "$ROOT"

mapfile -t PACKAGES < <(python3 - <<'PY'
import tomllib
from pathlib import Path

members = tomllib.loads(Path("pyproject.toml").read_text())["tool"]["uv"]["workspace"]["members"]
for member in members:
    print(tomllib.loads((Path(member) / "pyproject.toml").read_text())["project"]["name"])
PY
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
echo "== dist/ (alarm line: non-.py files over $ALARM% of a wheel's bytes)"
python3 - "$ALARM" <<'PY'
import hashlib
import sys
import zipfile
from pathlib import Path

alarm = float(sys.argv[1])
over = []
twice = []
for path in sorted(Path("dist").iterdir()):
    if path.name.startswith("."):
        continue
    note = ""
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as wheel:
            members = wheel.infolist()
        total = sum(info.file_size for info in members)
        non_py = [info for info in members if not info.filename.endswith(".py")]
        pct = 100 * sum(info.file_size for info in non_py) / total if total else 0.0
        note = f"  non-.py {pct:5.2f}%"
        if pct > alarm:
            note += "  <-- OVER THE LINE"
            over.append((path, pct, non_py))
        with zipfile.ZipFile(path) as wheel:
            by_bytes = {}
            for info in members:
                if info.file_size and not info.is_dir():
                    by_bytes.setdefault(hashlib.sha256(wheel.read(info)).hexdigest(), []).append(info.filename)
        same = [names for names in by_bytes.values() if len(names) > 1]
        if same:
            note += "  <-- SAME BYTES TWICE"
            twice.append((path, same))
    print(f"{path.stat().st_size:>12,}  {path.name}{note}")

for path, pct, non_py in over:
    print(f"\n!! {path.name}: non-.py files are {pct:.2f}% of its bytes. Largest non-.py members:")
    for info in sorted(non_py, key=lambda info: -info.file_size)[:12]:
        print(f"   {info.file_size:>10,}  {info.filename}")

for path, same in twice:
    print(f"\n!! {path.name} holds the same bytes under more than one name (RM397):")
    for names in same:
        print("   " + "  ==  ".join(names))

if over or twice:
    print(
        f"\n!! {len(over)} wheel(s) over {alarm}% non-.py bytes, {len(twice)} holding duplicate "
        "files: check the build exclusions before publishing (WHEEL_NONPY_ALARM_PCT raises the line).",
        file=sys.stderr,
    )
    sys.exit(3)
PY
