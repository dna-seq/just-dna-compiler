"""RM438 (S151, S152): a coordinate-only row's rsID is narrowed by the row's alleles, on both back-fill paths.

`22:42128945` holds two rsIDs in the split Ensembl snapshot (dbSNP 157): `rs3892097`, the CYP2D6*4 SNV
(`C>A`, `C>G`, `C>T`), and `rs2517910443`, a 16 bp insertion. The legacy `resolve_variants` back-fill
gave an `A/G` row the lexicographically first rsID, the insertion, and said nothing; the enrich path gave
the first by ALT order and flagged it `ambiguous`, never reading the genotype either. One rule now
narrows both: the row's `alts` when stated, else its genotype's alleles, through the hosting judgement
(`site_verdicts`), an allele it cannot read narrowing nothing. `resolve_variants` withholds on more than
one rsID left; `enrich` keeps its pick-and-flag.

The fixture is the four S151 rows exactly as the reporter quoted them; the oracle for "can this rsID
host this genotype" is the shared predicate itself, asked over the fixture's own rows.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.resolution import site_verdicts
from just_dna_enricher import resolver
from just_dna_enricher.enrich import enrich
from just_dna_enricher.events import kleene_any
from just_dna_enricher.resolver import resolve_variants
from just_dna_format.findings import CodedWarning
from just_dna_format.spec import VariantRow

CHROM, START, REF = "22", 42128945, "C"
STAR4 = "rs3892097"  # CYP2D6*4, the reporter's ground truth
INSERTION = "rs2517910443"  # new in dbSNP 157
INSERTED = "CGGGTAAGGGGGCGTCT"

#: S151's four rows, as the reporter quoted them from the split snapshot.
S151_ROWS = [
    (CHROM, START, REF, "A", STAR4),
    (CHROM, START, REF, "G", STAR4),
    (CHROM, START, REF, "T", STAR4),
    (CHROM, START, REF, INSERTED, INSERTION),
]

_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)


def _snapshot(root: Path, rows: list[tuple[str, int, str, str, str]]) -> Path:
    data = root / "data"
    data.mkdir(parents=True)
    pl.DataFrame(
        {
            "chrom": [r[0] for r in rows],
            "start": [r[1] for r in rows],
            "ref": [r[2] for r in rows],
            "alt": [r[3] for r in rows],
            "id": [r[4] for r in rows],
        }
    ).write_parquet(data / "homo_sapiens-split.parquet")
    return root


def _hosts(rows: list[tuple[str, int, str, str, str]], genotype: str) -> set[str]:
    """The oracle: the rsIDs whose own fixture rows the hosting judgement does not refute for `genotype`."""
    by_rsid: dict[str, list[tuple[str, int, str, str]]] = {}
    for chrom, start, ref, alt, rsid in rows:
        by_rsid.setdefault(rsid, []).append((chrom, start, ref, alt))
    return {rsid for rsid, loci in by_rsid.items() if kleene_any(site_verdicts(genotype, loci)) is not False}


def _row(genotype: str, alts: str | None = None) -> VariantRow:
    return VariantRow(
        chrom=CHROM, start=START, ref=REF, alts=alts, genotype=genotype, state="risk", conclusion="c"
    )


def _codes(warnings: list) -> list[str]:
    return [w.code for w in warnings if isinstance(w, CodedWarning)]


# ── the oracle agrees with the domain fact before anything is asked of the code ──────────────────────


def test_the_predicate_says_only_the_snv_hosts_a_g() -> None:
    assert _hosts(S151_ROWS, "A/G") == {STAR4}
    assert _hosts(S151_ROWS, f"C/{INSERTED}") == {INSERTION}
    assert _hosts(S151_ROWS, "C/CA") == set()


# ── the legacy back-fill: `resolve_variants` → `_lookup_rsids_by_position` ────────────────────────────


def test_resolve_variants_gives_the_a_g_row_the_star4_rsid(tmp_path: Path) -> None:
    """S151 itself: the row the reporter's `test_position_to_rsid` asks about."""
    snap = _snapshot(tmp_path / "ens", S151_ROWS)
    patched, warnings = resolve_variants([_row("A/G")], ensembl_cache=snap)
    assert [p.rsid for p in patched] == [STAR4]
    assert {STAR4} == _hosts(S151_ROWS, "A/G")
    assert "rsid_ambiguous" not in _codes(warnings)


@pytest.mark.parametrize(
    "alts, genotype, expected",
    [
        ("A", "A/C", STAR4),
        (INSERTED, f"C/{INSERTED}", INSERTION),
        # Multi-valued `alts` narrows too: the rsID must host every allele the row states.
        ("A,G", "A/G", STAR4),
        # `alts` wins over the genotype when stated: a hom-ref call narrows nothing, the ALT does.
        ("A", "C/C", STAR4),
    ],
)
def test_resolve_variants_narrows_on_the_stated_alts_first(
    tmp_path: Path, alts: str, genotype: str, expected: str
) -> None:
    snap = _snapshot(tmp_path / "ens", S151_ROWS)
    patched, warnings = resolve_variants([_row(genotype, alts=alts)], ensembl_cache=snap)
    assert [p.rsid for p in patched] == [expected]
    assert "rsid_ambiguous" not in _codes(warnings)


@pytest.mark.parametrize("genotype", ["*/C", "<DEL:16>/C"])
def test_resolve_variants_withholds_when_the_genotype_cannot_be_read(tmp_path: Path, genotype: str) -> None:
    """An allele it cannot read narrows nothing: both rsIDs stay, so the rsID is withheld and both named."""
    snap = _snapshot(tmp_path / "ens", S151_ROWS)
    patched, warnings = resolve_variants([_row(genotype)], ensembl_cache=snap)
    assert [p.rsid for p in patched] == [None]
    ambiguous = [w for w in warnings if isinstance(w, CodedWarning) and w.code == "rsid_ambiguous"]
    assert len(ambiguous) == 1
    assert STAR4 in ambiguous[0] and INSERTION in ambiguous[0]
    assert "withheld" in ambiguous[0]


def test_resolve_variants_withholds_when_two_rsids_host(tmp_path: Path) -> None:
    """A dbSNP merge at one SNV: both rsIDs host `C/T`, so neither is attached."""
    merged = "rs9999999901"
    rows = [*S151_ROWS, (CHROM, START, REF, "T", merged)]
    assert _hosts(rows, "C/T") == {STAR4, merged}
    snap = _snapshot(tmp_path / "ens", rows)
    patched, warnings = resolve_variants([_row("C/T")], ensembl_cache=snap)
    assert [p.rsid for p in patched] == [None]
    ambiguous = [w for w in warnings if isinstance(w, CodedWarning) and w.code == "rsid_ambiguous"]
    assert len(ambiguous) == 1
    assert STAR4 in ambiguous[0] and merged in ambiguous[0]
    assert INSERTION not in ambiguous[0]  # narrowed out, so not a candidate


@pytest.mark.parametrize(
    "rows, genotype",
    [(S151_ROWS, "C/CA"), ([r for r in S151_ROWS if r[4] == INSERTION], "A/G")],
    ids=["two_to_zero", "one_to_zero"],
)
def test_resolve_variants_attaches_nothing_when_no_rsid_hosts(
    tmp_path: Path, rows: list, genotype: str
) -> None:
    """Zero hosts is an answer, not an unknown: no rsID, and the warning says none can host the genotype."""
    assert _hosts(rows, genotype) == set()
    snap = _snapshot(tmp_path / "ens", rows)
    patched, warnings = resolve_variants([_row(genotype)], ensembl_cache=snap)
    assert [p.rsid for p in patched] == [None]
    assert "rsid_ambiguous" not in _codes(warnings)
    labels = [
        w for w in warnings if isinstance(w, CodedWarning) and w.code == "rsid_without_resolution_label"
    ]
    assert len(labels) == 1 and "can host" in labels[0]


def test_resolve_variants_reads_every_row_of_one_key(tmp_path: Path) -> None:
    """A key authored with `C/C` and `A/G`: hom-ref refutes nothing, `A/G` refutes the insertion, so both
    rows get the one rsID — never one answer per row of one variant."""
    snap = _snapshot(tmp_path / "ens", S151_ROWS)
    patched, warnings = resolve_variants([_row("C/C"), _row("A/G")], ensembl_cache=snap)
    assert [p.rsid for p in patched] == [STAR4, STAR4]
    assert "rsid_ambiguous" not in _codes(warnings)


def test_resolve_variants_keeps_a_lone_hosting_rsid(tmp_path: Path) -> None:
    """A position with one rsID that hosts is attached exactly as before."""
    snap = _snapshot(tmp_path / "ens", [r for r in S151_ROWS if r[4] == STAR4])
    patched, warnings = resolve_variants([_row("A/G")], ensembl_cache=snap)
    assert [p.rsid for p in patched] == [STAR4]
    assert _codes(warnings) == []


# ── the enrich path: `_lookup_rsid_candidates` → the assembly loop ─────────────────────────────────────


def _spec(root: Path, header: str, rows: list[str], table: str = "variants.csv") -> Path:
    spec = root / "spec"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / table).write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return spec


def _enrich(tmp_path: Path, spec: Path, rows: list = S151_ROWS):
    snap = _snapshot(tmp_path / "ens", rows)
    return enrich(spec, offline=True, ensembl_cache=snap, clinvar_cache=tmp_path / "no_clinvar")


_HEADER = "chrom,start,ref,genotype,state,conclusion"


def test_enrich_resolves_the_a_g_row_on_the_one_rsid_that_hosts_it(
    tmp_path: Path, no_ambient_caches: Path
) -> None:
    """S152: `ambiguous` → `resolved` exactly where one rsID hosts the genotype."""
    spec = _spec(tmp_path, _HEADER, [f"{CHROM},{START},{REF},A/G,risk,c"])
    result = _enrich(tmp_path, spec)
    [row] = result.rows
    assert (row.rsid, row.status, row.rsid_alternates, row.source) == (STAR4, "resolved", None, "cache")


def test_enrich_keeps_pick_and_flag_when_the_genotype_cannot_be_read(
    tmp_path: Path, no_ambient_caches: Path
) -> None:
    spec = _spec(tmp_path, _HEADER, [f"{CHROM},{START},{REF},*/C,risk,c"])
    [row] = _enrich(tmp_path, spec).rows
    assert row.status == "ambiguous"
    assert set((row.rsid_alternates or "").split(",")) == {STAR4, INSERTION}


def test_enrich_keeps_pick_and_flag_for_a_row_with_no_genotype(
    tmp_path: Path, no_ambient_caches: Path
) -> None:
    """A pharm row may author no genotype at all: nothing to narrow by, so both candidates stay."""
    spec = _spec(
        tmp_path,
        "chrom,start,ref,gene,drug,conclusion",
        [f"{CHROM},{START},{REF},CYP2D6,codeine,c"],
        table="pharm_variants.csv",
    )
    [row] = _enrich(tmp_path, spec).rows
    assert row.status == "ambiguous"
    assert set((row.rsid_alternates or "").split(",")) == {STAR4, INSERTION}


def test_enrich_narrows_the_alternates_when_two_rsids_host(tmp_path: Path, no_ambient_caches: Path) -> None:
    merged = "rs9999999901"
    rows = [*S151_ROWS, (CHROM, START, REF, "T", merged)]
    spec = _spec(tmp_path, _HEADER, [f"{CHROM},{START},{REF},C/T,risk,c"])
    [row] = _enrich(tmp_path, spec, rows).rows
    assert row.status == "ambiguous"
    assert row.rsid_alternates is not None
    assert set(row.rsid_alternates.split(",")) == _hosts(rows, "C/T") == {STAR4, merged}


@pytest.mark.parametrize(
    "rows, genotype",
    [(S151_ROWS, "C/CA"), ([r for r in S151_ROWS if r[4] == INSERTION], "A/G")],
    ids=["two_to_zero", "one_to_zero"],
)
def test_enrich_back_fills_nothing_when_no_rsid_hosts(
    tmp_path: Path, no_ambient_caches: Path, rows: list, genotype: str
) -> None:
    assert _hosts(rows, genotype) == set()
    spec = _spec(tmp_path, _HEADER, [f"{CHROM},{START},{REF},{genotype},risk,c"])
    [row] = _enrich(tmp_path, spec, rows).rows
    assert (row.rsid, row.status, row.source) == (None, "resolved", "authored")


def test_enrich_reads_every_row_of_one_key(tmp_path: Path, no_ambient_caches: Path) -> None:
    """The hom-ref row first, so a first-row reading would narrow nothing and stay ambiguous."""
    spec = _spec(
        tmp_path, _HEADER, [f"{CHROM},{START},{REF},C/C,neutral,c", f"{CHROM},{START},{REF},A/G,risk,c"]
    )
    [row] = _enrich(tmp_path, spec).rows
    assert (row.rsid, row.status) == (STAR4, "resolved")


def test_enrich_single_alts_rows_are_unchanged(tmp_path: Path, no_ambient_caches: Path) -> None:
    """A row stating one ALT was already allele-exact, and is outside the declared exposure: unchanged."""
    spec = _spec(
        tmp_path,
        "chrom,start,ref,alts,genotype,state,conclusion",
        [f"{CHROM},{START},{REF},A,C/C,risk,c", f"{CHROM},{START},{REF},{INSERTED},C/{INSERTED},risk,c"],
    )
    rows = _enrich(tmp_path, spec).rows
    assert {(r.alts, r.rsid, r.status) for r in rows} == {
        ("A", STAR4, "resolved"),
        (INSERTED, INSERTION, "resolved"),
    }


# ── the shared rule itself ───────────────────────────────────────────────────────────────────────────


def _candidates() -> dict[str, list[tuple[str, int, str, str]]]:
    out: dict[str, list[tuple[str, int, str, str]]] = {}
    for chrom, start, ref, alt, rsid in S151_ROWS:
        out.setdefault(rsid, []).append((chrom, start, ref, alt))
    return out


@pytest.mark.parametrize("genotype", [None, "", "N/A", "rs3892097", "<DEL:16>/C", "*/C", "A/<INS>"])
def test_an_allele_the_rule_cannot_read_narrows_nothing(genotype: str | None) -> None:
    cands = _candidates()
    assert resolver._hosting_rsids(cands, REF, None, [genotype]) == list(cands)


@pytest.mark.parametrize("genotype", ["A/G", "C/C", "A/A", "C/CA", f"C/{INSERTED}", "T/T", "G/GT"])
def test_narrowing_only_ever_removes_candidates(genotype: str) -> None:
    """Narrowed ⊆ un-narrowed, in the un-narrowed order (the pick stays the first of what is left)."""
    cands = _candidates()
    narrowed = resolver._hosting_rsids(cands, REF, None, [genotype])
    assert narrowed == [r for r in cands if r in narrowed]
    assert set(narrowed) == _hosts(S151_ROWS, genotype)


def test_enrich_reads_clinvar_when_the_snapshot_candidates_are_all_refuted(
    tmp_path: Path, no_ambient_caches: Path
) -> None:
    """A link whose candidates the row refutes is a miss, as a rejected forward answer is (RM382): the
    Ensembl snapshot holds only the insertion here, ClinVar holds the SNV, and the `A/G` row takes ClinVar's."""
    ensembl_rows = [r for r in S151_ROWS if r[4] == INSERTION]
    clinvar_rows = [r for r in S151_ROWS if r[4] == STAR4]
    assert _hosts(ensembl_rows, "A/G") == set() and _hosts(clinvar_rows, "A/G") == {STAR4}
    cv = tmp_path / "cv" / "data"
    cv.mkdir(parents=True)
    pl.DataFrame(
        {
            "rsid": [r[4] for r in clinvar_rows],
            "chrom": [r[0] for r in clinvar_rows],
            "start": [r[1] for r in clinvar_rows],
            "ref": [r[2] for r in clinvar_rows],
            "alt": [r[3] for r in clinvar_rows],
        }
    ).write_parquet(cv / "clinvar.parquet")
    spec = _spec(tmp_path, _HEADER, [f"{CHROM},{START},{REF},A/G,risk,c"])
    result = enrich(
        spec,
        offline=True,
        ensembl_cache=_snapshot(tmp_path / "ens", ensembl_rows),
        clinvar_cache=tmp_path / "cv",
        verify_clinsig=False,
    )
    [row] = result.rows
    assert (row.rsid, row.status, row.source) == (STAR4, "resolved", "clinvar")


def test_a_key_whose_rows_name_both_rsids_gets_neither(tmp_path: Path) -> None:
    """Every row's genotype must be hostable, so a key authored `A/C` (only the SNV) and `C/<insertion>`
    (only the insertion) refutes each rsID with the other row: no rsID, where `enrich` used to write
    `ambiguous` with both. The rows describe two variants under one coordinate key; neither label fits all."""
    rows = [_row("A/C"), _row(f"C/{INSERTED}")]
    assert _hosts(S151_ROWS, "A/C") == {STAR4} and _hosts(S151_ROWS, f"C/{INSERTED}") == {INSERTION}
    snap = _snapshot(tmp_path / "ens", S151_ROWS)
    patched, warnings = resolve_variants(rows, ensembl_cache=snap)
    assert [p.rsid for p in patched] == [None, None]
    assert _codes(warnings) == ["rsid_without_resolution_label"]
