"""Shared fixtures for the enricher suite.

**One autouse fixture, and it exists for the failure mode that only shows up on a machine that has
done real work.** `lookup_variant` consults the PubMind snapshot since RM134 § D, and a caller that
passes no `pubmind_cache` falls through to `$JUST_DNA_PUBMIND_CACHE` and then to the default cache
directory. Every existing lookup test passes an explicit `ensembl_cache`/`clinvar_cache` and no
PubMind one, so on a developer's machine — where a snapshot exists precisely because somebody built
it while designing this — the hint would gain `pubmind` advisories that CI never sees, and
`test_the_live_locus_is_labelled_live_and_not_as_a_snapshot` asserts an *exact set* of advisory
sources. Passing alone and failing in the one place that matters is the shape `@test-no-credential`
names.

So the variable is pointed at a directory that does not exist, which is the ladder's own way of
saying "no snapshot": `_resolve_parquet_cache` takes the explicit value over the default directory,
and a path that is not a directory resolves to `None`. Set rather than deleted, for the same reason
that rule gives — a `delenv` leaves the *default* directory still in play, which is the other half of
the ladder and the half that actually holds a built snapshot. A test that wants a snapshot passes one
explicitly and is unaffected.
"""

import gzip
from dataclasses import dataclass
from pathlib import Path

import pytest
from just_dna_enricher import clinvar_build
from just_dna_enricher.mitomap_build import build_snapshot as build_mitomap_snapshot
from just_dna_enricher.mitomap_miss_build import build_miss_snapshot


@pytest.fixture(autouse=True)
def _no_ambient_pubmind_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    absent = Path(tmp_path_factory.getbasetemp()) / "no-pubmind-snapshot"
    monkeypatch.setenv("JUST_DNA_PUBMIND_CACHE", str(absent))


# ── the MITOMAP corpus (RM171) ──────────────────────────────────────────────────────────────────
#
# Here rather than in `test_mitomap.py` because two modules read it — the reader/builder tests and the
# derived miss lane's — and pytest test modules are not importable from one another. A corpus copied
# into a second file is a corpus that drifts, which is exactly the failure the miss lane exists to
# report about its own parents.

# ── the fixture ─────────────────────────────────────────────────────────────────────────────────
#
# Row shapes lifted from the real dump, one per case the code has to distinguish. The two variant
# tables carry the same grammar and different fourth columns (`aa` against `rna`), which is why the
# snapshot keeps both rather than folding them.

MMUTATION = [
    # id locus dz allele position refna regna aa cons contr homo hetero status cfrm_date
    "1\tMT-ND1\tLHON\tm.3460G>A\t3460\tG\tA\tA52T\t.\t0\t+\t+\tCfrm [P]\t2010.01.01",
    "2\tMT-ND5\tMELAS\tm.13513G>A\t13513\tG\tA\tD393N\t.\t0\t-\t+\tCfrm [LP]\t\\N",
    "3\tMT-ATP6\tNARP\tm.8993T>G\t8993\tT\tG\tL156R\t.\t0\t+\t+\tCfrm [VUS*]\t\\N",
    "4\tMT-CR\tBD-associated\tm.114C>T\t114\tC\tT\tnoncoding\t.\t.\t+\t-\tReported\t\\N",
    "5\tMT-ATP8/6\tunspecified\tm.8527A>G\t8527\tA\tG\tM1V\t.\t.\tnr\tnr\tReported [VUS]\t\\N",
    "6\tMT-CO1\tdeafness\tm.7402del\t7402\tC\t:\tnoncoding\t.\t.\t-\t+\tReported\t\\N",
    "7\tMT-CYB\tEXIT\tm.15150G>A\t15150\tG\tA\tW135*\t.\t0\t-\t+\tConflicting reports\t\\N",
    "8\tMT-ND2\tLHON modifier\tm.4917A>G\t4917\tA\tG\tN150D\t.\t.\t+\t-\tReported [LB]\t\\N",
]
RTMUTATION = [
    # id locus dz allele position refna regna rna cons contr homo hetero status cfrm_date
    "16\tMT-TL1\tMELAS\tA3243G\t3243\tA\tG\ttRNA Leu\t.\t0\t-\t+\tCfrm [P]\t2020.07.29",
    "17\tMT-TL1\tMELAS\tT3271C\t3271\tT\tC\ttRNA Leu\t.\t0\t-\t+\tCfrm [LP]\t\\N",
    "18\tMT-TF\tclinical lab\tT578C\t578\tT\tC\ttRNA Phe\t91.11%\t0\tnr\t+\tReported [VUS-]\t\\N",
    "19\tMT-RNR1\tdeafness\tA1555G\t1555\tA\tG\t12S rRNA\t.\t0\t+\t+\tUnclear\t\\N",
    "20\tMT-TS1 precursor\thearing loss\tT7511C\t7511\tT\tC\ttRNA Ser\t.\t0\tnr\t+\tReported [B] in hg K,U\t\\N",
]
MMUTATION_REFERENCE = ["1\t100", "1\t101", "2\t100", "3\t102", "6\t103"]
RTMUTATION_REFERENCE = ["16\t100", "17\t101", "19\t102"]
REFERENCE = [
    # id authors title publication editors volume number pages date city publisher keywords abstract nlmid
    "100\tWallace, D.C.\tMitochondrial DNA mutation\tScience\t.\t242\t4884\t1427-1430\t1988\t.\t.\t.\t.\t3201231",
    "101\tGoto, Y.\tA mutation in tRNA(Leu)\tNature\t.\t348\t6302\t651-653\t1990\t.\t.\t.\t.\t2263545",
    # The one shape the whole-column walk turned up that is not a PMID: an Ovid article id whose
    # first eight characters are digits, which a substring search would happily cite as a paper.
    "102\tSomebody, A.\tAn Ovid-hosted review\tSome Journal\t.\t1\t1\t1-2\t2026\t.\t.\t.\t.\t01930224-202601000-00006",
    # And the other: no `nlmid` at all, 397 of them in the real file.
    "103\tNobody, B.\tAn uncited note\tA Newsletter\t.\t1\t1\t1-2\t1999\t.\t.\t.\t.\t\\N",
]
EDIT_DATE = [
    "45097\tmMut\t2026-08-21",
    "45098\trtMut\t2026-08-19",
    "45091\tref\t2026-08-20",
]

BLOCKS = [
    ('COPY mitomap.mmutation (id, locus, dz, allele, "position", refna, regna, aa, cons, contr, '
     "homo, hetero, status, cfrm_date) FROM stdin;", MMUTATION),
    ('COPY mitomap.rtmutation (id, locus, dz, allele, "position", refna, regna, rna, cons, contr, '
     "homo, hetero, status, cfrm_date) FROM stdin;", RTMUTATION),
    ("COPY mitomap.mmutation_reference (mmutation_id, reference_id) FROM stdin;", MMUTATION_REFERENCE),
    ("COPY mitomap.rtmutation_reference (rtmutation_id, reference_id) FROM stdin;", RTMUTATION_REFERENCE),
    ("COPY mitomap.reference (id, authors, title, publication, editors, volume, number, pages, "
     "date, city, publisher, keywords, abstract, nlmid) FROM stdin;", REFERENCE),
    ("COPY mitomap.edit_date (id, table_name, date) FROM stdin;", EDIT_DATE),
]


def write_mitomap_dump(path: Path, blocks=BLOCKS) -> Path:
    """A gzipped `pg_dump` fragment in the shape the real one has, plus a table nothing reads."""
    lines = [
        "--", "-- PostgreSQL database dump", "--", "SET statement_timeout = 0;", "",
        "COPY mitomap.code (id, codon, aa) FROM stdin;", "1\tTTT\tPhe", "\\.", "",
    ]
    for header, rows in blocks:
        lines.extend([header, *rows, "\\.", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


@dataclass(frozen=True)
class MitomapCorpus:
    """The synthetic dump, and the row lists a test asserts against.

    Handed out as one object rather than as loose module constants, because the two test modules that
    need it are not importable from each other and a corpus copied into a second file is a corpus
    that drifts — which is the failure the miss lane exists to report about its own parents.
    """

    def write(self, path: Path, blocks=None) -> Path:
        return write_mitomap_dump(path, BLOCKS if blocks is None else blocks)

    def without(self, table: str) -> list:
        """The blocks with one table's COPY removed — the dump-is-short-a-table case."""
        return [b for b in BLOCKS if not b[0].startswith(f"COPY mitomap.{table} ")]

    @property
    def mmutation(self) -> list[str]:
        return list(MMUTATION)

    @property
    def references(self) -> list[str]:
        return list(REFERENCE)

    @property
    def mmutation_links(self) -> list[tuple[str, ...]]:
        return [tuple(row.split("\t")) for row in MMUTATION_REFERENCE]


@pytest.fixture
def mitomap_corpus() -> MitomapCorpus:
    return MitomapCorpus()


@pytest.fixture
def mitomap_dump(tmp_path: Path, mitomap_corpus: MitomapCorpus) -> Path:
    """A gzipped MITOMAP `pg_dump` fragment — the parent every MITOMAP test builds from."""
    return mitomap_corpus.write(tmp_path / "mitomap.dump.sql.gz")


# ── the parents the MITOMAP-miss lane joins (RM171) ─────────────────────────────────────────────
#
# A five-record chrMT ClinVar snapshot, cut through `clinvar_build`'s own VCF path rather than
# hand-written as a parquet, so the join runs against the file the real builder produces. The rows are
# chosen against the corpus above to exercise all four buckets and the one trap: 8993 T>C is a
# *different allele at the same position* as MITOMAP's 8993 T>G, so a position-level join would report
# a photocopy where the exact one correctly reports a miss.

CLINVAR_MT_VCF = """##fileformat=VCFv4.1
##fileDate=2026-06-27
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
MT\t3460\t9999\tG\tA\t.\t.\tALLELEID=1;CLNSIG=Pathogenic;CLNREVSTAT=reviewed_by_expert_panel;GENEINFO=MT-ND1:4535
MT\t114\t9998\tC\tT\t.\t.\tALLELEID=2;CLNSIG=Benign;CLNREVSTAT=criteria_provided,_single_submitter
MT\t8993\t9997\tT\tC\t.\t.\tALLELEID=3;CLNSIG=Uncertain_significance;CLNREVSTAT=criteria_provided,_single_submitter
MT\t3243\t9996\tA\tG\t.\t.\tALLELEID=4;CLNSIG=Pathogenic;CLNREVSTAT=reviewed_by_expert_panel
MT\t1555\t9995\tA\tG\t.\t.\tALLELEID=5;CLNSIG=Pathogenic;CLNREVSTAT=reviewed_by_expert_panel
"""


@pytest.fixture
def clinvar_mt_vcf() -> str:
    """The default chrMT VCF text, so a test can build a *newer* ClinVar out of it.

    A fixture rather than an import: a pytest `conftest` is not an importable module, and a second
    copy of the text in the test that needs to modify it is the drift this file exists to avoid.
    """
    return CLINVAR_MT_VCF


@pytest.fixture
def build_clinvar_mt(tmp_path: Path):
    """A factory: `build_clinvar_mt()` writes `<tmp>/clinvar`, `build_clinvar_mt(other)` rebuilds it.

    A factory rather than a plain fixture because one test needs the *same directory* rebuilt from a
    newer file — which is precisely the case the child's parent pin exists to catch.
    """
    def build(vcf_text: str = CLINVAR_MT_VCF) -> Path:
        vcf = tmp_path / "clinvar.vcf.gz"
        with gzip.open(vcf, "wt", encoding="utf-8") as handle:
            handle.write(vcf_text)
        clinvar_build.build_snapshot(vcf, tmp_path / "clinvar")
        return tmp_path / "clinvar"

    return build


@pytest.fixture
def mitomap_snapshot(tmp_path: Path, mitomap_dump: Path) -> Path:
    """A built MITOMAP snapshot — the first parent."""
    build_mitomap_snapshot(
        mitomap_dump, tmp_path / "mitomap", source_last_modified="Mon, 24 Aug 2026 05:01:10 GMT"
    )
    return tmp_path / "mitomap"


@pytest.fixture
def mitomap_miss_snapshot(tmp_path: Path, mitomap_snapshot: Path, build_clinvar_mt) -> Path:
    """The derived increment, built from both parents through the real join."""
    build_miss_snapshot(mitomap_snapshot, build_clinvar_mt(), tmp_path / "miss")
    return tmp_path / "miss"

