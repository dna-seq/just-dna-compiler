"""
Module spec compiler: validates a spec directory and compiles it to a composed multi-parquet
artifact plus a `manifest.json`. A module composes from optional table kinds (RM2): the three-parquet
SNP core (weights, annotations, studies) when it carries variants, plus one parquet per 0.4 table
kind it includes (diplotypes, pharm_variants, pgs, the binning kinds, …). `ARTIFACT_PARQUETS` is the
roster and `len(ARTIFACT_PARQUETS)` the count — stated that way rather than spelled, because this
sentence carried a spelled-out figure for two releases while the tuple grew past it (RM218).

Public API:
    validate_spec(spec_dir) -> ValidationResult
    compile_module(spec_dir, output_dir, ...) -> CompilationResult   (emits manifest.json)
    reverse_module(parquet_dir, output_dir, ...) -> Path

The DSL/manifest schema comes from `just-dna-format`; this package is the transform between them.

RM260: this `__init__` is the re-export shell that keeps every dotted path into the old single-file
`compiler.py` resolving to the same object. The code lives in the submodules beside it; the shell is
removed at 1.0.
"""

import csv as csv
import difflib as difflib
import logging as logging
import math as math
import re as re
import shutil as shutil
import types as types
import warnings as warnings
from collections import defaultdict as defaultdict
from collections.abc import Callable as Callable
from collections.abc import Iterable as Iterable
from dataclasses import dataclass as dataclass
from importlib.metadata import PackageNotFoundError as PackageNotFoundError
from importlib.metadata import version as version
from pathlib import Path as Path
from typing import Any as Any
from typing import NamedTuple as NamedTuple
from typing import Union as Union
from typing import get_args as get_args
from typing import get_origin as get_origin

import yaml as yaml
from just_dna_format.alleles import RECOMMENDED_SYMBOLIC_SUBTYPES as RECOMMENDED_SYMBOLIC_SUBTYPES
from just_dna_format.alleles import SYMBOLIC_ALLELE_TYPES as SYMBOLIC_ALLELE_TYPES
from just_dna_format.alleles import is_symbolic_allele as is_symbolic_allele
from just_dna_format.alleles import is_unobservable_allele as is_unobservable_allele
from just_dna_format.alleles import non_nucleotide_reason as non_nucleotide_reason
from just_dna_format.alleles import split_genotype as split_genotype
from just_dna_format.alleles import symbolic_allele_defect as symbolic_allele_defect
from just_dna_format.assertions import ClinicalAssertionRow as ClinicalAssertionRow
from just_dna_format.base import DEFAULT_GENOME_BUILD as DEFAULT_GENOME_BUILD
from just_dna_format.base import IDENTITY_FIELDS as IDENTITY_FIELDS
from just_dna_format.base import AuthoredModel as AuthoredModel
from just_dna_format.base import authored_field_names as authored_field_names
from just_dna_format.base import derive_variant_key as derive_variant_key
from just_dna_format.binning import ActivityPhenotypeRow as ActivityPhenotypeRow
from just_dna_format.binning import CopyNumberRow as CopyNumberRow
from just_dna_format.binning import HeteroplasmyRow as HeteroplasmyRow
from just_dna_format.binning import MeasureBinRow as MeasureBinRow
from just_dna_format.binning import RepeatAlleleRow as RepeatAlleleRow
from just_dna_format.binning import deprecation_warnings as deprecation_warnings
from just_dna_format.binning import format_group_key as format_group_key
from just_dna_format.binning import measurement_shape_warnings as measurement_shape_warnings
from just_dna_format.binning import validate_bins as validate_bins
from just_dna_format.concordance import ClinSigAuthorityCallRow as ClinSigAuthorityCallRow
from just_dna_format.concordance import ClinSigConcordanceRow as ClinSigConcordanceRow
from just_dna_format.expression import ExpressionEffectRow as ExpressionEffectRow
from just_dna_format.findings import CodedWarning as CodedWarning
from just_dna_format.findings import classify as classify
from just_dna_format.findings import restate as restate
from just_dna_format.frequency import FrequencyRow as FrequencyRow
from just_dna_format.gene_metrics import GeneMetricsRow as GeneMetricsRow
from just_dna_format.gene_validity import SUPERSEDED as SUPERSEDED
from just_dna_format.gene_validity import GeneValidityRow as GeneValidityRow
from just_dna_format.gene_validity import classify_currency as classify_currency
from just_dna_format.gene_validity import superseded_groups as superseded_groups
from just_dna_format.gene_validity import undecidable_groups as undecidable_groups
from just_dna_format.gwas import GwasEffectRow as GwasEffectRow
from just_dna_format.identity import is_valid_version as is_valid_version
from just_dna_format.integrity import build_artifact as build_artifact
from just_dna_format.integrity import clin_sig_authority_call_signature as clin_sig_authority_call_signature
from just_dna_format.integrity import clin_sig_concordance_signature as clin_sig_concordance_signature
from just_dna_format.integrity import file_entries as file_entries
from just_dna_format.integrity import file_entry as file_entry
from just_dna_format.integrity import newline_normalized_file_entries as newline_normalized_file_entries
from just_dna_format.integrity import sha256_file as sha256_file
from just_dna_format.layout import DERIVED_SUBDIR as DERIVED_SUBDIR
from just_dna_format.layout import SOURCES_CSV as SOURCES_CSV
from just_dna_format.layout import VERIFICATION_JSON as VERIFICATION_JSON
from just_dna_format.layout import SidecarCollision as SidecarCollision
from just_dna_format.layout import deprecation_notice as deprecation_notice
from just_dna_format.layout import resolve_sidecar as resolve_sidecar
from just_dna_format.layout import sidecar_relative_names as sidecar_relative_names
from just_dna_format.layout import sidecar_spellings as sidecar_spellings
from just_dna_format.layout import sidecar_write_path as sidecar_write_path
from just_dna_format.literature import LiteratureRow as LiteratureRow
from just_dna_format.manifest import LOGO_EXTENSIONS as LOGO_EXTENSIONS
from just_dna_format.manifest import README_CANDIDATES as README_CANDIDATES
from just_dna_format.manifest import README_EXTENSIONS as README_EXTENSIONS
from just_dna_format.manifest import ClinicalAssertions as ClinicalAssertions
from just_dna_format.manifest import ClinSigConcordance as ClinSigConcordance
from just_dna_format.manifest import Compilation as Compilation
from just_dna_format.manifest import Display as Display
from just_dna_format.manifest import ExpressionEffects as ExpressionEffects
from just_dna_format.manifest import FileEntry as FileEntry
from just_dna_format.manifest import Frequency as Frequency
from just_dna_format.manifest import GeneMetrics as GeneMetrics
from just_dna_format.manifest import GeneValidity as GeneValidity
from just_dna_format.manifest import GwasEffects as GwasEffects
from just_dna_format.manifest import Identity as Identity
from just_dna_format.manifest import Literature as Literature
from just_dna_format.manifest import ModuleManifest as ModuleManifest
from just_dna_format.manifest import Provenance as Provenance
from just_dna_format.manifest import ProvenanceDoc as ProvenanceDoc
from just_dna_format.manifest import Sources as Sources
from just_dna_format.manifest import Stats as Stats
from just_dna_format.manifest import Verification as Verification
from just_dna_format.manifest import VerificationDoc as VerificationDoc
from just_dna_format.manifest import read_manifest as read_manifest
from just_dna_format.manifest import write_manifest as write_manifest
from just_dna_format.normalize import now_utc_iso as now_utc_iso
from just_dna_format.normalize import parse_p_value as parse_p_value
from just_dna_format.normalize import strip_authority_keys as strip_authority_keys
from just_dna_format.overrides import LOSSY_OVERLAY_TABLES as LOSSY_OVERLAY_TABLES
from just_dna_format.overrides import OVERRIDABLE_TABLES as OVERRIDABLE_TABLES
from just_dna_format.overrides import VINDICATING_OVERLAY_TABLE as VINDICATING_OVERLAY_TABLE
from just_dna_format.overrides import OverrideRow as OverrideRow
from just_dna_format.overrides import apply_overrides as apply_overrides
from just_dna_format.overrides import classify_update_targets as classify_update_targets
from just_dna_format.overrides import classify_vindicated_answers as classify_vindicated_answers
from just_dna_format.overrides import overlay_coherence_errors as overlay_coherence_errors
from just_dna_format.overrides import update_targets as update_targets
from just_dna_format.pgs import PgsRow as PgsRow
from just_dna_format.pgx import AlleleFunctionRow as AlleleFunctionRow
from just_dna_format.pgx import DiplotypeRow as DiplotypeRow
from just_dna_format.pgx import HaplotypeRow as HaplotypeRow
from just_dna_format.pgx import PharmVariantRow as PharmVariantRow
from just_dna_format.resolution import ResolutionRow as ResolutionRow
from just_dna_format.sources import SourceRow as SourceRow
from just_dna_format.sources import taints_commercial_use as taints_commercial_use
from just_dna_format.sources import taints_redistribution as taints_redistribution
from just_dna_format.spec import RESERVED_FLAGS as RESERVED_FLAGS
from just_dna_format.spec import Defaults as Defaults
from just_dna_format.spec import ModuleSpecConfig as ModuleSpecConfig
from just_dna_format.spec import StudyRow as StudyRow
from just_dna_format.spec import VariantRow as VariantRow
from just_dna_format.spec import extract_pmids as extract_pmids
from just_dna_format.verification import attest as attest
from just_dna_format.verification import attestation_failure as attestation_failure
from just_dna_format.verification import close as close
from just_dna_format.verification import module_binding as module_binding
from just_dna_format.verification import read_verification as read_verification
from just_dna_format.verification import verification_block as verification_block
from just_dna_format.verification import write_verification as write_verification
from just_dna_format.vocab import ALLELE_PATTERN as ALLELE_PATTERN
from just_dna_format.vocab import VALID_ELEMENT_RULES as VALID_ELEMENT_RULES
from just_dna_format.vocab import VCF_COLLIDING_KEYS as VCF_COLLIDING_KEYS
from just_dna_format.vocab import VCF_COLLISION_REASONS as VCF_COLLISION_REASONS
from just_dna_format.vocab import VCF_NUMBER_MEANINGS as VCF_NUMBER_MEANINGS
from just_dna_format.vocab import VCF_POINTER_COMPANIONS as VCF_POINTER_COMPANIONS
from just_dna_format.vocab import VCF_POINTER_FIELDS as VCF_POINTER_FIELDS
from just_dna_format.vocab import is_multi_valued_number as is_multi_valued_number
from just_dna_format.vocab import population_sort_key as population_sort_key
from just_dna_format.vocab import split_field_pointer as split_field_pointer
from just_dna_format.vocab import vcf_field_number as vcf_field_number
from just_dna_format.vrs import UnsupportedBuildError as UnsupportedBuildError
from just_dna_format.vrs import builds_containing_position as builds_containing_position
from just_dna_format.vrs import contig_length as contig_length
from just_dna_format.vrs import derive_vrs_allele_id as derive_vrs_allele_id
from just_dna_format.vrs import in_pseudoautosomal_region as in_pseudoautosomal_region
from just_dna_format.vrs import is_substitution as is_substitution
from just_dna_format.vrs import sole_build_naming_contig as sole_build_naming_contig
from just_dna_format.vrs import split_vrs_ids as split_vrs_ids
from pydantic import BaseModel as BaseModel
from pydantic import ValidationError as ValidationError

from just_dna_compiler.compiler.allele_checks import _ALLELE_CELL_SEP as _ALLELE_CELL_SEP
from just_dna_compiler.compiler.allele_checks import _SYMBOLIC_DROPPABLE_TABLES as _SYMBOLIC_DROPPABLE_TABLES
from just_dna_compiler.compiler.allele_checks import _SYMBOLIC_REASONS as _SYMBOLIC_REASONS
from just_dna_compiler.compiler.allele_checks import _allele_verdict as _allele_verdict
from just_dna_compiler.compiler.allele_checks import _allowed_alleles as _allowed_alleles
from just_dna_compiler.compiler.allele_checks import _apply_symbolic_drops as _apply_symbolic_drops
from just_dna_compiler.compiler.allele_checks import _check_allele_membership as _check_allele_membership
from just_dna_compiler.compiler.allele_checks import _check_genotype_coverage as _check_genotype_coverage
from just_dna_compiler.compiler.allele_checks import _check_p_value_num as _check_p_value_num
from just_dna_compiler.compiler.allele_checks import (
    _check_study_effect_alleles as _check_study_effect_alleles,
)
from just_dna_compiler.compiler.allele_checks import _check_symbolic_alleles as _check_symbolic_alleles
from just_dna_compiler.compiler.allele_checks import _emptied_table_errors as _emptied_table_errors
from just_dna_compiler.compiler.allele_checks import _ordinal as _ordinal
from just_dna_compiler.compiler.allele_checks import _resolved_allele_verdict as _resolved_allele_verdict
from just_dna_compiler.compiler.allele_checks import _site_reference_allele as _site_reference_allele
from just_dna_compiler.compiler.allele_checks import _spelling_because as _spelling_because
from just_dna_compiler.compiler.allele_checks import _spelling_clauses as _spelling_clauses
from just_dna_compiler.compiler.allele_checks import _symbolic_allele_messages as _symbolic_allele_messages
from just_dna_compiler.compiler.allele_checks import _symbolic_findings as _symbolic_findings
from just_dna_compiler.compiler.allele_checks import _SymbolicFinding as _SymbolicFinding
from just_dna_compiler.compiler.binning_checks import _BINNING_TABLE_KINDS as _BINNING_TABLE_KINDS
from just_dna_compiler.compiler.binning_checks import _CITING_TABLE_KINDS as _CITING_TABLE_KINDS
from just_dna_compiler.compiler.binning_checks import (
    _check_binning_deprecations as _check_binning_deprecations,
)
from just_dna_compiler.compiler.binning_checks import _check_binning_grounding as _check_binning_grounding
from just_dna_compiler.compiler.binning_checks import _check_measure_shape as _check_measure_shape
from just_dna_compiler.compiler.fact_checks import _REDUNDANCY_TOLERANCE as _REDUNDANCY_TOLERANCE
from just_dna_compiler.compiler.fact_checks import _check_ba1_lint as _check_ba1_lint
from just_dna_compiler.compiler.fact_checks import _check_frequency_arithmetic as _check_frequency_arithmetic
from just_dna_compiler.compiler.fact_checks import (
    _check_gene_metrics_arithmetic as _check_gene_metrics_arithmetic,
)
from just_dna_compiler.compiler.fact_checks import (
    _check_gene_validity_currency as _check_gene_validity_currency,
)
from just_dna_compiler.compiler.fact_checks import (
    _check_quote_counter_is_current as _check_quote_counter_is_current,
)
from just_dna_compiler.compiler.fact_checks import (
    _check_quoted_article_licenses as _check_quoted_article_licenses,
)
from just_dna_compiler.compiler.fact_checks import (
    _classify_deferred_overlay_updates as _classify_deferred_overlay_updates,
)
from just_dna_compiler.compiler.fact_checks import _close as _close
from just_dna_compiler.compiler.fact_checks import (
    _cross_check_clin_sig_concordance as _cross_check_clin_sig_concordance,
)
from just_dna_compiler.compiler.fact_checks import (
    _cross_check_clinical_assertions as _cross_check_clinical_assertions,
)
from just_dna_compiler.compiler.fact_checks import _cross_check_frequencies as _cross_check_frequencies
from just_dna_compiler.compiler.fact_checks import _cross_check_gene_metrics as _cross_check_gene_metrics
from just_dna_compiler.compiler.fact_checks import _cross_check_gene_validity as _cross_check_gene_validity
from just_dna_compiler.compiler.fact_checks import _cross_check_gwas_effects as _cross_check_gwas_effects
from just_dna_compiler.compiler.fact_checks import _cross_check_literature as _cross_check_literature
from just_dna_compiler.compiler.fact_checks import _currency_group_names as _currency_group_names
from just_dna_compiler.compiler.fact_checks import cited_pmids as cited_pmids
from just_dna_compiler.compiler.fact_checks import literature_target_survives as literature_target_survives
from just_dna_compiler.compiler.fact_checks import resolution_target_survives as resolution_target_survives
from just_dna_compiler.compiler.fact_checks import split_cited_literature as split_cited_literature
from just_dna_compiler.compiler.load import _DEFAULTED_VARIANT_FIELDS as _DEFAULTED_VARIANT_FIELDS
from just_dna_compiler.compiler.load import SpecError as SpecError
from just_dna_compiler.compiler.load import _citations_over as _citations_over
from just_dna_compiler.compiler.load import _content_signature as _content_signature
from just_dna_compiler.compiler.load import _load_csv_rows as _load_csv_rows
from just_dna_compiler.compiler.load import _load_kind_rows as _load_kind_rows
from just_dna_compiler.compiler.load import _load_yaml as _load_yaml
from just_dna_compiler.compiler.load import _resolve_spec_defaults as _resolve_spec_defaults
from just_dna_compiler.compiler.load import binning_citations as binning_citations
from just_dna_compiler.compiler.load import content_signature as content_signature
from just_dna_compiler.compiler.load import load_binning_rows as load_binning_rows
from just_dna_compiler.compiler.load import load_citing_rows as load_citing_rows
from just_dna_compiler.compiler.load import load_csv_rows as load_csv_rows
from just_dna_compiler.compiler.load import load_spec as load_spec
from just_dna_compiler.compiler.load import load_spec_variants as load_spec_variants
from just_dna_compiler.compiler.load import spec_tables as spec_tables
from just_dna_compiler.compiler.load import table_citations as table_citations
from just_dna_compiler.compiler.manifest import _UNCORROBORABLE_LAYERS as _UNCORROBORABLE_LAYERS
from just_dna_compiler.compiler.manifest import BUILD_AGREEMENT_CHECK as BUILD_AGREEMENT_CHECK
from just_dna_compiler.compiler.manifest import UNCLOSED_PHRASE as UNCLOSED_PHRASE
from just_dna_compiler.compiler.manifest import _build_manifest as _build_manifest
from just_dna_compiler.compiler.manifest import (
    _check_declared_license_agrees as _check_declared_license_agrees,
)
from just_dna_compiler.compiler.manifest import _check_license_gate as _check_license_gate
from just_dna_compiler.compiler.manifest import _clin_sig_concordance_block as _clin_sig_concordance_block
from just_dna_compiler.compiler.manifest import _clinical_assertion_signature as _clinical_assertion_signature
from just_dna_compiler.compiler.manifest import _clinical_assertions_block as _clinical_assertions_block
from just_dna_compiler.compiler.manifest import _closure_warning as _closure_warning
from just_dna_compiler.compiler.manifest import _collect_logo as _collect_logo
from just_dna_compiler.compiler.manifest import _collect_logs as _collect_logs
from just_dna_compiler.compiler.manifest import _collect_provenance as _collect_provenance
from just_dna_compiler.compiler.manifest import _collect_readme as _collect_readme
from just_dna_compiler.compiler.manifest import _compiler_version as _compiler_version
from just_dna_compiler.compiler.manifest import _concordance_warnings as _concordance_warnings
from just_dna_compiler.compiler.manifest import _expression_effect_signature as _expression_effect_signature
from just_dna_compiler.compiler.manifest import _expression_effects_block as _expression_effects_block
from just_dna_compiler.compiler.manifest import _findings_warning as _findings_warning
from just_dna_compiler.compiler.manifest import _frequency_block as _frequency_block
from just_dna_compiler.compiler.manifest import _frequency_signature as _frequency_signature
from just_dna_compiler.compiler.manifest import _gene_metrics_block as _gene_metrics_block
from just_dna_compiler.compiler.manifest import _gene_metrics_signature as _gene_metrics_signature
from just_dna_compiler.compiler.manifest import _gene_validity_block as _gene_validity_block
from just_dna_compiler.compiler.manifest import _gene_validity_signature as _gene_validity_signature
from just_dna_compiler.compiler.manifest import _gwas_effect_signature as _gwas_effect_signature
from just_dna_compiler.compiler.manifest import _gwas_effects_block as _gwas_effects_block
from just_dna_compiler.compiler.manifest import _literature_block as _literature_block
from just_dna_compiler.compiler.manifest import _literature_signature as _literature_signature
from just_dna_compiler.compiler.manifest import _module_binding as _module_binding
from just_dna_compiler.compiler.manifest import _now_iso as _now_iso
from just_dna_compiler.compiler.manifest import _read_verification_block as _read_verification_block
from just_dna_compiler.compiler.manifest import _source_checks as _source_checks
from just_dna_compiler.compiler.manifest import _source_signature as _source_signature
from just_dna_compiler.compiler.manifest import _sources_block as _sources_block
from just_dna_compiler.compiler.manifest import _verification_block as _verification_block
from just_dna_compiler.compiler.manifest import build_disagreement_error as build_disagreement_error
from just_dna_compiler.compiler.manifest import module_stats as module_stats
from just_dna_compiler.compiler.manifest import variant_stats as variant_stats
from just_dna_compiler.compiler.parquets import _build_annotations as _build_annotations
from just_dna_compiler.compiler.parquets import _build_frequencies as _build_frequencies
from just_dna_compiler.compiler.parquets import _build_studies as _build_studies
from just_dna_compiler.compiler.parquets import _build_weights as _build_weights
from just_dna_compiler.compiler.pipeline import _resolution_signature as _resolution_signature
from just_dna_compiler.compiler.pipeline import close_module as close_module
from just_dna_compiler.compiler.pipeline import compile_module as compile_module
from just_dna_compiler.compiler.positional import _GENE_BEARING_TABLE_KINDS as _GENE_BEARING_TABLE_KINDS
from just_dna_compiler.compiler.positional import _POSITIONAL_TABLE_KINDS as _POSITIONAL_TABLE_KINDS
from just_dna_compiler.compiler.positional import UNJOINABLE_PHRASE as UNJOINABLE_PHRASE
from just_dna_compiler.compiler.positional import _apply_positional_resolution as _apply_positional_resolution
from just_dna_compiler.compiler.positional import (
    _check_positional_joinability as _check_positional_joinability,
)
from just_dna_compiler.compiler.positional import _table_row_key as _table_row_key
from just_dna_compiler.compiler.positional import positional_placement as positional_placement
from just_dna_compiler.compiler.reverse import _artifact_verification as _artifact_verification
from just_dna_compiler.compiler.reverse import (
    _authored_version_from_artifact as _authored_version_from_artifact,
)
from just_dna_compiler.compiler.reverse import _genome_build_from_artifact as _genome_build_from_artifact
from just_dna_compiler.compiler.reverse import _module_name_from_parquets as _module_name_from_parquets
from just_dna_compiler.compiler.reverse import _most_common as _most_common
from just_dna_compiler.compiler.reverse import _resolution_key as _resolution_key
from just_dna_compiler.compiler.reverse import _resolution_record as _resolution_record
from just_dna_compiler.compiler.reverse import _reverse_locus_index as _reverse_locus_index
from just_dna_compiler.compiler.reverse import _smallest_free as _smallest_free
from just_dna_compiler.compiler.reverse import _verification_loss_notice as _verification_loss_notice
from just_dna_compiler.compiler.reverse import _write_resolution_csv as _write_resolution_csv
from just_dna_compiler.compiler.reverse import _write_studies_csv as _write_studies_csv
from just_dna_compiler.compiler.reverse import _write_variants_csv as _write_variants_csv
from just_dna_compiler.compiler.reverse import logger as logger
from just_dna_compiler.compiler.reverse import reverse_module as reverse_module
from just_dna_compiler.compiler.table_checks import _IMPLIED_REFERENCE as _IMPLIED_REFERENCE
from just_dna_compiler.compiler.table_checks import _KNOWN_SPEC_FILES as _KNOWN_SPEC_FILES
from just_dna_compiler.compiler.table_checks import _REFERENCE_HAPLOTYPE as _REFERENCE_HAPLOTYPE
from just_dna_compiler.compiler.table_checks import _ROOT_NEAR_MISS_SUFFIXES as _ROOT_NEAR_MISS_SUFFIXES
from just_dna_compiler.compiler.table_checks import _check_misspelled_tables as _check_misspelled_tables
from just_dna_compiler.compiler.table_checks import (
    _cross_validate_haplotype_definitions as _cross_validate_haplotype_definitions,
)
from just_dna_compiler.compiler.table_checks import (
    _cross_validate_phase_ambiguity as _cross_validate_phase_ambiguity,
)
from just_dna_compiler.compiler.table_checks import _cross_validate_studies as _cross_validate_studies
from just_dna_compiler.compiler.table_checks import _examples as _examples
from just_dna_compiler.compiler.table_checks import _unphased_signature as _unphased_signature
from just_dna_compiler.compiler.table_checks import _validate_table_kind as _validate_table_kind
from just_dna_compiler.compiler.tables import _DERIVED_FILES as _DERIVED_FILES
from just_dna_compiler.compiler.tables import _FACT_TABLES as _FACT_TABLES
from just_dna_compiler.compiler.tables import _INPUT_FILES as _INPUT_FILES
from just_dna_compiler.compiler.tables import _PROVENANCE_FILE as _PROVENANCE_FILE
from just_dna_compiler.compiler.tables import _TABLE_DUPE_KEYS as _TABLE_DUPE_KEYS
from just_dna_compiler.compiler.tables import _TABLE_KIND_CSVS as _TABLE_KIND_CSVS
from just_dna_compiler.compiler.tables import _TABLE_KINDS as _TABLE_KINDS
from just_dna_compiler.compiler.tables import ARTIFACT_PARQUETS as ARTIFACT_PARQUETS
from just_dna_compiler.compiler.tables import BA1_ALLELE_FREQUENCY_THRESHOLD as BA1_ALLELE_FREQUENCY_THRESHOLD
from just_dna_compiler.compiler.tables import LEAD_PARQUETS as LEAD_PARQUETS
from just_dna_compiler.compiler.tables import OVERRIDES_CSV as OVERRIDES_CSV
from just_dna_compiler.compiler.tables import OVERRIDES_PARQUET as OVERRIDES_PARQUET
from just_dna_compiler.compiler.tables import SNP_CORE_PARQUETS as SNP_CORE_PARQUETS
from just_dna_compiler.compiler.tables import _build_table as _build_table
from just_dna_compiler.compiler.tables import _key_of as _key_of
from just_dna_compiler.compiler.tables import _list_cell as _list_cell
from just_dna_compiler.compiler.tables import _list_fields as _list_fields
from just_dna_compiler.compiler.tables import _locate_sidecar as _locate_sidecar
from just_dna_compiler.compiler.tables import _polars_type as _polars_type
from just_dna_compiler.compiler.tables import _scalar_cell as _scalar_cell
from just_dna_compiler.compiler.tables import _split_genotype as _split_genotype
from just_dna_compiler.compiler.tables import _strip_optional as _strip_optional
from just_dna_compiler.compiler.tables import _write_table_csv as _write_table_csv
from just_dna_compiler.compiler.tables import authored_input_entries as authored_input_entries
from just_dna_compiler.compiler.tables import pl as pl
from just_dna_compiler.compiler.tables import table_bindings as table_bindings
from just_dna_compiler.compiler.validate import _GENE_LIST_SEPARATORS as _GENE_LIST_SEPARATORS
from just_dna_compiler.compiler.validate import _check_composite_gene_cells as _check_composite_gene_cells
from just_dna_compiler.compiler.validate import _overlay_targets_missing as _overlay_targets_missing
from just_dna_compiler.compiler.validate import _validate_spec as _validate_spec
from just_dna_compiler.compiler.validate import load_overlay as load_overlay
from just_dna_compiler.compiler.validate import validate_spec as validate_spec
from just_dna_compiler.compiler.variant_checks import _build_remedy as _build_remedy
from just_dna_compiler.compiler.variant_checks import _check_build_coordinates as _check_build_coordinates
from just_dna_compiler.compiler.variant_checks import _check_contig_ploidy as _check_contig_ploidy
from just_dna_compiler.compiler.variant_checks import _coordinate_label as _coordinate_label
from just_dna_compiler.compiler.variant_checks import _CoordinateTable as _CoordinateTable
from just_dna_compiler.compiler.variant_checks import _cross_validate_variants as _cross_validate_variants
from just_dna_compiler.compiler.variant_checks import _restamp_for_build as _restamp_for_build
from just_dna_compiler.compiler.vcf_checks import _ALTS_BEARING_KINDS as _ALTS_BEARING_KINDS
from just_dna_compiler.compiler.vcf_checks import _INVERTING_QUALITY_FIELD as _INVERTING_QUALITY_FIELD
from just_dna_compiler.compiler.vcf_checks import MISSING_ALLELE_PHRASE as MISSING_ALLELE_PHRASE
from just_dna_compiler.compiler.vcf_checks import QUAL_INVERSION_PHRASE as QUAL_INVERSION_PHRASE
from just_dna_compiler.compiler.vcf_checks import _check_missing_allele_marker as _check_missing_allele_marker
from just_dna_compiler.compiler.vcf_checks import _check_quality_inversion as _check_quality_inversion
from just_dna_compiler.compiler.vcf_checks import _check_vcf_pointers as _check_vcf_pointers
from just_dna_compiler.compiler.vcf_checks import _quality_fields as _quality_fields
from just_dna_compiler.compiler.vrs_checks import _BLAME_ROW as _BLAME_ROW
from just_dna_compiler.compiler.vrs_checks import _BLAME_TIER as _BLAME_TIER
from just_dna_compiler.compiler.vrs_checks import _SYMBOLIC_GAP_REASON as _SYMBOLIC_GAP_REASON
from just_dna_compiler.compiler.vrs_checks import _UNOBSERVABLE_GAP_REASON as _UNOBSERVABLE_GAP_REASON
from just_dna_compiler.compiler.vrs_checks import _VRS_CARRIED_EXAMPLES as _VRS_CARRIED_EXAMPLES
from just_dna_compiler.compiler.vrs_checks import _carried_vrs_warnings as _carried_vrs_warnings
from just_dna_compiler.compiler.vrs_checks import _recompute_vrs_id as _recompute_vrs_id
from just_dna_compiler.compiler.vrs_checks import _verify_vrs_ids as _verify_vrs_ids
from just_dna_compiler.compiler.vrs_checks import _vrs_coverage as _vrs_coverage
from just_dna_compiler.compiler.vrs_checks import _vrs_coverage_warnings as _vrs_coverage_warnings
from just_dna_compiler.compiler.vrs_checks import _vrs_gap_reason as _vrs_gap_reason
from just_dna_compiler.ladder import LadderFinding as LadderFinding
from just_dna_compiler.ladder import route as route
from just_dna_compiler.models import ClosureResult as ClosureResult
from just_dna_compiler.models import CompilationResult as CompilationResult
from just_dna_compiler.models import ValidationResult as ValidationResult
from just_dna_compiler.resolution import ambiguous_refusals as ambiguous_refusals
from just_dna_compiler.resolution import hosting_verdict as hosting_verdict
from just_dna_compiler.resolution import resolve_from_table as resolve_from_table
from just_dna_compiler.resolution import resolve_positional_rows as resolve_positional_rows
from just_dna_compiler.resolution import unresolved_subjects as unresolved_subjects
from just_dna_compiler.resolution import withdrawn_refusals as withdrawn_refusals
from just_dna_compiler.resolution_findings import resolution_not_injected as resolution_not_injected
from just_dna_compiler.resolution_findings import skipped_cross_build as skipped_cross_build
from just_dna_compiler.resolution_findings import unresolved_rsid as unresolved_rsid
