"""ClinPGx → pharm_variants.csv (0.5, RM26) — the second drafting provider.

Built against the **real snapshot** when one is present, so the expectations are computed from the
data rather than read off a dump. What is pinned: the five-part key (so a re-run adds nothing), one
row per drug in a `;`-joined annotation, the `CC` → `C/C` re-spelling, and that everything the
grammar cannot hold is skipped with a warning rather than coerced.
"""

import csv
import io
from pathlib import Path

import pytest
from just_dna_compiler.compiler import _load_csv_rows, validate_spec
from just_dna_compiler.draft import natural_key
from just_dna_enricher.clinpgx_draft import (
    _authored_genotype,
    _meets_level,
    _rows_from_snapshot,
    _split_cell,
    _symbolic_types,
    draft_pharm_variants,
)
from just_dna_format.layout import SOURCES_CSV, preferred_spelling
from just_dna_format.pgx import PharmVariantRow

#: The licence sidecar's current filename, derived rather than named: it gained a second
#: spelling in 0.6 (RM51) and the older one retires at 1.0, so a literal here would pin a test
#: to whichever spelling happened to be current when it was written.
_LICENCE_CSV = preferred_spelling(SOURCES_CSV)

_SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "interim" / "clinpgx"
_needs_snapshot = pytest.mark.skipif(
    not (_SNAPSHOT / "data" / "annotations.parquet").is_file(),
    reason="no local ClinPGx snapshot (build it with `just-dna-enricher clinpgx build`)",
)

def _rows(path: Path) -> list[dict]:
    """A drafted CSV as dicts — the raw cells, so a test can see what was written."""
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


_RECORDS = [
    {"annotation_id": "1", "rsid": "rs6265", "genotype": "CC", "evidence_level": "3",
     "phenotype_category": "Efficacy", "drugs": "citalopram;paroxetine"},
    {"annotation_id": "2", "rsid": "rs1", "genotype": "*1", "evidence_level": "1A",
     "phenotype_category": "Toxicity", "drugs": "codeine"},
    {"annotation_id": "3", "rsid": "rs2", "genotype": "del/del", "evidence_level": "4",
     "phenotype_category": "Efficacy", "drugs": "warfarin"},
    {"annotation_id": "4", "rsid": "", "genotype": "AG", "evidence_level": "1A",
     "phenotype_category": "Efficacy", "drugs": "warfarin"},
]


def test_a_concatenated_genotype_becomes_the_authored_form() -> None:
    assert _authored_genotype("CC") == "C/C"
    assert _authored_genotype("TC") == "C/T"  # unphased calls are alphabetical
    # a star allele belongs on diplotypes.csv, and a symbolic one carries no length here
    assert _authored_genotype("*1") is None
    assert _authored_genotype("del/del") is None
    assert _authored_genotype("C/del") is None


def test_an_already_separated_call_is_taken_as_written() -> None:
    """`CTT/CTT` needs no splitting decision, so declining it was pure loss (S44).

    This assertion used to read `_authored_genotype("CAT") is None`, on the rule *only two
    unambiguous bases*. That rule was narrower than the schema it writes into: `validate_allele`
    accepts any `^[ACGT]+$` allele, and ClinPGx separates with `/` wherever an allele runs past one
    base — so the ambiguity the rule guarded against does not arise on these cells. Changed
    deliberately rather than adjusted around.
    """
    assert _authored_genotype("CTT/CTT") == "CTT/CTT"
    assert _authored_genotype("TTAAAGTTA/TTAAAGTTA") == "TTAAAGTTA/TTAAAGTTA"
    assert _authored_genotype("CTT/AGG") == "AGG/CTT", "still sorted, like the two-base form"
    # and the row it produces is one the schema takes
    assert PharmVariantRow(
        rsid="rs113993960", gene="CFTR", genotype="CTT/CTT", drug="ivacaftor", conclusion="x"
    ).genotype == "CTT/CTT"


def test_a_single_haploid_allele_is_a_genotype() -> None:
    """ClinPGx spells an mtDNA call as one allele, and the grammar already holds that form.

    Skipping it cost every MT-RNR1 annotation — aminoglycoside-induced hearing loss, a CPIC
    guideline — for want of a second allele that does not exist on a haploid contig. Same reasoning
    as `clinvar_draft.sole_expressible_genotype`: the placeholder protects a zygosity decision, and
    on a haploid contig there is none to protect.
    """
    assert _authored_genotype("A") == "A"
    assert _authored_genotype("CCCCCCC") == "CCCCCCC"
    assert PharmVariantRow(
        rsid="rs267606617", gene="MT-RNR1", genotype="A",
        drug="aminoglycoside antibacterials", conclusion="x",
    ).genotype == "A"


def test_the_pass_is_never_narrower_than_the_schema_it_writes_into() -> None:
    """The general rule behind both cases above, asserted rather than restated in a comment.

    Every genotype spelling this pass declines must be one `PharmVariantRow` would *also* refuse —
    otherwise the provider is dropping rows the format can hold, which is what S44 reported twice.
    The converse is allowed: declining `del/del` is deliberate even though the schema would take a
    length-bearing `<DEL:1500>`, because ClinPGx publishes no length.
    """
    from pydantic import ValidationError

    accepted_by_schema = []
    for spelling in ("CC", "CTT/CTT", "A", "CCCCCCC", "TTAAAGTTA/TTAAAGTTA", "GT/GT"):
        try:
            PharmVariantRow(rsid="rs1", genotype=spelling, drug="d", conclusion="x")
        except ValidationError:  # pragma: no cover - the point is that none of these raise
            continue
        accepted_by_schema.append(spelling)
    declined_anyway = [s for s in accepted_by_schema if _authored_genotype(s) is None]
    assert declined_anyway == [], (
        f"the schema accepts these and the provider drops them: {declined_anyway}"
    )


def test_one_annotation_naming_several_drugs_becomes_one_row_each() -> None:
    rows, _ = _rows_from_snapshot(_RECORDS[:1], genes=(), drugs=(), min_evidence_level=None)
    assert [r.drug for r in rows] == ["citalopram", "paroxetine"]
    # they share the annotation, and still key distinctly — the drug is part of the key
    assert len({natural_key(r) for r in rows}) == 2
    assert {r.annotation_id for r in rows} == {"1"}


def test_what_this_pass_cannot_write_is_skipped_with_a_reason() -> None:
    rows, warnings = _rows_from_snapshot(_RECORDS, genes=(), drugs=(), min_evidence_level=None)
    assert {r.rsid for r in rows} == {"rs6265"}
    joined = " ".join(warnings)
    assert "diplotypes.csv" in joined      # the star allele is routed, not dropped silently
    assert "RM5" in joined                 # the symbolic allele has its own line
    assert "no rsID" in joined


def test_the_symbolic_skip_names_the_length_and_not_the_grammar() -> None:
    """**The reason moved in 0.6 and the old wording became false.** RM5 widened the grammar to hold
    `<DEL:1500>`, so `del/del` is no longer something the format cannot spell — it is something
    ClinPGx does not publish a *length* for, and a lengthless symbolic allele is a rule the compiler
    drops. Writing the row anyway would hand the author work the next command in the documented
    workflow undoes, which is why this pass still declines."""
    _, warnings = _rows_from_snapshot(_RECORDS, genes=(), drugs=(), min_evidence_level=None)
    symbolic = next(w for w in warnings if "structural allele" in w)
    assert "length" in symbolic
    assert _symbolic_types("del/del") == ["DEL", "DEL"]
    assert _symbolic_types("C/del") == ["DEL"]
    assert _symbolic_types("C/T") == []
    # A cell that is neither a star allele nor a structural one is its own reason, not this one.
    assert _symbolic_types("CAT") == []


def test_the_evidence_floor_keeps_unknown_levels() -> None:
    """An unknown level is kept: dropping it would silently hide an annotation we cannot rank."""
    assert _meets_level("1A", "3") and _meets_level("3", "3")
    assert not _meets_level("4", "3")
    assert _meets_level(None, "1A") and _meets_level("weird", "1A")


def test_split_cell_keeps_first_occurrence_order() -> None:
    """Emitted order is digest-visible, so it must be stable and not set-derived."""
    assert _split_cell("b;a;b;c") == ["b", "a", "c"]
    assert _split_cell(None) == []


#: The multi-gene shape, taken from the snapshot rather than invented (R2-1). `rs17886199` really is
#: published as `PRSS53;VKORC1`, and it really is one of the 3 rows `--gene VKORC1` used to drop.
_MULTI_GENE = [
    {"annotation_id": "10", "rsid": "rs17886199", "gene": "PRSS53;VKORC1", "genotype": "CC",
     "evidence_level": "3", "phenotype_category": "Dosage", "drugs": "warfarin"},
    {"annotation_id": "11", "rsid": "rs4149056", "gene": "SLCO1B1", "genotype": "CC",
     "evidence_level": "1A", "phenotype_category": "Metabolism/PK", "drugs": "simvastatin"},
    {"annotation_id": "12", "rsid": "", "gene": "CYP2D6", "genotype": "AG",
     "evidence_level": "1A", "phenotype_category": "Efficacy", "drugs": "codeine"},
]


def test_a_gene_filter_matches_a_member_and_not_the_whole_cell() -> None:
    """`--gene VKORC1` must find VKORC1 inside `PRSS53;VKORC1` (R2-1).

    The old filter tested the whole cell against the requested set, so a real VKORC1 annotation was
    dropped in silence — the CPIC `gene.chr` shape, a claim true of the cell and false of the column.
    """
    rows, _ = _rows_from_snapshot(
        _MULTI_GENE, genes=["VKORC1"], drugs=(), min_evidence_level=None
    )
    assert [r.rsid for r in rows] == ["rs17886199"]
    # …and the written cell is the member the request selected, not the source's joined string,
    # which is a non-symbol in a column documented as a symbol.
    assert [r.gene for r in rows] == ["VKORC1"]


def test_an_unselected_multi_gene_cell_is_withheld_and_reported() -> None:
    """With nothing to select by, the cell is left empty and the author is told which genes it named.

    Withholding rather than writing `PRSS53;VKORC1` is the house answer for a value the column
    cannot hold: an empty cell reads as *not stated*, which is weaker than the truth; the joined
    cell is false about its own column and matches no consumer's gene filter. The row is still
    drafted — only the one column is withheld.
    """
    rows, warnings = _rows_from_snapshot(_MULTI_GENE, genes=(), drugs=(), min_evidence_level=None)
    by_rsid = {r.rsid: r.gene for r in rows}
    assert by_rsid["rs17886199"] is None
    assert by_rsid["rs4149056"] == "SLCO1B1"  # a single-gene cell is untouched
    withheld = next(w for w in warnings if "empty `gene`" in w)
    assert "PRSS53;VKORC1" in withheld


def test_two_requested_members_in_one_cell_select_nothing() -> None:
    """Asking for both genes of one cell restores the ambiguity, so the answer is withhold again.

    Position cannot break the tie: the pharmacogene is first in `CYP3A5;ZSCAN25` and second in
    `PRSS53;VKORC1`, so "take the first" would be right half the time and silent about it.
    """
    rows, _ = _rows_from_snapshot(
        _MULTI_GENE, genes=["VKORC1", "PRSS53"], drugs=(), min_evidence_level=None
    )
    assert [(r.rsid, r.gene) for r in rows] == [("rs17886199", None)]


def test_the_unidentified_count_is_scoped_to_the_requested_genes() -> None:
    """`skipped_unidentified` must count within `--gene`, not across the whole database (R2-11).

    The rsID check used to run before the gene filter, so the "records the source could not
    identify" number was inflated by every unrequested gene — which destroys the one thing it is
    for, judging whether the source's coverage of *your* gene is poor. Here `rs17886199` and the
    rsID-less CYP2D6 record are both present; asking for VKORC1 must report neither as unidentified.
    """
    _, filtered = _rows_from_snapshot(
        _MULTI_GENE, genes=["VKORC1"], drugs=(), min_evidence_level=None
    )
    assert not [w for w in filtered if "no rsID" in w]

    # Unfiltered, the same record is genuinely unidentifiable and is still reported — the fix is
    # the scope of the count, not the removal of the check.
    _, everything = _rows_from_snapshot(_MULTI_GENE, genes=(), drugs=(), min_evidence_level=None)
    assert [w for w in everything if "no rsID" in w] == [
        "1 annotation(s) skipped: carrying no rsID, so nothing this format can key on."
    ]


@_needs_snapshot
def test_the_real_snapshot_yields_the_rows_the_whole_cell_filter_hid(tmp_path: Path) -> None:
    """Against the real snapshot, computed rather than recalled: the hidden rows are now drafted.

    The expectation is derived from the parquet in the same test, so it cannot rot into a hardcoded
    count read off a dump — what is asserted is the *relationship*, that per-member matching is a
    strict superset of whole-cell matching and that the difference is exactly the `;` rows.
    """
    import duckdb

    parquet = str(_SNAPSHOT / "data" / "annotations.parquet")
    con = duckdb.connect()
    hidden = {
        r[0]
        for r in con.sql(
            f"select distinct rsid from '{parquet}' "
            "where gene like '%;%' and ';' || upper(gene) || ';' like '%;VKORC1;%' and rsid <> ''"
        ).fetchall()
    }
    assert hidden, "snapshot carries no multi-gene VKORC1 row; the probe this test encodes is stale"

    draft_pharm_variants(
        tmp_path, snapshot=_SNAPSHOT, genes=["VKORC1"], declared_use="non_commercial"
    )
    rows, errors, _ = _load_csv_rows(
        tmp_path / "pharm_variants.csv", PharmVariantRow, "pharm_variants.csv"
    )
    assert errors == []
    drafted = {r.rsid for r in rows}
    assert hidden <= drafted
    # every drafted row names VKORC1 or names nothing — never the joined cell
    assert {r.gene for r in rows} <= {"VKORC1", None}


def test_a_commercial_declaration_refuses_before_reading_anything(tmp_path: Path) -> None:
    """ClinPGx forbids sale, and the terms are accepted by taking the data — so nothing is read."""
    with pytest.raises(Exception):
        draft_pharm_variants(
            tmp_path, snapshot=tmp_path / "nonexistent", declared_use="commercial"
        )


def test_unstated_use_skips_rather_than_refusing(tmp_path: Path) -> None:
    result = draft_pharm_variants(tmp_path, snapshot=tmp_path / "nonexistent")
    assert result.skipped and result.warnings
    assert not (tmp_path / "pharm_variants.csv").exists()


@_needs_snapshot
def test_drafting_the_real_snapshot_is_re_runnable_and_reloads(tmp_path: Path) -> None:
    """Real data, expectations computed: draft, reload through the compiler, then re-run and add none."""
    first = draft_pharm_variants(
        tmp_path, snapshot=_SNAPSHOT, drugs=["simvastatin"], declared_use="non_commercial"
    )
    assert first.added > 0
    path = tmp_path / "pharm_variants.csv"
    rows, errors, _ = _load_csv_rows(path, PharmVariantRow, "pharm_variants.csv")
    assert errors == []
    assert len(rows) == first.added
    # every drafted row really is about the drug asked for, and carries the full key
    assert {r.drug for r in rows} == {"simvastatin"}
    assert len({natural_key(r) for r in rows}) == len(rows)
    # a source consulted must be accounted for
    assert (tmp_path / _LICENCE_CSV).is_file()

    before = path.read_bytes()
    again = draft_pharm_variants(
        tmp_path, snapshot=_SNAPSHOT, drugs=["simvastatin"], declared_use="non_commercial"
    )
    assert again.added == 0
    assert sum(len(r.already_present) for r in again.reports) == len(rows)
    assert path.read_bytes() == before


@_needs_snapshot
def test_a_drafted_pgx_module_validates(tmp_path: Path) -> None:
    """The point of the whole exercise: what is drafted is a module, not a pile of rows."""
    (tmp_path / "module_spec.yaml").write_text(
        "schema_version: '1.0'\n"
        "module:\n  name: clinpgx_demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
    )
    draft_pharm_variants(
        tmp_path, snapshot=_SNAPSHOT, drugs=["simvastatin"], declared_use="non_commercial"
    )
    result = validate_spec(tmp_path)
    assert result.valid, result.errors


@_needs_snapshot
def test_the_real_snapshot_yields_the_mt_and_indel_annotations_that_were_dropped(
    tmp_path: Path,
) -> None:
    """The two families S44 named, recovered from the snapshot rather than from a fixture.

    MT-RNR1 is the haploid case and CFTR F508del the already-separated one; both are asserted by
    *presence of the annotation*, not by a row count, so the test survives a snapshot rebuild. The
    `del`-spelled rows of those same CFTR annotations stay skipped — the point is that the
    pure-nucleotide sibling no longer goes with them.
    """
    result = draft_pharm_variants(
        tmp_path, snapshot=_SNAPSHOT, genes=["MT-RNR1", "CFTR"], declared_use="non_commercial",
    )
    assert not result.skipped, result.warnings
    rows = _rows(tmp_path / "pharm_variants.csv")
    assert rows, "the snapshot must carry these genes or this proves nothing"

    mt = [r for r in rows if "MT-RNR1" in (r["gene"] or "")]
    assert mt, "no MT-RNR1 rows — the haploid genotype is being skipped again"
    assert all("/" not in r["genotype"] and r["genotype"] for r in mt), (
        "an mtDNA call is one allele; a pair here would be invented zygosity"
    )
    assert "1A" in {r["evidence_level"] for r in mt}, "the guideline-level annotations are the point"

    cftr = [r for r in rows if "CFTR" in (r["gene"] or "")]
    assert cftr, "no CFTR rows — F508del's CTT/CTT genotype is being skipped again"
    spellings = {r["genotype"] for r in cftr}
    assert "CTT/CTT" in spellings, "F508del's pure-nucleotide genotype is being skipped again"
    assert not [g for g in spellings if "del" in g.lower()], (
        "the del/ spellings stay skipped — ClinPGx publishes no length for them"
    )


@_needs_snapshot
def test_the_licence_terms_are_pinned_to_the_text_that_governed_them(tmp_path: Path) -> None:
    """`license_sha256` was null on a share-alike source whose LICENSE.txt sits in the snapshot (S44).

    `SourceTerms.row` has taken `license_text=` all along and this caller passed only `declared_use`
    and `dataset`, so the module recorded ClinPGx's terms without pinning them — which is the one
    thing that field is for. Computed here from the file rather than compared to `release.json`'s
    stated hash: the file is what the module is claiming, and hashing it independently is what makes
    the assertion mean something.
    """
    import hashlib

    from just_dna_enricher.locations import SNAPSHOT_LICENSE_FILENAME

    licence = _SNAPSHOT / SNAPSHOT_LICENSE_FILENAME
    assert licence.is_file(), "the snapshot must carry its LICENSE.txt or this proves nothing"
    expected = "sha256:" + hashlib.sha256(licence.read_bytes()).hexdigest()

    result = draft_pharm_variants(
        tmp_path, snapshot=_SNAPSHOT, genes=["CYP2C19"], declared_use="non_commercial",
    )
    assert not result.skipped, result.warnings
    sources = _rows(tmp_path / preferred_spelling(SOURCES_CSV))
    clinpgx = [r for r in sources if r["layer"] == "annotation"]
    assert clinpgx, "the pass must write its SourceRow"
    assert {r["license_sha256"] for r in clinpgx} == {expected}
