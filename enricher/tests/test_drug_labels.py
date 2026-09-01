"""The regulator drug-label cross-check (RM166), run against three shipped corpus modules.

Each of the three is here for a different half of the design, and each was chosen by reading the
corpus rather than by inventing a case:

* `cyp2c19_star_alleles` — the disagreement. Five agencies label clopidogrel against CYP2C19 and one
  of them states a different level from the other four, at **both** join tiers: three of the five name
  the star alleles and two name only the gene.
* `pgx_slco1b1_simvastatin` — the blank. Two of the three labels reaching SLCO1B1 + simvastatin state
  no `Testing Level` at all, which is the third-of-the-file case the whole tri-state exists for.
* `cyp2c9_warfarin_grch37` — the miss. It states a CYP4F2 + warfarin claim no agency labels, which is
  withheld rather than reported as an absence of pharmacogenomics.

**Every expected value is computed from the fixture at runtime**, including which agency disagrees:
ClinPGx re-curates labels, and `'EMA'` typed into an assertion would convert that into a permanently
red test. The reference modules are copied into `tmp_path` first — they are closed with a
`verification.json` binding, and this check writes an attestation.
"""

import csv
import json
import os
import shutil
import zipfile
from pathlib import Path

import pytest
from just_dna_enricher.drug_labels import (
    _CONCORDANCE_SENTENCES,
    _FINDING_SENTENCES,
    _POSITION_SENTENCES,
    CELL_SEPARATOR,
    CHECK_NAME,
    LABEL_TIERS,
    NO_CLINICAL_PGX,
    SOURCE_NAME,
    VALID_AUTHORED_ACTION,
    VALID_AUTHORED_POSITION,
    VALID_LABEL_CONCORDANCE,
    VALID_TESTING_LEVELS,
    DrugLabelError,
    DrugLabelIndex,
    LabelCall,
    LabelRow,
    LabelSubject,
    _authored_action,
    check_drug_labels,
    classify_labels,
    load_drug_labels,
    verification_record,
)
from just_dna_enricher.drug_labels_build import (
    LABELS_MEMBER,
    build_drug_label_snapshot,
    download_drug_labels_zip,
)
from just_dna_enricher.licensing import LicenseRefusal
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.vocab import VALID_VERIFICATION_CHECKS, VALID_VERIFICATION_SKIPS

_ROOT = Path(__file__).resolve().parents[2]
_SLICE = _ROOT / "assets" / "clinpgx_drug_labels_slice"
_EXAMPLES = _ROOT / "reference_examples"

#: The three corpus modules and the (gene, drug) pair each one is about. Read off the shipped specs
#: rather than invented, which is what makes "one disagrees, one is blank, one is unlabelled" a
#: measurement instead of a claim.
_CORPUS = {
    "cyp2c19_star_alleles": ("CYP2C19", "clopidogrel"),
    "pgx_slco1b1_simvastatin": ("SLCO1B1", "simvastatin"),
    "cyp2c9_warfarin_grch37": ("VKORC1", "warfarin"),
}


def _fixture_rows() -> list[dict[str, str]]:
    with open(_SLICE / LABELS_MEMBER, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _labels_for(gene: str, drug: str, *, allele: str | None = None) -> list[dict[str, str]]:
    """The fixture rows reaching one pair, read independently of the index under test."""
    out = []
    for row in _fixture_rows():
        genes = {token.strip() for token in row["Genes"].split(CELL_SEPARATOR)}
        chemicals = {token.strip().casefold() for token in row["Chemicals"].split(CELL_SEPARATOR)}
        variants = {token.strip() for token in row["Variants/Haplotypes"].split(CELL_SEPARATOR)}
        if gene not in genes or drug.casefold() not in chemicals:
            continue
        if allele is not None and allele not in variants:
            continue
        out.append(row)
    return out


@pytest.fixture(scope="module")
def index(tmp_path_factory: pytest.TempPathFactory) -> DrugLabelIndex:
    tmp = tmp_path_factory.mktemp("drug-labels")
    archive = tmp / "drugLabels.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(_SLICE.iterdir()):
            handle.write(path, path.name)
    result = build_drug_label_snapshot(
        archive, tmp / "snap", source_url="file://clinpgx_drug_labels_slice"
    )
    return load_drug_labels(result.out_dir)


def _module(tmp_path: Path, name: str) -> Path:
    dest = tmp_path / name
    shutil.copytree(_EXAMPLES / name, dest)
    return dest


# ── The vocabularies, walked rather than restated ───────────────────────────────────────────────


def test_the_testing_levels_this_release_knows_are_the_ones_the_file_states(
    index: DrugLabelIndex,
) -> None:
    """An equality, not a floor. A sixth level upstream has to be a visible edit here."""
    assert index.testing_levels() == VALID_TESTING_LEVELS
    assert NO_CLINICAL_PGX in VALID_TESTING_LEVELS


def test_every_verdict_arm_owes_a_distinct_sentence() -> None:
    """`@answered-is-not-absent`: a verdict function with N arms owes a reason function with N arms."""
    assert set(_CONCORDANCE_SENTENCES) == VALID_LABEL_CONCORDANCE
    assert set(_POSITION_SENTENCES) == VALID_AUTHORED_POSITION
    for sentences in (_CONCORDANCE_SENTENCES, _POSITION_SENTENCES, _FINDING_SENTENCES):
        assert len(set(sentences.values())) == len(sentences)


def test_the_attestation_member_is_the_published_one() -> None:
    assert CHECK_NAME in VALID_VERIFICATION_CHECKS
    #: Named for the labels, never for an agency — the file carries five of them.
    assert not any(
        agency.casefold() in CHECK_NAME.casefold()
        for agency in {row["Source"] for row in _fixture_rows()}
    )


# ── The separator, and the join key ─────────────────────────────────────────────────────────────


def test_a_comma_inside_a_variant_token_is_data_and_not_a_separator(index: DrugLabelIndex) -> None:
    """`vocab.MULTI_SEP` splits on `,;|` and would cut one DPYD haplotype into two false names."""
    commas = [row for row in _fixture_rows() if "," in row["Variants/Haplotypes"]]
    assert commas, "the slice must keep a row whose variant cell holds a comma"
    for raw in commas:
        stored = next(row for row in index.labels if row.label_id == raw["PharmGKB ID"])
        assert stored.variants == tuple(
            token.strip() for token in raw["Variants/Haplotypes"].split(CELL_SEPARATOR)
        )
        assert any("," in token for token in stored.variants)


def test_the_star_tokens_are_gene_qualified_and_not_the_authored_key_verbatim(
    index: DrugLabelIndex, tmp_path: Path
) -> None:
    """The item's entry says the star tokens are `haplotypes.csv`'s key verbatim. They are not.

    The file writes `CYP2C19*2`; the module writes `*2` in `haplotype_name` with the gene in its own
    column, so the join composes them. This is the measurement behind that composition.
    """
    gene, drug = _CORPUS["cyp2c19_star_alleles"]
    authored = {
        row["haplotype_name"]
        for row in csv.DictReader(
            (_EXAMPLES / "cyp2c19_star_alleles" / "haplotypes.csv").open(encoding="utf-8")
        )
    }
    tokens = {token for row in index.labels for token in row.variants if token.startswith(gene)}
    assert tokens, "the slice must name star alleles for this gene"
    assert not (tokens & authored), "the two spellings must differ, or there is nothing to compose"
    assert {token.removeprefix(gene) for token in tokens} & authored

    spec = _module(tmp_path, "cyp2c19_star_alleles")
    result = check_drug_labels(spec, snapshot=index, declared_use="non_commercial", write=False)
    allele_subjects = {s.allele for s in result.compared if s.allele}
    assert allele_subjects <= authored
    assert allele_subjects, "the composed key must actually match something"
    assert all(subject.drug == drug for subject in result.compared)


# ── The two join tiers ──────────────────────────────────────────────────────────────────────────


def test_a_gene_tier_and_an_allele_tier_finding_are_distinguishable(
    index: DrugLabelIndex, tmp_path: Path
) -> None:
    """The disagreement is reported at both granularities, and each finding says which it is."""
    gene, drug = _CORPUS["cyp2c19_star_alleles"]
    spec = _module(tmp_path, "cyp2c19_star_alleles")
    result = check_drug_labels(spec, snapshot=index, declared_use="non_commercial", write=False)

    assert {finding.tier for finding in result.findings} == set(LABEL_TIERS)
    gene_findings = [f for f in result.findings if f.tier == "gene"]
    allele_findings = [f for f in result.findings if f.tier == "allele"]
    assert [f.subject for f in gene_findings] == [LabelSubject(gene, None, drug)]
    assert all(f.subject.allele for f in allele_findings)
    assert all(f.kind == "regulators_disagree" for f in result.findings)

    # The gene-tier question is answered by every label naming the pair; the allele-tier one only by
    # the labels that enumerate that allele. So the finer tier is answered by strictly fewer.
    gene_calls = len(gene_findings[0].calls)
    assert gene_calls == len(_labels_for(gene, drug))
    assert all(len(f.calls) < gene_calls for f in allele_findings)


def test_the_disagreeing_regulator_is_the_one_the_file_disagrees_with(
    index: DrugLabelIndex, tmp_path: Path
) -> None:
    """Computed from the fixture: whichever agency is the odd one out must be inside the sentence."""
    gene, drug = _CORPUS["cyp2c19_star_alleles"]
    levels: dict[str, set[str]] = {}
    for row in _labels_for(gene, drug):
        levels.setdefault(row["Testing Level"], set()).add(row["Source"])
    assert len(levels) > 1, "the fixture must hold a real disagreement about this pair"
    minority = min(levels.values(), key=len)

    spec = _module(tmp_path, "cyp2c19_star_alleles")
    result = check_drug_labels(spec, snapshot=index, declared_use="non_commercial", write=False)
    sentence = str(next(f for f in result.findings if f.tier == "gene"))
    assert all(agency in sentence for agency in minority)


def test_an_allele_no_label_names_is_answered_at_the_gene_tier_and_counted(
    index: DrugLabelIndex, tmp_path: Path
) -> None:
    """Not withheld and not a finding — a number, because the gene-tier subject answers for it."""
    gene, drug = _CORPUS["cyp2c19_star_alleles"]
    named = {
        token.strip().removeprefix(gene)
        for row in _labels_for(gene, drug)
        for token in row["Variants/Haplotypes"].split(CELL_SEPARATOR)
        if token.strip().startswith(gene)
    }
    # From `diplotypes.csv` rather than `haplotypes.csv`: the subjects are the claims that name a
    # drug, and the definition table carries alleles no diplotype row uses.
    authored = {
        allele
        for row in csv.DictReader(
            (_EXAMPLES / "cyp2c19_star_alleles" / "diplotypes.csv").open(encoding="utf-8")
        )
        if row["drug"].strip() == drug and row["gene"].strip() == gene
        for allele in (row["haplotype_a"], row["haplotype_b"])
        if allele.strip()
    }
    spec = _module(tmp_path, "cyp2c19_star_alleles")
    result = check_drug_labels(spec, snapshot=index, declared_use="non_commercial", write=False)

    compared_alleles = {s.allele for s in result.compared if s.allele}
    unnamed_alleles = {s.allele for s in result.unnamed_alleles}
    assert compared_alleles == named & authored
    assert unnamed_alleles == authored - named
    assert not (compared_alleles & unnamed_alleles)
    assert LabelSubject(gene, None, drug) in result.compared


# ── The blank level ─────────────────────────────────────────────────────────────────────────────


def test_a_blank_testing_level_is_unknown_and_is_neither_a_negative_nor_a_silence(
    index: DrugLabelIndex, tmp_path: Path
) -> None:
    """Reading the blank as `No Clinical PGx` would turn the file's largest silence into a claim."""
    gene, drug = _CORPUS["pgx_slco1b1_simvastatin"]
    blanks = [row for row in _labels_for(gene, drug) if not row["Testing Level"].strip()]
    assert blanks, "the slice must keep a blank-level label for this pair"

    spec = _module(tmp_path, "pgx_slco1b1_simvastatin")
    result = check_drug_labels(spec, snapshot=index, declared_use="non_commercial", write=False)

    subject = LabelSubject(gene, None, drug)
    verdict = result.verdicts[subject]
    # The blanks are not a negative claim, so they cannot put the module in opposition and they
    # cannot be the thing that makes the levels differ.
    assert verdict.position != "opposed"
    assert NO_CLINICAL_PGX not in str(verdict)
    stated = {row["Testing Level"] for row in _labels_for(gene, drug) if row["Testing Level"].strip()}
    assert (verdict.concordance == "discordant") == (len(stated) > 1)

    # Counted, and in the record rather than only in the log.
    assert result.unstated_calls == len(blanks)
    assert str(len(blanks)) in (verification_record(result).detail or "")


def test_one_agency_with_two_labels_keeps_both_and_no_winner_is_picked(
    index: DrugLabelIndex, tmp_path: Path
) -> None:
    """`@multiplicity-is-a-finding`, and it is why the unit is the label rather than the agency.

    Swissmedic covers SLCO1B1 + simvastatin twice — once for the drug and once for the
    fenofibrate/simvastatin combination — at two different levels. Collapsing them to one opinion per
    agency would need a winner this check has no basis to pick.
    """
    gene, drug = _CORPUS["pgx_slco1b1_simvastatin"]
    by_agency: dict[str, list[dict[str, str]]] = {}
    for row in _labels_for(gene, drug):
        by_agency.setdefault(row["Source"], []).append(row)
    doubled = {agency: rows for agency, rows in by_agency.items() if len(rows) > 1}
    assert doubled, "the slice must keep an agency with two labels for one pair"

    spec = _module(tmp_path, "pgx_slco1b1_simvastatin")
    result = check_drug_labels(spec, snapshot=index, declared_use="non_commercial", write=False)
    finding = next(f for f in result.findings if f.subject == LabelSubject(gene, None, drug))
    assert [call.row.label_id for call in finding.calls] == [
        row["PharmGKB ID"] for row in sorted(_labels_for(gene, drug), key=lambda r: r["PharmGKB ID"])
    ]
    for agency, rows in doubled.items():
        assert sum(1 for call in finding.calls if call.row.regulator == agency) == len(rows)
    assert "label(s)" in str(finding) and "regulator(s)" not in str(finding)


def test_an_unstated_level_never_establishes_an_agreement_on_its_own() -> None:
    """Kleene at the level of the classifier: `discordant` survives a silent agency, `concordant` does not."""
    stated = LabelRow("PA1", "A", "Actionable PGx", ("G",), ("d",), ())
    other = LabelRow("PA2", "B", "Informative PGx", ("G",), ("d",), ())
    silent = LabelRow("PA3", "C", None, ("G",), ("d",), ())
    call = lambda row: LabelCall(row=row, matched_on="G")  # noqa: E731

    assert classify_labels("absent", [call(stated), call(other), call(silent)]).concordance == (
        "discordant"
    )
    assert classify_labels("absent", [call(stated), call(silent)]).concordance == "unstated"
    assert classify_labels("absent", [call(stated), call(stated)]).concordance == "concordant"
    assert classify_labels("absent", [call(stated)]).concordance == "single"
    assert classify_labels("absent", []).concordance == "none"
    # A module that recommends where nobody stated a level is unchecked, never opposed.
    assert classify_labels("recommends", [call(silent)]).position == "unchecked"


def test_only_the_negative_level_is_placed_against_an_authored_recommendation() -> None:
    """The three middle levels are stated and unplaced — no invented ladder."""
    def _row(level: str | None) -> LabelCall:
        return LabelCall(
            row=LabelRow("PA1", "A", level, ("G",), ("d",), ()), matched_on="G"
        )

    assert classify_labels("recommends", [_row(NO_CLINICAL_PGX)]).position == "opposed"
    for level in sorted(VALID_TESTING_LEVELS - {NO_CLINICAL_PGX}):
        assert classify_labels("recommends", [_row(level)]).position == "unplaced"
    # The reverse direction withholds: declining to recommend a genotype is not a claim about whether
    # the medicine's label carries pharmacogenomics.
    assert classify_labels("declines", [_row("Testing Required")]).position == "unplaced"
    assert classify_labels("absent", [_row(NO_CLINICAL_PGX)]).position == "absent"

    # Kleene, in the direction that matters: an opposition already witnessed is not un-witnessed by a
    # label that stated no level (`unknown AND false` is `false`). But with nobody stating one at all
    # there is no opposition to witness, and the answer is `unchecked` rather than either verdict.
    assert classify_labels("recommends", [_row(NO_CLINICAL_PGX), _row(None)]).position == "opposed"
    assert classify_labels("recommends", [_row(None), _row(None)]).position == "unchecked"
    # And a second agency stating something else takes the opposition back to unplaced, because
    # "every label that stated a level" is then false.
    assert classify_labels(
        "recommends", [_row(NO_CLINICAL_PGX), _row("Testing Required")]
    ).position == "unplaced"


def test_a_recommendation_against_a_wholly_negative_pair_is_the_one_authored_finding(
    index: DrugLabelIndex, tmp_path: Path
) -> None:
    """Built from the fixture's own all-negative pair, not from an invented one."""
    pairs: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in _fixture_rows():
        for gene in (token.strip() for token in row["Genes"].split(CELL_SEPARATOR)):
            for chemical in (token.strip() for token in row["Chemicals"].split(CELL_SEPARATOR)):
                pairs.setdefault((gene, chemical), []).append(row)
    negative = [
        pair
        for pair, rows in pairs.items()
        if len(rows) >= 2 and {row["Testing Level"] for row in rows} == {NO_CLINICAL_PGX}
    ]
    assert negative, "the slice must keep a pair every agency calls No Clinical PGx"
    gene, drug = min(negative)

    spec = tmp_path / "negative_pair"
    spec.mkdir()
    (spec / "diplotypes.csv").write_text(
        "gene,haplotype_a,haplotype_b,phenotype,conclusion,drug,recommendation_strength\n"
        f"{gene},*1,*2,Intermediate Metabolizer,"
        f"{gene} *1/*2 on {drug}: reduce the dose,{drug},strong\n",
        encoding="utf-8",
    )
    result = check_drug_labels(spec, snapshot=index, declared_use="non_commercial", write=False)
    opposed = [f for f in result.findings if f.kind == "recommendation_without_label_pgx"]
    assert opposed, "an authored recommendation against a wholly negative pair must be reported"
    assert {f.subject.gene for f in opposed} == {gene}
    assert all(NO_CLINICAL_PGX in str(finding) for finding in opposed)


# ── Withholding, severity, and what is not written ──────────────────────────────────────────────


def test_a_pair_no_agency_labels_is_withheld_rather_than_called_clear(
    index: DrugLabelIndex, tmp_path: Path
) -> None:
    spec = _module(tmp_path, "cyp2c9_warfarin_grch37")
    result = check_drug_labels(spec, snapshot=index, declared_use="non_commercial", write=False)

    authored_pairs = {
        (row["gene"], row["drug"])
        for row in csv.DictReader(
            (_EXAMPLES / "cyp2c9_warfarin_grch37" / "pharm_variants.csv").open(encoding="utf-8")
        )
        if row["drug"].strip() and row["gene"].strip()
    }
    unlabelled = {pair for pair in authored_pairs if not _labels_for(*pair)}
    assert unlabelled, "the corpus must state a pair the slice does not label"
    assert {(s.gene, s.drug) for s, _note in result.withheld} == unlabelled
    assert not any((s.gene, s.drug) in unlabelled for s in result.compared)
    # Withheld, and in the record rather than only in the log.
    assert "withheld" in (verification_record(result).detail or "")


def test_strict_reports_exactly_what_best_effort_reports_and_refuses_nothing(
    index: DrugLabelIndex, tmp_path: Path
) -> None:
    """Five expert regulators disagreeing is not a defect in the module (`@clinsig-never-escalates`)."""
    lenient = check_drug_labels(
        _module(tmp_path / "a", "cyp2c19_star_alleles"),
        snapshot=index, declared_use="non_commercial", write=False,
    )
    strict = check_drug_labels(
        _module(tmp_path / "b", "cyp2c19_star_alleles"),
        snapshot=index, mode="strict", declared_use="non_commercial", write=False,
    )
    assert lenient.findings, "the module must actually disagree, or this proves nothing"
    assert [str(f) for f in strict.findings] == [str(f) for f in lenient.findings]
    assert strict.contested == lenient.contested


def test_a_malformed_authored_table_refuses_in_both_modes(
    index: DrugLabelIndex, tmp_path: Path
) -> None:
    """`strict` not escalating a source disagreement says nothing about a file that will not load."""
    for mode in ("best_effort", "strict"):
        spec = tmp_path / mode
        spec.mkdir()
        (spec / "diplotypes.csv").write_text(
            "gene,haplotype_a,haplotype_b,phenotype,conclusion,drug,recommendation_strength\n"
            "CYP2C19,*1,*2,Intermediate,text,clopidogrel,extremely_strong\n",
            encoding="utf-8",
        )
        with pytest.raises(DrugLabelError, match="diplotypes.csv"):
            check_drug_labels(
                spec, snapshot=index, mode=mode, declared_use="non_commercial", write=False
            )


def test_the_check_writes_no_sources_row_and_leaves_the_licence_table_alone(
    index: DrugLabelIndex, tmp_path: Path
) -> None:
    """The decision in `drug_labels`'s docstring, pinned.

    `merge_sources_csv` keys on `(source, layer)` and `clinpgx`/`annotation` is already owned by the
    evidence-level check, whose tautology guard reads that row's `dataset`. A drug-label row there
    would stamp a *different* archive's release date into it.
    """
    spec = _module(tmp_path, "cyp2c19_star_alleles")
    before = (spec / "licensing.csv").read_text(encoding="utf-8")
    check_drug_labels(spec, snapshot=index, declared_use="non_commercial", write=True)
    assert (spec / "licensing.csv").read_text(encoding="utf-8") == before
    assert not (spec / "sources.csv").exists()


def test_a_commercial_declaration_refuses_the_read(index: DrugLabelIndex, tmp_path: Path) -> None:
    spec = _module(tmp_path, "cyp2c19_star_alleles")
    with pytest.raises(LicenseRefusal):
        check_drug_labels(spec, snapshot=index, declared_use="commercial", write=False)


# ── The attestation ─────────────────────────────────────────────────────────────────────────────


def _records(spec: Path) -> list[dict]:
    document = json.loads((spec / VERIFICATION_JSON).read_text(encoding="utf-8"))
    return [r for r in document["records"] if r["check"] == CHECK_NAME]


def test_the_record_names_both_tiers_and_never_more_findings_than_subjects(
    index: DrugLabelIndex, tmp_path: Path
) -> None:
    spec = _module(tmp_path, "cyp2c19_star_alleles")
    result = check_drug_labels(spec, snapshot=index, declared_use="non_commercial", write=True)
    record = _records(spec)[-1]

    assert record["subjects"] == len(result.compared)
    assert record["findings"] == len(result.contested)
    assert record["findings"] <= record["subjects"]
    assert record["source"] == SOURCE_NAME
    assert record["release"] == result.dataset
    for tier in LABEL_TIERS:
        assert f"at the {tier} tier" in record["detail"]


def test_no_snapshot_is_a_skip_that_says_so(tmp_path: Path) -> None:
    spec = _module(tmp_path, "cyp2c19_star_alleles")
    result = check_drug_labels(spec, snapshot=None, declared_use="non_commercial", write=True)
    assert result.not_checked == "no_reference"
    assert result.not_checked in VALID_VERIFICATION_SKIPS
    record = _records(spec)[-1]
    assert record["skipped"] == "no_reference"
    assert "build-labels" in record["detail"]


def test_a_module_with_no_pgx_table_is_not_attested_at_all(
    index: DrugLabelIndex, tmp_path: Path
) -> None:
    """Recording a skip would mine a nonce and create a `verification.json` nobody asked for."""
    spec = tmp_path / "no_pgx"
    spec.mkdir()
    result = check_drug_labels(spec, snapshot=index, declared_use="non_commercial", write=True)
    assert result.not_checked == "nothing_to_check"
    assert not (spec / VERIFICATION_JSON).exists()


def test_a_module_whose_pgx_table_names_no_drug_is_a_skip_and_not_a_zero(
    index: DrugLabelIndex, tmp_path: Path
) -> None:
    """`@tautology-zero`: a check with nothing in scope must not publish a denominator of its own."""
    spec = tmp_path / "no_drug"
    spec.mkdir()
    (spec / "diplotypes.csv").write_text(
        "gene,haplotype_a,haplotype_b,phenotype,conclusion\n"
        "CYP2C19,*1,*2,Intermediate Metabolizer,CYP2C19 *1/*2: Intermediate Metabolizer\n",
        encoding="utf-8",
    )
    result = check_drug_labels(spec, snapshot=index, declared_use="non_commercial", write=True)
    assert result.not_checked == "nothing_to_check"
    assert _records(spec)[-1]["skipped"] == "nothing_to_check"


def test_re_running_the_check_is_idempotent_over_what_it_reports(
    index: DrugLabelIndex, tmp_path: Path
) -> None:
    """A property of the module, not of the run (`@lap-stable-means-a-property-of-the-module`)."""
    spec = _module(tmp_path, "cyp2c19_star_alleles")
    first = check_drug_labels(spec, snapshot=index, declared_use="non_commercial", write=True)
    second = check_drug_labels(spec, snapshot=index, declared_use="non_commercial", write=True)
    assert [str(f) for f in first.findings] == [str(f) for f in second.findings]
    assert first.tier_subjects == second.tier_subjects
    assert first.unstated_calls == second.unstated_calls
    assert len(_records(spec)) == 1, "the record is replaced, never appended twice"


def test_the_authored_action_vocabulary_is_the_one_the_classifier_accepts() -> None:
    assert _authored_action([]) == "absent"
    assert _authored_action([None, None]) == "absent"
    assert _authored_action(["no_recommendation"]) == "declines"
    assert _authored_action(["no_recommendation", "strong"]) == "recommends"
    assert {_authored_action(v) for v in ([], ["no_recommendation"], ["strong"])} == (
        VALID_AUTHORED_ACTION
    )
    with pytest.raises(DrugLabelError):
        classify_labels("maybe", [])


def test_the_live_snapshot_still_answers_the_corpus(tmp_path: Path) -> None:
    """Opt-in (`JUST_DNA_NETWORK_TESTS=1`): the whole file, against every corpus module.

    Relationships rather than the day's numbers — the live archive must reach at least what the slice
    reaches, and must state no level this release cannot place.
    """
    if not os.getenv("JUST_DNA_NETWORK_TESTS"):
        pytest.skip("network test; set JUST_DNA_NETWORK_TESTS=1 to run")

    archive, digest = download_drug_labels_zip(tmp_path / "drugLabels.zip")
    built = build_drug_label_snapshot(archive, tmp_path / "snap", source_sha256=digest)
    live = load_drug_labels(built.out_dir)
    assert live.testing_levels() <= VALID_TESTING_LEVELS

    for name in _CORPUS:
        result = check_drug_labels(
            _module(tmp_path / name, name), snapshot=live, declared_use="non_commercial",
            write=False,
        )
        assert len(result.compared) + len(result.withheld) > 0
        assert len(result.contested) <= len(result.compared)
