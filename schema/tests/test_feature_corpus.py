"""`features/` accounts for **every** member of the registries it claims to cover, and quotes real text.

**Why this is a test.** RM149's corpus is a hand-kept set of scenarios over vocabularies that grow —
`VALID_WARNING_CODES`, `VALID_VERIFICATION_CHECKS`, `VALID_VERIFICATION_SKIPS` — which is this
project's most-repeated defect shape, and the rule drawn from it is `@registry-completeness`: *assert
an equality over a walked set, never a floor or a count in prose*. A corpus that is 68 of 73 codes
long looks complete, reads well, and is wrong about the five nobody wrote down.

**Equalities over the registries, and groundings over what each scenario claims — and the groundings
are the ones that matter most.** (No count of them here, deliberately: a figure beside a list of
`test_` functions in the same file is the `@registry-completeness` shape one more time, and this file
exists because of it.) A scenario corpus derived from documentation rather than from code is a second
place for prose to drift, which would make RM149 worse rather than better. So every scenario names its
emission site (`# source: <path>:<line>`), and this asserts:

* the path exists and the line is inside it;
* a `@code:X` scenario's source really is X's emission site, within three lines — a scenario pointing
  at the wrong `CodedWarning` call is the shape a copy-paste produces;
* the same alignment for `@check:`/`@skip:`, which was **missing at first and cost exactly what it was
  supposed to prevent**: two unrelated fixes in this session inserted comment lines above eleven
  referenced sites, every `# source:` after them silently pointed six to eight lines early, and the
  suite stayed green because those tags had only *the line is inside the file*;
* every phrase a scenario quotes as the warning's text is a **real substring of a real string literal
  in that file**. A warning's text is an API (`@warning-text-is-api`), so a paraphrase is not a
  smaller version of the claim, it is a different claim — and quoting from a documentation paragraph
  instead of from the f-string is exactly the failure the corpus exists to stop. This one was **also
  narrower than it read at first**: keyed on a verb before the quote, it extracted 46 of 162 phrases,
  so it is keyed on the step keyword instead and now checks all of them.

**It imports no Gherkin parser and adds no dependency.** The corpus is read as text, which is all the
structure these assertions need, and is the same choice `test_docs_site_nav.py` makes about
`mkdocs`: a guard over a surface should not require the tool that consumes it.

It sits beside `test_doc_links.py` and `test_docs_site_nav.py`, the other guards that walk the
repository rather than a tier: it imports `just_dna_format.vocab` for the registries and nothing else.
"""

import ast
import re
from pathlib import Path

from just_dna_format.vocab import (
    ACTIONABLE_WARNING_CODES,
    CARRIED_WARNING_CODES,
    VALID_VERIFICATION_CHECKS,
    VALID_VERIFICATION_SKIPS,
    VALID_WARNING_CODES,
)

_ROOT = Path(__file__).resolve().parents[2]
_FEATURES = _ROOT / "features"

#: How far a scenario's `# source:` line may sit from the `CodedWarning(` call it claims. A call spans
#: several lines (the code on one, the f-string on the next few) and `ast` reports the call's own line,
#: so a source taken from a `grep` of the code string lands within a couple of lines either way.
_SOURCE_SLACK = 3


class _Scenario:
    """One scenario: its tags, its `# source:`, and the phrases its steps quote."""

    def __init__(self, feature: Path, name: str, line: int, *, outline: bool) -> None:
        self.feature = feature
        self.name = name
        self.line = line
        self.outline = outline
        self.tags: set[str] = set()
        self.source: tuple[str, int] | None = None
        self.text_from: str | None = None
        self.phrases: list[str] = []
        self.keywords: set[str] = set()
        self.has_examples = False

    @property
    def where(self) -> str:
        return f"{self.feature.relative_to(_ROOT)}:{self.line} ({self.name})"

    def codes(self) -> set[str]:
        return {t.split(":", 1)[1] for t in self.tags if t.startswith("code:")}

    def checks(self) -> set[str]:
        return {t.split(":", 1)[1] for t in self.tags if t.startswith("check:")}

    def skips(self) -> set[str]:
        return {t.split(":", 1)[1] for t in self.tags if t.startswith("skip:")}


_TAG = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z0-9_.\-]+)?)")
_SOURCE = re.compile(r"#\s*source:\s*(\S+?):(\d+)\s*$")
#: Where a finding's TEXT lives, when that is not the module that codes it. A message built by one
#: module and wrapped in a `CodedWarning` by another is a real shape here — `layout.deprecation_notice`
#: writes the sentence and `_locate_sidecar` names the code — and it is the shape where a code goes
#: missing at a boundary (`@finding-loses-its-code-at-a-boundary`). So the scenario names both: the
#: emission site the code is checked against, and the module the quoted phrase is checked against.
_TEXT = re.compile(r"#\s*text:\s*(\S+?)\s*$")
_SCENARIO = re.compile(r"^\s*(Scenario|Scenario Outline)\s*:\s*(.+?)\s*$")
#: A quoted phrase a step asserts is in the message: EVERY double-quoted run of six characters or more
#: on an outcome step. Keyed on the step keyword rather than on a verb before the quote, and that is the
#: correction rather than the first design — the verb list (`contains|says|states|…`) extracted 46 of the
#: 162 quoted phrases in this corpus, because a `Then` says `saying the flag "…"`, `ends at "…"`,
#: `continues "…"`, `offers "…"` and a dozen other shapes, and a guard that checks a quarter of the
#: claims while the reference says it checks all of them is worse than no guard.
#:
#: `Given`/`When` are deliberately excluded: those name an input VALUE (a genotype, a filename, an
#: rsID), which has no reason to appear in the module's own strings.
_QUOTED = re.compile(r'"([^"]{6,})"')
_OUTCOME_STEP = re.compile(r"^(?:Then|And|But)\b")


def _parse(feature: Path) -> list[_Scenario]:
    """Every scenario in one feature file, with the tags and `# source:` that precede it.

    Tags and the source comment attach to the *next* scenario, which is Gherkin's own rule for tags and
    is the convention `features/README.md` states for the comment. A file-level comment block before
    the `Feature:` line therefore attaches to nothing, which is what makes a header possible.
    """
    scenarios: list[_Scenario] = []
    pending_tags: set[str] = set()
    pending_source: tuple[str, int] | None = None
    pending_text: str | None = None
    current: _Scenario | None = None
    for number, raw in enumerate(feature.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        source_match = _SOURCE.search(line)
        if line.startswith("#") and source_match:
            pending_source = (source_match.group(1), int(source_match.group(2)))
            continue
        text_match = _TEXT.search(line)
        if line.startswith("#") and text_match:
            pending_text = text_match.group(1)
            continue
        if line.startswith("@"):
            pending_tags |= set(_TAG.findall(line))
            continue
        scenario_match = _SCENARIO.match(raw)
        if scenario_match:
            current = _Scenario(
                feature,
                scenario_match.group(2),
                number,
                outline=scenario_match.group(1) == "Scenario Outline",
            )
            current.tags = pending_tags
            current.source = pending_source
            current.text_from = pending_text
            scenarios.append(current)
            pending_tags, pending_source, pending_text = set(), None, None
            continue
        if line.startswith("Feature:"):
            pending_tags, pending_source, pending_text = set(), None, None
            continue
        if current is None or line.startswith("#"):
            continue
        if _OUTCOME_STEP.match(line):
            current.phrases.extend(_QUOTED.findall(line))
        keyword = line.split(" ", 1)[0].rstrip(":")
        if keyword in {"Given", "When", "Then", "And", "But"}:
            current.keywords.add(keyword)
        elif keyword == "Examples":
            current.has_examples = True
    return scenarios


def _feature_files() -> list[Path]:
    return sorted(_FEATURES.rglob("*.feature"))


def _scenarios() -> list[_Scenario]:
    return [s for feature in _feature_files() for s in _parse(feature)]


def _joined_literals(path: Path) -> list[str]:
    """Every string a module builds, with interpolation holes marked so no phrase can span one.

    An f-string's literal halves are separate `JoinedStr` values, so `"…not diploid here — use a "`
    and the sentence it continues into are one message and two nodes; a phrase quoted across that seam
    is still one phrase in the emitted text. Joining the literal parts is what lets the assertion be
    about the *message* rather than about a source line. The `{…}` marker is deliberate: a phrase that
    appears to span an interpolated value is a phrase no consumer will ever match, so it must fail.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            out.append(
                "".join(
                    part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else "{…}"
                    for part in node.values
                )
            )
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            pieces = [
                child.value
                for child in (node.left, node.right)
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            ]
            if pieces:
                out.append("".join(pieces))
    return out


def _call_sites(
    callee: set[str], *, argument: int = 0, resolve_check_constant: bool = False
) -> dict[Path, dict[int, set[str]]]:
    """`{module: {line: {the string at `argument`, …}}}` for every call to one of `callee`.

    One walker for all three registries, and `argument` is which position holds the name — that
    parameter exists because the first version of this guard did not have it and reported four correct
    scenarios as misaligned: `skipped(check, reason)` puts the CHECK first and the SKIP REASON second, so
    a `@skip:` scenario is aligned against argument 1. `CodedWarning("<code>", msg)` and `ran(check, …)`
    both name theirs first. `alphagenome_check` names its member through a module-level `CHECK`
    constant, which `resolve_check_constant` follows. A line may carry more than one name where a call is
    nested, so the value is a set rather than a string.
    """
    sites: dict[Path, dict[int, set[str]]] = {}
    for module in sorted(_ROOT.glob("*/src/**/*.py")):
        if "generated" in module.parts:
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"))
        constant = (
            next(
                (
                    node.value.value
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Assign)
                    and isinstance(node.value, ast.Constant)
                    and any(getattr(target, "id", None) == "CHECK" for target in node.targets)
                ),
                None,
            )
            if resolve_check_constant
            else None
        )
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id not in callee or len(node.args) <= argument:
                continue
            chosen = node.args[argument]
            named = (
                chosen.value
                if isinstance(chosen, ast.Constant) and isinstance(chosen.value, str)
                else (constant if argument == 0 else None)
            )
            if isinstance(named, str):
                sites.setdefault(module, {}).setdefault(node.lineno, set()).add(named)
    return sites


def test_the_corpus_is_not_empty() -> None:
    """A guard over an empty directory passes every equality below by vacuity."""
    assert _feature_files(), f"no .feature files under {_FEATURES}"
    assert _scenarios(), "feature files carry no scenarios"


def test_every_warning_code_has_a_scenario() -> None:
    """The equality, reported as a symmetric difference so a failure names the code."""
    tagged = {code for s in _scenarios() for code in s.codes()}
    missing = VALID_WARNING_CODES - tagged
    unknown = tagged - VALID_WARNING_CODES
    assert not missing, f"warning codes with no scenario: {sorted(missing)}"
    assert not unknown, f"@code: tags naming no member of VALID_WARNING_CODES: {sorted(unknown)}"


def test_carried_and_actionable_tags_match_the_vocabulary() -> None:
    """`@carried` / `@actionable` restate a published split, so they are checked against it.

    Carried means *no edit to the spec directory can clear this*. A scenario that tags it the other way
    tells a reader the opposite of what `CodedWarning.carried` will answer, which is worse than leaving
    the tag off — so a scenario must carry exactly one of the two.
    """
    problems: list[str] = []
    for scenario in _scenarios():
        for code in scenario.codes():
            has_carried = "carried" in scenario.tags
            has_actionable = "actionable" in scenario.tags
            if has_carried == has_actionable:
                problems.append(f"{scenario.where}: @code:{code} needs exactly one of @carried/@actionable")
                continue
            expected_carried = code in CARRIED_WARNING_CODES
            if has_carried != expected_carried:
                wanted = "@carried" if expected_carried else "@actionable"
                problems.append(f"{scenario.where}: {code} is {wanted}")
    assert not problems, "\n".join(problems)


def test_carried_and_actionable_partition_the_codes() -> None:
    """The two sets the tags restate are themselves a partition — if they stop being one, the rule above
    is checking a scenario against a vocabulary that no longer has two halves."""
    assert CARRIED_WARNING_CODES | ACTIONABLE_WARNING_CODES == VALID_WARNING_CODES
    assert not CARRIED_WARNING_CODES & ACTIONABLE_WARNING_CODES


def test_every_verification_check_has_a_scenario() -> None:
    tagged = {check for s in _scenarios() for check in s.checks()}
    missing = VALID_VERIFICATION_CHECKS - tagged
    unknown = tagged - VALID_VERIFICATION_CHECKS
    assert not missing, f"verification checks with no scenario: {sorted(missing)}"
    assert not unknown, f"@check: tags naming no member of VALID_VERIFICATION_CHECKS: {sorted(unknown)}"


def test_every_skip_reason_has_a_scenario() -> None:
    tagged = {skip for s in _scenarios() for skip in s.skips()}
    missing = VALID_VERIFICATION_SKIPS - tagged
    unknown = tagged - VALID_VERIFICATION_SKIPS
    assert not missing, f"skip reasons with no scenario: {sorted(missing)}"
    assert not unknown, f"@skip: tags naming no member of VALID_VERIFICATION_SKIPS: {sorted(unknown)}"


def test_every_scenario_names_a_source_that_exists() -> None:
    """A `# source:` is mandatory, and both halves of it are checked.

    Mandatory because the direction of the corpus is code → Gherkin: a scenario with no site is one
    nobody can check against the thing it describes, which is the drift RM149 is about.
    """
    problems: list[str] = []
    for scenario in _scenarios():
        if scenario.source is None:
            problems.append(f"{scenario.where}: no `# source:` comment")
            continue
        relative, line = scenario.source
        path = _ROOT / relative
        if not path.is_file():
            problems.append(f"{scenario.where}: source path does not exist: {relative}")
            continue
        total = len(path.read_text(encoding="utf-8").splitlines())
        if not 1 <= line <= total:
            problems.append(f"{scenario.where}: {relative} has {total} lines, source names {line}")
        if scenario.text_from is not None and not (_ROOT / scenario.text_from).is_file():
            problems.append(f"{scenario.where}: `# text:` path does not exist: {scenario.text_from}")
    assert not problems, "\n".join(problems)


def _reason_sites() -> dict[Path, dict[int, set[str]]]:
    """`{module: {line: {skip reason, …}}}` for every string literal naming a member of the vocabulary.

    Wider than a call-site walk, and it has to be: **two of the eight reasons are never passed as a
    literal to `skipped()` at all.** `tautology` and `not_permitted` are decided somewhere else and
    travel as a variable — `result.not_checked = "not_permitted"` in `clinpgx`, `clin_sig_skip =
    "tautology"` in `enrich` — so a call-site walk reports the two scenarios that describe them as
    misaligned while they point at the only line in the workspace that actually names the reason.

    Which is the better pointer anyway: where a reason is *decided* is what a reader wants, and the
    `skipped()` call three functions away is plumbing. So the site is any literal occurrence, and the
    assertion this supports is the one that matters — the line still names the thing the scenario says it
    does, so an edit above it is caught.
    """
    sites: dict[Path, dict[int, set[str]]] = {}
    for module in sorted(_ROOT.glob("*/src/**/*.py")):
        if "generated" in module.parts:
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value in VALID_VERIFICATION_SKIPS:
                sites.setdefault(module, {}).setdefault(node.lineno, set()).add(node.value)
    return sites


def _misaligned(tag: str, sites: dict[Path, dict[int, set[str]]], reader) -> list[str]:
    """Scenarios whose `# source:` is not within `_SOURCE_SLACK` lines of a site naming their member."""
    problems: list[str] = []
    for scenario in _scenarios():
        members = reader(scenario)
        if not members or scenario.source is None:
            continue
        relative, line = scenario.source
        in_file = sites.get(_ROOT / relative, {})
        near = {
            name
            for site_line, names in in_file.items()
            if abs(site_line - line) <= _SOURCE_SLACK
            for name in names
        }
        for member in sorted(members - near):
            problems.append(
                f"{scenario.where}: @{tag}:{member} but {relative}:{line} names {sorted(near) or 'no member'}"
            )
    return problems


def test_a_code_scenario_points_at_that_codes_emission_site() -> None:
    """`@code:X` and a `# source:` that is not X's emission site is the copy-paste failure."""
    problems = _misaligned("code", _call_sites({"CodedWarning"}), lambda s: s.codes())
    assert not problems, "\n".join(problems)


def test_a_check_or_skip_scenario_points_at_that_members_record_site() -> None:
    """The same alignment for the verification vocabulary, and it exists because it was missing.

    The `@code:` check above had it from the start and these two had only *the line is inside the file*
    — so when RM242 inserted six comment lines into `alphagenome_check.py` and RM243 added eight to
    `enrich.py`, eleven `# source:` lines in `features/enricher/` silently began pointing six to eight
    lines early and the suite stayed green. A `# source:` with no alignment check is a line number that
    rots on the next edit above it, which is the whole failure mode the corpus is supposed to resist.

    Scoped to `@check:`/`@skip:` scenarios, which are the ones that name a record site. The rest of the
    corpus's `# source:` lines are structural — a docstring, a branch, a constant — and have no call to
    align against; that residue is stated in RM149's addendum as a known cost rather than left implied.
    """
    checks = _call_sites({"ran", "skipped"}, resolve_check_constant=True)
    reasons = _reason_sites()
    problems = _misaligned("check", checks, lambda s: s.checks() - _RESERVED_CHECK_TAGS(s))
    problems += _misaligned("skip", reasons, lambda s: s.skips())
    assert not problems, "\n".join(problems)


def _RESERVED_CHECK_TAGS(scenario: _Scenario) -> set[str]:
    """A `@reserved` member is emitted by nothing, so its scenario names the vocabulary, not a call."""
    return scenario.checks() if "reserved" in scenario.tags else set()


def test_every_quoted_phrase_is_real_text_from_the_source() -> None:
    """The anti-paraphrase guard, and the reason this corpus is worth more than the prose it replaces.

    A step saying the warning *contains* a phrase is a claim about a published string. If the phrase
    came from a documentation paragraph rather than from the f-string, the scenario is a fourth place
    for the same sentence to be almost-right — so the phrase must be a substring of a string literal
    in the module the scenario names.
    """
    problems: list[str] = []
    cache: dict[Path, list[str]] = {}
    for scenario in _scenarios():
        if scenario.source is None or not scenario.phrases:
            continue
        named = scenario.text_from or scenario.source[0]
        path = _ROOT / named
        if not path.is_file() or path.suffix != ".py":
            continue
        if path not in cache:
            cache[path] = _joined_literals(path)
        literals = cache[path]
        for phrase in scenario.phrases:
            if not any(phrase in literal for literal in literals):
                problems.append(f'{scenario.where}: no literal in {named} contains "{phrase}"')
    assert not problems, "\n".join(problems)


def test_every_scenario_has_a_when_and_a_then() -> None:
    """Gherkin shape, read as text: a scenario with no `Then` states no expectation at all."""
    problems = [
        f"{s.where}: no `{keyword}` step"
        for s in _scenarios()
        for keyword in ("When", "Then")
        if keyword not in s.keywords
    ]
    assert not problems, "\n".join(problems)


def test_a_scenario_outline_has_examples() -> None:
    """An outline with no `Examples` table is a scenario with holes in it and no values to fill them."""
    problems = [
        f"{s.where}: a Scenario Outline with no Examples table"
        for s in _scenarios()
        if s.outline and not s.has_examples
    ]
    assert not problems, "\n".join(problems)
