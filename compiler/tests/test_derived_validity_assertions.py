"""The two 0.6 derived-fact sidecars in the compiler (RM24 `gene_validity`, RM25 `clinical_assertions`).

The same three properties `test_fact_tables.py` pins for the 0.5 four, because they are the properties
that decide whether a derived table is safe to add at all:

* a module that does **not** carry them is byte-identical to what it compiled to before — otherwise a
  new optional table is not additive, whatever the charter says;
* a module that **does** carry them has a different `artifact.digest`, because it genuinely holds more
  content, while the SNP core's own bytes never move; and
* `compile → reverse → compile` is a fixed point on both parquets and both signatures (Principle 7).

Plus the two findings each table exists to make visible, checked as differences rather than as fields
that merely exist.
"""

import csv
from pathlib import Path

import polars as pl
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_format.assertions import ClinicalAssertionRow
from just_dna_format.gene_validity import GeneValidityRow
from just_dna_format.integrity import clinical_assertion_signature, gene_validity_signature
from just_dna_format.vrs import derive_vrs_allele_id

_YAML = """\
schema_version: "1.0"
module:
  name: demo_validity
  title: Validity and Assertions
  description: The 0.6 derived sidecars
  report_title: Validity and Assertions
defaults:
  curator: tester
  method: manual
genome_build: GRCh38
"""

_VARIANTS = (
    "chrom,start,ref,alts,genotype,state,conclusion,gene\n"
    "19,38449938,C,T,C/T,risk,Malignant hyperthermia susceptibility,RYR1\n"
    "11,5227002,T,A,A/T,risk,Sickle-cell carrier,HBB\n"
)

_STUDIES = (
    "chrom,start,ref,pmid,conclusion\n"
    "19,38449938,C,12345678,RYR1 variants and malignant hyperthermia\n"
    "11,5227002,T,23456789,Sickle-cell trait in carriers\n"
)

_RYR1 = derive_vrs_allele_id("19", 38449938, "C", "T")
_SICKLE = derive_vrs_allele_id("11", 5227002, "T", "A")

# Two RYR1 rows differing ONLY by mode of inheritance — the real ClinGen shape that made `moi` part of
# the key (59 such pairs in the 2026-08-13 release). If the key dropped it, one of these would vanish.
_GENE_VALIDITY = (
    "gene,gene_id,disease_id,disease_label,moi,classification,classification_raw,"
    "classification_date,submitter,assertion_id,report_url,dataset,source,status,fetched_at\n"
    "RYR1,HGNC:10483,MONDO:0007783,malignant hyperthermia susceptibility,autosomal_dominant,"
    "definitive,Definitive,2019-03-05T16:00:00Z,Malignant Hyperthermia Susceptibility GCEP,"
    "CGGV:assertion_aaa,,clingen_gene_validity_2026-08-13,clingen,resolved,\n"
    "RYR1,HGNC:10483,MONDO:0007783,malignant hyperthermia susceptibility,autosomal_recessive,"
    "moderate,Moderate,2019-03-05T16:00:00Z,Malignant Hyperthermia Susceptibility GCEP,"
    "CGGV:assertion_bbb,,clingen_gene_validity_2026-08-13,clingen,resolved,\n"
    "HBB,HGNC:4827,MONDO:0011382,sickle cell anemia,autosomal_recessive,definitive,Definitive,"
    "2018-06-07T16:00:00Z,Sickle Cell Disease GCEP,CGGV:assertion_ccc,,"
    "clingen_gene_validity_2026-08-13,clingen,resolved,\n"
)

# One allele with two archive records under different conditions at different review tiers — the shape
# that makes `(variant_key, variation_id)` the grain rather than one row per variant.
#
# The `review_status` cells are QUOTED because ClinVar's own wording contains commas
# (`criteria_provided,_single_submitter`). That is not fixture tidiness: an unquoted one is the exact
# ragged-row failure `hints.inspect_rows` exists to diagnose, and writing the fixture the way the
# enricher's `csv.DictWriter` writes it is what keeps the two producers agreeing.
_ASSERTIONS = (
    "variant_key,rsid,chrom,start,ref,alt,genome_build,clin_sig,clin_sig_raw,review_status,"
    "review_stars,condition,variation_id,dataset,source,status,fetched_at\n"
    f"{_RYR1},rs118192172,19,38449938,C,T,GRCh38,pathogenic,Pathogenic,practice_guideline,4,"
    "Malignant hyperthermia susceptibility,133,clinvar_2026-06-27,clinvar,resolved,\n"
    f"{_RYR1},rs118192172,19,38449938,C,T,GRCh38,uncertain_significance,Uncertain_significance,"
    '"criteria_provided,_single_submitter",1,Central core disease,134,clinvar_2026-06-27,'
    "clinvar,resolved,\n"
    f"{_SICKLE},rs334,11,5227002,T,A,GRCh38,pathogenic,Pathogenic,"
    '"criteria_provided,_multiple_submitters,_no_conflicts",2,Sickle cell anemia,15333,'
    "clinvar_2026-06-27,clinvar,resolved,\n"
)


def _spec(tmp_path: Path, *, validity: bool = False, assertions: bool = False) -> Path:
    spec = tmp_path / f"spec_{int(validity)}{int(assertions)}"
    spec.mkdir(parents=True)
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text(_VARIANTS)
    (spec / "studies.csv").write_text(_STUDIES)
    if validity:
        (spec / "gene_validity.csv").write_text(_GENE_VALIDITY)
    if assertions:
        (spec / "clinical_assertions.csv").write_text(_ASSERTIONS)
    return spec


# ── additive: a module without them does not move ───────────────────────────────────────────────


def test_the_new_sidecars_leave_the_snp_core_byte_identical(tmp_path: Path) -> None:
    bare = compile_module(_spec(tmp_path), tmp_path / "o_bare", resolve_with_ensembl=False)
    rich = compile_module(
        _spec(tmp_path, validity=True, assertions=True), tmp_path / "o_rich",
        resolve_with_ensembl=False,
    )
    assert bare.success and rich.success, (bare.errors, rich.errors)
    for name in ("weights.parquet", "annotations.parquet"):
        assert (tmp_path / "o_bare" / name).read_bytes() == (tmp_path / "o_rich" / name).read_bytes()
    # ...and the authored identity is the same content either way: these are reference facts, not
    # authored rows, so `content_signature` must not see them at all.
    assert bare.manifest.content_signature == rich.manifest.content_signature
    # ...but the artifact identity DOES differ, because the module genuinely carries more content.
    assert bare.manifest.artifact.digest != rich.manifest.artifact.digest
    assert bare.manifest.gene_validity is None and bare.manifest.clinical_assertions is None


def test_the_new_sidecar_csvs_are_fact_hashed_not_byte_hashed(tmp_path: Path) -> None:
    """Like every sidecar and unlike an authored CSV — otherwise a reverse→recompile cycle would read
    as tampering over nothing but column order and timestamps."""
    result = compile_module(
        _spec(tmp_path, validity=True, assertions=True), tmp_path / "out",
        resolve_with_ensembl=False,
    )
    input_names = {entry.name for entry in result.manifest.inputs}
    assert not {"gene_validity.csv", "clinical_assertions.csv"} & input_names
    derived_names = {entry.name for entry in result.manifest.derived}
    assert {"gene_validity.csv", "clinical_assertions.csv"} <= derived_names
    artifact_names = {entry.name for entry in result.manifest.artifact.files}
    assert {"gene_validity.parquet", "clinical_assertions.parquet"} <= artifact_names


# ── the parquet and the manifest blocks ─────────────────────────────────────────────────────────


def test_the_two_inheritance_modes_survive_as_two_rows(tmp_path: Path) -> None:
    """The probe finding, pinned where a narrowed key would break it.

    ClinGen curates *RYR1* against malignant hyperthermia under two inheritance modes at two
    strengths. A table keyed `(gene, disease)` would keep one of them, and the module would silently
    claim the surviving verdict covers both.
    """
    spec = _spec(tmp_path, validity=True)
    compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    frame = pl.read_parquet(tmp_path / "out" / "gene_validity.parquet")
    ryr1 = frame.filter(pl.col("gene") == "RYR1").sort("moi")
    assert ryr1["moi"].to_list() == ["autosomal_dominant", "autosomal_recessive"]
    assert ryr1["classification"].to_list() == ["definitive", "moderate"]


def test_the_manifest_blocks_summarize_the_new_sidecars(tmp_path: Path) -> None:
    spec = _spec(tmp_path, validity=True, assertions=True)
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    validity, assertions = result.manifest.gene_validity, result.manifest.clinical_assertions

    assert validity.row_count == 3
    assert validity.genes == ["HBB", "RYR1"]
    assert validity.diseases == ["MONDO:0007783", "MONDO:0011382"]
    assert validity.classifications == ["definitive", "moderate"]
    assert validity.datasets == ["clingen_gene_validity_2026-08-13"]

    # The point of the second table: three records, two alleles, and a star range that says the module
    # is mixing a practice guideline with a single submitter.
    assert (assertions.row_count, assertions.variant_count) == (3, 2)
    assert (assertions.min_review_stars, assertions.max_review_stars) == (1, 4)
    assert assertions.unrated_count == 0 and assertions.not_found_count == 0
    assert assertions.clin_sigs == ["pathogenic", "uncertain_significance"]

    # Both signatures are the producer-independent fact-hashes, recomputable by a consumer holding
    # nothing but the CSV — which is what makes them worth publishing.
    assert validity.signature == gene_validity_signature(_load(spec / "gene_validity.csv", GeneValidityRow))
    assert assertions.signature == clinical_assertion_signature(
        _load(spec / "clinical_assertions.csv", ClinicalAssertionRow)
    )


def test_an_unrated_record_leaves_the_star_range_null_rather_than_zero(tmp_path: Path) -> None:
    """A range over records that state no review status is not a range of zero.

    `Literature.quotes_found`'s rule, and it bites harder here: 0 is a real ClinVar rating, so a
    fabricated 0 would report the module's evidence as the weakest available.
    """
    spec = _spec(tmp_path, assertions=True)
    (spec / "clinical_assertions.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alt,genome_build,clin_sig,clin_sig_raw,review_status,"
        "review_stars,condition,variation_id,dataset,source,status,fetched_at\n"
        f"{_SICKLE},rs334,11,5227002,T,A,GRCh38,pathogenic,Pathogenic,,,,15333,"
        "clinvar_2026-06-27,clinvar,resolved,\n"
    )
    block = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False).manifest.clinical_assertions
    assert block.min_review_stars is None and block.max_review_stars is None
    assert block.unrated_count == 1


def test_a_not_found_record_is_counted_as_the_fact_it_is(tmp_path: Path) -> None:
    """"Asked and absent" is a fact about the archive; it must be visible without reading the parquet."""
    spec = _spec(tmp_path, assertions=True)
    (spec / "clinical_assertions.csv").write_text(
        _ASSERTIONS
        + f"{_SICKLE}x,,11,5227003,T,C,GRCh38,,,,,,,clinvar_2026-06-27,clinvar,not_found,\n"
    )
    block = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False).manifest.clinical_assertions
    assert block.not_found_count == 1
    assert block.row_count == 4


# ── round-trip (Principle 7) ────────────────────────────────────────────────────────────────────


def test_compile_reverse_compile_is_a_fixed_point(tmp_path: Path) -> None:
    spec = _spec(tmp_path, validity=True, assertions=True)
    first = compile_module(spec, tmp_path / "o1", resolve_with_ensembl=False)
    reverse_module(tmp_path / "o1", tmp_path / "rev")
    second = compile_module(tmp_path / "rev", tmp_path / "o2", resolve_with_ensembl=False)

    assert second.success, second.errors
    for name in ("gene_validity.csv", "clinical_assertions.csv"):
        assert (tmp_path / "rev" / name).exists()
    for name in ("gene_validity.parquet", "clinical_assertions.parquet"):
        assert (tmp_path / "o1" / name).read_bytes() == (tmp_path / "o2" / name).read_bytes()
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    assert first.manifest.gene_validity.signature == second.manifest.gene_validity.signature
    assert (
        first.manifest.clinical_assertions.signature
        == second.manifest.clinical_assertions.signature
    )


def test_the_reversed_csvs_carry_every_column_the_model_declares(tmp_path: Path) -> None:
    """A column missing from the reverse writer round-trips as silent data loss.

    `_write_table_csv` derives its columns from `model_fields`, so this is a property of the generic
    path rather than of a hand-kept list — which is exactly what makes it worth asserting once, since
    a future column added to either model gets the guarantee for free or fails here.
    """
    spec = _spec(tmp_path, validity=True, assertions=True)
    compile_module(spec, tmp_path / "o1", resolve_with_ensembl=False)
    reverse_module(tmp_path / "o1", tmp_path / "rev")
    for name, model in (
        ("gene_validity.csv", GeneValidityRow),
        ("clinical_assertions.csv", ClinicalAssertionRow),
    ):
        header = (tmp_path / "rev" / name).read_text().splitlines()[0].split(",")
        assert set(header) == set(model.model_fields)


# ── cross-checks ────────────────────────────────────────────────────────────────────────────────


def test_orphan_rows_warn_but_do_not_fail(tmp_path: Path) -> None:
    """An over-broad sidecar is harmless; failing would punish the author for the enricher's reach."""
    spec = _spec(tmp_path, validity=True, assertions=True)
    (spec / "gene_validity.csv").write_text(
        _GENE_VALIDITY
        + "NOTINMODULE,,MONDO:0000001,something,autosomal_dominant,limited,Limited,,,,,"
        "clingen_gene_validity_2026-08-13,clingen,resolved,\n"
    )
    (spec / "clinical_assertions.csv").write_text(
        _ASSERTIONS
        + "9:99:A,,9,99,A,G,GRCh38,benign,Benign,practice_guideline,4,,777,clinvar_2026-06-27,"
        "clinvar,resolved,\n"
    )
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors
    assert any("gene_validity.csv names" in w and "NOTINMODULE" in w for w in result.warnings)
    assert any("clinical_assertions.csv describes" in w and "9:99:A" in w for w in result.warnings)


def test_the_licence_row_for_a_new_layer_is_not_reported_as_an_orphan(tmp_path: Path) -> None:
    """`sources.csv` must stay LAST in `_FACT_TABLES`, and this is what notices if it does not.

    The compile loop stores each model's rows before running its check, and `_sources_checks` reads
    that store to decide which declared sources a table used. A fact table registered *after*
    `sources.csv` would be invisible to it, and every module carrying one would be told its own
    licence row is stale.
    """
    spec = _spec(tmp_path, validity=True, assertions=True)
    # The current spelling (RM51), so this test does not also carry a deprecation notice it is not about.
    (spec / "licensing.csv").write_text(
        "source,layer,license,license_url,license_sha256,attribution,notice,share_alike,"
        "commercial_use,redistribution,declared_use,dataset,fetched_at\n"
        "clingen,gene_validity,CC0-1.0,,,ClinGen,,false,true,true,unstated,,\n"
        "clinvar,clinical_assertion,public-domain,,,ClinVar NCBI,,false,true,true,unstated,,\n"
    )
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert result.success, result.errors
    assert not [w for w in result.warnings if "no table in this module uses" in w]
    assert result.manifest.sources.layers == ["clinical_assertion", "gene_validity"]


def test_an_invalid_row_in_either_new_sidecar_is_a_compile_error(tmp_path: Path) -> None:
    spec = _spec(tmp_path, validity=True)
    (spec / "gene_validity.csv").write_text(
        _GENE_VALIDITY.replace(",definitive,Definitive,", ",probably,Definitive,")
    )
    result = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert not result.success
    assert any("classification" in e for e in result.errors)


def test_validate_refuses_what_compile_refuses(tmp_path: Path) -> None:
    """The parity rule: both loops iterate `_FACT_TABLES`, so a new table joins both at once.

    Worth asserting rather than assuming — a green pre-flight followed by a refusal sends an author
    hunting a change they did not make, which is the failure that made this rule a rule.
    """
    from just_dna_compiler.compiler import validate_spec

    spec = _spec(tmp_path, assertions=True)
    (spec / "clinical_assertions.csv").write_text(_ASSERTIONS.replace(",4,", ",9,"))
    validation = validate_spec(spec)
    compilation = compile_module(spec, tmp_path / "out", resolve_with_ensembl=False)
    assert not validation.valid and not compilation.success
    assert any("review_stars" in e for e in validation.errors)


def _load(path: Path, model: type) -> list:
    """Reload a fixture CSV through the model the way `load_csv_rows` would, for a recomputed hash."""
    with path.open(newline="") as handle:
        return [model(**{k: (v or None) for k, v in row.items()}) for row in csv.DictReader(handle)]
