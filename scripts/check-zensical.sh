#!/usr/bin/env bash
# Is Zensical able to build this site yet?
#
# The docs site is built by ProperDocs, a frozen MkDocs 1.x continuation, while the *living* project is
# Zensical — the Material team's successor, which reads the same `mkdocs.yml`. The switch is blocked on
# exactly one thing, measured rather than assumed on 2026-09-12: Zensical validates that
# `mkdocs-gen-files` is installed and then **ignores** it, so the generated home page and the per-module
# API reference come out absent with no warning. `mkdocstrings` itself works. See
# `@a-docs-site-nav-is-a-registry-over-a-directory-that-grows` in docs/AGENT_NOTES.md.
#
# So this script asks the only question whose answer changes the decision, and it asks it the way that
# cannot be fooled by a green build: **count the emitted pages.** A silent no-op is the failure mode
# here, so a zero exit from the builder proves nothing on its own.
#
# Run it fortnightly (the CI workflow `zensical-watch.yml` does, on a schedule) or by hand any time:
#
#   scripts/check-zensical.sh
#
# Exit 0 = still blocked, nothing to do. Exit 3 = **Zensical can now build this site**, go read the
# output and consider the migration. Any other exit is the script or the environment failing, not a
# verdict.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d -t zensical-probe-XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

# Zensical refuses a symlinked `docs_dir` ("docs_dir must be within project root"), so the probe works
# on copies. The three `*/src` trees come along because `mkdocstrings` resolves `paths:` against them,
# and `scripts/` because that is where the gen-files script lives.
cp "$ROOT/mkdocs.yml" "$ROOT/README.md" "$WORK/"
cp -r "$ROOT/docs" "$ROOT/scripts" "$WORK/"
for member in schema compiler enricher; do cp -r "$ROOT/$member" "$WORK/"; done
# Keep the probe's output inside the temp dir rather than in the checkout's data/.
sed -i 's#^site_dir: .*#site_dir: probe_site#' "$WORK/mkdocs.yml"

echo "Building with Zensical (ephemeral install, nothing is added to the project venv)…"
cd "$WORK"
# `--with` overlays rather than installing into the workspace, so this never touches `uv.lock` or the
# `docs` group. Failure here is reported, not swallowed: a builder that refuses outright is a *clearer*
# answer than the silent no-op this exists to detect.
if ! uv run --with zensical \
             --with 'mkdocstrings[python]' \
             --with mkdocs-gen-files \
             --with mkdocs-literate-nav \
             --quiet zensical build > "$WORK/build.log" 2>&1; then
  echo "Zensical build FAILED. Still blocked. Tail of its output:"
  tail -20 "$WORK/build.log"
  exit 0
fi

zensical_version="$(uv run --with zensical --quiet zensical --version 2>/dev/null | tr -d '\n')"

# The pass criterion, derived rather than hardcoded: one API page per module the gen-files script would
# write, and a home page. Counting `docs/**/*.md` proves the ordinary pages rendered too, which
# separates "gen-files did nothing" from "the whole build did nothing".
#
# Every count is `|| true`-guarded and every test is an `if`: under `set -euo pipefail` a `find` over a
# directory that does not exist fails the *pipeline*, and `[ -f x ] && y=1` exits the script when the
# file is absent — and "the directory is absent" is precisely the expected result here. The first
# version of this script died silently at exactly the outcome it was written to report.
expected_modules="$(find "$ROOT"/{schema,compiler,enricher}/src -name '*.py' \
  -not -path '*/__pycache__/*' -not -path '*/generated/*' -not -path '*/_atlas_protos/*' \
  2>/dev/null | wc -l || true)"
api_pages="$(find probe_site/api -name index.html 2>/dev/null | wc -l || true)"
doc_pages="$(find probe_site -name index.html 2>/dev/null | wc -l || true)"
if [ -f probe_site/index.html ]; then home="yes"; else home="no"; fi

echo
echo "  $zensical_version"
echo "  ordinary pages rendered : $doc_pages"
echo "  home page (gen-files)   : $home"
echo "  API pages (gen-files)   : $api_pages   (expected around $expected_modules, one per module)"
echo

if [ "$home" = "yes" ] && [ "$api_pages" -gt 0 ]; then
  cat <<'MSG'
ZENSICAL CAN NOW BUILD THIS SITE — mkdocs-gen-files ran.

What to do, in order:
  1. Re-read the reasoning in pyproject.toml's `docs` group before changing anything; it records why
     ProperDocs was chosen and what would reverse that.
  2. Compare the two builds page-for-page, not just by count — search index, nav, the anchor
     diagnostic, the edit URLs on generated pages (those were a 404 once already).
  3. `zensical.toml` is NOT the move: keeping `mkdocs.yml` is what makes this a change of build command.
  4. The switch touches pyproject.toml (the group), mkdocs.yml (nothing, ideally), the CI docs job, and
     the README's build commands. Update docs/AGENT_NOTES.md's entry in the same commit.
MSG
  exit 3
fi

echo "Still blocked: the ordinary pages render but gen-files produced nothing. Nothing to do."
if [ "$doc_pages" -eq 0 ]; then
  # A zero-exit build that emitted no pages at all is not the known blocker — it is a new failure, and
  # the log is the only evidence, so it outlives the temp directory.
  keep="${TMPDIR:-/tmp}/zensical-probe-emitted-nothing.log"
  cp "$WORK/build.log" "$keep"
  echo "It emitted NO pages at all, which is not the known blocker. Log kept at $keep"
fi
exit 0
