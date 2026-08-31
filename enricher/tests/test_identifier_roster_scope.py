"""S86: the identifier roster is every authored table carrying the column, not `variants.csv` alone.

`check_identifiers` built its roster from `variants.csv` while **eleven** authored models declare
`trait_efo_id` or `gene`. A module whose traits live in `studies.csv` — where `StudyRow` has carried
the column since 0.3 — therefore reported nothing checked, nothing flagged, and shipped a retired
CURIE with every gate green. The unreadable `0` is the item rather than the omission: it said *this
module declares no trait* and *its traits are in a table nobody read* in the same breath, which is the
three-valued rule at a finer grain and the thing `unconsulted_rsids` protects one tier down.

Every test here is offline — the roster is pure table-reading and reaches no registry.
"""

from pathlib import Path

import httpx
import pytest
from just_dna_enricher.identifiers import (
    IdentifierRoster,
    OntologyClient,
    _id_bearing_tables,
    authored_identifiers,
    check_identifiers,
)
from just_dna_enricher.net import PacingGate
from typer.testing import CliRunner

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: s86\n  title: S86\n  description: d\n  report_title: S86\n"
)


def _spec(tmp_path: Path, **tables: str) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    for name, body in tables.items():
        (spec / name.replace("__", ".")).write_text(body, encoding="utf-8")
    return spec


_VARIANTS = "rsid,genotype,state,conclusion,gene\nrs1801133,C/T,risk,c,MTHFR\n"


def test_a_trait_id_that_lives_only_in_studies_csv_is_found(tmp_path: Path) -> None:
    """The reported case, and it is the whole item: the id is real and was never looked at."""
    spec = _spec(
        tmp_path,
        variants__csv=_VARIANTS,
        studies__csv="rsid,pmid,trait_efo_id\nrs1801133,25741868,EFO:0004458\n",
    )
    roster = authored_identifiers(spec, "trait_efo_id")
    assert roster.ids == ["EFO:0004458"]
    assert "studies.csv" in roster.read


def test_an_empty_roster_says_which_tables_were_behind_it(tmp_path: Path) -> None:
    """`0` must never mean two things. A module that genuinely declares no trait and one whose traits
    sit in an unread table both produce `ids == []`; only the first has read the tables."""
    spec = _spec(tmp_path, variants__csv=_VARIANTS, studies__csv="rsid,pmid\nrs1801133,25741868\n")
    roster = authored_identifiers(spec, "trait_efo_id")
    assert roster.ids == []
    # ...and this is what distinguishes it from the defect: the tables really were opened.
    assert sorted(roster.read) == ["studies.csv", "variants.csv"]
    assert all(why == "not present" for why in roster.not_read.values())
    assert roster.unreadable == {}


def test_a_table_that_will_not_parse_is_unread_rather_than_skipped(tmp_path: Path) -> None:
    """An absent optional table is the normal shape of every module and says nothing. One that exists
    and will not parse means ids the module carries went unchecked, which is the half worth warning
    about — so the two must not render the same way."""
    spec = _spec(
        tmp_path,
        variants__csv=_VARIANTS,
        studies__csv="rsid,pmid,trait_efo_id\nrs1801133,not-a-pmid,EFO:0004458\n",
    )
    roster = authored_identifiers(spec, "trait_efo_id")
    assert "studies.csv" not in roster.read
    assert "studies.csv" in roster.unreadable
    # The reason travels, rather than the file merely being missing from the list.
    assert "could not be read" in roster.not_read["studies.csv"]


def test_the_gene_half_reaches_a_pgx_table_too(tmp_path: Path) -> None:
    """Filed with the trait half because one fix covers both: a `gene` outside `variants.csv` was
    never checked either. `haplotypes.csv` carries `gene` and no `trait_efo_id`, so it also pins that
    the two rosters are built per column rather than per table."""
    spec = _spec(
        tmp_path,
        variants__csv="rsid,genotype,state,conclusion\nrs1801133,C/T,risk,c\n",
        studies__csv="rsid,pmid\nrs1801133,25741868\n",
        haplotypes__csv="haplotype_name,allele,gene,rsid\nCYP2C9*2,T,CYP2C9,rs1799853\n",
    )
    genes = authored_identifiers(spec, "gene")
    assert genes.ids == ["CYP2C9"]
    assert "haplotypes.csv" in genes.read
    # The same table is not in the trait roster at all — it declares no `trait_efo_id`.
    assert "haplotypes.csv" not in _id_bearing_tables("trait_efo_id")


def test_multi_valued_cells_split_and_dedupe_across_tables(tmp_path: Path) -> None:
    """One row may name several traits, and two tables may name the same one. First-occurrence order
    is preserved, because the roster is the order a reader sees in the report."""
    spec = _spec(
        tmp_path,
        variants__csv=(
            "rsid,genotype,state,conclusion,trait_efo_id\n"
            "rs1801133,C/T,risk,c,EFO:0004458;EFO:0004611\n"
        ),
        studies__csv="rsid,pmid,trait_efo_id\nrs1801133,25741868,EFO:0004458\n",
    )
    roster = authored_identifiers(spec, "trait_efo_id")
    assert roster.ids == ["EFO:0004458", "EFO:0004611"]


def test_the_roster_is_derived_from_the_registry_and_not_a_literal() -> None:
    """`@registry-completeness`, and the reason this repair is not a longer list.

    The defect was a roster naming one table while eleven declare the column, so a hand-kept set here
    would be the same bug with more strings in it. Asserted as an **equality over a walked set**: a
    table kind added later joins by existing, and one that never reached `DRAFTABLE` fails here rather
    than being silently unchecked.

    `MeasureBinRow` is excluded on purpose and nothing is missed — it is the abstract base whose four
    concrete subclasses are each their own entry, which this asserts rather than assumes.
    """
    from just_dna_format.base import AuthoredModel
    from just_dna_format.binning import MeasureBinRow
    from just_dna_format.reference import _ALL_MODELS

    for column in ("trait_efo_id", "gene"):
        walked = {
            model.__name__
            for model in _ALL_MODELS.values()
            if issubclass(model, AuthoredModel)
            and column in model.model_fields
            and model is not MeasureBinRow
        }
        derived = {model.__name__ for model in _id_bearing_tables(column).values()}
        assert derived == walked, column

    assert {c.__name__ for c in MeasureBinRow.__subclasses__()} <= {
        m.__name__ for m in _id_bearing_tables("trait_efo_id").values()
    }


def test_derived_tables_are_outside_the_roster() -> None:
    """`GeneMetricsRow`, `GeneValidityRow` and `GwasEffectRow` carry these columns and are machine-
    written, so a stale id in one is the *source's* currency and no author can act on it. Widening to
    them would report findings against rows nobody wrote."""
    from just_dna_format.gene_metrics import GeneMetricsRow
    from just_dna_format.gene_validity import GeneValidityRow

    models = set(_id_bearing_tables("gene").values())
    assert GeneMetricsRow not in models and GeneValidityRow not in models


@pytest.mark.parametrize("column", ["trait_efo_id", "gene"])
def test_a_spec_with_no_optional_tables_reads_what_exists(tmp_path: Path, column: str) -> None:
    """The ordinary module. Nothing is unreadable, and the absent kinds are recorded as absent rather
    than silently dropped, so the denominator is legible either way."""
    spec = _spec(tmp_path, variants__csv=_VARIANTS, studies__csv="rsid,pmid\nrs1801133,25741868\n")
    roster = authored_identifiers(spec, column)
    assert "variants.csv" in roster.read
    assert roster.unreadable == {}
    assert set(roster.read) | set(roster.not_read) == set(_id_bearing_tables(column))


def test_the_roster_type_separates_absent_from_unreadable() -> None:
    """A unit on the property, since the warning and the report both key on it."""
    roster = IdentifierRoster(
        not_read={"studies.csv": "not present", "pgs.csv": "could not be read (bad row)"}
    )
    assert roster.unreadable == {"pgs.csv": "could not be read (bad row)"}


# ── the reported surface: what a reader actually sees ────────────────────────────────────────────


def test_the_command_never_reports_a_pass_over_a_question_it_did_not_put(tmp_path: Path) -> None:
    """The same unreadable `0`, one level up, and the reason the CLI half is part of this fix.

    `report.clean` is vacuously true when nothing was checked, so the green *"all identifiers
    current"* asserted a pass over an empty roster — which is what a reader greps. It now says what it
    read, and the count names its own denominator.
    """
    from just_dna_enricher.cli import app
    from typer.testing import CliRunner

    spec = _spec(tmp_path, variants__csv=_VARIANTS, studies__csv="rsid,pmid\nrs1801133,25741868\n")
    result = CliRunner().invoke(
        app, ["check-identifiers", str(spec), "--no-traits", "--no-genes"]
    )
    assert result.exit_code == 0
    assert "all identifiers current" not in result.output
    assert "no identifiers were checked" in result.output
    # And the count states the tables it is out of, rather than a bare zero.
    assert "traits checked: 0 (from 0 table(s)" in result.output


# ── the residue: the widened roster could not be reached from a spec with no `variants.csv` ──────


_PGX_YAML = _YAML
_HAPLOTYPES = (
    "haplotype_name,rsid,start,allele,gene\n"
    "*2,rs4244285,94781859,A,CYP2C19\n"
)


def _hgnc(bands: dict[str, str]) -> OntologyClient:
    """An HGNC that approves exactly `bands`' symbols. Local to this file, which is offline by claim."""

    def handler(request: httpx.Request) -> httpx.Response:
        symbol = str(request.url).rsplit("/", 1)[-1]
        band = bands.get(symbol)
        if band is None or "prev_symbol" in str(request.url):
            return httpx.Response(200, json={"response": {"numFound": 0, "docs": []}})
        return httpx.Response(200, json={"response": {"numFound": 1, "docs": [
            {"symbol": symbol, "status": "Approved", "hgnc_id": "HGNC:1", "location": band}
        ]}})

    client = OntologyClient()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


def test_a_module_with_no_variants_csv_reaches_the_widened_roster(tmp_path: Path) -> None:
    """The residue of the widening, and the shape it is worst on.

    `variants.csv` is not mandatory, and the PGx kinds a module can be built entirely out of are among
    the nine tables that carry `gene`. `check_identifiers(spec_dir=)` nevertheless loaded that table
    unconditionally and raised `variants.csv is invalid: ... not found`, so the roster this file exists
    to widen could not be reached from a spec directory at all — the CLI's own filename guard returned
    first and hid it. This repo ships four such modules.
    """
    spec = _spec(tmp_path, haplotypes__csv=_HAPLOTYPES)
    assert not (spec / "variants.csv").exists()
    report = check_identifiers(
        spec_dir=spec, check_traits=False, client=_hgnc({"CYP2C19": "10q23.33"})
    )
    assert [g.symbol for g in report.genes] == ["CYP2C19"]
    assert report.gene_tables_read == ["haplotypes.csv"]


def test_no_rows_to_place_a_symbol_against_is_a_reason_and_not_a_silent_zero(tmp_path: Path) -> None:
    """`compared=0` with nothing beside it is the `ran(0, 0)` the attestation refuses to write.

    The gene/chromosome comparison needs rows; a module with none has symbols in hand and nothing to
    place them against, which is a question never put rather than an agreement.
    """
    spec = _spec(tmp_path, haplotypes__csv=_HAPLOTYPES)
    report = check_identifiers(
        spec_dir=spec, check_traits=False, client=_hgnc({"CYP2C19": "10q23.33"})
    )
    assert report.gene_loci_compared == 0
    assert report.gene_loci == []
    assert report.gene_loci_not_checked is not None
    assert "no variants.csv rows" in report.gene_loci_not_checked


def test_a_variants_csv_that_exists_and_will_not_parse_still_raises(tmp_path: Path) -> None:
    """Absent is a module shape; present-and-unreadable is the author's to fix, and stays an error."""
    spec = _spec(tmp_path, haplotypes__csv=_HAPLOTYPES, variants__csv="rsid,genotype\nrs1,\n")
    with pytest.raises(ValueError, match="variants.csv is invalid"):
        check_identifiers(spec_dir=spec, check_traits=False, check_genes=False)


def test_the_command_guard_is_the_roster_rather_than_a_filename(tmp_path: Path) -> None:
    """The CLI half. It opened on `variants.csv`'s existence and returned "nothing to check".

    Nine tables carry each column, so that guard skipped modules whose identifiers are entirely real.
    The replacement asks the roster: it says nothing to check only when no id-bearing table was read,
    and reaches HGNC on a module that carries one — which is why this half of the test needs no client
    (the empty case returns before any is built).
    """
    from just_dna_enricher.cli import app

    bare = _spec(tmp_path / "bare")
    result = CliRunner().invoke(app, ["check-identifiers", str(bare)])
    assert result.exit_code == 0
    assert "no variants.csv" not in result.output
    assert "no table carrying trait ids or gene symbols" in result.output
    # ...and nothing was attested, because no question was put.
    assert not (bare / "verification.json").exists()
