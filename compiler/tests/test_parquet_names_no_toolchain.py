"""RM341: a compiled parquet must not carry the polars version that wrote it.

From polars 2.0 the parquet footer's `created_by` names the polars version and build hash
(pola-rs/polars#29106). Every byte of the footer is inside `artifact.digest`, so under 2.x one
`compiler_version` mints a different digest for the same spec on each polars release, a patch
included. Principle 4 pins reproducibility to `compiler_version`, so `polars<2` is capped until
RM342 records the toolchain in the manifest. This test is what turns red if the cap is lifted
without it: it reads the footer of every parquet a real compile writes, and fails when the
installed polars version appears there.
"""

import struct
from pathlib import Path

import polars as pl
from just_dna_compiler.compiler import compile_module

REPO = Path(__file__).resolve().parents[2]
EXAMPLE = REPO / "reference_examples" / "apoe_epsilon"


def _footer(parquet: Path) -> bytes:
    """The thrift-encoded FileMetaData: the bytes between the footer length and the closing magic."""
    data = parquet.read_bytes()
    assert data[-4:] == b"PAR1", f"{parquet.name} does not end in the parquet magic"
    (length,) = struct.unpack("<I", data[-8:-4])
    return data[-8 - length : -8]


def test_no_compiled_parquet_names_the_polars_version_that_wrote_it(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = compile_module(EXAMPLE, out, resolve_with_ensembl=False)
    assert result.success, result.errors
    parquets = sorted(out.glob("*.parquet"))
    assert parquets, "the compile wrote no parquet"
    version = pl.__version__.encode()
    carrying = [p.name for p in parquets if version in _footer(p)]
    assert not carrying, (
        f"polars {pl.__version__} writes its version into the parquet footer of {carrying}, so "
        "artifact.digest now depends on the polars release; lift the polars<2 cap only with RM342"
    )
