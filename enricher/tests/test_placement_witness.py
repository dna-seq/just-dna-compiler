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
from pathlib import Path

import polars as pl
import pytest
from ga4gh.vrs.dataproxy import _DataProxy
from just_dna_compiler.compiler import compile_module, load_csv_rows
from just_dna_enricher.caches import LANES_BY_NAME
from just_dna_enricher.clinvar_gkm import ALLELE_FILE, VARIATION_FILE, WITNESS_PARQUET, parse_manifest
from just_dna_enricher.clinvar_gkm_build import build_snapshot
from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.enrich.orchestration import _filled_pieces
from just_dna_enricher.enrich.resolution_csv import _write_resolution_csv
from just_dna_enricher.licensing import sources_path
from just_dna_enricher.placement import Allele, compare_placements, same_event
from just_dna_enricher.sequences import SequenceProxy, normalize_locus, spelling_verdict
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
    """Every rsID here is in the snapshot, so a live request is a defect in the test's arrangement."""

    def resolve_rsid(self, rsid: str):
        raise AssertionError(f"live Ensembl asked about {rsid}")

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
    result = _enrich(spec, tmp_path, monkeypatch, clinvar_gkm_cache=tmp_path / "gkm")
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
    result = _enrich(spec, tmp_path, monkeypatch)
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
    (row,) = _enrich(spec, tmp_path, monkeypatch).rows
    assert (row.start, row.left_aligned) == (start, None)
    (row,) = _enrich(spec, tmp_path, monkeypatch, rederive=True).rows
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
    result = _enrich(spec, tmp_path, monkeypatch)
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
    result = _enrich(spec, tmp_path, monkeypatch, rederive=True)
    assert result.rederived is not None
    assert {(d.variant_key, d.respelled) for d in result.rederived} == {
        ("rs72613567", True),
        ("rs4988235", False),
    }


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
