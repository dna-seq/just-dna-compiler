"""Scaffolding — create a module's authored files from nothing, refusing to touch what exists (0.5).

The de-novo half of the authoring story, beside `draft`'s append-into-an-existing-table half. Nothing
generated `module_spec.yaml` before this: every example and test in the repo hand-wrote one, which is
the same "copy a shape out of the docs" that `blank_template` exists to abolish for CSVs.

Pure and offline (Principle 2) — it writes only into the spec directory it is given, and only files
that are not already there.

**Refusal is file-level here, and row-level in `draft` — the difference is derivable, not stipulated.**
`draft`'s docstring rejects file-level refusal because it "self-defuses after the first gene": you
re-run an append per gene, so refusing a file that exists would make a multi-gene module unbuildable.
Scaffolding has no such re-run: you create a module's tables once. And row-level refusal presupposes a
natural key that decides sameness, which a stub row does not have — its key columns *are* the
placeholder. What it does share with `draft` is the definition of absent: a zero-byte file (a bare
`touch`) counts as not there, so the two never disagree about whether a file exists.

Refusal is also **per file, not per run**: an existing `variants.csv` must not stop a `pgs.csv` from
being scaffolded into the same module, or a module could never gain a second table kind.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from just_dna_format.base import authored_field_names
from just_dna_format.spec import ModuleSpecConfig
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER
from pydantic import BaseModel

from just_dna_compiler.compiler import _TABLE_KIND_CSVS
from just_dna_compiler.draft import field_category, model_for, stub_template

logger = logging.getLogger(__name__)

#: The spec file every module has.
MODULE_SPEC = "module_spec.yaml"

#: Table kinds that drag another kind in with them, so a scaffold is never invalid for a reason
#: unrelated to the stubs the author was asked to fill. Pinned against the compiler's real rules by a
#: test rather than trusted.
#:
#: The pair is **symmetric, and both halves were found by that test**: `variants.csv` without
#: `studies.csv` fails with "Grounding evidence is mandatory", and `studies.csv` alone fails with
#: "module has no recognized table" — evidence about nothing is as incomplete as a claim with no
#: evidence. One level only, not transitive: each side pulls in the other exactly once.
#:
#: **One half is conditional, and reading this dict alone gets it wrong (S49).** `studies.csv` needs
#: `variants.csv` only when it is *literally* alone, which is what its half of the comment above
#: always said — but the pull was applied unconditionally, so
#: `scaffold_module(kinds=["copynumbers.csv", "studies.csv"])` invited an empty `variants.csv` into a
#: module that compiles strict-green without one. RM47 made a study row legal with no variant identity,
#: precisely so a binning module can ground its thresholds, and that is the *intended* shape. Ask
#: `companions_for()` rather than this mapping: it applies the condition, and it is what
#: `scaffold_module` itself uses.
COMPANION_KINDS: dict[str, tuple[str, ...]] = {
    "variants.csv": ("studies.csv",),
    "studies.csv": ("variants.csv",),
}

#: What actually satisfies the compiler's composition rule — `variants.csv` **or** at least one table
#: kind (`compiler`: `if not has_variants and not kind_row_counts`). Derived from the compiler's own
#: tuple, so a table kind added in a future release counts here without an edit; `sources.csv` is
#: deliberately absent, being a licence ledger rather than a table a module can consist of.
_RECOGNIZED_TABLES: frozenset[str] = frozenset(_TABLE_KIND_CSVS) | {"variants.csv"}


def companions_for(kinds: Sequence[str]) -> list[str]:
    """The kinds to scaffold *beside* those asked for, with `COMPANION_KINDS`' conditional half applied.

    Public because a consumer passing the raw mapping through answers a question it cannot answer
    alone, and would then contradict its own composition advice: never add an empty table to keep
    another company (S49).

    `variants.csv` still pulls `studies.csv` unconditionally — that direction has no condition, since
    the compiler requires grounding evidence for a variant claim however the module is composed.
    `studies.csv` pulls `variants.csv` **only when nothing else recognised was requested**, which is
    the "alone" its own justification always named: beside a binning table the studies row grounds the
    bins through `pmid` and the module needs no variant at all.
    """
    requested = list(dict.fromkeys(kinds))
    grounded_by_another_table = bool(_RECOGNIZED_TABLES & set(requested))
    companions: list[str] = []
    for kind in requested:
        for companion in COMPANION_KINDS.get(kind, ()):
            if companion in requested or companion in companions:
                continue
            if kind == "studies.csv" and grounded_by_another_table:
                continue
            companions.append(companion)
    return companions


@dataclass
class ScaffoldPlan:
    """What a scaffold run created, and what it refused to touch."""

    spec_dir: Path
    created: list[Path] = field(default_factory=list)
    refused: list[tuple[Path, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    written: bool = False

    def __str__(self) -> str:
        verb = "created" if self.written else "to create"
        return f"{self.spec_dir}: {len(self.created)} {verb}, {len(self.refused)} left untouched"


def _exists(path: Path) -> bool:
    """Absent means missing *or* zero-byte — the same rule `draft.append_rows` applies."""
    return path.exists() and path.stat().st_size > 0


def _stub_value(model: type[BaseModel], name: str) -> Any:
    """The scaffold cell for one field of a YAML block, by the same three-way split the CSVs use."""
    category = field_category(model, name)
    if category == "required":
        return TEMPLATE_PLACEHOLDER
    return model.model_fields[name].get_default(call_default_factory=True)


def module_spec_template(*, name: str | None = None) -> str:
    """A `module_spec.yaml` skeleton generated from the live models.

    Required scalars carry the placeholder, so the file cannot compile until a human has filled them;
    defaulted ones carry their real default, so the author sees the values that will apply. Optional
    blocks (`panel`, `license`) are left out entirely rather than emitted empty — `panel: null` would
    fail typing, and an empty `authorship: []` would quietly claim the module has no authors.
    """
    spec: dict[str, Any] = {}
    for field_name in ModuleSpecConfig.model_fields:
        category = field_category(ModuleSpecConfig, field_name)
        if category == "optional":
            continue
        annotation = ModuleSpecConfig.model_fields[field_name].annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            spec[field_name] = {
                inner: _stub_value(annotation, inner)
                for inner in authored_field_names(annotation)
                if field_category(annotation, inner) != "optional"
            }
        else:
            value = _stub_value(ModuleSpecConfig, field_name)
            # An empty collection default is dropped rather than emitted: `authorship: []` is valid
            # but states "this module has no contributors", which is a claim, not a starting point.
            # The author adds the block when there is someone to name (RM14).
            if isinstance(value, (list, dict, tuple)) and not value:
                continue
            spec[field_name] = value
    if name is not None and isinstance(spec.get("module"), dict):
        spec["module"]["name"] = name
    return yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, default_flow_style=False)


def scaffold_module(
    spec_dir: Path,
    *,
    kinds: Sequence[str] = (),
    name: str | None = None,
    rows: int = 1,
    dry_run: bool = False,
) -> ScaffoldPlan:
    """Create `module_spec.yaml` plus a stub CSV per requested kind, skipping whatever exists.

    Never overwrites, never deletes, never edits: an existing file is reported and left byte-for-byte
    alone. `dry_run` reports the same plan and writes nothing.
    """
    requested = list(dict.fromkeys(kinds))
    for kind in requested:
        model_for(kind)  # raises DraftError for a kind this format does not define

    companions = companions_for(requested)
    plan = ScaffoldPlan(spec_dir=spec_dir)
    for companion in companions:
        plan.warnings.append(
            f"{companion} added: a module carrying {', '.join(k for k in requested if companion in COMPANION_KINDS.get(k, ()))}"
            f" does not compile without it."
        )

    targets: list[tuple[Path, str]] = [
        (spec_dir / MODULE_SPEC, module_spec_template(name=name))
    ]
    targets.extend((spec_dir / kind, stub_template(kind, rows=rows)) for kind in requested + companions)

    for path, content in targets:
        if _exists(path):
            plan.refused.append((path, "already exists — scaffolding never overwrites"))
            continue
        plan.created.append(path)
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    plan.written = bool(plan.created) and not dry_run
    return plan
