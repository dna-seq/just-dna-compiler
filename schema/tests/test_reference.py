"""RM8/RM9 — the drift-proof authoring reference and the recommended display palette."""

import json

from just_dna_format.base import authored_field_names
from just_dna_format.binning import VALID_MEASURE_KINDS
from just_dna_format.frequency import FrequencyRow
from just_dna_format.manifest import COLOR_PATTERN, RECOMMENDED_COLORS, RECOMMENDED_ICONS
from just_dna_format.reference import authoring_reference, json_schemas
from just_dna_format.spec import VariantRow


def test_authoring_reference_is_json_serializable_with_expected_shape() -> None:
    ref = authoring_reference()
    json.dumps(ref)  # a single source of truth must serialise for MCP/agents/docs
    assert set(ref) >= {
        "schema_version", "genome_build_default", "models", "vocabularies",
        "reserved_names", "recommended_palette",
    }
    assert ref["genome_build_default"] == "GRCh38"


def test_authoring_reference_is_generated_not_hardcoded() -> None:
    # Drift-proofing: fields/vocab come from the live models, so they include the 0.3/0.4 additions.
    ref = authoring_reference()
    variant_fields = {f["name"] for f in ref["models"]["VariantRow"]}
    assert {"direction", "clin_sig", "effect_allele", "trait_efo_id"} <= variant_fields
    cn_fields = {f["name"] for f in ref["models"]["CopyNumberRow"]}
    assert {"modifier_gene", "modifier_cn", "source_field", "unresolved"} <= cn_fields
    assert {"tissue", "reference_sequence"} <= {f["name"] for f in ref["models"]["HeteroplasmyRow"]}
    assert {"match_rate_floor", "training_cohort"} <= {f["name"] for f in ref["models"]["PgsRow"]}
    # the vocab is the live frozenset, not a copy that could drift
    assert ref["vocabularies"]["measure_kind"] == sorted(VALID_MEASURE_KINDS)
    assert "reference_db" in ref["reserved_names"]
    # `actionability` is reported under `vocabularies`, not `open_recommended`: `VariantRow` rejects
    # a non-member, so it is closed however `ACTIONABILITY_SEED` is named. This assertion used to
    # pin the opposite and was pinning the drift.
    assert "descriptive" in ref["vocabularies"]["actionability"]
    # adoption pass: PharmVariantRow + evidence_level + the VariantRow axes appear (generated)
    assert "PharmVariantRow" in ref["models"]
    assert ref["vocabularies"]["evidence_level"] == ["1A", "1B", "2A", "2B", "3", "4"]
    assert {"requires_callable", "acmg_sf", "actionability", "callable_from"} <= {
        f["name"] for f in ref["models"]["VariantRow"]
    }
    # retired names are no longer reserved (they became VariantRow columns — `callable_from` in 0.5)
    assert not (
        {"requires_callable", "acmg_sf", "actionability", "callable_from"}
        & set(ref["reserved_names"])
    )
    # RM14 authorship: the Contribution model + role vocab + open kind seed all surface (generated)
    assert {"who", "role", "kind", "at"} == {f["name"] for f in ref["models"]["Contribution"]}
    assert ref["vocabularies"]["author_role"] == ["audited", "created", "edited", "reviewed"]
    assert {"human", "human_expert", "human_certified", "ai", "swarm"} <= set(
        ref["open_recommended"]["author_kind"]
    )


def test_authoring_reference_omits_every_compiler_managed_field() -> None:
    # This reference is what an agent authors a module from, so a stamped column listed here reads as
    # one the author writes. The exclusion used to be a hand-kept name set naming only `variant_key`,
    # and it drifted the moment 0.5 added `authored_ident` — a `list[str]` an author cannot even
    # spell in a CSV cell. It now reads the fields' own marker, so this asserts against the marker
    # rather than against a second copy of the same list.
    ref = authoring_reference()
    listed = {f["name"] for f in ref["models"]["VariantRow"]}
    assert listed == set(authored_field_names(VariantRow))
    assert {"variant_key", "authored_ident"}.isdisjoint(listed)
    # …while the machine-facing schema stays complete: it describes the materialized shape, which
    # genuinely has these columns.
    assert {"variant_key", "authored_ident"} <= set(json_schemas()["VariantRow"]["properties"])


def test_a_genuinely_authored_field_is_not_hidden_by_a_shared_name() -> None:
    # `FrequencyRow.variant_key` is required and authored — the same *name* as `VariantRow`'s stamped
    # column, and a name-based exclusion would have hidden it from an author who must supply it.
    # Marking the field rather than the name is what keeps the two apart.
    assert "variant_key" in authored_field_names(FrequencyRow)
    assert FrequencyRow.model_fields["variant_key"].is_required()


def test_authoring_reference_surfaces_version_and_registry_stamped_boundary() -> None:
    ref = authoring_reference()
    # `version` is a genuine authored field (0.4.1) — it shows up on ModuleInfo, generated.
    module_fields = {f["name"] for f in ref["models"]["ModuleInfo"]}
    assert "version" in module_fields
    # The registry-stamped keys are the S2 field-ownership boundary — distinct from reserved_names,
    # and `version` is deliberately NOT among them.
    stamped = ref["registry_stamped_keys"]
    assert set(stamped) == {"namespace", "owner", "canonical_id"}
    assert "version" not in stamped
    assert not (set(stamped) & set(ref["reserved_names"]))
    assert all(stamped.values())  # every key carries a reason


def test_authoring_reference_field_records_carry_type_required_description() -> None:
    genotype = next(
        f for f in authoring_reference()["models"]["VariantRow"] if f["name"] == "genotype"
    )
    assert genotype["required"] is True
    assert genotype["type"] == "str"
    assert genotype["description"]  # non-empty


def test_recommended_palette_is_valid() -> None:
    assert RECOMMENDED_COLORS and RECOMMENDED_ICONS
    for use, hex_code in RECOMMENDED_COLORS.items():
        assert COLOR_PATTERN.match(hex_code), f"{use} → {hex_code} not a 6-hex colour"
    for use, glyph in RECOMMENDED_ICONS.items():
        assert glyph and isinstance(glyph, str), f"{use} → {glyph!r} is not a non-empty icon name"
    # the palette is surfaced through the reference too
    assert authoring_reference()["recommended_palette"]["colors"] == RECOMMENDED_COLORS


def test_json_schemas_returns_a_schema_per_model() -> None:
    schemas = json_schemas()
    assert "VariantRow" in schemas and "properties" in schemas["VariantRow"]
    assert "CopyNumberRow" in schemas and "PgsRow" in schemas
    json.dumps(schemas)  # serialisable


# ── The vocabulary binding (0.5) ────────────────────────────────────────────────────────────────
# `authoring_reference()["vocabularies"]` was a hand-kept dict, and it drifted twice: it never
# learned about `recommendation_strength` or `phenotype_category` (added in 0.5), and it filed
# `actionability` under `open_recommended` although `VariantRow` rejects a non-member. The tests
# below discover the binding from the models themselves, so neither kind of drift can recur.

_JUNK = "zzz_not_a_vocabulary_member"


def _rejects_as_vocabulary(model, field: str) -> bool:
    """Does `model` reject `_JUNK` for `field` *because it is outside a vocabulary*?

    Validates a dict carrying only that field: other fields fail as missing, and we read the error
    for this one. That avoids a hand-kept table of plausible seed values per model — which is the
    hand-kept list these tests exist to abolish, relocated."""
    try:
        model.model_validate({field: _JUNK})
    except Exception as exc:  # pydantic ValidationError
        errors = getattr(exc, "errors", list)()
        return any(
            e.get("loc") == (field,) and "must be one of" in str(e.get("msg", ""))
            for e in errors
        )
    return False


def test_every_enforced_vocabulary_field_declares_its_options() -> None:
    """Enforcement implies a marker. Discovered by behaviour, so a new closed field is covered
    without editing this test — which a name list could never do."""
    from just_dna_format.base import authored_field_names, field_vocabularies
    from just_dna_format.reference import _ALL_MODELS

    missing = [
        f"{name}.{field}"
        for name, model in _ALL_MODELS.items()
        for field in authored_field_names(model)
        if _rejects_as_vocabulary(model, field) and field not in field_vocabularies(model)
    ]
    assert missing == []


def test_declared_closed_options_are_exactly_what_is_accepted() -> None:
    """And the converse: a `closed` marker implies enforcement, so a marker cannot advertise a
    vocabulary nothing rejects (the `actionability` drift, pointing the other way)."""
    from just_dna_format.base import field_vocabularies
    from just_dna_format.reference import _ALL_MODELS

    unenforced = [
        f"{name}.{field}"
        for name, model in _ALL_MODELS.items()
        for field, marker in field_vocabularies(model).items()
        if marker["closed"] and not _rejects_as_vocabulary(model, field)
    ]
    assert unenforced == []


def test_authoring_reference_vocabularies_come_from_the_markers() -> None:
    from just_dna_format.base import field_vocabularies
    from just_dna_format.reference import _ALL_MODELS

    ref = authoring_reference()
    expected = {
        marker["name"]: marker["options"]
        for model in _ALL_MODELS.values()
        for marker in field_vocabularies(model).values()
        if marker["closed"]
    }
    assert ref["vocabularies"] == expected


def test_the_two_vocabularies_0_5_added_are_reachable() -> None:
    """The concrete drift: both were enforced and neither was listed."""
    from just_dna_format.pgx import VALID_FUNCTION_STATUS  # noqa: F401 — sanity that pgx imports
    from just_dna_format.vocab import (
        VALID_PHENOTYPE_CATEGORIES,
        VALID_RECOMMENDATION_STRENGTH,
    )

    ref = authoring_reference()
    assert ref["vocabularies"]["recommendation_strength"] == sorted(VALID_RECOMMENDATION_STRENGTH)
    assert ref["vocabularies"]["phenotype_category"] == sorted(VALID_PHENOTYPE_CATEGORIES)


def test_actionability_is_reported_closed_because_it_is_enforced() -> None:
    """It was advertised as an open seed while `VariantRow` rejected non-members, so a tool that
    offered a novel value got a rejection it was told to expect to work."""
    from just_dna_format.vocab import ACTIONABILITY_SEED

    ref = authoring_reference()
    assert ref["vocabularies"]["actionability"] == sorted(ACTIONABILITY_SEED)
    assert "actionability_seed" not in ref["open_recommended"]


def test_the_one_hand_authored_sidecar_is_described() -> None:
    """S21. `sources.csv` is the only fact sidecar a human writes — the schema's own
    `MISPLACED_COLUMN_REASONS['source']` tells them to — and it is the only table the compile licence
    gate reads, so an author left to guess its columns is guessing at a licence declaration.

    The three permissions are asserted as **tri-state**, because that is the part nobody reconstructs
    from a filename: `None` is UNKNOWN, never false, so a source whose terms could not be established
    has not been shown to permit anything."""
    from just_dna_format.sources import SourceRow

    ref = authoring_reference()
    described = {field["name"]: field for field in ref["models"]["SourceRow"]}

    assert described.keys() == set(SourceRow.model_fields)   # no column left to guess at
    assert [described[axis]["type"] for axis in ("share_alike", "commercial_use", "redistribution")] \
        == ["bool | None"] * 3
    assert described["layer"]["closed"] is True              # and the gate's own column is pickable
    assert described["source"]["category"] == "required"


def test_the_sidecars_vocabularies_ride_on_its_fields() -> None:
    """The root of S21 was one level below the report: both fields ran a closed-vocabulary validator
    while carrying no marker, so no generated surface could see them. They were invisible to
    `test_every_enforced_vocabulary_field_declares_its_options` only because the model itself sat
    outside `_ALL_MODELS`; that guard covers them now, by behaviour, without naming them."""
    from just_dna_format.vocab import VALID_DECLARED_USE, VALID_SOURCE_LAYERS

    ref = authoring_reference()
    assert ref["vocabularies"]["source_layer"] == sorted(VALID_SOURCE_LAYERS)
    assert ref["vocabularies"]["declared_use"] == sorted(VALID_DECLARED_USE)


def test_required_any_of_agrees_with_each_models_own_validator() -> None:
    """The declaration is proven against the validator it mirrors, not trusted.

    For each declared group: a row carrying only that group's identity columns must construct, and
    a row carrying none of them must fail. Cases are derived from the declaration and checked
    against the real validator, so adding a branch to one without the other fails here."""
    from just_dna_format.reference import _ALL_MODELS

    # Non-identity columns each model needs before its identity rule is even reached.
    filler = {
        "VariantRow": {"genotype": "A/G", "state": "risk", "conclusion": "c"},
        "StudyRow": {"pmid": "12345678"},
        "HaplotypeRow": {"haplotype_name": "*4", "allele": "A"},
        "PharmVariantRow": {"drug": "warfarin", "conclusion": "c"},
    }
    identity_values = {"rsid": "rs1801133", "chrom": "1", "start": 100}
    checked = 0
    for name, model in _ALL_MODELS.items():
        groups = getattr(model, "REQUIRED_ANY_OF", ())
        if not groups:
            continue
        base = filler[name]
        for group in groups:
            model.model_validate({**base, **{c: identity_values[c] for c in group}})
            checked += 1
        try:
            model.model_validate(dict(base))
        except Exception:
            pass
        else:
            raise AssertionError(f"{name} accepted a row satisfying none of REQUIRED_ANY_OF")
    assert checked == sum(len(m.REQUIRED_ANY_OF) for m in _ALL_MODELS.values()
                          if getattr(m, "REQUIRED_ANY_OF", ()))
    assert checked > 0
