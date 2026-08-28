"""A redundancy-bearing advisory must not name a checker that cannot see the table (0.6, RM123 / S59).

`REDUNDANCY_BEARING` is keyed on a bare column name with no model attached, so the sentence explaining
*why* a cell is left to the author printed on every table carrying the column — including six
(column, table) pairs where the named checker reads a different table entirely. The advice stays
right; the reason was false, and a green run over one of those cells is not evidence of agreement with
any authority.

The scope map is hand-kept, because `hints` lives in the compiler tier and the checkers it names live
in the enricher, which the compiler may never import. So every entry is a claim, and these tests are
where the claims are checked: the two that mis-fired are pinned against the real reference tables, and
the six columns deliberately left **unscoped** are pinned too — an over-eager scope map would suppress
a *true* advisory, which is the same defect facing the other way.
"""

from pathlib import Path

from just_dna_compiler.draft import DRAFTABLE, authored_field_names
from just_dna_compiler.hints import (
    REDUNDANCY_BEARING,
    REDUNDANCY_BEARING_TABLES,
    inspect_rows,
)

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"

_UNSCOPED_REASON = "would make the check vacuous"
_SCOPED_REASON = "does not read"


def _advisory(csv_name: str, text: str, column: str) -> str | None:
    report = inspect_rows(csv_name, text)
    for finding in report.findings:
        if finding.level == "info" and finding.column == column:
            return finding.message
    return None


def _head(spec: str, csv_name: str, rows: int = 2) -> str:
    lines = (_EXAMPLES / spec / csv_name).read_text().splitlines(keepends=True)
    return "".join(lines[: rows + 1])


# ── the registry, and its two directions ─────────────────────────────────────────────────────────


def test_every_scoped_column_is_a_redundancy_bearing_one() -> None:
    """The scope map may only narrow a column the other map already declares."""
    assert set(REDUNDANCY_BEARING_TABLES) <= set(REDUNDANCY_BEARING)


def test_every_named_table_is_an_authored_one() -> None:
    """A scope naming a table that does not exist would silently never match, so every advisory on
    that column would read as out-of-scope."""
    named = {table for tables in REDUNDANCY_BEARING_TABLES.values() for table in tables}
    assert named <= set(DRAFTABLE)


def test_a_scope_names_at_least_one_table_that_really_carries_the_column() -> None:
    """Otherwise the entry is unfalsifiable: it would put every table out of scope, including the one
    the check actually runs on."""
    for column, tables in REDUNDANCY_BEARING_TABLES.items():
        carriers = {t for t in tables if column in set(authored_field_names(DRAFTABLE[t]))}
        assert carriers, (column, sorted(tables))


def test_the_unscoped_columns_are_the_ones_with_more_than_one_reader() -> None:
    """The six absences are claims too. `rsid`/`chrom`/`start`/`ref`/`alts` are cross-examined on the
    positional kinds because resolution reaches them (RM43), and `pmid` because `studies.csv` is one
    citation site of several — a binning row's since RM47, a `pharm_variants.csv` row's since RM132 —
    so scoping any of them would suppress a true advisory."""
    assert set(REDUNDANCY_BEARING) - set(REDUNDANCY_BEARING_TABLES) == {
        "rsid", "chrom", "start", "ref", "alts", "pmid",
    }


# ── the two pairs the report named, on the real tables ───────────────────────────────────────────


def test_clin_sig_on_a_binning_table_does_not_claim_clinvar_reads_it() -> None:
    message = _advisory("heteroplasmy.csv", _head("mt_heteroplasmy", "heteroplasmy.csv"), "clin_sig")
    assert message is not None
    assert _SCOPED_REASON in message and "heteroplasmy.csv" in message
    assert _UNSCOPED_REASON not in message
    assert "variants.csv" in message, "it must still say where the check does run"


def test_clin_sig_and_evidence_level_on_diplotypes_are_both_scoped() -> None:
    text = _head("cyp2c19_star_alleles", "diplotypes.csv")
    for column, elsewhere in (("clin_sig", "variants.csv"), ("evidence_level", "pharm_variants.csv")):
        message = _advisory("diplotypes.csv", text, column)
        assert message is not None, column
        assert _SCOPED_REASON in message, column
        assert elsewhere in message, column


def test_clin_sig_on_variants_keeps_the_original_reason() -> None:
    """The table the check does read must be unaffected — this is where filling the cell from ClinVar
    really would make `verify_clin_sig` vacuous."""
    message = _advisory(
        "variants.csv",
        "rsid,genotype,state,conclusion,gene\nrs429358,C/C,risk,APOE e4 allele,APOE\n",
        "clin_sig",
    )
    assert message is not None
    assert _UNSCOPED_REASON in message
    assert _SCOPED_REASON not in message


# ── the advisories that must NOT be scoped ───────────────────────────────────────────────────────


def test_a_binning_pmid_keeps_the_vacuous_reason_because_a_bin_really_is_a_citation() -> None:
    """RM47's second citation site: `enricher.literature` reads bin-row pmids through
    `table_citations`, so this advisory was always true and must stay unscoped."""
    message = _advisory(
        "repeat_alleles.csv", _head("htt_repeat_expansion", "repeat_alleles.csv"), "pmid"
    )
    assert message is not None
    assert _UNSCOPED_REASON in message


def test_a_pharm_pmid_keeps_it_too_because_the_third_site_is_read_the_same_way() -> None:
    """RM132's half of the same claim, on the table it lands on.

    The way this breaks is somebody scoping `pmid` to `studies.csv` on the reasoning that a citation
    lives there — which is exactly the reading RM47 and RM132 refuse. The literature pass reads this
    site the way it reads a bin's, so the advisory here is true and the sentence must say so."""
    text = _head("pgx_slco1b1_simvastatin", "pharm_variants.csv")
    assert "pmid" not in text.splitlines()[0], "the advisory is about a column nobody filled"
    message = _advisory("pharm_variants.csv", text, "pmid")
    assert message is not None
    assert _UNSCOPED_REASON in message
    assert _SCOPED_REASON not in message
    assert "enricher.literature" in message, "and it must still name the check that reads this site"


def test_a_positional_kinds_coordinate_keeps_the_vacuous_reason() -> None:
    """Resolution reaches the positional table kinds since RM43, so `rsid` on `heteroplasmy.csv` is
    genuinely cross-examined."""
    message = _advisory("heteroplasmy.csv", _head("mt_heteroplasmy", "heteroplasmy.csv"), "rsid")
    assert message is not None
    assert _UNSCOPED_REASON in message


# ── the explanation moved; the refusal did not ───────────────────────────────────────────────────


def test_the_refusal_map_is_still_keyed_on_the_bare_column() -> None:
    """`REDUNDANCY_BEARING` is what a drafting provider refuses on. Whether a provider should start
    filling `clin_sig` on a binning row is a decision nobody has taken, and making it fillable as a
    side effect of fixing a message is precisely what this change must not do."""
    assert all(isinstance(value, str) for value in REDUNDANCY_BEARING.values())
    assert "clin_sig" in REDUNDANCY_BEARING and "evidence_level" in REDUNDANCY_BEARING
