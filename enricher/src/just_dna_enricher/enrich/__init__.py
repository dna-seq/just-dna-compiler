"""`enrich` — fill the source-independent resolution table for a module spec, then hand off to compile.

The resolver chain, first-hit-wins: an existing/human-authored row (authoritative, never clobbered) →
the local cache (a downloaded snapshot, offline) → live Ensembl (V2 GraphQL → V1 REST). It writes
`resolution.csv` beside the spec; the compiler then consumes it with no source knowledge and no
network. Two modes: `best_effort` fills what it can and records the rest as `not_found`; `strict`
fails unless every in-scope variant resolves to a position (the network analogue of the compiler's
`strict=True`). `--offline` clamps the chain to the cache alone (guaranteed zero egress).

RM260: this `__init__` is the re-export shell that keeps every dotted path into the old single-file
`enrich.py` resolving to the same object. The code lives in the submodules beside it — `subjects`,
`outcome`, `build_declaration`, `orchestration`, `verification_records`, `resolution_csv` — and
those import one another directly, never through this shell. The shell is removed at 1.0.
"""

import csv as csv
import logging as logging
from collections.abc import Callable as Callable
from collections.abc import Collection as Collection
from collections.abc import Mapping as Mapping
from collections.abc import Sequence as Sequence
from dataclasses import dataclass as dataclass
from dataclasses import field as field
from pathlib import Path as Path
from typing import Optional as Optional

import yaml as yaml
from just_dna_compiler.compiler import SpecError as SpecError
from just_dna_compiler.compiler import _restamp_for_build as _restamp_for_build
from just_dna_compiler.compiler import load_csv_rows as load_csv_rows
from just_dna_compiler.compiler import load_spec as load_spec
from just_dna_compiler.resolution import contradiction_reason as contradiction_reason
from just_dna_compiler.resolution import hosting_verdict as hosting_verdict
from just_dna_compiler.resolution import undecided_reason as undecided_reason
from just_dna_format.alleles import strand_flip_explains as strand_flip_explains
from just_dna_format.base import derive_variant_key as derive_variant_key
from just_dna_format.base import merge_key as merge_key
from just_dna_format.binning import HeteroplasmyRow as HeteroplasmyRow
from just_dna_format.layout import atomic_writer as atomic_writer
from just_dna_format.manifest import VerificationRecord as VerificationRecord
from just_dna_format.normalize import now_utc_iso as now_utc_iso
from just_dna_format.pgx import HaplotypeRow as HaplotypeRow
from just_dna_format.pgx import PharmVariantRow as PharmVariantRow
from just_dna_format.resolution import RESOLUTION_FACT_FIELDS as RESOLUTION_FACT_FIELDS
from just_dna_format.resolution import ResolutionRow as ResolutionRow
from just_dna_format.spec import ModuleSpecConfig as ModuleSpecConfig
from just_dna_format.spec import VariantRow as VariantRow
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER as TEMPLATE_PLACEHOLDER
from just_dna_format.vrs import normalize_chrom as normalize_chrom
from just_dna_format.vrs import par_partner as par_partner
from pydantic import ValidationError as ValidationError

from just_dna_enricher import clinvar as clinvar
from just_dna_enricher.civic_citations import EvidenceStatusCheck as EvidenceStatusCheck
from just_dna_enricher.civic_citations import check_evidence_status_currency as check_evidence_status_currency
from just_dna_enricher.civic_citations import read_studies as read_studies
from just_dna_enricher.civic_refutation import REFUTATION_BESIDE_CLAIM as REFUTATION_BESIDE_CLAIM
from just_dna_enricher.civic_refutation import REFUTATION_WITHOUT_CLAIM as REFUTATION_WITHOUT_CLAIM
from just_dna_enricher.civic_refutation import RefutationFinding as RefutationFinding
from just_dna_enricher.civic_refutation import compare_refutations as compare_refutations
from just_dna_enricher.clinical import ClinSigComparison as ClinSigComparison
from just_dna_enricher.clinical import ClinSigConflict as ClinSigConflict
from just_dna_enricher.clinical import ConcordanceRecord as ConcordanceRecord
from just_dna_enricher.clinical import answered_call_shift as answered_call_shift
from just_dna_enricher.clinical import clin_sig_concordance as clin_sig_concordance
from just_dna_enricher.clinical import compare_clin_sig as compare_clin_sig
from just_dna_enricher.clinical import concordance_notes as concordance_notes
from just_dna_enricher.clinical import concordance_sentences as concordance_sentences
from just_dna_enricher.clinical import tautology_reason as tautology_reason
from just_dna_enricher.clinvar import clinvar_dataset_label as clinvar_dataset_label
from just_dna_enricher.concordance import AnsweredCallReport as AnsweredCallReport
from just_dna_enricher.concordance import answered_call_notes as answered_call_notes
from just_dna_enricher.concordance import answered_call_sentences as answered_call_sentences
from just_dna_enricher.concordance import write_concordance_tables as write_concordance_tables
from just_dna_enricher.currency import CurrencyCheck as CurrencyCheck
from just_dna_enricher.currency import ReleaseProbe as ReleaseProbe
from just_dna_enricher.currency import check_dataset_currency as check_dataset_currency
from just_dna_enricher.currency import summarize_currency as summarize_currency
from just_dna_enricher.currency import unchecked_sentences as unchecked_sentences
from just_dna_enricher.download import ensure_clinvar_snapshot as ensure_clinvar_snapshot
from just_dna_enricher.download import ensure_snapshot as ensure_snapshot
from just_dna_enricher.enrich.build_declaration import (
    _declared_build_behind_placeholders as _declared_build_behind_placeholders,
)
from just_dna_enricher.enrich.build_declaration import _fill_placeholders as _fill_placeholders
from just_dna_enricher.enrich.build_declaration import source_build_mismatch as source_build_mismatch
from just_dna_enricher.enrich.build_declaration import spec_genome_build as spec_genome_build
from just_dna_enricher.enrich.orchestration import _run_enrichment as _run_enrichment
from just_dna_enricher.enrich.orchestration import enrich as enrich
from just_dna_enricher.enrich.orchestration import logger as logger
from just_dna_enricher.enrich.outcome import EnrichmentError as EnrichmentError
from just_dna_enricher.enrich.outcome import EnrichmentResult as EnrichmentResult
from just_dna_enricher.enrich.outcome import SubjectDrift as SubjectDrift
from just_dna_enricher.enrich.outcome import _rederived_drift as _rederived_drift
from just_dna_enricher.enrich.outcome import _render_facts as _render_facts
from just_dna_enricher.enrich.outcome import _subject_key as _subject_key
from just_dna_enricher.enrich.resolution_csv import _FIELDNAMES as _FIELDNAMES
from just_dna_enricher.enrich.resolution_csv import _resolution_cell as _resolution_cell
from just_dna_enricher.enrich.resolution_csv import _write_resolution_csv as _write_resolution_csv
from just_dna_enricher.enrich.subjects import AbstractSet as AbstractSet
from just_dna_enricher.enrich.subjects import Subject as Subject
from just_dna_enricher.enrich.subjects import _authored_alt as _authored_alt
from just_dna_enricher.enrich.subjects import _check_authored_pairs as _check_authored_pairs
from just_dna_enricher.enrich.subjects import _locus_alleles as _locus_alleles
from just_dna_enricher.enrich.subjects import _subject_of_variant as _subject_of_variant
from just_dna_enricher.enrich.subjects import collect_subjects as collect_subjects
from just_dna_enricher.enrich.subjects import select_par_representative as select_par_representative
from just_dna_enricher.enrich.verification_records import _civic_release as _civic_release
from just_dna_enricher.enrich.verification_records import _clin_sig_detail as _clin_sig_detail
from just_dna_enricher.enrich.verification_records import _clinvar_release as _clinvar_release
from just_dna_enricher.enrich.verification_records import _refutation_detail as _refutation_detail
from just_dna_enricher.enrich.verification_records import _snapshot_release as _snapshot_release
from just_dna_enricher.enrich.verification_records import _verification_records as _verification_records
from just_dna_enricher.ensembl import EnsemblResolver as EnsemblResolver
from just_dna_enricher.gnomad import GnomadClient as GnomadClient
from just_dna_enricher.gnomad import GnomadError as GnomadError
from just_dna_enricher.grch37 import BuildDiagnosis as BuildDiagnosis
from just_dna_enricher.grch37 import BuildDiagnosisResult as BuildDiagnosisResult
from just_dna_enricher.grch37 import Grch37Client as Grch37Client
from just_dna_enricher.grch37 import diagnose_wrong_build as diagnose_wrong_build
from just_dna_enricher.grch37 import summarize_build_diagnoses as summarize_build_diagnoses
from just_dna_enricher.identifiers import IdentifierUnavailable as IdentifierUnavailable
from just_dna_enricher.identifiers import RsidStatus as RsidStatus
from just_dna_enricher.identifiers import check_rsids as check_rsids
from just_dna_enricher.licensing import overlay_answers as overlay_answers
from just_dna_enricher.licensing import read_sources_file as read_sources_file
from just_dna_enricher.licensing import record_source_terms as record_source_terms
from just_dna_enricher.licensing import require_sources_file as require_sources_file
from just_dna_enricher.licensing import resolution_authority as resolution_authority
from just_dna_enricher.licensing import sidecar_path as sidecar_path
from just_dna_enricher.locations import read_release as read_release
from just_dna_enricher.locations import resolve_civic_reference as resolve_civic_reference
from just_dna_enricher.locations import resolve_clinvar_reference as resolve_clinvar_reference
from just_dna_enricher.locations import resolve_ensembl_reference as resolve_ensembl_reference
from just_dna_enricher.locations import resolve_pubmind_reference as resolve_pubmind_reference
from just_dna_enricher.resolver import AlleleMismatch as AlleleMismatch
from just_dna_enricher.resolver import PairCheck as PairCheck
from just_dna_enricher.resolver import check_rsid_coordinates as check_rsid_coordinates
from just_dna_enricher.resolver import lookup_loci as lookup_loci
from just_dna_enricher.sequences import RefCheck as RefCheck
from just_dna_enricher.sequences import RefMismatch as RefMismatch
from just_dna_enricher.sequences import SequenceProxy as SequenceProxy
from just_dna_enricher.sequences import summarize_ref_mismatches as summarize_ref_mismatches
from just_dna_enricher.sequences import verify_reference_alleles as verify_reference_alleles
from just_dna_enricher.transaction import ResolutionJournal as ResolutionJournal
from just_dna_enricher.transaction import SubjectProgress as SubjectProgress
from just_dna_enricher.transaction import spec_lock as spec_lock
from just_dna_enricher.verification import DETAIL_LIMIT as DETAIL_LIMIT
from just_dna_enricher.verification import examples as examples
from just_dna_enricher.verification import ran as ran
from just_dna_enricher.verification import record_verification as record_verification
from just_dna_enricher.verification import skipped as skipped
from just_dna_enricher.vrs import MintResult as MintResult
from just_dna_enricher.vrs import VrsMinter as VrsMinter
from just_dna_enricher.vrs import mint_resolution_rows as mint_resolution_rows
