"""Every backoff goes through one shim that spells tenacity's first-wait keyword (RM371, then RM436).

tenacity 9.2.1 renamed `wait_exponential_jitter(initial=...)` to `multiplier=` and warns on the old keyword.
Each enricher client builds its wait inside a module-level `@retry` decorator, so a deprecated spelling warns
at **import**, once per site, in every consumer (RM371, S128). RM371 fixed that by renaming every site and
flooring `tenacity>=9.2.1`. That floor could not resolve beside google-genai, which caps `tenacity<9.2.0`
in every release (RM436, S149). So the keyword is now picked in one place, `net._jittered_backoff`, by the
installed constructor's signature, and the floor sits below 9.2.

**Why a static walk.** The suite errors on `DeprecationWarning`, but only under the tenacity the lock
installs, and only for modules a test happens to import. The walk reads the package's source, so a new
client is covered the day it is written, whatever is installed.
"""

import ast
import inspect
import re
import tomllib
import warnings
from pathlib import Path

import just_dna_enricher
from just_dna_enricher import net
from packaging.version import Version
from tenacity import wait_exponential_jitter

_PACKAGE = Path(just_dna_enricher.__file__).parent
_PYPROJECT = _PACKAGE.parents[1] / "pyproject.toml"

#: google-genai's cap, in every release checked (S149): `tenacity<9.2.0`. The floor must admit a release below it.
_GENAI_CAP = Version("9.2.0")

#: The floor a run proved (RM436): the enricher suite passed with `tenacity==9.0.0` installed over the lock, and
#: with the lock's newest, with no deprecation warning on either side.
_PROVED_FLOOR = Version("9.0.0")


def _is_wait_exponential_jitter(call: ast.Call) -> bool:
    func = call.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    return name == "wait_exponential_jitter"


def _wait_calls() -> list[tuple[str, str | None]]:
    """Every `wait_exponential_jitter(...)` call, with the function that most closely encloses it."""
    found: list[tuple[str, str | None]] = []
    for path in sorted(_PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        enclosing: dict[int, str] = {}
        # Outer functions first, inner ones after, so the innermost name wins for a nested call.
        for function in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)):
            for node in ast.walk(function):
                enclosing[id(node)] = function.name
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_wait_exponential_jitter(node):
                found.append((f"{path.relative_to(_PACKAGE)}:{node.lineno}", enclosing.get(id(node))))
    return found


def test_no_client_spells_the_wait_keyword_itself() -> None:
    calls = _wait_calls()
    # A walk that finds nothing passes for any source; the shim calls it, so an empty result means the walk
    # is broken, not that the rule holds.
    assert calls, "found no wait_exponential_jitter call under the enricher package"
    outside = sorted({site for site, enclosing in calls if enclosing != "_jittered_backoff"})
    assert outside == [], (
        f"wait_exponential_jitter is called at {outside}; build the wait with net._jittered_backoff(base=, cap=), "
        "the one place that picks `multiplier=` or `initial=` by the installed tenacity"
    )
    assert all(site.startswith("net.py:") for site, _ in calls)


def test_the_shim_picks_the_keyword_the_installed_tenacity_takes() -> None:
    takes = "multiplier" in inspect.signature(wait_exponential_jitter.__init__).parameters
    assert net._JITTER_TAKES_MULTIPLIER is takes
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # RM371's deprecation is an error here, on any tenacity
        wait = net._jittered_backoff(base=0.5, cap=8.0)
    assert wait.max == 8.0
    # Both spellings land on the same first wait, so a client's backoff does not move with the release.
    assert getattr(wait, "multiplier", None) == 0.5 or getattr(wait, "initial", None) == 0.5


def test_the_tenacity_floor_is_the_proved_one_and_below_google_genais_cap() -> None:
    dependencies = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]
    (spec,) = [dep for dep in dependencies if re.match(r"tenacity\b", dep)]
    floor = re.search(r">=\s*([0-9][0-9.]*)", spec)
    assert floor is not None, f"the tenacity requirement {spec!r} states no floor"
    assert Version(floor.group(1)) == _PROVED_FLOOR, (
        f"{spec!r}: the floor is the release a run proved ({_PROVED_FLOOR}); re-run the suite on a new one first"
    )
    assert Version(floor.group(1)) < _GENAI_CAP, (
        f"{spec!r} cannot resolve beside google-genai's tenacity<9.2.0"
    )
