"""The model-organism evidence table, `model_organisms.csv` (0.8, RM335).

One row is one model-organism lifespan finding about a **human gene**: which orthologue was altered, in
which species, by which intervention, under which sex and diet, what happened to lifespan, and whether
the direction agrees with the human allele's. It is the table for evidence that has nowhere else to go:

* a `studies.csv` row naming the rsID claims a mouse study was about the human variant;
* a `studies.csv` row naming no variant attaches to the whole module, since `StudyRow` has no `gene`;
* a meta-table member names a variant, a genotype row, a diplotype or a `(gene, allele)` pair, never a
  bare gene, and a mouse genotype such as `Igf1r+/-` is not a human allele.

**Annotation only.** Nothing here reaches an effect column, a weight or a tier: a consumer reads the rows
beside the module's findings and never scores a genome from them. That is why the table is keyed on the
gene itself and carries no variant, genotype or allele column, and why it is not a lead table — a module
whose only rows are model-organism evidence has nothing a genome is matched against.
"""

from typing import ClassVar

from pydantic import Field, field_validator

from just_dna_format.base import AuthoredModel, since, vocabulary
from just_dna_format.spec import CitationPair, validate_pmid_cell
from just_dna_format.vocab import check_vocab

#: `concordance`: does the model's lifespan effect point the same way as the human allele's? Closed, three
#: members. **Empty is unstated** — the curator could not tell, or did not say — and it is the answer for
#: most of longevitymap v2's rows (55 of 77 were recorded as "unclear"). No `unclear` member: an unknown is
#: an absent cell in this format, never a fourth value (the house three-valued rule).
VALID_MODEL_ORGANISM_CONCORDANCE: frozenset[str] = frozenset({"concordant", "discordant", "nonmonotone"})

_CONCORDANCE_NOTES: dict[str, str] = {
    "concordant": "the model's lifespan effect points the way the human allele's effect does",
    "discordant": "the model's lifespan effect points the other way",
    "nonmonotone": "the direction depends on a condition the row names (dose, diet, sex, age)",
}


class ModelOrganismRow(CitationPair, AuthoredModel):
    """One row of `model_organisms.csv`: a model-organism lifespan finding about a human gene.

    The key is every column except the two that state the finding (`lifespan_effect`, `concordance`): one
    gene, orthologue, species, intervention, sex, diet and citation make one experiment, and the same
    experiment stated twice with two effects is a contradiction the compiler refuses like every other keyed
    table's duplicate. A male and a female cohort, or a chow and a high-fat one, are two rows.

    `pmid`/`doi` are **optional and draw no warning** when both are empty (PT2 §3 item 23): GenAge-style
    entries carry no paper, and the table never reaches a score. When a row does cite, the pair's rules
    apply as on every citing table (`CitationPair`, RM336).
    """

    _KEY_FIELDS: ClassVar[tuple[str, ...]] = (
        "gene",
        "orthologue",
        "species",
        "model_type",
        "sex",
        "diet",
        "pmid",
        "doi",
    )

    gene: str = Field(
        json_schema_extra=since("0.8.0"),
        description=(
            "The **human** gene symbol the evidence is about (HGNC), e.g. IGF1R — never the orthologue's. "
            "The row's subject and the first column of its key."
        ),
    )
    orthologue: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "The model organism's gene, as that organism's nomenclature writes it (e.g. Igf1r in mouse, "
            "daf-2 in worm). A symbol or the organism database's id; kept verbatim."
        ),
    )
    species: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description="The model organism, by its binomial name, e.g. Mus musculus, Caenorhabditis elegans.",
    )
    model_type: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "The intervention that made the model, as the paper names it: heterozygous knockout, "
            "knock-in Pro12Ala, overexpression, RNAi."
        ),
    )
    sex: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "The sex of the animals the finding was measured in, free text as the paper states it "
            "(female, male, both, hermaphrodite). Descriptive: it is not `meta.csv`'s `sex`, which is a "
            "condition a consumer matches against a person's karyotype."
        ),
    )
    diet: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description="The diet the cohort was kept on, when the finding depends on it, e.g. high-fat.",
    )
    lifespan_effect: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "What happened to lifespan, in the paper's terms and with its number where it gives one, "
            "e.g. +33% (female). Prose: it is never read as a weight or an effect size."
        ),
    )
    concordance: str | None = Field(
        default=None,
        json_schema_extra={
            **vocabulary(
                "model_organism_concordance", VALID_MODEL_ORGANISM_CONCORDANCE, notes=_CONCORDANCE_NOTES
            ),
            **since("0.8.0"),
        },
        description=(
            "Whether the model's lifespan effect agrees in direction with the human allele's "
            "(concordant|discordant|nonmonotone). Empty means unstated: the curator could not tell."
        ),
    )
    pmid: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "PubMed id of the paper reporting the finding. Optional, and an uncited row draws no warning. "
            "`NONE` cites by `doi` alone (RM336). Free-form like `StudyRow.pmid`."
        ),
    )
    doi: str | None = Field(
        default=None,
        json_schema_extra=since("0.8.0"),
        description=(
            "Digital Object Identifier of the work THIS row cites, kept verbatim (bare or as a doi.org "
            "URL). Optional beside a PubMed id; **mandatory when `pmid` is `NONE`**, the sentinel for "
            "a work PubMed does not index (a preprint, a book, a dataset), RM336. Same rule as "
            "`StudyRow.doi`."
        ),
    )

    @field_validator("concordance")
    @classmethod
    def _validate_concordance(cls, v: str | None) -> str | None:
        return check_vocab(v, VALID_MODEL_ORGANISM_CONCORDANCE, "concordance")

    @field_validator("pmid")
    @classmethod
    def _validate_pmid(cls, v: str | None) -> str | None:
        # The one grammar every citation pointer goes through, optional here (PT2 §3 item 23). The `doi`
        # cell and the pmid/doi pair (`NONE` makes `doi` mandatory) are `CitationPair`'s.
        return validate_pmid_cell(v, "pmid", required=False)
