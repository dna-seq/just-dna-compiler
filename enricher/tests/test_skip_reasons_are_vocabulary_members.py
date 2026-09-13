"""Every `skipped(...)` call site names a real member of `VALID_VERIFICATION_SKIPS` (RM242).

**The defect this was written for.** `alphagenome_check.check_variant_impact`'s no-client branch wrote
`skipped(CHECK, "unchecked", …)`, and `"unchecked"` is not a member — it is one of the *old* per-pass
spellings the vocabulary's own comment says the set replaced, and it survived in one call site. The
model refuses it, so that branch raised `ValidationError` instead of recording a skip: a
`just-dna-enricher alphagenome check` run against a local AVI snapshot with no `ALPHAGENOME_API_KEY`
and at least one variant inside a knot — the ordinary shape for anyone without a key — crashed where it
was supposed to attest *nobody asked*.

**Walked rather than case-by-case, because the defect is the class and not the instance.** A test that
pinned the one branch would pass the day somebody writes `no_snapshot` in another pass; the rule is
`@registry-completeness` — assert an equality over a walked set. Every literal reason in the workspace
is collected here and checked against the vocabulary, so the next old spelling fails at import-time
speed rather than on a user's machine.

**Static rather than behavioural, and that is the point.** The branch is reachable only with a
provisioned AVI reference, a straddling variant and no client, which is a fixture this suite would have
to build to reach one line; the AST walk needs none of that and covers every other call site in the
same pass. A `reason` computed by the caller is out of reach here by construction — those are checked
where they are built (`acmg.AcmgUnavailable.skip`, `identifiers`' PGS leg, `clinical.tautology_reason`)
— so this asserts what it can see and says so rather than claiming a coverage it does not have.
"""

import ast
from pathlib import Path

from just_dna_format.vocab import VALID_VERIFICATION_SKIPS

_ROOT = Path(__file__).resolve().parents[2]


def _literal_skip_reasons() -> dict[str, list[str]]:
    """`{reason: [where, …]}` for every `skipped(check, "<literal>")` in the workspace's sources."""
    found: dict[str, list[str]] = {}
    for module in sorted(_ROOT.glob("*/src/**/*.py")):
        if "generated" in module.parts:
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "skipped" or len(node.args) < 2:
                continue
            reason = node.args[1]
            if isinstance(reason, ast.Constant) and isinstance(reason.value, str):
                where = f"{module.relative_to(_ROOT)}:{node.lineno}"
                found.setdefault(reason.value, []).append(where)
    return found


def test_the_walk_finds_call_sites_at_all() -> None:
    """A walk that matched nothing would pass the assertion below by vacuity."""
    reasons = _literal_skip_reasons()
    assert reasons, "no literal `skipped(check, '…')` call sites found — the walk is broken"


def test_every_literal_skip_reason_is_a_vocabulary_member() -> None:
    """The equality, reported so a failure names the file and line rather than a count."""
    reasons = _literal_skip_reasons()
    unknown = {
        reason: wheres for reason, wheres in sorted(reasons.items()) if reason not in VALID_VERIFICATION_SKIPS
    }
    assert not unknown, "skip reasons outside VALID_VERIFICATION_SKIPS: " + "; ".join(
        f"{reason!r} at {', '.join(wheres)}" for reason, wheres in unknown.items()
    )
