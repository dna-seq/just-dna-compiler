"""MITOMAP's dump reader, its `status` grammar and the snapshot built from it — RM171.

The corpus these tests are written against is the real one (602 `mmutation` rows and 494
`rtmutation` rows in a 63 MB gzipped `pg_dump`), and none of it is here: the fixture is a synthetic
dump carrying one COPY block per table, with the row shapes the real file actually contains —
including the two the adoption turns on, a `[VUS*]` bracket and a right-anchored `:` deletion. It
lives in `conftest.py` because the derived miss lane's tests build from the same parent.

**Nothing below asserts a number read off the real dump.** "16" is a fact about one join against one
ClinVar vintage, not a fact about MITOMAP, and the same goes for every other count: the tests assert
relationships (a withheld bracket produces no `clin_sig`; the release counts equal the rows the
fixture contains; a rebuild from the same bytes is byte-identical), which is what stays true when
either side moves.
"""

import json
from pathlib import Path

import pytest
from just_dna_enricher.clin_sig import normalize_clin_sig
from just_dna_enricher.licensing import (
    MITOMAP_TERMS,
    TERMS_BY_SOURCE,
    check_declared_use,
)
from just_dna_enricher.mitomap import (
    ALLELE_DEFECTS,
    MITOMAP_CONFIRMATION_TOKENS,
    MITOMAP_VCEP_CLASSES,
    MitomapError,
    allele_defect,
    allele_key,
    indefinite_length,
    nlmid_pmid,
    parse_status,
    read_dump_tables,
    single_gene,
    vcep_clin_sig,
    withheld_bracket,
)
from just_dna_enricher.mitomap_build import (
    CITATIONS_PARQUET,
    REFERENCES_PARQUET,
    VARIANT_PARQUET,
    build_snapshot,
    dataset_label,
)

pl = pytest.importorskip("polars")


# ── the status grammar ──────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "confirmation", "bracket"),
    [
        ("Reported", "Reported", None),
        ("Cfrm [LP]", "Cfrm", "LP"),
        ("Conflicting reports", "Conflicting reports", None),
        ("Unclear", "Unclear", None),
        ("Cfrm [VUS*]", "Cfrm", "VUS*"),
        ("Reported [VUS-]", "Reported", "VUS-"),
        ("Reported [VUS] -population dependent; hg M9 marker", "Reported", "VUS"),
        # No confirmation token at all: the cell opens with MITOMAP's alignment caveat.
        ("alt loc to 9480del15 [LP]", None, "LP"),
    ],
)
def test_the_two_token_grammar_splits_into_its_two_positions(raw, confirmation, bracket) -> None:
    parsed = parse_status(raw)
    assert parsed.confirmation == confirmation
    assert parsed.bracket == bracket
    assert parsed.raw == raw


def test_a_prose_qualifier_is_kept_rather_than_dropped() -> None:
    """The residue is where the two informative groups live — a genotype claim and an identity one."""
    combo = parse_status("Reported: individually neutral variants causing LHON in combination")
    assert combo.confirmation == "Reported"
    assert combo.bracket is None
    assert "in combination" in (combo.qualifier or "")

    alignment = parse_status("Cfrm [LP], alt locus at 9487del15")
    assert alignment.bracket == "LP"
    assert "9487del15" in (alignment.qualifier or "")


@pytest.mark.parametrize("token", MITOMAP_CONFIRMATION_TOKENS)
def test_a_confirmation_token_never_produces_a_clin_sig(token) -> None:
    """MITOMAP states in as many words that this token is not an assignment of pathogenicity.

    Walked over the constant rather than listed, so a fifth token arriving in the source has to be
    argued for here instead of quietly acquiring a mapping.
    """
    assert vcep_clin_sig(parse_status(token)) is None
    assert vcep_clin_sig(parse_status(f"{token} [")) is None


@pytest.mark.parametrize("bracket", sorted(MITOMAP_VCEP_CLASSES))
def test_a_documented_class_is_the_normalizers_image_of_the_bracket(bracket) -> None:
    """The assertion the strategy's §8 asks for, over the whole vocabulary rather than an example."""
    assert vcep_clin_sig(parse_status(f"Cfrm [{bracket}]")) == normalize_clin_sig(bracket)
    assert withheld_bracket(parse_status(f"Cfrm [{bracket}]")) is None


@pytest.mark.parametrize("bracket", ["VUS*", "VUS+", "VUS-", "VUS◊", "P?"])
def test_an_undocumented_bracket_is_withheld_and_counted_never_mapped(bracket) -> None:
    """`[VUS*]` is the motivating member; the others are the same refusal generalized.

    The second assertion is the load-bearing one and is easy to lose: the shared normalizer's own
    default is `other`, a *definite* member of `VALID_CLIN_SIG`, so leaving the withholding to it
    would turn an undocumented token into a confident call rather than an unknown.
    """
    status = parse_status(f"Cfrm [{bracket}]")
    assert vcep_clin_sig(status) is None
    assert withheld_bracket(status) == bracket
    assert normalize_clin_sig(bracket) == "other", "which is exactly why the guard is upstream"


def test_the_shared_normalizer_answers_the_same_for_both_sides_raw_tokens() -> None:
    """One normalizer, three spellings — ClinVar's, PubMind's and MITOMAP's (`@one-normalizer-two-spellings`).

    Both sides' raw tokens, as the rule asks: the abbreviation MITOMAP publishes and the underscored
    wording ClinVar publishes have to reach the same member, or the concordance between two adopted
    sources would report our own two maps disagreeing.
    """
    pairs = {
        "P": "Pathogenic", "LP": "Likely_pathogenic", "VUS": "Uncertain_significance",
        "LB": "Likely_benign", "B": "Benign",
    }
    assert set(pairs) == MITOMAP_VCEP_CLASSES
    for abbreviation, clinvar_wording in pairs.items():
        assert normalize_clin_sig(abbreviation) == normalize_clin_sig(clinvar_wording)


# ── alleles, genes and citations ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("ref", "alt", "reason"),
    [
        ("G", "A", None),
        ("A", "AA", None),                       # an insertion, right-anchored the way VCF spells one
        ("TA", ":", "right_anchored_deletion"),  # needs an rCRS base at position-1; P2 forbids the fetch
        ("24bp_deletion", None, "non_nucleotide"),
        ("A", "A", "ref_equals_alt"),
    ],
)
def test_an_allele_that_cannot_be_spelled_as_vcf_says_which_kind_it_is(ref, alt, reason) -> None:
    assert allele_defect(ref, alt) == reason
    assert reason is None or reason in ALLELE_DEFECTS


def test_the_join_key_exists_exactly_where_the_alleles_do() -> None:
    """One predicate behind both, so the miss set and the unmintable count cannot disagree."""
    assert allele_key("3460", "g", "a") == (3460, "G", "A")
    assert allele_key("7402", "C", ":") is None
    assert allele_key(None, "C", "T") is None


def test_only_a_bare_digit_run_is_read_as_a_pmid() -> None:
    """The whole `nlmid` column was walked, which the strategy note left owed on a sample of four."""
    assert nlmid_pmid("3201231") == "3201231"
    assert nlmid_pmid("  2263545 ") == "2263545"
    assert nlmid_pmid("01930224-202601000-00006") is None, "an Ovid id, not a PMID"
    assert nlmid_pmid("") is None
    assert nlmid_pmid(None) is None


def test_an_allele_name_stating_a_variable_number_of_copies_is_flagged_not_repaired() -> None:
    """MITOMAP's two encodings of one record disagree about definiteness, on exactly one row.

    `T961delT+ / -C(n)ins` describes a deletion plus a variable-length insertion; the allele *columns*
    on the same record flatten it to `T`→`CC`. Neither repair is available — dropping the row discards
    a published call, and rewriting it needs a rule for what `(n)` means that MITOMAP has not given —
    so the predicate exists to let a caller say so (`@multiplicity-is-a-finding`).
    """
    assert indefinite_length("T961delT+ / -C(n)ins") is True
    assert indefinite_length("961_962ins(n)") is True
    assert indefinite_length("m.3460G>A") is False, "a plain substitution is not a family"
    assert indefinite_length("m.5367_5385del") is False
    assert indefinite_length(None) is False


def test_a_locus_that_is_not_one_gene_withholds_rather_than_picking() -> None:
    assert single_gene("MT-ND1") == "MT-ND1"
    assert single_gene("MT-ATP8/6") is None, "two overlapping genes"
    assert single_gene("MT-CR") is None, "the control region is a locus, not a gene"
    assert single_gene("MT-TS1 precursor") is None, "a transcript stage, not the gene alone"


# ── the dump reader ─────────────────────────────────────────────────────────────────────────────


def test_the_reader_keeps_the_tables_asked_for_and_nothing_else(
    mitomap_dump: Path, mitomap_corpus
) -> None:
    tables = read_dump_tables(mitomap_dump)
    assert set(tables) == {
        "mmutation", "rtmutation", "mmutation_reference", "rtmutation_reference",
        "reference", "edit_date",
    }
    assert len(tables["mmutation"]) == len(mitomap_corpus.mmutation)
    assert tables["mmutation"][0]["locus"] == "MT-ND1"
    assert tables["mmutation"][1]["cfrm_date"] is None, "the COPY null marker is a None, not '\\\\N'"


def test_a_table_the_dump_does_not_publish_is_absent_rather_than_empty(
    tmp_path: Path, mitomap_corpus
) -> None:
    """Absent and empty are different facts, and the builder refuses on the second."""
    short = mitomap_corpus.write(tmp_path / "short.sql.gz", mitomap_corpus.without("rtmutation"))
    tables = read_dump_tables(short)
    assert "rtmutation" not in tables
    assert tables["mmutation"], "and the tables that are there still parsed"


def test_a_dump_missing_a_table_is_refused_rather_than_built_short(
    tmp_path: Path, mitomap_corpus
) -> None:
    short = mitomap_corpus.write(tmp_path / "short.sql.gz", mitomap_corpus.without("rtmutation"))
    with pytest.raises(MitomapError, match="rtmutation"):
        build_snapshot(short, tmp_path / "out")


# ── the snapshot ────────────────────────────────────────────────────────────────────────────────


def test_the_snapshot_holds_one_parquet_per_table_and_counts_what_it_read(
    mitomap_dump: Path, tmp_path: Path, mitomap_corpus
) -> None:
    """Every published number is the frame's own, re-derived here rather than copied from the build."""
    result = build_snapshot(
        mitomap_dump, tmp_path / "out", source_last_modified="Mon, 24 Aug 2026 05:01:10 GMT"
    )
    data = tmp_path / "out" / "data"
    assert {p.name for p in data.glob("*.parquet")} == {
        *VARIANT_PARQUET.values(), CITATIONS_PARQUET, REFERENCES_PARQUET,
    }
    for table, name in VARIANT_PARQUET.items():
        frame = pl.read_parquet(data / name)
        assert frame.height == result.rows[table]
        assert set(frame["table"].to_list()) == {table}

    release = json.loads((tmp_path / "out" / "release.json").read_text())
    assert release["rows"] == result.rows
    assert release["dataset"] == "mitomap_2026-08-21+2026-08-19"
    # The dump's own in-band statement of when each table was curated — a different fact from the
    # file's Last-Modified, so both are recorded rather than one standing in for the other.
    assert release["table_edit_dates"] == {"mmutation": "2026-08-21", "rtmutation": "2026-08-19"}

    references = pl.read_parquet(data / REFERENCES_PARQUET)
    assert references.height == release["reference_rows"] == len(mitomap_corpus.references)
    with_pmid = references.filter(pl.col("pmid").is_not_null()).height
    assert with_pmid == release["references_with_pmid"]
    assert (
        release["references_with_pmid"]
        + release["references_without_nlmid"]
        + release["references_not_a_pmid"]
    ) == references.height, "every reference row lands in exactly one of the three"


def test_a_citation_through_a_reference_with_no_pmid_is_dropped_not_invented(
    mitomap_dump: Path, tmp_path: Path, mitomap_corpus
) -> None:
    """Two of the fixture's links point at references this tier cannot express as a `StudyRow`.

    Asserted as a relationship against the link table rather than as a count: every citation row's
    reference carries a PMID, and every link whose reference does not is absent.
    """
    build_snapshot(mitomap_dump, tmp_path / "out")
    citations = pl.read_parquet(tmp_path / "out" / "data" / CITATIONS_PARQUET)
    references = pl.read_parquet(tmp_path / "out" / "data" / REFERENCES_PARQUET)
    usable = set(references.filter(pl.col("pmid").is_not_null())["reference_id"].to_list())
    assert set(citations["reference_id"].to_list()) <= usable
    linked = set(mitomap_corpus.mmutation_links)
    kept = {record for record, reference in linked if reference in usable}
    lost = {record for record, reference in linked if reference not in usable} - kept
    assert lost, "the fixture has to exercise the drop for this assertion to mean anything"
    written = set(citations.filter(pl.col("table") == "mmutation")["record_id"].to_list())
    assert written == kept
    assert not (written & lost), "a record whose only reference has no PMID gets no study row"


def test_the_snapshot_records_the_withheld_brackets_and_the_unmintable_alleles(
    mitomap_dump: Path, tmp_path: Path
) -> None:
    """Both are computed by the build, so both are published rather than recomputed by every reader."""
    build_snapshot(mitomap_dump, tmp_path / "out")
    release = json.loads((tmp_path / "out" / "release.json").read_text())
    frames = [
        pl.read_parquet(tmp_path / "out" / "data" / name) for name in VARIANT_PARQUET.values()
    ]
    withheld = pl.concat(frames).filter(pl.col("withheld_bracket").is_not_null())
    assert release["withheld_brackets"] == dict(
        sorted(withheld["withheld_bracket"].value_counts().iter_rows())
    )
    assert withheld.filter(pl.col("clin_sig").is_not_null()).is_empty(), (
        "a withheld bracket may never carry a clin_sig"
    )
    unmintable = pl.concat(frames).filter(pl.col("allele_defect").is_not_null())
    assert release["unmintable"] == dict(
        sorted(unmintable["allele_defect"].value_counts().iter_rows())
    )


def test_a_rebuild_from_the_same_bytes_is_byte_identical(
    mitomap_dump: Path, tmp_path: Path
) -> None:
    """Principle 7. `release.json`'s `built_at` is the only per-run-varying byte and lives outside."""
    first = build_snapshot(mitomap_dump, tmp_path / "a")
    second = build_snapshot(mitomap_dump, tmp_path / "b")
    for one, two in zip(sorted(first.parquet_files), sorted(second.parquet_files), strict=True):
        assert one.name == two.name
        assert one.read_bytes() == two.read_bytes(), one.name


def test_the_label_comes_from_inside_the_dump_so_a_local_build_is_comparable(
    mitomap_dump: Path, tmp_path: Path
) -> None:
    """The ClinVar precedent: `##fileDate` over `Last-Modified`, content over transfer.

    A downloaded build and a build from the same bytes on disk have to produce the same label, or the
    off-switch quietly produces a snapshot nothing can compare against.
    """
    downloaded = build_snapshot(
        mitomap_dump, tmp_path / "a", source_last_modified="Mon, 24 Aug 2026 05:01:10 GMT"
    )
    local = build_snapshot(mitomap_dump, tmp_path / "b")
    assert downloaded.dataset == local.dataset == "mitomap_2026-08-21+2026-08-19"
    # And the header is still recorded, because provenance of the fetch is a real second question.
    assert json.loads((tmp_path / "a" / "release.json").read_text())["source_last_modified"]
    assert json.loads((tmp_path / "b" / "release.json").read_text())["source_last_modified"] is None


def test_a_label_naming_only_one_of_the_two_tables_is_withheld() -> None:
    """Half a label is not a shorter label — it is one that cannot be compared."""
    assert dataset_label({"mmutation": "2026-08-21", "rtmutation": "2026-08-19"}) == (
        "mitomap_2026-08-21+2026-08-19"
    )
    assert dataset_label({"mmutation": "2026-08-21", "rtmutation": None}) is None
    assert dataset_label({}) is None


# ── the terms ───────────────────────────────────────────────────────────────────────────────────


def test_the_terms_are_the_live_read_and_the_gate_never_fires() -> None:
    """CC BY 3.0 with commercial and clinical use *stated*, so no declaration is refused.

    `commercial_use is True` rather than `None` is the half the 2026-09-03 browser read added: r4 left
    it to be inferred from the CC grant, r5 says it in words. An unestablished permission would be a
    `None` here, and the two are never the same answer.
    """
    assert TERMS_BY_SOURCE[MITOMAP_TERMS.source] is MITOMAP_TERMS
    assert MITOMAP_TERMS.license == "CC-BY-3.0"
    assert (MITOMAP_TERMS.commercial_use, MITOMAP_TERMS.redistribution) == (True, True)
    assert MITOMAP_TERMS.share_alike is False
    for declared in ("unstated", "non-commercial", "commercial"):
        assert check_declared_use(MITOMAP_TERMS, declared) is None


def test_the_licence_row_is_written_as_a_floor() -> None:
    """"Unless otherwise noted" is the floor-plus-per-record-override shape.

    Pinned on the notice text because that is where a reader of a published module meets it, and
    because the first repair anyone proposes is to read the site default as "every cell is CC BY 3.0"
    (`@a-hosts-terms-are-not-its-contents-terms`).
    """
    assert "FLOOR" in (MITOMAP_TERMS.notice or "")
    assert "unless otherwise noted" in (MITOMAP_TERMS.notice or "")
    assert "25489354" in (MITOMAP_TERMS.attribution or ""), "Lott et al. 2013, the second form"
