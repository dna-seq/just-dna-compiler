"""Fill repeat_grades.csv with the catalogue's own locus–disease evidence (RM294)."""

import csv
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.base import merge_key
from just_dna_format.layout import atomic_writer, nothing_to_write
from just_dna_format.normalize import now_utc_iso
from just_dna_format.repeat_grades import RepeatGradeRow, repeat_key

from just_dna_enricher.download import ensure_strchive_snapshot
from just_dna_enricher.licensing import (
    STRCHIVE_TERMS,
    record_table_sources,
    require_sources_file,
    sidecar_path,
    table_datasets,
)
from just_dna_enricher.locations import resolve_strchive_reference
from just_dna_enricher.strchive import (
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


@dataclass
class RepeatGradeResult:
    rows: list[RepeatGradeRow] = field(default_factory=list)
    covered: list[RepeatKey] = field(default_factory=list)
    missing: list[RepeatKey] = field(default_factory=list)
    could_not_ask: list[RepeatKey] = field(default_factory=list)
    reason: str | None = None
    added: int = 0

    @property
    def subjects(self) -> int:
        return len(self.covered) + len(self.missing) + len(self.could_not_ask)

    def _commit(self, spec_dir: Path) -> None:
        """Publish the merged rows under the run's lock, after its strict checks."""
        path = sidecar_path(spec_dir, REPEAT_GRADES_CSV, error=RepeatGradeError)
        if nothing_to_write(path, self.rows) or not self.added:
            return
        require_sources_file(spec_dir, error=RepeatGradeError)
        with atomic_writer(
            path,
            newline="",
            before_commit=lambda: record_table_sources(
                table_datasets(self.rows, release=lambda row: row.dataset),
                "repeat_grade",
                spec_dir,
                error=RepeatGradeError,
                answered_every_row=False,
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
    progress: Callable[[int, int], None] | None = None,
) -> RepeatGradeResult:
    """Merge all matches by their full fact key. An unreachable catalogue leaves the table alone."""
    spec_dir = Path(spec_dir)
    with spec_lock(spec_dir, enabled=write, error=RepeatGradeError):
        try:
            keys = sorted({repeat_key(row) for row in load_repeat_alleles(spec_dir)})
        except StrchiveError as exc:
            raise RepeatGradeError(str(exc)) from exc
        result = RepeatGradeResult()
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
            result.could_not_ask = keys
            if progress is not None:
                progress(len(keys), len(keys))
            return result

        index = loaded.by_gene_and_motif()
        seen = {merge_key(row) for row in result.rows}
        fetched_at = now_utc_iso()
        for done, key in enumerate(keys, 1):
            loci = index.get(key, [])
            if loci:
                result.covered.append(key)
            else:
                result.missing.append(key)
            for locus in sorted(loci, key=lambda item: item.locus_id):
                for grade in locus.evidence or (None,):
                    row = RepeatGradeRow(
                        gene=key[0],
                        repeat_unit=key[1],
                        locus_id=locus.locus_id,
                        grade=grade,
                        disease=locus.disease,
                        dataset=loaded.dataset,
                        source=STRCHIVE_TERMS.source,
                        status="resolved",
                        fetched_at=fetched_at,
                    )
                    identity = merge_key(row)
                    if identity not in seen:
                        seen.add(identity)
                        result.rows.append(row)
                        result.added += 1
            if progress is not None:
                progress(done, len(keys))
        if write:
            result._commit(spec_dir)
        return result
