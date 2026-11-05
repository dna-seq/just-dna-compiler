"""RM373: every resolution row says which release answered it, and a per-run label never speaks for a mixed table.

The 0.8 Ensembl migration probe found that nothing a module records tells an old-release resolution
from a new one: `resolution.csv` named the *link* (`cache`, `ensembl-rest`) and never the release, the
licence rows `enrich` writes left `dataset` blank, and RM372's `rsid_coordinate_agreement.release`
stated the run's snapshot over a table every row of which an older release had answered.

The fixtures are real snapshots in the two shapes the lane serves: the old repo's (no `manifest.json`,
so no label) and the split repo's, whose `manifest.json` is computed from the bytes it attests, so the
cache is served exactly as RM372's read-time check serves the real one.
"""

import hashlib
import io
import json
from pathlib import Path

import httpx
import polars as pl
import pytest
from just_dna_compiler.compiler import _load_csv_rows
from just_dna_enricher.caches import LANES_BY_NAME
from just_dna_enricher.clinvar import clinvar_dataset_label
from just_dna_enricher.enrich import enrich
from just_dna_enricher.enrich.releases import LINKS_WITHOUT_A_RELEASE, link_releases, witness_releases
from just_dna_enricher.ensembl import EnsemblResolver
from just_dna_enricher.licensing import (
    RESOLUTION_AUTHORITY_BY_LINK,
    record_table_sources,
    sources_path,
    table_release,
    write_sources_csv,
)
from just_dna_enricher.locations import SNAPSHOT_MANIFEST_FILENAME
from just_dna_enricher.placement import _NOT_INDEPENDENT, ENSEMBL_WITNESS, PLACEMENT_WITNESSES
from just_dna_enricher.verification import CHECK_WITNESSES
from just_dna_format.integrity import resolution_signature
from just_dna_format.layout import SOURCES_CSV, VERIFICATION_JSON, preferred_spelling
from just_dna_format.resolution import RESOLUTION_FACT_FIELDS, ResolutionRow
from just_dna_format.sources import SourceRow
from just_dna_format.verification import read_verification

_LICENCE_CSV = preferred_spelling(SOURCES_CSV)
_NEW = "ensembl-variation-2026_07_13-vep116.0"
_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)
#: rsID → (chrom, start, ref, alt), the GRCh38 VCF spellings both releases agree on.
_OLD_SITES = {"rs1801133": ("1", 11796321, "G", "A"), "rs429358": ("19", 44908684, "T", "C")}
_NEW_SITES = {**_OLD_SITES, "rs7412": ("19", 44908822, "C", "T")}


def _parquet(frame: pl.DataFrame) -> bytes:
    buf = io.BytesIO()
    frame.write_parquet(buf)
    return buf.getvalue()


def _snapshot(root: Path, sites: dict[str, tuple[str, int, str, str]], *, release_id: str | None) -> Path:
    """An Ensembl snapshot: the split repo's when `release_id` is given (a manifest attesting the bytes)."""
    body = _parquet(
        pl.DataFrame(
            {
                "id": list(sites),
                "chrom": [s[0] for s in sites.values()],
                "start": [s[1] for s in sites.values()],
                "ref": [s[2] for s in sites.values()],
                "alt": [s[3] for s in sites.values()],
            }
        )
    )
    (root / "data").mkdir(parents=True)
    (root / "data" / "homo_sapiens-chr.parquet").write_bytes(body)
    if release_id is not None:
        manifest = {
            "release_id": release_id,
            "layout_version": 1,
            "files": [
                {
                    "path": "data/homo_sapiens-chr.parquet",
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
            ],
        }
        (root / SNAPSHOT_MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    return root


@pytest.fixture
def old(tmp_path: Path) -> Path:
    """The old repo's bytes: no manifest, so the snapshot states no release."""
    return _snapshot(tmp_path / "old", _OLD_SITES, release_id=None)


@pytest.fixture
def new(tmp_path: Path) -> Path:
    return _snapshot(tmp_path / "new", _NEW_SITES, release_id=_NEW)


def _spec(root: Path, rows: list[str]) -> Path:
    spec = root / "spec"
    spec.mkdir(exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(
        "rsid,chrom,start,ref,genotype,state,conclusion\n" + "".join(f"{r},risk,c\n" for r in rows),
        encoding="utf-8",
    )
    (spec / "studies.csv").write_text("rsid,pmid\nrs1801133,9545397\n", encoding="utf-8")
    return spec


#: rs429358 authors both halves, so the run's `rsid_coordinate_agreement` check has a pair to compare.
_FIRST = ["rs1801133,,,,A/G", "rs429358,19,44908684,T,C/T"]
_SECOND = [*_FIRST, "rs7412,,,,C/T"]


def _enrich(spec: Path, cache: Path, **kwargs):
    options = {
        "offline": True,
        "ensembl_cache": cache,
        "clinvar_cache": spec.parent / "no-clinvar",
        "download": False,
        "use_gnomad": False,
        "verify_ref": False,
        "verify_rsids": False,
        "verify_clinsig": False,
        "mint_vrs": False,
    }
    options.update(kwargs)
    return enrich(spec, **options)


def _releases(spec: Path) -> dict[str, str | None]:
    rows, errors, _ = _load_csv_rows(spec / "resolution.csv", ResolutionRow, "resolution.csv")
    assert errors == []
    return {r.variant_key: r.source_release for r in rows}


def _dataset(spec: Path, source: str) -> str | None:
    rows, errors, _ = _load_csv_rows(spec / _LICENCE_CSV, SourceRow, _LICENCE_CSV)
    assert errors == []
    (row,) = [r for r in rows if (r.source, r.layer) == (source, "resolution")]
    return row.dataset


def _pair_record(spec: Path):
    (record,) = [
        r
        for r in read_verification(spec / VERIFICATION_JSON).records
        if r.check == "rsid_coordinate_agreement"
    ]
    return record


# ── the helper ─────────────────────────────────────────────────────────────────────────────────


def test_a_table_has_a_release_only_when_every_row_states_the_same_one() -> None:
    assert table_release(["r1", "r1"]) == "r1"
    # Two releases, an unrecorded row, an empty table: one cell cannot name any of them.
    assert table_release(["r1", "r2"]) is None
    assert table_release(["r1", None]) is None
    assert table_release(["r1", "  "]) is None
    assert table_release([]) is None


def test_the_column_is_provenance_outside_the_fact_signature() -> None:
    """A release that answered is said *beside* the fact; two releases agreeing on a fact hash equal."""
    assert "source_release" not in RESOLUTION_FACT_FIELDS
    fact = {"variant_key": "rs1", "rsid": "rs1", "chrom": "1", "start": 5, "ref": "G", "alts": "A"}
    a = resolution_signature([ResolutionRow(**fact, source_release="r1")])
    b = resolution_signature([ResolutionRow(**fact, source_release="r2")])
    assert a == b == resolution_signature([ResolutionRow(**fact)])


# ── a fresh run ────────────────────────────────────────────────────────────────────────────────


def test_every_row_the_cache_answered_records_the_snapshots_release(new: Path, tmp_path: Path) -> None:
    spec = _spec(tmp_path, [*_SECOND, ",1,999,A,A/T"])
    _enrich(spec, new)
    releases = _releases(spec)
    lane_label = LANES_BY_NAME["ensembl"].release_label(new)
    assert lane_label == _NEW
    assert {k: v for k, v in releases.items() if k.startswith("rs")} == {
        "rs1801133": lane_label,
        "rs429358": lane_label,
        "rs7412": lane_label,
    }
    # A coordinate no link answered is the module's own bytes: no release answered it.
    (authored,) = [v for k, v in releases.items() if not k.startswith("rs")]
    assert authored is None
    # The licence row says the same, through the lane's own label, and so does the run's record.
    assert _dataset(spec, "ensembl") == lane_label
    assert _pair_record(spec).release == lane_label


def test_a_snapshot_that_states_no_release_records_none_never_a_guess(old: Path, tmp_path: Path) -> None:
    spec = _spec(tmp_path, _FIRST)
    _enrich(spec, old)
    assert set(_releases(spec).values()) == {None}
    assert _dataset(spec, "ensembl") is None
    assert _pair_record(spec).release is None


# ── merge-not-clobber: the case the probe measured ────────────────────────────────────────────


def test_reenriching_an_old_table_keeps_its_rows_unlabelled_and_withholds_the_runs_label(
    old: Path, new: Path, tmp_path: Path
) -> None:
    """X372_cpic: every row the old release's, re-enriched against the new one without deleting.

    The old rows stay exactly as recorded, with no release; the one new subject is the new release's.
    The run's record withholds its label with the count behind it, and the licence row names no release,
    because one cell cannot name a table two releases answered.
    """
    spec = _spec(tmp_path, _FIRST)
    _enrich(spec, old)
    _spec(tmp_path, _SECOND)
    _enrich(spec, new)

    assert _releases(spec) == {"rs1801133": None, "rs429358": None, "rs7412": _NEW}
    assert _dataset(spec, "ensembl") is None
    record = _pair_record(spec)
    assert record.skipped is None and record.release is None
    assert "release withheld: 2 of 3 snapshot-answered row(s)" in record.detail
    assert "0 answered by another release, 2 recording none" in record.detail


def test_a_pre_0_8_table_without_the_column_is_never_back_filled(new: Path, tmp_path: Path) -> None:
    spec = _spec(tmp_path, _FIRST)
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,authority,status\n"
        "rs1801133,rs1801133,1,11796321,G,A,GRCh38,0,cache,ensembl,resolved\n"
        "rs429358,rs429358,19,44908684,T,C,GRCh38,0,cache,ensembl,resolved\n",
        encoding="utf-8",
    )
    _enrich(spec, new)
    assert _releases(spec) == {"rs1801133": None, "rs429358": None}
    assert _pair_record(spec).release is None


def test_a_row_another_release_answered_is_counted_apart_from_an_unrecorded_one(
    new: Path, tmp_path: Path
) -> None:
    spec = _spec(tmp_path, _FIRST)
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,authority,status,source_release\n"
        "rs1801133,rs1801133,1,11796321,G,A,GRCh38,0,cache,ensembl,resolved,ensembl-variation-2025_01_01\n"
        "rs429358,rs429358,19,44908684,T,C,GRCh38,0,cache,ensembl,resolved,\n",
        encoding="utf-8",
    )
    _enrich(spec, new)
    assert _releases(spec) == {"rs1801133": "ensembl-variation-2025_01_01", "rs429358": None}
    assert "1 answered by another release, 1 recording none" in _pair_record(spec).detail


def test_rederive_reanswers_every_row_and_the_label_returns(old: Path, new: Path, tmp_path: Path) -> None:
    spec = _spec(tmp_path, _FIRST)
    _enrich(spec, old)
    _spec(tmp_path, _SECOND)
    _enrich(spec, new)
    _enrich(spec, new, rederive=True)
    assert _releases(spec) == {"rs1801133": _NEW, "rs429358": _NEW, "rs7412": _NEW}
    assert _dataset(spec, "ensembl") == _NEW
    record = _pair_record(spec)
    assert record.release == _NEW and "withheld" not in (record.detail or "")


def test_a_rederive_that_cannot_ask_keeps_the_old_release_on_the_rows_it_carries(
    new: Path, tmp_path: Path
) -> None:
    """`@rederive-never-shortens`: a subject no source could be asked about keeps its rows, release included."""
    spec = _spec(tmp_path, ["rs1801133,,,,A/G"])
    _enrich(spec, new)
    _enrich(spec, tmp_path / "no-cache", rederive=True)
    assert _releases(spec) == {"rs1801133": _NEW}


# ── the live link ──────────────────────────────────────────────────────────────────────────────


def test_a_live_rest_answer_records_the_data_release_rest_reports(tmp_path: Path) -> None:
    """Asked once per run, of `/info/data` (`{"releases": [116]}`, read by hand on 2026-11-04)."""
    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(request.url.path)
        if "graphql" in str(request.url):
            return httpx.Response(503, text="beta down")
        if request.url.path == "/info/data":
            return httpx.Response(200, json={"releases": [116]})
        rsid = request.url.path.rsplit("/", 1)[-1]
        chrom, start, ref, alt = _NEW_SITES[rsid]
        mapping = {"seq_region_name": chrom, "start": start, "allele_string": f"{ref}/{alt}"}
        return httpx.Response(200, json={"name": rsid, "mappings": [{**mapping, "assembly_name": "GRCh38"}]})

    resolver = EnsemblResolver()
    resolver._client = httpx.Client(transport=httpx.MockTransport(handler))
    spec = _spec(tmp_path, ["rs1801133,,,,A/G", "rs7412,,,,C/T"])
    _enrich(spec, tmp_path / "no-cache", offline=False, resolver=resolver, verify_datasets=False)
    assert _releases(spec) == {"rs1801133": "ensembl_116", "rs7412": "ensembl_116"}
    assert asked.count("/info/data") == 1
    assert _dataset(spec, "ensembl") == "ensembl_116"


def test_a_release_the_service_will_not_state_is_none(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "graphql" in str(request.url):
            return httpx.Response(503, text="beta down")
        if request.url.path == "/info/data":
            return httpx.Response(200, json={"releases": [115, 116]})
        chrom, start, ref, alt = _NEW_SITES["rs1801133"]
        mapping = {"seq_region_name": chrom, "start": start, "allele_string": f"{ref}/{alt}"}
        return httpx.Response(
            200, json={"name": "rs1801133", "mappings": [{**mapping, "assembly_name": "GRCh38"}]}
        )

    resolver = EnsemblResolver()
    resolver._client = httpx.Client(transport=httpx.MockTransport(handler))
    spec = _spec(tmp_path, ["rs1801133,,,,A/G"])
    _enrich(spec, tmp_path / "no-cache", offline=False, resolver=resolver, verify_datasets=False)
    assert _releases(spec) == {"rs1801133": None}


# ── the review round (RM373, 2026-11-05) ───────────────────────────────────────────────────────


def _rest_handler(asked: list[str] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if asked is not None:
            asked.append(request.url.path)
        if "graphql" in str(request.url):
            return httpx.Response(503, text="beta down")
        if request.url.path == "/info/data":
            return httpx.Response(200, json={"releases": [116]})
        rsid = request.url.path.rsplit("/", 1)[-1]
        chrom, start, ref, alt = _LIVE_ONLY.get(rsid) or _NEW_SITES[rsid]
        mapping = {"seq_region_name": chrom, "start": start, "allele_string": f"{ref}/{alt}"}
        return httpx.Response(200, json={"name": rsid, "mappings": [{**mapping, "assembly_name": "GRCh38"}]})

    return handler


#: An rsID the snapshots do not hold, so only the live link can answer it.
_LIVE_ONLY = {"rs1061170": ("1", 196690107, "T", "C")}


def test_rest_rows_beside_snapshot_rows_leave_the_snapshots_label_standing(new: Path, tmp_path: Path) -> None:
    """The run's record speaks for the rows its snapshot answered; REST's rows carry their own release.

    The two links spell one Ensembl release two ways (`…vep116.0` and `ensembl_116`) and nothing here can
    equate them, so the licence row, which names the table, is still withheld. The record is not: it is
    the snapshot's, and every row the snapshot answered is this release's.
    """
    resolver = EnsemblResolver()
    resolver._client = httpx.Client(transport=httpx.MockTransport(_rest_handler()))
    spec = _spec(tmp_path, [*_FIRST, "rs1061170,,,,C/T"])
    _enrich(spec, new, offline=False, resolver=resolver, verify_datasets=False)
    assert _releases(spec) == {"rs1801133": _NEW, "rs429358": _NEW, "rs1061170": "ensembl_116"}
    record = _pair_record(spec)
    assert record.release == _NEW and "withheld" not in (record.detail or "")
    assert _dataset(spec, "ensembl") is None


class _RaisingRelease:
    """A host's resolver: it answers rsIDs and its release call fails in its own way."""

    def resolve_rsid(self, rsid: str):
        chrom, start, ref, alt = _LIVE_ONLY[rsid]
        return [{"chrom": chrom, "start": start, "ref": ref, "alts": alt}], "ensembl-rest"

    def data_release(self) -> str | None:
        raise RuntimeError("the host's own failure")

    def close(self) -> None:
        return None


def test_a_hosts_resolver_is_never_asked_for_a_release(tmp_path: Path) -> None:
    """An optional provenance label may not abort a run whose answers are already in."""
    spec = _spec(tmp_path, ["rs1061170,,,,C/T"])
    _enrich(spec, tmp_path / "no-cache", offline=False, resolver=_RaisingRelease(), verify_datasets=False)
    assert _releases(spec) == {"rs1061170": None}


class _Gnomad:
    """gnomAD's link: it answers from a dataset id that names a release line, never a release."""

    settings = type("S", (), {"dataset": "gnomad_r4"})()
    unanswered: dict = {}

    def resolve_rsids(self, rsids: list[str]) -> dict[str, list[dict]]:
        chrom, start, ref, alt = _LIVE_ONLY["rs1061170"]
        return {r: [{"chrom": chrom, "start": start, "ref": ref, "alts": alt}] for r in rsids}

    def close(self) -> None:
        return None


class _NoLive:
    def resolve_rsid(self, rsid: str):
        return [], "ensembl-rest"

    def close(self) -> None:
        return None


def test_a_gnomad_answer_records_no_release(tmp_path: Path) -> None:
    spec = _spec(tmp_path, ["rs1061170,,,,C/T"])
    _enrich(
        spec,
        tmp_path / "no-cache",
        offline=False,
        resolver=_NoLive(),
        use_gnomad=True,
        gnomad_client=_Gnomad(),
        verify_datasets=False,
    )
    rows, errors, _ = _load_csv_rows(spec / "resolution.csv", ResolutionRow, "resolution.csv")
    assert errors == [] and [(r.source, r.source_release) for r in rows] == [("gnomad", None)]


def _clinvar(root: Path, release: dict | None) -> Path:
    """A ClinVar snapshot holding only rs1061170, so ClinVar's link answers it."""
    chrom, start, ref, alt = _LIVE_ONLY["rs1061170"]
    (root / "data").mkdir(parents=True)
    pl.DataFrame(
        {"rsid": ["rs1061170"], "chrom": [chrom], "start": [start], "ref": [ref], "alt": [alt]}
    ).write_parquet(root / "data" / "c.parquet")
    if release is not None:
        (root / "release.json").write_text(json.dumps(release), encoding="utf-8")
    return root


def test_a_clinvar_answer_records_the_label_every_clinvar_reader_computes(new: Path, tmp_path: Path) -> None:
    """`clinvar_dataset_label` is the one spelling: a digest-only snapshot is named by its digest."""
    clinvar = _clinvar(tmp_path / "clinvar", {"source_sha256": "sha256:" + "ab" * 32})
    spec = _spec(tmp_path, ["rs1801133,,,,A/G", "rs1061170,,,,C/T"])
    _enrich(spec, new, clinvar_cache=clinvar)
    expected = clinvar_dataset_label(clinvar)
    assert expected == "clinvar_sha256:" + "ab" * 32
    assert _releases(spec)["rs1061170"] == expected


def test_a_source_publishing_past_the_snapshot_never_makes_strict_refuse(
    new: Path, tmp_path: Path, caplog
) -> None:
    """`@a-source-recuring-is-not-a-strict-matter`: no authored edit clears it, so it warns in both modes.

    The first run records ClinVar's release on the resolution layer; the second, strict, finds live ClinVar
    has published since. It stays green, and the warning names the remedy a derived table has.
    """
    clinvar = _clinvar(tmp_path / "clinvar", {"dataset": "clinvar_2026-06-27"})
    spec = _spec(tmp_path, ["rs1801133,,,,A/G", "rs1061170,,,,C/T"])
    options = {
        "clinvar_cache": clinvar,
        "offline": False,
        "resolver": _NoLive(),
        "release_probes": {"clinvar": lambda: "clinvar_2026-11-01"},
    }
    _enrich(spec, new, **options)
    assert _dataset(spec, "clinvar") == "clinvar_2026-06-27"
    with caplog.at_level("WARNING"):
        _enrich(spec, new, mode="strict", **options)
    assert "enrich --rederive" in caplog.text and "re-draft" not in caplog.text.lower()


def test_a_curators_row_for_a_source_with_no_terms_is_never_restamped(tmp_path: Path) -> None:
    """`record_table_sources` stamps only the rows it writes; `manual` has no terms constant, so none."""
    spec = tmp_path / "spec"
    spec.mkdir()
    path = sources_path(spec, error=RuntimeError)
    write_sources_csv([SourceRow(source="manual", layer="frequency", dataset="my_curation_v2")], path)
    record_table_sources(
        {"manual": [None], "gnomad": ["gnomad_v4.1_joint"]}, "frequency", spec, error=RuntimeError
    )
    rows, errors, _ = _load_csv_rows(path, SourceRow, path.name)
    assert errors == []
    assert {r.source: r.dataset for r in rows} == {"manual": "my_curation_v2", "gnomad": "gnomad_v4.1_joint"}


# ── the release maps cover their registries (2026-11-05, found merging block 3) ─────────────────
#
# The witness map was a hand-kept dict naming `clinvar` and `clinvar_gkm`, written before RM267 made
# Ensembl REST a witness, so every REST-witnessed row contributed no release. Each map keyed by a
# registry's members is now checked against the registry, with every exclusion named and given a reason.


def test_the_witness_release_map_must_name_every_placement_witness_and_nothing_else() -> None:
    full = {witness: f"{witness}_release" for witness in PLACEMENT_WITNESSES}
    assert witness_releases(full) == full
    for witness in PLACEMENT_WITNESSES:
        with pytest.raises(ValueError, match=f"missing \\['{witness}'\\]"):
            witness_releases({w: r for w, r in full.items() if w != witness})
    with pytest.raises(ValueError, match="unknown \\['pubmind'\\]"):
        witness_releases({**full, "pubmind": None})


def test_the_link_release_map_must_name_every_link_with_an_authority_bar_the_named_exclusions() -> None:
    # An exclusion naming a link the registry does not hold is a reason about nothing.
    assert set(LINKS_WITHOUT_A_RELEASE) <= set(RESOLUTION_AUTHORITY_BY_LINK)
    stamped = set(RESOLUTION_AUTHORITY_BY_LINK) - set(LINKS_WITHOUT_A_RELEASE)
    full = dict.fromkeys(stamped)
    assert link_releases(full) == full
    for link in stamped:
        with pytest.raises(ValueError, match="missing"):
            link_releases({k: v for k, v in full.items() if k != link})
    for excluded in LINKS_WITHOUT_A_RELEASE:
        with pytest.raises(ValueError, match="unknown"):
            link_releases({**full, excluded: None})


def test_every_map_keyed_by_placement_witness_names_the_same_witnesses() -> None:
    """The two other witness-keyed tables in this tier, each against the roster, exclusions named."""
    assert set(CHECK_WITNESSES["placement_agreement"].witness) == PLACEMENT_WITNESSES
    # `_NOT_INDEPENDENT` is read with a default: a witness absent from it is asked about placements of
    # its own authority. That is REST's design (RM292: it compares, and is counted self-consistent), so
    # it is the one named exclusion; any other witness has to say whom it may not speak for.
    asked_of_its_own_authority = {ENSEMBL_WITNESS: "REST against the snapshot is compared, never independent"}
    assert set(_NOT_INDEPENDENT) | set(asked_of_its_own_authority) == PLACEMENT_WITNESSES
    assert not set(_NOT_INDEPENDENT) & set(asked_of_its_own_authority)
