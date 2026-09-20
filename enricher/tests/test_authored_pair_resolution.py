"""A row that authors both an rsID and a coordinate is resolved from the reference, not copied (S104, RM251).

`enrich()` had a verbatim branch for such a row — *"already complete, or has a position — a full
record, nothing to resolve"* — that wrote the authored coordinate into `resolution.csv` under
`source="authored"`. But the same run had already looked the rsID up: the pair check
(`rsid_coordinate_agreement`) rides its rsIDs in the Ensembl cache batch, so the loci were in hand and
thrown away. The cost landed on every CPIC-drafted module, whose `haplotypes.csv` carries `rsid`,
`chrom` and `start` from `allele_definitions`: no `ref`, no `alts`, nothing to mint a VRS id from, and
the compiler's own cross-check comparing the module against a photocopy of itself.

The reference here is the same tiny synthetic `ensembl_variations` parquet the pair-check tests use,
carried in this file rather than imported: no test module imports another.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module
from just_dna_enricher.enrich import enrich
from just_dna_format import verification as verification_module

_EASY = 8
_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)
_HEADER = "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"


@pytest.fixture(autouse=True)
def _cheap_proof_of_work(monkeypatch):
    monkeypatch.setattr(verification_module, "VERIFICATION_DIFFICULTY_BITS", _EASY)


@pytest.fixture(autouse=True)
def _no_machine_caches(monkeypatch, tmp_path: Path) -> None:
    """`ensembl_cache=None` means *the machine's snapshot*, never *no snapshot* — point it nowhere."""
    absent = tmp_path / "no-such-cache"
    monkeypatch.setenv("JUST_DNA_ENSEMBL_CACHE", str(absent))
    monkeypatch.setenv("JUST_DNA_CLINVAR_CACHE", str(absent))
    monkeypatch.setenv("JUST_DNA_PIPELINES_CACHE_DIR", str(absent))


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    """Two real loci at their real GRCh38 positions: MTHFR c.677C>T and APOE rs429358."""
    data = tmp_path / "cache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {
            "id": ["rs1801133", "rs429358"],
            "chrom": ["1", "19"],
            "start": [11796321, 44908684],
            "ref": ["G", "T"],
            "alt": ["A", "C"],
        }
    ).write_parquet(data / "chr.parquet")
    return tmp_path / "cache"


def _spec(tmp_path: Path, rows: str) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(_HEADER + rows, encoding="utf-8")
    # A variants.csv module compiles only with grounding; one study row per rsID is enough.
    rsids = [line.split(",")[0] for line in rows.splitlines() if line]
    (spec / "studies.csv").write_text(
        "rsid,pmid\n" + "".join(f"{r},8696333\n" for r in rsids), encoding="utf-8"
    )
    return spec


def _haplotype_spec(tmp_path: Path, rows: str) -> Path:
    """The CPIC-drafted shape: `rsid`, `chrom` and `start`, no `ref`."""
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "haplotypes.csv").write_text(
        "haplotype_name,rsid,chrom,start,allele,gene\n" + rows, encoding="utf-8"
    )
    return spec


def _enrich(spec: Path, cache: Path | None, **over):
    # `verify_rsids=False` keeps dbSNP off the wire; minting stays on, since the id is the point.
    return enrich(spec, offline=True, ensembl_cache=cache, verify_rsids=False, **over)


def test_an_agreeing_pair_is_recorded_from_the_reference_with_its_alleles(
    tmp_path: Path, cache: Path
) -> None:
    """The authored pair agrees with the snapshot; the table now says what the snapshot said, and
    carries the two things the authored row never had — `ref`/`alts` and a minted VRS id."""
    spec = _spec(tmp_path, "rs1801133,1,11796321,G,A,A/G,risk,agrees\n")
    result = _enrich(spec, cache)

    [row] = result.rows
    assert (row.source, row.status) == ("cache", "resolved")
    assert (row.chrom, row.start, row.ref, row.alts) == ("1", 11796321, "G", "A")
    assert row.vrs_id is not None and row.vrs_id.startswith("ga4gh:VA.")
    assert result.unresolved == []


def test_the_cpic_shape_gains_ref_and_a_vrs_id_and_the_compile_stops_warning(
    tmp_path: Path, cache: Path
) -> None:
    """S104's actual report: `rsid + chrom + start`, no `ref`, drafted for every CPIC allele.

    Before: `source=authored`, `vrs_minted: 0`, and *"VRS allele identity covers 0/N"* on every
    compile with nothing the author could do. After: the reference's `ref`/`alts`, an id, and the
    positional fill gives `haplotypes.parquet` the `ref` the author left empty.
    """
    spec = _haplotype_spec(tmp_path, "*2,rs1801133,1,11796321,A,MTHFR\n")
    result = _enrich(spec, cache)

    [row] = result.rows
    assert (row.source, row.ref, row.alts) == ("cache", "G", "A")
    assert row.vrs_id is not None

    compiled = compile_module(spec, tmp_path / "out")
    assert compiled.success, compiled.errors
    assert not any("VRS allele identity covers" in str(w) for w in compiled.warnings), compiled.warnings
    assert not any("maps it to" in str(w) for w in compiled.warnings), compiled.warnings


def test_a_disagreeing_pair_records_the_reference_and_the_compiler_sees_it(
    tmp_path: Path, cache: Path
) -> None:
    """The finding the verbatim branch could never produce: the table holds the reference's locus,
    the module keeps the authored one, and the compiler's `_verify` — which compared the module
    against a copy of itself until now — warns in `best_effort` and refuses in `strict`."""
    spec = _spec(tmp_path, "rs429358,19,999,T,C,C/T,risk,authored at the wrong place\n")
    result = _enrich(spec, cache)

    [row] = result.rows
    assert (row.source, row.chrom, row.start) == ("cache", "19", 44908684)  # the reference's, not 999

    compiled = compile_module(spec, tmp_path / "out")
    assert compiled.success, compiled.errors
    assert any("maps it to" in str(w) for w in compiled.warnings), compiled.warnings
    refused = compile_module(spec, tmp_path / "out-strict", strict=True)
    assert not refused.success
    assert any("maps it to" in e for e in refused.errors), refused.errors


def test_a_pair_the_reference_does_not_know_stays_authored(tmp_path: Path, cache: Path) -> None:
    """No answer to record and no negative to fabricate: the authored record is the whole fact."""
    spec = _spec(tmp_path, "rs999999999,2,100,G,A,A/G,risk,unknown to the snapshot\n")
    result = _enrich(spec, cache)

    [row] = result.rows
    assert (row.source, row.status, row.chrom, row.start) == ("authored", "resolved", "2", 100)
    assert result.unresolved == []


def test_a_pair_whose_allele_no_reference_locus_can_host_stays_authored_and_is_a_finding(
    tmp_path: Path, cache: Path
) -> None:
    """The pair case of the allele-aware filter: the reference knows the rsID at a locus offering
    `G>A`, the row states `T`. Nothing hosts it, so the authored row is kept — it still has a
    coordinate, so it is neither `not_found` nor unresolved — and the mismatch is reported."""
    spec = _haplotype_spec(tmp_path, "*2,rs1801133,1,11796321,T,MTHFR\n")
    result = _enrich(spec, cache)

    [row] = result.rows
    assert (row.source, row.status, row.start) == ("authored", "resolved", 11796321)
    assert [m.rsid for m in result.allele_mismatches] == ["rs1801133"]
    assert result.unresolved == []


def test_with_no_reference_at_all_the_pair_is_transcribed_as_before(tmp_path: Path) -> None:
    """The pair check is snapshot-only, so with no snapshot nothing was asked and nothing changes."""
    spec = _spec(tmp_path, "rs1801133,1,11796321,G,A,A/G,risk,no snapshot on this machine\n")
    result = _enrich(spec, None)

    [row] = result.rows
    assert (row.source, row.status) == ("authored", "resolved")


def test_re_running_over_the_recorded_rows_is_a_no_op(tmp_path: Path, cache: Path) -> None:
    """Merge-not-clobber: the recorded subject is covered, so a second run neither re-asks nor
    rewrites — the bytes are the same (P7)."""
    spec = _spec(tmp_path, "rs1801133,1,11796321,G,A,A/G,risk,agrees\n")
    _enrich(spec, cache)
    first = (spec / "resolution.csv").read_bytes()
    _enrich(spec, cache)
    assert (spec / "resolution.csv").read_bytes() == first
