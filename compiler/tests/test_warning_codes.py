"""RM131 — the warnings channel says what each finding is and whether an author can clear it.

`manifest.compilation.warnings` was a flat `list[str]`: no code, no count, and no way to tell a
finding an author *can* clear from one they cannot. A compile of a 190-row module returned roughly
14 kB of it. The channel already shipped and already sat outside `artifact.digest`, so what this adds
is structure beside the prose: `carried` (the unclearable subset) and `warnings_summary` (counts by
code), with `warnings` itself unchanged down to the byte.

The tests here are the guards that keep it honest. The registry one is the load-bearing one: the
whole design fails the moment an emission site can be added without naming a code, because
`warnings_summary` would then quietly under-count and a reader would take the digest as complete.
Asserted as an **equality over a walked set** — a floor would pass unchanged on the day a new site
slips through, which is the only day it matters.
"""

import ast
import csv
import io
from pathlib import Path

import pytest
from just_dna_compiler.compiler import (
    UNCLOSED_PHRASE,
    close_module,
    compile_module,
    validate_spec,
)
from just_dna_compiler.sweep import ModuleOutput, compare_module
from just_dna_format.findings import CodedWarning, classify, restate
from just_dna_format.overrides import SUPPRESSED_PHRASE, apply_overrides
from just_dna_format.resolution import ResolutionRow
from just_dna_format.vocab import (
    ACTIONABLE_WARNING_CODES,
    CARRIED_WARNING_CODES,
    VALID_WARNING_CODES,
)

_REPO = Path(__file__).resolve().parents[2]
_EXAMPLES = _REPO / "reference_examples"
#: Every module in the tree that emits into this channel. Walked, not listed, so a package added to
#: the workspace is covered without editing this file.
_SOURCE_ROOTS = (
    _REPO / "schema" / "src" / "just_dna_format",
    _REPO / "compiler" / "src" / "just_dna_compiler",
    _REPO / "enricher" / "src" / "just_dna_enricher",
)

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: codes\n  title: Codes\n  description: d\n  report_title: Codes\n"
    "genome_build: GRCh38\n"
)


# ── the registry: every emission site names a code, and every code has a site ────────────────────


def _coded_calls() -> dict[Path, list[tuple[int, str | None]]]:
    """`{module: [(line, code_or_None)]}` for every `CodedWarning(...)` construction in the tree.

    `code_or_None` is the literal first argument, or `None` where the call passes something the walk
    cannot read statically — the shape `CodedWarning.restated` uses to carry a code forward.
    """
    found: dict[Path, list[tuple[int, str | None]]] = {}
    for root in _SOURCE_ROOTS:
        for path in sorted(root.rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "CodedWarning"
                    and node.args
                ):
                    continue
                first = node.args[0]
                literal = first.value if isinstance(first, ast.Constant) else None
                found.setdefault(path, []).append((node.lineno, literal))
    return found


#: The local names this workspace gives a list of warnings. A name is a *channel* name only if it
#: says "warning" or is one of the two collectors a check builds its findings into before the caller
#: routes them by mode — `findings` and `messages`, both of which reach `warnings` under
#: `best_effort`. `errors` is deliberately absent: a refusal is a different channel, which is what
#: exempts `_check_license_gate` and `_check_build_coordinates` by shape rather than by a list.
_CHANNEL_LOCALS = frozenset({"warnings", "all_warnings", "warnings_out", "warns", "findings", "messages"})


def _participating_modules() -> list[Path]:
    """Modules that import `CodedWarning`, i.e. the ones that emit into this channel.

    Derived rather than listed, and the derivation is the honest one: a module cannot put a coded
    finding into the channel without importing the class, so this set is exactly the set of emitters
    at any moment. What it does *not* cover is a brand-new module emitting a bare string — nothing
    static can, since the channel is a `list[str]` by design — and that is what the corpus test below
    is for: `classify` refuses an uncoded message wherever it came from.
    """
    found = []
    for root in _SOURCE_ROOTS:
        for path in sorted(root.rglob("*.py")):
            if "CodedWarning" in path.read_text(encoding="utf-8"):
                found.append(path)
    return found


def _warning_producers(tree: ast.Module) -> set[str]:
    """Function names in one module whose result reaches a warning list, by a two-pass closure.

    A helper that builds its finding straight into a returned list literal (`return [f"..."]`) is an
    emission site exactly like an append — `_closure_warning`, `_findings_warning` and
    `_unmatched_warnings` are all that shape — and a walk over `.append` alone cannot see one. What
    tells such a function apart from an error builder is where its result *goes*, which is readable:

    * seeded from every call whose result is put into a channel-named local, whether by an
      `extend`/`append` onto one, by an assignment to one, or by a tuple unpack naming one;
    * then closed over the returns of the functions already in the set, which is what reaches a
      helper called only from inside another producer's returned list.

    `_check_license_gate` fails both rules — its result only ever reaches `all_errors` — so it stays
    out without being named, which is the property that keeps this from becoming a hand-kept list.
    """
    seeds: set[str] = set()

    def callees(node: ast.AST) -> set[str]:
        return {
            n.func.id
            for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }

    for node in ast.walk(tree):
        into_channel = False
        payload: ast.AST | None = None
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"extend", "append"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in _CHANNEL_LOCALS
            and node.args
        ):
            into_channel, payload = True, node.args[0]
        elif isinstance(node, ast.Assign):
            names = {
                n.id
                for target in node.targets
                for n in ast.walk(target)
                if isinstance(n, ast.Name)
            }
            if names & _CHANNEL_LOCALS or any("warn" in n for n in names):
                into_channel, payload = True, node.value
        if into_channel and payload is not None:
            seeds |= callees(payload)

    defined = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    producers = seeds & set(defined)
    while True:
        grown = set(producers)
        for name in producers:
            for statement in ast.walk(defined[name]):
                if isinstance(statement, ast.Return) and statement.value is not None:
                    grown |= callees(statement.value) & set(defined)
        if grown == producers:
            return producers
        producers = grown


def _emission_sites() -> list[tuple[Path, int, str]]:
    """Every place a message is put into this channel, across the participating modules.

    Two shapes: an append onto a channel-named local, and a returned list literal inside a function
    whose result reaches one. The second is derived by `_warning_producers` rather than assumed, so a
    helper that starts feeding the channel is covered the moment it does.
    """
    sites: list[tuple[Path, int, str]] = []
    for path in _participating_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        producers = _warning_producers(tree)
        for function in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
            for node in ast.walk(function):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "append"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in _CHANNEL_LOCALS
                    and node.args
                ):
                    sites.append((path, node.lineno, ast.unparse(node.args[0])))
                elif (
                    function.name in producers
                    and isinstance(node, ast.Return)
                    and isinstance(node.value, ast.List)
                    and any(
                        isinstance(e, (ast.JoinedStr, ast.Constant)) for e in node.value.elts
                    )
                ):
                    sites.append((path, node.lineno, ast.unparse(node.value)))
    return sites


def test_the_walk_finds_the_emission_surface_it_claims_to() -> None:
    """Guard the premise of the two tests below, which are worthless over an empty walk.

    Every number here is a floor on the *instrument*, never on the property — the properties below
    are equalities. What this asserts is that the walk reaches all three tiers and finds real work, so
    a refactor that renamed `CodedWarning` or moved the emitters cannot make the guards vacuous. The
    named functions are the three return-literal shapes a `.append` walk cannot see, so their
    presence is what proves the producer closure did its job.
    """
    calls = _coded_calls()
    tiers = {p.name for p in _SOURCE_ROOTS if any(str(c).startswith(str(p)) for c in calls)}
    assert tiers == {"just_dna_format", "just_dna_compiler", "just_dna_enricher"}
    assert sum(len(v) for v in calls.values()) > 50

    sites = _emission_sites()
    assert len(sites) > 50
    by_module = {path: _warning_producers(ast.parse(path.read_text())) for path in _coded_calls()}
    compiler_producers = next(v for k, v in by_module.items() if k.name == "compiler.py")
    assert {"_closure_warning", "_findings_warning"} <= compiler_producers
    assert "_check_license_gate" not in compiler_producers, "a refusal is a different channel"


def test_every_warning_code_declared_is_a_code_some_check_actually_builds() -> None:
    """An EQUALITY over the walked set, in both directions, because both failures are real.

    A declared member nobody emits is a published key a consumer can wait for forever — the
    `VALID_VERIFICATION_CHECKS` reserved-member shape is legitimate there and deliberately not
    borrowed here, because a warning code exists to *count* something and a code that counts nothing
    is not reserved, it is wrong. A code emitted but undeclared cannot happen at runtime
    (`CodedWarning.__new__` refuses it), and is asserted anyway so the failure arrives at a source
    walk rather than at whichever compile first reaches that branch.
    """
    emitted = {
        code for sites in _coded_calls().values() for _line, code in sites if code is not None
    }
    assert emitted == VALID_WARNING_CODES


def test_every_emission_site_names_a_code_rather_than_a_bare_message() -> None:
    """The registry guard: no site may put a plain string into a warning list.

    Written as an equality between *the sites that emit* and *the sites that emit a coded warning*,
    with the error naming the offenders — a `len(...) >= N` here would pass on the day a site is added
    uncoded, which is the only day the guard is doing anything.

    An error-only builder is exempt by shape rather than by a list: `_check_license_gate` and
    `_check_build_coordinates` return refusals, and a refusal is not in this channel. They are
    recognised by where their result goes, which `_warning_producers` reads off the source.
    """
    coded = {(path, line) for path, sites in _coded_calls().items() for line, _code in sites}
    uncoded = [
        f"{path.name}:{line} {text[:90]}"
        for path, line, text in _emission_sites()
        if "CodedWarning" not in text and "restate" not in text
        # A site that appends a variable built elsewhere carries whatever that expression carries;
        # the code is named where the message is built, and the corpus test proves the pairing.
        and not text.isidentifier()
        and (path, line) not in coded
    ]
    assert uncoded == [], "warning sites with no code"


def test_the_carried_set_is_a_subset_of_the_vocabulary_and_actionable_is_its_complement() -> None:
    """Derived by subtraction, never restated — a new code defaults to actionable, the safe side.

    Claiming a finding is unclearable when it is not tells an author to stop looking at the one thing
    they could have fixed, so the default has a direction and this pins it.
    """
    assert CARRIED_WARNING_CODES < VALID_WARNING_CODES
    assert ACTIONABLE_WARNING_CODES == VALID_WARNING_CODES - CARRIED_WARNING_CODES
    assert not CARRIED_WARNING_CODES & ACTIONABLE_WARNING_CODES


# ── the derivation ───────────────────────────────────────────────────────────────────────────────


def test_the_summary_accounts_for_every_warning_and_carried_is_a_subset_of_them() -> None:
    """Two invariants a reader depends on, and the first is what makes the digest readable at all.

    `sum(summary.values()) == len(warnings)` is the claim *this summary is complete*; without it a
    consumer reading `{"module_not_closed": 1}` beside forty warnings would take thirty-nine of them
    as not existing. And `carried ⊆ warnings` is what makes the subtraction meaningful — the
    actionable set is defined as a difference, so a member of neither list would be invisible.
    """
    findings = [
        CodedWarning("module_not_closed", "a"),
        CodedWarning("vrs_id_unverifiable", "b"),
        CodedWarning("vrs_id_unverifiable", "c"),
    ]
    carried, summary = classify(findings)
    assert sum(summary.values()) == len(findings)
    assert set(carried) <= set(findings)
    assert [str(w) for w in carried] == ["b", "c"]
    assert [w for w in findings if w not in carried] == ["a"]
    assert summary == {"module_not_closed": 1, "vrs_id_unverifiable": 2}


def test_an_unclassified_message_is_refused_rather_than_bucketed() -> None:
    """The rejected repair, pinned: a catch-all key would make the summary silently partial.

    `classify` raising is what turns *somebody forgot a code* into a failure at the first compile that
    reaches the branch, rather than into a digest that quietly omits it.
    """
    with pytest.raises(ValueError, match="carry no code"):
        classify([CodedWarning("module_not_closed", "a"), "a bare message"])
    with pytest.raises(ValueError, match="cannot restate"):
        restate("a bare message", "prefixed: a bare message")


def test_a_result_supplying_one_derived_half_and_not_the_other_is_refused() -> None:
    """Both halves come from one classification, so half-supplied would publish a disagreement.

    `sum(warnings_summary.values()) == len(warnings)` is the claim *this summary is complete*. A caller
    that filled `carried` and let the summary default would break it silently, and which half they
    meant to own is not knowable from inside the validator — so it refuses rather than half-derives.
    Both together is the legitimate case (a result rebuilt from a dump of itself) and stands.
    """
    from just_dna_compiler.models import ValidationResult  # noqa: PLC0415 — one call site

    rebuilt = ValidationResult(
        valid=True, warnings=["prose"], carried=[], warnings_summary={"module_not_closed": 1}
    )
    assert rebuilt.warnings == ["prose"]
    for half in ({"carried": []}, {"warnings_summary": {"module_not_closed": 1}}):
        with pytest.raises(ValueError, match="both derived halves or neither"):
            ValidationResult(valid=True, warnings=["prose"], **half)


def test_a_reformatted_message_keeps_the_code_the_check_gave_it() -> None:
    """Reformatting is the one operation that silently loses a code, so it goes through `restate`.

    Three real sites prefix a table name onto a message another tier built. Every other string
    operation on a `CodedWarning` returns a plain `str` by construction, which is exactly why this
    needs its own route rather than a convention.
    """
    built = CodedWarning("bin_coverage_gap", "no bin covers (1, 2)")
    prefixed = restate(built, f"repeat_alleles.csv: {built}")
    assert prefixed.code == built.code
    assert prefixed == "repeat_alleles.csv: no bin covers (1, 2)"
    assert not isinstance(f"prefix: {built}", CodedWarning), "an f-string is the trap, not the route"


def test_a_coded_warning_is_a_string_everywhere_the_compiler_already_treats_it_as_one() -> None:
    """The de-duplication the compile path runs on is `w not in all_warnings`, on the message.

    Two sides emitting the same sentence must still collapse to one line — that is the whole reason
    `validate_spec`'s findings can be re-run inside `compile_module`. A transport that compared by
    identity, or by code, would publish both.
    """
    left = CodedWarning("module_not_closed", "the same sentence")
    right = CodedWarning("module_not_closed", "the same sentence")
    channel: list[str] = [left]
    channel.extend(w for w in [right] if w not in channel)
    assert channel == ["the same sentence"]
    assert left == "the same sentence" and hash(left) == hash("the same sentence")
    assert "same" in left and left.startswith("the")


def test_a_code_that_is_not_published_cannot_be_built() -> None:
    """The vocabulary is closed at the point of construction, not only at the manifest boundary."""
    with pytest.raises(ValueError, match="is not a warning code"):
        CodedWarning("a_code_nobody_declared", "…")


# ── end to end, over the real reference corpus ───────────────────────────────────────────────────


def _every_example() -> list[Path]:
    return sorted(p for p in _EXAMPLES.iterdir() if (p / "module_spec.yaml").is_file())


@pytest.mark.parametrize("spec", _every_example(), ids=lambda p: p.name)
def test_the_channel_classifies_on_every_reference_example(spec: Path, tmp_path: Path) -> None:
    """The half a source walk cannot reach: a message that lost its code on the way through.

    The static guard proves every *site* names a code. This proves every *message that arrives* still
    carries one, over the whole corpus and both entry points — which is what catches a new f-string
    rewrap, an extend from a tier nobody thought about, or a seed read back off a pydantic model that
    flattened the subclass away.

    Every expectation is computed from the run rather than written down: the corpus changes, and a
    hard-coded warning count here would be a number read off a data dump.
    """
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    published = result.manifest.compilation

    assert list(published.warnings) == list(result.warnings)
    assert sum(published.warnings_summary.values()) == len(published.warnings)
    assert set(published.carried) <= set(published.warnings)
    assert set(published.warnings_summary) <= VALID_WARNING_CODES
    # Nothing in `carried` is a code the vocabulary calls actionable, and vice versa — the two lists
    # partition the channel rather than overlapping it.
    actionable = [w for w in published.warnings if w not in set(published.carried)]
    assert len(actionable) + len(published.carried) == len(published.warnings)

    pre_flight = validate_spec(spec)
    assert sum(pre_flight.warnings_summary.values()) == len(pre_flight.warnings)
    assert set(pre_flight.carried) <= set(pre_flight.warnings)


def test_the_published_warning_text_is_unchanged_by_the_codes(tmp_path: Path) -> None:
    """`@warning-text-is-api`: a consumer grepping a phrase must see exactly what it saw before.

    Read off a real compile and compared against the phrases the catalogue publishes, rather than
    against a stored copy of the prose — the point is that the *text* still reaches the channel, not
    that some particular sentence was preserved verbatim in a fixture.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text(
        "rsid,genotype,conclusion,gene,state\nrs1801133,C/C,a conclusion,MTHFR,neutral\n"
    )
    (spec / "studies.csv").write_text("rsid,pmid\nrs1801133,12345678\n")
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    unclosed = [w for w in result.warnings if UNCLOSED_PHRASE in w]
    assert len(unclosed) == 1, result.warnings
    # The exact string reaches the published manifest, and its code says which finding it is.
    assert unclosed[0] in result.manifest.compilation.warnings
    assert result.manifest.compilation.warnings_summary.get("module_not_closed") == 1
    assert unclosed[0] not in result.manifest.compilation.carried, "an author can run `close`"


def test_a_failed_compile_publishes_the_same_classified_channel_as_a_successful_one(
    tmp_path: Path,
) -> None:
    """The failure path seeds from the pre-flight, and it must not arrive unclassified.

    `compile_module` returns early on an invalid spec, carrying the pre-flight's warnings. Reading
    them off the *model* rather than off the classified list would hand `classify` plain strings — the
    exact shape pydantic's coercion creates and the reason the internal entry point exists.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion\nrs1801133,C/C,risk,\n")
    (spec / "notes.csv").write_text("a stray near-miss file\n")
    result = compile_module(spec, tmp_path / "out")
    assert not result.success and result.errors
    assert sum(result.warnings_summary.values()) == len(result.warnings)


def test_closing_a_module_carries_the_classified_channel_too(tmp_path: Path) -> None:
    """`ClosureResult` is the third result type on this seam and the one easiest to forget.

    It filters the pre-flight's own reminder to run this very command, which is a filter over the
    findings list rather than over the model's copy — the same handoff the compile path needs.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion\nrs1801133,C/C,risk,\n")
    refused = close_module(spec)
    assert not refused.closed
    assert sum(refused.warnings_summary.values()) == len(refused.warnings)
    assert not [w for w in refused.warnings if UNCLOSED_PHRASE in w]


# ── the suppression record (RM124 × RM131) ───────────────────────────────────────────────────────


def test_a_suppression_is_reported_once_per_reason_with_a_count(tmp_path: Path) -> None:
    """A `suppress` leaves no trace in the build product, so it gets one aggregated line.

    Aggregated by **reason** and not per row, which is what `reason` being a required column buys: a
    module suppressing many rows for one cause produces one sentence saying how many. The counts are
    computed from the overlay this test writes rather than written down.
    """
    reasons = {"the source lists a retired locus": 3, "a duplicate ClinVar submission": 1}
    rows = [
        ResolutionRow(variant_key=f"rs{i}", locus_index=0, chrom="6", start=i, source="cache")
        for i in range(1, sum(reasons.values()) + 1)
    ]
    overlay_rows: list[dict[str, str]] = []
    subject = 1
    for reason, count in reasons.items():
        for _ in range(count):
            overlay_rows.append(
                {
                    "table": "resolution.csv",
                    "subject": f"rs{subject}",
                    "member": "0",
                    "operation": "suppress",
                    "reason": reason,
                }
            )
            subject += 1

    from just_dna_format.overrides import OverrideRow  # noqa: PLC0415 — test-local, one call site

    overlay = [OverrideRow.model_validate(r) for r in overlay_rows]
    after, errors, warnings = apply_overrides("resolution.csv", rows, overlay)
    assert errors == []
    assert after == [], "every row named was suppressed"

    lines = [w for w in warnings if SUPPRESSED_PHRASE in w]
    assert len(lines) == len(reasons), "one line per reason, never one per row"
    for reason, count in reasons.items():
        matching = [w for w in lines if w.endswith(reason)]
        assert len(matching) == 1 and f" {count} " in matching[0]
    assert {w.code for w in lines} == {"overlay_rows_suppressed"}
    assert not any(w.carried for w in lines), "the author owns the overlay and can delete the row"


def test_a_suppression_record_survives_the_compile_reverse_compile_lap(tmp_path: Path) -> None:
    """The lap-stability property, proved against the real compile path rather than argued.

    After `reverse_module` the derived table is already post-overlay, so the suppress matches nothing
    on the second lap. A record counted over the rows *removed* would say a number on lap 1 and
    vanish on lap 2, moving a published manifest field between a module and its own round trip. This
    one is counted over the overlay, so both laps publish the identical line.
    """
    from just_dna_compiler.compiler import reverse_module  # noqa: PLC0415 — one call site

    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text(
        "rsid,chrom,start,ref,genotype,state,conclusion\n"
        "rs1801133,1,11796321,G,A/A,risk,a conclusion\n"
    )
    (spec / "studies.csv").write_text("rsid,pmid\nrs1801133,12345678\n")
    (spec / "resolution.csv").write_text(
        "variant_key,locus_index,rsid,chrom,start,ref,alts,source,genome_build\n"
        "rs1801133,0,rs1801133,1,11796321,G,A,manual,GRCh38\n"
        "rs1801133,1,rs1801133,1,11796322,G,A,manual,GRCh38\n"
    )
    (spec / "overrides.csv").write_text(
        "table,subject,member,field,operation,value,reason\n"
        "resolution.csv,rs1801133,1,,suppress,,the second locus is a mapping artefact\n"
    )
    first = compile_module(spec, tmp_path / "out1")
    assert first.success, first.errors
    suppressed = [w for w in first.manifest.compilation.warnings if SUPPRESSED_PHRASE in w]
    assert len(suppressed) == 1, first.manifest.compilation.warnings

    back = tmp_path / "back"
    reverse_module(tmp_path / "out1", back)
    (back / "overrides.csv").write_text((spec / "overrides.csv").read_text())
    second = compile_module(back, tmp_path / "out2")
    assert second.success, second.errors
    again = [w for w in second.manifest.compilation.warnings if SUPPRESSED_PHRASE in w]
    assert again == suppressed, "a lap must publish the line the previous lap published"


# ── the RM126 seam ───────────────────────────────────────────────────────────────────────────────


def _output(name: str, warnings: list[str], carried: list[str]) -> ModuleOutput:
    return ModuleOutput(
        name=name,
        manifest={
            "compilation": {
                "compiler_version": "just-dna-compiler 0.7.0",
                "warnings": warnings,
                "carried": carried,
            },
            "artifact": {"digest": "sha256:same"},
            "content_signature": "sha256:same",
        },
        parquet_schemas={},
    )


def test_the_sweep_splits_a_new_warning_by_whether_an_author_can_clear_it() -> None:
    """RM126's second consumer for the split — the seam its own comment said would land here.

    A carried finding appearing is usually this repository saying more about a limit it always had; an
    actionable one appearing is work arriving at somebody's door. The `warnings` axis still fires on
    any movement, deliberately: narrowing it would change what a published axis means, and every
    record already written claims the wider reading.
    """
    before = _output("m", ["kept"], [])
    after = _output("m", ["kept", "a tier limit", "a thing to fix"], ["a tier limit"])
    delta = compare_module(before, after)
    assert delta.axes["warnings"] is True
    assert delta.warnings_added == ("a thing to fix", "a tier limit")
    assert delta.carried_added == ("a tier limit",)
    assert delta.actionable_added == ("a thing to fix",)
    assert set(delta.carried_added) | set(delta.actionable_added) == set(delta.warnings_added)


def test_a_manifest_with_no_carried_field_reports_every_addition_as_actionable() -> None:
    """A pre-0.7 manifest said nothing about actionability, and the safe reading is the loud one.

    Calling an unrecorded finding *carried* would tell a reader that something they could fix is
    unfixable. The other direction only over-reports, which is what a sweep is for.
    """
    before = ModuleOutput(name="m", manifest={"compilation": {"warnings": []}}, parquet_schemas={})
    after = ModuleOutput(
        name="m", manifest={"compilation": {"warnings": ["something"]}}, parquet_schemas={}
    )
    delta = compare_module(before, after)
    assert delta.carried_added == ()
    assert delta.actionable_added == ("something",)


# ── the published field, read back ───────────────────────────────────────────────────────────────


def test_the_two_derived_manifest_fields_are_routed_to_the_warnings_axis() -> None:
    """They move exactly when `compilation.warnings` moves, so counting them is a false positive.

    A release that reworded one message would otherwise fire `manifest_fields` three times over on
    every module in a catalogue, which is the failure `EXCLUDED_MANIFEST_FIELDS` exists to prevent.
    """
    from just_dna_format.release_records import EXCLUDED_MANIFEST_FIELDS  # noqa: PLC0415

    for path in ("compilation.carried", "compilation.warnings_summary"):
        assert "routed" in EXCLUDED_MANIFEST_FIELDS[path].lower()
        assert "warnings" in EXCLUDED_MANIFEST_FIELDS[path]


def test_a_stored_manifest_reads_its_channel_back_without_reclassifying_it(tmp_path: Path) -> None:
    """A published manifest holds plain JSON strings, and reading one must not try to code them.

    This is why the derivation sits on the write side rather than in a `Compilation` validator: the
    same model is how a consumer loads a stored artifact, and a validator there would either raise on
    every published manifest or silently rewrite what the consumer holds.
    """
    from just_dna_format.manifest import read_manifest  # noqa: PLC0415 — one call site

    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion\nrs1801133,C/C,risk,a conclusion\n")
    (spec / "studies.csv").write_text("rsid,pmid\nrs1801133,12345678\n")
    out = tmp_path / "out"
    written = compile_module(spec, out)
    assert written.success, written.errors

    reloaded = read_manifest(out / "manifest.json")
    assert reloaded.compilation.warnings == written.manifest.compilation.warnings
    assert reloaded.compilation.carried == written.manifest.compilation.carried
    assert reloaded.compilation.warnings_summary == written.manifest.compilation.warnings_summary
    assert all(type(w) is str for w in reloaded.compilation.warnings)


def test_the_summary_keys_accept_the_other_separator_and_store_the_declared_one() -> None:
    """The third part of the vocabulary idiom, on a field whose vocabulary binds a mapping's KEYS.

    `check_vocab` is RETURNED, not merely called, so `module-not-closed` lands as `module_not_closed`
    rather than surviving as a second spelling of one code inside a published field.
    """
    from just_dna_format.manifest import Compilation  # noqa: PLC0415 — one call site

    block = Compilation(warnings_summary={"module-not-closed": 2, "module_not_closed": 1})
    assert block.warnings_summary == {"module_not_closed": 3}, "two spellings are one count"
    with pytest.raises(ValueError, match="must be one of"):
        Compilation(warnings_summary={"not_a_code": 1})


def test_a_binning_table_finding_keeps_its_own_code_through_the_table_prefix(
    tmp_path: Path,
) -> None:
    """The schema tier builds it, the compiler prefixes the table name, and the code survives both.

    The three `validate_bins` findings are not one kind — an inferred tiling, a contradicted
    declaration and a coverage gap have three different remedies — so a prefix that flattened them
    into one bucket would be the summary lying about what it counted.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "repeat_alleles.csv").write_text(
        "gene,repeat_unit,measure_kind,measure_min,measure_max,phenotype,conclusion\n"
        "HTT,CAG,repeat_count,6,26,normal,no expansion\n"
        "HTT,CAG,repeat_count,40,,full,fully penetrant\n"
    )
    result = validate_spec(spec)
    gaps = [w for w in result.warnings if "coverage gap" in w]
    assert gaps and all(w.startswith("repeat_alleles.csv: ") for w in gaps)
    assert result.warnings_summary["bin_coverage_gap"] == len(gaps)


def test_the_channel_survives_a_table_whose_findings_two_tiers_both_report(tmp_path: Path) -> None:
    """Both passes reach the same sentence, the existing dedup collapses it, and the count is 1.

    Re-running a check on both sides is the normal case here — `validate_spec` runs inside
    `compile_module` — and the summary must count the published line rather than the emissions behind
    it, or a consumer reading `sum(values) == len(warnings)` would find it false.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text(
        "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
        "rs2469808710,2,120926480,A,<DEL>,A/A,risk,a lengthless deletion\n"
        # A second row that survives: emptying the table is a refusal in both modes, and this test is
        # about the surviving warning rather than about that error.
        "rs1801133,1,11796321,G,A,A/A,risk,a conclusion\n"
    )
    (spec / "studies.csv").write_text("rsid,pmid\nrs2469808710,12345678\n")
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    published = result.manifest.compilation
    dropped = [w for w in published.warnings if "DROPPED from the compiled artifact" in w]
    assert len(dropped) == 1, "the pre-flight and the compile emit one sentence, deduped to one line"
    assert published.warnings_summary["symbolic_allele_row_dropped"] == 1
    assert sum(published.warnings_summary.values()) == len(published.warnings)


def test_no_two_codes_share_an_identical_message_across_the_corpus(tmp_path: Path) -> None:
    """De-duplication is by message, so one sentence under two codes would be order-dependent.

    Two emissions of the identical text under different codes would collapse to one line and the
    summary would then depend on which side ran first — a published field decided by evaluation
    order. Checked over every message the whole reference corpus actually produces.
    """
    from just_dna_compiler.compiler import _validate_spec  # noqa: PLC0415 — one call site

    by_message: dict[str, set[str]] = {}
    for spec in _every_example():
        # The internal entry point, because it hands back the classified list — the public one's
        # `warnings` has been through pydantic and is prose again, which is the very trap below.
        _result, findings = _validate_spec(spec)
        for warning in findings:
            by_message.setdefault(str(warning), set()).add(warning.code)
    assert by_message, "the corpus must produce findings for this to mean anything"
    ambiguous = {message: codes for message, codes in by_message.items() if len(codes) > 1}
    assert ambiguous == {}


def test_the_catalogue_in_the_reference_lists_every_published_code() -> None:
    """The doc a consumer greps must name the whole vocabulary, and it rots silently otherwise.

    An equality over the walked set, not a floor: a doc listing most of the codes is the shape that
    sends a reader looking for the one it omits. COMPILER.md is where the warning-text catalogue
    already lives, so the codes join it rather than starting a second home.
    """
    catalogue = (_REPO / "docs" / "COMPILER.md").read_text(encoding="utf-8")
    listed = {code for code in VALID_WARNING_CODES if f"`{code}`" in catalogue}
    assert listed == VALID_WARNING_CODES, sorted(VALID_WARNING_CODES - listed)


def test_the_reference_marks_which_codes_are_carried() -> None:
    """The other half of the catalogue: which findings an author cannot clear.

    Without it the doc publishes a vocabulary and withholds the one thing the split exists for.
    """
    catalogue = (_REPO / "docs" / "COMPILER.md").read_text(encoding="utf-8")
    start = catalogue.index("**Carried findings**")
    section = catalogue[start : catalogue.index("**Every published code**", start)]
    marked = {code for code in VALID_WARNING_CODES if f"`{code}`" in section}
    assert marked == CARRIED_WARNING_CODES


def test_a_warning_list_read_off_a_result_model_is_plain_prose(tmp_path: Path) -> None:
    """Stated as a test because it is the trap the whole handoff exists around.

    Pydantic flattens the subclass into `list[str]`, which is right for the published surface and
    fatal for a caller that keeps building on it. Anyone reaching for `result.warnings` as a seed gets
    a failing `classify`, and this pins the behaviour so the next reader meets it here rather than in
    a traceback.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML)
    (spec / "variants.csv").write_text("rsid,genotype,state,conclusion\nrs1801133,C/C,risk,a conclusion\n")
    (spec / "studies.csv").write_text("rsid,pmid\nrs1801133,12345678\n")
    result = validate_spec(spec)
    assert result.warnings, "the fixture must produce at least one finding"
    assert all(type(w) is str for w in result.warnings)
    with pytest.raises(ValueError, match="carry no code"):
        classify(result.warnings)
    # …and the derived halves are on the model precisely so nobody has to.
    assert sum(result.warnings_summary.values()) == len(result.warnings)


def test_a_csv_round_trip_of_the_summary_keeps_it_readable_by_a_consumer(tmp_path: Path) -> None:
    """A summary is a mapping a consumer will flatten; nothing in the keys needs escaping."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerows(sorted((code, 1) for code in VALID_WARNING_CODES))
    parsed = {row[0] for row in csv.reader(io.StringIO(buffer.getvalue())) if row}
    assert parsed == VALID_WARNING_CODES
