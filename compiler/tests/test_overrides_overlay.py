"""The overlay through the real compile/reverse paths, on a real reference example (RM124).

`overrides.csv` is the mechanism the 2026-08-12 cost amendment asked for: a derived table that is
both machine-written and human-overridable can be edited into a state that is not merely stale but a
false claim, and the repair is to move the edit out of the file. What that buys is only real if the
compiler applies the overlay everywhere the derived rows are read, and only *safe* if the round trip
survives the overlay being applied twice — because `reverse_module` emits the post-overlay table
**plus** the overlay, deliberately, rather than recording the value each correction replaced.

So the load-bearing test here is the Principle 7 lap, run against `hfe_hemochromatosis` (a real
module carrying `resolution.csv`, `gwas_effects.csv` and `studies.csv`) with an overlay that
exercises all three operations at once. The rest are the decisions around it: the placement rule that
`insert` owes because parquet bytes depend on row order, the covered-table registry, and the promise
that a module with no overlay is byte-for-byte the module it was before this feature existed.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import (
    _FACT_TABLES,
    ARTIFACT_PARQUETS,
    compile_module,
    content_signature,
    reverse_module,
    validate_spec,
)
from just_dna_format.overrides import OVERRIDABLE_TABLES

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"
_HEADER = [
    "table", "subject", "member", "field", "operation", "value", "reason", "decided_by",
    "decided_at",
]


def _example(tmp_path: Path, name: str = "hfe_hemochromatosis") -> Path:
    """A writable copy of a published reference example.

    Copied rather than edited in place — the corpus is the repo's ground truth and a test that
    mutates it is a test that breaks every other one. `verification.json` is dropped because the
    attestation is bound to the authored bytes and this test is about to add a file to them.
    """
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLES / name, spec)
    (spec / "verification.json").unlink(missing_ok=True)
    return spec


def _write_overlay(spec: Path, rows: list[list[str]]) -> None:
    with (spec / "overrides.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(_HEADER)
        writer.writerows(rows)


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _why(what: str) -> list[str]:
    """The three trailing columns, so a row in a test reads as its decision and not as boilerplate."""
    return [what, "curator", "2026-08-28"]


# ── the load-bearing one ────────────────────────────────────────────────────────────────────────


def test_a_module_with_an_overlay_is_a_principle_7_fixed_point(tmp_path: Path) -> None:
    """compile → reverse → compile → reverse → compile, with all three operations in the overlay.

    Every signature holds from the **first** lap, which is the strict form: `artifact.digest` follows
    parquet bytes and therefore row order, so this fails if `insert` places a row differently on the
    second pass, and `content_signature` fails if reverse loses a single overlay cell.

    The idempotency is not incidental — it is what pays for reverse emitting the post-overlay table.
    All three operations are idempotent set operations, so the second application is a no-op: an
    update to a value already present, an insert of a row already keyed, a suppress of a row already
    absent.
    """
    spec = _example(tmp_path)
    resolution = _read(spec / "resolution.csv")
    gwas = _read(spec / "gwas_effects.csv")
    corrected, dropped = resolution[0]["variant_key"], gwas[0]["association_id"]

    _write_overlay(
        spec,
        [
            ["resolution.csv", corrected, "0", "source", "update", "manual",
             *_why("re-checked against dbSNP by hand")],
            ["gwas_effects.csv", dropped, "", "", "suppress", "",
             *_why("the association was retracted upstream")],
            ["resolution.csv", "rs_curated_only", "0", "chrom", "insert", "6",
             *_why("the source has no answer for this locus")],
            ["resolution.csv", "rs_curated_only", "0", "start", "insert", "26093141",
             *_why("the source has no answer for this locus")],
        ],
    )

    first = compile_module(spec, tmp_path / "a1")
    assert first.success, first.errors
    assert content_signature(spec) == first.manifest.content_signature

    # The overlay has to have *done* something, or every equality below holds vacuously — a fixed
    # point over a transform that is the identity proves nothing at all.
    bare = _example(tmp_path / "bare")
    without = compile_module(bare, tmp_path / "a0")
    assert without.success, without.errors
    assert without.manifest.artifact.digest != first.manifest.artifact.digest
    assert without.manifest.content_signature != first.manifest.content_signature

    reverse_module(tmp_path / "a1", tmp_path / "rev1")
    reversed_check = validate_spec(tmp_path / "rev1")
    assert reversed_check.valid, reversed_check.errors

    second = compile_module(tmp_path / "rev1", tmp_path / "a2")
    assert second.success, second.errors
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
    assert first.manifest.content_signature == second.manifest.content_signature
    assert (
        first.manifest.compilation.resolution_signature
        == second.manifest.compilation.resolution_signature
    )

    reverse_module(tmp_path / "a2", tmp_path / "rev2")
    third = compile_module(tmp_path / "rev2", tmp_path / "a3")
    assert third.success, third.errors
    assert second.manifest.artifact.digest == third.manifest.artifact.digest


def test_the_overlay_survives_reverse_cell_for_cell(tmp_path: Path) -> None:
    """The half the digest cannot see on its own: `reverse_module` has to rebuild `overrides.csv`
    from `overrides.parquet`, because there is nowhere else the corrections could come from.

    Without it the round trip would silently discard every correction and quietly hand back a module
    that says what its source says — the exact loss this table exists to prevent, performed by the
    tool instead of by an `rm`.
    """
    spec = _example(tmp_path)
    pmid_free_subject = _read(spec / "resolution.csv")[0]["variant_key"]
    _write_overlay(
        spec,
        [["resolution.csv", pmid_free_subject, "0", "source", "update", "manual",
          *_why("re-checked against dbSNP by hand")]],
    )
    compile_module(spec, tmp_path / "art")
    reverse_module(tmp_path / "art", tmp_path / "rev")

    before = _read(spec / "overrides.csv")[0]
    after = _read(tmp_path / "rev" / "overrides.csv")[0]
    assert {k: v for k, v in after.items() if k != "decided_at"} == {
        k: v for k, v in before.items() if k != "decided_at"
    }
    # The one cell that is deliberately not preserved verbatim: a timestamp is canonicalized on load,
    # because it reaches `artifact.digest` where two spellings of one instant are two identities.
    assert after["decided_at"] == "2026-08-28T00:00:00Z"


# ── the effects, shown to be real ───────────────────────────────────────────────────────────────


def test_the_derived_file_on_disk_is_never_touched(tmp_path: Path) -> None:
    """`derived = f(source, overlay)`, which is the whole point: the sidecar stays a build product,
    so `rm` plus a re-run costs nothing. A test that only checked the parquet could not tell this
    design from the hand-edit it replaces."""
    spec = _example(tmp_path)
    original = (spec / "resolution.csv").read_bytes()
    subject = _read(spec / "resolution.csv")[0]["variant_key"]
    _write_overlay(
        spec,
        [["resolution.csv", subject, "0", "source", "update", "manual",
          *_why("re-checked against dbSNP by hand")]],
    )
    result = compile_module(spec, tmp_path / "art")
    assert result.success, result.errors
    assert (spec / "resolution.csv").read_bytes() == original


def test_a_suppress_removes_the_row_from_the_parquet_and_the_manifest_count(
    tmp_path: Path,
) -> None:
    """Counted against the authored file at runtime rather than against a number read off a dump."""
    spec = _example(tmp_path)
    gwas = _read(spec / "gwas_effects.csv")
    _write_overlay(
        spec,
        [["gwas_effects.csv", gwas[0]["association_id"], "", "", "suppress", "",
          *_why("the association was retracted upstream")]],
    )
    result = compile_module(spec, tmp_path / "art")
    assert result.success, result.errors
    built = pl.read_parquet(tmp_path / "art" / "gwas_effects.parquet")
    assert built.height == len(gwas) - 1
    assert gwas[0]["association_id"] not in set(built["association_id"].to_list())


def test_an_inserted_row_lands_at_the_end_of_its_subjects_group(tmp_path: Path) -> None:
    """The placement rule, through the real compile: row order is load-bearing because parquet bytes
    depend on it, so `insert` is a function of the overlay's own authored order rather than of a sort
    over values a later correction could move.

    `gwas_effects.csv` is the table that shows it, because its rows survive reverse verbatim while
    `resolution.csv` is rebuilt from the artifact."""
    spec = _example(tmp_path)
    gwas = _read(spec / "gwas_effects.csv")
    template = gwas[0]
    _write_overlay(
        spec,
        [
            ["gwas_effects.csv", "GCST_CURATED", "", column, "insert", template[column],
             *_why("published in a supplement the catalog has not indexed")]
            for column in ("variant_key", "dataset", "source", "status")
        ],
    )
    result = compile_module(spec, tmp_path / "art")
    assert result.success, result.errors
    built = pl.read_parquet(tmp_path / "art" / "gwas_effects.parquet")
    ids = built["association_id"].to_list()
    # The subject is new, so its group is empty and the row goes at the end of the table.
    assert ids == [row["association_id"] for row in gwas] + ["GCST_CURATED"]


# ── the registries and the promise to already-published modules ─────────────────────────────────


def test_the_covered_set_is_every_merge_not_clobber_sidecar_but_the_licence_table() -> None:
    """An **equality over a walked set**, never a floor (`@registry-completeness`).

    Derived from the compiler's own table tuples, so a new derived sidecar landing without an entry
    in `OVERRIDABLE_TABLES` fails here rather than shipping as a table nobody can correct. The one
    exclusion is stated as a name because it is a decision: `sources.csv` / `licensing.csv` has its
    own merge path and is the one derived table a human is told to hand-write.
    """
    derived = {"resolution.csv"} | {csv_name for csv_name, _, _ in _FACT_TABLES}
    assert set(OVERRIDABLE_TABLES) == derived - {"sources.csv"}
    assert len(OVERRIDABLE_TABLES) == 7


def test_the_overlay_parquet_is_last_so_no_published_digest_moves() -> None:
    """`ARTIFACT_PARQUETS` **is** `artifact.digest` order and an absent file contributes nothing, so
    the end of the tuple is the one slot a new parquet can take without moving the digest of every
    module that carries a later table."""
    assert ARTIFACT_PARQUETS[-1] == "overrides.parquet"


@pytest.mark.parametrize(
    "example", ["hfe_hemochromatosis", "cyp2c9_warfarin_grch37"], ids=lambda n: n
)
def test_a_module_with_no_overlay_keeps_both_identities(tmp_path: Path, example: str) -> None:
    """The additive promise (Principle 3), asserted against the corpus rather than argued.

    An absent optional table contributes nothing to `content_signature` and no file to
    `artifact.digest`, exactly as an unset optional column does — so this feature moves the identity
    of no module already published. Two examples with different shapes (a SNP panel with fact
    sidecars, and a GRCh37 PGx module with none of them)."""
    spec = _example(tmp_path, example)
    assert not (spec / "overrides.csv").exists()
    result = compile_module(spec, tmp_path / "art")
    assert result.success, result.errors
    assert not (tmp_path / "art" / "overrides.parquet").exists()
    assert "overrides.parquet" not in {entry.name for entry in result.manifest.artifact.files}


# ── the refusals and the warnings, through the two public entry points ──────────────────────────


def test_validate_refuses_everything_compile_refuses(tmp_path: Path) -> None:
    """`@validate-refuses-all`: the documented order is `validate` then `compile`, so a green
    pre-flight followed by a refusal sends an author looking for a change they did not make."""
    spec = _example(tmp_path)
    _write_overlay(
        spec,
        [
            ["resolution.csv", "rs1", "0", "chrom", "update", "6", *_why("a")],
            ["resolution.csv", "rs1", "0", "chrom", "update", "7", *_why("b")],
        ],
    )
    pre_flight = validate_spec(spec)
    compiled = compile_module(spec, tmp_path / "art")
    assert not pre_flight.valid
    assert not compiled.success
    assert any("duplicate row" in message for message in pre_flight.errors)
    assert set(compiled.errors) <= set(pre_flight.errors)


def test_an_empty_overlay_file_is_an_error_rather_than_a_silent_nothing(tmp_path: Path) -> None:
    spec = _example(tmp_path)
    _write_overlay(spec, [])
    result = validate_spec(spec)
    assert not result.valid
    assert any("overrides.csv is present but has no rows." in e for e in result.errors)


def test_correcting_a_table_the_module_does_not_carry_warns_in_both_modes(
    tmp_path: Path,
) -> None:
    """The scoping decision, pinned as a phrase because a consumer keys on it: an overlay lies on top
    of a derived table and never creates one."""
    spec = _example(tmp_path)
    assert not (spec / "frequencies.csv").exists()
    _write_overlay(
        spec,
        [["frequencies.csv", "rs1800562", "global", "source", "update", "gnomad",
          *_why("the pass has not been run yet")]],
    )
    phrase = "An overlay lies on top of a derived table and never creates one"
    for strict in (False, True):
        result = compile_module(spec, tmp_path / f"art{strict}", strict=strict)
        assert result.success, result.errors
        hits = [w for w in result.warnings if phrase in w]
        assert len(hits) == 1, "reported once, not once per pass"
        assert "frequencies.csv" in hits[0]


def test_an_update_reaching_no_row_warns_once_across_both_passes(tmp_path: Path) -> None:
    """`compile_module` runs `validate_spec` first, so a check living in both places emits its
    sentence twice unless the caller dedupes on the message. Re-running is the normal case; printing
    the identical sentence a second time is not."""
    spec = _example(tmp_path)
    _write_overlay(
        spec,
        [["resolution.csv", "rs_not_in_this_module", "0", "source", "update", "manual",
          *_why("re-checked by hand")]],
    )
    result = compile_module(spec, tmp_path / "art")
    assert result.success, result.errors
    phrase = "may be mistyped, or the source may have stopped publishing"
    assert len([w for w in result.warnings if phrase in w]) == 1


def test_a_misplaced_overlay_under_derived_is_reported_rather_than_tolerated(
    tmp_path: Path,
) -> None:
    """The overlay is authored, so it has one legal place. Under `derived/` its rows are read from
    nowhere and the module compiles green without them — the silent-success shape."""
    spec = _example(tmp_path)
    (spec / "derived").mkdir()
    with (spec / "derived" / "overrides.csv").open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(_HEADER)
    result = validate_spec(spec)
    assert any(
        "overrides.csv is an authored table sitting in derived/" in w for w in result.warnings
    )
