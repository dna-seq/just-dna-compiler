"""Cache locations: the `.env` has to be loaded before the default directory is computed.

Every assertion here runs in a **subprocess** with a controlled cwd and environment, and that is not
incidental. The bug is process-scoped ordering — it only shows on the *first* resolve — and
`locations.load_env()` mutates `os.environ` for the rest of the session, so an in-process test would
both miss the defect and leak the repo's own `.env` into every test that ran after it.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_PROBE = """
from just_dna_enricher.locations import default_clinvar_cache_dir, resolve_clinvar_reference
print("FIRST", resolve_clinvar_reference())
print("SECOND", resolve_clinvar_reference())
print("DEFAULT", default_clinvar_cache_dir())
"""

#: The pre-fix arrangement, reproduced in-process: `_cache_dir` did not load the environment, so the
#: default handed to `_resolve_parquet_cache` was computed before `load_env()` ran inside it.
_PROBE_WITHOUT_THE_FIX = """
import just_dna_enricher.locations as loc
loc.load_env = lambda override=False: None
print("FIRST", loc.resolve_clinvar_reference())
"""


@pytest.fixture
def dotenv_only_cache(tmp_path_factory) -> tuple[Path, Path]:
    """A snapshot whose base is stated **only** in a `.env`, and a working directory next to it."""
    root = Path(tempfile.mkdtemp(dir=tmp_path_factory.mktemp("env")))
    (root / "clinvar" / "data").mkdir(parents=True)
    (root / "clinvar" / "data" / "chr.parquet").write_bytes(b"stand-in for a built snapshot")
    work = root / "work"
    work.mkdir()
    (work / ".env").write_text(f"JUST_DNA_PIPELINES_CACHE_DIR={root}\n", encoding="utf-8")
    return root, work


def _run(script: str, cwd: Path) -> dict[str, str]:
    """Run a probe with `$JUST_DNA_PIPELINES_CACHE_DIR` unset, so only the `.env` can supply it."""
    env = {k: v for k, v in os.environ.items() if k != "JUST_DNA_PIPELINES_CACHE_DIR"}
    done = subprocess.run(
        [sys.executable, "-c", script], cwd=cwd, env=env, capture_output=True, text=True, check=True
    )
    return dict(line.split(" ", 1) for line in done.stdout.strip().splitlines())


def test_the_first_resolve_in_a_process_finds_a_dotenv_only_cache(dotenv_only_cache) -> None:
    """`cache status` reported *absent* right after a successful `cache pull` because of this."""
    root, work = dotenv_only_cache
    out = _run(_PROBE, work)

    assert out["FIRST"] == str(root / "clinvar")
    assert out["SECOND"] == out["FIRST"], "and it is not the second call that fixes it"
    # The directory `cache pull` writes into is the one the resolvers read — the same value.
    assert out["DEFAULT"] == str(root / "clinvar")


def test_without_the_load_the_first_resolve_really_did_miss(dotenv_only_cache) -> None:
    """The demonstration, on the old arrangement rather than an assertion about it.

    Without this the fix above is untestable in the honest sense: a passing `resolve_*` proves the
    lookup works, not that the ordering was ever wrong.
    """
    _root, work = dotenv_only_cache
    assert _run(_PROBE_WITHOUT_THE_FIX, work)["FIRST"] == "None"


def test_a_real_environment_variable_still_outranks_the_dotenv(dotenv_only_cache) -> None:
    """`override=False` — a value already in the environment wins, including a test's empty one."""
    root, work = dotenv_only_cache
    elsewhere = root / "elsewhere"
    (elsewhere / "clinvar" / "data").mkdir(parents=True)
    (elsewhere / "clinvar" / "data" / "chr.parquet").write_bytes(b"another snapshot")
    done = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=work,
        env={**os.environ, "JUST_DNA_PIPELINES_CACHE_DIR": str(elsewhere)},
        capture_output=True, text=True, check=True,
    )
    assert f"FIRST {elsewhere / 'clinvar'}" in done.stdout
