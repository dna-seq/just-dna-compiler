"""
DSL model regression tests ported from just-dna-lite's `test_module_compiler.py` (the model
unit-test half), repointed to `just_dna_format.spec`. Preserved here because the compiler code —
and these tests — are being removed from just-dna-lite.
"""

import pytest
from just_dna_format.spec import ModuleInfo, ModuleSpecConfig, StudyRow, VariantRow
from just_dna_format.vrs import derive_vrs_allele_id


class TestModuleSpecConfig:
    def test_invalid_module_name(self) -> None:
        with pytest.raises(Exception):
            ModuleInfo(name="Bad Name!", title="T", description="D", report_title="R")

    def test_invalid_schema_version(self) -> None:
        with pytest.raises(Exception):
            ModuleSpecConfig(
                schema_version="2.0",
                module=ModuleInfo(name="test", title="T", description="D", report_title="R"),
            )

    def test_defaults_applied(self) -> None:
        config = ModuleSpecConfig(
            module=ModuleInfo(name="test", title="T", description="D", report_title="R")
        )
        assert config.schema_version == "1.0"
        assert config.genome_build == "GRCh38"
        assert config.defaults.curator == "ai-module-creator"


class TestVariantRow:
    def test_valid_row_with_both(self) -> None:
        row = VariantRow(
            rsid="rs1801133", chrom="1", start=11796321, ref="G", alts="A",
            genotype="A/G", weight=-0.5, state="risk", conclusion="Heterozygous",
            gene="MTHFR", phenotype="Reduced methylation", category="methylation",
        )
        assert row.variant_key == "rs1801133"

    def test_position_only_valid(self) -> None:
        row = VariantRow(
            chrom="10", start=94781859, ref="G", alts="A", genotype="A/G",
            weight=-0.5, state="risk", conclusion="Position-only",
        )
        assert row.rsid is None
        # A resolved substitution keys on its GA4GH VRS allele id (0.5) — content-addressed and
        # build-naming. Computed here rather than pasted so the test pins the *rule*, not a literal.
        assert row.variant_key == derive_vrs_allele_id("10", 94781859, "G", "A")

    def test_distinct_alleles_at_one_locus_get_distinct_keys(self) -> None:
        # Indels: no VRS id can be minted offline (justification needs the reference sequence), so
        # these keep the coordinate key — and it still carries the alt, so they stay distinct.
        common = {"chrom": "11", "start": 5226762, "ref": "C", "state": "risk", "conclusion": "x"}
        ins = VariantRow(alts="CAAAG", genotype="C/CAAAG", **common)
        dele = VariantRow(alts="CA", genotype="C/CA", **common)
        assert ins.variant_key == "11:5226762:C:CAAAG"
        assert dele.variant_key == "11:5226762:C:CA"
        assert ins.variant_key != dele.variant_key  # no collision on chrom:start:ref
        # alts are normalized (sorted) so authored allele order doesn't change identity
        ab = VariantRow(alts="G,A", genotype="A/G", **common).variant_key
        ba = VariantRow(alts="A,G", genotype="A/G", **common).variant_key
        assert ab == ba == "11:5226762:C:A,G"
        # position-only (no alt) keeps the bare coordinate key; unchanged from before
        pos = VariantRow(chrom="1", start=100, ref="G", genotype="G/G", state="risk", conclusion="x")
        assert pos.variant_key == "1:100:G"

    def test_distinct_substitutions_at_one_locus_get_distinct_keys(self) -> None:
        # The substitution half of the same guarantee, now carried by the VA: a benign C>G beside a
        # pathogenic C>A at one position must not collide (the same-locus allele collision 0.5 fixed).
        common = {"chrom": "11", "start": 5226762, "ref": "C", "state": "risk", "conclusion": "x"}
        to_g = VariantRow(alts="G", genotype="C/G", **common)
        to_a = VariantRow(alts="A", genotype="A/C", **common)
        assert to_g.variant_key != to_a.variant_key
        assert to_g.variant_key == derive_vrs_allele_id("11", 5226762, "C", "G")
        assert to_a.variant_key == derive_vrs_allele_id("11", 5226762, "C", "A")

    def test_neither_rsid_nor_position_rejected(self) -> None:
        with pytest.raises(Exception, match="At least one identifier"):
            VariantRow(genotype="A/G", weight=0.0, state="neutral", conclusion="Test")

    def test_invalid_rsid(self) -> None:
        with pytest.raises(Exception, match="rsid"):
            VariantRow(rsid="notAnRsid", genotype="A/G", weight=0.0, state="neutral", conclusion="T")

    def test_unsorted_genotype_rejected(self) -> None:
        with pytest.raises(Exception, match="alphabetically sorted"):
            VariantRow(rsid="rs123", genotype="G/A", weight=0.0, state="neutral", conclusion="T")

    def test_invalid_state(self) -> None:
        with pytest.raises(Exception, match="state"):
            VariantRow(rsid="rs123", genotype="A/G", weight=0.0, state="bad_state", conclusion="T")

    def test_chrom_normalization(self) -> None:
        row = VariantRow(
            rsid="rs123", chrom="chr1", start=100, genotype="A/G",
            weight=0.0, state="neutral", conclusion="Test",
        )
        assert row.chrom == "1"

    def test_partial_position_rejected(self) -> None:
        with pytest.raises(Exception, match="chrom and start are required"):
            VariantRow(
                rsid="rs123", chrom="1", start=None, genotype="A/G",
                weight=0.0, state="neutral", conclusion="Test",
            )

    def test_ref_without_position_rejected(self) -> None:
        with pytest.raises(Exception, match="ref/alts require chrom and start"):
            VariantRow(
                rsid="rs123", ref="A", genotype="A/G", weight=0.0,
                state="neutral", conclusion="Test",
            )


class TestStudyRow:
    def test_valid_study_with_rsid(self) -> None:
        assert StudyRow(rsid="rs1801133", pmid="9545397", conclusion="Test").variant_key == "rs1801133"

    def test_valid_study_with_position(self) -> None:
        row = StudyRow(chrom="10", start=94781859, ref="G", pmid="12345", conclusion="Test")
        assert row.variant_key == "10:94781859:G"

    def test_study_naming_no_variant_is_accepted_and_has_no_key(self) -> None:
        """RM47 relaxed this: a citation row may ground the module or a bin boundary.

        It used to raise "At least one identifier". The rule was unsatisfiable for exactly the
        modules that most needed a citation — a `repeat_alleles.csv` row is keyed `(gene,
        repeat_unit)` — so authors were pushed into writing a bare `chrom` the paper is not about.
        `variant_key` answers `None` rather than the string `"None:None:None"`."""
        row = StudyRow(pmid="8458085", conclusion="CAG threshold definition")
        assert row.variant_key is None
        assert StudyRow.REQUIRED_ANY_OF == ()

    def test_empty_pmid_rejected(self) -> None:
        with pytest.raises(Exception, match="pmid"):
            StudyRow(rsid="rs123", pmid="", conclusion="Test")

    def test_freeform_pmid_accepted(self) -> None:
        row = StudyRow(rsid="rs123", pmid="PMID 17478681; PMID 21378990;", conclusion="Test")
        assert row.pmid == "PMID 17478681; PMID 21378990;"
