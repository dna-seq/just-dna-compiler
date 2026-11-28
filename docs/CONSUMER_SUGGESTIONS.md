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

## S166 — just-dna-registry (liaison), 2026-11-28: a local sequence source that reaches every read, and how it is provisioned

**Context.** A host re-deriving ClinVar-scale modules (about 438k rows over three modules) spends almost all of the
run reading reference sequence one request at a time from the default `seqrepo+https://` source, about 6 reads a
second: 13 to 30 h per sweep, measured from `ga4gh.vrs.dataproxy` log lines. The host's plan is to hand every
`enrich()` path one shared local `SequenceProxy` (a `fasta+file://` GRCh38 FASTA, RM385) and read nothing over HTTP.
Read at `0.10` `d23fd638`:

1. **No lane provisions it.** `CACHE_LANES` has no sequence lane, so `prepare_caches` cannot place the FASTA or its
   `.refget.json` sidecar, and a host's provisioning command has nothing to read. Is the local reference meant to
   stay host-provisioned (then say so in INTEGRATION_0_10, with the file that binds all 25 and its first-read
   cost), or will 0.10 register a lane for it?
2. **A caller's resolver cannot be handed the source.** `enrich()` threads `sequences=` into the resolver it builds
   (`orchestration.py`, "a caller's resolver is never altered"), but a host that passes its own shared
   `EnsemblResolver` (one per process, for the pacing gate) has only the private `_read_base`; left unset,
   `_base_reader()` builds `SequenceProxy()`, the remote default. So on an online run the host's indel anchors are
   still read over HTTP. Asked: a public constructor field on `EnsemblResolver` (a `SequenceProxy`, or the
   reader), or a documented rule that `enrich()` hands a caller's resolver its `sequences` when the resolver holds
   none.
3. **One more reader builds the remote default whatever the host holds**: `civic_draft.py` (the drafter's anchor
   reader, `held_by_one_run(SequenceProxy(offline=offline))`) takes no `sequences=`. `pgx_draft` already takes one.
   Asked: the same parameter there, so a host's one source reaches the drafters too.

**Done would look like**: with a local source passed everywhere a host can pass one, a re-derivation and a draft
make no `ga4gh.vrs.dataproxy` `Fetching https://` request (a socket-tripwire test on the host's side).

## S167 — just-dna-registry (liaison), 2026-11-28: a `.fai` writer beside the FASTA reader

**Context.** RM385's `fasta+file://` reader needs an uncompressed GRCh38 FASTA with `<path.fa>.fai` beside it, and
ENRICHER.md says to index it with `samtools faidx` "or any writer of the same five-column `.fai`". Nothing in the
enricher writes one, and a host that runs only the enricher has no `samtools`, `pysam` or `pyfaidx` (ours has none,
in its lock or on its production box). So a host's provisioning step (download, md5 check, gunzip) must take a new
dependency only to write a five-column file.

**Why it belongs beside the reader.** `fasta.py` already owns the `.fai`'s rules: it refuses an index whose line
endings or wrap width disagree with the file ("FASTA line endings do not match the .fai", "FASTA length or line
wrapping does not match the .fai"). A writer in the same module keeps one owner of that format, so a host's index
and the reader's checks cannot disagree.

**Asked**, either of:
1. `fasta.write_index(path)` (or `FastaReference.index_fasta(path)`): writes `<path>.fai` for an uncompressed FASTA,
   refusing a file it could not then read (mixed wrap widths, a gzip).
2. A provisioning step that indexes when the `.fai` is missing and then does the first full read, so the
   `.refget.json` sidecar is written once at provisioning rather than inside a host's first request.

**Not blocking.** The registry builds its setting, download, checksum and gunzip now, and takes whichever arrives;
until then it would carry `pyfaidx` as a server dependency for this one file.
