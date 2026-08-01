"""The tier boundary, asserted rather than trusted: the compiler reaches no network.

VRS arrived in 0.5 and put a *GA4GH* concept into the format and compiler tiers, which is exactly the
kind of change that quietly drags a client library and a service dependency behind it. It did not — the
identification algorithm is `sha512t24u` over canonical JSON, which is arithmetic — but "it did not" is
a claim that decays unless something checks it. This is that something.

The check runs in a **subprocess**, because the test suite has already imported the enricher (and
therefore `ga4gh.vrs`, `httpx`, `duckdb`) into `sys.modules`; asking the question in-process would
always answer "yes, network things are loaded" and prove nothing. A fresh interpreter that imports only
the compiler is the only way to see its true closure.
"""

import subprocess
import sys
import textwrap

# Top-level module names that mean "this tier can talk to something". `urllib`/`http` are stdlib but
# are still the shape of a network surface, so they count.
_NETWORK_MODULES = (
    "ga4gh", "requests", "httpx", "urllib3", "urllib.request", "http.client",
    "duckdb", "huggingface_hub", "seqrepo", "socket",
)


def _in_fresh_interpreter(body: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(body)],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"subprocess failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


def test_importing_the_compiler_pulls_in_no_network_client() -> None:
    """Importing the whole compile path must not load a network client.

    `socket` is the interesting one: it is stdlib and something innocuous could pull it in, but if the
    compiler has no reason to open one then it has no reason to import one either, and holding that
    line is what keeps the boundary crisp.
    """
    loaded = _in_fresh_interpreter(f"""
        import sys
        import just_dna_compiler.compiler          # the whole compile path
        import just_dna_format.vrs                 # the VRS half specifically
        watch = {_NETWORK_MODULES!r}
        hits = sorted(m for m in sys.modules if any(
            m == w or m.startswith(w + ".") for w in watch))
        print(",".join(hits))
    """)
    assert loaded == "", f"the compiler tier imported network-capable module(s): {loaded}"


def test_the_format_tiers_vrs_module_is_stdlib_only() -> None:
    """`derive_vrs_allele_id` must be computable from the standard library alone.

    This is what lets a verify-only consumer recompute an allele identity offline, and what keeps
    `just-dna-format` at pydantic + cryptography (Goal 2).
    """
    third_party = _in_fresh_interpreter("""
        import sys, pathlib, sysconfig
        before = set(sys.modules)
        import just_dna_format.vrs as v
        stdlib = pathlib.Path(sysconfig.get_paths()["stdlib"]).resolve()
        outside = []
        for name in set(sys.modules) - before:
            mod = sys.modules.get(name)
            path = getattr(mod, "__file__", None)
            if path is None or name.startswith("just_dna_format"):
                continue
            try:
                pathlib.Path(path).resolve().relative_to(stdlib)
            except ValueError:
                outside.append(name)
        print(",".join(sorted(outside)))
    """)
    assert third_party == "", f"just_dna_format.vrs pulled non-stdlib module(s): {third_party}"


def test_a_va_is_minted_and_verified_with_sockets_disabled() -> None:
    """End to end with the network physically unavailable — mint, key, and reject a tampered id.

    Booby-trapping `socket.socket` rather than merely checking imports: it proves the behaviour is
    genuinely offline, not just that the obvious libraries happen to be absent.
    """
    output = _in_fresh_interpreter("""
        import socket
        class Blocked(socket.socket):
            def __init__(self, *a, **k):
                raise AssertionError("the compiler opened a network socket")
        socket.socket = Blocked

        import pathlib, tempfile
        import polars as pl
        from just_dna_compiler.compiler import compile_module
        from just_dna_format.vrs import derive_vrs_allele_id

        sickle = derive_vrs_allele_id("11", 5227002, "T", "A")
        other = derive_vrs_allele_id("1", 11796321, "G", "A")

        d = pathlib.Path(tempfile.mkdtemp())
        spec = d / "spec"; spec.mkdir()
        (spec / "module_spec.yaml").write_text(
            "schema_version: '1.0'\\nmodule:\\n  name: purity\\n  title: T\\n"
            "  description: D\\n  report_title: R\\n"
            "defaults:\\n  curator: c\\n  method: m\\ngenome_build: GRCh38\\n")
        (spec / "variants.csv").write_text(
            "chrom,start,ref,alts,genotype,state,conclusion\\n"
            "11,5227002,T,A,A/T,risk,carrier\\n")
        (spec / "studies.csv").write_text("chrom,start,ref,pmid\\n11,5227002,T,12345678\\n")

        def resolution(vrs_id):
            (spec / "resolution.csv").write_text(
                "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,"
                "vrs_id,vrs_spec,source,status\\n"
                f"{sickle},rs334,11,5227002,T,A,GRCh38,0,{vrs_id},2.0,gnomad,resolved\\n")

        resolution(sickle)
        good = compile_module(spec, d / "out1")
        key = pl.read_parquet(d / "out1" / "weights.parquet")["variant_key"][0]

        resolution(other)   # right shape, wrong allele
        bad = compile_module(spec, d / "out2")

        print(f"{good.success}|{key == sickle}|{bad.success}")
    """)
    compiled, keyed_on_va, tampered_compiled = output.split("|")
    assert compiled == "True", "a correct vrs_id should compile offline"
    assert keyed_on_va == "True", "variant_key should be the VA in weights.parquet"
    assert tampered_compiled == "False", "a tampered substitution vrs_id must be rejected"
