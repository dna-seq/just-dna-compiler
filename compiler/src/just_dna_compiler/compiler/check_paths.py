"""Which path asks each check: the roster behind `validate`/`compile` parity (RM367).

`validate_spec` is the pre-flight for `compile_module`, and the contract between them is one verdict and
one set of findings (`@validate-refuses-all`, `@parity-by-check`). A check is normally asked on **both**
paths. This module names the ones that are not, each with its reason, and
`compiler/tests/test_check_paths.py` walks the two function bodies and asserts the roster as an
**equality** against what they call: a check added to one path and not the other fails the walk until it
is either asked on the other path too or entered here with a reason.

The pre-flight-only side is large and needs no reason per entry: `compile_module` runs the pre-flight
first, in its own mode, refuses on its errors and seeds its warning channel from its findings, so a check
asked only there reaches the compile's result without being asked twice. The compile-only side is where a
reason is owed, and it is meant to stay short.

**The one exemption the walk cannot see.** The deprecated `ensembl_cache` path (removed at 1.0) resolves
rows against a reference the pre-flight is never handed, so what follows from that resolution — coverage,
the strict aggregate, the resolved-row cross-checks — is the compile's alone on that path
(`_validate_spec(legacy_reference=True)`, which then skips those judgements rather than ask them over
unresolved rows). It is a reference, not a check, so it has no name to walk.
"""

#: Checks the compile asks and the pre-flight does not call by this name, with the reason.
COMPILE_ONLY: dict[str, str] = {
    "meta_scale_errors": (
        "the pre-flight asks it inside `build_meta`; the compile asks it alone, before `mkdir`, because "
        "it expands the meta-table only after the positional fill"
    ),
}

#: Checks the pre-flight asks and the compile inherits through it (seeded warnings, refused errors), or
#: asks under another name: `_collect_logs` calls `discover_logs`, and the resolution step's helpers call
#: `_cross_validate_variants`, `_check_build_coordinates` and `_check_contig_ploidy`.
PREFLIGHT_ONLY: frozenset[str] = frozenset(
    {
        "_check_build_coordinates",
        "_check_composite_gene_cells",
        "_check_conclusion_genotypes",
        "_check_contig_ploidy",
        "_check_fact_rows_contradict",
        "_check_genotype_coverage",
        "_check_missing_allele_marker",
        "_check_misspelled_tables",
        "_check_phenotype_classes",
        "_check_qual_floor_on_reference_evidence",
        "_check_vcf_pointers",
        "_cross_validate_haplotype_definitions",
        "_cross_validate_phase_ambiguity",
        "_cross_validate_studies",
        "_cross_validate_variants",
        "_validate_table_kind",
        "discover_logs",
    }
)
