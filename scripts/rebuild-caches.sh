#!/usr/bin/env bash
# Rebuild every cache this tier builds, in one run — the driver behind `cache rebuild` (RM176).
#
# A thin driver, deliberately. Every decision about which lanes exist, which can be built
# unattended, which are licence-gated and which may be published lives in the registry
# (`just_dna_enricher.caches.CACHE_LANES`), where a test walks it against the builder modules on
# disk. Anything this script decided for itself would be a second roster nothing checks, which is
# the exact defect the registry replaced — so all it does is set the arguments and get out of the
# way. Add a lane by adding it to the registry; this file needs no edit.
#
# It assumes the workspace checkout (`uv sync` at the repo root). For a deployment with no checkout
# the same run is `pip install 'just-dna-enricher[dev]'` and then the same command without `uv run`;
# the `[dev]` extra is what brings polars and openpyxl, which every builder needs and no runtime
# check does.
#
# What it does NOT do is move anything into the live caches. Each lane is built into
# "$OUT/<lane>/", and pointing the deployment at the result is a separate, deliberate step: a
# rebuild takes minutes, and an `enrich` reading a half-written snapshot sees a real but incomplete
# table — a short parquet still has a footer, so no resolver can catch it.
#
#   scripts/rebuild-caches.sh /srv/just-dna/caches-2026-09-02
#   JUST_DNA_USE=non-commercial scripts/rebuild-caches.sh /srv/... --publish
#
# Every argument after the output directory is passed through to `cache rebuild`, so a partial run
# is `--only clinvar --only cpic` and a rehearsal is `--publish --dry-run`.

set -euo pipefail

OUT="${1:-}"
if [[ -z "$OUT" ]]; then
    echo "usage: $0 <output-base> [extra args for 'cache rebuild']" >&2
    echo "  e.g. $0 /srv/just-dna/caches-\$(date +%F) --publish --dry-run" >&2
    exit 2
fi
shift

# The declared use reaches the licence-gated lanes (ClinPGx, its drug labels, CPIC, PharmVar). They
# forbid sale, so `unstated` SKIPS them and `commercial` REFUSES: an operator who does not say gets
# a run that quietly builds fewer lanes, which is why this defaults to nothing and lets the gate
# print its own reason rather than picking a declaration on the operator's behalf.
USE="${JUST_DNA_USE:-unstated}"

# The releases worth pinning. MANE discovers its own current version, so it is absent here on
# purpose; CIViC has no default at all and stays in the not-run state until an operator names a
# dated release, because a build from "whatever was there that afternoon" cannot be re-run.
PINS=()
[[ -n "${JUST_DNA_STRCHIVE_RELEASE:-}" ]] && PINS+=(--pin "strchive=$JUST_DNA_STRCHIVE_RELEASE")
[[ -n "${JUST_DNA_CIVIC_RELEASE:-}" ]] && PINS+=(--pin "civic=$JUST_DNA_CIVIC_RELEASE")
[[ -n "${JUST_DNA_MANE_RELEASE:-}" ]] && PINS+=(--pin "mane=$JUST_DNA_MANE_RELEASE")

# ACMG is the one lane with no acquire stage: the SF workbook is Elsevier supplementary material and
# nothing may fetch it on the operator's behalf. Without this the lane reports not-run and says so.
SOURCES=()
[[ -n "${JUST_DNA_ACMG_WORKBOOK:-}" ]] && SOURCES+=(--source "acmg=$JUST_DNA_ACMG_WORKBOOK")

# `..` from scripts/ is the workspace root, which is what `--project` wants. It is the only line
# here that knows where this file lives, so moving the file means editing this and nothing else.
RUNNER=(uv run --project "$(dirname "$0")/.." just-dna-enricher)
command -v uv >/dev/null 2>&1 || RUNNER=(just-dna-enricher)

"${RUNNER[@]}" cache rebuild --out "$OUT" --use "$USE" \
    ${PINS[@]+"${PINS[@]}"} ${SOURCES[@]+"${SOURCES[@]}"} "$@"

echo
echo "Built into $OUT. Nothing has been moved into the live caches — point"
echo "\$JUST_DNA_PIPELINES_CACHE_DIR at it, or copy each <lane>/ directory across, then run"
echo "  ${RUNNER[*]} cache status"
