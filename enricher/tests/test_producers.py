"""Every field of `DERIVED_PRODUCERS` is checked against the registry that actually owns it.

**A registry is only worth having if something walks it**, and this one describes four things it does
not own: the set of derived tables (`_FACT_TABLES`), the source tokens (`licensing`'s `SourceTerms`),
the check names (`VALID_VERIFICATION_CHECKS`), and the commands (the live Typer tree). Each of those
is asserted as an equality or a containment against its owner, never as a count and never as a list
repeated here — `@registry-completeness`, which this workspace has now paid for in
`VALID_SOURCE_LAYERS`, `RM_TOC.md` and the §4 threshold counter.

The command assertion is the one with an incident behind it in a neighbouring registry: `cache status`
composed `f"{name} build"` and printed two commands that do not exist, because two lanes do not follow
that convention. A string an operator is asked to type is pinned against the tree that defines it.
"""

import ast
from pathlib import Path

import just_dna_enricher
import pytest
import typer
from just_dna_compiler.compiler import _FACT_TABLES
from just_dna_enricher import cli as enricher_cli
from just_dna_enricher import licensing
from just_dna_enricher.caches import CACHE_LANES, LANES_BY_NAME
from just_dna_enricher.producers import (
    ALL_PRODUCER_COMMANDS,
    ALL_PRODUCER_SOURCES,
    DERIVED_PRODUCERS,
    LANES_READ_WITHOUT_A_LICENCE_ROW,
    SOURCES_WITHOUT_TERMS,
    WRITTEN_BY_EVERY_PASS,
    producers_for,
)
from just_dna_format.layout import sidecar_spellings
from just_dna_format.vocab import VALID_VERIFICATION_CHECKS

_PACKAGE = Path(just_dna_enricher.__file__).resolve().parent


def _declared_sources() -> set[str]:
    """Every `SourceTerms.source` this tier declares, walked off the module rather than listed."""
    return {
        value.source
        for name in dir(licensing)
        if name.endswith("_TERMS")
        for value in [getattr(licensing, name)]
        if isinstance(value, licensing.SourceTerms)
    }


def _cli_commands() -> set[str]:
    """Every invocable command path under the enricher binary, without the binary itself."""
    group = typer.main.get_command(enricher_cli.app)

    def walk(command, prefix: str) -> set[str]:
        children = getattr(command, "commands", {})
        if not children:
            return {prefix} if prefix else set()
        found: set[str] = set()
        for name, child in children.items():
            found |= walk(child, f"{prefix} {name}".strip())
        return found

    return walk(group, "")


def test_every_derived_table_has_a_producer_or_is_named_as_having_none():
    """The equality that makes the registry total — a table missing from it is invisible to the page.

    `resolution.csv` is derived without being a fact table, and the licence table is written by every
    pass rather than by one (`@write-the-sourcerow`), so both sides are stated rather than a
    containment being asserted in one direction and the gap left to a reader.
    """
    derived = {csv for csv, _, _ in _FACT_TABLES} | {"resolution.csv"}
    accounted = set(DERIVED_PRODUCERS) | {
        csv for csv in derived for sp in sidecar_spellings(csv) if sp in WRITTEN_BY_EVERY_PASS
    }
    assert accounted == derived, (
        f"unaccounted derived tables: {sorted(derived - accounted)}; "
        f"named but not derived: {sorted(accounted - derived)}"
    )


def test_no_producer_claims_a_table_written_by_every_pass():
    """The licence table has no single writer, so naming one would name whichever came first."""
    assert not (set(DERIVED_PRODUCERS) & WRITTEN_BY_EVERY_PASS)


def test_every_producer_names_its_own_table():
    """The mapping's key and the entry's `table` cannot disagree — a copy-paste this shape invites."""
    for csv_name, group in DERIVED_PRODUCERS.items():
        for producer in group:
            assert producer.table == csv_name, f"{producer.command} is filed under {csv_name}"


def test_every_source_is_one_this_tier_declares_terms_for():
    """A producer cannot cite a source the licence registry has never heard of.

    The comparison is one-directional on purpose — this tier declares terms for plenty of sources no
    *derived* table comes from (the drafting providers', the snapshot lanes'), so an equality over the
    whole set would fail for a correct reason. What **is** an equality is the shortfall against the
    declared exemptions, below.
    """
    unknown = ALL_PRODUCER_SOURCES - _declared_sources()
    # **Equality, not containment, against the declared exemptions.** The shortfall is real and
    # designed — the two literature indexes have no terms constant because a paper's terms are the
    # article's (`@per-article-terms`) — so the repair is to declare it with its reason rather than to
    # loosen the guard that found it. An equality means a third unterm'd source cannot slip in by being
    # typed, and a token that *gains* terms cannot sit in the exemption list unnoticed.
    assert unknown == set(SOURCES_WITHOUT_TERMS), (
        f"sources with no SourceTerms and no declared reason: {sorted(unknown - set(SOURCES_WITHOUT_TERMS))}; "
        f"declared as having none but the registry now has terms for them: "
        f"{sorted(set(SOURCES_WITHOUT_TERMS) - unknown)}"
    )
    assert all(SOURCES_WITHOUT_TERMS.values()), "an exemption without a reason is an omission"


def test_every_check_a_producer_claims_is_a_vocabulary_member():
    """Membership is the right shape HERE: the vocabulary also holds checks no table-filling pass
    writes (`check-acmg`, `pgx`, …), so this direction is the only one entailed. The completeness
    claim is the equality below, against what each pass's code actually writes."""
    claimed = {check for group in DERIVED_PRODUCERS.values() for p in group for check in p.checks}
    assert claimed <= VALID_VERIFICATION_CHECKS, (
        f"checks no vocabulary member covers: {sorted(claimed - VALID_VERIFICATION_CHECKS)}"
    )


def _module_source(module: str) -> Path:
    """The file or package `DerivedProducer.module` names. Exactly one must exist, or the walk below
    covers nothing for that pass and an equality over nothing is a pass on an empty set."""
    candidates = [_PACKAGE / f"{module}.py", _PACKAGE / module]
    found = [path for path in candidates if path.exists()]
    assert len(found) == 1, f"producer module {module!r} resolves to {found}, expected exactly one"
    return found[0]


@pytest.mark.parametrize("command", sorted(ALL_PRODUCER_COMMANDS))
def test_each_pass_claims_exactly_the_checks_its_code_writes(command: str, checks_written_in) -> None:
    """**RM365 — an equality, never a subset.** `checks` says which checks a pass attests while it
    writes, and the only test it had asked whether its names were vocabulary members. So
    `DERIVED_PRODUCERS["resolution.csv"]` stayed at the six names it shipped with while `enrich` grew
    `published_refutation`, `evidence_status_currency` and `placement_agreement`, and the literature
    pass wrote `provenance_quote` beside the two it claimed. A page or tool built from the registry
    named four fewer attestations than `verification.json` carries.

    Grouped by **command**, because a check is attested by a run, not by a table: `enrich` fills three
    tables and writes its records once, from `enrich/verification_records.py`, while the concordance
    tables it also fills name `clinical_significance` from a module that writes no record itself. The
    walk is the shared one in `conftest.py`, over every module the command's producers name, and a
    call whose check name it cannot read is refused rather than skipped.
    """
    group = [p for csv in DERIVED_PRODUCERS.values() for p in csv if p.command == command]
    claimed = {check for p in group for check in p.checks}
    walk = checks_written_in(sorted({_module_source(p.module) for p in group}))
    assert not walk.unresolved, (
        f"{command}: record calls whose check name a walk cannot read: {walk.unresolved}"
    )
    assert claimed == walk.names, (
        f"`{command}` writes checks its producers do not claim: {sorted(walk.names - claimed)}; "
        f"claims checks it does not write: {sorted(claimed - walk.names)}"
    )


def test_every_command_a_producer_names_exists_in_the_cli():
    """The incident this guard is modelled on printed two commands that do not exist.

    `CacheLane.build_command` is a field rather than a composition for exactly this reason, and the
    reason generalises: a string an operator is asked to type has to be pinned against the tree that
    defines it, never against a naming convention. `gene-metrics` and `alphagenome expression` are the
    two here that no convention would produce.
    """
    missing = ALL_PRODUCER_COMMANDS - _cli_commands()
    assert not missing, f"producers naming commands the CLI does not have: {sorted(missing)}"


def test_every_module_a_producer_names_is_importable():
    import importlib

    for group in DERIVED_PRODUCERS.values():
        for producer in group:
            importlib.import_module(f"just_dna_enricher.{producer.module}")


def test_a_table_with_two_writers_says_why_each_shares_it():
    """Two writers of one table is the shape a reader needs a reason for, so it is required there.

    Asserted as an implication over the walked set rather than by naming `gene_metrics.csv`: a second
    writer arriving on another table inherits the requirement instead of the rule needing an edit.
    """
    for csv_name, group in DERIVED_PRODUCERS.items():
        if len(group) > 1:
            silent = [p.command for p in group if not p.shares_table_because]
            assert not silent, f"{csv_name} has {len(group)} writers and {silent} say nothing about why"


def test_producers_for_answers_empty_rather_than_raising():
    assert producers_for("variants.csv") == ()
    assert producers_for("licensing.csv") == ()
    assert len(producers_for("gene_metrics.csv")) == 2


# ── RM373: a lane's release reaches the licence row of every pass that reads it ────────────────


#: The functions a pass writes a licence row through. Only `record_table_sources` may appear in a
#: derived pass: it labels the row by the committed table. The other two leave `dataset` as the first
#: run wrote it, which is how every derived licence row came to name no release or a stale one.
_LICENCE_WRITERS = frozenset({"merge_sources_file", "record_source_terms", "record_table_sources"})


def _calls(path: Path) -> set[str]:
    """Every function name a module (or a package's modules) calls, by bare or attribute name."""
    files = [path] if path.is_file() else sorted(path.rglob("*.py"))
    names: set[str] = set()
    for file in files:
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    names.add(func.id)
                elif isinstance(func, ast.Attribute):
                    names.add(func.attr)
    return names


def _lanes_read(path: Path) -> set[str]:
    """The cache lanes a module reads, by the resolver each `CACHE_LANES` member declares."""
    by_resolver = {lane.resolve.__name__: lane.name for lane in CACHE_LANES}
    assert len(by_resolver) == len(CACHE_LANES), "two lanes share a resolver, so a read names neither"
    return {by_resolver[name] for name in _calls(path) if name in by_resolver}


_MODULES = sorted({p.module for group in DERIVED_PRODUCERS.values() for p in group})


@pytest.mark.parametrize("module", _MODULES)
def test_every_lane_a_pass_reads_is_declared_or_named_as_owing_no_licence_row(module: str) -> None:
    """**An equality.** The lanes a pass's code reads, against `release_lanes` plus the stated exemptions.

    A pass that starts reading a lane fails here until it says whether that lane's release reaches its
    licence row, which is the question the 0.8 Ensembl migration probe found nobody had asked: the
    resolution pass read three lanes and its licence rows named no release at all.
    """
    declared = {
        lane
        for group in DERIVED_PRODUCERS.values()
        for p in group
        if p.module == module
        for _, lane in p.release_lanes
    }
    exempt = {lane for (owner, lane) in LANES_READ_WITHOUT_A_LICENCE_ROW if owner == module}
    assert not declared & exempt, f"{module}: a lane both declared and exempted: {sorted(declared & exempt)}"
    assert _lanes_read(_module_source(module)) == declared | exempt


def test_every_release_lane_names_a_real_lane_and_a_declared_source() -> None:
    pairs = {pair for group in DERIVED_PRODUCERS.values() for p in group for pair in p.release_lanes}
    assert {lane for _, lane in pairs} <= set(LANES_BY_NAME)
    assert {source for source, _ in pairs} <= _declared_sources()
    assert {lane for _, lane in LANES_READ_WITHOUT_A_LICENCE_ROW} <= set(LANES_BY_NAME)


@pytest.mark.parametrize("module", _MODULES)
def test_a_derived_pass_writes_its_licence_rows_through_the_one_helper(module: str) -> None:
    """Every licence write in a derived pass is `record_table_sources`, and a pass reading a lane makes one."""
    writes = _calls(_module_source(module)) & _LICENCE_WRITERS
    assert writes <= {"record_table_sources"}, f"{module} writes licence rows through {sorted(writes)}"
    declared = any(
        p.release_lanes for group in DERIVED_PRODUCERS.values() for p in group if p.module == module
    )
    if declared:
        assert writes == {"record_table_sources"}
