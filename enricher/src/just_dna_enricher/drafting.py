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

import csv
import hashlib
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from just_dna_compiler.compiler import load_csv_rows
from just_dna_compiler.draft import authoring_requirements
from just_dna_format.sources import SourceRow

from just_dna_enricher.licensing import (
    record_source_terms,
    require_sources_file,
    sources_path,
    withdraw_stale_dataset,
    write_sources_csv,
)
from just_dna_enricher.provenance import DraftProjection

logger = logging.getLogger(__name__)

#: Field separator inside one projected row, and row separator between them. Control characters, so
#: no cell value can contain one and forge a row boundary.
_UNIT = "\x1f"
_RECORD = "\x1e"


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
            fields=("chrom", "start", "ref", "alts", "clin_sig"),
            reason=(
                "MITOMAP publishes MT coordinates and no rsIDs, so every row it drafts is identified "
                "by the full coordinate and `match_on` omits `rsid` for the same reason. `clin_sig` "
                "is here because a `rated_miss` carries one by construction — it is a fact about this "
                "source's row shape, not an identity requirement, and the guard exists so a malformed "
                "snapshot earns a named refusal rather than a raw ValidationError about a column the "
                "author never wrote (`@specific-rejection`). It is unreachable from a well-formed "
                "snapshot, which is why it is declared rather than removed"
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


def licence_commit(
    *,
    sources: Sequence[str],
    spec_dir: Path,
    dataset: str | None,
    declared_use: str | None,
    error: type[Exception],
    layer: str = "annotation",
    extra_datasets: Mapping[str, str] | None = None,
    license_texts: Mapping[str, str] | None = None,
) -> Callable[[], None]:
    """The licence merge as a callable, for `draft.append_*`'s `before_commit` (RM232).

    The *merge half* of `record_draft_provenance`, and nothing else — no stale-label withdrawal, no
    projection restamp. Those two need `drafted` and the provider's `kind`, both of which are answers
    about the run as a whole rather than about one table, so they stay where they were, at the tail.

    **Why it is a factory and not a second call site.** A drafter appends its tables through the
    compiler's writer, which renames each one into place on its own; the licence row was recorded
    afterwards, so a refused merge — a scaffold's `<<REPLACE>>` placeholder is enough — left drafted
    rows in the author's tables with no licence record and the compile gate, which reads
    `sources.csv` and nothing else, nothing to refuse on. Handing this closure to every append binds
    the row to the commit of each table it licenses. One body rather than a copy per drafter, because
    a copy per drafter is what RM228 existed to remove.

    Never-clobber, so calling it once per table records one row.

    **The pre-flight is here rather than in each drafter** (S98, RM231): building the closure reads
    the licence table through `require_sources_file`, so a `licensing.csv` that does not load — a
    scaffold's unreplaced `<<REPLACE>>` row is the case S98 was filed on — refuses before the first
    append instead of after it. One place, so a new drafter inherits it rather than remembering it.

    **This makes a dry run refuse where it used to report, and that is intended.** A drafter builds
    the closure unconditionally, so `--dry-run` against a module with an unreadable licence table now
    raises instead of printing what it would have written. A dry run exists to say what the real run
    will do, and a dry run that passes while the real one refuses says the opposite; RM231 made the
    same trade at the same seam.
    """
    require_sources_file(spec_dir, error=error)
    consulted = list(sources)
    datasets = dict(extra_datasets or {})
    if dataset and consulted:
        datasets.setdefault(consulted[0], dataset)

    def commit() -> None:
        if not consulted:
            return
        record_source_terms(
            consulted,
            layer,
            spec_dir,
            error=error,
            declared_use=declared_use or "unstated",
            datasets=datasets or None,
            license_texts=license_texts,
        )

    return commit


def record_draft_provenance(
    *,
    provider: DraftProvider,
    sources: Sequence[str],
    spec_dir: Path,
    dataset: str | None,
    covered: bool,
    drafted: bool,
    declared_use: str | None,
    error: type[Exception],
    layer: str = "annotation",
    extra_datasets: Mapping[str, str] | None = None,
    license_texts: Mapping[str, str] | None = None,
    stale_warning: Callable[[str, str | None], str] | None = None,
) -> list[str]:
    """Write this run's `SourceRow`s if it covered anything, and withdraw a stale release label.

    **One function because they are one decision made twice.** Three providers wrote the licence row
    themselves; two of those never called `withdraw_stale_dataset` at all, so a CPIC or ClinPGx
    re-curation left a row naming the older release with nothing able to notice (8.10 #5). Splitting
    them is what let one half be forgotten, so the scaffold does not offer the halves separately.

    **`sources` is plural because a draft really can consult several.** `civic_draft` records CIViC
    and, when it asked it, the ClinGen Allele Registry — so the singular shape would have forced that
    provider to keep writing its own rows and stay outside the scaffold, which is how the patchwork
    started. This delegates to `record_source_terms`, the general primitive that already takes a
    `datasets` map (RM222), rather than reaching past it to `merge_sources_file`.

    `covered` is *what this run covered* — at least one row in the module's table because of this
    provider, added now or recognised as `already_present`. **A pass that contributes nothing writes
    no row** (`@write-the-sourcerow`): a `--gene` filter matching nothing leaves the module untouched,
    and a licence row saying "this module uses X" would be a claim about a module that does not. That
    is RM222, and it was written wrong here once already.

    `drafted` gates the withdrawal separately and narrowly: a re-draft that added no row changed
    nothing to be honest about, so there is no stale label to withdraw. The withdrawal targets the
    **first** source only — the provider's own — because a secondary registry consulted along the way
    does not own this module's release label.

    Widening a module from a **newer** snapshot leaves the row naming the older release, because the
    merge is never-clobber — right for a curator's hand-written terms and a false claim for
    `dataset`. The stale label is **withdrawn, never re-labelled**: a module carrying rows from two
    releases has no honest single label, and unknown is withheld.

    Returns the warnings to append, rather than logging, so a caller keeps one reporting path.
    """
    if not covered or not sources:
        return []

    # The same body the drafters hand to `before_commit`, called here for the run that covered
    # something and wrote nothing — every row `already_present`, so no append reached a writer and no
    # callback fired. That run still owes the row (RM232).
    licence_commit(
        sources=sources,
        spec_dir=spec_dir,
        dataset=dataset,
        declared_use=declared_use,
        error=error,
        layer=layer,
        extra_datasets=extra_datasets,
        license_texts=license_texts,
    )()
    # A `projection` provider later re-reads a column it wrote, so its digest has to be restamped
    # explicitly — `record_source_terms` is never-clobber, and a second draft's digest would
    # otherwise be silently dropped. Unconditional, because a run that appended nothing leaves the
    # projection unchanged and this is then a no-op. Driven by `kind` rather than by each provider
    # remembering, which is the whole point of the registry.
    if provider.kind == "projection":
        stamp_draft_digest(spec_dir, sources[0], layer, error=error)

    if not drafted:
        return []

    superseded = withdraw_stale_dataset(spec_dir, sources[0], layer, dataset, error=error)
    if superseded is None:
        return []
    # **The wording is the provider's, because a published warning is an API** — two providers ship
    # two sentences for this finding and unifying them would change one of them
    # (`@warning-text-is-api`). What the scaffold owns is that the withdrawal happens at all.
    if stale_warning is not None:
        return [stale_warning(superseded, dataset)]
    return [
        f"the licence row recorded {superseded} and this run drafted from "
        f"{dataset or 'an unlabelled snapshot'}, so the release label was withdrawn rather than "
        f"re-labelled: one column cannot name two releases."
    ]


#: The subset of providers that cross-check a column they drafted, as `provenance` wants it.
#:
#: **Derived, not restated** (RM228). This map used to be hand-kept in `provenance` and its own
#: comment pointed at `clinvar_draft._MATCH_ON` by name — two copies of one fact, one of them private
#: to a module. `identity` reads the provider's `identity` property, which is `match_on` unless the
#: provider states a reason to differ; `pubmind` does, and that reason is now a field.
#:
#: It lives here rather than in `provenance` so the dependency runs one way: `drafting` owns the
#: registry and calls `provenance`'s digest machinery, and `provenance` imports nothing back.
DRAFT_PROJECTIONS: dict[str, DraftProjection] = {
    name: DraftProjection(table=p.table, identity=p.identity, checked=p.checked)
    for name, p in DRAFT_PROVIDERS.items()
    if p.kind == "projection"
}


def draft_digest(spec_dir: Path, source: str) -> str | None:
    """Hash `source`'s drafted table as it stands on disk, or `None` when there is nothing to hash.

    `None` for a source that drafts nothing, for a table this module does not carry, and for one that
    carries no rows — all three are "no copy has been established", which is the state that leaves a
    check running.
    """
    projection = DRAFT_PROJECTIONS.get(source)
    if projection is None:
        return None
    path = Path(spec_dir) / projection.table
    if not path.exists() or path.stat().st_size == 0:
        return None

    columns = (*projection.identity, *projection.checked)
    with open(path, encoding="utf-8", newline="") as handle:
        # `(cell or "").strip()` for the same reason the compiler's loader normalizes: a trailing
        # space an editor left behind is not an edit to the claim, and treating it as one would
        # re-enable the full check for nothing.
        projected = sorted(
            _UNIT.join((row.get(name) or "").strip() for name in columns) for row in csv.DictReader(handle)
        )
    if not projected:
        return None
    payload = _RECORD.join(projected)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stamp_draft_digest(spec_dir: Path, source: str, layer: str, *, error: type[Exception]) -> str | None:
    """Record the current digest onto the `(source, layer)` licence row. Returns what it wrote.

    **This exists because `merge_sources_file` is never-clobber**, which is right for terms a curator
    may have hand-written and wrong for a machine-stamped cell that must track the table. Without an
    explicit restamp a second draft's digest is silently dropped, the recorded one stays behind
    naming a table that has since grown, and the skip dies permanently — in the safe direction, and
    invisibly, which is what would make it a trap rather than a bug. `withdraw_stale_dataset` is the
    same lesson on the neighbouring column, and it is the precedent for overwriting here at all.

    Unlike `dataset`, this one **re-labels rather than withdraws**, and the difference is real: a
    release label cannot name two releases, so a module spanning two has no honest value and unknown
    is withheld. A digest has no such problem — it describes the table as it now stands, whatever
    mixture of releases and hands produced it, so recomputing is always the honest answer.

    Called unconditionally by a provider that wrote anything: a run that appended no row leaves the
    projection unchanged, so the restamp is a no-op rather than a special case to guard.
    """
    digest = draft_digest(spec_dir, source)
    path = sources_path(spec_dir, error=error)
    if not path.exists():
        return None
    rows, errors, _ = load_csv_rows(path, SourceRow, path.name)
    if errors:
        raise error(f"existing {path.name} is invalid: {errors[0]}")
    recorded = next((r for r in rows if r.source == source and r.layer == layer), None)
    if recorded is None or recorded.draft_digest == digest:
        return None
    recorded.draft_digest = digest
    write_sources_csv(rows, path)
    return digest


def drafted_unchanged(spec_dir: Path, source: str, sources: list[SourceRow]) -> bool | None:
    """Has every checked cell stayed as the drafter wrote it? Tri-state.

    * `None` — nothing recorded a digest for this source, so nothing was ever established. A module
      nobody drafted, one drafted before this shipped, or a table that has since been deleted.
    * `False` — a checked value has moved since the draft. The row stopped being a copy, whoever
      moved it, and the cross-check has something real to compare.
    * `True` — the projection still hashes to what the drafter recorded.

    `True` alone is **not** grounds to skip a check. The digest describes this module's table, not
    the source's release, so it is silent about currency: a matching digest against a *newer*
    snapshot is a genuine comparison, not a tautology. The caller conjoins this with the release
    check (`clinical.tautology_reason`'s existing rule) and skips only when both hold.
    """
    recorded = [
        row.draft_digest for row in sources if row.source == source and (row.draft_digest or "").strip()
    ]
    if not recorded:
        return None
    current = draft_digest(spec_dir, source)
    if current is None:
        # A digest was recorded and the table is now unreadable or gone. Not a match, and deliberately
        # not `None` either: something was established and no longer holds, which is exactly the case
        # a check should be run over rather than waved through.
        return False
    return all(value == current for value in recorded)
