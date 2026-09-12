"""Write the site's home page and its API reference at **build time**, never onto disk.

`mkdocs-gen-files` hands this script a virtual filesystem rooted at `docs/`, so everything it writes
exists only inside `data/site/`. That is the point: `docs/` root "holds only what is still live"
(CLAUDE.md), `schema/tests/test_doc_links.py` walks every tracked markdown file, and
`schema/tests/test_docs_site_nav.py` asserts the nav and `not_in_nav` partition exactly the files
that are *there*. An `index.md` and a hundred `api/*.md` committed into `docs/` would make all three
answer questions about pages nobody wrote.

**It lives in `scripts/` under protest, and the alternative was worse.** `scripts/README.md` draws the
line at audience — an operator runs what is here, an agent runs what is in `.claude/` — and nobody runs
this one by hand: `mkdocs build` does, through the `gen-files` plugin. It is still closer to an
operator's build than to agent tooling, and the only other home is a loose module in the repository
root, which the data conventions rule out for generated things and taste rules out for this.

The API reference is **derived** from the source tree rather than listed: three packages, around a
hundred modules, and a hand-kept list loses one (`@registry-completeness`).
"""

import re
from pathlib import Path

import mkdocs_gen_files

_ROOT = Path(__file__).resolve().parents[1]
_BLOB = "https://github.com/dna-seq/just-dna-format/blob/main"

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

_LINK = re.compile(r"(\[[^\]]*\]\(\s*)([^)\s]+)(\s*\))")


def _rewrite_target(target: str) -> str:
    """Point a README link at the right thing once the README is the site's home page.

    Three cases, decided from the path alone. A link into `docs/` becomes site-relative, because that
    file *is* a page here. A link at anything else in the repository — `schema/`,
    `reference_examples/apoe_epsilon/`, `CLAUDE.md` — becomes an absolute GitHub URL, since the site
    carries no copy of it and a relative path would 404. Anything already absolute, or a bare
    fragment, is left alone.
    """
    if target.startswith(("http://", "https://", "#", "mailto:")):
        return target
    path, _, fragment = target.partition("#")
    suffix = f"#{fragment}" if fragment else ""
    if path.startswith("docs/"):
        return path.removeprefix("docs/") + suffix
    return f"{_BLOB}/{path.rstrip('/')}{suffix}"


def _write_home() -> None:
    """`index.md`, from the README, with its links repointed.

    The README is the maintained front door and it is what a visitor to the repository reads first;
    keeping one text means the site's home page cannot drift from it, which is the failure a
    hand-written duplicate reaches within one release.
    """
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    body = _LINK.sub(lambda m: m[1] + _rewrite_target(m[2]) + m[3], readme)
    with mkdocs_gen_files.open("index.md", "w") as fh:
        fh.write(body)
    mkdocs_gen_files.set_edit_path("index.md", "README.md")


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
            mkdocs_gen_files.set_edit_path(doc_path, source)
            label = dotted.split(".")[-1] if dotted != package else "Overview"
            lines.append(f"    - [{label}]({doc_path.relative_to('api').as_posix()})\n")
    with mkdocs_gen_files.open("api/SUMMARY.md", "w") as fh:
        fh.writelines(lines)


_write_home()
_write_api()
