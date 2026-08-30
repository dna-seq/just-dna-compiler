"""The N-authority clinical-significance concordance check (RM134 § B).

Two real snapshots, both built by their own shipped builders at test time: the committed ClinVar
slice (`assets/clinvar_GRCh38_slice.vcf.gz`) and a PubMind table written at the same locus and run
through `pubmind_build.build_snapshot`. Nothing here mocks a lookup — the point of the check is that
two *normalizations* agree, so a test that hands the comparison pre-normalized values would agree
with itself in exactly the way the check must not.

The locus is HBB `11:5227002`, where the ClinVar slice carries `T>A` as pathogenic (2 stars) and
`T>G` as likely benign (1 star) under one rsID. It is the hazard the two-way check was built around
and it is the right place to put a second authority: an authority-blind comparison would report a
module that is simply right.
"""

import csv
import io
from pathlib import Path

import pytest
from just_dna_compiler.compiler import load_csv_rows
from just_dna_enricher import pubmind as pubmind_reader
from just_dna_enricher.clinical import (
    AUTHORITY_LEG_STATES,
    AUTHORITY_ORDER,
    CLINVAR_AUTHORITY,
    PUBMIND_AUTHORITY,
    clin_sig_concordance,
    concordance_notes,
    concordance_sentences,
    fold_authority_records,
    verify_clin_sig,
)
from just_dna_enricher.clinvar import clinvar_dataset_label, select_by_gene
from just_dna_enricher.clinvar_build import build_snapshot as build_clinvar_snapshot
from just_dna_enricher.clinvar_draft import draft_gene_panel
from just_dna_enricher.concordance import (
    AUTHORITY_CALLS_CSV,
    CONCORDANCE_CSV,
    AuthorityCall,
    classify_concordance,
)
from just_dna_enricher.enrich import EnrichmentError, enrich
from just_dna_enricher.licensing import merge_sources_file, read_sources_file
from just_dna_enricher.provenance import DRAFT_PROJECTIONS, DraftProjection, draft_digest
from just_dna_enricher.pubmind import PUBMIND_CONFIDENCE_UNIT, pubmind_dataset_label
from just_dna_enricher.pubmind_build import build_snapshot as build_pubmind_snapshot
from just_dna_format.base import authored_field_names
from just_dna_format.resolution import ResolutionRow
from just_dna_format.sources import SourceRow
from just_dna_format.spec import VariantRow
from just_dna_format.vocab import VALID_AUTHORED_POSITION, VALID_AUTHORITY_CONCORDANCE

_CLINVAR_SLICE = Path(__file__).parents[2] / "assets" / "clinvar_GRCh38_slice.vcf.gz"

#: The HBB locus both of the slice's opposed `rs334` records sit at.
_CHROM, _START, _REF = "11", 5227002, "T"

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)

_PUBMIND_HEADER = (
    "#Chr\tStart\tEnd\tRef\tAlt\tPVID\tPubMindDB_pathogenicity_sum\t"
    "PubMindDB_paper_level_pathogenicity_score\tPubMindDB_confidence"
)


@pytest.fixture(scope="module")
def clinvar(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The real ClinVar slice, built once — the check reads it exactly as `enrich()` would."""
    out = tmp_path_factory.mktemp("cv")
    build_clinvar_snapshot(_CLINVAR_SLICE, out / "cv")
    return out / "cv"


def _pubmind(directory: Path, rows: list[tuple[str, int, str, str, str, str, str, str]]) -> Path:
    """Build a PubMind snapshot from `(chrom, start, ref, alt, pvid, sig, score, confidence)`.

    Written through the real builder rather than as a hand-made parquet: the column names, the
    normalization and the emitted order are the builder's, so a test writing the parquet itself would
    be asserting against its own idea of the snapshot rather than against the one that ships.
    """
    directory.mkdir(parents=True, exist_ok=True)
    table = directory / "pubmind_slice.txt"
    body = "\n".join(
        f"{chrom}\t{start}\t{start + len(ref) - 1}\t{ref}\t{alt}\t{pvid}\t{sig}\t{score}\t{conf}"
        for chrom, start, ref, alt, pvid, sig, score, conf in rows
    )
    table.write_text(f"{_PUBMIND_HEADER}\n{body}\n", encoding="utf-8")
    out = directory / "snapshot"
    build_pubmind_snapshot(table, out)
    return out


def _no_pubmind(tmp_path: Path) -> Path:
    """A cache path nothing resolves from, for a run that must have no PubMind authority.

    Passed explicitly rather than left to the default resolution, because that reads
    `$JUST_DNA_PUBMIND_CACHE` and then the platformdirs cache — so a machine that happens to hold a
    built snapshot would hand the run a second authority and change what these tests assert. The
    same hazard already broke a digest-parity test one file over, on the ClinVar cache. Emptying the
    environment variable does **not** work: `explicit or os.getenv(...)` reads `""` as unset and
    falls through to the default directory.
    """
    return tmp_path / "no-pubmind-snapshot-here"


def _variant(clin_sig: str, genotype: str, **kw) -> VariantRow:
    return VariantRow(
        chrom=_CHROM, start=_START, ref=_REF, alts="A,G", genotype=genotype,
        state="risk", conclusion="c", clin_sig=clin_sig, **kw
    )


def _resolution(variant: VariantRow) -> list[ResolutionRow]:
    return [
        ResolutionRow(
            variant_key=variant.variant_key, rsid="rs334", chrom=_CHROM, start=_START,
            ref=_REF, alts="A,G", source="clinvar", status="resolved",
        )
    ]


def _call_for(record, authority: str):
    return next(c for c in record.calls if c.authority == authority)


# ── the subsumption: three-way instead of, never beside, two-way ─────────────────────────────────


def test_with_no_pubmind_snapshot_the_record_names_exactly_the_two_way_findings(
    clinvar: Path,
) -> None:
    """The degenerate case is precisely today's ClinVar-only finding, and that is the contract.

    A check that ran beside the two-way one would make an author meet the same disagreement twice, so
    the contested SET must equal the conflict set exactly — computed from the same run rather than
    from two lists somebody wrote down, because the claim is that the two agree.
    """
    opposed = _variant("benign", "A/T")
    agreeing = _variant("pathogenic", "A/T", rsid="rs334")
    rows = [*_resolution(opposed), *_resolution(agreeing)]

    conflicts = verify_clin_sig([opposed, agreeing], rows, reference=clinvar)
    record = clin_sig_concordance([opposed, agreeing], rows, reference=clinvar)
    assert record is not None

    assert {(p.variant_key, p.genotype) for p in record.parents} == {
        (c.variant_key, c.genotype) for c in conflicts
    }
    # And exactly once each: the subsumption is worthless if the record duplicates a subject.
    assert len(record.parents) == len({(p.variant_key, p.genotype) for p in record.parents})


def test_a_pubmind_snapshot_with_no_record_here_contests_nothing_new(
    clinvar: Path, tmp_path: Path
) -> None:
    """Absence is not disagreement. A variant missing from PubMind means no paper in the corpus was
    kept by its triage stage — not that the literature is silent, and certainly not that the variant
    is benign. So a snapshot that has nothing to say about this locus must leave the contested set
    exactly as the ClinVar-only run left it, while still being distinguishable from never having been
    asked."""
    elsewhere = _pubmind(tmp_path / "pm", [("7", 117559590, "G", "A", "PV1", "Pathogenic", "0.9", "2")])
    variant = _variant("benign", "A/T")
    rows = _resolution(variant)

    without = clin_sig_concordance([variant], rows, reference=clinvar)
    with_it = clin_sig_concordance([variant], rows, reference=clinvar, pubmind_reference=elsewhere)
    assert without is not None and with_it is not None
    assert {(p.variant_key, p.genotype) for p in without.parents} == {
        (p.variant_key, p.genotype) for p in with_it.parents
    }

    # ...and the two runs say different things about WHY, which is the whole tri-state.
    assert _call_for(without, PUBMIND_AUTHORITY).status == "unchecked"
    assert _call_for(with_it, PUBMIND_AUTHORITY).status == "no_record"
    assert [p.authority_concordance for p in without.parents] == ["unchecked"]
    assert [p.authority_concordance for p in with_it.parents] == ["single"]


def test_unchecked_is_not_none_and_is_never_agreement(clinvar: Path, tmp_path: Path) -> None:
    """The three readings of a leg that produced no call, kept apart on one subject.

    `unchecked` — nobody asked. `no_record` — asked, and the archive has nothing. Agreement — asked,
    and it said the same thing. Collapsing any two of these is how a run with no snapshot comes to
    report a clean bill.
    """
    variant = _variant("benign", "A/T")
    rows = _resolution(variant)
    agreeing = _pubmind(tmp_path / "agree", [(_CHROM, _START, "T", "A", "PV1", "Pathogenic", "0.9", "2")])

    unasked = clin_sig_concordance([variant], rows, reference=clinvar)
    absent = clin_sig_concordance(
        [variant], rows, reference=clinvar,
        pubmind_reference=_pubmind(tmp_path / "absent", [("7", 117559590, "G", "A", "PV1", "Benign", "0.1", "1")]),
    )
    spoke = clin_sig_concordance([variant], rows, reference=clinvar, pubmind_reference=agreeing)
    assert unasked is not None and absent is not None and spoke is not None

    assert [p.authority_concordance for p in unasked.parents] == ["unchecked"]
    assert [p.authority_concordance for p in absent.parents] == ["single"]
    assert [p.authority_concordance for p in spoke.parents] == ["concordant"]
    # The authorities agree with each other and the module disagrees with both — a position the
    # two-way check could not state at all.
    assert [p.authored_position for p in spoke.parents] == ["matches_none"]


def test_the_two_authorities_can_disagree_with_each_other(clinvar: Path, tmp_path: Path) -> None:
    """`discordant` is the finding nothing before this release could report.

    It is **not a defect in the module**: PubMind reading the literature one way and ClinVar's
    submitters another is a fact about the field. The module here agrees with one of them, which is
    `matches_some` — and nothing resolves the split, at two authorities or at five.
    """
    against = _pubmind(tmp_path / "against", [(_CHROM, _START, "T", "A", "PV1", "Benign", "0.1", "1")])
    variant = _variant("pathogenic", "A/T")
    record = clin_sig_concordance(
        [variant], _resolution(variant), reference=clinvar, pubmind_reference=against
    )
    assert record is not None
    assert [p.authority_concordance for p in record.parents] == ["discordant"]
    assert [p.authored_position for p in record.parents] == ["matches_some"]
    assert [p.opposed for p in record.parents] == [True]
    # Nothing on the record picks a winner, and no column says which authority was preferred.
    assert not [
        name for name in type(record.parents[0]).model_fields
        if name in {"majority", "consensus", "resolved_clin_sig", "winner"}
    ]


def test_each_authoritys_confidence_stays_in_its_own_units(clinvar: Path, tmp_path: Path) -> None:
    """A gold-star count and an evidence-depth count are different instruments, so neither is
    converted and each travels with the name of the scale it is on."""
    pubmind = _pubmind(tmp_path / "pm", [(_CHROM, _START, "T", "A", "PV1", "Benign", "0.1", "3")])
    variant = _variant("pathogenic", "A/T")
    record = clin_sig_concordance(
        [variant], _resolution(variant), reference=clinvar, pubmind_reference=pubmind
    )
    assert record is not None
    assert _call_for(record, CLINVAR_AUTHORITY).confidence_unit == "review_stars"
    assert _call_for(record, PUBMIND_AUTHORITY).confidence_unit == PUBMIND_CONFIDENCE_UNIT
    assert _call_for(record, PUBMIND_AUTHORITY).confidence == "3"
    assert _call_for(record, PUBMIND_AUTHORITY).dataset == pubmind_dataset_label(pubmind)
    assert _call_for(record, CLINVAR_AUTHORITY).dataset == clinvar_dataset_label(clinvar)


def test_the_detail_rows_come_out_in_the_declared_authority_order(
    clinvar: Path, tmp_path: Path
) -> None:
    """Row order is parquet-visible, so it cannot depend on which snapshot answered first."""
    pubmind = _pubmind(tmp_path / "pm", [(_CHROM, _START, "T", "A", "PV1", "Benign", "0.1", "1")])
    variant = _variant("pathogenic", "A/T")
    record = clin_sig_concordance(
        [variant], _resolution(variant), reference=clinvar, pubmind_reference=pubmind
    )
    assert record is not None
    assert tuple(c.authority for c in record.calls) == AUTHORITY_ORDER
    assert tuple(leg.authority for leg in record.legs) == AUTHORITY_ORDER


# ── the multiplicity, kept and counted rather than collapsed ─────────────────────────────────────


def test_several_pvids_that_straddle_the_camps_fold_to_conflicting_not_to_the_severest(
    clinvar: Path, tmp_path: Path
) -> None:
    """The camp guard runs before the severity fold, and that ordering is the safety property.

    PubMind consolidates on the *text* it extracted, so one allele legitimately carries several PVIDs
    whose verdicts disagree — 35,742 disagreeing keys in the measured file. Folding those by severity
    would answer `pathogenic`, because severity ranks it above `benign`: a winner picked by an
    ordering nobody defined, over records nobody compared. `conflicting` is the vocabulary's own word
    for the situation and sits in the camp that opposes nothing.
    """
    contested = _pubmind(tmp_path / "pm", [
        (_CHROM, _START, "T", "A", "PV1", "Pathogenic", "0.9", "2"),
        (_CHROM, _START, "T", "A", "PV2", "Benign", "0.1", "1"),
    ])
    # Authored `benign`, so the subject is contested by ClinVar either way and the record exists
    # under the mutation too — otherwise removing the guard would fail this test by emptying the
    # record, and the assertion that matters would never be reached.
    variant = _variant("benign", "A/T")
    record = clin_sig_concordance(
        [variant], _resolution(variant), reference=clinvar, pubmind_reference=contested
    )
    assert record is not None
    call = _call_for(record, PUBMIND_AUTHORITY)
    assert call.clin_sig == "conflicting"
    assert call.clin_sig != "pathogenic"  # what the severity fold alone would have answered
    # Both wordings survive, so the fold stays auditable rather than hiding what it folded.
    assert set((call.clin_sig_raw or "").split("|")) == {"Pathogenic", "Benign"}
    # And a magnitude standing for two records is withheld: PubMind's count is per record, so
    # neither number nor any function of the two is this subject's evidence depth.
    assert call.confidence is None
    assert record.multi_record_subjects == 1
    assert record.internally_contested == 1


def test_within_one_camp_the_fold_is_the_shared_normalizers_own_severity_rule() -> None:
    """Two records saying `Benign` and `Likely benign` fold exactly as the single composite token
    `Benign/Likely benign` does — one rule applied twice, not a second rule invented here."""
    folded, raw, contested = fold_authority_records([
        {"clin_sig": "benign", "clin_sig_raw": "Benign"},
        {"clin_sig": "likely_benign", "clin_sig_raw": "Likely benign"},
    ])
    assert (folded, contested) == ("likely_benign", False)
    assert raw == "Benign|Likely benign"


def test_the_straddling_fold_is_symmetric_in_the_order_the_records_arrive() -> None:
    """Reversing the input cannot change the answer — a fold that depended on arrival order would be
    the unsorted `mode()` this item rejected, wearing a different name."""
    # Same camp, so the camp guard is not what is being exercised: the answer has to come from the
    # severity order, and a fold reading `records[0]` would give two different answers here.
    within = [
        {"clin_sig": "benign", "clin_sig_raw": "Benign"},
        {"clin_sig": "likely_benign", "clin_sig_raw": "Likely benign"},
    ]
    assert fold_authority_records(within) == fold_authority_records(list(reversed(within)))
    across = [
        {"clin_sig": "benign", "clin_sig_raw": "Benign"},
        {"clin_sig": "pathogenic", "clin_sig_raw": "Pathogenic"},
    ]
    assert fold_authority_records(across) == fold_authority_records(list(reversed(across)))


def test_a_subject_no_authority_classified_carries_no_classification() -> None:
    """An unknown is withheld, never written down as a negative."""
    assert fold_authority_records([]) == (None, None, False)
    assert fold_authority_records([{"clin_sig": None, "clin_sig_raw": "n/a"}]) == (None, None, False)


# ── the tautology, per leg ───────────────────────────────────────────────────────────────────────


def _drafted_panel(spec: Path, snapshot: Path) -> Path:
    """A real HBB panel drafted from the slice, with the genotype placeholders filled."""
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    result = draft_gene_panel(spec, ["HBB"], snapshot=snapshot, min_review_stars=2)
    assert result.added_for("variants.csv") > 0, result.warnings
    _fill_genotypes(spec, snapshot)
    return spec


def _fill_genotypes(spec: Path, snapshot: Path) -> None:
    """Do what an author does after a draft: decide the zygosity each finding is about.

    Keyed on `(rsid, clin_sig)` rather than on the rsID alone, for the reason the whole check exists:
    `rs334` names a pathogenic `T>A` **and** a likely-benign `T>G` at one locus, so keying on the
    rsID would hand a row its sibling allele's genotype and quietly change which variant it is about.
    """
    alleles = {
        (record["rsid"], record["clin_sig"]): (record["ref"], record["alt"])
        for record in select_by_gene(snapshot, ["HBB"], min_review_stars=0)
        if record["rsid"]
    }
    path = spec / "variants.csv"
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))
    for row in rows:
        # Alphabetically sorted, which is what an unphased genotype must be — the loader refuses the
        # other order, so build it the way the format spells it.
        row["genotype"] = "/".join(sorted(alleles[(row["rsid"], row["clin_sig"])]))
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8")


def _resolution_for(variants: list[VariantRow], snapshot: Path) -> list[ResolutionRow]:
    """Resolution rows for a drafted panel, built from the snapshot the panel was drafted out of.

    The drafter writes an rsID and no coordinate — that is its contract — so the comparison plan has
    nothing to ask about until something resolves them. Taking the loci from the same snapshot is what
    `enrich()`'s ClinVar link does, so the rows here are the ones a real run would have.
    """
    loci: dict[str, tuple[str, int, str, set[str]]] = {}
    for record in select_by_gene(snapshot, ["HBB"], min_review_stars=0):
        rsid = record["rsid"]
        if not rsid:
            continue
        chrom, start, ref, alt = record["chrom"], int(record["start"]), record["ref"], record["alt"]
        entry = loci.setdefault(rsid, (chrom, start, ref, set()))
        entry[3].add(alt)
    rows = []
    for variant in variants:
        found = loci.get(variant.rsid or "")
        if found is None:
            continue
        chrom, start, ref, alts = found
        rows.append(
            ResolutionRow(
                variant_key=variant.variant_key, rsid=variant.rsid, chrom=chrom, start=start,
                ref=ref, alts=",".join(sorted(alts)), source="clinvar", status="resolved",
            )
        )
    return rows


def _read_variants(spec: Path) -> list[VariantRow]:
    rows, errors, _ = load_csv_rows(spec / "variants.csv", VariantRow, "variants.csv")
    assert not errors, errors
    return rows


def test_a_module_drafted_from_clinvar_still_gets_a_record_out_of_the_other_authority(
    clinvar: Path, tmp_path: Path
) -> None:
    """The tautology is decided **per leg**, and this is the case a module-level skip gets wrong.

    Where the `clin_sig` column was copied out of the ClinVar snapshot it would be compared against,
    the ClinVar leg is a comparison of a value against itself and is guaranteed to find nothing.
    PubMind copied nothing, so its leg is a real comparison — skipping the whole check to suppress
    the hollow half would throw away the genuine one. The ClinVar leg contributes **no call at all**:
    a recorded call there would agree with the module by construction, and the record would publish
    that agreement as though somebody had checked it.
    """
    spec = _drafted_panel(tmp_path / "panel", clinvar)
    variants = _read_variants(spec)
    resolution = _resolution_for(variants, clinvar)
    assert resolution, "the drafted rows must resolve, or nothing is compared and this proves nothing"
    disagreeing = _pubmind(tmp_path / "pm", [
        (row.chrom, row.start, row.ref, alt, f"PV{i}{j}", "Benign", "0.1", "1")
        for i, row in enumerate(resolution)
        for j, alt in enumerate((row.alts or "").split(","))
        if alt
    ])
    sources = read_sources_file(spec)

    record = clin_sig_concordance(
        variants, resolution, reference=clinvar, pubmind_reference=disagreeing,
        sources=sources, spec_dir=spec,
    )
    assert record is not None
    assert record.consulted == (PUBMIND_AUTHORITY,)
    states = {leg.authority: leg.state for leg in record.legs}
    assert states == {CLINVAR_AUTHORITY: "tautological", PUBMIND_AUTHORITY: "consulted"}
    assert {c.authority for c in record.calls} == {PUBMIND_AUTHORITY}
    assert record.parents, "the authority that copied nothing found a real disagreement"


def test_where_every_leg_is_hollow_or_unasked_no_record_is_written(
    clinvar: Path, tmp_path: Path
) -> None:
    """The defect this release has now caught five times, in the place it is likeliest to reappear.

    ClinVar tautological and no PubMind snapshot leaves nobody who could have disagreed. Two empty
    tables there are the claim *nothing here is contested*, published on no evidence at all — the
    same shape as the `findings: 0` that started RM130. `None` instead, which writes nothing and
    leaves any earlier record where it is.
    """
    spec = _drafted_panel(tmp_path / "panel", clinvar)
    variants = _read_variants(spec)
    resolution = _resolution_for(variants, clinvar)
    assert resolution, "the drafted rows must resolve, or the skip is untested"
    assert clin_sig_concordance(
        variants, resolution, reference=clinvar,
        sources=read_sources_file(spec), spec_dir=spec,
    ) is None
    # A run that could not put the question reports no zero either.
    assert concordance_sentences(None) == []
    assert concordance_notes(None) == []


def test_the_pubmind_leg_reads_its_skip_from_the_projection_registry_rather_than_a_literal(
    clinvar: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard is **derived** from `DRAFT_PROJECTIONS`, so the drafter § C adds needs no edit here.

    `pubmind` is not a drafting provider yet, so today the leg can never be tautological — which is
    exactly the state in which a restated guard rots unnoticed. Registering a projection and stamping
    the licence row the way a drafter would proves the derivation instead of the literal: the leg
    goes hollow with nothing in `clinical.py` naming PubMind's table or its checked column.
    """
    variant = _variant("pathogenic", "A/T")
    pubmind = _pubmind(tmp_path / "pm", [(_CHROM, _START, "T", "A", "PV1", "Benign", "0.1", "1")])
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    _write_variants(spec, [variant])

    monkeypatch.setitem(
        DRAFT_PROJECTIONS,
        PUBMIND_AUTHORITY,
        DraftProjection(
            table="variants.csv",
            identity=("rsid", "chrom", "start", "ref", "alts"),
            checked=("clin_sig",),
        ),
    )
    merge_sources_file(
        [
            SourceRow(
                source=PUBMIND_AUTHORITY, layer="annotation", declared_use="non_commercial",
                dataset=pubmind_dataset_label(pubmind),
                draft_digest=draft_digest(spec, PUBMIND_AUTHORITY),
            )
        ],
        spec,
        error=EnrichmentError,
    )
    sources = read_sources_file(spec)

    record = clin_sig_concordance(
        [variant], _resolution(variant), reference=clinvar, pubmind_reference=pubmind,
        sources=sources, spec_dir=spec,
    )
    assert record is not None
    states = {leg.authority: leg.state for leg in record.legs}
    assert states[PUBMIND_AUTHORITY] == "tautological"
    assert states[CLINVAR_AUTHORITY] == "consulted"
    # The note names the column the projection declares, so it stays right when the projection moves.
    note = next(n for n in concordance_notes(record) if n.startswith(PUBMIND_AUTHORITY))
    assert "clin_sig" in note

    # Move one checked cell and the leg runs again in full — the digest half of the conjunction.
    _write_variants(spec, [_variant("benign", "A/T")])
    moved = clin_sig_concordance(
        [_variant("benign", "A/T")], _resolution(variant), reference=clinvar,
        pubmind_reference=pubmind, sources=read_sources_file(spec), spec_dir=spec,
    )
    assert moved is not None
    assert {leg.authority: leg.state for leg in moved.legs}[PUBMIND_AUTHORITY] == "consulted"


def _write_variants(spec: Path, variants: list[VariantRow]) -> None:
    """Write a `variants.csv` from the model's own **authored** surface.

    `authored_field_names` rather than `model_fields`, which is the rule this repo already paid for:
    `model_fields` includes the compiler-managed columns, and writing those back out produces a file
    the loader refuses. Skipping by the marker rather than by name means a column added later is
    handled without this helper learning about it.
    """
    fieldnames = list(authored_field_names(VariantRow))
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for variant in variants:
        dumped = variant.model_dump()
        writer.writerow({k: ("" if v is None else v) for k, v in dumped.items() if k in fieldnames})
    (spec / "variants.csv").write_text(buffer.getvalue(), encoding="utf-8")


# ── arity, with a real second authority rather than five synthetic ones ──────────────────────────


def _shapes(name: str) -> list[AuthorityCall]:
    """The five shapes one authority can take: two opinionated calls, an undecided one, an
    established absence, and never-asked."""
    return [
        AuthorityCall(authority=name, status="recorded", clin_sig="pathogenic"),
        AuthorityCall(authority=name, status="recorded", clin_sig="benign"),
        AuthorityCall(authority=name, status="recorded", clin_sig="uncertain_significance"),
        AuthorityCall(authority=name, status="no_record"),
        AuthorityCall(authority=name, status="unchecked"),
    ]


def _reachable_beyond(base: list[AuthorityCall], extra: int) -> tuple[set[str], set[str]]:
    """Every verdict pair reachable from a real record's calls plus `extra` synthetic authorities."""
    concordance: set[str] = set()
    position: set[str] = set()

    def walk(index: int, calls: list[AuthorityCall]) -> None:
        if index == extra:
            for authored in ("pathogenic", "benign", "uncertain_significance", None):
                verdict = classify_concordance(authored, calls)
                concordance.add(verdict.authority_concordance)
                position.add(verdict.authored_position)
            return
        for shape in _shapes(f"extra{index}"):
            walk(index + 1, [*calls, shape])

    walk(0, list(base))
    return concordance, position


def test_the_real_pair_of_authorities_grows_to_five_without_a_new_member(
    clinvar: Path, tmp_path: Path
) -> None:
    """The arity property, seeded from the **producer** rather than from five synthetic names.

    RM130 proved the classifier holds at three authorities and at five; what a coverage test at two
    cannot see is whether the thing that actually builds the calls stays inside that property once a
    second real authority arrives. So this takes the calls a real ClinVar+PubMind run produced,
    appends one and then three more authorities in every shape they can take, and asserts the member
    sets are **equal** — not contained, because containment is a floor a sixth member would satisfy.
    """
    pubmind = _pubmind(tmp_path / "pm", [(_CHROM, _START, "T", "A", "PV1", "Benign", "0.1", "1")])
    variant = _variant("pathogenic", "A/T")
    record = clin_sig_concordance(
        [variant], _resolution(variant), reference=clinvar, pubmind_reference=pubmind
    )
    assert record is not None
    real = [
        AuthorityCall(
            authority=call.authority, status=call.status, clin_sig=call.clin_sig,
            clin_sig_raw=call.clin_sig_raw, confidence=call.confidence,
            confidence_unit=call.confidence_unit, dataset=call.dataset,
        )
        for call in record.calls
    ]
    assert len(real) == 2, "the fixture must really produce two authorities, or this proves nothing"

    at_three = _reachable_beyond(real, 1)
    at_five = _reachable_beyond(real, 3)
    assert at_three == at_five
    assert at_five[0] <= VALID_AUTHORITY_CONCORDANCE
    assert at_five[1] <= VALID_AUTHORED_POSITION


# ── the registries, walked ───────────────────────────────────────────────────────────────────────


def test_every_leg_state_is_reachable_from_a_real_run(clinvar: Path, tmp_path: Path) -> None:
    """An equality over the walked set, never a floor: a state nothing can produce is a state whose
    branch nothing exercises, and a fourth added later has to earn its way in here."""
    variant = _variant("pathogenic", "A/T")
    rows = _resolution(variant)
    pubmind = _pubmind(tmp_path / "pm", [(_CHROM, _START, "T", "A", "PV1", "Benign", "0.1", "1")])
    spec = _drafted_panel(tmp_path / "panel", clinvar)
    drafted = _read_variants(spec)
    drafted_rows = _resolution_for(drafted, clinvar)

    observed: set[str] = set()
    for record in (
        clin_sig_concordance([variant], rows, reference=clinvar),                       # unchecked
        clin_sig_concordance([variant], rows, reference=clinvar, pubmind_reference=pubmind),
        clin_sig_concordance(                                                           # tautological
            drafted, drafted_rows, reference=clinvar, pubmind_reference=pubmind,
            sources=read_sources_file(spec), spec_dir=spec,
        ),
    ):
        assert record is not None
        observed.update(leg.state for leg in record.legs)
    assert observed == AUTHORITY_LEG_STATES


# ── severity: warnings in both modes, escalation in neither ──────────────────────────────────────


def test_a_contested_module_never_refuses_a_strict_run(clinvar: Path, tmp_path: Path) -> None:
    """`@clinsig-never-escalates`, with more force at two authorities than at one.

    A disagreement with a literature miner's aggregate is a statement about that extraction's limits
    at least as often as about the module — the corpus join measured 62 % agreement — so `discordant`
    is a fact about the field, not a defect to gate on. Both modes warn; neither refuses.
    """
    pubmind = _pubmind(tmp_path / "pm", [(_CHROM, _START, "T", "A", "PV1", "Benign", "0.1", "1")])
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    _write_variants(spec, [_variant("benign", "A/T", rsid="rs334")])

    for mode in ("best_effort", "strict"):
        result = enrich(
            spec, mode=mode, offline=True, clinvar_cache=clinvar, pubmind_cache=pubmind,
            use_gnomad=False, verify_rsids=False, verify_datasets=False, mint_vrs=False,
        )
        assert result.clin_sig_record is not None, mode
        assert result.clin_sig_record.parents, mode
        assert (spec / CONCORDANCE_CSV).is_file(), mode
        assert (spec / AUTHORITY_CALLS_CSV).is_file(), mode


def test_the_two_way_skip_and_the_leg_note_do_not_both_print_the_same_sentence(
    clinvar: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """One sentence, once. `clin_sig_not_checked` and the ClinVar leg's `reason` are the same prose —
    both come out of `tautology_reason` — so a drafted module would otherwise read the tautology
    twice in one run. Matched on the sentence rather than on a skip key, so a reword stays deduped.
    """
    spec = _drafted_panel(tmp_path / "panel", clinvar)
    pubmind = _pubmind(tmp_path / "pm", [(_CHROM, _START, "T", "A", "PV1", "Benign", "0.1", "1")])
    with caplog.at_level("INFO", logger="just_dna_enricher.enrich"):
        result = enrich(
            spec, offline=True, clinvar_cache=clinvar, pubmind_cache=pubmind, use_gnomad=False,
            verify_rsids=False, verify_datasets=False, mint_vrs=False,
        )
    sentence = result.clin_sig_not_checked
    assert sentence and "drafted from" in sentence
    printed = [record.getMessage() for record in caplog.records if sentence in record.getMessage()]
    assert len(printed) == 1, printed


def test_the_reported_sentences_carry_their_denominator_and_the_authorities_that_answered(
    clinvar: Path, tmp_path: Path
) -> None:
    """A count with no denominator is unreadable, and nine contested subjects mean something
    different when one archive spoke and when two did. Both phrases are pinned, because a warning's
    text is an API."""
    pubmind = _pubmind(tmp_path / "pm", [(_CHROM, _START, "T", "A", "PV1", "Benign", "0.1", "1")])
    variant = _variant("pathogenic", "A/T")
    record = clin_sig_concordance(
        [variant], _resolution(variant), reference=clinvar, pubmind_reference=pubmind
    )
    assert record is not None
    sentences = concordance_sentences(record)
    assert any(
        f"{record.contested} of {record.subjects} subject(s) put to the authorities are contested"
        in line
        for line in sentences
    )
    assert any("Authorities consulted: clinvar, pubmind" in line for line in sentences)
    assert any(
        f"{record.contested} contested subject(s) are a disagreement between the authorities "
        f"themselves" in line
        for line in sentences
    )
    assert any(CONCORDANCE_CSV in line for line in sentences)
    assert any(AUTHORITY_CALLS_CSV in line for line in sentences)


def test_a_run_that_found_nothing_contested_reports_no_zero(clinvar: Path, tmp_path: Path) -> None:
    """A check that found nothing does not announce it as though it were evidence; the denominator
    stays on the record for a caller that wants it."""
    agreeing = _pubmind(tmp_path / "pm", [(_CHROM, _START, "T", "A", "PV1", "Pathogenic", "0.9", "2")])
    variant = _variant("pathogenic", "A/T")
    record = clin_sig_concordance(
        [variant], _resolution(variant), reference=clinvar, pubmind_reference=agreeing
    )
    assert record is not None
    assert record.parents == []
    assert concordance_sentences(record) == []
    assert record.subjects == 1


def test_an_unasked_authority_is_named_rather_than_left_silent(clinvar: Path) -> None:
    """A leg that silently did not run reads as a leg that found nothing, which is the failure the
    whole tri-state exists to prevent."""
    variant = _variant("pathogenic", "A/T")
    record = clin_sig_concordance([variant], _resolution(variant), reference=clinvar)
    assert record is not None
    notes = concordance_notes(record)
    assert any(line.startswith(f"{PUBMIND_AUTHORITY} was not consulted") for line in notes)
    assert any("never agreement" in line for line in notes)


def test_a_record_survives_a_run_that_could_not_replace_it(clinvar: Path, tmp_path: Path) -> None:
    """A run with no authority to ask writes nothing rather than emptying the record, so the last
    real answer stays readable instead of being overwritten by a comparison nobody made."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    _write_variants(spec, [_variant("benign", "A/T", rsid="rs334")])

    enrich(spec, offline=True, clinvar_cache=clinvar, pubmind_cache=_no_pubmind(tmp_path),
           use_gnomad=False, verify_rsids=False, verify_datasets=False, mint_vrs=False)
    written = (spec / CONCORDANCE_CSV).read_text(encoding="utf-8")
    assert len(written.splitlines()) > 1, "the first run really did record a contested subject"

    # Now take the snapshot away: nobody can be asked, so nothing may be rewritten.
    empty = tmp_path / "empty"
    empty.mkdir()
    result = enrich(spec, offline=True, clinvar_cache=empty, pubmind_cache=_no_pubmind(tmp_path),
                    use_gnomad=False, verify_rsids=False, verify_datasets=False, mint_vrs=False)
    assert result.clin_sig_record is None
    assert (spec / CONCORDANCE_CSV).read_text(encoding="utf-8") == written


def test_a_refused_strict_run_leaves_no_record_behind(clinvar: Path, tmp_path: Path) -> None:
    """The transaction's written promise, asserted on the bytes: everything before the gate is
    staging, so a run that refuses must not have written the record."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    _write_variants(spec, [
        _variant("benign", "A/T", rsid="rs334"),
        # A well-formed rsID with no coordinate anywhere, so `strict` refuses on `unresolved`.
        VariantRow(rsid="rs999999999", genotype="A/G", state="risk",
                   conclusion="c", clin_sig="benign"),
    ])
    with pytest.raises(Exception):
        enrich(spec, mode="strict", offline=True, clinvar_cache=clinvar,
               pubmind_cache=_no_pubmind(tmp_path), use_gnomad=False,
               verify_rsids=False, verify_datasets=False, mint_vrs=False)
    assert not (spec / CONCORDANCE_CSV).exists()
    assert not (spec / AUTHORITY_CALLS_CSV).exists()


def test_the_snapshot_reader_is_never_a_resolver_link() -> None:
    """PubMind annotates loci something else resolved: its coordinates are back-mappings of extracted
    text, so nothing it produces may enter `resolution.csv` (`@source-vs-authority`). Asserted on the
    module's surface rather than on a comment, because the tempting repair is to add the function."""
    assert not [name for name in dir(pubmind_reader) if "lookup_loci" in name]
    assert not [name for name in dir(pubmind_reader) if name.endswith("_rsid_candidates")]
