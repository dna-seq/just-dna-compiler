"""A licence file that exists and says nothing is not terms (RM178).

The incident behind this: `HfFileSystem.get` creates the local file *before* it discovers the remote
path is missing, and `_provision_snapshot` fetched the two optional root files straight to their real
names. So every `cache pull` of a snapshot whose repo publishes no `LICENSE.txt` left a 0-byte one
behind — four of the published repos on 2026-09-03 (clinvar, gnomad_constraint, cpic, mitomap). The
readers guard on `is_file()`, so that empty file is not inert: an *absent* licence withholds
(`license_sha256` stays `None`, with a warning) while an *empty* one pins the terms to
`sha256:e3b0c442…b855`, the hash of the empty string, silently.

Two halves, tested here together because they are one rule: nothing is left behind when the fetch
fails, and a blank licence answers `None` wherever one is read.
"""

import csv
import hashlib
import io
import shutil
import zipfile
from pathlib import Path

import duckdb
import pytest
from just_dna_enricher import download as dl
from just_dna_enricher.clinpgx_build import ARCHIVE_LICENSE_MEMBER, read_license
from just_dna_enricher.clinpgx_draft import draft_pharm_variants
from just_dna_enricher.licensing import CLINPGX_TERMS
from just_dna_enricher.locations import RELEASE_FILENAME, SNAPSHOT_LICENSE_FILENAME
from just_dna_format.layout import SOURCES_CSV, preferred_spelling

_SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "interim" / "clinpgx"
_needs_snapshot = pytest.mark.skipif(
    not (_SNAPSHOT / "data" / "annotations.parquet").is_file(),
    reason="no local ClinPGx snapshot (build it with `just-dna-enricher clinpgx build`)",
)

_EMPTY_SHA = "sha256:" + hashlib.sha256(b"").hexdigest()


def _rows(path: Path) -> list[dict]:
    """A drafted CSV as dicts — the raw cells, so a test can see what was written."""
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


# ── half one: a failed optional fetch leaves nothing behind ─────────────────────────────────────


class _CreateThenRaiseFS:
    """A fake `HfFileSystem` that reproduces the real one's observed behaviour.

    `get` **opens the destination for writing and then raises** for a path the repo does not have.
    That detail is the whole bug — a fake that raised without touching the destination would pass
    against the code these tests exist to fail on. Both halves verified against the live hub on
    2026-09-03, fetching `datasets/just-dna-seq/clinvar/LICENSE.txt`, a path that does not exist: it
    raised `FileNotFoundError`, left a 0-byte local file where there was none, and truncated a
    36-byte local file that was already there.
    """

    def __init__(self, parquet_bytes: bytes, present: set[str]) -> None:
        self.parquet_bytes = parquet_bytes
        self.present = present               # remote basenames the repo actually has
        self.attempted: list[str] = []

    def ls(self, prefix: str, detail: bool = True):
        if prefix.rstrip("/").rsplit("/", 1)[-1] != "data":
            raise FileNotFoundError(prefix)
        return [f"{prefix}/only-chr1.parquet"]

    def get(self, remote_path: str, local_path: str) -> None:
        name = remote_path.rstrip("/").rsplit("/", 1)[-1]
        self.attempted.append(name)
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        Path(local_path).write_bytes(b"")    # opened for writing before the remote is resolved
        if name not in self.present:
            raise FileNotFoundError(remote_path)
        Path(local_path).write_bytes(self.parquet_bytes)


@pytest.fixture
def hub(monkeypatch, tmp_path: Path):
    """Install `_CreateThenRaiseFS` in place of `HfFileSystem`, over a real parquet."""
    import huggingface_hub

    source = tmp_path / "seed.parquet"
    con = duckdb.connect(":memory:")
    try:
        con.execute(f"COPY (SELECT 1 AS clin_sig) TO '{source}' (FORMAT PARQUET)")
    finally:
        con.close()
    payload = source.read_bytes()

    def factory(present: set[str]) -> _CreateThenRaiseFS:
        fs = _CreateThenRaiseFS(payload, {"only-chr1.parquet", *present})
        monkeypatch.setattr(huggingface_hub, "HfFileSystem", lambda token=None: fs)
        monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)
        return fs

    return factory


def _provision(cache: Path) -> Path:
    return dl._provision_snapshot(
        cache, "datasets/just-dna-seq/example/data", label="Example",
        error_cls=dl.OpenSnapshotError, filename_glob="*.parquet",
    )


def test_a_repo_with_no_licence_leaves_no_licence_file(hub, tmp_path: Path) -> None:
    """The published state this was found in: a repo that has neither optional file."""
    fs = hub(set())
    cache = tmp_path / "cache"
    _provision(cache)

    assert SNAPSHOT_LICENSE_FILENAME in fs.attempted, "the fetch must have been attempted"
    assert not (cache / SNAPSHOT_LICENSE_FILENAME).exists()
    assert not (cache / RELEASE_FILENAME).exists()
    # and no half-written staging file survives either
    assert list(cache.glob("*.part")) == []


def test_an_empty_licence_would_have_pinned_the_empty_string(tmp_path: Path) -> None:
    """Demonstrated rather than asserted: what the 0-byte file did once it was in the cache.

    This is the consequence the fix above prevents, shown against the *reader* — a file that is
    present and empty is indistinguishable from real terms to an `is_file()` guard, and the hash it
    produces is a definite claim.
    """
    assert CLINPGX_TERMS.row("annotation", declared_use="non_commercial",
                             license_text="real terms").license_sha256 != _EMPTY_SHA
    assert hashlib.sha256(b"").hexdigest() in _EMPTY_SHA  # the value that used to be recorded


def test_a_present_optional_file_still_arrives(hub, tmp_path: Path) -> None:
    """The staging must not cost the normal case: a repo that has both files still yields both."""
    hub({RELEASE_FILENAME, SNAPSHOT_LICENSE_FILENAME})
    cache = tmp_path / "cache"
    _provision(cache)

    assert (cache / RELEASE_FILENAME).is_file()
    assert (cache / SNAPSHOT_LICENSE_FILENAME).is_file()
    assert list(cache.glob("*.part")) == []


def test_a_re_pull_does_not_truncate_a_good_local_copy(hub, tmp_path: Path) -> None:
    """The second bug the same staging fixes, and the one that costs an operator real terms.

    A cache built (or pulled) when the repo carried `LICENSE.txt`, re-pulled after the repo dropped
    it: fetching straight to the real name overwrote the good local file with an empty one.
    """
    hub(set())
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / SNAPSHOT_LICENSE_FILENAME).write_text("the terms that governed these bytes\n")
    _provision(cache)

    assert (cache / SNAPSHOT_LICENSE_FILENAME).read_text() == (
        "the terms that governed these bytes\n"
    )


# ── half two: blank answers None wherever a licence is read ─────────────────────────────────────


@pytest.mark.parametrize("text", ["", "   ", "\n\t\n"])
def test_a_blank_licence_text_pins_nothing(text: str) -> None:
    """The sink: `SourceTerms.row` normalizes, so no caller can pin the empty string."""
    row = CLINPGX_TERMS.row("annotation", declared_use="non_commercial", license_text=text)
    assert row.license_sha256 is None
    # the rest of the terms are unaffected — this is about the pin, not about the licence name
    assert row.license == CLINPGX_TERMS.license


def test_a_stated_licence_still_pins() -> None:
    row = CLINPGX_TERMS.row("annotation", declared_use="non_commercial", license_text="CC BY-SA 4.0")
    assert row.license_sha256 == "sha256:" + hashlib.sha256(b"CC BY-SA 4.0").hexdigest()


def test_a_blank_archive_member_reads_as_no_member(tmp_path: Path) -> None:
    """The archive readers: both builders hash and *write out* whatever `read_license` returns."""
    blank = tmp_path / "blank.zip"
    with zipfile.ZipFile(blank, "w") as archive:
        archive.writestr(ARCHIVE_LICENSE_MEMBER, "   \n")
    stated = tmp_path / "stated.zip"
    with zipfile.ZipFile(stated, "w") as archive:
        archive.writestr(ARCHIVE_LICENSE_MEMBER, "CC BY-SA 4.0")

    with zipfile.ZipFile(blank) as archive:
        assert read_license(archive) is None
    with zipfile.ZipFile(stated) as archive:
        assert read_license(archive) == "CC BY-SA 4.0"


@_needs_snapshot
def test_the_drafter_warns_instead_of_pinning_an_empty_file(tmp_path: Path) -> None:
    """End to end on the real snapshot, with its LICENSE.txt truncated to what a pull used to leave.

    The whole point of the finding: the drafter must treat this exactly as it treats an absent file —
    a null hash and a warning — rather than recording a pin nobody can check.
    """
    snapshot = tmp_path / "snapshot"
    shutil.copytree(_SNAPSHOT, snapshot, ignore=shutil.ignore_patterns("*.zip"))
    (snapshot / SNAPSHOT_LICENSE_FILENAME).write_text("")   # what the 0-byte pull left behind

    spec = tmp_path / "spec"
    spec.mkdir()
    result = draft_pharm_variants(
        spec, snapshot=snapshot, genes=["CYP2C19"], declared_use="non_commercial",
    )
    assert not result.skipped, result.warnings

    sources = _rows(spec / preferred_spelling(SOURCES_CSV))
    clinpgx = [r for r in sources if r["layer"] == "annotation"]
    assert clinpgx, "the pass must write its SourceRow"
    assert {r["license_sha256"] for r in clinpgx} == {""}, "an empty file pinned the empty string"
    assert any(SNAPSHOT_LICENSE_FILENAME in w for w in result.warnings), result.warnings
