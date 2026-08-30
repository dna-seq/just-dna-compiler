"""The draft-provenance digest (RM73) — the properties the three providers and three checks rely on.

`test_clinical.py` covers the ClinVar route end to end through the shipped surface. This file pins the
mechanism itself, including the two things that decide whether it works at all: that the digest is
computed from **raw cells** (so it can be taken at draft time, when the table is full of placeholders
the models refuse to load), and that it is scoped to the **checked column** (so filling a required
stub does not destroy it).
"""

import csv
from pathlib import Path

import pytest
from just_dna_enricher.licensing import write_sources_csv
from just_dna_enricher.provenance import (
    DRAFT_PROJECTIONS,
    draft_digest,
    drafted_unchanged,
    stamp_draft_digest,
)
from just_dna_format.sources import SourceRow
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER


class _Err(RuntimeError):
    pass


def _variants(spec: Path, rows: list[dict]) -> Path:
    spec.mkdir(parents=True, exist_ok=True)
    fields = ["rsid", "chrom", "start", "ref", "alts", "genotype", "state", "conclusion", "clin_sig"]
    with open(spec / "variants.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({name: row.get(name, "") for name in fields} for row in rows)
    return spec


def _drafted_rows() -> list[dict]:
    """What `clinvar_draft` writes: identity and `clin_sig` filled, `genotype` still a stub."""
    return [
        {"rsid": "rs334", "genotype": TEMPLATE_PLACEHOLDER, "state": "risk",
         "conclusion": "a", "clin_sig": "pathogenic"},
        {"rsid": "rs1799945", "genotype": TEMPLATE_PLACEHOLDER, "state": "risk",
         "conclusion": "b", "clin_sig": "benign"},
    ]


def test_the_map_covers_every_source_that_drafts_and_then_checks_the_same_column() -> None:
    """The one hand-kept thing here, so it is guarded rather than trusted.

    A fourth provider that drafts a column one of its own checks later compares must appear here, or
    it reintroduces the silent tautology this exists to end. Asserted as set equality against the
    providers that actually ship, not as a count.
    """
    assert set(DRAFT_PROJECTIONS) == {"clinvar", "cpic", "clinpgx", "pubmind"}
    for source, projection in DRAFT_PROJECTIONS.items():
        assert projection.table.endswith(".csv"), source
        assert projection.identity and projection.checked, source
        # Identity and subject must be disjoint, or the digest would be partly hashing the thing it
        # is meant to detect changes in against itself.
        assert not set(projection.identity) & set(projection.checked), source


def test_the_digest_is_taken_from_raw_cells_so_it_survives_an_unfilled_stub(tmp_path: Path) -> None:
    """The constraint that decided the implementation.

    One function serves the writer and the reader, because two that disagreed would not fail — they
    would silently never match. So it must work at *draft* time, and a freshly drafted `variants.csv`
    carries `<<REPLACE>>` in `genotype`, which `vocab.reject_template_placeholders` refuses to load by
    design. A model-based digest could not be taken here at all.
    """
    spec = _variants(tmp_path / "drafted", _drafted_rows())
    assert draft_digest(spec, "clinvar") is not None


def test_filling_the_stub_leaves_the_digest_alone_but_editing_the_call_moves_it(
    tmp_path: Path,
) -> None:
    """Why the projection is a column and not a row.

    Every ClinVar-drafted module receives at least one edit by construction — `genotype` is a required
    cell the source cannot supply — so a whole-row hash would be invalidated on every module and the
    skip would never fire once. The digest must be blind to that edit and sharp about the other one.
    """
    before = draft_digest(_variants(tmp_path / "a", _drafted_rows()), "clinvar")

    filled = _drafted_rows()
    for row in filled:
        row["genotype"] = "A/G"
    assert draft_digest(_variants(tmp_path / "b", filled), "clinvar") == before

    edited = _drafted_rows()
    edited[0]["clin_sig"] = "benign"
    assert draft_digest(_variants(tmp_path / "c", edited), "clinvar") != before


def test_the_digest_is_order_independent_but_identity_bound(tmp_path: Path) -> None:
    """A reorder changes no claim — the reasoning `content_signature` already follows.

    The second half is what stops that being a hole: swapping which *row* carries which call is a real
    edit and must be caught, so the value is hashed bound to its identity rather than as a bare
    multiset of calls.
    """
    rows = _drafted_rows()
    base = draft_digest(_variants(tmp_path / "base", rows), "clinvar")
    assert draft_digest(_variants(tmp_path / "rev", list(reversed(rows))), "clinvar") == base

    swapped = _drafted_rows()
    swapped[0]["clin_sig"], swapped[1]["clin_sig"] = swapped[1]["clin_sig"], swapped[0]["clin_sig"]
    assert draft_digest(_variants(tmp_path / "swap", swapped), "clinvar") != base


@pytest.mark.parametrize("rows", [[], None], ids=["empty-table", "no-table"])
def test_nothing_to_hash_is_none_rather_than_a_digest_of_nothing(tmp_path: Path, rows) -> None:
    """`None` is "no copy was established", which is the state that leaves a check running.

    A digest over an empty table would be a perfectly stable value that every empty table shares — so
    it would match, and the skip would fire on a module nobody drafted.
    """
    spec = tmp_path / "spec"
    spec.mkdir()
    if rows is not None:
        _variants(spec, rows)
    assert draft_digest(spec, "clinvar") is None


def test_a_source_that_drafts_nothing_has_no_digest(tmp_path: Path) -> None:
    spec = _variants(tmp_path / "spec", _drafted_rows())
    assert draft_digest(spec, "gnomad") is None


def _licence_row(dataset: str = "clinvar_2026-06-27", digest: str | None = None) -> SourceRow:
    return SourceRow(
        source="clinvar", layer="annotation", license="public-domain",
        dataset=dataset, draft_digest=digest,
    )


def test_the_stamp_overwrites_because_the_merge_never_would(tmp_path: Path) -> None:
    """The trap this function exists for.

    `merge_sources_file` keeps the existing row so a curator's hand-written terms survive a re-run,
    which is right — and it would therefore silently drop a second draft's digest, leaving a stale one
    behind that describes a table that has since grown. Invisible, and in the safe direction, which is
    what would have made it a trap rather than a bug.
    """
    spec = _variants(tmp_path / "spec", _drafted_rows())
    write_sources_csv([_licence_row(digest="stale")], spec / "sources.csv")

    written = stamp_draft_digest(spec, "clinvar", "annotation", error=_Err)
    assert written == draft_digest(spec, "clinvar") != "stale"

    # Idempotent: a re-draft that appended nothing leaves the projection unchanged, so there is
    # nothing to rewrite and the call is a no-op rather than a special case the caller must guard.
    assert stamp_draft_digest(spec, "clinvar", "annotation", error=_Err) is None


def test_drafted_unchanged_is_tri_state(tmp_path: Path) -> None:
    """`None` is not `False` and neither is `True` — the house algebra, and it decides the skip.

    Only the established match may skip a check; both other answers run it, for different reasons that
    a caller may want to word differently.
    """
    spec = _variants(tmp_path / "spec", _drafted_rows())
    digest = draft_digest(spec, "clinvar")

    assert drafted_unchanged(spec, "clinvar", [_licence_row()]) is None, "nothing recorded"
    assert drafted_unchanged(spec, "clinvar", [_licence_row(digest=digest)]) is True
    assert drafted_unchanged(spec, "clinvar", [_licence_row(digest="other")]) is False


def test_a_recorded_digest_whose_table_is_gone_is_false_not_unknown(tmp_path: Path) -> None:
    """Something was established and no longer holds, which is a case to check rather than wave through."""
    spec = tmp_path / "spec"
    spec.mkdir()
    assert drafted_unchanged(spec, "clinvar", [_licence_row(digest="anything")]) is False


def test_the_digest_is_outside_the_source_fact_set(tmp_path: Path) -> None:
    """It must not move `source_signature`: it tracks how this module was built, not what the row
    claims about the source, and it changes on every re-draft while the terms and release stand still."""
    from just_dna_format.integrity import fact_signature
    from just_dna_format.sources import SOURCE_FACT_FIELDS

    assert "draft_digest" not in SOURCE_FACT_FIELDS
    assert fact_signature([_licence_row()], SOURCE_FACT_FIELDS) == fact_signature(
        [_licence_row(digest="anything at all")], SOURCE_FACT_FIELDS
    )


def test_the_digest_survives_a_round_trip_because_it_rides_the_licence_parquet(
    tmp_path: Path,
) -> None:
    """The argument for putting this on `SourceRow` rather than in a sidecar of its own — demonstrated.

    `reverse_module` rebuilds authored files from parquet alone, so a free-standing sidecar would ride
    nothing and be dropped silently (the RM51 class). This column rides `sources.parquet`. Asserted
    both ways: the cell comes back, **and** it still describes the reversed table — reverse
    canonicalizes cell formatting, so a digest that survived as a string while ceasing to match would
    be the worse outcome of the two.
    """
    from just_dna_compiler.compiler import compile_module, reverse_module
    from just_dna_format.layout import SOURCES_CSV, resolve_sidecar

    spec = _variants(tmp_path / "spec", [
        {"rsid": "rs334", "genotype": "A/T", "state": "risk", "conclusion": "a",
         "clin_sig": "pathogenic"},
    ])
    (spec / "studies.csv").write_text("rsid,pmid\nrs334,12345678\n", encoding="utf-8")
    (spec / "module_spec.yaml").write_text(
        'schema_version: "1.0"\nmodule:\n  name: demo\n  title: T\n  description: d\n'
        '  report_title: R\ngenome_build: GRCh38\n',
        encoding="utf-8",
    )
    write_sources_csv([_licence_row()], spec / "sources.csv")
    stamped = stamp_draft_digest(spec, "clinvar", "annotation", error=_Err)
    assert stamped is not None

    out, reversed_dir = tmp_path / "out", tmp_path / "reversed"
    assert compile_module(spec, out, resolve_with_ensembl=False).success
    reverse_module(out, reversed_dir)

    path = resolve_sidecar(reversed_dir, SOURCES_CSV)
    assert path is not None, "the licence table came back"
    carried = [
        row["draft_digest"]
        for row in csv.DictReader(path.read_text(encoding="utf-8").splitlines())
        if row["source"] == "clinvar"
    ]
    assert carried == [stamped], "the digest rode sources.parquet through the round trip"
    # And it still answers the question it exists for, against the table reverse re-emitted.
    assert draft_digest(reversed_dir, "clinvar") == stamped
