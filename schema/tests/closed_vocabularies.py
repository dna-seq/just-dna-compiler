"""Read the closed vocabularies from whichever format release this interpreter imports."""

import ast
import importlib
import inspect
import json
import pkgutil
import sys
from types import ModuleType

import just_dna_format
from just_dna_format import vocab
from just_dna_format.base import field_vocabularies
from pydantic import BaseModel

# These vocab.py sets classify field names or existing members, rather than accept values.
_NON_VOCABULARIES = {
    "RESERVED_NAMES_0_4",
    "VCF_COLLIDING_KEYS",
    "CARRIED_WARNING_CODES",
    "ACTIONABLE_WARNING_CODES",
}


def _validated_sets(module: ModuleType) -> set[str]:
    """Include direct check_vocab bindings even outside field metadata (e.g. OverlayTarget)."""
    return {
        node.args[1].id
        for node in ast.walk(ast.parse(inspect.getsource(module)))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "check_vocab"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Name)
    }


def closed_vocabularies() -> dict[str, list[str]]:
    """Measure both named sets and closed field bindings, including inline and inherited ones."""
    found: dict[str, list[str]] = {}
    for info in pkgutil.walk_packages(just_dna_format.__path__, "just_dna_format."):
        module = importlib.import_module(info.name)
        validated = _validated_sets(module)
        for name, value in vars(module).copy().items():
            if isinstance(value, frozenset) and (
                name in validated
                or name.startswith("VALID_")
                or (
                    module is vocab
                    and name.isupper()
                    and not name.startswith("RECOMMENDED_")
                    and name not in _NON_VOCABULARIES
                )
            ):
                found[name] = sorted(value)
            if (
                inspect.isclass(value)
                and issubclass(value, BaseModel)
                and value.__module__ == module.__name__
            ):
                for marker in field_vocabularies(value).values():
                    if marker["closed"]:
                        found[marker["name"]] = marker["options"]
    return found


if __name__ == "__main__":
    json.dump(closed_vocabularies(), sys.stdout)
