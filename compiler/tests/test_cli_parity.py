"""CLI/Python-API parity for the surfaces the schema tier cannot expose itself (0.5.1).

`just-dna-format` ships no CLI — Typer would breach its pydantic-plus-cryptography dependency floor
(CONSTITUTION Goal 2) — so anything it owns that a *user* needs has to be reachable through
`just-dna-compiler`. `verify` was built on exactly that argument. Two more of its functions were
still Python-only, and the gaps were load-bearing rather than cosmetic:

* `sign --private-key` demanded a key file the toolchain had no way to produce;
* `verify --public-key` demanded a string only `public_key_b64_from_pem` could derive;
* `authoring_reference()`/`json_schemas()` — the drift-proof replacement for a hand-kept spec dump —
  had no route at all, which is worst for the consumer that most needs it (an MCP surface).
"""

import json
from pathlib import Path

import pytest
from just_dna_compiler import draft
from just_dna_compiler.cli import app
from just_dna_compiler.draft import DRAFTABLE, model_for
from just_dna_compiler.hints import describe_table
from just_dna_format.base import field_category
from just_dna_format.manifest import read_manifest
from just_dna_format.reference import _ALL_MODELS, authoring_reference
from just_dna_format.vocab import RESERVED_NAMES_0_4
from typer.testing import CliRunner

runner = CliRunner()

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: parity\n  title: P\n  description: d\n  report_title: P\n"
)
_VARIANTS = "rsid,genotype,state,conclusion\nrs1800562,A/A,risk,c\n"
_STUDIES = "rsid,pmid\nrs1800562,10453733\n"


def _module(tmp_path: Path) -> Path:
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    (spec / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    out = tmp_path / "out"
    assert runner.invoke(app, ["compile", str(spec), str(out)]).exit_code == 0
    return out


# ── keygen: the missing first step of sign → verify ────────────────────────────────────────────


def test_the_whole_sign_then_verify_loop_runs_from_the_cli_alone(tmp_path: Path) -> None:
    """The parity claim, end to end: no Python needed at any step."""
    module = _module(tmp_path)
    key = tmp_path / "key.pem"

    keygen = runner.invoke(app, ["keygen", "--out", str(key)])
    assert keygen.exit_code == 0, keygen.output
    public_key = next(
        line.split("public key:")[1].strip()
        for line in keygen.output.splitlines()
        if "public key:" in line
    )

    assert runner.invoke(app, ["sign", str(module), "--private-key", str(key)]).exit_code == 0
    verified = runner.invoke(
        app, ["verify", str(module), "--no-require-marketplace", "--public-key", public_key]
    )
    assert verified.exit_code == 0, verified.output
    assert "signature: verified" in verified.output


def test_the_public_key_keygen_prints_is_the_one_that_lands_in_the_manifest(tmp_path: Path) -> None:
    module = _module(tmp_path)
    key = tmp_path / "key.pem"
    printed = runner.invoke(app, ["keygen", "--out", str(key)]).output
    runner.invoke(app, ["sign", str(module), "--private-key", str(key)])
    manifest = read_manifest(module / "manifest.json")
    assert manifest.signature is not None
    assert manifest.signature.public_key in printed


def test_a_different_key_fails_verification(tmp_path: Path) -> None:
    """Without this the loop above would pass for the wrong reason."""
    module = _module(tmp_path)
    signing_key, other_key = tmp_path / "a.pem", tmp_path / "b.pem"
    runner.invoke(app, ["keygen", "--out", str(signing_key)])
    other = runner.invoke(app, ["keygen", "--out", str(other_key)]).output
    other_public = next(
        line.split("public key:")[1].strip() for line in other.splitlines() if "public key:" in line
    )
    runner.invoke(app, ["sign", str(module), "--private-key", str(signing_key)])
    result = runner.invoke(
        app, ["verify", str(module), "--no-require-marketplace", "--public-key", other_public]
    )
    assert result.exit_code == 1


def test_keygen_refuses_to_overwrite_a_key(tmp_path: Path) -> None:
    """Overwriting orphans every signature made with the old key, and published bytes never change."""
    key = tmp_path / "key.pem"
    assert runner.invoke(app, ["keygen", "--out", str(key)]).exit_code == 0
    before = key.read_bytes()
    result = runner.invoke(app, ["keygen", "--out", str(key)])
    assert result.exit_code == 1
    assert key.read_bytes() == before


def test_keygen_without_an_out_path_writes_no_file(tmp_path: Path) -> None:
    before = set(tmp_path.iterdir())
    result = runner.invoke(app, ["keygen"])
    assert result.exit_code == 0
    assert "BEGIN PRIVATE KEY" in result.output
    assert set(tmp_path.iterdir()) == before


# ── reference: the schema tier's own description, reachable ────────────────────────────────────


def test_reference_emits_the_live_authoring_reference() -> None:
    result = runner.invoke(app, ["reference"])
    assert result.exit_code == 0
    assert json.loads(result.output) == authoring_reference()


def test_reference_schemas_emits_a_schema_per_model() -> None:
    result = runner.invoke(app, ["reference", "--schemas"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert {"VariantRow", "DiplotypeRow", "PgsRow"} <= set(payload)
    # The full materialized shape, unlike the authoring reference: compiler-managed columns included.
    assert "variant_key" in payload["VariantRow"]["properties"]


def test_the_summary_names_every_model_and_the_vocabularies() -> None:
    result = runner.invoke(app, ["reference", "--summary"])
    assert result.exit_code == 0
    for model in authoring_reference()["models"]:
        assert model in result.output
    # Derived from the live set rather than pinned to one name: `RESERVED_NAMES_0_4` gained two
    # members in 0.6 (the element-rule companions RM54 held back), and a literal here would fail for
    # a reason that has nothing to do with what this test is about — that the summary prints them.
    assert f"reserved names: {', '.join(sorted(RESERVED_NAMES_0_4))}" in result.output


# ── the requiredness drift the reference used to carry ─────────────────────────────────────────


def test_the_reference_reports_the_three_way_category_not_just_is_required() -> None:
    """`required` alone told an authoring tool to fill three columns and produced a file the compiler
    refused, naming a fourth. `draft` was fixed and this surface was not — the exact drift this
    module exists to prevent."""

    fields = {f["name"]: f for f in authoring_reference()["models"]["RepeatAlleleRow"]}
    # The trap: not required, and *not* safely left blank either.
    assert fields["measure_kind"]["required"] is False
    assert fields["measure_kind"]["category"] == "defaulted"
    assert fields["unresolved"]["category"] == "defaulted"
    assert fields["gene"]["category"] == "required"
    assert fields["repeat_unit"]["category"] == "required"


def test_both_surfaces_now_read_one_definition() -> None:
    """`just_dna_compiler.draft.field_category` and the reference must not be able to disagree."""
    assert draft.field_category is field_category
    for model_name, fields in authoring_reference()["models"].items():
        model = _ALL_MODELS[model_name]
        for entry in fields:
            assert entry["category"] == field_category(model, entry["name"])


# ── describe vs reference: one description of a column, two commands (D1-4) ────────────────────
# `describe <kind>` calls itself "the full machine description of one table kind" and is the command
# an author filling *one* table runs; `reference` is the whole-schema dump an MCP surface renders.
# Anything the second says about a column the first has to say too, or the per-table command is the
# one that quietly knows less. The concrete instance: `ELEMENT_RULE_MEANINGS` reached `reference`'s
# `vocabulary_notes` and nothing else, so `describe repeat_alleles.csv` printed `source_element`'s
# eight members with no way to tell which of them counts the reference element — the very question
# the vocabulary was added to answer.


def _column_vocabulary_facts(entry: dict) -> dict:
    """The vocabulary half of one column's description, however the surface spells the rest."""
    return {key: entry[key] for key in ("vocabulary", "options", "closed", "notes") if key in entry}


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_describe_carries_the_member_prose_the_whole_schema_reference_carries(kind: str) -> None:
    """A vocabulary's per-member prose must reach the per-table command, not only the whole-schema one.

    Anchored on `reference["vocabulary_notes"]`, which is where the prose already lived: for every
    vocabulary-bound column of every draftable kind, whatever that block says about the column's
    vocabulary is what `describe` must say about the column."""
    notes_by_vocabulary = authoring_reference()["vocabulary_notes"]
    for entry in describe_table(kind)["columns"]:
        expected = notes_by_vocabulary.get(entry.get("vocabulary"))
        if expected is None:
            continue
        assert entry.get("notes") == expected, f"{kind}:{entry['name']}"


def test_some_draftable_kind_actually_exercises_the_prose_path() -> None:
    """The parametrized guard above is vacuous for a kind whose columns carry no prose, and *every*
    kind would be vacuous if the prose came unbound at the marker — a green sweep saying nothing.

    Which kinds carry it is derived rather than listed: naming the four that bind `source_element`
    today is the hand-kept list this whole binding exists to abolish, and it goes stale on the fifth."""
    notes_by_vocabulary = authoring_reference()["vocabulary_notes"]
    assert notes_by_vocabulary, "no vocabulary carries per-member prose; the marker channel is dead"
    reached = {
        (kind, column["name"])
        for kind in DRAFTABLE
        for column in describe_table(kind)["columns"]
        if column.get("vocabulary") in notes_by_vocabulary
    }
    assert reached, "no draftable table binds a vocabulary that carries prose"


@pytest.mark.parametrize("kind", sorted(DRAFTABLE))
def test_the_two_descriptions_of_a_column_agree(kind: str) -> None:
    """And the general form: neither surface may know something about a column the other does not.

    `field_category` was the only cross-surface guard here, and it left the vocabulary half — the
    part a picker renders — unpinned in both directions."""
    model = model_for(kind)
    reference_entries = {f["name"]: f for f in authoring_reference()["models"][model.__name__]}
    for entry in describe_table(kind)["columns"]:
        mirror = reference_entries[entry["name"]]
        assert _column_vocabulary_facts(entry) == _column_vocabulary_facts(mirror), entry["name"]
        assert entry["required"] == mirror["required"]
        assert entry["category"] == mirror["category"]
