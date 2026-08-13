"""Contig geometry per build — the offline half of the wrong-build diagnosis (RM48).

Two constant tables and three tri-state readers, and every test below is really about the same thing:
what may be *concluded* from a coordinate, and what must be withheld. A wrong-build diagnosis that
fires on a correct row is worse than no diagnosis at all, because it becomes a false accusation about
data the author got right — so the withholding cases are as load-bearing as the firing ones and get
as many tests.

The tables carry no refget accessions on purpose. An accession is what a content-addressed identity
is a function of; a length and a name answer only "could this coordinate exist", which is a question
about a claim. Adding a second build's *identity* is RM15, and `refget_accession` still raises.
"""

import json
import os
import urllib.request

import pytest
from just_dna_format.spec import VariantRow
from just_dna_format.vrs import (
    CONTIGS_ONLY_IN,
    PRIMARY_CONTIG_LENGTHS,
    REFGET_GRCh38,
    REFGET_GRCh38_LENGTHS,
    UnsupportedBuildError,
    builds_containing_position,
    contig_length,
    refget_accession,
    sole_build_naming_contig,
)

# The two builds the tables describe. Named here rather than derived from the dict so a table that
# quietly loses a build fails a test instead of making every check below vacuous.
_BUILDS = ("GRCh37", "GRCh38")


def test_both_builds_describe_the_same_25_primary_contigs() -> None:
    """Equal key sets, which is what makes a cross-build comparison meaningful at all.

    `builds_containing_position` compares one build's contig against another's *of the same name*. If
    one table gained or lost a contig the comparison would silently answer about different sequences,
    and the "this position fits GRCh37" clause would be about a contig GRCh38 does not have.
    """
    assert set(PRIMARY_CONTIG_LENGTHS) == set(_BUILDS)
    keys = {build: set(lengths) for build, lengths in PRIMARY_CONTIG_LENGTHS.items()}
    assert keys["GRCh37"] == keys["GRCh38"]
    assert keys["GRCh38"] == set(REFGET_GRCh38)


def test_the_only_primary_contig_of_equal_length_is_MT() -> None:
    """MT is the rCRS in both builds; every other primary contig moved between them.

    This is why a length check discriminates the two builds at all — and why an MT coordinate never
    does, which the compiler's message has to get right rather than offering GRCh37 as an explanation
    it cannot support.
    """
    same = {
        contig
        for contig in PRIMARY_CONTIG_LENGTHS["GRCh38"]
        if PRIMARY_CONTIG_LENGTHS["GRCh38"][contig] == PRIMARY_CONTIG_LENGTHS["GRCh37"][contig]
    }
    assert same == {"MT"}


def test_the_two_exclusive_contig_sets_are_disjoint_and_carry_no_primary_contig() -> None:
    """"Only in build X" must mean it — a name in both sets, or a primary name in either, is a bug."""
    assert not CONTIGS_ONLY_IN["GRCh37"] & CONTIGS_ONLY_IN["GRCh38"]
    primary = set(PRIMARY_CONTIG_LENGTHS["GRCh38"])
    for build in _BUILDS:
        assert not CONTIGS_ONLY_IN[build] & primary


class TestContigLength:
    def test_a_primary_contig_answers_per_build(self) -> None:
        assert contig_length("1", "GRCh38") == REFGET_GRCh38_LENGTHS["1"]
        assert contig_length("1", "GRCh37") > contig_length("1", "GRCh38")

    def test_it_normalizes_the_contig_the_way_every_other_reader_does(self) -> None:
        assert contig_length("chr1", "GRCh38") == contig_length("1", "GRCh38")
        assert contig_length("chrM", "GRCh38") == contig_length("MT", "GRCh38")

    @pytest.mark.parametrize(
        ("chrom", "build"),
        [
            (None, "GRCh38"),          # no contig given
            ("1", "T2T-CHM13v2.0"),    # a build with no table
            ("GL000209.1", "GRCh37"),  # a real contig of that build, but not a primary one
            ("KI270728.1", "GRCh38"),
        ],
    )
    def test_it_withholds_rather_than_guessing_a_bound(self, chrom, build) -> None:
        """`None` for every unknown, and a caller may conclude nothing about a position on it."""
        assert contig_length(chrom, build) is None

    def test_it_does_not_raise_where_refget_accession_does(self) -> None:
        """The split is deliberate: an identity may not be guessed, a diagnosis may be withheld."""
        assert contig_length("1", "GRCh37") is not None
        with pytest.raises(UnsupportedBuildError):
            refget_accession("1", "GRCh37")


class TestBuildsContainingPosition:
    def test_a_grch37_tail_position_names_only_grch37(self) -> None:
        """The 294 kb of chromosome 1 that GRCh37 has and GRCh38 does not — the un-lifted case."""
        tail = PRIMARY_CONTIG_LENGTHS["GRCh38"]["1"] + 1000
        assert tail <= PRIMARY_CONTIG_LENGTHS["GRCh37"]["1"]
        assert builds_containing_position("1", tail) == ("GRCh37",)

    def test_an_ordinary_position_is_in_both(self) -> None:
        assert builds_containing_position("6", 26_093_141) == ("GRCh37", "GRCh38")

    def test_a_position_past_every_build_names_none(self) -> None:
        """Distinct from the case above, and the compiler must render the two differently."""
        assert builds_containing_position("MT", 20_000) == ()

    def test_it_says_nothing_about_a_low_position(self) -> None:
        """VCF writes POS 0 for a telomeric variant, so a low position is evidence of nothing."""
        assert builds_containing_position("1", 0) == ("GRCh37", "GRCh38")

    def test_no_coordinate_answers_nothing(self) -> None:
        assert builds_containing_position("1", None) == ()


class TestSoleBuildNamingContig:
    @pytest.mark.parametrize(
        ("chrom", "expected"),
        [
            ("GL000209.1", "GRCh37"),   # an hg19 unplaced scaffold
            ("KI270728.1", "GRCh38"),   # a GRCh38 one
            ("gl000209.1", "GRCh37"),   # a spelling slip is a slip, not a build question
        ],
    )
    def test_an_exclusive_scaffold_names_its_build_in_either_direction(self, chrom, expected) -> None:
        assert sole_build_naming_contig(chrom) == expected

    @pytest.mark.parametrize(
        "chrom",
        [
            "1", "MT", "X",     # spelled identically in both builds, so they settle nothing
            "GL000194.1",       # a scaffold BOTH builds carry
            "GL000205",         # unversioned: `.1` is GRCh37's and `.2` is GRCh38's
            "HSCHR6_MHC_APD_CTG1",  # an alt locus, in no top-level listing at all
            None,
        ],
    )
    def test_it_withholds_wherever_the_name_does_not_decide(self, chrom) -> None:
        assert sole_build_naming_contig(chrom) is None

    def test_the_versioned_pair_really_does_split_between_builds(self) -> None:
        """The version suffix is the discriminator, which is why the bare accession must withhold."""
        assert sole_build_naming_contig("GL000205.1") == "GRCh37"
        assert sole_build_naming_contig("GL000205.2") == "GRCh38"


class TestChromRejectionNamesTheBuild:
    """`VariantRow.chrom` refuses a scaffold either way; what changed is whether it says why.

    Scaffold names do not arrive by typo — they arrive by pasting rows out of a VCF built on the other
    assembly, which means the module's *other* rows are probably on it too. Told only that the value
    is out of the vocabulary, an author deletes the row and ships the rest.
    """

    def _row(self, chrom: str) -> None:
        VariantRow(chrom=chrom, start=1000, genotype="A/A", state="risk", conclusion="x")

    def test_a_grch37_scaffold_says_which_build_names_it(self) -> None:
        with pytest.raises(ValueError, match="top-level sequence of GRCh37") as excinfo:
            self._row("GL000209.1")
        assert "GL000209.1" in str(excinfo.value)

    def test_a_grch38_scaffold_says_the_other_one(self) -> None:
        with pytest.raises(ValueError, match="top-level sequence of GRCh38"):
            self._row("KI270728.1")

    def test_a_shared_scaffold_is_still_refused_and_earns_no_diagnosis(self) -> None:
        """The verdict never changed; a name that decides nothing must claim nothing."""
        with pytest.raises(ValueError, match="chrom must be one of") as excinfo:
            self._row("GL000194.1")
        assert "top-level sequence" not in str(excinfo.value)

    def test_an_ordinary_typo_keeps_the_plain_message(self) -> None:
        with pytest.raises(ValueError, match="chrom must be one of") as excinfo:
            self._row("23")
        assert "top-level sequence" not in str(excinfo.value)


@pytest.mark.integration
def test_the_contig_tables_match_the_two_live_ensembl_services() -> None:
    """Re-derive both length tables and both difference sets from `/info/assembly/homo_sapiens`.

    The roadmap's stated blocker for RM48 was that recovering an rs-number needs a chain file, i.e.
    "the whole snapshot apparatus for one authoring convenience". These are 25 numbers and ~200 names
    per build, taken from a permanent public endpoint and committed — which is what makes the offline
    half of this item possible at all. Checked against the source rather than trusted, for the same
    reason `test_refget_table_matches_the_public_seqrepo` is: a wrong number here would accuse a
    correct row.

    Opt-in: two live requests.
    """
    if not os.getenv("JUST_DNA_NETWORK_TESTS"):
        pytest.skip("reads two live Ensembl services — set JUST_DNA_NETWORK_TESTS=1 to run")

    endpoints = {
        "GRCh38": "https://rest.ensembl.org",
        "GRCh37": "https://grch37.rest.ensembl.org",
    }
    top_level: dict[str, dict[str, int]] = {}
    for build, endpoint in endpoints.items():
        request = urllib.request.Request(
            f"{endpoint}/info/assembly/homo_sapiens",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
        assert payload["assembly_name"].startswith(build), payload["assembly_name"]
        top_level[build] = {r["name"]: r["length"] for r in payload["top_level_region"]}

    for build, regions in top_level.items():
        live_primary = {
            name: length
            for name, length in regions.items()
            if name in PRIMARY_CONTIG_LENGTHS[build]
        }
        assert live_primary == PRIMARY_CONTIG_LENGTHS[build], build
    assert set(top_level["GRCh38"]) - set(top_level["GRCh37"]) == CONTIGS_ONLY_IN["GRCh38"]
    assert set(top_level["GRCh37"]) - set(top_level["GRCh38"]) == CONTIGS_ONLY_IN["GRCh37"]
