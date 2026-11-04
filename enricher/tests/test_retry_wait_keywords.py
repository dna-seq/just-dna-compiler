"""Every backoff names tenacity's `multiplier`, never the deprecated `initial` (RM371, S128).

tenacity 9.2.1 renamed `wait_exponential_jitter(initial=...)` to `multiplier=` and warns on the old
keyword. Each enricher client builds its wait inside a module-level `@retry` decorator, so the warning
fires at **import**, once per site, in every consumer that imports the module. The warning is the
small half: the floor had no cap, so the release that drops `initial` would have turned all eighteen
decorators into a `TypeError` at import and taken every enricher command with them. That is the
failure shape S107 had with protobuf.

**Why a static walk.** The suite errors on `DeprecationWarning`, but only under the tenacity the lock
installs, and only for modules a test happens to import. The walk reads the package's source, so a new
client is covered the day it is written, whatever is installed.

Two shapes are refused, not one. In 9.2.1 the **first positional** parameter is still `initial`, so
`wait_exponential_jitter(0.5, max=8)` is the same deprecated call with the name left off.
"""

import ast
import re
import tomllib
from pathlib import Path

import just_dna_enricher
from packaging.version import Version

_PACKAGE = Path(just_dna_enricher.__file__).parent
_PYPROJECT = _PACKAGE.parents[1] / "pyproject.toml"

# The first tenacity release whose `wait_exponential_jitter` takes `multiplier`. PyPI has no 9.2.0, and
# 9.1.4's constructor is `(initial, max, exp_base, jitter)` only, so a floor below this would install a
# tenacity the renamed calls raise `TypeError` on.
_MULTIPLIER_SINCE = Version("9.2.1")


def _is_wait_exponential_jitter(call: ast.Call) -> bool:
    func = call.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    return name == "wait_exponential_jitter"


def _wait_calls() -> list[tuple[str, ast.Call]]:
    found: list[tuple[str, ast.Call]] = []
    for path in sorted(_PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_wait_exponential_jitter(node):
                found.append((f"{path.relative_to(_PACKAGE)}:{node.lineno}", node))
    return found


def test_every_backoff_names_multiplier_and_never_initial() -> None:
    calls = _wait_calls()
    # A walk that finds nothing passes for any source; the package has retried clients, so an empty
    # result means the walk is broken, not that the rule holds.
    assert calls, "found no wait_exponential_jitter call under the enricher package"
    offenders = [
        site
        for site, call in calls
        if call.args or any(keyword.arg == "initial" for keyword in call.keywords)
    ]
    assert offenders == [], (
        "wait_exponential_jitter passes the deprecated `initial` (by name or as the first positional "
        f"argument) at {offenders}; spell it `multiplier=`"
    )
    unnamed = [site for site, call in calls if not any(k.arg == "multiplier" for k in call.keywords)]
    assert unnamed == [], (
        f"wait_exponential_jitter at {unnamed} states no `multiplier=`, so its backoff is tenacity's "
        "default rather than a value this client chose"
    )


def test_the_tenacity_floor_carries_the_multiplier_keyword() -> None:
    dependencies = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]
    (spec,) = [dep for dep in dependencies if re.match(r"tenacity\b", dep)]
    floor = re.search(r">=\s*([0-9][0-9.]*)", spec)
    assert floor is not None, f"the tenacity requirement {spec!r} states no floor"
    assert Version(floor.group(1)) >= _MULTIPLIER_SINCE, (
        f"{spec!r} admits a tenacity whose wait_exponential_jitter has no `multiplier`"
    )
