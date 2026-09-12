"""A gate's verdict is bool-like, carries why it is a `no`, and refuses a code nobody declared.

**The shape under test is the one exception to the house tri-state**, so the tests that matter are
the ones pinning where the exception starts and stops: a gate answers yes or no because it has to
choose an exit code, and the unknown rides beside the answer instead of inside it. What must not
happen is the set growing to mean *anything that is not a plain pass* — a check the caller switched
off is not an error, and a module with no row a check applies to is not one either.

The two properties that return one are asserted through their own reports in `test_acmg.py` and
`test_identifiers.py`; here it is the type itself, plus the equality that keeps the vocabulary from
drifting away from the two call sites.
"""

import ast
import pathlib

import pytest
from just_dna_enricher.acmg import AcmgReport
from just_dna_enricher.identifiers import IdentifierReport
from just_dna_enricher.verdict import VALID_VERDICT_CODES, Verdict

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "just_dna_enricher"


def test_the_empty_set_is_the_pass_and_any_code_is_a_fail():
    assert Verdict()
    assert bool(Verdict(frozenset({"offline"}))) is False
    assert bool(Verdict(frozenset({"offline", "stale_identifiers"}))) is False


def test_a_code_outside_the_vocabulary_is_refused_at_construction():
    """Principle 6's closed vocabulary, enforced where the value is made rather than where it is read."""
    with pytest.raises(ValueError, match="not a VALID_VERDICT_CODES member: made_up"):
        Verdict(frozenset({"made_up"}))
    with pytest.raises(ValueError, match="not_requested"):
        # The deliberate non-member, and the one a future caller is most likely to reach for: a check
        # the caller switched off is not an error, and admitting it here would make
        # `--strict --no-traits` fail a build for doing as it was told.
        Verdict(frozenset({"not_requested"}))


def test_of_carries_only_the_truthy_reasons():
    assert set(Verdict.of(offline=False, stale_identifiers=[])) == set()
    assert set(Verdict.of(offline=True, stale_identifiers=[])) == {"offline"}
    assert set(Verdict.of(offline=True, stale_identifiers=["rs1"])) == {"offline", "stale_identifiers"}


def test_iteration_and_str_are_ordered():
    """Deterministic ordering is not only a parquet rule — a message built from a set is one too."""
    v = Verdict(frozenset({"stale_identifiers", "offline", "tables_unreadable"}))
    assert list(v) == sorted(v.codes)
    assert str(v) == "fail: offline, stale_identifiers, tables_unreadable"
    assert str(Verdict()) == "pass"


def test_every_declared_code_is_one_a_call_site_can_actually_produce():
    """`@registry-completeness`, over the vocabulary rather than over a roster.

    A member nothing writes is the defect `VALID_SOURCE_LAYERS` carried for a release — reserved
    members no file ever produced, which made the vocabulary describe a format nobody had. The two
    properties that build a `Verdict` do so through `Verdict.of(...)`, so the keywords at those call
    sites are the set of codes this tier can emit, and that set must be the vocabulary exactly.

    Walked out of the source rather than listed here, so adding an arm to one property without
    declaring it — or declaring one and wiring it nowhere — fails rather than passing quietly.
    """
    produced: set[str] = set()
    for name in ("acmg.py", "identifiers.py"):
        tree = ast.parse((SRC / name).read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "of"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "Verdict"
            ):
                produced.update(kw.arg for kw in node.keywords if kw.arg)
    assert produced == set(VALID_VERDICT_CODES)


def test_a_run_that_could_not_read_an_id_bearing_table_is_a_no():
    """RM235's surviving half, on the report itself.

    The five stale lists are empty when a table carrying identifiers would not parse for exactly the
    same reason they are empty when everything agreed, so `clean` answered `True` over ids nobody had
    looked at. The command printed the unreadable table and then exited 0 beneath *all identifiers
    current*; a library caller — which is how this arrived, as an MCP tool reading the dataclass —
    saw only the verdict.
    """
    unreadable = IdentifierReport(trait_tables_not_read={"studies.csv": "could not be read (…)"})
    assert not unreadable.clean
    assert set(unreadable.clean) == {"tables_unreadable"}


def test_a_table_that_is_merely_absent_or_unopened_is_not_a_no():
    """The other side of the same line, and the one a prose filter got wrong.

    `unreadable_tables` filtered only `"not present"`, so the row-taking call form's reason — which
    is a statement about how the caller invoked the check, not about a file — counted as a table that
    would not parse. Nothing caught it because the CLI always passes `spec_dir`. Both benign reasons
    are now one constant each, read by the filter and written by the producer.
    """
    from just_dna_enricher.identifiers import NOT_PRESENT, ROWS_PASSED_IN

    for reason in (NOT_PRESENT, ROWS_PASSED_IN):
        report = IdentifierReport(
            trait_tables_not_read={"studies.csv": reason},
            gene_tables_not_read={"haplotypes.csv": reason},
        )
        assert report.unreadable_tables == {}, reason
        assert report.clean, reason


def test_the_acmg_arms_split_where_one_is_an_error_and_one_is_not():
    """`offline` fails, `nothing_to_check` passes — the behaviour change, pinned in one place."""
    assert not AcmgReport(version=None, verdicts=[]).clean
    assert AcmgReport(version="3.3", verdicts=[]).clean
    assert AcmgReport(version="3.3", verdicts=[]).checked == 0
