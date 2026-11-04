"""The refusals only `strict` adds are told apart by a published phrase, never by a guess (RM377, S129).

`ValidationResult.errors` and `CompilationResult.errors` are `list[str]` with no code, so a consumer that
grades a spec has to read an error's words to know which refusal it is. Two errors exist only under
`strict` (RM218 corrected the docstring that said `strict` changes severity only): the unresolved-position
aggregate and the recorded build disagreement. A registry grading a dry run treats them differently, and
the only handle it had was wording nothing promised to keep.

The phrases are now API, published in COMPILER.md's *Warning texts a consumer keys on*. This file reads
them **from that table** rather than restating them, so the document and the guard cannot drift apart,
and asserts three things:

- every error the code opens with `strict compile:` carries exactly one documented phrase, walked off the
  package source, so a third strict-only refusal fails here until it is published;
- each documented phrase is what both entry points return, and only for its own case;
- `strict compile:` opens nothing else, so the prefix alone says *a refusal `strict` added*.

Codes for errors are RM378, a minor; this is the patch half that holds until then.
"""

import ast
import re
from pathlib import Path

import just_dna_compiler
import pytest
from just_dna_compiler.compiler import BUILD_AGREEMENT_CHECK, compile_module, validate_spec
from just_dna_enricher.verification import record_verification
from just_dna_format.manifest import VerificationRecord

_ROOT = Path(__file__).resolve().parents[2]
_DOC = _ROOT / "docs" / "COMPILER.md"
_SECTION = "### The refusals only `strict` adds"
_PREFIX = "strict compile: "

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: refusal\n"
    "  title: Refusal\n"
    "  description: d\n"
    "  report_title: Refusal\n"
    "genome_build: GRCh38\n"
)


def _documented() -> dict[str, str]:
    """`{finding: phrase}` from the table under `_SECTION`: first column the finding, second the phrase."""
    text = _DOC.read_text(encoding="utf-8")
    start = text.index(_SECTION)
    end = text.find("\n#", start + len(_SECTION))
    rows = {}
    for line in text[start : end if end != -1 else None].splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not cells[1].startswith("`") or set(cells[0]) <= {"-", " "}:
            continue
        rows[cells[0].strip("`")] = cells[1].strip("`")
    return rows


def _emitted_texts() -> list[str]:
    """Every string literal in the compiler package that opens with `_PREFIX`, its f-string holes as `{}`.

    Walked off the source rather than listed, so a strict-only refusal written tomorrow is in this set the
    day it is written, wherever the package's modules are split.
    """
    found = []
    for path in sorted(Path(just_dna_compiler.__file__).parent.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # An f-string's literal pieces are `Constant` nodes of their own, and the first piece opens with the
        # prefix too; read each f-string whole, once, and never its pieces.
        pieces = {id(v) for n in ast.walk(tree) if isinstance(n, ast.JoinedStr) for v in n.values}
        for node in ast.walk(tree):
            if id(node) in pieces:
                continue
            if isinstance(node, ast.JoinedStr):
                text = "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
            else:
                continue
            if text.startswith(_PREFIX):
                found.append(text)
    return found


def _unresolved_spec(d: Path) -> Path:
    """An rsID-only row and nothing injected to place it, which is the aggregate's case.

    Resolution stays on (the default): with it off, `main`'s pre-flight passes what the compile refuses,
    a parity gap the `0.8` line closes as RM367, and this file is about the phrase, not that gap.
    """
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (d / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene\nrs1801133,A/G,risk,MTHFR risk,MTHFR\n", encoding="utf-8"
    )
    (d / "studies.csv").write_text("rsid,pmid\nrs1801133,9545397\n", encoding="utf-8")
    return d


def _build_spec(d: Path) -> Path:
    """A GRCh37 coordinate in a GRCh38 module, with the enricher's finding recorded (S78's case)."""
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (d / "variants.csv").write_text(
        "rsid,chrom,start,ref,alts,genotype,state,conclusion\n"
        "rs61849494,10,51613269,G,A,A/G,alt,Pasted verbatim from a GRCh37 paper.\n",
        encoding="utf-8",
    )
    (d / "studies.csv").write_text("rsid,pmid\nrs61849494,12345678\n", encoding="utf-8")
    (d / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
        "10:51613269:G:A,rs61849494,10,51613269,G,A,GRCh38,0,ensembl-rest,resolved\n",
        encoding="utf-8",
    )
    record = VerificationRecord(
        check=BUILD_AGREEMENT_CHECK, subjects=1, findings=1, source="ensembl-grch37", detail="10:51613269"
    )
    record_verification([record], d, error=RuntimeError)
    return d


#: The case that provokes each documented finding. Keyed by the finding's name in the table, and compared
#: to the table by equality, so a row published without a case here, or a case for an unpublished row,
#: fails.
_CASES = {
    "unresolved_positions": (_unresolved_spec, {}),
    "genome_build_disagreement": (_build_spec, {}),
}


def test_the_table_names_exactly_the_cases_this_file_provokes() -> None:
    assert set(_documented()) == set(_CASES)


def test_every_strict_compile_error_in_the_source_carries_exactly_one_published_phrase() -> None:
    phrases = list(_documented().values())
    texts = _emitted_texts()
    assert texts, "no `strict compile:` literal found; the walk is reading the wrong package"
    for text in texts:
        # Implicit concatenation is merged by the parser, so a refusal wrapped over several lines is one
        # node here; only the line breaks inside it differ from the published phrase.
        matching = [p for p in phrases if _skeleton(p) in _skeleton(text)]
        assert len(matching) == 1, f"{text[:120]!r} carries {len(matching)} published phrase(s), not one"
    for phrase in phrases:
        assert any(_skeleton(phrase) in _skeleton(t) for t in texts), (
            f"{phrase!r} is published and emitted nowhere"
        )


def _skeleton(text: str) -> str:
    """Whitespace collapsed, so a phrase the source wraps across two f-string pieces still compares."""
    return re.sub(r"\s+", " ", text).strip()


@pytest.mark.parametrize("finding", sorted(_CASES))
def test_both_entry_points_refuse_with_the_published_phrase_and_only_their_own(
    finding: str, tmp_path: Path
) -> None:
    documented = _documented()
    build, kwargs = _CASES[finding]
    spec = build(tmp_path / "spec")

    validated = validate_spec(spec, strict=True, **kwargs)
    compiled = compile_module(spec, tmp_path / "out", strict=True, **kwargs)

    for errors in (validated.errors, compiled.errors):
        strict_only = [e for e in errors if e.startswith(_PREFIX)]
        assert len(strict_only) == 1, errors
        carried = {name for name, phrase in documented.items() if phrase in strict_only[0]}
        assert carried == {finding}, strict_only[0]


def test_the_prefix_opens_nothing_without_strict(tmp_path: Path) -> None:
    """`strict compile:` means *a refusal `strict` added*, so best-effort never says it, in any list."""
    for finding, (build, kwargs) in _CASES.items():
        spec = build(tmp_path / finding)
        validated = validate_spec(spec, **kwargs)
        compiled = compile_module(spec, tmp_path / f"{finding}-out", **kwargs)
        said = [*validated.errors, *validated.warnings, *compiled.errors, *compiled.warnings]
        assert not [m for m in said if m.startswith(_PREFIX)], finding
