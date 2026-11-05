"""The enricher's wheel carries the generated Atlas tree once, and its sdist carries the build input (RM397).

0.8.0's wheel shipped the fetched `.proto` sources twice: once as `_atlas_protos/` (the build input)
and once inside `generated/`, beside the bindings. The wheel needs only `generated/`; the sdist needs
the fetched sources, so that a build from it needs no network. This builds both through the real
backend and reads what is in them.

Marked `network`: on a fresh checkout the build hook fetches the pinned sources and the isolated
build environment resolves hatchling and grpcio-tools. `scripts/build-dists.sh`, run at every cut,
is the always-on half: it refuses a wheel holding two members with the same bytes.
"""

import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest
from just_dna_enricher import atlas_protos

ENRICHER_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "just_dna_enricher"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[list[str], list[str]]:
    out = tmp_path_factory.mktemp("dist")
    subprocess.run(["uv", "build", "--out-dir", str(out), str(ENRICHER_ROOT)], check=True)
    wheel = next(out.glob("*.whl"))
    sdist = next(out.glob("*.tar.gz"))
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
    with tarfile.open(sdist) as archive:
        sdist_names = archive.getnames()
    return wheel_names, sdist_names


SOURCE_FILES = (*atlas_protos.PROTOS, atlas_protos.SERVICE_CONFIG_NAME, atlas_protos.LICENSE_NAME)


@pytest.mark.network
def test_the_wheel_carries_no_fetched_source_tree(built):
    wheel_names, _ = built
    fetched = [name for name in wheel_names if name.startswith(f"{PACKAGE}/{atlas_protos.PROTO_DIRNAME}/")]
    assert fetched == []


@pytest.mark.network
def test_the_wheel_carries_what_the_runtime_reads(built):
    wheel_names, _ = built
    generated = f"{PACKAGE}/{atlas_protos.OUT_DIR.name}/"
    expected = {
        f"{generated}{atlas_protos.SERVICE_CONFIG_NAME}",
        f"{generated}{atlas_protos.LICENSE_NAME}",
        *(
            f"{generated}{atlas_protos.STAGE_PREFIX}/{Path(proto).stem}_pb2.py"
            for proto in atlas_protos.PROTOS
        ),
    }
    assert expected - set(wheel_names) == set()


@pytest.mark.network
def test_the_sdist_carries_the_fetched_sources(built):
    _, sdist_names = built
    in_sdist = {
        Path(name).name for name in sdist_names if f"/src/{PACKAGE}/{atlas_protos.PROTO_DIRNAME}/" in name
    }
    assert set(SOURCE_FILES) - in_sdist == set()
