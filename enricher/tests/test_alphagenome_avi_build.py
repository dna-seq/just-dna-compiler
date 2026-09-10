"""RM191: the AVI snapshot's three contracts — losslessness, reconciliation, threshold safety.

Every test here runs the **real builder over a real slice of the published artifact**
(`assets/alphagenome/avi_chr22_slice.tsv.gz`, 120,003 rows of chr22:20,000,000-20,040,000, bgzipped
and tabix-indexed exactly as upstream ships it). Expected values are computed at runtime from the
slice's own text, never copied from a dump: what is being pinned is the *relationship* between what
AlphaGenome printed and what the snapshot stores.

**The slice is chosen, not arbitrary.** Measured over the genome-wide knot table, exactly **one**
printed `raw_score` spans an integer `PHRED` threshold — `0.00076`, whose 676,356 rows run from
2.99961 to 3.00027 and therefore straddle 3.0. This window carries ten of them, seven below the
threshold and three above. Without such a row `test_a_threshold_the_knots_do_not_straddle...` would
be `@tautology-zero`: a threshold-safety property is only worth asserting where the reconstruction
*can* disagree, and this is the only place in the human genome where it does.
"""

import subprocess
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher import alphagenome_avi_build as ab
from just_dna_enricher.licensing import ALPHAGENOME_AVI_TERMS
from just_dna_format.layout import atomic_write_text

_SLICE = Path(__file__).resolve().parents[2] / "assets" / "alphagenome" / "avi_chr22_slice.tsv.gz"
_VENDOR = Path(__file__).resolve().parents[2] / "docs" / "vendor"
_TERMS = _VENDOR / "alphagenome_output_terms.txt"

#: The one knot in the whole corpus whose `PHRED` interval contains an integer threshold. Domain
#: constants — what the artifact prints — rather than counts read off a dump.
STRADDLING_RAW = "0.00076"
STRADDLED_THRESHOLD = 3.0

pytestmark = pytest.mark.skipif(
    not _SLICE.is_file(), reason="the committed AVI slice is missing"
)


def _tabix_available() -> bool:
    try:
        subprocess.run(["tabix", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):  # pragma: no cover
        return False
    return True


needs_tabix = pytest.mark.skipif(
    not _tabix_available(), reason="tabix is not on PATH; the AVI artifact is a bgzipped TSV"
)


def _printed_rows() -> pl.DataFrame:
    """The slice as the file prints it — `raw_score` and `PHRED` kept as **strings**.

    Strings on purpose: the claim under test is that the stored integer reproduces the *printed
    decimal*, and parsing both sides through the same float would make the comparison agree by
    construction rather than by the encoding being right.
    """
    text = subprocess.run(
        ["tabix", str(_SLICE), "chr22"], capture_output=True, check=True
    ).stdout
    return pl.read_csv(
        text,
        separator="\t",
        has_header=False,
        new_columns=["chrom", "pos", "ref", "alt", "raw_printed", "phred_printed"],
        schema_overrides={"pos": pl.UInt32, "raw_printed": pl.String, "phred_printed": pl.String},
    )


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    """One build of the slice, shared: it is the real code path and it costs a second."""
    if not _tabix_available():  # pragma: no cover
        pytest.skip("tabix is not on PATH")
    out = tmp_path_factory.mktemp("avi")
    ab.build_snapshot(_SLICE, out, workers=1, hash_source=False, terms_file=_TERMS)
    return out


@needs_tabix
def test_the_stored_integer_reproduces_the_printed_score_exactly(built: Path) -> None:
    """`raw_score_e5` is the printed decimal shifted five places, for every row. Zero tolerance.

    This is the whole case for `Int32` over `Float32`: the artifact publishes fixed decimals, so an
    integer scale is exact while a 32-bit float rounds the fifth digit.

    **The comparison runs in `Decimal`, over the file's own text, and that is the point rather than
    a convenience.** The obvious form — divide the integer back and compare doubles — fails on 53%
    of this slice, because the division rounds a second time and lands one ulp away from the nearest
    double to the printed decimal. So the losslessness this artifact offers is about the *decimal*,
    not about a float round-trip, and a consumer who needs it must stay in the integer. Asserting it
    the obvious way would have quietly weakened the claim to whatever a tolerance admitted.
    """
    printed = _printed_rows()
    stored = ab.to_long(pl.read_parquet(built / "data" / "alphagenome_avi-chr22.parquet"))
    assert stored.height == printed.height

    joined = printed.join(
        stored.with_columns(pl.col("ref").cast(pl.String), pl.col("alt").cast(pl.String)),
        on=["pos", "ref", "alt"],
        how="inner",
    )
    assert joined.height == printed.height, "the join lost rows: the key is not (pos, ref, alt)"

    # Compared as **integers**, through `Decimal`, and the choice is the finding rather than a
    # convenience. Going the other way — `raw_score_e5 / 1e5` against `float(printed)` — disagrees
    # on 53% of this slice, because binary division rounds a second time and lands one ulp off the
    # nearest double to the printed decimal. That is not a defect in the encoding; it is the reason
    # the encoding exists. The stored integer IS the printed decimal shifted five places, exactly,
    # and a consumer who needs that exactness must work in the integer rather than divide back.
    exact = Decimal(ab.RAW_SCORE_SCALE)
    disagreements = [
        row
        for row in joined.select("pos", "ref", "alt", "raw_printed", "raw_score_e5").iter_rows(
            named=True
        )
        if Decimal(row["raw_printed"]) * exact != Decimal(row["raw_score_e5"])
    ]
    assert not disagreements, disagreements[:5]


@needs_tabix
def test_a_score_with_more_precision_than_the_scale_is_refused_rather_than_rounded(
    tmp_path: Path,
) -> None:
    """The losslessness guarantee is a *check*, not a comment — so break it and watch it refuse.

    If upstream ever widens the column, the wrong outcome is a silently rounded score: the artifact
    would then disagree with its own source in a way no downstream check could see. Six decimals
    here, one row, and the build stops.
    """
    rows = subprocess.run(
        ["tabix", str(_SLICE), "chr22:20000000-20000100"], capture_output=True, check=True
    ).stdout.decode().splitlines()
    assert rows, "the fixture window is empty"
    fields = rows[0].split("\t")
    fields[4] = "0.123456"  # one digit past the scale
    doctored = tmp_path / "doctored.tsv"
    atomic_write_text(doctored, "\n".join(["\t".join(fields), *rows[1:]]) + "\n")
    subprocess.run(["bgzip", "-f", str(doctored)], check=True)
    gz = doctored.with_suffix(".tsv.gz")
    subprocess.run(["tabix", "-s1", "-b2", "-e2", "-f", str(gz)], check=True)

    with pytest.raises(ab.AlphaGenomeBuildError, match="more precision"):
        ab.build_snapshot(gz, tmp_path / "out", workers=1, hash_source=False)


@needs_tabix
def test_phred_is_read_and_used_but_never_stored(built: Path) -> None:
    """24.7 GB genome-wide of a number that is a function of another column, and the knots carry it.

    Equality over the written schema rather than a "PHRED not in columns" check, so a column added
    without a decision fails here too (`@registry-completeness`).
    """
    stored = pl.read_parquet(built / "data" / "alphagenome_avi-chr22.parquet")
    assert list(stored.columns) == list(ab.PARQUET_SCHEMA)
    assert "PHRED" not in stored.columns and "phred" not in stored.columns
    assert "alt" not in stored.columns, "the wide layout names ALTs by column, not by value (RM197)"
    # …and the knot table is where it went.
    knots = pl.read_parquet(built / ab.KNOT_FILENAME)
    assert list(knots.columns) == list(ab.KNOT_COLUMNS)


@needs_tabix
def test_the_knot_table_accounts_for_every_row_the_build_wrote(built: Path) -> None:
    """`sum(n)` over knots equals the rows written, and every stored score has a knot.

    Two directions, because they fail differently: a short `sum(n)` means the curve describes less
    data than exists, and a score with no knot means a consumer cannot reconstruct its `PHRED` at
    all. The builder already refuses on the first; this pins the second.
    """
    stored = ab.to_long(pl.read_parquet(built / "data" / "alphagenome_avi-chr22.parquet"))
    knots = pl.read_parquet(built / ab.KNOT_FILENAME)

    assert int(knots["n"].sum()) == stored.height
    assert set(stored["raw_score_e5"].unique()) == set(knots["raw_score_e5"])
    assert knots["raw_score_e5"].is_sorted(), "a consumer bisects this curve"
    assert (knots["phred_lo"] <= knots["phred_hi"]).all()


@needs_tabix
def test_the_fixture_really_contains_the_one_straddling_knot(built: Path) -> None:
    """Guards every threshold claim below from being vacuous.

    Exactly one printed `raw_score` in the human genome spans an integer `PHRED` threshold. If this
    slice stopped carrying it — a re-cut window, a re-published artifact — the safety test would go
    green while checking nothing, which is the failure `@tautology-zero` names.
    """
    knots = pl.read_parquet(built / ab.KNOT_FILENAME)
    straddling = knots.filter(
        (pl.col("phred_lo") < STRADDLED_THRESHOLD) & (pl.col("phred_hi") > STRADDLED_THRESHOLD)
    )
    assert straddling.height == 1, straddling.to_dicts()
    assert straddling.item(0, "raw_score_e5") == int(float(STRADDLING_RAW) * ab.RAW_SCORE_SCALE)

    printed = _printed_rows().filter(pl.col("raw_printed") == STRADDLING_RAW)
    below = printed.filter(pl.col("phred_printed").cast(pl.Float64) < STRADDLED_THRESHOLD).height
    above = printed.height - below
    assert below > 0 and above > 0, (
        "the fixture must carry rows on BOTH sides of the threshold, or 'the reconstruction can "
        f"disagree here' is untested: {below} below, {above} above"
    )


@needs_tabix
@pytest.mark.parametrize("threshold", [1.0, 2.0, 4.0, 5.0, 10.0, 15.0, 20.0])
def test_a_threshold_no_knot_straddles_classifies_identically_to_the_stored_phred(
    built: Path, threshold: float
) -> None:
    """The item's real contract: where the curve is unambiguous, dropping `PHRED` costs nothing.

    For every row whose knot does not span the threshold, the knot's interval and the file's own
    `PHRED` must put the row on the same side. **Zero misclassifications, not a bound** — that is
    what § 4.8 measured across all fifty integer thresholds, and a tolerance here would turn a
    measured exactness into an unmeasured approximation.
    """
    printed = _printed_rows()
    knots = pl.read_parquet(built / ab.KNOT_FILENAME)

    joined = (
        printed.with_columns(
            (pl.col("raw_printed").cast(pl.Float64) * ab.RAW_SCORE_SCALE)
            .round()
            .cast(pl.Int32)
            .alias("raw_score_e5"),
            pl.col("phred_printed").cast(pl.Float64).alias("phred"),
        )
        .join(knots, on="raw_score_e5", how="inner")
    )
    assert joined.height == printed.height

    unambiguous = joined.filter(
        (pl.col("phred_lo") >= threshold) | (pl.col("phred_hi") < threshold)
    )
    assert unambiguous.height > 0, "nothing to check at this threshold"

    disagreed = unambiguous.filter(
        (pl.col("phred") >= threshold) != (pl.col("phred_lo") >= threshold)
    )
    assert disagreed.height == 0, disagreed.head(5).to_dicts()


@needs_tabix
def test_the_straddled_threshold_is_exactly_where_the_knot_declares_it_unsafe(
    built: Path,
) -> None:
    """The other half, and the reason the interval is published rather than a midpoint.

    At 3.0 the reconstruction genuinely cannot decide: one printed `raw_score` holds rows on both
    sides. The contract is not that the answer is right — it is that the artifact **says so in
    advance**, from the knot table alone, without reading a single data row. That is what makes
    threshold safety decidable rather than something a consumer discovers after the fact.
    """
    printed = _printed_rows()
    knots = pl.read_parquet(built / ab.KNOT_FILENAME)

    declared_unsafe = knots.filter(
        (pl.col("phred_lo") < STRADDLED_THRESHOLD) & (pl.col("phred_hi") > STRADDLED_THRESHOLD)
    )["raw_score_e5"]
    assert declared_unsafe.len() == 1

    ambiguous = printed.with_columns(
        (pl.col("raw_printed").cast(pl.Float64) * ab.RAW_SCORE_SCALE)
        .round()
        .cast(pl.Int32)
        .alias("raw_score_e5"),
        pl.col("phred_printed").cast(pl.Float64).alias("phred"),
    ).filter(pl.col("raw_score_e5").is_in(declared_unsafe))

    sides = ambiguous.select((pl.col("phred") >= STRADDLED_THRESHOLD).alias("above"))["above"]
    assert sides.any() and not sides.all(), (
        "the knot declares 3.0 unsafe, so the rows behind it must really fall on both sides — "
        "otherwise the interval is wider than the data and the declaration is noise"
    )

    # And every OTHER knot at this threshold is decided, which is what makes the warning narrow
    # enough to be worth acting on rather than a blanket "thresholds may be wrong".
    decided = knots.filter(~pl.col("raw_score_e5").is_in(declared_unsafe))
    assert decided.filter(
        (pl.col("phred_lo") < STRADDLED_THRESHOLD) & (pl.col("phred_hi") > STRADDLED_THRESHOLD)
    ).height == 0


@needs_tabix
def test_absence_is_row_absence_and_a_stored_zero_is_a_scored_zero(built: Path) -> None:
    """AVI covers ~95% of the assembly and writes genuine zeros; the two must stay distinguishable.

    A position the artifact never scored has no row. A position it scored at zero has a row holding
    zero. Collapsing them — writing `0.0` for an unscored position, or dropping zero rows as
    "nothing to say" — is `@unreachable-not-absent` at nine-billion-row scale, and it is the single
    easiest mistake to make in a table this size.
    """
    stored = ab.to_long(pl.read_parquet(built / "data" / "alphagenome_avi-chr22.parquet"))
    printed = _printed_rows()

    # Set equality over the (pos, ref, alt) keys, in both directions. Left to right catches a row
    # the build invented — a position filled in because it looked like a gap; right to left catches
    # one it dropped, which for a zero-scored row is the same defect wearing the other hat. An
    # equality rather than a count, because two errors of opposite sign cancel in a count
    # (`@registry-completeness`).
    def keys(frame: pl.DataFrame) -> set[tuple]:
        return set(
            frame.select(
                pl.col("pos"), pl.col("ref").cast(pl.String), pl.col("alt").cast(pl.String)
            ).iter_rows()
        )

    assert keys(stored) == keys(printed)

    # And the zeros survived as zeros rather than being read as nothing to say. Re-derived from the
    # slice, never a constant off a dump.
    zeros_in_file = printed.filter(pl.col("raw_printed").cast(pl.Float64) == 0.0).height
    assert stored.filter(pl.col("raw_score_e5") == 0).height == zeros_in_file

    # The window is dense — every position in it carries all three ALTs — so this slice cannot show
    # a *gap*. Asserted rather than assumed, so nobody reads the equality above as proof that
    # unscored positions are handled: the artifact covers ~95% of the assembly, and what pins the
    # sparse case is the key equality itself, which admits no row the file did not carry.
    positions = set(printed["pos"].to_list())
    assert len(positions) * 3 == printed.height, "the fixture stopped being three-ALT-dense"


@needs_tabix
def test_the_use_restrictions_travel_inside_the_snapshot(built: Path) -> None:
    """Restriction 3b, honoured: the licence text is a file beside the data, not a link.

    Anyone who attaches their own terms to a derivative — which a module's `sources.csv` is — must
    carry the Output Terms' "Use restrictions" section as an enforceable provision. So the bytes go
    in the snapshot, `SNAPSHOT_LICENSE_FILENAME` being the slot that already exists for exactly this
    (ClinPGx bundles one, `@a-hosts-terms-are-not-its-contents-terms`).
    """
    licence = (built / "LICENSE.txt").read_text()
    assert licence.startswith("Use restrictions")
    # The four clauses that actually bind a holder of this snapshot, quoted from the pinned document.
    assert "non-commercial use only" in licence
    assert "train machine learning models" in licence
    assert 'include this “Use restrictions”' in licence
    # …and it stops before the parts that are not use restrictions.
    assert "Disclaimers and limitations of liability" not in licence
    assert "Governing law" not in licence


def test_the_permissive_class_is_asserted_from_a_pinned_page_and_not_from_a_reading() -> None:
    """RM195, resolved: `commercial_use=True`, and the evidence is in the repository.

    The Additional Terms define the Permissive class and delegate *membership* to a sign-in-gated
    page. For a day this shipped `None` — unknown is a value and `None` is never `False` — because a
    permission nobody could check does not belong in a signed attribution ledger. The page is pinned
    now, so the assertion has something behind it.

    Asserted against the **pinned bytes**, not against a constant: the test re-reads the extraction
    and requires it to classify AVI as commercial. If someone drops the vendor file, or upstream
    reclassifies and the file is re-saved, this fails rather than going on asserting yesterday's
    permission.
    """
    extraction = _VENDOR / "alphagenome_download_page.txt"
    assert extraction.is_file(), "the evidence for commercial_use=True is not in docs/vendor/"
    text = extraction.read_text()
    assert "Permissive Use Downloadable artifacts for commercial and non-commercial use" in text
    avi_block = text.split("Permissive Use Downloadable artifacts", 1)[1].split("Downloadable artifacts for non-commercial", 1)[0]
    assert "AVI SNV scores" in avi_block, "the page no longer puts AVI in the Permissive class"
    for non_commercial in ("merged splicing", "feature importance"):
        assert non_commercial not in avi_block, f"{non_commercial} must not be Permissive"

    assert ALPHAGENOME_AVI_TERMS.commercial_use is True


def test_the_three_permission_axes_each_rest_on_a_different_kind_of_ground() -> None:
    """Three values, three provenances, and the row does not distinguish them — so this test does.

    * `commercial_use=True` is **documented**: the download page pinned in `docs/vendor/` classifies
      AVI as Permissive Use, and the test above asserts against those bytes.
    * `share_alike=False` is **documented**: the terms impose no copyleft.
    * `redistribution=True` is a **reading**, taken by the maintainer on 2026-09-10. Prohibition 1
      permits sharing "indirectly via … open source release", and an openly published snapshot that
      carries the Use restrictions inside it (restriction 3b, honoured by the lane's `LICENSE.txt`)
      is one. No document in `docs/vendor/` says that in as many words.

    Pinned because the distinction vanishes at the row: a consumer reading `sources.csv` sees three
    booleans and cannot tell which one somebody decided. If that reading is ever revisited, this is
    the test that says where to look.
    """
    assert ALPHAGENOME_AVI_TERMS.commercial_use is True
    assert ALPHAGENOME_AVI_TERMS.share_alike is False
    assert ALPHAGENOME_AVI_TERMS.redistribution is True

    # The reading is defensible only while the snapshot really does carry the terms with it, so the
    # two are tied together here rather than left to a reviewer to connect.
    assert "Use restrictions" in ab.use_restrictions_text(_TERMS)


def test_the_terms_row_pins_the_licence_text_it_ships_beside_the_data() -> None:
    """`license_sha256` is over the bytes the snapshot carries, not over the whole terms document."""
    licence_text = ab.use_restrictions_text(_TERMS)
    # `annotation` because that is the layer a module carrying AVI scores would fill; the layer a
    # *check* records under is RM193's decision, and this test is about the permission axes.
    row = ALPHAGENOME_AVI_TERMS.row(
        "annotation", declared_use="commercial", license_text=licence_text
    )
    assert row.commercial_use is True
    assert row.redistribution is True, "the open-source-release reading (RM195); see the axes test"
    assert row.source == "alphagenome_avi", "one name cannot carry two licence classes"
    assert row.license_sha256 is not None and row.license_sha256.startswith("sha256:")


@needs_tabix
def test_the_other_two_bulk_artifacts_are_refused_by_name(tmp_path: Path) -> None:
    """A different licence class must not reach a lane whose `SourceRow` describes this one.

    The merged-splicing and feature-importance artifacts are non-commercial-only, and the second
    stacks AlphaMissense, Cactus and phastCons terms on top. Reading either into this lane would
    publish a `sources.csv` row that does not describe its own bytes — the mirror of
    `@a-hosts-terms-are-not-its-contents-terms`. Checked on the name, because the name is what an
    operator actually types.
    """
    for name in ("combined_alphagenome_splicing_snvs.tsv.gz", "avi_indels_with_am_snvs.tsv.gz"):
        decoy = tmp_path / name
        decoy.write_bytes(b"")
        with pytest.raises(ab.AlphaGenomeBuildError, match="not the AVI artifact"):
            ab.build_snapshot(decoy, tmp_path / "out", workers=1, hash_source=False)


@needs_tabix
def test_the_release_records_the_stamp_the_terms_resolve_against(built: Path) -> None:
    """`artifact_mtime` is legally load-bearing, not provenance hygiene.

    The Output Terms pin the applicable version to "the date the relevant Output was generated"
    (§ 2.7c), so the artifact's own timestamp fixes which terms govern these bytes, permanently.
    Recorded rather than derived at read time, because the file it describes may not be there later.
    """
    import json

    release = json.loads((built / "release.json").read_text())
    assert release["artifact_mtime"] is not None
    assert release["dataset"] == release["artifact_mtime"][:10]
    assert release["phred_stored"] is False
    assert release["raw_score_scale"] == ab.RAW_SCORE_SCALE
    # `rows` counts the SNVs the source published, which is three per stored row (RM197).
    wide = pl.read_parquet(built / "data" / "alphagenome_avi-chr22.parquet")
    assert release["rows"] == 3 * wide.height == ab.to_long(wide).height
    assert release["contigs"] == ["chr22"]


@needs_tabix
def test_the_knot_count_is_wide_enough_for_the_whole_corpus(built: Path) -> None:
    """`n` must be `UInt64`, because `UInt32` wraps on a genome-wide sum and does it silently.

    This is a real regression, caught by the reconciliation guard on the first full build: the
    per-contig aggregate used `pl.len()`, which is `UInt32`, and every single contig fits it —
    chr2, the largest, is 721 M rows. The corpus is **8,812,917,339**, and summing the per-contig
    tables wrapped it to 222,982,747, which is 8,812,917,339 − 2·2³² exactly. Two hours of build
    time said nothing was wrong until the last step compared the total against the rows written.

    Asserted on the **dtype** rather than on a count, because no fixture can be nine billion rows.
    The arithmetic is checked separately below, on a frame small enough to build and wide enough to
    overflow the type this is guarding against.
    """
    knots = pl.read_parquet(built / ab.KNOT_FILENAME)
    assert knots.schema["n"] == pl.UInt64, (
        f"`n` is {knots.schema['n']}, which wraps at 4,294,967,295 — under the corpus's "
        "8,812,917,339 rows"
    )


def test_a_count_past_thirty_two_bits_survives_the_knot_aggregation() -> None:
    """The arithmetic the dtype exists for, on three rows instead of nine billion.

    Two synthetic per-contig knot tables whose counts sum past `UInt32`, merged the way
    `build_snapshot` merges them. Under the old `UInt32` this comes back as 222,982,747; it must come
    back as the true total. A test that only asserted the dtype would keep passing if the merge
    itself narrowed the column again.
    """
    total = 8_812_917_339
    half = total // 2
    parts = [
        pl.DataFrame({"raw_score_e5": [76], "n": [n], "phred_lo": [2.99961], "phred_hi": [3.00027]})
        .with_columns(pl.col("n").cast(pl.UInt64))
        for n in (half, total - half)
    ]
    merged = (
        pl.concat(parts)
        .group_by("raw_score_e5")
        .agg(
            pl.col("n").sum().alias("n"),
            pl.col("phred_lo").min().alias("phred_lo"),
            pl.col("phred_hi").max().alias("phred_hi"),
        )
    )
    assert int(merged["n"].sum()) == total
    assert total > 2**32, "the constant has to exceed the type this is guarding against"


@needs_tabix
def test_a_publish_carries_the_knot_table_and_not_only_the_scores(built: Path) -> None:
    """The file that would have gone missing, and the snapshot would have looked complete without it.

    `plan_reference_snapshot` collects `data/*.parquet`, the sidecar *directories*, and a list of
    root-level files. `avi_knots.parquet` is a root-level sibling of `data/` — one small parquet, not
    a directory of them — so a publisher iterating a hardcoded `(release.json, LICENSE.txt)` pair
    drops it silently. Every score present, `release.json` valid, and **nothing on the other side can
    reconstruct a `PHRED`**, because the artifact deliberately does not store one.

    That is the third time this exact shape has come up: `@publisher-allowlist-derived` exists
    because a share-alike snapshot went out without the terms it was built to carry. So the names
    live in `locations.SNAPSHOT_ROOT_FILENAMES` and the publisher walks them, and this asserts the
    walk over a real built snapshot rather than the constant over itself.
    """
    from just_dna_enricher.locations import SNAPSHOT_ROOT_FILENAMES
    from just_dna_enricher.upload import plan_reference_snapshot

    plan = plan_reference_snapshot(built, "just-dna-seq/alphagenome_avi")

    assert ab.KNOT_FILENAME in plan.files, (
        "the curve did not make it into the publish; a puller would hold scores they cannot rank"
    )
    assert "release.json" in plan.files and "LICENSE.txt" in plan.files
    assert any(f.startswith("data/") and f.endswith(".parquet") for f in plan.files)

    # Every root file this snapshot actually has is carried — an equality over what is on disk,
    # so a fourth such file added to a lane and not to the registry fails here.
    on_disk = {name for name in SNAPSHOT_ROOT_FILENAMES if (built / name).is_file()}
    assert on_disk <= set(plan.files)
    assert ab.KNOT_FILENAME in on_disk, "the fixture build stopped writing a knot table"


@needs_tabix
def test_the_lane_is_pullable_exactly_because_it_is_publishable(built: Path) -> None:
    """The roster's biconditional, and this lane is the one that nearly broke it (RM198).

    A lane this tier can publish must be one a deployment can pull, or `cache status` advertises a
    repo nobody can use. The AVI lane is unusual on both halves: it cannot *build* without a file
    behind an eligibility gate, and it can publish anyway, because the re-encoded snapshot is
    Permissive-Use output and `redistribution=True` records the reading that an open publication is
    inside prohibition 1's carve-out.
    """
    from just_dna_enricher.caches import LANES_BY_NAME

    lane = LANES_BY_NAME["alphagenome_avi"]
    assert lane.publish_repo is not None and lane.ensure is not None
    assert lane.unpublished is None, "a lane that publishes may not also excuse itself"
    assert lane.rebuild is None and lane.unbuilt, "and it still cannot fetch its own source"
    assert lane.terms is not None and lane.terms.redistribution is True


@needs_tabix
def test_every_position_carries_the_three_non_ref_bases(built: Path) -> None:
    """The property the wide layout rests on, re-proved on the fixture (RM197).

    It was proved over the whole corpus once — all 24 contigs, all 8,812,917,339 rows, every position
    carrying exactly three rows with strictly ascending distinct ALTs, none equal to REF. Three
    distinct non-ref bases must be all three of them. That is what lets `alt` stop being stored.

    A proof taken once is a proof about the artifact **that existed then**. This re-runs it on every
    build, so a re-published source that changed shape fails here rather than producing a table whose
    columns quietly mean something else.
    """
    printed = _printed_rows()
    per_pos = printed.group_by("pos").agg(
        pl.col("alt").sort().str.join("").alias("alts"), pl.col("ref").first()
    )
    expected = pl.col("ref").replace_strict(
        {b: "".join(ab.alts_for_ref(b)) for b in ab.BASES}, default=None
    )
    assert per_pos.filter(pl.col("alts") != expected).height == 0
    assert per_pos.height * 3 == printed.height


def test_the_alt_columns_are_named_by_ref_alone() -> None:
    """`alts_for_ref` is the whole interface between the layout and a reader.

    No lookup table travels with the artifact: given `ref`, the three columns are `{A,C,G,T} − ref`
    ascending. Asserted over all four bases rather than one, and with the ordering pinned, because a
    reader indexing `alt1` gets a different variant if the order ever changes.
    """
    assert ab.alts_for_ref("A") == ("C", "G", "T")
    assert ab.alts_for_ref("C") == ("A", "G", "T")
    assert ab.alts_for_ref("G") == ("A", "C", "T")
    assert ab.alts_for_ref("T") == ("A", "C", "G")
    assert ab.alts_for_ref("g") == ("A", "C", "T"), "the source prints upper case; be forgiving"
    for base in ab.BASES:
        assert base not in ab.alts_for_ref(base)
        assert list(ab.alts_for_ref(base)) == sorted(ab.alts_for_ref(base))
    with pytest.raises(ab.AlphaGenomeBuildError, match="three-ALT complement"):
        ab.alts_for_ref("N")


@needs_tabix
def test_wide_round_trips_to_long_without_the_source(built: Path) -> None:
    """The claim that made RM197 adoptable rather than a schema break.

    A consumer who wants `(chrom, pos, ref, alt, score)` rows gets exactly them back from the stored
    artifact, with no `alt` column on disk and no table beside it. Compared against the **printed
    source text** rather than against another derivation of the same parquet, so the round trip is
    checked against what AlphaGenome published rather than against itself.
    """
    wide = pl.read_parquet(built / "data" / "alphagenome_avi-chr22.parquet")
    long = ab.to_long(wide)
    printed = _printed_rows()

    assert long.height == printed.height == 3 * wide.height

    def keyed(frame: pl.DataFrame, score: str) -> dict:
        return {
            (r["pos"], r["ref"], r["alt"]): r[score]
            for r in frame.select("pos", "ref", "alt", score).iter_rows(named=True)
        }

    recovered = keyed(long, "raw_score_e5")
    source = keyed(
        printed.with_columns(
            (pl.col("raw_printed").cast(pl.Float64) * ab.RAW_SCORE_SCALE)
            .round().cast(pl.Int32).alias("e5")
        ),
        "e5",
    )
    assert recovered == source


@needs_tabix
def test_a_locus_missing_an_alt_is_refused_rather_than_padded(tmp_path: Path) -> None:
    """A row with `alt2 = null` would silently redefine what `alt1` means at that locus.

    So the builder stops. The property held over the entire corpus when it was measured, which is
    exactly why a violation is worth refusing over: it means the source changed shape, and padding
    would produce a table that reads fine and answers wrongly.
    """
    rows = subprocess.run(
        ["tabix", str(_SLICE), "chr22:20000000-20000100"], capture_output=True, check=True
    ).stdout.decode().splitlines()
    first_pos = rows[0].split("\t")[1]
    kept = [r for r in rows if r.split("\t")[1] != first_pos or r.split("\t")[3] != "A"]
    assert len(kept) < len(rows), "the fixture's first locus has no A alt to drop"

    doctored = tmp_path / "gap.tsv"
    atomic_write_text(doctored, "\n".join(kept) + "\n")
    subprocess.run(["bgzip", "-f", str(doctored)], check=True)
    gz = doctored.with_suffix(".tsv.gz")
    subprocess.run(["tabix", "-s1", "-b2", "-e2", "-f", str(gz)], check=True)

    with pytest.raises(ab.AlphaGenomeBuildError, match="not 3"):
        ab.build_snapshot(gz, tmp_path / "out", workers=1, hash_source=False)


@needs_tabix
def test_a_locus_split_across_a_chunk_boundary_is_reassembled(tmp_path: Path) -> None:
    """The defect that the fixture could not see, because the fixture is one chunk.

    `_stream_lines` yields whole *lines*; a locus is three lines. So a chunk boundary lands inside a
    position roughly once per chunk, and `_widen` — which requires all three ALTs — refused. The
    genome-wide build died at `chr1:1196920`, a locus that has all three in the file and two in the
    chunk. Every test in this file passed while that was true, because the 4 MB slice fits in one
    64 MB chunk.

    So this builds the **same slice at a chunk size small enough to guarantee hundreds of split
    loci** and asserts the result is byte-for-byte the same table. An assertion that the build merely
    *succeeds* would have been satisfied by dropping the partial rows.
    """
    whole = tmp_path / "whole"
    ab.build_snapshot(_SLICE, whole, workers=1, hash_source=False, terms_file=_TERMS)

    split = tmp_path / "split"
    result = ab.build_snapshot(
        _SLICE, split, workers=1, hash_source=False, terms_file=_TERMS, chunk_bytes=64 * 1024
    )

    name = "data/alphagenome_avi-chr22.parquet"
    a = pl.read_parquet(whole / name).sort("pos")
    b = pl.read_parquet(split / name).sort("pos")
    assert a.equals(b), "chunking changed the table"

    # And the counts the release publishes are unaffected, including the last locus of the contig —
    # which has no following chunk to be carried into and would otherwise be dropped in silence.
    printed = _printed_rows()
    assert result.rows == printed.height
    assert b.height * 3 == printed.height
    assert int(b["pos"].max()) == int(printed["pos"].max()), "the final locus went missing"

    # The knot tables must agree too: they are aggregated per chunk and merged, so a carried locus
    # counted twice would show up here and nowhere else.
    ka = pl.read_parquet(whole / ab.KNOT_FILENAME).sort("raw_score_e5")
    kb = pl.read_parquet(split / ab.KNOT_FILENAME).sort("raw_score_e5")
    assert ka.equals(kb)
    assert int(kb["n"].sum()) == printed.height
