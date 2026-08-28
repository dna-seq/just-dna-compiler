"""The PubMind snapshot builder, against a real slice of the ANNOVAR-distributed table (RM134 § A).

The fixture (`assets/hg38_pubmind_db_slice.txt.gz`) is cut from the actual 2026-08-24
`hg38_pubmind_db.txt.gz`, and it is cut rather than written because every property under test only
exists in the real file: the HFE C282Y coordinate carrying several PVIDs whose verdicts disagree, the
`A>0` and `A>N` rows whose alt is not an allele, the `Ref == Alt` rows, the codon triplets differing
at one, two and three bases, and the pair of triplets that decompose onto one identical output row.

**No count from the assessment document is pasted into an assertion.** Those numbers are a dated
reading of a file that will move, and a test pinning them fails on the next ANNOVAR release for no
reason. Every expected value below is recomputed from the fixture at runtime; the only hardcoded
values are domain constants — column names, vocabulary members, the HFE coordinate.
"""

import csv
import gzip
import json
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher.clin_sig import normalize_clin_sig
from just_dna_enricher.pubmind_build import (
    DEFAULT_PUBMIND_URL,
    PUBMIND_DERIVATIONS,
    PUBMIND_DROP_REASONS,
    PubMindBuildError,
    PubMindUnavailable,
    build_snapshot,
    download_pubmind_table,
)
from just_dna_format.vocab import VALID_CLIN_SIG

_SLICE = Path(__file__).resolve().parents[2] / "assets" / "hg38_pubmind_db_slice.txt.gz"

#: HFE C282Y — one of the best-characterised variants in medical genetics, and the worked example of
#: PubMind's record identity: consolidation into a PVID is keyed on the extracted *text*, so one
#: physical variant fragments into many records whose verdicts disagree.
_HFE_C282Y = ("6", 26092913, "G", "A")


def _source_rows() -> list[dict[str, str]]:
    with gzip.open(_SLICE, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("pubmind")
    result = build_snapshot(_SLICE, out)
    return result, pl.read_parquet(result.parquet_file), json.loads(
        (out / "release.json").read_text()
    )


# ── the fixture really does carry the shapes the rules exist for ────────────────────────────────


def test_the_fixture_carries_every_shape_the_builder_decides_about() -> None:
    """Guard the premise: a slice missing a shape would make the rule for it untested and green."""
    shapes: dict[str, int] = {}
    for row in _source_rows():
        ref, alt = row["Ref"], row["Alt"]
        if not (set(ref) <= set("ACGT") and set(alt) <= set("ACGT")):
            name = "non_acgt"
        elif ref == alt:
            name = "ref_equals_alt"
        elif len(ref) != len(alt):
            name = "indel"
        elif len(ref) == 1:
            name = "direct"
        else:
            differing = sum(1 for a, b in zip(ref, alt, strict=True) if a != b)
            name = "codon_d1" if differing == 1 else f"codon_d{differing}"
        shapes[name] = shapes.get(name, 0) + 1
    for required in ("non_acgt", "ref_equals_alt", "indel", "direct", "codon_d1", "codon_d2"):
        assert shapes.get(required, 0) > 0, (required, shapes)


def test_the_fixture_carries_the_contested_hfe_coordinate() -> None:
    """The multi-PVID case is the finding this snapshot exists to keep, so it has to be in the slice."""
    chrom, start, ref, alt = _HFE_C282Y
    at_locus = [r for r in _source_rows() if r["#Chr"] == chrom and int(r["Start"]) == start]
    joinable = [r for r in at_locus if r["Ref"] == ref and r["Alt"] == alt]
    assert len({r["PVID"] for r in joinable}) > 1, at_locus
    assert len({normalize_clin_sig(r["PubMindDB_pathogenicity_sum"]) for r in joinable}) > 1


# ── every row is accounted for, as an equality over the walked drop registry ─────────────────────


def test_every_input_row_is_either_kept_or_counted_under_a_named_reason(snapshot) -> None:
    """The one assertion that makes "we dropped two thirds of the file" honest.

    An equality over the walked registry rather than a floor: a new drop reason that forgets to join
    the sum breaks this, which is the whole point of `PUBMIND_DROP_REASONS` being a registry
    (`@registry-completeness`). Silent truncation reads as full coverage.
    """
    result, frame, release = snapshot
    assert set(result.dropped) == set(PUBMIND_DROP_REASONS)
    assert result.input_rows == len(_source_rows())
    assert result.record_count == frame.height
    assert result.input_rows == result.record_count + sum(result.dropped.values())
    assert release["dropped"] == result.dropped
    assert release["input_rows"] == result.input_rows
    assert release["record_count"] == result.record_count


def test_a_drop_count_is_zero_only_where_the_filter_really_found_nothing(snapshot) -> None:
    """The counters are measurements, not decoration — each is recomputed from the fixture here.

    `off_target_chrom` is the one that reads zero on this file, and it is kept because it is a real
    filter a future ANNOVAR release carrying a scaffold would trip, not a check that cannot fail.
    """
    result, _frame, _release = snapshot
    rows = _source_rows()
    valid = {str(i) for i in range(1, 23)} | {"X", "Y", "MT"}
    assert result.dropped["off_target_chrom"] == sum(1 for r in rows if r["#Chr"] not in valid)
    assert result.dropped["non_acgt"] == sum(
        1 for r in rows if not (set(r["Ref"]) <= set("ACGT") and set(r["Alt"]) <= set("ACGT"))
    )
    acgt = [r for r in rows if set(r["Ref"]) <= set("ACGT") and set(r["Alt"]) <= set("ACGT")]
    assert result.dropped["ref_equals_alt"] == sum(1 for r in acgt if r["Ref"] == r["Alt"])


# ── the decomposition ───────────────────────────────────────────────────────────────────────────


def test_a_codon_block_differing_at_one_base_lands_on_that_base(snapshot) -> None:
    """Decomposition as a property over every such row in the fixture, not one worked example."""
    _result, frame, _release = snapshot
    emitted = {tuple(r) for r in frame.select("chrom", "start", "ref", "alt", "pvid").rows()}
    checked = 0
    for row in _source_rows():
        ref, alt = row["Ref"], row["Alt"]
        if len(ref) != len(alt) or len(ref) == 1 or ref == alt:
            continue
        differing = [i for i in range(len(ref)) if ref[i] != alt[i]]
        if len(differing) != 1:
            continue
        index = differing[0]
        assert (
            row["#Chr"], int(row["Start"]) + index, ref[index], alt[index], row["PVID"],
        ) in emitted
        checked += 1
    assert checked > 0, "the fixture must contain decomposable rows or this asserts nothing"


def test_a_block_needing_two_substitutions_is_dropped_rather_than_guessed_at(snapshot) -> None:
    """It asserts a change to the protein, not to a position a consumer can genotype.

    Two halves, and the second is the one a coarser assertion misses: the count must match the
    fixture's own, *and* no equal-length multi-base block may survive into the output at all. Keying
    the check on `(chrom, start, pvid)` would be wrong — the same PVID legitimately reaches the same
    position through a different source row, so a per-key absence test fails on correct output.
    """
    result, frame, _release = snapshot
    expected = 0
    for row in _source_rows():
        ref, alt = row["Ref"], row["Alt"]
        if not (set(ref) <= set("ACGT") and set(alt) <= set("ACGT")) or ref == alt:
            continue
        if len(ref) != len(alt) or len(ref) == 1:
            continue
        if sum(1 for a, b in zip(ref, alt, strict=True) if a != b) > 1:
            expected += 1
    assert expected > 0, "the fixture must carry undecomposable blocks"
    assert result.dropped["multi_substitution"] == expected
    survivors = [
        (r, a) for r, a in zip(frame["ref"], frame["alt"], strict=True) if len(r) == len(a) > 1
    ]
    assert survivors == []


def test_every_kept_row_carries_a_derivation_and_the_vocabulary_is_covered(snapshot) -> None:
    """An equality over the walked vocabulary: a member no row reaches is a member nothing tests."""
    result, frame, release = snapshot
    assert set(frame["derivation"].to_list()) == PUBMIND_DERIVATIONS
    assert set(result.derivations) == PUBMIND_DERIVATIONS
    assert sum(result.derivations.values()) == frame.height
    assert release["derivations"] == result.derivations
    indels = frame.filter(pl.col("derivation") == "indel")
    assert indels.height > 0
    assert all(len(r) != len(a) for r, a in zip(indels["ref"], indels["alt"], strict=True))


# ── the multiplicity is recorded, and nothing collapses it ──────────────────────────────────────


def test_every_pvid_on_a_contested_coordinate_survives_as_its_own_row(snapshot) -> None:
    """Collapsing to one winner was rejected: it needs an ordering nobody defined.

    Recomputed from the fixture rather than pinned, and asserted as the *set* of PVIDs rather than a
    count — a builder that kept the right number of the wrong records would pass a count.
    """
    _result, frame, _release = snapshot
    chrom, start, ref, alt = _HFE_C282Y
    expected = {
        r["PVID"]
        for r in _source_rows()
        if (r["#Chr"], int(r["Start"]), r["Ref"], r["Alt"]) == _HFE_C282Y
    }
    got = frame.filter(
        (pl.col("chrom") == chrom) & (pl.col("start") == start)
        & (pl.col("ref") == ref) & (pl.col("alt") == alt)
    )
    assert set(got["pvid"].to_list()) == expected
    assert got.height == len(expected)
    # The verdicts really do disagree — which is why keeping them all is a finding rather than noise.
    assert len(set(got["clin_sig"].to_list())) > 1


def test_the_multiplicity_and_the_disagreement_are_both_recorded(snapshot) -> None:
    """Two different numbers: how many coordinates carry several records, and how many contradict.

    A coordinate whose records all agree is tidy-up work; one whose records disagree is the reason
    the multiplicity may not be collapsed. Recording only the first would lose that.
    """
    result, frame, release = snapshot
    by_key: dict[tuple, set[str]] = {}
    sigs: dict[tuple, set[str]] = {}
    for chrom, start, ref, alt, pvid, sig in frame.select(
        "chrom", "start", "ref", "alt", "pvid", "clin_sig"
    ).rows():
        by_key.setdefault((chrom, start, ref, alt), set()).add(pvid)
        sigs.setdefault((chrom, start, ref, alt), set()).add(sig)
    assert result.allele_keys == len(by_key)
    assert result.multi_pvid_keys == sum(1 for v in by_key.values() if len(v) > 1)
    assert result.max_pvids_per_key == max(len(v) for v in by_key.values())
    assert result.contested_keys == sum(1 for v in sigs.values() if len(v) > 1)
    assert result.contested_keys > 0, "the fixture must carry a real disagreement"
    assert result.contested_keys <= result.multi_pvid_keys
    for name in ("allele_keys", "multi_pvid_keys", "max_pvids_per_key", "contested_keys"):
        assert release[name] == getattr(result, name)


def test_two_source_rows_decomposing_onto_one_identical_row_collapse_and_are_counted(
    snapshot,
) -> None:
    """The model enumerates several ref codons for one amino-acid change, and two can meet.

    Collapsed only when *every* column matches — a pair differing anywhere is two claims and stays
    two rows, because the dedup key decides which columns may become several rows.
    """
    result, frame, _release = snapshot
    assert result.dropped["identical_duplicate"] > 0, "the fixture must carry the collision"
    assert frame.height == frame.unique().height


# ── the columns ─────────────────────────────────────────────────────────────────────────────────


def test_the_columns_are_unprefixed_and_share_the_clinvar_snapshot_vocabulary(snapshot) -> None:
    """`clin_sig`/`clin_sig_raw`, never `pubmind_sig`: the source is the file, so a prefix restates it.

    One column vocabulary across every snapshot is what lets an N-authority check read them all with
    no per-source mapping, which is the reason the rename is not cosmetic.
    """
    _result, frame, _release = snapshot
    from just_dna_enricher.clinvar_build import _empty_schema

    assert frame.columns == [
        "chrom", "start", "ref", "alt", "pvid",
        "clin_sig", "clin_sig_raw", "pathogenicity_score", "confidence", "derivation",
    ]
    shared = {"chrom", "start", "ref", "alt", "clin_sig", "clin_sig_raw"}
    assert shared <= set(_empty_schema())
    assert not [c for c in frame.columns if c.startswith("pubmind")]


def test_clin_sig_is_normalized_by_the_shared_normalizer_and_the_raw_token_survives(
    snapshot,
) -> None:
    """The mapping stays auditable: `clin_sig_raw` is verbatim, `clin_sig` is the fold of it."""
    _result, frame, _release = snapshot
    assert set(frame["clin_sig"].to_list()) <= VALID_CLIN_SIG
    for mapped, raw in zip(frame["clin_sig"], frame["clin_sig_raw"], strict=True):
        assert mapped == normalize_clin_sig(raw)
    assert set(frame["clin_sig_raw"].to_list()) <= {
        r["PubMindDB_pathogenicity_sum"] for r in _source_rows()
    }
    # The two tokens the shared normalizer was fixed for really do occur here, and neither is `other`.
    assert {"uncertain_significance", "conflicting"} <= set(frame["clin_sig"].to_list())


def test_a_missing_score_is_null_and_never_zero(snapshot) -> None:
    """PubMind leaves the paper-level score blank on rows it did not compute one for.

    Reading a blank as `0.0` would invent a confidently-benign verdict, which is the opposite of what
    the absence says.
    """
    _result, frame, _release = snapshot
    blank = sum(1 for r in _source_rows() if not r["PubMindDB_paper_level_pathogenicity_score"])
    assert blank > 0, "the fixture must carry rows with no score"
    assert frame["pathogenicity_score"].null_count() > 0
    assert 0.0 not in frame.filter(pl.col("pathogenicity_score").is_null())["pathogenicity_score"]


def test_start_is_the_source_position_untouched_for_a_direct_row(snapshot) -> None:
    """`start` is the 1-based VCF position; a direct row must not be shifted (`@start-1based`)."""
    _result, frame, _release = snapshot
    direct = frame.filter(pl.col("derivation") == "direct")
    positions = {
        (r["#Chr"], int(r["Start"]), r["Ref"], r["Alt"])
        for r in _source_rows()
        if len(r["Ref"]) == len(r["Alt"]) == 1
    }
    for chrom, start, ref, alt in direct.select("chrom", "start", "ref", "alt").rows():
        assert (chrom, start, ref, alt) in positions


# ── reproducibility and provenance ──────────────────────────────────────────────────────────────


def test_rebuild_is_byte_identical(tmp_path: Path) -> None:
    """Principle 7: the fixed column order and explicit sort make the parquet reproducible."""
    first = build_snapshot(_SLICE, tmp_path / "a")
    second = build_snapshot(_SLICE, tmp_path / "b")
    assert first.parquet_file.read_bytes() == second.parquet_file.read_bytes()

    release_a = json.loads((tmp_path / "a" / "release.json").read_text())
    release_b = json.loads((tmp_path / "b" / "release.json").read_text())
    assert release_a.pop("built_at") != "" and release_b.pop("built_at") != ""
    assert release_a == release_b


def test_rows_are_emitted_in_karyotype_order(snapshot) -> None:
    """Parquet bytes depend on row order, so the order is stated rather than inherited from a dict."""
    _result, frame, _release = snapshot
    order = [str(i) for i in range(1, 23)] + ["X", "Y", "MT"]
    keys = [
        (order.index(c), s, r, a, p)
        for c, s, r, a, p in frame.select("chrom", "start", "ref", "alt", "pvid").rows()
    ]
    assert keys == sorted(keys)


def test_release_json_records_the_provenance_and_says_the_terms_are_unknown(snapshot) -> None:
    """All three of sha256/ETag/Last-Modified, so an upstream revision becomes a finding.

    A local `--table` establishes none of the two headers, so they are recorded as `null` — unknown
    rather than absent, the tri-state everywhere else in this workspace.
    """
    result, _frame, release = snapshot
    assert release["source_sha256"] == result.source_sha256
    assert release["dataset"] == result.dataset
    assert result.dataset is not None and result.source_sha256 is not None
    assert result.dataset.endswith(result.source_sha256[:12])
    assert release["source_etag"] is None and release["source_last_modified"] is None
    assert release["genome_build"] == "GRCh38"
    assert release["redistributable"] is False
    assert "no data terms" in release["notice"]
    assert release["builder_version"] and release["built_at"]


def test_a_download_carries_its_etag_and_last_modified_into_the_release(tmp_path: Path) -> None:
    """The headers reach `release.json` when the caller has them, which is the point of keeping them."""
    result = build_snapshot(
        _SLICE, tmp_path / "snap",
        source_sha256="deadbeef" * 8,
        source_etag='"63275d-659cb3f35fd80"',
        source_last_modified="Mon, 24 Aug 2026 13:48:54 GMT",
    )
    release = json.loads((tmp_path / "snap" / "release.json").read_text())
    assert release["source_etag"] == '"63275d-659cb3f35fd80"'
    assert release["source_last_modified"] == "Mon, 24 Aug 2026 13:48:54 GMT"
    assert release["source_sha256"] == "deadbeef" * 8
    assert result.dataset == "pubmind_deadbeefdead"


# ── refusals ────────────────────────────────────────────────────────────────────────────────────


def test_a_table_with_the_wrong_columns_is_refused_rather_than_mis_parsed(tmp_path: Path) -> None:
    """A silently mis-parsed table would put someone else's numbers behind PubMind's name."""
    path = tmp_path / "wrong.txt"
    path.write_text("#Chr\tStart\tEnd\tRef\tAlt\n1\t100\t100\tA\tG\n", encoding="utf-8")
    with pytest.raises(PubMindBuildError) as caught:
        build_snapshot(path, tmp_path / "out")
    assert "PVID" in str(caught.value)


def test_a_missing_table_raises_rather_than_writing_an_empty_snapshot(tmp_path: Path) -> None:
    """An empty snapshot would later read as "PubMind says nothing about anything"."""
    with pytest.raises(FileNotFoundError):
        build_snapshot(tmp_path / "absent.txt.gz", tmp_path / "out")


def _tiny(tmp_path: Path, body: str, name: str = "tiny.txt") -> Path:
    """A hand-written table in the source's own column order, for the malformed-input cases."""
    header = (
        "#Chr\tStart\tEnd\tRef\tAlt\tPVID\tPubMindDB_pathogenicity_sum\t"
        "PubMindDB_paper_level_pathogenicity_score\tPubMindDB_confidence"
    )
    path = tmp_path / name
    path.write_text(f"{header}\n{body}", encoding="utf-8")
    return path


def test_a_row_with_no_pvid_is_dropped_rather_than_carried_with_a_null(tmp_path: Path) -> None:
    """The PVID is PubMind's record id, and this snapshot is organised around record identity.

    The bug this pins is two-headed. A null `pvid` sorts against a real one in the emit key — and two
    records at one coordinate is this snapshot's *headline* property, so the tuple comparison really is
    reached — which crashed the whole build with a `TypeError`. And a null id would silently merge
    distinct records under `identical_duplicate`, since that collapse compares whole rows.
    """
    path = _tiny(
        tmp_path,
        "1\t100\t100\tA\tG\t\tPathogenic\t0.9\t2\n"
        "1\t100\t100\tA\tG\tPV1\tBenign\t0.1\t1\n",
    )
    result = build_snapshot(path, tmp_path / "out")
    assert result.dropped["no_pvid"] == 1
    frame = pl.read_parquet(result.parquet_file)
    assert frame["pvid"].to_list() == ["PV1"]
    assert frame["pvid"].null_count() == 0
    assert result.input_rows == result.record_count + sum(result.dropped.values())


def test_a_truncated_line_is_dropped_and_counted_rather_than_silently_kept(tmp_path: Path) -> None:
    """A short row used to be *kept*, asserting `not_provided` where the source said nothing at all.

    `csv.DictReader` fills missing trailing fields with `None` unless told otherwise, so five of nine
    columns produced a record whose significance folded to "PubMind states no classification" at a
    coordinate PubMind never mentioned — and no drop reason counted it, against a module whose stated
    discipline is that every dropped row is counted.
    """
    result = build_snapshot(_tiny(tmp_path, "1\t100\t100\tA\tG\n"), tmp_path / "out")
    assert result.record_count == 0
    assert result.dropped["no_pvid"] == 1
    assert result.input_rows == 1 == sum(result.dropped.values())


def test_a_position_that_is_not_a_number_is_dropped_rather_than_killing_the_build(
    tmp_path: Path,
) -> None:
    """`Start` was the one cell parsed with a bare `int()`, so a blank raised mid-stream.

    Raising after an arbitrary amount of work is the worst of both: no snapshot, and no count of what
    was wrong with the input.
    """
    result = build_snapshot(
        _tiny(
            tmp_path,
            "1\t\t100\tA\tG\tPV1\tPathogenic\t0.9\t2\n"
            "1\tnot-a-number\t100\tA\tG\tPV2\tBenign\t0.1\t1\n"
            "1\t300\t300\tA\tG\tPV3\tBenign\t0.1\t1\n",
        ),
        tmp_path / "out",
    )
    assert result.dropped["unparsable_position"] == 2
    assert result.record_count == 1
    assert result.input_rows == result.record_count + sum(result.dropped.values())


def test_a_non_finite_or_non_integral_number_is_withheld_rather_than_accepted(
    tmp_path: Path,
) -> None:
    """`float()` accepts `NaN` and `inf`, and `NaN` is a routine cell in a bioinformatics TSV.

    Both would have slipped past the counter as parsed values and then poisoned every comparison
    downstream — and `int(float("nan"))` raises outright. `2.7` is the quieter half of the same
    defect: truncating it to `2` records a definite evidence count the source never stated.
    """
    result = build_snapshot(
        _tiny(
            tmp_path,
            "1\t100\t100\tA\tG\tPV1\tPathogenic\tNaN\t2\n"
            "1\t200\t200\tA\tG\tPV2\tBenign\tinf\t1\n"
            "1\t300\t300\tA\tG\tPV3\tBenign\t0.5\tNaN\n"
            "1\t400\t400\tA\tG\tPV4\tBenign\t0.5\t2.7\n",
        ),
        tmp_path / "out",
    )
    frame = pl.read_parquet(result.parquet_file)
    assert result.record_count == 4, "a bad cell withholds a value, it does not drop the row"
    assert result.unparsable_score == 2                     # NaN and inf
    assert result.unparsable_confidence == 2                # NaN and 2.7
    assert frame["pathogenicity_score"].null_count() == 2
    assert frame["confidence"].to_list() == [2, 1, None, None]


def test_a_download_failure_arrives_as_this_tier_s_own_type(tmp_path: Path, monkeypatch) -> None:
    """A moved bulk URL must not surface as `httpx`'s type: the pass owes its own.

    `PubMindUnavailable` is a **subclass** of `PubMindBuildError`, so one `except` arm on the parent
    catches both an outage and a malformed table while a caller who needs to tell them apart can.
    """
    import httpx

    def _refuse(*_args, **_kwargs):
        raise httpx.ConnectError("name or service not known")

    monkeypatch.setattr(httpx, "stream", _refuse)
    with pytest.raises(PubMindUnavailable) as caught:
        download_pubmind_table(tmp_path / "table.txt.gz")
    assert issubclass(PubMindUnavailable, PubMindBuildError)
    assert "--table" in str(caught.value), "the message has to name the way round it"
    assert DEFAULT_PUBMIND_URL in str(caught.value)
    assert not (tmp_path / "table.txt.gz").exists(), "no half-written file survives the failure"


def test_a_local_table_records_no_source_url_it_did_not_establish(tmp_path: Path) -> None:
    """`release.json` exists to pin which bytes a snapshot holds; a guessed URL is not that.

    Defaulting `source_url` to the ANNOVAR address wrote it into the provenance of a snapshot built
    from a file on disk, beside the `null` ETag and `null` Last-Modified that correctly said the build
    established nothing about where the bytes came from.
    """
    build_snapshot(_SLICE, tmp_path / "local")
    assert json.loads((tmp_path / "local" / "release.json").read_text())["source_url"] is None

    build_snapshot(_SLICE, tmp_path / "fetched", source_url=DEFAULT_PUBMIND_URL)
    assert (
        json.loads((tmp_path / "fetched" / "release.json").read_text())["source_url"]
        == DEFAULT_PUBMIND_URL
    )


def test_an_unreadable_numeric_cell_is_withheld_rather_than_guessed_and_is_counted(
    tmp_path: Path,
) -> None:
    """"The source did not say" and "the source said something we cannot hold" are different.

    A blank score is an absence; `NA` is a value the numeric column cannot express. Both end as
    `null`, and only the second is counted — otherwise the two become one number.
    """
    header = (
        "#Chr\tStart\tEnd\tRef\tAlt\tPVID\tPubMindDB_pathogenicity_sum\t"
        "PubMindDB_paper_level_pathogenicity_score\tPubMindDB_confidence"
    )
    body = (
        "1\t100\t100\tA\tG\tPVID1\tPathogenic\tNA\t2\n"
        "1\t200\t200\tA\tG\tPVID2\tBenign\t\t1\n"
        "1\t300\t300\tA\tG\tPVID3\tBenign\t0.25\tNA\n"
    )
    path = tmp_path / "tiny.txt"
    path.write_text(f"{header}\n{body}", encoding="utf-8")
    result = build_snapshot(path, tmp_path / "out")
    frame = pl.read_parquet(result.parquet_file)
    assert result.unparsable_score == 1
    assert result.unparsable_confidence == 1
    assert frame["pathogenicity_score"].null_count() == 2   # one absent, one unreadable
    assert frame["confidence"].null_count() == 1
    release = json.loads((tmp_path / "out" / "release.json").read_text())
    assert release["unparsable_score"] == 1
    assert release["unparsable_confidence"] == 1


def test_an_off_target_contig_is_dropped_and_counted(tmp_path: Path) -> None:
    """The counter reads zero on today's file; run the case that makes it non-zero."""
    header = (
        "#Chr\tStart\tEnd\tRef\tAlt\tPVID\tPubMindDB_pathogenicity_sum\t"
        "PubMindDB_paper_level_pathogenicity_score\tPubMindDB_confidence"
    )
    body = (
        "GL000009.2\t100\t100\tA\tG\tPVID1\tPathogenic\t1.0\t2\n"
        "chrM\t200\t200\tA\tG\tPVID2\tBenign\t0.0\t1\n"
    )
    path = tmp_path / "scaffold.txt"
    path.write_text(f"{header}\n{body}", encoding="utf-8")
    result = build_snapshot(path, tmp_path / "out")
    assert result.dropped["off_target_chrom"] == 1
    frame = pl.read_parquet(result.parquet_file)
    assert frame["chrom"].to_list() == ["MT"]     # `chrM` is normalized, not discarded
    assert result.input_rows == result.record_count + sum(result.dropped.values())
