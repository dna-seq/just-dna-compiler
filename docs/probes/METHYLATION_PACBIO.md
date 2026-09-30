# Methylation on PacBio HiFi — what a consumer actually holds, and whether a module can bin it

**Question:** a consumer holding PacBio HiFi samples has methylation data. In which files and fields,
at what scale, and can a just-dna annotation module point at it and bin it the way `repeat_alleles.csv`
bins `FORMAT/REPCN`? The open question from the VCF 4.5 audit (§6) was whether any real tool writes
the 4.5 `M5mC`/`DPM5mC`/`ADM5mC` FORMAT keys, or whether PacBio users hold bedMethyl-like BED files
instead, which a VCF pointer never reaches.

**Date of analysis:** 2026-09-30. **This is evidence, never contract**, the standing rule for
everything under `docs/probes/`. It proposes no design and files nothing; §6 prices what the
measurements imply.

**Basis — tools, read from source and run where marked.** Every repository was cloned on 2026-09-30
into `data/interim/methylation/` (git-ignored); versions are the latest GitHub release on that day.

| Tool | Version read | Released | Source read | Run here |
|---|---|---|---|---|
| TRGT | v5.1.0 (HEAD `b21c621`) | 2026-06-10 | `docs/vcf_files.md`, `src/trgt/writers/write_vcf.rs`, `src/trgt/workflows/tr.rs`, `src/trgt/reads/read.rs`, `CHANGELOG.md`, tags v0.7.0–v0.9.0 | yes, binary v5.1.0 |
| pb-CpG-tools | v3.0.0 (HEAD `119ff2b`, 2025-07-09) | 2025-01-28 | `README.md`, `CHANGELOG.md` | yes, binary v3.0.0, `model` and `count` modes |
| MethBat | v1.1.0 (HEAD `859e01c`, 2026-07-15) | 2026-06-02 | `docs/pileup_guide.md`, `docs/profile_guide.md`, `docs/report_guide.md`, `docs/migration_v1.md`, `CHANGELOG.md`, `data/report_regions/` | yes, binary v1.1.0: `pileup`, `profile`, `report` |
| HiFi-human-WGS-WDL | v4.0.0 (`15e82cb`) | 2026-08-18 | `docs/tools.md`, `docs/tools_containers.md`, `docs/singleton.md`, `workflows/wdl-common/wdl/tasks/methbat.wdl`; `docs/tools_containers.md` at tags v2.1.0, v3.0.0, v3.1.0, v3.2.0 | no |
| modkit (ONT) | v0.6.4 (HEAD `5cecc3f`) | 2026-06-11 | `book/src/intro_pileup.md`, `book/src/migrating_060.md`, `tests/resources/` | yes, binary v0.6.4 (see §1.6) |
| pbsv | v2.11.0 | 2025-02-26 | whole repo grepped | no |
| sawfish | v2.2.1 | 2025-11-04 | whole repo grepped | no |
| HiFiCNV | v1.0.1 | 2024-10-22 | whole repo grepped | no |
| Paraphase | v4.1.0 | 2026-09-25 | whole repo grepped | no |
| DeepVariant | v1.10.0 (latest release 2026-03-05) | — | GitHub code search over `google/deepvariant`; `deepvariant/channels/base_methylation_channel.cc`, `deepvariant/methylation_aware_phasing.h` | no |
| rastair | v2.2.0 | 2026-08-24 | `src/vcf/schema.rs`, `tests/snapshots/call_cli__vcf_with_ml.snap` | no |
| VCF 4.5 | hts-specs `510c107` (2026-08-12) | — | `data/interim/vcf45/hts-specs/VCFv4.5.tex`, the §1.6.2 block and Table 2 | — |

**Basis — data.** Every file below is public and was opened here; §2 gives the URLs.

- PacBio's 2022Q4 Revio WGS pipeline outputs for the HG002 trio (TRGT 0.5.0, pb-CpG-tools 2.3.2).
- PacBio's 2026Q2 HG002 SPRQ-Nx run (TRGT 5.0.0, pb-CpG-tools 3.0.0, MethBat 0.17.0). The TRGT VCF and
  CpG BEDs were read by tabix range request, and the haplotagged BAM was sliced over three loci.
- PacBio's 2024Q4 PureTarget repeat-expansion panel on Coriell lines (TRGT 1.1.2), including three FMR1
  expansion carriers.

**The single most load-bearing measurement.** Two female FMR1 carriers, each with one expanded and one
normal allele, as TRGT reports them:

| sample | karyotype | `MC` (CGG per allele) | `AM` (methylation per allele) |
|---|---|---|---|
| HM06968 | XX | `33,112` | `0.90,0.07` |
| NA06905 | XX | `23,79` | `0.03,0.88` |
| NA09237 | XY | `898` | `0.85` |

In HM06968 the expanded allele is the **unmethylated** one. Every element rule the format has picks a
value by the field's own magnitude, so `largest` over `AM` selects `0.90`, which belongs to the
33-repeat allele. The bin a fragile X module means is "the methylation of the expanded allele", and
that means selecting an index of `AM` by the values of a *different* field, `MC`. No member of
`VALID_ELEMENT_RULES` can say that. The male record is the case the `fmr1_cgg_repeat` example's prose
describes, and it holds there: 898 CGG, `AM=0.85`.

---

## 1. What each tool emits

### 1.1 TRGT — a per-allele methylation mean in a VCF FORMAT field

The field is `AM`. The header line TRGT writes today (`write_vcf.rs:39`, and every file opened here from
TRGT 1.1.2 on):

```
##FORMAT=<ID=AM,Number=.,Type=Float,Description="Mean methylation level per allele">
```

`docs/vcf_files.md` describes it as *"Mean 5mCpG methylation level per allele (`.` when no CpG sites or
methylation data unavailable)"*, one value per called allele, in **TRGT allele order**, which the same
page says is not reordered to match a phased `GT`.

What the number is, read from the source rather than the page:

- **Per read**, `get_tr_meth` (`tr.rs:260`) averages the ML probability (`value / 255.0`) over the CpG
  dinucleotides that fall **inside the repeat span** of that read. Flanks are excluded, so this is the
  methylation of the tract, not of the promoter CpG island around it.
- **Per allele**, `get_meth_by_hap` (`tr.rs:199`) assigns each spanning read to an allele by its tract
  length (`assign_read`) and takes the mean of those per-read means. The allele assignment is by
  length, not by the `HP` haplotag.
- `encode_am` (`write_vcf.rs:401`) rounds to two decimals and writes a missing value for an allele with
  no reads that carried a methylation profile.
- A haploid call (`GT=1`, a male chrX, or `--karyotype XY`) carries one value.

So it is a mean of means, a probability-weighted fraction, not a count of methylated reads. It is 5mC
only: `get_meth` keeps modifications whose canonical base is `C` and never asks the modification code.
That is safe for 5mC-only BAMs, and TRGT 1.5.1 fixed a bug in exactly this path for BAMs carrying
several modifications. What it does with a BAM carrying both 5mC and 5hmC calls on the same C (the
SPRQ-Nx data in §2 does) was not established.

**The type and scale moved once, and the changelog does not say so.** The 2022Q4 file, written by TRGT
0.5.0, declares:

```
##FORMAT=<ID=AM,Number=.,Type=Integer,Description="Mean methylation level per allele">
chrX	147912051	.	CGGCGG…CGG	CGGCGG…CGG	0	.	TRID=FMR1;END=147912110;MOTIFS=CGG;STRUC=(CGG)n	GT:AL:ALLR:SD:MC:MS:AP:AM	1:93:90-97:18:31:0(0-93):0.978495:50
chr1	44836	.	AAATAAATAAATAAATAAATAAATAAATAAAT	AAATAAATAAATAAATAAATAAATAAATAAATAAATAAATAAAT	0	.	TRID=chr1_44835_44867;END=44867;MOTIFS=AAAT;STRUC=(AAAT)n	GT:AL:ALLR:SD:MC:MS:AP:AM	0/1:32,44:31-32,43-44:8,3:8,11:0(0-32),0(0-44):1,1:159,185
```

The earliest source tag in the repository, v0.7.0 (2023-12-11), already declares `Type=Float`. TRGT
0.1.0–0.5.0 were released without source, and `CHANGELOG.md` has no entry for the change, so the
integer scale (values up to 185 are seen, which reads like the 0–255 ML byte) is **inferred, not
verified**. An integer `AM` also appears on the AAAT repeat above, which has no CpG in its span, so the
0.5.0 computation was not the one quoted from 5.1.0 either. A band authored on `[0, 1]` misreads every
0.5.0 file.

A current record, from the 2026Q2 pipeline run on HG002 (male, normal FMR1):

```
##trgtVersion=5.0.0-e9acee0
chrX	147912049	.	CGCGG…GGC	CGCGG…GGC	.	.	TRID=FXS_FMR1;END=147912111;MOTIFS=CGG;STRUC=<TR>	GT:AL:ALLR:SD:MC:MS:AP:AM	1:95:88-98:27:29:0(1-31)_0(34-61)_0(64-94):0.957895:0.1
```

The same run carries a second, wider record over the same tract
(`TRID=chrX_147911948_147912141_GGC`, `AM=0.11`), from a different catalog entry. The `TRID` of the
FMR1 record is `FMR1` in the 2022Q4 and PureTarget files and `FXS_FMR1` in the 2026Q2 one, so which
record a consumer reads for "FMR1" depends on the catalog the pipeline shipped.

Rerunning TRGT 5.1.0 here on the PureTarget BAMs (`--preset targeted`) and on the HG002 slice
reproduced the published values: NA09237 `GT=1`, `MC=895`, `AM=0.85`; HM06968 `MC=32,112`,
`AM=0.9,0.07`; HG002 `MC=29`, `AM=0.1`.

**`AM=.` has two readings, and the file cannot tell them apart.** `get_tr_meth` returns nothing both
when the span holds no CpG (the AAAT repeat in a modern file) and when the input BAM carries no MM/ML
tags at all. No FORMAT field says whether methylation was called. `SD` is a depth, but a depth of
length support, not of methylation calls.

### 1.2 pb-CpG-tools — per-CpG BED, one file per haplotype

`aligned_bam_to_cpg_scores` writes `<prefix>.combined.bed.gz`, and `hap1`/`hap2` when the BAM is
haplotagged, each with a tabix index and a bigWig. Since v3.0.0 the BEDs are bgzipped and carry a
`##` header; v2 wrote plain, headerless BED (the 2022Q4 files, 1.3 GB uncompressed, are v2.3.2).

Columns 1–6 are shared by both pileup modes: chrom, 0-based begin (the C of the CpG: the reference
at chr15:24954889–24954890, 1-based, reads `CG`), end (one base), `mod_score`
(**percent**), `type` (`Total`, `hap1`, `hap2`), `cov`. `model` mode (the default) adds
`est_mod_count`, `est_unmod_count`, `discretized_mod_score`; `count` mode adds `mod_count`,
`unmod_count`, `avg_mod_score`, `avg_unmod_score`. One row per CpG, strands collapsed. The bigWig keeps
columns 1–4.

A real header and rows, from the 2026Q2 HG002 run, over the SNURF DMR:

```
##pb-cpg-tools-version=3.0.0
##cmdline=aligned_bam_to_cpg_scores --threads 16 --bam HG002.GRCh38.haplotagged.bam --ref human_GRCh38_no_alt_analysis_set.fasta --output-prefix HG002.GRCh38 --min-mapq 1 --min-coverage 4
##pileup-mode=model
##modsites-mode=denovo
##min-coverage=4
##min-mapq=1
##basemod-source=jasmine	26.1.3 (commit v26.1.3)
#chrom	begin	end	mod_score	type	cov	est_mod_count	est_unmod_count	discretized_mod_score
chr15	24954888	24954889	46.2	Total	63	30	33	47.6
chr15	24954888	24954889	86.7	hap1	32	28	4	87.5
chr15	24954888	24954889	4.1	hap2	31	1	30	3.2
```

The 2022Q4 v2.3.2 row shape, for comparison (no header at all):

```
chr1	10468	10469	63.1	Total	14	8	6	57.1
```

Running v3.0.0 here on the BAM slice reproduced those three rows exactly in `model` mode. In `count`
mode the same site reads `47.6` Total, `78.1` hap1, `16.1` hap2. So the two modes of one tool
disagree by 12 points on the unmethylated haplotype at one CpG, and the mode is a header line, not a
column.

### 1.3 MethBat — the pileup that replaced pb-CpG-tools, plus region labels

MethBat 1.0.0 (2026-05-19) added `methbat pileup` and dropped pb-CpG-tools as an input. It writes one
BED per modification, with `Total`/`hap1`/`hap2` rows interleaved in one file, 15 columns. From the run
here (`methbat pileup`, v1.1.0, same BAM slice):

```
##methbat_version=1.1.0-fbf4686
##base_modification=5mC
#chrom	start	end	name	score	strand	mod_score	type	cov	mod_count	unmod_count	inferred_unmod_count	diff_base_count	avg_mod_score	avg_unmod_score
chr15	24954888	24954889	m	476	.	47.6	Total	63	30	33	0	0	0.897	0.114
chr15	24954888	24954889	m	781	.	78.1	hap1	32	25	7	0	0	0.929	0.158
chr15	24954888	24954889	m	161	.	16.1	hap2	31	5	26	0	0	0.736	0.102
```

and in the `5hmC` file, stranded:

```
chr15	24954888	24954889	h	0	+	0.0	Total	63	0	63	63	0	0.000	0.000
```

`mod_score` is percent, `score` is the same value in tenths (0–1000), and `name` is the modification
code. The default is pb-CpG-tools **count** mode (the numbers above match it), not model mode.

Two downstream commands aggregate over regions:

- `methbat profile` labels each region `Methylated` (mean ≥ 80 %), `Unmethylated` (≤ 20 %),
  `AlleleSpecificMethylation` (≥ 50 % of sites phased, Fisher p ≤ 0.01, haplotype delta ≥ 50 points),
  `Uncategorized` or `NoData`, with `mean_hap1_methyl`, `mean_hap2_methyl`, `mean_combined_methyl`,
  site counts and median coverages.
- `methbat report` compares those labels against an expected category per region and writes `PASS`,
  `Inconclusive`, `AnomalousQcWarning` or `Anomalous`, with QC warnings (`LowPhasedSites`,
  `LowHaplotypeCoverage`, `WeakASM`). MethBat ships `data/report_regions/hg38_imprinting_targets.tsv`,
  15 imprinted DMRs from Mackay et al. 2022, Table 2, each `expected_category=AlleleSpecificMethylation`
  and `anomalous_categories=Methylated;Unmethylated`.

`methbat report` run here against that file:

```
chrom	start	end	region_label	report_summary	qc_warnings	expected_category	summary_label	mean_combined_methyl	mean_meth_delta	mean_hap1_methyl	mean_hap2_methyl
chr11	2698717	2701029	KCNQ1OT1:TSS-DMR	PASS	PASS	AlleleSpecificMethylation	AlleleSpecificMethylation	49.4	71.1	15.3	86.4
chr15	24954856	24956829	SNURF:TSS-DMR	PASS	PASS	AlleleSpecificMethylation	AlleleSpecificMethylation	48.9	-65.5	80.1	14.6
```

(The other 13 regions report `NoData` or `Inconclusive` here only because the slice did not include
them.)

**The scale moved at 1.0.0.** `docs/migration_v1.md` calls it a breaking change: profile, report and
compare columns that were unit fractions are now percentages. The 2026Q2 pipeline ran MethBat 0.17.0
and its `profile.tsv` holds fractions:

```
#methbat_version=0.17.0-7c5e249
#command=methbat profile --input-prefix HG002.GRCh38.cpg_pileup --input-regions …/cpgIslandExt.sorted.hg38.tsv --output-region-profile HG002.GRCh38.methbat.profile.tsv
chr15	24954888	24955907	CpG:_77	AlleleSpecificMethylation	…	0.8806080283353007	0.041076080548510176	-0.8395319477867907	…	0.48489584542693237	…
```

That is the same DMR in the same sample, `0.88`/`0.04` here and `80.1`/`14.6` from 1.1.0, under the
same column names.

### 1.4 The HiFi-human-WGS-WDL pipeline — which of these a user ends up holding

From `docs/tools_containers.md` at each release tag:

| pipeline | date | CpG pileup | region profile | TRGT |
|---|---|---|---|---|
| v2.1.0 | 2025-01-10 | pb-CpG-tools 2.3.2 | — | 1.4.1 |
| v3.0.0 | 2025-07-07 | pb-CpG-tools 3.0.0 | — | 3.0.0 |
| v3.1.0 | 2025-09-09 | pb-CpG-tools 3.0.0 | MethBat 0.15.0 | 4.0.0 |
| v3.2.0 | 2026-01-15 | pb-CpG-tools 3.0.0 | MethBat 0.15.0 | 5.0.0 |
| v4.0.0 | 2026-08-18 | MethBat 1.1.0 `pileup` | MethBat 1.1.0 | 5.1.0 |

In v4.0.0 (`methbat.wdl`) the user holds, per sample:

- `<prefix>.5mC.bed.gz` (+ `.tbi`) — per-CpG, `Total`/`hap1`/`hap2` rows, the §1.3 layout;
- `<prefix>.5hmC.bed.gz` (+ `.tbi`) — per-strand;
- `<prefix>.6mA.bed.gz` — declared as an output but skipped by default (`skip_6mA = true`);
- `<prefix>.methbat.profile.tsv` — `methbat profile` over the `methbat_region_tsv` shipped in the
  reference container. The 2026Q2 run used `cpgIslandExt.sorted.hg38.tsv`, UCSC CpG islands;
- the phased TRGT VCF, with `AM`.

The pipeline runs `methbat profile`, **not** `methbat report`, so no pipeline output labels the
imprinted DMRs. A user holds CpG-island numbers, at island boundaries, which for SNURF (`CpG:_77`,
chr15:24954888–24955907) and KCNQ1OT1 (`CpG:_159`) sit inside the Mackay DMRs but are not them.

The 2026Q2 run's VCFs declare `VCFv4.2` (TRGT, DeepVariant small variants), `VCFv4.3` (MitorSaw)
and `VCFv4.4` (sawfish structural variants). None declares 4.5.

### 1.5 The other PacBio callers: none writes a methylation field

- **pbsv 2.11.0, HiFiCNV 1.0.1, Paraphase 4.1.0** — no occurrence of `methyl`, `M5mC` or `VCFv4.5`
  anywhere in the repository.
- **sawfish 2.2.1** — two hits, both in a vendored BAM utility (`lib/rust-vc-utils/src/bam_utils/basemod.rs`)
  that *reads* 5mC from MM/ML. Nothing in its VCF writer.
- **DeepVariant** — reads 5mC as an input pileup channel (`BaseMethylationChannel`) and uses it for
  methylation-aware phasing of unphased reads (`methylation_aware_phasing.h`). A code search of the
  repository for `M5mC` returns zero hits. It consumes methylation and emits none.
- **GitHub, `org:PacificBiosciences M5mC`** — zero hits.

### 1.6 Beyond PacBio, for the record

**ONT modkit 0.6.4** writes bedMethyl, 18 columns: chrom, start, end, modification code, score
(= N_valid_cov), strand, thickStart, thickEnd, colour, N_valid_cov, **percent modified**, N_mod,
N_canonical, N_other_mod, N_delete, N_fail, N_diff, N_nocall (`book/src/intro_pileup.md`). With
`--phased` it writes `combined`, `hp1` and `hp2` files. A fixture row from `tests/resources`:

```
oligo_1512_adapters	9	10	m	4	.	9	10	255,0,0	4	25.00	1	1	2	0	0	2	0
```

The book mentions no VCF output anywhere. Run here on the PacBio SPRQ-Nx slice, modkit produced **zero
rows**: `modkit modbam check-tags` flagged 103 of 161 records `conflict-explicit-prob-greater-than-one`
(jasmine 26.1.3 writes 5mC and 5hmC calls on the same C), and pileup still processed nothing after
`adjust-mods --ignore h` and `--no-filtering`. That was not investigated further, and it says nothing
about ONT data.

**Who writes VCF 4.5 base-modification fields at all.** GitHub code search on 2026-09-30:
`"ID=M5mC"` 22 hits, `"ID=DPM5mC"` 13. Apart from spec copies and RDF fixtures, two producers:

- **rastair** (TAPS / 5-base, Ludwig Institute; used by JAX's `5baseTAPS` pipeline) writes
  `##fileformat=VCFv4.5` with `M5mC`/`DPM5mC`/`ADM5mC`, but declares them `Number=.`, not the spec's
  `Number=M`. Its source says why: *"`Number=M` … is not in the VCF grammar. htslib tolerates it, but
  a strict parser (noodles, and so every tool built on it) rejects the whole file rather than the
  line."* It writes a value on both the C and the G of a CpG, which is the strand-specific form the
  spec allows (its INFO `M5mC_Strands` counts per strand); the `Number=.` is the departure. A real record from its test snapshot:

  ```
  ##FORMAT=<ID=M5mC,Number=.,Type=Float,Description="Methylation level at CpG sites, one value per CpG context">
  chr19	6105712	.	C	.	99	PASS	AD=10;BQ=35.5778;DP=18;MQ=60;M5mC_Strands=4,8,6,0;CPG	GT:GL:GC:DP:M5mC:DPM5mC:ADM5mC	0/0:99:18:18:0.666667:12:8
  ```

- **Illumina DRAGEN 5-base** gVCFs, as documented by Illumina Connected Annotations: FORMAT
  `M5mC`/`DPM5mC` on reference blocks, plus an **INFO** `M5mC` declared `Number=R,Type=String`, a
  per-base context string, which is not the spec's field at all. The FORMAT header line is not shown
  in that page, and no DRAGEN file was opened here.

So the fields exist in the wild, from short-read methylation chemistries, and neither producer writes
them in the spec's shape. Nothing in the PacBio stack writes them.

---

## 2. The open samples

| what | URL (under `https://downloads.pacbcloud.com/public/`) | opened here |
|---|---|---|
| 2022Q4 HG002 trio, pipeline outputs (README lists tool versions) | `revio/2022Q4/WGS-variant-pipeline-analysis/` | README; `trgt/HG002.GRCh38.haplotagged.trgt.sorted.vcf.gz` (7 MB, whole); first bytes of `cpg/HG002.GRCh38.combined.bed` and `hap1.bed` by HTTP range |
| 2024Q4 PureTarget panel, 24 Coriell lines | `2024Q4/Vega/PureTargetCoriell24/` | README; `puretarget_report.genotype.csv`; `TRGT_VCF_files/` for HM06968, NA06905, NA09237 (both reps), NA03697, NA13509, ND11494; `PBMM2-BAM-Input-For-IGV-And-TRGT/` BAMs for NA09237_rep1 and HM06968 (≈ 0.4–0.6 MB each) |
| 2024Q4 HG002, pipeline v2.0.0-rc4 | `2024Q4/Vega/HG002/Human-WGS-variant-pipeline/` | listed only (headerless v2-era CpG BEDs, TRGT VCF) |
| 2026Q2 HG002 SPRQ-Nx, three uses (5mC, 5hmC, 6mA called on instrument) | `2026Q2/HG002-SPRQ-Nx/Use1/analysis/` | README, `inputs.json`, `outputs.json`, `HG002.stats.txt`, `HG002.GRCh38.methbat.profile.tsv` (5 MB, whole); tabix slices of `HG002.GRCh38.trgt.sorted.vcf.gz` and the three `cpg_pileup.*.bed.gz`; a 161-read slice of the 64.7 GB `HG002.GRCh38.haplotagged.bam` over SNURF, KCNQ1OT1 and FMR1 |

The PureTarget README states the data cover only each sample's target locus, for privacy. The
consumer-shaped files a module would read are all here: the TRGT VCF, the CpG BEDs in two generations,
and a MethBat profile. What was **not** found is any public PacBio file with a VCF 4.5
base-modification field. The searches: the full directory crawl of `revio/` and of every quarterly
folder from `2024Q4` to `2026Q2` for `vcf`, and the GitHub code searches in §1.5–§1.6.

The runs here (§1.1–§1.3) used the reference as UCSC hg38 `chr11`, `chr15` and `chrX`; the scratch
outputs are in `data/interim/methylation/run/`.

---

## 3. Six measured facts a design would have to meet

1. **The allele a band is about is selected by another field.** HM06968 and NA06905 above. In both
   female carriers one allele is about 0.9 and the other below 0.1, and which one is which does not
   follow length. That is consistent with X inactivation (n = 2, not established here). The format's
   consequence does not depend on the biology: on a two-allele record a band on `AM` reads the value
   of whichever allele the rule picks, and no current rule can pick "the allele with the most CGG".
2. **An expansion's CpGs have no reference coordinate.** NA09237's reads carry about 2,700 bp of tract.
   pb-CpG-tools run here on that BAM reports 88 CpG sites for the whole locus, all at reference
   positions; the inserted tract has no position to report a CpG at. Per-base files cannot hold the
   methylation of an expanded repeat. Only a per-allele summary like `AM` can.
3. **The same quantity arrives on four scales across seven fields.** TRGT 0.5.0 `AM` integer (scale
   unverified), TRGT ≥ 0.7
   `AM` fraction, pb-CpG-tools `mod_score` percent, MethBat 0.17 profile fraction, MethBat 1.x profile
   percent, MethBat `score` tenths of a percent, and VCF 4.5 `M5mC` fraction. Twice the scale changed
   under an unchanged field or column name.
4. **The number depends on the tool and its mode.** At chr15:24954888, hap2 is 4.1 % in pb-CpG-tools
   `model` mode and 16.1 % in `count` mode (MethBat's default). The mode is a header line.
5. **Haplotype labels are not parental.** In one sample the methylated allele is `hap1` at SNURF and
   `hap2` at KCNQ1OT1. HiPhase haplotypes are phase-block-local, so no file here can say "the maternal
   allele is methylated". A band can say "one allele methylated and the other not", or bin the delta
   or the pooled value.
6. **Absence has more than one cause.** A missing `AM` is either no CpG in the span or no MM/ML in the
   BAM (§1.1). A missing BED row is coverage below `--min-coverage` (4) or no CpG in the reads
   (`denovo` sites mode), never "unmethylated". The H19/IGF2 IG-DMR in the 2026Q2 run has combined rows
   (mean coverage 11.9) but no haplotype rows at all, which MethBat's own README attributes to ALT
   contigs pulling reads away from the locus.

---

## 4. Mapping onto the format

### 4.1 FMR1 repeat methylation — reachable today, and one rule short

What a row would point at: the TRGT VCF, `FORMAT/AM`, `Number=.`, `Type=Float`, one value per called
allele, on `[0, 1]` since TRGT 0.7. `source_field: FORMAT/AM` already passes the pointer grammar. The
bands the corpus example asserts in prose are a fraction of the tract methylated: NA09237 (full
mutation, male) 0.85, HG002 (normal, male) 0.10.

What it needs that the format lacks:

- **a measure kind.** None of the five `VALID_MEASURE_KINDS` is a methylation fraction; binning it as
  `allele_fraction` would put two quantities under one name (P5), as the VCF 4.5 audit §6 said.
- **a host table.** `repeat_alleles.csv` pins `measure_kind=repeat_count` (`RepeatAlleleRow._EXPECTED_KIND`),
  and it is the table keyed `(gene, repeat_unit)` that already names the FMR1 tract.
- **an element rule that selects by another field.** "The `AM` value at the allele index where `MC` is
  largest." On a hemizygous record (`GT=1`) any rule gives the one value, which is why the male case
  works. On a two-allele record none of the eight rules gives the right one (§3.1).
- **the unresolved sentinel, with its two causes named.** The existing `unresolved` row covers "no
  value"; it cannot say which of §1.1's two absences happened.

An adjacent observation, for the same module: no PacBio file opened here carries `REPCN`. The
example's count pointer `FORMAT/REPCN` is ExpansionHunter's key. TRGT carries the count as `MC`, a
`Type=String` field with `_`-joined per-motif counts inside each allele (`18_8,25_8` at HTT), so the
count half of the module does not reach a PacBio user either, unless the author writes
`FORMAT/REPCN|FORMAT/MC` and the consumer can parse a motif-segmented string.

### 4.2 Imprinting (SNURF/SNRPN at 15q11–13, KCNQ1OT1 at 11p15 IC2, H19 at IC1) — real data, no pointer

What the data are: per-CpG rows in `<prefix>.5mC.bed.gz` (MethBat 1.x) or
`<prefix>.cpg_pileup.{combined,hap1,hap2}.bed.gz` (pb-CpG-tools 3.x), and a region aggregate in
`profile.tsv`. For HG002, measured three ways:

| DMR (Mackay 2022, GRCh38, 0-based) | pipeline pb-CpG-tools model, mean of sites | MethBat 1.1.0 `report` | pipeline MethBat 0.17.0 `profile` (CpG island) |
|---|---|---|---|
| SNURF:TSS-DMR chr15:24954856–24956829 | Total 48.7, hap1 84.1, hap2 6.6 (113 sites) | ASM, PASS; 48.9 / 80.1 / 14.6 | `CpG:_77`: ASM; 0.88 / 0.04 |
| KCNQ1OT1:TSS-DMR chr11:2698717–2701029 | Total 48.5, hap1 8.9, hap2 87.3 (193 sites) | ASM, PASS; 49.4 / 15.3 / 86.4 | `CpG:_159`: ASM; 0.07 / 0.91 |
| H19/IGF2:IG-DMR chr11:1997581–2003510 | Total 38.6 (250 sites, mean cov 11.9), no haplotype rows | not in the slice | `CpG:_19` Methylated, `CpG:_27` Uncategorized, unphased |

What a module row would need to state:

- **the region**, as chrom, start and end on a named build. No VCF record exists for it, so
  `variant_key` and `rsid` do not apply.
- **the file and column**: a BED column (`mod_score`) in rows of one `type`, or a `profile.tsv` column
  (`mean_combined_methyl`). `source_field` is a VCF pointer by grammar and description, so it cannot
  reach either.
- **the aggregation** from sites to region (MethBat's is the mean of site percentages over the sites
  inside the region). `profile.tsv` has done it already, but only for the regions the pipeline was
  given, which in the 2026Q2 run were CpG islands.
- **the haplotype selector**: `Total`, or a statement about both haplotypes together (the delta, or
  "one high and one low"). §3.5 rules out "the maternal allele".
- **the unit** (§3.3) and **the modification** (5mC; the 5hmC file sits beside it).
- **the bands.** MethBat's `report_regions/README.md` says loss of imprinting *"typically manifest[s]
  as fully methylated or unmethylated"*, and that where phasing is absent a combined value near 50 %
  may be treated as normal. That is a three-band pooled shape, with MethBat's own thresholds at 20 and
  80 %, plus a haplotype-delta band for the ASM confirmation.
- **callability**: a coverage floor (`cov` per site; `median_hap*_coverage` or `num_phased_sites` per
  region), since a missing row is not an unmethylated one (§3.6).

MethBat's `hg38_imprinting_targets.tsv` is itself close to such a module: region, label, expected
category, anomalous categories. What it lacks for this format is a citation per row and bands a
consumer applies without running MethBat.

---

## 5. The design questions, against the data

- **Per-base vs region.** Settled by the data: both clinical questions are regional. TRGT has already
  aggregated over the tract, per allele; MethBat `profile`/`report` aggregate over a region. The
  per-base BED is what a consumer holds, not what a band reads. A per-base element rule, the VCF 4.5
  audit's "the value at this base on this strand", has no customer in the PacBio stack.
- **Pooled vs per-haplotype.** Dissolved for FMR1: `AM` is per allele, selected by length, not by
  haplotag. For imprinting both exist (`Total` and `hap1`/`hap2` rows) and both are meaningful: the
  pooled value carries the three-band answer, and the haplotype values confirm allele-specificity, but
  never with a parent attached (§3.5).
- **Modification type as an axis.** Real. MethBat writes one file per modification and a `name`
  column, the SPRQ-Nx instrument calls 5mC, 5hmC and 6mA, and VCF 4.5 names each (`M5mC`, `M5hmC`,
  `M6mA`). TRGT and pb-CpG-tools are 5mC only. If it is ever a kind, P5 wants the modification as its
  own axis rather than folded into several kind names.
- **Tissue.** In no file opened here. HG002 and the Coriell samples are cell lines. MethBat's
  `data/README.md` warns that its HPRC cell-line background gives more false calls on blood. It would
  be a column, as `HeteroplasmyRow.tissue` is, and nothing in the data supplies it.
- **The element rule.** Sharpened. What is missing is not a per-base rule but a cross-field one: pick
  an index of one field by the values of another (§3.1).
- **Callability via a depth field.** Partly answered. BED rows carry `cov`, `mod_count`/`unmod_count`,
  and profiles carry median coverages and phased-site counts. TRGT carries none for methylation, and
  its missing value is ambiguous (§1.1).
- **Whether `source_field` reaches the data.** Yes for `FORMAT/AM`, and nothing else. Every per-base or
  per-region methylation number on PacBio is in a BED or TSV. VCF 4.5 `M5mC` would be reachable by
  grammar, but no PacBio tool writes it, and the two producers found write it with `Number=.`.

---

## 6. What it would cost

Read against `docs/CONSTITUTION.md` in full, legality first (P3, P6, P8), then price (P9). Everything
below is additive, so everything is minor-legal and nothing is patch scope.

| addition | legality | P9 cost |
|---|---|---|
| a `measure_kind` member for a methylation fraction | minor: an additive vocabulary member (P3, P6) | small but authored, and a one-way door under P5, so the name wants the audit P5 asks for. The data say it should be a fraction on `[0, 1]` with the unit in the description, and consumers of MethBat 1.x or pb-CpG-tools divide by 100 |
| hosting `AM` bins in `repeat_alleles.csv` | minor, if the table accepts a second kind and the kind joins the bin-group key; a relaxed validation accepts more and invalidates nothing (P8) | no new column, but a table whose rows then mean two quantities; the alternative, a new table kind keyed like `repeat_alleles.csv`, is full cost |
| a cross-field element rule | minor: a new `VALID_ELEMENT_RULES` member is additive | a member alone would have to hard-code `MC`, a TRGT convention, into the vocabulary. Naming the selecting field needs a new optional pointer column, full cost and a new shape of rule. The one-way door here is larger than §6 of the VCF 4.5 audit priced |
| a region-level methylation table (imprinting) | minor: a new optional table kind (P3) | full cost: region, build, file and column, row selector, aggregation, unit, modification, coverage floor, bands. P9's "one concern per table" gate is met only if it stays that one concern |
| widening `source_field` to name a BED/TSV column | grammar widening is minor-legal, since every value that passed still passes | cheap in columns, dear in meaning: one field would then name either a VCF key or a column in some other file, which is the overloading P5 forbids. The priced alternative is a separate pointer column |

The FMR1 half is the cheaper one and the only one with a live pointer: a kind member plus the
cross-field selection. The imprinting half is a new table at full cost, against no consumer request.
The RELEASE_CYCLE rule that a commit on `main` is patch scope only puts either half on the open minor
branch.

---

## 7. Verdict

**Three answers, not one.**

- **FMR1 repeat methylation: real.** TRGT writes `FORMAT/AM` in every version whose output or source was
  opened (0.5.0, 0.7.0 to 5.1.0); every PacBio pipeline output opened here carries it; open samples exist, including a male full mutation
  (NA09237, 898 CGG, `AM=0.85`), reproduced here with TRGT 5.1.0. The pointer grammar reaches it today.
  A module cannot yet bin it correctly on a two-allele record.
- **Imprinting: the data are real, the pointer is not.** HG002 shows allele-specific methylation at
  SNURF and KCNQ1OT1 in pipeline outputs and in MethBat run here. All of it is in BED and TSV files,
  and `source_field` cannot name a column in either.
- **VCF 4.5 `M5mC` from PacBio: not real yet.** No PacBio tool writes it, no PacBio VCF opened declares 4.5, and the two producers found anywhere (rastair, DRAGEN 5-base) are short-read and write it in a
  shape that departs from the spec's `Number=M`.

---

## 8. Could not verify

- **The TRGT 0.5.0 integer `AM` scale.** Source for 0.1.0–0.5.0 is not in the repository; values up to
  185 suggest the 0–255 ML byte. Also unverified: which release between 0.5.0 and 0.7.0 moved it to
  Float, since `CHANGELOG.md` is silent.
- **TRGT on a BAM carrying 5mC and 5hmC calls on the same C.** `get_meth` does not check the
  modification code. The HG002 SPRQ-Nx value (0.1) is low, as a normal male's should be, but
  whether 5hmC probabilities leak into `AM` was not tested.
- **The default `methbat_region_tsv` in pipeline v4.0.0.** It sits in a 3.2 GB reference-data tar
  (Zenodo 21517827) that was not downloaded. The 2026Q2 run used `cpgIslandExt.sorted.hg38.tsv`.
- **Which pipeline release produced the 2026Q2 outputs.** `inputs.json` names `GRCh38.ref_map.v3p1p0`,
  and the tool versions in the file headers (pb-CpG-tools 3.0.0, MethBat 0.17.0, TRGT 5.0.0) match no
  tagged `tools_containers.md` exactly.
- **X inactivation as the reason for the female `AM` pattern.** n = 2, cell lines, no XCI assay.
- **modkit on PacBio data.** It produced no rows on the SPRQ-Nx slice; the cause was not diagnosed.
  modkit on ONT data was not run; its columns are quoted from its book and a test fixture.
- **DRAGEN's actual VCF bytes and FORMAT header.** Only Illumina's documentation page was read.
- **DeepVariant's VCF writer.** Known to consume 5mC; the claim that it emits no methylation field rests
  on a code search for `M5mC` and a read of two headers, not on the writer itself.
- **Clinical band values.** The 20 and 80 % imprinting thresholds are MethBat's defaults, not a
  guideline. No paper was opened for a methylation threshold at FMR1 or at any DMR, so any bin values
  quoted here are observations from samples, not proposed boundaries.
