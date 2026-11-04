"""A pass that answered nothing writes no file (RM370, `@write-the-sourcerow`).

`@write-the-sourcerow` says a pass that **contributes nothing** writes no licence row, because a row in
`sources.csv` is the claim *this module uses this source*. The same claim, one file over, was being
made by the data tables: `enrich` wrote a header-only `clin_sig_concordance.csv` and
`clin_sig_authority_calls.csv` into every module with no `clin_sig` cell, and the 0.8 reference
examples carried them (`longevity_studies`, `model_organisms`, `cpic_gene_pairs`). The class was wider
than that pair: nine sidecars across seven passes wrote a table with a header and nothing under it
whenever the run had no subject to ask about.

**The rule is one predicate, `licensing.nothing_to_write`, called by every sidecar writer:** zero rows
and no file there already means nothing is written — and so the licence row, which only ever lands
inside the table's commit, is not written either. It never suppresses a write over a file that is
already there, because two passes empty an existing table on purpose and that emptying is an answer:
the concordance record clears a subject the authorities stopped contesting, and a merge pass prunes
rows whose variant the author deleted.

Two guards, so the next pass inherits the rule instead of remembering it:

* **behavioural**, over every `(table, command)` in `producers.DERIVED_PRODUCERS` — each run on a
  module that gives that pass nothing to answer, and the table must not appear. The runner set is
  asserted *equal* to the registry, so a new producer without a runner is red;
* **structural**, an AST walk: every enricher function that writes a CSV through `atomic_writer` calls
  the predicate, or is named in `_NOT_A_MODULE_SIDECAR` with its reason (equality, not a subset).
"""

import ast
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest
from just_dna_enricher import licensing
from just_dna_enricher.assertions import enrich_clinical_assertions
from just_dna_enricher.clingen import enrich_dosage_sensitivity
from just_dna_enricher.clinvar_build import build_snapshot
from just_dna_enricher.enrich import enrich
from just_dna_enricher.expression import enrich_expression
from just_dna_enricher.frequencies import enrich_frequencies
from just_dna_enricher.gene_metrics import enrich_gene_metrics
from just_dna_enricher.gene_validity import enrich_gene_validity
from just_dna_enricher.gnomad import GnomadClient, GnomadSettings
from just_dna_enricher.gwas import enrich_gwas
from just_dna_enricher.ld_pairs import enrich_ld_pairs
from just_dna_enricher.licensing import (
    CLINVAR_TERMS,
    merge_sources_file,
    nothing_to_write,
    require_sources_file,
)
from just_dna_enricher.literature import enrich_literature
from just_dna_enricher.net import PacingGate
from just_dna_enricher.opentargets import enrich_opentargets
from just_dna_enricher.producers import DERIVED_PRODUCERS
from just_dna_format import verification as verification_module
from just_dna_format.layout import SOURCES_CSV, resolve_sidecar
from just_dna_format.vrs import derive_vrs_allele_id

_ROOT = Path(__file__).resolve().parents[2]
_CLINVAR_SLICE = _ROOT / "assets" / "clinvar_GRCh38_slice.vcf.gz"
_OPENTARGETS_SLICE = _ROOT / "assets" / "opentargets_slice"

_YAML = (
    "schema_version: '1.0'\nmodule:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
    "genome_build: GRCh38\n"
)
# One placed variant with no `clin_sig`, no gene, no rsID and no citation: every question a pass could
# put needs one of those, so each runner below adds only the input that pass reads, emptied of subjects.
_VARIANTS = "chrom,start,ref,alts,genotype,state,conclusion\n11,5227002,T,A,A/T,risk,c\n"
_RESOLUTION_HEADER = "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
# Resolved, but on GRCh37: the two coordinate passes (gnomAD v4, the ClinVar GRCh38 snapshot) decline
# an off-build row rather than ask about it, so this module has a resolution table and no subject.
_OFF_BUILD_RESOLUTION = _RESOLUTION_HEADER + "11:5227002:T:A,,11,5227002,T,A,GRCh37,0,cache,resolved\n"
# Resolved on GRCh38 at a locus the Open Targets slice does not carry.
_ON_BUILD_RESOLUTION = (
    _RESOLUTION_HEADER
    + f"{derive_vrs_allele_id('11', 5227002, 'T', 'A')},,11,5227002,T,A,GRCh38,0,cache,resolved\n"
)
# A ClinGen curation list and a gene-validity export naming genes this module does not carry.
_CURATION_TSV = (
    "#ClinGen Gene Curation Results\n#01 Aug,2026\n"
    "#Genomic Locations are reported on GRCh38 (hg38): GCF_000001405.36\n"
    "#Gene Symbol\tGene ID\tHaploinsufficiency Score\tHaploinsufficiency Description\t"
    "Triplosensitivity Score\tTriplosensitivity Description\n"
    "BRCA1\t672\t3\tSufficient evidence for dosage pathogenicity\t0\tNo evidence available\n"
)
_PLUS = ",".join(['"+++"'] * 10)
_VALIDITY_CSV = (
    '"CLINGEN GENE DISEASE VALIDITY CURATIONS","","","","","","","","",""\n'
    '"FILE CREATED: 2026-08-13","","","","","","","","",""\n'
    f"{_PLUS}\n"
    '"GENE SYMBOL","GENE ID (HGNC)","DISEASE LABEL","DISEASE ID (MONDO)","MOI","SOP","CLASSIFICATION",'
    '"ONLINE REPORT","CLASSIFICATION DATE","GCEP"\n'
    f"{_PLUS}\n"
    '"RYR1","HGNC:10483","malignant hyperthermia susceptibility","MONDO:0007783","AD","SOP9","Definitive",'
    '"https://search.clinicalgenome.org/kb/gene-validity/CGGV:assertion_aaa-2019-03-05T160000.000Z",'
    '"2019-03-05T16:00:00.000Z","Malignant Hyperthermia Susceptibility GCEP"\n'
)


@pytest.fixture(autouse=True)
def _cheap_proof_of_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verification_module, "VERIFICATION_DIFFICULTY_BITS", 8)


@pytest.fixture(scope="module")
def clinvar_snapshot(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The committed real ClinVar slice, built once — the snapshot `enrich` and `assertions` read."""
    out = tmp_path_factory.mktemp("cv") / "cv"
    build_snapshot(_CLINVAR_SLICE, out)
    return out


class _NoNetwork(httpx.BaseTransport):
    """A pass with nothing to ask must not ask: any request fails the test outright."""

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"a pass with nothing to answer made a request to {request.url}")


def _gnomad() -> GnomadClient:
    client = GnomadClient(settings=GnomadSettings())
    client._client = httpx.Client(transport=_NoNetwork())
    client.gate = PacingGate(interval=0.0, clock=lambda: 0.0, sleeper=lambda _s: None)
    return client


class _NeverAsked:
    """Any client a pass with nothing to answer must never touch."""

    def __getattr__(self, name: str):
        raise AssertionError(f"a pass with nothing to answer called {name!r}")


@dataclass
class _NoScores:
    """An Atlas client answering an interval with no score at all."""

    asked: list = field(default_factory=list)

    def score_interval(self, chrom, start, end, *, scorers=(), gene_names=(), field_mask=True):
        self.asked.append((chrom, start, end))
        return ()


def _module(tmp_path: Path, **files: str) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    for name, text in files.items():
        (spec / name.replace("__", ".")).write_text(text, encoding="utf-8")
    return spec


# ── one runner per pass, each giving that pass nothing to answer ────────────────────────────────


def _enrich_nothing_asked(tmp_path: Path, _cv: Path) -> Path:
    """`enrich` on an rsID-only module with no cache and `--offline`: no source could be asked."""
    spec = _module(tmp_path)
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion\nrs334,A/T,risk,c\n", encoding="utf-8")
    enrich(spec, offline=True, use_gnomad=False, verify_rsids=False, verify_clinsig=False)
    return spec


def _enrich_no_clin_sig(tmp_path: Path, cv: Path) -> Path:
    """`enrich` with a ClinVar snapshot to consult and no `clin_sig` cell to consult it about."""
    spec = _module(tmp_path)
    enrich(spec, offline=True, clinvar_cache=cv, use_gnomad=False, verify_rsids=False)
    return spec


def _frequencies(tmp_path: Path, _cv: Path) -> Path:
    spec = _module(tmp_path, resolution__csv=_OFF_BUILD_RESOLUTION)
    enrich_frequencies(spec, client=_gnomad())
    return spec


def _gene_metrics(tmp_path: Path, _cv: Path) -> Path:
    spec = _module(tmp_path)
    enrich_gene_metrics(spec, client=_gnomad(), constraint_cache=tmp_path / "no-lane", download=False)
    return spec


def _dosage(tmp_path: Path, _cv: Path) -> Path:
    spec = _module(tmp_path)
    enrich_dosage_sensitivity(spec, curation_text=_CURATION_TSV)
    return spec


def _gene_validity(tmp_path: Path, _cv: Path) -> Path:
    spec = _module(tmp_path)
    enrich_gene_validity(spec, export_text=_VALIDITY_CSV)
    return spec


def _assertions(tmp_path: Path, cv: Path) -> Path:
    spec = _module(tmp_path, resolution__csv=_OFF_BUILD_RESOLUTION)
    enrich_clinical_assertions(spec, offline=True, clinvar_cache=cv)
    return spec


def _gwas(tmp_path: Path, _cv: Path) -> Path:
    spec = _module(tmp_path)
    enrich_gwas(spec, client=_NeverAsked())
    return spec


def _opentargets(tmp_path: Path, _cv: Path) -> Path:
    spec = _module(tmp_path, resolution__csv=_ON_BUILD_RESOLUTION)
    enrich_opentargets(spec, snapshot=_OPENTARGETS_SLICE)
    return spec


def _literature(tmp_path: Path, _cv: Path) -> Path:
    """A module whose one citation is DOI-only: there is no PMID for `literature.csv` to carry a row for."""
    spec = _module(tmp_path, studies__csv="chrom,start,pmid,doi\n11,5227002,NONE,10.1101/2025.11.27.690701\n")
    never = _NeverAsked()
    enrich_literature(
        spec, eutils=never, bioc=never, crossref=never, europepmc=never, check_doi=False, check_fulltext=False
    )
    return spec


def _expression(tmp_path: Path, _cv: Path) -> Path:
    spec = _module(tmp_path)
    enrich_expression(
        spec,
        "HFE",
        client=_NoScores(),
        chrom="6",
        start=26089000,
        end=26091000,
        declared_use="non_commercial",
        mane_cache=tmp_path / "no-mane-lane",
    )
    return spec


def _ld_pairs(tmp_path: Path, _cv: Path) -> Path:
    spec = _module(tmp_path)
    enrich_ld_pairs(spec, client=_NeverAsked())
    return spec


#: `(table, command) -> the runner giving that pass nothing to answer`. Asserted EQUAL to the registry
#: below, so a producer added to `DERIVED_PRODUCERS` without a runner here is red rather than unguarded.
_NOTHING_TO_ANSWER: dict[tuple[str, str], Callable[[Path, Path], Path]] = {
    ("resolution.csv", "enrich"): _enrich_nothing_asked,
    ("clin_sig_concordance.csv", "enrich"): _enrich_no_clin_sig,
    ("clin_sig_authority_calls.csv", "enrich"): _enrich_no_clin_sig,
    ("frequencies.csv", "frequencies"): _frequencies,
    ("gene_metrics.csv", "gene-metrics"): _gene_metrics,
    ("gene_metrics.csv", "dosage"): _dosage,
    ("gene_validity.csv", "gene-validity"): _gene_validity,
    ("clinical_assertions.csv", "assertions"): _assertions,
    ("gwas_effects.csv", "gwas"): _gwas,
    ("gwas_effects.csv", "opentargets enrich"): _opentargets,
    ("literature.csv", "literature"): _literature,
    ("expression_effects.csv", "alphagenome expression"): _expression,
    ("locus_to_gene.csv", "opentargets enrich"): _opentargets,
    ("colocalisations.csv", "opentargets enrich"): _opentargets,
    ("consequences.csv", "opentargets enrich"): _opentargets,
    ("ld_pairs.csv", "ld-pairs"): _ld_pairs,
}

#: Runners where another table of the same run DID answer, and legitimately recorded a licence row for
#: it — `enrich` places the variant from the ClinVar snapshot while the concordance leg has no subject.
_ANOTHER_TABLE_ANSWERED = {_enrich_no_clin_sig}


def test_every_producer_has_a_nothing_to_answer_runner() -> None:
    registered = {(p.table, p.command) for group in DERIVED_PRODUCERS.values() for p in group}
    assert set(_NOTHING_TO_ANSWER) == registered


@pytest.mark.usefixtures("no_ambient_caches")
@pytest.mark.parametrize(("table", "command"), sorted(_NOTHING_TO_ANSWER), ids=lambda v: v)
def test_a_pass_with_nothing_to_answer_writes_no_table(
    table: str, command: str, tmp_path: Path, clinvar_snapshot: Path
) -> None:
    runner = _NOTHING_TO_ANSWER[(table, command)]
    spec = runner(tmp_path, clinvar_snapshot)
    written = resolve_sidecar(spec, table)
    assert written is None, (
        f"`{command}` answered nothing and still wrote {written.name}:\n{written.read_text()}"
        if written
        else ""
    )
    if runner not in _ANOTHER_TABLE_ANSWERED:
        # The licence row lands only inside a table's commit, so no table means no row either.
        assert require_sources_file(spec, error=AssertionError) == []
        assert resolve_sidecar(spec, SOURCES_CSV) is None


# ── the predicate's other half: an existing table is still the pass's to empty ──────────────────


@pytest.mark.usefixtures("no_ambient_caches")
def test_a_record_that_stopped_being_contested_is_still_cleared(
    tmp_path: Path, clinvar_snapshot: Path
) -> None:
    """Zero rows over a file already there is an ANSWER, and is written: the concordance record clears.

    A previous run's contested subject is in the record; this run consults the same snapshot about a
    module with no `clin_sig` left. Keeping the old row would publish a disagreement nobody has any more.
    """
    spec = _enrich_no_clin_sig(tmp_path, clinvar_snapshot)
    stale = spec / "clin_sig_concordance.csv"
    stale.write_text(
        "variant_key,genotype,authored_clin_sig,authority_concordance,authored_position,opposed,checked_at\n"
        f"{derive_vrs_allele_id('11', 5227002, 'T', 'A')},A/T,benign,single,dissents,true,2026-01-01T00:00:00Z\n",
        encoding="utf-8",
    )
    enrich(spec, offline=True, clinvar_cache=clinvar_snapshot, use_gnomad=False, verify_rsids=False)
    assert stale.read_text(encoding="utf-8").count("\n") == 1  # the header, and the stale row gone


def test_a_licence_merge_that_adds_nothing_creates_no_licence_table(tmp_path: Path) -> None:
    spec = _module(tmp_path)
    assert merge_sources_file([], spec, error=AssertionError) == []
    assert resolve_sidecar(spec, SOURCES_CSV) is None
    # …and a real row still lands.
    merge_sources_file([CLINVAR_TERMS.row("resolution", declared_use="unstated")], spec, error=AssertionError)
    assert [r.source for r in require_sources_file(spec, error=AssertionError)] == [CLINVAR_TERMS.source]


def test_the_predicate() -> None:
    present = Path(__file__)
    absent = present.with_name("no-such-sidecar.csv")
    assert nothing_to_write(absent, []) is True
    assert nothing_to_write(absent, [object()]) is False
    assert nothing_to_write(present, []) is False


# ── the structural guard: every CSV writer under the enricher calls the predicate ───────────────

_SRC = Path(licensing.__file__).parent
_PREDICATE = "nothing_to_write"

#: Enricher functions that write a CSV through `atomic_writer` and are not a module's sidecar writer,
#: each with the reason. Equality below, so an entry that stops being true is red too.
_NOT_A_MODULE_SIDECAR: dict[tuple[str, str], str] = {
    ("transaction.py", "_flush"): (
        "the resolution journal: staged network answers beside the target, read by nothing but the next "
        "run and deleted at the commit — never a table a module carries"
    ),
    ("acmg_build.py", "build_acmg_snapshot"): (
        "a cache lane's snapshot under the operator's cache base, not a file beside a spec"
    ),
}


def _called_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _csv_writers() -> dict[tuple[str, str], set[str]]:
    """`(file, function) -> the names it calls`, for every function opening `atomic_writer` with a CSV header."""
    found: dict[tuple[str, str], set[str]] = {}
    for path in sorted(p for p in _SRC.rglob("*.py") if "generated" not in p.relative_to(_SRC).parts):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.FunctionDef):
                continue
            called = {_called_name(c) for c in ast.walk(node) if isinstance(c, ast.Call)}
            if "atomic_writer" in called and "writeheader" in called:
                found[(path.name, node.name)] = called
    return found


def test_every_sidecar_writer_calls_the_predicate() -> None:
    writers = _csv_writers()
    assert writers, "the walk found no CSV writer — the names it keys on moved"
    exempt = {key for key in writers if key in _NOT_A_MODULE_SIDECAR}
    assert exempt == set(_NOT_A_MODULE_SIDECAR), (
        f"exemptions naming no CSV writer any more: {sorted(set(_NOT_A_MODULE_SIDECAR) - exempt)}"
    )
    missing = sorted(key for key, called in writers.items() if key not in exempt and _PREDICATE not in called)
    assert not missing, (
        f"these write a sidecar without asking `licensing.{_PREDICATE}` first, so a run that answered "
        f"nothing leaves a header-only table behind (RM370): {missing}"
    )
