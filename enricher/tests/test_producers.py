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

import typer
from just_dna_compiler.compiler import _FACT_TABLES
from just_dna_enricher import cli as enricher_cli
from just_dna_enricher import licensing
from just_dna_enricher.producers import (
    ALL_PRODUCER_COMMANDS,
    ALL_PRODUCER_SOURCES,
    DERIVED_PRODUCERS,
    SOURCES_WITHOUT_TERMS,
    WRITTEN_BY_EVERY_PASS,
    producers_for,
)
from just_dna_format.layout import sidecar_spellings
from just_dna_format.vocab import VALID_VERIFICATION_CHECKS


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
    claimed = {check for group in DERIVED_PRODUCERS.values() for p in group for check in p.checks}
    assert claimed <= VALID_VERIFICATION_CHECKS, (
        f"checks no vocabulary member covers: {sorted(claimed - VALID_VERIFICATION_CHECKS)}"
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
