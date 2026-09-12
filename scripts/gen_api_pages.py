"""Write the site's API reference at **build time**, never onto disk.

`mkdocs-gen-files` hands this script a virtual filesystem rooted at `docs/`, so everything it writes
exists only inside `data/site/`. That is the point: `docs/` root "holds only what is still live"
(CLAUDE.md), `schema/tests/test_doc_links.py` walks every tracked markdown file, and
`schema/tests/test_docs_site_nav.py` asserts the nav and `not_in_nav` partition exactly the files
that are *there*. A hundred `api/*.md` committed into `docs/` would make all three answer
questions about pages nobody wrote.

**It lives in `scripts/` under protest, and the alternative was worse.** `scripts/README.md` draws the
line at audience — an operator runs what is here, an agent runs what is in `.claude/` — and nobody runs
this one by hand: `mkdocs build` does, through the `gen-files` plugin. It is still closer to an
operator's build than to agent tooling, and the only other home is a loose module in the repository
root, which the data conventions rule out for generated things and taste rules out for this.

The API reference is **derived** from the source tree rather than listed: three packages, around a
hundred modules, and a hand-kept list loses one (`@registry-completeness`).
"""

from pathlib import Path

import mkdocs_gen_files

_ROOT = Path(__file__).resolve().parents[1]
#: `<import name>: <source root>`, in the dependency order the README presents them — format first,
#: because a reader meets the contract before the tools that target it.
_PACKAGES: tuple[tuple[str, str], ...] = (
    ("just_dna_format", "schema/src"),
    ("just_dna_compiler", "compiler/src"),
    ("just_dna_enricher", "enricher/src"),
)

#: Directory names under a package that hold no hand-written module. `generated`/`_atlas_protos` are
#: `protoc` output — already excluded from ruff for the same reason — and rendering their docstrings
#: would bury the surface a reader came for under machine-written stubs.
_SKIP_DIRS = frozenset({"__pycache__", "generated", "_atlas_protos"})

#: What `set_edit_path` needs prepended to reach a file **outside** `docs/`. The path it takes is
#: resolved against `docs_dir` and then appended to `edit_uri` (`edit/main/docs/`), so every
#: `*/src/**.py` this script renders — none of them under `docs/` — came out as
#: `edit/main/docs/schema/src/…`, a 404 on the edit button of every generated page. Found by reading the emitted `href`, which is the only place it is visible:
#: `mkdocs`/`properdocs` validate a page's *links* and never the edit URL they compose.
_EDIT_ROOT = "../"


def _modules(package: str, src: str) -> list[tuple[str, Path]]:
    """Every importable module in one package, as `(dotted name, path relative to the repository)`.

    Sorted, so the generated nav is stable between builds — the same reason emitted rows are sorted
    everywhere else in this project.
    """
    root = _ROOT / src / package
    found: list[tuple[str, Path]] = []
    for path in sorted(root.rglob("*.py")):
        parts = path.relative_to(_ROOT / src).with_suffix("").parts
        if _SKIP_DIRS.intersection(parts):
            continue
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            continue
        found.append((".".join(parts), path.relative_to(_ROOT)))
    return found


def _write_api() -> None:
    """One page per module, plus the `SUMMARY.md` that `literate-nav` turns into the API section."""
    lines: list[str] = []
    for package, src in _PACKAGES:
        lines.append(f"- {package}\n")
        for dotted, source in _modules(package, src):
            doc_path = Path("api", *dotted.split(".")).with_suffix(".md")
            with mkdocs_gen_files.open(doc_path, "w") as fh:
                fh.write(f"# `{dotted}`\n\n::: {dotted}\n")
            mkdocs_gen_files.set_edit_path(doc_path, _EDIT_ROOT + source.as_posix())
            label = dotted.split(".")[-1] if dotted != package else "Overview"
            lines.append(f"    - [{label}]({doc_path.relative_to('api').as_posix()})\n")
    with mkdocs_gen_files.open("api/SUMMARY.md", "w") as fh:
        fh.writelines(lines)


_write_api()
