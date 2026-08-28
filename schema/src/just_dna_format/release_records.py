"""
What a release changed about **compiled output** — the channel Principle 3 names (RM126).

The charter, as amended on 2026-08-21, lets a corrected derivation ship in any release but never
*silently*: each release declares its corrections, readable offline and without recompiling. Until
this module existed the charter named a surface that was not there.

**The question it answers, and the two it does not.** A consumer holding a stored artifact can
already ask *is the stored input still legal?* (`validate_spec` says `ok`) and *was this compiled by
a contract-incompatible compiler?* (compare versions; a patch is compatible). Neither is **would
recompiling this artifact produce different output than the stored one?** — and that question is not
hypothetical. All sixteen `reference_examples/` compiled under `0.6.1` and again under `0.6.6`, from
byte-identical spec inputs across an interval that is entirely patch releases, changed a published
manifest field on every single one; ten moved `artifact.digest`; none moved `content_signature`. Six
changed a published, *indexed* manifest field with **both** hashes byte-identical, which is exactly
the shape a digest comparison, a signature comparison and a `revalidate` all correctly report as *no
change*.

**This is a fact channel, never a verdict.** There is deliberately no `should_rebuild`: the same fact
costs a registry an immutable PATCH and a local cache a free rebuild, so the decision belongs to the
consumer and only the fact is ours. `needs_recompile` is named for the question, and it answers with
the per-axis breakdown plus the declared correction/addition split — the half no diff can compute,
because only the person who fixed the bug knows whether the stored value was *wrong* or merely
*absent*.

**Why this module and not `_ALL_MODELS`.** Every member of `reference._ALL_MODELS` describes module
content — a row an author writes or a compiler emits into a spec directory or an artifact. A release
record describes *this package*, so admitting it would make `authoring_reference()` — the drift-proof
description a consumer renders **instead of** a hand-kept spec dump — advertise a table nobody
authors. The compensating control is the pair of equality guards in
`schema/tests/test_release_records.py`, which walk the same registries the `_ALL_MODELS` guards walk;
and both vocabularies live in `vocab.py`, so `test_vocab_separator.py`'s discovery-by-inspection
covers them exactly as it covers every other closed set. Do not re-file the exclusion as an
oversight.

**Scope, stated because a silence would be read as a claim.** v1 measures **compiler-derived
outputs** — the manifest, the parquet schemas and the parquet bytes. Enricher-side outputs
(`resolution.csv` and the fact sidecars) are **unmeasured**, which is not the same claim as
unchanged.
"""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, field_validator

from just_dna_format.base import vocabulary
from just_dna_format.identity import parse_version
from just_dna_format.vocab import (
    VALID_RELEASE_CHANGE_KINDS,
    VALID_RELEASE_OUTPUT_AXES,
    check_vocab,
)

#: The axes a consumer acts on when deciding whether to recompile. `warnings` is the one member of
#: `VALID_RELEASE_OUTPUT_AXES` deliberately left out: `compilation.warnings` is a published manifest
#: field, and a release that rewords a message moves it on essentially every module in a catalogue.
#: Derived from the vocabulary by subtraction rather than restated, so a new axis joins the driving
#: set unless it is explicitly excluded — the safe default for a staleness signal.
NON_RECOMPILE_AXES: frozenset[str] = frozenset({"warnings"})
RECOMPILE_DRIVING_AXES: frozenset[str] = VALID_RELEASE_OUTPUT_AXES - NON_RECOMPILE_AXES

#: Manifest fields the sweep must never count as *a published field changed*, each with the reason.
#: Published here rather than kept inside the compiler's instrument, because a consumer reading a
#: record's `manifest_fields` needs to know what the set excludes before they can read it at all.
#:
#: `compiler_version` is the trap and it is not hypothetical: it moves on **every** release by
#: construction, so counting it would make every record fire on every module and rebuild, inside our
#: own instrument, precisely the false-positive class the interval shape exists to avoid.
EXCLUDED_MANIFEST_FIELDS: dict[str, str] = {
    "compilation.compiled_at": "a wall-clock timestamp; it moves on every recompile of anything",
    "compilation.compiled_by": "who ran the compile — an environment fact, not an output fact",
    "compilation.compiler_version": "moves on every release by construction; it IS the interval key",
    "compilation.warnings": "routed to the `warnings` axis, which is outside the recompile drivers",
    "content_signature": "routed to the `content_signature` axis",
    "artifact.digest": "routed to the `parquet_bytes` axis",
    "artifact.files": "routed to the `parquet_bytes` axis (per-file hashes and sizes)",
}


class DeclaredChange(BaseModel):
    """One thing a release changed about compiled output, and whether what we published was WRONG.

    This is the half of the record a measurement cannot produce. A differ sees `stats.genes` move
    from `[]` to `["CYP2C19"]` and `studies.parquet` gain a `curator` column, and the two look
    identical to it: a field changed. They are not the same fact. The first was **wrong** — the
    module always named that gene on 1,332 rows and the published value said otherwise, so every
    artifact holding it is serving a value we no longer stand behind. The second was merely
    **absent** — the column did not exist, and no earlier artifact could have carried it.

    A consumer routes those differently, and only this repo holds the knowledge that separates them.
    """

    model_config = ConfigDict(extra="forbid")

    axis: str = Field(
        json_schema_extra=vocabulary("release_output_axis", VALID_RELEASE_OUTPUT_AXES),
        description="Which axis this change lands on (VALID_RELEASE_OUTPUT_AXES).",
    )
    target: str = Field(
        description=(
            "What moved, spelled the way the axis spells it: a dotted manifest path "
            "(`stats.genes`), a parquet file or `file:column` for the schema axis, or the axis "
            "name itself where the movement has no finer target."
        ),
    )
    kind: str = Field(
        json_schema_extra=vocabulary("release_change_kind", VALID_RELEASE_CHANGE_KINDS),
        description=(
            "`correction` when the value we published was wrong, `addition` when it was absent. "
            "The distinction is declared, never measured."
        ),
    )
    detail: str = Field(description="The sentence a consumer reads: what moved, and why.")
    item: str | None = Field(
        default=None,
        description="The roadmap item behind it (`RM120`), when there is one.",
    )

    @field_validator("axis")
    @classmethod
    def _check_axis(cls, value: str) -> str:
        return check_vocab(value, VALID_RELEASE_OUTPUT_AXES, "axis")

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        return check_vocab(value, VALID_RELEASE_CHANGE_KINDS, "kind")


class ReleaseRecord(BaseModel):
    """What one release changed about compiled output, over the interval `(previous, version]`.

    **Keyed on an interval, not on a field, and that is load-bearing rather than incidental.** The
    question a consumer has is always *compiled under X, installed Y*, and the interval shape is what
    gives convergence for free: **the interval from a version to itself is empty**, so an automated
    sweep acting on this cannot mint a fresh PATCH every run, forever. A field-keyed table — or a
    "latest known defect" list — would fire for a version compiled by the exact compiler now
    installed and would not have the property. It also bounds a false positive to one wasted version
    number per module, ever, which is what makes acting on it unattended defensible at all.

    **`axes` is tri-state per axis and every member is present.** `True` moved, `False` measured and
    did not move, `None` **not measured on this interval** — which is not `False`. A release that
    adds an axis cannot retroactively measure the ones before it, and a record that quietly reported
    `False` there would be worse than no record, because a consumer would stop recompiling on the
    strength of a silence.

    **A release where nothing moved records a measured zero with its `evidence`, never silence.** An
    absent record and an all-`False` record answer different questions.
    """

    model_config = ConfigDict(extra="forbid")

    version: str = Field(description="The release this record describes — the interval's upper end.")
    previous: str = Field(
        description=(
            "The release it was measured against — the interval's *open* lower end. Chaining these "
            "links is what composes an arbitrary interval without storing O(releases²) rows."
        ),
    )
    axes: dict[str, bool | None] = Field(
        description=(
            "Every member of VALID_RELEASE_OUTPUT_AXES, tri-state: moved / did not move / not "
            "measured. `None` is never `False`."
        ),
    )
    manifest_fields: list[str] = Field(
        default_factory=list,
        description=(
            "The published manifest fields that moved, as dotted paths, sorted. The detail under "
            "the `manifest_fields` axis; EXCLUDED_MANIFEST_FIELDS never appear here."
        ),
    )
    declared: list[DeclaredChange] = Field(
        default_factory=list,
        description="The correction-versus-addition split — declared by the author, never measured.",
    )
    evidence: str = Field(
        description=(
            "How the measurement was taken: what was compiled, under which two releases, and any "
            "module that could not be measured. A record without this is a hand-kept map."
        ),
    )

    @field_validator("version", "previous")
    @classmethod
    def _check_semver(cls, value: str) -> str:
        parse_version(value)  # raises on anything but MAJOR.MINOR.PATCH
        return value

    @field_validator("axes")
    @classmethod
    def _check_axes_are_complete(cls, value: dict[str, bool | None]) -> dict[str, bool | None]:
        """An EQUALITY over the vocabulary, never a subset check.

        A record silent about an axis and a record saying `None` about it are the same claim, and
        making the silence illegal is what forces a new axis to be answered — with `None` if it
        cannot be measured — on every record rather than defaulting to whatever the reader assumes.
        """
        canonical = {check_vocab(name, VALID_RELEASE_OUTPUT_AXES, "axes"): moved
                     for name, moved in value.items()}
        if set(canonical) != set(VALID_RELEASE_OUTPUT_AXES):
            missing = sorted(VALID_RELEASE_OUTPUT_AXES - set(canonical))
            raise ValueError(f"axes must name every release output axis; missing: {missing}")
        return canonical


def release_version(stamp: str) -> str:
    """The bare `MAJOR.MINOR.PATCH` out of whatever a caller is holding.

    `manifest.compilation.compiler_version` reads `just-dna-compiler 0.6.1`, package name included,
    and that string is what a consumer has in their hand. Making them strip it before they can ask a
    question is the kind of unstated convention that ends up implemented three different ways in
    three different registries, so this accepts either spelling and returns the canonical one.

    Raises on anything else — `just-dna-compiler unknown` included. A malformed version is a caller
    bug, not an unknown *fact*: the tri-state in this module is about whether the table covers an
    interval, and quietly answering `unknown` here would hide a typo behind the same silence a real
    gap uses.
    """
    token = stamp.strip().rsplit(" ", 1)[-1]
    parse_version(token)
    return token


@dataclass(frozen=True)
class RecompileAnswer:
    """The facts about an interval. Not a verdict — see this module's docstring.

    `axes` is tri-state per axis under Kleene semantics: a single measured `True` beats any number of
    `None`s (something moved, whatever else is unknown), while a `False` survives only when *every*
    release in the interval was measured and none of them moved.
    """

    compiled_under: str
    current: str
    axes: dict[str, bool | None]
    manifest_fields: tuple[str, ...]
    """Fields that moved **inside** the asked interval. An overshooting link's are withheld here."""
    declared: tuple[DeclaredChange, ...]
    """Declarations attributable to the asked interval. An overshooting link's are withheld here."""
    covered: tuple[str, ...]
    """The releases whose records were folded in, newest first. Empty for a self-interval."""
    complete: bool
    """Whether the chain covered `(compiled_under, current]` exactly, with no gap and no overshoot."""
    span: tuple[str, str]
    """The interval the answer actually describes, which an overshooting link makes wider than asked."""
    out_of_span_manifest_fields: tuple[str, ...] = ()
    """Fields a link covering a WIDER span reports, which may have moved outside the asked one."""
    out_of_span_declared: tuple[DeclaredChange, ...] = ()
    """The same for declarations, and the reason both of these exist rather than being folded in.

    `_blunt_to_unknown` already refuses to narrow a `True` axis, so an overshooting link answers
    *cannot say* — and folding that link's `manifest_fields` and `declared` into the main tuples
    anyway would contradict the axis in the same object. A registry acting on `corrections` burns an
    immutable PATCH, and *this moved somewhere in a wider interval* is not a fact about the artifact
    in front of them. Withheld here rather than dropped: they are still the best evidence available,
    and a caller who wants them can read them knowing what they are."""

    @property
    def output_differs(self) -> bool | None:
        """Kleene OR over `RECOMPILE_DRIVING_AXES` — `warnings` is excluded by construction.

        `None` means *cannot say*, and a consumer must read it as such: the whole point of the axis
        being tri-state is that a silence is not a licence to stop recompiling.
        """
        values = [self.axes[axis] for axis in sorted(RECOMPILE_DRIVING_AXES)]
        if any(value is True for value in values):
            return True
        return None if any(value is None for value in values) else False

    @property
    def corrections(self) -> tuple[DeclaredChange, ...]:
        """The declared changes where what we published was **wrong**, not merely absent."""
        return tuple(change for change in self.declared if change.kind == "correction")

    @property
    def additions(self) -> tuple[DeclaredChange, ...]:
        return tuple(change for change in self.declared if change.kind == "addition")


def _unknown_axes() -> dict[str, bool | None]:
    return {axis: None for axis in VALID_RELEASE_OUTPUT_AXES}


def _kleene_or(left: bool | None, right: bool | None) -> bool | None:
    """`True` dominates, then `None`, then `False`. The house algebra, not withhold-on-any-unknown."""
    if left is True or right is True:
        return True
    if left is None or right is None:
        return None
    return False


def _blunt_to_unknown(axes: dict[str, bool | None]) -> dict[str, bool | None]:
    """A link that reaches BELOW the asked-about lower bound answers a wider question than was put.

    `False` survives the narrowing and `True` does not, and the asymmetry is sound rather than
    cautious: if nothing moved across the wider span then nothing moved inside it either, whereas
    something moving across the wider span says nothing about *where* — it may have moved entirely
    outside the interval the caller asked about.
    """
    return {axis: (False if moved is False else None) for axis, moved in axes.items()}


def needs_recompile(
    compiled_under: str,
    current: str,
    records: dict[str, ReleaseRecord] | None = None,
) -> RecompileAnswer:
    """What changed about compiled output between the release an artifact was compiled under and now.

    `compiled_under` is `manifest.compilation.compiler_version`; `current` is the release the caller
    is holding. **Both are explicit and neither is defaulted** — this module lives in the format
    tier, which cannot know which compiler is installed, and defaulting to its own version would
    answer with the wrong package's number.

    Composition is a **union over the releases in `(a, b]`**, walked along each record's `previous`
    link. Storage is therefore linear in releases rather than quadratic, and *moved-and-moved-back
    still counts as moved*, which is the right reading for staleness: a consumer asking whether their
    stored bytes match a recompile is not asking whether the difference is interesting.

    Three answers that are not the same and must not collapse into one another:

    * **the self-interval** — `compiled_under == current` — is **empty**, so every axis is `False`
      with `complete=True`, even for a version this table has never heard of. That is the
      convergence property S65 made a hard requirement, and it holds structurally rather than by a
      special case in a caller.
    * **an uncovered interval** answers `None` on every axis nothing measured. Never an empty result,
      never `False`.
    * **a backwards interval** — an artifact compiled under something *newer* than `current`, which
      happens whenever a consumer downgrades — is `None` throughout. The union is not symmetric: a
      correction declared forward is not a correction backward, and this table records what a release
      *did*, not what undoing it would do.
    """
    table = RELEASE_RECORDS if records is None else records
    compiled_under = release_version(compiled_under)
    current = release_version(current)
    low = parse_version(compiled_under)
    high = parse_version(current)

    if low == high:
        return RecompileAnswer(
            compiled_under=compiled_under,
            current=current,
            axes={axis: False for axis in VALID_RELEASE_OUTPUT_AXES},
            manifest_fields=(),
            declared=(),
            covered=(),
            complete=True,
            span=(compiled_under, current),
        )
    if low > high:
        return RecompileAnswer(
            compiled_under=compiled_under,
            current=current,
            axes=_unknown_axes(),
            manifest_fields=(),
            declared=(),
            covered=(),
            complete=False,
            span=(current, compiled_under),
        )

    axes: dict[str, bool | None] = {axis: False for axis in VALID_RELEASE_OUTPUT_AXES}
    fields: set[str] = set()
    outside_fields: set[str] = set()
    declared: list[DeclaredChange] = []
    outside_declared: list[DeclaredChange] = []
    covered: list[str] = []
    cursor = high
    complete = True
    reached = high
    # Walk down the `previous` chain. Each hop is one release's measurement; a missing hop is a gap
    # and folds in as all-unknown rather than being skipped, which is the difference between "we
    # measured nothing there" and "nothing happened there".
    while cursor > low:
        record = table.get(str(cursor))
        if record is None:
            axes = {axis: _kleene_or(axes[axis], None) for axis in axes}
            complete = False
            break
        step = parse_version(record.previous)
        if step >= cursor:
            raise ValueError(
                f"release record {record.version} points at {record.previous}, which is not below "
                "it — the chain would not terminate"
            )
        # A link reaching below the asked bound answers a wider question. Its axes are blunted, and
        # its detail goes to the out-of-span tuples for the same reason — reporting a correction
        # under `corrections` while the axis beside it says *cannot say* would be one object
        # contradicting itself, and `corrections` is the field a registry spends a version number on.
        overshoots = step < low
        contribution = _blunt_to_unknown(record.axes) if overshoots else record.axes
        axes = {axis: _kleene_or(axes[axis], contribution.get(axis)) for axis in axes}
        if overshoots:
            outside_fields.update(record.manifest_fields)
            outside_declared.extend(record.declared)
            complete = False
        else:
            if record.axes.get("manifest_fields") is not False:
                fields.update(record.manifest_fields)
            declared.extend(record.declared)
        covered.append(record.version)
        reached = step
        cursor = step

    return RecompileAnswer(
        compiled_under=compiled_under,
        current=current,
        axes=axes,
        manifest_fields=tuple(sorted(fields)),
        declared=tuple(declared),
        covered=tuple(covered),
        complete=complete,
        span=(str(min(reached, low)), current),
        out_of_span_manifest_fields=tuple(sorted(outside_fields)),
        out_of_span_declared=tuple(outside_declared),
    )


# ── The roster: which manifest fields a consumer can recompute for themselves (S65) ─────────────


@dataclass(frozen=True)
class RosterEntry:
    """One manifest field a consumer can recompute from the authored rows, and when they cannot.

    The roster is the half of RM126 that *shrinks* it. For a field that is a pure function of the
    authored rows, a consumer holding the stored spec can compute the **current** answer directly —
    no enrichment, no parquet, no network, and no need to consult the record table at all. What the
    interval table then has to cover is only what a consumer cannot recompute.
    """

    field: str
    """The dotted manifest path."""
    recompute: str
    """How, in terms of the compiler's public surface."""
    condition: str | None
    """`None` when the equality is unconditional; otherwise the case where it legitimately fails."""


#: The condition that makes the `stats` half of the roster conditional, and it is invisible from
#: outside without the counter that closes it. `validate_spec` computes `stats` over the **full** row
#: set; `compile_module` re-derives them over the survivors **only when the symbolic-allele drop
#: removed something**. So a recomputation from the authored rows is the *pre-drop* side, and
#: `manifest.stats` legitimately disagrees with it — permanently, under any compiler — for a module
#: that lost the sole row naming a gene.
#:
#: A roster claiming "pure function of the authored rows" without saying this would send a consumer
#: to spend version numbers on modules that are perfectly current. It is checkable rather than merely
#: stated because `compilation.dropped_rows` shipped on 2026-08-24: empty means the recomputation and
#: the manifest must agree, and non-empty means the manifest is the post-drop answer and the
#: disagreement is correct.
DROPPED_ROWS_CONDITION: str = (
    "holds only while `compilation.dropped_rows` is empty — a symbolic-allele drop makes "
    "`manifest.stats` the post-drop answer while a recomputation from the authored rows is the "
    "pre-drop one, and the two then disagree permanently and correctly"
)

#: Which manifest fields are pure functions of the authored rows. Ships beside the record table
#: because it is a fact this repo holds and a consumer would otherwise guess at.
#: The recipe every conditional entry shares, spelled against the compiler's public surface. Both
#: halves are public for this reason: `spec_tables` (S53) returns the parsed, `defaults:`-folded rows
#: `content_signature` hashes, and `module_stats` (S57) is the derivation over them. Hashing
#: `load_csv_rows` output directly gives a different answer, because the fold is the part that
#: silently produces a wrong one.
_STATS_RECIPE: str = (
    "rows, _build = spec_tables(spec_dir); "
    "module_stats(rows.get('variants.csv', []), rows)[{key!r}]"
)

AUTHORED_ROW_DERIVED_FIELDS: tuple[RosterEntry, ...] = (
    RosterEntry(
        field="content_signature",
        recompute="just_dna_compiler.compiler.content_signature(spec_dir)",
        condition=None,
    ),
    RosterEntry(
        field="stats.study_count",
        # Never re-derived after the symbolic-allele drop, so unlike the `module_stats` facets below
        # this one is the authored-row answer under every compiler.
        recompute="len(spec_tables(spec_dir)[0].get('studies.csv', []))",
        condition=None,
    ),
    *(
        RosterEntry(
            field=f"stats.{key}",
            recompute=_STATS_RECIPE.format(key=key),
            condition=DROPPED_ROWS_CONDITION,
        )
        for key in (
            "variant_count",
            "gene_count",
            "genes",
            "categories",
            "clinvar_count",
            "pathogenic_count",
            "benign_count",
        )
    ),
)


# ── The table ───────────────────────────────────────────────────────────────────────────────────
#
# One record per **published** release, keyed by version. The 0.6 line published three compiler
# releases — 0.6.0, 0.6.1 and 0.6.6 — so those are the only intervals a stored artifact's
# `compiler_version` can name, and the tags in between never reached a consumer. Everything older
# than 0.6.0 is honestly absent rather than recorded as unchanged.
#
# The gate in the release sequence is what keeps this from becoming the hand-kept map everyone agrees
# it must not be: the measurement forces the declaration rather than the author remembering to write
# one. See `just_dna_compiler.sweep` and COMPILER.md § The release-record sweep.
#
# Both records below were **measured** on 2026-08-28 with that instrument, over all sixteen
# `reference_examples/` compiled from one spec root under each release in turn (`just-dna-compiler`
# and `just-dna-format` pinned together, since the workspace cuts all three packages at one number).
# The declarations underneath were then written against what the measurement showed.
RELEASE_RECORDS: dict[str, ReleaseRecord] = {
    "0.6.1": ReleaseRecord(
        version="0.6.1",
        previous="0.6.0",
        # A measured zero, with its denominator in `evidence`. This record exists precisely so that
        # "0.6.0 → 0.6.1 changed nothing" is an answer a consumer can read rather than a silence they
        # have to interpret.
        axes={axis: False for axis in VALID_RELEASE_OUTPUT_AXES},
        manifest_fields=[],
        declared=[],
        evidence=(
            "16 reference module(s) compiled under 0.6.0 and 0.6.1 from one spec root, so the "
            "compiler is the only variable; modules moved per axis: content_signature 0/16, "
            "manifest_fields 0/16, parquet_bytes 0/16, parquet_schema 0/16, warnings 0/16"
        ),
    ),
    "0.6.6": ReleaseRecord(
        version="0.6.6",
        previous="0.6.1",
        axes={
            "parquet_schema": True,
            "parquet_bytes": True,
            "content_signature": False,
            "manifest_fields": True,
            "warnings": False,
        },
        manifest_fields=[
            "literature.quotes_unchecked",
            "stats.gene_count",
            "stats.genes",
        ],
        declared=[
            DeclaredChange(
                axis="parquet_schema",
                target="studies.parquet:curator",
                kind="addition",
                detail=(
                    "RM120 added the authored `curator` column to `studies.csv`, so the compiled "
                    "`studies.parquet` gained a column no earlier artifact could have carried. The "
                    "value was absent, never wrong."
                ),
                item="RM120",
            ),
            DeclaredChange(
                axis="parquet_bytes",
                target="studies.parquet",
                kind="addition",
                detail=(
                    "The same column, measured as bytes: `studies.parquet` grew by 257 bytes on each "
                    "of the ten examples carrying one, which moved `artifact.digest` with it. A "
                    "parquet schema moving across an interval that is entirely patch releases is the "
                    "sharpest form of this whole finding."
                ),
                item="RM120",
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="stats.genes",
                kind="correction",
                detail=(
                    "RM121/S57: `genes` was derived from `variants.csv` alone, so a module whose "
                    "lead table is `diplotypes.csv` or `allele_function.csv` published `[]` however "
                    "many of its rows named a gene — 1,332 of them on "
                    "`reference_examples/cyp2c19_star_alleles`. A registry's gene facet is fed from "
                    "this field, so the value we published was WRONG and every artifact holding it "
                    "is serving it still."
                ),
                item="RM121",
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="stats.gene_count",
                kind="correction",
                detail="The count beside `stats.genes`, wrong for the same reason and on the same modules.",
                item="RM121",
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="literature.quotes_unchecked",
                kind="addition",
                detail=(
                    "RM119 added the third counter to the citation block, so a consumer can tell "
                    "`checked and not found` from `never retrievable`. The counter did not exist "
                    "before, so no earlier artifact could have published it."
                ),
                item="RM119",
            ),
        ],
        evidence=(
            "16 reference module(s) compiled under 0.6.1 and 0.6.6 from one spec root, so the "
            "compiler is the only variable; modules moved per axis: content_signature 0/16, "
            "manifest_fields 9/16, parquet_bytes 10/16, parquet_schema 10/16, warnings 0/16"
        ),
    ),
}
