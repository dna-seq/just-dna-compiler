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

import hashlib
import json
from pathlib import Path

import polars as pl
import pytest
from ga4gh.vrs.dataproxy import _DataProxy
from just_dna_compiler.compiler import load_csv_rows
from just_dna_enricher.clinvar_gkm import ALLELE_FILE, VARIATION_FILE, WITNESS_PARQUET, parse_manifest
from just_dna_enricher.clinvar_gkm_build import build_snapshot
from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.licensing import sources_path
from just_dna_enricher.placement import Allele, compare_placements, same_event
from just_dna_enricher.sequences import SequenceProxy
from just_dna_enricher.vrs import VrsMinter
from just_dna_format.integrity import resolution_signature
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vrs import refget_accession

SLICE = Path(__file__).resolve().parents[2] / "assets" / "clinvar_gkm_slice"

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
    # The respellings: written at Ensembl's spelling, the witness recorded on the row.
    for rsid, vrs_id in (("rs72613567", HSD17B13_ID), ("rs77944059", RS77944059_ID)):
        row = rows[rsid]
        assert (row.chrom, row.start, row.ref, row.alts) == ENSEMBL[rsid]
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
        assert ResolutionRow(variant_key="rs1", placement_verdict=verdict).placement_verdict == verdict
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
