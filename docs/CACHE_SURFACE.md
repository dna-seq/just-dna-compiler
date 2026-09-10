# The cache surface — what a lane is, and how to add one without shipping a hole

**Read this before adding a lane, and again before calling one done.** It exists because a lane was
marked shipped with a `publish_repo` no command could reach (RM202): every field was set correctly,
every test passed, and nothing an operator could type would publish it. The checklist at the end is
the thing that would have caught it.

`CACHE_LANES` in `caches.py` is the registry — **15 lanes** — and it is the single source for
`cache status`, `cache pull`, `cache prepare`, `cache rebuild` and the publisher. It replaced a
hand-kept list that had drifted three lanes behind reality (RM176), so the standing rule is
`@registry-completeness`: **assert an equality over a walked set, never a count and never a list
beside the thing it lists.**

## The three stages, and why a lane may lack one

A lane has an **acquire** stage, a **build** stage and a **publish** stage. Any of them may be
absent, and **an absent stage must state its reason in a field** — never in a comment, because
`cache status` interpolates the reason at the moment an operator asks.

| stage | present when | absent reason lives in |
| --- | --- | --- |
| acquire (pull) | `ensure` is set | `unpublished` |
| build (unattended) | `rebuild` is set | `unbuilt` |
| publish | `publish_repo` is set | `unpublished` |

`test_an_absent_stage_states_its_reason_and_a_present_one_does_not` asserts both biconditionals in
**both** directions. The second direction is the one people forget: a lane that gains a publish
command and keeps its excuse goes on telling operators to build their own, which is worse than never
having said it.

## Every field, and what breaks if it is wrong

| field | required | what it is, and the failure it prevents |
| --- | --- | --- |
| `name` | ✅ | the lane's identity. Must match `<name>_build.py`, `resolve_<name>_reference`, `default_<name>_cache_dir` and `<NAME>_SUBDIR` — all four walked |
| `subdir` | ✅ | `<base>/<subdir>`. Distinct across lanes, or two lanes overwrite each other in one base |
| `serves` | ✅ | what an operator gets. Rendered by `cache status` |
| `build_command` | ✅ | the command as typed. **Not derivable from `name`** — there is no `drug_labels build` and no `constraint build`, and `cache status` once printed both |
| `resolve` | ✅ | identity-checked against `locations.resolve_<name>_reference`. Two lanes sharing one resolver would report a snapshot present under both names |
| `default_dir` | ✅ | where `prepare` **writes**. `resolve` cannot answer this — it returns `None` for an absent cache, which is exactly the case provisioning is for |
| `env_var` | ✅ | the override. The last lane attribute that was a string literal inside its resolver (RM184) |
| `rebuild` | ✅ | the unattended adapter, or `None` with `unbuilt` stated |
| `ensure` | ✅ | the pull, or `None` with `unpublished` stated |
| `publish_repo` | ✅ | the HF dataset, or `None` |
| `terms` | ✅ | the `SourceTerms`, or `None`. Drives the `declared_use` gate |
| `publish_command` | — | needed **only** when the lane has a `publish_repo` and no `rebuild` (RM202) |
| `unpublished` / `unbuilt` | — | stated iff the stage is absent |
| `release_label` | — | override only if `release.json`'s `dataset` is not the label |
| `parents` | — | for a derived lane; an absent parent is *could not run*, never an empty result |

## The two routes to publishing, and the trap between them

`cache rebuild --publish` walks lanes **that have a `rebuild` adapter**. That is eight of the nine
publishable lanes, so it reads like the universal route and is not.

**A lane can be publishable without being rebuildable.** `alphagenome_avi` is: its source is 88.5 GB
behind a sign-in whose eligibility clause bars classes of holder, so there is nothing for an
unattended rebuild to fetch — but the *re-encoded* snapshot is publishable. Such a lane needs its own
`publish_command`, and `test_every_publishable_lane_can_actually_be_published` asserts exactly one of
the two routes exists and that a named command answers `--help` in the real Typer tree.

**Publishing sends the description last.** The payload is one commit and `release.json` a second
(RM199), because a description that arrives before its bytes describes a snapshot nobody has. Above
5 GB the payload goes through `upload_large_folder`, which resumes but is **not atomic** — and a
declared layout retirement on that path is *refused*, because RM186 promises the arrival and the
departure are one commit.

**A root-level file must be in the registry or it is silently dropped.** `SNAPSHOT_ROOT_FILENAMES`
carries them in publish order. This has bitten twice: a share-alike snapshot published without the
`LICENSE.txt` it exists to carry, and `avi_knots.parquet`, without which a puller holds scores nobody
can rank.

---

## Checklist: adding a lane

Nothing here is advice — **every line is asserted by a test in `test_cache_lanes.py` (42 of them) or
`test_locations.py`**, and the parenthesis names the guard. If you skip a step the suite tells you;
the point of the list is to not need the suite to find out.

**Naming and resolution**
- [ ] `<name>_build.py` exists, named for the lane, not for the source
      (`test_every_builder_module_has_a_lane_…` — rename the module rather than excepting it)
- [ ] `locations.<NAME>_SUBDIR`, `<NAME>_CACHE_VAR`, `resolve_<name>_reference`,
      `default_<name>_cache_dir` all exist and are wired into the lane
      (`test_every_lane_resolves_through_the_locations_family`,
      `…pairs_its_resolver_with_the_matching_default_directory`)
- [ ] the subdir and the env var are distinct from every other lane's
      (`test_every_lane_names_a_distinct_cache_subdirectory`,
      `test_the_variables_the_module_reads_are_exactly_the_ones_the_lanes_claim`)
- [ ] a line in `.env.template` for the override

**Commands**
- [ ] `build_command` is a command the CLI actually answers
      (`test_every_build_command_the_registry_names_is_one_the_cli_answers_to`)
- [ ] the builder's `--out` default is `repro_out("<lane>")` and **never a literal**
      (`test_every_out_default_is_derived_rather_than_written_as_a_literal`)

**Stages and their reasons**
- [ ] every absent stage states its reason in `unbuilt` / `unpublished`, and no present stage states
      one (`test_an_absent_stage_states_its_reason_and_a_present_one_does_not`)
- [ ] if the lane has a `publish_repo`: it is reachable by a `rebuild` adapter **or** a
      `publish_command`, exactly one (`test_every_publishable_lane_can_actually_be_published`)
- [ ] **run the publish command's `--dry-run` and read the file list.** A field being set is not a
      capability — that is the whole of RM202

**Data and terms**
- [ ] any root-level file the snapshot needs is in `SNAPSHOT_ROOT_FILENAMES`, with `release.json`
      last (`test_a_publish_carries_the_knot_table_and_not_only_the_scores`)
- [ ] `terms` is a `SourceTerms` whose permission axes are each either **documented** or recorded as
      a **reading**, and the difference is written down somewhere — `sources.csv` shows only booleans
      (`test_the_three_permission_axes_each_rest_on_a_different_kind_of_ground`)
- [ ] `release.json` records the source digest and the label a currency check will compare
- [ ] the lane appears in ENRICHER.md's cache table with its legend marks

**Before calling it shipped**
- [ ] `just-dna-enricher cache status` shows the lane, and shows it **present** against a real
      snapshot — not just listed
- [ ] every command you added has been **run**, not only unit-tested. RM202's tests all passed
      against a lane no operator could publish, because they asserted the registry rather than
      invoking the CLI
