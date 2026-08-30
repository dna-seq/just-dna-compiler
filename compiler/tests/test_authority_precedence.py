"""`module_spec.yaml`'s `authority_precedence:` — a stance recorded, and computed with by nothing.

The one authored field RM134 adds, and the whole of its contract is a negative: it says whose
clinical call this module's curator weighted while deciding, and **no tier reads it to resolve
anything**. That is not an omission waiting to be filled in. With five authorities in a
two-against-three disagreement this order says one thing and a majority says another, and choosing
between those rules is a judgement about how rank trades against agreement count — a weighting model
this workspace has declined to invent three times.

So the tests below are shaped around proving an absence. A round trip of the field would prove only
that it survives; what has to be proved is that changing it changes *nothing else*: no verdict, no
ordering, no emitted row, neither identity half. The one thing it does move is `manifest.inputs[0]`,
because `module_spec.yaml` is byte-hashed — the same trade `weighting:` makes.
"""

from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_format.spec import ModuleSpecConfig
from pydantic import ValidationError

_BASE_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: rm134\n"
    "  title: RM134\n"
    "  description: whose call this curator weighted\n"
    "  report_title: RM134\n"
    "genome_build: GRCh38\n"
)

_VARIANTS = (
    "rsid,chrom,start,ref,alts,genotype,weight,state,conclusion,gene,clin_sig\n"
    "rs1800562,6,26092913,G,A,A/A,0.8,risk,C282Y homozygote,HFE,pathogenic\n"
    "rs334,11,5227002,T,A,A/T,0.5,risk,sickle trait,HBB,benign\n"
)

_STUDIES = "rsid,pmid\nrs1800562,16199547\n"


def _spec(directory: Path, order: list[str] | None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    block = ""
    if order is not None:
        block = "authority_precedence:\n" + "".join(f"  - {name}\n" for name in order)
    (directory / "module_spec.yaml").write_text(_BASE_YAML + block, encoding="utf-8")
    (directory / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    (directory / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    return directory


# ── the model ───────────────────────────────────────────────────────────────────────────────────


def test_the_vocabulary_is_open_because_authority_is_open_everywhere_else() -> None:
    """A deployment may weigh an authority this release has never heard of, and a closed set would
    make declaring that impossible rather than merely unusual."""
    module = {"name": "m", "title": "T", "description": "d", "report_title": "R"}
    config = ModuleSpecConfig(module=module, authority_precedence=["some_local_archive", "clinvar"])
    assert config.authority_precedence == ["some_local_archive", "clinvar"]


def test_absent_means_the_module_has_not_said() -> None:
    """An empty list, and it is not the claim that the curator weighted the authorities equally."""
    module = {"name": "m", "title": "T", "description": "d", "report_title": "R"}
    assert ModuleSpecConfig(module=module).authority_precedence == []


@pytest.mark.parametrize(
    ("order", "because"),
    [
        (["clinvar", ""], "an empty entry ranks nothing"),
        (["clinvar", "pubmind", "clinvar"], "two ranks for one authority is not an order"),
    ],
)
def test_a_list_that_is_not_an_order_is_refused(order: list[str], because: str) -> None:
    """The two refusals are about the list being an *order*, not about which authorities exist."""
    module = {"name": "m", "title": "T", "description": "d", "report_title": "R"}
    with pytest.raises(ValidationError):
        ModuleSpecConfig(module=module, authority_precedence=order)


# ── recorded ────────────────────────────────────────────────────────────────────────────────────


def test_the_order_reaches_the_manifest_verbatim(tmp_path: Path) -> None:
    """Machine-readable so a consumer can see the stance instead of inferring it by reading every
    contested row — which is the entire reason the field is worth an authored column's full price."""
    result = compile_module(_spec(tmp_path / "spec", ["pubmind", "clinvar"]), tmp_path / "out")
    assert result.success, result.errors
    assert result.manifest.authority_precedence == ["pubmind", "clinvar"]


def test_a_module_that_has_not_said_records_an_empty_list(tmp_path: Path) -> None:
    result = compile_module(_spec(tmp_path / "spec", None), tmp_path / "out")
    assert result.success, result.errors
    assert result.manifest.authority_precedence == []


# ── and computed with by nothing, which is the property that needs proving ───────────────────────


def test_reversing_the_order_changes_no_row_no_ordering_and_neither_identity_half(
    tmp_path: Path,
) -> None:
    """The claim in full, asserted against two compiles that differ **only** in this field.

    A round trip of the value would show it survives and nothing more. What has to hold is that the
    field is inert: the same parquet bytes, the same row order inside them, the same
    `content_signature` and the same `artifact.digest`. If anything ever starts resolving with this
    order, one of these four moves.
    """
    forward = compile_module(_spec(tmp_path / "a", ["clinvar", "pubmind"]), tmp_path / "oa")
    backward = compile_module(_spec(tmp_path / "b", ["pubmind", "clinvar"]), tmp_path / "ob")
    absent = compile_module(_spec(tmp_path / "c", None), tmp_path / "oc")
    assert forward.success and backward.success and absent.success

    digests = {
        forward.manifest.artifact.digest,
        backward.manifest.artifact.digest,
        absent.manifest.artifact.digest,
    }
    assert len(digests) == 1, "the order reached a parquet"
    signatures = {
        forward.manifest.content_signature,
        backward.manifest.content_signature,
        absent.manifest.content_signature,
    }
    assert len(signatures) == 1, "the order reached the authored content identity"

    # Byte equality over every artifact file, which is the ordering claim as well as the value one:
    # parquet bytes depend on row order, so an emitted row that moved would show up here.
    for entry in forward.manifest.artifact.files:
        first = (tmp_path / "oa" / entry.name).read_bytes()
        second = (tmp_path / "ob" / entry.name).read_bytes()
        third = (tmp_path / "oc" / entry.name).read_bytes()
        assert first == second == third, entry.name


def test_declaring_the_order_still_moves_the_input_hash(tmp_path: Path) -> None:
    """The other side of the same coin, and the one an author will notice: `module_spec.yaml` is
    byte-hashed into `manifest.inputs[0]`, and the RM45 attestation binds the same set — so a module
    that was `close`d before adopting the field has to be re-closed. Existing modules are unaffected
    only because they do not adopt it."""
    with_order = compile_module(_spec(tmp_path / "a", ["clinvar"]), tmp_path / "oa")
    without = compile_module(_spec(tmp_path / "b", None), tmp_path / "ob")
    a = next(f for f in with_order.manifest.inputs if f.name == "module_spec.yaml")
    b = next(f for f in without.manifest.inputs if f.name == "module_spec.yaml")
    assert a.sha256 != b.sha256


def test_no_warning_or_error_mentions_the_field(tmp_path: Path) -> None:
    """Nothing consults it, so nothing may complain about it — including a module whose declared
    order names an authority the check never asks about. A gate reading this field would be the
    weighting model the item refused."""
    spec = _spec(tmp_path / "spec", ["an_authority_no_check_consults"])
    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors
    assert not [w for w in result.warnings if "authority_precedence" in w]
    check = validate_spec(spec, strict=True)
    assert check.valid, check.errors
    assert not [w for w in check.warnings if "authority_precedence" in w]


def test_reverse_drops_it_and_the_result_still_compiles(tmp_path: Path) -> None:
    """Same class as `weighting:`/`authorship:`/`license:`, and dropped for the same reason:
    `reverse_module` rebuilds the spec from the parquets, this reaches no parquet, and inventing a
    default would author a methodological claim no human made."""
    spec = _spec(tmp_path / "spec", ["clinvar", "pubmind"])
    first = compile_module(spec, tmp_path / "a1")
    assert first.success, first.errors
    assert first.manifest.authority_precedence == ["clinvar", "pubmind"]

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    assert "authority_precedence" not in (tmp_path / "rev" / "module_spec.yaml").read_text()
    check = validate_spec(tmp_path / "rev")
    assert check.valid, check.errors
