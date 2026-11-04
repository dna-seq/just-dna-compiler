"""The enricher judges whether an authored spelling and a resolved one are one event (RM375).

**The red case is real.** `reference_examples/cpic_gene_pairs/haplotypes.csv` authors NUDT15's
`rs761191455` at `13:48041104` (no `ref`), the old Ensembl snapshot's right-shifted spelling
`G>GG`; the new snapshot (`ensembl_variations_split`, dbSNP 157) places it left-aligned at
`13:48041103 T>TG`. GRCh38 reads `…GAGCCT G AAAAAA…` with the `T` at 48041103, so the inserted `G` slides
one base right and no further: the two are one event. Until RM375 compile called the row
`positional_identity_contradicted`, the rsid↔coordinate pass called it a disagreement (an insertion's
one-base `ref` read as a substitution), and `--rederive` called a respelling a source change whenever
a row had no VRS id.

The reference window is recorded once from seqrepo (`assets/grch38_rm375_nudt15_window.json`), so
nothing here needs the network; the one opt-in test reads seqrepo itself
(`JUST_DNA_NETWORK_TESTS=1`).
"""

import ast
import csv
import io
import json
import os
import re
from pathlib import Path

import polars as pl
import pytest
from ga4gh.vrs.dataproxy import _DataProxy
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_enricher.enrich import enrich
from just_dna_enricher.enrich.outcome import SubjectDrift, _same_events
from just_dna_enricher.events import (
    AUTHORED_EVENT_VERDICT,
    Allele,
    authored_event,
    names_event,
    same_allele_sets,
    same_event,
)
from just_dna_enricher.placement import compare_placements
from just_dna_enricher.resolver import check_rsid_coordinates, coordinate_verdict
from just_dna_enricher.sequences import SequenceProxy, indel_spellings
from just_dna_enricher.vrs import VrsMinter
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vocab import VALID_AUTHORED_EVENT_VERDICTS
from just_dna_format.vrs import refget_accession

_ROOT = Path(__file__).resolve().parents[2]
_WINDOW = json.loads((_ROOT / "assets" / "grch38_rm375_nudt15_window.json").read_text(encoding="utf-8"))
_FIRST, _BASES = _WINDOW["windows"][0]["start"], _WINDOW["windows"][0]["bases"]
_ACCESSION = refget_accession("13")

RSID = "rs761191455"
#: The new snapshot's spelling and the old one's, as each snapshot holds them (domain constants).
NEW = ("13", 48041103, "T", "TG")
OLD = ("13", 48041104, "G", "GG")


def read(chrom: str, start: int, end: int) -> str | None:
    """1-based inclusive GRCh38 bases from the recorded window, clipped at the left edge only."""
    if chrom != "13" or end < _FIRST or end > _FIRST + len(_BASES) - 1:
        return None
    return _BASES[max(start, _FIRST) - _FIRST : end - _FIRST + 1]


class _RecordedBases(_DataProxy):
    """A `ga4gh.vrs` data proxy holding only the recorded window; any read outside it raises."""

    def get_sequence(self, identifier: str, start: int | None = None, end: int | None = None) -> str:
        lo, hi = int(start or 0) - (_FIRST - 1), int(end or 0) - (_FIRST - 1)
        if identifier != f"ga4gh:{_ACCESSION}" or lo < 0 or hi > len(_BASES) or hi < lo:
            raise ValueError(f"{identifier}:[{start},{end}) is outside the recorded window")
        return _BASES[lo:hi]

    def get_metadata(self, identifier: str) -> dict:
        if identifier != f"ga4gh:{_ACCESSION}":
            raise KeyError(identifier)
        return {"length": 10**9, "aliases": [identifier], "alphabet": "ACGT"}


class RecordedSequences(SequenceProxy):
    """The run's own proxy class, reading the recorded window instead of seqrepo."""

    def proxy(self) -> _DataProxy:
        return _RecordedBases()

    def subsequence(self, accession: str, start: int, end: int) -> str | None:
        return read("13", start + 1, end) if accession == _ACCESSION else None


def _mint(minter: VrsMinter):
    return lambda chrom, start, ref, alt: minter.mint(chrom, start, ref, alt)[0]


OFFLINE = _mint(VrsMinter(offline=True))


# ── the judge on its own ─────────────────────────────────────────────────────────────────────────


def test_the_window_holds_both_spellings_and_the_walk_finds_exactly_them() -> None:
    assert read("13", NEW[1], NEW[1] + 1) == "TG", "the recorded bases are the ones the spellings name"
    assert indel_spellings(*NEW, read) == [NEW, OLD]
    assert indel_spellings(*OLD, read) == [NEW, OLD], "either spelling walks to the same anchors"
    assert indel_spellings(*NEW, lambda *_: None) is None


#: `(authored chrom, start, ref, alts)`, the read window, and the answer the one judge owes, against the
#: new snapshot's `13:48041103 T>TG`. The corpus every registered judge is run over.
CORPUS: list[tuple[str, tuple, bool, bool | None]] = [
    ("the cpic row: old anchor, no ref", ("13", OLD[1], None, None), True, True),
    ("the old anchor and its base", ("13", OLD[1], "G", None), True, True),
    ("the old spelling whole", OLD, True, True),
    ("a half coordinate (no chrom)", (None, OLD[1], None, None), True, True),
    ("no reference read", ("13", OLD[1], None, None), False, None),
    ("the old spelling whole, offline", OLD, False, None),
    ("outside every base the event touches", ("13", NEW[1] + 40, None, None), True, False),
    ("another contig", ("12", OLD[1], None, None), True, False),
    ("a padded ref, no alt", ("13", NEW[1] - 1, "CT", None), True, None),
]


@pytest.mark.parametrize(
    ("authored", "reads", "expected"), [c[1:] for c in CORPUS], ids=[c[0] for c in CORPUS]
)
def test_names_event_answers_three_ways(authored: tuple, reads: bool, expected: bool | None) -> None:
    window = read if reads else None
    assert names_event(*authored, Allele(*NEW), mint=OFFLINE, read_window=window) is expected


def test_an_insertion_touches_its_anchor_and_the_next_base_only() -> None:
    """A 3 bp insertion `GAC` after the `T` slides through `GAAA` to anchor 48041105, and sits between
    that anchor and 48041106. A position past that is outside the event however long the payload."""
    ins = Allele("13", NEW[1], "T", "TGAC")
    assert [s[1] for s in indel_spellings(*ins.spelling, read)] == [NEW[1], NEW[1] + 1, NEW[1] + 2]
    assert names_event("13", NEW[1] + 3, None, None, ins, mint=OFFLINE, read_window=read) is None
    assert names_event("13", NEW[1] + 4, None, None, ins, mint=OFFLINE, read_window=read) is False


def test_a_moved_substitution_is_a_different_event_with_no_reference() -> None:
    """A substitution cannot slide, so no read is needed to call another position another event."""
    snv = Allele("2", 135851076, "G", "A")
    assert names_event("2", 135851077, None, None, snv, mint=OFFLINE, read_window=None) is False
    assert names_event("2", 135851076, None, None, snv, mint=OFFLINE, read_window=None) is True


# ── the class: every judge of two spellings answers what the one judge answers ──────────────────
#
# A registry, walked: each entry adapts one site that compares two spellings for event identity onto
# the corpus. `test_the_registry_is_every_caller_of_the_judge` asserts it is every site that calls the
# judge, so a new comparer cannot join the tier without joining the corpus.


def _locus(spelling: tuple, **extra: object) -> dict[str, object]:
    chrom, start, ref, alt = spelling
    return {"chrom": chrom, "start": start, "ref": ref, "alts": alt, **extra}


def _rows(spelling: tuple) -> list[ResolutionRow]:
    chrom, start, ref, alt = spelling
    return [
        ResolutionRow(
            variant_key=RSID, rsid=RSID, chrom=chrom, start=start, ref=ref, alts=alt, status="resolved"
        )
    ]


_VERDICT = {"same_event": True, "different_event": False, "undecided": None}


def _via_authored_event(authored: tuple, window) -> bool | None:
    judged = authored_event(authored, _locus(NEW), mint=OFFLINE, read_window=window)
    return None if judged is None else _VERDICT[judged[0]]


def _via_coordinate_verdict(authored: tuple, window) -> bool | None:
    chrom, start, ref, _alts = authored
    return coordinate_verdict(chrom or NEW[0], start, ref, [_locus(NEW)], mint=OFFLINE, read_window=window)


def _via_same_events(authored: tuple, window) -> bool | None:
    if authored[2] is None or authored[3] is None:
        pytest.skip("a recorded row is a whole spelling")
    return _same_events(_rows(authored), _rows(NEW), mint=OFFLINE, read_window=window)


def _via_compare_placements(authored: tuple, window) -> bool | None:
    if authored[2] is None or authored[3] is None:
        pytest.skip("a placement is a whole spelling")
    check = compare_placements(
        {RSID: [_locus(NEW)]},
        {RSID: "ensembl"},
        {"clinvar": {RSID: [_locus(authored)]}},
        mint=OFFLINE,
        read_window=window,
    )
    if check.contested:
        return False
    return {"same_event": True, "undecided": None}[check.rows[(RSID, (NEW[0], NEW[1], NEW[2], NEW[3]))][1]]


JUDGES = {
    ("events", "authored_event"): _via_authored_event,
    ("resolver", "coordinate_verdict"): _via_coordinate_verdict,
    ("enrich.outcome", "_same_events"): _via_same_events,
    ("placement", "compare_placements"): _via_compare_placements,
}


@pytest.mark.parametrize(
    ("authored", "reads", "expected"), [c[1:] for c in CORPUS], ids=[c[0] for c in CORPUS]
)
@pytest.mark.parametrize("site", list(JUDGES), ids=[".".join(k) for k in JUDGES])
def test_every_judge_answers_the_corpus_as_the_one_judge_does(
    site: tuple[str, str], authored: tuple, reads: bool, expected: bool | None
) -> None:
    if site == ("placement", "compare_placements") and authored[0] != NEW[0]:
        pytest.skip("a witness on another contig is no counterpart: unplaced, never compared")
    assert JUDGES[site](authored, read if reads else None) is expected


#: The judge's entry points, and the functions allowed to call them: the registry above plus the judge's
#: own internals and the run that stamps the verdict on a row.
_ENTRY_POINTS = {"same_event", "names_event", "authored_event", "same_allele_sets"}
_INTERNAL = {
    ("events", "names_event"),
    ("events", "same_allele_sets"),
    ("enrich.orchestration", "_run_enrichment"),
}


def test_the_registry_is_every_caller_of_the_judge() -> None:
    """An AST walk over the enricher: every function calling the judge is registered or internal."""
    src = _ROOT / "enricher" / "src" / "just_dna_enricher"
    callers: set[tuple[str, str]] = set()
    for path in src.rglob("*.py"):
        module = ".".join(path.relative_to(src).with_suffix("").parts)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.FunctionDef):
                continue
            for call in ast.walk(node):
                if isinstance(call, ast.Call):
                    name = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
                    if name in _ENTRY_POINTS:
                        callers.add((module, node.name))
    assert callers == set(JUDGES) | _INTERNAL


def test_the_cell_is_a_closed_vocabulary_and_the_judge_writes_only_its_members() -> None:
    assert set(AUTHORED_EVENT_VERDICT.values()) == VALID_AUTHORED_EVENT_VERDICTS
    with pytest.raises(ValueError):
        ResolutionRow(variant_key=RSID, authored_event="respelled")


# ── the drift canary: respelled / moved / unknown ────────────────────────────────────────────────


def test_rederive_drift_is_three_valued() -> None:
    same = _same_events(_rows(OLD), _rows(NEW), mint=OFFLINE, read_window=read)
    unknown = _same_events(_rows(OLD), _rows(NEW), mint=OFFLINE, read_window=None)
    moved = _same_events(
        _rows(("2", 135851077, "G", "A")), _rows(("2", 135851076, "G", "A")), mint=OFFLINE, read_window=None
    )
    assert (same, unknown, moved) == (True, None, False)
    texts = [str(SubjectDrift(RSID, "a", "b", respelled)) for respelled in (True, None, False)]
    assert "respelled" in texts[0] and "undecided" in texts[1] and "moved" in texts[2]
    assert len(set(texts)) == 3


def test_an_offline_locus_kept_whole_against_its_online_pieces_is_unknown_never_moved() -> None:
    """RM376's case, `rs746071566`: offline the hosting filter cannot settle an indel ALT and keeps the
    whole locus; online RM270 splits it and keeps the piece the genotype names. The source answered
    once; the two runs kept different indel ALTs of it, so the drift is undecided, not a move."""
    whole = [Allele("X", 100, "AG", "A"), Allele("X", 100, "AG", "AGGG"), Allele("X", 100, "AG", "AGGGG")]
    piece = [Allele("X", 100, "AG", "A")]
    assert same_allele_sets(whole, piece, mint=OFFLINE, read_window=None) is None
    assert (
        same_allele_sets(
            [Allele("X", 100, "G", "A"), Allele("X", 100, "G", "T")],
            [Allele("X", 100, "G", "A")],
            mint=OFFLINE,
            read_window=None,
        )
        is False
    )
    assert same_event(Allele(*OLD), Allele(*NEW), mint=OFFLINE, read_window=read) is True


# ── end to end: the real row, enriched against the new spelling, compiled, reversed ─────────────


_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)


def _spec(root: Path, start: int = OLD[1]) -> Path:
    """The cpic_gene_pairs row, verbatim but for `start` where a test moves it."""
    spec = root / "spec"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "haplotypes.csv").write_text(
        f"haplotype_name,rsid,chrom,start,allele,gene\n*1,{RSID},13,{start},G,NUDT15\n", encoding="utf-8"
    )
    return spec


def _snapshot(root: Path) -> Path:
    """An Ensembl snapshot placing the rsID as the new release does."""
    data = root / "ensembl" / "data"
    data.mkdir(parents=True)
    chrom, start, ref, alt = NEW
    pl.DataFrame([{"id": RSID, "chrom": chrom, "start": start, "ref": ref, "alt": alt}]).write_parquet(
        data / "variants.parquet"
    )
    return root / "ensembl"


class _NoLiveEnsembl:
    def resolve_rsid(self, rsid: str):
        raise AssertionError(f"live Ensembl asked about {rsid}")

    def resolve_rsid_rest(self, rsid: str):
        return None, None

    def close(self) -> None:
        return None


def _enrich(spec: Path, root: Path, monkeypatch: pytest.MonkeyPatch, *, recorded: bool = True, **kwargs):
    if recorded:
        monkeypatch.setattr("just_dna_enricher.enrich.orchestration.SequenceProxy", RecordedSequences)
    options = {
        "ensembl_cache": _snapshot(root),
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


def _resolution(spec: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO((spec / "resolution.csv").read_text(encoding="utf-8"))))


def _pair_record(spec: Path) -> dict:
    doc = json.loads((spec / VERIFICATION_JSON).read_text(encoding="utf-8"))
    return {r["check"]: r for r in doc["records"]}["rsid_coordinate_agreement"]


def _contradictions(warnings: list[str]) -> list[str]:
    return [w for w in warnings if "are left exactly as authored" in w]


_ACCUSING = re.compile(r"\b(contradicts|disagreement|disagrees)\b")


def test_the_cpic_row_is_judged_the_same_event_and_compiles_as_agreement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    spec = _spec(tmp_path)
    _enrich(spec, tmp_path, monkeypatch)
    (row,) = _resolution(spec)
    assert (row["start"], row["ref"], row["alts"], row["authored_event"], row["judged_coordinate"]) == (
        str(NEW[1]),
        NEW[2],
        NEW[3],
        "same_event",
        f"13:{OLD[1]}",
    )
    assert _pair_record(spec)["findings"] == 0, "the insertion's one-base ref is not a substitution"

    first = compile_module(spec, tmp_path / "a1", strict=True)
    assert first.success, first.errors
    assert _contradictions(first.manifest.compilation.warnings) == []
    hap = pl.read_parquet(tmp_path / "a1" / "haplotypes.parquet")
    assert (hap["chrom"].to_list(), hap["start"].to_list(), hap["ref"].to_list()) == (
        ["13"],
        [OLD[1]],
        [None],
    )

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    second = compile_module(tmp_path / "rev", tmp_path / "a2", strict=True)
    assert second.success, second.errors
    one, two = first.manifest, second.manifest
    assert (one.content_signature, one.compilation.resolution_signature, one.artifact.digest) == (
        two.content_signature,
        two.compilation.resolution_signature,
        two.artifact.digest,
    )
    assert _contradictions(one.compilation.warnings) == _contradictions(two.compilation.warnings) == []


def test_offline_the_same_row_is_undecided_and_compile_withholds_without_accusing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    spec = _spec(tmp_path)
    _enrich(spec, tmp_path, monkeypatch, recorded=False, offline=True)
    (row,) = _resolution(spec)
    assert row["authored_event"] == "undecided"
    assert _pair_record(spec)["findings"] == 0, "undecided is never a disagreement"

    result = compile_module(spec, tmp_path / "a1")
    assert result.success, result.errors
    (line,) = _contradictions(result.manifest.compilation.warnings)
    assert "undecided" in line and not _ACCUSING.search(line), line


def test_a_coordinate_outside_the_event_is_a_different_event_and_still_accused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    spec = _spec(tmp_path, start=NEW[1] + 40)
    _enrich(spec, tmp_path, monkeypatch)
    (row,) = _resolution(spec)
    assert row["authored_event"] == "different_event"
    assert _pair_record(spec)["findings"] == 1
    result = compile_module(spec, tmp_path / "a1")
    (line,) = _contradictions(result.manifest.compilation.warnings)
    assert "contradicts" in line


def test_an_identical_spelling_records_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """Nothing to judge: the compiler sees agreement on its own, and a verdict on every agreeing row
    would only be noise in every committed table."""
    spec = _spec(tmp_path, start=NEW[1])
    _enrich(spec, tmp_path, monkeypatch)
    (row,) = _resolution(spec)
    assert row["authored_event"] == ""


def test_the_pair_check_reads_the_judge(tmp_path: Path) -> None:
    """`check_rsid_coordinates` with the reference reaches a verdict where it used to accuse."""
    pairs = [(RSID, "13", OLD[1], None)]
    loci = {RSID: [_locus(NEW)]}
    judged = check_rsid_coordinates(pairs, loci, mint=OFFLINE, read_window=read)
    blind = check_rsid_coordinates(pairs, loci, mint=OFFLINE, read_window=None)
    assert (judged.subjects, judged.disagreements, judged.undecided) == (1, [], [])
    assert (blind.subjects, blind.disagreements, blind.undecided) == (0, [], [RSID])


@pytest.mark.skipif(os.environ.get("JUST_DNA_NETWORK_TESTS") != "1", reason="network test (opt-in)")
def test_the_cpic_row_against_seqrepo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_ambient_caches: Path
) -> None:
    """The same judgement with the run's own sequence service, not the recorded window."""
    spec = _spec(tmp_path)
    _enrich(spec, tmp_path, monkeypatch, recorded=False)
    (row,) = _resolution(spec)
    assert row["authored_event"] == "same_event"
    assert row["vrs_id"], "online, the insertion's id is minted"
