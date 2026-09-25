"""The genome build a spec declares, read without compiling it: `spec_genome_build` and
`source_build_mismatch` (RM260 split this out of the former single-file `enrich.py`).
"""

from pathlib import Path

import yaml
from just_dna_compiler.compiler import SpecError, load_spec
from just_dna_format.spec import ModuleSpecConfig
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER
from pydantic import ValidationError

from just_dna_enricher.enrich.outcome import EnrichmentError


def spec_genome_build(spec_dir: Path) -> str:
    """The build the module itself declares, which is the only build enrichment may resolve against.

    `enrich()` took `genome_build` as a plain parameter defaulting to `"GRCh38"` and **nothing ever
    passed it** — no CLI flag, no caller — so the GRCh38 gate on every link below was unreachable and a
    `genome_build: GRCh37` module was resolved against GRCh38 Ensembl, its GRCh38 coordinates written
    into `resolution.csv` labelled `GRCh38`, and GRCh38 VRS ids minted for them. The compiler then
    (correctly) refused to use any of it. The guard existed; the value never arrived — the same shape as
    the `VariantRow` re-stamp bug, where a `build` parameter and its fall-through both existed and were
    never reached.

    A spec with no `module_spec.yaml` gets the format's own default. That is not a guess: `enrich` is
    routinely pointed at a bare table directory in tests and by hand, and `ModuleSpecConfig.genome_build`
    defaults to `"GRCh38"`, so this returns what compiling that directory would assume. A spec whose
    yaml is *present but unreadable* is a different case and raises — enrichment writes facts into that
    directory, and picking a build for a module whose declaration cannot be read is exactly the
    invention this function exists to remove.
    """
    path = spec_dir / "module_spec.yaml"
    if not path.exists():
        return "GRCh38"
    # Through the public loader since S74 — this call site is what made the case that one was needed,
    # since the workspace's own network tier was reaching into `_load_yaml`. It already raised on the
    # `None` half of the tuple, which is `load_spec`'s contract, so the translation is the only thing
    # left here: a pass owes its caller its own exception type.
    try:
        return load_spec(path).genome_build
    except SpecError as exc:
        # **Guard at the answerer (S103).** The question is the build, and a scaffold's unfilled
        # `title:` says nothing about it — yet `load_spec` validates the whole file, so `scaffold`
        # followed by `draft`, the reference README's own recipe, refused on `<<REPLACE>>` in three
        # fields the draft never reads. Only that one defect is looked past, and only outside the
        # build cell: a typo'd key, a wrong type, or a placeholder *in* `genome_build` still refuses,
        # because reading the default past those would reopen the `genome_bild:` hole the model's
        # `extra="forbid"` closed.
        declared, residual = _declared_build_behind_placeholders(path)
        if declared is not None:
            return declared
        # No `pass genome_build=` remedy in this sentence: that parameter belongs to `enrich()` alone,
        # and the drafters that share this reader have no such flag to offer. `residual` is the
        # diagnosis that remains once the stubs are looked past — the placeholder guard runs first
        # and would otherwise hide a `genome_bild:` behind "fill in the title".
        raise EnrichmentError(
            f"cannot read the module's genome_build: {residual or exc}. Enrichment resolves against "
            f"one assembly and records the answer under the module's declared build, so it will not "
            f"choose one for you — fix module_spec.yaml."
        ) from exc


def _declared_build_behind_placeholders(path: Path) -> tuple[str | None, str | None]:
    """The build a scaffolded, not-yet-filled `module_spec.yaml` declares, and the residual diagnosis.

    `(build, None)` when the file validates once its template stubs are filled. `(None, reason)`
    when a problem *other* than unfilled cells remains — a key the model refuses, a wrong type, a
    placeholder in `genome_build` itself — with `reason` naming it, since the placeholder guard runs
    first and its sentence would otherwise hide the real one. `(None, None)` when the file has no
    stubs at all (nothing to look past), is unparsable, or is not a mapping: the caller's own
    diagnosis already says so. The test is exact rather than a reading of the error text: every
    placeholder outside the build cell is replaced by a filler and the model is asked again, so what
    is tolerated is precisely "this file validates once the scaffold's stubs are filled".
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None, None
    if not isinstance(raw, dict):
        return None, None
    filled, replaced = _fill_placeholders({k: v for k, v in raw.items() if k != "genome_build"})
    if not replaced:
        return None, None
    if "genome_build" in raw:
        filled["genome_build"] = raw["genome_build"]
    try:
        return ModuleSpecConfig.model_validate(filled).genome_build, None
    except ValidationError as exc:
        residual = "; ".join(
            f"module_spec.yaml [{' → '.join(str(x) for x in err['loc'])}]: {err['msg']}"
            for err in exc.errors()
        )
        return None, residual


def _fill_placeholders(value: object) -> tuple[object, bool]:
    """A copy of `value` with every `TEMPLATE_PLACEHOLDER` string leaf replaced, and whether any was."""
    if isinstance(value, dict):
        out: dict[str, object] = {}
        hit = False
        for key, item in value.items():
            out[key], one = _fill_placeholders(item)
            hit = hit or one
        return out, hit
    if isinstance(value, list):
        items = [_fill_placeholders(item) for item in value]
        return [item for item, _ in items], any(one for _, one in items)
    if value == TEMPLATE_PLACEHOLDER:
        return "filled", True
    return value, False


def source_build_mismatch(spec_dir: Path, source: str, source_build: str = "GRCh38") -> str | None:
    """A warning when a drafting provider is about to write `source_build` coordinates into a module
    that declares a different one — or `None` when the builds agree.

    **The gap this closes is that `spec_genome_build` had exactly one caller.** It was written for the
    bug where "the guard existed; the value never arrived", and then `draft`, `draft-panel` and
    `draft-clinpgx` all shipped without asking it. Every source these providers read serves GRCh38 —
    CPIC's `allele_definitions`, the ClinVar snapshot, the ClinPGx annotations — so drafting into a
    `genome_build: GRCh37` module writes `10,94942290` for `rs1799853`, whose GRCh37 position is
    `96702047`, and nothing anywhere says a word. The compiler cannot catch it: a coordinate is legal
    on either build, it is simply a different place. The whole point of `reference_examples/grch37_build`
    is that this family of defect is *silent by construction*, and this is its ninth instance.

    **Reported, not repaired, and not refused.** The provider still writes the row: refusing would
    make the three drafting commands unusable on a non-GRCh38 module rather than merely
    unhelpful, and stripping the coordinate to leave an rsid-only row is a *different* row than the
    author asked for — both are design decisions with real trade-offs, and the enricher's standing
    rule is that a pass which finds a disagreement says so and changes nothing. Which of the two the
    providers should eventually do is filed rather than decided here.

    Returns `None` for the agreeing case, which is nearly every call — the house tri-state applies to
    the *answer*, and "the builds agree" is not a finding.
    """
    declared = spec_genome_build(spec_dir)
    if declared == source_build:
        return None
    return (
        f"{source} publishes {source_build} coordinates and this module declares "
        f"genome_build={declared!r}: every chrom/start drafted below names a {source_build} position, "
        f"recorded as though it were {declared}. Nothing downstream can detect this — a coordinate is "
        f"valid on either assembly, it is simply a different base — so either re-declare the module as "
        f"{source_build}, or delete the drafted coordinates and keep the rsIDs, which name a variant "
        f"without naming an assembly (`just-dna-enricher hint recover` converts in that direction)."
    )
