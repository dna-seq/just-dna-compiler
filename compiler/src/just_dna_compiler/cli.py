"""
Command-line front door for the reference compiler — a thin Typer shell over the Python API
(`validate_spec` / `compile_module` / `reverse_module`). Lives in `just-dna-compiler` (never
`just-dna-format`): the CLI dep (Typer/click) rides with the already-heavy compiler, keeping the
schema package's dependency tier untouched (CONSTITUTION Goal 2).

Exit codes are CI/registry-gateable: `0` success, `1` failure (invalid spec / failed compile).

    just-dna-compiler validate spec/
    just-dna-compiler compile spec/ out/ --strict --ensembl-cache ref.duckdb
    just-dna-compiler reverse parquet_dir/ spec_out/ --version 1.2.3
    just-dna-compiler verify out/ --no-require-marketplace --public-key <base64>
    just-dna-compiler keygen --out key.pem          # the key `sign` needs, and its public half
    just-dna-compiler sign out/ --private-key key.pem
    just-dna-compiler reference --json              # the live authoring reference / JSON Schemas
"""

import json
from pathlib import Path

import typer
from just_dna_format.integrity import IntegrityError, verify_manifest
from just_dna_format.layout import SidecarCollision
from just_dna_format.manifest import ModuleManifest, read_manifest, write_manifest
from just_dna_format.normalize import IDENTITY_AUTHORITY_KEYS
from just_dna_format.reference import authoring_reference, json_schemas
from just_dna_format.signing import (
    generate_private_key_pem,
    public_key_b64_from_pem,
    sign_digest,
)
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER
from pydantic import ValidationError

from just_dna_compiler.compiler import (
    compile_module,
    content_signature,
    reverse_module,
    validate_spec,
)
from just_dna_compiler.draft import (
    DraftError,
    authoring_requirements,
    blank_template,
    stub_template,
)
from just_dna_compiler.hints import describe_table, inspect_rows
from just_dna_compiler.scaffold import scaffold_module

app = typer.Typer(
    add_completion=False,
    help="Validate, compile, and reverse just-dna annotation modules.",
    no_args_is_help=True,
)


def _authority_keys(strip_identity: bool, authority_key: list[str]) -> set[str] | None:
    """Assemble the inject-only authority-key set from the two flags, or None if neither is given."""
    keys: set[str] = set(authority_key)
    if strip_identity:
        keys |= set(IDENTITY_AUTHORITY_KEYS)
    return keys or None


def _echo_messages(result) -> None:
    """Print a validate/compile result's errors, warnings, and info to the right streams."""
    for e in result.errors:
        typer.secho(f"  error: {e}", fg=typer.colors.RED, err=True)
    for w in result.warnings:
        typer.secho(f"  warning: {w}", fg=typer.colors.YELLOW, err=True)
    for i in getattr(result, "info", []):
        typer.secho(f"  info: {i}", fg=typer.colors.BLUE)


@app.command()
def validate(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    strip_identity: bool = typer.Option(
        False, "--strip-identity", help="Inject the identity authority keys (namespace/owner/canonical_id) to strip."
    ),
    authority_key: list[str] = typer.Option(
        [], "--authority-key", help="Extra authority-owned module key to strip (repeatable)."
    ),
    strict: bool = typer.Option(
        False, "--strict/--best-effort",
        help="Pre-flight for a strict compile: escalate the mode-laddered findings to errors, as "
             "`compile --strict` does. Use it whenever the compile you intend to run is strict.",
    ),
) -> None:
    """Validate a spec directory without producing output. Exit 1 if invalid."""
    result = validate_spec(
        spec_dir,
        authority_keys=_authority_keys(strip_identity, authority_key),
        strict=strict,
    )
    _echo_messages(result)
    if result.valid:
        typer.secho(f"valid: {spec_dir}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"INVALID: {spec_dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@app.command()
def compile(  # noqa: A001 — the verb is the command name; shadowing builtins.compile is fine in a CLI module
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
    output_dir: Path = typer.Argument(..., file_okay=False, help="Output dir for parquet + manifest.json"),
    strict: bool = typer.Option(
        False, "--strict/--no-strict", help="All-or-nothing: fail rather than emit a partial artifact with unresolved positions."
    ),
    ensembl_cache: Path | None = typer.Option(
        None, "--ensembl-cache",
        help="DEPRECATED (removed at 1.0): Ensembl reference (.duckdb/parquet dir); routes to "
             "just-dna-enricher. Prefer producing resolution.csv with `just-dna-enricher enrich`.",
    ),
    resolve: bool = typer.Option(
        True, "--resolve/--no-resolve", help="Resolve missing rsid/position via the injected Ensembl reference."
    ),
    compression: str = typer.Option("zstd", "--compression", help="Parquet compression codec."),
    compiled_by: str | None = typer.Option(
        None, "--compiled-by", help="Provenance tag for the manifest (e.g. marketplace-server)."
    ),
    strip_identity: bool = typer.Option(
        False, "--strip-identity", help="Inject the identity authority keys (namespace/owner/canonical_id) to strip."
    ),
    authority_key: list[str] = typer.Option(
        [], "--authority-key", help="Extra authority-owned module key to strip (repeatable)."
    ),
) -> None:
    """Compile a spec directory into a parquet artifact + manifest.json. Exit 1 on failure."""
    result = compile_module(
        spec_dir,
        output_dir,
        compression=compression,
        resolve_with_ensembl=resolve,
        ensembl_cache=ensembl_cache,
        compiled_by=compiled_by,
        authority_keys=_authority_keys(strip_identity, authority_key),
        strict=strict,
    )
    _echo_messages(result)
    if result.success:
        manifest = result.manifest
        typer.secho(f"compiled: {output_dir}", fg=typer.colors.GREEN)
        typer.echo(f"digest: {manifest.artifact.digest if manifest else '?'}")
        typer.echo(f"content_signature: {manifest.content_signature if manifest else '?'}")
        if manifest is not None:
            comp = manifest.compilation
            # The count travels with the flag here for the same reason it does in the manifest (RM44):
            # `fully_resolved: True` over 0 subjects is vacuous, and printing the flag alone is how a
            # reader learns the wrong thing from a true statement.
            typer.echo(
                f"resolution_mode: {comp.resolution_mode}  fully_resolved: {comp.fully_resolved} "
                f"(over {comp.resolution_subjects} variant row(s))"
            )
            if comp.resolution_signature is not None:
                typer.echo(f"resolution_signature: {comp.resolution_signature}")
    else:
        typer.secho(f"COMPILE FAILED: {spec_dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@app.command()
def signature(
    spec_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Module spec directory"),
) -> None:
    """Print the content signature of a spec's raw authored data — no compile, no Ensembl.

    Name- and reference-independent, so a client can compute it and dedup against a registry without
    recompiling (surviving metadata-strip and a recompile against a different reference)."""
    typer.echo(content_signature(spec_dir))


def _read_manifest_or_exit(module_dir: Path) -> ModuleManifest:
    """Load `module_dir/manifest.json`, turning any unreadable manifest into a clean exit-1.

    Shared by `verify` and `sign` so the failure is reported once, in one shape. It matters most for
    `verify`, whose whole job is judging an artifact that may be corrupt or hostile: a manifest that
    is truncated, not JSON, or missing required blocks is an ordinary input to that command, not an
    internal error, and answering it with a pydantic traceback buries the verdict a caller came for.
    """
    manifest_path = module_dir / "manifest.json"
    if not manifest_path.is_file():
        typer.secho(f"no manifest.json in {module_dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    try:
        return read_manifest(manifest_path)
    except (ValidationError, UnicodeDecodeError, OSError) as exc:
        typer.secho(
            f"manifest.json in {module_dir} could not be read as a module manifest: {exc}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from exc


@app.command()
def verify(
    module_dir: Path = typer.Argument(
        ..., exists=True, file_okay=False, help="Compiled module directory (holding manifest.json)"
    ),
    require_marketplace: bool = typer.Option(
        True,
        "--require-marketplace/--no-require-marketplace",
        help="Demand compile_success and compiled_by=marketplace-server. Off for a local artifact.",
    ),
    public_key: str | None = typer.Option(
        None, "--public-key", help="Base64 raw Ed25519 key the manifest signature MUST verify against."
    ),
    check_inputs: bool = typer.Option(False, "--check-inputs", help="Also hash the declared inputs[]."),
    check_logs: bool = typer.Option(False, "--check-logs", help="Also hash any logs[] present on disk."),
    check_provenance: bool = typer.Option(
        False, "--check-provenance", help="Also hash the provenance document, if declared and present."
    ),
    check_logo: bool = typer.Option(False, "--check-logo", help="Also hash the logo, if declared."),
    check_readme: bool = typer.Option(
        False, "--check-readme", help="Also hash the readme, if declared."
    ),
    check_derived: bool = typer.Option(
        False,
        "--check-derived",
        help="Also hash any declared derived-fact sidecar CSVs present on disk.",
    ),
) -> None:
    """Verify a compiled module against its manifest (SPEC §5 verify-then-install). Exit 1 on failure.

    The verify-only path the format has always specified and never exposed: `verify_manifest` and the
    signature check live in `just-dna-format`, which ships no CLI of its own (Typer would breach its
    pydantic-plus-cryptography dependency floor), so until now a consumer had to write Python to check
    a download. It re-hashes every artifact file, recomputes `artifact.digest` over the set, and — when
    a key is pinned — verifies the Ed25519 signature over that digest.
    """
    manifest = _read_manifest_or_exit(module_dir)
    try:
        verify_manifest(
            module_dir,
            manifest,
            require_marketplace=require_marketplace,
            check_inputs=check_inputs,
            check_logs=check_logs,
            check_provenance=check_provenance,
            check_logo=check_logo,
            check_readme=check_readme,
            check_derived=check_derived,
            public_key=public_key,
        )
    except IntegrityError as exc:
        typer.secho(f"VERIFY FAILED: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"verified: {module_dir}", fg=typer.colors.GREEN)
    typer.echo(f"digest: {manifest.artifact.digest}  files: {len(manifest.artifact.files)}")
    # Say which of the three trust questions were actually answered — an unsigned artifact that
    # verifies is a weaker statement than a signed one, and reporting them alike would blur that.
    typer.echo(
        f"signature: {'verified against the pinned key' if public_key else
                      ('present, self-consistent only' if manifest.signature else 'absent')}"
    )


@app.command()
def sign(
    module_dir: Path = typer.Argument(
        ..., exists=True, file_okay=False, help="Compiled module directory (holding manifest.json)"
    ),
    private_key: Path = typer.Option(
        ..., "--private-key", exists=True, dir_okay=False, help="Ed25519 private key PEM."
    ),
) -> None:
    """Sign a compiled module's `artifact.digest` and write the signature into its manifest.json.

    Signs the digest, never the files directly: the digest is already a Merkle root over the whole
    file set, so one signature covers every artifact byte, and re-signing after any edit is impossible
    to forget — the digest moves and the old signature stops verifying.
    """
    manifest = _read_manifest_or_exit(module_dir)
    manifest.signature = sign_digest(manifest.artifact.digest, private_key.read_bytes())
    write_manifest(manifest, module_dir / "manifest.json")
    typer.secho(f"signed: {module_dir / 'manifest.json'}", fg=typer.colors.GREEN)
    typer.echo(f"digest: {manifest.artifact.digest}")
    typer.echo(f"public key: {manifest.signature.public_key}")


@app.command()
def keygen(
    out: Path | None = typer.Option(
        None, "--out", dir_okay=False,
        help="Write the private key PEM here (refuses to overwrite). Omit to print it to stdout.",
    ),
) -> None:
    """Generate an Ed25519 signing key: the private PEM `sign` needs, and the public key `verify` pins.

    Closes the same gap `verify` was built to close, one step upstream. `verify_manifest` and the
    signing helpers live in `just-dna-format`, which ships no CLI of its own (Typer would breach its
    pydantic-plus-cryptography dependency floor) — so `sign --private-key` demanded a file the
    toolchain had no way to produce, and `verify --public-key` demanded a string derivable only by
    calling `public_key_b64_from_pem` from Python. Both halves now have a route.

    The key is unencrypted PKCS#8, which is what `sign_digest` reads. That is a deliberate limit
    rather than an oversight: this command bootstraps a key, it is not a key-management system, and
    pretending otherwise by adding a passphrase prompt would imply custody guarantees nothing here
    provides. A publishing key belongs in whatever secret store the publisher already runs.
    """
    private_key_pem = generate_private_key_pem()
    public_key = public_key_b64_from_pem(private_key_pem)
    if out is None:
        typer.echo(private_key_pem.decode("ascii"), nl=False)
        typer.secho(f"public key: {public_key}", fg=typer.colors.GREEN, err=True)
        return
    if out.exists():
        # Never silently: overwriting a signing key orphans every signature made with it, and the
        # artifacts are immutable, so there is no re-signing the ones already published.
        typer.secho(
            f"{out} already exists — refusing to overwrite a signing key. Every signature made with "
            f"the old key would stop verifying, and a published artifact's bytes are never mutated.",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=1)
    out.write_bytes(private_key_pem)
    out.chmod(0o600)
    typer.secho(f"private key: {out} (mode 600)", fg=typer.colors.GREEN)
    typer.echo(f"public key: {public_key}")


@app.command()
def reference(
    as_json: bool = typer.Option(
        True, "--json/--summary", help="Full JSON (default), or a one-line-per-table summary."
    ),
    schemas: bool = typer.Option(
        False, "--schemas", help="Emit the per-model JSON Schemas instead of the authoring reference."
    ),
) -> None:
    """Print the authoring reference — every model's columns, vocabularies and requirements.

    Generated from the live pydantic models, so it cannot drift from what the compiler accepts. That
    is the point: it is the drift-proof replacement for a hand-kept spec dump, and the consumer that
    most needs it (an MCP surface offering an author the valid values) had to import
    `just_dna_format.reference` and write Python, because the schema tier ships no CLI. `describe`
    answers the same question for **one** table; this answers it for all of them at once, plus the
    vocabularies, the open-vs-closed flag, the `REQUIRED_ANY_OF` rules and the recommended palette.
    """
    payload = json_schemas() if schemas else authoring_reference()
    if as_json:
        typer.echo(json.dumps(payload, indent=2, sort_keys=False))
        return
    if schemas:
        for name in payload:
            typer.echo(name)
        return
    typer.echo(f"schema_version: {payload['schema_version']}")
    for model, fields in payload["models"].items():
        required = [f["name"] for f in fields if f.get("required")]
        typer.echo(f"{model}: {len(fields)} column(s), {len(required)} required — {', '.join(required)}")
    typer.echo(f"vocabularies: {', '.join(payload['vocabularies'])}")
    typer.echo(f"open/recommended: {', '.join(payload['open_recommended'])}")
    typer.echo(f"reserved names: {', '.join(payload['reserved_names']) or '(none)'}")


@app.command()
def reverse(
    parquet_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Compiled parquet directory"),
    output_dir: Path = typer.Argument(..., file_okay=False, help="Output dir for the reconstructed spec"),
    module_name: str | None = typer.Option(None, "--module-name", help="Override the recovered module name."),
    title: str | None = typer.Option(None, "--title"),
    description: str | None = typer.Option(None, "--description"),
    report_title: str | None = typer.Option(None, "--report-title"),
    icon: str = typer.Option("database", "--icon"),
    color: str = typer.Option("#6435c9", "--color"),
    version: str | None = typer.Option(None, "--version", help="Advisory module.version to re-emit into the spec."),
    resolution: bool = typer.Option(
        True, "--resolution/--no-resolution",
        help="Also emit resolution.csv (the resolved facts), so reverse→compile is fully offline.",
    ),
    genome_build: str | None = typer.Option(
        None, "--genome-build",
        help="Override the build. Read from the artifact's manifest.json by default; only needed for "
             "a bare parquet directory that carries no manifest.",
    ),
) -> None:
    """Reverse a compiled parquet artifact back into the authored spec DSL (yaml + csv)."""
    # An output directory already carrying two copies of one sidecar cannot be written to without
    # choosing between them, and that choice is not this tool's to make. The exception says which
    # files collide, so print it as the diagnosis it is rather than as a traceback; nothing was
    # written when it is raised.
    try:
        out = reverse_module(
            parquet_dir,
            output_dir,
            module_name=module_name,
            title=title,
            description=description,
            report_title=report_title,
            icon=icon,
            color=color,
            version=version,
            write_resolution=resolution,
            genome_build=genome_build,
        )
    except SidecarCollision as collision:
        typer.secho(f"  error: {collision}", fg=typer.colors.RED)
        raise typer.Exit(1) from collision
    typer.secho(f"reversed: {out}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()


# ── Authoring surface (0.5): templating and requirements, pure and offline ───────────────────────
# These live here, not on `just-dna-enricher`, because they need no network: they are generated from
# the live models. `template` shipped on the enricher CLI first, which meant an author who installed
# only the tier that *owns the CSV shape* had the API and no command.


@app.command()
def template(
    kind: str = typer.Argument(..., help="Authored CSV to emit a header for, e.g. repeat_alleles.csv"),
) -> None:
    """Print a header-only CSV for one authored table kind, generated from the live models.

    The requirements go to stderr, so `just-dna-compiler template x.csv > x.csv` stays clean.
    """
    try:
        typer.echo(blank_template(kind), nl=False)
        reqs = authoring_requirements(kind)
    except DraftError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"required: {', '.join(reqs['always'])}", fg=typer.colors.BLUE, err=True)
    for group in reqs["any_of"]:
        typer.secho(f"and one of: {' + '.join(group)}", fg=typer.colors.BLUE, err=True)
    if reqs["defaulted"]:
        # The columns that bite: they have a default, so nothing calls them required, but an empty
        # cell arrives as None and fails on type. `stub` writes them out for you.
        shown = ", ".join(f"{k}={v}" for k, v in reqs["defaulted"].items())
        typer.secho(f"must not be left empty (defaults): {shown}", fg=typer.colors.YELLOW, err=True)


@app.command()
def stub(
    kind: str = typer.Argument(..., help="Authored CSV to emit stub rows for"),
    rows: int = typer.Option(1, "--rows", min=1, help="How many stub rows to emit."),
) -> None:
    """Print a header plus stub rows, with a placeholder wherever a human must decide.

    An unreplaced stub cannot compile — it is refused by name and row — so a half-filled table fails
    loudly on exactly the rows still to do rather than compiling into a module that asserts nothing.
    """
    try:
        typer.echo(stub_template(kind, rows=rows), nl=False)
    except DraftError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.secho(f"replace every {TEMPLATE_PLACEHOLDER} before compiling", fg=typer.colors.BLUE, err=True)


@app.command()
def requirements(
    kind: str = typer.Argument(..., help="Authored CSV to describe"),
    as_json: bool = typer.Option(False, "--json", help="Emit the machine-readable form."),
) -> None:
    """What an author must supply for one table kind: always, one-of, and never-empty defaults."""
    try:
        reqs = authoring_requirements(kind)
    except DraftError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if as_json:
        typer.echo(json.dumps(reqs, indent=2, sort_keys=True))
        return
    typer.echo(f"{kind}")
    typer.echo(f"  always:    {', '.join(reqs['always']) or '(none)'}")
    for group in reqs["any_of"]:
        typer.echo(f"  one of:    {' + '.join(group)}")
    for column, default in reqs["defaulted"].items():
        typer.echo(f"  default:   {column}={default}  (never leave empty)")
    typer.echo(f"  optional:  {', '.join(reqs['optional']) or '(none)'}")


@app.command()
def scaffold(
    spec_dir: Path = typer.Argument(..., file_okay=False, help="Module spec directory to create"),
    kind: list[str] = typer.Option([], "--kind", help="Authored table kind to stub (repeatable)."),
    name: str | None = typer.Option(None, "--name", help="Machine name for the module block."),
    rows: int = typer.Option(1, "--rows", min=1, help="Stub rows per table."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Report the plan; write nothing."),
) -> None:
    """Create module_spec.yaml plus a stub CSV per kind. Never overwrites; existing files are kept.

    Re-runnable: run it again with a different --kind to add a table to a module that already exists.
    """
    try:
        plan = scaffold_module(spec_dir, kinds=kind, name=name, rows=rows, dry_run=dry_run)
    except DraftError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    for warning in plan.warnings:
        typer.secho(f"  note: {warning}", fg=typer.colors.YELLOW, err=True)
    verb = "would create" if dry_run else "created"
    for path in plan.created:
        typer.secho(f"  {verb}: {path.name}", fg=typer.colors.GREEN)
    for path, reason in plan.refused:
        typer.secho(f"  kept:  {path.name} — {reason}", fg=typer.colors.YELLOW, err=True)
    typer.echo(str(plan))


@app.command()
def describe(
    kind: str = typer.Argument(..., help="Authored CSV to describe, e.g. variants.csv"),
) -> None:
    """Emit the full machine description of one table kind: columns, options, requirements.

    Always JSON — this is the form an authoring tool or MCP surface consumes, beside
    `just_dna_format.reference.authoring_reference()`.
    """
    try:
        typer.echo(json.dumps(describe_table(kind), indent=2))
    except DraftError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def hint(
    kind: str = typer.Argument(..., help="Authored CSV the rows belong to"),
    rows_file: Path | None = typer.Option(
        None, "--file", exists=True, dir_okay=False, help="Read the CSV text from a file."
    ),
    row: str | None = typer.Option(None, "--row", help="A single CSV row (or header+rows) inline."),
    as_json: bool = typer.Option(False, "--json", help="Emit the full machine report."),
) -> None:
    """Inspect authored CSV rows and report what is wrong, what the model rewrites, and what is left
    to you on purpose. **Writes nothing** — the corrected text goes to stdout for you to use or not.

    Offline: this is the pure half. The enricher adds the lookups that need a reference.
    """
    if (rows_file is None) == (row is None):
        typer.secho("give exactly one of --file or --row", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    text = rows_file.read_text(encoding="utf-8") if rows_file is not None else f"{row}\n"
    try:
        report = inspect_rows(kind, text)
    except DraftError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if as_json:
        typer.echo(report.to_json())
        return
    for line in report.csv_out:
        typer.echo(line)
    for alteration in report.alterations:
        typer.secho(
            f"  normalized row {alteration.row} {alteration.column}: "
            f"{alteration.before!r} -> {alteration.after!r} ({alteration.note})",
            fg=typer.colors.YELLOW,
            err=True,
        )
    colours = {"error": typer.colors.RED, "warning": typer.colors.YELLOW, "info": typer.colors.BLUE}
    for finding in report.findings:
        # `line` and not `row`: the author is looking at a file in an editor, and `validate`/`compile`
        # already name a location as `line 2 [column]` (1-based, header included). Two error surfaces
        # over one file used to use two conventions and state neither (S18).
        where = f"line {finding.line} " if finding.line is not None else ""
        column = f"[{finding.column}] " if finding.column else ""
        typer.secho(f"  {finding.level}: {where}{column}{finding.message}", fg=colours[finding.level], err=True)
    typer.secho(str(report), fg=typer.colors.GREEN, err=True)
