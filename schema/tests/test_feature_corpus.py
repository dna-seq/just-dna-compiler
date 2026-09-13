"""`features/` accounts for **every** member of the registries it claims to cover, and quotes real text.

**Why this is a test.** RM149's corpus is a hand-kept set of scenarios over vocabularies that grow —
`VALID_WARNING_CODES`, `VALID_VERIFICATION_CHECKS`, `VALID_VERIFICATION_SKIPS` — which is this
project's most-repeated defect shape, and the rule drawn from it is `@registry-completeness`: *assert
an equality over a walked set, never a floor or a count in prose*. A corpus that is 68 of 73 codes
long looks complete, reads well, and is wrong about the five nobody wrote down.

**Four equalities and two groundings, and the groundings are the ones that matter most.** A scenario
corpus derived from documentation rather than from code is a second place for prose to drift, which
would make RM149 worse rather than better. So every scenario names its emission site
(`# source: <path>:<line>`), and this asserts:

* the path exists and the line is inside it;
* a `@code:X` scenario's source really is X's emission site, within three lines — a scenario pointing
  at the wrong `CodedWarning` call is the shape a copy-paste produces;
* every phrase a scenario quotes as the warning's text is a **real substring of a real string literal
  in that file**. A warning's text is an API (`@warning-text-is-api`), so a paraphrase is not a
  smaller version of the claim, it is a different claim — and quoting from a documentation paragraph
  instead of from the f-string is exactly the failure the corpus exists to stop.

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
#: A quoted phrase a step asserts is in the message. Only the `contains "…"` / `says "…"` /
#: `states "…"` forms are treated as claims about the text; a `Given` naming a value is not one.
_QUOTED = re.compile(r'(?:contains|says|stating|states|naming the phrase)\s+"([^"]{6,})"')


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


def _emission_sites() -> dict[Path, dict[int, str]]:
    """`{module: {line: code}}` for every `CodedWarning("<code>", …)` call in the workspace."""
    sites: dict[Path, dict[int, str]] = {}
    for module in sorted(_ROOT.glob("*/src/**/*.py")):
        if "generated" in module.parts:
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "CodedWarning" or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                sites.setdefault(module, {})[node.lineno] = first.value
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


def test_a_code_scenario_points_at_that_codes_emission_site() -> None:
    """`@code:X` and a `# source:` that is not X's emission site is the copy-paste failure."""
    sites = _emission_sites()
    problems: list[str] = []
    for scenario in _scenarios():
        codes = scenario.codes()
        if not codes or scenario.source is None:
            continue
        relative, line = scenario.source
        path = _ROOT / relative
        in_file = sites.get(path, {})
        for code in codes:
            near = {
                emitted
                for emitted_line, emitted in in_file.items()
                if abs(emitted_line - line) <= _SOURCE_SLACK
            }
            if code not in near:
                problems.append(
                    f"{scenario.where}: @code:{code} but {relative}:{line} emits "
                    f"{sorted(near) or 'no coded warning'}"
                )
    assert not problems, "\n".join(problems)


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
