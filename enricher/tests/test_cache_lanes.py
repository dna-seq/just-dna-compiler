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

import dataclasses
import inspect
import json
from pathlib import Path

import pytest
from just_dna_enricher import caches, locations, pharmvar
from just_dna_enricher.acmg import load_acmg_snapshot
from just_dna_enricher.caches import (
    CACHE_LANES,
    LANES_BY_NAME,
    RebuildOutcome,
    RebuildRequest,
    rebuild_lane,
)
from just_dna_enricher.cli import app
from just_dna_enricher.clinvar import clinvar_dataset_label
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



def _unwrapped(result) -> str:
    """A Typer/Rich result's text with its box drawing and line wrapping collapsed to single spaces."""
    raw = result.output + (result.stderr if result.stderr_bytes else "")
    stripped = "".join(" " if ch in "\u2502\u2500\u256d\u256e\u256f\u2570\n" else ch for ch in raw)
    return " ".join(stripped.split())

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


def test_every_lane_pairs_its_resolver_with_the_matching_default_directory() -> None:
    """`prepare` *writes* to `default_dir`, so a lane pointing at another's would provision over it.

    `resolve` cannot answer this question — it returns `None` for an absent cache, and an absent
    cache is exactly the case provisioning exists for — so the directory is its own field and is
    checked the way the resolver already is: identity against the `locations` function, and
    distinctness across the registry.
    """
    for lane in CACHE_LANES:
        assert lane.default_dir is getattr(locations, f"default_{lane.name}_cache_dir"), lane.name
    assert len({lane.default_dir for lane in CACHE_LANES}) == len(CACHE_LANES)


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


def test_every_lane_can_name_the_release_its_snapshot_holds(tmp_path: Path) -> None:
    """Walked, because the defect was one lane silently answering nothing (RM180).

    `cache status` read `release.json`'s `dataset` for every lane. Eleven write it; ClinVar writes
    `clinvar_file_date` instead, so the fastest-moving snapshot in the registry was the one printing a
    blank release while every slower one printed its own. A per-lane reader fixes it, and this asserts
    the property over the whole registry rather than over the lane that happened to be wrong.
    """
    for lane in CACHE_LANES:
        directory = tmp_path / lane.name
        directory.mkdir()
        (directory / locations.RELEASE_FILENAME).write_text(
            json.dumps({"dataset": f"{lane.name}_2026-09-03", "clinvar_file_date": "2026-08-29"}),
            encoding="utf-8",
        )
        assert lane.release_label(directory) is not None, lane.name
        # …and an unlabelled snapshot withholds rather than inventing one
        bare = tmp_path / f"{lane.name}-bare"
        bare.mkdir()
        assert lane.release_label(bare) is None, lane.name


def test_the_lane_that_reads_its_release_differently_is_exactly_the_one_named() -> None:
    """The exception is enumerated, so it cannot quietly grow — the shape `build_command` needed.

    A second lane that stops writing `dataset` should have to say so here rather than start printing
    a blank label, which is how this one went unnoticed.
    """
    from just_dna_enricher.caches import _dataset_label

    overridden = {lane.name for lane in CACHE_LANES if lane.release_label is not _dataset_label}
    assert overridden == {"clinvar"}


def test_the_clinvar_label_is_the_one_the_drafter_writes(tmp_path: Path) -> None:
    """Shared rather than mirrored: two spellings of one label never match, and never fail either."""
    directory = tmp_path / "clinvar"
    directory.mkdir()
    (directory / locations.RELEASE_FILENAME).write_text(
        json.dumps({"clinvar_file_date": "2026-08-29", "record_count": 4460499}), encoding="utf-8",
    )
    lane = LANES_BY_NAME["clinvar"]
    assert lane.release_label(directory) == clinvar_dataset_label(directory)
    assert lane.release_label(directory) == "clinvar_2026-08-29"


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


def test_a_lane_that_cannot_run_unattended_is_not_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Four lanes land in the third state for four different reasons, and none of them is an error.

    Run through the real CLI rather than the adapters, because the thing under test is the exit code:
    a nightly rebuild that exited 1 because PharmVar needs a personal key would be reporting the
    licence working as designed.

    `_checkout_assets` is emptied because this suite runs *inside* the checkout, which now supplies
    the ACMG workbook by default — so without this the lane builds and the case under test is one
    short. That is the state a plain `pip install` is in, and the one this lane's message is written
    for.
    """
    monkeypatch.setattr(caches, "_checkout_assets", list)
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


def test_a_relative_source_path_builds_rather_than_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Path("./x.xlsx").as_uri()` raises, and a relative path is what an operator types.

    The documented invocation is `--source acmg=./acmg_sf_v3.3.xlsx`, so the documented one was the
    one that produced a traceback instead of an outcome. Run from a directory holding the workbook,
    which is the shape of the failure rather than a reconstruction of it.
    """
    pytest.importorskip("openpyxl")
    workbook = Path(__file__).resolve().parents[2] / "assets" / "acmg_sf_v3.3.xlsx"
    staged = tmp_path / workbook.name
    staged.write_bytes(workbook.read_bytes())
    monkeypatch.chdir(tmp_path)

    outcome = rebuild_lane(
        LANES_BY_NAME["acmg"],
        RebuildRequest(out_dir=Path("out") / "acmg", source=Path("./" + workbook.name)),
    )
    assert outcome.built is True, outcome.detail
    assert (tmp_path / "out" / "acmg" / locations.ACMG_SNAPSHOT_FILENAME).is_file()


def test_pharmvar_separates_no_key_from_a_key_that_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No key is the designed third state; a configured key that then fails is asked-and-failed.

    PharmVar has one flat error class and its 401 is identical for an absent, a malformed and an
    unrecognised key, so the split cannot come from the exception — it is decided before the request.
    Folding the second case into *not run* would leave a nightly rebuild quiet about a broken lane
    (`@answered-is-not-absent`). The empty string rather than `delenv`, because a `.env` refills a
    deleted variable and a real one still wins (`@test-no-credential`).
    """
    monkeypatch.setenv(pharmvar.API_KEY_ENV, "")
    no_key = rebuild_lane(
        LANES_BY_NAME["pharmvar"],
        RebuildRequest(out_dir=tmp_path / "p", declared_use="non-commercial"),
    )
    assert no_key.built is None
    assert pharmvar.API_KEY_ENV in no_key.detail

    monkeypatch.setenv(pharmvar.API_KEY_ENV, "a-key-that-will-not-work")
    monkeypatch.setattr(
        caches.pharmvar_build, "build_snapshot",
        lambda *a, **k: (_ for _ in ()).throw(pharmvar.PharmVarError("PharmVar rejected the key")),
    )
    with_key = rebuild_lane(
        LANES_BY_NAME["pharmvar"],
        RebuildRequest(out_dir=tmp_path / "q", declared_use="non-commercial"),
    )
    assert with_key.built is False, "a key that fails is a failure, not a lane opting out"


def test_the_civic_adapter_takes_the_same_three_files_the_per_lane_command_does() -> None:
    """One release must not build two different snapshots depending on which caller asked.

    RM169 made `--submitted` opt-in because the release VCF *widens the status basis*: it admits
    submitted-but-not-accepted evidence. An adapter fetching it unconditionally would make
    `cache rebuild --pin civic=X` and `civic build --release X` two artifacts from one release, which
    is the fork this endpoint exists to prevent. Asserted on the source rather than by running a
    build, because the alternative is four network fetches.
    """
    source = inspect.getsource(caches._rebuild_civic)
    assert "CIVIC_VCF_FILE" not in source
    assert "status_basis" in source, "and the outcome prints the basis, so a divergence is visible"


def test_a_source_path_that_does_not_exist_is_refused_before_anything_downloads(
    tmp_path: Path,
) -> None:
    """A typo in an operator-supplied path must not cost a full run first.

    `--source acmg=<workbook>` is a path, and typer's `exists=True` cannot reach a value embedded in
    a `lane=value` string — so a mistyped one used to travel all the way to the lane's builder and
    surface as a bare `[Errno 2] No such file or directory` **after** every lane before it had
    downloaded. ACMG is last in the registry, so that is the whole run (`@specific-rejection`: a
    generic rejection is a dead end where a specific one is a fix).
    """
    result = CliRunner().invoke(
        app,
        ["cache", "rebuild", "--out", str(tmp_path), "--only", "acmg",
         "--source", f"acmg={tmp_path / 'nope.xlsx'}"],
    )
    assert result.exit_code != 0
    # Rich wraps the refusal inside a box, so a phrase is split across lines by border characters at
    # a width nobody chose. The text is normalized before it is matched — pinning a message against
    # its own line-wrapping tests the terminal width, not the message (`@warning-text-is-api` is
    # about the words).
    printed = _unwrapped(result)
    assert "not a readable file" in printed
    assert "nothing will fetch it" in printed


def test_a_source_path_may_be_written_with_a_tilde(tmp_path: Path) -> None:
    """`--source acmg=~/x.xlsx` puts the tilde inside an assignment, where no shell expands it.

    So the CLI expands it, at the check and again where the path is used — a validation that
    expanded and a build that did not would refuse a good path or accept a bad one, depending which
    way round the omission fell.
    """
    workbook = Path(__file__).resolve().parents[2] / "assets" / "acmg_sf_v3.3.xlsx"
    staged = tmp_path / "home" / "acmg.xlsx"
    staged.parent.mkdir()
    staged.write_bytes(workbook.read_bytes())

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["cache", "rebuild", "--out", str(tmp_path / "out"), "--only", "acmg",
         "--source", "acmg=~/acmg.xlsx"],
        env={"HOME": str(staged.parent)},
    )
    assert "not a readable file" not in _unwrapped(result), result.output


# ── the ACMG workbook the checkout already carries ──────────────────────────────────────────────


def test_the_checkouts_own_workbook_is_used_when_nobody_names_one(tmp_path: Path) -> None:
    """The lane's input ships in `assets/`, so a checkout should not have to be told where it is.

    Asserted on the built snapshot rather than on the message: the point is that a real workbook was
    read, and the version comes off the file rather than out of this test.
    """
    outcome = rebuild_lane(LANES_BY_NAME["acmg"], RebuildRequest(out_dir=tmp_path / "acmg"))
    assert outcome.built is True, outcome.detail
    listed = load_acmg_snapshot(tmp_path / "acmg")
    assert listed.version and listed.genes
    assert listed.version in outcome.detail


def test_a_named_workbook_still_outranks_the_checkouts(tmp_path: Path) -> None:
    """`--source` is explicit and explicit always wins — the default fills the *unset* case only."""
    workbook = Path(__file__).resolve().parents[2] / "assets" / "acmg_sf_v3.3.xlsx"
    copied = tmp_path / "mine.xlsx"
    copied.write_bytes(workbook.read_bytes())
    outcome = rebuild_lane(
        LANES_BY_NAME["acmg"], RebuildRequest(out_dir=tmp_path / "acmg", source=copied),
    )
    assert outcome.built is True, outcome.detail
    assert "mine.xlsx" in outcome.detail


def test_two_workbooks_are_reported_rather_than_ordered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A directory with v3.3 and v3.4 has two answers and nothing orders them.

    "The highest version" is an ordering somebody would have to define, and filename sort is not it —
    a v3.10 would sort below v3.4. So several is reported like none, naming them, and the operator
    says which (`@multiplicity-is-a-finding`).
    """
    assets = tmp_path / "assets"
    assets.mkdir()
    real = Path(__file__).resolve().parents[2] / "assets" / "acmg_sf_v3.3.xlsx"
    for name in ("acmg_sf_v3.3.xlsx", "acmg_sf_v3.4.xlsx"):
        (assets / name).write_bytes(real.read_bytes())
    monkeypatch.setattr(caches, "_checkout_assets", lambda: [assets])

    outcome = rebuild_lane(LANES_BY_NAME["acmg"], RebuildRequest(out_dir=tmp_path / "acmg"))
    assert outcome.built is None, "picking one would be an ordering nobody defined"
    assert "acmg_sf_v3.3.xlsx" in outcome.detail and "acmg_sf_v3.4.xlsx" in outcome.detail


def test_no_checkout_falls_back_to_the_operator_supplied_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`assets/` is deliberately not in the wheel, so a plain install must still say what it needs.

    The workbook is ACMG/Elsevier supplementary material and shipping it in a published package is
    the redistribution question this lane's registry entry records as unestablished — so the default
    is a convenience for a checkout and never a promise the package makes.
    """
    monkeypatch.setattr(caches, "_checkout_assets", list)
    outcome = rebuild_lane(LANES_BY_NAME["acmg"], RebuildRequest(out_dir=tmp_path / "acmg"))
    assert outcome.built is None
    assert "--source acmg=" in outcome.detail


def test_the_glob_is_not_pinned_to_one_version() -> None:
    """v3.2 → v3.3 happened in June 2025 and v3.4 will happen too.

    A constant naming today's file stops finding the asset the day the next one lands, silently, and
    the silence falls in the direction that scrapes NCBI's stale page.
    """
    assert "v*" in caches.ACMG_WORKBOOK_GLOB
    assert caches.ACMG_WORKBOOK_GLOB.endswith(".xlsx")


# ── prepare: pull what is published, build what is not ──────────────────────────────────────────


def test_prepare_picks_each_lanes_route_from_the_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The routing rule, asserted over the whole registry rather than sampled.

    A lane with an `ensure` pulls; one without it builds, because it is unpublished for a recorded
    reason and building is the only route there will ever be. Neither leg is exercised here — both
    are stubbed — because the thing under test is *which* one each lane takes, and running them would
    make this a network test that also happens to check the routing.
    """
    pulled: list[str] = []
    built: list[str] = []
    def stub_build(lane, req):
        built.append(lane.name)
        req.out_dir.mkdir(parents=True, exist_ok=True)   # a real builder writes; so does this one
        return caches.RebuildOutcome(lane.name, True, "stub", req.out_dir)

    monkeypatch.setattr(caches, "rebuild_lane", stub_build)
    lanes = []
    for lane in CACHE_LANES:
        base = tmp_path / lane.name
        stub_ensure = None
        if lane.ensure is not None:
            def stub_ensure(_name=lane.name, _base=base):  # noqa: ANN001 - bound per lane
                pulled.append(_name)
                _base.mkdir(parents=True, exist_ok=True)
                return _base
        lanes.append(dataclasses.replace(
            lane,
            ensure=stub_ensure,
            resolve=lambda: None,
            default_dir=lambda _base=base: _base,
            terms=None,
        ))
    outcomes = caches.prepare_caches(lanes)

    by_name = {o.lane: o for o in outcomes}
    for lane in CACHE_LANES:
        expected = "pulled" if lane.ensure is not None else ("built" if lane.rebuild else "none")
        assert by_name[lane.name].route == expected, lane.name
    assert set(pulled) == {x.name for x in CACHE_LANES if x.ensure is not None}
    assert set(built) == {
        x.name for x in CACHE_LANES if x.ensure is None and x.rebuild is not None
    }


def test_prepare_leaves_a_present_cache_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Idempotent and cheap to re-run, like `cache pull` — and for a sharper reason.

    Re-deriving a snapshot something may be reading is how a resolver comes to see a half-written
    table, and a short parquet still has a footer. Re-cutting one is `cache rebuild`, which writes
    somewhere else on purpose.
    """
    touched: list[str] = []
    lane = dataclasses.replace(
        LANES_BY_NAME["strchive"],
        resolve=lambda: tmp_path / "already-here",
        ensure=lambda: touched.append("pulled") or tmp_path,
        default_dir=lambda: tmp_path / "already-here",
    )
    monkeypatch.setattr(caches, "rebuild_lane", lambda *a, **k: touched.append("built"))
    outcome = caches.prepare_lane(lane, RebuildRequest(out_dir=tmp_path))
    assert outcome.route == "present" and outcome.ready is True
    assert touched == [], "a present cache must cost neither a download nor a build"


def test_a_built_lane_is_staged_and_moved_rather_than_written_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The build target is never the live directory while the build is running.

    The resolvers read by globbing, so a build writing straight into the cache is visible half-done —
    and unlike a truncated download there is no footer check to catch it, because the file is real.
    Asserted on where the builder was *pointed*, which is the property; the move is then observable
    from the outside.
    """
    target = tmp_path / "acmg_sf"
    pointed: list[Path] = []

    def fake_rebuild(lane, request):
        pointed.append(request.out_dir)
        request.out_dir.mkdir(parents=True, exist_ok=True)
        (request.out_dir / "acmg_sf.csv").write_text("gene\n", encoding="utf-8")
        return caches.RebuildOutcome(lane.name, True, "stub", request.out_dir)

    monkeypatch.setattr(caches, "rebuild_lane", fake_rebuild)
    lane = dataclasses.replace(
        LANES_BY_NAME["acmg"], resolve=lambda: None, default_dir=lambda: target,
    )
    outcome = caches.prepare_lane(lane, RebuildRequest(out_dir=target))

    assert pointed == [target.parent / "acmg_sf.incoming"], "built into the live directory"
    assert outcome.ready is True and outcome.route == "built"
    assert (target / "acmg_sf.csv").is_file()
    assert not (target.parent / "acmg_sf.incoming").exists(), "the staging directory is not left behind"


def test_a_failed_build_leaves_no_half_snapshot_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lane that fails must not leave a directory a later `cache status` calls present."""
    target = tmp_path / "acmg_sf"

    def failing(lane, request):
        request.out_dir.mkdir(parents=True, exist_ok=True)
        (request.out_dir / "acmg_sf.csv").write_text("half\n", encoding="utf-8")
        return caches.RebuildOutcome(lane.name, False, "the source went away")

    monkeypatch.setattr(caches, "rebuild_lane", failing)
    lane = dataclasses.replace(
        LANES_BY_NAME["acmg"], resolve=lambda: None, default_dir=lambda: target,
    )
    outcome = caches.prepare_lane(lane, RebuildRequest(out_dir=target))
    assert outcome.ready is False
    assert not target.exists()
    assert not (target.parent / "acmg_sf.incoming").exists()


def test_a_repo_nobody_has_published_is_unavailable_rather_than_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`prepare`'s job is to leave the machine usable, and an unpublished repo is a fact about the
    world that no retry changes — so it is the third state, and the exit code stays clean."""
    def unpublished():
        raise caches.SnapshotNotPublished("nothing at datasets/x/data")

    lane = dataclasses.replace(
        LANES_BY_NAME["civic"], resolve=lambda: None, ensure=unpublished,
        default_dir=lambda: tmp_path / "civic",
    )
    outcome = caches.prepare_lane(lane, RebuildRequest(out_dir=tmp_path / "civic"))
    assert outcome.ready is None
    assert "nothing published yet" in outcome.detail


def test_a_gated_lane_is_skipped_when_no_use_is_declared(tmp_path: Path) -> None:
    """Downloading is taking the data, so the terms are accepted here exactly as in `cache pull`."""
    lane = dataclasses.replace(
        LANES_BY_NAME["cpic"], resolve=lambda: None,
        ensure=lambda: pytest.fail("the gate did not run before the download"),
        default_dir=lambda: tmp_path / "cpic",
    )
    outcome = caches.prepare_lane(lane, RebuildRequest(out_dir=tmp_path / "cpic"))
    assert outcome.ready is None and "skipped" in outcome.detail


def test_rebuild_caches_and_prepare_caches_are_the_cli_loops(tmp_path: Path) -> None:
    """Both commands call these, so a caller in Python gets the routing rather than re-deriving it.

    Walked over the registry: the pairing that matters is one outcome per lane, in registry order, so
    a caller can zip the result against `CACHE_LANES` without matching on names.
    """
    prepared = caches.prepare_caches([LANES_BY_NAME["ensembl"]])
    assert [o.lane for o in prepared] == ["ensembl"]

    rebuilt = caches.rebuild_caches([LANES_BY_NAME["ensembl"]], out=tmp_path)
    assert [o.lane for o in rebuilt] == ["ensembl"]
    assert rebuilt[0].built is None, "ensembl is built by just-dna-pipelines, not here"


def test_a_builder_that_writes_nothing_is_a_failure_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`built is True` has to mean a snapshot exists, and this is where that is established.

    Without the check the move raises a raw `FileNotFoundError` naming a staging path the operator
    has never heard of — a generic rejection where a specific one is a fix.
    """
    monkeypatch.setattr(
        caches, "rebuild_lane",
        lambda lane, req: caches.RebuildOutcome(lane.name, True, "claimed success", req.out_dir),
    )
    lane = dataclasses.replace(
        LANES_BY_NAME["acmg"], resolve=lambda: None, default_dir=lambda: tmp_path / "acmg_sf",
    )
    outcome = caches.prepare_lane(lane, RebuildRequest(out_dir=tmp_path / "acmg_sf"))
    assert outcome.ready is False
    assert "wrote nothing" in outcome.detail
