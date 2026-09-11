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

import logging
from dataclasses import dataclass

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
