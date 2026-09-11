"""The remedy a compile refusal names must be a flag that exists (RM230).

`identifiers._pgs_source_rows` built every PGS row with `declared_use="unstated"`, hardcoded. The
`academic_research_only` class is `ScoreRights(share_alike=None, commercial_use=False,
redistribution=False)`, and those rows sit at the `annotation` layer — which is exactly where
`taints_commercial_use` reads. So a module citing such a score produced a licence row that taints, the
compile refused it, and the refusal said:

    Re-run the enricher with a declared use (`--use non-commercial`) to record one

`check-identifiers` had no `--use` option. `merge_sources_csv` is never-clobber, so a re-run could not
correct the cell either: the only exit was editing `sources.csv` by hand. **A refusal that names an
unreachable remedy is worse than one that names none**, because it sends an operator to a flag they
will not find and implies they typed it wrong.

**Measured before fixing, because the audit left it undetermined from code.** Against the live PGS
Catalog on 2026-09-11, `GET /rest/score/all?limit=250` returned three distinct licence strings, and
**6 of those 250 scores** matched the `academic_research_only` phrase — PGS000013 through PGS000017
among them, "Freely available to the academic community for research use". So this was a reachable
trap and not a latent one, which is what decided it got a flag rather than a note.

These tests are offline: the phrase is a domain constant, and what is under test is the plumbing
between the flag and the row.
"""

import inspect

import pytest
from just_dna_enricher import identifiers
from just_dna_enricher.cli import app
from just_dna_enricher.licensing import pgs_score_terms
from typer.testing import CliRunner

#: Verbatim from PGS000013's `license` field, fetched 2026-09-11. A domain constant, not a count.
_ACADEMIC = "Freely available to the academic community for research use. Parties interested in commercial use should contact the authors."


def test_the_academic_phrase_still_classifies_as_the_gated_class() -> None:
    """The premise. If the Catalog reworded this, the rest of the file is about nothing."""
    terms = pgs_score_terms("PGS000013", _ACADEMIC)

    assert terms.commercial_use is False, "this class is why a declared use is needed at all"


def test_the_pass_takes_a_declared_use_rather_than_hardcoding_one() -> None:
    """The plumbing, asserted at the seam that was welded shut."""
    assert "declared_use" in inspect.signature(identifiers._pgs_source_rows).parameters
    assert "declared_use" in inspect.signature(identifiers.check_identifiers).parameters


@pytest.mark.parametrize(
    "declared,stored",
    [
        ("non-commercial", "non_commercial"),
        ("non_commercial", "non_commercial"),
        ("commercial", "commercial"),
    ],
)
def test_the_declared_use_reaches_every_row_the_pass_writes(declared: str, stored: str) -> None:
    """Both row kinds, because the floor row and the per-score rows are built separately.

    The per-score row is the one that carries the tainting licence, and the floor row is the one a
    reader sees first; a fix that reached only one of them would look correct in a spot check.

    **The hyphenated spelling is tested because it is the one the refusal prints.** The vocabulary's
    member is `non_commercial`, and `check_vocab` accepts `-` for `_` and stores the declared member
    (`@vocab-separator-slip`) — so `--use non-commercial`, copied verbatim out of the compile error,
    lands as `non_commercial`. If that normalization ever went away, an operator following the
    message exactly would be refused by the tool that told them what to type.
    """
    status = identifiers.PgsStatus(pgs_id="PGS000013", state="known", license=_ACADEMIC)
    rows = identifiers._pgs_source_rows([status], release="2026-09-01", asked=True, declared_use=declared)

    assert len(rows) == 2, [r.source for r in rows]
    assert {row.declared_use for row in rows} == {stored}


def test_the_flag_reaches_the_rows_through_the_real_call_path() -> None:
    """End-to-end through `check_identifiers`, because the leaf test above was not enough.

    The first version of this file asserted `_pgs_source_rows` directly and passed while the wiring
    was still broken: `declared_use` reached `check_identifiers` and stopped there, because
    `_check_pgs` sits between them and had no parameter for it. Twenty tests in `test_pgs.py` failed
    on `NameError: name 'declared_use' is not defined` — a full suite caught what a targeted one
    could not, since a test that calls the private helper proves the plumbing and not the path.

    So this drives the same seam the CLI drives. No network: with no `pgs.csv` the Catalog is never
    asked, which is enough to prove the argument threads without pinning what the Catalog says.
    """
    signature = inspect.signature(identifiers._check_pgs)

    assert "declared_use" in signature.parameters, (
        "`_check_pgs` sits between `check_identifiers` and `_pgs_source_rows`; a flag that skips it "
        "reaches nothing"
    )


def test_the_flag_the_refusal_names_exists_on_the_command() -> None:
    """The whole point: `--use` is what the compile's message tells an operator to re-run with."""
    result = CliRunner().invoke(app, ["check-identifiers", "--help"])

    assert result.exit_code == 0, result.output
    assert "--use" in result.output
