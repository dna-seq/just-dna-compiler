"""What every command module shares: the root `app`, the mode/`--use` spellings, and the two helpers
more than one command group calls (RM260 split this out of the former single-file `cli.py`).
"""

from pathlib import Path

import typer
from just_dna_compiler.draft import DraftError
from just_dna_format.manifest import VerificationRecord
from just_dna_format.vocab import VALID_DECLARED_USE, match_vocab

from just_dna_enricher.enrich import EnrichmentError
from just_dna_enricher.verification import record_verification

app = typer.Typer(
    add_completion=False,
    help="Fill the source-independent resolution table (cache + live Ensembl) the compiler consumes.",
    no_args_is_help=True,
)


#: What a drafting command must catch beyond its own source's error, and **why it is a named tuple
#: rather than two more entries in two `except` clauses** (R2-2).
#:
#: Every provider that writes a coordinate asks `enrich.source_build_mismatch` before it writes (F1),
#: and that function raises `EnrichmentError` on a present-but-unreadable `module_spec.yaml` —
#: deliberately, because picking a build for a module whose declaration cannot be read is the
#: invention it exists to remove. Neither CLI caught it: `draft` caught `(CpicError, DraftError)` and
#: `draft-panel` caught `(ClinVarDraftError, DraftError)`, so a spec carrying only `name:` — an
#: ordinary mid-authoring state — turned `draft-panel --gene PALB2 --offline` into a rich traceback
#: where every other enricher command exits cleanly. The presentation regressed *because* the build
#: defect was fixed, which is the shape worth naming: a shared precondition added to three providers
#: owes the same addition to each of their handlers, and a tuple makes the fourth provider inherit it
#: instead of rediscovering it.
_DRAFT_PRECONDITION_ERRORS: tuple[type[Exception], ...] = (DraftError, EnrichmentError)


def _mode(strict: bool) -> str:
    return "strict" if strict else "best_effort"


def _use(value: str) -> str:
    """Normalize the `--use` spelling to the `VALID_DECLARED_USE` member.

    A three-state string rather than a `--commercial/--non-commercial` bool pair: a bool cannot
    express the default, and defaulting either way would have the tool assert a purpose on the
    user's behalf. `unstated` is the honest default.

    The separator normalization moved onto `vocab.match_vocab`, which every closed vocabulary now
    shares. This private copy was the whole reason `--use non-commercial` worked while the identical
    string in an authored cell was refused: the flag taught a spelling the file rejected. What stays
    here is the case-folding and the `--use`-specific message — the flag is the CLI's, the vocabulary
    is the schema's.
    """
    matched = match_vocab(value.strip().lower(), VALID_DECLARED_USE)
    if matched is None:
        raise typer.BadParameter(f"--use must be one of {sorted(VALID_DECLARED_USE)}, got: {value!r}")
    return matched


def _attest_on_the_way_out(records: list[VerificationRecord], spec_dir: Path) -> None:
    """Attest on the way out of a failed run, and report rather than raise if that fails too.

    Used by the two check commands' failure paths only. The command is already exiting 1 with the
    reason the source could not be read, and replacing that sentence with a layout or filesystem
    complaint would tell the author about the wrong problem. `vrs mint`'s "BUT NOT ATTESTED" message
    exists because *there* the run succeeded and only the record failed; here both went wrong and the
    first one is the one to say. `OSError` is caught beside the caller's own error because
    `record_verification` translates only a sidecar collision — a read-only spec directory reaches
    here as an `OSError` and would otherwise replace the message this exists to protect.
    """
    try:
        record_verification(records, spec_dir, error=EnrichmentError)
    except (EnrichmentError, OSError) as exc:
        typer.secho(f"  (not attested either: {exc})", fg=typer.colors.YELLOW, err=True)
