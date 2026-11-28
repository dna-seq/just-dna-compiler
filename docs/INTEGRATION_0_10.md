# Old-reader breaks

A 0.9 format reader rejects a row or record that uses one of these 0.10 members. Upgrade readers
that validate licensing rows, verification records or warning summaries before producing modules
that use the new values.

| Closed vocabulary and field binding | New member |
| --- | --- |
| `VALID_SOURCE_LAYERS`, `source_layer` | `repeat_grade` |
| `VALID_VERIFICATION_CHECKS`, `verification_check` | `hla_allele_assignment` |
| `VALID_WARNING_CODES`, `warning_code` | `hla_allele_deleted` |
| `VALID_WARNING_CODES`, `warning_code` | `hla_allele_not_assigned` |
| `VALID_WARNING_CODES`, `warning_code` | `panel_unmatched_has_rows` |
| `VALID_WARNING_CODES`, `warning_code` | `panel_unmatched_not_requested` |
| `VALID_WARNING_CODES`, `warning_code` | `rsid_genotype_reads_as_two_events` |
| `VALID_WARNING_CODES`, `warning_code` | `study_effect_direction_disagrees_with_size` |

A 0.9 compiler reading a 0.10 spec warns `table_file_near_miss` on `repeat_grades.csv`.
Its similarity to `repeat_alleles.csv` is exactly 0.8, the filename check’s inclusive cutoff.
