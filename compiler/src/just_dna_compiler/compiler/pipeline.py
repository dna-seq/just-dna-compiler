"""`compile_module` and `close_module`: the compile pipeline end to end."""

import warnings
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from just_dna_format.assertions import ClinicalAssertionRow
from just_dna_format.concordance import ClinSigAuthorityCallRow, ClinSigConcordanceRow
from just_dna_format.expression import ExpressionEffectRow
from just_dna_format.findings import CodedWarning
from just_dna_format.frequency import FrequencyRow
from just_dna_format.gene_metrics import GeneMetricsRow
from just_dna_format.gene_validity import GeneValidityRow
from just_dna_format.gwas import GwasEffectRow
from just_dna_format.integrity import resolution_signature as _resolution_signature
from just_dna_format.layout import SOURCES_CSV, VERIFICATION_JSON, SidecarCollision, sidecar_write_path
from just_dna_format.literature import LiteratureRow
from just_dna_format.manifest import VerificationDoc, write_manifest
from just_dna_format.normalize import now_utc_iso
from just_dna_format.overrides import (
    LOSSY_OVERLAY_TABLES,
    OVERRIDABLE_TABLES,
    VINDICATING_OVERLAY_TABLE,
    OverrideRow,
    apply_overrides,
    update_targets,
)
from just_dna_format.resolution import ResolutionRow
from just_dna_format.sources import SourceRow
from just_dna_format.spec import StudyRow, VariantRow
from just_dna_format.verification import (
    attest,
    attestation_failure,
    close,
    read_verification,
    write_verification,
)
from pydantic import ValidationError

from just_dna_compiler.compiler.allele_checks import (
    _apply_symbolic_drops,
    _check_allele_membership,
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
    _check_ba1_lint,
    _check_frequency_arithmetic,
    _check_gene_metrics_arithmetic,
    _check_gene_validity_currency,
    _classify_deferred_overlay_updates,
    _cross_check_clin_sig_concordance,
    _cross_check_clinical_assertions,
    _cross_check_frequencies,
    _cross_check_gene_metrics,
    _cross_check_gene_validity,
    _cross_check_gwas_effects,
    _cross_check_literature,
    split_cited_literature,
)
from just_dna_compiler.compiler.load import _load_csv_rows, _load_yaml, content_signature
from just_dna_compiler.compiler.manifest import (
    UNCLOSED_PHRASE,
    _build_manifest,
    _check_declared_license_agrees,
    _check_license_gate,
    _clin_sig_concordance_block,
    _clinical_assertions_block,
    _collect_logo,
    _collect_logs,
    _collect_provenance,
    _collect_readme,
    _concordance_warnings,
    _expression_effects_block,
    _frequency_block,
    _gene_metrics_block,
    _gene_validity_block,
    _gwas_effects_block,
    _literature_block,
    _module_binding,
    _source_checks,
    _sources_block,
    _verification_block,
    build_disagreement_error,
    module_stats,
)
from just_dna_compiler.compiler.parquets import (
    _build_annotations,
    _build_frequencies,
    _build_studies,
    _build_weights,
)
from just_dna_compiler.compiler.positional import (
    _apply_positional_resolution,
    _check_positional_joinability,
    positional_placement,
)
from just_dna_compiler.compiler.tables import (
    _FACT_TABLES,
    _TABLE_KINDS,
    BA1_ALLELE_FREQUENCY_THRESHOLD,
    OVERRIDES_PARQUET,
    SNP_CORE_PARQUETS,
    _build_table,
    _locate_sidecar,
)
from just_dna_compiler.compiler.validate import _overlay_targets_missing, _validate_spec, load_overlay
from just_dna_compiler.compiler.variant_checks import (
    _check_build_coordinates,
    _check_contig_ploidy,
    _CoordinateTable,
    _cross_validate_variants,
    _restamp_for_build,
)
from just_dna_compiler.compiler.vrs_checks import _verify_vrs_ids, _vrs_coverage, _vrs_coverage_warnings
from just_dna_compiler.models import ClosureResult, CompilationResult
from just_dna_compiler.resolution import resolve_from_table
from just_dna_compiler.resolution_findings import resolution_not_injected


def compile_module(
    spec_dir: Path,
    output_dir: Path,
    compression: str = "zstd",
    resolve_with_ensembl: bool = True,
    ensembl_cache: Path | None = None,
    compiled_by: str | None = None,
    ensembl_reference: str | None = None,
    log_files: list[Path] | None = None,
    provenance_file: Path | None = None,
    logo_file: Path | None = None,
    readme_file: Path | None = None,
    authority_keys: Iterable[str] | None = None,
    strict: bool = False,
    ba1_threshold: float = BA1_ALLELE_FREQUENCY_THRESHOLD,
) -> CompilationResult:
    """Compile a module spec directory into parquet files plus a `manifest.json`.

    Args:
        spec_dir: Path to the module spec directory.
        output_dir: Directory for output parquet files + manifest.json.
        compression: Parquet compression codec.
        resolve_with_ensembl: Master switch for resolution — of **every** kind, despite the name.
            With a `resolution.csv` present it drives the preferred, source-independent table path;
            `ensembl_cache` is the deprecated fallback. Setting it False with a `resolution.csv`
            present disables that table too, and warns, because the compile then succeeds with no
            resolved position on any row.
        ensembl_cache: **Deprecated (removed at 1.0).** Path to a prebuilt Ensembl DuckDB or parquet
            cache dir. In-compiler DuckDB resolution has moved to `just-dna-enricher`; when given, this
            emits a `DeprecationWarning` and routes to the enricher (which must be installed). Prefer
            producing a `resolution.csv` (`just-dna-enricher enrich`) — the compiler then resolves with
            no reference and no network.
        compiled_by: Provenance tag for the manifest (the marketplace passes "marketplace-server";
            a local compile leaves it None, so downloaders treat it as untrusted).
        ensembl_reference: Pinned reference id recorded in the manifest for reproducibility.
        log_files: Explicit run/provenance log files to record. If None, auto-discovers a top-level
            `*.log` plus per-role files under `spec_dir/logs/`. Logs are optional.
        provenance_file: Explicit structured-provenance document. If None, auto-discovers
            `spec_dir/provenance.json`. Optional; summarized into `manifest.provenance`.
        logo_file: Explicit module logo image. If None, auto-discovers `spec_dir/logo.{png,jpg,jpeg}`.
            Optional; hashed into `manifest.logo`, kept out of `artifact.digest`.
        readme_file: Explicit module readme. If None, auto-discovers the first of
            `manifest.README_CANDIDATES` (`README.md` first) beside the spec. Optional; hashed into
            `manifest.readme`, kept out of `artifact.digest` and `content_signature` — prose about the
            module is not part of its identity, so fixing a caveat is a patch (S25).
        authority_keys: Inject-only set of consumer/registry-owned identity keys to strip from the
            authored `module:` block before validation (e.g. `just_dna_format.normalize.
            IDENTITY_AUTHORITY_KEYS`). None strips nothing.
        strict: All-or-nothing compile. When True, fail (rather than emit a partial artifact) if any
            variant still lacks a resolved genomic position (`chrom`+`start`) after resolution — an
            unresolved position means the injected reference was incomplete/absent and the parquet
            bytes (hence `artifact.digest`) would not be reproducible. Default False keeps the
            best-effort behavior (positions left unset, surfaced as warnings).
        ba1_threshold: Allele frequency above which a `pathogenic` variant draws the ACMG BA1 warning
            (`_check_ba1_lint`). Defaults to ACMG's 5%. Raise it for a module curating a common
            recessive carrier allele, where the default fires on correct data. Warning-only in both
            modes, so this tunes noise, never whether the compile succeeds.
    """
    spec_dir = Path(spec_dir)
    output_dir = Path(output_dir)

    # `strict` is deliberately NOT passed (the pre-flight runs in best_effort whatever this compile's
    # mode, which is why every mode-ladder check re-runs below); `resolve_with_ensembl` is, because it
    # is not a severity — it decides whether the injected table is consulted at all, and a pre-flight
    # answering that differently would seed `all_warnings` with a finding this compile contradicts.
    validation, validation_findings = _validate_spec(
        spec_dir, authority_keys, resolve_with_ensembl=resolve_with_ensembl
    )
    if not validation.valid:
        # The classified list, not `validation.warnings` — a failed compile publishes the same
        # readable channel a successful one does, and the model's copy has lost its codes.
        return CompilationResult(success=False, errors=validation.errors, warnings=validation_findings)

    config, _, _ = _load_yaml(spec_dir / "module_spec.yaml", authority_keys)
    assert config is not None
    module_name = config.module.name

    # A module composes from optional table kinds (RM2): load whatever is present.
    variants: list[VariantRow] = []
    if (spec_dir / "variants.csv").exists():
        variants, _, _ = _load_csv_rows(
            spec_dir / "variants.csv",
            VariantRow,
            "variants.csv",
            genome_build=config.genome_build,
        )
        # Same re-stamp as in `validate_spec`; this function re-loads its own rows, so the fix has to
        # happen on both copies or the artifact would carry the un-corrected keys.
        _restamp_for_build(variants, config.genome_build)
    studies: list[StudyRow] = []
    if (spec_dir / "studies.csv").exists():
        studies, _, _ = _load_csv_rows(
            spec_dir / "studies.csv", StudyRow, "studies.csv", genome_build=config.genome_build
        )
    # The 0.4 table kinds, loaded here rather than at materialization time. Two reasons, and the
    # second is the load-bearing one: the symbolic-allele check below has to reach them, and a check
    # that can refuse must do so **before** `output_dir.mkdir()` — the placement the licence gate
    # already has, for the same reason. (It also removes a second load of every table kind.)
    kind_rows: dict[str, list[Any]] = {}
    for csv_name, _parquet_name, model in _TABLE_KINDS:
        if (spec_dir / csv_name).exists():
            kind_rows[csv_name], _, _ = _load_csv_rows(
                spec_dir / csv_name, model, csv_name, genome_build=config.genome_build
            )

    # Seeded from the classified list rather than from `validation.warnings`, whose members pydantic
    # has already flattened to plain strings. The two lists carry identical text, so every `if w not
    # in all_warnings` de-duplication below still compares exactly what it compared before.
    all_warnings = list(validation_findings)

    # Symbolic/structural alleles the module cannot apply (RM5). Runs before anything is written, and
    # before resolution, because it decides which rows exist: under `best_effort` a row stating an
    # unusable rule is **dropped** (the warning says so — `reverse` will not re-emit it), under
    # `strict` the compile refuses. Re-run here rather than trusted from `validate_spec`, which ran in
    # `best_effort` whatever this compile's mode; the warnings it already produced are de-duplicated
    # on the message, the way ploidy's and allele-membership's are.
    symbolic_errors, symbolic_warnings, symbolic_drops = _check_symbolic_alleles(
        {"variants.csv": variants, **kind_rows}, strict=strict
    )
    all_warnings.extend(w for w in symbolic_warnings if w not in all_warnings)
    if symbolic_errors:
        return CompilationResult(success=False, errors=symbolic_errors, warnings=all_warnings)
    for table, drop_rows in symbolic_drops.items():
        if table == "variants.csv":
            variants = _apply_symbolic_drops(variants, drop_rows)
        else:
            kind_rows[table] = _apply_symbolic_drops(kind_rows[table], drop_rows)
    if symbolic_drops:
        # Re-derive the stats over what survived. `validate_spec` computed them from the full set, and
        # `weights_rows` counts the parquet, so leaving them would publish a `variant_count` higher
        # than the artifact holds (the RM44 class: a manifest number a catalog keys on and cannot
        # check). **After the whole loop, not inside its `variants.csv` branch** — since S57 put the
        # gene facets on every authored kind, a drop that empties the last row naming a gene in a
        # *kind* table has to move `genes` too, and the old placement could not see one.
        validation.stats.update(module_stats(variants, kind_rows))

    # The source-independent resolution table (0.5), if authored/produced beside the spec. When
    # present it is the *preferred* resolution path: the compiler consumes already-resolved facts and
    # owns no source convention (Ensembl/DuckDB/provisioning) — the strict inject-only end state
    # (Principle 2). An injected `ensembl_cache` (the DuckDB path) is the superseded fallback (P3).
    # The authored overlay (RM124), loaded before the first derived table it lies on. `validate_spec`
    # above already reported every finding it has — this pass re-loads its own copy, the way it
    # re-loads `variants.csv`, because the rows themselves are needed to build the artifact.
    overrides, overlay_errors, overlay_warnings = load_overlay(spec_dir)
    if overlay_errors:
        return CompilationResult(success=False, errors=overlay_errors, warnings=all_warnings)
    # De-duplicated on the message like every other check that runs on both sides: the pre-flight
    # already emitted these over the same bytes. Extended rather than discarded so a finding this
    # loader gains later cannot go missing from a compile that never runs `validate` separately.
    all_warnings.extend(w for w in overlay_warnings if w not in all_warnings)
    overlaid: set[str] = set()
    #: RM137, the compile's half of the same stash: unmatched `update` targets for the two tables a
    #: reverse rebuilds from something narrower, split below once `studies` and the citing tables are
    #: in scope. Same reason as in `validate_spec`, and the same function does the splitting.
    compile_deferred: dict[str, list[tuple[tuple[str, str], bool]]] = {}

    resolution_rows: list[ResolutionRow] = []
    resolution_table: dict[str, list[ResolutionRow]] = {}
    resolution_sources: list[str] = []
    resolution_sig: str | None = None
    # 0/0 for a module with no resolution table: no allele identities were attempted, which is a
    # different statement from "none were achieved" and is what the manifest should carry.
    vrs_alleles = vrs_identified = 0
    resolution_path, res_spelling_warnings, res_spelling_errors = _locate_sidecar(spec_dir, "resolution.csv")
    if res_spelling_errors:
        return CompilationResult(success=False, errors=res_spelling_errors, warnings=all_warnings)
    all_warnings.extend(w for w in res_spelling_warnings if w not in all_warnings)
    if resolution_path is not None:
        resolution_rows, res_errors, _ = _load_csv_rows(resolution_path, ResolutionRow, resolution_path.name)
        if res_errors:
            return CompilationResult(success=False, errors=res_errors, warnings=all_warnings)
        # The overlay first, so everything below — the membership table, the VRS pass, the coverage
        # count and `resolution_signature` — reads what the module asserts rather than what the last
        # enrichment happened to write (RM124).
        overlaid.add("resolution.csv")
        # Deferred and stashed on the PRE-overlay rows (RM137) — see `_classify_deferred_overlay_updates`.
        compile_deferred["resolution.csv"] = update_targets("resolution.csv", resolution_rows, overrides)
        resolution_rows, apply_errors, apply_warnings = apply_overrides(
            "resolution.csv", resolution_rows, overrides, defer_unmatched=True
        )
        if apply_errors:
            return CompilationResult(success=False, errors=apply_errors, warnings=all_warnings)
        all_warnings.extend(w for w in apply_warnings if w not in all_warnings)
        for row in resolution_rows:
            resolution_table.setdefault(row.variant_key, []).append(row)
        # Content-addressed identities are checkable against themselves — do it before anything is
        # written, so a tampered id never reaches an artifact. Dep-free (stdlib), see `_verify_vrs_ids`.
        # De-duplicated on the message, the same way ploidy and allele-membership are: `validate_spec`
        # ran this pass over the same injected rows and `all_warnings` was seeded from its result, so
        # every finding is already in the list once. Harmless while these were strict-mode *errors*
        # (which return early) and merely untidy for the coverage line (one per module); now that an
        # unverifiable allele warns in every mode it is one duplicated line per allele, and
        # `pathogenic_clinvar` alone would print 185 of them twice.
        vrs_errors, vrs_warnings = _verify_vrs_ids(resolution_rows)
        all_warnings.extend(w for w in vrs_warnings if w not in all_warnings)
        if vrs_errors:
            return CompilationResult(success=False, errors=vrs_errors, warnings=all_warnings)
        all_warnings.extend(w for w in _vrs_coverage_warnings(resolution_rows) if w not in all_warnings)
        vrs_alleles, vrs_identified, _gaps = _vrs_coverage(resolution_rows)
        # The table's identity is stamped **here**, where the table was read, rather than inside the
        # `variants`-gated resolution block below — which is where it used to sit, and which meant a
        # module with no `variants.csv` published `resolution_signature: null` while carrying a
        # perfectly good `resolution.csv` beside its spec. Four of the eleven reference examples are
        # exactly that shape, so a consumer holding a PGx manifest could not tell a module resolved
        # from one that never was, on the one field that answers it.
        #
        # It was gated that way for a real reason that RM43 removed: until 0.6 `reverse_module` rebuilt
        # this table from `weights.parquet` alone, so a table-only module round-tripped to a spec with
        # no `resolution.csv` and stamping the signature would have published an identity the next
        # compile could not reproduce (P7). Reverse now rebuilds it from the positional parquets too.
        #
        # **The residual, measured rather than assumed.** The signature reproduces exactly when the
        # artifact consumed the whole table — all eleven reference examples, and every clean row of
        # `test_resolution_matrix.py`. It does **not** reproduce when the table says more than the
        # module uses: a row about a variant the module does not carry, an unplaced one-to-many, a
        # coordinate the author overrode. Reverse rebuilds the table from the artifact, so a fact the
        # artifact never held has nowhere to come back from — the same structural reason
        # `rsid_alternates` is unrecoverable. That is **not new and not positional**: a plain SNP
        # module with one unused injected row has always behaved this way, and it is pinned in the
        # matrix now (`Case.table_says_more`) because stamping here is what first made it visible.
        # `artifact.digest` is reproducible throughout, which is why `strict` has nothing to refuse.
        #
        # Still gated on `resolve_with_ensembl`: under `--no-resolve` the table is deliberately not
        # consulted (the warning above says so), and a signature naming a table that shaped nothing
        # would claim the artifact was built from it.
        #
        # And gated on the table having ROWS, not merely existing. A header-only `resolution.csv`
        # hashes to the empty-set digest, which is a perfectly valid signature of nothing — publishing
        # it costs `resolution_signature is not None` its meaning ("this module was resolved"). The
        # deprecated `ensembl_cache` branch makes it worse than cosmetic: an empty `resolution_table`
        # is falsy there, so the DuckDB path runs and the manifest would name an injected table that
        # shaped none of the bytes — the same false claim the `--no-resolve` warning refuses to make.
        if resolve_with_ensembl and resolution_rows:
            resolution_sources = sorted({row.source for row in resolution_rows if row.source})
            resolution_sig = _resolution_signature(resolution_rows)

    # Do the alleles the module *states* exist at the loci it points at? Runs here, on the AUTHORED
    # rows, because resolution may expand one rsid into several loci that share this genotype — after
    # that expansion the check reports the siblings it was never about. See `_check_allele_membership`.
    allele_errors, allele_warnings = _check_allele_membership(variants, resolution_table, strict=strict)
    # De-duplicated on the message, the same way `_check_contig_ploidy` below is and for the same
    # reason: `compile_module` runs `validate_spec` first, in **best_effort** regardless of this
    # compile's mode, so a check living in both places emits its warning twice. Re-running it here is
    # not redundant — it is how a mode ladder reaches its real severity, since the inner pass cannot
    # know `strict`. What is redundant is printing the identical sentence a second time.
    all_warnings.extend(w for w in allele_warnings if w not in all_warnings)
    if allele_errors:
        return CompilationResult(success=False, errors=allele_errors, warnings=all_warnings)

    # RM91's study-side half, de-duplicated on the message for the same reason as the block above.
    study_allele_errors, study_allele_warnings = _check_study_effect_alleles(
        studies, resolution_table, strict=strict
    )
    all_warnings.extend(w for w in study_allele_warnings if w not in all_warnings)
    if study_allele_errors:
        return CompilationResult(success=False, errors=study_allele_errors, warnings=all_warnings)

    # De-duplicated on the message, like the two blocks above (RM94). This one was the exception, and
    # the reason it survived is worth keeping: `@no-rerun-with-counts` guards against a re-run whose
    # message embeds a count, because the two copies then disagree and the manifest publishes two
    # numbers. This message carries no count, so the copies agreed and the field was merely redundant
    # rather than self-contradicting -- an untidiness nobody was looking for. The wider rule the
    # neighbours already follow is the one to take from it: a check that runs on both sides dedupes on
    # the message, and re-running it is the normal case rather than the exception.
    #
    # The re-run itself earns its place and is not what was removed. `compile_module` runs
    # `validate_spec` in best_effort regardless of this compile's mode, so this second pass in the
    # caller's mode is the only thing that lets `--strict` escalate the warning into a refusal.
    p_value_errors, p_value_warnings = _check_p_value_num(studies, strict=strict)
    all_warnings.extend(w for w in p_value_warnings if w not in all_warnings)
    if p_value_errors:
        return CompilationResult(success=False, errors=p_value_errors, warnings=all_warnings)

    resolution_mode: str | None = None
    # `None` until the injected-table path runs and reports them (S33) — see the assignment below for
    # why no other branch can.
    expanded_keys: int | None = None
    expanded_rows: int | None = None
    # The flag reads as "do not use Ensembl", and since 0.5 made the compiler inject-only that is
    # exactly what a consumer migrating to `resolution.csv` expects it to mean. It is actually the
    # master switch for resolution *of any kind*, so turning it off with a complete, correct table
    # sitting beside the spec compiles **successfully** with `chrom=None` on every weight row — rows
    # that can never match a VCF. A silent success is the worst shape a mistake can take, so the
    # combination that cannot be intended says so. (Renaming it is a 1.0 conversation: the parameter
    # is part of a published signature.)
    if not resolve_with_ensembl and resolution_table:
        # The unread row count is in the message because a warning that quantifies over a table should
        # publish the size of what it skipped — the same reason `vrs_alleles` ships beside
        # `vrs_alleles_identified`. Rows, not keys: a one-to-many rsid contributes several.
        unread = sum(len(rows) for rows in resolution_table.values())
        all_warnings.append(
            CodedWarning(
                "resolution_disabled",
                f"--no-resolve (resolve_with_ensembl=False) switches off resolution entirely, including "
                f"the injected resolution.csv beside this spec ({unread} row(s), covering "
                f"{len(resolution_table)} variant key(s)), which was not read — every variant will compile "
                f"with no chrom/start and match no VCF. The flag names Ensembl but is the master switch; "
                f"drop it to use the injected table. There is no flag for 'do not reach the network' "
                f"because the compiler never does (CONSTITUTION P2) — omitting this one is that request.",
            )
        )
    if resolve_with_ensembl and variants:
        resolution_mode = "strict" if strict else "best_effort"
        resolve_warnings: list[str] = []
        resolve_strict_errors: list[str] = []
        if resolution_table:
            outcome = resolve_from_table(variants, resolution_table, genome_build=config.genome_build)
            variants = outcome.variants
            resolve_warnings = outcome.warnings
            resolve_strict_errors = outcome.strict_errors
            # S33. Only this branch can answer it: the deprecated `ensembl_cache` path returns a bare
            # (variants, warnings) pair and is removed at 1.0, so its modules keep `None` — "not
            # established", never "no expansion". Assigned here rather than derived from `variants`
            # further down, because after the expansion an expanded row is indistinguishable from an
            # ordinary coordinate-keyed one; the fact only exists while the loop is running.
            expanded_keys = outcome.expanded_keys
            expanded_rows = outcome.expanded_rows
            if outcome.errors:
                # Fatal in both modes — today only a curator-recorded `withdrawn` rsID. See
                # `ResolutionOutcome`.
                return CompilationResult(
                    success=False,
                    errors=[f"resolution: {e}" for e in outcome.errors],
                    warnings=all_warnings + resolve_warnings,
                )
            # `resolution_sources` / `resolution_sig` are stamped where the table is READ, several
            # blocks up — not here. This branch is about applying the table to `variants.csv`, and
            # tying the table's identity to that application is what left every table-only module
            # unstamped.
        elif ensembl_cache is not None:
            # DEPRECATED (removed at 1.0): the in-compiler DuckDB-reference path. Resolution now belongs
            # to the source-independent `resolution.csv` (produce it with `just-dna-enricher enrich`); the
            # compiler owns no source/DuckDB logic. This surface is kept working by routing to the
            # enricher — additive-within-a-major binds the wire/artifact *contract*, not this internal
            # call, so the legacy path can retire at the next major. Guarded optional import (CLAUDE.md).
            warnings.warn(
                "compile_module(ensembl_cache=...) / in-compiler DuckDB resolution is deprecated and "
                "will be removed at 1.0. Produce a resolution.csv (e.g. `just-dna-enricher enrich`) and "
                "the compiler consumes it with no reference and no network.",
                DeprecationWarning,
                stacklevel=2,
            )
            try:
                from just_dna_enricher.resolver import resolve_variants as _legacy_resolve
            except ImportError:
                return CompilationResult(
                    success=False,
                    errors=[
                        "ensembl_cache resolution now lives in just-dna-enricher (the network tier). "
                        "Install just-dna-enricher, or precompute resolution.csv and recompile without "
                        "ensembl_cache."
                    ],
                    warnings=all_warnings,
                )
            variants, resolve_warnings = _legacy_resolve(
                variants, ensembl_cache, genome_build=config.genome_build
            )
        elif any(v.chrom is None or v.start is None for v in variants):
            # Nothing injected: the compiler no longer auto-discovers or fetches a reference (P2,
            # tightened in 0.5). Variants lacking a position are left unresolved with a pointer.
            resolve_warnings = [
                CodedWarning(
                    "resolution_not_injected",
                    resolution_not_injected(
                        missing="No resolution.csv and no ensembl_cache injected",
                        remedy="Produce a resolution.csv with just-dna-enricher.",
                    ),
                )
            ]
        # De-duplicated on the message, the `_check_contig_ploidy` idiom: since S76 the pre-flight
        # emits the `rsid_unresolved` sentence for the same subjects, and `compile_module` runs that
        # pre-flight whatever its own mode, so appending blind published every such finding twice —
        # and `warnings_summary` counted 24 for 12 subjects. Safe here for the reason the rule
        # requires: no message resolution re-derives embeds a count, so two passes over one subject
        # produce the identical sentence rather than two that differ by a number.
        all_warnings.extend(w for w in resolve_warnings if w not in all_warnings)
        # The round-trip contract. `strict` promises a *reproducible* artifact, and these are the
        # conditions under which `compile → reverse → compile` cannot reproduce the resolution table
        # it started from (a dropped locus, an authored coordinate contradicting the table), plus the
        # one that is reproducible but rests on a guessed label (`ambiguous`). `best_effort` already
        # carries them as warnings above. See COMPILER.md § Resolution.
        if strict and resolve_strict_errors:
            return CompilationResult(
                success=False,
                errors=[f"strict resolution: {e}" for e in resolve_strict_errors],
                warnings=all_warnings,
            )
        # Resolution is an enrichment that can *change identity*: filling a coordinate or expanding a
        # one-to-many rsid into coord-keyed rows may collide with an already-authored row. validate_spec
        # ran on the pre-resolution set, so re-run the identity checks on the resolved set — a duplicate
        # (variant_key, genotype) or an inconsistent position must fail the compile, not silently land in
        # weights.parquet. Only errors are taken (warnings were already surfaced pre-resolution).
        post_errors, _ = _cross_validate_variants(variants)
        if post_errors:
            return CompilationResult(
                success=False,
                errors=[f"post-resolution: {e}" for e in post_errors],
                warnings=all_warnings,
            )

    # The non-diploid guardrail runs **here**, once, because this is the first point at which `chrom`
    # is final for every row — resolution has either run and filled it or was skipped. Inside
    # `_cross_validate_variants` it was emitted from the pre-resolution pass only (the post-resolution
    # call takes errors alone), so an rsID-authored MT or Y row — the shape every drafting provider
    # writes — was never checked at all.
    all_warnings.extend(
        w for w in _check_contig_ploidy(variants, config.genome_build) if w not in all_warnings
    )

    # Wrong-build coordinates, re-run **here** for the same reason ploidy is: this is the first point
    # at which `chrom`/`start` are final. `validate_spec` sees an rsid-only row with no coordinate at
    # all; resolution has since filled one, and the deprecated `ensembl_cache` path fills it from a
    # reference `validate_spec` never opened. Unlike ploidy this needs no de-duplication: it returns
    # errors, `compile_module` returns early on any validation error, so anything reaching here is a
    # coordinate the pre-flight could not have seen.
    build_errors = _check_build_coordinates(
        [_CoordinateTable("variants.csv", config.genome_build, True, variants)]
    )
    if build_errors:
        return CompilationResult(
            success=False,
            errors=[f"post-resolution: {e}" for e in build_errors],
            warnings=all_warnings,
        )

    # Outcome axis (orthogonal to the requested `resolution_mode` policy, Principle 5): did every
    # in-scope variant resolve to a genomic position? Vacuously true for a table-kind-only module —
    # which is why the denominator travels beside it into the manifest (RM44). Both come from the same
    # list, so the flag can never be published without the count that says what it quantified over.
    fully_resolved = all(v.chrom is not None and v.start is not None for v in variants)
    resolution_subjects = len(variants)

    # Strict (all-or-nothing): refuse to write a partial artifact. A variant still missing its
    # genomic position after resolution means the injected reference was incomplete or absent, so the
    # coordinate-anchored parquet bytes (and `artifact.digest`) would not be reproducible — the
    # failure mode behind "local hash differs from published". Best-effort (strict=False) leaves such
    # rows unset with a warning instead. Scope is the SNP-core VariantRow; the 0.4 table kinds carry
    # no positions.
    if strict and variants:
        unresolved = sorted(v.rsid or v.variant_key for v in variants if v.chrom is None or v.start is None)
        if unresolved:
            return CompilationResult(
                success=False,
                errors=[
                    f"strict compile: {len(unresolved)} variant(s) have unresolved genomic "
                    f"positions after resolution: {unresolved}. A partial artifact would not be "
                    f"byte-reproducible; inject a complete Ensembl reference (ensembl_cache=) or "
                    f"compile without strict."
                ],
                warnings=all_warnings,
            )

    # The wrong-build gate (S78, RM143), here for the same placement reason as the licence gate below
    # and one line ahead of it: a refusal must leave nothing written. It reads the attestation the
    # enricher wrote and acts on one recorded finding — see `build_disagreement_error` for why that
    # one and no other, and why this does not move the strict line. The block is re-read rather than
    # carried down from the pre-flight because a stale attestation is dropped by the reader, and the
    # gate must see what the reader saw.
    if strict:
        build_error = build_disagreement_error(_verification_block(spec_dir)[0])
        if build_error is not None:
            return CompilationResult(success=False, errors=[build_error], warnings=all_warnings)

    # Licensing gate. Loaded here rather than with the other fact tables because those are read
    # *after* `output_dir.mkdir()`, and a refusal must leave nothing written — this is the last point
    # at which that is still true. Purely computation over injected data: the compiler holds no
    # source→licence map (Principle 2 — it owns no source convention) and only reads what the
    # enricher recorded.
    sources_path, gate_spelling_warnings, gate_spelling_errors = _locate_sidecar(spec_dir, SOURCES_CSV)
    if gate_spelling_errors:
        return CompilationResult(success=False, errors=gate_spelling_errors, warnings=all_warnings)
    all_warnings.extend(w for w in gate_spelling_warnings if w not in all_warnings)
    if sources_path is not None:
        gate_rows, gate_load_errors, _ = _load_csv_rows(sources_path, SourceRow, sources_path.name)
        if gate_load_errors:
            return CompilationResult(success=False, errors=gate_load_errors, warnings=all_warnings)
        gate_errors = _check_license_gate(gate_rows)
        if gate_errors:
            return CompilationResult(success=False, errors=gate_errors, warnings=all_warnings)

    output_dir.mkdir(parents=True, exist_ok=True)

    # SNP core: weights/annotations only when the module actually has variants.
    weights_df = _build_weights(variants, config) if variants else None
    annotations_df = _build_annotations(variants, module_name) if variants else None
    studies_df = _build_studies(studies, module_name) if studies else None
    # Names taken from `SNP_CORE_PARQUETS` rather than spelled again: this is the site the binding was
    # extracted from, so a literal here would be the copy the constant exists to remove.
    _weights_name, _annotations_name = SNP_CORE_PARQUETS["variants.csv"]
    (_studies_name,) = SNP_CORE_PARQUETS["studies.csv"]
    if weights_df is not None:
        weights_df.write_parquet(output_dir / _weights_name, compression=compression)
    if annotations_df is not None:
        annotations_df.write_parquet(output_dir / _annotations_name, compression=compression)
    if studies_df is not None:
        studies_df.write_parquet(output_dir / _studies_name, compression=compression)

    # The positional fill (RM43), on the rows that survive. It runs **after** the symbolic-allele
    # ladder (RM5) and before `_build_table`, and that order is the only correct one: the drop decides
    # which rows exist, so filling first would resolve a coordinate onto a row about to be discarded
    # and — worse — leave the joinability report below counting rows the artifact does not contain.
    # The two never disagree because the drop happens up at load time, long before the resolution
    # table is even read; this comment is here so the distance between them does not read as accident.
    # Gated on `resolve_with_ensembl` like every other resolution, so `--no-resolve` consults nothing.
    fill_warnings, fill_applied = _apply_positional_resolution(
        kind_rows, resolution_table, config.genome_build, resolve=resolve_with_ensembl
    )
    all_warnings.extend(w for w in fill_warnings if w not in all_warnings)

    # 0.4 table kinds (RM1): materialize each present CSV via the generic materializer. The rows were
    # loaded above, before `mkdir`, so the symbolic-allele check could refuse without leaving a
    # half-written directory behind — and so a row it dropped is absent from the parquet here.
    table_rows: dict[str, int] = {}
    for csv_name, parquet_name, model in _TABLE_KINDS:
        rows = kind_rows.get(csv_name)
        if rows is None:
            continue
        table_df = _build_table(rows, model, module_name)
        table_df.write_parquet(output_dir / parquet_name, compression=compression)
        table_rows[parquet_name] = table_df.height

    # Re-run here so the finding reaches a caller who compiles without validating first, and
    # de-duplicated on the message the way `_check_contig_ploidy` is: `compile_module` runs
    # `validate_spec` itself, so a check living in both places otherwise prints its sentence twice.
    all_warnings.extend(
        w
        for w in _check_positional_joinability(
            kind_rows, resolution_table, config.genome_build, fill_applied=fill_applied
        )
        if w not in all_warnings
    )
    # The same facts as counts rather than as a sentence, for the catalog that was reading the
    # sentence (S31). Computed here, beside the check, so the two cannot describe different row sets.
    positional_rows, positional_rows_placed = positional_placement(kind_rows)
    all_warnings.extend(w for w in _check_binning_grounding(kind_rows, studies) if w not in all_warnings)
    # `kind_rows` is freshly loaded and never resolved, so re-running the binning check here produces
    # the identical sentence and the message-dedup above does its job.
    all_warnings.extend(w for w in _check_measure_shape(kind_rows) if w not in all_warnings)
    all_warnings.extend(w for w in _check_binning_deprecations(kind_rows) if w not in all_warnings)

    # **THREE checks of this round are deliberately NOT re-run here, and that is the fix rather than an
    # omission.** `_check_missing_allele_marker`, `_check_quality_inversion` and `_check_vcf_pointers`
    # all read authored cells (`alts`, `requires_callable` + `quality_from`, the pointer columns) that
    # resolution never fills, so `validate_spec`'s pass — which runs before any expansion — already has
    # the right answer, and it reaches this list through `all_warnings = list(validation.warnings)`
    # above. Running any of them again on `variants` would count the *expanded* rows: by this point
    # `variants` is `outcome.variants`, one row per resolved locus, so a one-to-many rsid becomes N rows
    # carrying one authored genotype and the same finding is reported with a different count and
    # different example keys. The de-duplication above keys on the **message**, so two sentences
    # differing only in their count can never collapse, and both are published into
    # `manifest.compilation.warnings` — a surface RM44 established that consumers parse. Measured twice,
    # independently, on the way in: an rsid-only `requires_callable` row over a two-locus
    # `resolution.csv` emitted "1 row(s) …" beside "2 row(s) …", and the pointer check emitted 328
    # beside 337 on `pathogenic_clinvar`.
    #
    # Nothing is lost by staying behind resolution: all three are warning-only in both modes, so there
    # is no severity for a re-run to recover — which is the whole reason the *mode-ladder* checks re-run
    # at all. This is the mirror of the `_check_contig_ploidy` lesson rather than a contradiction of it:
    # that warning had to **move** here because resolution fills its input; these three must stay behind
    # it because resolution fills nothing they read. The rule that covers both: re-run a check after
    # resolution exactly when resolution changes its input, and never when the message embeds a count.

    # 0.5 derived-fact sidecars: materialize each present CSV, and cross-check it against what the
    # module actually contains. A row describing something the module never mentions is a warning, not
    # an error — an over-broad sidecar is harmless (a stale gene left in after a variant was removed),
    # while failing the compile over it would punish the author for the enricher's generosity.
    # One branch per sidecar, keyed by model. A two-way `if/else` was fine for two tables and stops
    # being readable at three, so each entry states its own checks and its own builder; the loop below
    # stays generic. Errors are fatal, warnings accumulate — the same contract the SNP core uses.
    def _frequency_checks(rows: list) -> tuple[list[str], list[str]]:
        # De-duplicated on the message, the `_literature_checks` idiom eleven lines below and the
        # `_check_contig_ploidy` one before it: `compile_module` runs `validate_spec`, which has run
        # `_check_frequency_arithmetic` over these same injected rows since RM93 added it for parity,
        # so an unfiltered re-run publishes the finding **twice** in `manifest.compilation.warnings`
        # (RM44) and every consumer counting warnings overstates what is wrong with the module.
        # Re-running is the normal case and is not the bug; not filtering is (`@no-rerun-with-counts`).
        # Only the warnings need it — validate's errors abort the compile before this closure runs.
        errors, warns = _check_frequency_arithmetic(rows)
        warns = [w for w in warns if w not in all_warnings]
        warns.extend(_cross_check_frequencies(rows, variants))
        warns.extend(_check_ba1_lint(rows, variants, threshold=ba1_threshold))
        return errors, warns

    def _gene_metrics_checks(rows: list) -> tuple[list[str], list[str]]:
        # Both have run in the pre-flight since RM211, so both arrive twice. The **extend site**
        # below de-duplicates every fact-table check on the message — `@first-fact-check-on-both-
        # sides`, dedupe where the results are collected rather than in each closure — which is why
        # this one carries no filter of its own and `_gene_validity_checks` below carries none
        # either. Re-running is the normal case; what would break it is a message embedding a count,
        # and neither of these does.
        return [], [*_check_gene_metrics_arithmetic(rows), *_cross_check_gene_metrics(rows, variants)]

    def _literature_checks(rows: list) -> tuple[list[str], list[str]]:
        # De-duplicated on the message: `compile_module` runs `validate_spec`, which runs this same
        # check, so a finding living in both places would otherwise print twice (the
        # `_check_contig_ploidy` idiom).
        return [], [w for w in _cross_check_literature(rows, studies, kind_rows) if w not in all_warnings]

    def _gene_validity_checks(rows: list) -> tuple[list[str], list[str]]:
        # Both warn in either mode (see `_check_gene_validity_currency`), so nothing here reads
        # `strict` — the errors list stays empty by construction rather than by a branch.
        return [], [
            *_cross_check_gene_validity(rows, variants),
            *_check_gene_validity_currency(rows),
        ]

    def _clinical_assertion_checks(rows: list) -> tuple[list[str], list[str]]:
        return [], list(_cross_check_clinical_assertions(rows, variants))

    def _gwas_effect_checks(rows: list) -> tuple[list[str], list[str]]:
        return [], list(_cross_check_gwas_effects(rows, variants))

    def _expression_effect_checks(rows: list) -> tuple[list[str], list[str]]:
        """No checks, and the absence is a decision rather than a gap (RM194/RM200).

        **`_cross_check_gwas_effects`'s orphan warning deliberately does not transfer**, though the
        two tables look alike enough that copying it would be the obvious move. A `GwasEffectRow` is
        module-scoped by construction: the pass queries the Catalog *with the module's own rsIDs*, so
        a row naming an identity the module does not carry really is the residue of a narrowed
        variant list, which is what that warning is about.

        `expression_effects.csv` is **locus-wide by construction instead**. The pass queries a
        genomic interval and AlphaGenome answers for every scored variant in it, most of which the
        module does not author — and finding those is the entire point of the item, because slicing
        by gene position silently drops the promoters and enhancers that act on a gene without
        sitting in it. Running the identical check here would fire on nearly every row of every
        module, which is a warning that means "this table is working".

        A gene-scoped variant of it — warn when `gene` names no gene the module annotates — was
        considered and left unbuilt. A warning code is a permanent key (`@warning-code-names-the-
        finding`), nobody has asked for this one, and minting one speculatively costs more than the
        check would return. It is additive if a caller ever wants it.

        Returning `([], [])` rather than reporting a zero is `@tautology-zero`: this is a table with
        no check, not a check that always passes.
        """
        return [], []

    def _concordance_checks(rows: list) -> tuple[list[str], list[str]]:
        # De-duplicated on the message, the `_literature_checks` idiom: `compile_module` runs
        # `validate_spec`, which emits the identical sentences over the identical post-overlay rows,
        # and an unfiltered re-run would publish the count twice. Safe to run twice at all because
        # no compile step between the two passes touches this table or the overlay above it — which
        # is the standing test `@no-rerun-with-counts` actually applies.
        warns = [w for w in _concordance_warnings(rows) if w not in all_warnings]
        warns.extend(
            w
            for w in _cross_check_clin_sig_concordance(rows, variants, table="clin_sig_concordance.csv")
            if w not in all_warnings
        )
        return [], warns

    def _authority_call_checks(rows: list) -> tuple[list[str], list[str]]:
        # No check that the subject also appears in the parent record, deliberately: an author who
        # answers a contested subject suppresses the parent row through the overlay, and the calls
        # behind it stay — the evidence outliving the question is correct, and warning about it would
        # make answering a finding produce a finding.
        return [], [
            w
            for w in _cross_check_clin_sig_concordance(rows, variants, table="clin_sig_authority_calls.csv")
            if w not in all_warnings
        ]

    def _sources_checks(rows: list) -> tuple[list[str], list[str]]:
        # `sources.csv` is last in `_FACT_TABLES`, so the other sidecars are already parsed into
        # `fact_rows` and their `source` values can be cross-checked here. Warnings only — the gate
        # that can actually refuse already ran, before anything was written.
        #
        # `SourceRow` is excluded from the "used" set: the loop stores each model's rows into
        # `fact_rows` *before* calling its check, so including it would let sources.csv vouch for
        # itself and no orphan could ever be reported.
        # Resolution contributes its **authority**, not its `source`: that column names which *link*
        # answered (`ensembl-rest`, `cache`) while every other table's names a licensed source, so
        # comparing them by string made every enriched module warn that `ensembl-rest` has no terms
        # recorded (RM33). A row with no authority contributes nothing — `authored`/`reversed` have no
        # external source to declare, and an older `resolution.csv` written before the column existed
        # simply says nothing rather than saying the wrong thing.
        used = {r.authority for r in resolution_rows if r.authority}
        for model, parsed in fact_rows.items():
            if model in (SourceRow, LiteratureRow):
                continue
            used |= {getattr(r, "source", None) for r in parsed if getattr(r, "source", None)}
        warns = _source_checks(rows, {s for s in used if s})
        warns.extend(_check_declared_license_agrees(rows, config.license if config else None))
        return [], warns

    _FACT_HANDLERS: dict[type, tuple[Callable, Callable]] = {
        FrequencyRow: (_frequency_checks, lambda rows: _build_frequencies(rows, module_name)),
        GeneMetricsRow: (_gene_metrics_checks, lambda rows: _build_table(rows, GeneMetricsRow, module_name)),
        LiteratureRow: (_literature_checks, lambda rows: _build_table(rows, LiteratureRow, module_name)),
        GeneValidityRow: (
            _gene_validity_checks,
            lambda rows: _build_table(rows, GeneValidityRow, module_name),
        ),
        ClinicalAssertionRow: (
            _clinical_assertion_checks,
            lambda rows: _build_table(rows, ClinicalAssertionRow, module_name),
        ),
        GwasEffectRow: (
            _gwas_effect_checks,
            lambda rows: _build_table(rows, GwasEffectRow, module_name),
        ),
        ExpressionEffectRow: (
            _expression_effect_checks,
            lambda rows: _build_table(rows, ExpressionEffectRow, module_name),
        ),
        ClinSigConcordanceRow: (
            _concordance_checks,
            lambda rows: _build_table(rows, ClinSigConcordanceRow, module_name),
        ),
        ClinSigAuthorityCallRow: (
            _authority_call_checks,
            lambda rows: _build_table(rows, ClinSigAuthorityCallRow, module_name),
        ),
        SourceRow: (_sources_checks, lambda rows: _build_table(rows, SourceRow, module_name)),
    }

    fact_rows: dict[type, list] = {}
    for csv_name, parquet_name, model in _FACT_TABLES:
        # Spelling collisions and the deprecation notice were both already surfaced by the licence
        # gate above (for `sources.csv`) or are surfaced here for the first time; either way the
        # notices de-duplicate, the way ploidy's and the VRS pass's already do.
        fact_path, fact_spelling_warnings, fact_spelling_errors = _locate_sidecar(spec_dir, csv_name)
        if fact_spelling_errors:
            return CompilationResult(success=False, errors=fact_spelling_errors, warnings=all_warnings)
        all_warnings.extend(w for w in fact_spelling_warnings if w not in all_warnings)
        if fact_path is None:
            continue
        rows, fact_errors, _ = _load_csv_rows(fact_path, model, fact_path.name)
        if fact_errors:
            return CompilationResult(success=False, errors=fact_errors, warnings=all_warnings)
        # The overlay, before the table's own check runs (RM124) — the check reports on what the
        # module asserts, and the parquet, the fact signature and the manifest block are all built
        # from the same post-overlay rows.
        if csv_name in OVERRIDABLE_TABLES:
            overlaid.add(csv_name)
            lossy = csv_name in LOSSY_OVERLAY_TABLES or csv_name == VINDICATING_OVERLAY_TABLE
            if lossy:
                compile_deferred[csv_name] = update_targets(csv_name, rows, overrides)
            rows, apply_errors, apply_warnings = apply_overrides(
                csv_name, rows, overrides, defer_unmatched=lossy
            )
            if apply_errors:
                return CompilationResult(success=False, errors=apply_errors, warnings=all_warnings)
            all_warnings.extend(w for w in apply_warnings if w not in all_warnings)
        check, build = _FACT_HANDLERS[model]
        # **The check sees every row; everything after it sees the kept ones** (RM79). A literature
        # row for a citation no study and no bin names joins to nothing, so carrying it into the
        # parquet and the manifest is dead weight — but reporting it needs the full list, which is why
        # the split happens here rather than at load. `literature.csv` itself is untouched: it is
        # merge-not-clobber on purpose, and that pin is what makes a re-run cheap.
        check_errors, check_warnings = check(rows)
        if model is LiteratureRow:
            rows, _dropped = split_cited_literature(rows, studies, kind_rows)
        fact_rows[model] = rows
        if check_errors:
            return CompilationResult(success=False, errors=check_errors, warnings=all_warnings)
        # De-duplicated on the message, like every other check that runs on both sides (RM94): a
        # fact-table check the pre-flight also performs reaches the identical sentence twice, and a
        # doubled line in `manifest.compilation.warnings` doubles `warnings_summary`'s count with it.
        # Both passes read the same POST-OVERLAY rows — `validate_spec` applies the overlay in its own
        # loop — so a message embedding a count says the same number on both sides and
        # `@no-rerun-with-counts` is satisfied rather than dodged. The dedup was previously
        # unnecessary here because no fact check ran in the pre-flight; RM108's currency check is the
        # first, and stating the rule once is cheaper than remembering it for the second.
        all_warnings.extend(w for w in check_warnings if w not in all_warnings)
        fact_df = build(rows)
        fact_df.write_parquet(output_dir / parquet_name, compression=compression)
        table_rows[parquet_name] = fact_df.height

    # De-duplicated on the message like every other check that runs on both sides: `validate_spec`
    # ran this over the same overlay and `all_warnings` was seeded from its result.
    all_warnings.extend(w for w in _overlay_targets_missing(overrides, overlaid) if w not in all_warnings)
    # And RM137's split, deferred from both overlay sites to here — `studies` and the citing tables are
    # in scope now. De-duplicated on the message for the reason every both-sides check is: the
    # pre-flight computed the identical sentence from the identical inputs.
    all_warnings.extend(
        w
        for w in _classify_deferred_overlay_updates(
            compile_deferred, studies, kind_rows, variants, resolution_rows
        )
        if w not in all_warnings
    )

    # The overlay itself, materialized verbatim and in authored order — it is authored input, so it
    # goes to parquet the way `variants.csv` does rather than being re-derived from what it changed.
    # This is what `reverse_module` reads the corrections back out of (RM124).
    if overrides:
        overlay_df = _build_table(overrides, OverrideRow, module_name)
        overlay_df.write_parquet(output_dir / OVERRIDES_PARQUET, compression=compression)
        table_rows[OVERRIDES_PARQUET] = overlay_df.height

    frequency_rows: list[FrequencyRow] = fact_rows.get(FrequencyRow, [])
    gene_metrics_rows: list[GeneMetricsRow] = fact_rows.get(GeneMetricsRow, [])
    literature_rows: list[LiteratureRow] = fact_rows.get(LiteratureRow, [])
    gene_validity_rows: list[GeneValidityRow] = fact_rows.get(GeneValidityRow, [])
    clinical_assertion_rows: list[ClinicalAssertionRow] = fact_rows.get(ClinicalAssertionRow, [])
    gwas_effect_rows: list[GwasEffectRow] = fact_rows.get(GwasEffectRow, [])
    expression_effect_rows: list[ExpressionEffectRow] = fact_rows.get(ExpressionEffectRow, [])
    concordance_rows: list[ClinSigConcordanceRow] = fact_rows.get(ClinSigConcordanceRow, [])
    authority_call_rows: list[ClinSigAuthorityCallRow] = fact_rows.get(ClinSigAuthorityCallRow, [])
    source_rows: list[SourceRow] = fact_rows.get(SourceRow, [])

    logs = _collect_logs(spec_dir, output_dir, log_files)
    # Authored side-car assets are validated here (validate_spec does not read them). Surface a
    # malformed one as a compile error instead of letting the exception escape mid-compile.
    try:
        provenance = _collect_provenance(spec_dir, output_dir, provenance_file)
    except ValidationError as exc:
        return CompilationResult(
            success=False, errors=[f"provenance.json is invalid: {exc}"], warnings=all_warnings
        )
    try:
        logo = _collect_logo(spec_dir, output_dir, logo_file)
    except ValueError as exc:
        return CompilationResult(success=False, errors=[str(exc)], warnings=all_warnings)
    try:
        readme = _collect_readme(spec_dir, output_dir, readme_file)
    except ValueError as exc:
        return CompilationResult(success=False, errors=[str(exc)], warnings=all_warnings)
    # The attestation, re-read here because the block is what gets stamped (`validate_spec` ran the
    # same call for its warning and threw the block away). De-duplicated on the message for the
    # standard reason: the pre-flight already emitted the identical sentence.
    verification, verification_warnings = _verification_block(spec_dir)
    all_warnings.extend(w for w in verification_warnings if w not in all_warnings)

    # Content identity over the RAW authored data (re-read from disk, so pre-resolution and
    # reference-independent — the in-scope `variants` here are already resolved). Out of
    # `artifact.digest`; lets a registry dedup across recompile/metadata-strip.
    manifest = _build_manifest(
        config=config,
        spec_dir=spec_dir,
        output_dir=output_dir,
        validation=validation,
        weights_rows=weights_df.height if weights_df is not None else 0,
        warnings=all_warnings,
        dropped_rows={t: len(r) for t, r in sorted(symbolic_drops.items())},
        compiled_by=compiled_by,
        ensembl_reference=ensembl_reference,
        logs=logs,
        provenance=provenance,
        logo=logo,
        readme=readme,
        content_sig=content_signature(spec_dir),
        resolution_mode=resolution_mode,
        fully_resolved=fully_resolved,
        resolution_subjects=resolution_subjects,
        expanded_keys=expanded_keys,
        expanded_rows=expanded_rows,
        positional_rows=positional_rows,
        positional_rows_placed=positional_rows_placed,
        vrs_alleles=vrs_alleles,
        vrs_alleles_identified=vrs_identified,
        resolution_sig=resolution_sig,
        resolution_sources=resolution_sources,
        frequency=_frequency_block(frequency_rows),
        gene_metrics=_gene_metrics_block(gene_metrics_rows),
        gene_validity=_gene_validity_block(gene_validity_rows),
        clinical_assertions=_clinical_assertions_block(clinical_assertion_rows),
        gwas_effects=_gwas_effects_block(gwas_effect_rows),
        expression_effects=_expression_effects_block(expression_effect_rows),
        clin_sig_concordance=_clin_sig_concordance_block(concordance_rows, authority_call_rows),
        literature=_literature_block(literature_rows),
        sources=_sources_block(source_rows),
        verification=verification,
    )
    write_manifest(manifest, output_dir / "manifest.json")

    stats: dict[str, Any] = {
        "module_name": module_name,
        "weights_rows": weights_df.height if weights_df is not None else 0,
        "annotations_rows": annotations_df.height if annotations_df is not None else 0,
        "studies_rows": studies_df.height if studies_df is not None else 0,
        "table_rows": table_rows,
    }
    return CompilationResult(
        success=True,
        output_dir=output_dir,
        errors=[],
        warnings=all_warnings,
        stats=stats,
        manifest=manifest,
    )


def close_module(
    spec_dir: Path,
    *,
    closed_by: str | None = None,
    private_key_pem: bytes | None = None,
    now: str | None = None,
    difficulty: int | None = None,
) -> ClosureResult:
    """Declare a module's authoring phase finished, binding the statement to its authored bytes (RM73).

    A flat CSV row records nothing about how it came to be, so authoring had no end and every check
    that needed one guessed. This is the end: a `closure` block inside the module's `verification.json`
    naming the hash of the authored files as they stand. A later edit moves that hash, the compiler
    recomputes it, and the closure is dropped along with the rest of the attestation — which is why
    there is no second file and no second binding here to keep in step.

    **Deliberate, never a side effect.** `validate_spec` stays read-only and nothing stamps this on a
    passing run: a record written by whatever happened to execute says only *someone ran a tool*,
    which is the exact defect RM73 levels at an attestation produced as a by-product. So this is its
    own function behind its own command, and `--private-key` makes the act attributable rather than
    merely evident.

    **It refuses on an invalid spec and not on a warning.** Declaring a set finished that the compiler
    will not accept is a contradiction; declaring one finished that carries an unresolvable rsID or an
    ungrounded threshold is ordinary, and refusing there would make closure unreachable for every
    module whose findings no authored edit can clear (P5, the `not_covered` class).

    Existing check records survive **only while they describe these bytes**, and then the whole
    document is kept verbatim rather than rebuilt — `producer` names who put the *checks*, so stamping
    this tier's label over it would have the compiler claim an enricher's cross-checks. Records that no
    longer hold are dropped and named in `dropped_checks`: carrying them across would re-bind a claim
    to rows the check never saw, which is the failure `module_hash` exists to catch, committed by the
    tool instead of by an edit.
    """
    spec_dir = Path(spec_dir)
    validation, validation_findings = _validate_spec(spec_dir)
    if not validation.valid:
        return ClosureResult(
            closed=False,
            errors=[
                "This spec does not validate, so its authoring set cannot be declared finished. "
                "Fix the errors below and close it afterwards.",
                *validation.errors,
            ],
            # Everything the pre-flight found, except its reminder to run *this command* — which is
            # what an author was being told, as the first line of output, while running it. The
            # pre-flight is right to say it and this caller is the one context where it is answered
            # by definition. Filtered on the phrase rather than by re-deciding, so the two cannot
            # drift apart.
            warnings=[w for w in validation_findings if UNCLOSED_PHRASE not in w],
        )

    try:
        path = sidecar_write_path(spec_dir, VERIFICATION_JSON)
    except SidecarCollision as exc:
        return ClosureResult(closed=False, errors=[str(exc)])

    binding = _module_binding(spec_dir)
    stamp = now or now_utc_iso()
    statement = close(binding, closed_at=stamp, closed_by=closed_by, private_key_pem=private_key_pem)
    warnings: list[str] = []
    previous: VerificationDoc | None = None
    if path.is_file():
        try:
            previous = read_verification(path)
        except (OSError, ValueError) as exc:
            warnings.append(
                CodedWarning(
                    "closure_discarded_unreadable_record",
                    f"The existing {path.name} could not be read ({exc}); this closure replaces it, so "
                    f"any checks it recorded are gone. Re-run the checks (just-dna-enricher).",
                )
            )

    held = previous is not None and attestation_failure(previous, binding) is None
    if held:
        # Everything the document says still holds, so the closure is the only new claim in it and the
        # rest is kept **verbatim** — including `producer`, which names who put the *checks*. Writing
        # this tier's own label there would say the compiler ran an enricher's cross-checks, which is
        # a false claim manufactured by an unrelated act. Reusing the document also keeps the nonce
        # already mined over an unchanged payload, so closing costs no work rather than the same work
        # twice.
        doc = previous.model_copy(update={"closure": statement})
    else:
        # Either there was no document, or it no longer describes these bytes. Its records are dropped
        # rather than re-attested: re-binding them would claim a check was put against rows it never
        # saw, which is the failure `module_hash` exists to catch, committed by the tool instead of by
        # an edit.
        #
        # `producer` and `produced_at` both stay unset, as a pair: they describe the run that put the
        # checks, and this document has none. Stamping the time here left a closure-only manifest
        # reading `producer: null, produced_at: <now>, checks: []` — a timestamp for a run that did not
        # happen, beside the closure's own `closed_at` saying the same thing about the act that did.
        doc = attest([], binding, difficulty=difficulty, closure=statement)
    dropped = sorted(r.check for r in previous.records) if previous is not None and not held else []
    write_verification(doc, path)
    return ClosureResult(
        closed=True,
        path=path,
        module_hash=binding,
        signed=doc.closure is not None and doc.closure.signature is not None,
        dropped_checks=dropped,
        warnings=warnings,
    )
