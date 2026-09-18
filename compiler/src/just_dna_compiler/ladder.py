"""The mode ladder, as one mechanism (RM246).

**What the ladder is.** A check whose severity is the compile mode: it reports under `best_effort` and
refuses under `strict`. Every such check answers two questions — *which channel does this go in* and
*what does it say there* — and before this module the codebase answered them in three unrelated shapes,
which is why the ladder read as one thing and behaved as three:

* `(errors if strict else warnings_out).append(finding)` — one sentence, two channels. Four codes.
* `if strict:` with the same messages moved into `errors` and a **side effect suppressed** — the
  symbolic-allele drop, where `best_effort` drops the unusable rows and `strict` refuses instead of
  dropping. Same text, and a behaviour difference the channel does not carry.
* `ResolutionOutcome.strict_errors` — a warning **paired with a different, longer refusal**. Three
  findings. Calling these ladder members and quoting the warning's words describes a compile that
  succeeds; quoting the refusal's words quotes a sentence `best_effort` never emits.

The third is the general case and the first two are its degenerate form, which is the whole content of
this module: **a ladder finding carries what `best_effort` says and, optionally, a different thing
`strict` says.** `refusal=None` means *the same sentence, the other channel*, and that is a claim worth
being explicit about rather than a shape one has to infer from which spelling a function happened to use.

**What is deliberately NOT here.** What the compile *does* with an error — accumulate and keep checking,
or abort with a `"strict resolution: "` prefix and a failed result — is the caller's policy, not the
ladder's. `compile_module` returns immediately on a refused resolution because a module whose identities
cannot be reproduced has nothing further worth checking; it accumulates the allele-membership refusals
because those are per-row and an author wants all of them. Folding that into `route` would make one
decision out of two that are made for different reasons.
"""

from dataclasses import dataclass

from just_dna_format.findings import CodedWarning


@dataclass(frozen=True)
class LadderFinding:
    """One finding whose severity is the mode.

    `warning` is what `best_effort` emits, code and all. `refusal` is what `strict` says **instead** —
    `None` where the two modes say the same thing, which is the common case and reads as one.

    A refusal is a bare `str` rather than a second `CodedWarning` on purpose: a code classifies a
    *warning* channel a consumer filters, and an error is already fatal, so a code there would be a
    second vocabulary over a set with one member. The warning's code is the finding's identity in both
    modes, and `route` is what keeps them from drifting apart.
    """

    warning: CodedWarning
    refusal: str | None = None

    def text(self, *, strict: bool) -> str:
        """What this finding says in `strict`, or in `best_effort`."""
        return (self.refusal or self.warning) if strict else self.warning


def route(findings: list[LadderFinding], *, strict: bool) -> tuple[list[str], list[str]]:
    """`(errors, warnings)` — the one place the mode picks a channel and a sentence.

    Deliberately total and deliberately boring: every ladder check calls this, so the question *which
    checks escalate under strict* is answered by grepping one callee rather than by recognising three
    spellings. A check that wants to escalate and does not call this is visible to
    `schema/tests/test_feature_corpus.py`, which walks the construction sites and asserts the `@ladder`
    tag against them.
    """
    if strict:
        return [f.text(strict=True) for f in findings], []
    return [], [f.warning for f in findings]
