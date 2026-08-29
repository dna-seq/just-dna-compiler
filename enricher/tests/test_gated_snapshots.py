"""RM38–RM41: the licence-gated caches, and the three seams a consumer could not cross.

Nothing here opens a socket. The snapshot fixtures are written with polars (the `[dev]` builder's
dependency) in the layout `cpic_build` / `pharmvar_build` actually write, and read back through the
duckdb runtime clients — so the two halves of the house convention are exercised against each other
rather than against a mock.

The shapes are trimmed from the **real** payloads probed on 2026-08-07: CPIC's 132-gene `gene` table
with `chr` on it, and PharmVar's `/genes` collection with each variant listed against both assemblies.
"""

import json
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import load_csv_rows, load_spec_variants
from just_dna_enricher.clingen import enrich_dosage_sensitivity
from just_dna_enricher.cpic import CpicError, CpicSnapshotClient
from just_dna_enricher.locations import (
    RELEASE_FILENAME,
    SNAPSHOT_DATA_DIRNAME,
    resolve_cpic_reference,
    resolve_pharmvar_reference,
)
from just_dna_enricher.net import RETRY_ATTEMPTS_ENV, attempt_floor, retry_attempts
from just_dna_enricher.pgx import enrich_pgx
from just_dna_enricher.pgx_draft import draft_gene
from just_dna_enricher.pharmvar import PharmVarError, PharmVarSnapshotClient
from just_dna_format.pgx import DiplotypeRow
from just_dna_format.spec import VariantRow

_YAML_37 = (
    'schema_version: "1.0"\n'
    "module:\n  name: probe\n  title: T\n  report_title: T\n  description: d\n"
    "genome_build: GRCh37\n"
)
_ALLELE_FUNCTION = "gene,allele,function_status\nCYP2C19,*1,normal_function\nCYP2C19,*2,normal_function\n"


def _cpic_snapshot(root: Path) -> Path:
    """A CPIC snapshot in the layout `cpic_build` writes: five parquets under `data/` + release.json."""
    data = root / SNAPSHOT_DATA_DIRNAME
    data.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        {"gene": ["CYP2C19", "CYP2C9"], "chrom": ["10", "10"], "ensembl_id": [None, None],
         "hgnc_id": [None, None], "lookup_method": ["PHENOTYPE", "ACTIVITY_SCORE"]},
        schema={"gene": pl.Utf8, "chrom": pl.Utf8, "ensembl_id": pl.Utf8, "hgnc_id": pl.Utf8,
                "lookup_method": pl.Utf8},
    ).write_parquet(data / "genes.parquet")
    pl.DataFrame(
        # CPIC's own prose, verbatim — the mapping happens at read time, not in the builder.
        {"gene": ["CYP2C19", "CYP2C19"], "allele": ["*1", "*2"], "activity_value": [1.0, 0.0],
         "clinical_function_status": ["Normal function", "No function"]},
        schema={"gene": pl.Utf8, "allele": pl.Utf8, "activity_value": pl.Float64,
                "clinical_function_status": pl.Utf8},
    ).write_parquet(data / "alleles.parquet")
    pl.DataFrame(
        {"gene": ["CYP2C19", "CYP2C19"], "diplotype": ["*1/*1", "*1/*2"],
         "phenotype": ["Normal Metabolizer", "Intermediate Metabolizer"],
         "activity_score": ["2.0", "1.0"]},
        schema={"gene": pl.Utf8, "diplotype": pl.Utf8, "phenotype": pl.Utf8,
                "activity_score": pl.Utf8},
    ).write_parquet(data / "diplotypes.parquet")
    pl.DataFrame(
        # Row two is the real CYP2C9 shape the chromosome fix unblocked: a position and no rsID.
        {"gene": ["CYP2C19", "CYP2C9"], "allele": ["*2", "*57"],
         "rsid": ["rs4244285", None], "chrom": ["10", "10"], "start": [94781859, 94947907],
         "variant_allele": ["A", "G"]},
        schema={"gene": pl.Utf8, "allele": pl.Utf8, "rsid": pl.Utf8, "chrom": pl.Utf8,
                "start": pl.Int64, "variant_allele": pl.Utf8},
    ).write_parquet(data / "allele_definitions.parquet")
    pl.DataFrame(
        # Two rows for one phenotype+drug: CPIC scopes clopidogrel to three clinical contexts. The
        # third row names two genes, so the reader must drop it exactly as the live client does.
        {"gene": ["CYP2C19", "CYP2C19", "CYP2C19"],
         "phenotype": ["Intermediate Metabolizer"] * 3,
         "drug": ["clopidogrel"] * 3,
         "population": ["CVI ACS PCI", "NVI", "general"],
         "classification": ["Strong", "Moderate", "Strong"],
         "recommendation": ["Use prasugrel", "Standard dosing", "n/a"],
         "implication": ["Reduced activation", "Reduced activation", "n/a"],
         "activity_score": [None, None, None],
         "gene_count": [1, 1, 2]},
        schema={"gene": pl.Utf8, "phenotype": pl.Utf8, "drug": pl.Utf8, "population": pl.Utf8,
                "classification": pl.Utf8, "recommendation": pl.Utf8, "implication": pl.Utf8,
                "activity_score": pl.Utf8, "gene_count": pl.Int64},
    ).write_parquet(data / "recommendations.parquet")
    (root / RELEASE_FILENAME).write_text(
        json.dumps({"dataset": "cpic_snapshot_deadbeef1234", "content_sha256": "sha256:deadbeef"}),
        encoding="utf-8",
    )
    return root


def _pharmvar_snapshot(root: Path) -> Path:
    data = root / SNAPSHOT_DATA_DIRNAME
    data.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        {"gene": ["CYP2C19", "CYP2C19"], "allele": ["CYP2C19*1", "CYP2C19*2"],
         "function": ["normal function", "no function"], "activity_value": [None, None],
         "evidence_level": ["1", "1"]},
        schema={"gene": pl.Utf8, "allele": pl.Utf8, "function": pl.Utf8,
                "activity_value": pl.Float64, "evidence_level": pl.Utf8},
    ).write_parquet(data / "alleles.parquet")
    pl.DataFrame(
        {"gene": ["CYP2C19"], "allele": ["CYP2C19*2"], "variant_index": [0],
         "rsid": ["rs4244285"], "chrom": ["10"], "start": [94781859], "ref": ["G"], "alt": ["A"]},
        schema={"gene": pl.Utf8, "allele": pl.Utf8, "variant_index": pl.Int64, "rsid": pl.Utf8,
                "chrom": pl.Utf8, "start": pl.Int64, "ref": pl.Utf8, "alt": pl.Utf8},
    ).write_parquet(data / "variants.parquet")
    (root / RELEASE_FILENAME).write_text(
        json.dumps({"dataset": "pharmvar_snapshot_cafe12345678", "genome_build": "GRCh38"}),
        encoding="utf-8",
    )
    return root


def _spec(tmp_path: Path, yaml: str = _YAML_37) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(yaml, encoding="utf-8")
    (spec / "allele_function.csv").write_text(_ALLELE_FUNCTION, encoding="utf-8")
    return spec


# ── RM38: the caches ────────────────────────────────────────────────────────────────────────────
def test_the_three_gated_caches_resolve_from_their_own_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each gated source gets its own override, and an absent cache is `None` rather than a guess.

    `$JUST_DNA_PIPELINES_CACHE_DIR` is neutralized to a temp root so a developer's real cache cannot
    make this pass for the wrong reason — the same hazard the PharmVar-key fixture exists for.
    """
    monkeypatch.setenv("JUST_DNA_PIPELINES_CACHE_DIR", str(tmp_path / "nothing"))
    for var in ("JUST_DNA_CPIC_CACHE", "JUST_DNA_PHARMVAR_CACHE", "JUST_DNA_CLINPGX_CACHE"):
        monkeypatch.setenv(var, "")
    assert resolve_cpic_reference(load_dotenv_file=False) is None
    assert resolve_pharmvar_reference(load_dotenv_file=False) is None

    built = _cpic_snapshot(tmp_path / "cpic")
    monkeypatch.setenv("JUST_DNA_CPIC_CACHE", str(built))
    assert resolve_cpic_reference(load_dotenv_file=False) == built
    # An explicit path outranks the variable — the inject-only escape hatch.
    other = _cpic_snapshot(tmp_path / "elsewhere")
    assert resolve_cpic_reference(other, load_dotenv_file=False) == other


def test_a_snapshot_answers_exactly_what_the_live_client_would(tmp_path: Path) -> None:
    """The snapshot client is duck-typed against the live one, so the passes need no branch.

    The vocabulary mapping is the part worth pinning: the parquet holds CPIC's prose (`No function`,
    `Strong`) and `map_function_status` / `map_classification` run on the way out, so a snapshot answer
    and a live answer are the same object rather than merely similar. Freezing the mapping into the
    builder would pin one release's translation into every snapshot built under it.
    """
    client = CpicSnapshotClient(_cpic_snapshot(tmp_path / "cpic"))
    alleles = client.alleles_for_gene("CYP2C19")
    assert [(a.allele, a.function_status) for a in alleles] == [
        ("*1", "normal_function"), ("*2", "no_function"),
    ]
    assert client.chrom_for_gene("CYP2C19") == "10"
    assert client.dataset == "cpic_snapshot_deadbeef1234"

    diplotypes = client.diplotypes_for_gene("CYP2C19")
    assert [(d.diplotype, d.phenotype) for d in diplotypes] == [
        ("*1/*1", "Normal Metabolizer"), ("*1/*2", "Intermediate Metabolizer"),
    ]
    # A gene the snapshot does not cover is an empty answer, never an error.
    assert client.alleles_for_gene("TPMT") == []


def test_a_multi_gene_recommendation_is_dropped_by_the_snapshot_too(tmp_path: Path) -> None:
    """`len(phenotypes) != 1` is the live client's rule, and the flattened table must reproduce it.

    A recommendation naming CYP2C19 *and* CYP2D6 is not a statement about CYP2C19 alone. Flattening
    the JSON map to one row per gene loses that unless the count travels with the row, which is why
    `gene_count` is a column — the fixture's third row has `gene_count=2` and must not appear.
    """
    client = CpicSnapshotClient(_cpic_snapshot(tmp_path / "cpic"))
    recommendations = client.recommendations("CYP2C19", "Clopidogrel")   # case-insensitive, as live
    assert [(r.population, r.classification) for r in recommendations] == [
        ("CVI ACS PCI", "strong"), ("NVI", "moderate"),
    ]
    assert all(r.gene == "CYP2C19" for r in recommendations)


def test_defining_variants_from_a_snapshot_carry_the_chromosome(tmp_path: Path) -> None:
    """The 36 coordinate-only variants are usable from the cache as well as live."""
    client = CpicSnapshotClient(_cpic_snapshot(tmp_path / "cpic"))
    variants, warnings = client.defining_variants("CYP2C9")
    assert [(v.allele, v.rsid, v.chrom, v.start) for v in variants] == [
        ("*57", None, "10", 94947907)
    ]
    assert warnings == []


def test_a_snapshot_built_by_an_older_builder_says_which_table_is_missing(tmp_path: Path) -> None:
    """Silence would read as "CPIC has nothing for this gene", which is a claim about the data."""
    root = _cpic_snapshot(tmp_path / "cpic")
    (root / SNAPSHOT_DATA_DIRNAME / "recommendations.parquet").unlink()
    with pytest.raises(CpicError, match="recommendations.parquet"):
        CpicSnapshotClient(root).recommendations("CYP2C19", "clopidogrel")


def test_the_pgx_pass_runs_fully_offline_off_snapshots_and_records_the_route(tmp_path: Path) -> None:
    """RM38's whole point: a hosted enricher checks a licence-gated source without reaching it.

    `--offline` used to be a no-op that warned and returned, so this check simply did not happen on a
    deployment that had it set. Both routes must read `snapshot`, both `SourceRow`s must carry the
    snapshot's release in `dataset` (a consumer must be able to tell a pinned file from a live API),
    and the deliberate authoring error must still be caught.
    """
    spec = _spec(tmp_path)
    result = enrich_pgx(
        spec, offline=True, declared_use="non_commercial",
        cpic_cache=_cpic_snapshot(tmp_path / "cpic"),
        pharmvar_cache=_pharmvar_snapshot(tmp_path / "pharmvar"),
    )
    assert result.routes == {"cpic": "snapshot", "pharmvar": "snapshot"}
    assert result.skipped_offline == []
    assert {(c.source, c.allele, c.reported) for c in result.conflicts} == {
        ("cpic", "*2", "no_function"), ("pharmvar", "*2", "no_function"),
    }
    by_source = {r.source: r for r in result.rows}
    assert by_source["cpic"].dataset == "cpic_snapshot_deadbeef1234"
    assert by_source["pharmvar"].dataset == "pharmvar_snapshot_cafe12345678"
    # Terms still recorded, and still non-sellable — the cache changes the route, not the licence.
    assert all(r.commercial_use is False for r in result.rows)


def test_a_pharmvar_snapshot_stands_in_for_the_personal_key(tmp_path: Path) -> None:
    """No key, no network, and the leg still answers — which is the deployment case.

    `configured` is True for a snapshot because the question it answers is "can this leg run?", and a
    resolved snapshot has already answered it.
    """
    client = PharmVarSnapshotClient(_pharmvar_snapshot(tmp_path / "pharmvar"))
    assert client.configured and client.genome_build == "GRCh38"
    alleles = client.alleles_for_gene("CYP2C19")
    assert [(a.allele, a.function) for a in alleles] == [
        ("CYP2C19*1", "normal function"), ("CYP2C19*2", "no function"),
    ]
    variant = alleles[1].variants[0]
    assert (variant.rsid, variant.chrom, variant.start) == ("rs4244285", "10", 94781859)


def test_a_snapshot_refuses_a_question_it_can_only_half_answer(tmp_path: Path) -> None:
    """Sub-alleles need the live API; a subset returned as if complete is the one outcome to refuse."""
    client = PharmVarSnapshotClient(_pharmvar_snapshot(tmp_path / "pharmvar"))
    with pytest.raises(PharmVarError, match="core alleles only"):
        client.alleles_for_gene("CYP2C19", include_sub_alleles=True)


def test_drafting_offline_from_a_snapshot_produces_the_same_rows(tmp_path: Path) -> None:
    """`draft` had no `--offline` at all, so a caller running the family under one flag still egressed.

    Demonstrated on the old behaviour: with no snapshot resolvable, `offline=True` now skips with a
    reason instead of reaching CPIC — and with one, it drafts.
    """
    spec = _spec(tmp_path)
    skipped = draft_gene(
        spec, "CYP2C19", declared_use="non_commercial", offline=True,
        cpic_cache=tmp_path / "absent",
    )
    assert skipped.skipped and skipped.added == 0
    assert any("--offline and no built snapshot" in w for w in skipped.warnings)

    drafted = draft_gene(
        spec, "CYP2C19", declared_use="non_commercial", offline=True,
        cpic_cache=_cpic_snapshot(tmp_path / "cpic"),
    )
    assert drafted.added > 0
    rows, errors, _ = load_csv_rows(spec / "diplotypes.csv", DiplotypeRow, "diplotypes.csv")
    assert not errors
    assert {(r.haplotype_a, r.haplotype_b) for r in rows} == {("*1", "*1"), ("*1", "*2")}


# ── RM39: the flag that meant the same thing in every function but one ──────────────────────────
def test_dosage_offline_is_a_noop_with_a_reason_not_a_silent_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every sibling pass takes `offline`; this one downloaded regardless, which is silent egress.

    Demonstrated rather than asserted about: `fetch_curation_list` is replaced by something that fails
    the test if it is called at all, which is exactly what the old code would have done.
    """
    def _must_not_fetch(*args: object, **kwargs: object) -> str:
        raise AssertionError("offline must not reach ClinGen")

    monkeypatch.setattr("just_dna_enricher.clingen.fetch_curation_list", _must_not_fetch)
    spec = _spec(tmp_path)
    result = enrich_dosage_sensitivity(spec, offline=True)
    assert result.skipped_offline is True
    # Three states, not two: "did not run" is neither "ran and found nothing" nor a failure.
    assert result.rows == [] and result.covered == [] and result.missing == []
    assert result.source_row is None
    assert not (spec / "gene_metrics.csv").exists()


def test_dosage_offline_still_honours_an_injected_file(tmp_path: Path) -> None:
    """Injecting the bytes is not egress, so `offline` must not refuse it — inject-only, as always."""
    curation = (
        "#ClinGen Dosage Sensitivity\n"
        "#01 Aug,2026\n"
        "#Gene Symbol\tHaploinsufficiency Score\tTriplosensitivity Score\n"
        "CYP2C19\t3\tNot yet evaluated\n"
    )
    spec = _spec(tmp_path)
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,gene,conclusion\nrs4244285,A/A,risk,CYP2C19,c\n", encoding="utf-8"
    )
    result = enrich_dosage_sensitivity(spec, offline=True, curation_text=curation)
    assert result.skipped_offline is False
    assert result.covered == ["CYP2C19"]
    assert result.rows[0].haploinsufficiency is not None
    assert result.rows[0].triplosensitivity is None      # "Not yet evaluated" is an absence


# ── RM41: the loader, and the two checks that made every caller reach for it ────────────────────
def test_load_spec_variants_injects_the_modules_declared_build(tmp_path: Path) -> None:
    """The trap a hand-rolled loader falls into, on a GRCh37 module — the corpus's uniform axis.

    A row is stamped at construction, where `module_spec.yaml` is not in scope, so a loader that does
    not inject the build *and* re-stamp mints GRCh38 identities for GRCh37 coordinates. Demonstrated
    on the old behaviour: the bare `load_csv_rows` call a consumer would write produces a different
    `variant_key` from the spec-aware one.
    """
    spec = _spec(tmp_path)
    (spec / "variants.csv").write_text(
        "chrom,start,ref,alts,genotype,state,conclusion\n10,94781859,G,A,A/A,risk,c\n", encoding="utf-8"
    )
    naive, _, _ = load_csv_rows(spec / "variants.csv", VariantRow, "variants.csv")
    aware, errors, _ = load_spec_variants(spec)
    assert not errors
    # Both mint a content-addressed id; they are ids of *different sequences*, 228 bp apart in reality.
    assert naive[0].variant_key != aware[0].variant_key
    assert aware[0]._genome_build == "GRCh37"

    # And an empty cell arrives as None with the key kept, not as "" — the other rule.
    assert aware[0].gene is None


def test_the_row_taking_checks_take_a_spec_dir_too(tmp_path: Path) -> None:
    """Both forms stay; exactly one may be passed, and neither/both is refused rather than guessed."""
    from just_dna_enricher.acmg import AcmgSfError, verify_acmg_sf
    from just_dna_enricher.identifiers import check_identifiers

    spec = _spec(tmp_path)
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,gene,acmg_sf,conclusion\nrs4244285,A/A,risk,BRCA1,true,c\n", encoding="utf-8"
    )
    # Offline with no list: nothing is checked, which is the `unchecked` ≠ `absent` answer — and the
    # point here is that it got the rows from the spec dir at all.
    report = verify_acmg_sf(spec_dir=spec, offline=True)
    assert [v.verdict for v in report.verdicts] == ["unchecked"]

    with pytest.raises(AcmgSfError, match="exactly one"):
        verify_acmg_sf(offline=True)
    with pytest.raises(AcmgSfError, match="exactly one"):
        verify_acmg_sf([], spec_dir=spec, offline=True)
    with pytest.raises(ValueError, match="exactly one"):
        check_identifiers()


# ── RM42: the retry ceiling a deployment could not raise ────────────────────────────────────────
def test_the_retry_ceiling_is_a_floor_that_preserves_per_client_tuning(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """A server inside an unattended publish wants more persistence than an author at a terminal.

    `stop_after_attempt(3)` was a decorator argument evaluated at import, so there was no moment at
    which a caller could influence it — a consumer's only route was to walk the package and reassign
    `policy.stop`, i.e. reach into another package's decorator state.

    A **floor**, not a setting: gnomAD and eutils sit at 4 because their budgets are tightest, and a
    single number that *set* every client would flatten tuning chosen on purpose.
    """
    monkeypatch.setenv(RETRY_ATTEMPTS_ENV, "")
    assert (retry_attempts(3), retry_attempts(4)) == (3, 4)

    monkeypatch.setenv(RETRY_ATTEMPTS_ENV, "8")
    assert (retry_attempts(3), retry_attempts(4)) == (8, 8)

    # Below a client's own default it is a no-op, never a way to make it give up sooner.
    monkeypatch.setenv(RETRY_ATTEMPTS_ENV, "2")
    assert (retry_attempts(3), retry_attempts(4)) == (3, 4)

    # Garbage falls back to the client's own number rather than raising mid-retry.
    monkeypatch.setenv(RETRY_ATTEMPTS_ENV, "lots")
    assert retry_attempts(3) == 3


def test_every_live_client_reads_the_floor_rather_than_a_frozen_constant(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pinned across the whole tier, so a tenth client cannot arrive with a frozen `stop`.

    Demonstrated end to end on a real policy rather than asserted about the source: the stop object is
    called with a synthetic attempt number, and the answer must move when the environment does.
    """
    import importlib
    import pkgutil

    import just_dna_enricher
    from tenacity import BaseRetrying

    # **Discovered, not listed** (RM100). This walked a hand-kept list of seven modules and asserted
    # `len(found) >= 9` against prose in `net.py` claiming nine policies — while the tree carried
    # twelve, across nine modules. A floor cannot see three new policies and a list cannot see two
    # whole modules, so the guard was blind on both axes at once. `@registry-completeness`: a registry
    # nothing iterates is a number somebody has to remember.
    found: dict[str, BaseRetrying] = {}
    for info in sorted(pkgutil.iter_modules(just_dna_enricher.__path__), key=lambda m: m.name):
        module = importlib.import_module(f"just_dna_enricher.{info.name}")
        # `@retry` hangs the policy off the wrapped function, so the walk is: module attributes, and
        # for a class its own `vars` (the methods). This is the same walk the consumer had to write.
        # Owners are filtered to those DEFINED here, or a client imported into another module would be
        # counted once per importer — the reason a naive walk reports 34 policies rather than 12.
        here = module.__name__  # the dotted name, which is what `__module__` carries
        owners = [v for v in vars(module).values() if getattr(v, "__module__", None) == here]
        owners += [
            m
            for v in vars(module).values()
            if isinstance(v, type) and getattr(v, "__module__", None) == here
            for m in vars(v).values()
            if getattr(m, "__module__", None) == here
        ]
        for owner in owners:
            policy = getattr(owner, "retry", None)
            if isinstance(policy, BaseRetrying):
                found[f"{info.name}.{getattr(owner, '__qualname__', owner)}"] = policy

    # An EQUALITY over what the walk found, so a new policy has to be named here and a deleted one
    # cannot go unnoticed — the two things the floor allowed through.
    assert set(found) == {
        "cpic.CpicClient._request",
        # RM85's release probe: the retried inner reads the header, the outer translates both legs.
        "currency.ClinVarReleaseClient._header_bytes",
        "ensembl.EnsemblResolver._graphql_rsid",
        "ensembl.EnsemblResolver._rest_rsid",
        "eutils.EutilsClient._request",
        "gnomad.GnomadClient._request",
        "grch37.Grch37Client._get",
        "gwas.GwasCatalogClient._get",
        # `_request`, not `_get`, since RM101: the retried inner and the translating outer are
        # now split here the way `cpic`, `eutils` and `gnomad` already split them.
        "identifiers.OntologyClient._request",
        "literature.CrossrefClient.exists",
        "literature.EuropePmcClient._get",
        "literature.PmcIdConverterClient._get",
        "pharmvar.PharmVarClient._request",
    }, sorted(found)
    assert all(isinstance(p.stop, attempt_floor) for p in found.values()), (
        [type(p.stop) for p in found.values()]
    )
    # The two tightest budgets keep their own, higher default.
    defaults = {p.stop.default for p in found.values()}
    assert defaults == {3, 4}

    class _State:
        attempt_number = 5

    monkeypatch.setenv(RETRY_ATTEMPTS_ENV, "")
    assert attempt_floor(3)(_State()) is True         # 5 >= 3: stop
    monkeypatch.setenv(RETRY_ATTEMPTS_ENV, "9")
    assert attempt_floor(3)(_State()) is False        # 5 >= 9 is false: keep going
