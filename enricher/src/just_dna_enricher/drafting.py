"""The shared drafting scaffold: what every `*_draft.py` provider does the same way (RM228).

Drafting grew bottom-up, one provider at a time, and seven modules ended up reimplementing the same
four decisions. The tell is that the two implementations which *did* derive their skip rule derived
it differently, and the better-looking one derived it from an **incomplete** oracle (see
`identity_refused_by_model`). This module is the mechanism those seven were each approximating.

**The split this module exists to enforce.** A provider's skip rule is two different rules that were
being written as one hand-kept list:

1. **The model's requirement** — what `VariantRow` (or whichever row model) will accept. Derivable,
   identical for every provider, and it must never be restated: `pgx_draft` once restated "no rsID
   *and* no position" where `HaplotypeRow` wants rsID **or** chrom+start, and `draft --gene CYP2C9`
   died on an unhandled pydantic error.
2. **The provider's own source precondition** — a true fact about *that* snapshot, such as ClinPGx
   carrying no coordinate. Legitimate, provider-specific, and it needs a stated reason.

Mashed into one list nobody can tell them apart, which is how `mitomap_draft` came to gate *identity*
on `clin_sig` — a column that is not an identity requirement at all — without anyone noticing. A
`SourcePrecondition` carries its reason as a field, so the two halves can never merge again.

**What is deliberately not here.** `DRAFT_PROJECTIONS` in `provenance` stays where it is and is now
*derived* from this registry rather than restated beside it — it answers a narrower question (which
sources cross-check a column they drafted) about a subset of these providers.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.draft import authoring_requirements

from just_dna_enricher.licensing import (
    SourceTerms,
    merge_sources_file,
    withdraw_stale_dataset,
)

#: Filled into an identity probe so that only the identity clause is under test. Every value is one
#: the model is known to accept, so a `ValidationError` from a probe can only be about identity.
IDENTITY_PROBE_FILLER: Mapping[str, Mapping[str, object]] = {
    "variants.csv": {"genotype": "A/A", "state": "risk", "conclusion": "identity probe"},
}


@dataclass(frozen=True)
class SourcePrecondition:
    """Cells this provider's *source* requires, beyond whatever the model requires.

    `reason` is not documentation — it is the field that makes the precondition auditable. A
    condition with no reason is indistinguishable from a misread of the model, which is exactly the
    state `mitomap_draft`'s `clin_sig` clause was in.
    """

    fields: tuple[str, ...]
    reason: str

    def missing(self, cells: Mapping[str, object]) -> list[str]:
        return [name for name in self.fields if not str(cells.get(name) or "").strip()]


@dataclass(frozen=True)
class DraftProvider:
    """One drafting provider, and everything the scaffold needs to treat it uniformly.

    `identity` is **per provider and not per table**, deliberately. `append_partial_rows` builds its
    covered-set from a single `match_on` tuple for the whole batch, so handing two providers that
    write the same table one shared tuple would make the second one's rows stop matching on lap 2 and
    be re-added every run (`@match-on-is-per-batch`). MITOMAP's differs from CIViC's because MT
    variants carry no rsIDs, which is a fact about the source and so is recorded as one.
    """

    name: str
    module: str
    table: str
    #: What `append_partial_rows` matches a row on when deciding `added` vs `already_present`.
    match_on: tuple[str, ...]
    #: `projection` — this provider later cross-checks a column it drafted, so it owes a
    #: `DraftProjection`. `judgement` — it drafts an interpretation rather than a copy of a source
    #: column, and there is nothing to re-read.
    kind: str
    precondition: SourcePrecondition | None = None
    #: The columns a `projection` provider re-reads. Empty for a `judgement`.
    checked: tuple[str, ...] = ()
    #: The cells the cross-check treats as this row's identity. Defaults to `match_on` and is
    #: **separate from it on purpose** — `pubmind` matches on all five identity columns so a
    #: coordinate it and ClinVar both name is one row, but never *writes* `rsid`, so including it
    #: would move the digest the moment an author added an rs-number to a row nobody had touched.
    #: A provider that overrides this owes `projection_identity_reason`.
    projection_identity: tuple[str, ...] | None = None
    projection_identity_reason: str = ""
    #: An identity reason a provider withholds on, folded here rather than inlined per module.
    withheld_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in {"projection", "judgement"}:
            raise ValueError(f"{self.name}: kind must be projection or judgement, got {self.kind!r}")
        if self.kind == "judgement" and self.checked:
            raise ValueError(f"{self.name}: a judgement provider has nothing to re-read")
        if self.kind == "projection" and not self.checked:
            raise ValueError(f"{self.name}: a projection provider must name the columns it re-reads")
        if self.projection_identity is not None and not self.projection_identity_reason:
            raise ValueError(
                f"{self.name}: a projection identity that differs from match_on needs its reason, "
                "or the difference reads as an oversight (RM228)"
            )

    @property
    def identity(self) -> tuple[str, ...]:
        """The cross-check's identity — `match_on` unless the provider states otherwise."""
        return self.projection_identity if self.projection_identity is not None else self.match_on


def identity_refused_by_model(model: type, cells: Mapping[str, object], table: str) -> str | None:
    """`None` when `model` accepts these identity cells, else the model's own complaint.

    **Constructing the model is the oracle, and `authoring_requirements` is not.** That was measured
    rather than assumed: `authoring_requirements("variants.csv")` answers
    `any_of: [['rsid'], ['chrom','start']]`, a grammar that cannot express `VariantRow`'s third
    clause — *`ref`/`alts` require `chrom` and `start`*. So a guard built on it accepts
    `{"rsid": "rs1", "alts": "G"}`, which the model refuses and a compile would refuse, and the
    partial coordinate rides through (`@identity-whole-or-none`). One provider had exactly that
    shape. `authoring_requirements` still answers the *human-readable* question below; it is not the
    verdict.

    **No message parsing.** Every non-identity field is pre-filled from `IDENTITY_PROBE_FILLER` with
    values the model is known to accept, so any `ValidationError` reaching here **is** an identity
    refusal and needs no inspection. The previous implementation branched on
    `"identifier" in message or "positional" in message or "chrom" in message` — pydantic's rendered
    text as an API, which moves on a dependency bump with no warning.
    """
    probe = {**IDENTITY_PROBE_FILLER.get(table, {}), **{k: v for k, v in cells.items() if v is not None}}
    try:
        model(**probe)
    except Exception as exc:
        message = str(exc)
        return message.split("\n")[1].strip() if "\n" in message else message
    return None


def missing_required(table: str, cells: Mapping[str, object], stubbed: Sequence[str] = ()) -> list[str]:
    """The required cells this row does not carry, named for a human.

    Reported, never used as the verdict — `identity_refused_by_model` is the verdict. This exists so
    a warning can say *which* cells are absent, which the model's own message does not always spell.
    """
    requirements = authoring_requirements(table)
    stubs = set(stubbed)

    def stated(name: str) -> bool:
        return str(cells.get(name) or "").strip() != ""

    missing = [n for n in requirements["always"] if n not in stubs and not stated(n)]
    groups = [g for g in requirements["any_of"] if not any(n in stubs for n in g)]
    if groups and not any(all(stated(n) for n in group) for group in groups):
        missing.append(" or ".join("+".join(group) for group in groups))
    return missing


def skip_reason(provider: DraftProvider, model: type, cells: Mapping[str, object]) -> str | None:
    """Why this row is skipped, or `None` to draft it — the model's rule and the source's, in order.

    The model is asked **first** so that a row failing both is reported as the identity problem it
    is, rather than as whatever the provider additionally wanted.
    """
    refused = identity_refused_by_model(model, cells, provider.table)
    if refused is not None:
        return refused
    if provider.precondition is not None:
        absent = provider.precondition.missing(cells)
        if absent:
            return f"{provider.name} needs {', '.join(absent)}: {provider.precondition.reason}"
    return None


#: Every drafting provider, and the single place each of these facts is written down.
#:
#: `provenance.DRAFT_PROJECTIONS` is **derived** from the `projection` members below rather than
#: restated beside them, and each drafter reads its `match_on` from here rather than keeping a
#: private `_MATCH_ON` — those were two copies of one fact, and the registry's own comment already
#: pointed at `clinvar_draft._MATCH_ON` by name.
DRAFT_PROVIDERS: dict[str, DraftProvider] = {
    "clinvar": DraftProvider(
        name="clinvar",
        module="clinvar_draft",
        table="variants.csv",
        match_on=("rsid", "chrom", "start", "ref", "alts"),
        kind="projection",
        checked=("clin_sig",),
        precondition=SourcePrecondition(
            fields=("ref", "alts"),
            reason=(
                "a lone `alts` on a position-only row makes `derive_variant_key` mint a VRS "
                "`ga4gh:VA.…` id instead of `chrom:start:ref`, so a partial coordinate is a different "
                "identity rather than a rougher one (S41)"
            ),
        ),
    ),
    "pubmind": DraftProvider(
        name="pubmind",
        module="pubmind_draft",
        table="variants.csv",
        match_on=("rsid", "chrom", "start", "ref", "alts"),
        kind="projection",
        checked=("clin_sig",),
        projection_identity=("chrom", "start", "ref", "alts"),
        projection_identity_reason=(
            "the snapshot has no rsID column and most of its rows carry no rs-number, so the "
            "projection is the coordinate this provider actually establishes; including `rsid` would "
            "move the digest when an author added an rs-number to an otherwise untouched row"
        ),
    ),
    "clinpgx": DraftProvider(
        name="clinpgx",
        module="clinpgx_draft",
        table="pharm_variants.csv",
        match_on=(
            "rsid",
            "chrom",
            "start",
            "ref",
            "drug",
            "genotype",
            "phenotype_category",
            "annotation_id",
        ),
        kind="projection",
        checked=("evidence_level",),
        precondition=SourcePrecondition(
            fields=("rsid",),
            reason="the ClinPGx snapshot carries no coordinate, so an rsID is the only identity it can offer",
        ),
    ),
    "cpic": DraftProvider(
        name="cpic",
        module="pgx_draft",
        table="allele_function.csv",
        match_on=("gene", "allele"),
        kind="projection",
        checked=("function_status",),
    ),
    "civic": DraftProvider(
        name="civic",
        module="civic_draft",
        table="variants.csv",
        match_on=("rsid", "chrom", "start", "ref", "alts"),
        kind="judgement",
    ),
    "mitomap": DraftProvider(
        name="mitomap",
        module="mitomap_draft",
        table="variants.csv",
        match_on=("chrom", "start", "ref", "alts"),
        kind="judgement",
        precondition=SourcePrecondition(
            fields=("chrom", "start", "ref", "alts"),
            reason=(
                "MITOMAP publishes MT coordinates and no rsIDs, so every row it drafts is identified "
                "by the full coordinate; `match_on` omits `rsid` for the same reason"
            ),
        ),
    ),
    "strchive": DraftProvider(
        name="strchive",
        module="strchive_draft",
        table="repeat_alleles.csv",
        match_on=("gene", "repeat_unit"),
        kind="judgement",
    ),
}


def record_draft_provenance(
    *,
    provider: DraftProvider,
    terms: SourceTerms,
    spec_dir: Path,
    dataset: str | None,
    covered: bool,
    drafted: bool,
    declared_use: str | None,
    error: type[Exception],
    layer: str = "annotation",
) -> list[str]:
    """Write this run's `SourceRow` if it covered anything, and withdraw a stale release label.

    **One function because they are one decision made twice.** Three providers wrote the licence row
    themselves; two of those never called `withdraw_stale_dataset` at all, so a CPIC or ClinPGx
    re-curation left a row naming the older release with nothing able to notice (8.10 #5). Splitting
    them is what let one half be forgotten, so the scaffold does not offer the halves separately.

    `covered` is *what this run covered* — at least one row in the module's table because of this
    provider, added now or recognised as `already_present`. **A pass that contributes nothing writes
    no row** (`@write-the-sourcerow`): a `--gene` filter matching nothing leaves the module untouched,
    and a licence row saying "this module uses X" would be a claim about a module that does not. That
    is RM222, and it was written wrong here once already.

    `drafted` gates the withdrawal separately and narrowly: a re-draft that added no row changed
    nothing to be honest about, so there is no stale label to withdraw.

    Widening a module from a **newer** snapshot leaves the row naming the older release, because the
    merge is never-clobber — right for a curator's hand-written terms and a false claim for
    `dataset`. The stale label is **withdrawn, never re-labelled**: a module carrying rows from two
    releases has no honest single label, and unknown is withheld.

    Returns the warnings to append, rather than logging, so a caller keeps one reporting path.
    """
    if not covered:
        return []

    merge_sources_file(
        [terms.row(layer, declared_use=declared_use, dataset=dataset)],
        spec_dir,
        error=error,
    )
    if not drafted:
        return []

    superseded = withdraw_stale_dataset(spec_dir, terms.source, layer, dataset, error=error)
    if superseded is None:
        return []
    return [
        f"the licence row recorded {superseded} and this run drafted from "
        f"{dataset or 'an unlabelled snapshot'}, so the release label was withdrawn rather than "
        f"re-labelled: one column cannot name two releases."
    ]
