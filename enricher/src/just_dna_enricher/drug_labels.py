"""`clinpgx check-labels` — a module's PGx claims against the drug labels five regulators publish.

ClinPGx's `drugLabels.zip` annotates the pharmacogenomic content of medicine labels from **five**
agencies — FDA, Health Canada (HCSC), EMA, Swissmedic and PMDA. The item that adopts it (RM166) asked
for the FDA and the file supplied four more at no extra cost, which is why nothing in this surface
names an agency: the number of authorities is a *parameter*, and baking one into a published name is
the mistake RM134 caught in `ClinSigConflict` before it shipped. The attestation key is
`regulator_label_agreement`, and the fifth agency costs one more row in the index.

**Two join tiers, and the tier is a property of the SUBJECT.** A label names a gene, and 15 % of them
also name a variant or a star allele, so a module's claim is put at two granularities: `(gene, drug)`
is the gene-tier question and `(gene, allele, drug)` the allele-tier one. A label naming both answers
**both**, because they are two questions rather than one asked twice. Every finding says which tier it
came from, because *"three agencies disagree about CYP2C19\\*2 and clopidogrel"* and *"five agencies
disagree about CYP2C19 and clopidogrel"* send an author to different places — and the alternative,
scoring every authored allele against whatever the gene-level labels say, reported the EMA's single
disagreement 34 times on `cyp2c19_star_alleles`, once per star allele the label never mentions.

**A blank `Testing Level` is `unknown` and withholds.** A third of the file states none (472 of 1,433
on 2026-08-05), and reading a blank as `No Clinical PGx` would turn the largest silence in the source
into its most common negative claim. So an unstated level is counted, reported, and kept out of every
verdict — `unknown AND false` is `false`, so it cannot un-see a disagreement already witnessed, and it
never establishes an agreement on its own.

**Only the two ends of the level axis are placed against an authored claim, deliberately.** The module
carries no testing-level column, so `Testing Required` → `strong` is a mapping this format would be
inventing. `No Clinical PGx` needs no mapping — it is the negative claim by its own name — so the one
authored arm fires when a module ships a prescribing recommendation for a pair every label that stated
a level calls `No Clinical PGx`. The three middle levels are stated and *unplaced*: a verdict this
check declines to reach is reported as such rather than as an agreement.

**Never escalates under `--strict`.** Five expert regulators genuinely disagree with each other and
with a curator — the clopidogrel/CYP2C19 labels are `Actionable PGx` at four agencies and `Informative
PGx` at the EMA — and failing a compile over that would make the format arbitrate between its own
authorities (`@clinsig-never-escalates`, `@a-source-recuring-is-not-a-strict-matter`). `strict` still
refuses a *structural* failure: an authored table that will not load raises in both modes.

**It writes no `SourceRow`, and that is a decision rather than an omission.** Two reasons, and either
alone would settle it. Nothing from the labels lands in the module — this check writes no authored
cell, and `sources.csv` accounts for what a module *carries* (`@write-the-sourcerow`'s converse: a pass
that contributes nothing writes none; `strchive`'s band check is the shipped precedent). And the row it
would write is not free: `merge_sources_csv` keys on `(source, layer)`, `clinpgx`/`annotation` is
already owned by `clinpgx check` and `draft-clinpgx`, and its `dataset` is load-bearing — the
evidence-level check's tautology guard compares that recorded label against the *annotation* snapshot's.
Stamping `clinpgx_drug_labels_<date>` into that slot would silently disable a shipped check, which is
`@two-surfaces-two-denominators` reaching `sources.csv`. Every other layer is outside the compiler's
orphan-check exemption and would warn `source_row_unused` on every module.

**The licence gate still applies**, at the `clinpgx_draft`/`clinpgx check` reading rather than a third
one: ClinPGx's terms are accepted when the data is taken, so a `commercial` declaration refuses here
too, and the skip is `not_permitted` — what clears it is a *declaration*, not egress.
"""

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.manifest import VerificationRecord
from just_dna_format.pgx import DiplotypeRow, PharmVariantRow

from just_dna_enricher.licensing import CLINPGX_TERMS, check_declared_use
from just_dna_enricher.locations import (
    RELEASE_FILENAME,
    SNAPSHOT_DATA_DIRNAME,
    resolve_drug_labels_reference,
)
from just_dna_enricher.verification import examples, ran, record_verification, skipped

logger = logging.getLogger(__name__)

#: The licensed source, taken from the terms constant rather than re-spelled: this string reaches
#: `verification.json` beside a record `clinpgx check` also writes, and two spellings of one source
#: would split a consumer's grouping. The *agencies* are data in the `regulator` column and are never
#: named by this module.
SOURCE_NAME: str = CLINPGX_TERMS.source

#: The check key, and the parquet the snapshot stores the labels in.
CHECK_NAME = "regulator_label_agreement"
LABELS_PARQUET = "drug_labels.parquet"

#: The archive the snapshot is built from, on the endpoint `summaryAnnotations.zip` already comes
#: from. It lives in the *reader* rather than in the builder so the CLI can offer it as a `--url`
#: default without importing the `[dev]` builder at start-up (`drug_labels_build` imports it back).
DEFAULT_DRUG_LABELS_URL = "https://api.clinpgx.org/v1/download/file/data/drugLabels.zip"

#: The snapshot's column order, bound here because the reader is what a column list is *for*; the
#: builder derives its schema from this tuple rather than keeping a second copy.
LABEL_COLUMNS: tuple[str, ...] = (
    "label_id",
    "label_name",
    "regulator",
    "biomarker_flag",
    "testing_level",
    "has_prescribing_info",
    "has_dosing_info",
    "has_alternate_drug",
    "has_other_prescribing_guidance",
    "cancer_genome",
    "prescribing",
    "chemicals",
    "genes",
    "variants",
    "latest_history_date",
)

#: The multi-value separator inside a `Genes` / `Chemicals` / `Variants/Haplotypes` cell.
#:
#: **`;` only, and NOT `vocab.MULTI_SEP`.** That pattern splits on `,;|`, and a comma inside one of
#: these cells is data rather than a separator: `DPYD c.1129-5923C>G, c.1236G>A (HapB3)` is one
#: haplotype named by two variants, and `Ascorbic acid (vitamin C), combinations` is one chemical.
#: Splitting on the comma reports 604 variant tokens where the file states 601, and turns three real
#: names into six that match nothing.
CELL_SEPARATOR = ";"

#: ClinPGx's PGx level for a label, as published. Derived from the payload rather than from the
#: documentation, and a test walks the fixture and asserts equality with this set
#: (`@registry-completeness`) — a sixth member upstream must be a visible edit here, not a silent
#: `.get(x, default)` (`@lookup-with-a-default-hides-a-new-member`).
VALID_TESTING_LEVELS: frozenset[str] = frozenset(
    {
        "Testing Required",
        "Testing Recommended",
        "Actionable PGx",
        "Informative PGx",
        "No Clinical PGx",
    }
)

#: The one member this check places against an authored recommendation. It needs no ordinal ladder —
#: the name is the claim.
NO_CLINICAL_PGX = "No Clinical PGx"

#: The two join tiers, finest first. The tier is a property of the **subject** — see `LabelSubject` —
#: so a label naming a star allele answers the allele-tier subject and the gene-tier one both.
LABEL_TIERS: tuple[str, ...] = ("allele", "gene")

#: Do the regulators that spoke at this tier state the same level?
VALID_LABEL_CONCORDANCE: frozenset[str] = frozenset(
    {"concordant", "discordant", "single", "unstated", "none"}
)

#: Where the module's own claim sits relative to them.
#:
#: **`VALID_LABEL_POSITION`, not `VALID_AUTHORED_POSITION`**, which is a *different* closed vocabulary
#: in `just_dna_format.vocab` with different members — `matches_all` / `matches_some` / `matches_none`
#: / `absent` / `unchecked`, the clinical-significance concordance axis. Two names that shadow each
#: other on import and disagree about their members is a silent wrong answer waiting for the first
#: module that reads both, so this one carries the lane's prefix the way `VALID_LABEL_CONCORDANCE`
#: does beside `VALID_AUTHORITY_CONCORDANCE`.
VALID_LABEL_POSITION: frozenset[str] = frozenset(
    {"opposed", "unplaced", "unchecked", "absent", "no_label"}
)

#: What the module says about the pair, read from `recommendation_strength` alone.
VALID_LABEL_ACTION: frozenset[str] = frozenset({"recommends", "declines", "absent"})

#: The authored tables this check reads. `pharm_variants.csv` contributes subjects keyed on an rsID —
#: 415 of the 601 variant tokens in the file are rsID-shaped, so the allele tier is not the star
#: alleles alone.
DIPLOTYPES_CSV = "diplotypes.csv"
PHARM_VARIANTS_CSV = "pharm_variants.csv"

#: One sentence per concordance member, pairwise distinct (`@answered-is-not-absent`). A verdict
#: function with five arms owes a reason function with five arms.
_CONCORDANCE_SENTENCES: dict[str, str] = {
    "concordant": "every label that stated a level states the same one",
    "discordant": "the labels that stated a level do not state the same one",
    "single": "one label stated a level, and one voice is not corroboration",
    "unstated": "a label reaches this subject but none of them states a testing level",
    "none": "no label reaches this subject at this tier",
}

#: One sentence per authored-position member, pairwise distinct.
_POSITION_SENTENCES: dict[str, str] = {
    "opposed": (
        "the module states a prescribing recommendation where every label that stated a level says "
        "the medicine carries no clinical pharmacogenomics"
    ),
    "unplaced": (
        "the levels in play are ones this check does not place against a prescribing "
        "recommendation, so no position is claimed"
    ),
    "unchecked": "the labels reached state no testing level, so the question was put and not answered",
    "absent": "the module states no recommendation strength for this pair",
    "no_label": "no label reaches this subject at this tier, so there is nothing to take a position on",
}

#: Every kind of finding, with the sentence each one gets — one map rather than a chain of `if`s, and
#: a test asserts the emitted kinds equal these keys.
#: **`label(s)` and never `regulator(s)`**, because one agency can carry two labels for one pair:
#: Swissmedic states `Testing Recommended` for simvastatin + SLCO1B1 and `Actionable PGx` for the
#: fenofibrate/simvastatin combination, both naming `rs4149056`. Both rows are kept and neither is
#: picked as the agency's opinion (`@multiplicity-is-a-finding`), so the count is of labels.
#:
#: **`{count}` is the labels that STATED a level, never every label reached.** The first version
#: counted all of them and produced *"4 label(s) … state ['Actionable PGx', 'Testing Recommended']"*
#: over a set of four that included two stating nothing — and on the `opposed` arm that sentence would
#: have read a blank cell as `No Clinical PGx`, which is the one reading this whole module forswears.
#: The silent ones are named by `{silent}` instead, so nothing about them is dropped.
_FINDING_SENTENCES: dict[str, str] = {
    "regulators_disagree": (
        "{count} label(s) reaching this pair at the {tier} tier state {levels}{silent}"
    ),
    "recommendation_without_label_pgx": (
        "the module recommends here, and {count} label(s) reaching this pair at the {tier} "
        f"tier state {NO_CLINICAL_PGX!r}" + "{silent}"
    ),
}


class DrugLabelError(RuntimeError):
    """A drug-label snapshot could not be read, or an authored table could not be loaded."""


class DrugLabelUnavailable(DrugLabelError):
    """No snapshot was provisioned, so the comparison could not be put at all."""


@dataclass(frozen=True)
class LabelRow:
    """One regulator's label annotation, reduced to what this check reads.

    Deliberately not the whole record. `label_name`, `biomarker_flag`, the prescribing flags and the
    history date are in the snapshot and are not parsed here, because nothing in this check emits
    them — a field carried and never used is dead weight. A reader who wants the label's title has
    its `label_id`, which is ClinPGx's own accession for it.
    """

    label_id: str
    regulator: str
    testing_level: str | None
    genes: tuple[str, ...]
    chemicals: tuple[str, ...]
    variants: tuple[str, ...]

    def __str__(self) -> str:
        return f"{self.regulator} {self.label_id} ({self.testing_level or 'no level stated'})"


@dataclass(frozen=True)
class LabelCall:
    """What one label says about one subject, and the token the join matched on."""

    row: LabelRow
    #: A star allele, an rsID, or the gene symbol. Recorded so a reader can tell `CYP2C19*2` from
    #: `CYP2C19` without re-deriving the join.
    matched_on: str

    @property
    def stated(self) -> bool:
        """Whether this regulator stated a testing level at all — never whether it stated a *no*."""
        return self.row.testing_level is not None


@dataclass(frozen=True)
class LabelSubject:
    """One claim the module makes, at one join granularity.

    **The tier is a property of the subject, not of the call**, and that is the whole shape of the
    comparison. `(gene, drug)` is the gene-tier question — *what do the agencies say about this gene
    and this medicine* — and `(gene, allele, drug)` is the allele-tier one. A label naming both
    answers both, because they are two questions and not one asked twice.

    The alternative, scoring every authored allele against whatever the gene-level labels say, was
    written first and measured: on `cyp2c19_star_alleles` it reported the EMA's single disagreement
    about clopidogrel **34 times**, once per star allele, none of which the label mentions.
    """

    gene: str
    allele: str | None
    drug: str

    @property
    def tier(self) -> str:
        return "allele" if self.allele else "gene"

    def __str__(self) -> str:
        # `CYP2C19*2` is the source's own spelling and reads as one token; `CYP4F2rs2108622` does
        # not, so an rsID gets the space it needs.
        if not self.allele:
            where = self.gene
        elif self.allele.startswith("*"):
            where = f"{self.gene}{self.allele}"
        else:
            where = f"{self.gene} {self.allele}"
        return f"{where} + {self.drug}"


@dataclass(frozen=True)
class LabelVerdict:
    """The two orthogonal verdicts for one subject at one tier.

    Two fields rather than one, for RM134's reason: *do the authorities agree with each other* and
    *where does the module sit relative to them* are different questions, and folding them into a
    single value makes an unreachable authority indistinguishable from an agreement.
    """

    concordance: str
    position: str
    contested: bool


@dataclass(frozen=True)
class LabelFinding:
    """One established difference about one subject. Its tier is the subject's."""

    kind: str
    subject: LabelSubject
    calls: tuple[LabelCall, ...]

    @property
    def tier(self) -> str:
        return self.subject.tier

    def __str__(self) -> str:
        spoke = [call for call in self.calls if call.stated]
        silent = len(self.calls) - len(spoke)
        sentence = _FINDING_SENTENCES[self.kind].format(
            count=len(spoke),
            tier=self.tier,
            levels=sorted({call.row.testing_level for call in spoke}),
            silent=f", and {silent} more state no level" if silent else "",
        )
        who = ", ".join(str(call.row) for call in self.calls)
        return f"{self.subject}: {sentence} — {who}"


@dataclass
class DrugLabelIndex:
    """A parsed snapshot, plus the two joins the check puts questions to.

    Both joins are materialized once at construction rather than scanned per subject: a module with a
    diplotype table states one subject per star allele per drug, and a linear pass over 1,433 labels
    for each of them is the shape that turns a check into a wait. File order is preserved inside each
    bucket, so what the record reports does not depend on dictionary iteration (Principle 7).
    """

    labels: tuple[LabelRow, ...]
    dataset: str | None = None
    #: `(allele token, chemical)` and `(gene symbol, chemical)`, both case-folded, → the labels
    #: naming both. Built in `__post_init__`, so a caller cannot hold one that disagrees with `labels`.
    _by_allele: dict[tuple[str, str], list[LabelRow]] = field(default_factory=dict, repr=False)
    _by_gene: dict[tuple[str, str], list[LabelRow]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._by_allele.clear()
        self._by_gene.clear()
        for row in self.labels:
            chemicals = {value.casefold() for value in row.chemicals}
            for chemical in chemicals:
                for token in row.variants:
                    self._by_allele.setdefault((token.casefold(), chemical), []).append(row)
                for gene in row.genes:
                    self._by_gene.setdefault((gene.casefold(), chemical), []).append(row)

    def testing_levels(self) -> frozenset[str]:
        """Every level this snapshot actually states — the walked set the vocabulary is asserted against."""
        return frozenset(row.testing_level for row in self.labels if row.testing_level)

    def regulators(self) -> frozenset[str]:
        return frozenset(row.regulator for row in self.labels if row.regulator)

    def by_allele(self, allele: str, drug: str) -> tuple[LabelRow, ...]:
        """Labels naming this allele token and this chemical, in file order."""
        return tuple(self._by_allele.get((allele.casefold(), drug.casefold()), ()))

    def by_gene(self, gene: str, drug: str) -> tuple[LabelRow, ...]:
        """Labels naming this gene symbol and this chemical, in file order."""
        return tuple(self._by_gene.get((gene.casefold(), drug.casefold()), ()))


def _split(cell: str | None) -> tuple[str, ...]:
    """A multi-value cell as its tokens. See `CELL_SEPARATOR` for why the comma is not one."""
    if not cell:
        return ()
    return tuple(token.strip() for token in cell.split(CELL_SEPARATOR) if token.strip())


def load_drug_labels(reference: Path) -> DrugLabelIndex:
    """Read a built snapshot directory: the parquet, and the `release.json` label beside it.

    Read with **duckdb**, not polars — builder in polars, runtime pass in duckdb, the convention
    `clinpgx.load_snapshot` and `clinvar.py` already follow. The column list is `SELECT *` for the
    reason a hand-kept projection lost `gene` and `annotation_text` from the annotation snapshot.
    """
    reference = Path(reference)
    parquet = reference / SNAPSHOT_DATA_DIRNAME / LABELS_PARQUET
    if not parquet.is_file():
        raise DrugLabelUnavailable(f"no drug-label snapshot at {parquet}")
    release_path = reference / RELEASE_FILENAME
    dataset: str | None = None
    if release_path.is_file():
        try:
            release = json.loads(release_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # A snapshot whose provenance file is damaged still holds readable labels; losing the
            # label is a weaker outcome than refusing the comparison, and the record says `None`.
            logger.warning("Could not read %s (%s); the release label is unknown.", release_path, exc)
        else:
            dataset = (release.get("dataset") or None) if isinstance(release, dict) else None

    pattern = str(parquet).replace("'", "''")
    con = duckdb.connect(":memory:")
    try:
        cursor = con.execute(f"SELECT * FROM read_parquet('{pattern}')")
        columns = [description[0] for description in cursor.description]
        records = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    finally:
        con.close()

    missing = sorted(set(LABEL_COLUMNS) - set(columns))
    if missing:
        raise DrugLabelError(
            f"{parquet} is missing {len(missing)} expected column(s): {missing}. Rebuild it with "
            f"`just-dna-enricher clinpgx build-labels`."
        )
    labels = tuple(
        LabelRow(
            label_id=record["label_id"],
            regulator=record["regulator"] or "",
            testing_level=record["testing_level"],
            genes=_split(record["genes"]),
            chemicals=_split(record["chemicals"]),
            variants=_split(record["variants"]),
        )
        for record in records
        if record.get("label_id")
    )
    return DrugLabelIndex(labels=labels, dataset=dataset)


# ── The comparison ──────────────────────────────────────────────────────────────────────────────


def classify_labels(action: str, calls: Sequence[LabelCall]) -> LabelVerdict:
    """The two verdicts for one subject at one tier, at any number of labels.

    **`concordance` — do the labels that stated a level agree with each other?** A disagreement already
    witnessed is not un-witnessed by an agency that stated no level (`unknown AND false` is `false`),
    so `discordant` wins over `unstated`. Otherwise an unstated level leaves the question open and the
    answer is `unstated` rather than an agreement nobody established. With every level stated it is
    `concordant` for two or more agreeing, `single` for exactly one — one voice is not corroboration
    — and `none` when no label reaches this subject at this tier at all.

    **The unit is the label, not the agency.** One regulator can publish two labels reaching one pair —
    Swissmedic covers simvastatin + SLCO1B1 twice, once for the drug and once for the
    fenofibrate/simvastatin combination, at two different levels — and collapsing them to one opinion
    per agency would need a winner this check has no basis to pick (`@multiplicity-is-a-finding`).

    Level *equality*, not an ordering: this comparison needs no ladder, so a level upstream adds later
    still classifies correctly here and only the `opposed` arm below has to learn about it.

    **`position` — where does the module's own claim sit?** `no_label` first, because a tier with no
    label offers nothing to take a position against whatever the module says. `opposed` is the one
    arm this check places, and it needs the negative claim by name rather than by rank: the module
    recommends, and every level stated is `No Clinical PGx`. `unchecked` is labels reached and no
    level stated; `unplaced` is the deliberate withholding — a stated level this check does not rank
    against a recommendation strength.
    """
    if action not in VALID_LABEL_ACTION:
        raise DrugLabelError(f"not an authored action: {action!r}")
    spoke = [call for call in calls if call.stated]
    silent = [call for call in calls if not call.stated]
    levels = {call.row.testing_level for call in spoke}

    if not calls:
        concordance = "none"
    elif len(levels) > 1:
        concordance = "discordant"
    elif silent:
        concordance = "unstated"
    elif len(spoke) >= 2:
        concordance = "concordant"
    else:
        concordance = "single"

    if not calls:
        position = "no_label"
    elif action == "absent":
        position = "absent"
    elif not spoke:
        position = "unchecked"
    elif action == "recommends" and levels == {NO_CLINICAL_PGX}:
        position = "opposed"
    else:
        # Includes `declines`, in both directions, and that withholding is deliberate: a module
        # declining to recommend for one diplotype is a statement about that genotype, not about
        # whether the drug's label carries pharmacogenomics, so a `Testing Required` label beside it
        # is not the opposite claim (`@refutation-withholds`).
        position = "unplaced"

    return LabelVerdict(
        concordance=concordance,
        position=position,
        contested=concordance == "discordant" or position == "opposed",
    )


@dataclass
class DrugLabelResult:
    """What the comparison put, what it withheld, and why — the tri-state made reportable."""

    findings: list[LabelFinding] = field(default_factory=list)
    #: Subjects at least one label reached. The attestation's denominator.
    compared: list[LabelSubject] = field(default_factory=list)
    #: `(subject, sentence)` for a claim no label reaches at either tier. Counted, never negated: a
    #: pair no agency has labelled has not been shown to lack pharmacogenomics.
    withheld: list[tuple[LabelSubject, str]] = field(default_factory=list)
    #: `subject -> verdict`, so a reader can see the arm each subject landed in. The subject carries
    #: its own tier, so this needs no second key.
    verdicts: dict[LabelSubject, LabelVerdict] = field(default_factory=dict)
    #: Subjects answered at each tier — the two join tiers, counted rather than merged.
    tier_subjects: dict[str, int] = field(default_factory=dict)
    #: Allele claims no label names **whose gene-tier sibling WAS answered**. Not withheld and not a
    #: finding: the gene-tier subject for the same pair is what answers for them, so this is a coverage
    #: number rather than a silence (`@dont-discard-computed`). An allele whose gene-tier sibling is
    #: itself unlabelled has no such answer and goes to `withheld` instead — the first version put it
    #: here and the attestation then said, of one `cyp2c9_warfarin_grch37` claim, both that it was
    #: answered at the gene tier and that no regulator labels the pair.
    unnamed_alleles: list[LabelSubject] = field(default_factory=list)
    #: Label ids reached whose `Testing Level` is blank — a third of the file, so it is published
    #: rather than dropped (`@dont-discard-computed`). **Label ids and not a running count**, because a
    #: blank label naming both a gene and one of its alleles is reached by two subjects and is still
    #: one label; incrementing per call reported it twice under a sentence that says "label(s)".
    unstated_labels: set[str] = field(default_factory=set)

    #: `verdict arm -> how many subjects landed in it`, per axis. The arms a run actually reached,
    #: which is what lets the record publish the reason map instead of only the bare token.
    concordance_arms: dict[str, int] = field(default_factory=dict)
    position_arms: dict[str, int] = field(default_factory=dict)
    #: Levels the snapshot states that `VALID_TESTING_LEVELS` does not know.
    unknown_levels: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mode: str = "best_effort"
    declared_use: str = "unstated"
    dataset: str | None = None
    regulators: list[str] = field(default_factory=list)
    not_checked: str | None = None

    @property
    def contested(self) -> set[LabelSubject]:
        """Subjects carrying at least one finding — the numerator, which cannot exceed `compared`."""
        return {finding.subject for finding in self.findings}


def _allele_keys(gene: str, allele: str) -> tuple[str, ...]:
    """Every spelling of one authored allele the label file might use, most specific first.

    **The star tokens are NOT `haplotypes.csv`'s key verbatim**, which the item's own entry says they
    are. The file writes `CYP2C19*2`; the module writes `*2` in `haplotype_name` with `CYP2C19` in a
    separate `gene` column, so the join has to compose them.

    **And it composes them two ways, because the file spells a gene-qualified token two ways.** The
    star alleles run together (`CYP2C19*2`, `TPMT*3A`) but the DPYD haplotypes are spaced
    (`DPYD c.1905+1G>A (*2A)`, `DPYD c.1129-5923C>G, c.1236G>A (HapB3)`). Trying only the concatenation
    told a DPYD module its allele was named by no label while two regulators named it exactly, which is
    a false coverage claim rather than a miss. The bare spelling is tried last, for an rsID subject
    that carries no gene prefix and an HLA allele already authored with one.
    """
    stripped = allele.strip()
    if not stripped:
        return ()
    if stripped.casefold().startswith(gene.casefold()):
        return (stripped,)
    return (f"{gene}{stripped}", f"{gene} {stripped}", stripped)


def _authored_action(strengths: Sequence[str | None]) -> str:
    """`recommends` / `declines` / `absent`, from the `recommendation_strength` cells alone.

    `evidence_level` is deliberately not read: it is ClinPGx's own metadata about its own annotation,
    `clinpgx check` owns that column, and treating "there is 1A evidence" as "this module recommends"
    would put two axes in one field.
    """
    stated = [value for value in strengths if value]
    if not stated:
        return "absent"
    if any(value != "no_recommendation" for value in stated):
        return "recommends"
    return "declines"


def authored_subjects(spec_dir: Path) -> dict[LabelSubject, str]:
    """Every claim the module makes, at **both** granularities, with its authored action.

    A `diplotypes.csv` row naming a drug contributes three subjects: the gene-tier `(gene, drug)` and
    one allele-tier subject per haplotype. A `pharm_variants.csv` row contributes the gene-tier pair
    and its rsID. The gene-tier subject aggregates every row for the pair, which is what makes it the
    question the gene-level labels are actually answering.

    Row order is the module's own, preserved rather than sorted, so the reported order does not depend
    on which tables a deployment happens to hold (Principle 7).
    """
    spec_dir = Path(spec_dir)
    strengths: dict[LabelSubject, list[str | None]] = {}

    def _claim(gene: str, allele: str | None, drug: str, strength: str | None) -> None:
        for subject in (LabelSubject(gene, None, drug), LabelSubject(gene, allele or None, drug)):
            strengths.setdefault(subject, []).append(strength)

    diplotypes = spec_dir / DIPLOTYPES_CSV
    if diplotypes.exists():
        rows, errors, _ = load_csv_rows(diplotypes, DiplotypeRow, DIPLOTYPES_CSV)
        if errors:
            # Structural, so it refuses in BOTH modes: `strict` not escalating a source disagreement
            # says nothing about a file that will not load.
            raise DrugLabelError(f"{DIPLOTYPES_CSV} is invalid: {errors[0]}")
        for row in rows:
            if not row.drug or not row.gene:
                continue
            for allele in (row.haplotype_a, row.haplotype_b):
                _claim(row.gene, allele, row.drug, row.recommendation_strength)

    pharm = spec_dir / PHARM_VARIANTS_CSV
    if pharm.exists():
        rows, errors, _ = load_csv_rows(pharm, PharmVariantRow, PHARM_VARIANTS_CSV)
        if errors:
            raise DrugLabelError(f"{PHARM_VARIANTS_CSV} is invalid: {errors[0]}")
        for row in rows:
            if not row.drug or not row.gene:
                continue
            # `PharmVariantRow` has no `recommendation_strength`, so a variant row states an
            # association and never a prescribing action: it contributes the subject and `absent`.
            _claim(row.gene, row.rsid, row.drug, None)

    return {subject: _authored_action(values) for subject, values in strengths.items()}


def calls_for(index: DrugLabelIndex, subject: LabelSubject) -> tuple[LabelCall, ...]:
    """Every label that answers one subject, in the snapshot's own row order.

    A label naming `CYP2C19*2` answers the allele subject **and** the gene subject, because those are
    two different questions rather than one asked twice: *what do the agencies say about this gene and
    this medicine* is a claim in its own right, and a label enumerating alleles has made it.
    """
    if not subject.allele:
        return tuple(
            LabelCall(row=row, matched_on=subject.gene)
            for row in index.by_gene(subject.gene, subject.drug)
        )
    calls: list[LabelCall] = []
    seen: set[str] = set()
    for key in _allele_keys(subject.gene, subject.allele):
        for row in index.by_allele(key, subject.drug):
            if row.label_id in seen:
                continue
            seen.add(row.label_id)
            calls.append(LabelCall(row=row, matched_on=key))
    return tuple(calls)


def check_drug_labels(
    spec_dir: Path,
    *,
    snapshot: Path | DrugLabelIndex | None = None,
    mode: str = "best_effort",
    declared_use: str = "unstated",
    write: bool = True,
) -> DrugLabelResult:
    """Compare a module's PGx claims against the regulator drug labels. Reports, never repairs.

    `mode` is carried for the report and **is not a severity ladder here**: five agencies drawing a
    line in different places is a difference between authorities, and `strict` refusing it would have
    the format pick the winner. The one thing `strict` still refuses is structural — an authored table
    that will not load — and that refuses in `best_effort` too.
    """
    spec_dir = Path(spec_dir)
    result = DrugLabelResult(mode=mode, declared_use=declared_use)

    if not (spec_dir / DIPLOTYPES_CSV).exists() and not (spec_dir / PHARM_VARIANTS_CSV).exists():
        # **Not attested, and this is the one skip that must not be.** A module carrying no PGx table
        # has posed no question a drug label could answer, and recording a skip would mine a nonce and
        # create a `verification.json` on a module that never asked for one.
        result.warnings.append(
            f"drug-label cross-check skipped: the module carries neither {DIPLOTYPES_CSV} nor "
            f"{PHARM_VARIANTS_CSV}."
        )
        result.not_checked = "nothing_to_check"
        return result

    reason = check_declared_use(CLINPGX_TERMS, declared_use)  # raises on `commercial`
    if reason is not None:
        result.warnings.append(reason)
        logger.warning("%s", reason)
        result.not_checked = "not_permitted"
        return _attest(result, spec_dir, write=write)

    subjects = authored_subjects(spec_dir)
    if not subjects:
        note = (
            f"neither {DIPLOTYPES_CSV} nor {PHARM_VARIANTS_CSV} names a drug alongside a gene, so "
            f"the module states no claim a medicine label speaks to"
        )
        result.warnings.append(note)
        result.not_checked = "nothing_to_check"
        return _attest(result, spec_dir, write=write)

    if snapshot is None:
        # A provisioned snapshot is used without being named — the same repair the ClinPGx annotation
        # lane got when `resolve_clinpgx_reference` landed, one archive later.
        snapshot = resolve_drug_labels_reference()
    if snapshot is None:
        note = (
            "drug-label cross-check skipped: no snapshot was provisioned. Build one with "
            "`just-dna-enricher clinpgx build-labels --out <dir>`, or point at one with --snapshot."
        )
        result.warnings.append(note)
        logger.warning("%s", note)
        result.not_checked = "no_reference"
        return _attest(result, spec_dir, write=write)

    index = snapshot if isinstance(snapshot, DrugLabelIndex) else load_drug_labels(snapshot)
    result.dataset = index.dataset
    result.regulators = sorted(index.regulators())
    result.unknown_levels = sorted(index.testing_levels() - VALID_TESTING_LEVELS)
    if result.unknown_levels:
        note = (
            f"this snapshot states {len(result.unknown_levels)} testing level(s) this release does "
            f"not know: {result.unknown_levels}. They are compared for agreement like any other "
            f"level and are never read as {NO_CLINICAL_PGX!r}."
        )
        result.warnings.append(note)
        logger.warning("%s", note)

    result.tier_subjects = dict.fromkeys(LABEL_TIERS, 0)
    for subject, action in subjects.items():
        calls = calls_for(index, subject)
        if not calls:
            # **An allele is only "covered by the gene tier" when the gene tier has an answer.** The
            # question is asked of the index rather than of what this loop has recorded so far, so
            # the verdict does not depend on the order the subjects happen to arrive in.
            if subject.allele and index.by_gene(subject.gene, subject.drug):
                result.unnamed_alleles.append(subject)
            else:
                result.withheld.append(
                    (subject, f"{subject}: no regulator in this snapshot labels this pair")
                )
            continue
        result.compared.append(subject)
        result.tier_subjects[subject.tier] += 1
        result.unstated_labels.update(
            call.row.label_id for call in calls if not call.stated
        )
        verdict = classify_labels(action, calls)
        result.verdicts[subject] = verdict
        result.concordance_arms[verdict.concordance] = (
            result.concordance_arms.get(verdict.concordance, 0) + 1
        )
        result.position_arms[verdict.position] = result.position_arms.get(verdict.position, 0) + 1
        if verdict.concordance == "discordant":
            result.findings.append(LabelFinding("regulators_disagree", subject, calls))
        if verdict.position == "opposed":
            result.findings.append(
                LabelFinding("recommendation_without_label_pgx", subject, calls)
            )

    for finding in result.findings:
        logger.warning("Regulator-label difference — %s", finding)
    for _subject, note in result.withheld:
        logger.info("Drug labels not compared — %s", note)
    if result.unnamed_alleles:
        note = (
            f"{len(result.unnamed_alleles)} authored allele(s) are named by no label in this "
            f"snapshot, so they were answered at the gene tier only: "
            + examples([str(subject) for subject in result.unnamed_alleles])
        )
        result.warnings.append(note)
        logger.info("%s", note)

    return _attest(result, spec_dir, write=write)


def arm_summary(result: DrugLabelResult) -> str:
    """Which verdict arms this run reached, how many subjects each holds, and what each one means.

    **This is what the two reason maps are for.** A verdict function with five arms owes a reason
    function with five arms (`@answered-is-not-absent`), and a map that only a test reads is a map
    nothing speaks: the tokens `single`, `unstated` and `unplaced` reach a reader with no way to tell
    what they claim. Aggregated by arm rather than listed per subject, so the sentence count is
    bounded by the vocabularies and not by the module's size.

    **The two axes are named, not flat-joined.** They answer different questions — *do the labels agree
    with each other* and *where does the module sit relative to them* — and a reader given
    `8 discordant; 9 unplaced` cannot tell which is which. The members happen to be disjoint today,
    so a flat list is unambiguous by accident; a vocabulary gaining a member the other one already has
    would make it silently wrong, and that is the shape this tree keeps closing rather than relying on.
    """
    axes = (
        ("concordance", result.concordance_arms, _CONCORDANCE_SENTENCES),
        ("position", result.position_arms, _POSITION_SENTENCES),
    )
    return "; ".join(
        f"{axis}: "
        + ", ".join(f"{count} {arm} ({sentences[arm]})" for arm, count in sorted(arms.items()))
        for axis, arms, sentences in axes
        if arms
    )


def verification_record(result: DrugLabelResult) -> VerificationRecord:
    """The `regulator_label_agreement` record: what was compared, at which tier, or why nothing was.

    `subjects` is **claims a label reached** and `findings` is **subjects in disagreement**, never a
    count of sentences: one subject can differ at both tiers at once, and `VerificationRecord` refuses
    more findings than subjects for exactly that reason. The sentences travel in `detail`, aggregated,
    and every one of them is in the log.
    """
    if result.not_checked is not None:
        return skipped(
            "regulator_label_agreement",
            result.not_checked,
            detail=result.warnings[-1] if result.warnings else None,
            source=SOURCE_NAME,
        )
    if not result.compared:
        # **`ran` with `subjects=0`, not a skip.** The check did run — a snapshot was read and every
        # authored claim was put to it — and `nothing_to_check` is defined as "the module carries no
        # row this check applies to", which is false about a module that states claims no agency has
        # labelled.
        return ran(
            "regulator_label_agreement",
            subjects=0,
            findings=0,
            source=SOURCE_NAME,
            release=result.dataset,
            detail=(
                # `examples()`, like every other path on this function: a panel module stating a
                # hundred unlabelled pairs must not write a hundred sentences into a hashed record.
                examples([note for _subject, note in result.withheld])
                or "no authored claim could be matched to a label"
            ),
        )
    tiers = ", ".join(f"{count} at the {tier} tier" for tier, count in result.tier_subjects.items())
    detail = (
        f"compared {len(result.compared)} gene/allele/drug claim(s) against "
        f"{len(result.regulators)} regulator(s) in {SOURCE_NAME}'s drug labels"
        f"{f' ({result.dataset})' if result.dataset else ''} — {tiers}"
    )
    detail += ". " + arm_summary(result)
    if result.unstated_labels:
        detail += (
            f". {len(result.unstated_labels)} label(s) reached state no testing level and are "
            f"counted as unknown rather than as {NO_CLINICAL_PGX!r}"
        )
    if result.unnamed_alleles:
        detail += (
            f". {len(result.unnamed_alleles)} authored allele(s) are named by no label and were "
            f"answered at the gene tier only"
        )
    if result.findings:
        detail += ". " + examples([str(finding) for finding in result.findings])
    if result.withheld:
        # The claims that were NOT compared, in the record and not only in the log: a coverage figure
        # whose denominator lives in stderr is the defect this tier keeps closing.
        detail += f". {len(result.withheld)} claim(s) withheld — " + examples(
            [note for _subject, note in result.withheld]
        )
    return ran(
        "regulator_label_agreement",
        subjects=len(result.compared),
        findings=len(result.contested),
        source=SOURCE_NAME,
        release=result.dataset,
        detail=detail,
    )


def _attest(result: DrugLabelResult, spec_dir: Path, *, write: bool) -> DrugLabelResult:
    """Record what this check put into `verification.json`, on every path that put one.

    Called on **every** return path that got past the applicability test, skips included: a pass that
    records its findings and stays silent about not having run leaves the manifest unable to tell the
    two apart, which is the defect RM45 exists to close.
    """
    if write:
        record_verification([verification_record(result)], spec_dir, error=DrugLabelError)
    return result
