"""Every command a message or docstring quotes is one an app registers (RM427, S142).

A message that names a remedy is read as an instruction, and an author copies it. The clinical-assertion
pass's skip told them to run `clinvar pull` in two places, the log line and the CLI's own line, after
`pull` had moved under `cache`; both answered "No such command". The reporter's walk keyed on the
`just-dna-*` prefix and found only the first, and a hand check had already read the second as gone when
it had only moved file. So this walks every backticked span in the three `src/` trees, prefixed or not,
and resolves each group-and-subcommand path against the command trees the two typer apps build.

Typer ships its own copy of click, so `isinstance(cmd, click.Group)` is False for every group it
builds; a group is found by having `commands`, which is the attribute the resolution reads anyway.
"""

import re
from pathlib import Path

import pytest
import typer.main
from just_dna_compiler.cli import app as compiler_app
from just_dna_enricher.cli import app as enricher_app

_REPO = Path(__file__).resolve().parents[2]
_SPAN = re.compile(r"`([^`\n]+)`")
_WORD = re.compile(r"^[a-z][a-z0-9-]*$")

_ROOTS = {
    "just-dna-enricher": typer.main.get_command(enricher_app),
    "just-dna-compiler": typer.main.get_command(compiler_app),
}

#: Quotes of a command that deliberately does not exist, keyed by file and span. Each says why; a
#: new entry needs the same sentence, or it is a stale remedy given a pass.
_DELIBERATE_ABSENCES = {
    ("enricher/src/just_dna_enricher/cli/pgx_commands.py", "pharmvar publish"): (
        "PharmVar's API key is personal under its terms §2, so its bulk data is never republished: "
        "the docstring says there is no `pharmvar publish`, and there will not be."
    ),
    ("enricher/src/just_dna_enricher/pharmvar_build.py", "pharmvar publish"): (
        "The same refusal, in the builder's module docstring: no HF repo, no ensure function, no "
        "publish command."
    ),
}


def _unregistered(span: str) -> str | None:
    """The first word of `span` that falls under a group yet names none of its commands, else `None`.

    A span names a command path when its first word (after an optional `just-dna-*`) is a group of
    either app; the walk then descends while the node it reached is a group. It stops at the first
    token that is not a plain word (an option, a placeholder, an f-string field), which ends the path.
    """
    words = span.split()
    if not words:
        return None
    if words[0] in _ROOTS:
        candidates = [_ROOTS[words[0]]]
        words = words[1:]
    else:
        candidates = list(_ROOTS.values())
    if not words:
        return None
    nodes = [
        root.commands[words[0]]
        for root in candidates
        if words[0] in root.commands and hasattr(root.commands[words[0]], "commands")
    ]
    if not nodes:
        return None
    for word in words[1:]:
        if not _WORD.match(word):
            return None
        reached = [node.commands[word] for node in nodes if word in node.commands]
        if not reached:
            return word
        nodes = [node for node in reached if hasattr(node, "commands")]
        if not nodes:
            return None
    return None


def _quotes() -> list[tuple[str, int, str, str]]:
    found = []
    for path in sorted(_REPO.glob("*/src/**/*.py")):
        rel = path.relative_to(_REPO).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in _SPAN.finditer(line):
                bad = _unregistered(match.group(1))
                if bad is not None:
                    found.append((rel, number, match.group(1), bad))
    return found


def test_every_quoted_command_is_registered() -> None:
    """Both directions: no unregistered quote outside the list, and no list entry that matches nothing.

    The second half keeps the list from outliving its reason: once a command is built, or the quote
    is reworded, its exemption would otherwise sit there excusing the next author's typo.
    """
    found = _quotes()
    unexplained = [
        f"{rel}:{number}: `{span}` ({bad!r} is no command there)"
        for rel, number, span, bad in found
        if (rel, span) not in _DELIBERATE_ABSENCES
    ]
    assert unexplained == []
    assert {(rel, span) for rel, _, span, _ in found} == set(_DELIBERATE_ABSENCES)


@pytest.mark.parametrize(
    ("span", "bad"),
    [
        ("just-dna-enricher clinvar pull", "pull"),
        ("clinvar pull", "pull"),
        ("cache pull --only clinvar", None),
        ("just-dna-enricher clinvar build", None),
        ("just-dna-compiler close <spec-dir>", None),
        ("cache {name}", None),
        ("just-dna-enricher unknown", None),
    ],
)
def test_the_walk_reads_a_path_the_way_a_shell_would(span: str, bad: str | None) -> None:
    """The cases the walk has to tell apart, the S142 quote first.

    Prefixed or not, `clinvar pull` is caught; a path that exists passes with its options and
    placeholders after it; a version label after the program name (`just-dna-enricher unknown`)
    names no group, so it is not read as a command at all.
    """
    assert _unregistered(span) == bad
