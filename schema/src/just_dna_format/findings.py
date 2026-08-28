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

**A caller holding plain prose is not an error**, and this is where that is decided rather than at
each result model: the public result types have accepted `warnings=["..."]` since 0.6 and Principle 3
keeps them accepting it, so `classify` withholds for such a caller and refuses only the part-classified
channel no legitimate caller can produce.
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

    def __getnewargs__(self) -> tuple[str, str]:
        """Keep the code through `copy`/`pickle`, which reconstruct via `__new__`.

        `str.__getnewargs__` hands back just the text, so the two-argument `__new__` above was called
        with one argument and raised `TypeError` — on `copy.deepcopy` and on any pickle. That is not
        hypothetical here: `_validate_spec` hands its classified list to a caller and tells it to keep
        building, so the list outlives the function and a caller is entitled to copy it.
        """
        return self.code, str(self)

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
    """`(carried, warnings_summary)` for a finished warning list — three cases, no flag.

    `carried` is the subset of `warnings` no edit to the spec directory can remove, in the order the
    findings appear, so a consumer subtracting it from `warnings` gets the actionable set and both
    lists read in the same order as the channel they came from.

    * **Every member classified** — the compiler's own channel — and the answer is the full one:
      `sum(summary.values()) == len(warnings)`, which is the claim *this summary is complete*.
    * **No member classified** — a caller holding plain prose, which the public result models have
      accepted since 0.6 and must keep accepting (Principle 3) — and the answer is **withheld**:
      `([], {})`. Nothing here can tell what those messages are, and the house rule is to withhold an
      unknown rather than report or negate it. An empty summary beside a non-empty channel reads as
      *not classified*, which is a different statement from *complete and short*.
    * **Mixed** — some coded, some not — is the one case that cannot arise from a legitimate caller,
      because every emission site in this repository names a code. So it **raises**, loudly, at the
      first compile that reaches the branch.

    **No catch-all key, in any of the three.** A `warnings_summary` with a bucket for the unclassified
    is the rejected repair wearing a different hat: it silently omits findings nobody classified while
    looking complete, and the reader believes the digest. Withholding says less; it does not lie.

    The residual gap the three cases leave — a module whose *only* warning lost its code, so the list
    is uniformly unclassified rather than mixed — is what the static registry guard over the emission
    sites covers, and it is why that guard is an equality rather than a floor.
    """
    coded = [w for w in warnings if isinstance(w, CodedWarning)]
    if not coded:
        return [], {}
    if len(coded) != len(warnings):
        unclassified = [w for w in warnings if not isinstance(w, CodedWarning)]
        raise ValueError(
            f"{len(unclassified)} of {len(warnings)} warning(s) carry no code, so this channel is "
            f"part classified and cannot be summarised honestly: {unclassified[0][:120]!r}"
            + (f" (+{len(unclassified) - 1} more)" if len(unclassified) > 1 else "")
            + ". Every emission site names a member of VALID_WARNING_CODES; a message that was "
            "reformatted after being built goes through `findings.restate`."
        )
    summary: dict[str, int] = {}
    for warning in coded:
        summary[warning.code] = summary.get(warning.code, 0) + 1
    return (
        [w for w in coded if w.carried],
        {code: summary[code] for code in sorted(summary)},
    )
