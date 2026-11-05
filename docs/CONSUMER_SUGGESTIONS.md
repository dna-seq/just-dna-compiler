# Consumer suggestions

Field notes from consumers adopting the libraries — **the open ones**. An item answered with a
`**Status —**` reply moves to [CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md),
which carries an index of every one and where it landed; the runbook for answering them is
[CONSUMER_TRIAGE_LOOP.md](CONSUMER_TRIAGE_LOOP.md).

**This file is the inbox, so an empty one means nothing is owed** — which is the property the split
exists for, and the reason answered items do not stay here.

## The next item is S129

**Claim ids from here, never from what this file shows.** S1–S127 are all answered and live in the
history file, so an empty inbox says nothing about how many ids are taken — number from the corpus, or
the next report is a second S1. The number is computed rather than remembered:

```
python3 .claude/triage-state.py --next        # scans this file AND the history file
```

It reads this file's path from `.blueprints.toml`'s `[triage]` table. The pinned number above is the
answer when you cannot run it.

Ids are never reused, including for an item answered as a non-issue: the reply is part of the record and
a recycled id would collide with it.

## Everything before S30

S1–S29 are all answered, as of 2026-08-16 — see
[CONSUMER_SUGGESTIONS_HISTORY.md](CONSUMER_SUGGESTIONS_HISTORY.md), whose contents list is the one-line
summary of every one. Seven spawned roadmap items — **RM43**, **RM44**, **RM45**, **RM46**, **RM47**,
**RM48**, **RM49** — and all seven shipped in 0.6.0, RM44 and RM49 on 2026-08-12 and the rest with the
design round on 2026-08-13; **S29** spawned **RM80**, shipped 2026-08-16. [RM_TOC.md](RM_TOC.md) is the index for that half and carries their status. The distinction the sentence was written for still holds:
*answered* means a consumer has a reply, never that the work is finished.

**Answered is not installable, and this is the standing rule for every reply in both files (S34).**
A reply that says "shipped in the tree" means the code and tests are committed, never that a consumer
can `pip install` it — check [CHANGELOG.md](CHANGELOG.md) for whether the version it names has actually
been cut. S25 and S26 were the first replies to carry that state; everything labelled 0.6.0 sat in it
until **2026-08-17, when 0.6.0 was cut and tagged `v0.6.0`** across all three packages. Tagged is still
not installed — publishing is a separate step and the maintainer's call — so the rule is unchanged and
only the example moved. S34 is here because a document of ours presented a table of 0.6 fields as
"also shipped since you last synced", and a consumer spent an afternoon looking for fields no version
they could install has. Write the version, and write whether it was cut.

## Adding one

Append a `## Sn — <what happened>` section with the id above. Write the report, not a request: what you
ran, what you expected, what happened, and what you did about it meanwhile. A candidate fix is welcome
and so is a reason a candidate is wrong — several of the answers in the history file are shaped entirely
by a reporter's argument against their own first option.

Prose is left byte-for-byte when it is answered and when it is moved, so it stays the record of what was
observed rather than of what was decided.

---

## S130 — the Ensembl lane's repository has no public name, so a consumer pinning it spells the string or reads a private one

*From just-dna-registry's liaison seat, 2026-11-05, against the `0.8` branch at `5b1b73b8`, relayed from the
registry's lead while it pre-builds its 0.8 adoption.*

**What we ran.** The registry passes `compile_module(ensembl_reference=…)` a pinned reference id, which lands in
every published (immutable) manifest. Its default was `"just-dna-seq/ensembl_variations"`. RM372 moves the lane
to `just-dna-seq/ensembl_variations_split`, so the default has to move with it (our map's M8).

**What happened.** On the branch the repository id has no public name. The ensembl lane's `publish_repo` is
`None` (`caches.py:946`; the `unbuilt` reason explains it, since prepare-annotations builds the snapshot), and
the string lives in `download._ENSEMBL_HF_PREFIX = "datasets/just-dna-seq/ensembl_variations_split/data"`
(`download.py:64`), private. The public map `download.SNAPSHOT_REPO_PREFIXES["ensembl"]` (RM372) carries the same
value, but as an fsspec path prefix, not a repo id, so getting `just-dna-seq/ensembl_variations_split` out of
it means stripping `datasets/` and `/data` from a spelling. Every other pulled lane has a public
`DEFAULT_*_REPO_ID` (`DEFAULT_CLINVAR_REPO_ID` and its siblings, imported at `caches.py:178`).

**What we did meanwhile.** Our lead's pre-build spells the new repo in our `config.py`, with a test that reads
your private prefix to catch drift. Both retire with either fix below.

**Candidate fixes.** (a) A public `DEFAULT_ENSEMBL_REPO_ID` beside the others, with `_ENSEMBL_HF_PREFIX` derived
from it the way the other prefixes presumably are. (b) A public map of lane → repo id beside
`SNAPSHOT_REPO_PREFIXES`, which answers the question for every pulled lane at once; (b) reads better if
`publish_repo` is meant to stay "where this tier publishes", which the ensembl lane does not. One reason (a)
may not be the whole answer for us: what a reproducibility pin wants may be the *release* rather than the
repo, and `locations.ensembl_release_label` (RM372) already gives that from the snapshot itself. If that is
your view, say so and we pin the release label instead; the repo id still has no public name for anyone
else who needs it.
