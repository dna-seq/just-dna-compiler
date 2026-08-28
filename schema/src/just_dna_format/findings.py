"""A warning that knows what it is and whether an author can clear it (RM131).

`manifest.compilation.warnings` already ships and already carries every finding a compile made. What
it could not do was answer the two questions a reader of 14 kB of prose actually has — *what kind of
thing is this?* and *can I do anything about it?* — even though the compiler computes the second at
the point each finding is built and spends it on severity alone (`_BLAME_TIER`/`_BLAME_ROW`, whose
own comment says "blame decides severity and nothing else").

**The transport stays `list[str]`, deliberately.** `CodedWarning` is a `str` subclass, so every
`.extend`, every `if w not in all_warnings` de-duplication, every `"; ".join` and every consumer
already grepping a phrase keeps working untouched, and the published field keeps its exact type and
its exact text (`@warning-text-is-api`). What the subclass adds is a `code` the emission site names,
from which `carried` follows — and `classify` reads both back off a finished list.

**Pydantic strips the subclass at a model boundary**, which is a feature for serialization (the
manifest holds plain JSON strings) and a trap for anything that reads warnings back off a result
model and keeps building. So the rule is: classify *before* constructing the model, and hand the
classified list — not the model's `warnings` — to whatever compiles next.
"""

from collections.abc import Sequence

from just_dna_format.vocab import CARRIED_WARNING_CODES, VALID_WARNING_CODES


class CodedWarning(str):
    """One warning sentence, plus the code its emission site named it with.

    A `str` for every purpose but one: `.code` says which member of `VALID_WARNING_CODES` this is,
    and `.carried` says whether the author can clear it. Equality, hashing, `in` and formatting are
    the base class's, so a `CodedWarning` and the identical plain string are interchangeable everywhere
    the compiler already de-duplicates on the message.
    """

    __slots__ = ("code",)

    code: str

    def __new__(cls, code: str, message: str) -> "CodedWarning":
        if code not in VALID_WARNING_CODES:
            raise ValueError(
                f"{code!r} is not a warning code. A finding names one member of "
                f"VALID_WARNING_CODES, and the set is published, so a new kind of finding takes an "
                f"existing code where the remediation is the same and earns a new member where it "
                f"is not."
            )
        finding = super().__new__(cls, message)
        object.__setattr__(finding, "code", code)
        return finding

    @property
    def carried(self) -> bool:
        """Whether no edit to the spec directory can clear this — a property of the code alone."""
        return self.code in CARRIED_WARNING_CODES

    def restated(self, message: str) -> "CodedWarning":
        """The same finding under a new sentence — for a caller that prefixes a table name.

        Re-wrapping is the one operation that silently loses the code, because every other string
        operation on a `CodedWarning` returns a plain `str` by construction. A caller that reformats a
        message goes through here so the code travels with the text it belongs to.
        """
        return CodedWarning(self.code, message)


def restate(finding: str, message: str) -> CodedWarning:
    """`finding.restated(message)`, tolerating a plain `str` only by refusing it out loud.

    A reformatting site is exactly where a code goes missing, so this refuses rather than inventing
    one: the caller is holding something that never named its kind, and bucketing it here would
    reproduce the silently-partial summary the whole item exists to avoid.
    """
    if not isinstance(finding, CodedWarning):
        raise ValueError(
            f"cannot restate an unclassified warning: {finding[:80]!r}. The message being "
            f"reformatted was built without a warning code, so there is nothing to carry over — "
            f"give its emission site a member of VALID_WARNING_CODES."
        )
    return finding.restated(message)


def classify(warnings: Sequence[str]) -> tuple[list[str], dict[str, int]]:
    """`(carried, warnings_summary)` for a finished warning list.

    `carried` is the subset of `warnings` no edit to the spec directory can remove, in the order the
    findings appear, so a consumer subtracting it from `warnings` gets the actionable set and both
    lists read in the same order as the channel they came from. `warnings_summary` counts every
    finding by code, so `sum(summary.values()) == len(warnings)` always — a summary that does not
    account for the whole channel is one a reader would take as complete and be wrong about.

    **Refuses an unclassified member rather than bucketing it.** A `warnings_summary` with a
    catch-all key is the rejected repair wearing a different hat: it silently omits the findings
    nobody classified, and the reader believes the digest. An emission site with no code is a defect
    in this repository, caught by the registry guard over the emission sites before it can ship.
    """
    unclassified = [w for w in warnings if not isinstance(w, CodedWarning)]
    if unclassified:
        raise ValueError(
            f"{len(unclassified)} warning(s) carry no code and cannot be summarised: "
            f"{unclassified[0][:120]!r}"
            + (f" (+{len(unclassified) - 1} more)" if len(unclassified) > 1 else "")
            + ". Every emission site names a member of VALID_WARNING_CODES; a message that was "
            "reformatted after being built goes through `findings.restate`."
        )
    summary: dict[str, int] = {}
    for warning in warnings:
        code = warning.code  # type: ignore[union-attr]
        summary[code] = summary.get(code, 0) + 1
    return (
        [w for w in warnings if w.carried],  # type: ignore[union-attr]
        {code: summary[code] for code in sorted(summary)},
    )
