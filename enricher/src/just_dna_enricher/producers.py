"""Which pass fills each machine-produced table, from which source, and what it checks while it does.

**The counterpart to `drafting.DRAFT_PROVIDERS`, and it exists for the same reason.** An authored
table can already answer *who drafts me* by construction — every drafter declares its `table`, so a
tool or a page walks the registry and gets the truth. A derived table could answer nothing: the
writer's name lived in a **comment** on `VALID_VERIFICATION_CHECKS` — *— enrich*, *— literature* —
the source was a `SourceRow` literal inside ten different passes, and the CLI's help text is prose. So
the docs site's per-table reference had exactly two ways to say *the enricher fills this one*: hand-keep
a mapping in the generator, or say nothing. The first is `@registry-not-a-list` and the very failure
`gen_table_pages.py`'s own docstring refuses — *a command-surface table rots silently* — and the second
is what shipped.

**Every field here is a fact some other registry already owns, referenced rather than restated.**
`source` is a `SourceTerms.source` from `licensing`, so a producer cannot name a source this tier does
not have terms for. `checks` are `VALID_VERIFICATION_CHECKS` members, so a pass cannot claim an
attestation the vocabulary has no word for. `table` is a `_FACT_TABLES` CSV (plus `resolution.csv`,
which is derived without being a fact table). `command` is the one thing with no registry behind it —
so `test_producers.py` walks the live Typer tree and asserts each one resolves, the same way
`CacheLane.build_command` is pinned, and for the same incident: a string an operator is asked to type
must come from where the command is declared, never from a naming convention.

**Not folded into `CACHE_LANES`, deliberately.** A lane is a *snapshot* — where bytes are cached, who
may publish them, how to rebuild. A producer is a *pass* — which table it fills in a spec directory.
Several passes read no lane and one lane feeds several passes, so the two are orthogonal axes and
Principle 5 keeps them apart. `serves` on a lane is prose for an operator reading `cache status`; it is
not this question asked in another place.
"""

from dataclasses import dataclass

from just_dna_enricher.licensing import (
    ALPHAGENOME_ATLAS_TERMS,
    CIVIC_TERMS,
    CLINGEN_TERMS,
    CLINVAR_TERMS,
    ENSEMBL_TERMS,
    GENCC_TERMS,
    GNOMAD_TERMS,
    GWAS_CATALOG_TERMS,
    PUBMIND_TERMS,
)


@dataclass(frozen=True)
class DerivedProducer:
    """One pass that fills one machine-produced table."""

    #: The CSV this pass writes beside the spec.
    table: str
    #: The command as an operator types it, without the binary — `"frequencies"`,
    #: `"alphagenome expression"`. A sub-app's command carries its group, because that is what is typed.
    command: str
    #: The enricher module holding the pass, so a reader can reach the code from the table.
    module: str
    #: `SourceTerms.source` tokens, in the order the pass consults them. A pass that derives its rows
    #: from tables already beside the spec rather than from a fetch names the sources those rows came
    #: from, because that is the provenance question a reader of the table is actually asking.
    sources: tuple[str, ...]
    #: `VALID_VERIFICATION_CHECKS` members this pass attests while it writes. Empty is honest and
    #: common: filling a table is a recording pass, and only some of them also compare something.
    checks: tuple[str, ...] = ()
    #: Why this pass writes a table another pass also writes, stated iff it shares one. Two writers of
    #: one table is the shape that needs a reason on the page rather than a reader inferring one.
    shares_table_because: str = ""

    def __post_init__(self) -> None:
        if not self.sources:
            raise ValueError(f"{self.command}: a producer names the source(s) its rows come from")


#: `csv -> the pass(es) that fill it`. A tuple because `gene_metrics.csv` genuinely has two writers,
#: and a dict-of-one would have hidden that behind a shape that cannot express it.
DERIVED_PRODUCERS: dict[str, tuple[DerivedProducer, ...]] = {
    "resolution.csv": (
        DerivedProducer(
            table="resolution.csv",
            command="enrich",
            module="enrich",
            # The resolver chain in the order `enrich` tries it: the cache/snapshot first, then the
            # two links that answer where it does not. ENRICHER.md § Resolver chain is the long form.
            sources=(ENSEMBL_TERMS.source, CLINVAR_TERMS.source, GNOMAD_TERMS.source),
            checks=(
                "reference_allele",
                "rsid_currency",
                "clinical_significance",
                "rsid_coordinate_agreement",
                "genome_build_agreement",
                "dataset_currency",
            ),
        ),
    ),
    "frequencies.csv": (
        DerivedProducer(
            table="frequencies.csv",
            command="frequencies",
            module="frequencies",
            sources=(GNOMAD_TERMS.source,),
        ),
    ),
    "gene_metrics.csv": (
        DerivedProducer(
            table="gene_metrics.csv",
            command="gene-metrics",
            module="gene_metrics",
            sources=(GNOMAD_TERMS.source,),
            shares_table_because=(
                "constraint and dosage sensitivity are two different measurements of one gene from two "
                "authorities, and they share a table because a consumer asks one question of it"
            ),
        ),
        DerivedProducer(
            table="gene_metrics.csv",
            command="dosage",
            module="clingen",
            sources=(CLINGEN_TERMS.source,),
            shares_table_because=(
                "ClinGen's haploinsufficiency and triplosensitivity calls are gene metrics like gnomAD's "
                "constraint, and are CC0, which is what keeps a module carrying them sellable"
            ),
        ),
    ),
    "gene_validity.csv": (
        DerivedProducer(
            table="gene_validity.csv",
            command="gene-validity",
            module="gene_validity",
            sources=(CLINGEN_TERMS.source, GENCC_TERMS.source),
        ),
    ),
    "clinical_assertions.csv": (
        DerivedProducer(
            table="clinical_assertions.csv",
            command="assertions",
            module="assertions",
            sources=(CLINVAR_TERMS.source,),
        ),
    ),
    "gwas_effects.csv": (
        DerivedProducer(
            table="gwas_effects.csv",
            command="gwas",
            module="gwas",
            sources=(GWAS_CATALOG_TERMS.source,),
        ),
    ),
    "literature.csv": (
        DerivedProducer(
            table="literature.csv",
            command="literature",
            module="literature",
            # PubMed and Europe PMC are the two registries this pass records against; Crossref answers
            # existence for what PubMed does not index (`@citation-existence`) and writes no row.
            sources=("pubmed", "europepmc"),
            checks=("citation_existence", "citation_identifier"),
        ),
    ),
    "clin_sig_concordance.csv": (
        DerivedProducer(
            table="clin_sig_concordance.csv",
            command="enrich",
            module="concordance",
            # A derived comparison rather than a fetch: the rows come from the authorities `enrich`
            # already consulted, which is why they are named here rather than a request being implied.
            sources=(CLINVAR_TERMS.source, CIVIC_TERMS.source, PUBMIND_TERMS.source),
            checks=("clinical_significance",),
        ),
    ),
    "clin_sig_authority_calls.csv": (
        DerivedProducer(
            table="clin_sig_authority_calls.csv",
            command="enrich",
            module="concordance",
            sources=(CLINVAR_TERMS.source, CIVIC_TERMS.source, PUBMIND_TERMS.source),
            checks=("clinical_significance",),
            shares_table_because=(
                "the per-authority calls are the detail rows behind each concordance verdict, written by "
                "the same pass so a verdict and the calls it was computed from cannot disagree"
            ),
        ),
    ),
    "expression_effects.csv": (
        DerivedProducer(
            table="expression_effects.csv",
            command="alphagenome expression",
            module="expression",
            sources=(ALPHAGENOME_ATLAS_TERMS.source,),
        ),
    ),
}

#: Source tokens a producer may name that have **no** `SourceTerms`, each with the reason — because
#: the alternative is loosening the guard that caught them, which turns a designed absence into an
#: unexplained one. Both are the literature registries and both are `@per-article-terms`: a paper's
#: terms are the *article's*, not the index's, so a single `pubmed` licence constant would state a
#: claim about content the registry does not own. The guard asserts this set is exactly the shortfall,
#: so a third token cannot join them by being typed.
SOURCES_WITHOUT_TERMS: dict[str, str] = {
    "pubmed": (
        "literature terms are per article, never per index — a `pubmed` SourceTerms would make a "
        "licence claim about content PubMed does not own (`@per-article-terms`)"
    ),
    "europepmc": (
        "the same rule one index over: Europe PMC's own terms are not the terms of the articles it "
        "surfaces, and the per-article record is what `literature.csv` carries"
    ),
}

#: Tables written by **every** pass rather than by one, so they have no producer row of their own.
#: `licensing.csv` is the case: `@write-the-sourcerow` says every pass that consults a source writes
#: its row there, and one that contributes nothing writes none — so naming a producer for it would be
#: naming whichever pass happened to be listed first.
WRITTEN_BY_EVERY_PASS: frozenset[str] = frozenset({"licensing.csv", "sources.csv"})


def producers_for(csv_name: str) -> tuple[DerivedProducer, ...]:
    """The pass(es) that fill `csv_name`, or an empty tuple for a table no single pass owns."""
    return DERIVED_PRODUCERS.get(csv_name, ())


#: Every source token any producer names, for a caller that wants the set rather than the mapping.
ALL_PRODUCER_SOURCES: frozenset[str] = frozenset(
    source for group in DERIVED_PRODUCERS.values() for p in group for source in p.sources
)

#: Every command any producer names, likewise — what `test_producers.py` walks the CLI against.
ALL_PRODUCER_COMMANDS: frozenset[str] = frozenset(
    p.command for group in DERIVED_PRODUCERS.values() for p in group
)
