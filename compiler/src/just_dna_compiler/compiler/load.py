"""Reading a spec directory: `module_spec.yaml`, the per-table CSV loaders, the citing and binning
row sets, and `spec_tables`/`content_signature` over what was read.
"""

import csv
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml
from just_dna_format.base import DEFAULT_GENOME_BUILD, AuthoredModel
from just_dna_format.binning import MeasureBinRow
from just_dna_format.integrity import content_signature as _content_signature
from just_dna_format.normalize import strip_authority_keys
from just_dna_format.overrides import OverrideRow
from just_dna_format.spec import Defaults, ModuleSpecConfig, StudyRow, VariantRow, extract_pmids
from pydantic import BaseModel, ValidationError

from just_dna_compiler.compiler.binning_checks import _BINNING_TABLE_KINDS, _CITING_TABLE_KINDS
from just_dna_compiler.compiler.tables import _TABLE_KINDS, OVERRIDES_CSV
from just_dna_compiler.compiler.variant_checks import _restamp_for_build

# ── File loading helpers ───────────────────────────────────────────────────────


class SpecError(ValueError):
    """A `module_spec.yaml` that could not be loaded — see `load_spec`.

    A `ValueError` subclass so a caller that already brackets a load with `except (OSError,
    ValueError)`, the way `read_verification`'s callers do, keeps working without knowing this type
    exists.
    """


def load_spec(path: Path, *, authority_keys: Iterable[str] | None = None) -> ModuleSpecConfig:
    """Load and validate a `module_spec.yaml`, raising on anything wrong (S74).

    The public route to a `ModuleSpecConfig`. The model has always been exported from
    `just_dna_format.spec` and the only thing that produced one was `_load_yaml`, underscored — so a
    consumer wanting `weighting:` or `authorship:` had to `yaml.safe_load` the file and read a raw
    dict, losing the authority-key handling and every diagnosis below, and carrying **PyYAML** for no
    reason except that ours was unreachable. Sibling of `just_dna_format.read_manifest` and
    `read_verification`: same shape, same contract, one per file a module carries.

    It lives here rather than in the format tier because loading it needs `pyyaml`, and the format
    tier is `pydantic` + `cryptography` by charter. A consumer already depending on the compiler —
    which every caller of `validate_spec` is — can drop their own PyYAML with this.

    `authority_keys` is inject-only and unchanged: pass
    `just_dna_format.normalize.IDENTITY_AUTHORITY_KEYS` so a registry-stamped
    `namespace:`/`owner:`/`canonical_id:` is stripped before validation rather than tripping
    `extra="forbid"`. The format applies none by default, and a key outside the injected set still
    trips. **Which keys were dropped is not reported here** — that is `validate_spec`'s `.info`, and a
    caller who needs it wants the validator rather than the loader.

    Raises `SpecError` with every diagnosis joined, where `_load_yaml` returns them for accumulation.
    That difference is the whole reason both exist: `validate_spec` collects errors from a dozen
    sources and reports them together, which is right for a validator and wrong for a loader — a
    caller who just wants the object should not have to check a tuple's second element to find out
    it got `None`.
    """
    config, errors, _dropped = _load_yaml(Path(path), authority_keys)
    if config is None:
        raise SpecError("; ".join(errors) or f"module_spec.yaml could not be loaded from {path}")
    return config


def _load_yaml(
    path: Path, authority_keys: Iterable[str] | None = None
) -> tuple[ModuleSpecConfig | None, list[str], list[str]]:
    """Load and validate module_spec.yaml. Returns (config, errors, dropped_authority_keys).

    When `authority_keys` is given, the format's reference stripper removes those consumer/registry-
    owned identity keys from the `module:` block *before* validation (inject-only — the caller supplies
    the set, e.g. `just_dna_format.normalize.IDENTITY_AUTHORITY_KEYS`). The validator itself stays
    strict: any key NOT in the injected set still trips `extra="forbid"`. `dropped` is the sorted list
    of keys actually removed, for the caller to surface as INFO."""
    if not path.exists():
        return None, [f"module_spec.yaml not found at {path}"], []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        # A syntax error is the most likely mistake in a hand-written file, and it used to come out as
        # an unhandled `yaml.parser.ParserError` traceback from inside `validate` — for the one command
        # whose whole job is to report problems in a form an author can act on. pyyaml's own message
        # locates the line and column, so it is kept verbatim and merely labelled.
        return None, [f"module_spec.yaml is not valid YAML: {exc}"], []
    if raw is None:
        return None, ["module_spec.yaml is empty"], []
    if not isinstance(raw, dict):
        # A scalar or a list parses fine and then dies in `model_validate` with a pydantic message
        # about the wrong input type, which does not name the actual problem.
        return (
            None,
            [
                f"module_spec.yaml must be a mapping of top-level keys (module:, defaults:, …), not "
                f"{type(raw).__name__}"
            ],
            [],
        )
    dropped: list[str] = []
    if authority_keys and isinstance(raw, dict) and isinstance(raw.get("module"), dict):
        raw["module"], dropped = strip_authority_keys(raw["module"], authority_keys)
    try:
        return ModuleSpecConfig.model_validate(raw), [], dropped
    except ValidationError as exc:
        errors = []
        for err in exc.errors():
            loc = " → ".join(str(x) for x in err["loc"])
            errors.append(f"module_spec.yaml [{loc}]: {err['msg']}")
        return None, errors, dropped


def load_csv_rows(
    path: Path, row_model: type, file_label: str, genome_build: str = DEFAULT_GENOME_BUILD
) -> tuple[list[Any], list[str], list[str]]:
    """Load a CSV and validate each row against a Pydantic model. Returns (rows, errors, warnings).

    **Public as of 0.5.1 (RM41), and it was public in practice long before.** This is the only correct
    way to turn an authored CSV into row models, `just-dna-enricher` consumes it across a package
    boundary in a dozen places, and a downstream consumer wiring the pipeline server-side had the
    choice of reaching for a private symbol or re-implementing it. Re-implementing is a trap rather
    than a chore, because it is not `csv.DictReader` plus `Model(**row)` — it carries the two rules
    below, each of which this workspace has already had to fix once:

    * **an empty cell becomes `None`, and the key is kept.** `MeasureBinRow.measure_kind` has a
      default, so `is_required()` is `False`, but the model then receives `None` rather than its
      default and fails on type. A `""` where this would have put `None` is a different failure again.
    * **`genome_build` is told to each row** (below), so a loader that omits it mints GRCh38
      identities for a GRCh37 module.

    `_load_csv_rows` remains as an alias so no caller breaks.

    `genome_build` is **told to each row**, not read from it. A coordinate is not absolute, so a row
    deriving an identity from one needs the module's assembly — and a pydantic model built from a CSV
    dict has no `module_spec.yaml` in scope. Injecting it here keeps the build declared exactly once
    (the yaml) while reaching every row: it is a private attribute, so it is not a column, reaches no
    parquet, and moves no digest. See `AuthoredModel._genome_build` for why per-row or per-CSV
    declaration was rejected. Callers that load a build-independent table — the resolution and fact
    sidecars, which carry their own `genome_build` column — leave it at the default and are unaffected.
    """
    errors: list[str] = []
    rows: list[Any] = []
    if not path.exists():
        return [], [f"{file_label} not found at {path}"], []

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return [], [f"{file_label} has no header row"], []
        for line_num, raw_row in enumerate(reader, start=2):
            # DictReader buckets any cells past the header under the `None` key (a list). Silently
            # dropping them would let a shifted/surplus column slip past `extra="forbid"` — a real
            # authoring error (a misaligned row) reported as valid. Flag a non-empty surplus instead.
            surplus = [s for s in (raw_row.get(None) or []) if isinstance(s, str) and s.strip()]
            if surplus:
                errors.append(
                    f"{file_label} line {line_num}: more values than header columns "
                    f"(surplus: {surplus}) — check for a shifted or extra column"
                )
                continue
            cleaned = {
                k.strip(): (v.strip() if isinstance(v, str) and v.strip() != "" else None)
                for k, v in raw_row.items()
                if k is not None
            }
            try:
                row = row_model.model_validate(cleaned)
                if isinstance(row, AuthoredModel):
                    row.with_genome_build(genome_build)
                rows.append(row)
            except ValidationError as exc:
                for err in exc.errors():
                    loc = " → ".join(str(x) for x in err["loc"])
                    errors.append(f"{file_label} line {line_num} [{loc}]: {err['msg']}")
    return rows, errors, []


#: The pre-0.5.1 spelling. Kept because it is imported across a package boundary and by consumers
#: outside this workspace; a rename that breaks them buys nothing. Not deprecated — same function,
#: two names, one of which no longer lies about being internal.
_load_csv_rows = load_csv_rows


def load_spec_variants(spec_dir: Path) -> tuple[list[VariantRow], list[str], list[str]]:
    """A spec directory's `variants.csv`, loaded and re-stamped for the build the module declares.

    The other half of RM41. Two enricher checks take rows rather than a `spec_dir` —
    `acmg.verify_acmg_sf` and `identifiers.check_identifiers` — unlike every other pass, so a caller
    has to do this itself, and doing it *right* means three steps rather than one: read the declared
    build out of `module_spec.yaml`, inject it into every row, and then re-stamp the identities, since
    `VariantRow._freeze_identity` runs at construction where the yaml is not in scope.

    Missing or unreadable yaml falls back to `DEFAULT_GENOME_BUILD`, matching what compiling that
    directory would assume — this is a read-only check helper, not the enrichment path, which refuses
    rather than choose a build for a module whose declaration cannot be read (it writes facts back).

    Returns `(variants, errors, warnings)`; an absent `variants.csv` is an empty list and one error,
    exactly as `load_csv_rows` reports it.
    """
    spec_dir = Path(spec_dir)
    config = None
    if (spec_dir / "module_spec.yaml").exists():
        config, _, _ = _load_yaml(spec_dir / "module_spec.yaml")
    build = config.genome_build if config else DEFAULT_GENOME_BUILD
    variants, errors, warnings = load_csv_rows(
        spec_dir / "variants.csv", VariantRow, "variants.csv", genome_build=build
    )
    warnings.extend(_restamp_for_build(variants, build))
    return variants, errors, warnings


def _load_kind_rows(spec_dir: Path, kinds: tuple[tuple[str, type[BaseModel]], ...]) -> dict[str, list[Any]]:
    """The shared body behind `load_citing_rows` and `load_binning_rows` — load the named kinds that
    are present beside a spec, keyed by CSV name.

    One body rather than two, so the two public loaders cannot drift on where a table lives or on what
    an unparseable one does. Row errors are raised rather than returned: a caller wanting the per-row
    diagnosis has `validate_spec`, and a pass reading citations out of a table it could not parse would
    silently under-report.
    """
    spec_dir = Path(spec_dir)
    config, _, _ = _load_yaml(spec_dir / "module_spec.yaml")
    declared_build = config.genome_build if config else DEFAULT_GENOME_BUILD
    out: dict[str, list[Any]] = {}
    for csv_name, model in kinds:
        # `spec_dir / csv_name`, never `_locate_sidecar`: that resolver is scoped to the
        # machine-written sidecars, and an authored table has exactly one legal name in exactly one
        # legal place (RM49/RM51). Both compile-side load loops read authored kinds this way, and a
        # reader that resolved them differently would find a table the compiler does not — which for
        # this function would mean the enricher writing `literature.csv` rows for citations
        # `_cross_check_literature` then reports as orphans.
        path = spec_dir / csv_name
        if not path.is_file():
            continue
        rows, errors, _ = _load_csv_rows(path, model, csv_name, genome_build=declared_build)
        if errors:
            raise ValueError(f"{csv_name} is invalid: {errors[0]}")
        out[csv_name] = rows
    return out


def load_citing_rows(spec_dir: Path) -> dict[str, list[Any]]:
    """Every **citing** table present beside a spec, keyed by CSV name — the annotation rows that
    ground their own claim with a `pmid` (`MeasureBinRow.pmid` RM47, `PharmVariantRow.pmid` RM132).

    Public because a second tier needs it: the enricher's literature pass has to check these pointers
    alongside `studies.csv`, and its two alternatives were importing a private symbol or hand-keeping a
    parallel list of the citing kinds — the RM40/RM41 shape exactly, and the list would go stale on the
    next kind that declares the column.

    Supersedes `load_binning_rows`, which stays and still means what it always did: it reads the
    binning kinds only, so a caller wanting *the citations a module makes* wants this one.
    """
    return _load_kind_rows(spec_dir, _CITING_TABLE_KINDS)


def load_binning_rows(spec_dir: Path) -> dict[str, list[MeasureBinRow]]:
    """Every **binning** table present beside a spec, keyed by CSV name (RM47).

    Narrower than `load_citing_rows` since 0.7 and deliberately kept: a caller asking for the binning
    kinds is asking about thresholds, not about citations, and quietly widening what it returns would
    hand such a caller `PharmVariantRow`s where it expects `MeasureBinRow`s.
    """
    return _load_kind_rows(spec_dir, _BINNING_TABLE_KINDS)


def _citations_over(
    rows_by_csv: dict[str, list[Any]], kinds: tuple[tuple[str, type[BaseModel]], ...]
) -> list[str]:
    """The shared body behind `table_citations` and `binning_citations`."""
    seen: dict[str, None] = {}
    for csv_name, _model in kinds:
        for row in rows_by_csv.get(csv_name) or []:
            if row.pmid:
                for pmid in extract_pmids(row.pmid):
                    seen.setdefault(pmid, None)
    return list(seen)


def table_citations(rows_by_csv: dict[str, list[Any]]) -> list[str]:
    """Digit-only PMIDs the module's annotation tables cite, de-duplicated — **every** citing kind
    (`MeasureBinRow.pmid` RM47, `PharmVariantRow.pmid` RM132).

    Takes the whole table-kind map a caller already holds and reads only the citing kinds out of it, so
    a caller cannot accidentally hand over a `haplotypes.csv` (no `pmid` column) and get an attribute
    error. The kind set is derived from the models, never hand-listed, so a kind that gains the column
    is read here without an edit.

    First-occurrence order rather than sorted, because it feeds emission order downstream (P7), and
    normalization goes through `extract_pmids` so a table pointer and `studies.csv` cannot drift into
    two spellings of one citation.
    """
    return _citations_over(rows_by_csv, _CITING_TABLE_KINDS)


def binning_citations(rows_by_csv: dict[str, list[Any]]) -> list[str]:
    """Digit-only PMIDs the **binning** tables cite (`MeasureBinRow.pmid`), de-duplicated.

    Narrowed by `table_citations` since 0.7 the same way `load_binning_rows` is by `load_citing_rows`,
    and kept for the same reason. Nothing inside the compiler calls it any more: the literature
    cross-check must read every citation site, and this one answers a question about thresholds.
    """
    return _citations_over(rows_by_csv, _BINNING_TABLE_KINDS)


#: The `Defaults` fields a `VariantRow` may also carry on the row, resolved before hashing (RM37).
_DEFAULTED_VARIANT_FIELDS: tuple[str, ...] = ("curator", "method", "priority")


def _resolve_spec_defaults(rows: list[Any], defaults: Defaults) -> None:
    """Replace each row's `curator`/`method`/`priority` with its **effective** value, in place (RM37).

    `defaults:` in `module_spec.yaml` and the cell on the row are two spellings of one value, and
    which one a module uses is a matter of where the author typed it. Hashing the cell alone made the
    two spellings different content — so `compile → reverse → compile` moved `content_signature` for
    any module that wrote the value per row, because `reverse_module` re-emits it in the other place
    (it infers the module default from the commonest value and blanks the matching cells). The data
    was never lost: `artifact.digest` was byte-identical, because the *compile* side has always
    resolved the same `row value or default`. Only the pre-resolution identity disagreed with itself.

    Resolving here makes the signature a function of what the module *means* rather than of where it
    was written, which is the property a content-dedup key needs.

    **A value equal to the `Defaults` model's own default is written back as `None`, not as itself.**
    That is not a special case — it is the same normalization `integrity.content_signature` already
    applies to `genome_build` and to every unset optional column (`exclude_none=True`), and it is what
    keeps the change targeted: a module that never mentions `curator`/`method`, or names the built-in
    values, keeps its existing signature byte for byte. What moves is a module that states something
    else, which is exactly the module whose two spellings were being hashed apart.
    """
    model_defaults = {name: Defaults.model_fields[name].default for name in _DEFAULTED_VARIANT_FIELDS}
    for row in rows:
        for name, model_default in model_defaults.items():
            authored = getattr(row, name)
            effective = authored if authored is not None else getattr(defaults, name)
            setattr(row, name, None if effective == model_default else effective)


def spec_tables(spec_dir: Path) -> tuple[dict[str, list[Any]], str]:
    """The parsed, defaults-folded authored rows `content_signature` hashes, and the declared build.

    PUBLIC, and the reason is that everything finer than a whole-module hash needs these rows and had
    no way to get them (S53). `content_signature` returned only the digest, so a tool answering *what
    moved between two versions of this module* — per table, per row — had to rebuild the mapping
    outside, and rebuilding it meant restating two private things: the table roster (`_TABLE_KINDS`)
    and the `defaults:` fold (`_resolve_spec_defaults`, `_DEFAULTED_VARIANT_FIELDS`).

    **The fold is the part that silently produces a wrong answer**, which is why this returns the
    finished mapping rather than exporting the pieces. A caller hashing `load_csv_rows` output directly
    gets a different digest from `content_signature` for the same module: measured on
    `reference_examples/hfe_hemochromatosis`, writing one `curator` value on every variant row in one
    copy and the identical value under `defaults:` in another, `content_signature` agrees across the
    pair (correct — RM37) while the raw-rows build disagrees, so a per-table comparison built the
    obvious way reports twelve changed rows where there are none. Exporting `_TABLE_KINDS` and
    `_resolve_spec_defaults` separately would hand out three pieces that must be assembled in one
    order — load with the declared build injected, fold, then hash — and the order is the easy half to
    get wrong. One function that returns the finished mapping cannot be assembled wrongly.

    **The roster is authored tables only**, so the licensing table is outside it: `sources.csv` /
    `licensing.csv` is hashed by `integrity.source_signature` instead, and neither renaming it nor
    editing a cell in it moves `content_signature`. Both verified on the same example. That is correct
    — the licence layer is its own identity — and it is stated here because it is the one authored,
    hand-editable table a licence audit sends an author looking for.

    Raises `ValueError` if a present data CSV fails validation, exactly as `content_signature` does:
    the contract carries over unchanged, because that function is now this one plus the hash.
    """
    spec_dir = Path(spec_dir)
    # The declared build is part of the content, not metadata about it: identical coordinate rows on
    # two assemblies describe two different loci. A spec whose yaml will not load falls back to the
    # format default — this function raises on an invalid *data* CSV, and an unreadable yaml is
    # `validate_spec`'s finding to report, not this one's.
    config, _, _ = _load_yaml(spec_dir / "module_spec.yaml")
    declared_build = config.genome_build if config else DEFAULT_GENOME_BUILD
    kinds: list[tuple[str, type[BaseModel]]] = [
        ("variants.csv", VariantRow),
        ("studies.csv", StudyRow),
        *((csv_name, model) for csv_name, _parquet, model in _TABLE_KINDS),
        # The overlay is authored input, so it is content (RM124) — by its value cells. Its three
        # provenance cells (`reason`/`decided_by`/`decided_at`) are `exclude=True` on the model and
        # so outside the hash (S87): rewording a reason is a patch, not a new identity. No published
        # module's signature moves: `content_signature` skips a table this loop finds no file for,
        # exactly as an unset optional column contributes nothing, and no module published to date
        # carries one.
        (OVERRIDES_CSV, OverrideRow),
    ]
    tables: dict[str, list[Any]] = {}
    for csv_name, model in kinds:
        path = spec_dir / csv_name
        if not path.is_file():
            continue
        rows, errors, _ = _load_csv_rows(path, model, csv_name, genome_build=declared_build)
        if errors:
            raise ValueError(f"cannot compute content_signature: {csv_name} is invalid: {errors[0]}")
        if model is VariantRow:
            # The only model carrying `Defaults`' fields. Safe to mutate: these rows were loaded here
            # and go nowhere else — the compile path loads its own copy.
            _resolve_spec_defaults(rows, config.defaults if config else Defaults())
        tables[csv_name] = rows
    return tables, declared_build


def content_signature(spec_dir: Path) -> str:
    """Stable content identity over the raw authored data CSVs — name- and Ensembl-independent.

    Reads `variants.csv`, `studies.csv`, and any present 0.4 table CSVs, validates each row, and
    hashes the normalized + deterministically-sorted rows via
    `just_dna_format.integrity.content_signature`. The data is read **as authored** (no Ensembl
    resolution, no parquet build), so this is cheap and reference-independent — a client can compute
    it without recompiling and dedup against a registry, surviving both metadata-strip and a recompile
    against a different reference. Raises `ValueError` if a present data CSV fails validation.

    "As authored" means the *rows*, not the *spelling*: `module_spec.yaml`'s `defaults:` block is
    folded into each variant row first (`_resolve_spec_defaults`, RM37), because a value written once
    under `defaults:` and the same value written on every row are the same content.

    This is `spec_tables` plus the hash and nothing else, so a consumer wanting the rows behind the
    digest — per-table or per-row work — calls that instead of restating the roster and the fold (S53).
    """
    return _content_signature(*spec_tables(spec_dir))
