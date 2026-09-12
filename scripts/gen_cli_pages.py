"""Write the site's CLI reference at **build time**, derived from the Typer apps themselves.

The two tools carry dozens of top-level commands each, and the enricher's are mostly sub-apps with
their own subcommands — of the order of a hundred commands and several hundred flags. `CLAUDE.md` already records
what happens to a hand-kept version of that: *"a command-surface table rots silently (no test reads
it)"*, which is why the authoring surface delegates everything about schemas to `describe` /
`requirements` / `reference` rather than restating it. The same argument applies one level up, so the
pages below are walked off the live `click` command tree — a flag that is added, renamed or given a new
default shows up in the next build with nobody remembering to edit anything.

**Nothing here may use `isinstance` against `click`, and that is not a style preference.** Typer 0.20
vendors its own copy of click: a command's parameters are `typer.core.TyperArgument` and
`TyperOption`, whose MRO runs through `typer._click.core.Parameter` and never touches the installed
`click` package at all. So `isinstance(param, click.Option)` is `False` for every option there has ever
been, and the first version of this script emitted a heading and a help paragraph per command with the
argument and option tables **silently empty** — a hundred pages that looked finished. The discriminator
is `param.param_type_name`, which both spellings of click carry and which says `"argument"` or
`"option"` directly, so the parameters are read structurally and typed as `Any`.

**And the rule is now enforced here rather than only in a test, because the failure is invisible to
every other gate.** `--strict` was green over those hundred empty pages, the links resolved and the nav
partitioned — a docs build in CI would have published them. So `_render` asserts the parameter names it
rendered against `_expected_parameters`, which walks `command.params` **without** the classification, so
a classification matching nothing leaves the expected set full and the rendered one empty and the build
stops. Verified by reintroducing the `isinstance` version and watching the build fail naming
`just-dna-compiler close`'s three parameters, then restoring from a copy — `cp`, never `git checkout`,
which reverts a file rather than a line.

**Structured rather than captured.** The obvious alternative is to shell out to `--help` and fence the
output, and it is worse in three ways: Typer renders through Rich, so the text arrives wrapped into a
box at whatever width the build happens to run at, long help strings are truncated with an ellipsis
that loses the sentence, and the result is a screenshot rather than something a reader can search or a
link can point at. So this reads `click`'s own objects — `Command.help`, each `Parameter`'s opts, type,
default and help — and emits real markdown tables.

It sits beside `gen_api_pages.py`, shares its `mkdocs-gen-files` virtual filesystem, and lands nothing
on disk for the same reason: `docs/` root "holds only what is still live", and
`schema/tests/test_docs_site_nav.py` asserts that `nav` and `not_in_nav` partition exactly the files
that are *there*.
"""

from typing import Any

import mkdocs_gen_files
import typer.main
from just_dna_compiler import cli as compiler_cli
from just_dna_enricher import cli as enricher_cli

#: `<command name>: (<page slug>, <the Typer app>)`, in the order a reader meets them — the compiler
#: first, because a module is compiled before anything enriches it, and because the compiler is the
#: tier more readers install.
_TOOLS: tuple[tuple[str, str, typer.Typer], ...] = (
    ("just-dna-compiler", "compiler", compiler_cli.app),
    ("just-dna-enricher", "enricher", enricher_cli.app),
)

#: Flags every command inherits and no reader needs listed ninety times.
_UNINTERESTING = frozenset({"--help", "--install-completion", "--show-completion"})


def _clean(text: str | None) -> str:
    """One-line a help string for a table cell.

    Typer help is written as a paragraph and often carries a blank line and a second one; a markdown
    table row cannot hold either, and a raw `|` in a default value would end the cell.
    """
    if not text:
        return ""
    return " ".join(text.split()).replace("|", "\\|")


def _default(param: Any) -> str:
    """What the parameter falls back to, or `required`, as a cell."""
    if param.required:
        return "**required**"
    value = param.default
    if value is None or value is False:
        return ""
    if value is True:
        return "on"
    return f"`{_clean(str(value))}`"


def _type_name(param: Any) -> str:
    """The parameter's type as the user sees it, with a flag pair spelled as a flag."""
    if getattr(param, "is_flag", False):
        return "flag"
    name = getattr(param.type, "name", "") or ""
    return f"`{name}`" if name else ""


def _expected_parameters(command: Any) -> set[str]:
    """Every parameter this command declares that a reader should see a row for.

    Ground truth for the assertion in `_render`, and deliberately computed **without** the
    argument/option classification the rows go through: `command.params` is the list click itself
    keeps, so a classification that matches nothing leaves this set full and the rendered one empty.
    The only exclusions are the inherited flags and a parameter whose every spelling is one of them.
    """
    expected = set()
    for param in command.params:
        opts = [o for o in (*param.opts, *getattr(param, "secondary_opts", ())) if o not in _UNINTERESTING]
        if opts:
            expected.add(param.name)
    return expected


def _parameter_rows(command: Any) -> tuple[list[str], list[str], set[str]]:
    """`(argument rows, option rows, the parameter names rendered)` for one command's tables."""
    arguments: list[str] = []
    options: list[str] = []
    rendered: set[str] = set()
    for param in command.params:
        if param.param_type_name == "argument":
            arguments.append(
                f"| `{param.name}` | {_type_name(param)} | {_default(param)} | "
                f"{_clean(getattr(param, 'help', None))} |"
            )
            rendered.add(param.name)
            continue
        if param.param_type_name != "option":
            continue
        opts = [o for o in (*param.opts, *param.secondary_opts) if o not in _UNINTERESTING]
        if not opts:
            continue
        spelled = " / ".join(f"`{o}`" for o in opts)
        options.append(f"| {spelled} | {_type_name(param)} | {_default(param)} | {_clean(param.help)} |")
        rendered.add(param.name)
    return arguments, options, rendered


def _render(command: Any, invocation: str, level: int) -> list[str]:
    """One command as markdown: a heading, its help paragraph, then its two tables.

    `level` is the heading depth, so a sub-app's children sit under it rather than beside it.
    """
    lines = [f"{'#' * level} `{invocation}`\n\n"]
    help_text = command.help or command.short_help
    if help_text:
        # Typer keeps the docstring's own line breaks, and a paragraph break has to survive: the
        # command help below is prose that was written to be read, not a one-liner.
        lines.append("\n".join(line.strip() for line in help_text.splitlines()).strip() + "\n\n")
    arguments, options, rendered = _parameter_rows(command)
    missing = _expected_parameters(command) - rendered
    if missing:
        raise AssertionError(
            f"`{invocation}` declares {sorted(missing)} and the generated page shows no row for them "
            "— the classification above matched nothing, which renders a page that looks finished and "
            "documents nothing. See this module's docstring on Typer's vendored click."
        )
    if arguments:
        lines.append("| Argument | Type | Default | Says |\n|---|---|---|---|\n")
        lines.extend(f"{row}\n" for row in arguments)
        lines.append("\n")
    if options:
        lines.append("| Option | Type | Default | Says |\n|---|---|---|---|\n")
        lines.extend(f"{row}\n" for row in options)
        lines.append("\n")
    return lines


def _walk(command: Any, invocation: str, level: int) -> list[str]:
    """One command and, when it is a group, every subcommand beneath it.

    Sorted, so the page is stable between builds — the same reason the API reference sorts and the
    same reason emitted rows are sorted everywhere else in this project.
    """
    lines = _render(command, invocation, level)
    children = getattr(command, "commands", {})
    for name in sorted(children):
        lines.extend(_walk(children[name], f"{invocation} {name}", level + 1))
    return lines


def _write_tool(binary: str, slug: str, app: typer.Typer) -> None:
    group = typer.main.get_command(app)
    lines = [f"# `{binary}`\n\n"]
    if group.help:
        lines.append("\n".join(line.strip() for line in group.help.splitlines()).strip() + "\n\n")
    lines.append(
        "Generated from the command tree itself at build time, so a flag added or renamed in the "
        "code appears here without anyone editing a table.\n\n"
    )
    for name in sorted(getattr(group, "commands", {})):
        lines.extend(_walk(group.commands[name], f"{binary} {name}", 2))
    with mkdocs_gen_files.open(f"cli/{slug}.md", "w") as fh:
        fh.writelines(lines)


def _write_summary() -> None:
    """The `SUMMARY.md` that `literate-nav` turns into the CLI section."""
    with mkdocs_gen_files.open("cli/SUMMARY.md", "w") as fh:
        for binary, slug, _ in _TOOLS:
            fh.write(f"- [{binary}]({slug}.md)\n")


for _binary, _slug, _app in _TOOLS:
    _write_tool(_binary, _slug, _app)
_write_summary()
