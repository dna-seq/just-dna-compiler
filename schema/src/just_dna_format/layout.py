"""Where a module's machine-written sidecars live, and what they may be called.

The compiler *reads* these files, the enricher *writes* them, a publisher uploads them and a registry
splits them back apart — four parties, one layout. `just_dna_enricher.locations` exists because every
disagreement about a snapshot's layout so far has been silent, and this is the same class of fact one
tier down, so it lives in the schema tier where both consumers import it rather than copy it.

Nothing here fetches, parses or validates. It is `pathlib` and two tuples of names, which is why it can
sit in the dependency-light tier at all.

**Scope is the machine-written sidecars only** — `resolution.csv` and the fact tables. The authored DSL
(`module_spec.yaml`, `variants.csv`, `studies.csv`, the table kinds) has exactly one legal name in
exactly one legal place, and that asymmetry is deliberate: a second legal home for `variants.csv` means
a module can carry two copies and the one the compiler ignores is invisible, which is the
silent-success shape this codebase treats as the worst kind of mistake. Only the machine-written tables
move, because only they have a machine that knows where to put them.
"""

from pathlib import Path

#: `sources.csv` is the deprecated spelling and `licensing.csv` the one 0.6 introduces (RM51).
#:
#: The name was always wrong — the file records *licence terms*, and its own `source` column collides
#: with the `source` column four other tables carry — but a rename that only lands at 1.0 has to
#: **add** a spelling at the major, which is the expensive half. Landing it in a minor inverts that:
#: every module drafted under 0.6+ already carries the new name, so 1.0 only has to **remove** one.
#:
#: This is minor-legal for a checked reason rather than a hopeful one. `sources.csv` is deliberately
#: outside the compiler's `_INPUT_FILES` — the fact sidecars are hashed by their *facts*, not their
#: bytes — so the filename enters no identity at all: `content_signature` is over authored rows,
#: `source_signature` over `SOURCE_FACT_FIELDS`, and `manifest.derived` is documented transport-only.
#:
#: What could **not** come along, and it is a real cost taken knowingly: `sources.parquet` is inside
#: `artifact.digest` and consumers read it by name, and `manifest.sources` is a published key. Renaming
#: either breaks a reader, so both wait for the major. For the whole 0.x tail a module therefore reads
#: `licensing.csv` → `sources.parquet` → `manifest.sources`.
SOURCES_CSV: str = "sources.csv"
LICENSING_CSV: str = "licensing.csv"

#: Accepted spellings per sidecar, **deprecated first and preferred last**. A sidecar absent from this
#: map has exactly one spelling, which is its own name.
SIDECAR_SPELLINGS: dict[str, tuple[str, ...]] = {
    SOURCES_CSV: (SOURCES_CSV, LICENSING_CSV),
}

#: Spellings a reader still accepts but an author should stop writing. Removal is queued for 1.0 — the
#: cadence the 0.6 charter amendment settled (deprecate in a minor, remove at the next major), and this
#: is the case that prompted it. Warn-only, in both modes: the file is read exactly as before, and a
#: deprecation that refused anything would be a breaking change wearing a notice.
DEPRECATED_SPELLINGS: frozenset[str] = frozenset({SOURCES_CSV})


#: A subdirectory a spec may put its machine-written sidecars in (RM49).
#:
#: Nothing in a flat listing says which files a human wrote and which `just-dna-enricher` produced —
#: `module_spec.yaml`/`variants.csv`/`studies.csv` against `resolution.csv` and the fact tables, with
#: the licence table genuinely both. A registry gave its publishers this tree, then found a downloaded
#: module does not recompile where it sits, so their layout stays transport-only: flatten on upload,
#: re-split on download.
#:
#: **Tolerated, never required, and never canonical.** `reverse_module` keeps emitting a flat tree and
#: the enricher keeps creating one — making this the canonical layout would buy two supported layouts
#: instead of one and have `reverse` emit a tree that older compilers in the same major cannot read,
#: which is a layout migration dressed as a convenience.
#:
#: **One fixed name, not "search any subdirectory".** Walking the tree would blind the near-miss guard
#: that catches a mistyped table name: a typo'd `derived/varaints.csv` would be invisible to the check
#: written precisely to catch that, so the feature would re-open a hole a previous item closed. One
#: name keeps the guard able to look in exactly one more place.
DERIVED_SUBDIR: str = "derived"


class SidecarCollision(ValueError):
    """Two files claim to be the same sidecar, and neither may be silently preferred.

    Not a merge and not newest-wins. These tables are fact-hashed and **human-overridable** — a curator
    edits a row the enricher wrote and that edit is the point — so two copies are two legitimate claims
    and picking one discards somebody's work without saying so. The only honest answer names both paths
    and stops.
    """


def sidecar_spellings(name: str) -> tuple[str, ...]:
    """Every accepted filename for `name`, deprecated first, preferred last."""
    return SIDECAR_SPELLINGS.get(name, (name,))


def preferred_spelling(name: str) -> str:
    """The spelling a fresh file should be created under."""
    return sidecar_spellings(name)[-1]


def is_deprecated_spelling(filename: str) -> bool:
    """Whether a filename is a spelling that still reads but should no longer be written."""
    return filename in DEPRECATED_SPELLINGS


def sidecar_candidates(spec_dir: Path, name: str) -> list[Path]:
    """Every place `name` may legally be — each spelling, at the root and under `derived/`.

    Order is the tie-break nothing else can supply, so it is fixed rather than incidental: a caller
    that wants "the one that exists" gets a deterministic answer, and a caller that wants "where do I
    create it" reads the same list from the front. The root comes first because it is the layout every
    existing module and every `reverse_module` output uses.
    """
    root = Path(spec_dir)
    return [
        root / directory / spelling
        for directory in ("", DERIVED_SUBDIR)
        for spelling in sidecar_spellings(name)
    ]


def resolve_sidecar(spec_dir: Path, name: str) -> Path | None:
    """The single existing copy of a sidecar, or `None` when the module carries none.

    Raises `SidecarCollision` when more than one candidate exists. That is an error rather than a
    warning because there is no correct silent behaviour available — see the exception's own docstring.
    """
    present = [path for path in sidecar_candidates(spec_dir, name) if path.is_file()]
    if not present:
        return None
    if len(present) > 1:
        listed = " and ".join(str(path) for path in present)
        raise SidecarCollision(
            f"{listed} are the same table in two places, and both are present. These tables are "
            f"fact-hashed and may be edited by hand, so two copies are two claims and neither can be "
            f"preferred without discarding the other — keep one and delete the other. "
            f"{preferred_spelling(name)!r} is the spelling to keep; either the spec root or "
            f"{DERIVED_SUBDIR}/ is a fine place for it."
        )
    return present[0]


def sidecar_relative_names(name: str) -> list[str]:
    """Every legal spelling-and-location of `name`, as paths relative to the spec directory.

    For hashing rather than reading: `integrity.file_entries` skips the names that are not there, so
    handing it this list records whichever one the module actually carries — and `FileEntry.name` then
    carries the relative path, which is what a registry re-splitting a downloaded tree needs.
    """
    return [str(path) for path in sidecar_candidates(Path(), name)]


def sidecar_write_path(spec_dir: Path, name: str) -> Path:
    """Where a pass should write a sidecar: the copy that exists, else the preferred spelling.

    **Write to the file you read.** A pass that always created the preferred spelling at the root
    would, on a module carrying the deprecated one or a `derived/` tree, leave two copies behind — the
    collision above, produced by following the documented workflow rather than by misusing it. Running
    `enrich` on a downloaded split module is exactly that path.

    With nothing to follow it creates the flat layout, because `derived/` is *tolerated* rather than
    canonical: a module only ends up split because somebody chose to split it.
    """
    found = resolve_sidecar(spec_dir, name)
    return found if found is not None else Path(spec_dir) / preferred_spelling(name)


def deprecation_notice(path: Path, name: str, *, shown_as: str | None = None) -> str | None:
    """The warning for reading a deprecated spelling, or `None` when the name is current.

    Actionable by construction, which is what the 0.6 amendment requires of a deprecation in a minor:
    the replacement exists, the old name is not mandatory, and the migration is `git mv`.

    `shown_as` is what the message calls the file — a caller that knows the spec directory passes the
    path relative to it, so on a split tree the notice says *which* copy rather than a bare filename
    that could be either.
    """
    if not is_deprecated_spelling(path.name):
        return None
    return (
        f"{shown_as or path.name} is the deprecated spelling of this table and will be removed at 1.0 "
        f"— rename it to {preferred_spelling(name)!r}. It is read exactly as before until then; the "
        f"compiled parquet and the manifest key keep their current names, which only a major may change."
    )
