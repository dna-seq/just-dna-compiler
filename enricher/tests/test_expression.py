"""`alphagenome expression`: the pass that fills `expression_effects.csv` (RM194 + RM200).

Every case runs offline against a stub client. The live leg lives in `test_atlas_client.py`, behind
`JUST_DNA_NETWORK_TESTS=1` — a whole gene is ~50 minutes at the measured rate, so nothing here is
allowed near the network, and the arithmetic that would make it expensive is tested as a pure
function instead.

The stub returns hand-built blocks in the shape the service returns them: a `(1, tracks)` `RNA_SEQ`
block carrying a `gene_scorers` payload, which is what the row-major measurement on 2026-09-11
established and what `_gene_block`'s shape assertion is defending.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from just_dna_enricher.expression import (
    DEFAULT_MAX_ROWS,
    SIDECAR_NAME,
    WITHHELD_REASONS,
    ExpressionError,
    _summarise,
    enrich_expression,
)

_YAML = """\
schema_version: "1.0"
module:
  name: expression_pass
  title: Expression pass
  description: fixture
  report_title: Expression pass
genome_build: GRCh38
"""


@dataclass(frozen=True)
class _Gene:
    gene_id: str
    name: str


@dataclass(frozen=True)
class _Block:
    scorer: str
    raw: tuple
    shape: tuple
    genes: tuple = ()
    quantile: tuple | None = None


@dataclass(frozen=True)
class _Score:
    chrom: str
    position: int
    ref: str
    alt: str
    scores: tuple


@dataclass
class _Stub:
    """Returns prepared scores and records what it was asked, so a test can assert the query."""

    scores: tuple = ()
    asked: list = field(default_factory=list)

    def score_interval(self, chrom, start, end, *, scorers=(), gene_names=(), field_mask=True):
        self.asked.append((chrom, start, end, scorers, gene_names))
        return self.scores


_HFE_GENE = (_Gene("ENSG00000010704.19", "HFE"),)


def _tracks(down: int, up: int) -> tuple:
    """A track vector with a stated split, so a test never counts on an opaque fixture."""
    return tuple([-0.5] * down + [0.25] * up)


def _score(position: int, *, down: int = 300, up: int = 71, ref: str = "G", alt: str = "A") -> _Score:
    return _Score("chr6", position, ref, alt,
                  (_Block("RNA_SEQ", _tracks(down, up), (1, down + up), _HFE_GENE),))


def _spec(tmp_path: Path) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML)
    return spec


def _run(spec: Path, stub: _Stub, **kw):
    """The pass with the licence declared and no MANE lane, which is the ordinary offline case."""
    args = {"chrom": "6", "start": 26089000, "end": 26091000,
            "declared_use": "non_commercial", "mane_cache": spec / "no-mane-lane"}
    args.update(kw)
    return enrich_expression(spec, "HFE", client=stub, **args)


# ── what one row says ────────────────────────────────────────────────────────────────────────────


def test_a_scored_variant_becomes_one_row_carrying_the_sources_own_gene(tmp_path: Path) -> None:
    result = _run(_spec(tmp_path), _Stub((_score(26090000),)))
    (row,) = result.rows
    assert row.gene == "HFE"
    assert row.gene_id == "ENSG00000010704.19", "the versioned accession the service sent, verbatim"
    assert row.effect_measure == "RNA_SEQ"
    assert (row.chrom, row.start, row.ref, row.alt) == ("6", 26090000, "G", "A")


def test_the_contig_is_stored_the_way_a_module_spells_it(tmp_path: Path) -> None:
    """RM193 found this exact join matching nothing while looking like an uncovered region.

    The artifact and the API ship `chr22`; a `VariantRow` stores `22`. A silent wrong answer, because
    an empty join and an unscored region are indistinguishable downstream.
    """
    result = _run(_spec(tmp_path), _Stub((_score(26090000),)))
    assert result.rows[0].chrom == "6"
    assert not result.rows[0].chrom.startswith("chr")


def test_the_query_is_always_gene_filtered_because_an_unfiltered_one_cannot_be_served(
    tmp_path: Path,
) -> None:
    """Not an optimisation: unfiltered, 32 bp answers with 43 MB against grpc's 4 MB limit."""
    stub = _Stub((_score(26090000),))
    _run(_spec(tmp_path), stub)
    (_chrom, _start, _end, scorers, genes) = stub.asked[0]
    assert genes == ("HFE",)
    assert scorers == ("RNA_SEQ",)


# ── the two aggregates, which answer different questions ─────────────────────────────────────────


def test_direction_is_the_majority_sign_and_size_is_the_extreme_keeping_it(tmp_path: Path) -> None:
    """`effect_size` keeps the sign AVI's `MAX_ABS` features discard — the point of the whole item."""
    result = _run(_spec(tmp_path), _Stub((_score(26090000, down=300, up=71),)))
    row = result.rows[0]
    assert row.effect_direction == "decrease"
    assert row.effect_size == -0.5
    assert (row.tracks_agreeing, row.tracks_total) == (300, 371)


def test_an_even_split_names_no_direction_rather_than_picking_one(tmp_path: Path) -> None:
    """The house algebra: unknown withholds, and a tie is genuinely unknown.

    The magnitude survives, because "we cannot say which way" is not "we measured nothing".
    """
    result = _run(_spec(tmp_path), _Stub((_score(26090000, down=50, up=50),)))
    row = result.rows[0]
    assert row.effect_direction is None
    assert row.effect_size is not None
    assert row.tracks_agreeing == 0


def test_the_two_aggregates_are_allowed_to_disagree() -> None:
    """One tissue moving hard against a mild general trend is real, not an inconsistency.

    Asserted on the pure function so the case can be stated exactly: nine tracks up a little, one
    down a lot. Consensus says increase; the strongest single effect is a decrease.
    """
    size, direction, agreeing, total = _summarise(tuple([0.1] * 9 + [-0.9]))
    assert direction == "increase"
    assert size == -0.9
    assert (agreeing, total) == (9, 10)


def test_agreement_is_recorded_and_never_gates(tmp_path: Path) -> None:
    """RM200 tested consensus-as-confidence and killed it — `CAGE` is 97% unanimous at PHRED 0.007.

    So a barely-agreeing row is written exactly like a unanimous one, and the counts are the record.
    """
    barely = _run(_spec(tmp_path / "a"), _Stub((_score(26090000, down=186, up=185),)))
    unanimous = _run(_spec(tmp_path / "b"), _Stub((_score(26090000, down=371, up=0),)))
    assert barely.written == unanimous.written == 1


# ── the shape assertion ──────────────────────────────────────────────────────────────────────────


def test_a_block_with_more_than_one_gene_is_withheld_rather_than_guessed_at(tmp_path: Path) -> None:
    """A leading axis other than 1 means the gene filter did not apply.

    Picking a gene from a multi-gene block would be inventing the attribution
    `@gene-map-is-another-sources-attribution` exists to forbid — so it is refused under a counted
    reason, which is what keeps the candidate accounting honest instead of quietly dropping a row.
    """
    unfiltered = _Score("chr6", 26090000, "G", "A",
                        (_Block("RNA_SEQ", tuple([0.1] * 10), (2, 5), _HFE_GENE),))
    result = _run(_spec(tmp_path), _Stub((unfiltered,)))
    assert result.written == 0
    assert result.withheld == {"no_gene_axis": 1}
    assert result.accounts_for_every_candidate()


def test_every_admitted_candidate_is_written_or_counted_under_a_named_reason(tmp_path: Path) -> None:
    """The self-audit, over a mixed batch — a withhold that cannot say which kind it was is the
    absence the roster exists to prevent."""
    scores = (
        _score(26090000),
        _Score("chr6", 26090001, "C", "T", (_Block("RNA_SEQ", tuple([0.1] * 10), (3, 4), _HFE_GENE),)),
        _score(26090002, ref="A", alt="T"),
    )
    result = _run(_spec(tmp_path), _Stub(scores))
    assert result.candidates == 3
    assert result.accounts_for_every_candidate()
    assert set(result.withheld) <= set(WITHHELD_REASONS)


# ── merge-not-clobber ────────────────────────────────────────────────────────────────────────────


def test_a_second_lap_adds_nothing_and_does_not_move_the_bytes(tmp_path: Path) -> None:
    """Lap-stable is a property of the module, fired matched-or-not (`@lap-stable-means-a-property-
    of-the-module`), so the assertion is an equality between laps rather than a floor."""
    spec = _spec(tmp_path)
    scores = (_score(26090000), _score(26090001, ref="C", alt="T"))
    first = _run(spec, _Stub(scores))
    written_once = (spec / SIDECAR_NAME).read_text()

    second = _run(spec, _Stub(scores))
    assert second.written == 0
    assert second.withheld["already_recorded"] == len(scores)
    assert (spec / SIDECAR_NAME).read_text() == written_once
    assert len(second.rows) == len(first.rows)


def test_a_hand_edited_row_survives_a_re_run(tmp_path: Path) -> None:
    """Merge, never clobber. The existing row is authoritative on the key it already holds."""
    spec = _spec(tmp_path)
    _run(spec, _Stub((_score(26090000),)))
    edited = (spec / SIDECAR_NAME).read_text().replace("RNA_SEQ", "RNA_SEQ_CURATED")
    (spec / SIDECAR_NAME).write_text(edited)

    _run(spec, _Stub((_score(26090000),)))
    assert "RNA_SEQ_CURATED" in (spec / SIDECAR_NAME).read_text()


def test_the_header_is_the_model_and_not_a_hand_kept_list(tmp_path: Path) -> None:
    """`@fieldnames-from-model`: a hand-kept column list loses a column."""
    from just_dna_format.expression import ExpressionEffectRow

    spec = _spec(tmp_path)
    _run(spec, _Stub((_score(26090000),)))
    header = (spec / SIDECAR_NAME).read_text().splitlines()[0].split(",")
    assert set(header) == set(ExpressionEffectRow.model_fields)


def test_an_unreadable_existing_sidecar_raises_rather_than_being_overwritten(tmp_path: Path) -> None:
    """Merging into a table that did not parse would silently drop every recorded row."""
    spec = _spec(tmp_path)
    (spec / SIDECAR_NAME).write_text("variant_key,gene,dataset\n,,\n")
    with pytest.raises(ExpressionError, match="invalid"):
        _run(spec, _Stub((_score(26090000),)))


# ── the three ways to write nothing, kept apart ──────────────────────────────────────────────────


def test_offline_is_a_stated_no_op_and_not_a_failure(tmp_path: Path) -> None:
    spec = _spec(tmp_path)
    result = enrich_expression(spec, "HFE", offline=True, declared_use="non_commercial")
    assert result.skipped and not (spec / SIDECAR_NAME).exists()
    assert "offline" in result.warnings[0].lower()


def test_an_undeclared_run_skips_in_the_sources_own_words_before_any_request(tmp_path: Path) -> None:
    """`check_declared_use` gates the FETCH (`@acquisition-gate-is-not-a-read-gate`), and with
    `commercial_use=False` an undeclared run is a skip rather than permission.

    The stub records what it was asked, so this proves the gate runs *before* the RPC rather than
    merely that nothing was written.
    """
    spec = _spec(tmp_path)
    stub = _Stub((_score(26090000),))
    result = enrich_expression(spec, "HFE", client=stub, chrom="6", start=1, end=2,
                               mane_cache=spec / "none")
    assert result.skipped
    assert stub.asked == [], "the gate must run before the request, not after it"
    assert not (spec / SIDECAR_NAME).exists()


def test_an_empty_answer_writes_no_row_and_names_both_readings_it_cannot_separate(
    tmp_path: Path,
) -> None:
    """`@unreachable-not-absent`: write no row, name it separately — and two readings of one silence
    are not automatically equal, so both are stated rather than one being chosen."""
    spec = _spec(tmp_path)
    result = _run(spec, _Stub(()))
    assert result.written == 0 and not (spec / SIDECAR_NAME).exists()
    note = " ".join(result.warnings)
    assert "horizon" in note and "does not know the symbol" in note


def test_nothing_written_means_no_source_row_either(tmp_path: Path) -> None:
    """The `SourceRow` is written only when the run actually covered something — a filter that
    matched nothing must leave the licence table untouched."""
    spec = _spec(tmp_path)
    _run(spec, _Stub(()))
    assert not (spec / "licensing.csv").exists() and not (spec / "sources.csv").exists()


def test_a_covered_run_writes_the_source_row_under_its_own_layer(tmp_path: Path) -> None:
    """`@write-the-sourcerow`, keyed `(source, layer)` — and never `alphagenome_avi`'s row, because
    one name cannot carry two licence classes."""
    spec = _spec(tmp_path)
    _run(spec, _Stub((_score(26090000),)))
    table = (spec / "licensing.csv").read_text()
    assert "alphagenome_atlas,expression_effect" in table
    assert "alphagenome_avi" not in table


# ── distance, and the bar that needs it ──────────────────────────────────────────────────────────


def test_distance_is_null_with_a_stated_reason_when_no_span_is_available(tmp_path: Path) -> None:
    """Null rather than an interval edge, which would be a number that looks like a distance."""
    result = _run(_spec(tmp_path), _Stub((_score(26090000),)))
    assert result.rows[0].distance_to_gene is None
    assert any("mane build" in w for w in result.warnings)


def test_distance_is_measured_from_the_mane_span_even_when_the_interval_was_explicit(
    tmp_path: Path,
) -> None:
    """Two questions, and an explicit interval only answers the first.

    Supplying `--chrom/--start/--end` makes the *query* possible without MANE; it does not make
    `distance_to_gene` computable, because distance is to the gene rather than to the window. So the
    lane is consulted either way, and this is the positive half of the tri-state the test above
    covers the null half of.
    """
    pl = pytest.importorskip("polars", reason="writing the fixture snapshot needs the [dev] extra")
    mane = tmp_path / "mane"
    mane.mkdir(parents=True)
    pl.DataFrame(
        [{"symbol": "HFE", "grch38_chr": "NC_000006.12", "chr_start": 26087281,
          "chr_end": 26098343, "mane_status": "MANE Select"}],
        schema={"symbol": pl.Utf8, "grch38_chr": pl.Utf8, "chr_start": pl.Int64,
                "chr_end": pl.Int64, "mane_status": pl.Utf8},
    ).write_parquet(mane / "summary.parquet")

    spec = _spec(tmp_path)
    inside = _score(26090000)                       # within the gene
    upstream = _score(26000000, ref="C", alt="T")   # 87,281 bp before it starts
    result = _run(spec, _Stub((inside, upstream)), mane_cache=mane)

    by_position = {row.start: row.distance_to_gene for row in result.rows}
    assert by_position[26090000] == 0, "a variant inside the gene is at distance zero"
    assert by_position[26000000] == 26087281 - 26000000
    assert not any("mane build" in w for w in result.warnings)


def test_the_identity_names_the_sources_assembly_and_not_the_modules(tmp_path: Path) -> None:
    """A GRCh37 module still gets GRCh38-minted keys, and is *told* rather than silently corrected.

    The AST guard in `test_build_call_sites.py` checks that a `build=` is passed; it cannot check
    which one, and the two candidates here are both defensible-sounding. The coordinate in the row
    came from AlphaGenome, which serves GRCh38 only, so the identity minted from it names GRCh38 —
    minting it as the module's declared build would claim a liftover nobody performed.

    The disagreement is reported and never repaired, which is the call every drafting provider makes
    (`@restamp-for-build`: the row's build travels to the mint, and the mismatch is a warning).
    """
    spec = _spec(tmp_path)
    (spec / "module_spec.yaml").write_text(_YAML.replace("GRCh38", "GRCh37"))
    result = _run(spec, _Stub((_score(26090000),)))

    from just_dna_format.base import derive_variant_key

    expected = derive_variant_key(None, "6", 26090000, "G", "A", build="GRCh38")
    assert result.rows[0].variant_key == expected
    assert expected != derive_variant_key(None, "6", 26090000, "G", "A", build="GRCh37")
    assert any("GRCh37" in w for w in result.warnings), "the build disagreement must be reported"


def test_min_score_withholds_under_its_own_reason(tmp_path: Path) -> None:
    result = _run(_spec(tmp_path), _Stub((_score(26090000),)), min_score=10.0)
    assert result.written == 0
    assert result.withheld == {"below_min_score": 1}


def test_more_rows_than_the_cap_refuses_and_says_how_to_get_past_it(tmp_path: Path) -> None:
    """Refusing beats truncating: a silently short table is a false claim about a locus."""
    scores = tuple(_score(26090000 + i) for i in range(4))
    with pytest.raises(ExpressionError, match="over the"):
        _run(_spec(tmp_path), _Stub(scores), max_rows=2)


def test_the_cap_is_a_named_default_rather_than_a_literal() -> None:
    """A constant two deployments want different values of is a knob (`@retry-attempt-floor`)."""
    assert DEFAULT_MAX_ROWS > 0


# ── the live leg ─────────────────────────────────────────────────────────────────────────────────
#
# Opt-in twice over (`@network-tests-optin`): `JUST_DNA_NETWORK_TESTS=1` **and** a key, because a
# missing credential and a switched-off network test are different absences and neither should look
# like the other.
#
# **One test, one 400 bp interval, and that is a deliberate ceiling.** A whole gene plus its ±512 kb
# flanks is ~3.3 M SNVs at the measured 1,091 SNVs/s — about 50 minutes — which is precisely why
# RM194 sat unbuilt. A gene-filtered 400 bp query answers in ~1.1 s, so the live leg proves the
# premise everything offline rests on without the suite ever going near the expensive path. The
# ±512 kb horizon itself is *not* re-measured here: RM194 already measured it (scores at +500 kb,
# nothing at +700 kb) and the ROADMAP entry is the record, so paying for it again on every run would
# buy a number we already have.

NETWORK = os.environ.get("JUST_DNA_NETWORK_TESTS") == "1"
API_KEY = os.environ.get("ALPHAGENOME_API_KEY") or ""
live = pytest.mark.skipif(
    not (NETWORK and API_KEY),
    reason="set JUST_DNA_NETWORK_TESTS=1 and ALPHAGENOME_API_KEY to run the live leg",
)


@live
def test_the_service_really_does_return_one_gene_axis_and_name_it(tmp_path: Path) -> None:
    """The premise every offline test here stands on, checked against the real service.

    Three claims, none of which this workspace can prove by asserting against its own stub:

    1. a gene-filtered interval answers `(1, tracks)`, so `_gene_block`'s shape assertion is
       defending a real invariant rather than a fixture convention;
    2. the block carries a `gene_scorers` payload, so `gene_id` is the source's own attribution and
       not something reconstructed — `@gene-map-is-another-sources-attribution`;
    3. the accession comes back **versioned**, contradicting upstream's own proto comment, which is
       the reason the column stores it verbatim.
    """
    pytest.importorskip("grpc", reason="the [atlas] extra is what makes the Atlas reachable")
    from just_dna_enricher.atlas_client import connect

    spec = _spec(tmp_path)
    result = enrich_expression(
        spec, "TBX1",
        chrom="22", start=19756703, end=19757103,
        client=connect(API_KEY),
        declared_use="non_commercial",
        mane_cache=spec / "no-mane-lane",
    )

    assert result.written > 0, "a 400 bp interval inside TBX1 returned no scored variant"
    assert "no_gene_axis" not in result.withheld, (
        "a gene-filtered query came back with a leading axis other than 1 — the filter did not apply"
    )
    row = result.rows[0]
    assert row.gene == "TBX1"
    assert row.gene_id and row.gene_id.startswith("ENSG"), "the service named no gene accession"
    assert "." in row.gene_id, (
        "the accession came back unversioned — upstream's proto comment would then be right, and "
        "this column's whole justification for storing it verbatim would need re-reading"
    )
    assert row.tracks_total > 1, "RNA_SEQ reported a single track, which is not the gene axis"
