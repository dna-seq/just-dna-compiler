"""A key in `.env` reaches the AlphaGenome paths, and an exported-empty one still does not (RM212).

`@credential-where-read` has two clauses and this tier kept forgetting the second. Reading
`os.environ` at the point of use is the first; **a guard in front of a loader must load too** is the
second, and `expression._connect` — the one function whose own docstring cites the rule — read the
variable without calling `load_env()`. Nothing else on `alphagenome expression`'s path loads a `.env`,
so a key that lives only there was invisible and the pass refused with *is not set* while the file sat
in the working directory. `cli._atlas_client_or_none` had the same gap and degraded to the knot
interval for rows the Atlas could have refined.

It is the same incident `caches._rebuild_pharmvar` already carries a comment about, one lane over, and
the comment there says what makes it worse than a plain bug: *a pre-check that answers differently
from the code it is guarding is worse than no pre-check*.

**The two absences stay two.** `load_env` uses `override=False`, so a variable that is present is kept
whatever the `.env` says — and an empty string is present. `export ALPHAGENOME_API_KEY=` is therefore
strictly stronger than never setting the variable, which is the opposite of what anyone expects and is
exactly why the tier's own tests neutralize a credential with `""` rather than `delenv`
(`@test-no-credential`: `.env` leaks into `os.environ` from any unrelated test, so `delenv` lets the
developer's real key refill it). Both states are asserted here, because collapsing them is how the
diagnosis stops being actionable.

Every case runs in `tmp_path` with `monkeypatch.chdir`, since `load_env` walks up from the CWD and the
repository's own `.env` is what a naive test would find.
"""

import inspect
from pathlib import Path

import pytest
from just_dna_enricher import cli, expression

_VAR = "ALPHAGENOME_API_KEY"
_KEY = "probe-key-not-a-real-credential"


@pytest.fixture
def dotenv_dir(tmp_path: Path, monkeypatch) -> Path:
    """A directory holding a `.env` with a key, with the process environment saying nothing."""
    (tmp_path / ".env").write_text(f"{_VAR}={_KEY}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # `""` rather than `delenv`: an unrelated test may already have loaded the developer's `.env`
    # into `os.environ`, and an empty value is what this tier means by "not passed".
    monkeypatch.setenv(_VAR, "")
    return tmp_path


def test_a_key_that_lives_only_in_dotenv_is_found(dotenv_dir: Path, monkeypatch) -> None:
    """The defect: `_connect` refused with *is not set* while this file sat in the CWD."""
    # `""` is *present*, and `load_env(override=False)` would keep it — which is the exported-empty
    # case below. Here the variable is genuinely absent, which is what a fresh shell looks like.
    monkeypatch.delenv(_VAR, raising=False)
    seen: dict[str, str] = {}
    monkeypatch.setattr(expression, "connect", lambda key, **kw: seen.setdefault("key", key))

    expression._connect()

    assert seen["key"] == _KEY


def test_an_exported_empty_key_is_still_unusable(dotenv_dir: Path) -> None:
    """`export VAR=` outranks the `.env`, and the refusal must say which absence it is."""
    with pytest.raises(expression.ExpressionError) as excinfo:
        expression._connect()

    message = str(excinfo.value)
    assert _VAR in message
    # The diagnosis, not just the fact: `missing_credential_reason` is what separates "never set"
    # from "exported empty", and a message that named neither sent an operator to the wrong fix.
    assert "empty" in message.lower() or "set to an empty" in message.lower(), message


def test_the_refusal_still_points_at_the_offline_escape(dotenv_dir: Path) -> None:
    """The remedy sentence is part of the contract — this pass has no snapshot to fall back on."""
    with pytest.raises(expression.ExpressionError) as excinfo:
        expression._connect()

    assert "--offline" in str(excinfo.value)


def test_no_key_anywhere_refuses(tmp_path: Path, monkeypatch) -> None:
    """The control: with no `.env` and no variable, the answer is unchanged."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(_VAR, raising=False)

    with pytest.raises(expression.ExpressionError):
        expression._connect()


def test_the_cli_helper_reads_the_same_way() -> None:
    """The second site, asserted structurally rather than by driving Typer.

    `_atlas_client_or_none` degrades to a printed sentence rather than raising, so a behavioural test
    would assert on stderr; what actually has to hold is that it loads before it reads. Both call
    sites are checked here so neither can regress alone — the gap existed in both at once, which is
    what a per-function test would have missed.
    """
    for func in (cli._atlas_client_or_none, expression._connect):
        source = inspect.getsource(func)
        assert "load_env()" in source, func.__qualname__
        assert source.index("load_env()") < source.index("os.environ.get"), func.__qualname__
