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
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from pydantic import BaseModel

from just_dna_format.frequency import FREQUENCY_FACT_FIELDS
from just_dna_format.gene_metrics import GENE_METRICS_FACT_FIELDS
from just_dna_format.literature import LITERATURE_FACT_FIELDS
from just_dna_format.manifest import (
    MARKETPLACE_COMPILED_BY,
    Artifact,
    FileEntry,
    ModuleManifest,
    Signature,
)
from just_dna_format.resolution import RESOLUTION_FACT_FIELDS

SHA256_PREFIX: str = "sha256:"
_CHUNK: int = 1 << 20  # 1 MiB streaming reads


class IntegrityError(Exception):
    """Raised when a file hash, artifact digest, or trust check fails verification."""


def verify_signature(
    digest: str, signature: Signature, *, trusted_public_key: Optional[str] = None
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
        raise IntegrityError(f"artifact digest signature is invalid: {exc}")


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


def artifact_digest(files: list[FileEntry]) -> str:
    """
    Merkle-style root over the file set (SPEC §5): build the JSON array
    `[{"name","sha256","size"}, ...]` sorted by name, serialized with sorted keys and no
    whitespace, then hash. Verifying this one digest verifies the whole set, and it is the
    version's immutable content identity — independent of the order files were listed in.
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


def content_signature(tables: Mapping[str, Sequence[BaseModel]]) -> str:
    """Stable content identity over the RAW authored data rows — the canonical, owned algorithm.

    Distinct from `artifact_digest`: that hashes the *compiled parquet* bytes, which are
    GRCh38-coordinate-relative and therefore depend on the Ensembl reference the resolver was given
    (and move if the module is recompiled elsewhere). `content_signature` instead hashes the authored
    *data* rows as parsed — so it is:

    - **Ensembl/build-independent** — computed from the rows *before* resolution (an rsid-only row is
      hashed as authored, not as resolved coordinates), so recompiling against a different/complete
      reference does not change it.
    - **Name/metadata-independent** — only the data tables feed it; `module_spec.yaml` (name, version,
      namespace, display) is excluded, so a metadata edit or a registry strip does not change it.
    - **Normalized** — each row is `model_dump(mode="json", exclude_none=True)`, so CSV reformatting
      (whitespace, quoting, column reorder, cell canonicalization like `1.00`→`1.0`) and additive
      schema growth (a new optional column left unset) do not change it.
    - **Deterministically sorted, order-independent** — the normalized rows of each file are sorted by
      their canonical JSON, and files are sorted by name, so re-ordering rows yields the *same*
      signature. (This is deliberately unlike `artifact.digest`, which *preserves* authored row order:
      the two are different identities — a byte-reproducibility digest vs. a content-dedup key.)

    `tables` maps each data-CSV filename (`variants.csv`, `studies.csv`, and the 0.4 table kinds) to
    its parsed, validated rows. The result is the enabling identity for content-level dedup that
    survives import/recompile and metadata-strip. It is the reference algorithm a marketplace's
    `find_versions_by_content` should adopt (see docs/PROPOSAL_0_4_1.md).
    """
    listing = [
        {
            "file": filename,
            "rows": sorted(
                json.dumps(
                    row.model_dump(mode="json", exclude_none=True),
                    sort_keys=True,
                    separators=(",", ":"),
                )
                for row in rows
            ),
        }
        for filename, rows in tables.items()
    ]
    listing.sort(key=lambda part: part["file"])
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
    public_key: Optional[str] = None,
) -> None:
    """
    Verify a downloaded module against its manifest (SPEC §5 verify-then-install).

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

    if manifest.signature is not None:
        verify_signature(
            manifest.artifact.digest, manifest.signature, trusted_public_key=public_key
        )
    elif public_key is not None:
        raise IntegrityError("public_key pinned but manifest carries no signature")
