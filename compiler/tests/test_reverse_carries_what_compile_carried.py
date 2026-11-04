"""`reverse_module` gives back everything `compile_module` carried, or says why not (RM364).

RM241 put every `module_spec.yaml` field on one side of a registry. This is the same move one level
out: every field of the **manifest** a compile writes is either reconstructed by `compile → reverse →
compile` (and compared, lap against lap) or excluded with a reason. Before it, `provenance.json` and the
shipped logs were copied into the artifact, hashed into the manifest, and left behind by reverse, while
the README and logo beside them came back; nothing listed the four together, so the round-trip gate
compared the two it had been told about.

The walk is over `ModuleManifest` and `Compilation`, so a manifest field added later fails
`test_every_manifest_field_is_reconstructed_or_excluded` until somebody decides which side it is on.
The behavioural half reads the decision back: the projection of every reconstructed field is the same
on the first, second and third lap, on a fixture that carries every shipped file kind (the corpus
carries no `provenance.json` and no logs, so a sweep over it alone would pass by never exercising them).
"""

import json
import shutil
import typing
from pathlib import Path

from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_compiler.compiler.reverse import (
    REVERSE_MANIFEST_EXCLUDED,
    REVERSE_MANIFEST_RECONSTRUCTED,
    reconstructed_projection,
    shipped_files,
)
from just_dna_format.integrity import sha256_file
from just_dna_format.layout import resolve_sidecar
from just_dna_format.manifest import (
    Compilation,
    FileEntry,
    ModuleManifest,
    Provenance,
    ProvenanceDoc,
    ProvenanceItem,
)

_EXAMPLE = Path(__file__).resolve().parents[2] / "reference_examples" / "hfe_hemochromatosis"


def _walked_manifest_fields() -> set[str]:
    """Every manifest field, with the `compilation` block walked one level down as dotted paths."""
    return set(ModuleManifest.model_fields) | {f"compilation.{name}" for name in Compilation.model_fields}


def test_every_manifest_field_is_reconstructed_or_excluded() -> None:
    walked = _walked_manifest_fields()
    assert walked == REVERSE_MANIFEST_RECONSTRUCTED | set(REVERSE_MANIFEST_EXCLUDED)
    assert not REVERSE_MANIFEST_RECONSTRUCTED & set(REVERSE_MANIFEST_EXCLUDED)
    assert all(len(reason.split()) >= 5 for reason in REVERSE_MANIFEST_EXCLUDED.values())


def _with_shipped_files(tmp_path: Path) -> Path:
    """A copy of a real example carrying every file kind a compile ships beside the parquets."""
    spec_dir = tmp_path / "spec"
    shutil.copytree(_EXAMPLE, spec_dir)
    variant_key = next(
        line.split(",", 1)[0]
        for line in (spec_dir / "variants.csv").read_text(encoding="utf-8").splitlines()[1:]
        if line.split(",", 1)[0]
    )
    doc = ProvenanceDoc(
        generator="a-named-pipeline",
        model="a-model-id",
        agent_version="1.2.3",
        items=[ProvenanceItem(variant_key=variant_key, rationale="why this row", human_reviewed=True)],
    )
    (spec_dir / "provenance.json").write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    # The PNG signature and nothing else: the compile checks a logo's extension, never its pixels.
    (spec_dir / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (spec_dir / "session.log").write_text("top-level aggregate log\n", encoding="utf-8")
    (spec_dir / "logs").mkdir()
    (spec_dir / "logs" / "researcher.log").write_text("a role's log\n", encoding="utf-8")
    (spec_dir / "logs" / "notes.md").write_text("# Notes\n\nA markdown note.\n", encoding="utf-8")
    (spec_dir / "logs" / "ledger.jsonl").write_text(json.dumps({"step": 1}) + "\n", encoding="utf-8")
    return spec_dir


def _laps(spec_dir: Path, tmp_path: Path):
    first = compile_module(spec_dir, tmp_path / "a1")
    assert first.success, first.errors
    reverse_module(tmp_path / "a1", tmp_path / "rev1")
    second = compile_module(tmp_path / "rev1", tmp_path / "a2")
    assert second.success, second.errors
    reverse_module(tmp_path / "a2", tmp_path / "rev2")
    third = compile_module(tmp_path / "rev2", tmp_path / "a3")
    assert third.success, third.errors
    return first, second, third


def test_every_reconstructed_field_survives_two_laps(tmp_path: Path) -> None:
    spec_dir = _with_shipped_files(tmp_path)
    first, second, third = _laps(spec_dir, tmp_path)
    # The fixture really does ship every kind, or the comparison below proves nothing about it.
    assert first.manifest.provenance is not None and first.manifest.provenance.item_count == 1
    assert {entry.name for entry in first.manifest.logs} == {
        "session.log",
        "logs/researcher.log",
        "logs/notes.md",
        "logs/ledger.jsonl",
    }
    assert first.manifest.readme is not None and first.manifest.logo is not None

    projection = reconstructed_projection(first.manifest)
    assert reconstructed_projection(second.manifest) == projection
    assert reconstructed_projection(third.manifest) == projection


#: The manifest fields naming a file that is NOT beside the parquets: both describe files beside the
#: *spec*, which a compile hashes where they are authored and does not copy into the module directory.
_NOT_SHIPPED = {"inputs", "derived"}


def _names_a_file(annotation: object) -> bool:
    """Whether a field's annotation is, or contains, a `FileEntry` or the `Provenance` file pointer."""
    if annotation in (FileEntry, Provenance):
        return True
    return any(_names_a_file(arg) for arg in typing.get_args(annotation))


def test_every_file_the_manifest_names_beside_the_parquets_is_shipped_back(tmp_path: Path) -> None:
    """`shipped_files` reads exactly the manifest fields that name a file a compile copies into the artifact.

    Derived from the model's annotations, so a fifth file-bearing field fails here until reverse copies
    it back or the field joins `_NOT_SHIPPED` with its reason. Asserted on a real compile of a fixture
    that carries every kind, so the set is what the function returns rather than what it says it reads.
    """
    file_fields = {
        name for name, info in ModuleManifest.model_fields.items() if _names_a_file(info.annotation)
    }
    compiled = compile_module(_with_shipped_files(tmp_path), tmp_path / "a1")
    assert compiled.success, compiled.errors
    assert {shipped.what for shipped in shipped_files(compiled.manifest)} == file_fields - _NOT_SHIPPED


def test_shipped_files_come_back_byte_for_byte(tmp_path: Path) -> None:
    spec_dir = _with_shipped_files(tmp_path)
    compiled = compile_module(spec_dir, tmp_path / "a1")
    assert compiled.success, compiled.errors
    reverse_module(tmp_path / "a1", tmp_path / "rev")

    manifest = compiled.manifest
    assert manifest.provenance is not None and manifest.provenance.file is not None
    shipped = [(entry.name, entry.sha256) for entry in manifest.logs]
    shipped.append((manifest.provenance.file, manifest.provenance.sha256))
    for name, sha256 in shipped:
        copied = tmp_path / "rev" / name
        assert copied.read_bytes() == (spec_dir / name).read_bytes(), name
        assert sha256_file(copied) == sha256, name


def test_a_shipped_file_that_disagrees_with_its_record_is_not_copied(tmp_path: Path) -> None:
    spec_dir = _with_shipped_files(tmp_path)
    compiled = compile_module(spec_dir, tmp_path / "a1")
    assert compiled.success, compiled.errors
    for name in ("provenance.json", "logs/researcher.log"):
        path = tmp_path / "a1" / name
        path.write_bytes(path.read_bytes() + b"\n")

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    assert not (tmp_path / "rev" / "provenance.json").exists()
    assert not (tmp_path / "rev" / "logs" / "researcher.log").exists()
    # The untouched ones still come back: one bad record does not cost the others.
    assert (tmp_path / "rev" / "logs" / "notes.md").is_file()
    assert (tmp_path / "rev" / "session.log").is_file()


def test_a_shipped_name_that_leaves_the_module_is_not_followed(tmp_path: Path) -> None:
    """A manifest is read, not trusted: a log named `../x.log` would write outside the reversed spec."""
    spec_dir = _with_shipped_files(tmp_path)
    compiled = compile_module(spec_dir, tmp_path / "a1")
    assert compiled.success, compiled.errors
    outside = tmp_path / "outside.log"
    outside.write_text("not part of the module\n", encoding="utf-8")
    manifest_path = tmp_path / "a1" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["logs"].append(
        {"name": "../outside.log", "sha256": sha256_file(outside), "size": outside.stat().st_size}
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    reverse_module(tmp_path / "a1", tmp_path / "rev" / "spec")
    assert not (tmp_path / "rev" / "outside.log").exists()
    assert (tmp_path / "rev" / "spec" / "session.log").is_file()


_YAML = "schema_version: '1.0'\nmodule:\n  name: demo\n  title: D\n  description: d\n  report_title: D\n"
_RES = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
    "rs777,rs777,7,700,C,G,GRCh38,0,manual,resolved\n"
)


def _contradicted_pharm_spec(tmp_path: Path) -> Path:
    """A PGx module whose one row authors a `start` the injected table places elsewhere (NUDT15's shape)."""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (spec / "pharm_variants.csv").write_text(
        "rsid,chrom,start,ref,gene,genotype,drug,conclusion\nrs777,,999,,SLCO1B1,C/G,simvastatin,c\n",
        encoding="utf-8",
    )
    (spec / "resolution.csv").write_text(_RES, encoding="utf-8")
    return spec


def test_a_row_the_fill_left_alone_gives_back_the_tables_answer(tmp_path: Path) -> None:
    """Reverse used to write the row's AUTHORED `start` back as a resolution fact.

    So the reversed table agreed with the row, the second lap's contradiction warning went silent, and
    `resolution_signature` moved. The parquet now carries the table's own loci for the row's key.
    """
    spec = _contradicted_pharm_spec(tmp_path)
    first, second, _third = _laps(spec, tmp_path)
    reversed_rows = (tmp_path / "rev1" / "resolution.csv").read_text(encoding="utf-8").splitlines()
    assert len(reversed_rows) == 2 and ",7,700,C,G," in reversed_rows[1], reversed_rows

    def contradicted(result) -> list[str]:
        return [w for w in result.warnings if "authored start=999 contradicts" in w]

    assert contradicted(first) and contradicted(second) == contradicted(first)
    assert reconstructed_projection(second.manifest) == reconstructed_projection(first.manifest)


def test_a_module_that_read_no_table_gets_none_back(tmp_path: Path) -> None:
    """`grch37_build` carries no `resolution.csv`, so its reversed spec carries none either.

    Reverse used to rebuild one from the authored coordinates, which the second lap then read: its
    manifest published a `resolution_signature` and VRS coverage the first lap's did not.
    """
    example = _EXAMPLE.parent / "grch37_build"
    assert resolve_sidecar(example, "resolution.csv") is None
    first, second, _third = _laps(example, tmp_path)
    assert resolve_sidecar(tmp_path / "rev1", "resolution.csv") is None
    assert first.manifest.compilation.resolution_signature is None
    assert reconstructed_projection(second.manifest) == reconstructed_projection(first.manifest)


def test_a_shipped_file_reached_through_a_symlink_is_not_copied(tmp_path: Path) -> None:
    """A downloaded artifact may ship a log that is a link to a file elsewhere, with that file's hash.

    `_inside` reads the name and cannot see a link, so reverse would follow it and copy the target into
    the reversed spec. A compile never ships a link (`_reached_through_a_link`), so reverse never follows one.
    """
    spec_dir = _with_shipped_files(tmp_path)
    compiled = compile_module(spec_dir, tmp_path / "a1")
    assert compiled.success, compiled.errors
    secret = tmp_path / "secret.log"
    secret.write_text("outside the module\n", encoding="utf-8")
    shipped = tmp_path / "a1" / "logs" / "researcher.log"
    shipped.unlink()
    shipped.symlink_to(secret)
    manifest_path = tmp_path / "a1" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["logs"]:
        if entry["name"] == "logs/researcher.log":
            entry["sha256"] = sha256_file(secret)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    reverse_module(tmp_path / "a1", tmp_path / "rev")
    assert not (tmp_path / "rev" / "logs" / "researcher.log").exists()
    assert (tmp_path / "rev" / "logs" / "notes.md").is_file()


def test_a_table_the_spec_carried_comes_back_even_with_no_rows(tmp_path: Path) -> None:
    """A header-only `resolution.csv` leaves no signature, and is still in `manifest.derived`."""
    spec = _contradicted_pharm_spec(tmp_path)
    (spec / "resolution.csv").write_text(_RES.splitlines()[0] + "\n", encoding="utf-8")
    first, _second, _third = _laps(spec, tmp_path)
    assert first.manifest.compilation.resolution_signature is None
    assert resolve_sidecar(tmp_path / "rev1", "resolution.csv") is not None


def test_a_table_no_resolve_left_unread_still_comes_back(tmp_path: Path) -> None:
    """`--no-resolve` reads no table, so no row carries its loci; the spec carried one all the same."""
    spec = _contradicted_pharm_spec(tmp_path)
    compiled = compile_module(spec, tmp_path / "a1", resolve_with_ensembl=False)
    assert compiled.success, compiled.errors
    assert compiled.manifest.compilation.resolution_signature is None
    reverse_module(tmp_path / "a1", tmp_path / "rev")
    assert resolve_sidecar(tmp_path / "rev", "resolution.csv") is not None
