"""`module_spec.yaml`'s `weighting:` block — what a module's `weight` column means (0.6, RM92).

`VariantRow.weight` is the one magnitude in the format with no unit beside it: `effect_size` has
`effect_measure`, `weight` has "Score (positive=protective)" and nothing else. A consumer reported the
consequence — across a corpus the weights "construct nonsense", because every module means something
different by the column and the artifact cannot say so (S36).

Three free-text strings, advisory, manifest-only. The tests below pin the four properties that make
that legal and useful: it reaches the manifest **verbatim**, it moves **neither** identity half, an
unknown key is **refused** rather than silently ignored, and `reverse_module` **drops** it.

That last one is the interesting test. `license`, `panel` and `authorship` behave identically and
**nothing in the suite pins any of them** — the behaviour is documented in three field descriptions
and asserted nowhere, so the round trip could start re-emitting one and no test would notice. Written
here for the new block rather than left to the same gap.
"""

from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_format.manifest import Weighting
from just_dna_format.spec import ModuleSpecConfig
from pydantic import ValidationError

_BASE_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: rm92\n"
    "  title: RM92\n"
    "  description: what this module's weights mean\n"
    "  report_title: RM92\n"
    "genome_build: GRCh38\n"
)

_WEIGHTING_YAML = (
    "weighting:\n"
    "  scale: '0-1, curator-set, arbitrary'\n"
    "  method: 'literature triage; no GWAS input'\n"
    "  note: 'not comparable across modules'\n"
)

_VARIANTS = (
    "rsid,chrom,start,ref,alts,genotype,weight,state,conclusion,gene\n"
    "rs1800562,6,26092913,G,A,A/A,0.8,risk,C282Y homozygote,HFE\n"
)

_STUDIES = "rsid,pmid\nrs1800562,16199547\n"


def _spec(directory: Path, *, weighting: bool) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module_spec.yaml").write_text(
        _BASE_YAML + (_WEIGHTING_YAML if weighting else "")
    )
    (directory / "variants.csv").write_text(_VARIANTS)
    (directory / "studies.csv").write_text(_STUDIES)
    return directory


# ── the model ───────────────────────────────────────────────────────────────────────────────────


def test_every_field_is_optional_and_free_text() -> None:
    """No vocabulary, no validator beyond the type. An empty block is legal — a module may say
    "I have not decided" by writing nothing, which is the tri-state reading of an absent key."""
    assert Weighting().scale is None
    assert Weighting(scale="whatever the curator felt").scale == "whatever the curator felt"


def test_an_unknown_key_in_the_block_is_refused() -> None:
    """`extra="forbid"`, like every other authored block. A typo'd `scale:` that silently did nothing
    would leave the module claiming a scale it has not stated — worse than not having the block."""
    with pytest.raises(ValidationError):
        Weighting(scal="0-1")


def test_the_block_is_rejected_at_the_top_level_when_misspelled() -> None:
    """`ModuleSpecConfig` forbids extras too, so `wieghting:` is a hard error rather than a no-op."""
    with pytest.raises(ValidationError):
        ModuleSpecConfig.model_validate(
            {
                "module": {
                    "name": "x",
                    "title": "X",
                    "description": "d",
                    "report_title": "X",
                },
                "wieghting": {"scale": "0-1"},
            }
        )


# ── the compile path ────────────────────────────────────────────────────────────────────────────


def test_the_block_reaches_the_manifest_verbatim(tmp_path: Path) -> None:
    spec = _spec(tmp_path / "spec", weighting=True)
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    block = result.manifest.weighting
    assert block is not None
    assert block.scale == "0-1, curator-set, arbitrary"
    assert block.method == "literature triage; no GWAS input"
    assert block.note == "not comparable across modules"


def test_absent_means_absent_not_a_default(tmp_path: Path) -> None:
    """`None`, never an empty `Weighting()`. "The module has not said" and "the module said nothing
    in particular" are different claims, and only the first is true of a module without the block."""
    spec = _spec(tmp_path / "spec", weighting=False)
    result = compile_module(spec, tmp_path / "out")
    assert result.success, result.errors
    assert result.manifest.weighting is None


def test_the_block_moves_neither_identity_half(tmp_path: Path) -> None:
    """The property that makes it the cheapest legal class of addition.

    `artifact.digest` hashes the parquets and this reaches none of them; `content_signature` excludes
    the identity/display half of `module_spec.yaml` by design. So two modules differing only by this
    block are the same content **and** the same bytes — which is right: it describes the weights, it
    is not one of them.
    """
    with_block = compile_module(_spec(tmp_path / "a", weighting=True), tmp_path / "oa")
    without = compile_module(_spec(tmp_path / "b", weighting=False), tmp_path / "ob")
    assert with_block.success and without.success, (with_block.errors, without.errors)
    assert with_block.manifest.artifact.digest == without.manifest.artifact.digest
    assert with_block.manifest.content_signature == without.manifest.content_signature


def test_adopting_the_block_changes_the_input_hash(tmp_path: Path) -> None:
    """The other side of the same coin, and the one an author will actually notice.

    `module_spec.yaml` is byte-hashed into `manifest.inputs[0]`, so adding the block **does** move
    that entry — and the RM45 attestation binds the same set, so a module that was `close`d before
    adopting the block has to be re-closed. Existing modules are unaffected only because they do not
    adopt it; this is not a free edit for one that does.
    """
    with_block = compile_module(_spec(tmp_path / "a", weighting=True), tmp_path / "oa")
    without = compile_module(_spec(tmp_path / "b", weighting=False), tmp_path / "ob")
    a = next(f for f in with_block.manifest.inputs if f.name == "module_spec.yaml")
    b = next(f for f in without.manifest.inputs if f.name == "module_spec.yaml")
    assert a.sha256 != b.sha256


# ── the round trip ──────────────────────────────────────────────────────────────────────────────


def test_reverse_drops_the_block_and_the_result_still_compiles(tmp_path: Path) -> None:
    """Documented in the field description as "the same class as `panel`/`authorship`/`license`",
    and pinned here because none of those three is pinned anywhere.

    Dropping it is a real loss and the right one: `reverse_module` rebuilds the spec from the
    parquets, and this block reaches no parquet, so there is nothing to rebuild it from. Inventing a
    default would author a claim about the weights that no human made.
    """
    spec = _spec(tmp_path / "spec", weighting=True)
    first = compile_module(spec, tmp_path / "a1")
    assert first.success, first.errors
    assert first.manifest.weighting is not None

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    reversed_yaml = (tmp_path / "rev" / "module_spec.yaml").read_text()
    assert "weighting" not in reversed_yaml

    check = validate_spec(tmp_path / "rev")
    assert check.valid, check.errors


def test_the_loss_does_not_break_the_fixed_point(tmp_path: Path) -> None:
    """compile → reverse → compile → reverse → compile. Stable from the second lap.

    The corpus sweep compares *signatures*, not the reversed spec against the original, so a
    manifest-only field going missing cannot break it — but that is a property worth asserting rather
    than inferring, since it is the reason this block is safe to put in a reference example at all.
    """
    spec = _spec(tmp_path / "spec", weighting=True)
    first = compile_module(spec, tmp_path / "a1")
    reverse_module(tmp_path / "a1", tmp_path / "rev1")
    second = compile_module(tmp_path / "rev1", tmp_path / "a2")
    reverse_module(tmp_path / "a2", tmp_path / "rev2")
    third = compile_module(tmp_path / "rev2", tmp_path / "a3")

    assert first.success and second.success and third.success
    assert second.manifest.artifact.digest == third.manifest.artifact.digest
    assert second.manifest.content_signature == third.manifest.content_signature
    # And the digest never moved in the first place, because the block is outside it.
    assert first.manifest.artifact.digest == second.manifest.artifact.digest
