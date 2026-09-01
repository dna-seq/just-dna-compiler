"""The `pubmind` command surface: build works, publish refuses, and the refusal names its reason.

A command that exists in order to say no is only worth having if the no carries the reason, so the
refusal's text is pinned the same way a warning's is (`@warning-text-is-api`). And `pubmind` has to
be reachable from both entry points, which is the defect the registration-ordering comment at the
bottom of `cli.py` exists for.
"""

import json
import re
from pathlib import Path

from just_dna_enricher.cli import PUBMIND_PUBLISH_REFUSAL, app
from just_dna_enricher.locations import (
    PUBMIND_SUBDIR,
    default_pubmind_cache_dir,
    resolve_pubmind_reference,
)
from typer.testing import CliRunner

_SLICE = Path(__file__).resolve().parents[2] / "assets" / "hg38_pubmind_db_slice.txt.gz"
_runner = CliRunner()

#: Typer renders `--help` through Rich, and Rich decides whether to colour by asking the environment.
#: A developer's terminal usually says no; a CI runner with `FORCE_COLOR` set says yes, and then every
#: flag arrives as ANSI-split fragments — `--pubmind-cache` is emitted as an escape, `-`, an escape,
#: `-pubmind-cache`, so a substring match finds nothing and `str.split()` yields tokens that begin
#: with an escape rather than a dash. Two tests below read the rendered help, and both passed locally
#: and failed on GitHub for exactly that reason. Strip the escapes before reading, rather than
#: pinning the environment: the help text a user sees is the same either way, and a test that only
#: works on an uncoloured terminal is testing the terminal.
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _plain(text: str) -> str:
    """`text` with terminal escapes removed, so a flag is one token again."""
    return _ANSI.sub("", text)


def test_publish_refuses_and_says_why() -> None:
    """Exit non-zero, and name the unestablished terms plus the PharmVar precedent behind them.

    The three phrases are the reason a reader can act on: what is missing (data terms), what rule
    applies (an unestablished permission is not a permission), and what lifts it (an answer from
    CHOP, not a flag).
    """
    result = _runner.invoke(app, ["pubmind", "publish"])
    assert result.exit_code == 1
    output = result.output + (result.stderr or "")
    assert "REFUSED" in output
    assert "no data terms of its own" in PUBMIND_PUBLISH_REFUSAL
    assert "unestablished permission is not a permission" in PUBMIND_PUBLISH_REFUSAL
    assert "PharmVar" in PUBMIND_PUBLISH_REFUSAL
    assert "Office of Technology Transfer" in PUBMIND_PUBLISH_REFUSAL


def test_publish_takes_no_arguments_that_could_look_like_a_way_round_it() -> None:
    """No `--force`, no `--repo`, no `--dry-run`: there is nothing to configure about a refusal."""
    result = _runner.invoke(app, ["pubmind", "publish", "--help"])
    assert result.exit_code == 0
    for flag in ("--repo", "--force", "--dry-run", "--message"):
        assert flag not in result.output


def test_build_writes_the_snapshot_and_reports_every_drop(tmp_path: Path) -> None:
    """The counts a silent truncation would hide reach the operator's terminal, not only the JSON."""
    out = tmp_path / "snap"
    result = _runner.invoke(app, ["pubmind", "build", "--table", str(_SLICE), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert (out / "data" / "pubmind.parquet").is_file()
    release = json.loads((out / "release.json").read_text())
    for reason, count in release["dropped"].items():
        assert f"{reason} {count}" in result.output
    assert f"kept: {release['record_count']} of {release['input_rows']}" in result.output
    assert "never published" in result.output or "inject-only" in result.output


def test_build_names_the_multiplicity_it_refused_to_collapse(tmp_path: Path) -> None:
    """The contested coordinates are a finding, so the build says so rather than only recording it."""
    out = tmp_path / "snap"
    result = _runner.invoke(app, ["pubmind", "build", "--table", str(_SLICE), "--out", str(out)])
    assert result.exit_code == 0, result.output
    release = json.loads((out / "release.json").read_text())
    assert f"{release['multi_pvid_keys']} of {release['allele_keys']}" in result.output
    assert "ordering nobody defined" in result.output


def test_build_refuses_with_neither_a_table_nor_a_download() -> None:
    """No input is an error, not an empty snapshot that later reads as "PubMind says nothing"."""
    result = _runner.invoke(app, ["pubmind", "build"])
    assert result.exit_code == 1
    assert "--table" in (result.output + (result.stderr or ""))


def test_build_offers_no_declared_use_flag() -> None:
    """A flag feeding a gate that can only ever skip is a flag that does nothing.

    PubMind's `commercial_use` is unknown, so `check_declared_use` returns a skip reason for every
    declaration. Wiring `--use` in the way `pharmvar build` does would make the command permanently
    dead, so the surface omits it and the refusal lives on `publish`, where the act actually is.
    """
    result = _runner.invoke(app, ["pubmind", "build", "--help"])
    assert result.exit_code == 0
    # Read the flags Typer advertises, not the prose: the docstring names `--use` in order to explain
    # why it is absent, and matching on the raw text would find that sentence.
    flags = {token for token in _plain(result.output).split() if token.startswith("--")}
    assert "--use" not in flags
    # An EQUALITY over the advertised surface, not a floor: `<=` passes unchanged on the day a
    # flag is silently added or one of these three is dropped, which is the only day it matters.
    assert flags == {"--table", "--download", "--out", "--help"}


def test_the_cache_resolver_finds_a_built_snapshot_and_withholds_otherwise(
    tmp_path: Path, monkeypatch
) -> None:
    """`None` for absent, so a caller branches on it rather than on a default.

    Nobody-asked is the third state beside asked-and-failed and asked-and-absent, and it is the state
    a deployment with no PubMind snapshot is in.
    """
    monkeypatch.setenv("JUST_DNA_PUBMIND_CACHE", str(tmp_path / "nothing-here"))
    assert resolve_pubmind_reference(load_dotenv_file=False) is None

    out = tmp_path / "snap"
    assert _runner.invoke(
        app, ["pubmind", "build", "--table", str(_SLICE), "--out", str(out)]
    ).exit_code == 0
    monkeypatch.setenv("JUST_DNA_PUBMIND_CACHE", str(out))
    assert resolve_pubmind_reference(load_dotenv_file=False) == out


def test_the_default_cache_directory_sits_beside_the_others(tmp_path: Path, monkeypatch) -> None:
    """One base serves every snapshot, so a single deployment cache holds all of them."""
    monkeypatch.setenv("JUST_DNA_PIPELINES_CACHE_DIR", str(tmp_path))
    assert default_pubmind_cache_dir(load_dotenv_file=False) == tmp_path / PUBMIND_SUBDIR


def test_cache_status_lists_pubmind_as_build_your_own(tmp_path: Path, monkeypatch) -> None:
    """It has no `ensure_*` and never will, and `cache status` has to say `pubmind build` not pull."""
    monkeypatch.setenv("JUST_DNA_PUBMIND_CACHE", str(tmp_path / "absent"))
    result = _runner.invoke(app, ["cache", "status"])
    assert result.exit_code == 0
    line = next(ln for ln in result.output.splitlines() if ln.strip().startswith("pubmind"))
    assert "absent" in line and "`pubmind build`" in line


def test_there_is_no_ensure_pubmind_snapshot_to_pair_with_the_resolver() -> None:
    """Deliberate absence: refused publish means no HF repo, so there is nothing to provision from."""
    from just_dna_enricher import download

    assert not [name for name in vars(download) if "pubmind" in name.lower()]


def test_enrich_takes_the_pubmind_cache_the_check_needs(tmp_path: Path, monkeypatch) -> None:
    """The concordance check shipped with no way to reach it from the command line.

    RM134 § B built the second authority's leg but could not add the flag, because `cli.py` belonged
    to the sibling lane that release; its report said one was owed. Without it the only routes were
    `enrich(pubmind_cache=...)` in Python or the environment variable, so the flag the check exists
    for was unreachable from the surface every author actually uses.

    Asserted through the real CLI signature rather than the help text, because a help string can say
    `--pubmind-cache` while the value never reaches `enrich()` — which is the failure this pins.
    """
    import inspect

    from just_dna_enricher.cli import enrich_

    assert "pubmind_cache" in inspect.signature(enrich_).parameters

    source = inspect.getsource(enrich_)
    assert "pubmind_cache=pubmind_cache" in source, "the flag is declared but never passed through"

    result = _runner.invoke(app, ["enrich", "--help"])
    assert result.exit_code == 0
    assert "--pubmind-cache" in _plain(result.output)
