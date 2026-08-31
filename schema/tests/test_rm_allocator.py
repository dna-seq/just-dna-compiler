"""`RMn` is allocated under a lock, because an index is not an allocator.

`docs/RM_TOC.md` is the complete list of every roadmap item, but nothing in the loop ever *claimed* a
number: a session grepping "the highest in use" and then writing its entry leaves a window, and the
next session's grep lands inside it. On 2026-09-01 two sessions sharing this working tree filed
different work as RM159 a minute apart and the tree carried two RM159 entries — git `741ec59`, which
renumbered one to RM161. This is that incident as a test, plus the two properties the repair turns on.

**The lock is proven by running the failing version**, not asserted: the same concurrent allocation
with `flock` neutered collides, and with it in place does not. A guard nobody has watched fail is a
guess — the rule this repo's own triage tests were written under.
"""

import importlib.util
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLAUDE = ROOT / ".claude"

_TOC = """# `RM` table of contents

## ⏳ Open, no release decided — [ROADMAP.md](ROADMAP.md#active-items)

- ✅ **[RM1](ROADMAP_HISTORY.md#rm1)** — the first item
- ✅ **[RM2](ROADMAP_HISTORY.md#rm2)** — the second item

## Where an item comes from

Prose at the end of the file, which a reservation row must never land under.
"""


def _sandbox(tmp_path: pathlib.Path, toc: str = _TOC, *, lock: bool = True) -> pathlib.Path:
    """A miniature repo: `.claude/rm-next.py` beside a `docs/` holding one index."""
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / "docs").mkdir()
    source = (CLAUDE / "rm-next.py").read_text()
    if not lock:
        # Neuter ONLY the lock, so the concurrent run below differs in exactly one thing.
        source = source.replace(
            "        _FCNTL.flock(fd, _FCNTL.LOCK_EX)", "        pass  # disabled for this probe"
        )
        assert "disabled for this probe" in source, "the flock call moved; this probe is stale"
    (repo / ".claude" / "rm-next.py").write_text(source)
    (repo / "docs" / "RM_TOC.md").write_text(toc)
    return repo


def _load(repo: pathlib.Path):
    spec = importlib.util.spec_from_file_location(
        f"rm_next_{repo.parent.name}", repo / ".claude" / "rm-next.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _allocate_concurrently(repo: pathlib.Path, n: int = 8) -> list[str]:
    """Run `n` allocators at once and return what each printed on stdout."""
    procs = [
        subprocess.Popen(
            [sys.executable, str(repo / ".claude" / "rm-next.py")],
            cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        for _ in range(n)
    ]
    return [p.communicate()[0].strip() for p in procs]


# ── the incident ────────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(not hasattr(os, "fork"), reason="POSIX flock only")
def test_concurrent_allocations_never_take_the_same_number(tmp_path: pathlib.Path) -> None:
    """Eight at once, eight distinct numbers, contiguous from the current maximum."""
    repo = _sandbox(tmp_path)
    got = _allocate_concurrently(repo)
    assert len(set(got)) == len(got), got
    assert sorted(int(g.removeprefix("RM")) for g in got) == list(range(3, 11))


@pytest.mark.skipif(not hasattr(os, "fork"), reason="POSIX flock only")
def test_the_same_run_collides_once_the_lock_is_removed(tmp_path: pathlib.Path) -> None:
    """**The guard, watched failing.** Identical to the test above but for the `flock` call, and it
    must produce duplicates — otherwise the test above is passing for some other reason and the lock
    is not what is doing the work. Scheduling decides how many collide, so the assertion is that at
    least two runs agreed, never an exact count."""
    repo = _sandbox(tmp_path, lock=False)
    got = _allocate_concurrently(repo)
    assert len(set(got)) < len(got), f"expected a collision without the lock, got {got}"


# ── the two properties the repair turns on ──────────────────────────────────────────────────────


def test_a_reservation_is_what_makes_the_next_scan_see_the_number(tmp_path: pathlib.Path) -> None:
    """The mechanism in one assertion: reserving is a *write*, and the write is what closes the race.

    A tool that only printed the next number would return the same one twice, which is the defect —
    so this pins that a second allocation moves on without the first having written an item.
    """
    repo = _sandbox(tmp_path)
    module = _load(repo)
    module.DOCS = repo / "docs"
    module.TOC = repo / "docs" / "RM_TOC.md"
    first = module.allocate(note=None, dry_run=False)
    second = module.allocate(note=None, dry_run=False)
    assert (first, second) == (3, 4)
    assert module.next_free(module.used_numbers()) == 5


def test_a_dry_run_writes_nothing_and_therefore_reserves_nothing(tmp_path: pathlib.Path) -> None:
    """`--dry-run` is for reading the number, and it must not appear to have claimed it."""
    repo = _sandbox(tmp_path)
    module = _load(repo)
    module.DOCS = repo / "docs"
    module.TOC = repo / "docs" / "RM_TOC.md"
    before = module.TOC.read_text()
    assert module.allocate(note=None, dry_run=True) == 3
    assert module.TOC.read_text() == before
    assert module.allocate(note=None, dry_run=True) == 3


def test_a_released_number_is_spent_rather_than_freed(tmp_path: pathlib.Path) -> None:
    """Ids are never reused — the `Sn` rule, and the bug the first cut of this shipped.

    Deleting the reservation row outright made the number invisible to the scan, so a released RM10
    was handed straight back out. Whatever argued the withdrawal refers to the number, so a reused id
    makes two items answer to one name.
    """
    repo = _sandbox(tmp_path)
    module = _load(repo)
    module.DOCS = repo / "docs"
    module.TOC = repo / "docs" / "RM_TOC.md"
    claimed = module.allocate(note=None, dry_run=False)
    assert module.release(claimed) == 0
    assert module.reservations(module.TOC.read_text()) == {}
    # The tombstone still contains the number, which is the only thing the scanner reads.
    assert f"RM{claimed}" in module.TOC.read_text()
    assert module.allocate(note=None, dry_run=False) == claimed + 1


def test_releasing_something_that_was_never_reserved_refuses(tmp_path: pathlib.Path) -> None:
    """A shipped item is not a reservation, and `--release` must not delete its index row."""
    repo = _sandbox(tmp_path)
    module = _load(repo)
    module.DOCS = repo / "docs"
    module.TOC = repo / "docs" / "RM_TOC.md"
    before = module.TOC.read_text()
    assert module.release(1) == 1
    assert module.TOC.read_text() == before


# ── placement, which is the furniture hazard one document over ──────────────────────────────────


def test_a_reservation_lands_under_the_open_heading_not_in_the_trailing_prose(
    tmp_path: pathlib.Path,
) -> None:
    """`RM_TOC.md` ends in a prose section, and a row appended at EOF reads as part of it — the same
    furniture hazard the triage loop's § 6 records for the consumer documents."""
    repo = _sandbox(tmp_path)
    module = _load(repo)
    module.DOCS = repo / "docs"
    module.TOC = repo / "docs" / "RM_TOC.md"
    module.allocate(note=None, dry_run=False)
    lines = module.TOC.read_text().splitlines()
    row = next(i for i, line in enumerate(lines) if line.startswith("- 🔷"))
    heading = next(i for i, line in enumerate(lines) if line.startswith(module.ANCHOR))
    prose = next(i for i, line in enumerate(lines) if line.startswith("## Where an item comes from"))
    assert heading < row < prose


def test_a_missing_anchor_appends_and_says_so(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """If the heading is ever renamed the row still lands, and the run warns — a reservation quietly
    written somewhere nobody reads is worse than one in the wrong place with a notice."""
    repo = _sandbox(tmp_path, toc="# `RM` table of contents\n\n- ✅ **RM1** — only item\n")
    module = _load(repo)
    module.DOCS = repo / "docs"
    module.TOC = repo / "docs" / "RM_TOC.md"
    assert module.allocate(note=None, dry_run=False) == 2
    assert "no '## ⏳ Open, no release decided' heading" in capsys.readouterr().err
    assert module.TOC.read_text().rstrip().endswith("--release`).")


# ── the scan ────────────────────────────────────────────────────────────────────────────────────


def test_a_number_used_anywhere_under_docs_is_taken(tmp_path: pathlib.Path) -> None:
    """The scan is the whole tree, not the index. An item is referenced from proposals, probes and the
    changelog, and a scanner reading one file would hand out a number another document already uses.
    """
    repo = _sandbox(tmp_path)
    (repo / "docs" / "probes").mkdir()
    (repo / "docs" / "probes" / "SOMETHING.md").write_text("Filed as RM7 during a probe round.\n")
    module = _load(repo)
    module.DOCS = repo / "docs"
    module.TOC = repo / "docs" / "RM_TOC.md"
    used = module.used_numbers()
    assert 7 in used and "probes/SOMETHING.md" in used[7]
    assert module.next_free(used) == 8


def test_the_number_climbs_past_a_gap_rather_than_filling_it(tmp_path: pathlib.Path) -> None:
    """A gap means an item was withdrawn, and its number stays referenced wherever that was argued."""
    repo = _sandbox(
        tmp_path,
        toc="# TOC\n\n## ⏳ Open, no release decided\n\n- ✅ **RM1** — one\n- ✅ **RM5** — five\n",
    )
    module = _load(repo)
    module.DOCS = repo / "docs"
    module.TOC = repo / "docs" / "RM_TOC.md"
    assert module.next_free(module.used_numbers()) == 6


def test_this_repo_allocates_above_its_own_highest(tmp_path: pathlib.Path) -> None:
    """Run against the real `docs/`, so the tool cannot pass its sandbox and fail the tree — the
    number it would hand out here must be free everywhere, including in this test file."""
    spec = importlib.util.spec_from_file_location("rm_next_real", CLAUDE / "rm-next.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    used = module.used_numbers()
    assert used, "the scan found no RM numbers at all, which cannot be right for this repo"
    assert module.next_free(used) not in used
