"""Draft provenance — telling a value still copied from a source from one a human has edited (RM73).

**The problem this closes.** A module's authored tables are flat CSV, and a row carries no record of
how it came to be. The three ways it can have arrived — hand-authored, drafted, drafted-then-edited —
have different verification status by construction, so every check that needs to know has guessed.
The sharpest instance is the tautology: a table drafted from ClinVar carries ClinVar's own
`clin_sig`, so cross-checking it compares a value against itself, and the resulting zero *looks like
evidence*. RM4 shipped a module-level skip keyed on the licence row's `dataset` because that was the
finest grain available, and named the hole it left — a single cell edited after the draft is no
longer a copy, and no module-level fact can see it.

**The mechanism: one digest per drafting source, over the projection the check actually reads.**
`(identity cells, checked cell)` for every row of the drafted table, sorted and hashed. A drafting
provider stamps it; the check recomputes it and compares. A match means no checked value has moved
since the drafter last wrote, so the comparison really is a value against itself and the skip is
sound rather than hopeful. Anything else and the check simply runs.

**Why the projection is a column and not a row.** A `clinvar_draft` module *always* has edited rows
by construction — `genotype` is a placeholder the human is required to fill — so a whole-row hash
would never match and the skip would never fire once. Scoping the hash to the column the check
compares makes it exactly as sensitive as the question being asked: filling a stub does not disturb
it, editing a `clin_sig` does.

**Raw CSV cells, never loaded models, and that is forced rather than stylistic.** One function serves
both sides, because a writer and a reader that computed this differently would not fail — they would
silently never match, which is the trap `clinvar.clinvar_dataset_label` was built to avoid. That
means the same code runs at *draft* time, when a freshly drafted `variants.csv` is full of
`<<REPLACE>>` and `vocab.reject_template_placeholders` refuses to load it at all (fatal by design).
So the projection reads `csv.DictReader` and compares text. The consequence is that `variant_key` and
`effective_clin_sig` are unavailable here, which is why the identity is spelled as the raw cells a
provider already matches on.

**Order-independent**, because a reorder changes no claim — the same reasoning that makes
`content_signature` order-independent. Missing columns render as the empty string rather than being
dropped, so a table gaining an optional column later does not silently re-key the rows it already
had.

**What this is not.** It is change-evidence, not tamper-proofing: nothing stops an author editing a
row and re-running the drafter. What it buys is that a copy can be *established* rather than assumed,
and the safe direction is the default — every unknown leaves the check running.
"""

import csv
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from just_dna_compiler.compiler import load_csv_rows
from just_dna_format.sources import SourceRow

from just_dna_enricher.licensing import sources_path, write_sources_csv

logger = logging.getLogger(__name__)

#: Field separator inside one projected row, and row separator between them. Control characters, so
#: no cell value can contain one and forge a row boundary.
_UNIT = "\x1f"
_RECORD = "\x1e"


@dataclass(frozen=True)
class DraftProjection:
    """Which table a source drafts, how its rows are identified, and which cells a check re-reads.

    The three travel together because they are one fact about one check, not three settings. `table`
    and `checked` say what the cross-check compares; `identity` says what stays put while a human
    finishes the row, which is precisely why filling a `genotype` stub does not invalidate the digest
    of a `clin_sig` projection.
    """

    table: str
    identity: tuple[str, ...]
    checked: tuple[str, ...]


#: Every source that both drafts rows and later cross-checks one of the columns it wrote.
#:
#: Three entries, and each is the definition of a check's subject rather than a restatement of
#: something already written down elsewhere — which is the line this repo draws around a hand-kept
#: map. `test_draft_provenance` asserts the set matches the providers that actually exist, so a
#: fourth cannot arrive silently.
#:
#: `clinpgx`'s identity is wide because `annotation_id` is optional and one variant+drug pair
#: legitimately carries several annotations separated only by `phenotype_category` — the bare triple
#: is a bug this package has already made once. An empty cell participates as the empty string rather
#: than being dropped, so a row naming no `annotation_id` still keys distinctly from its siblings.
DRAFT_PROJECTIONS: dict[str, DraftProjection] = {
    "clinvar": DraftProjection(
        table="variants.csv",
        # `clinvar_draft._MATCH_ON` — the cells that identify the variant regardless of how the
        # human later finishes the row.
        identity=("rsid", "chrom", "start", "ref", "alts"),
        checked=("clin_sig",),
    ),
    "cpic": DraftProjection(
        table="allele_function.csv",
        identity=("gene", "allele"),
        checked=("function_status",),
    ),
    "clinpgx": DraftProjection(
        table="pharm_variants.csv",
        identity=(
            "rsid", "chrom", "start", "ref",
            "drug", "genotype", "phenotype_category", "annotation_id",
        ),
        checked=("evidence_level",),
    ),
}


def draft_digest(spec_dir: Path, source: str) -> str | None:
    """Hash `source`'s drafted table as it stands on disk, or `None` when there is nothing to hash.

    `None` for a source that drafts nothing, for a table this module does not carry, and for one that
    carries no rows — all three are "no copy has been established", which is the state that leaves a
    check running.
    """
    projection = DRAFT_PROJECTIONS.get(source)
    if projection is None:
        return None
    path = Path(spec_dir) / projection.table
    if not path.exists() or path.stat().st_size == 0:
        return None

    columns = (*projection.identity, *projection.checked)
    with open(path, encoding="utf-8", newline="") as handle:
        # `(cell or "").strip()` for the same reason the compiler's loader normalizes: a trailing
        # space an editor left behind is not an edit to the claim, and treating it as one would
        # re-enable the full check for nothing.
        projected = sorted(
            _UNIT.join((row.get(name) or "").strip() for name in columns)
            for row in csv.DictReader(handle)
        )
    if not projected:
        return None
    payload = _RECORD.join(projected)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stamp_draft_digest(
    spec_dir: Path, source: str, layer: str, *, error: type[Exception]
) -> str | None:
    """Record the current digest onto the `(source, layer)` licence row. Returns what it wrote.

    **This exists because `merge_sources_file` is never-clobber**, which is right for terms a curator
    may have hand-written and wrong for a machine-stamped cell that must track the table. Without an
    explicit restamp a second draft's digest is silently dropped, the recorded one stays behind
    naming a table that has since grown, and the skip dies permanently — in the safe direction, and
    invisibly, which is what would make it a trap rather than a bug. `withdraw_stale_dataset` is the
    same lesson on the neighbouring column, and it is the precedent for overwriting here at all.

    Unlike `dataset`, this one **re-labels rather than withdraws**, and the difference is real: a
    release label cannot name two releases, so a module spanning two has no honest value and unknown
    is withheld. A digest has no such problem — it describes the table as it now stands, whatever
    mixture of releases and hands produced it, so recomputing is always the honest answer.

    Called unconditionally by a provider that wrote anything: a run that appended no row leaves the
    projection unchanged, so the restamp is a no-op rather than a special case to guard.
    """
    digest = draft_digest(spec_dir, source)
    path = sources_path(spec_dir, error=error)
    if not path.exists():
        return None
    rows, errors, _ = load_csv_rows(path, SourceRow, path.name)
    if errors:
        raise error(f"existing {path.name} is invalid: {errors[0]}")
    recorded = next((r for r in rows if r.source == source and r.layer == layer), None)
    if recorded is None or recorded.draft_digest == digest:
        return None
    recorded.draft_digest = digest
    write_sources_csv(rows, path)
    return digest


def drafted_unchanged(spec_dir: Path, source: str, sources: list[SourceRow]) -> bool | None:
    """Has every checked cell stayed as the drafter wrote it? Tri-state.

    * `None` — nothing recorded a digest for this source, so nothing was ever established. A module
      nobody drafted, one drafted before this shipped, or a table that has since been deleted.
    * `False` — a checked value has moved since the draft. The row stopped being a copy, whoever
      moved it, and the cross-check has something real to compare.
    * `True` — the projection still hashes to what the drafter recorded.

    `True` alone is **not** grounds to skip a check. The digest describes this module's table, not
    the source's release, so it is silent about currency: a matching digest against a *newer*
    snapshot is a genuine comparison, not a tautology. The caller conjoins this with the release
    check (`clinical.tautology_reason`'s existing rule) and skips only when both hold.
    """
    recorded = [
        row.draft_digest
        for row in sources
        if row.source == source and (row.draft_digest or "").strip()
    ]
    if not recorded:
        return None
    current = draft_digest(spec_dir, source)
    if current is None:
        # A digest was recorded and the table is now unreadable or gone. Not a match, and deliberately
        # not `None` either: something was established and no longer holds, which is exactly the case
        # a check should be run over rather than waved through.
        return False
    return all(value == current for value in recorded)
