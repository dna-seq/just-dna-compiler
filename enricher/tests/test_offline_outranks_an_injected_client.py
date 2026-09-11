"""`--offline` means no egress from a licence-gated source, injected client or not (RM220).

Two readings of the flag coexist in this tier, and until now nothing said which applied where.

- **`pgx` makes it absolute**, and `test_pgx_licensing.py` asserts it by name: *"An injected live
  client is not a loophole: `offline` outranks the injection, because a live client under a flag
  documented as making no egress is exactly the failure RM38 closes."*
- **`gwas` does not**, and says so deliberately in its own docstring: *"An injected `client` still
  wins, because handing over a transport you already hold is not egress."*

`expression` had `gwas`'s shape (`if offline and client is None:`) against `pgx`'s situation. The
AlphaGenome Atlas is licence-gated — its Additional Terms bar classes of holder outright — so an
injected client under `--offline` fetched from a gated source, which is the loophole the PGx rule
exists to close. `@flag-means-same`.

**The difference between the two readings is the source's licence, not a preference**, and that is
now written down rather than inferable only by reading three modules. `gwas` keeps its behaviour: the
GWAS Catalog is ungated, its docstring argues the case, and changing a stated contract for a
Python-API caller is a decision rather than a repair — surfaced in ENRICHER.md instead.

The declared-use gate is a **separate** check and still runs; this is about egress, not permission,
and a test below pins that the two remain distinguishable.
"""

import shutil
from pathlib import Path

import pytest
from just_dna_enricher import expression


class _WouldFetch:
    """A client that fails the test by being used at all."""

    def __init__(self) -> None:
        self.calls = 0

    def score_interval(self, *args, **kwargs):  # pragma: no cover - the point is it is never reached
        self.calls += 1
        raise AssertionError("the Atlas was queried under --offline")

    def close(self) -> None:
        pass


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    """A real reference example, so a failure here is about the gate and not about the spec.

    A hand-built `module_spec.yaml` was tried first and made the pre-fix demonstration unreadable:
    the unfixed code ran past the offline gate and then died on an unrelated identity-key refusal,
    so the test failed for the right reason and said the wrong thing. Copying a spec the repository
    already compiles removes every failure mode but the one under test.
    """
    spec = tmp_path / "spec"
    shutil.copytree(Path(__file__).resolve().parents[2] / "reference_examples" / "hfe_hemochromatosis", spec)
    return spec


def test_an_injected_client_does_not_reopen_the_flag(spec: Path) -> None:
    """**`--use non-commercial` is the point of this case, not a detail.**

    The declared-use gate runs after the offline gate and skips an *undeclared* run, so a test that
    left `declared_use` at its default would pass against the unfixed code — the licence refusal
    masking the egress hole rather than the egress gate closing it. Declaring the use removes that
    second gate, which is the only way to see whether the first one holds on its own.
    """
    client = _WouldFetch()

    result = expression.enrich_expression(
        spec, gene="CYP2D6", offline=True, client=client, declared_use="non_commercial"
    )

    assert result.skipped
    assert client.calls == 0, "an injected client fetched under --offline"
    assert any("--offline" in w for w in result.warnings), result.warnings


def test_the_skip_says_the_injection_was_considered(spec: Path) -> None:
    """A no-op that does not say why reads as a pass that found nothing."""
    result = expression.enrich_expression(
        spec, gene="CYP2D6", offline=True, client=_WouldFetch(), declared_use="non_commercial"
    )

    (note,) = [w for w in result.warnings if "--offline" in w]
    assert "injected client" in note, note
    assert "licence-gated" in note or "licence" in note, note


def test_nothing_is_written(spec: Path) -> None:
    """The other half of a no-op: a skipped pass leaves no sidecar behind."""
    expression.enrich_expression(
        spec, gene="CYP2D6", offline=True, client=_WouldFetch(), declared_use="non_commercial"
    )

    assert not list(spec.glob("expression_effects.csv"))


def test_offline_without_a_client_is_unchanged(spec: Path) -> None:
    """The control — this arm already worked, and the repair must not have moved it."""
    result = expression.enrich_expression(spec, gene="CYP2D6", offline=True)

    assert result.skipped
    assert any("--offline" in w for w in result.warnings)
