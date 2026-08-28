"""Cache locations: the `.env` has to be loaded before the default directory is computed.

Every assertion that *resolves* anything runs in a **subprocess** with a controlled cwd and
environment, and that is not incidental. The bug is process-scoped ordering — it only shows on the *first* resolve — and
`locations.load_env()` mutates `os.environ` for the rest of the session, so an in-process test would
both miss the defect and leak the repo's own `.env` into every test that ran after it.
"""

import inspect
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from just_dna_enricher import locations

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
    """Run a probe with `$JUST_DNA_PIPELINES_CACHE_DIR` unset, so only the `.env` can supply it.

    **`XDG_CACHE_HOME` is redirected at an empty directory**, which is what makes "nothing supplied a
    base, so the resolve misses" a property of the arrangement rather than of the developer's laptop.
    Without it the platformdirs fallback finds whatever real snapshot the machine happens to hold, so
    `test_without_the_load_the_first_resolve_really_did_miss` passes on a clean checkout and fails for
    anyone who has run `cache pull` — the documented workflow. Same trap as the `.env` credentials in
    CLAUDE.md: green on CI, broken on the machine that actually uses the tool. (Linux/XDG; a macOS
    runner would need the same redirection through its own cache variable.)
    """
    env = {k: v for k, v in os.environ.items() if k != "JUST_DNA_PIPELINES_CACHE_DIR"}
    env["XDG_CACHE_HOME"] = tempfile.mkdtemp(prefix="just-dna-empty-cache-")
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


# ── the off-switch (S39) ────────────────────────────────────────────────────────────────────────
#
# `load_dotenv_file=False` reached none of the six resolvers until 0.6.3: each passes its
# `default_*_cache_dir()` as an *argument*, and that helper loaded the `.env` unconditionally, so the
# load happened before the resolver had looked at its own flag. Two properties are worth pinning
# separately — that the knob works, and that every resolver *has* it — because the second is what a
# seventh snapshot would silently break.

#: A variable no real `.env` has, so a leak cannot be mistaken for the developer's own environment.
_MARKER = "JUST_DNA_S39_PROBE_TOKEN"

_LEAK_PROBE = f"""
import os
from just_dna_enricher import locations
os.environ.pop({_MARKER!r}, None)
locations.{{resolver}}(load_dotenv_file={{flag}})
print("MARKER", os.environ.get({_MARKER!r}, "unset"))
"""

#: The pre-fix arrangement, restored in-process: `_cache_dir` ignoring the flag it is handed.
_LEAK_PROBE_WITHOUT_THE_FIX = f"""
import os
import just_dna_enricher.locations as loc
_real = loc._cache_dir
loc._cache_dir = lambda subdir, *, load_dotenv_file=True: _real(subdir, load_dotenv_file=True)
os.environ.pop({_MARKER!r}, None)
loc.{{resolver}}(load_dotenv_file=False)
print("MARKER", os.environ.get({_MARKER!r}, "unset"))
"""


def _resolver_names() -> list[str]:
    """Every `resolve_*_reference` the module publishes, walked rather than listed.

    A hand-kept list is the defect this repo keeps meeting: it is complete on the day it is written
    and silently short afterwards. The seventh snapshot's resolver joins these tests by existing.
    """
    return sorted(n for n in dir(locations) if n.startswith("resolve_") and n.endswith("_reference"))


@pytest.fixture
def dotenv_with_a_credential(tmp_path) -> Path:
    """A working directory whose `.env` holds a credential-shaped variable and nothing else."""
    work = tmp_path / "work"
    work.mkdir()
    (work / ".env").write_text(f"{_MARKER}=leaked_from_the_dotenv\n", encoding="utf-8")
    return work


@pytest.mark.parametrize("resolver", _resolver_names())
def test_load_dotenv_file_false_leaves_the_process_environment_alone(
    resolver, dotenv_with_a_credential
) -> None:
    """The consumer's report (S39): a library call refilling a variable a test had deleted.

    `load_dotenv(override=False)` skips a variable that is **present**, so deleting one is precisely
    what lets the file win — which is why the leak shows up as a test's own isolation being undone.
    """
    out = _run(_LEAK_PROBE.format(resolver=resolver, flag="False"), dotenv_with_a_credential)
    assert out["MARKER"] == "unset"


@pytest.mark.parametrize("resolver", _resolver_names())
def test_the_default_still_loads_the_dotenv(resolver, dotenv_with_a_credential) -> None:
    """The other half: the flag is what did it, not a fixture that failed to write a `.env`.

    The unconditional load is a fix in its own right (three "the cache is right there" reports), so
    the repair threads the flag rather than removing the load.
    """
    out = _run(_LEAK_PROBE.format(resolver=resolver, flag="True"), dotenv_with_a_credential)
    assert out["MARKER"] == "leaked_from_the_dotenv"


@pytest.mark.parametrize("resolver", _resolver_names())
def test_without_the_fix_the_off_switch_really_did_leak(resolver, dotenv_with_a_credential) -> None:
    """The demonstration on the old arrangement, not an assertion about it."""
    out = _run(_LEAK_PROBE_WITHOUT_THE_FIX.format(resolver=resolver), dotenv_with_a_credential)
    assert out["MARKER"] == "leaked_from_the_dotenv"


def test_every_resolver_and_default_dir_takes_the_off_switch() -> None:
    """The knob is only as complete as the set of functions carrying it.

    Both families are walked: a resolver that forgot the parameter, or a `default_*_cache_dir` that
    cannot be told, puts the leak straight back for that one snapshot.

    **The premise is an equality over the two walked sets, not a count.** It was
    `len(named) == 12` with "expected six resolvers and six default dirs" in the message, and the
    seventh snapshot (PubMind, RM134) failed it for no reason but arithmetic — a counted prose
    assertion that has to be edited every time the thing it guards grows correctly. Pairing the
    families by snapshot name says something the count never did: that no resolver is missing its
    default directory and no default directory is orphaned.
    """
    defaults = sorted(
        n for n in dir(locations) if n.startswith("default_") and n.endswith("_cache_dir")
    )
    named = _resolver_names() + defaults
    assert {n.removeprefix("resolve_").removesuffix("_reference") for n in _resolver_names()} == {
        n.removeprefix("default_").removesuffix("_cache_dir") for n in defaults
    }, f"a resolver and its default cache directory do not pair up: {named}"
    without = [
        n for n in named
        if "load_dotenv_file" not in inspect.signature(getattr(locations, n)).parameters
    ]
    assert without == [], f"cannot be told to leave the environment alone: {without}"
