"""The enrichment run as a transaction: staged answers, an advisory lock, progress, `rederive`.

Network-free. The live Ensembl link is a stub resolver injected the way `resolver=` exists to allow,
so "the source answered" and "the process died mid-run" are both things a test can produce exactly.
Every run here disables the passes that would reach a sequence service or dbSNP — this file is about
durability, not about the checks, and a pass that egresses would make the assertions non-deterministic
as well as breaking the suite's opt-in-network rule.
"""

import csv
import logging
import shutil
from pathlib import Path

import pytest
from just_dna_enricher import transaction
from just_dna_enricher.enrich import EnrichmentError, _write_resolution_csv, enrich
from just_dna_enricher.licensing import resolution_authority
from just_dna_enricher.transaction import (
    LOCK_HELD_MESSAGE,
    LOCK_TARGET_MESSAGE,
    ResolutionJournal,
    SubjectProgress,
    spec_lock,
    staging_dir_for,
)
from just_dna_format.layout import SOURCES_CSV, preferred_spelling
from just_dna_format.resolution import ResolutionRow

#: The licence sidecar's current filename, derived rather than named: it has two spellings and the
#: preferred one is `licensing.csv`, so a literal `sources.csv` here would assert the absence of a file
#: nothing writes — a test that passes without discriminating.
_LICENCE_CSV = preferred_spelling(SOURCES_CSV)

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)

#: Three subjects, all rsid-only, so every one of them reaches the live link and nothing resolves off
#: an authored coordinate. Deliberate: a subject the chain never asks about cannot be journaled, and a
#: fixture full of those would let a broken journal still pass every assertion below.
_VARIANTS = (
    "rsid,genotype,state,conclusion\n"
    "rs1801133,A/G,risk,c\n"
    "rs429358,C/T,risk,c\n"
    "rs7412,C/T,risk,c\n"
)

#: What the stub resolver answers for each rsid — one locus each, distinct positions.
_ANSWERS: dict[str, list[dict]] = {
    "rs1801133": [{"chrom": "1", "start": 11856377, "ref": "G", "alts": "A"}],
    "rs429358": [{"chrom": "19", "start": 44908684, "ref": "T", "alts": "C"}],
    "rs7412": [{"chrom": "19", "start": 44908822, "ref": "C", "alts": "T"}],
}


class _StubResolver:
    """A live-Ensembl stand-in that answers from `_ANSWERS`, and can die or refuse on cue.

    `die_after` reproduces the incident: the process is killed once the source has answered some of
    the subjects and before the table is written. `refuse` is the discriminating half of the resume
    test — a resumed run that re-asks about a journaled rsid fails loudly instead of quietly costing
    the thirty minutes again.
    """

    def __init__(self, *, die_after: int | None = None, refuse: frozenset[str] = frozenset()) -> None:
        self.die_after = die_after
        self.refuse = refuse
        self.asked: list[str] = []

    def resolve_rsid(self, rsid: str) -> tuple[list[dict] | None, str | None]:
        if rsid in self.refuse:
            raise AssertionError(f"{rsid} was already staged and must not be asked again")
        self.asked.append(rsid)
        if self.die_after is not None and len(self.asked) > self.die_after:
            raise _Killed(f"killed after {self.die_after} answer(s)")
        return _ANSWERS.get(rsid, []), "ensembl-rest"

    def close(self) -> None:
        return None


class _UnreachableFor(_StubResolver):
    """A resolver that answers normally except for one rsid it cannot be asked about at all.

    `resolve_rsid` returning `None` is the live link's third outcome — could not ask, as distinct from
    an empty answer — and it is the state that makes an un-asked subject reach the carry-forward.
    """

    def __init__(self, rsid: str) -> None:
        super().__init__()
        self.unreachable = rsid

    def resolve_rsid(self, rsid: str) -> tuple[list[dict] | None, str | None]:
        if rsid == self.unreachable:
            self.asked.append(rsid)
            return None, None
        return super().resolve_rsid(rsid)


class _Revised(_StubResolver):
    """A source that has since changed its answer for one rsid — the thing `--rederive` exists to find."""

    def __init__(self, rsid: str, start: int) -> None:
        super().__init__()
        self.revised = rsid
        self.start = start

    def resolve_rsid(self, rsid: str) -> tuple[list[dict] | None, str | None]:
        loci, source = super().resolve_rsid(rsid)
        if rsid == self.revised and loci:
            return [{**loci[0], "start": self.start}], source
        return loci, source


class _Killed(RuntimeError):
    """Stands in for the process dying mid-run: it escapes `enrich` exactly as a kill would."""


def _spec(directory: Path, variants: str = _VARIANTS) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (directory / "variants.csv").write_text(variants, encoding="utf-8")
    return directory


def _run(spec: Path, tmp_path: Path, **kwargs):
    """`enrich` with every network-touching pass off and no cache to find. See the module docstring."""
    defaults = {
        "ensembl_cache": tmp_path / "no-ensembl-cache",
        "clinvar_cache": tmp_path / "no-clinvar-cache",
        "download": False,
        "use_gnomad": False,
        "mint_vrs": False,
        "verify_ref": False,
        "verify_clinsig": False,
        "verify_rsids": False,
    }
    defaults.update(kwargs)
    return enrich(spec, **defaults)


def _table(spec: Path) -> Path:
    return spec / "resolution.csv"


# ── the transaction: staging, resume, and what a refusal commits ────────────────────────────────


def test_a_run_resumed_after_a_kill_produces_the_table_an_uninterrupted_run_produces(
    tmp_path: Path,
) -> None:
    """P7's shape for this item: the transaction may recover work, never change the answer.

    The kill lands after one rsid has been answered, so the staged file is the only thing carrying it
    when the second run starts — and that run is given a resolver that raises if it is asked about the
    staged rsid, which is what makes the test discriminate. Without the journal the second run either
    re-asks (and the resolver fails the test) or resolves less (and the bytes differ).
    """
    whole = _spec(tmp_path / "whole")
    _run(whole, tmp_path, resolver=_StubResolver())
    expected = _table(whole).read_bytes()

    interrupted = _spec(tmp_path / "interrupted")
    killer = _StubResolver(die_after=1)
    with pytest.raises(_Killed):
        _run(interrupted, tmp_path, resolver=killer)
    assert not _table(interrupted).exists(), "the killed run committed a table"
    assert staging_dir_for(_table(interrupted)).exists(), "the killed run staged nothing"

    answered = killer.asked[0]
    resumed = _StubResolver(refuse=frozenset({answered}))
    _run(interrupted, tmp_path, resolver=resumed)

    assert _table(interrupted).read_bytes() == expected
    # The saving is the point, not a side effect: the one subject the source had already answered was
    # not asked again, and every other one was.
    assert set(resumed.asked) == set(_ANSWERS) - {answered}


def test_a_strict_refusal_commits_nothing_and_leaves_the_staged_work_behind(tmp_path: Path) -> None:
    """The promise the item was really about, asserted on the bytes on disk rather than on a return.

    A pre-existing table is what makes it discriminate: "the file is absent" would pass for a run that
    wrote nothing *and* for one that wrote and then failed to clean up. Here the module already has a
    table, and after the refusal it must be the same bytes it was before.
    """
    spec = _spec(
        tmp_path / "spec",
        "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\nrs7412,C/T,risk,c\nrs999,A/G,risk,c\n",
    )
    _write_recorded(spec, [_recorded("rs1801133", "1", 11856377, "G", "A")])
    before = _table(spec).read_bytes()

    with pytest.raises(EnrichmentError, match="strict enrichment"):
        _run(spec, tmp_path, mode="strict", resolver=_StubResolver())

    assert _table(spec).read_bytes() == before
    assert not (spec / "verification.json").exists()
    assert not (spec / _LICENCE_CSV).exists()
    # Staged, though — a refusal is not a reason to throw the answers away, and the next run resumes.
    assert staging_dir_for(_table(spec)).exists()


def test_the_staging_directory_is_a_sibling_of_the_table_it_stages(tmp_path: Path) -> None:
    """The cross-device property, asserted structurally rather than trusted from a docstring.

    `os.replace` is atomic only within one filesystem; a tempdir may be on another one, where the move
    degrades to copy-then-delete and stops being atomic. Staging beside the target makes that
    impossible rather than merely avoided, so the relationship is the invariant — checked on a
    contrived path *and* on the directory a real run actually creates.
    """
    for target in (Path("/a/b/resolution.csv"), Path("derived/resolution.csv"), tmp_path / "r.csv"):
        assert staging_dir_for(target).parent == target.parent

    spec = _spec(tmp_path / "spec")
    _run(spec, tmp_path, resolver=_StubResolver(), keep_staging=True)
    staged = staging_dir_for(_table(spec))
    assert staged.exists()
    assert staged.parent == _table(spec).parent


def test_keep_staging_removes_the_staged_answers_when_it_is_off_and_keeps_them_when_it_is_on(
    tmp_path: Path,
) -> None:
    """Both values of the knob, because a flag the callee never sees is a flag that does nothing.

    The disabling value is the default, so the off case is the one that would rot unnoticed: a run
    that quietly kept its staging files forever would look identical to a correct one until the
    directory filled up.
    """
    kept = _spec(tmp_path / "kept")
    _run(kept, tmp_path, resolver=_StubResolver(), keep_staging=True)
    assert staging_dir_for(_table(kept)).exists()
    # A committed run writes all three artifacts, which is what makes the refusal test's assertions
    # about their absence discriminate rather than pass on a file nothing ever creates.
    assert (kept / "verification.json").exists()
    assert (kept / _LICENCE_CSV).exists()

    removed = _spec(tmp_path / "removed")
    _run(removed, tmp_path, resolver=_StubResolver(), keep_staging=False)
    assert not staging_dir_for(_table(removed)).exists()
    assert _table(removed).read_bytes() == _table(kept).read_bytes()


def test_a_resume_with_nothing_left_to_ask_still_commits(tmp_path: Path) -> None:
    """The run with nothing to do is a path. Every subject is already staged, so no link has anything
    left to ask — and a transaction that only committed when it had asked something would leave the
    table unwritten on exactly the run that finishes an interrupted one."""
    spec = _spec(tmp_path / "spec")
    staged = ResolutionJournal(_table(spec), genome_build="GRCh38")
    for rsid, loci in _ANSWERS.items():
        staged.record(rsid, "ensembl-rest", loci)

    result = _run(spec, tmp_path, resolver=_StubResolver(refuse=frozenset(_ANSWERS)))

    assert result.unresolved == []
    assert _table(spec).exists()


def test_a_resume_drops_a_staged_answer_from_a_link_this_run_has_switched_off(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A resume must reproduce the run its own flags describe, not the run that was killed.

    gnomAD reports only the alleles observed **in gnomAD**, which is why the link goes last; honouring
    a staged gnomAD answer on a `--no-gnomad` run would stamp a `source="gnomad"` row a first run with
    those flags could never have written — and `alts` is a fact column, so it would move the compiled
    digest too.
    """
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\n")
    staged = ResolutionJournal(_table(spec), genome_build="GRCh38")
    # Hostable by the authored `A/G`, so the test turns on the link gate alone rather than on
    # the allele filter quietly dropping the locus for an unrelated reason.
    staged.record("rs1801133", "gnomad", [{"chrom": "1", "start": 42, "ref": "G", "alts": "A"}])

    stub = _StubResolver()
    with caplog.at_level(logging.INFO):
        result = _run(spec, tmp_path, use_gnomad=False, resolver=stub)

    assert "switched off this run" in caplog.text
    row = next(r for r in result.rows if r.rsid == "rs1801133")
    assert row.source != "gnomad"
    assert row.start == _ANSWERS["rs1801133"][0]["start"]   # the live link was asked instead
    assert "rs1801133" in stub.asked


def test_a_rederivation_does_not_seed_from_a_gap_filling_run_s_staged_answers(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A re-derivation resumes only another re-derivation, and this is the reason.

    After a gap-filling run commits, its staged answers are exactly what produced the recorded table.
    A later `--rederive` seeded from them would compare that table against its own provenance and
    report a clean bill for precisely the subjects it was asked to re-check — the canary, silenced by
    a file left behind for debugging.
    """
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\n")
    _run(spec, tmp_path, resolver=_StubResolver(), keep_staging=True)
    assert staging_dir_for(_table(spec)).exists()

    with caplog.at_level(logging.WARNING):
        result = _run(spec, tmp_path, resolver=_Revised("rs1801133", 11863052), rederive=True)

    assert [d.variant_key for d in result.rederived] == ["rs1801133"]
    assert next(r for r in result.rows if r.rsid == "rs1801133").start == 11863052
    assert "now answer differently from the recorded table" in caplog.text


def test_staged_answers_recorded_under_another_build_are_ignored_rather_than_seeded(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A coordinate is valid on either assembly; it is simply a different base.

    Nothing downstream can detect a GRCh37 position recorded as this module's own, which is why the
    journal carries the build it was written under and a mismatch is discarded whole.
    """
    spec = _spec(tmp_path / "spec")
    foreign = ResolutionJournal(_table(spec), genome_build="GRCh37")
    foreign.record("rs1801133", "ensembl-rest", [{"chrom": "1", "start": 11863052, "ref": "G", "alts": "A"}])

    with caplog.at_level(logging.WARNING):
        result = _run(spec, tmp_path, resolver=_StubResolver())

    assert "recorded under a different genome build" in caplog.text
    row = next(r for r in result.rows if r.rsid == "rs1801133")
    assert row.start == _ANSWERS["rs1801133"][0]["start"]  # the source's answer, not the foreign one


# ── the advisory lock ───────────────────────────────────────────────────────────────────────────


def test_a_second_run_over_one_spec_directory_refuses_instead_of_racing(tmp_path: Path) -> None:
    """The reported incident's shape: a zombie run reaching the write and halving the table.

    The refusal text is pinned because a consumer greps it — it has to be distinguishable from every
    other `EnrichmentError`, which are all about the module's data rather than about another process.

    The first run is stood in for by `spec_lock` itself rather than by a hand-rolled `flock` call, so
    both sides acquire the lock exactly the way the enricher does. A shared lock would let two real
    runs in, and a test that took an exclusive one by hand would not notice.
    """
    spec = _spec(tmp_path / "spec")
    with spec_lock(spec, error=EnrichmentError) as first:
        assert first.held is True
        with pytest.raises(EnrichmentError) as caught:
            _run(spec, tmp_path, resolver=_StubResolver())

    assert LOCK_HELD_MESSAGE.format(spec_dir=spec) == str(caught.value)
    assert not _table(spec).exists()
    # The lock died with the descriptor, so the very next run succeeds. That is the whole argument for
    # `flock` over a lockfile: nothing is left to go stale and nothing needs a clock to expire it.
    _run(spec, tmp_path, resolver=_StubResolver())
    assert _table(spec).exists()


def test_a_platform_without_fcntl_degrades_loudly_instead_of_locking_silently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The degradation the design owes: documented, never silent. `fcntl` is POSIX-only."""
    monkeypatch.setattr(transaction, "_FCNTL", None)
    spec = _spec(tmp_path / "spec")
    with caplog.at_level(logging.WARNING):
        _run(spec, tmp_path, resolver=_StubResolver())

    assert "Advisory locking is unavailable" in caplog.text
    assert "this platform has no fcntl" in caplog.text
    assert _table(spec).exists()  # the run still completes; only the mutual exclusion is missing


def test_a_filesystem_that_refuses_the_lock_degrades_loudly_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A network mount may answer `ENOLCK`/`EOPNOTSUPP`, or emulate `flock` and exclude nothing.

    `flock` is untested here on the network filesystems a consumer may use, so the branch that says so
    is exercised rather than merely written — an unreached refusal branch is not an API.
    """
    def refuse(fd: int, operation: int) -> None:
        raise OSError(37, "No locks available")

    monkeypatch.setattr(transaction._FCNTL, "flock", refuse)
    spec = _spec(tmp_path / "spec")
    with caplog.at_level(logging.WARNING):
        _run(spec, tmp_path, resolver=_StubResolver())

    assert "Advisory locking is unavailable" in caplog.text
    assert "No locks available" in caplog.text
    assert _table(spec).exists()


def test_a_run_that_writes_nothing_takes_no_lock_and_stages_nothing(tmp_path: Path) -> None:
    """`write` gates the persistence machinery whole, so it means one thing in every mode.

    A caller dry-running against a read-only checkout touches no file today, and staging under
    `write=False` would leave droppings behind with nothing to commit toward. Proven by running it
    while another descriptor holds the lock: a run that took one could not get past this.
    """
    spec = _spec(tmp_path / "spec")
    with spec_lock(spec, error=EnrichmentError):
        result = _run(spec, tmp_path, resolver=_StubResolver(), write=False)

    assert result.rows
    assert not _table(spec).exists()
    assert not staging_dir_for(_table(spec)).exists()


# ── progress ────────────────────────────────────────────────────────────────────────────────────


def test_progress_reports_done_and_total_over_subjects_monotonically(tmp_path: Path) -> None:
    """`(done, total)` over subjects, `total` known before the first call, `done` never going back.

    The counts are derived at runtime from the module rather than written down: the subject count is
    what `_collect_subjects` dedupes to, and hardcoding it here would pin the test to today's fixture
    instead of to the invariant.
    """
    spec = _spec(tmp_path / "spec")
    calls: list[tuple[int, int]] = []
    result = _run(
        spec, tmp_path, resolver=_StubResolver(),
        progress=lambda done, total: calls.append((done, total)),
    )

    subjects = len({row.variant_key for row in result.rows})
    assert calls, "a run with subjects reported no progress at all"
    assert calls[0] == (0, subjects), "total was not known before the first call"
    assert {total for _done, total in calls} == {subjects}
    assert [done for done, _total in calls] == sorted(done for done, _total in calls)
    assert calls[-1] == (subjects, subjects)


def test_progress_is_optional_and_its_absence_changes_nothing(tmp_path: Path) -> None:
    """The default is `None`, and a run without a callback produces the same table as one with."""
    watched = _spec(tmp_path / "watched")
    _run(watched, tmp_path, resolver=_StubResolver(), progress=lambda _d, _t: None)
    silent = _spec(tmp_path / "silent")
    _run(silent, tmp_path, resolver=_StubResolver())
    assert _table(watched).read_bytes() == _table(silent).read_bytes()


# ── `--rederive` ────────────────────────────────────────────────────────────────────────────────


def _recorded(rsid: str, chrom: str, start: int, ref: str, alts: str) -> ResolutionRow:
    """A row as a previous run left it — `authority` included, derived rather than written down.

    A fixture that left it empty would be a row `enrich` never writes, and the carry-forward test
    would then be comparing against a table the code fills in on its way past.
    """
    return ResolutionRow(
        variant_key=rsid, rsid=rsid, chrom=chrom, start=start, ref=ref, alts=alts,
        genome_build="GRCh38", locus_index=0, source="ensembl-rest",
        authority=resolution_authority("ensembl-rest"), status="resolved",
    )


def _write_recorded(spec: Path, rows: list[ResolutionRow]) -> None:
    """A `resolution.csv` as `enrich` itself writes one, through the same writer, so the fixture and
    the code under test cannot disagree about the column list."""
    _write_resolution_csv(rows, spec / "resolution.csv")


def test_an_ordinary_run_never_re_asks_a_recorded_subject_and_reports_no_re_derivation(
    tmp_path: Path,
) -> None:
    """Merge-not-clobber, unchanged — and `rederived is None` says nobody looked, not "nothing moved"."""
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\n")
    _write_recorded(spec, [_recorded("rs1801133", "1", 999, "G", "A")])

    stub = _StubResolver(refuse=frozenset({"rs1801133"}))
    result = _run(spec, tmp_path, resolver=stub)

    assert result.rederived is None
    assert next(r for r in result.rows if r.rsid == "rs1801133").start == 999


def test_rederive_names_the_subjects_whose_source_changed_its_answer(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The canary, performed. A source that quietly revises an answer moves no signature and no digest
    on an ordinary run, because an ordinary run never re-asks about a recorded row."""
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\nrs7412,C/T,risk,c\n")
    _write_recorded(spec, [
        _recorded("rs1801133", "1", 999, "G", "A"),                       # the source now says 11856377
        _recorded("rs7412", "19", 44908822, "C", "T"),                    # unchanged
    ])

    with caplog.at_level(logging.WARNING):
        result = _run(spec, tmp_path, resolver=_StubResolver(), rederive=True)

    assert [d.variant_key for d in result.rederived] == ["rs1801133"]
    assert "999" in result.rederived[0].before
    assert str(_ANSWERS["rs1801133"][0]["start"]) in result.rederived[0].after
    assert "now answer differently from the recorded table" in caplog.text
    # The fresh answer is what gets committed, and the recorded one is not kept anywhere.
    assert next(r for r in result.rows if r.rsid == "rs1801133").start == 11856377


def test_the_rederive_denominator_counts_only_the_subjects_that_were_re_asked(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The count a warning publishes has to be the count its sentence names.

    The carried-forward rows are back in the fresh table by the time the comparison runs, so a naive
    denominator would call an un-asked subject one that was re-asked. Two recorded subjects here, one
    of which the stub answers and one it cannot be asked about, and exactly one of them was re-asked.
    """
    spec = _spec(
        tmp_path / "spec",
        "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\nrs6567160,C/T,risk,c\n",
    )
    _write_recorded(spec, [
        _recorded("rs1801133", "1", 999, "G", "A"),          # the source now says 11856377
        _recorded("rs6567160", "6", 98865669, "C", "T"),     # the request fails: never asked
    ])

    with caplog.at_level(logging.WARNING):
        result = _run(spec, tmp_path, resolver=_UnreachableFor("rs6567160"), rederive=True)

    assert [d.variant_key for d in result.rederived] == ["rs1801133"]
    assert "1 of 1 re-asked subject(s)" in caplog.text
    assert "kept the recorded rows for 1 subject(s)" in caplog.text
    # And the un-asked subject keeps the rows it had, rather than vanishing from the table.
    assert next(r for r in result.rows if r.rsid == "rs6567160").start == 98865669


def test_rederive_reports_nothing_when_nothing_moved(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An empty list, not a line saying zero: a comparison whose empty result is the normal case must
    not announce it as evidence. `[]` is still distinguishable from `None`, which means nobody asked."""
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs7412,C/T,risk,c\n")
    _write_recorded(spec, [_recorded("rs7412", "19", 44908822, "C", "T")])

    with caplog.at_level(logging.WARNING):
        result = _run(spec, tmp_path, resolver=_StubResolver(), rederive=True)

    assert result.rederived == []
    assert "re-asked subject" not in caplog.text


def test_rederive_keeps_the_rows_of_a_subject_no_source_could_be_asked_about(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Re-deriving must never be a way to shorten the table — the reported incident, wearing a flag.

    Offline with no cache is the case that guarantees it: every link is gated off, so the three
    branches that deliberately write no row for an unanswerable subject fire for every subject at
    once. A fresh table committed from that would replace a full one with an empty one, and nothing
    downstream could tell it from a module whose author resolved less.
    """
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs1801133,A/G,risk,c\nrs7412,C/T,risk,c\n")
    recorded = [
        _recorded("rs1801133", "1", 11856377, "G", "A"),
        _recorded("rs7412", "19", 44908822, "C", "T"),
    ]
    _write_recorded(spec, recorded)
    before = _table(spec).read_bytes()

    with caplog.at_level(logging.WARNING):
        result = _run(spec, tmp_path, offline=True, rederive=True)

    assert {r.variant_key for r in result.rows} == {r.variant_key for r in recorded}
    assert result.unresolved == []          # they are resolved; they simply were not re-asked
    assert result.rederived == []           # nothing was compared, so nothing moved
    assert "kept the recorded rows for" in caplog.text
    assert _table(spec).read_bytes() == before


def test_rederive_prunes_a_recorded_row_for_a_variant_the_author_deleted(tmp_path: Path) -> None:
    """The carry-forward is for subjects that could not be asked, not for subjects that are gone.

    An ordinary run drops a recorded row whose variant has left `variants.csv` — the assembly loop
    iterates the spec's subjects and nothing else — so a carry-forward that walked the whole recorded
    table would make `--rederive` resurrect rows a plain re-run prunes.
    """
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs7412,C/T,risk,c\n")
    _write_recorded(spec, [
        _recorded("rs7412", "19", 44908822, "C", "T"),
        _recorded("rs1801133", "1", 11856377, "G", "A"),   # no longer authored anywhere
    ])

    plain = _run(_deleted_variant_copy(spec, tmp_path / "plain"), tmp_path,
                 resolver=_StubResolver(refuse=frozenset({"rs7412"})))
    rederived = _run(spec, tmp_path, resolver=_StubResolver(), rederive=True)

    assert {r.rsid for r in rederived.rows} == {r.rsid for r in plain.rows} == {"rs7412"}


def _deleted_variant_copy(spec: Path, into: Path) -> Path:
    """The same spec and the same recorded table, for the run that must agree with the re-derivation."""
    shutil.copytree(spec, into)
    return into


def test_rederive_replaces_a_subject_the_source_now_says_it_does_not_have(tmp_path: Path) -> None:
    """Answered-and-absent is an answer and does replace, unlike could-not-ask.

    The distinction is the whole of the carry-forward rule: a source that has dropped a record is
    telling us something, and the `not_found` row it produces is the honest record of that.
    """
    spec = _spec(tmp_path / "spec", "rsid,genotype,state,conclusion\nrs55555555,A/G,risk,c\n")
    _write_recorded(spec, [_recorded("rs55555555", "1", 42, "G", "A")])

    result = _run(spec, tmp_path, resolver=_StubResolver(), rederive=True)

    row = next(r for r in result.rows if r.rsid == "rs55555555")
    assert row.status == "not_found"
    assert row.chrom is None
    assert result.unresolved == ["rs55555555"]


# ── the journal's own reader ────────────────────────────────────────────────────────────────────


def test_the_journal_round_trips_every_locus_of_a_one_to_many_rsid(tmp_path: Path) -> None:
    """One rsID legitimately names several loci, and a journal that kept only the first would silently
    narrow the table a resumed run produces."""
    target = tmp_path / "resolution.csv"
    loci = [
        {"chrom": "X", "start": 500, "ref": "A", "alts": "T"},
        {"chrom": "Y", "start": 600, "ref": "A", "alts": "T"},
    ]
    ResolutionJournal(target, genome_build="GRCh38").record("rs999", "cache", loci)

    reread = ResolutionJournal(target, genome_build="GRCh38").resume()
    assert reread == {"rs999": ("cache", loci)}

    with (staging_dir_for(target) / transaction.JOURNAL_NAME).open(newline="", encoding="utf-8") as f:
        assert [row["rsid"] for row in csv.DictReader(f)] == ["rs999", "rs999"]


def test_a_spec_dir_that_is_not_a_directory_gets_the_pass_own_exception_type(tmp_path: Path) -> None:
    """`spec_lock` runs ahead of every loader, so a wrong path meets it first.

    Without a check here `os.open` would raise `FileNotFoundError`/`NotADirectoryError` straight past
    the caller's `except EnrichmentError`, which both CLI commands and any SDK caller are written
    around. A pass owes its caller its own exception type.
    """
    missing = tmp_path / "not-a-spec"
    with pytest.raises(EnrichmentError) as caught:
        enrich(missing)
    assert LOCK_TARGET_MESSAGE.format(spec_dir=missing) == str(caught.value)


def test_the_settled_count_grows_whether_or_not_a_callback_is_listening() -> None:
    """`done` is the size of a set that only grows — including when nobody asked to be told.

    Guarding the update on the callback rather than only the report would make `settled` a silent
    zero for every caller that reads the count without registering one, which is the opposite of what
    a monotonic counter promises.
    """
    silent = SubjectProgress(3, None)
    silent.settle(["a", "b"])
    silent.settle(["b"])
    assert silent.settled == 2

    calls: list[tuple[int, int]] = []
    watched = SubjectProgress(3, lambda done, total: calls.append((done, total)))
    watched.settle(["a", "b"])
    watched.settle(["b"])          # already settled: no second report
    assert watched.settled == silent.settled
    assert calls == [(0, 3), (2, 3)]
