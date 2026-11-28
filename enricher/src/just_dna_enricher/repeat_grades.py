"""Fill repeat_grades.csv with the catalogue's own locus–disease evidence (RM294)."""

import csv
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.layout import atomic_writer, nothing_to_write
from just_dna_format.normalize import now_utc_iso
from just_dna_format.repeat_grades import RepeatGradeRow, repeat_key
from just_dna_format.spelling import comparison_key

from just_dna_enricher.download import ensure_strchive_snapshot
from just_dna_enricher.licensing import (
    STRCHIVE_TERMS,
    TERMS_BY_SOURCE,
    record_table_sources,
    require_sources_file,
    sidecar_path,
    table_datasets,
    table_release,
)
from just_dna_enricher.locations import resolve_strchive_reference
from just_dna_enricher.strchive import (
    REPEAT_ALLELES_CSV,
    StrchiveCatalogue,
    StrchiveError,
    load_repeat_alleles,
    load_strchive_catalogue,
)
from just_dna_enricher.transaction import spec_lock

type RepeatKey = tuple[str, str]
REPEAT_GRADES_CSV = "repeat_grades.csv"


class RepeatGradeError(RuntimeError):
    """The pass could not read or commit the module's own tables."""


def _row_key(row: RepeatGradeRow) -> tuple:
    """A grade row's identity: its declared key fields, each compared as its column is (`gene_key` for a gene)."""
    return tuple(comparison_key(name, getattr(row, name)) for name in RepeatGradeRow._KEY_FIELDS)


@dataclass
class RepeatGradeResult:
    """The grade table proposed for commit and the outcome for each authored repeat key."""

    rows: list[RepeatGradeRow] = field(default_factory=list)
    covered: list[RepeatKey] = field(default_factory=list)
    missing: list[RepeatKey] = field(default_factory=list)
    could_not_ask: list[RepeatKey] = field(default_factory=list)
    reason: str | None = None
    added: int = 0

    contested: list[RepeatKey] = field(default_factory=list)
    answered_every_row: bool = False
    _changed: bool = False

    @property
    def subjects(self) -> int:
        return len(self.covered) + len(self.missing) + len(self.could_not_ask)

    def _commit(self, spec_dir: Path) -> None:
        """Publish the merged rows under the run's lock, after its strict checks."""
        path = sidecar_path(spec_dir, REPEAT_GRADES_CSV, error=RepeatGradeError)
        if nothing_to_write(path, self.rows) or not (self.covered or self.missing):
            return
        terms = require_sources_file(spec_dir, error=RepeatGradeError)
        releases = table_datasets(self.rows, release=lambda row: row.dataset)
        if not self._changed:
            expected = {
                source: table_release(labels)
                for source, labels in releases.items()
                if source in TERMS_BY_SOURCE
            }
            recorded = {
                row.source: row.dataset
                for row in terms
                if row.layer == "repeat_grade"
                and row.source in TERMS_BY_SOURCE
                and (self.answered_every_row or row.source in expected)
            }
            if recorded == expected:
                return
        with atomic_writer(
            path,
            newline="",
            before_commit=lambda: record_table_sources(
                releases,
                "repeat_grade",
                spec_dir,
                error=RepeatGradeError,
                answered_every_row=self.answered_every_row,
            ),
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(RepeatGradeRow.model_fields))
            writer.writeheader()
            writer.writerows(row.model_dump() for row in self.rows)


def enrich_repeat_grades(
    spec_dir: Path,
    *,
    catalogue: Path | None = None,
    offline: bool = False,
    download: bool = True,
    write: bool = True,
    rederive: bool = False,
    progress: Callable[[int, int], None] | None = None,
) -> RepeatGradeResult:
    """Refresh each answered repeat from the catalogue, preserving its first authored spelling.

    A routine run retains the timestamp of an identical answer. A full re-derivation stamps the
    new observation even when STRchive still gives the same answer.
    """
    spec_dir = Path(spec_dir)
    with spec_lock(spec_dir, enabled=write, error=RepeatGradeError):
        result = RepeatGradeResult()
        try:
            repeats = load_repeat_alleles(spec_dir)
        except (StrchiveError, OSError, UnicodeError, csv.Error) as exc:
            result.reason = f"Could not read subjects from {REPEAT_ALLELES_CSV}: {exc}"
            return result
        spellings: dict[RepeatKey, RepeatKey] = {}
        for repeat in repeats:
            spellings.setdefault(repeat_key(repeat), (repeat.gene, repeat.repeat_unit))
        keys = sorted(spellings)
        if progress is not None:
            progress(0, len(keys))
        if not keys:
            return result
        path = sidecar_path(spec_dir, REPEAT_GRADES_CSV, error=RepeatGradeError)
        if write:
            require_sources_file(spec_dir, error=RepeatGradeError)
        if path.exists():
            result.rows, errors, _ = load_csv_rows(path, RepeatGradeRow, path.name)
            if errors:
                raise RepeatGradeError(f"existing {path.name} is invalid: {errors[0]}")
        loaded: StrchiveCatalogue | None = None
        try:
            reference = catalogue or resolve_strchive_reference()
            if reference is None and download and not offline:
                reference = ensure_strchive_snapshot()
            if reference is not None:
                loaded = load_strchive_catalogue(reference)
        except (OSError, StrchiveError) as exc:
            result.reason = str(exc)

        if loaded is None:
            result.reason = result.reason or "no local STRchive snapshot"
            result.could_not_ask = [spellings[key] for key in keys]
            if progress is not None:
                progress(len(keys), len(keys))
            return result

        index = loaded.by_gene_and_motif(comparison_keys=True)
        previous = result.rows
        by_key = {_row_key(row): row for row in previous}
        # The module is authoritative about its subjects. A sidecar row outside this roster
        # belongs to the compiler's orphan check and has no fresh catalogue answer here.
        carried = [row for row in previous if repeat_key(row) not in spellings]
        result.answered_every_row = not carried
        fresh: dict[tuple, RepeatGradeRow] = {}
        fetched_at = now_utc_iso()
        for done, key in enumerate(keys, 1):
            loci = index.get(key, [])
            subject = spellings[key]
            if loci:
                result.covered.append(subject)
                if len({locus.locus_id for locus in loci}) > 1:
                    result.contested.append(subject)
            else:
                result.missing.append(subject)
            for locus in sorted(loci, key=lambda item: item.locus_id):
                for grade in locus.evidence or (None,):
                    row = RepeatGradeRow(
                        gene=subject[0],
                        repeat_unit=subject[1],
                        locus_id=locus.locus_id,
                        grade=grade,
                        disease=locus.disease,
                        dataset=loaded.dataset,
                        source=STRCHIVE_TERMS.source,
                        status="resolved",
                        fetched_at=fetched_at,
                    )
                    identity = _row_key(row)
                    old = by_key.get(identity)
                    if (
                        old is not None
                        and not rederive
                        and row.model_copy(update={"fetched_at": old.fetched_at}) == old
                    ):
                        row = old
                    fresh.setdefault(identity, row)
            if progress is not None:
                progress(done, len(keys))
        result.added = len(fresh.keys() - by_key.keys())
        result.rows = [*carried, *fresh.values()]
        result._changed = result.rows != previous
        if write:
            result._commit(spec_dir)
        return result
