"""The repeat-band cross-check (RM165), run against **both** corpus modules.

Running only `htt_repeat_expansion` would prove nothing: it is the module the catalogue agrees with
on the bands it states, so a check that compared nothing at all would pass it. `fmr1_cgg_repeat` is
the one that disagrees, and it disagrees in the place the whole design turns on — STRchive runs one
`intermediate` band from 45 to 200 where the module states 45–54 and 55–200, and 55 is the
premutation threshold. Both are exercised here, from the shipped spec directories.

**Every expected value is computed from the fixture at runtime.** `assets/strchive_loci_slice.json`
is cut verbatim from the real `dashnowlab/STRchive` catalogue and the numbers in it will drift when
the project re-curates a locus; a `55` typed into an assertion would convert that drift into a
permanently red test. So the tests read the boundary out of the two files and assert the relationship
between them.

The reference modules are **copied into `tmp_path` first**. They are closed with a `verification.json`
binding, and this check writes an attestation — running it in place would move `module_hash` on two
shipped examples.
"""

import ast
import inspect
import json
import os
import shutil
from pathlib import Path

import pytest
from just_dna_enricher import strchive
from just_dna_enricher.provenance import DRAFT_PROJECTIONS
from just_dna_enricher.strchive import (
    Band,
    BandFinding,
    RepeatBandResult,
    StrchiveCatalogue,
    check_repeat_bands,
    compare_bands,
    load_strchive_catalogue,
    parse_locus,
)
from just_dna_format.binning import RepeatAlleleRow, _bin_groups
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.vocab import VALID_VERIFICATION_CHECKS

_ROOT = Path(__file__).resolve().parents[2]
_SLICE = _ROOT / "assets" / "strchive_loci_slice.json"
_EXAMPLES = _ROOT / "reference_examples"

#: The two shipped modules that carry a `repeat_alleles.csv`, and the STRchive locus each one is
#: about. Read off the corpus rather than invented, which is what makes "the source agrees with one
#: and is coarser than the other" a measurement instead of a claim.
_CORPUS = {"htt_repeat_expansion": "HD_HTT", "fmr1_cgg_repeat": "FXS_FMR1"}


@pytest.fixture(scope="module")
def catalogue() -> StrchiveCatalogue:
    return load_strchive_catalogue(_SLICE)


def _module(tmp_path: Path, name: str, *, into: str | None = None) -> Path:
    """A writable copy of a shipped reference module — the check attests, and those are closed."""
    target = tmp_path / (into or name)
    shutil.copytree(_EXAMPLES / name, target)
    return target


def _locus(catalogue: StrchiveCatalogue, locus_id: str) -> strchive.StrchiveLocus:
    return next(locus for locus in catalogue.loci if locus.locus_id == locus_id)


def _authored_bins(spec_dir: Path) -> list[RepeatAlleleRow]:
    return strchive.load_repeat_alleles(spec_dir)


def test_the_fixture_is_the_two_corpus_loci_plus_the_two_shapes_that_have_no_corpus(
    catalogue: StrchiveCatalogue,
) -> None:
    """What the slice has to contain for the rest of this file to mean anything.

    HTT and FMR1 are the corpus; the `ARX` pair is the published fan-out (two loci sharing
    `(gene, motif)`), and `ADTKD_MUC1` is a locus the source states no bands for. Both of those are
    real records from the same file, not constructed cases.
    """
    assert {locus.locus_id for locus in catalogue.loci} >= set(_CORPUS.values())
    contested = [key for key, loci in catalogue.by_gene_and_motif().items() if len(loci) > 1]
    assert contested, "the slice must keep a contested (gene, motif) key"
    assert any(not locus.bands for locus in catalogue.loci), "and one locus stating no bands"


def test_every_finding_kind_compare_bands_can_emit_has_its_own_sentence() -> None:
    """A verdict function with several arms owes a reason function with the same arms.

    An **equality over a walked set**: the kinds are read out of `compare_bands`' own AST, so a
    seventh arm added without a sentence fails here rather than raising `KeyError` at the moment a
    real module hits it. Pairwise distinct, too — two arms sharing a sentence is the same defect
    wearing a different hat.
    """
    tree = ast.parse(inspect.getsource(compare_bands))
    emitted = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "BandFinding"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    assert emitted == set(strchive._FINDING_SENTENCES), sorted(
        emitted.symmetric_difference(strchive._FINDING_SENTENCES)
    )
    sentences = list(strchive._FINDING_SENTENCES.values())
    assert len(set(sentences)) == len(sentences), "two arms share a sentence"


def test_the_attestation_member_is_wired_rather_than_reserved() -> None:
    """The member flipped out of the RESERVED block, and this pass is what puts it."""
    assert "repeat_band_agreement" in VALID_VERIFICATION_CHECKS
    record = strchive.verification_record(
        RepeatBandResult(compared=[("HTT", "CAG", None)], dataset="strchive_v0")
    )
    assert record.check == "repeat_band_agreement" and record.skipped is None


# ── the corpus, both modules ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("name", sorted(_CORPUS))
def test_both_corpus_modules_are_compared_against_their_locus(
    tmp_path: Path, catalogue: StrchiveCatalogue, name: str
) -> None:
    """The precondition for anything below: each shipped module matches exactly one catalogue locus.

    Parametrized rather than written once for HTT, because "the check ran" is the claim a
    single-module test would silently stop making.
    """
    result = check_repeat_bands(_module(tmp_path, name), catalogue=catalogue, write=False)
    assert len(result.compared) == 1 and not result.withheld
    assert {finding.locus_id for finding in result.findings} <= {_CORPUS[name]}


def test_fmr1_finding_names_the_boundary_the_catalogue_does_not_have(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """The measurement the whole item rests on: STRchive is one band coarser exactly where it matters.

    The expected value is **derived**: it is the authored lower bound that lies strictly inside
    STRchive's `intermediate` band. Asserting `55` outright would pin a number the source may
    re-curate, and would not show that the finding is about the module's extra division at all.
    """
    spec = _module(tmp_path, "fmr1_cgg_repeat")
    locus = _locus(catalogue, "FXS_FMR1")
    intermediate = next(band for band in locus.bands if band.label == "intermediate")
    expected = sorted(
        row.measure_min
        for row in _authored_bins(spec)
        if row.measure_min is not None and intermediate.divides(row.measure_min)
    )
    assert expected, "the fixture no longer has an authored bound inside STRchive's intermediate band"

    result = check_repeat_bands(spec, catalogue=catalogue, write=False)
    extra = [f for f in result.findings if f.kind == "boundary_only_in_module"]
    assert [f.value for f in extra] == expected
    # And the finding says *where* — a bare "the tables differ" would not tell an author which line
    # they are about to lose.
    assert str(intermediate) in str(extra[0]) and "no boundary" in str(extra[0])


def test_htt_agrees_on_the_bands_the_catalogue_states_and_is_finer_below_them(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """The other half of the measurement, and one correction to the entry that filed it.

    STRchive's `benign 6–26` / `intermediate 27–35` reproduce the shipped table exactly — no
    `boundary_only_in_source`, no floor difference. But the module *also* divides STRchive's single
    pathogenic band, at the reduced-penetrance / full-penetrance line, so HTT is finer than the
    catalogue too. Both corpus modules refine it; only the FMR1 case was named when the item was
    written.
    """
    spec = _module(tmp_path, "htt_repeat_expansion")
    locus = _locus(catalogue, "HD_HTT")
    pathogenic = next(band for band in locus.bands if band.label == "pathogenic")

    result = check_repeat_bands(spec, catalogue=catalogue, write=False)
    kinds = sorted(f.kind for f in result.findings)
    assert "boundary_only_in_source" not in kinds, "the source states no boundary the module lacks"
    assert "floor_only_in_module" not in kinds, "the two agree on where the axis starts"
    extra = [f for f in result.findings if f.kind == "boundary_only_in_module"]
    assert [f.other for f in extra] == [pathogenic], "the extra division is inside the top band"


def test_the_catalogue_ceiling_is_reported_and_written_nowhere(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """`pathogenic_max` is a corpus maximum, not a clinical bound — the refusal, demonstrated.

    Two assertions, and the second is the one that matters: the number is in the finding, and the
    authored table's bytes are untouched. A module that imported 250 as `measure_max` would answer
    *nothing at all* for a 300-repeat allele, silently and under `--strict` too.
    """
    spec = _module(tmp_path, "htt_repeat_expansion")
    locus = _locus(catalogue, "HD_HTT")
    ceiling = max(band.hi for band in locus.bands if band.hi is not None)
    before = (spec / "repeat_alleles.csv").read_bytes()

    result = check_repeat_bands(spec, catalogue=catalogue, write=False)
    reported = [f for f in result.findings if f.kind == "ceiling_only_in_source"]
    assert [f.source_value for f in reported] == [ceiling]

    after = (spec / "repeat_alleles.csv").read_bytes()
    assert after == before, "the check repaired a cell"
    assert str(int(ceiling)) not in after.decode("utf-8"), "the catalogue ceiling reached a cell"


@pytest.mark.parametrize("name", sorted(_CORPUS))
def test_strict_reports_exactly_what_best_effort_reports(
    tmp_path: Path, catalogue: StrchiveCatalogue, name: str
) -> None:
    """`--strict` never escalates a source disagreement, deliberately.

    Two expert bodies drawing a threshold in different places is a difference between authorities;
    failing a compile over it would have the format arbitrate between the two it depends on. Asserted
    on both corpus modules, including the one that disagrees, because a test run only on the agreeing
    module would pass with the escalation still in place.
    """
    strict = check_repeat_bands(
        _module(tmp_path, name, into="strict"), catalogue=catalogue, mode="strict", write=False
    )
    lenient = check_repeat_bands(
        _module(tmp_path, name, into="lenient"), catalogue=catalogue, write=False
    )
    assert [str(f) for f in strict.findings] == [str(f) for f in lenient.findings]
    assert strict.mode == "strict" and lenient.mode == "best_effort"


# ── the arms with no corpus behind them ─────────────────────────────────────────────────────────


def _spec(tmp_path: Path, rows: list[str], name: str = "spec") -> Path:
    """A minimal spec directory carrying one `repeat_alleles.csv`.

    `measure_kind` and `unresolved` are written explicitly on every row: both are *defaulted, not
    optional*, and `load_csv_rows` turns an empty cell into `None` while keeping the key, so a blank
    one fails on type rather than falling back (`@requiredness-three-shapes`).
    """
    spec = tmp_path / name
    spec.mkdir(parents=True, exist_ok=True)
    header = "gene,repeat_unit,measure_kind,measure_min,measure_max,measure_tiling,conclusion,unresolved"
    (spec / "repeat_alleles.csv").write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return spec


def test_a_boundary_the_source_states_and_the_module_does_not_is_the_other_arm(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """The symmetric case: a module coarser than the catalogue.

    No corpus module is, so it is built from the catalogue's own HTT bands — one bin spanning the
    benign and intermediate bands. The finding must name the division the module lost, which is the
    same sentence shape the FMR1 case gets in the other direction.
    """
    locus = _locus(catalogue, "HD_HTT")
    benign = next(b for b in locus.bands if b.label == "benign")
    intermediate = next(b for b in locus.bands if b.label == "intermediate")
    spec = _spec(
        tmp_path,
        [
            f"HTT,CAG,repeat_count,{int(benign.lo)},{int(intermediate.hi)},,'one coarse bin',false",
            f"HTT,CAG,repeat_count,{int(intermediate.hi) + 1},,,'the rest',false",
        ],
    )
    result = check_repeat_bands(spec, catalogue=catalogue, write=False)
    missing = [f for f in result.findings if f.kind == "boundary_only_in_source"]
    assert len(missing) == 1
    # The window between `benign_max` and `intermediate_min`; under this group's quantised default the
    # message names the upper endpoint, which is the lower bound of the band the source starts there.
    assert missing[0].value == intermediate.lo
    assert "no boundary" in str(missing[0])


def test_the_same_division_spelled_for_either_tiling_agrees_with_the_source(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """One division, two spellings, and neither may read as a disagreement.

    Under quantised tiling adjacent bins are `[6,26] [27,35]`; under continuous they share the
    endpoint, `[6,26] [26,35]` (`@dense-bin-boundary`). STRchive states its bands in the quantised
    form, so a continuous table saying exactly the same thing must not read as a difference — which is
    why the comparison reads lower bounds against a window rather than matching endpoints.

    Both tables are generated from the catalogue's own bands, so this asserts a property of the
    comparison rather than of two hand-typed fixtures.
    """
    locus = _locus(catalogue, "HD_HTT")
    bands = list(locus.bands)
    assert len(bands) >= 3 and all(b.lo is not None and b.hi is not None for b in bands)

    quantised = _spec(tmp_path, [
        f"HTT,CAG,repeat_count,{int(b.lo)},{int(b.hi)},quantised,'{b.label}',false" for b in bands
    ], name="quantised")
    # The same divisions with the endpoint shared: each bin starts where the previous one ended.
    continuous = _spec(tmp_path, [
        f"HTT,CAG,repeat_count,{int(bands[0].lo if i == 0 else bands[i - 1].hi)},{int(b.hi)},"
        f"continuous,'{b.label}',false"
        for i, b in enumerate(bands)
    ], name="continuous")

    verdicts = {}
    for spec in (quantised, continuous):
        result = check_repeat_bands(spec, catalogue=catalogue, write=False)
        assert len(result.compared) == 1
        verdicts[spec.name] = sorted(f.kind for f in result.findings)
    assert verdicts["quantised"] == verdicts["continuous"] == [], verdicts


def test_a_contested_gene_and_motif_key_is_withheld_rather_than_resolved_by_file_order(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """A source's own fan-out is a finding, never a `mode()` winner (`@multiplicity-is-a-finding`).

    `ARX` carries two loci under one `(gene, motif)` key in the published file. Comparing against the
    first would make the verdict depend on the order records happen to appear in.
    """
    gene, motif = next(
        key for key, loci in catalogue.by_gene_and_motif().items() if len(loci) > 1
    )
    spec = _spec(tmp_path, [f"{gene},{motif},repeat_count,1,9,,'a bin',false"])
    result = check_repeat_bands(spec, catalogue=catalogue, write=False)

    assert result.compared == [] and result.findings == []
    assert result.contested == [(gene, motif)]
    ids = sorted(locus.locus_id for locus in catalogue.by_gene_and_motif()[(gene, motif)])
    reason = result.withheld[0][1]
    assert all(locus_id in reason for locus_id in ids), reason


def test_a_locus_stating_no_bands_is_withheld_not_read_as_agreement(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """Twelve of the published loci state no bands. Absent is not agreement."""
    locus = next(locus for locus in catalogue.loci if not locus.bands)
    spec = _spec(tmp_path, [f"{locus.gene},{locus.motifs[0]},repeat_count,1,9,,'a bin',false"])
    result = check_repeat_bands(spec, catalogue=catalogue, write=False)
    assert result.compared == [] and result.findings == []
    assert locus.locus_id in result.withheld[0][1]


def test_an_unmatched_group_says_whether_the_gene_or_the_motif_is_the_miss(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """Two absences, two sentences: a reader chasing a skipped locus looks in two different places.

    A gene the catalogue has never heard of is one answer; a gene it carries under a motif that does
    not match is another, and only the second is worth checking the strand for.
    """
    known = _locus(catalogue, "HD_HTT")
    unknown_gene = _spec(tmp_path, ["NOTAGENE,CAG,repeat_count,1,9,,'a bin',false"], name="gene")
    wrong_motif = _spec(
        tmp_path, [f"{known.gene},AAAAT,repeat_count,1,9,,'a bin',false"], name="motif"
    )

    gene_reason = check_repeat_bands(unknown_gene, catalogue=catalogue, write=False).withheld[0][1]
    motif_reason = check_repeat_bands(wrong_motif, catalogue=catalogue, write=False).withheld[0][1]
    assert "no locus for NOTAGENE" in gene_reason
    assert "under no motif" in motif_reason and known.gene in motif_reason
    assert gene_reason != motif_reason


# ── what gets attested, and what does not ───────────────────────────────────────────────────────


def test_a_module_with_no_band_table_attests_nothing(tmp_path: Path, catalogue: StrchiveCatalogue) -> None:
    """The check does not *apply*, which is not the same as having run and found nothing.

    Attesting here would mine a nonce and publish a `manifest.verification` block about a question the
    module cannot pose — `enrich_pgx`'s rule for a module carrying no PGx table.
    """
    spec = tmp_path / "bare"
    spec.mkdir()
    result = check_repeat_bands(spec, catalogue=catalogue)
    assert result.compared == [] and result.findings == []
    assert not (spec / VERIFICATION_JSON).exists()


def test_no_catalogue_is_a_no_reference_skip_rather_than_a_clean_pass(tmp_path: Path) -> None:
    """Nobody-asked is a third state, and it must reach the attestation as one.

    A module whose bands were never compared and one whose bands agree ship identical manifests unless
    the absence is recorded, which is the collapse the whole attestation exists to undo.
    """
    spec = _module(tmp_path, "htt_repeat_expansion")
    check_repeat_bands(spec, catalogue=None)
    doc = json.loads((spec / VERIFICATION_JSON).read_text(encoding="utf-8"))
    record = next(r for r in doc["records"] if r["check"] == "repeat_band_agreement")
    assert record["skipped"] == "no_reference"
    assert record.get("findings") in (None, 0) and "strchive build" in record["detail"]


def test_the_record_counts_groups_in_disagreement_not_sentences(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """`VerificationRecord` refuses more findings than subjects, and HTT is one group with two of them.

    A count of sentences is not a count of things checked. The sentences travel in `detail`, which is
    where a human reads them, and the numerator stays a property of the comparison.
    """
    spec = _module(tmp_path, "htt_repeat_expansion")
    result = check_repeat_bands(spec, catalogue=catalogue, write=False)
    assert len(result.findings) > len(result.compared), "HTT must differ in more than one way"

    record = strchive.verification_record(result)
    assert (record.subjects, record.findings) == (len(result.compared), 1)
    assert record.release == catalogue.dataset
    assert record.source == "strchive"


def test_the_attestation_is_written_into_a_module_that_was_compared(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """End to end through the real writer, on the module that disagrees."""
    spec = _module(tmp_path, "fmr1_cgg_repeat")
    check_repeat_bands(spec, catalogue=catalogue)
    doc = json.loads((spec / VERIFICATION_JSON).read_text(encoding="utf-8"))
    record = next(r for r in doc["records"] if r["check"] == "repeat_band_agreement")
    assert record["subjects"] == 1 and record["findings"] == 1
    assert "compared 1 repeat-count bin group" in record["detail"]


def test_an_unreadable_band_table_refuses_in_both_modes(tmp_path: Path, catalogue: StrchiveCatalogue) -> None:
    """`strict` not escalating a *difference* says nothing about a file that will not load."""
    spec = _spec(tmp_path, ["HTT,CAG,repeat_count,notanumber,9,,'a bin',false"])
    for mode in ("best_effort", "strict"):
        with pytest.raises(strchive.StrchiveError, match="repeat_alleles.csv is invalid"):
            check_repeat_bands(spec, catalogue=catalogue, mode=mode, write=False)


def test_a_module_that_bins_only_the_actionable_range_is_not_disagreeing_about_a_floor(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """Binning only from the pathogenic threshold up is a normal shape, not a threshold dispute.

    An unconditional "the two lowest bounds differ" fires on every such module and puts a finding
    into a hashed record about a decision the author made deliberately. The floor arm is gated the
    same way the boundary arms are: it fires only where the module's floor *cuts* a band the source
    classifies.
    """
    locus = _locus(catalogue, "HD_HTT")
    pathogenic = next(band for band in locus.bands if band.label == "pathogenic")
    spec = _spec(tmp_path, [
        f"HTT,CAG,repeat_count,{int(pathogenic.lo)},,,'only the actionable range',false",
    ])
    result = check_repeat_bands(spec, catalogue=catalogue, write=False)
    assert len(result.compared) == 1
    assert [f.kind for f in result.findings if f.kind.startswith("floor")] == []


def test_a_floor_that_cuts_a_band_the_source_classifies_is_reported(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """The case the floor arm exists for: counts the catalogue calls benign match no bin at all.

    Built one above the catalogue's own lowest bound, so the finding is about the module leaving part
    of a band unbinned rather than about the two covering different ranges.
    """
    locus = _locus(catalogue, "HD_HTT")
    benign = next(band for band in locus.bands if band.label == "benign")
    floor = int(benign.lo) + 1
    spec = _spec(tmp_path, [f"HTT,CAG,repeat_count,{floor},,,'from one above benign_min',false"])

    result = check_repeat_bands(spec, catalogue=catalogue, write=False)
    found = [f for f in result.findings if f.kind == "floor_only_in_module"]
    assert [f.value for f in found] == [float(floor)]
    assert str(benign) in str(found[0])


def test_every_group_withheld_is_a_run_over_nothing_rather_than_a_skip(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """`subjects=0` with no `skipped` is the model's encoding for *ran and had nothing in scope*.

    The check really did run — a catalogue was read and every authored group was put to it — so
    `nothing_to_check` ("the module carries no row this check applies to") would be false about a
    module that carries a band table. The genuinely inapplicable cases are skipped earlier.
    """
    spec = _spec(tmp_path, ["NOTAGENE,CAG,repeat_count,1,9,,'a bin',false"], name="unmatched")
    result = check_repeat_bands(spec, catalogue=catalogue, write=False)
    record = strchive.verification_record(result)
    assert (record.skipped, record.subjects, record.findings) == (None, 0, 0)
    assert "NOTAGENE" in record.detail

    # And the table that really does carry no applicable row keeps the skip.
    sentinel = _spec(tmp_path, ["HTT,CAG,repeat_count,,,,'not measured',true"], name="sentinel")
    skipped_result = check_repeat_bands(sentinel, catalogue=catalogue, write=False)
    assert skipped_result.compared == [] and skipped_result.warnings


# ── the builder ─────────────────────────────────────────────────────────────────────────────────


def test_a_failed_download_is_this_module_error_and_leaves_no_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mistyped release tag is a 404, and it must not reach the CLI as an httpx traceback.

    The transport is what is replaced, not the translation under test: the function really runs, and
    the assertion is that `httpx`'s exception does not leave it (`@client-exception-contract`).
    """
    import httpx
    from just_dna_enricher.strchive_build import download_catalogue

    def _refuse(*_args, **_kwargs):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(httpx, "stream", _refuse)
    dest = tmp_path / strchive.CATALOGUE_FILENAME
    with pytest.raises(strchive.StrchiveUnavailable, match="could not download"):
        download_catalogue(dest, "https://example.invalid/loci.json")
    assert sorted(p.name for p in tmp_path.iterdir()) == [], "a .part survived the failure"


def test_a_rebuild_never_leaves_a_release_json_describing_bytes_that_are_gone(
    tmp_path: Path,
) -> None:
    """The provenance and the catalogue are committed together, or neither is.

    Writing the catalogue first and validating after would let a bad rebuild leave new bytes under the
    previous run's `release.json` — and `check-repeat-bands` would then attest the new catalogue under
    the old release label.
    """
    from just_dna_enricher.strchive_build import build_strchive_snapshot

    out = tmp_path / "snap"
    good = build_strchive_snapshot(out, catalogue=_SLICE, release="v0.0.1")
    assert good.dataset == "strchive_v0.0.1"
    first = (out / strchive.CATALOGUE_FILENAME).read_bytes()

    empty = tmp_path / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    with pytest.raises(strchive.StrchiveError, match="zero loci"):
        build_strchive_snapshot(out, catalogue=empty, release="v0.0.2")

    assert (out / strchive.CATALOGUE_FILENAME).read_bytes() == first, "the good catalogue survived"
    assert load_strchive_catalogue(out).dataset == "strchive_v0.0.1"
    assert not list(out.glob("*.incoming")), "the refused bytes were left behind"


def test_a_snapshot_built_from_a_release_tag_records_a_verifiable_digest(tmp_path: Path) -> None:
    """`source_sha256` describes bytes a reader can check with `sha256sum`, not a re-encoding.

    The catalogue is copied rather than re-serialized, which is what makes that true — and it is why
    the builder writes no parquet.
    """
    import hashlib
    import json as _json

    from just_dna_enricher.strchive_build import build_strchive_snapshot

    built = build_strchive_snapshot(tmp_path / "snap", catalogue=_SLICE, release="v0.0.1")
    assert built.catalogue_file.read_bytes() == _SLICE.read_bytes()
    assert built.source_sha256 == hashlib.sha256(_SLICE.read_bytes()).hexdigest()

    release = _json.loads(built.release_file.read_text(encoding="utf-8"))
    assert set(release) >= {
        "source_url", "source_sha256", "dataset", "built_at", "builder_version", "locus_count",
    }
    assert release["locus_count"] == len(load_strchive_catalogue(_SLICE).loci)


# ── the catalogue reader ────────────────────────────────────────────────────────────────────────


def test_a_band_with_neither_bound_is_absent_rather_than_covering_the_axis() -> None:
    """Reading an absent band as open-everywhere would invent a claim the source never made."""
    locus = parse_locus({"id": "X_Y", "gene": "Y", "benign_min": None, "benign_max": None})
    assert locus.bands == ()


def test_a_snapshot_supplies_the_release_label_and_a_bare_file_does_not(tmp_path: Path) -> None:
    """`dataset` is the source's own label or nothing; it is never invented from the filename.

    An unlabelled snapshot is honestly unlabelled — the record then says the comparison happened
    against an unnamed release, which is a weaker claim than a fabricated one and a true one.
    """
    bare = tmp_path / strchive.CATALOGUE_FILENAME
    shutil.copyfile(_SLICE, bare)
    assert load_strchive_catalogue(bare).dataset is None

    snapshot = tmp_path / "snap"
    snapshot.mkdir()
    shutil.copyfile(_SLICE, snapshot / strchive.CATALOGUE_FILENAME)
    (snapshot / strchive.RELEASE_FILENAME).write_text(
        json.dumps({"dataset": "strchive_v0.0.0"}), encoding="utf-8"
    )
    assert load_strchive_catalogue(snapshot).dataset == "strchive_v0.0.0"


def test_a_missing_catalogue_is_its_own_unavailable_type(tmp_path: Path) -> None:
    with pytest.raises(strchive.StrchiveUnavailable):
        load_strchive_catalogue(tmp_path / "nothing.json")


def test_both_motif_orientations_join_because_the_module_has_no_orientation_column() -> None:
    """`repeat_unit` is one string with nothing beside it to say which strand it is written on.

    A minus-strand locus is legitimately authored either way, so the join reads the union — and the
    reference spelling comes first so a locus that publishes both is still one entry per spelling.
    """
    locus = parse_locus({
        "id": "X_Y", "gene": "Y",
        "pathogenic_motif_reference_orientation": ["CAG"],
        "pathogenic_motif_gene_orientation": ["CTG", "CAG"],
    })
    assert locus.motifs == ("CAG", "CTG")


def test_the_partition_is_the_one_the_overlap_rule_is_enforced_over(
    tmp_path: Path, catalogue: StrchiveCatalogue
) -> None:
    """The group key is `_KEY_FIELDS + (trait_efo_id,)`, and comparing on anything else is a bug.

    Demonstrated rather than asserted about the import: two HTT groups differing only in
    `trait_efo_id` are two groups to `binning`, so they must be two subjects here — a coarser
    partition would compare a union the overlap rule never enforced.
    """
    spec = tmp_path / "two-traits"
    spec.mkdir()
    header = (
        "gene,repeat_unit,measure_kind,measure_min,measure_max,trait_efo_id,conclusion,unresolved"
    )
    (spec / "repeat_alleles.csv").write_text(
        f"{header}\n"
        "HTT,CAG,repeat_count,6,26,MONDO_0007739,'a',false\n"
        "HTT,CAG,repeat_count,6,26,EFO_0000001,'b',false\n",
        encoding="utf-8",
    )
    rows = _authored_bins(spec)
    assert len(_bin_groups(rows)) == 2
    result = check_repeat_bands(spec, catalogue=catalogue, write=False)
    assert len(result.compared) == 2


def test_strchive_is_deliberately_absent_from_the_draft_projections() -> None:
    """The map is "drafts a column one of its own checks later compares", and this source does not.

    The split is the whole item: the identity half is drafted and the band half is checked, so the
    columns this check reads were never copies of anything. A projection over `measure_min`/`measure_max`
    would let the tautology skip fire on cells no drafter ever wrote — the false skip that mechanism
    exists to prevent, arriving through the door marked "be consistent with the other providers".
    """
    assert "strchive" not in DRAFT_PROJECTIONS


def test_the_finding_renders_a_whole_number_as_one() -> None:
    """These sentences reach `verification.json`, which is a hashed input.

    `binning.format_group_key` normalizes a group key for exactly this reason; a bound that rendered
    `26.0` in one release and `26` in the next would move a module's bytes with nothing else changed.
    """
    finding = BandFinding(
        "floor_only_in_module", ("HTT", "CAG", None), "HD_HTT",
        value=6.0, source_value=5.0, other=Band("benign", 5.0, 44.0),
    )
    assert "6.0" not in str(finding) and " 6," in str(finding)
    assert str(Band("benign", 6.0, 26.0)) == "benign [6, 26]"


# ── live ────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    not os.getenv("JUST_DNA_NETWORK_TESTS"), reason="set JUST_DNA_NETWORK_TESTS=1 to hit the network"
)
def test_the_fixture_still_describes_the_published_catalogue(tmp_path: Path) -> None:
    """The slice is cut from the real file, so the live catalogue is what says whether it still is.

    Compares the *shape* rather than the numbers: the loci are still there under the same ids, and
    they still carry bands. A live band that has moved is the source re-curating, which is a fact
    about STRchive and not a failure of this package — it is reported by the check, which is the
    whole design.
    """
    from just_dna_enricher.strchive_build import build_strchive_snapshot

    built = build_strchive_snapshot(tmp_path / "snap", release="v2.26.0")
    live = load_strchive_catalogue(built.out_dir)
    fixture = load_strchive_catalogue(_SLICE)

    by_id = {locus.locus_id: locus for locus in live.loci}
    assert set(by_id) >= {locus.locus_id for locus in fixture.loci}
    for locus in fixture.loci:
        assert by_id[locus.locus_id].motifs == locus.motifs, locus.locus_id
        assert bool(by_id[locus.locus_id].bands) == bool(locus.bands), locus.locus_id
    assert built.dataset == "strchive_v2.26.0"
