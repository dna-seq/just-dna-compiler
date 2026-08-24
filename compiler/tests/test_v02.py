"""0.2.0 additive features end-to-end through the compiler: ClinVar stats, structured provenance,
gene-panel passthrough, the `negatives` field, module logo, `icon_set`, and signed-manifest verify.

All run with resolve_with_ensembl=False (no reference/network needed)."""

import json
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_format.integrity import IntegrityError, sha256_file, verify_manifest
from just_dna_format.manifest import README_CANDIDATES
from just_dna_format.signing import generate_private_key_pem, public_key_b64_from_pem, sign_digest

_YAML = """\
schema_version: "1.0"
module:
  name: demo2
  title: Demo Two
  description: A demo module
  report_title: Demo Report
  icon: shield
  icon_set: awesome
  color: "#21ba45"
defaults:
  curator: tester
  method: manual
genome_build: GRCh38
panel:
  source: clinvar
  reference: "2026-06"
  reference_sha256: "sha256:deadbeef"
  genes: [BRCA1, BRCA2]
  significance: [pathogenic, likely_pathogenic]
"""

# Two clinvar rows, one pathogenic; one row carries `negatives`.
_VARIANTS = """\
rsid,chrom,start,ref,alts,genotype,weight,state,conclusion,negatives,gene,category,clinvar,pathogenic,benign
rs1801133,1,11856378,G,A,A/G,0.5,protective,ok,carries a trade-off,MTHFR,metabolism,true,false,false
rs7412,19,44908822,C,T,C/T,-0.3,risk,bad,,APOE,lipids,true,true,false
"""

_STUDIES = """\
rsid,pmid,population,p_value,conclusion,study_design
rs1801133,[PMID: 12345],EUR,0.01,assoc,GWAS
rs7412,67890,EUR,0.001,assoc,meta-analysis
"""

# A derived-fact sidecar: machine-produced, fact-hashed, byte-hashed into `manifest.derived` (S26).
# The two studies rows cite 12345/67890, so this is the citation check for one of them.
_LITERATURE = """\
pmid,doi,pmcid,exists,is_open_access,quotes_authored,quotes_found,source,status,fetched_at
12345,10.1000/demo,PMC12345,true,true,0,,pubmed,resolved,2026-08-01T20:55:37Z
"""

_PROVENANCE = {
    "generator": "agent-x",
    "model": "claude",
    "agent_version": "1.0",
    "items": [
        {"variant_key": "rs1801133", "rationale": "curated", "human_reviewed": True},
        {"variant_key": "rs7412", "confidence": 0.9},
    ],
}


def _write_spec(
    d: Path, *, provenance: bool = True, logo: bool = True, readme: bool = True
) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (d / "variants.csv").write_text(_VARIANTS, encoding="utf-8")
    (d / "studies.csv").write_text(_STUDIES, encoding="utf-8")
    if provenance:
        (d / "provenance.json").write_text(json.dumps(_PROVENANCE), encoding="utf-8")
    if logo:
        (d / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n fake-logo-bytes")
    if readme:
        (d / "README.md").write_text(
            "# demo2\n\nCandidate findings only — one association is not significant.\n",
            encoding="utf-8",
        )
    return d


def _compile(spec: Path, out: Path):
    result = compile_module(spec, out, resolve_with_ensembl=False, compiled_by="marketplace-server")
    assert result.success, result.errors
    assert result.manifest is not None
    return result.manifest


def test_clinvar_stats_counts(tmp_path: Path) -> None:
    m = _compile(_write_spec(tmp_path / "s"), tmp_path / "o")
    assert m.stats.clinvar_count == 2
    assert m.stats.pathogenic_count == 1
    assert m.stats.benign_count == 0


def test_panel_passthrough_verbatim(tmp_path: Path) -> None:
    m = _compile(_write_spec(tmp_path / "s"), tmp_path / "o")
    assert m.panel is not None
    assert m.panel.source == "clinvar"
    assert m.panel.genes == ["BRCA1", "BRCA2"]
    assert m.panel.significance == ["pathogenic", "likely_pathogenic"]
    assert m.panel.reference_sha256 == "sha256:deadbeef"
    # Panel does not materialize variants: count still reflects only variants.csv.
    assert m.stats.variant_count == 2


def test_the_panel_block_still_compiles_and_says_it_is_going(tmp_path: Path) -> None:
    """RM4: deprecated in 0.6, removed at 1.0 — warn-only, so nothing about the test above changes.

    The warning has to be *actionable* (the charter scopes the cadence on exactly that), which here
    means naming the release it goes in, what to do, and what took over the one job the block still
    had. It is emitted once, by `validate_spec`, and `compile_module` seeds its warnings from there —
    so a module that carries the block does not print it twice, and a catalog reading only the
    published manifest still sees it.
    """
    spec = _write_spec(tmp_path / "s")
    result = compile_module(spec, tmp_path / "o", resolve_with_ensembl=False)
    assert result.success, result.errors

    emitted = [w for w in result.warnings if "`panel:` block" in w]
    assert len(emitted) == 1
    assert "removed at 1.0" in emitted[0] and "dataset" in emitted[0]
    assert result.manifest is not None
    assert emitted == [w for w in result.manifest.compilation.warnings if "`panel:` block" in w]
    assert [w for w in validate_spec(spec).warnings if "`panel:` block" in w] == emitted

    # And a module without the block is silent: a deprecation nobody triggered is not a finding.
    plain = tmp_path / "plain"
    _write_spec(plain)
    (plain / "module_spec.yaml").write_text(
        _YAML[: _YAML.index("panel:")], encoding="utf-8"
    )
    quiet = compile_module(plain, tmp_path / "o2", resolve_with_ensembl=False)
    assert quiet.success and not [w for w in quiet.warnings if "`panel:` block" in w]


def test_icon_set_flows_to_manifest(tmp_path: Path) -> None:
    m = _compile(_write_spec(tmp_path / "s"), tmp_path / "o")
    assert m.display.icon == "shield"
    assert m.display.icon_set == "awesome"


def test_negatives_lands_in_weights(tmp_path: Path) -> None:
    out = tmp_path / "o"
    _compile(_write_spec(tmp_path / "s"), out)
    weights = pl.read_parquet(out / "weights.parquet")
    assert "negatives" in weights.columns
    row = weights.filter(pl.col("rsid") == "rs1801133")
    assert row["negatives"].to_list() == ["carries a trade-off"]


def test_provenance_summary_and_hash(tmp_path: Path) -> None:
    out = tmp_path / "o"
    m = _compile(_write_spec(tmp_path / "s"), out)
    assert m.provenance is not None
    assert m.provenance.item_count == 2
    assert m.provenance.generator == "agent-x"
    assert m.provenance.file == "provenance.json"
    assert (out / "provenance.json").is_file()
    assert m.provenance.sha256 == sha256_file(out / "provenance.json")


def test_logo_hashed_and_shipped(tmp_path: Path) -> None:
    out = tmp_path / "o"
    m = _compile(_write_spec(tmp_path / "s"), out)
    assert m.logo is not None
    assert m.logo.name == "logo.png"
    assert (out / "logo.png").is_file()
    assert m.logo.sha256 == sha256_file(out / "logo.png")
    # Logo is NOT an artifact file (out of digest).
    assert "logo.png" not in {f.name for f in m.artifact.files}


def test_readme_hashed_and_shipped(tmp_path: Path) -> None:
    """`manifest.readme` mirrors `logo`: shipped beside the parquet, hashed, out of the digest (S25).

    The field exists so prose can be *served and verified* by anything reading manifests — a registry,
    an installer, a mirror. Before it, a publisher's README sat on disk attested by nothing, so a
    registry that (rightly) refuses to serve files it cannot hash could not serve it at all."""
    out = tmp_path / "o"
    m = _compile(_write_spec(tmp_path / "s"), out)
    assert m.readme is not None
    assert m.readme.name == "README.md"
    assert (out / "README.md").is_file()
    assert m.readme.sha256 == sha256_file(out / "README.md")
    assert m.readme.size == (out / "README.md").stat().st_size
    # Prose is not content: out of artifact.files, so out of the digest.
    assert "README.md" not in {f.name for f in m.artifact.files}
    # And not an input either — `inputs[]` is the authored data, which a readme is not.
    assert "README.md" not in {f.name for f in m.inputs}


def test_readme_discovery_prefers_the_conventional_spelling(tmp_path: Path) -> None:
    """Discovery order is fixed and stated, because two candidates on disk must not pick by luck.

    `README_CANDIDATES` puts the uppercase stem first and sorts extensions (`md` before `rst`/`txt`),
    so a directory carrying several readmes resolves the same way on every machine — the deterministic
    -ordering rule the rest of this codebase applies to emitted rows applies to a discovered file too."""
    spec = _write_spec(tmp_path / "s", readme=False)
    (spec / "readme.md").write_text("lowercase\n", encoding="utf-8")
    (spec / "README.txt").write_text("plain text\n", encoding="utf-8")
    (spec / "README.md").write_text("the conventional one\n", encoding="utf-8")

    m = _compile(spec, tmp_path / "o")
    assert m.readme is not None
    assert m.readme.name == "README.md"
    assert README_CANDIDATES[0] == "README.md"
    # A non-markdown readme is still legal — the extension travels for whoever renders it.
    alt = _write_spec(tmp_path / "s2", readme=False)
    (alt / "README.rst").write_text("Title\n=====\n", encoding="utf-8")
    assert _compile(alt, tmp_path / "o2").readme.name == "README.rst"


def test_unsupported_readme_extension_rejected(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path / "s", readme=False)
    doc = spec / "README.docx"
    doc.write_bytes(b"PK\x03\x04not-really-a-docx")
    result = compile_module(
        spec, tmp_path / "o", resolve_with_ensembl=False, readme_file=doc
    )
    assert not result.success
    assert any("readme must be one of" in e for e in result.errors)


def test_optional_files_do_not_change_either_identity(tmp_path: Path) -> None:
    """Both halves of identity, not just the digest — the property S25's reporter reasoned from.

    They rejected putting `README.md` in `artifact.files` themselves, because on an immutable registry
    a corrected caveat would then cost a version number and the fixed module would collide with its
    own predecessor under a content-dedup check. That argument only holds if the readme stays out of
    `content_signature` too, so this computes both rather than asserting the digest alone."""
    full = _compile(_write_spec(tmp_path / "full"), tmp_path / "of")
    bare = _compile(
        _write_spec(tmp_path / "bare", provenance=False, logo=False, readme=False),
        tmp_path / "ob",
    )
    # provenance.json + logo.png + README.md are out of artifact.digest → identical byte identity.
    assert full.artifact.digest == bare.artifact.digest
    assert full.content_signature == bare.content_signature
    assert full.readme is not None and bare.readme is None


def test_editing_the_readme_moves_no_identity(tmp_path: Path) -> None:
    """The motivating case: fixing a typo in a caveat must be a patch, not a new version.

    Same authored data, a rewritten readme. Both identities must be byte-identical and only the
    readme's own hash may move — otherwise a publisher correcting a sentence mints a module that
    collides with its predecessor."""
    spec = _write_spec(tmp_path / "s")
    first = _compile(spec, tmp_path / "o1")
    (spec / "README.md").write_text(
        "# demo2\n\nCandidate findings only — one association is **not** significant.\n",
        encoding="utf-8",
    )
    second = _compile(spec, tmp_path / "o2")

    assert second.artifact.digest == first.artifact.digest
    assert second.content_signature == first.content_signature
    assert second.readme.sha256 != first.readme.sha256


def test_unsupported_logo_extension_rejected(tmp_path: Path) -> None:
    spec = _write_spec(tmp_path / "s", logo=False)
    gif = spec / "logo.gif"
    gif.write_bytes(b"GIF89a")
    # An unsupported logo now surfaces as a compile error, not an uncaught exception.
    result = compile_module(spec, tmp_path / "o", resolve_with_ensembl=False, logo_file=gif)
    assert not result.success
    assert any("logo must be one of" in e for e in result.errors)


def test_derived_sidecars_are_attested_without_becoming_content(tmp_path: Path) -> None:
    """`manifest.derived` byte-hashes the sidecar CSVs so they can be served (S26).

    They were reachable by nobody: `_INPUT_FILES` excludes them on purpose (they are fact-hashed, not
    byte-hashed) and only their *parquets* are in `_OUTPUT_FILES`, so a registry serving only what the
    manifest attests could not hand back the table that produced a parquet. The two hashes answer
    different questions and this test pins both: the byte hash appears, and neither identity moves."""
    spec = _write_spec(tmp_path / "s")
    bare = _compile(spec, tmp_path / "o1")
    assert bare.derived == []  # nothing fabricated when no sidecar exists

    (spec / "literature.csv").write_text(_LITERATURE, encoding="utf-8")
    with_sidecar = _compile(spec, tmp_path / "o2")

    names = {e.name for e in with_sidecar.derived}
    assert names == {"literature.csv"}
    entry = with_sidecar.derived[0]
    assert entry.sha256 == sha256_file(spec / "literature.csv")

    # Attested, but not content: the sidecar's own parquet is in the artifact and its CSV is not.
    assert "literature.parquet" in {f.name for f in with_sidecar.artifact.files}
    assert "literature.csv" not in {f.name for f in with_sidecar.artifact.files}
    assert "literature.csv" not in {f.name for f in with_sidecar.inputs}
    # The authored data did not change, so the authored identity must not have.
    assert with_sidecar.content_signature == bare.content_signature


def test_the_byte_hash_never_displaces_the_fact_hash(tmp_path: Path) -> None:
    """The trap this field creates, pinned: a rewrite that preserves the FACTS moves the byte hash.

    That is why `derived[]` is excluded from `_INPUT_FILES` and why its docstring says the byte hash is
    transport only. A consumer reading it as identity would call a legitimate re-emission tampering —
    the exact failure the fact signatures exist to prevent, so the two must be observably independent."""
    spec = _write_spec(tmp_path / "s")
    (spec / "literature.csv").write_text(_LITERATURE, encoding="utf-8")
    first = _compile(spec, tmp_path / "o1")

    # Same facts, different bytes: a trailing blank line and a reordered column would both do it.
    (spec / "literature.csv").write_text(_LITERATURE + "\n", encoding="utf-8")
    second = _compile(spec, tmp_path / "o2")

    assert second.derived[0].sha256 != first.derived[0].sha256, "byte hash should track bytes"
    assert second.literature.signature == first.literature.signature, "facts are unchanged"
    assert second.content_signature == first.content_signature


def test_verify_catches_a_tampered_sidecar_but_tolerates_an_absent_one(tmp_path: Path) -> None:
    """Sidecars live beside the spec, so a consumer holding only the artifact has none — skip, not fail.

    Mirrors `logs`, and deliberately not `inputs`, which *raises* on a missing file. That asymmetry is
    the reporter's own requirement ("an absent one must not invalidate a module") and it is what makes
    the check usable against a module dir that was never meant to carry them."""
    spec = _write_spec(tmp_path / "s")
    (spec / "literature.csv").write_text(_LITERATURE, encoding="utf-8")
    out = tmp_path / "o"
    m = _compile(spec, out)

    # The artifact dir carries no sidecar at all: every entry is skipped, nothing fails.
    verify_manifest(out, m, check_derived=True)

    # Beside the spec, where they really live, a substitution is caught.
    (out / "literature.csv").write_text(_LITERATURE.replace("12345", "99999"), encoding="utf-8")
    with pytest.raises(IntegrityError, match="derived sidecar hash mismatch"):
        verify_manifest(out, m, check_derived=True)
    verify_manifest(out, m)  # off by default


def test_verify_manifest_checks_optional_files(tmp_path: Path) -> None:
    out = tmp_path / "o"
    m = _compile(_write_spec(tmp_path / "s"), out)
    verify_manifest(
        out, m, check_logs=True, check_provenance=True, check_logo=True, check_readme=True
    )

    (out / "provenance.json").write_text("tampered", encoding="utf-8")
    with pytest.raises(IntegrityError, match="provenance hash mismatch"):
        verify_manifest(out, m, check_provenance=True)


def test_verify_catches_a_tampered_readme(tmp_path: Path) -> None:
    """A served readme must be *verifiable*, which is the whole reason it is a hashed `FileEntry`.

    Also pins the tri-state the other optional assets use: an absent readme is skipped rather than
    failed, since a consumer may legitimately not download one."""
    out = tmp_path / "o"
    m = _compile(_write_spec(tmp_path / "s"), out)

    (out / "README.md").write_text("substituted prose\n", encoding="utf-8")
    with pytest.raises(IntegrityError, match="readme hash mismatch"):
        verify_manifest(out, m, check_readme=True)
    # Off by default: the same tampered file passes when the caller did not ask.
    verify_manifest(out, m)

    (out / "README.md").unlink()
    verify_manifest(out, m, check_readme=True)  # absent ≠ failed


def test_signed_manifest_verifies_with_pinned_key(tmp_path: Path) -> None:
    out = tmp_path / "o"
    m = _compile(_write_spec(tmp_path / "s"), out)
    pem = generate_private_key_pem()
    m.signature = sign_digest(m.artifact.digest, pem)

    verify_manifest(out, m, public_key=public_key_b64_from_pem(pem))
    with pytest.raises(IntegrityError, match="pinned"):
        verify_manifest(out, m, public_key=public_key_b64_from_pem(generate_private_key_pem()))


def test_pinned_key_but_unsigned_manifest_fails(tmp_path: Path) -> None:
    out = tmp_path / "o"
    m = _compile(_write_spec(tmp_path / "s"), out)
    with pytest.raises(IntegrityError, match="no signature"):
        verify_manifest(out, m, public_key=public_key_b64_from_pem(generate_private_key_pem()))


# ── S52: a per-field outrank record, and what it must not disturb ────────────────────────────────


def test_an_outrank_record_survives_the_compile_byte_for_byte(tmp_path: Path) -> None:
    """The file is copied and hashed, not re-serialized, so the prose reaches a reader unchanged.

    That matters more here than for the other item fields: the record's whole value is a human
    reading *why* a row disagrees with a source, and a round-trip through our models would be a
    silent place for it to be reshaped.
    """
    from just_dna_format.manifest import ProvenanceDoc

    why = "PMID 24489884 was retracted in 2025; ClinVar has not absorbed it."
    doc = {
        **_PROVENANCE,
        "items": [{"variant_key": "rs1801133", "outranks": {"clin_sig": why}}],
    }
    spec = _write_spec(tmp_path / "s", provenance=False)
    (spec / "provenance.json").write_text(json.dumps(doc), encoding="utf-8")

    out = tmp_path / "o"
    m = _compile(spec, out)
    assert m.provenance is not None
    assert m.provenance.sha256 == sha256_file(out / "provenance.json")

    shipped = ProvenanceDoc.model_validate_json((out / "provenance.json").read_text())
    assert shipped.items[0].outranks == {"clin_sig": why}


def test_outranks_does_not_change_what_item_count_counts(tmp_path: Path) -> None:
    """The reason shape 1 was chosen over a `field` on the item (S52).

    `Provenance.item_count` is a published number meaning *variants carrying a record*. One item
    justifying two columns must stay one item, or every consumer already reading that number starts
    reading a different quantity with no signal that it changed.
    """
    doc = {
        **_PROVENANCE,
        "items": [
            {
                "variant_key": "rs1801133",
                "outranks": {"clin_sig": "retraction", "direction": "meta-analysis reversed it"},
            }
        ],
    }
    spec = _write_spec(tmp_path / "s", provenance=False)
    (spec / "provenance.json").write_text(json.dumps(doc), encoding="utf-8")
    m = _compile(spec, tmp_path / "o")
    assert m.provenance is not None
    assert m.provenance.item_count == 1


def test_an_outrank_record_stays_out_of_both_identities(tmp_path: Path) -> None:
    """Provenance is metadata about the content, never the content, so neither identity moves.

    Compiled twice from the same rows, once with an outrank record and once without: the authored
    `content_signature` and `artifact.digest` must be equal across the pair. Otherwise recording why
    a row disagrees with an archive would fork the module's identity, and an author would be paying
    for the honesty with a digest.
    """
    bare = _write_spec(tmp_path / "bare", provenance=False)
    marked = _write_spec(tmp_path / "marked", provenance=False)
    (marked / "provenance.json").write_text(
        json.dumps({**_PROVENANCE, "items": [
            {"variant_key": "rs1801133", "outranks": {"clin_sig": "retraction"}}
        ]}),
        encoding="utf-8",
    )

    a = _compile(bare, tmp_path / "oa")
    b = _compile(marked, tmp_path / "ob")
    assert a.content_signature == b.content_signature
    assert a.artifact.digest == b.artifact.digest


def _with_clinvar_licence(spec: Path, dataset: str) -> Path:
    """A `clinvar`/`annotation` licence row — the thing that replaced the `panel:` block's reader.

    Written by hand because none of the sixteen `reference_examples/` carries a `panel:` block at
    all, which the reporter noted and which is why the deprecation had no worked example on either
    side of the seam.
    """
    import csv

    from just_dna_compiler.scaffold import authored_field_names
    from just_dna_format.sources import SourceRow

    fields = authored_field_names(SourceRow)
    row = SourceRow(
        source="clinvar",
        layer="annotation",
        dataset=dataset,
        license="public_domain",
        declared_use="unstated",
    )
    with open(spec / "sources.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow({f: getattr(row, f) if getattr(row, f) is not None else "" for f in fields})
    return spec


def test_the_panel_deprecation_refuses_to_advise_deletion_with_no_replacement(
    tmp_path: Path,
) -> None:
    """A deprecation is legal in a minor only where its audience can act on it (S69).

    The reported case is a module drafted 2026-08-10, before the drafter filled `dataset`, whose
    licence row therefore carries none — and `merge_sources_file` is never-clobber, so re-running the
    pass does not backfill it. There is no path from that module to the state the old sentence
    assumed, and following its advice deletes the module's only record of which snapshot it came
    from. So the warning has to know whether the replacement is present, which is why it moved behind
    the licence rows.
    """
    spec = _write_spec(tmp_path / "s")
    assert not (spec / "sources.csv").exists()

    emitted = [w for w in validate_spec(spec).warnings if "`panel:` block" in w]
    assert len(emitted) == 1
    assert "Do NOT delete the block yet" in emitted[0]
    assert "never-clobber" in emitted[0], "an author needs to know a re-draft will not fix it"

    # An empty cell is an absence, not a value: the same branch, for the reported `cardio` shape.
    _with_clinvar_licence(spec, "")
    still = [w for w in validate_spec(spec).warnings if "`panel:` block" in w]
    assert "Do NOT delete the block yet" in still[0]


def test_the_panel_deprecation_advises_deletion_once_the_replacement_is_there(
    tmp_path: Path,
) -> None:
    """With a filled `dataset` the old advice is correct again, and is what fires."""
    spec = _with_clinvar_licence(_write_spec(tmp_path / "s"), "clinvar_2026-06-27")

    emitted = [w for w in validate_spec(spec).warnings if "`panel:` block" in w]
    assert len(emitted) == 1
    assert "Do NOT delete the block yet" not in emitted[0]
    assert "removed at 1.0" in emitted[0] and "draft-panel" in emitted[0]


def test_neither_branch_claims_nothing_else_is_lost(tmp_path: Path) -> None:
    """The clause that was false in *both* states, which gating alone would not have fixed.

    `GenePanelSpec` carries five fields and `SourceRow.dataset` is one release label. It cannot hold
    `genes` — the denominator, and the only thing separating *not in the panel* from *in the panel,
    nothing found*, which the reporter measured as 425 declared against `gene_count: 298`. It cannot
    hold `significance`, the predicate that makes the row set reproducible. And it is a name rather
    than a digest, so it cannot hold `reference_sha256`; ClinVar reissues, and a release label does
    not pin bytes.
    """
    from just_dna_format.manifest import GenePanelSpec

    unreplaced = {"genes", "significance", "reference_sha256"}
    assert unreplaced < set(GenePanelSpec.model_fields)

    for dataset in ("", "clinvar_2026-06-27"):
        spec = _write_spec(tmp_path / f"s{len(dataset)}")
        if dataset:
            _with_clinvar_licence(spec, dataset)
        emitted = [w for w in validate_spec(spec).warnings if "`panel:` block" in w]
        assert "nothing else is lost" not in emitted[0]
        assert all(field in emitted[0] for field in unreplaced), emitted[0]


#: Proof-of-work bits for the attestation fixtures below. The production constant is 20 (~0.7s per
#: document); a reader refuses anything mined at less, so the constant is patched for the whole test
#: rather than passed to `attest` alone.
_EASY_BITS = 8


@pytest.fixture
def attested(monkeypatch):
    """Write a `verification.json` bound to a spec as it stands, cheap enough to mine in a test."""
    from just_dna_format import verification as verification_module

    monkeypatch.setattr(verification_module, "VERIFICATION_DIFFICULTY_BITS", _EASY_BITS)

    def _write(spec: Path, records) -> Path:
        from just_dna_compiler.compiler import authored_input_entries
        from just_dna_format.verification import attest, module_binding, write_verification

        doc = attest(
            records,
            module_binding(authored_input_entries(spec)),
            producer="test",
            produced_at="2026-08-24T00:00:00Z",
            difficulty=_EASY_BITS,
        )
        write_verification(doc, spec / "verification.json")
        return spec

    return _write


def test_a_check_that_found_something_is_said_where_the_author_is_standing(
    tmp_path: Path, attested
) -> None:
    """Nothing read `VerificationRecord.findings`, so fifty-two contested rows were silent (S70).

    The counts do reach `manifest.verification.checks[]`, so a consumer that goes looking finds them —
    but the author running `validate` saw a green result with warnings about closure and nothing about
    the rows a source disagrees with. Reported as 20 of 141,616 and 32 of 618,629 on two real modules.
    """
    from just_dna_format.manifest import VerificationRecord

    spec = attested(
        _write_spec(tmp_path / "s"),
        [
            VerificationRecord(check="clinical_significance", subjects=141_616, findings=20,
                               source="clinvar", detail="20 opposed: 1:100:A:G (pathogenic vs benign)"),
            VerificationRecord(check="reference_allele", subjects=300, findings=0, source="ensembl"),
        ],
    )
    warnings = [w for w in validate_spec(spec).warnings if "records 20 finding" in w]
    assert len(warnings) == 1, warnings
    assert "clinical_significance (20 of 141616)" in warnings[0]
    # A finding is a question, not a defect — and the reference_allele record found nothing, so it
    # must not appear at all.
    assert "reference_allele" not in warnings[0]
    assert "never fails a build" in warnings[0]


def test_a_clean_attestation_says_nothing_about_findings(tmp_path: Path, attested) -> None:
    """A check that could not fail must not report a zero — the same rule, on the other side."""
    from just_dna_format.manifest import VerificationRecord

    spec = attested(
        _write_spec(tmp_path / "s"),
        [VerificationRecord(check="reference_allele", subjects=300, findings=0, source="ensembl")],
    )
    assert not [w for w in validate_spec(spec).warnings if "finding(s) across" in w]


def test_the_findings_warning_is_published_once_despite_running_on_both_sides(
    tmp_path: Path, attested
) -> None:
    """The message embeds counts and `_verification_block` runs in validate AND compile.

    Normally that is the `@no-rerun-with-counts` trap: a check re-run after resolution reports the
    same finding with two different numbers, message-dedup cannot collapse two different sentences,
    and both reach `manifest.compilation.warnings` — a published field contradicting itself. It is
    safe here for the reason the call site already gives: the input is `verification.json`, which no
    compile step touches, so both passes reach a byte-identical sentence. Pinned rather than argued.
    """
    from just_dna_format.manifest import VerificationRecord

    spec = attested(
        _write_spec(tmp_path / "s"),
        [VerificationRecord(check="clinical_significance", subjects=99, findings=7, source="clinvar")],
    )
    result = compile_module(spec, tmp_path / "o", resolve_with_ensembl=False)
    assert result.success, result.errors

    emitted = [w for w in result.warnings if "finding(s) across" in w]
    assert len(emitted) == 1, emitted
    assert emitted == [w for w in result.manifest.compilation.warnings if "finding(s) across" in w]
