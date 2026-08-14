"""The rsid↔coordinate check `enrich()` puts, and the record it attests (D4-1, RM45).

`VALID_VERIFICATION_CHECKS.rsid_coordinate_agreement` was emitted by nothing. The vocabulary's own
comment pointed at `resolver._check_rsid_coord_consistency` as its emitter, and that function lives on
`resolve_variants` — the deprecated DuckDB path whose only non-test caller is the compiler, a tier that
must not attest. `enrich()` never ran the comparison at all: a subject authoring both an rsID and a
coordinate needs no resolution, so it fell through to the verbatim branch and nothing looked at it.

So the tests here pin two things at once — that the comparison happens, and that the record never
overstates it. The second is F4's lesson from this same batch: a check that could not run must land
under a skip reason, never as `subjects 0, findings 0, skipped null`.

Network-free: the reference is the same tiny synthetic `ensembl_variations` parquet the resolver unit
tests inject, and every run is `offline=True`.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher.enrich import enrich
from just_dna_format import verification as verification_module
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.manifest import VerificationRecord
from just_dna_format.verification import read_verification

_CHECK = "rsid_coordinate_agreement"
_EASY = 8

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)
_HEADER = "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"


@pytest.fixture(autouse=True)
def _cheap_proof_of_work(monkeypatch):
    monkeypatch.setattr(verification_module, "VERIFICATION_DIFFICULTY_BITS", _EASY)


@pytest.fixture(autouse=True)
def _no_machine_caches(monkeypatch, tmp_path: Path) -> None:
    """`ensembl_cache=None` means *the machine's snapshot*, never *no snapshot* — neutralize it.

    F10's lesson from this same batch, arriving from the other side: `resolve_ensembl_reference(None)`
    walks `$JUST_DNA_ENSEMBL_CACHE`, then `$JUST_DNA_PIPELINES_CACHE_DIR`, then platformdirs, and
    `load_env()` inside it pulls the repo's own `.env` in on the way. So the no-reference test passed
    on CI and, on a provisioned machine, silently ran against the real 4.4M-row snapshot — green
    where the caches are absent and wrong where they are not. An empty string is the *credential*
    idiom and is inverted here (empty is falsy, so the ladder falls through to the default dir): these
    point at a directory that does not exist.
    """
    absent = tmp_path / "no-such-cache"
    monkeypatch.setenv("JUST_DNA_ENSEMBL_CACHE", str(absent))
    monkeypatch.setenv("JUST_DNA_CLINVAR_CACHE", str(absent))
    monkeypatch.setenv("JUST_DNA_PIPELINES_CACHE_DIR", str(absent))


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    """Two real loci at their real GRCh38 positions: MTHFR c.677C>T and APOE rs429358.

    Real, because a synthetic coordinate cannot tell a working comparison from a broken one — the
    first draft of this fixture carried rs1801133's **GRCh37** position, and the check dutifully
    reported it as a disagreement against a machine's real snapshot.
    """
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


def _spec(tmp_path: Path, rows: str, *, build: str | None = None) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    yaml = _YAML if build is None else _YAML + f"genome_build: {build}\n"
    (spec / "module_spec.yaml").write_text(yaml, encoding="utf-8")
    (spec / "variants.csv").write_text(_HEADER + rows, encoding="utf-8")
    return spec


def _haplotype_spec(tmp_path: Path, rows: str) -> Path:
    """A PGx-shaped module: `haplotypes.csv`, whose `ref` is optional and whose `chrom` is verbatim."""
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "haplotypes.csv").write_text(
        "haplotype_name,rsid,chrom,start,allele,gene\n" + rows, encoding="utf-8"
    )
    return spec


def _record(spec: Path) -> VerificationRecord | None:
    path = spec / VERIFICATION_JSON
    if not path.is_file():
        return None
    by_check = {r.check: r for r in read_verification(path).records}
    return by_check.get(_CHECK)


def _enrich(spec: Path, cache: Path | None = None, **over) -> None:
    enrich(spec, offline=True, ensembl_cache=cache, verify_rsids=False, mint_vrs=False, **over)


def test_an_authored_pair_is_compared_against_the_reference(tmp_path: Path, cache: Path) -> None:
    """The whole point: two pairs go in, one contradicts the snapshot, and the record says 1 of 2."""
    spec = _spec(
        tmp_path,
        "rs1801133,1,11796321,G,A,A/G,risk,agrees with the snapshot\n"
        "rs429358,19,999,T,C,C/T,risk,authored at a position the snapshot does not give\n",
    )
    _enrich(spec, cache)

    record = _record(spec)
    assert record is not None, f"{_CHECK} is emitted by nothing"
    assert record.skipped is None
    assert (record.subjects, record.findings) == (2, 1)
    assert record.source == "ensembl"
    assert "rs429358" in (record.detail or "")


def test_a_module_authoring_no_pair_says_nothing_to_check(tmp_path: Path, cache: Path) -> None:
    """An rsID-only module carries no pair — that is not a check that passed over zero rows."""
    spec = _spec(tmp_path, "rs1801133,,,,,A/G,risk,rsid only\n")
    _enrich(spec, cache)

    record = _record(spec)
    assert record is not None
    assert record.skipped == "nothing_to_check"
    assert (record.subjects, record.findings) == (0, 0)


def test_no_reference_is_a_skip_not_a_clean_pass(tmp_path: Path) -> None:
    """F4's lesson, on this check: nothing was compared, so nothing may read as compared."""
    spec = _spec(tmp_path, "rs1801133,1,11796321,G,A,A/G,risk,unchecked\n")
    _enrich(spec, None)

    record = _record(spec)
    assert record is not None
    assert record.skipped == "offline", "offline with no snapshot is cleared by egress, so say so"
    assert (record.subjects, record.findings) == (0, 0)


def test_a_pair_the_snapshot_never_heard_of_is_not_an_agreement(tmp_path: Path, cache: Path) -> None:
    """An answered absence is not a verdict (S20): an unknown rsID is outside the denominator."""
    spec = _spec(
        tmp_path,
        "rs1801133,1,11796321,G,A,A/G,risk,in the snapshot\n"
        "rs1799945,6,26090951,C,G,C/G,risk,not in the snapshot\n",
    )
    _enrich(spec, cache)

    record = _record(spec)
    assert record is not None
    assert (record.subjects, record.findings) == (1, 0), "the unknown pair must not be counted"
    assert "rs1799945" in (record.detail or ""), "what was NOT compared has to be stated"


def test_a_snapshot_that_knows_none_of_the_pairs_records_no_reference(
    tmp_path: Path, cache: Path
) -> None:
    """Zero comparable pairs is `no_reference`, never `ran(0, 0)`."""
    spec = _spec(tmp_path, "rs1799945,6,26090951,C,G,C/G,risk,not in the snapshot\n")
    _enrich(spec, cache)

    record = _record(spec)
    assert record is not None
    assert record.skipped == "no_reference"
    assert "rs1799945" in (record.detail or "")


def test_a_non_grch38_module_records_unsupported(tmp_path: Path, cache: Path) -> None:
    """Coordinate resolution is GRCh38-bound, so the pair has nothing to be compared against."""
    spec = _spec(
        tmp_path,
        "rs1801133,1,11854476,G,A,A/G,risk,a GRCh37 coordinate\n",
        build="GRCh37",
    )
    _enrich(spec, cache)

    record = _record(spec)
    assert record is not None
    assert record.skipped == "unsupported"


def test_a_disagreement_is_reported_in_both_modes_and_refuses_neither(
    tmp_path: Path, cache: Path
) -> None:
    """A dbSNP merge or a build difference is not something an authored edit is owed — P5.

    `strict` means *reproducible artifact*; the compiler's half of this question escalates because the
    authored value wins and the table's position is then lost on a reverse. Here nothing is dropped,
    so escalating would refuse a compile for a finding the enricher itself carries as a warning.
    """
    spec = _spec(tmp_path, "rs429358,19,999,T,C,C/T,risk,contradicts the snapshot\n")
    _enrich(spec, cache, mode="strict")

    record = _record(spec)
    assert record is not None and (record.subjects, record.findings) == (1, 1)


# ── the four review findings, each pinned on the row shape that produced it ─────────────────────


def test_a_row_that_authored_no_ref_is_compared_at_its_position(tmp_path: Path, cache: Path) -> None:
    """`ref` is optional on `HaplotypeRow`, and `pgx_draft` writes exactly that shape.

    Keying the comparison on `chrom:start:ref` rendered `1:11796321:None` for such a row, which can
    match nothing — so every CPIC-drafted defining variant with a position was stamped as a reference
    disagreement, in the register `verification.json` publishes. The claim a ref-less row makes is
    about a *place*, and that is what is compared.
    """
    spec = _haplotype_spec(tmp_path, "*2,rs1801133,1,11796321,A,MTHFR\n")
    _enrich(spec, cache)

    record = _record(spec)
    assert record is not None
    assert (record.skipped, record.subjects, record.findings) == (None, 1, 0)


def test_a_chr_prefixed_contig_is_the_same_place(tmp_path: Path, cache: Path) -> None:
    """No PGx model runs the chrom validator, so `chr1` reaches the comparison verbatim.

    `VariantRow` folds it to `1`; `HaplotypeRow` does not, and a string comparison would then read one
    place as two. The contig is normalized on both sides instead.
    """
    spec = _haplotype_spec(tmp_path, "*2,rs1801133,chr1,11796321,A,MTHFR\n")
    _enrich(spec, cache)

    record = _record(spec)
    assert record is not None
    assert (record.skipped, record.subjects, record.findings) == (None, 1, 0)


def test_an_indel_anchored_a_base_earlier_is_undecided_not_a_disagreement(tmp_path: Path) -> None:
    """One deletion has several valid spellings, and re-anchoring moves the coordinate (RM31).

    ClinVar's `CAG>C` at 634689 and Ensembl's `AGAG>AG` at 634690 are the same 2 bp deletion. Reporting
    the position difference as a contradiction is the false accusation RM31 exists to end — worse here
    than in the resolver, because this verdict is attested. The pair is left undecided and named.
    """
    data = tmp_path / "cache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {
            "id": ["rs869312907"],
            "chrom": ["X"],
            "start": [634690],
            "ref": ["AGAG"],
            "alt": ["AG"],
        }
    ).write_parquet(data / "chr.parquet")
    spec = _haplotype_spec(tmp_path, "*2,rs869312907,X,634689,C,SHOX\n")
    _enrich(spec, tmp_path / "cache")

    record = _record(spec)
    assert record is not None
    assert record.findings == 0, "an alternative anchoring is not a contradiction"
    assert record.skipped == "no_reference", "and it is not a comparison either"
    assert "rs869312907" in (record.detail or "")


def test_an_unqueryable_cache_does_not_become_fatal_because_of_this_check(
    tmp_path: Path
) -> None:
    """A check that gates nothing must not turn a broken cache into a failed run.

    A located cache can still refuse to answer — a stale snapshot, or a parquet another tool wrote. A
    module where every row authors both halves needs *no* resolution, so before this pass it never
    opened the cache at all; widening the gate to reach it must not make the cache's state fatal.
    """
    data = tmp_path / "cache" / "data"
    data.mkdir(parents=True)
    pl.DataFrame({"not_the_ensembl_columns": ["x"]}).write_parquet(data / "chr.parquet")
    spec = _spec(tmp_path, "rs1801133,1,11796321,G,A,A/G,risk,both halves authored\n")
    _enrich(spec, tmp_path / "cache")

    record = _record(spec)
    assert record is not None
    assert record.skipped == "no_reference"


def test_a_module_with_no_pair_says_so_whatever_its_build(tmp_path: Path, cache: Path) -> None:
    """`unsupported` describes a pair that could not be compared — not the absence of one."""
    spec = _spec(tmp_path, "rs1801133,,,,,A/G,risk,rsid only\n", build="GRCh37")
    _enrich(spec, cache)

    record = _record(spec)
    assert record is not None
    assert record.skipped == "nothing_to_check"


def test_a_re_run_over_an_existing_resolution_table_still_puts_the_question(
    tmp_path: Path, cache: Path
) -> None:
    """The second run must not degrade a real verdict into a skip, and the reason is structural.

    `enrich()` treats an existing `resolution.csv` as authoritative and skips the work for every key it
    covers — which, on a fully coordinate-authored module, is every key. If the pair check took its
    subjects from what still *needed* resolving it would find none on run two and record
    `nothing_to_check`, replacing a genuine finding with an absence (`merge_records` is newest-wins per
    check). It takes them from the authored rows instead: a resolution row is machine-written or
    hand-corrected, so comparing against it would be comparing the module with itself.
    """
    spec = _spec(tmp_path, "rs429358,19,999,T,C,C/T,risk,contradicts the snapshot\n")
    _enrich(spec, cache)
    assert (spec / "resolution.csv").is_file()
    first = _record(spec)

    _enrich(spec, cache)
    second = _record(spec)
    assert first is not None and second is not None
    assert (second.skipped, second.subjects, second.findings) == (None, 1, 1)
    assert (first.subjects, first.findings) == (second.subjects, second.findings)


def test_the_record_is_byte_stable_across_a_no_op_re_run(tmp_path: Path, cache: Path) -> None:
    """The attestation's determinism pin (D4): only the timestamps may move."""
    spec = _spec(tmp_path, "rs1801133,1,11796321,G,A,A/G,risk,agrees\n")
    _enrich(spec, cache)
    first = read_verification(spec / VERIFICATION_JSON)
    (spec / "resolution.csv").unlink()
    _enrich(spec, cache)
    second = read_verification(spec / VERIFICATION_JSON)

    assert (first.module_hash, first.signature, first.nonce, first.difficulty) == (
        second.module_hash, second.signature, second.nonce, second.difficulty
    )
