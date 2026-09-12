"""A gate's verdict, with the reasons it is a `no` travelling beside it.

**Why this is not the house tri-state.** Everything else that answers a question here is
true / false / unknown and withholds on the third arm (CLAUDE.md, `@tri-state-is-the-house-algebra`).
A *gate* is the one shape that cannot: `check-acmg --strict` and `check-identifiers --strict` have to
choose an exit code, and a build that could not be certified is a `no` — the same way a 500 fails a
request rather than leaving it pending. So the unknown does not go into the verdict; it goes **beside**
it, as the reason the verdict is `no`. `Verdict` is falsy exactly when it carries codes, and the empty
set is the pass.

**The set holds errors, not non-answers**, which is the line that decides every member below. A
registry that refused, a list nobody could obtain, a table that carries identifiers and will not
parse — those are errors and they make the verdict false. A check the caller switched off, or a module
that simply has no row the check applies to, is not an error and does not: a run that asked nothing
because there was nothing to ask is a true, with its own denominator printed beside it. Conflating the
two is how `--strict --no-traits` would start failing builds for doing what it was told.

**Bool-like rather than a tuple**, because these are `@property` returns and a caller already writes
`if report.clean:`. `__bool__` keeps every such caller correct across the change, and a caller that
wants the reasons reads `.codes` instead of making a second call. The codes are ordered on the way out
(`sorted`), never iterated as a set, so a message built from one is stable between runs — the
deterministic-ordering rule applies to anything that reaches a user, not only to parquet bytes.
"""

from dataclasses import dataclass, field

#: Why a gate answered `no`. Closed vocabulary (Principle 6): a `frozenset` plus a validator, never an
#: `Enum` or a `Literal`.
#:
#: **The spellings are `VALID_VERIFICATION_SKIPS`' wherever they name the same fact**, because one fact
#: under two spellings is a normalizer waiting to happen (`@one-normalizer-two-spellings`): a run that
#: attests `skipped="offline"` must not report a verdict code called `no_list`. `stale_identifiers`,
#: `mismatched_assertions` and `tables_unreadable` have no counterpart there — they are findings rather
#: than skips, and a skip vocabulary has no word for *the check ran and failed*.
VALID_VERDICT_CODES: frozenset[str] = frozenset(
    {
        # findings: the check ran, and it found something
        "stale_identifiers",  # an id a registry no longer serves, or two authored cells contradicting
        "mismatched_assertions",  # an authored claim the consulted list does not carry
        # errors: the check could not run over everything it was asked about
        "offline",  # no list/snapshot was obtained, so nothing was compared
        "tables_unreadable",  # a table carrying subjects is present and will not parse
    }
)

#: Codes that are **not** members, and deliberately. `not_requested` and `nothing_to_check` are honest
#: non-answers rather than errors, so they leave the verdict true and are reported through the
#: denominators that already exist. `unreachable` is absent for a stronger reason: a registry outage
#: raises `IdentifierUnavailable` before a report is built, so no path could ever set it, and a
#: vocabulary member nothing writes is the defect `@registry-completeness` names — `VALID_SOURCE_LAYERS`
#: carried reserved members no file ever wrote, and that is the incident behind the rule.
_DELIBERATELY_ABSENT: frozenset[str] = frozenset({"not_requested", "nothing_to_check", "unreachable"})


@dataclass(frozen=True)
class Verdict:
    """A yes/no with its reasons. Falsy when it carries any code; the empty set is the pass."""

    codes: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        unknown = sorted(self.codes - VALID_VERDICT_CODES)
        if unknown:
            raise ValueError(
                f"not a VALID_VERDICT_CODES member: {', '.join(unknown)}. "
                f"Known: {', '.join(sorted(VALID_VERDICT_CODES))}."
            )

    def __bool__(self) -> bool:
        return not self.codes

    def __iter__(self):
        """Sorted, so a message built by walking a verdict is the same message twice."""
        return iter(sorted(self.codes))

    def __contains__(self, code: str) -> bool:
        return code in self.codes

    def __str__(self) -> str:
        return "pass" if not self.codes else "fail: " + ", ".join(sorted(self.codes))

    @classmethod
    def of(cls, **reasons: object) -> "Verdict":
        """`Verdict.of(offline=..., tables_unreadable=...)` — a code is carried when its value is truthy.

        The call site then reads as the sentence it implements, and the codes are checked against the
        vocabulary by `__post_init__` rather than at each caller.
        """
        return cls(frozenset(code for code, holds in reasons.items() if holds))
