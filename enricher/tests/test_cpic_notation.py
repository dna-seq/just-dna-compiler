"""RM253: the CPIC drafter spells CPIC's repeat-count, `DEL`/`INS` and HGVS-named alleles.

Run against the **provisioned CPIC snapshot** (skipped when the machine has none) and a recorded slice
of the GRCh38 reference (`assets/grch38_cpic_notation_windows.json`, read once by hand through the
enricher's own `SequenceProxy` from the public seqrepo service), so nothing here opens a socket. The
translation itself (`_left_align`, the run count, the delins pairing) is the real code path.

Every expected spelling is **derived**, not copied: the test applies the drafted VCF event to the
recorded reference and checks that it produces the haplotype CPIC's notation describes, and that no
spelling one base further left produces it too (left-normalized). The decision's own literals for
UGT1A1 (`C>CAT`, `CAT>C`, `C>CATAT` at `2:233760233`) are domain constants and asserted as well.
"""

import json
import os
from pathlib import Path

import pytest
from just_dna_compiler.compiler import _load_csv_rows, compile_module, reverse_module, validate_spec
from just_dna_enricher.cpic import CpicSnapshotClient, unusable_allele_reason
from just_dna_enricher.cpic_notation import (
    NOT_SPELLED_EXPLANATION,
    NOT_SPELLED_REASONS,
    Notation,
    Spelled,
    delins_partner,
    parse_notation,
    spell,
)
from just_dna_enricher.locations import resolve_cpic_reference
from just_dna_enricher.pgx_draft import _draft_name, _reference_reader, draft_gene
from just_dna_enricher.sequences import SequenceProxy
from just_dna_format.pgx import STAR_ALLELE_PATTERN, AlleleFunctionRow, DiplotypeRow, HaplotypeRow
from just_dna_format.vrs import refget_accession

_ROOT = Path(__file__).resolve().parents[2]
_WINDOWS = json.loads((_ROOT / "assets" / "grch38_cpic_notation_windows.json").read_text(encoding="utf-8"))
_SNAPSHOT = resolve_cpic_reference()
_needs_snapshot = pytest.mark.skipif(
    _SNAPSHOT is None, reason="no provisioned CPIC snapshot (`just-dna-enricher cache pull cpic`)"
)

_YAML = (
    'schema_version: "1.0"\n'
    "module:\n  name: rm253\n  title: T\n  report_title: T\n  description: d\n"
    "genome_build: GRCh38\n"
)

#: The UGT1A1 promoter TA run, GRCh38 — the RM253 decision line's anchor.
_UGT1A1_ANCHOR = ("2", 233760233)


class _RecordedReference(SequenceProxy):
    """A `SequenceProxy` answering from the recorded windows: real bases, no socket.

    A read the recording does not cover answers `None`, which is exactly what an unreachable service
    answers, so a test that strays outside the recording sees the withheld path rather than a guess.
    """

    def __init__(self) -> None:
        super().__init__(offline=False)
        self.windows: dict[str, list[tuple[int, str]]] = {}
        for w in _WINDOWS["windows"]:
            accession = refget_accession(w["chrom"])
            self.windows.setdefault(accession, []).append((w["start"], w["bases"]))

    def subsequence(self, accession: str, start: int, end: int) -> str | None:
        for first, bases in self.windows.get(accession, []):
            lo, hi = start - (first - 1), end - (first - 1)
            if lo >= 0 and hi <= len(bases):
                return bases[lo:hi].upper()
        return None


def _reference(chrom: str, start: int, end: int) -> str:
    """1-based inclusive bases from the recording (the test's own independent reader)."""
    got = _RecordedReference().subsequence(refget_accession(chrom), start - 1, end)
    assert got is not None, (chrom, start, end)
    return got


def _apply(chrom: str, lo: int, hi: int, start: int, ref: str, alt: str) -> str:
    """The reference over `[lo, hi]` with the VCF event `start ref>alt` applied."""
    seq = _reference(chrom, lo, hi)
    i = start - lo
    assert seq[i : i + len(ref)] == ref, "the event's REF is not the reference"
    return seq[:i] + alt + seq[i + len(ref) :]


def _left_normalized(row: HaplotypeRow) -> bool:
    """No spelling one base further left exists: VCF's test, that REF and ALT end on different bases
    (an equal last base could be dropped and the anchor moved left)."""
    ref, alt = row.ref or "", row.allele
    return ref == alt or ref[-1] != alt[-1]


def _spec(tmp_path: Path) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    return spec


def _rows(spec: Path, csv_name: str, model) -> list:
    rows, errors, _ = _load_csv_rows(spec / csv_name, model, csv_name)
    assert not errors, errors
    return rows


def _draft(tmp_path: Path, gene: str, **kwargs):
    spec = _spec(tmp_path)
    result = draft_gene(
        spec,
        gene,
        declared_use="non_commercial",
        client=CpicSnapshotClient(_SNAPSHOT),
        sequences=kwargs.pop("sequences", _RecordedReference()),
        **kwargs,
    )
    return spec, result


def _cpic_values(gene: str) -> list[tuple[str, int, str]]:
    """`(allele, start, value)` for every notation value CPIC states for `gene`, off the snapshot."""
    variants, _ = CpicSnapshotClient(_SNAPSHOT).defining_variants(gene)
    return [
        (v.allele, v.start, v.variant_allele)
        for v in variants
        if v.variant_allele and unusable_allele_reason(v.variant_allele) == "notation"
    ]


# ── Seam 1: the repeat count ─────────────────────────────────────────────────────────────────────


@_needs_snapshot
def test_ugt1a1_star28_36_37_are_defined_by_the_spelled_indel(tmp_path: Path) -> None:
    spec, _ = _draft(tmp_path, "UGT1A1")
    rows = _rows(spec, "haplotypes.csv", HaplotypeRow)
    at_run = {r.haplotype_name: r for r in rows if (r.chrom, r.start) == _UGT1A1_ANCHOR}
    # Every allele CPIC defines by a TA count is drafted at the run, whatever the snapshot holds.
    counted = {allele for allele, _, value in _cpic_values("UGT1A1") if value.startswith("TA(")}
    assert {"*28", "*36", "*37"} <= counted
    assert set(at_run) == counted
    # The decision's literals — domain constants, and what every measured caller writes.
    assert (at_run["*28"].ref, at_run["*28"].allele) == ("C", "CAT")
    assert (at_run["*36"].ref, at_run["*36"].allele) == ("CAT", "C")
    assert (at_run["*37"].ref, at_run["*37"].allele) == ("C", "CATAT")
    # And derived: applying the event to the reference yields exactly CPIC's count of TA units.
    run = _reference("2", 233760235, 233760260)
    reference_copies = 0
    while run[2 * reference_copies : 2 * reference_copies + 2] == "TA":
        reference_copies += 1
    for allele, _, value in _cpic_values("UGT1A1"):
        if not value.startswith("TA("):
            continue
        count = int(value[3:-1])
        row = at_run[allele]
        before = _reference("2", 233760230, 233760234)
        after = _apply("2", 233760230, 233760260, row.start, row.ref or "", row.allele)
        expected = before + "TA" * count + _reference("2", 233760235 + 2 * reference_copies, 233760260)
        assert after == expected, (allele, value)
        assert _left_normalized(row), allele


@_needs_snapshot
def test_the_reference_count_is_the_reference_state_at_the_same_locus(tmp_path: Path) -> None:
    """`*1` is TA(7), the reference: written REF == ALT at the anchor the variants share."""
    spec, _ = _draft(tmp_path, "UGT1A1")
    star1 = [r for r in _rows(spec, "haplotypes.csv", HaplotypeRow) if r.haplotype_name == "*1"]
    at_run = [r for r in star1 if (r.chrom, r.start) == _UGT1A1_ANCHOR]
    assert len(at_run) == 1
    assert at_run[0].ref == at_run[0].allele == _reference(*_UGT1A1_ANCHOR, _UGT1A1_ANCHOR[1])


@_needs_snapshot
def test_no_repeat_row_keys_on_the_site_rsid(tmp_path: Path) -> None:
    """`rs3064744` is in no caller's ID column; a repeat row is keyed by its coordinate."""
    spec, _ = _draft(tmp_path, "UGT1A1")
    rows = _rows(spec, "haplotypes.csv", HaplotypeRow)
    assert "rs3064744" in {v.rsid for v in _defining("UGT1A1")}, "the trap is CPIC's own id"
    assert not [r for r in rows if r.rsid == "rs3064744"]
    at_run = [r for r in rows if (r.chrom, r.start) == _UGT1A1_ANCHOR]
    assert at_run and all(r.rsid is None and r.ref for r in at_run)
    assert all(r.variant_key == f"{r.chrom}:{r.start}:{r.ref}" for r in at_run)


def _defining(gene: str):
    variants, _ = CpicSnapshotClient(_SNAPSHOT).defining_variants(gene)
    return variants


@_needs_snapshot
def test_validate_no_longer_reports_the_counted_alleles_undefined(tmp_path: Path) -> None:
    spec, _ = _draft(tmp_path, "UGT1A1")
    result = validate_spec(spec, strict=True)
    assert result.valid, result.errors
    undefined = [w for w in result.warnings if "used but not defined" in w]
    for allele in ("*28", "*36", "*37", "*80+*28", "*80+*37"):
        assert not any(f"'{allele}'" in w or f" {allele}," in w or f" {allele}]" in w for w in undefined), (
            undefined
        )
    assert not undefined, undefined


@_needs_snapshot
def test_offline_withholds_the_spelling_and_says_why(tmp_path: Path) -> None:
    """No sequence access: the counted alleles are undefined again, and the run says it could not read."""
    spec, result = _draft(tmp_path, "UGT1A1", offline=True)
    names = {r.haplotype_name for r in _rows(spec, "haplotypes.csv", HaplotypeRow)}
    assert "*28" not in names
    [line] = [w for w in result.warnings if "could not be read" in w]
    assert "*28=TA(8)" in line or "(+" in line


# ── Seam 2: DEL<bases> / INS<bases> ──────────────────────────────────────────────────────────────


@_needs_snapshot
@pytest.mark.parametrize("gene", ["DPYD", "NUDT15", "RYR1", "TPMT"])
def test_every_deletion_and_insertion_is_the_event_cpic_states(tmp_path: Path, gene: str) -> None:
    """Applying the drafted event to the reference reproduces CPIC's deletion or insertion exactly."""
    spec, _ = _draft(tmp_path, gene)
    rows = _rows(spec, "haplotypes.csv", HaplotypeRow)
    by_allele: dict[str, list[HaplotypeRow]] = {}
    for r in rows:
        by_allele.setdefault(r.haplotype_name, []).append(r)
    values = _cpic_values(gene)
    delins_loci = {
        start
        for _, start, value in values
        if value.startswith("INS")
        and any(v.startswith("DEL") and len(v) > 3 and s == start for _, s, v in values)
        and not any(s == start and v == "DEL" for _, s, v in values)
    }
    checked = 0
    for allele, start, value in values:
        parsed = parse_notation(value)
        if not isinstance(parsed, Notation) or parsed.kind == "repeat":
            continue
        name = _draft_name(allele)
        lo, hi = start - 40, start + 60
        candidates = [r for r in by_allele.get(name, []) if r.ref and lo < r.start < hi]
        if start in delins_loci:
            if parsed.kind == "deletion":
                assert any(r.ref == r.allele == parsed.bases for r in candidates), (allele, value)
            else:
                partner = next(v[3:] for _, s, v in values if s == start and v.startswith("DEL"))
                want = _reference(gene_chrom(gene), lo, start - 1) + parsed.bases
                want += _reference(gene_chrom(gene), start + len(partner), hi)
                assert any(
                    _apply(gene_chrom(gene), lo, hi, r.start, r.ref, r.allele) == want for r in candidates
                ), (allele, value)
            checked += 1
            continue
        chrom = gene_chrom(gene)
        if parsed.kind == "deletion":
            want = _reference(chrom, lo, start - 1) + _reference(chrom, start + len(parsed.bases), hi)
        else:
            want = _reference(chrom, lo, start) + parsed.bases + _reference(chrom, start + 1, hi)
        matching = [r for r in candidates if _apply(chrom, lo, hi, r.start, r.ref, r.allele) == want]
        assert len(matching) == 1, (allele, value, candidates)
        assert _left_normalized(matching[0]) and matching[0].ref[0] == matching[0].allele[0]
        checked += 1
    assert checked, f"{gene}: no DEL/INS value was exercised"


def gene_chrom(gene: str) -> str:
    return CpicSnapshotClient(_SNAPSHOT).chrom_for_gene(gene)


@_needs_snapshot
def test_a_bare_del_stays_skipped_with_its_reason(tmp_path: Path) -> None:
    _, result = _draft(tmp_path, "NUDT15")
    assert any(v == "DEL" for *_, v in _cpic_values("NUDT15"))
    [line] = [w for w in result.warnings if "bare `DEL`" in w]
    assert "*1=DEL" in line


@_needs_snapshot
def test_every_bare_del_is_the_reference_row_at_an_insertion_site() -> None:
    """What ENRICHER.md says of the bare `DEL` the decision keeps skipped, re-measured over every gene."""
    client = CpicSnapshotClient(_SNAPSHOT)
    genes = [r["gene"] for r in client._rows("genes.parquet", "TRUE", [], "gene")]
    bare = 0
    for gene in genes:
        variants, _ = client.defining_variants(gene)
        for v in variants:
            if (v.variant_allele or "").upper() != "DEL":
                continue
            bare += 1
            here = [w.variant_allele for w in variants if (w.chrom, w.start) == (v.chrom, v.start)]
            assert any((x or "").startswith("INS") for x in here), (gene, v.allele, here)
            assert v.allele in ("*1", "Reference"), (gene, v.allele)
    assert bare, "the snapshot holds no bare DEL any more; the ENRICHER.md sentence is stale"


@_needs_snapshot
def test_the_closure_counts_of_notation_spellings_on_the_snapshot_it_names() -> None:
    """ROADMAP_HISTORY § RM253 states two counts for `cpic_snapshot_b0ffd4c6f010`; re-derived here.

    The distinct notation spellings, and those on star-named alleles (the only ones the drafter could
    reach before RM253). Asserted only against the snapshot the record names, since a newer release may
    hold more.
    """
    client = CpicSnapshotClient(_SNAPSHOT)
    if client.dataset != "cpic_snapshot_b0ffd4c6f010":
        pytest.skip(f"the record's counts are for cpic_snapshot_b0ffd4c6f010, not {client.dataset}")
    rows = client._rows("allele_definitions.parquet", "TRUE", [], "allele, variant_allele")
    notation = {
        (r["allele"], (r["variant_allele"] or "").strip().upper())
        for r in rows
        if unusable_allele_reason((r["variant_allele"] or "").strip().upper()) == "notation"
    }
    assert len({value for _, value in notation}) == 46
    assert len({value for allele, value in notation if STAR_ALLELE_PATTERN.match(allele or "")}) == 27


@_needs_snapshot
def test_alternatives_stay_skipped_as_an_uncertainty(tmp_path: Path) -> None:
    spec, result = _draft(tmp_path, "NUDT15")
    [line] = [w for w in result.warnings if "alternatives" in w]
    assert "GAGTCG(3) OR GAGTCG(4)" in line
    rows = _rows(spec, "haplotypes.csv", HaplotypeRow)
    assert not [r for r in rows if r.haplotype_name == "*3" and r.start and abs(r.start - 48037784) < 30]


# ── Seam 3: HGVS-named alleles ───────────────────────────────────────────────────────────────────


def test_a_dpyd_name_drops_its_spaces_and_writes_the_comma_as_an_ampersand() -> None:
    assert _draft_name("c.1129-5923C>G, c.1236G>A (HapB3)") == "c.1129-5923C>G&c.1236G>A(HapB3)"
    assert _draft_name("c.1003G>T (*11)") == "c.1003G>T(*11)"
    assert _draft_name("Reference") == "Reference"
    assert _draft_name("*28") == "*28"
    # A translated name is a fixed point, so a name read back from the module translates to itself.
    assert _draft_name("c.1129-5923C>G&c.1236G>A(HapB3)") == "c.1129-5923C>G&c.1236G>A(HapB3)"
    # Not HGVS: a comma there separates aliases, not variants, and `&` would claim a compound.
    assert _draft_name("Mediterranean, Dallas, Panama") is None
    assert _draft_name("rs2231142 reference (G)") is None


def test_all_three_pgx_models_accept_the_translated_name_without_widening() -> None:
    name = _draft_name("c.1129-5923C>G, c.1236G>A (HapB3)")
    HaplotypeRow(haplotype_name=name, rsid="rs75017182", allele="C")
    AlleleFunctionRow(gene="DPYD", allele=name)
    DiplotypeRow(gene="DPYD", haplotype_a=name, haplotype_b="Reference", conclusion="c")


@_needs_snapshot
def test_dpyd_drafts_under_its_translated_names(tmp_path: Path) -> None:
    spec, result = _draft(tmp_path, "DPYD")
    functions = {r.allele for r in _rows(spec, "allele_function.csv", AlleleFunctionRow)}
    assert "c.1129-5923C>G&c.1236G>A(HapB3)" in functions and "Reference" in functions
    pairs = {(r.haplotype_a, r.haplotype_b) for r in _rows(spec, "diplotypes.csv", DiplotypeRow)}
    assert ("c.1003G>T(*11)", "Reference") in pairs or ("Reference", "c.1003G>T(*11)") in pairs
    assert not [w for w in result.warnings if "HGVS" in w and "skipped" in w]
    validated = validate_spec(spec, strict=True)
    assert validated.valid, validated.errors
    assert not [w for w in validated.warnings if "used but not defined" in w]


@_needs_snapshot
@pytest.mark.parametrize("asked", ["c.1003G>T (*11)", "c.1003G>T(*11)"])
def test_the_allele_filter_takes_either_spelling_and_keeps_the_reference(tmp_path: Path, asked: str) -> None:
    """`--allele` compares under the written name, and `Reference` is kept where `*1` would be."""
    spec, _ = _draft(tmp_path, "DPYD", alleles=[asked])
    functions = {r.allele for r in _rows(spec, "allele_function.csv", AlleleFunctionRow)}
    assert functions == {"c.1003G>T(*11)", "Reference"}


# ── The module compiles and round-trips ──────────────────────────────────────────────────────────


@_needs_snapshot
@pytest.mark.parametrize("gene", ["UGT1A1", "DPYD"])
def test_the_drafted_module_compiles_strict_and_round_trips(tmp_path: Path, gene: str) -> None:
    spec, _ = _draft(tmp_path, gene)
    first = compile_module(spec, tmp_path / "a1", strict=True)
    assert first.success, first.errors
    reverse_module(tmp_path / "a1", tmp_path / "rev")
    second = compile_module(tmp_path / "rev", tmp_path / "a2", strict=True)
    assert second.success, second.errors
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    assert first.manifest.content_signature == second.manifest.content_signature


def test_a_notation_the_reference_does_not_bear_out_is_withheld() -> None:
    """Spelling a deletion of bases that are not there, or a run that does not start there, would
    invent an event — so it is withheld by name, and a real one at the same place is still spelled."""
    read = _reference_reader(_RecordedReference(), offline=False)
    chrom, run_start = "2", 233760235  # UGT1A1's TA run, which starts with `TA`
    assert spell(Notation("deletion", "GG"), chrom, run_start, read) == "reference_disagrees"
    assert spell(Notation("repeat", "GC", 3), chrom, run_start, read) == "reference_disagrees"
    assert (
        spell(Notation("insertion", "CT"), chrom, run_start, read, delins_ref="GG") == "reference_disagrees"
    )
    assert isinstance(spell(Notation("deletion", "TA"), chrom, run_start, read), Spelled)
    # Off the recording is the unreadable arm, never a guess.
    assert spell(Notation("deletion", "TA"), chrom, 1_000, read) == "reference_unreadable"


def test_a_repeat_position_inside_the_run_is_withheld_not_miscounted() -> None:
    """One unit into UGT1A1's run, a rightward count is one short and `TA(8)` would be spelled +2 units."""
    read = _reference_reader(_RecordedReference(), offline=False)
    assert isinstance(spell(Notation("repeat", "TA", 8), "2", 233760235, read), Spelled)
    assert spell(Notation("repeat", "TA", 8), "2", 233760237, read) == "reference_disagrees"


def test_a_short_read_at_a_delins_is_unreadable_never_a_disagreement() -> None:
    def clipped(chrom: str, start: int, end: int) -> str | None:
        return "T"

    assert (
        spell(Notation("insertion", "CT"), "19", 38572266, clipped, delins_ref="TC") == "reference_unreadable"
    )


def test_a_delins_needs_its_deletion_on_the_reference_allele() -> None:
    """Two variant alleles, one deleting and one inserting at a locus, are two events, not a delins."""
    names = frozenset({"*1", "Reference"})
    assert delins_partner([("Reference", "DELTC"), ("c.13994_13995delTCinsCT", "INSCT")], names) == "TC"
    assert delins_partner([("*7", "DELA"), ("*9", "INSG")], names) is None
    assert delins_partner([("*1", "DEL"), ("*9", "INSG")], names) is None
    assert delins_partner([("*1", "A"), ("*7", "DELA"), ("*9", "INSG")], names) is None


@_needs_snapshot
def test_the_allele_filter_does_not_change_how_a_locus_is_read(tmp_path: Path) -> None:
    """Filtered to an unrelated RYR1 allele, `Reference` keeps its reference state at the delins locus;
    judged from the filtered rows alone, its `DELTC` would read as a deletion CPIC never stated."""
    spec, _ = _draft(tmp_path, "RYR1", alleles=["c.14510delA"])
    at = [
        (r.ref, r.allele)
        for r in _rows(spec, "haplotypes.csv", HaplotypeRow)
        if r.haplotype_name == "Reference" and r.start == 38572266
    ]
    assert at == [("TC", "TC")]


def test_a_written_name_never_holds_a_separator() -> None:
    for raw in ("c.[61C>G;70A>G]", "c.61C>G|c.70A>G", "c.61C>G/c.70A>G"):
        assert _draft_name(raw) is None, raw


# ── The registries the warnings index ────────────────────────────────────────────────────────────


def test_every_reason_a_notation_is_not_spelled_has_a_sentence() -> None:
    assert set(NOT_SPELLED_EXPLANATION) == NOT_SPELLED_REASONS
    assert parse_notation("DEL") == "lengthless_deletion"
    assert parse_notation("GAGTCG(3) OR GAGTCG(4)") == "alternatives"
    assert parse_notation("DELINSCC; DELINSCCC") == "alternatives"
    assert parse_notation("TA(8)") == Notation("repeat", "TA", 8)


@_needs_snapshot
def test_the_skipped_spellings_shrink_to_what_the_decision_keeps(tmp_path: Path) -> None:
    """Over the genes the recording covers, what is still skipped is only a bare `DEL` or alternatives."""
    for gene in ("UGT1A1", "NUDT15", "RYR1", "DPYD", "TPMT"):
        _, result = _draft(tmp_path / gene, gene)
        notation_lines = [w for w in result.warnings if "not spelled" in w]
        for line in notation_lines:
            assert "bare `DEL`" in line or "alternatives" in line, line


@pytest.mark.skipif(os.environ.get("JUST_DNA_NETWORK_TESTS") != "1", reason="network test (opt-in)")
@_needs_snapshot
def test_the_live_reference_spells_star28_as_the_decision_says(tmp_path: Path) -> None:
    spec, _ = _draft(tmp_path, "UGT1A1", sequences=SequenceProxy())
    at_run = {
        r.haplotype_name: (r.ref, r.allele)
        for r in _rows(spec, "haplotypes.csv", HaplotypeRow)
        if (r.chrom, r.start) == _UGT1A1_ANCHOR
    }
    assert at_run["*28"] == ("C", "CAT")
