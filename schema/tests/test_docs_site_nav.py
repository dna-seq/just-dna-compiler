"""`mkdocs.yml`'s `nav` and `not_in_nav` together account for **every** file in `docs/`.

**Why this is a test.** A docs site's navigation is a hand-kept list over a directory that grows, which
is this project's most-repeated defect shape: `RM_TOC.md` exists because an item became unfindable when
neither table was complete, `test_counted_prose.py` exists because the same count went stale twice, and
the rule drawn from those is `@registry-completeness` — *assert an equality over a walked set, never a
floor or a count in prose*. Nothing about a missing nav entry is visible in a build: MkDocs reports an
un-navigated page at `INFO`, `--strict` does not care, and the page is reachable by URL and by search,
so the site looks fine and the sidebar is quietly one document short. The next `docs/SOMETHING.md`
either belongs in the reader's path or belongs in the records, and this is what forces that choice to
be made rather than defaulted.

**The partition is the assertion, not either half.** `nav` is curated and `not_in_nav` lists the
development records; a file in both, or in neither, is the failure. The equality is reported as a
symmetric difference so a run names the file rather than a count.

It sits beside `test_doc_links.py` for the same reason that one does: a guard over a surface a *reader*
consumes rather than over a tier's behaviour, importing nothing from any package and walking the
repository. Those two divide the work — this one asks whether every page is placed, that one asks
whether every link between them resolves.

**The docs group is not installed when this runs.** `uv sync` omits it (it is not in `default-groups`),
so nothing here may import `mkdocs`, and `yaml` arrives through pydantic's neighbours rather than as a
declared test dependency — it is the compiler tier's dependency, already used by other tests in this
suite the same way.
"""

import ast
import fnmatch
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_CONFIG = _ROOT / "mkdocs.yml"


class _TagTolerantLoader(yaml.SafeLoader):
    """`yaml.SafeLoader` that reads a Material config instead of refusing it.

    A Material `mkdocs.yml` names Python callables through `!!python/object/apply:` and `!!python/name:`
    tags — this one uses the first for the GitHub-compatible heading slugifier, which is what makes the
    corpus's 540-odd `FILE.md#anchor` links resolve. `yaml.safe_load` raises on an unknown tag, so a
    guard built on it could not parse its own subject, and the alternative (a config with no python tag
    at all) is a config that cannot spell a slugifier. `unsafe_load` is not the answer either: it would
    *construct* whatever the file names, and this test only needs the shape of `nav`.

    So unknown tags resolve to `None`. Nothing below reads a tagged value.
    """


_TagTolerantLoader.add_multi_constructor("", lambda loader, suffix, node: None)


def _config() -> dict:
    return yaml.load(_CONFIG.read_text(encoding="utf-8"), Loader=_TagTolerantLoader)


def _nav_entries(nav: object) -> list[str]:
    """Every target in `nav`, flattened out of the nested title/entry mapping MkDocs accepts.

    A nav is a list whose members are either a bare path or a single-key mapping from a title to a path
    or to another such list. Both spellings appear in this config — `CHANGELOG.md` sits at the top level
    while `SCHEMAS.md` sits under *Reference* — so a reader of only one shape would silently see half
    the nav.
    """
    found: list[str] = []
    if isinstance(nav, str):
        found.append(nav)
    elif isinstance(nav, list):
        for item in nav:
            found.extend(_nav_entries(item))
    elif isinstance(nav, dict):
        for value in nav.values():
            found.extend(_nav_entries(value))
    return found


def _walked_docs(docs_dir: Path) -> set[str]:
    """Every markdown file under `docs/`, as a posix path relative to it."""
    return {p.relative_to(docs_dir).as_posix() for p in docs_dir.rglob("*.md")}


def _excluded(patterns: str, walked: set[str]) -> set[str]:
    """The walked files `not_in_nav` matches, under the gitignore-ish subset this config uses.

    Three spellings, because that is what `mkdocs.yml` spells: a bare filename, a directory with a
    trailing slash meaning everything beneath it, and a **`!` line that re-includes** — gitignore
    semantics, applied in order, which is how one archived page (`history/INTEGRATION_0_6.md`) sits in
    the nav while the rest of `history/` stays out of it. Comment lines are skipped.

    Implemented rather than delegated because the real matcher lives in `mkdocs`, which is not installed
    here — and a fourth spelling appearing in the config would show up as a file in neither half, which
    is exactly what the partition assertion reports.
    """
    matched: set[str] = set()
    for raw in patterns.split("\n"):
        pattern = raw.strip()
        if not pattern or pattern.startswith("#"):
            continue
        negated = pattern.startswith("!")
        pattern = pattern.removeprefix("!")
        if pattern.endswith("/"):
            hit = {f for f in walked if f.startswith(pattern)}
        else:
            hit = {f for f in walked if fnmatch.fnmatch(f, pattern)}
        matched = (matched - hit) if negated else (matched | hit)
    return matched


def _gen_scripts() -> list[Path]:
    """Every script the `gen-files` plugin runs, read off the config rather than listed here.

    It was a single hardcoded path until a second generator (the CLI reference) was added, at which
    point the guard went on checking one script and answered about the other by not knowing it existed
    — `@registry-completeness`, the defect shape this file's own docstring is about. The plugin's
    `scripts:` list is the registry, so this walks it.
    """
    for plugin in _config()["plugins"]:
        if isinstance(plugin, dict) and "gen-files" in plugin:
            return [_ROOT / s for s in plugin["gen-files"]["scripts"]]
    raise AssertionError("mkdocs.yml declares no `gen-files` plugin, so no page is generated at all")


def _generated_prefixes() -> set[str]:
    """The site paths the gen-files scripts write, read out of them rather than restated.

    A nav entry may legitimately name a page that is not in `docs/` — the home page, the API reference
    built from the packages' docstrings, and the CLI reference walked off the Typer apps, all written
    into the build by `mkdocs-gen-files` so that nothing lands on disk. Naming them here as literals
    would be a second copy of each script's behaviour, and the copy is what goes stale; so they are
    derived from the scripts' own string literals, which is how `test_build_call_sites.py` reads the
    CLI.
    """
    tree = ast.parse("\n".join(p.read_text(encoding="utf-8") for p in _gen_scripts()))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "/" in node.value
        or isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.endswith(".md")
    }


def test_nav_and_not_in_nav_partition_the_docs_directory() -> None:
    config = _config()
    docs_dir = _ROOT / config["docs_dir"]
    walked = _walked_docs(docs_dir)
    assert walked, f"no markdown found under {docs_dir} — the walk, not the docs, is what broke"

    navigated = {e for e in _nav_entries(config["nav"]) if e in walked}
    excluded = _excluded(config["not_in_nav"], walked)

    assert not (navigated & excluded), (
        "these files are both navigated and listed in `not_in_nav`; a page is in the reader's path or "
        f"in the records, never both: {sorted(navigated & excluded)}"
    )
    unaccounted = walked - navigated - excluded
    assert not unaccounted, (
        "these files under docs/ appear in neither `nav` nor `not_in_nav`, so they are published "
        "without a place in the sidebar — add each to whichever it belongs to: "
        f"{sorted(unaccounted)}"
    )
    # Asked of the *patterns*, not of `excluded`: `excluded - walked` is empty by construction, since
    # `_excluded` only ever selects from `walked` — a check that cannot fail must not report a zero
    # (`@tautology-zero`). A pattern matching nothing is the real defect, and it is the one that
    # survives a file being renamed or archived: the exclusion stays, silently covering nothing.
    # Every pattern must still name something. Comments are skipped, and a `!` exception is checked on
    # its own terms: it is measured with the `!` stripped, because a dead re-inclusion is as stale as a
    # dead exclusion — it says "this page is the exception" about a page that is no longer there.
    idle = []
    for line in config["not_in_nav"].split("\n"):
        pattern = line.strip()
        if not pattern or pattern.startswith("#"):
            continue
        if not _excluded(pattern.removeprefix("!"), walked):
            idle.append(pattern)
    assert not idle, (
        "these `not_in_nav` patterns match no file under docs/, so they exclude (or re-include) nothing "
        f"— a renamed or archived page leaves one behind: {idle}"
    )


def test_every_nav_entry_exists_or_is_generated_by_the_build() -> None:
    """A nav entry names a real file in `docs/`, or a path the gen-files script writes."""
    config = _config()
    walked = _walked_docs(_ROOT / config["docs_dir"])
    generated = _generated_prefixes()
    missing = [
        entry
        for entry in _nav_entries(config["nav"])
        if entry not in walked and not any(g == entry or g.startswith(entry) for g in generated)
    ]
    assert not missing, (
        "these nav entries point at neither a file under docs/ nor anything the gen-files scripts "
        f"write: {missing}"
    )


def test_the_site_is_built_outside_the_repository_root() -> None:
    """`site_dir` lands under `data/`, which the workspace git-ignores wholesale.

    The house rule is that nothing a command generates goes in the repository root, and MkDocs' default
    `site_dir` is exactly that — a `site/` beside `docs/`, which would also be walked by
    `test_doc_links.py` as a second copy of every document. Every builder's `--out` is under `data/` for
    the same reason and a test refuses one that spells its own.
    """
    site_dir = Path(_config()["site_dir"])
    assert not site_dir.is_absolute(), f"site_dir must stay inside the checkout, got {site_dir}"
    assert site_dir.parts[0] == "data", (
        f"site_dir must be under data/ (git-ignored build output), got {site_dir}"
    )
