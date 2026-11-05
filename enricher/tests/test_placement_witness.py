"""RM267: a placement two loaded authorities give for one rsID is compared, and a disagreement withholds.

S117's case is `rs8176719` (ABO O1): the Ensembl snapshot places it at `9:133257520 G>GC`, dbSNP and
Ensembl REST at `9:133257521 T>TC`. Neither real witness holds it today (ClinVar's 2026-06-27 VCF has no
record there, and ClinVar-GKM lacks it), so the fixture's ClinVar snapshot carries the REST spelling to
exercise the withhold. GRCh38 reads `GGGG T ACC` at 517–524, so the two spellings are two haplotypes, not
one event respelled; they mint two VRS ids. `rs72613567` and `rs77944059` are the respelling class
(RM270): Ensembl anchors each a few bases right of ClinVar's left-aligned spelling, and both spellings
mint one id. An rsID only Ensembl knows has one witness, and is counted rather than read as agreement.

**The reference windows are real GRCh38 bases**, read by hand on 2026-11-04 from Ensembl REST
(`/sequence/region/human/<region>:1?coord_system_version=GRCh38`); chr4's was read from UCSC's
`api.genome.ucsc.edu/getData/sequence?genome=hg38` the same day while Ensembl answered 503, and the two
agreed when Ensembl came back. They are served to the run's own `SequenceProxy` and `VrsMinter` through a
data proxy holding only those bases, so every id below is minted by `ga4gh.vrs` for real, offline. The
first test proves the windows: the two RM270 alleles mint the ids RM270 and ClinVar-GKM recorded.
"""

import gzip
import hashlib
import json
import os
from pathlib import Path

import httpx
import polars as pl
import pytest
from ga4gh.vrs.dataproxy import _DataProxy
from just_dna_compiler.compiler import compile_module, load_csv_rows
from just_dna_enricher.caches import LANES_BY_NAME
from just_dna_enricher.clinvar_gkm import ALLELE_FILE, VARIATION_FILE, WITNESS_PARQUET, parse_manifest
from just_dna_enricher.clinvar_gkm_build import build_snapshot
from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.enrich.orchestration import _filled_pieces
from just_dna_enricher.enrich.releases import table_releases as orchestration_table_releases
from just_dna_enricher.enrich.resolution_csv import _write_resolution_csv
from just_dna_enricher.ensembl import EnsemblResolver
from just_dna_enricher.events import Allele, same_event
from just_dna_enricher.licensing import sources_path
from just_dna_enricher.placement import compare_placements
from just_dna_enricher.sequences import SequenceProxy, normalize_locus, spelling_verdict
from just_dna_enricher.verification import ran
from just_dna_enricher.vrs import VrsMinter
from just_dna_format.integrity import resolution_signature
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.resolution import ResolutionRow
from just_dna_format.snapshot import SnapshotRelease, write_release
from just_dna_format.sources import SourceRow
from just_dna_format.vrs import refget_accession

SLICE = Path(__file__).resolve().parents[2] / "assets" / "clinvar_gkm_slice"
CONSUMER_JOIN = Path(__file__).resolve().parents[2] / "assets" / "consumer_join"

#: `chrom -> (first 1-based position, bases)`; see the module docstring for where each was read.
WINDOWS: dict[str, tuple[int, str]] = {
    "9": (
        133257400,
        "CTGACTTACTTCTTGATGGCAAACACAGTTAACCCAATGGTGGTGTTCTGGAGCCTGAACTGCTCGTTGAGGATGTCGATGTTGAATGTGCC"
        "CTCCCAGACAATGGGAGCCAGCCAAGGGGTACCACGAGGACATCCTTCCTACTGCACATGGAGAGAGGCGTGCGGTCACATGGAGCTGGCAGGG"
        "TGCCACCCACATGCGCCTCTGGCACACGGCCGCCCCCACCTGGAAACTCCACTCA",
    ),
    "4": (
        87310100,
        "GGTTGCAGTGAGCCAAGATCATGCCACTGCAACCACCGCAATCCAGCCAGGGTGACAGAGTGAGACTCTGTCTAAAAAAAAAAAAAGCAAAAA"
        "AAAAAGCTCTATTGGTGTTTTAGTATTTGGGTGTTCTGTGCTGTACTTACTTCTGTAGTCTCAGAAAGATATTGATATACGATGGAACAAAAATC"
        "ATTTTCTTATTGGTAAGTATTCCATCTATCAGACTTCTTACGACTTCATCTGTCTCCAATACAGGCCATAATCTGTGATTAAAAAGAGGAAAA",
    ),
    "2": (
        166204400,
        "AGCTTTTTCATTGCATTATAGTATTTCTTCTGTTCTTCTGTCATAAAGATGTCTTGACCTCCAAGGTAAAGAAACAAACAAAAAATAAATGTAG"
        "TTAAAACCAGAATCATTGTCTACATCTTTCTATAGATTACTAAAATAGGTTAAAATGTGTTAATATA",
    ),
}
_BY_ACCESSION = {f"ga4gh:{refget_accession(chrom)}": window for chrom, window in WINDOWS.items()}

#: The ids RM270's probe and ClinVar-GKM record (domain constants).
HSD17B13_ID = "ga4gh:VA.Jml7SNku3QQBCVIj78BGiFvR21bNkos7"
RS77944059_ID = "ga4gh:VA.ks2GTWYOW0aKfGbJ2aeQUOZxOT_xC2ts"

#: Each rsID as the Ensembl snapshot places it, and as ClinVar's VCF does.
ENSEMBL = {
    "rs8176719": ("9", 133257520, "G", "GC"),
    "rs72613567": ("4", 87310241, "A", "AA"),
    "rs77944059": ("2", 166204477, "ACAAA", "A"),
    "rs4988235": ("2", 135851076, "G", "A"),  # LCT; the fixture's ClinVar does not carry it
}
CLINVAR = {
    "rs8176719": ("9", 133257521, "T", "TC"),
    "rs72613567": ("4", 87310240, "T", "TA"),
    "rs77944059": ("2", 166204470, "GAAAC", "G"),
}
GENOTYPES = {"rs8176719": "T/TC", "rs72613567": "T/TA", "rs77944059": "G/GAAAC", "rs4988235": "A/G"}

_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)


def read(chrom: str, start: int, end: int) -> str | None:
    """1-based inclusive bases from the recorded windows, clipped at the left edge only.

    `_left_align` indexes its read from the right end, so a read clipped on the left is shorter, not
    shifted; a read past a window's right edge is unreadable.
    """
    if chrom not in WINDOWS:
        return None
    first, bases = WINDOWS[chrom]
    if end > first + len(bases) - 1 or end < first:
        return None
    return bases[max(start, first) - first : end - first + 1]


class _RecordedBases(_DataProxy):
    """A `ga4gh.vrs` data proxy holding only the recorded windows; any read outside one raises."""

    def get_sequence(self, identifier: str, start: int | None = None, end: int | None = None) -> str:
        first, bases = _BY_ACCESSION[identifier]
        lo, hi = int(start or 0) - (first - 1), int(end or 0) - (first - 1)
        if lo < 0 or hi > len(bases) or hi < lo:
            raise ValueError(f"{identifier}:[{start},{end}) is outside the recorded window")
        return bases[lo:hi]

    def get_metadata(self, identifier: str) -> dict:
        if identifier not in _BY_ACCESSION:
            raise KeyError(identifier)
        return {"length": 10**9, "aliases": [identifier], "alphabet": "ACGT"}


_CHROM_OF = {refget_accession(chrom): chrom for chrom in WINDOWS}


class RecordedSequences(SequenceProxy):
    """The run's own proxy class, reading the recorded windows instead of seqrepo.

    `proxy()` feeds `ga4gh.vrs`; `subsequence` feeds the run's window reads (the hosting settle and
    `_left_align`), which read up to a kilobase left of a position and accept a left-clipped answer.
    """

    def proxy(self) -> _DataProxy:
        return _RecordedBases()

    def subsequence(self, accession: str, start: int, end: int) -> str | None:
        chrom = _CHROM_OF.get(accession)
        return None if chrom is None else read(chrom, start + 1, end)


def _minter() -> VrsMinter:
    return VrsMinter(sequences=RecordedSequences())


def _mint(minter: VrsMinter):
    return lambda chrom, start, ref, alt: minter.mint(chrom, start, ref, alt)[0]


# ── the windows, and the comparison on its own ──────────────────────────────────────────────────


def test_the_recorded_windows_mint_the_ids_ga4gh_and_clinvar_gkm_recorded() -> None:
    minter = _minter()
    assert minter.mint(*ENSEMBL["rs72613567"])[0] == HSD17B13_ID
    assert minter.mint(*CLINVAR["rs72613567"])[0] == HSD17B13_ID
    assert minter.mint(*ENSEMBL["rs77944059"])[0] == RS77944059_ID
    assert minter.mint(*CLINVAR["rs77944059"])[0] == RS77944059_ID
    # And S117's pair is two ids: two events, not one spelled twice.
    first, second = minter.mint(*ENSEMBL["rs8176719"])[0], minter.mint(*CLINVAR["rs8176719"])[0]
    assert first and second and first != second
    # The bases the ROADMAP entry quotes: GGGG T ACC at 517–524.
    assert read("9", 133257517, 133257524) == "GGGGTACC"


@pytest.mark.parametrize(
    ("rsid", "expected"),
    [("rs8176719", False), ("rs72613567", True), ("rs77944059", True)],
)
def test_same_event_by_vrs_id(rsid: str, expected: bool) -> None:
    ours, theirs = Allele(*ENSEMBL[rsid]), Allele(*CLINVAR[rsid])
    assert same_event(ours, theirs, mint=_mint(_minter()), read_window=None) is expected


@pytest.mark.parametrize(
    ("rsid", "expected"),
    [("rs8176719", False), ("rs72613567", True), ("rs77944059", True)],
)
def test_same_event_by_left_alignment_when_no_id_can_be_minted(rsid: str, expected: bool) -> None:
    """The ladder's fourth rung: no id (an offline minter), and the reference window decides."""
    offline = VrsMinter(offline=True)
    ours, theirs = Allele(*ENSEMBL[rsid]), Allele(*CLINVAR[rsid])
    assert same_event(ours, theirs, mint=_mint(offline), read_window=read) is expected


def test_with_neither_an_id_nor_a_window_a_respelling_is_undecided() -> None:
    offline = VrsMinter(offline=True)
    for rsid in ("rs8176719", "rs72613567"):
        assert (
            same_event(Allele(*ENSEMBL[rsid]), Allele(*CLINVAR[rsid]), mint=_mint(offline), read_window=None)
            is None
        )
    # An identical spelling and a substitution need neither.
    assert same_event(
        Allele("2", 5, "G", "A"), Allele("2", 5, "G", "A"), mint=_mint(offline), read_window=None
    )
    assert (
        same_event(Allele("2", 5, "G", "A"), Allele("2", 6, "G", "A"), mint=_mint(offline), read_window=None)
        is False
    )


def test_a_different_allele_of_the_rsid_is_unplaced_never_a_disagreement() -> None:
    """ClinVar holds the alleles somebody submitted. A substitution beside a different one is not a
    placement claim about it, and neither is a deletion beside an insertion."""
    placed = {"rs1": [{"chrom": "2", "start": 5, "ref": "G", "alts": "A"}]}
    witness = {"clinvar": {"rs1": [{"chrom": "2", "start": 5, "ref": "G", "alts": "T,GC"}]}}
    check = compare_placements(
        placed, {"rs1": "ensembl"}, witness, mint=_mint(VrsMinter(offline=True)), read_window=None
    )
    assert check.disagreements == [] and check.subjects == 0
    assert check.single_witness == ["rs1"]
    assert check.row_columns("rs1", placed["rs1"][0]) == ("clinvar", "unplaced")


def test_a_clinvar_fill_has_no_independent_witness_here() -> None:
    """ClinVar-GKM is ClinVar's own release, so it cannot witness what the ClinVar link filled."""
    loci = [dict(zip(("chrom", "start", "ref", "alts"), CLINVAR["rs72613567"], strict=True))]
    witness = {"clinvar": {"rs72613567": loci}, "clinvar_gkm": {"rs72613567": loci}}
    check = compare_placements(
        {"rs72613567": loci}, {"rs72613567": "clinvar"}, witness, mint=_mint(_minter()), read_window=read
    )
    assert check.subjects == 0 and check.single_witness == ["rs72613567"]
    assert check.row_columns("rs72613567", loci[0]) == (None, None)


# ── through `enrich` ────────────────────────────────────────────────────────────────────────────


def _locus(spelling: tuple[str, int, str, str]) -> dict[str, object]:
    return dict(zip(("chrom", "start", "ref", "alt"), spelling, strict=True))


def _ensembl_snapshot(root: Path) -> Path:
    data = root / "ensembl" / "data"
    data.mkdir(parents=True, exist_ok=True)
    rows = [{"id": rsid, **_locus(s)} for rsid, s in ENSEMBL.items()]
    pl.DataFrame(rows).write_parquet(data / "variants.parquet")
    return root / "ensembl"


def _clinvar_snapshot(root: Path, alleles: dict[str, tuple[str, int, str, str]] = CLINVAR) -> Path:
    data = root / "clinvar" / "data"
    data.mkdir(parents=True, exist_ok=True)
    pl.DataFrame([{"rsid": rsid, **_locus(s)} for rsid, s in alleles.items()]).write_parquet(
        data / "c.parquet"
    )
    return root / "clinvar"


def _gkm_snapshot(root: Path) -> Path:
    """The RM305 slice, built through the lane's own builder against its own manifest."""
    raw = json.loads((SLICE / "manifest.json").read_text(encoding="utf-8"))
    for entry in raw["files"]:
        path = {ALLELE_FILE: SLICE / ALLELE_FILE, VARIATION_FILE: SLICE / VARIATION_FILE}.get(entry["name"])
        if path is not None:
            entry["size"] = path.stat().st_size
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    out = root / "clinvar_gkm"
    build_snapshot(SLICE / ALLELE_FILE, SLICE / VARIATION_FILE, out, manifest=parse_manifest(json.dumps(raw)))
    return out


def _spec(root: Path, rows: dict[str, str] = GENOTYPES, *, pairs: dict[str, tuple] | None = None) -> Path:
    spec = root / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    lines = ["rsid,chrom,start,ref,alts,genotype,state,conclusion"]
    for rsid, genotype in rows.items():
        chrom, start, ref, alt = (pairs or {}).get(rsid, ("", "", "", ""))
        lines.append(f"{rsid},{chrom},{start},{ref},{alt},{genotype},risk,c")
    (spec / "variants.csv").write_text("\n".join(lines) + "\n")
    (spec / "studies.csv").write_text("rsid,pmid\n" + "".join(f"{r},9545397\n" for r in rows))
    return spec


class _NoLiveEnsembl:
    """Every rsID here is in the snapshot, so a live-link request is a defect in the test's arrangement,
    and so is a REST witness request unless the test says REST is unreachable (`rest_unreachable`); then
    the witness gets the could-not-ask answer and `asked` records what it tried."""

    def __init__(self, *, rest_unreachable: bool = False) -> None:
        self.rest_unreachable = rest_unreachable
        self.asked: list[str] = []

    def resolve_rsid(self, rsid: str):
        raise AssertionError(f"live Ensembl asked about {rsid}")

    def resolve_rsid_rest(self, rsid: str):
        if not self.rest_unreachable:
            raise AssertionError(f"the REST witness asked about {rsid}")
        self.asked.append(rsid)
        return None, None

    def close(self) -> None:
        return None


def _enrich(spec: Path, root: Path, monkeypatch: pytest.MonkeyPatch, **kwargs):
    monkeypatch.setattr("just_dna_enricher.enrich.orchestration.SequenceProxy", RecordedSequences)
    options = {
        "ensembl_cache": _ensembl_snapshot(root),
        "download": False,
        "use_gnomad": False,
        "verify_ref": False,
        "verify_clinsig": False,
        "verify_rsids": False,
        "verify_datasets": False,
        "resolver": _NoLiveEnsembl(),
    }
    options.update(kwargs)
    return enrich(spec, **options)


def _record(spec: Path) -> dict:
    doc = json.loads((spec / VERIFICATION_JSON).read_text(encoding="utf-8"))
    return {r["check"]: r for r in doc["records"]}["placement_agreement"]


def test_s117_is_withheld_and_both_respellings_are_written_with_their_witness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    spec = _spec(tmp_path)
    result = _enrich(
        spec,
        tmp_path,
        monkeypatch,
        clinvar_cache=_clinvar_snapshot(tmp_path),
        clinvar_gkm_cache=_gkm_snapshot(tmp_path),
    )
    rows = {r.rsid: r for r in result.rows}
    # rs8176719: two events, so no row at all, and the finding names both placements.
    assert "rs8176719" not in rows and "rs8176719" in result.unresolved
    assert result.placement is not None and result.placement.withheld == ["rs8176719"]
    (finding,) = result.placement.disagreements
    assert finding.placed == ("9:133257520 G>GC",) and finding.witness_placed == ("9:133257521 T>TC",)
    assert (finding.authority, finding.witness) == ("ensembl", "clinvar")
    # The respellings: one event, so written — left-aligned since RM270, which is ClinVar's spelling —
    # with the witness recorded on the row.
    for rsid, vrs_id in (("rs72613567", HSD17B13_ID), ("rs77944059", RS77944059_ID)):
        row = rows[rsid]
        assert (row.chrom, row.start, row.ref, row.alts) == CLINVAR[rsid]
        assert row.left_aligned is True
        assert (row.placement_witness, row.placement_verdict) == ("clinvar+clinvar_gkm", "same_event")
        assert row.vrs_id == vrs_id
    # One witness: asked, and holding nothing for it — counted, never agreement.
    assert (rows["rs4988235"].placement_witness, rows["rs4988235"].placement_verdict) == (
        "clinvar+clinvar_gkm",
        "unplaced",
    )
    assert result.placement.single_witness == ["rs4988235"]
    # The record, read back off disk: denominator, finding, abstentions, and the one-witness count.
    record = _record(spec)
    assert (record["subjects"], record["findings"], record["undecided"]) == (3, 1, 0)
    assert (record["checked_source"], record["witness_source"]) == ("reporting_source", "clinvar+clinvar_gkm")
    assert "1 of 4 placed rsID(s) had one witness only" in record["detail"]
    on_disk, errors, _ = load_csv_rows(spec / "resolution.csv", ResolutionRow, "resolution.csv")
    assert errors == [] and {r.rsid for r in on_disk} == {"rs72613567", "rs77944059", "rs4988235"}


def test_strict_refuses_the_withheld_rsid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    spec = _spec(tmp_path, {"rs8176719": "T/TC"})
    with pytest.raises(EnrichmentError, match="rs8176719"):
        _enrich(spec, tmp_path, monkeypatch, mode="strict", clinvar_cache=_clinvar_snapshot(tmp_path))
    assert not (spec / "resolution.csv").exists(), "a refused strict run commits nothing"


def test_an_authored_pair_keeps_its_own_coordinate_when_the_reference_placement_is_disputed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    spec = _spec(tmp_path, {"rs8176719": "T/TC"}, pairs={"rs8176719": CLINVAR["rs8176719"]})
    result = _enrich(spec, tmp_path, monkeypatch, clinvar_cache=_clinvar_snapshot(tmp_path))
    (row,) = result.rows
    assert (row.source, row.chrom, row.start, row.ref, row.alts) == ("authored", *CLINVAR["rs8176719"])
    assert result.placement is not None and result.placement.withheld == ["rs8176719"]


def test_offline_with_no_witness_asks_nobody_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    spec = _spec(tmp_path)
    result = _enrich(spec, tmp_path, monkeypatch, offline=True)
    assert {r.rsid for r in result.rows} == set(ENSEMBL)
    assert {(r.placement_witness, r.placement_verdict) for r in result.rows} == {(None, None)}
    record = _record(spec)
    assert record["skipped"] == "no_reference"
    assert "4 of 4 placed rsID(s) had one witness only" in record["detail"]
    # The question names Ensembl REST beside ClinVar, and these placements are Ensembl's: the skip says
    # so rather than reading `independent`.
    assert (record["checked_source"], record.get("independence")) == ("ensembl", None)


def test_offline_with_a_local_clinvar_snapshot_withholds_only_what_needs_no_sequence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """Offline, the sequence service is unreachable: an indel respelling is undecided, not agreed.

    The LCT row is a constructed disagreement — ClinVar's allele moved one base — because a
    substitution has one spelling, so two positions are two placements with no sequence needed.
    """
    monkeypatch.setattr("just_dna_enricher.enrich.orchestration.SequenceProxy", SequenceProxy)
    moved = {**CLINVAR, "rs4988235": ("2", 135851077, "G", "A")}
    spec = _spec(tmp_path)
    result = enrich(
        spec,
        offline=True,
        ensembl_cache=_ensembl_snapshot(tmp_path),
        clinvar_cache=_clinvar_snapshot(tmp_path, moved),
        download=False,
        use_gnomad=False,
        verify_ref=False,
        verify_clinsig=False,
        verify_rsids=False,
        verify_datasets=False,
    )
    rows = {r.rsid: r for r in result.rows}
    assert result.placement is not None and result.placement.withheld == ["rs4988235"]
    assert result.placement.undecided == ["rs72613567", "rs77944059", "rs8176719"]
    for rsid in ("rs72613567", "rs77944059", "rs8176719"):
        assert (rows[rsid].placement_witness, rows[rsid].placement_verdict) == ("clinvar", "undecided")
    record = _record(spec)
    assert (record["subjects"], record["findings"], record["undecided"]) == (4, 1, 3)


def test_rederive_does_not_carry_a_disputed_rows_old_placement_forward(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """The old table holds S117's wrong placement. Re-deriving asked, and the answer is "disputed":
    that is an answer, so the recorded row is not kept as though nothing could be asked."""
    spec = _spec(tmp_path, {"rs8176719": "T/TC"})
    chrom, start, ref, alt = ENSEMBL["rs8176719"]
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
        f"rs8176719,rs8176719,{chrom},{start},{ref},{alt},GRCh38,0,cache,resolved\n"
    )
    result = _enrich(spec, tmp_path, monkeypatch, rederive=True, clinvar_cache=_clinvar_snapshot(tmp_path))
    assert result.rows == [] and result.unresolved == ["rs8176719"]


def test_the_two_columns_are_outside_the_fact_signature() -> None:
    bare = ResolutionRow(variant_key="rs1", rsid="rs1", chrom="2", start=5, ref="G", alts="A")
    stamped = ResolutionRow(
        **bare.model_dump(exclude_none=True), placement_witness="clinvar", placement_verdict="same_event"
    )
    assert resolution_signature([bare]) == resolution_signature([stamped])


def test_the_verdict_is_a_closed_vocabulary() -> None:
    for verdict in ("same_event", "undecided", "unplaced"):
        # A verdict names what a witness answered, so it is written beside one (RM366).
        row = ResolutionRow(variant_key="rs1", placement_witness="clinvar", placement_verdict=verdict)
        assert row.placement_verdict == verdict
    with pytest.raises(ValueError, match="placement_verdict"):
        ResolutionRow(variant_key="rs1", placement_witness="clinvar", placement_verdict="agrees")


# ── review regressions ──────────────────────────────────────────────────────────────────────────


def test_one_disputed_locus_withholds_that_locus_only() -> None:
    """A multi-locus rsID keeps the placement both authorities agree on; only the disputed one goes."""
    agreed = {"chrom": "2", "start": 5, "ref": "G", "alts": "A"}
    disputed = dict(zip(("chrom", "start", "ref", "alts"), ENSEMBL["rs8176719"], strict=True))
    witness_disputed = dict(zip(("chrom", "start", "ref", "alts"), CLINVAR["rs8176719"], strict=True))
    check = compare_placements(
        {"rsX": [agreed, disputed]},
        {"rsX": "ensembl"},
        {"clinvar": {"rsX": [agreed, witness_disputed]}},
        mint=_mint(_minter()),
        read_window=read,
    )
    assert check.contested == ["rsX"] and check.withheld == []
    assert check.keeps("rsX", agreed) and not check.keeps("rsX", disputed)
    assert check.row_columns("rsX", agreed) == ("clinvar", "same_event")


def test_a_row_reads_same_event_only_when_every_alt_was_witnessed() -> None:
    """`C>T,G` with ClinVar holding only C>T: the G allele is unconfirmed, so the row is `unplaced`."""
    locus = {"chrom": "2", "start": 5, "ref": "C", "alts": "G,T"}
    check = compare_placements(
        {"rsX": [locus]},
        {"rsX": "ensembl"},
        {"clinvar": {"rsX": [{"chrom": "2", "start": 5, "ref": "C", "alts": "T"}]}},
        mint=_mint(VrsMinter(offline=True)),
        read_window=None,
    )
    assert check.row_columns("rsX", locus) == ("clinvar", "unplaced")
    assert check.subjects == 1 and check.single_witness == []


def test_an_overlay_answer_clears_the_strict_refusal_and_the_witness_terms_are_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    spec = _spec(tmp_path, {"rs8176719": "T/TC", "rs72613567": "T/TA"})
    header = "table,subject,member,field,operation,value,reason,decided_by,decided_at\n"
    insert = [("chrom", "9"), ("start", "133257521"), ("ref", "T"), ("alts", "TC")]
    rows = [
        f"resolution.csv,rs8176719,0,{f},insert,{v},REST and dbSNP place it at 521,c,2026-11-04\n"
        for f, v in insert
    ]
    # Half a placement answers nothing: the refusal stands.
    (spec / "overrides.csv").write_text(header + rows[0])
    with pytest.raises(EnrichmentError, match="placement disagreement"):
        _enrich(spec, tmp_path, monkeypatch, mode="strict", clinvar_cache=_clinvar_snapshot(tmp_path))
    (spec / "overrides.csv").write_text(header + "".join(rows))
    result = _enrich(spec, tmp_path, monkeypatch, mode="strict", clinvar_cache=_clinvar_snapshot(tmp_path))
    assert result.unresolved == [] and result.placement is not None
    assert result.placement.contested == ["rs8176719"], "still counted: the answer silences, never erases"
    # The licence table under the name this tree writes (`layout`), wherever the module keeps it.
    sources = sources_path(spec, error=EnrichmentError).read_text(encoding="utf-8")
    assert "clinvar,resolution" in sources and "ensembl,resolution" in sources


def test_the_strict_refusal_names_the_disagreement_rather_than_asking_for_a_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    spec = _spec(tmp_path, {"rs8176719": "T/TC"})
    with pytest.raises(EnrichmentError, match="placement disagreement") as raised:
        _enrich(spec, tmp_path, monkeypatch, mode="strict", clinvar_cache=_clinvar_snapshot(tmp_path))
    assert "complete cache" not in str(raised.value)


def test_an_unreadable_clinvar_gkm_snapshot_is_a_missing_witness_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    broken = tmp_path / "gkm" / "data"
    broken.mkdir(parents=True)
    # The lane's own file name, holding a frame the reader cannot map onto a placement.
    pl.DataFrame({"unrelated": [1]}).write_parquet(broken / WITNESS_PARQUET)
    spec = _spec(tmp_path, {"rs72613567": "T/TA"})
    result = _enrich(
        spec,
        tmp_path,
        monkeypatch,
        resolver=_NoLiveEnsembl(rest_unreachable=True),
        clinvar_gkm_cache=tmp_path / "gkm",
    )
    assert result.placement is not None and result.placement.not_checked == "no_reference"


def test_witnesses_holding_nothing_record_a_skip_never_a_zero_of_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    spec = _spec(tmp_path, {"rs4988235": "A/G"})
    result = _enrich(spec, tmp_path, monkeypatch, clinvar_cache=_clinvar_snapshot(tmp_path))
    assert result.placement is not None and result.placement.subjects == 0
    record = _record(spec)
    assert record["skipped"] == "nothing_to_check" and record.get("subjects") in (None, 0)
    assert "1 of 1 placed rsID(s) had one witness only" in record["detail"]


# ── Ensembl REST, the third witness: online only, for an indel no loaded witness holds ──────────────
#
# The mappings are what `rest.ensembl.org/variation/human/<rsid>?content-type=application/json` answered
# by hand on 2026-11-04 (17:33Z, after a run of 503s and timeouts from 17:26Z): rs8176719 is `-/C` with
# `start = end + 1`, the interbase point RM268 anchors on the base before it; rs77944059 is a two-sided
# `AAACAAACAAA/AAACAAA`, a four-base deletion spelled over its whole repeat. Only the fields the parser
# reads are kept.

REST_MAPPINGS: dict[str, list[dict]] = {
    "rs8176719": [
        {
            "assembly_name": "GRCh38",
            "seq_region_name": "9",
            "start": 133257522,
            "end": 133257521,
            "allele_string": "-/C",
        }
    ],
    "rs77944059": [
        {
            "assembly_name": "GRCh38",
            "seq_region_name": "2",
            "start": 166204471,
            "end": 166204481,
            "allele_string": "AAACAAACAAA/AAACAAA",
        }
    ],
}


class _Rest:
    """The live resolver over recorded REST answers: the real parse, the real RM268 anchor."""

    def __init__(self, status: int = 200) -> None:
        self.requested: list[str] = []
        self.status = status
        #: How many times the run asked REST which data release it answers from (RM373).
        self.release_asked = 0

    def resolver(self) -> EnsemblResolver:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.host == "rest.ensembl.org", f"asked {request.url}, not Ensembl REST"
            if request.url.path == "/info/data":
                # What `/info/data` answered by hand on 2026-11-04 (`test_source_release.py`).
                self.release_asked += 1
                return httpx.Response(200, json={"releases": [116]})
            rsid = request.url.path.rsplit("/", 1)[-1]
            self.requested.append(rsid)
            if self.status != 200:
                return httpx.Response(self.status, text="No server is available to handle this request.")
            return httpx.Response(200, json={"name": rsid, "mappings": REST_MAPPINGS.get(rsid, [])})

        resolver = EnsemblResolver()
        resolver._client = httpx.Client(transport=httpx.MockTransport(handler))
        resolver._read_base = lambda chrom, pos: read(chrom, pos, pos)
        return resolver


def _without(*rsids: str) -> dict[str, tuple[str, int, str, str]]:
    return {k: v for k, v in CLINVAR.items() if k not in rsids}


def test_rest_withholds_s117_when_no_loaded_witness_holds_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """S117's own case, as the real witnesses stand: ClinVar and ClinVar-GKM lack `rs8176719`, REST has it."""
    spec = _spec(tmp_path)
    rest = _Rest()
    result = _enrich(
        spec,
        tmp_path,
        monkeypatch,
        clinvar_cache=_clinvar_snapshot(tmp_path, _without("rs8176719")),
        clinvar_gkm_cache=_gkm_snapshot(tmp_path),
        resolver=rest.resolver(),
    )
    # Asked about the one indel nobody loaded holds: not the SNV, not the indels ClinVar holds.
    assert rest.requested == ["rs8176719"]
    rows = {r.rsid: r for r in result.rows}
    assert "rs8176719" not in rows and "rs8176719" in result.unresolved
    assert result.placement is not None and result.placement.withheld == ["rs8176719"]
    (finding,) = result.placement.disagreements
    assert (finding.authority, finding.witness) == ("ensembl", "ensembl")
    assert finding.placed == ("9:133257520 G>GC",) and finding.witness_placed == ("9:133257521 T>TC",)
    # The rows REST was not asked about do not name it.
    assert rows["rs72613567"].placement_witness == "clinvar+clinvar_gkm"
    record = _record(spec)
    assert record["findings"] == 1 and record["witness_source"] == "clinvar+clinvar_gkm+ensembl"
    # Part of the comparison is Ensembl against Ensembl, so neither word is true of the whole record.
    assert record["checked_source"] == "ensembl" and record.get("independence") is None
    assert "Ensembl REST" in record["detail"]


def test_a_rest_agreed_indel_is_written_with_ensembl_as_its_self_consistent_witness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """No snapshot witness at all: REST is the only second answer, and it is Ensembl's own."""
    spec = _spec(tmp_path, {"rs77944059": "G/GAAAC"})
    rest = _Rest()
    result = _enrich(spec, tmp_path, monkeypatch, resolver=rest.resolver())
    assert rest.requested == ["rs77944059"]
    (row,) = result.rows
    assert (row.placement_witness, row.placement_verdict) == ("ensembl", "same_event")
    assert row.vrs_id == RS77944059_ID
    # Agreement with its own source proves nothing about the placement: still one witness.
    assert result.placement is not None and result.placement.single_witness == ["rs77944059"]
    assert result.placement.self_consistent == ["rs77944059"]
    record = _record(spec)
    assert (record["subjects"], record["findings"]) == (1, 0)
    assert (record["checked_source"], record["witness_source"], record["independence"]) == (
        "ensembl",
        "ensembl",
        "self_consistent",
    )
    assert "1 of 1 placed rsID(s) had one witness only" in record["detail"]
    sources = sources_path(spec, error=EnrichmentError).read_text(encoding="utf-8")
    assert "ensembl,resolution" in sources


def test_rest_unreachable_is_not_asked_and_counted_never_agreement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    monkeypatch.setattr("time.sleep", lambda _seconds: None)  # tenacity's backoff
    spec = _spec(tmp_path, {"rs8176719": "T/TC"})
    rest = _Rest(status=503)
    result = _enrich(
        spec,
        tmp_path,
        monkeypatch,
        clinvar_cache=_clinvar_snapshot(tmp_path, _without("rs8176719")),
        resolver=rest.resolver(),
    )
    assert len(rest.requested) > 1, "a 503 is retried before the witness counts as not asked"
    # Nobody contradicted the snapshot, so it is written as before — and the row does not name REST.
    (row,) = result.rows
    assert (row.placement_witness, row.placement_verdict) == ("clinvar", "unplaced")
    assert result.placement is not None and result.placement.not_asked == ["rs8176719"]
    record = _record(spec)
    assert record["skipped"] == "nothing_to_check"
    assert "1 rsID(s) Ensembl REST could not be asked about" in record["detail"]


class _ResolverBeforeTheRestWitness:
    """An injected resolver written before `resolve_rsid_rest` existed: the shape a host hands `enrich`
    (just-dna-marketplace's test fake is exactly this, `resolve_rsid` and `close` only). Every rsID here
    is in the snapshot, so the live link must not ask it either."""

    def resolve_rsid(self, rsid: str):
        raise AssertionError(f"live Ensembl asked about {rsid}")

    def close(self) -> None:
        return None


def test_an_injected_resolver_without_the_rest_method_leaves_rest_not_asked_and_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The REST witness is an optional capability of an injected resolver. A resolver without it is a
    witness this run could not ask: the run completes, the snapshot's placement is written as it would
    have been with REST unreachable, the rsID is counted as not asked, and one warning names why."""
    spec = _spec(tmp_path, {"rs8176719": "T/TC", "rs77944059": "G/GAAAC"})
    with caplog.at_level("WARNING", logger="just_dna_enricher.enrich"):
        result = _enrich(
            spec,
            tmp_path,
            monkeypatch,
            clinvar_cache=_clinvar_snapshot(tmp_path, _without("rs8176719", "rs77944059")),
            resolver=_ResolverBeforeTheRestWitness(),
        )
    rows = {r.rsid: r for r in result.rows}
    assert set(rows) == {"rs8176719", "rs77944059"}
    assert all(row.placement_witness != "ensembl" for row in rows.values())
    assert result.placement is not None
    assert result.placement.not_asked == ["rs77944059", "rs8176719"]
    assert result.placement.not_asked_reason is not None
    (warning,) = [r for r in caplog.records if "resolve_rsid_rest" in r.getMessage()]
    assert "2 snapshot indel(s)" in warning.getMessage()
    record = _record(spec)
    assert "2 rsID(s) Ensembl REST could not be asked about" in record["detail"]
    assert "resolve_rsid_rest" in record["detail"]
    assert "unreachable after retries" not in record["detail"]


def test_offline_asks_rest_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    spec = _spec(tmp_path, {"rs8176719": "T/TC"})
    rest = _Rest()
    result = _enrich(spec, tmp_path, monkeypatch, offline=True, resolver=rest.resolver())
    assert rest.requested == []
    (row,) = result.rows
    assert (row.placement_witness, row.placement_verdict) == (None, None)
    assert result.placement is not None and result.placement.not_asked == []


@pytest.mark.skipif(os.environ.get("JUST_DNA_NETWORK_TESTS") != "1", reason="set JUST_DNA_NETWORK_TESTS=1")
def test_live_rest_places_s117_as_dbsnp_does() -> None:
    """The live rung, unmocked: REST's `-/C` anchors on GRCh38's own base to ClinVar/dbSNP's spelling,
    which the snapshot's `9:133257520 G>GC` is not."""
    resolver = EnsemblResolver()
    try:
        loci, source = resolver.resolve_rsid("rs8176719")
    finally:
        resolver.close()
    assert source == "ensembl-rest"
    assert loci == [dict(zip(("chrom", "start", "ref", "alts"), CLINVAR["rs8176719"], strict=True))]


# ── RM270: a fill is written left-aligned, an authored coordinate is judged, the id joins both ─────


def _coordinate_spec(root: Path, spellings: dict[str, tuple[str, int, str, str]]) -> Path:
    """Coordinate-authored rows (no rsID): the module's own spelling is its identity."""
    spec = root / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    lines = ["chrom,start,ref,alts,genotype,state,conclusion"]
    for name, (chrom, start, ref, alt) in spellings.items():
        lines.append(f"{chrom},{start},{ref},{alt},{'/'.join(sorted((ref, alt)))},risk,{name}")
    (spec / "variants.csv").write_text("\n".join(lines) + "\n")
    (spec / "studies.csv").write_text(
        "chrom,start,ref,pmid\n" + "".join(f"{c},{p},{r},9545397\n" for c, p, r, _ in spellings.values())
    )
    return spec


def _weights_ids(spec: Path, out: Path) -> dict[tuple, list | None]:
    result = compile_module(spec, out)
    assert result.success, result.errors
    df = pl.read_parquet(out / "weights.parquet")
    return {
        (r["chrom"], r["start"], r["ref"], ",".join(r["alts"])): r["vrs_id"] for r in df.iter_rows(named=True)
    }


def test_rm270_a_filled_respelling_is_written_left_aligned_and_compiles_to_its_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """The Ensembl snapshot gives each rsID a few bases right of the caller's spelling. The fill is
    outside `content_signature`, so the run writes it left-aligned — the spelling ClinVar and a
    caller's normalized VCF use — and the parquet carries the one id both spellings mint."""
    spec = _spec(tmp_path, {"rs72613567": "T/TA", "rs77944059": "G/GAAAC"})
    result = _enrich(spec, tmp_path, monkeypatch, resolver=_NoLiveEnsembl(rest_unreachable=True))
    rows = {r.rsid: r for r in result.rows}
    for rsid in ("rs72613567", "rs77944059"):
        assert (rows[rsid].chrom, rows[rsid].start, rows[rsid].ref, rows[rsid].alts) == CLINVAR[rsid]
        assert rows[rsid].left_aligned is True
    assert result.spelling is not None and len(result.spelling.respelled) == 2
    assert "rs72613567 4:87310241 A>AA → 4:87310240 T>TA" in result.spelling.respelled
    ids = _weights_ids(spec, tmp_path / "out")
    assert ids[(*CLINVAR["rs72613567"][:3], "TA")] == [HSD17B13_ID]
    assert ids[(*CLINVAR["rs77944059"][:3], "G")] == [RS77944059_ID]


def test_rm270_an_authored_coordinate_is_judged_never_rewritten_and_its_id_joins_both_spellings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """Both spellings of `rs72613567` and `rs77944059` authored as coordinates, and `rs8176719`'s two
    placements. The cells are the rows' identity: each is recorded exactly as authored, the
    right-shifted ones are stamped `left_aligned=false` with the leftmost spelling named, and on the
    parquet each event carries one id whichever way it was spelled while the two events carry two."""
    spellings = {
        "hsd17b13_ensembl": ENSEMBL["rs72613567"],
        "hsd17b13_clinvar": CLINVAR["rs72613567"],
        "rs77944059_ensembl": ENSEMBL["rs77944059"],
        "abo_ensembl": ENSEMBL["rs8176719"],
        "abo_clinvar": CLINVAR["rs8176719"],
    }
    spec = _coordinate_spec(tmp_path, spellings)
    authored = (spec / "variants.csv").read_bytes()
    result = _enrich(spec, tmp_path, monkeypatch)
    rows = {(r.chrom, r.start, r.ref, r.alts): r for r in result.rows}
    assert set(rows) == set(spellings.values()), "every cell recorded as authored"
    aligned = {name: rows[s].left_aligned for name, s in spellings.items()}
    assert aligned == {
        "hsd17b13_ensembl": False,
        "hsd17b13_clinvar": True,
        "rs77944059_ensembl": False,
        "abo_ensembl": True,
        "abo_clinvar": True,
    }
    assert result.spelling is not None
    assert (result.spelling.checked, result.spelling.unknown, result.spelling.respelled) == (5, 0, [])
    assert sorted(result.spelling.findings) == [
        "2:166204477:ACAAA:A: 2:166204477 ACAAA>A → 2:166204470 GAAAC>G",
        "4:87310241:A:AA: 4:87310241 A>AA → 4:87310240 T>TA",
    ]
    assert (spec / "variants.csv").read_bytes() == authored
    ids = _weights_ids(spec, tmp_path / "out")
    assert ids[ENSEMBL["rs72613567"]] == ids[CLINVAR["rs72613567"]] == [HSD17B13_ID]
    assert ids[ENSEMBL["rs77944059"]] == [RS77944059_ID]
    abo = ids[ENSEMBL["rs8176719"]], ids[CLINVAR["rs8176719"]]
    assert abo[0] and abo[1] and abo[0] != abo[1]


def test_rm270_offline_a_fill_keeps_its_links_spelling_and_says_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """No reference read, no verdict: the fill stays as the link gave it, `left_aligned` empty —
    unknown, never `false` — and a substitution is still decided, since it needs no read."""
    monkeypatch.setattr("just_dna_enricher.enrich.orchestration.SequenceProxy", SequenceProxy)
    spec = _spec(tmp_path, {"rs72613567": "T/TA", "rs4988235": "A/G"})
    result = enrich(
        spec,
        offline=True,
        ensembl_cache=_ensembl_snapshot(tmp_path),
        download=False,
        use_gnomad=False,
        verify_ref=False,
        verify_clinsig=False,
        verify_rsids=False,
        verify_datasets=False,
    )
    rows = {r.rsid: r for r in result.rows}
    assert (rows["rs72613567"].start, rows["rs72613567"].left_aligned) == (ENSEMBL["rs72613567"][1], None)
    assert rows["rs4988235"].left_aligned is True
    assert result.spelling is not None and result.spelling.respelled == []


def test_rm270_a_recorded_fill_is_respelled_only_on_rederive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """`@sidecar-authoritative`: an ordinary run leaves a recorded row alone, `--rederive` re-asks."""
    spec = _spec(tmp_path, {"rs72613567": "T/TA"})
    chrom, start, ref, alt = ENSEMBL["rs72613567"]
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
        f"rs72613567,rs72613567,{chrom},{start},{ref},{alt},GRCh38,0,cache,resolved\n"
    )
    (row,) = _enrich(spec, tmp_path, monkeypatch, resolver=_NoLiveEnsembl(rest_unreachable=True)).rows
    assert (row.start, row.left_aligned) == (start, None)
    (row,) = _enrich(
        spec, tmp_path, monkeypatch, resolver=_NoLiveEnsembl(rest_unreachable=True), rederive=True
    ).rows
    assert ((row.chrom, row.start, row.ref, row.alts), row.left_aligned) == (CLINVAR["rs72613567"], True)


def test_rm270_the_verdict_is_outside_the_fact_signature_and_reads_back_tri_state(tmp_path: Path) -> None:
    bare = ResolutionRow(variant_key="rs1", rsid="rs1", chrom="2", start=5, ref="G", alts="A")
    for verdict in (True, False):
        stamped = ResolutionRow(**bare.model_dump(exclude_none=True), left_aligned=verdict)
        assert resolution_signature([bare]) == resolution_signature([stamped])
        path = tmp_path / f"{verdict}.csv"
        _write_resolution_csv([stamped, bare], path)
        back, errors, _ = load_csv_rows(path, ResolutionRow, path.name)
        assert errors == [] and [r.left_aligned for r in back] == [verdict, None]


def _consumer_join_window(chrom: str, start: int, end: int) -> str | None:
    """1-based inclusive GRCh38 bases from the consumer-join fixture's windows (`samtools faidx`)."""
    with gzip.open(CONSUMER_JOIN / "grch38_windows.fa.gz", "rt") as handle:
        records = handle.read().split(">")[1:]
    for record in records:
        header, _, body = record.partition("\n")
        name, span = header.rsplit(":", 1)
        first = int(span.split("-")[0])
        bases = body.replace("\n", "").upper()
        if name == chrom and first <= end <= first + len(bases) - 1:
            return bases[max(start, first) - first : end - first + 1]
    return None


def test_rm270_shox_multi_allelic_fill_splits_into_the_two_spellings_a_caller_writes() -> None:
    """Ensembl's `X:634690 AGAG>AG,AGAGAG` is a 2 bp AG deletion and its duplication; ClinVar and a
    caller's `bcftools norm -m -any` write `X:634689 CAG>C` and `X:634689 C>CAG`. Two references, so two
    loci; a site whose ALTs share one leftmost `(start, ref)` stays one locus."""
    shox = {"chrom": "X", "start": 634690, "ref": "AGAG", "alts": "AG,AGAGAG"}
    normalized = normalize_locus(shox, _consumer_join_window)
    assert normalized.aligned is True and normalized.piece_of == (0, 1)
    assert [(lo["start"], lo["ref"], lo["alts"]) for lo in normalized.loci] == [
        (634689, "CAG", "C"),
        (634689, "C", "CAG"),
    ]
    # Offline: nothing decided, nothing respelled — whole or not at all.
    assert normalize_locus(shox, None).loci == [shox] and normalize_locus(shox, None).aligned is None
    # A multi-allelic substitution needs no read and stays one locus.
    snv = {"chrom": "X", "start": 641036, "ref": "C", "alts": "A,T"}
    assert (normalize_locus(snv, None).loci, normalize_locus(snv, None).aligned) == ([snv], True)
    # The authored half: judged per ALT, so the jointly trimmed spelling of the pair reads `false`.
    verdict = spelling_verdict("X", 634689, "CAG", "C,CAGAG", _consumer_join_window)
    assert verdict.verdict is False and verdict.normalized[1] == ("X", 634689, "C", "CAG")


def test_rm270_a_pairs_recorded_locus_is_judged_and_kept_in_the_links_spelling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """A row authoring both an rsID and a coordinate: the reference's locus is recorded beside the
    authored one for the compiler's spelling comparison (S104), so respelling it would manufacture an
    agreement or a disagreement the sources never stated. It is judged and kept as the link gave it."""
    spec = _spec(tmp_path, {"rs72613567": "T/TA"}, pairs={"rs72613567": ENSEMBL["rs72613567"]})
    result = _enrich(spec, tmp_path, monkeypatch, resolver=_NoLiveEnsembl(rest_unreachable=True))
    (row,) = result.rows
    assert ((row.chrom, row.start, row.ref, row.alts), row.left_aligned) == (ENSEMBL["rs72613567"], False)
    assert result.spelling is not None and result.spelling.respelled == []
    assert result.spelling.findings == ["rs72613567: 4:87310241 A>AA → 4:87310240 T>TA"]


@pytest.mark.parametrize(
    ("genotype", "written"),
    [
        # Spelled in the source locus's own frame: the genotype names the deletion, never the duplication.
        ("AG/AGAG", [("X", 634689, "CAG", "C")]),
        # Naming both ALTs: no one left-aligned locus holds them, so the source is written whole.
        ("AG/AGAGAG", [("X", 634690, "AGAG", "AG,AGAGAG")]),
        # Not in the source's frame, and either reading fits: both pieces, as the source fitted.
        ("C/CAG", [("X", 634689, "CAG", "C"), ("X", 634689, "C", "CAG")]),
    ],
)
def test_rm270_a_split_writes_the_piece_the_genotype_is_about(genotype: str, written: list[tuple]) -> None:
    """The source locus passed the hosting filter as one site; after the split each piece must carry the
    alleles the row's genotype names, or a compound het of the two ALTs would lose its only locus."""
    shox = {"chrom": "X", "start": 634690, "ref": "AGAG", "alts": "AG,AGAGAG"}
    pieces = _filled_pieces(genotype, shox, _consumer_join_window)
    assert [(p["chrom"], p["start"], p["ref"], p["alts"]) for p, _ in pieces] == written
    expected = written[0][1] != 634690
    assert {aligned for _, aligned in pieces} == {expected}


def test_rm270_a_respelling_on_rederive_is_not_reported_as_the_source_moving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """The drift canary compares facts, and a left-aligned fill moves `start`/`ref`/`alts`. With every
    allele's id the same on both sides it is the same event spelled this release's way, named apart."""
    spec = _spec(tmp_path, {"rs72613567": "T/TA", "rs4988235": "A/G"})
    chrom, start, ref, alt = ENSEMBL["rs72613567"]
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,vrs_id,vrs_spec,source,status\n"
        f"rs72613567,rs72613567,{chrom},{start},{ref},{alt},GRCh38,0,{HSD17B13_ID},2.0,cache,resolved\n"
        # A recorded answer the source no longer gives: real drift, and it must still read as drift.
        "rs4988235,rs4988235,2,135851077,G,A,GRCh38,0,,,cache,resolved\n"
    )
    result = _enrich(
        spec, tmp_path, monkeypatch, resolver=_NoLiveEnsembl(rest_unreachable=True), rederive=True
    )
    assert result.rederived is not None
    assert {(d.variant_key, d.respelled) for d in result.rederived} == {
        ("rs72613567", True),
        ("rs4988235", False),
    }


def test_a_reporting_source_record_names_its_reporter_only_once_a_reporter_is_a_witness() -> None:
    """`_reporting_side`'s arms, through the record the model derives `independence` on."""

    def record(reported_by: set[str], witness: str):
        return ran(
            "placement_agreement",
            subjects=1,
            findings=0,
            witness_source=witness,
            undecided=0,
            reported_by=reported_by,
        )

    # No reporter is a witness: the record reads as it did before REST, independent.
    plain = record({"ensembl", "gnomad"}, "clinvar+clinvar_gkm")
    assert (plain.checked_source, plain.independence) == ("reporting_source", "independent")
    # The one reporter is the only witness: Ensembl against Ensembl.
    alone = record({"ensembl"}, "ensembl")
    assert (alone.checked_source, alone.independence) == ("ensembl", "self_consistent")
    # Several reporters, one a witness: which side is which is per row, so the checked side withholds.
    mixed = record({"ensembl", "gnomad"}, "clinvar+ensembl")
    assert (mixed.checked_source, mixed.independence) == (None, None)
    with pytest.raises(ValueError, match="reporting_source"):
        ran("reference_allele", subjects=1, findings=0, reported_by={"ensembl"})


def test_a_placement_with_no_licensed_authority_names_no_reporter() -> None:
    """A link outside the authority map reports nothing a record could name, so it cannot make a run's
    checked side look like two reporters."""
    locus = {"chrom": "2", "start": 5, "ref": "G", "alts": "A"}
    check = compare_placements(
        {"rs1": [locus]},
        {"rs1": None},
        {"clinvar": {"rs1": [locus]}},
        mint=_mint(VrsMinter(offline=True)),
        read_window=None,
    )
    assert check.subjects == 1 and check.reported_by == set() and check.placed_by == set()


def test_a_witness_of_the_placements_own_authority_never_counts_as_independent() -> None:
    """A witness asked about a placement of its own authority (REST about the snapshot's) compares, and
    its agreement leaves the rsID with one witness; a loaded witness holding nothing is still named."""
    locus = {"chrom": "2", "start": 5, "ref": "G", "alts": "A"}
    check = compare_placements(
        {"rs1": [locus]},
        {"rs1": "ensembl"},
        {"ensembl": {"rs1": [locus]}, "clinvar_gkm": {}},
        mint=_mint(VrsMinter(offline=True)),
        read_window=None,
        asked_about={"ensembl": {"rs1"}},
    )
    assert check.single_witness == ["rs1"] and check.self_consistent == ["rs1"]
    assert check.row_columns("rs1", locus) == ("clinvar_gkm+ensembl", "same_event")


# ── RM373: a witness's licence row names the witness's release, and a plain re-run keeps it ────


def test_rm373_the_witness_licence_rows_carry_each_lanes_release_and_a_rerun_keeps_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """A witness has no column of its own, so a carried row speaks through the label recorded before.

    Without that, a second run with nothing to do would carry every row, know no witness release for
    any of them, and withdraw a label that is still true: the licence row would flip on a no-op run.
    """
    clinvar = _clinvar_snapshot(tmp_path)
    write_release(clinvar, SnapshotRelease(dataset="clinvar_20260627"))
    gkm = _gkm_snapshot(tmp_path)
    spec = _spec(tmp_path)

    def datasets() -> dict[str, str | None]:
        rows, errors, _ = load_csv_rows(sources_path(spec, error=EnrichmentError), SourceRow, "sources")
        assert errors == []
        return {r.source: r.dataset for r in rows if r.layer == "resolution"}

    _enrich(spec, tmp_path, monkeypatch, clinvar_cache=clinvar, clinvar_gkm_cache=gkm)
    expected = {
        "clinvar": LANES_BY_NAME["clinvar"].release_label(clinvar),
        "clinvar_gkm": LANES_BY_NAME["clinvar_gkm"].release_label(gkm),
        # The fixture's Ensembl snapshot is the old repo's shape: it states no release.
        "ensembl": None,
    }
    assert expected["clinvar"] == "clinvar_20260627" and expected["clinvar_gkm"]
    assert datasets() == expected
    _enrich(spec, tmp_path, monkeypatch, clinvar_cache=clinvar, clinvar_gkm_cache=gkm)
    assert datasets() == expected


def test_rm373_a_rest_witness_contributes_the_release_rest_answered_from(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """2026-11-05, found merging block 3: the witness map was written before REST became a witness.

    A run whose snapshot answered every rsID asks REST nothing as a link, so the release REST answered
    the witness from has to be asked by the witness, once. The licence row stays withheld here, and
    honestly: the row REST witnessed was answered by the snapshot, whose label (none, for this fixture's
    old-repo shape; `…vep116.0` for a split one) is never the same string as REST's `ensembl_116`. What
    moves is the reason — two releases, not an unrecorded one.
    """
    captured: dict[str, list[str | None]] = {}

    def spy(*args, **kwargs):
        captured.update(orchestration_table_releases(*args, **kwargs))
        return captured

    monkeypatch.setattr("just_dna_enricher.enrich.orchestration.table_releases", spy)
    snapshot = _ensembl_snapshot(tmp_path)
    spec = _spec(tmp_path, {"rs77944059": "G/GAAAC"})
    rest = _Rest()
    result = _enrich(spec, tmp_path, monkeypatch, ensembl_cache=snapshot, resolver=rest.resolver())
    (row,) = result.rows
    assert row.placement_witness == "ensembl" and row.source == "cache"
    assert rest.release_asked == 1
    # The snapshot's label as the row's authority, and REST's as its witness: neither is unrecorded.
    assert captured["ensembl"] == [LANES_BY_NAME["ensembl"].release_label(snapshot), "ensembl_116"]
    rows, errors, _ = load_csv_rows(sources_path(spec, error=EnrichmentError), SourceRow, "sources")
    assert errors == []
    assert {r.source: r.dataset for r in rows if r.layer == "resolution"} == {"ensembl": None}


def test_rm373_a_run_using_rest_as_link_and_witness_asks_its_release_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """The live link asked `/info/data` already, so the witness reuses that answer rather than asking again."""
    captured: dict[str, list[str | None]] = {}

    def spy(*args, **kwargs):
        captured.update(orchestration_table_releases(*args, **kwargs))
        return captured

    monkeypatch.setattr("just_dna_enricher.enrich.orchestration.table_releases", spy)
    # `rs1` is in no snapshot, so the live link asks REST about it, which holds no mapping for it.
    spec = _spec(tmp_path, {"rs77944059": "G/GAAAC", "rs1": "A/G"})
    rest = _Rest()
    result = _enrich(spec, tmp_path, monkeypatch, resolver=rest.resolver())
    assert rest.requested == ["rs1", "rs77944059"] and rest.release_asked == 1
    witnessed = [r for r in result.rows if r.placement_witness == "ensembl"]
    assert [r.rsid for r in witnessed] == ["rs77944059"]
    assert "ensembl_116" in captured["ensembl"]
