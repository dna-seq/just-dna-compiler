"""The release record and `needs_recompile` (RM126) — the channel Principle 3's amendment names.

Two properties here are load-bearing rather than incidental and are asserted as such: **the interval
from a version to itself is empty**, which is what stops an automated sweep minting a fresh PATCH
every run forever, and **moved-and-moved-back still reads as moved**, which is the right reading for
staleness and the one a per-field "current value" table would get wrong.

The third is the house algebra. An interval the table does not cover answers `unknown` — never an
empty result and never `False`, because a consumer would stop recompiling on the strength of a
silence.

The registry guards walk the vocabulary and the shipped records and assert an **equality**. A floor
would pass while a new axis went unanswered on every record, which is the failure the tri-state exists
to make impossible.
"""

from __future__ import annotations

import pytest
from just_dna_format.base import field_vocabularies
from just_dna_format.manifest import ModuleManifest
from just_dna_format.release_records import (
    AUTHORED_ROW_DERIVED_FIELDS,
    DROPPED_ROWS_CONDITION,
    EXCLUDED_MANIFEST_FIELDS,
    NON_RECOMPILE_AXES,
    RECOMPILE_DRIVING_AXES,
    RELEASE_RECORDS,
    DeclaredChange,
    ReleaseRecord,
    needs_recompile,
    release_version,
)
from just_dna_format.vocab import VALID_RELEASE_CHANGE_KINDS, VALID_RELEASE_OUTPUT_AXES
from pydantic import ValidationError


def _record(version: str, previous: str, **moved: bool | None) -> ReleaseRecord:
    """A synthetic record: every axis `False` unless this call says otherwise."""
    axes: dict[str, bool | None] = dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False)
    axes.update(moved)
    return ReleaseRecord(
        version=version,
        previous=previous,
        axes=axes,
        manifest_fields=["stats.genes"] if axes.get("manifest_fields") else [],
        declared=[],
        evidence=f"synthetic fixture for {previous} -> {version}",
    )


# ── the two properties the interval shape exists for ─────────────────────────────────────────────


def test_the_interval_from_a_version_to_itself_is_empty() -> None:
    """The convergence requirement, and it holds structurally rather than by a caller's special case.

    A hint that fires for a version compiled by the exact compiler now installed makes an unattended
    sweep mint a fresh PATCH every run, forever. Asserted for a version the table *does* record and
    for one it has never heard of, because the property must not depend on coverage.
    """
    for version in ("0.6.6", "9.9.9"):
        answer = needs_recompile(version, version)
        assert set(answer.axes.values()) == {False}
        assert answer.output_differs is False
        assert answer.complete is True
        assert answer.covered == ()
        assert answer.declared == ()


def test_a_value_that_moved_and_moved_back_still_reads_as_moved() -> None:
    """The union over `(a, b]`, not a comparison of the endpoints.

    A consumer asking whether their stored bytes match a recompile is not asking whether the
    difference is interesting — and a per-field "what does this field say now" table would answer
    `False` here, because the endpoints agree.
    """
    records = {
        "1.0.1": _record("1.0.1", "1.0.0", manifest_fields=True),
        "1.0.2": _record("1.0.2", "1.0.1", manifest_fields=True),
    }
    there_and_back = needs_recompile("1.0.0", "1.0.2", records)

    assert there_and_back.axes["manifest_fields"] is True
    assert there_and_back.complete is True
    assert there_and_back.covered == ("1.0.2", "1.0.1")
    # …while each single hop is what the endpoints-only reading would have seen.
    assert needs_recompile("1.0.1", "1.0.2", records).axes["manifest_fields"] is True


# ── unknown is a state ───────────────────────────────────────────────────────────────────────────


def test_an_uncovered_interval_answers_unknown_on_every_axis_and_never_false() -> None:
    """`None` is never `False`, and the distinction is the whole value of the surface here.

    Asserted with `is None` per axis rather than by truthiness: `False` and `None` are both falsy, so
    a truthiness assertion would pass on the exact bug this guards.
    """
    answer = needs_recompile("2.0.0", "2.0.1", {})

    assert set(answer.axes) == set(VALID_RELEASE_OUTPUT_AXES)
    for axis, moved in answer.axes.items():
        assert moved is None, axis
    assert answer.output_differs is None
    assert answer.complete is False
    # Not an empty result: the axes are present and answering, they are answering "cannot say".
    assert answer.axes != {}


def test_a_measured_move_survives_an_uncovered_remainder_under_kleene() -> None:
    """`true OR unknown` is `true`; `false OR unknown` is `unknown`. Not withhold-on-any-unknown.

    The interval below is half measured — the 1.0.2 hop moved `parquet_bytes` and nothing else, and
    the 1.0.1 hop is missing entirely. So the bytes answer is a definite yes while every other axis
    has to withhold.
    """
    records = {"1.0.2": _record("1.0.2", "1.0.1", parquet_bytes=True)}
    answer = needs_recompile("1.0.0", "1.0.2", records)

    assert answer.axes["parquet_bytes"] is True
    assert answer.axes["content_signature"] is None
    assert answer.output_differs is True
    assert answer.complete is False


def test_a_downgrade_interval_withholds_rather_than_answering_backwards() -> None:
    """An artifact compiled under something NEWER than the installed release.

    The union is not symmetric — this table records what a release *did*, not what undoing it would
    do — so the honest answer is `cannot say` on every axis.
    """
    answer = needs_recompile("0.6.6", "0.6.1")

    assert set(answer.axes.values()) == {None}
    assert answer.output_differs is None
    assert answer.complete is False
    assert answer.span == ("0.6.1", "0.6.6")


def test_a_link_reaching_below_the_asked_bound_keeps_false_and_blunts_true() -> None:
    """A record covering a wider span than was asked about answers a wider question.

    The narrowing is sound in one direction only: if nothing moved across the wider span then nothing
    moved inside it, whereas something moving across the wider span says nothing about *where*.
    """
    records = {"1.0.3": _record("1.0.3", "1.0.0", parquet_bytes=True, content_signature=False)}
    answer = needs_recompile("1.0.2", "1.0.3", records)

    assert answer.axes["parquet_bytes"] is None, "a `True` over a wider span cannot be narrowed"
    assert answer.axes["content_signature"] is False, "a `False` over a wider span narrows soundly"
    assert answer.complete is False
    assert answer.span == ("1.0.0", "1.0.3")


def test_an_overshooting_links_detail_is_withheld_rather_than_reported_in_span() -> None:
    """The blunting has to reach the detail too, or the answer contradicts itself in one object.

    A registry acts on `corrections` and spends an immutable PATCH doing it, so a correction that may
    have happened anywhere in a wider interval must not appear there while the axis beside it says
    *cannot say*. Withheld, not dropped — the out-of-span tuples still carry it for a caller who
    knows what they are reading.
    """
    record = ReleaseRecord(
        version="1.0.3",
        previous="1.0.0",
        axes={**dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False), "manifest_fields": True},
        manifest_fields=["stats.genes"],
        declared=[
            DeclaredChange(
                axis="manifest_fields", target="stats.genes", kind="correction", detail="was wrong"
            )
        ],
        evidence="measured across the whole of 1.0.0 -> 1.0.3",
    )
    inside = needs_recompile("1.0.0", "1.0.3", {"1.0.3": record})
    overshot = needs_recompile("1.0.2", "1.0.3", {"1.0.3": record})

    # Asked about exactly what the record measured, everything is reported.
    assert inside.manifest_fields == ("stats.genes",)
    assert [c.target for c in inside.corrections] == ["stats.genes"]
    assert inside.out_of_span_declared == ()

    # Asked about a sub-interval, the axis withholds — and so does everything under it.
    assert overshot.axes["manifest_fields"] is None
    assert overshot.manifest_fields == ()
    assert overshot.declared == ()
    assert overshot.corrections == ()
    assert overshot.out_of_span_manifest_fields == ("stats.genes",)
    assert [c.target for c in overshot.out_of_span_declared] == ["stats.genes"]


def test_a_chain_that_does_not_descend_is_refused_rather_than_looped() -> None:
    records = {"1.0.1": _record("1.0.1", "1.0.1")}
    with pytest.raises(ValueError, match="would not terminate"):
        needs_recompile("1.0.0", "1.0.1", records)


def test_the_stamped_compiler_version_is_accepted_as_the_key_a_consumer_holds() -> None:
    """`manifest.compilation.compiler_version` reads `just-dna-compiler 0.6.1`, name included.

    Making every consumer strip it themselves is how one convention becomes three implementations.
    """
    assert release_version("just-dna-compiler 0.6.1") == "0.6.1"
    assert release_version("0.6.1") == "0.6.1"
    assert needs_recompile("just-dna-compiler 0.6.1", "0.6.6").axes == needs_recompile(
        "0.6.1", "0.6.6"
    ).axes
    for malformed in ("just-dna-compiler unknown", "0.6", "", "v1"):
        with pytest.raises(ValueError):
            release_version(malformed)


# ── the registries, asserted as equalities ───────────────────────────────────────────────────────


def test_the_axis_vocabulary_is_closed_in_all_three_places() -> None:
    """A closed vocabulary is a constant, a marker on the field, and a validator that RETURNS.

    All three or the guards go blind: the constant alone is not enforced, a marker alone advertises a
    vocabulary nothing rejects, and a validator that calls `check_vocab` without returning it drops
    the separator canonicalisation on the floor.
    """
    markers = field_vocabularies(DeclaredChange)
    assert {marker["name"] for marker in markers.values()} == {
        "release_output_axis",
        "release_change_kind",
    }
    assert markers["axis"]["options"] == sorted(VALID_RELEASE_OUTPUT_AXES)
    assert markers["axis"]["closed"] is True
    assert markers["kind"]["options"] == sorted(VALID_RELEASE_CHANGE_KINDS)

    # Enforced, not merely advertised — and the `-`/`_` slip canonicalises to the declared member.
    assert DeclaredChange(
        axis="parquet-schema", target="t", kind="addition", detail="d"
    ).axis == "parquet_schema"
    with pytest.raises(ValidationError, match="must be one of"):
        DeclaredChange(axis="parquet_colour", target="t", kind="addition", detail="d")
    with pytest.raises(ValidationError, match="must be one of"):
        DeclaredChange(axis="parquet_schema", target="t", kind="regression", detail="d")


def test_every_record_answers_every_axis() -> None:
    """An EQUALITY over the vocabulary, per record — never a subset check and never a floor.

    A record silent about an axis and one saying `None` about it are the same claim; making the
    silence illegal is what forces a newly-added axis to be answered on every existing record, with
    `None` where it cannot be measured, instead of defaulting to whatever a reader assumes.
    """
    assert RELEASE_RECORDS, "the table must not be empty — an empty table is the pre-RM126 state"
    for version, record in RELEASE_RECORDS.items():
        assert record.version == version, "keyed by its own version"
        assert set(record.axes) == set(VALID_RELEASE_OUTPUT_AXES), version
        assert record.evidence.strip(), f"{version} records no evidence"


def test_the_recompile_drivers_are_the_axes_minus_the_declared_exclusions() -> None:
    """Derived by subtraction, so a new axis drives a recompile unless it is explicitly excluded.

    That default is the safe one for a staleness signal: an axis nobody classified should over-report
    rather than go silent.
    """
    assert RECOMPILE_DRIVING_AXES == VALID_RELEASE_OUTPUT_AXES - NON_RECOMPILE_AXES
    assert {"warnings"} == NON_RECOMPILE_AXES
    assert NON_RECOMPILE_AXES < VALID_RELEASE_OUTPUT_AXES


def test_a_warnings_only_release_does_not_read_as_output_differing() -> None:
    """The whole reason `warnings` is its own axis: RM131 and RM134 both move that channel in 0.7.

    Folding it into `manifest_fields` would report *a manifest field changed* on every module in a
    catalogue for a reworded message, and a registry acting on that mints an immutable PATCH across
    the lot.
    """
    records = {"3.0.1": _record("3.0.1", "3.0.0", warnings=True)}
    answer = needs_recompile("3.0.0", "3.0.1", records)

    assert answer.axes["warnings"] is True
    assert answer.output_differs is False, "a message change is not a reason to recompile"


def test_the_declared_split_is_exhaustive_over_the_kind_vocabulary() -> None:
    """`corrections` + `additions` covers every declaration, walked rather than counted.

    A third member added to `VALID_RELEASE_CHANGE_KINDS` without a property beside it would leave
    declarations reachable through neither accessor, and a length check on one of them would not see
    it.
    """
    # Declared kinds are a legitimate SUBSET — a release need not use every member — so this one
    # stays a containment.
    assert {change.kind for record in RELEASE_RECORDS.values() for change in record.declared} <= set(
        VALID_RELEASE_CHANGE_KINDS
    )
    # What the docstring actually promises, and what nothing asserted: every member is reachable
    # through an accessor. A third kind added with no property beside it leaves its declarations
    # readable through neither, and the containment above cannot see that.
    reachable = {"correction", "addition"}
    assert reachable == set(VALID_RELEASE_CHANGE_KINDS), (
        "a change kind gained or lost a member; `corrections`/`additions` must still cover all of them"
    )
    for version in RELEASE_RECORDS:
        answer = needs_recompile(RELEASE_RECORDS[version].previous, version)
        split = sorted(answer.corrections + answer.additions, key=lambda c: (c.axis, c.target))
        assert split == sorted(answer.declared, key=lambda c: (c.axis, c.target)), version


def test_every_recorded_manifest_field_is_a_path_the_manifest_really_has() -> None:
    """A record naming a field that does not exist is a record a consumer cannot act on.

    The check is over the models rather than a second list, so a manifest rename fails here instead
    of leaving the shipped records quietly pointing at nothing. `manifest_fields` also never carries
    a member of `EXCLUDED_MANIFEST_FIELDS` — those are answered by their own axis.
    """
    for version, record in RELEASE_RECORDS.items():
        for path in record.manifest_fields:
            assert _manifest_path_exists(path), f"{version}: {path}"
            assert path not in EXCLUDED_MANIFEST_FIELDS, f"{version}: {path}"
        assert record.manifest_fields == sorted(record.manifest_fields), version
        # A record listing fields while claiming the axis did not move contradicts itself.
        assert bool(record.manifest_fields) <= (record.axes["manifest_fields"] is True), version


def test_a_declared_field_ADDITION_is_also_listed_as_one_that_moved() -> None:
    """A field this release *adds* must appear in `manifest_fields`, and two did not (RM161).

    The two halves of a record are written at different times: `manifest_fields` comes out of a sweep
    (`SweepMeasurement.as_record`, whose `declared` list is empty on purpose) and the declarations are
    written by a person afterwards. So an item landing *after* the measurement can add its declaration
    and leave the measured list behind it — which is what happened to `gene_validity.superseded_count`
    and `identity.version_coerced_from`, and it turns the release gate red at the one moment nobody
    wants to be debugging a record.

    **Additions only, and that asymmetry is the whole test.** A field that did not exist before moves
    wherever its block appears, so a release claiming to add one and measuring no movement is claiming
    something the corpus contradicts. A **correction** may legitimately be unmeasurable: 0.7.0 declares
    `gene_validity.classifications` and `gene_metrics.signature`, and no reference module carries a
    re-curated gene-validity claim or a row from the snapshot the second is about. Those stay declared
    and unlisted, and the gate has a *note* for a listed field a sweep did not see move.

    Derived from the records rather than a literal, so a future release joins by existing.
    """
    for version, record in RELEASE_RECORDS.items():
        listed = set(record.manifest_fields)
        additions = {
            change.target
            for change in record.declared
            if change.axis == "manifest_fields" and change.kind == "addition"
        }
        assert additions <= listed, f"{version}: declared as added but not listed: {additions - listed}"


def test_a_declared_change_names_an_axis_the_record_says_moved() -> None:
    """A declaration on an axis the measurement reports as still is a contradiction in the record."""
    for version, record in RELEASE_RECORDS.items():
        for change in record.declared:
            assert record.axes[change.axis] is True, f"{version} declares {change.target} on a still axis"


def test_an_unmeasured_module_is_named_in_the_prose_that_used_to_be_its_only_home() -> None:
    """RM139: the field the gate reads and the sentence a person reads must not drift apart.

    `evidence` carried the exclusion alone until the field existed, and prose the gate cannot read is
    how a real cut ended up waved through by hand. Two homes for one fact is the shape that goes
    blind, so the field is pinned to the sentence rather than left to be maintained beside it.
    """
    for version, record in RELEASE_RECORDS.items():
        assert record.unmeasured == sorted(set(record.unmeasured)), version
        for name in record.unmeasured:
            assert name in record.evidence, f"{version} excludes {name} in a field its prose omits"


def test_a_record_declaring_nothing_unmeasured_says_so_by_default() -> None:
    """The field is additive, so a record written before it existed reads as *nothing excluded*.

    That is the correct reading rather than a convenient one: the 0.6.1 and 0.6.6 records each state
    a denominator of sixteen over a sixteen-module corpus, so their silence and an empty list are the
    same claim. A record whose evidence names an exclusion is the one that must fill the field, which
    is what the test above holds it to.
    """
    bare = ReleaseRecord(
        version="9.9.9",
        previous="9.9.8",
        axes=dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False),
        evidence="a measured zero over every module",
    )
    assert bare.unmeasured == []


def test_every_shipped_record_chains_to_a_lower_release() -> None:
    """The chain is what composes an interval; a link that does not descend cannot be walked."""
    from just_dna_format.identity import parse_version

    for version, record in RELEASE_RECORDS.items():
        assert parse_version(record.previous) < parse_version(version), version


# ── the roster, and the condition that must ship with it ─────────────────────────────────────────


def _manifest_path_exists(path: str) -> bool:
    """Whether a dotted path resolves through the manifest models, block by block."""
    model = ModuleManifest
    *blocks, leaf = path.split(".")
    for block in blocks:
        field = model.model_fields.get(block)
        if field is None:
            return False
        model = next(
            (arg for arg in getattr(field.annotation, "__args__", (field.annotation,))
             if hasattr(arg, "model_fields")),
            None,
        )
        if model is None:
            return False
    return leaf in model.model_fields


def test_the_roster_names_only_fields_the_manifest_actually_has() -> None:
    """Walked against the models, so a manifest rename cannot leave the roster pointing at nothing."""
    assert AUTHORED_ROW_DERIVED_FIELDS
    unresolved = [entry.field for entry in AUTHORED_ROW_DERIVED_FIELDS
                  if not _manifest_path_exists(entry.field)]
    assert unresolved == []


def test_the_roster_publishes_its_condition_beside_every_conditional_entry() -> None:
    """S65's third constraint: a roster claiming *pure function of the authored rows* without the
    condition sends consumers to spend version numbers on modules that are current.

    The condition rides on the entry rather than sitting in prose two files away, and it names the
    counter that makes it checkable — `compilation.dropped_rows`, which shipped 2026-08-24.
    """
    conditional = [entry for entry in AUTHORED_ROW_DERIVED_FIELDS if entry.condition is not None]
    unconditional = [entry for entry in AUTHORED_ROW_DERIVED_FIELDS if entry.condition is None]

    assert conditional and unconditional, "both halves are real; a roster of one kind hides the split"
    assert {entry.condition for entry in conditional} == {DROPPED_ROWS_CONDITION}
    assert "dropped_rows" in DROPPED_ROWS_CONDITION
    assert {entry.field for entry in unconditional} == {"content_signature", "stats.study_count"}
    for entry in AUTHORED_ROW_DERIVED_FIELDS:
        assert entry.recompute.strip(), entry.field


def test_the_excluded_manifest_fields_each_carry_their_reason() -> None:
    """`compiler_version` is the trap and it is not hypothetical: it moves on every release by
    construction, so counting it would make every record fire on every module."""
    assert "compilation.compiler_version" in EXCLUDED_MANIFEST_FIELDS
    assert "compilation.warnings" in EXCLUDED_MANIFEST_FIELDS
    unresolved = [path for path in EXCLUDED_MANIFEST_FIELDS if not _manifest_path_exists(path)]
    assert unresolved == []
    for path, reason in EXCLUDED_MANIFEST_FIELDS.items():
        assert reason.strip(), path
    # Every field excluded because it is ROUTED to its own axis, asserted as an equality over the
    # walked registry rather than as a floor — a `<=` here passes unchanged when a fifth routed field
    # is added and answered by nobody, which is the one thing this guard exists to catch. The prose
    # also said "three" while four entries gave routing as their reason.
    routed = {path for path, reason in EXCLUDED_MANIFEST_FIELDS.items() if "routed" in reason.lower()}
    assert routed == {
        "content_signature",
        "artifact.digest",
        "artifact.files",
        "compilation.warnings",
        # RM131's two derived halves of the warnings channel. They move exactly when `warnings`
        # moves, so a release that only reworded a message would otherwise fire `manifest_fields`
        # three times over on every module in a catalogue.
        "compilation.carried",
        "compilation.warnings_summary",
    }


def test_a_record_that_leaves_an_axis_unanswered_is_refused() -> None:
    with pytest.raises(ValidationError, match="must name every release output axis"):
        ReleaseRecord(
            version="1.0.1",
            previous="1.0.0",
            axes={"parquet_bytes": True},
            evidence="incomplete on purpose",
        )


def test_a_record_may_answer_an_axis_unknown_without_answering_it_false() -> None:
    """A release that adds an axis cannot retroactively measure the ones before it."""
    axes: dict[str, bool | None] = dict.fromkeys(VALID_RELEASE_OUTPUT_AXES, False)
    axes["parquet_schema"] = None
    record = ReleaseRecord(version="1.0.1", previous="1.0.0", axes=axes, evidence="partial")
    answer = needs_recompile("1.0.0", "1.0.1", {"1.0.1": record})

    assert answer.axes["parquet_schema"] is None
    assert answer.axes["parquet_bytes"] is False
    assert answer.output_differs is None
