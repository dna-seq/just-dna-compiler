"""Rendered CLI output carries no colour in the suite, so matching a token means matching the token.

**RM233, half of it.** `main` was red at `2001215` on both Python jobs while every local run was green.
Two tests match a string inside Typer's `--help` or its error box, and Typer renders through rich, which
decides colour from the environment: a GitHub runner got it, this developer's non-tty did not. With
colour on, `--use` is emitted as `\x1b[1;36m-\x1b[0m\x1b[1;36m-use\x1b[0m` — rich styles the two dashes
as their own span — so `"--use" in result.output` is false for a flag that is right there, and the
failure accuses the command of missing a flag.

**The pin is here rather than in the two tests because the class is wider than the instances.** 491
tests across 18 files invoke a CLI; two happen to match a token rich splits, and the other 489 pass on
the luck of what they match. Stripping escapes per call site fixes those two and leaves the next one to
be found by a red `main` again.

`TERM=dumb` is what does it, measured against the two failing tests: `NO_COLOR=1` alone fixes only one
of them and `FORCE_COLOR` outranks it anyway. Set in the root `conftest.py`, which pytest loads before
collecting any test module, and read later because every rich `Console` in a Typer app is constructed
per invocation. A test that wants colour can put it back with `monkeypatch.setenv`; none does, and
`enricher/tests/test_cli_rendering.py` fails if this stops working.

**`COLUMNS` is deliberately NOT set here, and that is the other half of RM233.** Click's `CliRunner`
pins its own terminal width inside `invoke()`, so the environment cannot widen the box: a long
diagnostic still wraps mid-sentence at 80 columns, which is why `nothing will fetch it` was the second
failure. Setting `COLUMNS` here looks like it addresses that and does nothing — it was in the first
draft of this file for exactly that reason. Phrase matching goes through `cli_text()` in
`enricher/tests/conftest.py` instead.
"""

import os

os.environ["TERM"] = "dumb"
