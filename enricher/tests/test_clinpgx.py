"""The ClinPGx snapshot builder and cross-check — network-free.

`assets/clinpgx_annotations_slice/` is cut verbatim from `summaryAnnotations.zip` as ClinPGx published
it on 2026-08-05: the real `LICENSE.txt` and `CREATED_<date>.txt`, four summary annotations and their
eleven genotype rows. Three of them are the rs4149056/simvastatin collision — one variant and one drug
carrying Metabolism/PK, Efficacy and Toxicity annotations at *different* levels, which is what broke
the first version of the cross-check — and the fourth is a real CYP2C19 haplotype annotation whose
subject is not an rsID and must not be mangled into one.

**Every expected value is computed from the slice at runtime.** ClinPGx re-curates, and RM175 is the
item about a number measured off one download outliving the file it was measured on, so a row count or
an evidence level typed into an assertion here would be the same mistake one layer down. The archive
member names and the id column are the source's own vocabulary and come from `clinpgx_build`'s vintage
table, never retyped.

**Both vintages are built from the one slice.** The retired 2025 spelling is the same rows written
under the old member names and the old id-column header, which is precisely what a stale URL serves —
so the refusal is tested against data that would otherwise have parsed perfectly.
"""

import csv
import hashlib
import json
import re
import zipfile
from pathlib import Path

import polars as pl
import pytest
from just_dna_enricher.clinpgx import ClinPgxEnrichmentError, enrich_clinpgx
from just_dna_enricher.clinpgx_build import (
    CURRENT_ARCHIVE,
    RETIRED_ARCHIVE,
    ArchiveVintage,
    ClinPgxArchiveError,
    build_snapshot,
    read_created_date,
    read_license,
)
from just_dna_enricher.licensing import LicenseRefusal
from just_dna_format import verification as verification_module
from just_dna_format.layout import VERIFICATION_JSON
from just_dna_format.verification import read_verification

_ROOT = Path(__file__).resolve().parents[2]
_SLICE = _ROOT / "assets" / "clinpgx_annotations_slice"
_LICENSE = (_SLICE / "LICENSE.txt").read_text(encoding="utf-8")


def _slice_rows(member: str) -> list[dict[str, str]]:
    """A fixture TSV read independently of the builder, so an assertion has its own ground truth."""
    with open(_SLICE / member, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _created_date() -> str:
    """The release date from the fixture's own `CREATED_<date>.txt`, never retyped."""
    names = [path.name for path in _SLICE.iterdir() if path.name.startswith("CREATED_")]
    assert len(names) == 1, names
    return names[0].removeprefix("CREATED_").removesuffix(".txt")


def _retitled(text: str, vintage: ArchiveVintage) -> str:
    """The fixture TSV with its id-column header written in `vintage`'s spelling.

    The id column appears once, in the header — a data cell is an integer id, never the column name.
    """
    assert text.count(CURRENT_ARCHIVE.id_column) == 1
    return text.replace(CURRENT_ARCHIVE.id_column, vintage.id_column)


def _archive(tmp_path: Path, vintage: ArchiveVintage = CURRENT_ARCHIVE) -> Path:
    """The fixture directory as a zip in `vintage`'s spelling.

    Zipped here rather than shipped as a binary so the fixture stays readable in the tree and a
    `git diff` on a re-cut slice shows the rows that moved.
    """
    dest = tmp_path / vintage.archive
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(_SLICE.iterdir()):
            if path.name == CURRENT_ARCHIVE.annotations:
                archive.writestr(vintage.annotations, _retitled(path.read_text(), vintage))
            elif path.name == CURRENT_ARCHIVE.alleles:
                archive.writestr(vintage.alleles, _retitled(path.read_text(), vintage))
            else:
                archive.write(path, path.name)
    return dest


_YAML = (
    'schema_version: "1.0"\n'
    "module:\n  name: slco\n  title: T\n  report_title: T\n  description: d\n"
)

_PHARM_COLUMNS = (
    "rsid", "gene", "genotype", "drug", "phenotype_category", "annotation_id",
    "evidence_level", "conclusion",
)


def _spelled(genotype: str) -> str:
    """ClinPGx writes `CC`; this workspace writes `C/C`. Both spellings are in the corpus."""
    return "/".join(genotype) if len(genotype) == 2 else genotype


def _faithful_rows() -> list[dict[str, str]]:
    """One authored row per rsID annotation in the slice, copied faithfully from it.

    Faithful means: every cell is what ClinPGx says, so any conflict the cross-check reports is the
    bug rather than the fixture. The genotype is the first the annotation's child rows carry, spelled
    the way a module author spells it.
    """
    alleles: dict[str, list[str]] = {}
    for row in _slice_rows(CURRENT_ARCHIVE.alleles):
        alleles.setdefault(row[CURRENT_ARCHIVE.id_column], []).append(row["Genotype/Allele"])
    rows = []
    for summary in _slice_rows(CURRENT_ARCHIVE.annotations):
        subject = summary["Variant/Haplotypes"]
        if not re.fullmatch(r"rs\d+", subject):
            continue  # a haplotype subject is not a variant identity; `pharm_variants.csv` wants one
        annotation_id = summary[CURRENT_ARCHIVE.id_column]
        rows.append(
            {
                "rsid": subject,
                "gene": summary["Gene"],
                "genotype": _spelled(alleles[annotation_id][0]),
                "drug": summary["Drug(s)"].split(";")[0],
                "phenotype_category": summary["Phenotype Category"],
                "annotation_id": annotation_id,
                "evidence_level": summary["Level of Evidence"],
                "conclusion": "c",
            }
        )
    return rows


def _csv(rows: list[dict[str, str]]) -> str:
    body = "\n".join(",".join(row[column] for column in _PHARM_COLUMNS) for row in rows)
    return ",".join(_PHARM_COLUMNS) + "\n" + body + "\n"


def _stale(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, str]]:
    """The same rows with one evidence level moved off what ClinPGx reports, and which row moved.

    The wrong level is derived from the right one so the fixture cannot accidentally state the truth.
    """
    moved = dict(rows[-1])
    moved["evidence_level"] = "4" if moved["evidence_level"] != "4" else "1A"
    return rows[:-1] + [moved], moved


def _ambiguous_row() -> dict[str, str]:
    """An authored row naming no category and no id where the slice holds several candidate levels.

    Derived: the (rsid, drug, genotype) the slice gives more than one evidence level for. Without one
    the ambiguity branch is unreachable and the test would be asserting nothing.
    """
    faithful = _faithful_rows()
    levels: dict[tuple[str, str, str], set[str]] = {}
    for row in faithful:
        key = (row["rsid"], row["drug"], row["genotype"])
        levels.setdefault(key, set()).add(row["evidence_level"])
    contested = [key for key, found in levels.items() if len(found) > 1]
    assert contested, f"the slice holds no contested (rsid, drug, genotype): {levels}"
    rsid, drug, genotype = contested[0]
    row = next(r for r in faithful if (r["rsid"], r["drug"], r["genotype"]) == (rsid, drug, genotype))
    return {**row, "phenotype_category": "", "annotation_id": ""}


@pytest.fixture
def archive(tmp_path: Path) -> Path:
    return _archive(tmp_path)


@pytest.fixture
def snapshot(archive: Path, tmp_path: Path) -> Path:
    build_snapshot(archive, tmp_path / "snap")
    return tmp_path / "snap"


def _spec(tmp_path: Path, pharm: str, name: str = "spec") -> Path:
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML)
    (d / "pharm_variants.csv").write_text(pharm)
    return d


# ── the builder ─────────────────────────────────────────────────────────────────────────────────
def test_license_is_read_from_the_archive_not_a_table(archive: Path, tmp_path: Path) -> None:
    """The whole point of the licensing design: the terms come from the bytes the data came in."""
    result = build_snapshot(archive, tmp_path / "snap")
    with zipfile.ZipFile(archive) as z:
        assert read_license(z) == _LICENSE
        assert read_created_date(z) == _created_date()
    # The hash is computed from the fixture's own text at runtime, never hardcoded.
    expected = "sha256:" + hashlib.sha256(_LICENSE.encode()).hexdigest()
    assert result.license_sha256 == expected
    assert (tmp_path / "snap" / "LICENSE.txt").read_text() == _LICENSE
    assert json.loads((tmp_path / "snap" / "release.json").read_text())["license_sha256"] == expected


def test_snapshot_grain_is_annotation_times_genotype(snapshot: Path) -> None:
    summaries = _slice_rows(CURRENT_ARCHIVE.annotations)
    known = {row[CURRENT_ARCHIVE.id_column] for row in summaries}
    children = [
        row for row in _slice_rows(CURRENT_ARCHIVE.alleles)
        if row[CURRENT_ARCHIVE.id_column] in known
    ]
    frame = pl.read_parquet(snapshot / "data" / "annotations.parquet")
    assert frame.height == len(children)  # one row per (annotation, genotype), the joined grain
    assert frame["annotation_id"].n_unique() == len(known)

    # A haplotype subject is not an rsID and must not be mangled into one.
    haplotypes = {
        row[CURRENT_ARCHIVE.id_column]: row["Variant/Haplotypes"]
        for row in summaries
        if not re.fullmatch(r"rs\d+", row["Variant/Haplotypes"])
    }
    assert haplotypes, "the slice must keep a non-rsID subject or this asserts nothing"
    for annotation_id, subject in haplotypes.items():
        rows = frame.filter(pl.col("annotation_id") == annotation_id)
        assert set(rows["rsid"].to_list()) == {None}
        assert set(rows["subject"].to_list()) == {subject}


def test_rebuild_is_byte_identical(archive: Path, tmp_path: Path) -> None:
    """Deterministic sort → a rebuild reproduces the parquet exactly (Principle 7)."""
    a = build_snapshot(archive, tmp_path / "a").parquet_path.read_bytes()
    b = build_snapshot(archive, tmp_path / "b").parquet_path.read_bytes()
    assert a == b


# ── the retired archive (RM175) ─────────────────────────────────────────────────────────────────
def test_the_retired_archive_is_refused_and_the_refusal_names_the_rename(tmp_path: Path) -> None:
    """It parses fine, and that is the whole problem — so the refusal is by *name*.

    `clinicalAnnotations.zip` is a frozen 2025-07-05 object the API still answers 200 through a 303,
    so a stale URL in someone's config is indistinguishable from a live one at the HTTP layer. These
    are the same rows as the current fixture under the old member names: the build would succeed and
    publish a parquet nobody could tell was fourteen months old.
    """
    retired = _archive(tmp_path, RETIRED_ARCHIVE)
    with zipfile.ZipFile(retired) as z:  # it really is readable, hence the guard
        assert RETIRED_ARCHIVE.annotations in z.namelist()

    out = tmp_path / "snap"
    with pytest.raises(ClinPgxArchiveError) as excinfo:
        build_snapshot(retired, out)
    message = str(excinfo.value)
    assert RETIRED_ARCHIVE.annotations in message and RETIRED_ARCHIVE.archive in message
    assert "2025-07-29" in message and "summary annotations" in message
    assert CURRENT_ARCHIVE.archive in message  # the refusal says what to build from instead
    assert not (out / "data" / "annotations.parquet").exists()


def test_an_archive_of_neither_vintage_gets_its_own_diagnosis(tmp_path: Path) -> None:
    """Three arms, three answers: the retired file and a wrong file are not the same problem."""
    neither = tmp_path / "somethingElse.zip"
    with zipfile.ZipFile(neither, "w") as z:
        z.writestr("LICENSE.txt", _LICENSE)
        z.writestr("relationships.tsv", "a\tb\n1\t2\n")

    with pytest.raises(ClinPgxArchiveError) as unknown:
        build_snapshot(neither, tmp_path / "snap")
    with pytest.raises(ClinPgxArchiveError) as retired:
        build_snapshot(_archive(tmp_path, RETIRED_ARCHIVE), tmp_path / "snap2")

    assert str(unknown.value) != str(retired.value)
    assert RETIRED_ARCHIVE.archive not in str(unknown.value).split("either")[0]
    assert CURRENT_ARCHIVE.annotations in str(unknown.value)


def test_the_default_url_names_the_archive_clinpgx_publishes(tmp_path: Path) -> None:
    """The URL and the member names are one fact; a rebuild that moves one must move the other."""
    from just_dna_enricher.clinpgx_build import DEFAULT_CLINPGX_URL

    assert DEFAULT_CLINPGX_URL.endswith("/" + CURRENT_ARCHIVE.archive)
    assert RETIRED_ARCHIVE.archive not in DEFAULT_CLINPGX_URL


# ── the cross-check ─────────────────────────────────────────────────────────────────────────────
def test_three_annotations_for_one_variant_drug_are_not_false_conflicts(
    snapshot: Path, tmp_path: Path
) -> None:
    """Regression: keying the index on (rsid, drug, genotype) alone reported all three as stale.

    rs4149056 + simvastatin is Metabolism/PK, Efficacy AND Toxicity, at levels ClinPGx does not agree
    with itself on. Comparing an authored Efficacy row against whichever annotation was indexed first
    flagged correctly-authored levels — every row here is faithful to the snapshot, so any conflict is
    the bug.
    """
    faithful = _faithful_rows()
    assert len({row["evidence_level"] for row in faithful}) > 1, "the collision must survive a re-cut"
    result = enrich_clinpgx(
        _spec(tmp_path, _csv(faithful)), snapshot=snapshot, declared_use="non_commercial"
    )
    assert result.conflicts == []
    assert result.unmatched == []


def test_a_genuinely_stale_level_is_still_caught(snapshot: Path, tmp_path: Path) -> None:
    """The fix must not have made the check silent."""
    rows, moved = _stale(_faithful_rows())
    result = enrich_clinpgx(
        _spec(tmp_path, _csv(rows)), snapshot=snapshot, declared_use="non_commercial"
    )
    assert len(result.conflicts) == 1
    reported = next(
        row["evidence_level"] for row in _faithful_rows()
        if row["annotation_id"] == moved["annotation_id"]
    )
    assert (result.conflicts[0].authored, result.conflicts[0].reported) == (
        moved["evidence_level"], reported,
    )


def test_strict_refuses_a_stale_level(snapshot: Path, tmp_path: Path) -> None:
    """A currency fact, not an opinion — so unlike the allele-function check, strict escalates."""
    rows, _ = _stale(_faithful_rows())
    with pytest.raises(ClinPgxEnrichmentError):
        enrich_clinpgx(
            _spec(tmp_path, _csv(rows)), snapshot=snapshot, mode="strict",
            declared_use="non_commercial",
        )


def test_an_ambiguous_row_is_reported_not_guessed(snapshot: Path, tmp_path: Path) -> None:
    """No category and no id, several candidate annotations → say so rather than flip a coin."""
    result = enrich_clinpgx(
        _spec(tmp_path, _csv([_ambiguous_row()])), snapshot=snapshot, declared_use="non_commercial"
    )
    assert result.conflicts == []
    assert any("was not checked" in w for w in result.warnings)


def test_genotype_spelling_is_normalized_across_the_two_conventions(
    snapshot: Path, tmp_path: Path
) -> None:
    """ClinPGx writes `CT`; this workspace writes `C/T`. They must match."""
    rows = [{**row, "genotype": _spelled("CT")} for row in _faithful_rows()]
    result = enrich_clinpgx(
        _spec(tmp_path, _csv(rows)), snapshot=snapshot, declared_use="non_commercial",
    )
    assert result.conflicts == [] and result.unmatched == []


def test_the_pinned_licence_hash_reaches_the_source_row(snapshot: Path, tmp_path: Path) -> None:
    result = enrich_clinpgx(
        _spec(tmp_path, _csv(_faithful_rows())), snapshot=snapshot, declared_use="non_commercial"
    )
    row = result.rows[0]
    assert row.license_sha256 == "sha256:" + hashlib.sha256(_LICENSE.encode()).hexdigest()
    assert row.commercial_use is False and row.declared_use == "non_commercial"
    assert row.dataset == f"clinpgx_{_created_date()}"


def test_declared_use_gate_applies_offline_too(snapshot: Path, tmp_path: Path) -> None:
    """The terms were accepted when the snapshot was built; using it is the same act."""
    faithful = _csv(_faithful_rows())
    with pytest.raises(LicenseRefusal):
        enrich_clinpgx(
            _spec(tmp_path, faithful, "commercial"), snapshot=snapshot,
            declared_use="commercial",
        )
    result = enrich_clinpgx(
        _spec(tmp_path, faithful, "unstated"), snapshot=snapshot
    )  # unstated
    assert result.rows == [] and result.warnings


# ── what the pass records about itself (RM45) ───────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _cheap_proof_of_work(monkeypatch):
    """8 bits instead of 20: these cases are about what is recorded, not about the work."""
    monkeypatch.setattr(verification_module, "VERIFICATION_DIFFICULTY_BITS", 8)


def _records(spec_dir: Path) -> dict:
    return {r.check: r for r in read_verification(spec_dir / VERIFICATION_JSON).records}


def test_a_run_that_compared_levels_records_what_it_compared(
    snapshot: Path, tmp_path: Path
) -> None:
    """The denominator comes from the pass, so the manifest cannot claim more than was looked up."""
    spec = _spec(tmp_path, _csv(_faithful_rows()))
    result = enrich_clinpgx(spec, snapshot=snapshot, declared_use="non_commercial")

    record = _records(spec)["pgx_evidence_level"]
    assert record.skipped is None
    assert record.subjects == result.compared > 0
    assert record.findings == len(result.conflicts) == 0
    assert record.source == "clinpgx" and record.release == result.dataset


def test_a_stale_level_is_recorded_as_a_finding(snapshot: Path, tmp_path: Path) -> None:
    rows, _ = _stale(_faithful_rows())
    spec = _spec(tmp_path, _csv(rows))
    enrich_clinpgx(spec, snapshot=snapshot, declared_use="non_commercial")

    record = _records(spec)["pgx_evidence_level"]
    assert (record.subjects, record.findings) == (len(rows), 1)


def test_an_ambiguous_row_counts_as_compared_and_not_as_a_finding(
    snapshot: Path, tmp_path: Path
) -> None:
    """It WAS looked up; the answer was "cannot tell". That is a comparison, not an absence of one.

    Recording it as unexamined would understate the denominator and make the pass look like it skipped
    a row it actually paid for.
    """
    spec = _spec(tmp_path, _csv([_ambiguous_row()]))
    enrich_clinpgx(spec, snapshot=snapshot, declared_use="non_commercial")

    record = _records(spec)["pgx_evidence_level"]
    assert (record.subjects, record.findings, record.skipped) == (1, 0, None)


def test_a_licensing_skip_is_not_spelled_offline(snapshot: Path, tmp_path: Path) -> None:
    """`not_permitted` is cleared by a declaration, so calling it `offline` misdirects the reader."""
    spec = _spec(tmp_path, _csv(_faithful_rows()), "unstated")
    enrich_clinpgx(spec, snapshot=snapshot)  # declared_use defaults to unstated

    record = _records(spec)["pgx_evidence_level"]
    assert record.skipped == "not_permitted"
    assert record.subjects == 0 and record.detail


def test_no_snapshot_records_the_skip_rather_than_a_clean_pass(
    tmp_path: Path, monkeypatch
) -> None:
    """The case the whole item is about: nothing ran, and the record has to say so.

    Without a record here the module is indistinguishable from one whose levels were all confirmed —
    `result.conflicts` is `[]` either way, which is the first assertion below.

    Reached with no cache and `offline` rather than by passing a bad `snapshot=`: an explicit path is
    the inject-only escape hatch and is never second-guessed, so a missing one raises instead of
    skipping.

    **The env var is pointed at an empty directory, NOT set to `""` — the credential idiom is
    inverted here and copying it silently disables this test.** For a credential, empty means absent:
    every reader does `api_key or os.environ.get(...)`, so `""` reads as "no key". For a *cache path*
    the ladder is `explicit → $env_var → the default dir`, and `os.getenv` returning `""` is falsy, so
    an empty value does not mean "no snapshot" — it means **"fall through to
    `~/.cache/just-dna-pipelines/clinpgx`"**, which is precisely where `just-dna-enricher cache pull`
    puts one. This test therefore passed on CI and failed on any machine that had followed the
    provisioning instructions: `enrich_clinpgx` found the real snapshot, ran the check over three
    subjects, and recorded no skip at all. Same failure shape as the `PHARMVAR_API_KEY` rule and the
    same wrong way round — green where nothing is configured, red where everything is.

    `offline=True` is not the lever either, and correctly so: reading a local parquet is not egress
    (RM38), so an offline run still consults a provisioned snapshot.
    """
    monkeypatch.setenv("JUST_DNA_CLINPGX_CACHE", str(tmp_path / "no-snapshot-here"))
    spec = _spec(tmp_path, _csv(_faithful_rows()))
    result = enrich_clinpgx(spec, declared_use="non_commercial", offline=True)
    assert result.conflicts == []  # the misleading half, on its own

    record = _records(spec)["pgx_evidence_level"]
    assert record.skipped == "offline" and record.subjects == 0


def test_a_module_with_no_pgx_table_attests_nothing_at_all(tmp_path: Path, snapshot: Path) -> None:
    """Not applicable is not the same as applicable-and-skipped, and only the second is worth a record.

    A module with no `pharm_variants.csv` has no PGx claim for this check to have an opinion about, so
    recording "skipped" would answer a question nobody asked — and it would do it by mining a nonce and
    creating a `verification.json` on a module that has nothing to do with ClinPGx. The skip vocabulary
    is for a check that COULD have run on this module; `nothing_to_check` stays reachable for a table
    that is present with no row in scope.
    """
    spec = tmp_path / "bare"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    enrich_clinpgx(spec, snapshot=snapshot, declared_use="non_commercial")

    assert not (spec / VERIFICATION_JSON).exists()


def test_two_passes_over_one_module_keep_both_records(snapshot: Path, tmp_path: Path) -> None:
    """The merge is what makes several commands share one attestation.

    A second command must not erase the first's answer — a run that did not put a question has said
    nothing about it, and dropping the earlier record would turn that into "never asked".
    """
    from just_dna_enricher.verification import ran, record_verification

    faithful = _faithful_rows()
    spec = _spec(tmp_path, _csv(faithful))
    enrich_clinpgx(spec, snapshot=snapshot, declared_use="non_commercial")
    record_verification(
        [ran("rsid_currency", subjects=4, findings=0, source="dbsnp")],
        spec,
        error=ClinPgxEnrichmentError,
    )

    records = _records(spec)
    assert set(records) == {"pgx_evidence_level", "rsid_currency"}
    assert records["pgx_evidence_level"].subjects == len(faithful)


def test_the_strict_refusal_attests_nothing(snapshot: Path, tmp_path: Path) -> None:
    """A raised pass produced no artifact, so there is nothing to record a check against."""
    rows, _ = _stale(_faithful_rows())
    spec = _spec(tmp_path, _csv(rows))
    with pytest.raises(ClinPgxEnrichmentError):
        enrich_clinpgx(spec, snapshot=snapshot, mode="strict", declared_use="non_commercial")
    assert not (spec / VERIFICATION_JSON).exists()
