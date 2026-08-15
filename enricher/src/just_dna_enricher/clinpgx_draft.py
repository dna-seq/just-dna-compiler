"""Draft `pharm_variants.csv` rows from the ClinPGx snapshot (0.5, RM26) — the second provider.

The clean contrast to `pgx_draft`: every column `PharmVariantRow` requires is *published*, so this
provider builds real rows and hands them to `draft.append_rows` unchanged. Nothing is stubbed and
nothing is invented. Where `pgx_draft` had to skip what CPIC's grammar could not express, the work
here is almost entirely re-spelling.

**What it fills, and what it deliberately does not.** It fills `rsid`, `gene`, `genotype`, `drug`,
`phenotype_category`, `annotation_id`, `evidence_level` and a transcribed `conclusion`. It does
**not** fill `chrom`/`start`/`ref`: the snapshot carries no coordinate, and even if it did, a
coordinate authored here would be compared by `resolution._verify` against the table that supplied
it. Resolution puts coordinates in `resolution.csv`, which is where they belong — and
`PharmVariantRow.variant_key` is a `@property` over them, so filling them would make a row's identity
depend on the enricher.

**The key is all five parts.** `(variant_key, drug, genotype, phenotype_category, annotation_id)`,
which is `draft.natural_key`'s own answer for this model, so a re-run can never append a row the
compiler would then reject. Indexing ClinPGx by the bare `(variant, drug)` triple is a real bug that
has already been made once in this package.

**One annotation names several drugs.** `drugs` is `;`-joined (`antidepressants;citalopram;paroxetine`
is one annotation), and `drug` is singular, so one snapshot record becomes one row per drug. They
share an `annotation_id` and key distinctly, which is correct: PharmGKB really is saying the same
thing about three drugs.

**One annotation also names several genes, and that one cannot become several rows.** `gene` is
`;`-joined by the same dialect (`PRSS53;VKORC1`) but sits **outside** the dedup key, so copies would
collide where the drug copies do not. `--gene` matches per member — it used to test the whole cell,
silently dropping the 3 VKORC1 rows hiding inside `PRSS53;VKORC1` — and the written cell is the
member the request selects, or empty when nothing selects one. `_authored_gene` carries the
argument.

Skipped, with a warning rather than a coercion: haplotype-keyed genotypes (`*1`, `*1/*1`) belong on
`DiplotypeRow`, and symbolic alleles (`del/del`) carry no length. Both are the policy `pgx_draft`
already set. **The second reason changed in 0.6 and the distinction is worth keeping straight**: the
grammar now holds `<DEL:1500>`, so the block is no longer "the format cannot spell it" but "ClinPGx
does not publish the length, and a lengthless symbolic allele is a rule the compiler drops". A
provider must not write rows the next command in the documented workflow discards.
"""

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.draft import DraftReport, append_rows
from just_dna_format.pgx import PharmVariantRow

from just_dna_enricher.clinpgx import ClinPgxEnrichmentError, _normalize_category, load_snapshot
from just_dna_enricher.licensing import CLINPGX_TERMS, check_declared_use, merge_sources_file

logger = logging.getLogger(__name__)

#: A diploid nucleotide call as ClinPGx writes it: two bases, unseparated (`CC`, `CT`).
_TWO_BASE = re.compile(r"^[ACGT]{2}$")

#: How ClinPGx spells a structural allele inside a genotype cell (`C/del`, `del/del`, `ins/ins`), and
#: the format's own name for the same thing. **Normalising a source's dialect belongs here, at the
#: boundary, not in the schema** — the `CC` → `C/C` rule one function down is the precedent, and a
#: grammar that accepted every source's spelling would owe every consumer the same union.
_CLINPGX_SYMBOLIC: dict[str, str] = {"del": "DEL", "ins": "INS", "dup": "DUP"}

#: ClinPGx joins the drugs one annotation covers with `;` — **and the genes too** (R2-1). The drug
#: half was known and handled from the first release; the gene half was not, and both readers here
#: treated the whole cell as one symbol. Probed against the provisioned snapshot: **396 of 16,087
#: rows** carry a `;` in `gene` (`IFNL3;IFNL4` ×51, `ANKK1;DRD2` ×24, `CYP2A7P1;CYP2B6` ×18), which
#: is the CPIC `gene.chr` lesson again — a claim true of the *cell* and false of the *column*.
#:
#: The two halves are not symmetric, and the asymmetry is the whole design here. `drug` is singular
#: **and outside no key**: it is *in* `PharmVariantRow`'s dedup key, so one record legitimately
#: becomes one row per drug. `gene` is singular and **outside** that key, so the same move is
#: illegal — N rows for N genes collide on
#: `(variant_key, drug, genotype, phenotype_category, annotation_id)` and the compiler refuses the
#: module. See `_authored_gene` for what is written instead.
_SEP = ";"


@dataclass
class ClinPgxDraftResult:
    """What a draft run did."""

    reports: list[DraftReport] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped: bool = False

    @property
    def added(self) -> int:
        return sum(len(r.added) for r in self.reports)

    @property
    def differs(self) -> int:
        return sum(len(r.differs) for r in self.reports)


def _authored_genotype(raw: str | None) -> str | None:
    """`CC` → `C/C`. Only an unambiguous two-base call; anything else is the caller's to skip.

    Splitting is safe *here* precisely because the cell is two single bases: `CT` can only be `C/T`.
    The general case needs the resolved ref/alt to disambiguate, which this pass does not have — so
    it does not guess, it declines. Sorted, because the authored grammar wants an unphased call
    alphabetical."""
    if not raw or not _TWO_BASE.match(raw.strip().upper()):
        return None
    first, second = sorted(raw.strip().upper())
    return f"{first}/{second}"


def _symbolic_types(raw: str | None) -> list[str]:
    """The structural types a ClinPGx genotype cell names, e.g. `C/del` → `['DEL']`. Empty otherwise.

    RM5 widened the grammar to hold `<DEL:1500>`, so the question this pass used to ask — *can the
    format spell it?* — is answered, and the reason these rows are still skipped moved: ClinPGx
    publishes no **length** for its `del`, and a lengthless symbolic allele is a rule the compiler
    drops. Writing the row anyway would emit something a compile is guaranteed to discard, which is
    worse than not writing it: a provider must not hand an author work the next command undoes.

    So this recognizes the dialect in order to *report accurately*, and the value it would have
    produced is deliberately not built. When a source arrives that does publish the length, this is
    where the mapping already is.
    """
    if not raw:
        return []
    found = [
        _CLINPGX_SYMBOLIC[token]
        for token in (t.strip().lower() for t in raw.split("/"))
        if token in _CLINPGX_SYMBOLIC
    ]
    return found


def _rows_from_snapshot(
    records: Sequence[dict],
    *,
    genes: Sequence[str],
    drugs: Sequence[str],
    min_evidence_level: str | None,
) -> tuple[list[PharmVariantRow], list[str]]:
    """Snapshot records → `PharmVariantRow`s, reporting everything the grammar cannot hold."""
    wanted_drugs = {d.strip().lower() for d in drugs if d.strip()}
    wanted_genes = {g.strip().upper() for g in genes if g.strip()}
    rows: list[PharmVariantRow] = []
    warnings: list[str] = []
    skipped_haplotype = skipped_symbolic = skipped_unidentified = 0
    skipped_other = skipped_gene = 0
    withheld_gene: list[str] = []

    for record in records:
        # **The `--gene` filter runs first, and that ordering is the fix for R2-11.** It used to sit
        # below the rsID check, so a record with no rsID from a gene the author never asked about
        # incremented `skipped_unidentified` — and the reported "records the source could not
        # identify" count was inflated by the whole rest of the database on any `--gene` draft,
        # which destroys the one thing that number is for: judging whether the source's coverage of
        # *your* gene is poor. Every skip counter below now counts within the requested scope.
        gene_members = _split_cell(record.get("gene"))
        if wanted_genes and not any(m.upper() in wanted_genes for m in gene_members):
            skipped_gene += 1
            continue
        rsid = (record.get("rsid") or "").strip()
        if not rsid:
            skipped_unidentified += 1
            continue
        gene = _authored_gene(gene_members, wanted_genes)
        if gene is None and len(gene_members) > 1:
            withheld_gene.append(_SEP.join(gene_members))
        raw_genotype = (record.get("genotype") or "").strip()
        genotype = _authored_genotype(raw_genotype)
        if genotype is None:
            if raw_genotype.startswith("*"):
                skipped_haplotype += 1
            elif _symbolic_types(raw_genotype):
                skipped_symbolic += 1
            else:
                skipped_other += 1
            continue
        if min_evidence_level and not _meets_level(record.get("evidence_level"), min_evidence_level):
            continue
        category = _normalize_category(record.get("phenotype_category"))
        annotation_id = (record.get("annotation_id") or "").strip() or None
        for drug in _split_cell(record.get("drugs")):
            if wanted_drugs and drug.lower() not in wanted_drugs:
                continue
            rows.append(
                PharmVariantRow(
                    rsid=rsid,
                    gene=gene,
                    genotype=genotype,
                    drug=drug,
                    phenotype_category=category,
                    annotation_id=annotation_id,
                    evidence_level=(record.get("evidence_level") or None),
                    # **The source's own sentence, verbatim** — which is what "a transcription of the
                    # published parts" was always supposed to mean. It used to synthesize
                    # `"ClinPGx 655385012: C/C and warfarin — dosage"`, a restatement of the row's own
                    # key: every word of it is already in the other columns, so the one column whose
                    # job is to say what the module *claims* said nothing, and no gate anywhere
                    # notices a conclusion that is content-free. `annotation_text` is populated on
                    # 16,087 of 16,087 snapshot rows, is written by our own builder, and was read by
                    # nothing.
                    #
                    # Verbatim rather than summarized, deliberately: the moment this rewords the
                    # sentence it is an interpretation, and the human — who owns what the module
                    # claims — can no longer see what the source actually said. Editing it is the
                    # author's job and the drafter appends rather than mutates, so their edit stands.
                    #
                    # No new licence exposure: the row already carries ClinPGx's `annotation_id` and
                    # the provider writes the `clinpgx` **annotation**-layer licence row beside it, so
                    # the CC BY-SA no-sale terms already gate this module (`declared_use`).
                    conclusion=(
                        (record.get("annotation_text") or "").strip()
                        or f"ClinPGx {annotation_id or '(no id)'}: {genotype} and {drug}"
                        f"{f' — {category}' if category else ''}"
                    ),
                )
            )
    for count, what in (
        (
            skipped_gene,
            "naming a gene outside --gene (the snapshot's `gene` column is populated on ~95% of "
            "rows; a row that names none is filtered out by any --gene)",
        ),
        (skipped_haplotype, "haplotype-keyed (a star allele belongs on diplotypes.csv)"),
        (
            skipped_symbolic,
            "naming a structural allele (del/ins/dup). The grammar holds these since RM5 — "
            "<DEL:1500> — but only with a length, and ClinPGx publishes none, so a row written here "
            "would state a rule nothing can apply and the compiler would drop it. Add the length by "
            "hand if you know it",
        ),
        (skipped_other, "a genotype this format cannot spell (not two bases, not a star allele)"),
        (skipped_unidentified, "carrying no rsID, so nothing this format can key on"),
    ):
        if count:
            warnings.append(f"{count} annotation(s) skipped: {what}.")
    if withheld_gene:
        # Aggregated by *cell*, not one line per row — the collapse rule this package has now needed
        # five times. The cells are named because the author's remedy is to fill the column by hand,
        # and they cannot do that without knowing which genes the source offered.
        cells = sorted(set(withheld_gene))
        warnings.append(
            f"{len(withheld_gene)} annotation(s) drafted with an empty `gene`: ClinPGx names "
            f"several genes in one cell ({', '.join(cells[:5])}"
            f"{f' and {len(cells) - 5} more' if len(cells) > 5 else ''}) and `gene` holds one "
            "symbol. Narrowing with --gene picks the member you asked for; otherwise the cell is "
            "left empty rather than written as a symbol no gene filter will match. The rows are "
            "drafted either way — only the gene column is withheld."
        )
    return rows, warnings


def _split_cell(raw: str | None) -> list[str]:
    """A `;`-joined ClinPGx cell, de-duplicated, first-occurrence order.

    First-occurrence rather than sorted because emitted row order is digest-visible, and shared by
    `drugs` and `gene` because it is one dialect: the separator does not change meaning between two
    columns of the same table. What differs is what the caller may *do* with the members — see
    `_authored_gene`.
    """
    if not raw:
        return []
    seen: dict[str, None] = {}
    for token in str(raw).split(_SEP):
        cleaned = token.strip()
        if cleaned:
            seen.setdefault(cleaned, None)
    return list(seen)


def _authored_gene(members: Sequence[str], wanted_genes: set[str]) -> str | None:
    """Which single symbol a multi-gene ClinPGx cell may be written down as, if any.

    `PharmVariantRow.gene` is described as *"Gene symbol, e.g. VKORC1"* and is singular. A cell
    naming several is the source saying something this column cannot hold, so the question is the
    one `unusable_allele_reason` and `map_function_status` answer elsewhere: transcribe what is
    holdable, and report the rest rather than coercing it.

    Three candidates, and only one survives:

    * **Write the cell verbatim** (`PRSS53;VKORC1`) — what this provider did until R2-1. It is a
      non-symbol in a column documented as a symbol, so every consumer's gene filter misses it for
      exactly the reason ours did, and nothing anywhere rejects it.
    * **One row per gene** — illegal, not merely undesirable. `gene` is outside
      `PharmVariantRow`'s dedup key, so the copies collide on
      `(variant_key, drug, genotype, phenotype_category, annotation_id)` and the compiler refuses
      the module. This is the structural difference from `drugs`, which *is* in the key.
    * **Pick a member from the cell alone** — there is no rule to pick by. The pharmacogene is
      first in `CYP3A5;ZSCAN25`, second in `ANKK1;DRD2`, `CYP2A7P1;CYP2B6` and `PRSS53;VKORC1`, so
      position orders nothing and "the one that matters" is a judgement about pharmacology this
      tier does not get to make.

    What is left is the CPIC `gene.chr` move — a **lookup in what the caller already stated**, not
    an inference. Under `--gene VKORC1` the request selects exactly one member of `PRSS53;VKORC1`,
    and writing it asserts only what the source asserts (this annotation names VKORC1). With no
    request, or with a request selecting two members of one cell, nothing selects, and the answer is
    the house one: **withhold**, and say so. An empty cell reads as *not stated*, which is weaker
    than the truth but is not false; the verbatim cell is false about its own column.
    """
    if len(members) == 1:
        return members[0]
    if not members:
        return None
    selected = [m for m in members if m.upper() in wanted_genes]
    return selected[0] if len(selected) == 1 else None


#: PharmGKB's levels, strongest first. Ordering them is a *presentation* of a published ranking, not
#: a re-encoding: unlike ClinGen's dosage codes, these sort correctly as strings only by accident
#: (`1A` < `1B` < `2A` … but `4` > `2A`), so the order is written out.
_LEVEL_ORDER: tuple[str, ...] = ("1A", "1B", "2A", "2B", "3", "4")


def _meets_level(level: str | None, floor: str) -> bool:
    """Is `level` at least as strong as `floor`? An unknown level is kept, never silently dropped."""
    if not level:
        return True
    try:
        return _LEVEL_ORDER.index(level) <= _LEVEL_ORDER.index(floor)
    except ValueError:
        return True


def draft_pharm_variants(
    spec_dir: Path,
    *,
    snapshot: Path,
    genes: Sequence[str] = (),
    drugs: Sequence[str] = (),
    min_evidence_level: str | None = None,
    declared_use: str = "unstated",
    dry_run: bool = False,
) -> ClinPgxDraftResult:
    """Append ClinPGx annotations into `pharm_variants.csv`, never rewriting a row that is there.

    Inject-only: `snapshot` is a path this function reads, never downloads (build it with
    `just-dna-enricher clinpgx build`). Re-runnable — narrow by `--drug` and run again as a module
    grows; a row already present is reported, not replaced.
    """
    skip_reason = check_declared_use(CLINPGX_TERMS, declared_use)
    if skip_reason:
        # Acquisition-time refusal: the terms are accepted by taking the data, so nothing is read.
        return ClinPgxDraftResult(warnings=[skip_reason], skipped=True)

    records, release = load_snapshot(snapshot)
    rows, warnings = _rows_from_snapshot(
        records, genes=genes, drugs=drugs, min_evidence_level=min_evidence_level
    )
    if not rows:
        return ClinPgxDraftResult(warnings=warnings + ["nothing matched; no rows drafted"])

    reports = [append_rows(spec_dir, "pharm_variants.csv", rows, dry_run=dry_run)]
    if not dry_run:
        # A pass that consults a source must WRITE its SourceRow: the compile gate and
        # `manifest.sources` read sources.csv and nothing else, so a row that is only returned is a
        # source the module cannot account for.
        merge_sources_file(
            [
                CLINPGX_TERMS.row(
                    "annotation",
                    declared_use=declared_use,
                    dataset=release.get("dataset"),
                )
            ],
            spec_dir,
            error=ClinPgxEnrichmentError,
        )
    return ClinPgxDraftResult(reports=reports, warnings=warnings)
