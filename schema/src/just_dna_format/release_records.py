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

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from just_dna_format.base import vocabulary
from just_dna_format.identity import parse_version
from just_dna_format.manifest import ModuleManifest
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
    # RM342: the Python and polars that wrote the bytes. It moves whenever the install does, the
    # `compiler_version` trap one field over; the sweep reads it as the reason a `parquet_bytes`
    # movement carries (`ModuleDelta.bytes_reason`), never as a published field that changed.
    "compilation.toolchain": "the environment that wrote the bytes, like `compiled_by`; it explains a "
    "`parquet_bytes` movement as `toolchain_differs` rather than being one",
    "compilation.warnings": "routed to the `warnings` axis, which is outside the recompile drivers",
    # RM131 published two fields DERIVED from `compilation.warnings`, so they move exactly when it
    # does. Left in, they would report *a manifest field changed* on every module in a catalogue for
    # a release that reworded one message — the same false positive the line above exists to prevent,
    # arriving three times over instead of once.
    "compilation.carried": "derived from `compilation.warnings`; routed to the `warnings` axis",
    "compilation.warnings_summary": "derived from `compilation.warnings`; routed to the `warnings` axis",
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
            "`correction` when the value we published was wrong, `addition` when it was absent, "
            "`toolchain` (0.8, `parquet_bytes` only) when the bytes moved with the content unchanged "
            "because the recorded toolchain (`compilation.toolchain`) did. The distinction is "
            "declared, never measured; the release gate accepts `toolchain` only when a sweep with "
            "the compiler held fixed backs it."
        ),
    )
    detail: str = Field(description="The sentence a consumer reads: what moved, and why.")
    item: str | None = Field(
        default=None,
        description="The roadmap item behind it (`RM120`), when there is one.",
    )
    requires: tuple[str, ...] | None = Field(
        default=None,
        description=(
            "Which modules the change can reach, as a NECESSARY condition: dotted manifest paths "
            "(`gene_metrics`, spelled as `manifest_fields` spells them) a module must carry non-null "
            "for the change to apply — all of them. `()` says every module; `None` says the reach "
            "could not be stated in this grammar, and a consumer treats the change as reaching any "
            "module. Presence of a path is the whole grammar: a value or membership predicate "
            "would be a separate field (S90, RM201)."
        ),
    )

    @field_validator("axis")
    @classmethod
    def _check_axis(cls, value: str) -> str:
        return check_vocab(value, VALID_RELEASE_OUTPUT_AXES, "axis")

    @field_validator("requires")
    @classmethod
    def _check_requires(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if value is None:
            return None
        for path in value:
            if not path or any(not segment for segment in path.split(".")):
                raise ValueError(f"requires must name dotted manifest paths, got: {path!r}")
        return tuple(value)

    def reaches(self, manifest: ModuleManifest | Mapping[str, Any]) -> bool | None:
        """Whether this change can reach the module `manifest` describes — three answers.

        `False` is the certain one and the only one a consumer acts on: the manifest lacks a path
        the change requires, so the value this change corrected or added was never in that module.
        `True` means *not excluded by what the record states* — `requires` is a necessary condition,
        not the exact reach. RM110 is the worked case: it reaches modules whose `gene_metrics` came
        from the snapshot route, and `("gene_metrics",)` over-approximates that in the safe
        direction. `None` means the record does not state the reach at all (RM121's `stats.genes`
        correction reached modules whose lead table named no gene, which presence cannot spell), and
        a consumer keeps the change — the house algebra, where unknown is never `False`.

        The predicate lives here rather than in a consumer because the grammar is ours (S90): a
        registry reading `target`'s first segment would break the day a target is spelled some
        third way, and would be re-deriving the rule from a field's spelling.
        """
        if self.requires is None:
            return None
        return all(manifest_carries(manifest, path) for path in self.requires)

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        return check_vocab(value, VALID_RELEASE_CHANGE_KINDS, "kind")

    @model_validator(mode="after")
    def _toolchain_explains_bytes_only(self) -> "DeclaredChange":
        """A `toolchain` move is a byte move by definition (RM352).

        The evidence that can back it is a byte measurement with the compiler held fixed, so on any
        other axis the claim could never be backed; refused here rather than left for the release
        gate to find a declaration it could never accept.
        """
        if self.kind == "toolchain" and self.axis != "parquet_bytes":
            raise ValueError(
                f"kind 'toolchain' declares bytes that moved with the content unchanged, so it belongs "
                f"on axis 'parquet_bytes', got axis {self.axis!r}"
            )
        return self


_MISSING = object()


def manifest_carries(manifest: ModuleManifest | Mapping[str, Any], path: str) -> bool:
    """Whether a manifest carries `path` non-null — the one predicate `DeclaredChange.requires` uses.

    Walks the dotted path block by block, over the pydantic model a consumer gets from
    `read_manifest` or over the plain mapping they get from `json.load`, so the two spellings of a
    manifest answer alike. A block that is `None` (an optional block the module never carried) fails
    the walk at that segment; a leaf that is `None` is absent too, because the record's `manifest_fields`
    grammar names published values and an unset optional field publishes none.
    """
    cursor: Any = manifest
    for segment in path.split("."):
        if isinstance(cursor, Mapping):
            cursor = cursor.get(segment, _MISSING)
        else:
            cursor = getattr(cursor, segment, _MISSING)
        if cursor is _MISSING or cursor is None:
            return False
    return True


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

    **`unmeasured` is a denominator, not an exemption (RM139).** `axes` is a claim about the modules
    the sweep could compare, and a minor that adds an authored column and exercises it in the corpus
    leaves at least one module the previous release cannot compile at all — so there is no before
    state to compare it against, and no measurement to declare. The 0.7.0 cut stated that fact in
    `evidence` prose, which the gate cannot read, so the tag had to be waved through by hand.
    Naming the modules in a field the gate checks for **equality** is the opposite of an escape
    hatch: it cannot cover a module that compiled on both sides, it cannot cover one this release
    broke, and listing a module the sweep did measure is itself reported.
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
        description="The correction / addition / toolchain split — declared by the author, never measured.",
    )
    unmeasured: list[str] = Field(
        default_factory=list,
        description=(
            "Modules the previous release produced no output for, so no like-for-like comparison "
            "exists — a new example, or one whose spec uses a column the previous release refuses. "
            "Sorted. Checked for EQUALITY against the sweep, so it acknowledges a measured fact and "
            "cannot excuse a module the sweep did measure (RM139)."
        ),
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
        canonical = {
            check_vocab(name, VALID_RELEASE_OUTPUT_AXES, "axes"): moved for name, moved in value.items()
        }
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
    gap uses. An **absent** stamp is not a malformed one — `needs_recompile` answers unknown for
    `None`/blank before it reaches here (S88), so this function only ever sees a stamp somebody wrote.

    The refusal quotes the **whole** stamp, not the last token: `just-dna-compiler 0.6.6
    (marketplace-server)` used to be refused as `'(marketplace-server)'`, which names nothing the
    caller wrote. The package name is deliberately not checked — one version across the workspace
    is the rule, so `just-dna-format 0.6.6` names the same release.
    """
    token = stamp.strip().rsplit(" ", 1)[-1]
    try:
        parse_version(token)
    except ValueError as exc:
        raise ValueError(
            f"a compiler version stamp must end in MAJOR.MINOR.PATCH "
            f"(`0.7.0` or `just-dna-compiler 0.7.0`), got: {stamp!r}"
        ) from exc
    return token


@dataclass(frozen=True)
class RecompileAnswer:
    """The facts about an interval. Not a verdict — see this module's docstring.

    `axes` is tri-state per axis under Kleene semantics: a single measured `True` beats any number of
    `None`s (something moved, whatever else is unknown), while a `False` survives only when *every*
    release in the interval was measured and none of them moved.
    """

    compiled_under: str | None
    """`None` when the manifest stamped no compiler version (S88): the interval has no lower bound."""
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
    span: tuple[str | None, str]
    """The interval the answer actually describes, which an overshooting link makes wider than asked.
    `(None, current)` for an unstamped `compiled_under` — an interval with no lower bound."""
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

    @property
    def toolchain_moves(self) -> tuple[DeclaredChange, ...]:
        """The declared byte moves the recorded toolchain explains, content unchanged (RM352).

        Nothing published was wrong and nothing was absent, so a registry that spends a PATCH only on
        `corrections` skips these; the bytes still differ, so `output_differs` still says so.
        """
        return tuple(change for change in self.declared if change.kind == "toolchain")

    def declared_for(self, manifest: ModuleManifest | Mapping[str, Any]) -> tuple[DeclaredChange, ...]:
        """The declarations that can reach the module `manifest` describes (S90, RM201).

        Drops a change only where `reaches` answers `False` — a stated requirement the manifest
        does not meet. A change whose reach is unstated (`None`) is **kept**, not dropped: the
        registry that filters `corrections` by this spends an immutable PATCH per module it keeps,
        and the cost of keeping one it did not need is one version number, where the cost of
        dropping one it needed is a module serving a value we have said is wrong.
        """
        return tuple(change for change in self.declared if change.reaches(manifest) is not False)


def _unknown_axes() -> dict[str, bool | None]:
    return dict.fromkeys(VALID_RELEASE_OUTPUT_AXES)


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
    compiled_under: str | None,
    current: str,
    records: dict[str, ReleaseRecord] | None = None,
) -> RecompileAnswer:
    """What changed about compiled output between the release an artifact was compiled under and now.

    `compiled_under` is `manifest.compilation.compiler_version`; `current` is the release the caller
    is holding. **Both are explicit and neither is defaulted** — this module lives in the format
    tier, which cannot know which compiler is installed, and defaulting to its own version would
    answer with the wrong package's number.

    **An absent stamp is the unknown arm, not a crash (S88).** `Compilation.compiler_version` is
    `str | None`, so a manifest that stamped nothing is well-formed and comes back through
    `read_manifest` as `None`; a registry walking manifests it did not produce will be handed one.
    `None`, `""` and whitespace are one fact — nobody stamped — and answer alike: every axis `None`,
    `complete=False`, `compiled_under=None`, `span=(None, current)`. That is the purest *unknown
    provenance* this table can be asked about, and the answer it already gives for a release it has
    no record of. A stamp that is **present and unreadable** (`"0.7"`, `"v0.7.0"`,
    `"0.6.6+local"`, a trailing note in parentheses) is a different state and still raises: it was
    asked and cannot be read, which is a caller's bug to fix, and the `ValueError` names the whole
    stamp so they can. Absent, malformed, uncovered: three states, two answers, and the middle one
    is the only refusal.

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
    current = release_version(current)
    if compiled_under is None or not compiled_under.strip():
        return RecompileAnswer(
            compiled_under=None,
            current=current,
            axes=_unknown_axes(),
            manifest_fields=(),
            declared=(),
            covered=(),
            complete=False,
            span=(None, current),
        )
    compiled_under = release_version(compiled_under)
    low = parse_version(compiled_under)
    high = parse_version(current)

    if low == high:
        return RecompileAnswer(
            compiled_under=compiled_under,
            current=current,
            axes=dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False),
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

    axes: dict[str, bool | None] = dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False)
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
    "rows, _build = spec_tables(spec_dir); module_stats(rows.get('variants.csv', []), rows)[{key!r}]"
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
        axes=dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False),
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
                # `requires` stays None on purpose (S90): the wrong value sat on modules whose
                # lead table named no gene while another table did, and presence of a manifest
                # path cannot spell that — every module carries `stats.genes`. Unstated, so a
                # consumer keeps it for every module, which is the conservative arm.
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
    "0.7.0": ReleaseRecord(
        version="0.7.0",
        previous="0.6.6",
        axes={
            "parquet_schema": True,
            "parquet_bytes": True,
            "content_signature": False,
            "manifest_fields": True,
            "warnings": True,
        },
        manifest_fields=[
            "authority_precedence",
            "clin_sig_concordance",
            "expression_effects",
            "gene_validity.superseded_count",
            "identity.version_coerced_from",
            "verification.checks",
        ],
        declared=[
            DeclaredChange(
                axis="manifest_fields",
                target="expression_effects",
                kind="addition",
                detail=(
                    "RM200's tenth derived-fact sidecar, `expression_effects.csv`, summarised as a "
                    "top-level manifest block beside `gene_metrics` and `gene_validity`. The block "
                    "is `None` on every module that carries no such table — which is every "
                    "reference module — so what moved is the key appearing at all, not a value. "
                    "Absent before, never wrong. Found by the release gate at the cut: the block "
                    "landed after the round's last sweep and nothing else walks the manifest's "
                    "top-level keys against the record."
                ),
                item="RM200",
                requires=(),
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="clin_sig_concordance",
                kind="addition",
                detail=(
                    "RM130's concordance summary block. A module enriched against a ClinVar snapshot "
                    "now carries the pair of concordance tables even when nothing is contested, so "
                    "the block appears where no earlier artifact had one. Absent before, never wrong."
                ),
                item="RM130",
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="authority_precedence",
                kind="addition",
                detail=(
                    "RM134 § B's optional `module_spec.yaml` field, echoed to the manifest so a "
                    "consumer can read the author's stance. Nothing computes with it, so its "
                    "appearance changes no verdict."
                ),
                item="RM134",
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="verification.checks",
                kind="addition",
                detail=(
                    "RM85 added `dataset_currency` to VALID_VERIFICATION_CHECKS, so a module whose "
                    "enrich run attested it lists one more member. A new member, not a changed one."
                ),
                item="RM85",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="haplotypes.parquet,pharm_variants.parquet:requires_callable",
                kind="addition",
                detail=(
                    "RM70 put the optional `requires_callable` column on `HaplotypeRow` and "
                    "`PharmVariantRow`, so those parquets gained a column earlier artifacts could "
                    "not carry. A module that never writes the cell hashes as it did."
                ),
                item="RM70",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="pharm_variants.parquet:pmid",
                kind="addition",
                detail=(
                    "RM132 put the optional `pmid` column on `PharmVariantRow`, so that parquet gains "
                    "a SECOND column in this release rather than only RM70's. Listed separately "
                    "because it is a separate item with a separate remediation: one states a "
                    "callability requirement, the other cites the evidence for a drug/genotype claim. "
                    "Absent, never wrong."
                ),
                item="RM132",
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="gene_validity.superseded_count",
                kind="addition",
                detail=(
                    "RM108 publishes how many gene-validity rows a later curation of the same claim "
                    "replaced. Derived rather than stored — the row that would carry a `superseded` "
                    "column is the one already in the file, and merge-not-clobber forbids the pass "
                    "editing it — so no parquet or signature moves with it. The counter did not "
                    "exist before, so no earlier artifact could have published it, and 0 is a real "
                    "answer rather than an absence."
                ),
                item="RM108",
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="gene_validity.classifications",
                kind="correction",
                detail=(
                    "The same field now spans the CURRENT rows rather than every row, so a module "
                    "carrying a re-curated claim publishes one verdict where it published a pair — "
                    "as far apart as ['definitive', 'refuted'] — with nothing saying which stood. A "
                    "CORRECTION, not an addition: the list we published named a superseded "
                    "classification as though it were live. A group nothing can order (a tie on "
                    "classification_date, or a row stating none) still contributes all of its "
                    "classifications, so the field is unchanged there."
                ),
                item="RM108",
                requires=("gene_validity",),
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="identity.version_coerced_from",
                kind="addition",
                detail=(
                    "RM103 publishes the `module.version` the author actually wrote whenever the "
                    "model rewrote it — `'v2'` beside `'2.0.0'`, `'abc'` beside `'0.0.0'`. The "
                    "coercion is unchanged and stays (RM17); what changes is that the artifact now "
                    "records what was READ, so an invented `0.0.0` stops being indistinguishable "
                    "from an author who wrote one. Absent on every module whose authored version was "
                    "already canonical SemVer, which is most of them, so this fires on few artifacts."
                ),
                item="RM103",
            ),
            DeclaredChange(
                axis="parquet_bytes",
                target="gene_metrics.parquet",
                kind="correction",
                detail=(
                    "RM110 normalized gnomAD's flag list, which the snapshot route had stored as a "
                    'JSON array literal — `"[]"` on 17,403 of the published v4.1 snapshot\'s 18,111 '
                    "rows, a real literal on the other 708, and not one row null. The cell changes "
                    "value, so `gene_metrics.parquet` and `artifact.digest` move on any module "
                    "compiled from that snapshot. A CORRECTION, not an addition: the value we "
                    "published contradicted the column's own description and read as *flagged* for "
                    "100% of snapshot rows where 3.9% are. One row in our corpus (`hboc_palb2`)."
                ),
                item="RM110",
                # A necessary condition, not the reach: the snapshot route is what it reaches,
                # and a module whose block came from the live route is kept, not excluded.
                requires=("gene_metrics",),
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="gene_metrics.signature",
                kind="correction",
                detail=(
                    "`constraint_flags` is inside `GENE_METRICS_FACT_FIELDS`, so the same gene "
                    "fetched two ways was already minting two signatures — which is why RM110 could "
                    "not be fixed by normalizing on the way out. Moves with the cell above, on the "
                    "same modules."
                ),
                item="RM110",
                requires=("gene_metrics",),
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="studies.parquet:statistical_test",
                kind="addition",
                detail=(
                    "RM140 added the authored `statistical_test` column to `studies.csv`, so the "
                    "compiled `studies.parquet` gained a column no earlier artifact could have "
                    "carried. Every module in the corpus leaves the cell unset, so the value was "
                    "absent rather than wrong — and `content_signature` does not move, because an "
                    "unset optional cell is omitted from it."
                ),
                item="RM140",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="studies.parquet:confidence,confidence_unit",
                kind="addition",
                detail=(
                    "RM160 added the authored `confidence`/`confidence_unit` pair to `studies.csv`, "
                    "so `studies.parquet` gained two more columns no earlier artifact could have "
                    "carried. They travel together — a magnitude with no instrument beside it is "
                    "refused — and every module in the corpus leaves both unset, so the value is "
                    "absent rather than wrong and `content_signature` does not move."
                ),
                item="RM160",
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="verification.checks",
                kind="addition",
                detail=(
                    "RM160 added `evidence_status_currency` to VALID_VERIFICATION_CHECKS, so a "
                    "module whose enrich run re-asked CIViC about a recovered citation lists one "
                    "more member. A new member, not a changed one."
                ),
                item="RM160",
            ),
            DeclaredChange(
                axis="parquet_bytes",
                target="studies.parquet",
                kind="addition",
                detail=(
                    "The column above lands in every `studies.parquet`, so the ten reference modules "
                    "carrying one move their `artifact.digest`. This is the bulk of the measured "
                    "parquet movement in this release and it is the cheapest kind: a new column no "
                    "row fills. RM140 arrived after the round closed and is measured here with "
                    "it, and RM160's two columns land in the same parquet on the same terms — the "
                    "ten digests were already moving."
                ),
                item="RM140",
            ),
            DeclaredChange(
                axis="parquet_bytes",
                target="clin_sig_concordance.parquet,clin_sig_authority_calls.parquet",
                kind="addition",
                detail=(
                    "The two concordance parquets are new files, so a module carrying them lists "
                    "two more entries in `artifact.files` and its `artifact.digest` moves. An "
                    "addition, not a correction: no value we previously published was wrong. (This "
                    "read `the release's most visible consequence` until RM140 landed after the "
                    "round and moved ten digests to these four — the claim was measured, so it was "
                    "corrected rather than kept.)"
                ),
                item="RM130",
            ),
            DeclaredChange(
                axis="warnings",
                target="compilation.warnings",
                kind="addition",
                detail=(
                    "RM131 restructured the findings channel and RM130/RM132/RM134 added emission "
                    "sites, so the warning text a module carries moves. The warnings axis is "
                    "deliberately OUTSIDE the set that drives a recompile, for exactly this release: "
                    "acting on it would mint a version across a whole catalogue for a message change. "
                    "`carried` is the discriminator that tells a rewording from a new finding."
                ),
                item="RM131",
            ),
        ],
        # RM139: the same fact its `evidence` sentence already states, in the field the gate reads.
        unmeasured=["cyp2c9_warfarin_grch37"],
        evidence=(
            "15 reference module(s) compiled under 0.6.6 and 0.7.0 from one spec root, so the "
            "compiler is the only variable; modules moved per axis: content_signature 0/15, "
            "manifest_fields 15/15, parquet_bytes 14/15, parquet_schema 14/15, warnings 3/15. "
            "Re-measured on 2026-08-31 when RM140 landed after the round closed: the two parquet "
            "axes read 4/15 before it, and its one new `studies.parquet` column moves every module "
            "carrying that table. `content_signature` stayed at 0/15 through it. "
            "`cyp2c9_warfarin_grch37` is unmeasured rather than unchanged: RM70 added "
            "`requires_callable` to its `pharm_variants.csv`, which 0.6.6 refuses under "
            '`extra="forbid"`, so its authored input is not byte-identical across the interval and '
            "no like-for-like comparison exists for it."
        ),
    ),
    # Measured at the 0.8.0 cut (2026-11-05) with the two sweeps COMPILER.md § The release-record sweep
    # describes: the release sweep (published 0.7.2 under polars 1.44.2 → this release under the locked
    # polars 2.1.0) and the fixed-compiler sweep (this release under 1.44.2 → under 2.1.0). Sixteen of the
    # 22 examples commit a 0.8-written `resolution.csv`, which 0.7.2 refuses, so they are `unmeasured`.
    "0.8.0": ReleaseRecord(
        version="0.8.0",
        previous="0.7.2",
        axes={
            "parquet_schema": True,
            "parquet_bytes": True,
            "content_signature": True,
            "manifest_fields": True,
            "warnings": True,
        },
        manifest_fields=[
            "colocalisations",
            "compilation.vrs_version",
            "consequences",
            "inputs",
            "ld_pairs",
            "literature.quotes_checked",
            "locus_to_gene",
            "meta_selectors",
            "stats.clin_sig_counts.affects",
            "stats.clin_sig_counts.association",
            "stats.clin_sig_counts.benign",
            "stats.clin_sig_counts.conflicting",
            "stats.clin_sig_counts.drug_response",
            "stats.clin_sig_counts.likely_benign",
            "stats.clin_sig_counts.likely_pathogenic",
            "stats.clin_sig_counts.not_provided",
            "stats.clin_sig_counts.other",
            "stats.clin_sig_counts.pathogenic",
            "stats.clin_sig_counts.protective",
            "stats.clin_sig_counts.risk_factor",
            "stats.clin_sig_counts.uncertain_significance",
            "stats.clin_sig_variant_counts.affects",
            "stats.clin_sig_variant_counts.association",
            "stats.clin_sig_variant_counts.benign",
            "stats.clin_sig_variant_counts.conflicting",
            "stats.clin_sig_variant_counts.drug_response",
            "stats.clin_sig_variant_counts.likely_benign",
            "stats.clin_sig_variant_counts.likely_pathogenic",
            "stats.clin_sig_variant_counts.not_provided",
            "stats.clin_sig_variant_counts.other",
            "stats.clin_sig_variant_counts.pathogenic",
            "stats.clin_sig_variant_counts.protective",
            "stats.clin_sig_variant_counts.risk_factor",
            "stats.clin_sig_variant_counts.uncertain_significance",
            "tier_scale",
            "verification",
            "verification.checks",
            "verification.closure.closed_at",
            "verification.closure.closed_by",
            "verification.closure.signature",
            "verification.module_hash",
            "verification.produced_at",
            "verification.producer",
            "verification.signature",
        ],
        declared=[
            DeclaredChange(
                axis="manifest_fields",
                target="stats.clin_sig_counts",
                kind="addition",
                detail=(
                    "RM300: authored `variants.csv` rows per ClinVar tier, every `VALID_CLIN_SIG` member "
                    "present with zeros included. The sweep walks a mapping, so it moves as one path per "
                    "tier. Absent before, never wrong; empty on an older manifest means not counted."
                ),
                item="RM300",
                requires=(),
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="stats.clin_sig_variant_counts",
                kind="addition",
                detail="RM300: the same tiers counted as distinct `variant_key`s.",
                item="RM300",
                requires=(),
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="compilation.vrs_version",
                kind="addition",
                detail=(
                    "RM304: the VRS version the module's `vrs_id`s are pinned to, `null` where no allele "
                    "carries an id. The key appears on every manifest."
                ),
                item="RM304",
                requires=(),
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="literature.quotes_checked",
                kind="addition",
                detail=(
                    "RM256: how many quotes a retrieved text settled, the denominator `quotes_found` is "
                    "read against. Null on an older manifest, which means not counted."
                ),
                item="RM256",
                requires=("literature",),
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="meta_selectors",
                kind="addition",
                detail=(
                    "RM28: every `meta.csv` member with the rows it matched; `null` on a module with no "
                    "`meta.csv`, so on most modules what moved is the key appearing."
                ),
                item="RM28",
                requires=(),
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="tier_scale",
                kind="addition",
                detail="RM324: the scale `meta.csv`'s `tier` grades on, copied from `module_spec.yaml`.",
                item="RM324",
                requires=(),
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="locus_to_gene",
                kind="addition",
                detail=(
                    "RM333's Open Targets lane: three new derived-table blocks, `null` on a module "
                    "carrying none of the tables, so what moved is the key appearing."
                ),
                item="RM333",
                requires=(),
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="colocalisations",
                kind="addition",
                detail="RM333: the colocalisation block, beside `locus_to_gene`.",
                item="RM333",
                requires=(),
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="consequences",
                kind="addition",
                detail="RM333: the consequence block, beside `locus_to_gene`.",
                item="RM333",
                requires=(),
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="ld_pairs",
                kind="addition",
                detail="RM331: the computed LD-pair block, `null` on a module with no `ld_pairs.csv`.",
                item="RM331",
                requires=(),
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="inputs",
                kind="addition",
                detail=(
                    "RM28: `meta.csv` (and RM335's `model_organisms.csv`) are compile inputs from 0.8, so a "
                    "module carrying one lists one more input. 0.7.2 tolerates the file as unknown and "
                    "compiles the module without it (`hla_alleles` in the corpus)."
                ),
                item="RM28",
            ),
            DeclaredChange(
                axis="manifest_fields",
                target="verification",
                kind="addition",
                detail=(
                    "RM292 and RM267: a verification record now names its witness (`checked_source`, "
                    "`witness_source`, `independence`, `undecided`) and may carry `placement_agreement`. "
                    "0.7.2 refuses such a `verification.json` and compiles with no verification block, so "
                    "the block appears on a module whose record a 0.8 enricher wrote (`hla_alleles`)."
                ),
                item="RM292",
                requires=("verification",),
            ),
            DeclaredChange(
                axis="content_signature",
                target="meta.csv",
                kind="addition",
                detail=(
                    "RM28: a module carrying `meta.csv` hashes its rows from 0.8, where 0.7.2 skipped the "
                    "file as unknown. New content, never a wrong value (`hla_alleles` in the corpus)."
                ),
                item="RM28",
                requires=("meta_selectors",),
            ),
            DeclaredChange(
                axis="content_signature",
                target="studies.csv,haplotypes.csv,pharm_variants.csv,heteroplasmy.csv:chrom",
                kind="correction",
                detail=(
                    "RM363: `studies`, `haplotypes`, `pharm_variants` and `heteroplasmy` store a "
                    "primary-assembly contig as the member (`chr12` → `12`, `chrM` → `MT`), as `variants` "
                    "has since 0.5, so a coordinate study meets its variant. A module that wrote "
                    "`chr`-prefixed contigs on those tables gets a new `content_signature`; no reference "
                    "example the sweep measured writes one."
                ),
                item="RM363",
                # Unstated on purpose (S90): the wrong value sat on modules that wrote `chr` on those
                # four tables, and presence of a manifest path cannot spell that.
                requires=None,
            ),
            DeclaredChange(
                axis="parquet_bytes",
                target="studies.parquet,haplotypes.parquet,pharm_variants.parquet,heteroplasmy.parquet",
                kind="correction",
                detail=(
                    "RM363's contig spelling, measured as bytes: the same modules' parquets carry `12` "
                    "where they carried `chr12`."
                ),
                item="RM363",
                requires=None,
            ),
            DeclaredChange(
                axis="parquet_bytes",
                target="haplotypes.parquet",
                kind="correction",
                detail=(
                    "RM361: an absent cell is never formatted into a key, so a positional key with no "
                    "`ref` reads `13:48037749`, where it read `13:48037749:None`. The value we published "
                    "was wrong; `haplotypes.parquet` moves on a module keying such rows "
                    "(`cpic_gene_pairs`, nine keys), with `content_signature` unchanged."
                ),
                item="RM361",
                # Unstated on purpose: the reach is a positional row with no `ref`, which no manifest
                # path spells.
                requires=None,
            ),
            DeclaredChange(
                axis="parquet_bytes",
                target="artifact.digest",
                kind="addition",
                detail=(
                    "The schema additions below land in every module carrying the parquets they reach, so "
                    "all six measured modules move `artifact.digest`, under polars 1.44.2 as under 2.1.0."
                ),
                requires=(),
            ),
            DeclaredChange(
                axis="parquet_bytes",
                target="weights.parquet",
                kind="addition",
                detail=(
                    "RM380: the superseded DuckDB compile path and the resolution-table path agree on "
                    "facts, not bytes: their `weights.parquet` differ only in `resolution_loci`, which the "
                    "DuckDB path does not fill. The DuckDB path is queued for removal at 1.0."
                ),
                item="RM380",
                requires=(),
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="weights.parquet,heteroplasmy.parquet:vrs_id,vrs_spec",
                kind="addition",
                detail=(
                    "RM270: the minted VRS id and its version on the variant parquets, an indel's "
                    "spelling-independent identity. Null where `resolution.csv` records no id."
                ),
                item="RM270",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="studies.parquet:proxy_rsid,proxy_loci",
                kind="addition",
                detail=(
                    "RM331: a study measured on an LD proxy names it, and `proxy_loci` carries the proxy's "
                    "resolved loci; `ld_pairs.parquet` is a new file for a module enriched with `ld-pairs`."
                ),
                item="RM331",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="weights.parquet,heteroplasmy.parquet:resolution_loci",
                kind="addition",
                detail=(
                    "RM364: the positional parquets carry the resolution rows behind each key, so "
                    "`reverse` gives back what the compile read."
                ),
                item="RM364",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="resolution_loci,proxy_loci",
                kind="addition",
                detail=(
                    "RM380: the locus struct is derived from `ResolutionRow`, so it gains `authority`, "
                    "`status`, `caid`, `placement_witness`, `placement_verdict`, `left_aligned`, "
                    "`authored_event`, `judged_coordinate` and `source_release`."
                ),
                item="RM380",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="resolution_loci,proxy_loci:source_loci",
                kind="addition",
                detail="RM387: the struct gains `source_loci`, every place the links answered an rsID at.",
                item="RM387",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="studies.parquet:sample_size,sample_unit,n_cases",
                kind="addition",
                detail="RM325: the study's size, what it counts, and its case count.",
                item="RM325",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="studies.parquet:phenotype_class;weights.parquet:outcome_lifespan,outcome_healthspan,outcome_exceptional",
                kind="addition",
                detail="RM326: the outcome a study measured, and the per-outcome flags it derives.",
                item="RM326",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="studies.parquet:ancestry;weights.parquet:eur_only_evidence",
                kind="addition",
                detail="RM328: the ancestry a study was measured in, and the flag for European-only evidence.",
                item="RM328",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="studies.parquet:age_min,age_max,age_of",
                kind="addition",
                detail="RM329: an age-stratified estimate's band.",
                item="RM329",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="studies.parquet:stratum,stratum_level",
                kind="addition",
                detail="RM330: an estimate measured in one stratum names it.",
                item="RM330",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="studies.parquet,weights.parquet:effect_unit",
                kind="addition",
                detail="RM332: the unit a beta is stated in.",
                item="RM332",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="the binning kinds' parquets,pharm_variants.parquet,gwas_effects.parquet:doi",
                kind="addition",
                detail="RM336: the citing tables carry a `doi` beside `pmid`.",
                item="RM336",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="literature.parquet:fulltext_status",
                kind="addition",
                detail="RM258: how the fulltext question ended, null for not asked.",
                item="RM258",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="meta.parquet,meta_resolved.parquet",
                kind="addition",
                detail="RM28: two new files for a module carrying `meta.csv`.",
                item="RM28",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="model_organisms.parquet",
                kind="addition",
                detail="RM335: a new file for a module carrying `model_organisms.csv`.",
                item="RM335",
            ),
            DeclaredChange(
                axis="parquet_schema",
                target="locus_to_gene.parquet,colocalisations.parquet,consequences.parquet",
                kind="addition",
                detail="RM333: three new files for a module the Open Targets pass enriched.",
                item="RM333",
            ),
            DeclaredChange(
                axis="warnings",
                target="compilation.warnings",
                kind="addition",
                detail=(
                    "`hla_alleles` loses two warnings 0.7.2 gave it: its 0.8-written verification record "
                    "read as stale there (0.7.2 hashed the module without `meta.csv`), so no closure was "
                    "read either. The warnings axis stays outside the recompile drivers."
                ),
                item="RM28",
            ),
        ],
        unmeasured=[
            "apoe_epsilon",
            "apoe_klvs_meta",
            "cpic_gene_pairs",
            "cyp2c19_star_alleles",
            "cyp2c9_warfarin_grch37",
            "hboc_palb2",
            "hfe_compound_het",
            "hfe_hemochromatosis",
            "longevity_studies",
            "model_organisms",
            "mt_common_deletion",
            "par_boundary",
            "pathogenic_clinvar",
            "pgx_slco1b1_simvastatin",
            "pleiotropy_tradeoff",
            "shox_par1",
        ],
        evidence=(
            "6 reference module(s) compiled under 0.7.2 and 0.8.0 from one spec root, both under polars "
            "1.44.2 on the BEFORE side, so the compiler is the only variable; modules moved per axis: "
            "content_signature 1/6, manifest_fields 6/6, parquet_bytes 6/6, parquet_schema 6/6, warnings 1/6. "
            "With polars held at 1.44.2 the same six move on every axis they move on here, so every byte "
            "move in this interval is the compiler's. The fixed-compiler sweep (0.8.0 under polars 1.44.2 "
            "and 2.1.0, all 22 examples) moved parquet_bytes 22/22 and nothing else: content_signature "
            "0/22. It explains no measured module on its own, so no `toolchain` change is declared; the "
            "toolchain move is real and lands on every module. `toolchain_differs` is the NORMAL case "
            "between this release and just-dna-lite, which stays on polars 1.x (polars-bio caps "
            "`polars<2`): one compiler, two toolchains, two digests, one content. Unmeasured rather than "
            "unchanged, because each commits a `resolution.csv` (or a `module_spec.yaml` key) written by "
            "0.8, which 0.7.2 refuses: apoe_epsilon, apoe_klvs_meta, cpic_gene_pairs, "
            "cyp2c19_star_alleles, cyp2c9_warfarin_grch37, hboc_palb2, hfe_compound_het, "
            "hfe_hemochromatosis, longevity_studies, model_organisms, mt_common_deletion, par_boundary, "
            "pathogenic_clinvar, pgx_slco1b1_simvastatin, pleiotropy_tradeoff, shox_par1. Example data "
            "moved too, and is not a compiler change: the 16 examples' resolution.csv were regenerated "
            "against ensembl-variation-2026_07_13-vep116.0, pathogenic_clinvar dropped a duplicate "
            "coordinate-only row (11:5226762 C>CAAAG, also authored as rs80356821), and cpic_gene_pairs' "
            "NUDT15 rs1457579126 row was re-anchored from 13:48040982 to 13:48040977."
        ),
    ),
}
