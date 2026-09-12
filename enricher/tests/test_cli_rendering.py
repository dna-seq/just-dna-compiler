"""A CLI's rendered output carries no escape codes and no wrapped phrase, so a test can match prose.

**RM233.** This is the guard over the root `conftest.py`, which pins `TERM=dumb`/`COLUMNS` for the
suite. Without it that file is an unexplained two-line side effect that a later cleanup deletes, and the
failure returns as a red `main` on a green local run — which is exactly how it was found.

It asserts the property rather than the mechanism: that the text a CLI test matches against is plain.
Demonstrated against the bug — under `FORCE_COLOR=1` and before the pin, `check-identifiers --help`
renders `--use` as three ANSI spans and the first assertion here fails.
"""

import re

from just_dna_enricher.cli import app
from typer.testing import CliRunner

#: A CSI escape sequence — what rich emits to colour a span, and what makes `'--use' in output` false
#: for a flag that is right there in the text.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def test_cli_help_output_carries_no_escape_codes() -> None:
    result = CliRunner().invoke(app, ["check-identifiers", "--help"])
    assert result.exit_code == 0
    found = _ANSI.findall(result.output)
    assert not found, (
        "rendered CLI output carries ANSI escapes, so any assertion over a phrase in it is a lottery — "
        f"the root conftest.py's TERM/COLUMNS pin has stopped working. First few: {found[:5]}"
    )


def test_a_flag_name_survives_rendering_whole() -> None:
    """The precise thing that broke: rich styles `-` and `-use` as separate spans."""
    result = CliRunner().invoke(app, ["check-identifiers", "--help"])
    assert "--use" in result.output, "a flag the command declares is unfindable in its own --help"
    assert "--strict" in result.output


def test_a_wrapped_diagnostic_is_matchable_through_cli_text(tmp_path, cli_text) -> None:
    """The second half of RM233: a phrase longer than the box, matchable only after normalizing.

    `--source acmg=<missing file>` is refused before anything downloads, and the wording is the part an
    operator acts on (`@warning-text-is-api`). Typer's box is drawn at a width `CliRunner` pins itself,
    so the sentence is broken across lines with `│` and padding in the middle — the raw assertion
    below is the one that went red on CI, and it fails **locally too**, which is the useful part: this
    half was never environment-dependent, it was only ever hidden by a shorter phrase.
    """
    missing = tmp_path / "nope.xls"
    result = CliRunner().invoke(app, ["cache", "rebuild", "--source", f"acmg={missing}"])
    assert result.exit_code != 0

    assert "nothing will fetch it" in cli_text(result)
    # And the raw output does NOT contain it, which is why the helper has to exist rather than being a
    # tidy-up. If this ever starts holding, the box stopped wrapping and the helper's reason is gone.
    assert "nothing will fetch it" not in result.output
