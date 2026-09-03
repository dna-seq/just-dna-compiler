"""
Integrity primitives (SPEC §5).

All hashes are SHA-256, lowercase hex, prefixed `sha256:`. These functions are the shared
implementation the compiler uses to *emit* integrity fields and a downloader uses to *verify*
them — keeping both sides byte-for-byte agreement by construction.

Time is never read here: callers pass any timestamps into the manifest. This keeps the module
pure and deterministic.
"""

import base64
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from pydantic import BaseModel

from just_dna_format.assertions import CLINICAL_ASSERTION_FACT_FIELDS
from just_dna_format.base import DEFAULT_GENOME_BUILD, content_identity_exclusions
from just_dna_format.concordance import (
    CLIN_SIG_AUTHORITY_CALL_FACT_FIELDS,
    CLIN_SIG_CONCORDANCE_FACT_FIELDS,
)
from just_dna_format.frequency import FREQUENCY_FACT_FIELDS
from just_dna_format.gene_metrics import GENE_METRICS_FACT_FIELDS
from just_dna_format.gene_validity import GENE_VALIDITY_FACT_FIELDS
from just_dna_format.gwas import GWAS_FACT_FIELDS
from just_dna_format.literature import LITERATURE_FACT_FIELDS
from just_dna_format.manifest import (
    MARKETPLACE_COMPILED_BY,
    Artifact,
    FileEntry,
    ModuleManifest,
    Signature,
)
from just_dna_format.resolution import RESOLUTION_FACT_FIELDS
from just_dna_format.sources import SOURCE_FACT_FIELDS

SHA256_PREFIX: str = "sha256:"
_CHUNK: int = 1 << 20  # 1 MiB streaming reads


class IntegrityError(Exception):
    """Raised when a file hash, artifact digest, or trust check fails verification."""


def verify_signature(
    digest: str, signature: Signature, *, trusted_public_key: str | None = None
) -> None:
    """Verify a `Signature` over the `artifact.digest` string. Raises `IntegrityError` on failure.

    When `trusted_public_key` (base64 raw) is given, the signature MUST have been made by that key
    — this is the real defense (a self-embedded key proves nothing against a backend that can
    rewrite both digest and key). When omitted, only self-consistency is checked.
    """
    if signature.algorithm != "ed25519":
        raise IntegrityError(f"unsupported signature algorithm: {signature.algorithm!r}")
    if trusted_public_key is not None and trusted_public_key != signature.public_key:
        raise IntegrityError("signature public key does not match the trusted (pinned) key")
    try:
        pub = ed25519.Ed25519PublicKey.from_public_bytes(base64.b64decode(signature.public_key))
        pub.verify(base64.b64decode(signature.signature), digest.encode("utf-8"))
    except (InvalidSignature, ValueError) as exc:
        raise IntegrityError(f"artifact digest signature is invalid: {exc}") from exc


def sha256_bytes(data: bytes) -> str:
    """SHA-256 of raw bytes, prefixed `sha256:`."""
    return SHA256_PREFIX + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """Streaming SHA-256 of a file's raw bytes, prefixed `sha256:`."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return SHA256_PREFIX + digest.hexdigest()


def file_entry(directory: Path, name: str) -> FileEntry:
    """Build a `FileEntry` (name, sha256, size) for `directory/name`."""
    path = Path(directory) / name
    return FileEntry(name=name, sha256=sha256_file(path), size=path.stat().st_size)


def file_entries(directory: Path, names: list[str]) -> list[FileEntry]:
    """Build `FileEntry` rows for each existing name under `directory` (skips missing)."""
    directory = Path(directory)
    return [file_entry(directory, name) for name in names if (directory / name).is_file()]


def newline_normalized_file_entry(directory: Path, name: str) -> FileEntry:
    """A `FileEntry` over `directory/name` with `\\r\\n` read as `\\n` — for the binding only (RM82).

    Rewriting an authored CSV with different line endings changes no value, no digest and no
    signature, and used to drop the whole verification attestation and the closure with it: an author
    whose editor normalizes newlines, or whose Git does it through `core.autocrlf`, un-closed a module
    without touching a cell. This entry builder is what `verification.module_binding` is computed over,
    through `just_dna_compiler.compiler.authored_input_entries`, so that rewrite is no longer an edit.

    **Both halves are normalized, and the second one is the whole trap.** `artifact_digest` hashes
    `{"name", "sha256", "size"}` per file, so a builder that normalized the bytes it hashed while
    reporting `stat().st_size` would still move the binding — by one byte per line, on exactly the
    files this exists to protect. So `size` here is the length of the *normalized* stream, not the
    length on disk. That is sound because these entries are only ever fed to `module_binding`: they are
    hashed, never published as a listing, and nothing reads them as a claim about a file's size. The
    entries that *are* published — `manifest.inputs[]` and `artifact.files[]` — keep coming from
    `file_entry`/`file_entries` with the on-disk bytes and the on-disk size.

    **A separate function rather than a `normalize=True` flag on `file_entries`.** A flag must mean the
    same thing in every function that takes one, and a boolean that silently changes *what a hash is
    over* is the opposite of that: a caller passing it by habit would re-baseline `manifest.inputs[]`
    with no error and no warning. Two functions cannot be confused at a call site.

    **The stopping point is newlines, and it is chosen rather than inherited.** A BOM, trailing
    whitespace and a missing final newline are the obvious next steps, and each makes the binding more
    content-ish without making it content — this deliberately implements none of them. Newlines are the
    one difference a *tool* introduces on a file the author did not edit; the others are things a human
    typed. A lone `\\r` is left exactly as it is, for the same reason: it is not what an editor or Git
    writes when it normalizes. If a real case arrives for one of the others it is additive and gets
    argued then, on its own evidence.
    """
    path = Path(directory) / name
    digest = hashlib.sha256()
    size = 0
    carry = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            data = carry + chunk
            # A trailing `\r` may be the first half of a `\r\n` split across the read boundary, so it
            # is held back rather than judged now — the one thing a chunked rewrite can get wrong.
            if data.endswith(b"\r"):
                data, carry = data[:-1], b"\r"
            else:
                carry = b""
            normalized = data.replace(b"\r\n", b"\n")
            digest.update(normalized)
            size += len(normalized)
    if carry:  # a file ending in a bare `\r`: nothing followed it, so it stands
        digest.update(carry)
        size += len(carry)
    return FileEntry(name=name, sha256=SHA256_PREFIX + digest.hexdigest(), size=size)


def newline_normalized_file_entries(directory: Path, names: list[str]) -> list[FileEntry]:
    """`newline_normalized_file_entry` for each existing name under `directory` (skips missing).

    The sibling of `file_entries`, with the same skip-missing contract — a module carries only the
    table kinds it uses, so an absent name is the ordinary case rather than a failure.
    """
    directory = Path(directory)
    return [
        newline_normalized_file_entry(directory, name)
        for name in names
        if (directory / name).is_file()
    ]


def artifact_digest(files: list[FileEntry]) -> str:
    """
    Merkle-style root over the file set (SPEC §5): build the JSON array
    `[{"name","sha256","size"}, ...]` sorted by name, serialized with sorted keys and no
    whitespace, then hash. Verifying this one digest verifies the whole set, independent of the order
    the files were listed in.

    This is the version's immutable **byte** identity — *these bytes, from this compiler* (Principle
    4) — and **not** its content identity, which is `content_signature`. The distinction is the whole
    reason there are two hashes: a recompile against a different reference moves the digest while the
    authored content is untouched, so reading a moved digest as moved content sends a reader hunting a
    change that did not happen. This docstring said "content identity" until 2026-08-12; the same
    wording was corrected in the docs when a consumer made exactly that misreading (S7), and the code
    copy outlived the fix.
    """
    listing = sorted(
        ({"name": f.name, "sha256": f.sha256, "size": f.size} for f in files),
        key=lambda entry: entry["name"],
    )
    canonical = json.dumps(listing, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(canonical.encode("utf-8"))


def build_artifact(output_dir: Path, filenames: list[str]) -> Artifact:
    """Hash each output file and compute the artifact digest over the set."""
    files = file_entries(output_dir, filenames)
    return Artifact(digest=artifact_digest(files), files=files)


def content_signature(
    tables: Mapping[str, Sequence[BaseModel]],
    genome_build: str = DEFAULT_GENOME_BUILD,
) -> str:
    """Stable content identity over the RAW authored data rows — the canonical, owned algorithm.

    Distinct from `artifact_digest`: that hashes the *compiled parquet* bytes, which are
    GRCh38-coordinate-relative and therefore depend on the Ensembl reference the resolver was given
    (and move if the module is recompiled elsewhere). `content_signature` instead hashes the authored
    *data* rows as parsed — so it is:

    - **Reference-independent** — computed from the rows *before* resolution (an rsid-only row is
      hashed as authored, not as resolved coordinates), so recompiling against a different/complete
      reference does not change it. This bullet used to say "build-independent", which was true of the
      *reference used to resolve* and false of the **declared assembly**, and the two are not the same
      thing: for a coordinate-authored module `genome_build` is not a resolution artifact, it is the
      frame the authored numbers are in. HFE C282Y is 6:26,093,141 on GRCh37 and 6:26,092,913 on
      GRCh38, so two modules with byte-identical CSVs and different declared builds describe loci 228 bp
      apart — and hashed equal, which for a *content-dedup* key is the wrong answer. The realistic way
      to hit it is not contrived: "lift over" a GRCh37 panel by editing the yaml and not the
      coordinates, and a registry keyed on this would call the result the same content.
    - **Build-aware, by omitting the default** — `genome_build` now feeds the hash, but only when it is
      not `DEFAULT_GENOME_BUILD`. That is the same normalization the bullet below already applies to
      an unset optional column, not an exception to it, and it is what keeps the fix targeted: every
      GRCh38 module — which is every module published to date — keeps its existing signature byte for
      byte, and only the modules that were being *misidentified* change.
    - **Name/metadata-independent** — the *identity and display* half of `module_spec.yaml` (name,
      version, namespace, title, colour) is excluded, so a metadata edit or a registry strip does not
      change it. `genome_build` is the one key from that file that does feed the hash, because it is
      not metadata about the module: it is part of what the rows *mean*.
    - **Normalized** — each row is `model_dump(mode="json", exclude_none=True)`, so CSV reformatting
      (whitespace, quoting, column reorder, cell canonicalization like `1.00`→`1.0`) and additive
      schema growth (a new optional column left unset) do not change it.
    - **Value cells, not the provenance beside them** — a column marked `OUTSIDE_CONTENT_IDENTITY`
      (`base.content_identity_exclusions`) is dropped from the dump here and nowhere else: the
      overlay's `reason`/`decided_by`/`decided_at` (S87) say why a correction was made, and two
      modules differing only there assert the same thing. It is the same exclusion `fact_signature`
      applies to a derived table's `fetched_at`, applied to the one authored table that carries
      provenance beside its claims.
    - **Deterministically sorted, order-independent** — the normalized rows of each file are sorted by
      their canonical JSON, and files are sorted by name, so re-ordering rows yields the *same*
      signature. (This is deliberately unlike `artifact.digest`, which *preserves* authored row order:
      the two are different identities — a byte-reproducibility digest vs. a content-dedup key.)

    `tables` maps each data-CSV filename (`variants.csv`, `studies.csv`, and the 0.4 table kinds) to
    its parsed, validated rows. The result is the enabling identity for content-level dedup that
    survives import/recompile and metadata-strip. It is the reference algorithm a marketplace's
    `find_versions_by_content` should adopt (see docs/proposals/PROPOSAL_0_4_1.md).
    """
    listing: list[dict[str, object]] = [
        {
            "file": filename,
            "rows": sorted(
                json.dumps(
                    row.model_dump(
                        mode="json",
                        exclude_none=True,
                        exclude=content_identity_exclusions(type(row)) or None,
                    ),
                    sort_keys=True,
                    separators=(",", ":"),
                )
                for row in rows
            ),
        }
        for filename, rows in tables.items()
    ]
    listing.sort(key=lambda part: str(part["file"]))
    if genome_build != DEFAULT_GENOME_BUILD:
        # Appended, and only when non-default, so every GRCh38 module keeps the signature it already
        # had — see the `genome_build` bullet above for why this is the existing omit-the-default
        # normalization rather than an exception to it.
        listing.append({"genome_build": genome_build})
    canonical = json.dumps(listing, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(canonical.encode("utf-8"))


def fact_signature(rows: Sequence[BaseModel], fact_fields: Sequence[str]) -> str:
    """Stable, producer-independent identity over a derived-fact table's fact columns.

    The shared body behind `resolution_signature`, `frequency_signature`, and
    `gene_metrics_signature` — three tables with one hashing discipline, so the rule cannot drift
    between them as more sidecars land. Each row is reduced to its `fact_fields` with `None` dropped,
    canonicalized, and the sorted set hashed:

    - **Fact-only** — the provenance columns each table excludes (`source`/`status`/`fetched_at`) are
      simply not in `fact_fields`, so a human-filled and a machine-filled table with identical facts
      hash equal. That producer-independence is the whole reason these tables are hashed here instead
      of entering `manifest.inputs` as raw-byte `FileEntry`s.
    - **Normalized** — `model_dump(mode="json")` with `None` dropped, so CSV reformatting and an unset
      optional column do not change it.
    - **Order-independent** — rows are sorted by their canonical JSON, so a producer that emits them in
      a different order still hashes equal.
    """
    normalized = sorted(
        json.dumps(
            {
                key: value
                for key, value in row.model_dump(mode="json").items()
                if key in fact_fields and value is not None
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        for row in rows
    )
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(canonical.encode("utf-8"))


def frequency_signature(rows: Sequence[BaseModel]) -> str:
    """Fact-hash of `frequencies.csv` (`frequency.FREQUENCY_FACT_FIELDS`). See `fact_signature`.

    Recorded in `manifest.frequency.signature` and kept out of `artifact.digest`: the compiled
    `frequencies.parquet` is already in the digest, and this is the *producer-independent* identity of
    the same content — the thing that stays equal when the enricher and a human write the same numbers
    with different column order and different timestamps.
    """
    return fact_signature(rows, FREQUENCY_FACT_FIELDS)


def gene_metrics_signature(rows: Sequence[BaseModel]) -> str:
    """Fact-hash of `gene_metrics.csv` (`gene_metrics.GENE_METRICS_FACT_FIELDS`)."""
    return fact_signature(rows, GENE_METRICS_FACT_FIELDS)


def literature_signature(rows: Sequence[BaseModel]) -> str:
    """Fact-hash of `literature.csv` (`literature.LITERATURE_FACT_FIELDS`).

    The narrowest fact set of the three, and deliberately so: only *which article this is* is a fact
    about the module. Open-access status and quote coverage are the outside world's state on the day
    the pass ran, so they stay outside — otherwise an embargo lifting would move a module's signature
    with no authored edit anywhere.
    """
    return fact_signature(rows, LITERATURE_FACT_FIELDS)


def gene_validity_signature(rows: Sequence[BaseModel]) -> str:
    """Fact-hash of `gene_validity.csv` (`gene_validity.GENE_VALIDITY_FACT_FIELDS`), 0.6 / RM24.

    Wider than its siblings, because the row's *identity* is wide: a gene–disease assertion is scoped
    by mode of inheritance and, on an aggregate like GenCC, by who made it.

    Two non-provenance columns are excluded, on one rule — **a column that locates or describes an
    assertion is not the assertion**. `report_url` locates the curation and moves when a site
    reorganizes; `disease_label` is the ontology's wording for a term `disease_id` already names, and
    it churns on its own (one real export carries MONDO:0017146 under two labels at once). The stable
    identities — `disease_id` and `assertion_id` — are inside.
    """
    return fact_signature(rows, GENE_VALIDITY_FACT_FIELDS)


def clinical_assertion_signature(rows: Sequence[BaseModel]) -> str:
    """Fact-hash of `clinical_assertions.csv` (`assertions.CLINICAL_ASSERTION_FACT_FIELDS`), RM25.

    `review_status` and `review_stars` are both inside it although one determines the other. The
    mapping between them is a ClinVar convention that Principle 2 keeps out of this tier, so from
    here they are two independent inputs — and a table whose stars disagreed with its own prose
    should hash differently from one where they agree.

    `rsid` is **outside**, unlike `FREQUENCY_FACT_FIELDS`, and the difference is where the value comes
    from: gnomAD reports an rsID in its own payload, while the ClinVar lookup is allele-exact and
    returns none, so this column is filled from the module's own `resolution.csv`. Inside the hash it
    would make two modules holding the same archive records hash differently on whether their resolver
    attached an rsID — the producer-dependence a fact hash exists to exclude.
    """
    return fact_signature(rows, CLINICAL_ASSERTION_FACT_FIELDS)


def gwas_effect_signature(rows: Sequence[BaseModel]) -> str:
    """Fact-hash of `gwas_effects.csv` (`gwas.GWAS_FACT_FIELDS`), 0.6 / RM90.

    `effect_unit` is **inside**, and it is the column that most needs to be: the same magnitude in
    `umol/l` and in the Catalog's uninformative `unit` are different facts, and a table that hashed
    equal across them would have thrown away the distinction this table exists to keep.

    `trait` is **outside**, on `gene_validity_signature`'s rule — a column that *describes* an
    assertion is not the assertion. The Catalog re-words a reported trait between releases for an
    unchanged `trait_efo_id`, so the label churns while the fact does not.

    `rsid` is **inside**, which inverts `clinical_assertion_signature` and does so deliberately. There
    the rsID is filled from the module's own `resolution.csv` because the archive returns none; here
    the Catalog is queried by rsID and echoes it back inside `riskAlleleName`, so it is part of what
    the source said rather than of what the module knew.
    """
    return fact_signature(rows, GWAS_FACT_FIELDS)


def clin_sig_concordance_signature(rows: Sequence[BaseModel]) -> str:
    """Fact-hash of `clin_sig_concordance.csv` (`concordance.CLIN_SIG_CONCORDANCE_FACT_FIELDS`), RM130.

    `opposed` is **inside**, and it is the column the fact set would be wrong without: the two verdict
    columns say the authorities disagree and where the module sits, and neither says whether the
    disagreement crosses the pathogenic/benign line. A module whose contested subjects are opposed
    asserts something different from one whose subjects merely differ, so the two must not hash equal.

    `checked_at` is **outside**, on the rule every sibling applies to `fetched_at`: a re-run that put
    the same questions and got the same answers has changed nothing anybody asserted.
    """
    return fact_signature(rows, CLIN_SIG_CONCORDANCE_FACT_FIELDS)


def clin_sig_authority_call_signature(rows: Sequence[BaseModel]) -> str:
    """Fact-hash of `clin_sig_authority_calls.csv`
    (`concordance.CLIN_SIG_AUTHORITY_CALL_FACT_FIELDS`), RM130.

    `confidence` and `confidence_unit` are both inside, together, for `gwas_effect_signature`'s own
    reason one table over: an unconverted magnitude and the instrument it was measured on are one
    fact in two cells, and hashing the number without the unit would make two authorities' different
    scales collide.

    `status` is inside too. `no_record` and `unchecked` are different statements about the same
    subject — one archive was asked and has nothing, the other could not be asked — and a record that
    swapped them says something else about how much of the check actually ran.
    """
    return fact_signature(rows, CLIN_SIG_AUTHORITY_CALL_FACT_FIELDS)


def source_signature(rows: Sequence[BaseModel]) -> str:
    """Fact-hash of `sources.csv` (`sources.SOURCE_FACT_FIELDS`).

    Note the one inversion against its siblings: `source` is **inside** this fact set, because here it
    is the subject of the row rather than the provenance of one. Only `fetched_at` is excluded, so
    re-reading the same terms at a different moment hashes equal, while a changed licence, a changed
    permission flag or a changed declaration all move the signature — which is the point.
    """
    return fact_signature(rows, SOURCE_FACT_FIELDS)


def resolution_signature(rows: Sequence[BaseModel]) -> str:
    """Stable, producer-independent identity over the resolution table's *facts* (0.5).

    `resolution.csv` is a multi-producer artifact — the enricher, a human, and `reverse_module` all
    write it, with byte-different but fact-identical output (column/row order, provenance columns,
    timestamps). So it is hashed HERE, over the fact columns only, and is deliberately NOT added to
    `manifest.inputs`: a raw-bytes `FileEntry` hash would be unstable across those producers and would
    make a `reverse → recompile` cycle "change the hash" for no real reason. Mirrors
    `content_signature`, restricted to `resolution.RESOLUTION_FACT_FIELDS`:

    - **Fact-only** — the provenance columns (`source`/`status`/`fetched_at`) are excluded, so a
      human-filled and an Ensembl-filled table carrying the same facts hash equal.
    - **Normalized** — each row is `model_dump(mode="json")` restricted to the fact fields with `None`
      dropped, so CSV reformatting and an unset optional column do not change it.
    - **Deterministically sorted, order-independent** — rows are sorted by their canonical JSON.

    Together with `content_signature` and `compiler_version` it fully determines `artifact.digest`, so
    a holder of the two small CSVs reproduces the artifact byte-for-byte, fully offline.
    """
    return fact_signature(rows, RESOLUTION_FACT_FIELDS)


def verify_manifest(
    module_dir: Path,
    manifest: ModuleManifest,
    *,
    require_marketplace: bool = True,
    check_inputs: bool = False,
    check_logs: bool = False,
    check_provenance: bool = False,
    check_logo: bool = False,
    check_readme: bool = False,
    check_derived: bool = False,
    public_key: str | None = None,
) -> None:
    """
    Verify a downloaded module against its manifest (SPEC §5 verify-then-install).

    **`require_marketplace` is a policy switch and its default is the registry one (S34).** Step 3
    demands `compiled_by == "marketplace-server"`, so with the default a consumer that wires exactly
    one call site rejects **every locally-compiled module** — including one this project's own
    compiler produced, which leaves `compiled_by` null by design. That is correct behaviour and a
    surprising default to meet through a parameter named for a requirement rather than for a policy.
    A consumer that installs from both places needs two call sites, not one:

    * `require_marketplace=True` — a registry install. The bytes came from a party you are trusting to
      have compiled them, so "who compiled this" is part of what you are checking.
    * `require_marketplace=False` — a local compile, a sideloaded directory, a file a user handed you.
      The hashes and the digest are still checked in full; only the *provenance* claim is dropped,
      because there is no registry to have made it.

    Nothing weaker is on offer and nothing here is a trust root: `compiled_by` is an unsigned string in
    a file the same party wrote. The real guarantee is `public_key` below — a detached Ed25519
    signature over `artifact.digest` by a key the client pins.

    Steps:
      1. Every `artifact.files[]` present on disk hashes to its declared value.
      2. The recomputed `artifact.digest` matches the manifest.
      3. `compile_success` is true and `compiled_by == "marketplace-server"`
         (when `require_marketplace`).
      4. Optionally (`check_inputs`) every `inputs[]` file on disk matches its declared hash.
      5. Optionally (`check_logs`) every `logs[]` file *present* on disk matches its declared hash;
         absent logs are skipped, since logs are optional and need not be downloaded.
      6. Optionally (`check_provenance`) the `provenance` document, if declared and present on disk,
         matches its declared hash; an absent provenance file is skipped (it is optional).
      6b. Optionally (`check_logo`) the `logo`, if declared and present on disk, matches its declared
         hash; an absent logo is skipped (it is optional and out of `artifact.digest`).
      5b. Optionally (`check_derived`) every `derived[]` sidecar CSV *present* on disk matches its
         declared byte hash; an absent one is skipped, exactly as for logs — these live beside the
         spec rather than in the module dir, so a consumer who fetched only the artifact has none of
         them, which is not a failure. This checks *bytes in transit*; it is not the tables' identity
         (that is the fact signatures, which survive a rewrite this check would flag).
      6c. Optionally (`check_readme`) the `readme`, on the same terms as the logo. This is the check
         that makes a served readme verifiable: a registry serving a file whose hash nothing records
         is serving something nobody can check, which is why the field exists rather than the bytes
         merely sitting on disk.
      7. Signature (SPEC §5): if `public_key` (base64 raw) is given, the manifest MUST carry a
         signature over `artifact.digest` made by that key. If a signature is present but no key is
         pinned, it is verified for self-consistency only.

    Raises `IntegrityError` on the first failure; returns `None` on success.
    """
    module_dir = Path(module_dir)

    for entry in manifest.artifact.files:
        path = module_dir / entry.name
        if not path.is_file():
            raise IntegrityError(f"artifact file missing on disk: {entry.name}")
        actual = sha256_file(path)
        if actual != entry.sha256:
            raise IntegrityError(
                f"artifact hash mismatch for {entry.name}: "
                f"declared {entry.sha256}, computed {actual}"
            )

    recomputed = artifact_digest(manifest.artifact.files)
    if recomputed != manifest.artifact.digest:
        raise IntegrityError(
            f"artifact digest mismatch: declared {manifest.artifact.digest}, "
            f"computed {recomputed}"
        )

    if require_marketplace:
        if not manifest.compilation.compile_success:
            raise IntegrityError("compilation.compile_success is not true — untrusted")
        if manifest.compilation.compiled_by != MARKETPLACE_COMPILED_BY:
            raise IntegrityError(
                f"compiled_by is {manifest.compilation.compiled_by!r}, "
                f"expected {MARKETPLACE_COMPILED_BY!r} — untrusted"
            )

    if check_inputs:
        for entry in manifest.inputs:
            path = module_dir / entry.name
            if not path.is_file():
                raise IntegrityError(f"input file missing on disk: {entry.name}")
            actual = sha256_file(path)
            if actual != entry.sha256:
                raise IntegrityError(
                    f"input hash mismatch for {entry.name}: "
                    f"declared {entry.sha256}, computed {actual}"
                )

    if check_logs:
        for entry in manifest.logs:
            path = module_dir / entry.name
            if not path.is_file():
                continue  # logs are optional — an absent one is not a failure
            actual = sha256_file(path)
            if actual != entry.sha256:
                raise IntegrityError(
                    f"log hash mismatch for {entry.name}: "
                    f"declared {entry.sha256}, computed {actual}"
                )

    if check_derived:
        for entry in manifest.derived:
            path = module_dir / entry.name
            if not path.is_file():
                continue  # sidecars live beside the spec — an absent one is not a failure
            actual = sha256_file(path)
            if actual != entry.sha256:
                raise IntegrityError(
                    f"derived sidecar hash mismatch for {entry.name}: "
                    f"declared {entry.sha256}, computed {actual}"
                )

    if check_provenance and manifest.provenance is not None:
        prov = manifest.provenance
        if prov.file and prov.sha256:
            path = module_dir / prov.file
            if path.is_file():  # provenance is optional — an absent one is not a failure
                actual = sha256_file(path)
                if actual != prov.sha256:
                    raise IntegrityError(
                        f"provenance hash mismatch for {prov.file}: "
                        f"declared {prov.sha256}, computed {actual}"
                    )

    if check_logo and manifest.logo is not None:
        path = module_dir / manifest.logo.name
        if path.is_file():  # logo is optional — an absent one is not a failure
            actual = sha256_file(path)
            if actual != manifest.logo.sha256:
                raise IntegrityError(
                    f"logo hash mismatch for {manifest.logo.name}: "
                    f"declared {manifest.logo.sha256}, computed {actual}"
                )

    if check_readme and manifest.readme is not None:
        path = module_dir / manifest.readme.name
        if path.is_file():  # readme is optional — an absent one is not a failure
            actual = sha256_file(path)
            if actual != manifest.readme.sha256:
                raise IntegrityError(
                    f"readme hash mismatch for {manifest.readme.name}: "
                    f"declared {manifest.readme.sha256}, computed {actual}"
                )

    if manifest.signature is not None:
        verify_signature(
            manifest.artifact.digest, manifest.signature, trusted_public_key=public_key
        )
    elif public_key is not None:
        raise IntegrityError("public_key pinned but manifest carries no signature")
