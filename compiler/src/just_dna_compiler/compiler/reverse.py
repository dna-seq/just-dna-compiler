"""`reverse_module`: an artifact back to an authored spec directory, including `resolution.csv`."""

import csv
import logging
from pathlib import Path
from typing import Any

import polars as pl
import yaml
from just_dna_format.base import derive_variant_key
from just_dna_format.layout import sidecar_write_path
from just_dna_format.manifest import Verification, read_manifest
from just_dna_format.overrides import OverrideRow

from just_dna_compiler.compiler.positional import _POSITIONAL_TABLE_KINDS
from just_dna_compiler.compiler.tables import (
    _FACT_TABLES,
    _TABLE_KINDS,
    OVERRIDES_CSV,
    OVERRIDES_PARQUET,
    _list_cell,
    _scalar_cell,
    _write_table_csv,
)

# `validate_spec`/`compile_module` return their findings on a result object, which is the right shape
# for anything a caller must act on. `reverse_module` returns a bare `Path` and has none, so the one
# thing it needs to say — that an attestation is being dropped — goes here (CLAUDE.md: stdlib
# `logging`, never `print`). Unconfigured, this still reaches stderr through logging's last-resort
# handler, so a CLI that sets nothing up does not swallow it.
# RM260: the name is spelled out because `__name__` here is the submodule's, and the logger has always
# been `just_dna_compiler.compiler` — the name a caller configuring or filtering it already uses.
logger = logging.getLogger("just_dna_compiler.compiler")


# ── Reverse engineering ────────────────────────────────────────────────────────


def _module_name_from_parquets(parquet_dir: Path) -> str | None:
    """Recover the module name from the `module` column of the first present parquet — so a module
    with no `weights.parquet` (a PGx/PharmGKB/PRS-only module) still reverses (RM2)."""
    for name in (
        "weights.parquet",
        "annotations.parquet",
        "studies.parquet",
        *(parquet for _, parquet, _ in _TABLE_KINDS),
    ):
        path = parquet_dir / name
        if path.is_file():
            df = pl.read_parquet(path)
            if "module" in df.columns:
                values = df["module"].drop_nulls().unique().to_list()
                if values:
                    # polars `unique()` order is unstable; `min` is the deterministic pick (a
                    # well-formed module has one value here, so this only matters defensively).
                    return min(values)
    return None


def _authored_version_from_artifact(parquet_dir: Path) -> str | None:
    """The `module.version` the author wrote, recovered from the artifact's own `manifest.json`.

    **`version_coerced_from` first, `version` second, and that order is the whole point (RM103).**
    `identity.version` holds the *coerced* SemVer, so re-emitting it would hand the next compile a
    string with nothing left to coerce — `version_coerced_from` would come back absent on lap 2, and a
    module would disagree with its own round trip on a published field. Preferring the pre-coercion
    string makes the field a fixed point: `v2` re-emits as `v2`, coerces to `2.0.0` again, and both
    manifest cells match lap 1.

    It also repairs a quieter loss. Reverse used to emit no `version:` at all unless a caller supplied
    one, so the author's spelling did not survive a round trip even when it was ordinary SemVer. Same
    tolerant shape as `_genome_build_from_artifact`, and the same rule: recover it or return `None`,
    never invent one.
    """
    path = parquet_dir / "manifest.json"
    if not path.is_file():
        return None
    try:
        identity = read_manifest(path).identity
    except (OSError, ValueError):
        return None
    return identity.version_coerced_from or identity.version


def _genome_build_from_artifact(parquet_dir: Path) -> str | None:
    """Recover the module's declared `genome_build` from the artifact's own `manifest.json`.

    `genome_build` is authored `module_spec.yaml` metadata that reaches the artifact through the
    manifest and **no parquet column**, so this is the only place it survives a compile. Reverse has
    to consult it: unlike `title`, getting the build wrong is not cosmetic — a coordinate is not
    absolute, so re-emitting a GRCh37 module as GRCh38 makes the next compile mint a GRCh38 VRS allele
    id for a GRCh37 position, which is a *false content-addressed claim* rather than a lost label.

    Returns `None` for a bare parquet directory with no manifest, or a manifest this compiler cannot
    parse — the same "recover it from the artifact, else fall back" shape as
    `_module_name_from_parquets`. A provenance failure must not stop a reverse, so the read is
    tolerant; what it must not do is *invent* a build, which is why the caller's fallback is explicit.
    """
    path = parquet_dir / "manifest.json"
    if not path.is_file():
        return None
    try:
        return read_manifest(path).genome_build
    except (OSError, ValueError):
        return None


def _artifact_verification(parquet_dir: Path) -> Verification | None:
    """The verification block reverse is about to drop, if the artifact carried one.

    Returns the block rather than a bool because **what is being lost decides what to say**. A
    document may carry checks, a closure (RM73), or both, and the remedies are different parties'
    jobs: re-running the enricher re-attests the checks, and only the author can close the module
    again. A single sentence naming the enricher was correct while checks were the only content and
    became a correct sentence aimed at the wrong defect the moment a closure could ride alone — which
    is now thirteen of the sixteen reference examples. That is the RM77 class, and the compile-side
    stale message already branches the same way.

    Tolerant in the same way and for the same reason as the build recovery above: an unreadable
    manifest is a provenance failure, and a provenance failure must not stop a reverse. A `None` here
    only ever costs the warning.
    """
    path = parquet_dir / "manifest.json"
    if not path.is_file():
        return None
    try:
        return read_manifest(path).verification
    except (OSError, ValueError):
        return None


def _verification_loss_notice(block: Verification) -> str:
    """What the reversed spec loses with the attestation, and whose job it is to put it back."""
    if not block.checks:
        return (
            "The source artifact carries a verification attestation (RM73) holding a closure and no "
            "checks, and the reversed spec will not: the document is not in the artifact, so there is "
            "nothing for reverse to read, and it holds no authority to declare someone else's "
            "authoring finished. Close %s yourself once you are satisfied with it; recompiling as-is "
            "produces a manifest with no `verification` block and warns that the module is open."
        )
    checks = (
        "the checks were put by the enricher, against sources this tier does not reach, and the "
        "record is bound to authored bytes reverse is re-emitting. Re-run the enricher on %s to "
        "re-attest"
    )
    if block.closure is not None:
        return (
            "The source artifact carries a verification attestation (RM45) with a closure (RM73) and "
            "the reversed spec will carry neither: " + checks + ", and close it yourself — reverse "
            "holds no authority to declare someone else's authoring finished. Recompiling as-is "
            "produces a manifest with no `verification` block."
        )
    return (
        "The source artifact carries a verification attestation (RM45) and the reversed spec "
        "will not: " + checks + "; recompiling as-is produces a manifest with no "
        "`verification` block."
    )


def reverse_module(
    parquet_dir: Path,
    output_dir: Path,
    module_name: str | None = None,
    title: str | None = None,
    description: str | None = None,
    report_title: str | None = None,
    icon: str = "database",
    color: str = "#6435c9",
    version: str | None = None,
    write_resolution: bool = True,
    genome_build: str | None = None,
) -> Path:
    """Reverse-engineer a parquet module back into the spec DSL (yaml + csv). Returns output_dir.

    `version` (like `title`/`description`) is authored `module:` metadata, out of `artifact.digest`
    and so not materialized into any parquet. **Since RM103 it is recovered from the artifact's own
    `manifest.json` when the caller supplies none**, rather than dropped: an explicit argument still
    wins, and a bare parquet directory with no manifest still leaves the key out of the block. What is
    recovered is `identity.version_coerced_from` where the compile recorded one, falling back to
    `identity.version` — the pre-coercion string, because re-emitting the coerced one gives the next
    compile nothing to coerce and `version_coerced_from` then goes absent on lap 2, which is a module
    disagreeing with its own round trip on a published field.

    `genome_build` is **not** in that class, even though it reaches the artifact the same way (the
    manifest, never a parquet column). A wrong title is cosmetic; a wrong build relocates every
    coordinate in the module. This used to be hardcoded `"GRCh38"`, so
    `compile → reverse → compile` on a `genome_build: GRCh37` module re-emitted it as GRCh38 and the
    recompile minted `ga4gh:VA.…` ids — GRCh38 allele identities for GRCh37 positions — moving
    `artifact.digest` and asserting a variant at a base the module never named. Resolution order is
    therefore: this argument, else the artifact's own `manifest.json`, else `"GRCh38"` for a bare
    parquet directory that records nothing.

    `write_resolution` (default True) also emits `resolution.csv` — the resolved facts recovered from
    the artifact — so `reverse → compile` reproduces the identical `artifact.digest` with **no network
    and no Ensembl reference** (Principle 7 hardened from reference-dependent to self-contained). A
    coord-keyed row's resolved rsid, dropped from `variants.csv`, is carried here and restored on
    recompile via `resolution.resolve_from_table`.

    The authored tables are written under their one legal name at the root. The machine-written
    sidecars go through `layout.sidecar_write_path`, so a fresh tree gets the **preferred** spelling
    (`licensing.csv`, not the deprecated `sources.csv` `_FACT_TABLES` still names for its parquet) and
    an output directory that already carries a copy has that copy overwritten rather than joined by a
    second one. Reversing into a directory that already holds two copies of one sidecar raises
    `layout.SidecarCollision`: which of two hand-editable claims to overwrite is not something this
    function may decide silently."""
    parquet_dir = Path(parquet_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # SNP core is optional (RM2): a module may have no weights.parquet.
    weights_path = parquet_dir / "weights.parquet"
    weights_df = pl.read_parquet(weights_path) if weights_path.is_file() else None

    # Every sidecar destination is resolved BEFORE the first write, and only for the tables this
    # artifact will actually produce. `sidecar_write_path` raises on an output directory that already
    # holds two copies of one table, and resolving late would raise it *after* `module_spec.yaml` and
    # the authored CSVs had been rewritten — a refusal that leaves a half-rebuilt spec behind. The
    # collision is refused with nothing touched instead, which is what the rest of this layout does.
    sidecar_paths: dict[str, Path] = {
        csv_name: sidecar_write_path(output_dir, csv_name)
        for csv_name, parquet_name, _ in _FACT_TABLES
        if (parquet_dir / parquet_name).is_file()
    }
    # Not `and weights_df is not None`: since RM43 the lookup table is rebuilt from the positional
    # parquets too, so a table-only module emits one and needs its path resolved the same way. The
    # writer itself returns before creating a file when there is nothing to write, so resolving the
    # path unconditionally cannot leave an empty `resolution.csv` behind.
    if write_resolution:
        sidecar_paths["resolution.csv"] = sidecar_write_path(output_dir, "resolution.csv")

    if module_name is None:
        module_name = _module_name_from_parquets(parquet_dir) or parquet_dir.name
    if genome_build is None:
        genome_build = _genome_build_from_artifact(parquet_dir) or "GRCh38"
    if version is None:
        version = _authored_version_from_artifact(parquet_dir)

    # **The attestation cannot be carried, and the silence about that was the defect (RM45).**
    # `verification.json` records checks the *enricher* put against sources this tier cannot reach,
    # and it is bound to the authored bytes by a hash — so reverse has nothing to rebuild it from and
    # must not invent one. What it can do is say so: without this line a module round-trips into a
    # spec that recompiles to a manifest with no `verification` block at all, and
    # `manifest.compilation.warnings` — a surface consumers parse (RM44) — differs between a module
    # and its own round trip with nothing edited. Losing a record of what was checked is acceptable;
    # losing it invisibly is the S16 silent-success shape.
    dropped_verification = _artifact_verification(parquet_dir)
    if dropped_verification is not None:
        logger.warning(_verification_loss_notice(dropped_verification), output_dir)

    default_curator = "unknown"
    default_method = "unknown"
    # `priority` is intentionally NOT defaulted. It is Optional with no `Defaults.priority` fallback
    # ('ai-module-creator'/'literature-review' back curator/method, but priority defaults to None),
    # so a null priority is *authored-absent*. Inferring a default from the mode would fabricate a
    # value for rows that never set one — turning weights `['high', None]` into `['high', 'high']`
    # on recompile (a Principle 7 idempotency break). It is written verbatim, per row, instead.
    default_priority: str | None = None
    if weights_df is not None:
        default_curator = _most_common(weights_df, "curator") or "unknown"
        default_method = _most_common(weights_df, "method") or "unknown"

    defaults_dict: dict[str, Any] = {"curator": default_curator, "method": default_method}

    module_block: dict[str, Any] = {
        "name": module_name,
        "title": title or module_name.replace("_", " ").title(),
        "description": description or f"Annotation module: {module_name}",
        "report_title": report_title or module_name.replace("_", " ").title(),
        "icon": icon,
        "color": color,
    }
    if version is not None:
        module_block["version"] = version
    spec = {
        "schema_version": "1.0",
        "module": module_block,
        "defaults": defaults_dict,
        "genome_build": genome_build,
    }
    (output_dir / "module_spec.yaml").write_text(
        yaml.dump(spec, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )

    # variants.csv + studies.csv only when the module has them.
    if weights_df is not None:
        ann_lookup: dict[tuple, dict[str, str]] = {}
        ann_key_columns: tuple[str, ...] = ()
        ann_path = parquet_dir / "annotations.parquet"
        if ann_path.exists():
            ann_df = pl.read_parquet(ann_path)
            # Which columns follow `variant_key` in this artifact's annotation key, read off the
            # artifact rather than assumed — three generations of the table are in the wild and each
            # keyed differently: 0.6 on (variant_key, genotype, conclusion, negatives) (RM80), 0.5 on
            # the variant-effect pair, and the oldest on variant_key alone. Detected once and used by
            # both the lookup and the weights-side probe, so the two cannot key differently.
            # Order is fixed here, not by column order in the parquet, or the two sides could agree
            # on the members and disagree on the tuple.
            ann_key_columns = tuple(
                name for name in ("genotype", "conclusion", "negatives") if name in ann_df.columns
            )
            for row in ann_df.iter_rows(named=True):
                # variant_key so position-only variants (rsid null) match; fall back to rsid for an
                # older artifact compiled before the variant_key column existed.
                base = row.get("variant_key") or row.get("rsid")
                if base is None:
                    continue
                key = (base, *(row.get(name) for name in ann_key_columns))
                ann_lookup[key] = {
                    "gene": row.get("gene", ""),
                    "phenotype": row.get("phenotype", ""),
                    "category": row.get("category", ""),
                }
        _write_variants_csv(
            weights_df,
            ann_lookup,
            ann_key_columns,
            default_curator,
            default_method,
            default_priority,
            output_dir / "variants.csv",
            genome_build=genome_build,
        )
    studies_path = parquet_dir / "studies.parquet"
    if studies_path.exists():
        _write_studies_csv(pl.read_parquet(studies_path), output_dir / "studies.csv")

    # 0.4 table kinds (RM1): each present parquet → its authored CSV.
    positional_frames: list[tuple[str, pl.DataFrame]] = []
    for csv_name, parquet_name, model in _TABLE_KINDS:
        kind_path = parquet_dir / parquet_name
        if kind_path.is_file():
            kind_df = pl.read_parquet(kind_path)
            _write_table_csv(kind_df, model, output_dir / csv_name)
            if csv_name in {name for name, _model in _POSITIONAL_TABLE_KINDS}:
                positional_frames.append((csv_name, kind_df))

    # `resolution.csv` last, because it is rebuilt from everything above. It is written from the SNP
    # core **and** the positional tables since 0.6 (RM43): once the compiler fills a resolved
    # coordinate into `pharm_variants`/`haplotypes`/`heteroplasmy`, a reverse that dropped the lookup
    # table would emit a spec whose recompile leaves those parquets unfilled — so `compile → reverse →
    # compile` would stop reproducing the artifact, which is Principle 7.
    # Through `sidecar_paths`, never `output_dir / "resolution.csv"` — the literal join RM51 abolishes.
    # Worth spelling out because the two halves of this arrived in different lanes and nearly cancelled:
    # RM43 *moved* this call out of the `weights_df is not None` block so a table-only module emits one,
    # while RM51's repair was applied to the call site at its old address. Taking either side of that
    # merge alone loses the other.
    if write_resolution:
        _write_resolution_csv(
            weights_df,
            positional_frames,
            sidecar_paths["resolution.csv"],
            genome_build=genome_build,
        )

    # 0.5 derived-fact sidecars: same round-trip, minus the columns that are recomputed rather than
    # stored. `_write_table_csv` drops any parquet column the model does not declare, so
    # `allele_frequency` (derived on write, absent from `FrequencyRow`'s fields) falls away by
    # construction rather than by a special case — re-deriving it on the next compile reproduces the
    # identical parquet.
    #
    # The filename comes from `sidecar_paths` (resolved above), not `output_dir / csv_name`: `_FACT_TABLES`
    # names the licence table by its *deprecated* spelling (the parquet and the manifest key keep it,
    # since only a major may rename those), so joining that name on by hand emitted `sources.csv` and
    # made `compile → reverse → compile` deprecation-warn on a module whose own compile is silent —
    # and `manifest.compilation.warnings` is a published field (RM44), so the module and its own round
    # trip disagreed on it. This is the same "write to the file you read" rule every other writer
    # follows rather than an exception to it: reverse builds a spec tree from an artifact, so on a
    # fresh directory there is nothing to follow and the rule yields the preferred spelling, while
    # reversing over a tree that already carries the old name (or a `derived/` split) overwrites that
    # copy instead of leaving a second one behind — which is the collision the rule exists to prevent.
    for csv_name, parquet_name, model in _FACT_TABLES:
        fact_path = parquet_dir / parquet_name
        if fact_path.is_file():
            _write_table_csv(pl.read_parquet(fact_path), model, sidecar_paths[csv_name])

    # The authored overlay (RM124), at the spec **root** and under its one legal name — it is authored
    # like `variants.csv`, not a machine-written sidecar, so it does not go through `sidecar_paths`.
    #
    # **This emits the post-overlay derived tables above AND the overlay, so the overlay applies
    # twice, and that is the design rather than an oversight.** The alternative — emitting the
    # *pre*-overlay tables so the apply happens exactly once — needs the overlay to record the value
    # it replaced, which is a derived cell inside an authored table and rots the moment the source
    # moves. All three operations are idempotent set operations instead (an update to a value already
    # present, an insert of a row already keyed, a suppress of a row already absent are each a
    # no-op), so the second lap is a fixed point and buys the round trip at no schema cost. It is
    # checked by test, never assumed — Principle 7 requires that of every derivation.
    overlay_parquet = parquet_dir / OVERRIDES_PARQUET
    if overlay_parquet.is_file():
        _write_table_csv(pl.read_parquet(overlay_parquet), OverrideRow, output_dir / OVERRIDES_CSV)

    return output_dir


def _write_resolution_csv(
    weights_df: pl.DataFrame | None,
    positional: list[tuple[str, pl.DataFrame]],
    output_path: Path,
    genome_build: str = "GRCh38",
) -> None:
    """Emit `resolution.csv` from the compiled artifact — the resolved facts, so `reverse → compile`
    is fully offline (no Ensembl reference, no network).

    Each *positioned* weights row yields one `ResolutionRow` keyed by its frozen `variant_key`,
    carrying the resolved rsid (which `variants.csv` drops on a coord-keyed row). On recompile,
    `resolution.resolve_from_table` restores that rsid and reproduces the identical `artifact.digest`.
    Rows without a resolved position (a best-effort partial) carry no fact and are skipped. Emitted in
    the weights' authored order; `resolution_signature` is order-independent regardless. `fetched_at`
    is left blank (no wall-clock is read here, keeping the emit deterministic).

    **The positional tables are a second source, and that is forced rather than chosen (RM43).** Since
    0.6 the compiler fills a resolved coordinate into `pharm_variants`/`haplotypes`/`heteroplasmy`, so
    a reverse that rebuilt this table from `weights.parquet` alone would hand back a spec whose
    recompile leaves those parquets unfilled — `compile → reverse → compile` would stop reproducing
    the artifact, breaking Principle 7. A PGx module carries no `weights.parquet` at all, and it is
    exactly the module this matters most for.

    Two ordering rules hold the two sources together, both borrowed from `enrich._collect_subjects`
    rather than invented here:

    * **weights first, and a key it emitted is never re-emitted.** `variants.csv` is the only table
      carrying `alts` as an authored fact, so letting a PGx row win would change what the table says
      about an allele — the same hazard that ordering exists to avoid one tier up.
    * **one row per key from the positional side.** These tables are never expanded, so a key names
      exactly one locus there; emitting a second row under one key would read back as a one-to-many
      rsID and send the next compile into the expansion path.

    **Reverse emits facts and discards provenance, deliberately and completely.** `source` becomes
    `reversed`, `status` becomes `resolved`, `fetched_at` empties — and the provenance-only columns
    (`rsid_alternates`, `rsid_current`, `rsid_status`, `vrs_id`, `caid`) are simply not written. This
    was once filed as a bug about `rsid_alternates` specifically; it is not one, and it is not fixable
    here. Those columns are **outside** the fact set precisely so they stay out of `weights.parquet`,
    so the information does not exist in the artifact this function reads — emitting the column names
    would produce a header with permanently empty cells and change nothing. Recovering an ambiguous
    candidate list after a round-trip means re-running the enricher, which is the correct place for it:
    the candidate list is a statement about a reference at a moment, not a property of the module.

    `authority` (RM33) joins that list for the same reason and one of its own: `source` is `reversed`
    here, and a reversed table's facts came out of parquet rather than from any licensed source, so
    there is no authority to name. The column is absent, loads as `None`, and contributes nothing to the
    compiler's `sources.csv` coherence check — which is the accurate statement.

    `genome_build` is the module's, and it reaches **both** the column and `derive_variant_key`. Getting
    only the column right is not enough and was the first shape of this fix: the key is minted from
    `(chrom, start, ref, alts)`, so on a GRCh37 module the default build produced a `ga4gh:VA.…` — a
    GRCh38 allele identity — on a row whose own `genome_build` cell said `GRCh37`. The row contradicted
    itself, and since `resolve_from_table` joins on `variant_key`, it also silently matched nothing on
    recompile."""
    fieldnames = [
        "variant_key",
        "rsid",
        "chrom",
        "start",
        "ref",
        "alts",
        "genome_build",
        "locus_index",
        "source",
        "status",
        "fetched_at",
    ]
    # A one-to-many rsid contributes N rows under ONE authored key, so `locus_index` counts within
    # that key — matching what the enricher writes and what `resolve_from_table` expects to read back.
    # Keying these on the per-locus `variant_key` instead (as this writer used to) left the re-emitted
    # table unjoinable to the collapsed authored row, and `resolution_signature` moved across the
    # round-trip.
    seen_rows: set[tuple] = set()
    locus_counter: dict[str, int] = {}
    #: The ordinals already written under each key — see `_reverse_locus_index`.
    emitted_indices: dict[str, set[int]] = {}
    emitted: list[dict[str, object]] = []

    for row in weights_df.iter_rows(named=True) if weights_df is not None else ():
        chrom, start = row.get("chrom"), row.get("start")
        if chrom is None or start is None:
            continue
        alts_list = row.get("alts")
        alts_cell = ",".join(alts_list) if alts_list else None
        resolution_key = _resolution_key(row, chrom, start, alts_cell, genome_build)
        # One authored row may appear several times in weights (one per genotype); the resolved
        # fact is the same each time, so emit it once.
        fact = (resolution_key, row.get("rsid"), chrom, start, row.get("ref"), alts_cell)
        if fact in seen_rows:
            continue
        seen_rows.add(fact)
        # The counter is maintained unconditionally even when the stored column answers, because the
        # positional pass below uses **membership** in it to enforce weights-first: a key this pass
        # emitted must never be re-emitted from a PGx table. Only the number written out switches.
        locus_counter[resolution_key] = locus_counter.get(resolution_key, 0) + 1
        emitted.append(
            _resolution_record(
                row,
                resolution_key,
                chrom,
                start,
                alts_cell,
                _reverse_locus_index(row, resolution_key, emitted_indices),
                genome_build,
            )
        )

    for _csv_name, table_df in positional:
        for row in table_df.iter_rows(named=True):
            chrom, start = row.get("chrom"), row.get("start")
            if chrom is None or start is None:
                continue
            alts_cell = row.get("alts") or None
            # The **stored** key here, unlike the weights pass above, and the difference is not a
            # shortcut. These tables are never expanded, so the stamped column already *is* the
            # authored-subset key — and it is the only place the model's own alts policy lives:
            # `PharmVariantRow`/`HaplotypeRow` key without `alts` while `HeteroplasmyRow` keys with
            # it, which no recomputation here can know. Recomputing filed a coordinate-authored pharm
            # fact under a `ga4gh:VA.…` the fill then never looked up, so the recompile left the row
            # unfilled and `resolution_signature` moved. The fallback covers a pre-0.6 parquet.
            resolution_key = row.get("variant_key") or _resolution_key(
                row, chrom, start, alts_cell, genome_build
            )
            if resolution_key in locus_counter:
                continue
            locus_counter[resolution_key] = 1
            emitted.append(_resolution_record(row, resolution_key, chrom, start, alts_cell, 0, genome_build))

    # A module that resolved nothing anywhere gets no file — writing a header-only `resolution.csv`
    # into a reversed spec that never had one would invent a derived sidecar (and a `manifest.derived`
    # entry) out of an absence. A module with a `weights.parquet` keeps the pre-0.6 behaviour of
    # always writing, so nothing that already round-trips changes shape.
    if weights_df is None and not emitted:
        return
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in emitted:
            writer.writerow(record)


def _reverse_locus_index(row: dict[str, Any], resolution_key: str, emitted: dict[str, set[int]]) -> int:
    """The `locus_index` a re-emitted `resolution.csv` row gets: the stored one, else encounter order.

    **Prefer the stored column (RM87), keep the recompute for a pre-0.6 artifact.** `weights.parquet`
    has carried `locus_index` since 0.6 and it is the compiler's own answer; an artifact compiled
    before the column existed has nothing to read, and Principle 3 requires it to keep reversing. On
    every reference example the two agree — pinned by reversing each expanding module twice, once with
    the column and once with it stripped — which is also what pins the sort dependency the recompute
    silently relies on.

    **Uniqueness is the guard, and it is not theoretical.** `ResolutionRow`'s own contract is several
    rows sharing a `variant_key` with *distinct* `locus_index`, and `locus_index` is inside
    `RESOLUTION_FACT_FIELDS`, so a duplicate is a malformed signed fact rather than a cosmetic slip.
    Unconditional prefer-stored can produce one: the stamp counts within a single authored row's
    hostable set, so two authored genotypes at one key that reach *different* sets — reachable only in
    `best_effort`, since dropping a locus appends a strict error — number the same locus differently,
    and this pass emits each locus once. The reproduced case is four loci where one genotype rejects
    one of them: the second genotype's surviving locus arrives carrying an ordinal the first genotype
    already spent.

    So a stored value is taken when it is free under this key and the smallest unused ordinal
    otherwise. That keeps the table well-formed, which is all it can do: in that case *no* numbering
    lines every weights row up with a table row, because one locus genuinely holds two ordinals in the
    artifact and the table has a single row for it. The clean case — every corpus module, and every
    module under `strict` — is byte-identical to what the counter alone produced.
    """
    used = emitted.setdefault(resolution_key, set())
    stored = row.get("locus_index")
    index = int(stored) if stored is not None and int(stored) not in used else _smallest_free(used)
    used.add(index)
    return index


def _smallest_free(used: set[int]) -> int:
    """The lowest non-negative integer not in `used` — encounter order, with the holes filled."""
    index = 0
    while index in used:
        index += 1
    return index


def _resolution_key(
    row: dict[str, Any],
    chrom: str,
    start: int,
    alts_cell: str | None,
    genome_build: str,
) -> str:
    """The key a reversed `resolution.csv` row is filed under: the identity the AUTHOR wrote.

    Recomputed from `authored_ident` rather than read off the parquet's own `variant_key`, because on
    the weights side those two differ exactly where it matters: a one-to-many rsID expansion re-keys
    each emitted row onto its own locus, so the stored key names a locus while the injected table
    named the rsID. Reading the stored column there would file N rows under N keys and leave the
    collapsed authored row joining to none of them.

    Falls back to the stored key, then to a fresh derivation, for an artifact compiled before
    `authored_ident` existed.
    """
    if (authored := row.get("authored_ident")) is not None:
        authored_set = set(authored)
        return derive_variant_key(
            row.get("rsid") if "rsid" in authored_set else None,
            chrom if "chrom" in authored_set else None,
            start if "start" in authored_set else None,
            row.get("ref") if "ref" in authored_set else None,
            alts_cell if "alts" in authored_set else None,
            build=genome_build,
        )
    return row.get("variant_key") or derive_variant_key(
        row.get("rsid"), chrom, start, row.get("ref"), alts_cell, build=genome_build
    )


def _resolution_record(
    row: dict[str, Any],
    resolution_key: str,
    chrom: str,
    start: int,
    alts_cell: str | None,
    locus_index: int,
    genome_build: str,
) -> dict[str, object]:
    """One re-emitted `resolution.csv` row. Shared by the weights and positional passes so the two
    sources cannot render the same fact two ways."""
    return {
        "variant_key": resolution_key,
        "rsid": _scalar_cell(row.get("rsid")),
        "chrom": _scalar_cell(chrom),
        "start": _scalar_cell(start),
        "ref": _scalar_cell(row.get("ref")),
        "alts": alts_cell or "",
        # The module's own declared build, not a constant. A GRCh37 module's facts were being
        # written out labelled GRCh38 — a coordinate relabelled onto an assembly where it names a
        # different base. `resolve_from_table` filters rows on this column, so the wrong label also
        # made a reversed table unjoinable.
        "genome_build": genome_build,
        "locus_index": locus_index,
        "source": "reversed",
        "status": "resolved",
        "fetched_at": "",
    }


def _most_common(df: pl.DataFrame, col: str) -> str | None:
    """Return the most common non-null value in a column, or None.

    On a tie, polars `mode()` gives no ordering guarantee (its result order is unstable even
    call-to-call), so the smallest value is picked deterministically — otherwise `reverse_module`'s
    inferred curator/method default (hence which rows emit a blank vs an explicit value) would vary
    run-to-run for the same artifact."""
    if col not in df.columns:
        return None
    non_null = df[col].drop_nulls()
    if non_null.len() == 0:
        return None
    return min(non_null.mode().to_list())


def _write_variants_csv(
    weights_df: pl.DataFrame,
    ann_lookup: dict[tuple, dict[str, str]],
    ann_key_columns: tuple[str, ...],
    default_curator: str,
    default_method: str,
    default_priority: str | None,
    output_path: Path,
    genome_build: str = "GRCh38",
) -> None:
    """Write variants.csv from weights parquet + annotations lookup.

    `genome_build` reaches `derive_variant_key` below for the same reason it does in
    `_write_resolution_csv`: the key is minted from the coordinate, so the default would mint a GRCh38
    `ga4gh:VA.…` for a row on another assembly. Here it decides only which artifact rows collapse into
    one authored row, so a wrong build mis-groups rather than mislabels — still wrong, and wrong in a
    way that shows up as a lost or duplicated row rather than as a bad cell."""
    fieldnames = [
        "rsid",
        "chrom",
        "start",
        "ref",
        "alts",
        "genotype",
        "weight",
        "state",
        "conclusion",
        "negatives",
        "priority",
        "gene",
        "phenotype",
        "category",
        "clinvar",
        "pathogenic",
        "benign",
        "curator",
        "method",
        # 0.3 additive columns
        "direction",
        "stat_significance",
        "effect_size",
        "effect_measure",
        "effect_allele",
        "flags",
        "trait_efo_id",
        "clin_sig",
        # 0.4 general annotation axes
        "requires_callable",
        "acmg_sf",
        "actionability",
        # 0.5 general annotation axis
        "callable_from",
        # 0.5.1 general annotation axes (RM29a)
        "quality_from",
        "min_quality",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        emitted_authored_keys: set[str] = set()
        for row in weights_df.iter_rows(named=True):
            raw_rsid = row.get("rsid")
            variant_key = row.get("variant_key")
            # `authored_ident` records which identity columns the author actually wrote, so reverse
            # re-emits that exact shape rather than whatever resolution filled in. This is what keeps
            # `content_signature` stable across a round-trip, and it is only safe because the key is
            # canonical: a VRS allele id identifies the row without the coordinate having to be
            # written into `variants.csv`, so dropping the resolved coordinate loses nothing.
            authored = row.get("authored_ident")
            if variant_key is None:
                # Pre-0.4 artifact with no frozen-key column: recompute it so the annotation lookup
                # below still joins. Independent of `authored_ident` — an artifact can carry one
                # without the other, and losing the join silently blanked every annotation column.
                variant_key = derive_variant_key(raw_rsid, row.get("chrom"), row.get("start"), row.get("ref"))
            if authored is not None:
                authored_set = set(authored)
                # An expanded one-to-many rsid is N artifact rows sharing ONE authored row. Emit it
                # once — writing N rows would fabricate per-locus annotations the author never made,
                # and the genotype can only be true of one of them.
                authored_key = derive_variant_key(
                    raw_rsid if "rsid" in authored_set else None,
                    row.get("chrom") if "chrom" in authored_set else None,
                    row.get("start") if "start" in authored_set else None,
                    row.get("ref") if "ref" in authored_set else None,
                    ",".join(row.get("alts") or []) if "alts" in authored_set else None,
                    build=genome_build,
                )
                dedupe_key = (
                    authored_key,
                    row.get("conclusion"),
                    row.get("negatives"),
                    tuple(row.get("genotype") or ()),
                )
                if dedupe_key in emitted_authored_keys:
                    continue
                emitted_authored_keys.add(dedupe_key)
            elif row.get("variant_key") is None:
                # No shape recorded and no frozen key: the prior (non-restoring) behaviour is the only
                # safe read — emit whatever the artifact holds.
                authored_set = (
                    {"rsid", "chrom", "start", "ref", "alts"}
                    if raw_rsid
                    else {"chrom", "start", "ref", "alts"}
                )
            else:
                # 0.5 artifact predating `authored_ident`: the frozen key is the only signal, so keep
                # the previous rule (rsid-keyed → rsid authored; anything else → position-only).
                authored_set = (
                    {"rsid"}
                    if (raw_rsid is not None and variant_key == raw_rsid)
                    else {"chrom", "start", "ref", "alts"}
                )
            emit_rsid = raw_rsid or "" if "rsid" in authored_set else ""
            genotype_list = row.get("genotype", [])
            curator = row.get("curator", "")
            method = row.get("method", "")
            priority = row.get("priority")
            # Reconstruct the genotype string. The `phased` bit (materialized alongside the allele
            # list) tells us which separator to re-emit: a phased pair keeps its order and joins with
            # '|'; an unphased pair is re-emitted alphabetically sorted with '/'; a single allele
            # (hemizygous / homoplasmic) passes through. Lossless round-trip (ROADMAP 0.3 item 5b).
            #
            # Runs **before** the annotation probe because since RM80 the genotype is part of that
            # key, and `weights.parquet` stores the allele list rather than the authored cell — so
            # the string has to be rebuilt before it can be joined on.
            if genotype_list and len(genotype_list) == 2:
                if row.get("phased"):
                    genotype_str = "|".join(genotype_list)
                else:
                    genotype_str = "/".join(sorted(genotype_list))
            else:
                genotype_str = "/".join(genotype_list) if genotype_list else ""
            # Probe the annotation on the same key the table was built with, whichever generation of
            # the table this artifact carries (see `ann_key_columns` at the call site).
            ann_probe = {
                "genotype": genotype_str,
                "conclusion": row.get("conclusion"),
                "negatives": row.get("negatives"),
            }
            ann = ann_lookup.get((variant_key, *(ann_probe[n] for n in ann_key_columns)), {})
            alts_list = row.get("alts")
            writer.writerow(
                {
                    # Each identity column is emitted only if the author wrote it. A resolved
                    # coordinate belongs in `resolution.csv`, not in `variants.csv` — putting it back
                    # here is what used to move `content_signature` on every rsid-authored module.
                    "rsid": emit_rsid,
                    "chrom": _scalar_cell(row.get("chrom")) if "chrom" in authored_set else "",
                    "start": _scalar_cell(row.get("start")) if "start" in authored_set else "",
                    "ref": _scalar_cell(row.get("ref")) if "ref" in authored_set else "",
                    "alts": (",".join(alts_list) if alts_list and "alts" in authored_set else ""),
                    "genotype": genotype_str,
                    "weight": _scalar_cell(row.get("weight")),
                    "state": _scalar_cell(row.get("state")),
                    "conclusion": _scalar_cell(row.get("conclusion")),
                    "negatives": _scalar_cell(row.get("negatives")),
                    # priority/curator/method: blank when equal to the inferred default (so a
                    # recompile re-applies the default), else the explicit value.
                    "priority": priority if priority != default_priority else "",
                    "gene": ann.get("gene", ""),
                    "phenotype": ann.get("phenotype", ""),
                    "category": ann.get("category", ""),
                    # Tri-state (True/False/None → true/false/empty), so an authored False survives.
                    "clinvar": _scalar_cell(row.get("clinvar")),
                    "pathogenic": _scalar_cell(row.get("pathogenic")),
                    "benign": _scalar_cell(row.get("benign")),
                    "curator": curator if curator != default_curator else "",
                    "method": method if method != default_method else "",
                    "direction": _scalar_cell(row.get("direction")),
                    "stat_significance": _scalar_cell(row.get("stat_significance")),
                    "effect_size": _scalar_cell(row.get("effect_size")),
                    "effect_measure": _scalar_cell(row.get("effect_measure")),
                    "effect_allele": _scalar_cell(row.get("effect_allele")),
                    "flags": _list_cell(row.get("flags")),
                    "trait_efo_id": _scalar_cell(row.get("trait_efo_id")),
                    "clin_sig": _scalar_cell(row.get("clin_sig")),
                    # 0.4 axes: Optional bools are tri-state (True/False/None → true/false/empty).
                    "requires_callable": _scalar_cell(row.get("requires_callable")),
                    "acmg_sf": _scalar_cell(row.get("acmg_sf")),
                    "actionability": _scalar_cell(row.get("actionability")),
                    "callable_from": _scalar_cell(row.get("callable_from")),
                    "quality_from": _scalar_cell(row.get("quality_from")),
                    "min_quality": _scalar_cell(row.get("min_quality")),
                }
            )


def _write_studies_csv(studies_df: pl.DataFrame, output_path: Path) -> None:
    """Write studies.csv from studies parquet."""
    fieldnames = [
        "rsid",
        "chrom",
        "start",
        "ref",
        "pmid",
        "population",
        "p_value",
        "conclusion",
        "study_design",
        # 0.3 additive columns, plus `effect_allele` (RM91, 0.6) beside the magnitude it qualifies.
        # This list is the third of `@three-touch-points` and the one that gets missed: a column
        # absent here reaches the parquet and then vanishes on reverse, which fails P7 silently.
        # **This writer has a FOURTH, and it is worse than the third** (found adding `curator`, S55):
        # the row dict below. Naming a column here and not there writes the *header* with an empty
        # cell on every row — `DictWriter` fills a missing key silently — so the reversed spec looks
        # right, re-validates, and loses the value. The digest fixed-point assertion is what catches
        # it; a column-presence check does not.
        "stat_significance",
        "effect_size",
        "effect_measure",
        "effect_allele",
        "trait_efo_id",
        # 0.7: which analysis produced `p_value`/`effect_size` (RM140, S75)
        "statistical_test",
        # 0.7: the citing source's own confidence in this link, and the instrument it is on (RM160)
        "confidence",
        "confidence_unit",
        # 0.4 provenance columns (RM11/RM12, from the 0.5 scope), and 0.6's locator beside them (S55)
        "doi",
        "provenance_quote",
        "provenance_regex",
        "curator",
        # 0.5: the authored numeric p-value. `neg_log10_p` is deliberately absent — it is derived on
        # write, so re-emitting it would author a value the next compile recomputes anyway.
        "p_value_num",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in studies_df.iter_rows(named=True):
            pmid = row.get("pmid")
            if pmid is None or str(pmid).strip() == "":
                continue
            writer.writerow(
                {
                    "rsid": _scalar_cell(row.get("rsid")),
                    # Position columns so a position-only study row (rsid null) keeps an identifier.
                    "chrom": _scalar_cell(row.get("chrom")),
                    "start": _scalar_cell(row.get("start")),
                    "ref": _scalar_cell(row.get("ref")),
                    "pmid": str(pmid).strip(),
                    "population": _scalar_cell(row.get("population")),
                    "p_value": _scalar_cell(row.get("p_value")),
                    "conclusion": _scalar_cell(row.get("conclusion")),
                    "study_design": _scalar_cell(row.get("study_design")),
                    "stat_significance": _scalar_cell(row.get("stat_significance")),
                    "effect_size": _scalar_cell(row.get("effect_size")),
                    "effect_measure": _scalar_cell(row.get("effect_measure")),
                    "effect_allele": _scalar_cell(row.get("effect_allele")),
                    "trait_efo_id": _scalar_cell(row.get("trait_efo_id")),
                    "statistical_test": _scalar_cell(row.get("statistical_test")),
                    "confidence": _scalar_cell(row.get("confidence")),
                    "confidence_unit": _scalar_cell(row.get("confidence_unit")),
                    "doi": _scalar_cell(row.get("doi")),
                    "provenance_quote": _scalar_cell(row.get("provenance_quote")),
                    "provenance_regex": _scalar_cell(row.get("provenance_regex")),
                    "curator": _scalar_cell(row.get("curator")),
                    "p_value_num": _scalar_cell(row.get("p_value_num")),
                }
            )
