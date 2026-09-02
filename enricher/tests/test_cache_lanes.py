"""The cache registry, walked — RM176.

`CACHE_LANES` replaced a hand-kept four-tuple list in `cli.py`, and the reason is what these tests
assert. The list had drifted in the way a list does: three lanes with builders were simply not in it,
so `cache status` reported nine caches on a machine that has twelve, and `cache pull` refused the
other three as unknown names. Nothing anywhere could have noticed, because nothing compared the list
to the set of things it was a list *of*.

**So the premise here is an equality over a walked set** (`@registry-completeness`), never a count.
`assert len(CACHE_LANES) == 12` would pass while a lane was silently swapped for another and would
have to be edited every time the registry grew correctly — the exact counted-prose failure
`test_locations.py` records in its own walk. The sets walked are the `*_build` modules on disk and
the resolver family in `locations`.
"""

import inspect
from pathlib import Path

import pytest
from just_dna_enricher import caches, locations
from just_dna_enricher.caches import (
    CACHE_LANES,
    LANES_BY_NAME,
    RebuildOutcome,
    RebuildRequest,
    rebuild_lane,
)
from just_dna_enricher.cli import app
from typer.testing import CliRunner

_SRC = Path(caches.__file__).parent

#: The one lane with no builder in this tier. Named rather than counted, so that a *second* builderless
#: lane appearing has to be argued for here instead of slipping past an inequality.
_BUILT_ELSEWHERE = {"ensembl"}


def _builder_modules() -> set[str]:
    """Every `<lane>_build.py` in the package, as a lane name.

    `constraint_build` is the gnomAD constraint lane and `drug_labels_build` the regulator labels;
    both already spell their lane name, so the mapping is the filename with the suffix removed and no
    table of exceptions. A new builder whose module is named for something other than its lane will
    fail this and should be renamed rather than excepted.
    """
    return {p.name.removesuffix("_build.py") for p in _SRC.glob("*_build.py")}


def test_every_builder_module_has_a_lane_and_every_lane_but_one_has_a_builder() -> None:
    """The equality the old list could not state, in both directions.

    Left to right catches the defect that happened: `acmg_build`, `strchive_build` and
    `drug_labels_build` existed with no roster entry. Right to left catches its mirror — a lane kept
    in the registry after its builder was deleted, which would advertise a rebuild that cannot run.
    """
    lanes_with_builders = {lane.name for lane in CACHE_LANES if lane.rebuild is not None}
    assert _builder_modules() == lanes_with_builders

    assert {lane.name for lane in CACHE_LANES if lane.rebuild is None} == _BUILT_ELSEWHERE


def test_every_lane_resolves_through_the_locations_family() -> None:
    """A lane's `resolve` must be the module's real resolver, not a lambda that happens to type-check.

    Pinned as an identity comparison because the failure it guards is subtle: two lanes pointed at
    one resolver reports a snapshot present under both names, and `cache status` would look right.
    """
    for lane in CACHE_LANES:
        assert lane.resolve is getattr(locations, f"resolve_{lane.name}_reference"), lane.name
    assert len({lane.resolve for lane in CACHE_LANES}) == len(CACHE_LANES)


def test_every_lane_names_a_distinct_cache_subdirectory() -> None:
    """Two lanes sharing a subdirectory would have each overwrite the other's snapshot in one base."""
    subdirs = [lane.subdir for lane in CACHE_LANES]
    assert len(set(subdirs)) == len(subdirs), subdirs
    for lane in CACHE_LANES:
        assert lane.subdir == getattr(locations, f"{lane.name.upper()}_SUBDIR"), lane.name


def test_an_absent_stage_states_its_reason_and_a_present_one_does_not() -> None:
    """The biconditional, in both directions, for both absences.

    One direction is the defect the fields exist to prevent: an unpublishable lane whose reason lives
    only in a comment tells an operator nothing at the point they ask. The other is the defect that
    follows a repair — a lane that gains a publish command and keeps its excuse goes on telling
    people to build their own, which is worse than never having said it.
    """
    for lane in CACHE_LANES:
        assert (lane.unpublished is None) == (lane.ensure is not None), lane.name
        assert (lane.unbuilt is None) == (lane.rebuild is not None), lane.name
        if lane.name in _BUILT_ELSEWHERE:
            # Ensembl is pullable and has no `publish_repo`, and that is not the same defect: the
            # snapshot on HuggingFace is real, and just-dna-pipelines is what uploads it. The field
            # means "the repo THIS tier publishes to", so a lane this tier does not build cannot
            # have one — which is why the biconditional below is scoped to the lanes it builds.
            assert lane.publish_repo is None, lane.name
            continue
        # For every lane this tier does build, publishable is exactly pullable. The two halves are
        # the upload target and the download that follows it, and one without the other is a lane
        # that sends bytes nobody can fetch, or fetches bytes nobody sends.
        assert (lane.publish_repo is None) == (lane.ensure is None), lane.name


def test_the_licence_gated_lanes_are_the_ones_carrying_terms() -> None:
    """Derived from `licensing`, not restated: the gate `cache pull` applies comes from this field.

    ClinPGx's terms cover two archives — the annotation lane and the drug labels — so the same
    `SourceTerms` object appears twice, which is the point of comparing the *sources* rather than
    counting the lanes.
    """
    gated = {lane.name: lane.terms.source for lane in CACHE_LANES if lane.terms is not None}
    assert gated == {"clinpgx": "clinpgx", "cpic": "cpic", "drug_labels": "clinpgx",
                     "pharmvar": "pharmvar"}


def test_lanes_by_name_is_derived_from_the_registry() -> None:
    assert LANES_BY_NAME == {lane.name: lane for lane in CACHE_LANES}


def test_every_build_command_the_registry_names_is_one_the_cli_answers_to() -> None:
    """`cache status` interpolates this string, so it is an instruction and it has to be runnable.

    The defect this replaces was a composed one — `f"`{lane.name} build`"` — which is right for ten
    lanes and wrong for the two that do not follow the convention: there is no `drug_labels build`
    and no `constraint build`, and `cache status` printed both. A string a message hands an operator
    cannot come from a naming rule two members break (`@warning-text-is-api`).

    Walked against the real Typer tree rather than a list here, because a second list would have the
    same failure mode as the first.
    """
    runner = CliRunner()
    for lane in CACHE_LANES:
        if lane.build_command is None:
            assert lane.rebuild is None, f"{lane.name} can be rebuilt but names no command"
            continue
        result = runner.invoke(app, [*lane.build_command.split(), "--help"])
        assert result.exit_code == 0, f"`{lane.build_command}` is not a command: {result.output}"


# ── the rebuild endpoint ────────────────────────────────────────────────────────────────────────


def test_a_lane_that_cannot_run_unattended_is_not_a_failure(tmp_path: Path) -> None:
    """Three lanes land in the third state for three different reasons, and none of them is an error.

    Run through the real CLI rather than the adapters, because the thing under test is the exit code:
    a nightly rebuild that exited 1 because PharmVar needs a personal key would be reporting the
    licence working as designed.
    """
    result = CliRunner().invoke(
        app,
        ["cache", "rebuild", "--out", str(tmp_path), "--only", "acmg", "--only", "civic",
         "--only", "pharmvar", "--only", "ensembl"],
    )
    assert result.exit_code == 0, result.output
    printed = result.output + (result.stderr if result.stderr_bytes else "")
    assert "rebuilt 0, failed 0, not run 4" in printed
    for expected in ("workbook", "release date to pin", "forbids sale", "just-dna-pipelines"):
        assert expected in printed, printed


def test_the_out_base_gives_each_lane_its_own_directory(tmp_path: Path) -> None:
    """A rebuild never writes into the resolved cache, because a half-built snapshot is still a
    readable one — a short parquet has a footer and an `enrich` mid-flight would believe it."""
    for lane in CACHE_LANES:
        request = RebuildRequest(out_dir=tmp_path / lane.name)
        assert request.out_dir.parent == tmp_path
        assert request.out_dir.name == lane.name


def test_an_unknown_cache_name_is_refused_by_every_flag_that_takes_one(tmp_path: Path) -> None:
    """`--only`, `--pin` and `--source` all name a lane, so all three check the same registry.

    A flag validating against its own idea of the lane set is how one of them comes to accept a name
    the others reject; they share `_pairs`/`_selected` precisely so they cannot drift.
    """
    runner = CliRunner()
    for flag, value in (("--only", "nosuch"), ("--pin", "nosuch=1"), ("--source", "nosuch=/tmp/x")):
        result = runner.invoke(app, ["cache", "rebuild", "--out", str(tmp_path), flag, value])
        assert result.exit_code != 0, f"{flag} accepted an unknown lane"
        printed = result.output + (result.stderr if result.stderr_bytes else "")
        assert "nosuch" in printed


def test_a_pin_without_a_value_is_refused_rather_than_read_as_empty(tmp_path: Path) -> None:
    """`--pin mane=` would otherwise pin the empty string, which builds the moving default silently."""
    result = CliRunner().invoke(
        app, ["cache", "rebuild", "--out", str(tmp_path), "--pin", "mane="]
    )
    assert result.exit_code != 0
    printed = result.output + (result.stderr if result.stderr_bytes else "")
    assert "lane=value" in printed


def test_every_adapter_takes_a_request_and_returns_an_outcome() -> None:
    """The uniform signature is what lets `rebuild_lane` have no per-lane branches.

    Walked rather than spot-checked: an adapter with an extra keyword would work when called from its
    own test and fail in the loop, which is the failure a registry is supposed to make impossible.
    """
    for lane in CACHE_LANES:
        if lane.rebuild is None:
            continue
        signature = inspect.signature(lane.rebuild)
        assert list(signature.parameters) == ["request"], lane.name


def test_a_lane_with_no_builder_reports_the_reason_the_registry_carries(tmp_path: Path) -> None:
    ensembl = LANES_BY_NAME["ensembl"]
    outcome = rebuild_lane(ensembl, RebuildRequest(out_dir=tmp_path / "ensembl"))
    assert outcome == RebuildOutcome("ensembl", None, ensembl.unbuilt)
    assert outcome.label == "not run"


def test_a_local_catalogue_rebuilds_strchive_with_no_network(tmp_path: Path) -> None:
    """`--source` is the off-switch, and an off-switch needs its own probe (`@off-switch-needs-a-probe`).

    Reading the flag is not evidence it reaches the builder: the adapter could accept `source` and go
    on downloading, and every test that only checked the flag parsed would pass. So this one runs the
    real build from the repository's own catalogue slice, offline, and asserts the snapshot on disk.
    """
    slice_file = Path(__file__).resolve().parents[2] / "assets" / "strchive_loci_slice.json"
    outcome = rebuild_lane(
        LANES_BY_NAME["strchive"],
        RebuildRequest(out_dir=tmp_path / "strchive", source=slice_file, pin="v0.0.1"),
    )
    assert outcome.built is True, outcome.detail
    assert (tmp_path / "strchive" / locations.STRCHIVE_CATALOGUE_FILENAME).is_file()
    assert "strchive_v0.0.1" in outcome.detail


def test_an_unpinned_strchive_build_is_built_and_says_it_cannot_name_its_release(
    tmp_path: Path,
) -> None:
    """Built, not failed — and the thing it cannot do is stated rather than papered over.

    The catalogue is usable without a pin; what a reader loses is the ability to say which release a
    comparison ran against, which is a property of the snapshot and not an error in this run.
    """
    slice_file = Path(__file__).resolve().parents[2] / "assets" / "strchive_loci_slice.json"
    outcome = rebuild_lane(
        LANES_BY_NAME["strchive"], RebuildRequest(out_dir=tmp_path / "s", source=slice_file),
    )
    assert outcome.built is True
    assert "unlabelled" in outcome.detail


@pytest.mark.parametrize("lane_name", ["mane", "civic"])
def test_the_three_file_lanes_refuse_a_single_source_rather_than_half_using_it(
    lane_name: str, tmp_path: Path,
) -> None:
    """Two of three is not a build for either, so `--source` is refused instead of partly honoured."""
    outcome = rebuild_lane(
        LANES_BY_NAME[lane_name],
        RebuildRequest(out_dir=tmp_path / lane_name, source=tmp_path / "one.txt", pin="1.5"),
    )
    assert outcome.built is None
    assert "three" in outcome.detail
