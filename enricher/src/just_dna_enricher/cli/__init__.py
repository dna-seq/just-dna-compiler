"""Command-line front door for the enricher (Typer) — the network tier's user-facing command.

just-dna-enricher enrich spec/ --strict --offline
just-dna-enricher frequencies spec/                 # pass 2: allele frequency (online only)
just-dna-enricher gene-metrics spec/                # pass 3: gene constraint (offline capable)
just-dna-enricher literature spec/                  # pass 4: citations (online only)
just-dna-enricher gene-validity spec/ --source gencc  # curated gene-disease assertions (online)
just-dna-enricher assertions spec/                  # ClinVar call + review tier (offline capable)
just-dna-enricher enrich-and-compile spec/ out/ --frequencies --gene-metrics
just-dna-enricher gnomad constraint build --download --out gnomad_constraint/   # [dev]
just-dna-enricher upload out/coronary --repo just-dna-seq/annotators            # [dev]

**RM260 shell.** This package was the single-file `cli.py` until RM260 split it by command group; this
`__init__` re-exports every name the old module carried at its old dotted path (removed at 1.0), and
assembles the root `app`: the command modules are imported in registration order, then the sub-apps
are attached in the order `--help` lists them.
"""

# isort: off
# Registration order is `--help` order: each module below registers its top-level commands on import,
# so the modules are imported in the order their commands were declared, and must not be sorted.
from just_dna_enricher.cli.pass_commands import assertions_ as assertions_
from just_dna_enricher.cli.pass_commands import dosage_ as dosage_
from just_dna_enricher.cli.pass_commands import enrich_ as enrich_
from just_dna_enricher.cli.pass_commands import frequencies_ as frequencies_
from just_dna_enricher.cli.pass_commands import gene_metrics_ as gene_metrics_
from just_dna_enricher.cli.pass_commands import gene_validity_ as gene_validity_
from just_dna_enricher.cli.pass_commands import gwas_ as gwas_
from just_dna_enricher.cli.pass_commands import literature_ as literature_
from just_dna_enricher.cli.pass_commands import pgx_ as pgx_
from just_dna_enricher.cli.authoring_commands import _mint_record as _mint_record
from just_dna_enricher.cli.authoring_commands import check_identifiers_ as check_identifiers_
from just_dna_enricher.cli.authoring_commands import draft_ as draft_
from just_dna_enricher.cli.authoring_commands import template_ as template_
from just_dna_enricher.cli.authoring_commands import vrs_app as vrs_app
from just_dna_enricher.cli.authoring_commands import vrs_mint_ as vrs_mint_
from just_dna_enricher.cli.acmg_commands import acmg_app as acmg_app
from just_dna_enricher.cli.acmg_commands import acmg_build_ as acmg_build_
from just_dna_enricher.cli.acmg_commands import check_acmg_ as check_acmg_
from just_dna_enricher.cli.module_commands import enrich_and_compile as enrich_and_compile
from just_dna_enricher.cli.module_commands import upload_ as upload_
from just_dna_enricher.cli.pgx_commands import clinpgx_app as clinpgx_app
from just_dna_enricher.cli.pgx_commands import clinpgx_build_ as clinpgx_build_
from just_dna_enricher.cli.pgx_commands import clinpgx_build_labels_ as clinpgx_build_labels_
from just_dna_enricher.cli.pgx_commands import clinpgx_check_ as clinpgx_check_
from just_dna_enricher.cli.pgx_commands import clinpgx_check_labels_ as clinpgx_check_labels_
from just_dna_enricher.cli.pgx_commands import clinpgx_publish_ as clinpgx_publish_
from just_dna_enricher.cli.pgx_commands import clinpgx_publish_labels_ as clinpgx_publish_labels_
from just_dna_enricher.cli.pgx_commands import cpic_app as cpic_app
from just_dna_enricher.cli.pgx_commands import cpic_build_ as cpic_build_
from just_dna_enricher.cli.pgx_commands import cpic_publish_ as cpic_publish_
from just_dna_enricher.cli.pgx_commands import draft_clinpgx_ as draft_clinpgx_
from just_dna_enricher.cli.pgx_commands import pharmvar_app as pharmvar_app
from just_dna_enricher.cli.pgx_commands import pharmvar_build_ as pharmvar_build_
from just_dna_enricher.cli.panel_commands import PANEL_SOURCES as PANEL_SOURCES
from just_dna_enricher.cli.panel_commands import _GENE_SCOPED_PANEL_SOURCES as _GENE_SCOPED_PANEL_SOURCES
from just_dna_enricher.cli.panel_commands import _panel_source as _panel_source
from just_dna_enricher.cli.panel_commands import draft_panel_ as draft_panel_
from just_dna_enricher.cli.strchive_commands import check_repeat_bands_ as check_repeat_bands_
from just_dna_enricher.cli.strchive_commands import draft_repeats_ as draft_repeats_
from just_dna_enricher.cli.strchive_commands import strchive_app as strchive_app
from just_dna_enricher.cli.strchive_commands import strchive_build_ as strchive_build_
from just_dna_enricher.cli.strchive_commands import strchive_publish_ as strchive_publish_

# isort: on
import json as json
import os as os
from pathlib import Path as Path
from urllib.parse import urlparse as urlparse

import typer as typer
from just_dna_compiler.compiler import compile_module as compile_module
from just_dna_compiler.draft import DraftError as DraftError
from just_dna_compiler.draft import authoring_requirements as authoring_requirements
from just_dna_compiler.draft import blank_template as blank_template
from just_dna_format.manifest import VerificationRecord as VerificationRecord
from just_dna_format.vocab import VALID_DECLARED_USE as VALID_DECLARED_USE
from just_dna_format.vocab import match_vocab as match_vocab

from just_dna_enricher.acmg import DEFAULT_ACMG_URL as DEFAULT_ACMG_URL
from just_dna_enricher.acmg import AcmgListUnavailable as AcmgListUnavailable
from just_dna_enricher.acmg import AcmgReport as AcmgReport
from just_dna_enricher.acmg import AcmgSfError as AcmgSfError
from just_dna_enricher.acmg import verify_acmg_sf as verify_acmg_sf
from just_dna_enricher.alphagenome_avi_build import KNOT_FILENAME as KNOT_FILENAME
from just_dna_enricher.alphagenome_avi_build import AlphaGenomeBuildError as AlphaGenomeBuildError
from just_dna_enricher.alphagenome_check import DEFAULT_REFINEMENT_CAP as DEFAULT_REFINEMENT_CAP
from just_dna_enricher.alphagenome_check import VariantImpactError as VariantImpactError
from just_dna_enricher.alphagenome_check import check_variant_impact as check_variant_impact
from just_dna_enricher.assertions import ASSERTION_GENOME_BUILD as ASSERTION_GENOME_BUILD
from just_dna_enricher.assertions import ClinicalAssertionError as ClinicalAssertionError
from just_dna_enricher.assertions import enrich_clinical_assertions as enrich_clinical_assertions
from just_dna_enricher.atlas_protos import ATLAS_IMPORT_FAILURES as ATLAS_IMPORT_FAILURES
from just_dna_enricher.atlas_protos import client_absence as client_absence
from just_dna_enricher.caches import CACHE_LANES as CACHE_LANES
from just_dna_enricher.caches import LANES_BY_NAME as LANES_BY_NAME
from just_dna_enricher.caches import CacheLane as CacheLane
from just_dna_enricher.caches import RebuildOutcome as RebuildOutcome
from just_dna_enricher.caches import RebuildRequest as RebuildRequest
from just_dna_enricher.caches import lane_name as lane_name
from just_dna_enricher.caches import lane_status as lane_status
from just_dna_enricher.caches import parents_from_rebuild_dir as parents_from_rebuild_dir
from just_dna_enricher.caches import prepare_caches as prepare_caches
from just_dna_enricher.caches import rebuild_lane as rebuild_lane
from just_dna_enricher.civic_draft import draft_panel_from_civic as draft_panel_from_civic
from just_dna_enricher.cli._shared import _DRAFT_PRECONDITION_ERRORS as _DRAFT_PRECONDITION_ERRORS
from just_dna_enricher.cli._shared import _attest_on_the_way_out as _attest_on_the_way_out
from just_dna_enricher.cli._shared import _mode as _mode
from just_dna_enricher.cli._shared import _use as _use
from just_dna_enricher.cli._shared import app as app
from just_dna_enricher.cli.acmg_commands import acmg_record as acmg_record
from just_dna_enricher.cli.alphagenome_commands import EXPRESSION_SIDECAR as EXPRESSION_SIDECAR
from just_dna_enricher.cli.alphagenome_commands import _atlas_client_or_none as _atlas_client_or_none
from just_dna_enricher.cli.alphagenome_commands import _resolve_avi_snapshot as _resolve_avi_snapshot
from just_dna_enricher.cli.alphagenome_commands import alphagenome_app as alphagenome_app
from just_dna_enricher.cli.alphagenome_commands import alphagenome_avi_build_ as alphagenome_avi_build_
from just_dna_enricher.cli.alphagenome_commands import alphagenome_check_ as alphagenome_check_
from just_dna_enricher.cli.alphagenome_commands import alphagenome_expression_ as alphagenome_expression_
from just_dna_enricher.cli.alphagenome_commands import alphagenome_publish_ as alphagenome_publish_
from just_dna_enricher.cli.alphagenome_commands import atlas_app as atlas_app
from just_dna_enricher.cli.alphagenome_commands import atlas_generate_ as atlas_generate_
from just_dna_enricher.cli.alphagenome_commands import (
    build_alphagenome_snapshot as build_alphagenome_snapshot,
)
from just_dna_enricher.cli.authoring_commands import identifier_pgs_withheld as identifier_pgs_withheld
from just_dna_enricher.cli.authoring_commands import identifier_records as identifier_records
from just_dna_enricher.cli.authoring_commands import identifier_unreachable as identifier_unreachable
from just_dna_enricher.cli.cache_commands import _lane_names as _lane_names
from just_dna_enricher.cli.cache_commands import _pairs as _pairs
from just_dna_enricher.cli.cache_commands import _publish_rebuilt as _publish_rebuilt
from just_dna_enricher.cli.cache_commands import _selected as _selected
from just_dna_enricher.cli.cache_commands import cache_app as cache_app
from just_dna_enricher.cli.cache_commands import cache_prepare_ as cache_prepare_
from just_dna_enricher.cli.cache_commands import cache_prune_ as cache_prune_
from just_dna_enricher.cli.cache_commands import cache_pull_ as cache_pull_
from just_dna_enricher.cli.cache_commands import cache_rebuild_ as cache_rebuild_
from just_dna_enricher.cli.cache_commands import cache_status_ as cache_status_
from just_dna_enricher.cli.civic_commands import _polars as _polars
from just_dna_enricher.cli.civic_commands import civic_app as civic_app
from just_dna_enricher.cli.civic_commands import civic_build_ as civic_build_
from just_dna_enricher.cli.civic_commands import civic_citations_ as civic_citations_
from just_dna_enricher.cli.civic_commands import civic_publish_ as civic_publish_
from just_dna_enricher.cli.civic_commands import civic_reproduce_ as civic_reproduce_
from just_dna_enricher.cli.clinvar_commands import PUBMIND_PUBLISH_REFUSAL as PUBMIND_PUBLISH_REFUSAL
from just_dna_enricher.cli.clinvar_commands import build_pubmind_snapshot as build_pubmind_snapshot
from just_dna_enricher.cli.clinvar_commands import clinvar_app as clinvar_app
from just_dna_enricher.cli.clinvar_commands import clinvar_build_ as clinvar_build_
from just_dna_enricher.cli.clinvar_commands import clinvar_citations_ as clinvar_citations_
from just_dna_enricher.cli.clinvar_commands import clinvar_publish_ as clinvar_publish_
from just_dna_enricher.cli.clinvar_commands import pubmind_app as pubmind_app
from just_dna_enricher.cli.clinvar_commands import pubmind_build_ as pubmind_build_
from just_dna_enricher.cli.clinvar_commands import pubmind_publish_ as pubmind_publish_
from just_dna_enricher.cli.gene_reference_commands import constraint_app as constraint_app
from just_dna_enricher.cli.gene_reference_commands import constraint_build_ as constraint_build_
from just_dna_enricher.cli.gene_reference_commands import constraint_publish_ as constraint_publish_
from just_dna_enricher.cli.gene_reference_commands import gnomad_app as gnomad_app
from just_dna_enricher.cli.gene_reference_commands import mane_app as mane_app
from just_dna_enricher.cli.gene_reference_commands import mane_build_ as mane_build_
from just_dna_enricher.cli.lookup_commands import _echo_hint as _echo_hint
from just_dna_enricher.cli.lookup_commands import hint_app as hint_app
from just_dna_enricher.cli.lookup_commands import hint_citation_ as hint_citation_
from just_dna_enricher.cli.lookup_commands import hint_gene_ as hint_gene_
from just_dna_enricher.cli.lookup_commands import hint_recover_ as hint_recover_
from just_dna_enricher.cli.lookup_commands import hint_trait_ as hint_trait_
from just_dna_enricher.cli.lookup_commands import hint_variant_ as hint_variant_
from just_dna_enricher.cli.lookup_commands import litvar_app as litvar_app
from just_dna_enricher.cli.lookup_commands import litvar_coverage_ as litvar_coverage_
from just_dna_enricher.cli.lookup_commands import litvar_gene_ as litvar_gene_
from just_dna_enricher.cli.lookup_commands import litvar_records as litvar_records
from just_dna_enricher.cli.mitomap_commands import mitomap_app as mitomap_app
from just_dna_enricher.cli.mitomap_commands import mitomap_build_ as mitomap_build_
from just_dna_enricher.cli.mitomap_commands import mitomap_miss_ as mitomap_miss_
from just_dna_enricher.cli.mitomap_commands import mitomap_publish_ as mitomap_publish_
from just_dna_enricher.cli.panel_commands import MITOMAP_MISS_SOURCE as MITOMAP_MISS_SOURCE
from just_dna_enricher.cli.pass_commands import CLINGEN_VALIDITY_SOURCE as CLINGEN_VALIDITY_SOURCE
from just_dna_enricher.cli.pgx_commands import build_clinpgx_snapshot as build_clinpgx_snapshot
from just_dna_enricher.cli.pgx_commands import build_cpic_snapshot as build_cpic_snapshot
from just_dna_enricher.cli.pgx_commands import build_pharmvar_snapshot as build_pharmvar_snapshot
from just_dna_enricher.clingen import DEFAULT_CLINGEN_URL as DEFAULT_CLINGEN_URL
from just_dna_enricher.clingen import ClinGenError as ClinGenError
from just_dna_enricher.clingen import enrich_dosage_sensitivity as enrich_dosage_sensitivity
from just_dna_enricher.clinpgx import ClinPgxEnrichmentError as ClinPgxEnrichmentError
from just_dna_enricher.clinpgx import enrich_clinpgx as enrich_clinpgx
from just_dna_enricher.clinpgx_build import CURRENT_ARCHIVE as CURRENT_ARCHIVE
from just_dna_enricher.clinpgx_build import DEFAULT_CLINPGX_URL as DEFAULT_CLINPGX_URL
from just_dna_enricher.clinpgx_build import ClinPgxArchiveError as ClinPgxArchiveError
from just_dna_enricher.clinpgx_build import download_clinpgx_zip as download_clinpgx_zip
from just_dna_enricher.clinpgx_draft import draft_pharm_variants as draft_pharm_variants
from just_dna_enricher.clinvar_build import DEFAULT_CITATIONS_URL as DEFAULT_CITATIONS_URL
from just_dna_enricher.clinvar_build import build_citations as build_citations
from just_dna_enricher.clinvar_build import download_var_citations as download_var_citations
from just_dna_enricher.clinvar_draft import ClinVarDraftError as ClinVarDraftError
from just_dna_enricher.clinvar_draft import draft_gene_panel as draft_gene_panel
from just_dna_enricher.cpic import DEFAULT_CPIC_ENDPOINT as DEFAULT_CPIC_ENDPOINT
from just_dna_enricher.cpic import CpicError as CpicError
from just_dna_enricher.cpic_build import CpicBuildError as CpicBuildError
from just_dna_enricher.currency import unchecked_sentences as unchecked_sentences
from just_dna_enricher.download import SnapshotNotPublished as SnapshotNotPublished
from just_dna_enricher.drug_labels import DEFAULT_DRUG_LABELS_URL as DEFAULT_DRUG_LABELS_URL
from just_dna_enricher.drug_labels import DrugLabelError as DrugLabelError
from just_dna_enricher.drug_labels import arm_summary as arm_summary
from just_dna_enricher.drug_labels import check_drug_labels as check_drug_labels
from just_dna_enricher.enrich import EnrichmentError as EnrichmentError
from just_dna_enricher.enrich import enrich as enrich
from just_dna_enricher.expression import DEFAULT_MAX_ROWS as DEFAULT_MAX_ROWS
from just_dna_enricher.expression import ExpressionError as ExpressionError
from just_dna_enricher.expression import enrich_expression as enrich_expression
from just_dna_enricher.frequencies import FrequencyEnrichmentError as FrequencyEnrichmentError
from just_dna_enricher.frequencies import enrich_frequencies as enrich_frequencies
from just_dna_enricher.gene_metrics import GeneMetricsEnrichmentError as GeneMetricsEnrichmentError
from just_dna_enricher.gene_metrics import enrich_gene_metrics as enrich_gene_metrics
from just_dna_enricher.gene_validity import GeneValidityError as GeneValidityError
from just_dna_enricher.gene_validity import enrich_gene_validity as enrich_gene_validity
from just_dna_enricher.grch37 import GRCH37_BUILD as GRCH37_BUILD
from just_dna_enricher.grch37 import summarize_build_diagnoses as summarize_build_diagnoses
from just_dna_enricher.gwas import GwasError as GwasError
from just_dna_enricher.gwas import enrich_gwas as enrich_gwas
from just_dna_enricher.identifiers import IdentifierCheckError as IdentifierCheckError
from just_dna_enricher.identifiers import IdentifierUnavailable as IdentifierUnavailable
from just_dna_enricher.identifiers import check_identifiers as check_identifiers
from just_dna_enricher.licensing import CLINPGX_TERMS as CLINPGX_TERMS
from just_dna_enricher.licensing import CPIC_TERMS as CPIC_TERMS
from just_dna_enricher.licensing import PHARMVAR_TERMS as PHARMVAR_TERMS
from just_dna_enricher.licensing import LicenseRefusal as LicenseRefusal
from just_dna_enricher.licensing import check_declared_use as check_declared_use
from just_dna_enricher.licensing import sidecar_path as sidecar_path
from just_dna_enricher.licensing import sources_path as sources_path
from just_dna_enricher.literature import LiteratureEnrichmentError as LiteratureEnrichmentError
from just_dna_enricher.literature import enrich_literature as enrich_literature
from just_dna_enricher.litvar import LitvarClient as LitvarClient
from just_dna_enricher.litvar import LitvarError as LitvarError
from just_dna_enricher.litvar import check_literature_coverage as check_literature_coverage
from just_dna_enricher.litvar import coverage_reason as coverage_reason
from just_dna_enricher.locations import CACHES_DIRNAME as CACHES_DIRNAME
from just_dna_enricher.locations import CITATIONS_DIRNAME as CITATIONS_DIRNAME
from just_dna_enricher.locations import RELEASE_FILENAME as RELEASE_FILENAME
from just_dna_enricher.locations import SNAPSHOT_LICENSE_FILENAME as SNAPSHOT_LICENSE_FILENAME
from just_dna_enricher.locations import STRCHIVE_CATALOGUE_FILENAME as STRCHIVE_CATALOGUE_FILENAME
from just_dna_enricher.locations import load_env as load_env
from just_dna_enricher.locations import missing_credential_reason as missing_credential_reason
from just_dna_enricher.locations import read_release as read_release
from just_dna_enricher.locations import repro_out as repro_out
from just_dna_enricher.lookup import as_report_rows as as_report_rows
from just_dna_enricher.lookup import lookup_citation as lookup_citation
from just_dna_enricher.lookup import lookup_gene as lookup_gene
from just_dna_enricher.lookup import lookup_old_assembly as lookup_old_assembly
from just_dna_enricher.lookup import lookup_trait as lookup_trait
from just_dna_enricher.lookup import lookup_variant as lookup_variant
from just_dna_enricher.mitomap import MitomapError as MitomapError
from just_dna_enricher.mitomap_build import DEFAULT_MITOMAP_URL as DEFAULT_MITOMAP_URL
from just_dna_enricher.mitomap_draft import MitomapDraftError as MitomapDraftError
from just_dna_enricher.mitomap_draft import draft_panel_from_mitomap_miss as draft_panel_from_mitomap_miss
from just_dna_enricher.pgx import PgxEnrichmentError as PgxEnrichmentError
from just_dna_enricher.pgx import enrich_pgx as enrich_pgx
from just_dna_enricher.pgx_draft import draft_gene as draft_gene
from just_dna_enricher.pharmvar import PharmVarError as PharmVarError
from just_dna_enricher.pubmind_build import PubMindBuildError as PubMindBuildError
from just_dna_enricher.pubmind_build import download_pubmind_table as download_pubmind_table
from just_dna_enricher.pubmind_draft import DEFAULT_MIN_CONFIDENCE as DEFAULT_MIN_CONFIDENCE
from just_dna_enricher.pubmind_draft import PubMindDraftError as PubMindDraftError
from just_dna_enricher.pubmind_draft import draft_gene_panel_from_pubmind as draft_gene_panel_from_pubmind
from just_dna_enricher.sequences import summarize_ref_mismatches as summarize_ref_mismatches
from just_dna_enricher.strchive import StrchiveError as StrchiveError
from just_dna_enricher.strchive import check_repeat_bands as check_repeat_bands
from just_dna_enricher.strchive_draft import StrchiveDraftError as StrchiveDraftError
from just_dna_enricher.strchive_draft import draft_repeat_loci as draft_repeat_loci
from just_dna_enricher.upload import DEFAULT_ALPHAGENOME_AVI_REPO_ID as DEFAULT_ALPHAGENOME_AVI_REPO_ID
from just_dna_enricher.upload import DEFAULT_CLINPGX_REPO_ID as DEFAULT_CLINPGX_REPO_ID
from just_dna_enricher.upload import DEFAULT_CPIC_REPO_ID as DEFAULT_CPIC_REPO_ID
from just_dna_enricher.upload import DEFAULT_DRUG_LABELS_REPO_ID as DEFAULT_DRUG_LABELS_REPO_ID
from just_dna_enricher.upload import DEFAULT_MITOMAP_REPO_ID as DEFAULT_MITOMAP_REPO_ID
from just_dna_enricher.upload import DEFAULT_STRCHIVE_REPO_ID as DEFAULT_STRCHIVE_REPO_ID
from just_dna_enricher.verification import record_verification as record_verification
from just_dna_enricher.verification import skipped as skipped
from just_dna_enricher.vrs import MintResult as MintResult

app.add_typer(clinpgx_app, name="clinpgx")
app.add_typer(acmg_app, name="acmg")
app.add_typer(clinvar_app, name="clinvar")
app.add_typer(cache_app, name="cache")
app.add_typer(cpic_app, name="cpic")
app.add_typer(pharmvar_app, name="pharmvar")
app.add_typer(civic_app, name="civic")
app.add_typer(pubmind_app, name="pubmind")
app.add_typer(gnomad_app, name="gnomad")
app.add_typer(vrs_app, name="vrs")
app.add_typer(hint_app, name="hint")
app.add_typer(litvar_app, name="litvar")
app.add_typer(mane_app, name="mane")
app.add_typer(strchive_app, name="strchive")
app.add_typer(mitomap_app, name="mitomap")
app.add_typer(atlas_app, name="atlas")
app.add_typer(alphagenome_app, name="alphagenome")
