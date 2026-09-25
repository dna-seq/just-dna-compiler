"""Manifest assembly: the files collected beside the artifact, the stats, the per-table fact blocks,
the sources and licence gate, the verification and closure blocks, and `_build_manifest`.
"""

import shutil
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from just_dna_format.assertions import ClinicalAssertionRow
from just_dna_format.concordance import ClinSigAuthorityCallRow, ClinSigConcordanceRow
from just_dna_format.expression import ExpressionEffectRow
from just_dna_format.findings import CodedWarning, classify
from just_dna_format.frequency import FrequencyRow
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.gene_validity import SUPERSEDED, GeneValidityRow, classify_currency
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.identity import is_valid_version
from just_dna_format.integrity import (
    build_artifact,
    clin_sig_authority_call_signature,
    clin_sig_concordance_signature,
    file_entries,
    file_entry,
    sha256_file,
)
from just_dna_format.integrity import clinical_assertion_signature as _clinical_assertion_signature
from just_dna_format.integrity import expression_effect_signature as _expression_effect_signature
from just_dna_format.integrity import frequency_signature as _frequency_signature
from just_dna_format.integrity import gene_metrics_signature as _gene_metrics_signature
from just_dna_format.integrity import gene_validity_signature as _gene_validity_signature
from just_dna_format.integrity import gwas_effect_signature as _gwas_effect_signature
from just_dna_format.integrity import literature_signature as _literature_signature
from just_dna_format.integrity import source_signature as _source_signature
from just_dna_format.layout import VERIFICATION_JSON, sidecar_relative_names
from just_dna_format.literature import LiteratureRow
from just_dna_format.manifest import (
    LOGO_EXTENSIONS,
    README_CANDIDATES,
    README_EXTENSIONS,
    ClinicalAssertions,
    ClinSigConcordance,
    Compilation,
    Display,
    ExpressionEffects,
    FileEntry,
    Frequency,
    GeneMetrics,
    GeneValidity,
    GwasEffects,
    Identity,
    Literature,
    ModuleManifest,
    Provenance,
    ProvenanceDoc,
    Sources,
    Stats,
    Verification,
)
from just_dna_format.normalize import now_utc_iso
from just_dna_format.sources import SourceRow, taints_commercial_use, taints_redistribution
from just_dna_format.spec import ModuleSpecConfig, VariantRow
from just_dna_format.verification import (
    attestation_failure,
    module_binding,
    read_verification,
    verification_block,
)
from just_dna_format.vocab import population_sort_key

from just_dna_compiler.compiler.positional import _GENE_BEARING_TABLE_KINDS
from just_dna_compiler.compiler.tables import (
    _DERIVED_FILES,
    _INPUT_FILES,
    _PROVENANCE_FILE,
    ARTIFACT_PARQUETS,
    _locate_sidecar,
    authored_input_entries,
)
from just_dna_compiler.models import ValidationResult


def _compiler_version() -> str:
    try:
        return f"just-dna-compiler {version('just-dna-compiler')}"
    except PackageNotFoundError:
        return "just-dna-compiler unknown"


def _now_iso() -> str:
    """The manifest's stamp, from the format tier's single producer (`normalize.now_utc_iso`).

    Already this spelling before it moved — kept as a thin alias so there is exactly one place
    that decides what a timestamp looks like across all three tiers."""
    return now_utc_iso()


def _collect_logs(spec_dir: Path, output_dir: Path, explicit: list[Path] | None) -> list[FileEntry]:
    """Gather optional run/provenance logs into the module dir and hash them.

    Auto-discovers a top-level aggregate log (`*.log` in `spec_dir`) plus per-role files under a
    `spec_dir/logs/` folder, preserving each file's path relative to the module. An explicit
    `log_files` list overrides discovery. Files are copied into `output_dir` (so they ship with the
    module) and returned as hashed `FileEntry` rows. No logs → empty list (a valid module).
    """
    pairs: list[tuple[str, Path]] = []  # (relative name in module dir, source file)
    if explicit is not None:
        for path in map(Path, explicit):
            try:
                rel = path.relative_to(spec_dir).as_posix()
            except ValueError:
                rel = path.name
            pairs.append((rel, path))
    else:
        for path in sorted(spec_dir.glob("*.log")):
            pairs.append((path.name, path))
        logs_dir = spec_dir / "logs"
        if logs_dir.is_dir():
            for path in sorted(logs_dir.rglob("*.log")):
                pairs.append((path.relative_to(spec_dir).as_posix(), path))

    seen: set[str] = set()
    names: list[str] = []
    for rel, src in pairs:
        if rel in seen or not src.is_file():
            continue
        seen.add(rel)
        dest = output_dir / rel
        if dest.resolve() != src.resolve():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
        names.append(rel)
    return file_entries(output_dir, names)


def _collect_provenance(spec_dir: Path, output_dir: Path, explicit: Path | None) -> Provenance | None:
    """Discover an optional `provenance.json`, validate it, ship it, and summarize it.

    Auto-discovers `spec_dir/provenance.json` (or uses an explicit path). The full per-variant
    items stay in the file (copied into the module dir, hashed like logs, and kept out of
    `artifact.digest`); the returned `Provenance` is the lean summary that rides in the manifest.
    Absent provenance → `None` (a valid module).
    """
    src = Path(explicit) if explicit is not None else spec_dir / _PROVENANCE_FILE
    if not src.is_file():
        return None
    doc = ProvenanceDoc.model_validate_json(src.read_text(encoding="utf-8"))
    dest = output_dir / _PROVENANCE_FILE
    if dest.resolve() != src.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    return Provenance(
        generator=doc.generator,
        model=doc.model,
        agent_version=doc.agent_version,
        item_count=len(doc.items),
        file=_PROVENANCE_FILE,
        sha256=sha256_file(dest),
    )


def _collect_logo(spec_dir: Path, output_dir: Path, explicit: Path | None) -> FileEntry | None:
    """Discover an optional module logo (`logo.png`/`.jpg`/`.jpeg`), ship it, and hash it.

    Uses an explicit path if given, else the first `logo.<ext>` (in `LOGO_EXTENSIONS` order) found
    beside the spec. The logo is copied into the module dir and returned as a hashed `FileEntry`
    kept OUT of `artifact.digest` (a logo swap is a PATCH, not a new content identity). Absent
    logo → `None`. Raises `ValueError` on an unsupported extension.
    """
    if explicit is not None:
        src: Path | None = Path(explicit)
    else:
        src = next(
            (
                spec_dir / f"logo.{ext}"
                for ext in sorted(LOGO_EXTENSIONS)
                if (spec_dir / f"logo.{ext}").is_file()
            ),
            None,
        )
    if src is None or not src.is_file():
        return None
    ext = src.suffix.lower().lstrip(".")
    if ext not in LOGO_EXTENSIONS:
        raise ValueError(f"logo must be one of {sorted(LOGO_EXTENSIONS)}, got: {src.name!r}")
    dest = output_dir / src.name
    if dest.resolve() != src.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    return file_entry(output_dir, src.name)


def _collect_readme(spec_dir: Path, output_dir: Path, explicit: Path | None) -> FileEntry | None:
    """Discover an optional module readme, ship it, and hash it — the `_collect_logo` shape exactly.

    Uses an explicit path if given, else the first of `manifest.README_CANDIDATES` found beside the
    spec (`README.md` first). The file is copied into the module dir and returned as a hashed
    `FileEntry` kept OUT of `artifact.digest` *and* out of `content_signature`, so correcting a
    sentence is a PATCH rather than a new identity. Absent readme → `None`. Raises `ValueError` on an
    unsupported extension.

    **The exclusion is the point, not an oversight.** A readme is prose about the module, and the
    alternative of putting it in `artifact.files` was rejected by the consumer who asked for this
    (S25): on an immutable registry a fixed typo in a caveat would then cost a version number, and the
    corrected module would collide with its own predecessor under a content-dedup check. Nothing here
    reads the markup — the extension travels in the name for whoever renders it."""
    if explicit is not None:
        src: Path | None = Path(explicit)
    else:
        src = next(
            (spec_dir / name for name in README_CANDIDATES if (spec_dir / name).is_file()),
            None,
        )
    if src is None or not src.is_file():
        return None
    ext = src.suffix.lower().lstrip(".")
    if ext not in README_EXTENSIONS:
        raise ValueError(f"readme must be one of {sorted(README_EXTENSIONS)}, got: {src.name!r}")
    dest = output_dir / src.name
    if dest.resolve() != src.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    return file_entry(output_dir, src.name)


def variant_stats(variants: list[VariantRow]) -> dict[str, Any]:
    """The `variants.csv`-derived facets of `ValidationResult.stats` / `manifest.stats`.

    Its own function because it now has **two** callers, and the second is why: `compile_module` may
    discard a row for carrying an unusable symbolic allele (RM5), and the stats were computed by
    `validate_spec` before that happened. `weights_rows` counts the parquet and so is post-drop, so a
    published manifest claimed a `variant_count` one higher than the artifact contained — the RM44
    class of defect exactly, a manifest number a catalog keys on and cannot check.
    """
    genes = sorted({v.gene for v in variants if v.gene})
    return {
        "variant_count": len({v.variant_key for v in variants}),
        "unique_rsids": len({v.rsid for v in variants if v.rsid is not None}),
        "gene_count": len(genes),
        "genes": genes,
        "categories": sorted({v.category for v in variants if v.category}),
        # ClinVar/quality flag counts over variant rows (ROADMAP item 5).
        "clinvar_count": sum(1 for v in variants if v.clinvar),
        "pathogenic_count": sum(1 for v in variants if v.pathogenic),
        "benign_count": sum(1 for v in variants if v.benign),
    }


def module_stats(variants: list[VariantRow], kind_rows: dict[str, list[Any]] | None = None) -> dict[str, Any]:
    """`variant_stats` plus the gene facets taken over **every** authored table, not just variants.

    PUBLIC, and it exists rather than a second parameter on `variant_stats` because that function's
    name is a promise about which table it reads and renaming it would be a major (S14's rule). What
    the two return differs in exactly two keys.

    **`stats` describes the module, and `Stats` has always said so** — *"card/detail stats derived from
    the spec"*, not from one table of it. `variant_stats` nevertheless derived `genes` from
    `variants.csv` alone, so a module whose lead table is `diplotypes.csv`, `allele_function.csv`,
    `copynumbers.csv` or any other gene-bearing kind published `gene_count: 0, genes: []` however many
    of its rows named a gene — and a registry's gene index is fed from that field, so the module was
    unreachable by a gene search (S57). Measured on `reference_examples/cyp2c19_star_alleles/`: 1,332
    rows carrying `gene=CYP2C19` across three tables, and `genes: []`.

    The honest workaround an author was left with was prose in the README, and the *dishonest* one —
    inventing an empty `variants.csv` to be discoverable — is what makes this ours to fix rather than a
    documentation note.

    Only authored kinds count. `_GENE_BEARING_TABLE_KINDS` derives from `_TABLE_KINDS`, which
    deliberately excludes the derived fact sidecars, so a gene reaching `gene_metrics.csv` because a
    pass looked it up never becomes a gene the module claims to be about.
    """
    stats = variant_stats(variants)
    genes = set(stats["genes"])
    for csv_name, _model in _GENE_BEARING_TABLE_KINDS:
        for row in (kind_rows or {}).get(csv_name) or []:
            gene = getattr(row, "gene", None)
            if gene:
                genes.add(gene)
    ordered = sorted(genes)
    stats["gene_count"] = len(ordered)
    stats["genes"] = ordered
    return stats


def _frequency_block(rows: list[FrequencyRow]) -> Frequency | None:
    """The manifest's `frequency` summary, or `None` when the module carries no frequency sidecar.

    `populations` is emitted in the canonical order rather than sorted alphabetically, so it reads the
    way the table reads (`global` first). Every other list is sorted — they are set-like facets, and a
    sorted list is the only order that cannot drift.
    """
    if not rows:
        return None
    populations = sorted({r.population for r in rows}, key=population_sort_key)
    return Frequency(
        signature=_frequency_signature(rows),
        sources=sorted({r.source for r in rows if r.source}),
        datasets=sorted({r.dataset for r in rows if r.dataset}),
        populations=populations,
        row_count=len(rows),
        variant_count=len({r.variant_key for r in rows}),
    )


def _gene_metrics_block(rows: list[GeneMetricsRow]) -> GeneMetrics | None:
    """The manifest's `gene_metrics` summary, or `None` when the module carries no such sidecar."""
    if not rows:
        return None
    return GeneMetrics(
        signature=_gene_metrics_signature(rows),
        sources=sorted({r.source for r in rows if r.source}),
        datasets=sorted({r.dataset for r in rows if r.dataset}),
        row_count=len(rows),
        genes=sorted({r.gene for r in rows}),
    )


def _gene_validity_block(rows: list[GeneValidityRow]) -> GeneValidity | None:
    """The manifest's `gene_validity` summary, or `None` when the module carries no such sidecar.

    Every facet is a sorted set, including `classifications` — the strength ladder is published once,
    as `vocab.ORDERED_GENE_VALIDITY`, so this block does not encode a second copy of it that could
    drift. `diseases` is here because indexing a module by condition is the reason a catalog would
    read this block instead of the parquet.
    """
    if not rows:
        return None
    # RM108. `classifications` is the one facet where "the union of every row" was the wrong
    # question: a re-curated claim contributed BOTH its verdicts, so a module whose only disagreement
    # was ClinGen changing its own mind published `["definitive", "refuted"]` and left a consumer to
    # reconstruct which one stands. Superseded rows are excluded here; every other facet still spans
    # the whole table, because "which submitters contributed" and "which releases" are questions
    # about the file rather than about the live verdict.
    #
    # A group nothing orders contributes **all** of its classifications, which is the withholding
    # rather than an oversight: with no way to say which curation is current, publishing one of them
    # would be picking a winner the data does not name.
    verdicts = classify_currency(rows)
    live = [row for row, verdict in zip(rows, verdicts, strict=True) if verdict != SUPERSEDED]
    return GeneValidity(
        signature=_gene_validity_signature(rows),
        sources=sorted({r.source for r in rows if r.source}),
        datasets=sorted({r.dataset for r in rows if r.dataset}),
        row_count=len(rows),
        genes=sorted({r.gene for r in rows}),
        diseases=sorted({r.disease_id for r in rows if r.disease_id}),
        classifications=sorted({r.classification for r in live if r.classification}),
        submitters=sorted({r.submitter for r in rows if r.submitter}),
        superseded_count=sum(1 for v in verdicts if v == SUPERSEDED),
    )


def _clinical_assertions_block(rows: list[ClinicalAssertionRow]) -> ClinicalAssertions | None:
    """The manifest's `clinical_assertions` summary, or `None` when the module carries no such sidecar.

    The star range is `min`/`max` over the rows that state one, and `None` when none does — never a
    zero. That is the same rule `Literature.quotes_found` follows and it matters more here: 0 is a real
    rating ("no assertion criteria provided"), so collapsing "nothing was rated" into it would report
    the module's evidence as the worst kind available rather than as unstated. `unrated_count` carries
    the size of that gap, because a range over an unstated fraction is not something a catalog can
    filter on.
    """
    if not rows:
        return None
    rated = [r.review_stars for r in rows if r.review_stars is not None]
    return ClinicalAssertions(
        signature=_clinical_assertion_signature(rows),
        sources=sorted({r.source for r in rows if r.source}),
        datasets=sorted({r.dataset for r in rows if r.dataset}),
        row_count=len(rows),
        variant_count=len({r.variant_key for r in rows}),
        clin_sigs=sorted({r.clin_sig for r in rows if r.clin_sig}),
        min_review_stars=min(rated) if rated else None,
        max_review_stars=max(rated) if rated else None,
        unrated_count=sum(1 for r in rows if r.review_stars is None),
        not_found_count=sum(1 for r in rows if r.status == "not_found"),
    )


def _gwas_effects_block(rows: list[GwasEffectRow]) -> GwasEffects | None:
    """The manifest's `gwas_effects` summary, or `None` when the module carries no such sidecar.

    `units` and the effect-allele pair are the facets that earn their place. A consumer asking "can I
    use these effects" needs two answers a row count cannot give: are the betas on one scale
    (`units` with more than one member says no), and how many associations name no allele at all
    (`without_effect_allele`, which the Catalog writes as `-?` and which is unusable as a weight).

    The unit set deliberately includes the Catalog's uninformative `unit`. Filtering it out would
    make a module whose betas are all in unstated units look like one whose betas share a scale,
    which is the more dangerous of the two mistakes.
    """
    if not rows:
        return None
    return GwasEffects(
        signature=_gwas_effect_signature(rows),
        sources=sorted({r.source for r in rows if r.source}),
        datasets=sorted({r.dataset for r in rows if r.dataset}),
        row_count=len(rows),
        variant_count=len({r.variant_key for r in rows}),
        with_effect_allele=sum(1 for r in rows if r.effect_allele),
        without_effect_allele=sum(1 for r in rows if not r.effect_allele),
        measures=sorted({r.effect_measure for r in rows if r.effect_measure}),
        units=sorted({r.effect_unit for r in rows if r.effect_unit}),
        traits=sorted({r.trait_efo_id for r in rows if r.trait_efo_id}),
        not_found_count=sum(1 for r in rows if r.status == "not_found"),
    )


def _expression_effects_block(rows: list[ExpressionEffectRow]) -> ExpressionEffects | None:
    """The manifest's `expression_effects` summary, or `None` when the module carries no such sidecar.

    `without_distance` and the direction pair are the facets that earn their place. A consumer asking
    "can I threshold these" needs two answers a row count cannot give: is a distance-aware threshold
    possible at all (`without_distance == row_count` says no, because no gene span was available), and
    how many pairs name no direction (`without_direction`, where the scorer's tracks split and the
    magnitude stands without a sign).

    `max_distance_to_gene` is `None` rather than `0` when nothing carries a distance, on the rule the
    whole family is built on: a table where the distance could not be computed is not a table where
    every variant sits inside its gene, and a zero would read as the latter.

    `genes` is published in full rather than counted, because for this table the gene list is what
    says what the rows are *about* — they are locus-wide, so the variant set does not.
    """
    if not rows:
        return None
    distances = [r.distance_to_gene for r in rows if r.distance_to_gene is not None]
    return ExpressionEffects(
        signature=_expression_effect_signature(rows),
        sources=sorted({r.source for r in rows if r.source}),
        datasets=sorted({r.dataset for r in rows if r.dataset}),
        row_count=len(rows),
        variant_count=len({r.variant_key for r in rows}),
        genes=sorted({r.gene for r in rows if r.gene}),
        measures=sorted({r.effect_measure for r in rows if r.effect_measure}),
        with_direction=sum(1 for r in rows if r.effect_direction),
        without_direction=sum(1 for r in rows if not r.effect_direction),
        without_distance=sum(1 for r in rows if r.distance_to_gene is None),
        max_distance_to_gene=max(distances) if distances else None,
    )


def _clin_sig_concordance_block(
    rows: list[ClinSigConcordanceRow], calls: list[ClinSigAuthorityCallRow]
) -> ClinSigConcordance | None:
    """The manifest's `clin_sig_concordance` summary, or `None` when the module carries no record.

    `None` rather than a block of zeros, on the rule the whole record is built on: a module that
    never had the comparison run is not a module where nothing is contested, and an all-zero summary
    would read as the latter.

    Two hashes, because it is two tables. A corrected normalization moves every detail row without
    moving one verdict, and a reader able to see that is a reader who can tell *our* mapping changed
    from *an archive* changed its mind.

    `opposed_count` and `unchecked_count` are published beside the row count because neither is
    derivable from it and both change what the number means: forty subjects where every disagreement
    crosses the pathogenic/benign line is a different module from forty that differ by a confidence
    step, and a record that shrank because an archive could not be reached has not improved.

    **No consensus facet.** Nothing here says which authority is right where two disagree; resolving
    a split needs a weighting model this format does not have, and publishing one as a summary field
    would make a judgement look like a fact.
    """
    if not rows:
        return None
    return ClinSigConcordance(
        signature=clin_sig_concordance_signature(rows),
        calls_signature=clin_sig_authority_call_signature(calls) if calls else None,
        authorities=sorted({r.authority for r in calls}),
        datasets=sorted({r.dataset for r in calls if r.dataset}),
        row_count=len(rows),
        call_count=len(calls),
        opposed_count=sum(1 for r in rows if r.opposed is True),
        unchecked_count=sum(1 for r in rows if "unchecked" in {r.authority_concordance, r.authored_position}),
        concordance_states=sorted({r.authority_concordance for r in rows}),
        authored_positions=sorted({r.authored_position for r in rows}),
    )


def _concordance_warnings(rows: list[ClinSigConcordanceRow]) -> list[str]:
    """Say that the module carries contested subjects, and where the answer goes (RM130).

    **A question, never a defect**, and never a `strict` matter: a disagreement with an archive is a
    fact about the field, the archive is the stale side often enough that failing a build on one
    would be wrong, and escalating would have this format arbitrate a clinical dispute — which is
    the same reason the check that produced these rows warns in both modes.

    **It names `overrides.csv` and never `provenance.json`'s `outranks`.** Both record an authored
    value beating a source with prose, and 0.7 settled the overlap as a dated succession: the
    overlay wins and the knob is filed for removal at the major. An author meeting this warning for
    the first time is exactly who should be steered onto the mechanism that survives, and it costs a
    clause.

    **The count is safe to embed although both passes emit it**, which is normally the trap where a
    message carrying a number is built twice from inputs resolution changed in between. This one
    reads `clin_sig_concordance.csv` after the overlay, and no compile step between the two passes
    touches either the file or the overlay — so both passes reach a byte-identical sentence and the
    existing message de-duplication collapses them. Pinned by a test rather than left to the
    argument.

    **Counted over the post-overlay rows**, which is what makes the finding clearable: an author who
    has answered a contested subject with a `suppress` override removes it from the built table, and
    the suppression is itself reported by `overlay_rows_suppressed`, so nothing goes quiet.
    """
    if not rows:
        return []
    opposed = sum(1 for r in rows if r.opposed is True)
    unresolved_camps = sum(1 for r in rows if r.opposed is None)
    split = f"{opposed} of them opposed calls (pathogenic-class against benign-class)"
    if unresolved_camps:
        split += f", {unresolved_camps} with an authority that could not be consulted"
    return [
        CodedWarning(
            "clin_sig_concordance_contested",
            f"clin_sig_concordance.csv records {len(rows)} contested subject(s): {split}. A contested "
            f"subject is a question, not a defect — half the time the archive is the stale side, which "
            f"is why this never fails a build in either mode. Answer one by adding a row to "
            f"overrides.csv naming table 'clin_sig_concordance.csv', the subject's variant_key and its "
            f"genotype, with the reason you stand by the module's call.",
        )
    ]


def _check_license_gate(rows: list[SourceRow]) -> list[str]:
    """Refuse to compile a module whose sources forbid sale and that records no matching declaration.

    The refusal fires in **both** modes. `strict`'s single meaning is "produce a reproducible
    artifact"; whether the terms were accepted is unrelated to reproducibility, and overloading the
    flag with a second axis is exactly the orthogonality Principle 5 protects.

    It is keyed on **data carried by the module**, never on a CLI flag. That is what keeps
    `compile → reverse → compile` a fixed point (Principle 7): `reverse_module` rebuilds
    `module_spec.yaml` from parquet alone and could never re-emit a flag, so a flag-gated compile
    would refuse on the third step. `sources.csv` round-trips, so the declaration travels with the
    module and the cycle reproduces.

    Most-restrictive-wins, module-wide: one tainting row refuses the whole compile. Mixing a
    permissive source into a restricted one cannot launder it, which is why the verdict is not
    computed per row or per layer.
    """
    tainted = [r for r in rows if taints_commercial_use(r)]
    if not tainted:
        return []
    # A single declaration governs the module, so any tainted row lacking one refuses. `unstated` is
    # not a loophole: it is the absence of a declaration, which is precisely what this gate wants.
    undeclared = sorted({r.source for r in tainted if r.declared_use != "non_commercial"})
    if not undeclared:
        return []
    return [
        f"licensing: {undeclared} contribute annotation-layer content under terms that forbid sale, "
        f"and this module records no non-commercial declaration for them. Re-run the enricher with "
        f"a declared use (`--use non-commercial`) to record one, or remove the affected content. "
        f"Declaring it is an assertion about how the module will be used — the compiler records that "
        f"assertion, it does not verify it."
    ]


#: The `sources.csv` layers no fact table's `source` column can ever corroborate, so a declaration at
#: one of them is uncorroborable rather than stale. See `_source_checks` for why each is here.
_UNCORROBORABLE_LAYERS: frozenset[str] = frozenset({"annotation", "literature"})


def _source_checks(rows: list[SourceRow], used_sources: set[str]) -> list[str]:
    """Warning-only coherence for `sources.csv`. Never escalates under `strict`.

    Two findings, both mirroring the existing orphan-sidecar precedent (don't punish the author for
    the enricher's generosity):

    - a declared source that no fact table actually used — over-declaration, harmless but probably
      stale; and
    - a source used by a fact table with no `sources.csv` row — under-declaration, which matters more
      but still cannot be an error, because the compiler cannot know whether the omission is an
      oversight or a source with no terms worth recording.

    The second is emitted **only when `sources.csv` exists at all**, so a module without one warns
    exactly as it does today (Principle 3).

    **`annotation`-layer rows are exempt from the orphan half, and that is structural rather than a
    softening.** "No table used it" is decided by reading the fact tables' `source` columns, and the
    annotation layer *is* `variants.csv`/`diplotypes.csv`/…, which carry no such column by design (a
    curated annotation's provenance is the module's, not a per-row link). So an annotation-layer row can
    never be corroborated and was reported as stale on **every** drafted module — `clinvar_draft` and
    `pgx_draft` both write exactly one such row, and it is the row that makes the licence gate work.
    Warning that the load-bearing row looks unused is the opposite of useful.

    **`literature` joins that exemption, and since 0.6 it joins it unconditionally (S23, then RM46).**
    The same argument, reached by the same route: `studies.csv` is the hand-curated literature table
    and carries no `source` column *by the design the annotation exemption cites*, so a module citing
    a PMID through it can never corroborate the service the curator read the record through. That left
    `literature.csv` — enricher-written, with a `source` column — as the only possible corroborator,
    which is why the exemption used to be conditional on the module having no study rows.

    RM46 removed that last joinable value, and the reason is the point rather than a simplification.
    `literature.csv`'s `source` names the **bibliographic registry that answered** (`pubmed`), not a
    licensed source, and the tier has no terms constant for it *because a literature source's terms
    are per article, not per source*: PubMed's metadata is one thing and the publisher's article is
    another, and Europe PMC's open subset spans CC-BY, CC-BY-NC and bronze. So the article's terms are
    recorded on the literature row itself (`license`/`share_alike`/`commercial_use`/`redistribution`)
    and its `source` is excluded from `used_sources` by the caller. A single `pubmed` row in
    `sources.csv` would be wrong in the dangerous direction — right for a module citing only ids, and
    a false all-clear for one carrying a `provenance_quote` lifted from a CC-BY-NC article. Nothing
    can therefore corroborate a literature-layer declaration, `studies.csv` or no, so the conditional
    could no longer distinguish anything.

    Note which way the old behaviour pushed an author, because that is what makes the exemption worth
    keeping: `vocab.MISPLACED_COLUMN_REASONS['source']` tells an author to declare a hand-read source
    by adding a row to `sources.csv`, and doing so earned a warning that the row is unused, while
    deleting it — and shipping with the provenance unrecorded — was silent. Compliance warned,
    omission quiet. An over-declaration here is the cheap error; an author talked out of recording
    their terms is not. `frequency` still warns, because `frequencies.csv` *is* machine-written with a
    `source` column naming a licensed source, so a frequency declaration in a module with no
    frequencies really is stale.
    """
    warnings: list[str] = []
    declared = {r.source for r in rows}
    corroborable = {r.source for r in rows if r.layer not in _UNCORROBORABLE_LAYERS}
    orphans = sorted(corroborable - used_sources)
    if orphans:
        warnings.append(
            CodedWarning(
                "source_row_unused",
                f"sources.csv declares {len(orphans)} source(s) no table in this module uses: {orphans}",
            )
        )
    undeclared = sorted(used_sources - declared)
    if undeclared:
        warnings.append(
            CodedWarning(
                "source_terms_unrecorded",
                f"sources.csv has no row for {len(undeclared)} source(s) the module's fact tables cite: "
                f"{undeclared} — their terms are unrecorded.",
            )
        )
    return warnings


def _check_declared_license_agrees(rows: list[SourceRow], declared_license: str | None) -> list[str]:
    """Warn when `module_spec.yaml`'s `license:` contradicts an annotation-layer source's.

    Warning in **both** modes, deliberately — the second such exception after the ClinVar `clin_sig`
    cross-check, and for the same reason. Every other compiler check compares an authored value
    against a *fact*; this compares two claims about a legal position, and failing the compile would
    make the format arbitrate a licensing dispute. String equality only: an SPDX compatibility matrix
    is world-knowledge that would go stale, and the compiler is not the tier that should hold it.

    **The message names its denominator (S79).** It used to render the *remainder* — the rows whose
    licence differs — as though it were the whole set, so a declaration matching one of two
    annotation-layer rows printed identically to one matching none. Those are different problems with
    different repairs: *your declaration is unsupported* versus *your declaration is not universal*,
    and the second is the ordinary shape of a mixed-licence module where the most restrictive term
    binds. An author reading the first when the second was true re-adjudicated the module's whole
    licence position and found nothing wrong, twice, in two separate reported rounds.

    So the count leads and the agreeing rows are named beside the disagreeing ones. **Suppressing the
    warning when any row matches was refused** — the reporter argued it against their own case and is
    right: a module declaring the *least* restrictive of several licences is exactly the one worth
    warning about.

    `@warning-text-is-api`: `declares license` is the fragment the existing test keys on and it still
    leads the sentence; what follows it is what changed.
    """
    if not declared_license:
        return []
    annotation = [r for r in rows if r.layer == "annotation" and r.license]
    conflicting = sorted({r.license for r in annotation if r.license != declared_license})
    if not conflicting:
        return []
    # Rows rather than distinct licences, because the denominator an author is checking against is how
    # many sources they have — two rows sharing a licence are two obligations, not one.
    agreeing = sum(1 for r in annotation if r.license == declared_license)
    standing = (
        f"{len(annotation) - agreeing} of {len(annotation)} annotation-layer source(s) report a "
        f"different licence: {conflicting}"
        if agreeing
        else f"no annotation-layer source reports it; they report {conflicting}"
    )
    return [
        CodedWarning(
            "declared_license_disagrees",
            f"module declares license {declared_license!r} and {standing}. Not adjudicated here — a "
            f"compatible pair is legitimate, an incompatible one is a real problem, and only a human can "
            f"tell which. A declaration matching some but not all of them is the ordinary mixed-licence "
            f"case, where the most restrictive term binds the whole artifact.",
        )
    ]


def _sources_block(rows: list[SourceRow]) -> Sources | None:
    """The manifest's `sources` summary, or `None` when the module carries no licensing sidecar.

    The per-layer facets stay lists (see `Sources`); only `commercial_use` collapses, because it is
    the one question with a single module-wide answer. Its ladder is most-restrictive-first: a
    forbidding source makes it `False`; failing that, an unknown makes it `None` (undetermined, never
    permitted); only an all-known, none-forbidding set makes it `True`.
    """
    if not rows:
        return None

    def _verdict(taints, is_unknown) -> bool | None:
        # Most-restrictive-first: a forbidding source makes it False; failing that, an unknown makes
        # it None (undetermined, never permitted); only an all-known, none-forbidding set makes True.
        if any(taints(r) for r in rows):
            return False
        return None if any(is_unknown(r) for r in rows) else True

    unknown = sorted({r.source for r in rows if r.commercial_use is None})
    verdict = _verdict(taints_commercial_use, lambda r: r.commercial_use is None)
    redistribution_verdict = _verdict(taints_redistribution, lambda r: r.redistribution is None)
    return Sources(
        signature=_source_signature(rows),
        sources=sorted({r.source for r in rows if r.source}),
        layers=sorted({r.layer for r in rows if r.layer}),
        licenses=sorted({r.license for r in rows if r.license}),
        attributions=sorted({r.attribution for r in rows if r.attribution}),
        notices=sorted({r.notice for r in rows if r.notice}),
        share_alike_layers=sorted({r.layer for r in rows if r.share_alike}),
        noncommercial_layers=sorted({r.layer for r in rows if r.commercial_use is False}),
        nonredistributable_layers=sorted({r.layer for r in rows if r.redistribution is False}),
        unknown_terms_sources=unknown,
        declared_uses=sorted({r.declared_use for r in rows if r.declared_use}),
        commercial_use=verdict,
        redistribution=redistribution_verdict,
        row_count=len(rows),
    )


def _verification_block(spec_dir: Path) -> tuple[Verification | None, list[str]]:
    """The manifest's `verification` block plus every warning about it — RM45's, and RM73's.

    A wrapper rather than a fourth branch inside the reader below, so the closure reminder is decided
    once from the outcome and both call sites (`validate_spec` and `compile_module`) inherit it
    without either having to remember. That mattered here: the two are already de-duplicated on the
    message, and a warning wired into only one of them is the pre-flight/compile parity gap this file
    has now closed four times.
    """
    block, warnings = _read_verification_block(spec_dir)
    return block, [*warnings, *_closure_warning(block), *_findings_warning(block)]


def _findings_warning(block: Verification | None) -> list[str]:
    """Say that a check *found something*, where the author is standing (S70).

    Nothing read `VerificationRecord.findings` at all: the counts reached
    `manifest.verification.checks[]`, so a consumer that went looking found them, while the author
    running `validate` saw a green result with warnings about closure and nothing about the rows a
    source disagrees with. Reported as 20 of 141,616 and 32 of 618,629 on two real modules.

    **A question, never a defect** — warning in both modes and never a `strict` matter, the
    `_closure_warning` class. Half the time the archive is the stale side, which is the whole reason
    the ClinVar cross-check does not escalate under `strict` either; making this fatal would have the
    format arbitrate a clinical disagreement, one tier further out than the check that refuses to.

    **The message carries counts and runs on both sides, which is normally the `@no-rerun-with-counts`
    trap and is not one here.** That rule fires where *resolution* changes a check's input between the
    two passes, so the same finding is reported with two different numbers and message-dedup cannot
    collapse them. This check's input is `verification.json`, which no compile step touches — the
    reason `_verification_block`'s call site already gives for being safe to double — so both passes
    reach a byte-identical sentence and the existing dedup collapses it. Pinned by a test rather than
    left to the argument.
    """
    if block is None:
        return []
    found = [r for r in block.checks if r.findings]
    if not found:
        return []
    named = ", ".join(
        f"{r.check} ({r.findings} of {r.subjects})"
        for r in sorted(found, key=lambda r: (-r.findings, r.check))
    )
    # `carried`, and the docstring above is the argument: the archive is the stale side often enough
    # that no authored edit is owed, and nothing an author writes moves the number in the record.
    return [
        CodedWarning(
            "verification_findings_recorded",
            f"verification.json records {sum(r.findings for r in found)} finding(s) across "
            f"{len(found)} check(s): {named}. A finding is a disagreement between this module and a "
            f"source, not a defect — the archive is the stale side often enough that this never fails a "
            f"build. Read the record's `detail` for which rows, and record why the module is right in "
            f"`provenance.json`'s `outranks` where it is.",
        )
    ]


def _read_verification_block(spec_dir: Path) -> tuple[Verification | None, list[str]]:
    """The manifest's `verification` block, or `None` plus the reason it is not being published (RM45).

    Returns `(block, warnings)` and **never errors**. Three outcomes, and the middle one is the whole
    point of the item:

    * no `verification.json` → `(None, [])`. Nothing was attested and nothing is said, silently: an
      unverified module is the ordinary case and warning about it would fire on every module in this
      repository.
    * an attestation that no longer matches these bytes, or one that cannot be read → `(None, [why])`.
      **Warn and drop.** Making a mismatch fatal was considered — a record asserting a check over
      bytes that are not these bytes is arguably the inconsistent-reference-allele class — and
      rejected: the goal is that a stale record never becomes a *published claim*, not that it be
      impossible to write, and dropping the block achieves that without stopping an author mid-edit.
      The manifest then carries no verification, which reads correctly as *says nothing* rather than
      as a pass.
    * an attestation that holds → `(block, [])`.

    The binding is recomputed from `authored_input_entries`, over the same file set `manifest.inputs`
    lists — but **not over the same bytes, and that is deliberate (RM82)**. The binding reads `\\r\\n`
    as `\\n`; the inputs listing reads every byte as it lies. So a file rewritten with different line
    endings moves the listing and leaves the attestation standing, which is the one way these two facts
    are meant to disagree: the listing says *these are the exact bytes*, the binding says *this is
    still the module those checks were put against*.
    """
    path, spelling_warnings, spelling_errors = _locate_sidecar(spec_dir, VERIFICATION_JSON)
    # A collision (root *and* `derived/`) is reported rather than raised, and it lands as a warning
    # here where the same collision on a fact table is an error, because the outcome is already the
    # weaker one: two attestations are two claims, neither may be preferred, so nothing is published.
    if spelling_errors:
        # A collision message is built by `layout` as a refusal and lands here as a warning, so it
        # arrives with no code of its own — coded at the point where it becomes a warning, which is
        # the only place that knows it is one.
        return None, [
            *(CodedWarning("verification_two_copies", e) for e in spelling_errors),
            *spelling_warnings,
        ]
    if path is None:
        return None, list(spelling_warnings)
    shown = path.relative_to(spec_dir)
    try:
        doc = read_verification(path)
    except (OSError, ValueError) as exc:
        return None, [
            *spelling_warnings,
            CodedWarning(
                "verification_unreadable",
                f"{shown} could not be read as a verification attestation ({exc}); this compile "
                f"records no verification. Re-run the checks (just-dna-enricher) to rewrite it.",
            ),
        ]
    failure = attestation_failure(doc, _module_binding(spec_dir))
    if failure is not None:
        # Naming the closure only when the dropped document actually carried one: the remedies differ
        # (re-running the checks is the enricher's job, re-closing is the author's), and a compile
        # that recommended both to everyone would send half its readers after a file they never had.
        remedy = (
            "Re-run the checks to attest these bytes, and close the module again."
            if doc.closure is not None
            else "Re-run the checks to attest these bytes."
        )
        return None, [
            *spelling_warnings,
            CodedWarning(
                "verification_stale",
                f"{shown} is stale: {failure}. The manifest records no verification for this "
                f"compile, which says nothing rather than claiming a pass. {remedy}",
            ),
        ]
    return verification_block(doc), list(spelling_warnings)


def build_disagreement_error(block: Verification | None) -> str | None:
    """The one recorded finding `strict` refuses on, or `None` (S78, RM143).

    **This does not move the strict line, and the distinction is the whole item.** `strict` means
    *reproducible*, never *right* — the compiler has no reference, so it cannot check a coordinate, and
    a whole file shifted by one base still passes. `genome_build_agreement` is the exception on
    internal-consistency grounds rather than correctness ones: a recorded finding there says the
    module's rows are **on a different assembly than the `genome_build` it declares**, which is one
    authored file contradicting another. Every other recorded finding is a disagreement between the
    module and an outside archive, where the archive is the stale side often enough that failing a
    build would have the format arbitrate someone else's dispute — that reasoning is unchanged and
    covers `clinical_significance`, `reference_allele` and the rest.

    **A fact the toolchain already established, not a check re-run here.** The judgement is the
    enricher's, made against the GRCh37 service the compiler may never call (Principle 2); what changed
    is that it stops being discarded at the boundary. So the gate keys on a *record* the enricher
    wrote — `findings > 0` on that one check — and the compiler adds no reference, no network and no
    opinion of its own.

    **Silent when no attestation exists, deliberately**, and that is not a hole this leaves open: an
    unverified module is the ordinary case, `_read_verification_block` says nothing about it on purpose,
    and refusing there would fail every module that has never been enriched. What this closes is the
    case where the answer *was* obtained and thrown away.

    A stale attestation is dropped before this sees it, which is the correct order: bytes that moved
    since the check ran are bytes the check did not judge.
    """
    if block is None:
        return None
    found = [r for r in block.checks if r.check == BUILD_AGREEMENT_CHECK and r.findings]
    if not found:
        return None
    total = sum(r.findings for r in found)
    subjects = sum(r.subjects for r in found)
    return (
        f"strict compile: verification.json records {total} row(s) of {subjects} whose coordinates "
        f"the enricher diagnosed as another assembly's ({BUILD_AGREEMENT_CHECK}). The module declares "
        f"a genome_build its own rows contradict, so the artifact would be internally consistent and "
        f"about the wrong locus. Read the record's `detail` for which rows and the rs-numbers to "
        f"author instead, fix the coordinates and re-run the checks — or compile without strict, "
        f"which builds it and says so."
    )


#: The one verification check whose findings `strict` acts on — see `build_disagreement_error`. Named
#: rather than inlined because it is the join between two tiers' vocabularies: the enricher writes this
#: member and the compiler reads it, and a rename on either side must not silently retire the gate.
BUILD_AGREEMENT_CHECK: str = "genome_build_agreement"


#: The authoring phase is not closed (RM73). Named because a consumer can only learn this from the
#: warning text until the manifest field reaches them, which is the unversioned-interface shape RM44
#: made a rule — `UNJOINABLE_PHRASE` is the precedent and a test pins this one the same way.
UNCLOSED_PHRASE: str = "records no closure"


def _closure_warning(block: Verification | None) -> list[str]:
    """The reminder that authoring was never declared finished — keyed on the OUTCOME, not the file.

    One sentence covers all three ways a compile ends up publishing no closure (no attestation
    document at all, one that no longer describes these bytes, one that was never closed), because
    what an author needs to know is the same in each: this artifact does not say the module is done.
    The reasons differ and the *other* warnings already carry them; repeating a diagnosis here would
    put two sentences on one cause.

    **Warning in both modes, and never a `strict` matter.** An unclosed module is perfectly
    reproducible — `strict` means "reproducible artifact", an unrelated axis — and this is the
    `not_covered` class read from the other end: a finding the author *can* clear, but whose severity
    is not the mode's business. It also carries no count, which is what keeps it collapsible under the
    de-duplication that runs it in both `validate_spec` and `compile_module`.
    """
    if block is not None and block.closure is not None:
        return []
    # Actionable, and the paragraph above already says why in so many words: a finding the author can
    # clear. `close` is the edit that clears it.
    return [
        CodedWarning(
            "module_not_closed",
            f"This module {UNCLOSED_PHRASE}: nothing in it states that authoring is finished, so a "
            f"consumer cannot tell a spec still being edited from one its author considers done. Run "
            f"`just-dna-compiler close <spec-dir>` when the module is complete — closing is a deliberate "
            f"act, it is never stamped by a passing check, and editing any authored file afterwards drops "
            f"the closure again. Compiling without one is a warning today; requiring it is filed for 1.0 "
            f"(RM73).",
        )
    ]


def _module_binding(spec_dir: Path) -> str:
    """The hash an attestation beside `spec_dir` must be bound to."""
    return module_binding(authored_input_entries(spec_dir))


def _literature_block(rows: list[LiteratureRow]) -> Literature | None:
    """The manifest's `literature` summary, or `None` when the module carries no citation sidecar.

    The counters are summed rather than recomputed so the manifest cannot claim more coverage than the
    sidecar recorded. `quotes_found` counts only rows where it is non-null: a null there means "no
    fulltext was retrievable", and folding that into zero would report an unchecked quote as a missing
    one — the single most misleading thing this block could say.

    **That per-row guard is not enough on its own, and `quotes_unchecked` is what finishes it** (S56).
    A sum over rows that are *all* null is `0`, so the sentence above described exactly what this
    block ended up saying one aggregation later: a module where no fulltext was ever retrieved
    published `quotes_found: 0`, indistinguishable from one where every quote was checked and missed.
    The count of null rows is published beside it rather than the pair being made nullable, because a
    reader needs the three states — found, missed, never asked — and `int | None` collapses the last
    two back into "no number".

    **And `quotes_unchecked` was not enough either, because it counts citations** (RM256, S109). An
    abstract-only row carries `quotes_found=0`, not null, so it was neither unchecked nor anything
    but a miss here: twenty-four quotes on one paywalled paper published as `quotes_found: 0,
    quotes_unchecked: 0`, the S56 reading one case over, while the enricher had already called all
    twenty-four unchecked. `quotes_checked` is the denominator in quote units, from the rule the
    enricher's report uses; `quotes_unchecked` keeps its published meaning rather than being
    redefined under a consumer who reads it.
    """
    if not rows:
        return None
    return Literature(
        signature=_literature_signature(rows),
        sources=sorted({r.source for r in rows if r.source}),
        row_count=len(rows),
        resolved_count=sum(1 for r in rows if r.exists is True),
        missing_count=sum(1 for r in rows if r.exists is False),
        open_access_count=sum(1 for r in rows if r.is_open_access is True),
        abstract_only_count=sum(1 for r in rows if r.quote_source == "abstract"),
        quotes_authored=sum(r.quotes_authored or 0 for r in rows),
        quotes_found=sum(r.quotes_found for r in rows if r.quotes_found is not None),
        quotes_checked=sum(r.quotes_checked() for r in rows),
        quotes_unchecked=sum(1 for r in rows if r.quotes_found is None),
    )


def _build_manifest(
    *,
    config: ModuleSpecConfig,
    spec_dir: Path,
    output_dir: Path,
    validation: ValidationResult,
    weights_rows: int,
    warnings: list[str],
    dropped_rows: dict[str, int] | None = None,
    compiled_by: str | None,
    ensembl_reference: str | None,
    logs: list[FileEntry],
    provenance: Provenance | None,
    logo: FileEntry | None,
    readme: FileEntry | None = None,
    content_sig: str | None = None,
    resolution_mode: str | None = None,
    fully_resolved: bool = False,
    resolution_subjects: int = 0,
    expanded_keys: int | None = None,
    expanded_rows: int | None = None,
    positional_rows: int | None = None,
    positional_rows_placed: int | None = None,
    resolution_sig: str | None = None,
    resolution_sources: list[str] | None = None,
    vrs_alleles: int = 0,
    vrs_alleles_identified: int = 0,
    frequency: Frequency | None = None,
    gene_metrics: GeneMetrics | None = None,
    gene_validity: GeneValidity | None = None,
    clinical_assertions: ClinicalAssertions | None = None,
    gwas_effects: GwasEffects | None = None,
    expression_effects: ExpressionEffects | None = None,
    clin_sig_concordance: ClinSigConcordance | None = None,
    literature: Literature | None = None,
    sources: Sources | None = None,
    verification: Verification | None = None,
) -> ModuleManifest:
    """Assemble the manifest from the spec, validation stats, and hashed input/output/log files."""
    module = config.module
    vstats = validation.stats
    # Pass an authored version into Identity only when it is already canonical SemVer — a freeform
    # advisory value (`v2`/`3`) stays None here (the registry stamps the canonical version on publish,
    # and Identity.version is SemVer-validated). Out of `artifact.digest` either way.
    authored_version = module.version if module.version and is_valid_version(module.version) else None
    _carried, _summary = classify(warnings)
    return ModuleManifest(
        # `version_coerced_from` is the authored string when the model rewrote it, and `None` when it
        # did not (RM103). Published because `identity.version` alone cannot distinguish an invented
        # `0.0.0` from an author who wrote one: the warning naming both values only ever existed in a
        # build log, and the artifact is what a consumer holds.
        identity=Identity(
            name=module.name,
            version=authored_version,
            version_coerced_from=module.version_coerced_from,
        ),
        display=Display(
            title=module.title,
            description=module.description,
            report_title=module.report_title,
            icon=module.icon,
            icon_set=module.icon_set,
            color=module.color,
        ),
        genome_build=config.genome_build,
        curator=config.defaults.curator,
        method=config.defaults.method,
        stats=Stats(
            variant_count=vstats.get("variant_count", 0),
            weights_rows=weights_rows,
            study_count=vstats.get("study_count", 0),
            gene_count=vstats.get("gene_count", 0),
            genes=vstats.get("genes", []),
            categories=vstats.get("categories", []),
            clinvar_count=vstats.get("clinvar_count", 0),
            pathogenic_count=vstats.get("pathogenic_count", 0),
            benign_count=vstats.get("benign_count", 0),
        ),
        compilation=Compilation(
            compile_success=True,
            compiled_by=compiled_by,
            compiler_version=_compiler_version(),
            ensembl_reference=ensembl_reference,
            compiled_at=_now_iso(),
            warnings=warnings,
            # RM131: derived here rather than in a `Compilation` validator, because that model is
            # also how a *published* manifest is read back — and a stored manifest's warnings are
            # plain JSON strings that classify into nothing. Deriving on read would rewrite what a
            # consumer holds; deriving on write says what this compile actually found.
            carried=_carried,
            warnings_summary=_summary,
            dropped_rows=dropped_rows or {},
            resolution_mode=resolution_mode,
            fully_resolved=fully_resolved,
            resolution_subjects=resolution_subjects,
            expanded_keys=expanded_keys,
            expanded_rows=expanded_rows,
            positional_rows=positional_rows,
            positional_rows_placed=positional_rows_placed,
            resolution_signature=resolution_sig,
            resolution_sources=resolution_sources or [],
            vrs_alleles=vrs_alleles,
            vrs_alleles_identified=vrs_alleles_identified,
        ),
        frequency=frequency,
        gene_metrics=gene_metrics,
        gene_validity=gene_validity,
        clinical_assertions=clinical_assertions,
        gwas_effects=gwas_effects,
        expression_effects=expression_effects,
        clin_sig_concordance=clin_sig_concordance,
        literature=literature,
        sources=sources,
        verification=verification,
        # Author-declared and copied through verbatim. NOT the `module.version` pattern, which a
        # publishing registry really does stamp: nothing overwrites this field, and
        # `_check_declared_license_agrees` compares it against the annotation-layer sources and warns,
        # which is the opposite of replacing it (RM111).
        license=config.license,
        # RM92: what the module's `weight` column means, copied verbatim. Advisory like `license`,
        # so it reaches the manifest and neither identity half.
        weighting=config.weighting,
        # RM134: whose clinical call this curator weighted, copied verbatim and read by nothing.
        # Same class as `weighting` — advisory, in the manifest, in neither identity half — and the
        # compile path deliberately does not consult it: resolving a disagreement between two
        # authorities needs a weighting model this format does not have.
        authority_precedence=list(config.authority_precedence),
        inputs=file_entries(spec_dir, list(_INPUT_FILES)),
        # `file_entries` skips what is absent, so a module carrying no sidecars gets an empty list
        # rather than a fabricated one — and a new optional sidecar cannot move an existing module's
        # manifest by appearing here.
        # Every accepted spelling *and* location is offered; `file_entries` skips the ones that are
        # not there, so the block records whichever the module actually carries (RM51/RM49) — and
        # `FileEntry.name` then carries `derived/…` for a split tree, which is what a registry
        # re-splitting a download needs. A module cannot carry two: `_locate_sidecar` refused before
        # anything was written.
        derived=file_entries(
            spec_dir, [name for csv in _DERIVED_FILES for name in sidecar_relative_names(csv)]
        ),
        content_signature=content_sig,
        artifact=build_artifact(output_dir, list(ARTIFACT_PARQUETS)),
        logs=logs,
        provenance=provenance,
        panel=config.panel,
        authorship=config.authorship,
        logo=logo,
        readme=readme,
    )
