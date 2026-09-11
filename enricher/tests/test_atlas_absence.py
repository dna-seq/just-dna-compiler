"""Two ways to have no Atlas client, and they must not be given one instruction.

Reported through S98's neighbourhood: a wheel user missing the `[atlas]` extra was told to install it
**and** run `just-dna-enricher atlas generate`, followed the second half, and hit "grpcio-tools is not
installed" — a third error about a fourth thing, when their fix was one `pip install`.
`@specific-rejection`: a generic rejection is a dead end where a specific one is a fix.

The discriminator lives in `atlas_protos` rather than `atlas_client`, because `atlas_client` is the
module that fails to import and so cannot be asked why. That placement is asserted here too: this
file must be able to answer the question on a checkout where the thing it describes is missing.
"""

import ast
import importlib.util

import pytest
from just_dna_enricher import atlas_protos
from just_dna_enricher.atlas_protos import OUT_DIR, STAGE_PREFIX, client_absence


def test_the_discriminator_is_importable_without_the_thing_it_describes() -> None:
    """Stdlib only. A module that needed `grpc` to say `grpc` is missing would be useless.

    Walked as an AST rather than grepped: the first version of this test asserted
    `"import grpc" not in source` and failed on the phrase *grpcio-tools* inside a docstring, which
    is the substring trap `@enumerate-shapes-not-type-sets` is about — a text search cannot tell a
    statement from a sentence describing one.
    """
    tree = ast.parse((OUT_DIR.parent / "atlas_protos.py").read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert "grpc" not in imported, f"the discriminator must not need what it reports on: {imported}"
    assert "just_dna_enricher" not in imported, "and must not reach back into the package it guards"


def test_a_present_install_has_no_absence_to_report() -> None:
    """This checkout has both halves, so the honest answer is `None` rather than a sentence."""
    assert (OUT_DIR / STAGE_PREFIX / "atlas_service_pb2.py").is_file(), "fixture premise"
    assert client_absence() is None


def test_a_missing_extra_names_pip_and_explicitly_warns_off_the_generator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reported failure, as the test that would have caught it.

    Not merely "says pip": it must also tell the reader **not** to run the generator, because the
    instruction they were given is the one they will otherwise repeat.
    """
    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda n, *a, **k: None if n == "grpc" else real(n, *a, **k)
    )
    reason = client_absence()
    assert reason is not None
    assert "pip install" in reason and "[atlas]" in reason
    assert "Do NOT run" in reason and "atlas generate" in reason


def test_missing_bindings_names_the_generator_and_says_a_checkout_is_required(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """The other arm: `grpc` imports, the generated package does not exist.

    It must say **checkout**, because the generator needs `grpcio-tools` and the upstream pins, and a
    wheel has neither — so a wheel reporting this is a packaging bug rather than something a user can
    generate their way out of (RM196).
    """
    monkeypatch.setattr(atlas_protos, "OUT_DIR", tmp_path / "nothing-generated-here")
    reason = client_absence()
    assert reason is not None
    assert "atlas generate" in reason and "checkout" in reason
    assert "pip install" not in reason, "this arm must not send the reader to the other remedy"


def test_the_two_reasons_are_pairwise_distinct(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """A verdict function with several arms owes a reason function with the same arms, pairwise
    distinct (`@answered-is-not-absent`). Folding them is exactly the defect this file is about."""
    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda n, *a, **k: None if n == "grpc" else real(n, *a, **k)
    )
    no_extra = client_absence()
    monkeypatch.undo()
    monkeypatch.setattr(atlas_protos, "OUT_DIR", tmp_path / "nothing-generated-here")
    no_bindings = client_absence()
    assert no_extra != no_bindings
    assert client_absence.__doc__ and "two" in client_absence.__doc__.lower()


def test_the_pass_reports_the_specific_reason_rather_than_both_remedies(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """End to end through `enrich_expression`, which is where the consumer met it."""
    from just_dna_enricher import expression as expression_module
    from just_dna_enricher.expression import ExpressionError, enrich_expression

    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(
        'schema_version: "1.0"\nmodule:\n  name: t\n  title: T\n  description: d\n'
        "  report_title: T\ngenome_build: GRCh38\n"
    )
    monkeypatch.setattr(expression_module, "ATLAS_CLIENT_AVAILABLE", False)
    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda n, *a, **k: None if n == "grpc" else real(n, *a, **k)
    )
    with pytest.raises(ExpressionError) as caught:
        enrich_expression(
            spec,
            "TBX1",
            chrom="22",
            start=1,
            end=2,
            declared_use="non_commercial",
            mane_cache=spec / "none",
        )
    assert "pip install" in str(caught.value)
    assert "Do NOT run" in str(caught.value)


def test_no_other_module_invents_its_own_version_of_this_sentence() -> None:
    """One voice, walked rather than remembered (`@registry-completeness`).

    Three sites folded the two absences independently — `expression`, `cli` and `alphagenome_check`
    — which is what a rule kept in prose gets you. This fails on the fourth: any module that names
    both remedies in one string is composing its own answer instead of asking `client_absence()`.

    `atlas_protos` is exempt because it is where the two sentences live, and `atlas_client` because
    its own `ImportError` is the bindings-arm message that `client_absence` defers to.

    **`help=` strings are exempt, and the distinction is the rule rather than a carve-out.** The
    `atlas` command group's help describes the surface — the extra is needed, the bindings are
    generated once per checkout — and naming both there is correct, because it is explaining how the
    thing works to someone who has not failed yet. An *error* names the one remedy that applies to
    the failure in hand. This guard found that line on its first run, which is the difference between
    a walked rule and a remembered one.
    """
    package = OUT_DIR.parent
    offenders = []
    for path in sorted(package.glob("*.py")):
        if path.name in {"atlas_protos.py", "atlas_client.py"}:
            continue
        tree = ast.parse(path.read_text())
        described: set[int] = set()
        for node in ast.walk(tree):
            for keyword in getattr(node, "keywords", []):
                if keyword.arg == "help":
                    described.update(
                        child.lineno
                        for child in ast.walk(keyword.value)
                        if isinstance(child, ast.Constant) and isinstance(child.value, str)
                    )
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
                if "[atlas]" in text and "atlas generate" in text and node.lineno not in described:
                    offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, (
        "these name both remedies in one string, which sends half the readers to the wrong one — "
        f"ask `client_absence()` instead: {offenders}"
    )
