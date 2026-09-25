"""`validate_spec` and the validation pass behind it, plus the overlay loader and its targets."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from just_dna_format.base import DEFAULT_GENOME_BUILD
from just_dna_format.concordance import ClinSigAuthorityCallRow, ClinSigConcordanceRow
from just_dna_format.findings import CodedWarning
from just_dna_format.frequency import FrequencyRow
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.gene_validity import GeneValidityRow
from just_dna_format.literature import LiteratureRow
from just_dna_format.overrides import (
    LOSSY_OVERLAY_TABLES,
    OVERRIDABLE_TABLES,
    VINDICATING_OVERLAY_TABLE,
    OverrideRow,
    apply_overrides,
    overlay_coherence_errors,
    update_targets,
)
from just_dna_format.resolution import ResolutionRow
from just_dna_format.sources import SourceRow
from just_dna_format.spec import RESERVED_FLAGS, StudyRow, VariantRow

from just_dna_compiler.compiler.allele_checks import (
    _apply_symbolic_drops,
    _check_allele_membership,
    _check_genotype_coverage,
    _check_p_value_num,
    _check_study_effect_alleles,
    _check_symbolic_alleles,
)
from just_dna_compiler.compiler.binning_checks import (
    _check_binning_deprecations,
    _check_binning_grounding,
    _check_measure_shape,
)
from just_dna_compiler.compiler.fact_checks import (
    _check_frequency_arithmetic,
    _check_gene_metrics_arithmetic,
    _check_gene_validity_currency,
    _classify_deferred_overlay_updates,
    _cross_check_clin_sig_concordance,
    _cross_check_gene_metrics,
    _cross_check_gene_validity,
    _cross_check_literature,
)
from just_dna_compiler.compiler.load import _load_csv_rows, _load_yaml, load_csv_rows
from just_dna_compiler.compiler.manifest import (
    _check_declared_license_agrees,
    _check_license_gate,
    _concordance_warnings,
    _verification_block,
    build_disagreement_error,
    module_stats,
)
from just_dna_compiler.compiler.positional import (
    _GENE_BEARING_TABLE_KINDS,
    _POSITIONAL_TABLE_KINDS,
    _apply_positional_resolution,
    _check_positional_joinability,
)
from just_dna_compiler.compiler.table_checks import (
    _check_misspelled_tables,
    _cross_validate_haplotype_definitions,
    _cross_validate_phase_ambiguity,
    _cross_validate_studies,
    _validate_table_kind,
)
from just_dna_compiler.compiler.tables import _FACT_TABLES, _TABLE_KINDS, OVERRIDES_CSV, _locate_sidecar
from just_dna_compiler.compiler.variant_checks import (
    _check_build_coordinates,
    _check_contig_ploidy,
    _CoordinateTable,
    _cross_validate_variants,
    _restamp_for_build,
)
from just_dna_compiler.compiler.vcf_checks import (
    _check_missing_allele_marker,
    _check_quality_inversion,
    _check_vcf_pointers,
)
from just_dna_compiler.compiler.vrs_checks import _verify_vrs_ids, _vrs_coverage_warnings
from just_dna_compiler.models import ValidationResult
from just_dna_compiler.resolution import ambiguous_refusals, unresolved_subjects, withdrawn_refusals
from just_dna_compiler.resolution_findings import resolution_not_injected, unresolved_rsid


def load_overlay(spec_dir: Path) -> tuple[list[OverrideRow], list[str], list[str]]:
    """Read `overrides.csv` and answer with `(rows, errors, warnings)` (RM124).

    **Public since RM136**, because the enricher needs it: an author who corrects a derived cell
    through the overlay must not go on being told the same finding by the tier that writes the file.
    Private, it would have been reached into the way `load_spec` was before S74, or — worse —
    reimplemented in the enricher, which is the drift the overlay's own design refuses.

    One loader for both public entry points, because both have to read it and a second copy is where
    `validate` and `compile` learn to disagree — the parity rule this module keeps re-learning
    (`@validate-refuses-all`). Everything it reports is structural: the rows parse or they do not, the
    key is duplicated or it is not, a key group carries one operation or several. Nothing here
    consults a derived table, which is what keeps every finding identical on both laps of a round
    trip.

    A file that is present with no rows is an **error**, the same answer `_TABLE_KINDS` gives: an
    empty authored table is a header somebody meant to fill.
    """
    path = spec_dir / OVERRIDES_CSV
    if not path.is_file():
        return [], [], []
    rows, errors, warnings = load_csv_rows(path, OverrideRow, OVERRIDES_CSV)
    if errors:
        return [], errors, warnings
    if not rows:
        return [], [f"{OVERRIDES_CSV} is present but has no rows."], warnings
    key_errors, key_warnings = _validate_table_kind(OVERRIDES_CSV, OverrideRow, rows)
    errors.extend(key_errors)
    warnings.extend(key_warnings)
    errors.extend(overlay_coherence_errors(rows))
    return rows, errors, warnings


def _overlay_targets_missing(overrides: list[OverrideRow], applied: set[str]) -> list[str]:
    """Warn about an overlay row naming a derived table this module does not carry.

    **The overlay lies on a table the module carries; it never creates one.** That is the scoping
    decision and not an omission: a table's rows come from the pass that derives them, and inventing a
    whole sidecar out of corrections would make the compiler a producer of facts, which is the line
    Principle 2 draws. Warning rather than refusing, in both modes, because the honest reading is
    ambiguous — the pass that writes the table may simply not have been run yet.
    """
    named = {row.table for row in overrides}
    missing = sorted(named - applied)
    if not missing:
        return []
    return [
        CodedWarning(
            "overlay_targets_missing_table",
            f"{OVERRIDES_CSV} corrects {', '.join(missing)}, which this module does not carry. An "
            f"overlay lies on top of a derived table and never creates one, so those rows change "
            f"nothing. Run the pass that writes the table, or drop the override rows.",
        )
    ]


def validate_spec(
    spec_dir: Path,
    authority_keys: Iterable[str] | None = None,
    *,
    strict: bool = False,
    resolve_with_ensembl: bool = True,
) -> ValidationResult:
    """Validate a module spec directory without producing output.

    `authority_keys` (inject-only) is the set of consumer/registry-owned identity keys to strip from
    the authored `module:` block before validation — pass `just_dna_format.normalize.
    IDENTITY_AUTHORITY_KEYS` (or your own set) so a legacy spec carrying `namespace:`/`owner:`/
    `canonical_id:` validates; the format applies none by default. Stripped keys are surfaced on
    `.info`. Everything else still trips `extra="forbid"`.

    `strict` mirrors `compile_module`'s flag and exists for one reason: several checks are a **mode
    ladder** (warning in `best_effort`, error in `strict`), so without a mode here the pre-flight
    could not answer the question the author actually asked — the documented order is `validate` then
    `compile --strict`, and a modeless `validate` is a pre-flight for the *other* compile.

    **It mirrors `compile_module`'s severities exactly, which is not the same as changing severity
    only** — this said the latter, in both of the two docstrings carrying it, and it was false
    (RM218). Two findings are *aggregates* with no `best_effort` counterpart sentence: the
    unresolved-position refusal (`strict compile: N variant(s) …`) and `build_disagreement_error`.
    Their `best_effort` rung is a different sentence — the per-subject `rsid_unresolved` warning,
    which fires in **both** modes — so under `strict` the aggregate is genuinely *added* rather than
    promoted. The contract the two commands share is that **`validate(strict=x)` and
    `compile(strict=x)` reach the same verdict**, not that the two modes of `validate` differ by a
    severity column.

    `resolve_with_ensembl` mirrors it for the same reason and is passed through by `compile_module`.
    The pre-flight applies the injected table to the positional 0.4 tables (RM43), and that decides
    whether their rows are reported as unjoinable — so a `validate` that ignored the master resolution
    switch would be *more optimistic* than the compile it precedes, which is the disagreement
    direction the parity rule exists to prevent.

    Stats include `genes`/`categories` as lists (filtering None) plus `variant_count`,
    `gene_count`, `study_count`, and the ClinVar quality counts
    (`clinvar_count`/`pathogenic_count`/`benign_count`) — the fields the manifest needs. See
    `ValidationResult.stats` for the full key contract.

    `warnings` is the complete list, unchanged; `carried` names the subset an author cannot clear and
    `warnings_summary` counts them by code (RM131). A caller that wants to keep *building* on this
    run's findings — as `compile_module` and `close_module` do — calls `_validate_spec` instead, for
    the reason given there.
    """
    return _validate_spec(spec_dir, authority_keys, strict=strict, resolve_with_ensembl=resolve_with_ensembl)[
        0
    ]


def _validate_spec(
    spec_dir: Path,
    authority_keys: Iterable[str] | None = None,
    *,
    strict: bool = False,
    resolve_with_ensembl: bool = True,
) -> tuple[ValidationResult, list[str]]:
    """`validate_spec`'s body, plus the findings list the result cannot carry back out.

    Pydantic coerces a `CodedWarning` to a plain `str` on its way into `ValidationResult.warnings`, which
    is right for the published surface and fatal for a caller that seeds its own channel from this
    one: `compile_module` starts from the pre-flight's warnings and keeps appending, and a seed that
    had lost its codes would arrive at `classify` unclassified. So the classified list comes back
    beside the result, and the two public entry points that continue a run take it.

    `authority_keys` (inject-only) is the set of consumer/registry-owned identity keys to strip from
    the authored `module:` block before validation — pass `just_dna_format.normalize.
    IDENTITY_AUTHORITY_KEYS` (or your own set) so a legacy spec carrying `namespace:`/`owner:`/
    `canonical_id:` validates; the format applies none by default. Stripped keys are surfaced on
    `.info`. Everything else still trips `extra="forbid"`.

    `strict` mirrors `compile_module`'s flag and exists for one reason: several checks are a **mode
    ladder** (warning in `best_effort`, error in `strict`), so without a mode here the pre-flight
    could not answer the question the author actually asked — the documented order is `validate` then
    `compile --strict`, and a modeless `validate` is a pre-flight for the *other* compile.

    **It mirrors `compile_module`'s severities exactly, which is not the same as changing severity
    only** — this said the latter, in both of the two docstrings carrying it, and it was false
    (RM218). Two findings are *aggregates* with no `best_effort` counterpart sentence: the
    unresolved-position refusal (`strict compile: N variant(s) …`) and `build_disagreement_error`.
    Their `best_effort` rung is a different sentence — the per-subject `rsid_unresolved` warning,
    which fires in **both** modes — so under `strict` the aggregate is genuinely *added* rather than
    promoted. The contract the two commands share is that **`validate(strict=x)` and
    `compile(strict=x)` reach the same verdict**, not that the two modes of `validate` differ by a
    severity column.

    `resolve_with_ensembl` mirrors it for the same reason and is passed through by `compile_module`.
    The pre-flight applies the injected table to the positional 0.4 tables (RM43), and that decides
    whether their rows are reported as unjoinable — so a `validate` that ignored the master resolution
    switch would be *more optimistic* than the compile it precedes, which is the disagreement
    direction the parity rule exists to prevent.

    Stats include `genes`/`categories` as lists (filtering None) plus `variant_count`,
    `gene_count`, `study_count`, and the ClinVar quality counts
    (`clinvar_count`/`pathogenic_count`/`benign_count`) — the fields the manifest needs. See
    `ValidationResult.stats` for the full key contract.
    """
    spec_dir = Path(spec_dir)
    all_errors: list[str] = []
    all_warnings: list[str] = []
    all_info: list[str] = []

    if not spec_dir.is_dir():
        return (
            ValidationResult(valid=False, errors=[f"Spec directory does not exist: {spec_dir}"]),
            [],
        )

    all_warnings.extend(_check_misspelled_tables(spec_dir))

    config, yaml_errors, dropped_authority = _load_yaml(spec_dir / "module_spec.yaml", authority_keys)
    all_errors.extend(yaml_errors)
    if dropped_authority:
        all_info.append(
            f"dropped injected authority keys from module: block (registry-stamped, not authored): "
            f"{dropped_authority}"
        )
    # `module.version` is advisory (the registry stamps the canonical Identity.version) and is COERCED
    # to SemVer by `ModuleInfo` since 0.5 (RM17). Report the rewrite rather than performing it here:
    # the model already did it, and `version_coerced_from` is how it says so. A clean
    # MAJOR.MINOR.PATCH coerces to itself and stays silent.
    if config is not None and config.module.version_coerced_from:
        all_warnings.append(
            CodedWarning(
                "module_version_coerced",
                f"module.version {config.module.version_coerced_from!r} was read as SemVer "
                f"{config.module.version!r}. It is advisory either way — the registry stamps the "
                f"canonical version on publish — but the module now compiles under the coerced value.",
            )
        )

    # The build every authored row below is loaded as being on. `config` is None when the yaml itself
    # failed to load, and the format's own default is the honest answer there — `validate` reports every
    # problem it can rather than stopping at the first, so the rows still have to be loaded somehow.
    declared_build = config.genome_build if config else DEFAULT_GENOME_BUILD

    # A module composes from optional table kinds (RM2): variants.csv is no longer mandatory — a PGx /
    # PharmGKB / PRS module carries only its own table(s). Load whatever is present.
    variants_path = spec_dir / "variants.csv"
    has_variants = variants_path.exists()
    variants: list[VariantRow] = []
    if has_variants:
        variants, var_errors, var_warnings = _load_csv_rows(
            variants_path, VariantRow, "variants.csv", genome_build=declared_build
        )
        all_errors.extend(var_errors)
        all_warnings.extend(var_warnings)
        # Before anything reads `variant_key`: a row is stamped at construction, where the module's
        # declared build is not knowable, so a non-GRCh38 module arrives carrying GRCh38-flavoured
        # ids. Fix the identity here, where both the row and the spec are in hand.
        all_warnings.extend(_restamp_for_build(variants, config.genome_build if config else "GRCh38"))

    # Validate each present 0.4 table kind against its model.
    kind_row_counts: dict[str, int] = {}
    loaded_kinds: dict[str, list[Any]] = {}
    for csv_name, _parquet, model in _TABLE_KINDS:
        kind_path = spec_dir / csv_name
        if not kind_path.exists():
            continue
        rows, kind_errors, kind_warnings = _load_csv_rows(
            kind_path, model, csv_name, genome_build=declared_build
        )
        all_errors.extend(kind_errors)
        all_warnings.extend(kind_warnings)
        kind_row_counts[csv_name] = len(rows)
        loaded_kinds[csv_name] = rows
        if not rows:
            if not kind_errors:
                all_errors.append(f"{csv_name} is present but has no rows.")
        elif not kind_errors:
            # Table-level coherence (bin overlap/gap, single sentinel, duplicate keys) — only when
            # every row validated, so the checks run on a complete, trustworthy set.
            tbl_errors, tbl_warnings = _validate_table_kind(csv_name, model, rows)
            all_errors.extend(tbl_errors)
            all_warnings.extend(tbl_warnings)

    # Cross-table PGx coherence: an allele used by the function/diplotype tables that the definition
    # table never defines can never be called. Runs after the loop so every kind is in hand.
    all_warnings.extend(
        _cross_validate_haplotype_definitions(
            loaded_kinds.get("haplotypes.csv", []),
            loaded_kinds.get("allele_function.csv", []),
            loaded_kinds.get("diplotypes.csv", []),
        )
    )
    all_warnings.extend(
        _cross_validate_phase_ambiguity(
            loaded_kinds.get("haplotypes.csv", []),
            loaded_kinds.get("diplotypes.csv", []),
        )
    )

    # Filled from `resolution.csv` below when it is present, and deliberately usable empty: allele
    # membership needs it only for a row that did not author its own `ref`/`alts`.
    membership_table: dict[str, list[ResolutionRow]] = {}
    # Injected resolution rows, grouped by the build each one records rather than by the module's:
    # `ResolutionRow.genome_build` is a column, so a row states which frame its numbers are in and
    # that is the frame its coordinate has to be possible in (RM48).
    resolution_by_build: dict[str, list[ResolutionRow]] = {}
    # Filled from `literature.csv` below; cross-checked once `studies.csv` is loaded further down.
    literature_rows: list[LiteratureRow] = []
    source_rows: list[SourceRow] = []

    # The injected tables: `resolution.csv` and the four 0.5 fact sidecars. They are not
    # `_TABLE_KINDS` — they are machine-produced and fact-hashed rather than authored DSL — but they
    # live in the spec directory and `compile_module` **refuses** on a bad row in any of them, so
    # leaving them out here made `validate` report `valid` for a directory `compile` then rejected.
    # That is the one thing this command must never do: the documented authoring order puts `validate`
    # immediately before `compile`, so it is the author's pre-flight, and a green pre-flight followed by
    # a refusal sends them looking for a change they did not make. Row-level validation, plus the
    # *self*-checks below — what stays compile-only is a check that needs **resolved** rows, which is a
    # narrower exemption than "a cross-check": `_verify_vrs_ids` compares a `resolution.csv` row against
    # its own content-addressed id and consults nothing else, so being a sidecar check never made it a
    # cross-check. Lumping the two together is how it stayed compile-only.
    #
    # **The overlay is applied inside this loop, before any check reads a row** (RM124). Every check
    # below asks what the module *asserts*, and since 0.7 that is the derived table plus the author's
    # recorded corrections — so a check reading the raw sidecar would report a finding the artifact
    # does not carry, and `compile` would then disagree with its own pre-flight.
    overrides, overlay_errors, overlay_warnings = load_overlay(spec_dir)
    all_errors.extend(overlay_errors)
    all_warnings.extend(overlay_warnings)
    overlaid: set[str] = set()
    #: RM137: `(table -> unmatched (subject, member) pairs)`, stashed from the loop below and split
    #: into its two readings once `studies.csv` is loaded. Computed on the PRE-overlay rows, because
    #: `apply_overrides` rebinds its input and an `insert` earlier in the same overlay would otherwise
    #: make a later update look matched.
    deferred_unmatched: dict[str, list[tuple[tuple[str, str], bool]]] = {}
    for csv_name, model in (
        ("resolution.csv", ResolutionRow),
        *((name, model) for name, _parquet, model in _FACT_TABLES),
    ):
        injected_path, spelling_warnings, spelling_errors = _locate_sidecar(spec_dir, csv_name)
        all_warnings.extend(spelling_warnings)
        all_errors.extend(spelling_errors)
        if injected_path is None:
            continue
        injected_rows, injected_errors, injected_warnings = _load_csv_rows(
            injected_path, model, injected_path.name
        )
        all_errors.extend(injected_errors)
        all_warnings.extend(injected_warnings)
        if csv_name in OVERRIDABLE_TABLES:
            # `overlaid` answers "does the module carry this table", which is what
            # `_overlay_targets_missing` reports on — so it is the file's PRESENCE that puts a name in
            # here, never whether it parsed. Gating it on a clean load made a malformed
            # `frequencies.csv` produce its load errors *and* "overrides.csv corrects frequencies.csv,
            # which this module does not carry", about a file sitting right there. The apply still
            # needs rows that parsed, so only that half stays behind the guard.
            overlaid.add(csv_name)
            if not injected_errors:
                # **Deferred for the two lossy tables, classified where the inputs exist** (RM137).
                # "Could an artifact of this module carry that row" needs `studies.csv` and the citing
                # tables, which this function loads further down — the same stash-here/check-later
                # shape the citation cross-check above already uses. The other six rebuild whole on a
                # reverse, so their unmatched warning is lap-stable already and takes the old path.
                # The two lossy tables (RM137) and the concordance record (RM117) both defer: the
                # first because reachability needs `studies.csv`, the second because an unmatched
                # answer there is the archive having caught up rather than a fault, and saying so is
                # the point.
                lossy = csv_name in LOSSY_OVERLAY_TABLES or csv_name == VINDICATING_OVERLAY_TABLE
                if lossy:
                    deferred_unmatched[csv_name] = update_targets(csv_name, injected_rows, overrides)
                injected_rows, apply_errors, apply_warnings = apply_overrides(
                    csv_name, injected_rows, overrides, defer_unmatched=lossy
                )
                all_errors.extend(apply_errors)
                all_warnings.extend(apply_warnings)
        if injected_rows and not injected_errors:
            # Table-level coherence for the fact tables too (RM107) — same function, same message, so
            # a duplicate key reads identically wherever it is found. Named by the file actually read
            # rather than by `csv_name`, since a sidecar may be under either spelling or under
            # `derived/`.
            tbl_errors, tbl_warnings = _validate_table_kind(injected_path.name, model, injected_rows)
            all_errors.extend(tbl_errors)
            all_warnings.extend(tbl_warnings)
            if model is GeneValidityRow:
                # Parity by CHECK, not by table (`@parity-by-check`): the currency finding is pure
                # computation over bytes the pre-flight has already loaded, needs no `output_dir` and
                # reads no resolved row, so it belongs here as well as in the compile. A green
                # pre-flight followed by a warning the author did not see coming is the shape
                # `validate` exists to prevent. The compile dedupes on message text, so a module
                # running both sees it once (`@no-rerun-with-counts`).
                all_warnings.extend(_check_gene_validity_currency(injected_rows))
            if model is GeneMetricsRow:
                # `@parity-by-check` again, and this is RM93's literal sibling (RM211).
                # `_check_frequency_arithmetic` was moved into this pre-flight for exactly this
                # reason and `_check_gene_metrics_arithmetic` — the same validate-by-redundancy over
                # a sidecar's own numbers, needing no `output_dir`, no reference and no resolved row
                # — was left behind in a per-model closure on the compile side. So a module whose
                # `oe_lof` disagrees with `obs_lof / exp_lof` passed a green `validate` and warned at
                # compile, which is the shape this pre-flight exists to prevent.
                #
                # The orphan check rides along because its key is a **gene**: `gene` is authored and
                # nothing fills it, so the answer here is the answer the compile reaches. Its three
                # position-keyed cousins stay compile-only, and that is the standing exemption
                # working rather than an oversight — see `_frequency_checks` below.
                all_warnings.extend(_check_gene_metrics_arithmetic(injected_rows))
                all_warnings.extend(_cross_check_gene_metrics(injected_rows, variants))
            if model is GeneValidityRow:
                # Same rule, same key. The currency finding above already runs here; the orphan one
                # is the other half of the same table's coherence and was reachable only at compile.
                all_warnings.extend(_cross_check_gene_validity(injected_rows, variants))
            if model is SourceRow:
                # Reads `sources.csv` against `module_spec.yaml`'s own `license:` — two authored
                # files, no sidecar join and no resolution. `_source_checks` is deliberately NOT
                # moved beside it: its `used_sources` is the set of sources the fact tables actually
                # cite, which is only complete once every sidecar in this loop has been read, so
                # asking it here would answer over a partial set and warn about orphans that are not.
                all_warnings.extend(
                    _check_declared_license_agrees(injected_rows, config.license if config else None)
                )
        if model is ResolutionRow and not injected_errors:
            for injected_row in injected_rows:
                membership_table.setdefault(injected_row.variant_key, []).append(injected_row)
                resolution_by_build.setdefault(injected_row.genome_build, []).append(injected_row)
            # A `ga4gh:VA.…` is the one column checkable with no reference, no network and no
            # dependency, so there is nothing about it that needs an `output_dir`. A **mismatch** is an
            # error in *both* modes, which is why this gap was reachable without `--strict` at all:
            # `validate` reported `valid` for a module a plain `compile` then refused as corrupt.
            # Gated on `not injected_errors` for the same reason `compile_module` is — a row that
            # failed to load cannot be re-derived from.
            vrs_errors, vrs_warnings = _verify_vrs_ids(injected_rows)
            all_errors.extend(vrs_errors)
            all_warnings.extend(vrs_warnings)
            # Coverage rides along for the same reason: counting absent ids reads injected bytes and
            # nothing else. It reports here too so an author sees the shortfall at pre-flight, where
            # the remedy (re-run the mint pass) is still cheap.
            all_warnings.extend(_vrs_coverage_warnings(injected_rows))
        if model is FrequencyRow and not injected_errors:
            # Validate-by-redundancy over the table's own numbers, here for the same parity reason as
            # `_verify_vrs_ids` above and missed for the same reason `_check_study_effect_alleles` was
            # (RM93): it lives in a per-model closure on the compile side, so a pass auditing table by
            # table saw `frequencies.csv` loaded here and stopped. Its integer half returns **errors**
            # in both modes, so leaving it compile-only let a plain `validate` report `valid` on a
            # module a plain `compile` refused. It reads the injected rows and nothing else — no
            # `output_dir`, no resolution — which is the standing test for what belongs in the
            # pre-flight. `@parity-by-check`, `@validate-refuses-all`.
            frequency_errors, frequency_warnings = _check_frequency_arithmetic(injected_rows)
            all_errors.extend(frequency_errors)
            all_warnings.extend(frequency_warnings)
        if model is ClinSigConcordanceRow and not injected_errors:
            # Reported at the pre-flight as well as at compile, for the reason the parity rule gives:
            # this reads injected bytes and the authored variant list and consults nothing else, so
            # there is nothing about it that needs an `output_dir`. It is also the finding an author
            # most wants *before* a compile — the answer to it is an `overrides.csv` row, and writing
            # one is cheap while the module is still open.
            all_warnings.extend(_concordance_warnings(injected_rows))
            all_warnings.extend(_cross_check_clin_sig_concordance(injected_rows, variants, table=csv_name))
        if model is ClinSigAuthorityCallRow and not injected_errors:
            all_warnings.extend(_cross_check_clin_sig_concordance(injected_rows, variants, table=csv_name))
        if model is LiteratureRow and not injected_errors:
            # Stashed rather than checked here: the citation sites (`studies.csv`, and since 0.6 the
            # binning tables' `pmid`) are loaded further down, so the cross-check runs once both are
            # in hand. Parity by CHECK, not by table — this is pure computation over injected and
            # authored bytes with no `output_dir`, so it belongs to the pre-flight, and it was
            # compile-only for the same reason `_check_allele_membership` was: nobody asked.
            literature_rows = injected_rows
        if model is SourceRow and not injected_errors:
            # Stashed for the `panel:` deprecation below, which cannot fire until it knows whether
            # the replacement field is actually filled (S69) — the same reason `literature_rows` is
            # held rather than checked in place.
            source_rows = injected_rows
            # The licence gate, run here for the same reason. It refuses in **both** modes and is pure
            # computation over injected bytes (the compiler holds no source→licence map, P2), so there
            # is nothing about it that needs an output directory — it was simply only wired into
            # `compile_module`. It is also the refusal most expensive to discover late: a module drafted
            # entirely from a no-sale source compiles right up to the gate.
            all_errors.extend(_check_license_gate(injected_rows))

    # After the loop, because it needs to know which covered tables were actually present.
    all_warnings.extend(_overlay_targets_missing(overrides, overlaid))

    # The `panel:` block lost its last reader in 0.6 (RM4) and is removed at 1.0. Warn-only, and the
    # block still compiles and still reaches `manifest.panel` exactly as before — the charter's
    # cadence is deprecate in a minor, remove at the next major.
    #
    # **It fires from here rather than beside `_load_yaml` because a deprecation in a minor is legal
    # only where its audience can ACT on it (P3), and whether they can depends on a value this pass
    # has not read until now (S69).** The replacement is the licence row's `dataset`, and a module
    # drafted before the drafter filled that column has an empty one — `merge_sources_file` is
    # never-clobber, so re-running the pass does not backfill it, and there is no path from such a
    # module to the state the old sentence assumed. It told that author to delete the block on the
    # strength of a replacement their module does not have.
    #
    # The other half is that the old sentence's closing clause was false in **both** states.
    # `GenePanelSpec` carries five fields and `dataset` is one release *label*: it cannot hold
    # `genes` (the denominator — which genes were searched and yielded nothing, the only thing
    # separating *not in the panel* from *in the panel, nothing found*), it cannot hold
    # `significance` (the predicate that makes the row set reproducible), and it is a name rather
    # than a digest so it cannot hold `reference_sha256`. So the advice is narrowed rather than
    # merely gated.
    if config is not None and config.panel is not None:
        replaced = any(
            row.source == "clinvar" and row.layer == "annotation" and (row.dataset or "").strip()
            for row in source_rows
        )
        unreplaced = (
            "`genes`, `significance` and `reference_sha256` have no replacement anywhere — keep the "
            "block until 1.0 if you need them recorded."
        )
        if replaced:
            all_warnings.append(
                CodedWarning(
                    "panel_block_deprecated",
                    "module_spec.yaml declares a `panel:` block. It is deprecated in 0.6 and removed at "
                    "1.0: the compiler never materialized rows from it, and the one thing that did read "
                    "it — the enricher's ClinVar clin_sig cross-check, deciding whether a drafted module "
                    "is being compared against its own source — now reads the `dataset` column of the "
                    "module's licence row, which `just-dna-enricher draft-panel` writes itself. The rows "
                    f"it describes are the authored variants.csv rows. {unreplaced}",
                )
            )
        else:
            all_warnings.append(
                CodedWarning(
                    "panel_block_deprecated",
                    "module_spec.yaml declares a `panel:` block, which is deprecated in 0.6 and removed "
                    "at 1.0 — but this module has no clinvar/annotation licence row carrying a "
                    "`dataset`, which is what replaced the block's one reader. Do NOT delete the block "
                    "yet: it is currently the only record of which snapshot this module was drafted "
                    "from. Fill the licence row's `dataset` first (re-drafting will not backfill it — "
                    f"the merge is never-clobber), then delete. {unreplaced}",
                )
            )

    # The verification attestation (RM45). Read here as well as in `compile_module` under the standing
    # rule — pure computation over injected bytes with no `output_dir` belongs in the pre-flight too —
    # and the two runs are safe to double precisely because this check is **not** a mode ladder and
    # its input does not differ between them: the binding is over the authored files, which no compile
    # step touches, so both passes reach the identical sentence and the dedup on the message below
    # collapses them. The block itself is discarded here; only the staleness warning is wanted, at the
    # point where an author can still re-run the checks before publishing.
    verification_doc, verification_warnings = _verification_block(spec_dir)
    all_warnings.extend(w for w in verification_warnings if w not in all_warnings)
    # And the one recorded finding `strict` acts on (S78, RM143), here so the pre-flight refuses what
    # the compile refuses — the standing parity rule, and this file has now closed that gap four
    # times. Pure computation over an injected sidecar with no `output_dir`, so it belongs on this
    # side by the rule's own test; the compile re-runs it because `compile_module` runs the pre-flight
    # in best_effort whatever its own mode, and only the compile knows the real severity.
    if strict:
        build_error = build_disagreement_error(verification_doc)
        if build_error is not None:
            all_errors.append(build_error)

    # The positional fill (RM43), and then the report of what it could not place. Both run here for
    # the same reason: pure computation over authored + injected bytes with no `output_dir`. The order
    # matters — filling first is what makes the joinability line describe the residue rather than the
    # whole table, and running the fill on one side only would have the pre-flight name a gap the
    # compile has already closed.
    #
    # **Over the rows a compile would keep, not every row loaded.** `compile_module` drops a row
    # carrying an unusable symbolic allele (RM5) *before* it resolves anything, so a pre-flight
    # filling and then counting the full set would report a coordinate gap over rows the artifact will
    # not contain. `_check_symbolic_alleles` is pure, so asking it for the drop set here costs a second
    # pass and nothing else; its **messages** are deliberately not taken — they belong to the block
    # further down that owns this check, and emitting them twice is the duplication the standing rule
    # about running a check in both commands exists to avoid. Under `strict` it reports rather than
    # drops, so the set is empty and nothing is filtered — which is also what the compile does there.
    _, _, would_drop = _check_symbolic_alleles({"variants.csv": variants, **loaded_kinds}, strict=strict)
    survivors = {
        csv_name: _apply_symbolic_drops(rows, would_drop.get(csv_name, set()))
        for csv_name, rows in loaded_kinds.items()
    }
    fill_warnings, fill_applied = _apply_positional_resolution(
        survivors, membership_table, declared_build, resolve=resolve_with_ensembl
    )
    all_warnings.extend(fill_warnings)
    all_warnings.extend(
        _check_positional_joinability(survivors, membership_table, declared_build, fill_applied=fill_applied)
    )

    # Composition: a module must carry at least one recognized table kind.
    if not has_variants and not kind_row_counts:
        all_errors.append(
            "module has no recognized table: add variants.csv or a 0.4 table "
            "(e.g. pharm_variants.csv, diplotypes.csv, pgs.csv)."
        )

    # Grounding (studies) is mandatory for *variant* annotations, so it is required iff variants.csv
    # is present. The 0.4 tables are exempt — but not, as this comment used to claim, because "they
    # carry their own evidence (e.g. evidence_level)". Two of the nine do: `DiplotypeRow` and
    # `PharmVariantRow`. `PgsRow` carries a catalog accession, which is a provenance and not a
    # citation, and the four binning kinds plus `HaplotypeRow`/`AlleleFunctionRow` carry nothing of the
    # sort. The real reason is that `StudyRow` can only name a variant, so for a gene-keyed table the
    # requirement would be unsatisfiable rather than merely unmet — which is S19/RM47, and is why
    # `_check_binning_grounding` below reports the absence instead of demanding the table.
    studies_path = spec_dir / "studies.csv"
    studies: list[StudyRow] = []
    if studies_path.exists():
        studies, study_errors, study_warnings = _load_csv_rows(
            studies_path, StudyRow, "studies.csv", genome_build=declared_build
        )
        all_errors.extend(study_errors)
        all_warnings.extend(study_warnings)
        if not studies and not study_errors:
            all_errors.append(
                "studies.csv is present but has no study rows. Grounding evidence is mandatory."
            )
        # Two encodings of one p-value, compared against each other — authored bytes only, no
        # resolution and no reference, so this belongs to the pre-flight as much as to the compile.
        # It is a pure mode ladder, which is what `strict` above is for.
        p_value_errors, p_value_warnings = _check_p_value_num(studies, strict=strict)
        all_errors.extend(p_value_errors)
        all_warnings.extend(p_value_warnings)
    elif has_variants:
        all_errors.append(
            "studies.csv is missing. Grounding evidence is mandatory; add study rows with PMIDs."
        )

    # RM137, and this is the point the loop above deferred to: `studies` and the citing tables are both
    # in scope now, so "could an artifact of this module carry that row" is answerable. Split here in
    # `validate_spec` as well as in `compile_module` because the two must report the same findings
    # (`@parity-by-check`) — the compile runs this pre-flight and dedupes on the message, so a module
    # running both sees each line once.
    all_warnings.extend(
        _classify_deferred_overlay_updates(
            deferred_unmatched,
            studies,
            loaded_kinds,
            variants,
            [row for rows in membership_table.values() for row in rows],
        )
    )

    # The other half of the same rule: a binning table states clinical thresholds and is exempt from
    # the requirement above, so nothing used to report a module that grounds none of them. Pure
    # computation over authored bytes with no `output_dir`, so it belongs to the pre-flight.
    all_warnings.extend(_check_binning_grounding(loaded_kinds, studies))
    # And the other defect those same tables carry: an integer tiling for a measurement VCF 4.4 makes
    # fractional and interval-valued (RM55/RM56). Same rule for why it is here — pure computation over
    # authored bytes, no `output_dir`.
    all_warnings.extend(_check_measure_shape(loaded_kinds))
    # And the column those tables are retiring (RM55's `modifier_cn`). Same rule again — it reads the
    # authored rows and nothing else, so the pre-flight must say it too, or an author clears their
    # `validate` and meets the notice for the first time at compile.
    all_warnings.extend(_check_binning_deprecations(loaded_kinds))
    # `.` in an alts cell, on every table that has one (RM58). Also pure, also authored-only, and it
    # reads `loaded_kinds` plus `variants` rather than a table name, so a future kind with an `alts`
    # column joins the check by declaring the column.
    all_warnings.extend(_check_missing_allele_marker(variants, loaded_kinds, declared_build))

    # Symbolic/structural alleles the module cannot actually apply (RM5). Pure computation over
    # authored bytes and a **mode ladder** on the droppable tables, so it belongs here by the standing
    # rule — the same one `_check_allele_membership` was moved here under. Nothing is dropped in this
    # command; the message states what a compile will do, which is what a pre-flight is for.
    symbolic_errors, symbolic_warnings, _ = _check_symbolic_alleles(
        {"variants.csv": variants, **loaded_kinds}, strict=strict
    )
    all_errors.extend(symbolic_errors)
    all_warnings.extend(symbolic_warnings)

    # Coordinates that cannot exist in the build they are recorded under (RM48) — pure arithmetic over
    # authored and injected bytes with no `output_dir`, so it belongs to the pre-flight by the standing
    # rule, and it is the finding an author most wants *before* a compile: a wrong-build coordinate is
    # cheap to fix and impossible to notice once it is a published digest.
    #
    # `resolution.csv` is in scope on purpose. Leaving it out would recreate the parity defect this
    # check exists beside: an rsid-only authored row carries no coordinate here, so `validate` would
    # see nothing while `compile` fills the position from the injected table and refuses — a green
    # pre-flight followed by a refusal for a change the author did not make. Each resolution row is
    # judged against **its own** `genome_build`, which is what that column is for.
    all_errors.extend(
        _check_build_coordinates(
            [
                _CoordinateTable("variants.csv", declared_build, True, variants),
                _CoordinateTable("studies.csv", declared_build, True, studies),
                *(
                    _CoordinateTable(csv_name, declared_build, True, loaded_kinds.get(csv_name) or [])
                    for csv_name, _model in _POSITIONAL_TABLE_KINDS
                ),
                *(
                    _CoordinateTable("resolution.csv", build, False, rows)
                    for build, rows in sorted(resolution_by_build.items())
                ),
            ]
        )
    )

    # Resolution *coverage*, by the same parity rule and for the case that reported it (S76). This is
    # the standing exemption's edge: what stays compile-only is a check reading **resolved** rows, and
    # this one does not — it asks whether the injected table *can* place each authored row, which is
    # arithmetic over the bytes already loaded here. `unresolved_subjects` is the predicate
    # `resolve_from_table` applies, shared rather than restated, so the two sides cannot drift into
    # disagreeing about which rows are unplaceable.
    #
    # It matters because the gap was the loud half of a silent failure: a spec whose `resolution.csv`
    # covers some of its variants passes `validate --strict` clean and is refused by
    # `compile --strict`, which is the green-pre-flight-then-refusal shape this rule exists to stop.
    # An author whose enrich run was killed partway sees nothing until the compile.
    #
    # Both severities mirror the compile exactly. The per-subject warnings carry `rsid_unresolved`,
    # the code `resolve_from_table` already emits for the identical sentence, so `compile_module` —
    # which runs this pre-flight in best_effort whatever its own mode — de-duplicates them on the
    # message rather than publishing each twice (the `_check_contig_ploidy` idiom). Neither message
    # embeds a count that resolution could change, which is what makes re-running one safe here.
    #
    # **Nobody-asked is not asked-and-absent, and the two get different messages** — the compile's own
    # split, mirrored rather than re-invented. With a table present, a row it does not cover is absent
    # from something that was consulted, and `resolve_from_table` names each such row. With no table at
    # all nothing was consulted, and the compile says so once, in one aggregated line, instead of
    # blaming a file that does not exist once per variant. Both refuse under `strict`, because a
    # partial artifact is unreproducible either way.
    if variants and resolve_with_ensembl:
        unplaceable = unresolved_subjects(variants, membership_table, declared_build)
        if membership_table:
            all_warnings.extend(
                w
                for w in (
                    CodedWarning(
                        "rsid_unresolved",
                        unresolved_rsid(
                            name,
                            searched="the resolution table",
                            consequence="position remains unset",
                        ),
                    )
                    for name in unplaceable
                )
                if w not in all_warnings
            )
        elif unplaceable:
            all_warnings.append(
                CodedWarning(
                    "resolution_not_injected",
                    resolution_not_injected(
                        missing="No resolution.csv and no ensembl_cache injected",
                        remedy="Produce a resolution.csv with just-dna-enricher.",
                    ),
                )
            )
        if strict and unplaceable:
            all_errors.append(
                f"strict compile: {len(unplaceable)} variant(s) have unresolved genomic "
                f"positions after resolution: {unplaceable}. A partial artifact would not be "
                f"byte-reproducible; inject a complete Ensembl reference (ensembl_cache=) or "
                f"compile without strict."
            )

    # The two refusals `resolve_from_table` raises over the injected table itself, asked here for the
    # same reason the coverage check above is: they read the table's own columns and no *resolved*
    # row, so the standing compile-only exemption does not cover them (`@validate-refuses-all`).
    # `withdrawn` is fatal in **both** modes and was the sharper gap — a green `validate --strict`
    # followed by a plain `compile` refusing is the exact sequence this pre-flight exists to prevent,
    # and it was reproducible on a reference example with one column changed (RM207).
    #
    # Both sentences come from the shared helpers rather than being re-phrased here, so there is one
    # of each text. Neither embeds a count, which is what makes asking them on both sides safe
    # (`@no-rerun-with-counts`); `compile_module` de-duplicates errors the way it already does for
    # `rsid_unresolved`'s warnings.
    #
    # **The prefixes are copied deliberately.** `compile_module` publishes these two as
    # `resolution: …` and `strict resolution: …`, and that text is what a consumer greps
    # (`@warning-text-is-api`). Emitting the bare sentence here would change the published string on
    # every module that carries one — so the *sentence* is shared, from one helper, and only the
    # channel label is restated. The pre-flight's own mode is not `compile_module`'s: it always runs
    # this side in best_effort, so the `strict` arm below is `validate --strict`'s, and the compile
    # reaches the identical text by its own strict path.
    if variants and resolve_with_ensembl and membership_table:
        all_errors.extend(
            f"resolution: {e}" for e in withdrawn_refusals(variants, membership_table, declared_build)
        )
        if strict:
            all_errors.extend(
                f"strict resolution: {e}"
                for e in ambiguous_refusals(variants, membership_table, declared_build)
            )

    # Same rule about where a check belongs: the VCF pointer columns are authored cells read against
    # two spec-derived constants, with no resolution step and no `output_dir` in sight, so the
    # pre-flight is exactly where an author should hear about them.
    all_warnings.extend(_check_vcf_pointers(variants, loaded_kinds))

    # The injected citation sidecar against BOTH citation sites, now that studies are loaded.
    #
    # **`survivors`, not `loaded_kinds`** (RM210). Every message this check builds embeds a COUNT, and
    # `compile_module` runs it a second time over its own post-drop tables, de-duplicating on the
    # message. Handing this side the pre-drop tables made the two sentences differ by a number, so both
    # survived the dedup and one manifest carried "1 citation(s) … ['99999999']" beside "2 citation(s)
    # … ['29165669', '99999999']" with `warnings_summary: {literature_row_uncited: 2}` for one finding.
    # `@no-rerun-with-counts` is the rule; the repair is to make the two inputs the same rather than to
    # stop re-running, because a citing table that is also symbolic-droppable (`pharm_variants.csv` is
    # both) is the only thing that separated them. `survivors` is the same post-drop view the
    # positional fill above already uses, computed once for exactly this reason.
    all_warnings.extend(_cross_check_literature(literature_rows, studies, survivors))

    # The study-side half of allele membership (RM91), here for the same parity reason as the check
    # below: it is a mode ladder, so leaving it compile-only would let `validate --strict` report valid
    # on a module `compile --strict` refuses.
    #
    # **Outside `if variants:`, and that is the whole of RM93's first half.** It sat inside, under a
    # comment claiming it was audited "by check, not by table", so it never ran for the one composition
    # it was written for: a module with a table kind, `studies.csv` and `resolution.csv` and no
    # `variants.csv` at all. The compile side has always run it unconditionally, so the two disagreed
    # exactly where it mattered. `membership_table` is filled from `resolution.csv` in the sidecar loop
    # far above and is in scope regardless of whether any variant was authored, which is why the check
    # simply moves rather than needing an input rebuilt. `@parity-by-check`, `@validate-refuses-all`.
    study_allele_errors, study_allele_warnings = _check_study_effect_alleles(
        studies, membership_table, strict=strict
    )
    all_errors.extend(study_allele_errors)
    all_warnings.extend(study_allele_warnings)

    if variants:
        cross_errors, cross_warnings = _cross_validate_variants(variants)
        all_errors.extend(cross_errors)
        all_warnings.extend(cross_warnings)
        # The quality floor that inverts on the record it is read from (RM57). Authored cells only —
        # resolution fills neither `requires_callable` nor `quality_from` — so the pre-flight sees
        # exactly what the compile will.
        all_warnings.extend(_check_quality_inversion(variants))
        # Allele membership, which was compile-only and should never have been. It is pure computation
        # over authored rows plus the injected table, needs no `output_dir` — the standing rule for what
        # belongs here — and it is a **mode ladder**, so `validate --strict` reported `valid` for a
        # module `compile --strict` then refused. The same defect the 2026-08-07 audit fixed for
        # `_verify_vrs_ids` and `_check_p_value_num`; this one sat beside them and was missed because
        # that pass went table by table rather than check by check. Its docstring already says it runs
        # on the AUTHORED rows *before* resolution expands them, which is exactly what makes it
        # computable here, where there is no resolution step at all. `membership_table` is empty when
        # the module carries no `resolution.csv`, and that is a working input: a row authoring its own
        # `ref`/`alts` is judged against those, and a row with neither is skipped either way.
        membership_errors, membership_warnings = _check_allele_membership(
            variants, membership_table, strict=strict
        )
        all_errors.extend(membership_errors)
        all_warnings.extend(membership_warnings)
        # Genotype coverage (S32). Here and **only** here: it is warning-only in both modes, so there
        # is no severity a compile-side re-run could recover, and its message carries a count — which
        # after resolution would be counted over the expanded rows and print a second, differently
        # numbered copy of the same finding into `manifest.compilation.warnings`. It reads authored
        # genotypes plus, for the reference allele alone, the injected table, so this side sees
        # everything it needs. `compile_module` inherits the warning through `validation.warnings`.
        all_warnings.extend(_check_genotype_coverage(variants, membership_table))
        # Ploidy runs here *and* post-resolution in `compile_module`, because the two passes see
        # different rows. Here it catches a hand-written `MT,3243,A/G` on the standalone `validate`
        # command, where there is no resolution step at all; there it catches the rsID-authored form,
        # whose `chrom` does not exist until the table has been consulted. A row that both passes can
        # see produces the same string twice, which compile de-duplicates.
        # `config` is None when the spec itself failed to load; default rather than crash, since
        # the point of `validate` is to report every problem it can, not to stop at the first.
        all_warnings.extend(_check_contig_ploidy(variants, config.genome_build if config else "GRCh38"))
        if studies:
            _, study_warnings = _cross_validate_studies(studies, variants)
            all_warnings.extend(study_warnings)
        # `flags` is an open vocabulary — surface non-reserved tags as INFO (not a warning; nothing
        # is wrong). ROADMAP 0.3 item 4.
        unknown_flags = sorted(
            {tag for v in variants if v.flags for tag in v.flags if tag not in RESERVED_FLAGS}
        )
        if unknown_flags:
            all_info.append(
                f"Non-reserved flags in use (allowed; reserved tags are "
                f"{sorted(RESERVED_FLAGS)}): {unknown_flags}"
            )

    stats: dict[str, Any] = {"study_count": len(studies)}
    if config:
        stats["module_name"] = config.module.name
    if kind_row_counts:
        stats["table_rows"] = kind_row_counts
    # The family-independent size, promoted from de-facto to documented (S72). The scalar counters
    # below describe `variants.csv` alone, so `variant_count: 0` on a `pharm_variants`-led module is
    # narrow rather than wrong — but a caller asking *how big is this module* had only `table_rows`,
    # which nothing in the contract mentioned.
    #
    # `variants.csv` and `studies.csv` are the SNP core and sit OUTSIDE `_TABLE_KINDS`, so they are
    # added by hand rather than swept up — the first draft summed `kind_row_counts` alone and
    # reported `row_count: 0` for a twelve-variant module, which is the very defect this key exists
    # to fix, one family over. Counted as authored rows (not distinct keys, which is `variant_count`'s
    # job) so the number means the same thing for every family.
    stats["row_count"] = sum(kind_row_counts.values()) + len(variants) + len(studies)
    gene_bearing = {
        csv_name: loaded_kinds.get(csv_name) or [] for csv_name, _model in _GENE_BEARING_TABLE_KINDS
    }
    # Unconditional where it used to be `if variants:` — a table-only module has no variant rows and is
    # exactly the module whose genes were being dropped (S57). The keys this adds for such a module are
    # all zero, which is what `Stats` already defaults them to, so no manifest number moves by it.
    if variants or any(gene_bearing.values()):
        stats.update(module_stats(variants, gene_bearing))
    all_warnings.extend(_check_composite_gene_cells(variants, gene_bearing))

    return (
        ValidationResult(
            valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            info=all_info,
            stats=stats,
        ),
        all_warnings,
    )


#: Separators that make a `gene` cell look like a list. Not a splitting rule — a detection one. `;`
#: is the reported case (ClinPGx exports `IFNL3;IFNL4` for the locus); the others are here because a
#: cell carrying any of them has the same effect on `stats.genes` and the same ambiguity about intent.
_GENE_LIST_SEPARATORS = (";", ",", "|", "/")


def _check_composite_gene_cells(variants: list[VariantRow], kind_rows: dict[str, list[Any]]) -> list[str]:
    """Warn when a single-valued `gene` cell looks like a list, and split nothing (S72).

    Since RM121 made `stats.genes` the field a registry's gene index is fed from, a composite cell
    becomes a **third gene** beside its two parts — `module_stats` does `genes.add(gene)` on the raw
    value — so `IFNL3;IFNL4` is published as a search term nobody will ever type. `VariantRow.gene` is
    `str | None` with no validator and neither is any other kind's, so nothing noticed.

    **It reports and never repairs, which is the reporter's own scoping and the right call.** Splitting
    would guess at a vocabulary, and `IFNL3;IFNL4` may legitimately name *the locus*, which is a real
    thing in that dataset — the value also came straight out of an upstream export rather than being
    the author's invention, so refusing it would refuse a faithful transcription. Naming the rows lets
    a human decide which of the two it is; that is all this can honestly do.

    Aggregated by cell rather than emitted per row: the reported module carried 33 rows sharing one
    value, and a per-row warning would be 33 lines saying one thing.
    """
    seen: dict[str, int] = {}
    for row in [*variants, *(r for rows in kind_rows.values() for r in rows)]:
        gene = (getattr(row, "gene", None) or "").strip()
        if gene and any(sep in gene for sep in _GENE_LIST_SEPARATORS):
            seen[gene] = seen.get(gene, 0) + 1
    if not seen:
        return []
    named = ", ".join(f"{cell!r} ({count} row(s))" for cell, count in sorted(seen.items()))
    return [
        CodedWarning(
            "composite_gene_cell",
            f"{len(seen)} gene cell(s) contain a list separator and are published as single gene names: "
            f"{named}. `stats.genes` is what a registry's gene index reads, so a composite value becomes "
            f"a gene nobody will search for, beside its parts. Nothing is split here — a composite may "
            f"legitimately name the locus — so either give the row one symbol, or leave it and know the "
            f"index will not find the module by either part.",
        )
    ]
