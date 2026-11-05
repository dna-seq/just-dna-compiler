"""`reverse_module`: an artifact back to an authored spec directory, including `resolution.csv`."""

import csv
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import polars as pl
import yaml
from just_dna_format.base import derive_variant_key
from just_dna_format.integrity import sha256_file
from just_dna_format.layout import sidecar_relative_names, sidecar_write_path
from just_dna_format.manifest import (
    LOGO_EXTENSIONS,
    README_CANDIDATES,
    SCHEMA_VERSION,
    ModuleManifest,
    Verification,
    read_manifest,
)
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import join_vrs_ids

from just_dna_compiler.compiler.manifest import _log_left_behind_reason
from just_dna_compiler.compiler.parquets import RESOLUTION_LOCUS_FIELDS
from just_dna_compiler.compiler.positional import _POSITIONAL_TABLE_CSVS, _POSITIONAL_TABLE_KINDS
from just_dna_compiler.compiler.tables import (
    _FACT_TABLES,
    _PROVENANCE_FILE,
    _TABLE_KINDS,
    AUTHORED_NON_KIND_TABLES,
    _list_cell,
    _scalar_cell,
    _write_table_csv,
)
from just_dna_compiler.compiler.vrs_columns import resolution_key as _resolution_key

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


#: Every `module_spec.yaml` field `reverse_module` writes back, as a dotted path (RM241). A test walks
#: `ModuleSpecConfig`, `ModuleInfo` and `Defaults` and asserts their fields equal this set together
#: with `REVERSE_EXCLUDED`, so a new spec field fails the suite until somebody decides which side it
#: is on. Before this registry, each field reverse recovered had been added on its own after its own
#: incident (`version` by RM103, `genome_build` by the 2026-08-06 audit), and nothing said which of
#: the others were missing — the round trip dropped `weighting`, the display block, `license`,
#: `authorship`, `authority_precedence` and `panel` while both identity digests held.
REVERSE_RECONSTRUCTED: frozenset[str] = frozenset(
    {
        "schema_version",
        "genome_build",
        "panel",
        "authorship",
        "license",
        "weighting",
        "tier_scale",
        "authority_precedence",
        "module.name",
        "module.version",
        "module.title",
        "module.description",
        "module.report_title",
        "module.icon",
        "module.icon_set",
        "module.color",
        "defaults.curator",
        "defaults.method",
    }
)

#: The spec fields reverse does **not** write back, each with the reason (RM241).
REVERSE_EXCLUDED: dict[str, str] = {
    # The two blocks are walked field by field; the block itself is a container, not a value.
    "module": "a block: its fields are listed individually",
    "defaults": "a block: its fields are listed individually",
    "defaults.priority": (
        "the manifest carries no default priority, and `priority` is written verbatim per row "
        "instead, so every row keeps its value and no default is needed to reproduce it"
    ),
}


#: Every `manifest.json` field a `compile → reverse → compile` gives back unchanged (RM364), as a dotted
#: path with the `compilation` block walked one level down. RM241's registry above is about the spec;
#: this one is about everything the compile CARRIED, and a test walks `ModuleManifest` and `Compilation`
#: and asserts their fields equal this set together with `REVERSE_MANIFEST_EXCLUDED`. The round-trip
#: gates compare `reconstructed_projection` over exactly this set, so a field placed here is a field the
#: corpus sweep holds lap against lap. Before it, `provenance.json` and the shipped logs were hashed into
#: the manifest and left behind by reverse while the README and logo beside them came back.
REVERSE_MANIFEST_RECONSTRUCTED: frozenset[str] = frozenset(
    {
        "manifest_version",
        "schema_version",
        "identity",
        "display",
        "genome_build",
        "curator",
        "method",
        "license",
        "authority_precedence",
        "weighting",
        "tier_scale",
        "meta_selectors",
        "authorship",
        "panel",
        "stats",
        # The fact sidecars' summaries: each table is re-emitted from its parquet and re-summarized.
        "frequency",
        "gene_metrics",
        "gene_validity",
        "clinical_assertions",
        "gwas_effects",
        "expression_effects",
        "locus_to_gene",
        "colocalisations",
        "consequences",
        "ld_pairs",
        "literature",
        "clin_sig_concordance",
        "sources",
        "content_signature",
        "artifact",
        # The four files a compile ships beside the parquets, each copied back byte for byte after a
        # hash check against its record here.
        "readme",
        "logo",
        "logs",
        "provenance",
        "compilation.compile_success",
        "compilation.compiled_by",
        "compilation.compiler_version",
        "compilation.ensembl_reference",
        "compilation.resolution_mode",
        "compilation.fully_resolved",
        "compilation.resolution_subjects",
        "compilation.expanded_keys",
        "compilation.expanded_rows",
        # A fixed point for every row the table files under a subject the artifact carries: each variant
        # parquet holds those rows as `resolution_loci` (RM364). A row about a variant the module does
        # not carry has no row to ride on and still moves it; the round-trip matrix pins that case as
        # `table_says_more`, the one shape this entry does not cover.
        "compilation.resolution_signature",
        "compilation.vrs_alleles",
        "compilation.vrs_alleles_identified",
        "compilation.vrs_version",
        "compilation.positional_rows",
        "compilation.positional_rows_placed",
        "compilation.toolchain",
    }
)

#: The manifest fields a round trip does **not** give back unchanged, each with the reason (RM364).
REVERSE_MANIFEST_EXCLUDED: dict[str, str] = {
    "compilation": "a block: its fields are listed individually",
    "verification": (
        "the attestation document is not in the artifact and is bound to authored bytes reverse "
        "re-emits, so reverse says it is dropping it (`_verification_loss_notice`) instead"
    ),
    "signature": "a detached signature a registry puts over a published digest; no compile writes it",
    "owner": "stamped by a registry at publish; no compile writes it",
    "authors": "stamped by a registry at publish; no compile writes it",
    "created_at": "stamped by a registry at publish; no compile writes it",
    "published_at": "stamped by a registry at publish; no compile writes it",
    "inputs": (
        "raw byte hashes of the authored files, and reverse re-emits their values with column order "
        "and cell formatting normalized; the identity they carry is `content_signature`, held above"
    ),
    "derived": (
        "raw byte hashes of the sidecars, which reverse re-emits normalized and with provenance "
        "discarded, and `verification.json` among them; each table's identity is its fact signature"
    ),
    "compilation.compiled_at": "the wall-clock time of the compile, which a second compile cannot repeat",
    "compilation.warnings": (
        "the first lap's findings include the attestation and closure reverse drops, and those about "
        "the resolution provenance reverse stamps itself (`source`) or leaves to the enricher "
        "(`rsid_status`, `rsid_alternates`, `parquets.RESOLUTION_LOCUS_EXCLUDED`)"
    ),
    "compilation.carried": "derived from `compilation.warnings`, which is excluded for the reason it gives",
    "compilation.warnings_summary": "derived from `compilation.warnings`, which is excluded for the reason it gives",
    "compilation.dropped_rows": (
        "rows the first compile dropped never reach a parquet, so the recompile of the reversed spec "
        "has nothing left to drop; the drop is the first lap's to report"
    ),
    "compilation.resolution_sources": (
        "the `source` column of `resolution.csv`, provenance reverse replaces with `reversed` because "
        "the facts it re-emits came out of parquet rather than from any link"
    ),
}


def reconstructed_projection(manifest: ModuleManifest) -> dict[str, Any]:
    """Every `REVERSE_MANIFEST_RECONSTRUCTED` value of `manifest`, as JSON, keyed by its dotted path.

    What a round trip must hold equal, lap against lap. Public because both round-trip gates compare it
    and a second copy of the list is how RM241's hand-kept projection came to miss logs and provenance.
    """
    dumped = manifest.model_dump(mode="json")
    projection: dict[str, Any] = {}
    for path in sorted(REVERSE_MANIFEST_RECONSTRUCTED):
        value: Any = dumped
        for part in path.split("."):
            value = value[part]
        projection[path] = value
    return projection


def _artifact_manifest(parquet_dir: Path) -> ModuleManifest | None:
    """The artifact's own `manifest.json`, or `None` for a bare parquet directory or one this
    compiler cannot parse.

    **Tolerant on purpose.** Every value read from it is provenance or presentation, and a provenance
    failure must not stop a reverse; what the callers must not do is *invent* a value, which is why
    each has an explicit fallback for the `None` case rather than a default buried here.
    """
    path = parquet_dir / "manifest.json"
    if not path.is_file():
        return None
    try:
        return read_manifest(path)
    except (OSError, ValueError):
        return None


def _authored_version_from_artifact(parquet_dir: Path) -> str | None:
    """The `module.version` the author wrote, recovered from the artifact's own `manifest.json`.

    **`version_coerced_from` first, `version` second, and that order is the whole point (RM103).**
    `identity.version` holds the *coerced* SemVer, so re-emitting it would hand the next compile a
    string with nothing left to coerce — `version_coerced_from` would come back absent on lap 2, and a
    module would disagree with its own round trip on a published field. Preferring the pre-coercion
    string makes the field a fixed point: `v2` re-emits as `v2`, coerces to `2.0.0` again, and both
    manifest cells match lap 1.
    """
    manifest = _artifact_manifest(parquet_dir)
    if manifest is None:
        return None
    return manifest.identity.version_coerced_from or manifest.identity.version


def _genome_build_from_artifact(parquet_dir: Path) -> str | None:
    """Recover the module's declared `genome_build` from the artifact's own `manifest.json`.

    `genome_build` is authored `module_spec.yaml` metadata that reaches the artifact through the
    manifest and **no parquet column**, so this is the only place it survives a compile. Getting it
    wrong is not cosmetic — a coordinate is not absolute, so re-emitting a GRCh37 module as GRCh38
    makes the next compile mint a GRCh38 VRS allele id for a GRCh37 position, which is a *false
    content-addressed claim* rather than a lost label.
    """
    manifest = _artifact_manifest(parquet_dir)
    return manifest.genome_build if manifest is not None else None


def _artifact_verification(parquet_dir: Path) -> Verification | None:
    """The verification block reverse is about to drop, if the artifact carried one.

    Returns the block rather than a bool because **what is being lost decides what to say**. A
    document may carry checks, a closure (RM73), or both, and the remedies are different parties'
    jobs: re-running the enricher re-attests the checks, and only the author can close the module
    again. A single sentence naming the enricher was correct while checks were the only content and
    became a correct sentence aimed at the wrong defect the moment a closure could ride alone — which
    is now thirteen of the sixteen reference examples. That is the RM77 class, and the compile-side
    stale message already branches the same way.
    """
    manifest = _artifact_manifest(parquet_dir)
    return manifest.verification if manifest is not None else None


@dataclass(frozen=True)
class ShippedFile:
    """One file a compile copied into the artifact beside the parquets and recorded in the manifest."""

    #: Its path relative to the module directory, as the manifest records it.
    name: str
    #: The `sha256:` the manifest records for it, or `None` where the record carries none.
    sha256: str | None
    #: The manifest field that records it: `readme`, `logo`, `provenance` or `logs`.
    what: str


def shipped_files(manifest: ModuleManifest) -> list[ShippedFile]:
    """Every file `manifest` says the compile shipped beside the parquets, in a fixed order (RM364).

    The four kinds a compile collects from the spec directory and copies into the artifact: the README
    and logo (RM241), `provenance.json` and the logs. Reverse copies each one back, and the round-trip
    tests walk this list, so a fifth kind is one entry here rather than a third `what ==` arm.
    """
    files: list[ShippedFile] = []
    if manifest.readme is not None:
        files.append(ShippedFile(manifest.readme.name, manifest.readme.sha256, "readme"))
    if manifest.logo is not None:
        files.append(ShippedFile(manifest.logo.name, manifest.logo.sha256, "logo"))
    if manifest.provenance is not None and manifest.provenance.file is not None:
        files.append(ShippedFile(manifest.provenance.file, manifest.provenance.sha256, "provenance"))
    files.extend(ShippedFile(entry.name, entry.sha256, "logs") for entry in manifest.logs)
    return files


def _discovered(shipped: ShippedFile, destination: Path, output_dir: Path) -> bool:
    """Whether the next compile of `output_dir` finds `destination` on its own, without an explicit path.

    The compile's own discovery rule for each kind, read rather than restated: README and logo by their
    fixed names, provenance by `_PROVENANCE_FILE`, and a log by `_log_left_behind_reason` (the function
    discovery itself asks) under `logs/` or as a top-level `*.log`.
    """
    if shipped.what == "readme":
        return shipped.name in README_CANDIDATES
    if shipped.what == "logo":
        return shipped.name in {f"logo.{ext}" for ext in LOGO_EXTENSIONS}
    if shipped.what == "provenance":
        return shipped.name == _PROVENANCE_FILE
    parts = PurePosixPath(shipped.name).parts
    top_level_log = len(parts) == 1 and destination.suffix == ".log"
    under_logs = len(parts) > 1 and parts[0] == "logs"
    if not (top_level_log or under_logs):
        return False
    return _log_left_behind_reason(destination, output_dir / "logs", output_dir) is None


def _inside(root: Path, name: str) -> Path | None:
    """`root / name` when `name` is a relative path that stays inside `root`, else `None`.

    A manifest is read, not trusted: a recorded name of `../x.log` or `/etc/x` would otherwise have
    reverse read a file outside the artifact and write one outside the reversed spec."""
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        return None
    return root / Path(*pure.parts)


def _leaves_through_a_link(path: Path, root: Path) -> bool:
    """Whether `path`, or a directory between it and `root`, is a symlink (the read and write halves).

    The lexical check in `_inside` cannot see a link; resolving can. Asked of the source in the artifact
    and of the destination in the reversed spec, before either is opened."""
    resolved_root = root.resolve()
    current = path
    while current != root and current != current.parent:
        if current.is_symlink():
            return True
        current = current.parent
    return not path.resolve().is_relative_to(resolved_root)


def _copy_shipped_file(parquet_dir: Path, output_dir: Path, shipped: ShippedFile) -> None:
    """Copy a file the compile shipped beside the parquets back into the spec, byte for byte, after
    checking it against the manifest's record of it (RM241 for the README and logo, RM364 for
    `provenance.json` and the logs).

    The compile copies each one into the artifact and records its hash, so the bytes are there to be
    read; reverse used to leave them behind, and the recompile's manifest then had no record of them at
    all. A file whose hash disagrees with the record is **not** copied: it is not the file the manifest
    describes, and passing it on would let the next compile attest bytes nobody compiled. Neither is a
    name that leaves the module directory. A file under a name the compile does not discover on its own
    is copied and named, since the next compile needs it passed explicitly to pick it up.
    """
    source = _inside(parquet_dir, shipped.name)
    destination = _inside(output_dir, shipped.name)
    if source is None or destination is None:
        logger.warning(
            "The artifact's manifest records a %s named %r, which is not a path inside the module, so it "
            "was not copied into the reversed spec.",
            shipped.what,
            shipped.name,
        )
        return
    if _leaves_through_a_link(source, parquet_dir) or _leaves_through_a_link(destination, output_dir):
        logger.warning(
            "The artifact's manifest records a %s (%s) reached through a symlink, so it was not copied "
            "into the reversed spec: a link can read or write outside the module, and a compile never "
            "ships one.",
            shipped.what,
            shipped.name,
        )
        return
    if not source.is_file():
        logger.warning(
            "The artifact's manifest records a %s (%s) that is not in %s, so the reversed spec has none.",
            shipped.what,
            shipped.name,
            parquet_dir,
        )
        return
    if shipped.sha256 is None:
        logger.warning(
            "The artifact's manifest records a %s (%s) with no hash, so it was not copied into the "
            "reversed spec: nothing says these are the bytes that were compiled.",
            shipped.what,
            shipped.name,
        )
        return
    if sha256_file(source) != shipped.sha256:
        logger.warning(
            "The %s in %s (%s) does not match the hash its manifest records, so it was not copied into "
            "the reversed spec: it is not the file that was compiled.",
            shipped.what,
            parquet_dir,
            shipped.name,
        )
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if not _discovered(shipped, destination, output_dir):
        logger.warning(
            "The %s was copied as %s, a name the compiler does not discover on its own; pass it "
            "explicitly when compiling the reversed spec.",
            shipped.what,
            shipped.name,
        )


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
    icon: str | None = None,
    color: str | None = None,
    version: str | None = None,
    write_resolution: bool = True,
    genome_build: str | None = None,
) -> Path:
    """Reverse-engineer a parquet module back into the spec DSL (yaml + csv). Returns output_dir.

    **Every `module_spec.yaml` field the artifact carries is written back (RM241)**, and
    `REVERSE_RECONSTRUCTED` / `REVERSE_EXCLUDED` say which those are. The spec's metadata reaches the
    artifact through `manifest.json` and no parquet column: the `module:` block's display fields
    (`manifest.display`), `version` (`identity`), `genome_build`, the defaults' `curator`/`method`,
    `license`, `weighting`, `authorship`, `authority_precedence` and `panel`. The README and logo the
    compile shipped beside the parquets are copied back byte for byte, after a hash check against the
    manifest. Each value is taken in the same order: **an explicit argument, then the manifest, then
    the fallback** a bare parquet directory with no manifest has always had (name-derived titles,
    `database`/`#6435c9`, the most common row curator/method). `icon` and `color` default to `None` so
    "not passed" can be told apart from "passed the old default".

    `version` is recovered as `identity.version_coerced_from` where the compile recorded one, falling
    back to `identity.version` — the pre-coercion string, because re-emitting the coerced one gives the
    next compile nothing to coerce and `version_coerced_from` then goes absent on lap 2 (RM103).

    `genome_build` matters more than the rest. A wrong title is cosmetic; a wrong build relocates every
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

    manifest = _artifact_manifest(parquet_dir)
    if module_name is None:
        module_name = _module_name_from_parquets(parquet_dir) or parquet_dir.name
    if genome_build is None:
        genome_build = (manifest.genome_build if manifest is not None else None) or "GRCh38"
    if version is None and manifest is not None:
        version = manifest.identity.version_coerced_from or manifest.identity.version

    # **The attestation cannot be carried, and the silence about that was the defect (RM45).**
    # `verification.json` records checks the *enricher* put against sources this tier cannot reach,
    # and it is bound to the authored bytes by a hash — so reverse has nothing to rebuild it from and
    # must not invent one. What it can do is say so: without this line a module round-trips into a
    # spec that recompiles to a manifest with no `verification` block at all, and
    # `manifest.compilation.warnings` — a surface consumers parse (RM44) — differs between a module
    # and its own round trip with nothing edited. Losing a record of what was checked is acceptable;
    # losing it invisibly is the S16 silent-success shape.
    dropped_verification = manifest.verification if manifest is not None else None
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
    # The manifest records the spec's own `defaults.curator`/`method` (RM241). The row-mode guess is
    # the bare-directory fallback, and it was worse than lossy on a table-only module: with no
    # `weights.parquet` there are no rows to take a mode over, so a PGx module's defaults came back as
    # `unknown` and the recompiled manifest said so.
    if manifest is not None and manifest.curator is not None:
        default_curator = manifest.curator
    elif weights_df is not None:
        default_curator = _most_common(weights_df, "curator") or "unknown"
    if manifest is not None and manifest.method is not None:
        default_method = manifest.method
    elif weights_df is not None:
        default_method = _most_common(weights_df, "method") or "unknown"

    defaults_dict: dict[str, Any] = {"curator": default_curator, "method": default_method}

    display = manifest.display if manifest is not None else None
    fallback_title = module_name.replace("_", " ").title()
    module_block: dict[str, Any] = {
        "name": module_name,
        "title": title or (display.title if display else fallback_title),
        "description": description
        or (display.description if display else f"Annotation module: {module_name}"),
        "report_title": report_title or (display.report_title if display else fallback_title),
        "icon": icon or (display.icon if display else "database"),
        "color": color or (display.color if display else "#6435c9"),
    }
    if display is not None:
        module_block["icon_set"] = display.icon_set
    if version is not None:
        module_block["version"] = version
    spec: dict[str, Any] = {
        # The one value the spec model accepts, so writing the constant is reconstructing it.
        "schema_version": SCHEMA_VERSION,
        "module": module_block,
        "defaults": defaults_dict,
        "genome_build": genome_build,
    }
    # The advisory blocks, copied through from the manifest the compile copied them into, and each
    # written only when the module carried it, so a module without one reverses to a spec without one.
    if manifest is not None:
        if manifest.panel is not None:
            spec["panel"] = manifest.panel.model_dump(mode="json", exclude_none=True)
        if manifest.authorship:
            spec["authorship"] = [
                entry.model_dump(mode="json", exclude_none=True) for entry in manifest.authorship
            ]
        if manifest.license is not None:
            spec["license"] = manifest.license
        if manifest.weighting is not None:
            spec["weighting"] = manifest.weighting.model_dump(mode="json", exclude_none=True)
        if manifest.authority_precedence:
            spec["authority_precedence"] = list(manifest.authority_precedence)
        if manifest.tier_scale is not None:
            spec["tier_scale"] = manifest.tier_scale
    (output_dir / "module_spec.yaml").write_text(
        yaml.dump(spec, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    if manifest is not None:
        for shipped in shipped_files(manifest):
            _copy_shipped_file(parquet_dir, output_dir, shipped)

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
    studies_df: pl.DataFrame | None = pl.read_parquet(studies_path) if studies_path.exists() else None
    if studies_df is not None:
        _write_studies_csv(studies_df, output_dir / "studies.csv")

    # 0.4 table kinds (RM1): each present parquet → its authored CSV.
    positional_frames: list[tuple[str, pl.DataFrame]] = []
    for csv_name, parquet_name, model in _TABLE_KINDS:
        kind_path = parquet_dir / parquet_name
        if kind_path.is_file():
            kind_df = pl.read_parquet(kind_path)
            _write_table_csv(kind_df, model, output_dir / csv_name)
            if csv_name in _POSITIONAL_TABLE_CSVS:
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
    # RM364: a spec that carried no table gets none back. Rebuilding one from the authored cells a
    # first compile never resolved is a table the author never wrote: the second lap then reads it, and
    # its manifest publishes a `resolution_signature`, VRS coverage and expansion counts the first did not.
    if write_resolution and not _no_table_was_read(manifest, weights_df, positional_frames):
        _write_resolution_csv(
            weights_df,
            positional_frames,
            sidecar_paths["resolution.csv"],
            genome_build=genome_build,
            studies_df=studies_df,
            spec_carried_one=manifest is not None and _spec_carried_a_table(manifest),
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

    # The authored tables that are not table kinds (RM357), each at the spec **root** under its one legal
    # name, from the first of its parquets, which carries every authored cell verbatim. They are
    # authored like `variants.csv`, not machine-written sidecars, so none goes through `sidecar_paths`.
    # `_write_table_csv` writes the authored columns only, so what a compile derived beside them falls
    # away and the recompile derives it again: the meta-table's `members_key` and matches, and the whole
    # of `meta_resolved.parquet`, which has no CSV and is rebuilt from these rows and the tables they name.
    #
    # **The overlay: this emits the post-overlay derived tables above AND the overlay, so the overlay
    # applies twice, and that is the design rather than an oversight.** The alternative — emitting the
    # *pre*-overlay tables so the apply happens exactly once — needs the overlay to record the value
    # it replaced, which is a derived cell inside an authored table and rots the moment the source
    # moves. All three operations are idempotent set operations instead (an update to a value already
    # present, an insert of a row already keyed, a suppress of a row already absent are each a
    # no-op), so the second lap is a fixed point and buys the round trip at no schema cost. It is
    # checked by test, never assumed — Principle 7 requires that of every derivation.
    for table in AUTHORED_NON_KIND_TABLES:
        authored_parquet = parquet_dir / table.parquets[0]
        if authored_parquet.is_file():
            _write_table_csv(pl.read_parquet(authored_parquet), table.model, output_dir / table.csv)

    return output_dir


#: The authored tables whose resolved subjects `_write_resolution_csv` rebuilds `resolution.csv` rows from:
#: `variants.csv` through `weights.parquet`, the positional kinds through their own parquets.
RESOLUTION_SOURCE_TABLES: tuple[str, ...] = (
    "variants.csv",
    *(csv_name for csv_name, _model in _POSITIONAL_TABLE_KINDS),
    # A study's LD proxy (RM331), through `studies.parquet.proxy_loci`.
    "studies.csv",
)


#: The columns `_resolution_record` stamps itself on every reversed row rather than reading off a locus:
#: the key, the module's build, and the reverse link's own provenance (`RESOLUTION_LOCUS_EXCLUDED` says why
#: each is not carried).
_REVERSE_STAMPED: frozenset[str] = frozenset(
    {"variant_key", "genome_build", "source", "status", "fetched_at"}
)

#: The reversed `resolution.csv` header, in the model's column order: every column a locus carries plus
#: the stamped ones, derived rather than hand-kept so a carried column reaches the file (RM380).
REVERSED_RESOLUTION_FIELDS: tuple[str, ...] = tuple(
    name for name in ResolutionRow.model_fields if name in RESOLUTION_LOCUS_FIELDS or name in _REVERSE_STAMPED
)


def _write_resolution_csv(
    weights_df: pl.DataFrame | None,
    positional: list[tuple[str, pl.DataFrame]],
    output_path: Path,
    genome_build: str = "GRCh38",
    studies_df: pl.DataFrame | None = None,
    spec_carried_one: bool = False,
) -> None:
    """Emit `resolution.csv` from the compiled artifact — the resolved facts, so `reverse → compile`
    is fully offline (no Ensembl reference, no network).

    **Since RM364 a parquet carries the table's own rows** (`resolution_loci` on `weights.parquet` and the
    positional parquets, beside `proxy_loci`), and this writes those, keyed on the authored key, in the
    order below. Everything from here to the end of this docstring describes the rebuild from a row's
    cells, which is now the fallback for a parquet compiled before the column existed: it lost every
    table row the fill did not take and wrote the author's coordinate back as a resolution fact.

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

    Two ordering rules hold the two sources together, both borrowed from `enrich.collect_subjects`
    rather than invented here:

    * **weights first, and a key it emitted is never re-emitted.** `variants.csv` is the only table
      carrying `alts` as an authored fact, so letting a PGx row win would change what the table says
      about an allele — the same hazard that ordering exists to avoid one tier up.
    * **what the table said, where the parquet carries it (RM364).** Every variant parquet compiled
      since RM364 carries `resolution_loci`, the rows the table files under the row's authored key, and
      those are emitted as stored, several under one key where the table had several. That is not the
      expansion hazard: the rows ARE the table's, so the next compile reads the one-to-many it read the
      first time. The cell rebuild below is the fallback for an older parquet, and there a positional
      table contributes **one row per key**: those tables are never expanded, so a second row rebuilt
      from cells would invent a one-to-many the table never stated.

    **Reverse writes back every column a parquet's locus carries (RM380)**, which is every
    `ResolutionRow` column but the ones `parquets.RESOLUTION_LOCUS_EXCLUDED` names with a reason, and
    the header is derived from the same list (`REVERSED_RESOLUTION_FIELDS`). Outside a signature is not
    the same as dropped: `authority`, `placement_witness`/`placement_verdict`, `left_aligned`,
    `source_release`, `caid`, `authored_event`/`judged_coordinate` and the `vrs_id`/`vrs_spec` pair
    all come back, because the next compile reads several of them (`sources_in_use`, the placement
    check's withholds, the release reading) and a second lap reading a table that says less than the
    first reached different findings. Five columns reverse stamps itself: the key, the module's
    `genome_build`, `source` (`reversed`, the link that wrote this row), `status` (`resolved`) and an
    empty `fetched_at` (no clock is read, so the emit is deterministic). Three it leaves out:
    `rsid_alternates`, `rsid_current` and `rsid_status`, statements about a reference at a moment that
    re-running the enricher recovers (`@rsid-alternates-closed`). A row the cell rebuild writes (a
    parquet compiled before the carried column existed, or one whose loci the row's cells reproduce and
    which held no provenance) writes those columns empty, as before.

    `genome_build` is the module's, and it reaches **both** the column and `derive_variant_key`. Getting
    only the column right is not enough and was the first shape of this fix: the key is minted from
    `(chrom, start, ref, alts)`, so on a GRCh37 module the default build produced a `ga4gh:VA.…` — a
    GRCh38 allele identity — on a row whose own `genome_build` cell said `GRCh37`. The row contradicted
    itself, and since `resolve_from_table` joins on `variant_key`, it also silently matched nothing on
    recompile."""
    fieldnames = list(REVERSED_RESOLUTION_FIELDS)
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
        alts_list = row.get("alts")
        alts_cell = ",".join(alts_list) if alts_list else None
        if row.get("resolution_loci"):
            # RM364: the loci the table filed under the row's AUTHORED key, as the table stated them,
            # carried exactly where this row's own cells would not reproduce them. Every genotype row and
            # every expanded locus of one authored row carries the same list, so the first emits it and
            # the key is then taken.
            key = _resolution_key(row, chrom, start, alts_cell, genome_build)
            if key not in locus_counter:
                _emit_loci(key, row["resolution_loci"], locus_counter, emitted, genome_build)
            continue
        # The cell rebuild: a row whose cells reproduce the table (the column is null there), and every
        # row of a `weights.parquet` compiled before the column existed.
        if chrom is None or start is None:
            continue
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
        # RM364: where a row carries `resolution_loci`, that answer is what comes back, never the row's own
        # cells. A row the fill left alone (its authored coordinate contradicted, its key naming several
        # loci, or a build the fill skips) holds the AUTHORED coordinate there, and writing that back as
        # a resolution fact both lost the table's answer and silenced the contradiction on the second
        # lap. The cell rebuild below serves a row whose cells reproduce the table (the column is null
        # there) and every row of a parquet compiled before the column existed.
        for row in table_df.iter_rows(named=True):
            chrom, start = row.get("chrom"), row.get("start")
            if row.get("resolution_loci"):
                key = row.get("variant_key")
                if key and key not in locus_counter:
                    _emit_loci(key, row["resolution_loci"], locus_counter, emitted, genome_build)
                continue
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

    # A study's LD proxy last (RM331), the order `collect_subjects` admits it in: one that is also a module
    # variant or a positional row was emitted above under the same key and keeps that row. Several study
    # rows may name one proxy, and each carries the same loci, so the first one emits them.
    proxy_rows = (
        studies_df.iter_rows(named=True)
        if studies_df is not None and "proxy_loci" in studies_df.columns
        else ()
    )
    for row in proxy_rows:
        key, loci = row.get("proxy_rsid"), row.get("proxy_loci")
        if not key or not loci or key in locus_counter:
            continue
        _emit_loci(key, loci, locus_counter, emitted, genome_build)

    # A module that resolved nothing anywhere gets no file — writing a header-only `resolution.csv`
    # into a reversed spec that never had one would invent a derived sidecar (and a `manifest.derived`
    # entry) out of an absence. A module with a `weights.parquet` keeps the pre-0.6 behaviour of
    # always writing, so nothing that already round-trips changes shape.
    # `spec_carried_one` (RM364): the compiled spec had a table, so the reversed one has one too, even
    # with nothing in it a parquet held.
    if weights_df is None and not emitted and not spec_carried_one:
        return
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in emitted:
            writer.writerow(record)


def _emit_loci(
    key: str,
    loci: list[dict[str, Any]],
    locus_counter: dict[str, int],
    emitted: list[dict[str, object]],
    genome_build: str,
) -> None:
    """Re-emit the loci a parquet carries for `key` (`proxy_loci`, `resolution_loci`), each as stored."""
    locus_counter[key] = len(loci)
    for locus in loci:
        emitted.append(
            _resolution_record(
                locus,
                key,
                locus["chrom"],
                locus["start"],
                locus.get("alts") or None,
                locus["locus_index"],
                genome_build,
            )
        )


#: The identity cells a resolution may fill into a parquet row, beside the ones the author wrote.
_FILLABLE_IDENTITY: tuple[str, ...] = ("rsid", "chrom", "start", "ref", "alts")


def _no_table_was_read(
    manifest: ModuleManifest | None,
    weights_df: pl.DataFrame | None,
    positional: list[tuple[str, pl.DataFrame]],
) -> bool:
    """Whether the compile that made this artifact resolved from nothing, so reverse writes no table (RM364).

    Three facts, all required. The manifest names no `resolution_signature`, which every compile since
    0.6 stamps where it reads a table with rows. Its `derived` list names no `resolution.csv`, which it
    records for a table with no rows or one `--no-resolve` left unread. And no parquet row carries an identity cell its
    `authored_ident` does not name: a filled cell came from somewhere, and an older compile, or the
    deprecated `ensembl_cache` path, fills one without stamping a signature, so that module still needs
    the table rebuilt to recompile to the same bytes. A parquet with no `authored_ident` column cannot
    tell a filled cell from an authored one and counts as filled; a bare directory with no manifest
    keeps the old behaviour of always writing.
    """
    if manifest is None or manifest.compilation.resolution_signature is not None:
        return False
    if _spec_carried_a_table(manifest):
        return False
    frames = [frame for frame in (weights_df,) if frame is not None] + [frame for _csv, frame in positional]
    return not any(_carries_a_filled_cell(frame) for frame in frames)


def _spec_carried_a_table(manifest: ModuleManifest) -> bool:
    """Whether the compiled spec carried a `resolution.csv`, by `manifest.derived`'s record of it.

    Recorded even when the table had no rows or was not read (`--no-resolve`), so the reversed spec
    carries one back, header-only if nothing a parquet holds came from it."""
    carried = set(sidecar_relative_names("resolution.csv"))
    return any(entry.name in carried for entry in manifest.derived)


def _carries_a_filled_cell(frame: pl.DataFrame) -> bool:
    """Whether some row of `frame` holds an identity cell its `authored_ident` does not name."""
    if "authored_ident" not in frame.columns:
        return True
    columns = [name for name in _FILLABLE_IDENTITY if name in frame.columns]
    for row in frame.select("authored_ident", *columns).iter_rows(named=True):
        authored = set(row["authored_ident"] or ())
        if any(row[name] not in (None, "", []) and name not in authored for name in columns):
            return True
    return False


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
    # Every carried column as the locus (or, in the cell rebuild, the row) holds it (RM380). A row's own
    # cells hold no provenance, so the cell rebuild writes those empty, as before.
    record: dict[str, object] = {name: _scalar_cell(row.get(name)) for name in RESOLUTION_LOCUS_FIELDS}
    record.update(
        {
            "variant_key": resolution_key,
            "chrom": _scalar_cell(chrom),
            "start": _scalar_cell(start),
            "alts": alts_cell or "",
            # The module's own declared build, not a constant. A GRCh37 module's facts were being
            # written out labelled GRCh38 — a coordinate relabelled onto an assembly where it names a
            # different base. `resolve_from_table` filters rows on this column, so the wrong label also
            # made a reversed table unjoinable.
            "genome_build": genome_build,
            "locus_index": locus_index,
            # RM270: the ids every variant parquet carries since 0.8 — a list parallel to `alts` on
            # `weights.parquet`, the `resolution.csv` cell itself on a positional table and a locus.
            # An older artifact has neither column and writes empty cells, as before.
            "vrs_id": _vrs_cell(row.get("vrs_id")),
            "source": "reversed",
            "status": "resolved",
            "fetched_at": "",
        }
    )
    return record


def _vrs_cell(value: object) -> str:
    """A parquet's `vrs_id` as `resolution.csv` spells it: a list joined with its holes kept."""
    if isinstance(value, list):
        return join_vrs_ids(value) or ""
    return _scalar_cell(value)


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


#: The reversed `variants.csv` header: `VariantRow`'s authored columns, in this order. A hand-kept list,
#: so `test_resolution_locus_carries_the_row` asserts it equals `authored_field_names(VariantRow)` (RM380).
VARIANTS_CSV_FIELDS: tuple[str, ...] = (
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
)


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
    fieldnames = list(VARIANTS_CSV_FIELDS)
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


#: The reversed `studies.csv` header: `StudyRow`'s authored columns, in this order. A hand-kept list,
#: so `test_resolution_locus_carries_the_row` asserts it equals `authored_field_names(StudyRow)` (RM380).
STUDIES_CSV_FIELDS: tuple[str, ...] = (
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
    # 0.8: the StudyRow batch (PROPOSAL_0_8_PT2 §3 items 11–17). Each is named twice, here and in
    # the row dict below, and the behavioural guard in test_roundtrip_regressions fills them all.
    "sample_size",
    "sample_unit",
    "n_cases",
    "phenotype_class",
    "ancestry",
    "age_min",
    "age_max",
    "age_of",
    "stratum",
    "stratum_level",
    "proxy_rsid",
    "effect_unit",
)


def _write_studies_csv(studies_df: pl.DataFrame, output_path: Path) -> None:
    """Write studies.csv from studies parquet."""
    fieldnames = list(STUDIES_CSV_FIELDS)
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
                    "sample_size": _scalar_cell(row.get("sample_size")),
                    "sample_unit": _scalar_cell(row.get("sample_unit")),
                    "n_cases": _scalar_cell(row.get("n_cases")),
                    "phenotype_class": _scalar_cell(row.get("phenotype_class")),
                    "ancestry": _list_cell(row.get("ancestry")),
                    "age_min": _scalar_cell(row.get("age_min")),
                    "age_max": _scalar_cell(row.get("age_max")),
                    "age_of": _scalar_cell(row.get("age_of")),
                    "stratum": _scalar_cell(row.get("stratum")),
                    "stratum_level": _scalar_cell(row.get("stratum_level")),
                    "proxy_rsid": _scalar_cell(row.get("proxy_rsid")),
                    "effect_unit": _scalar_cell(row.get("effect_unit")),
                }
            )
