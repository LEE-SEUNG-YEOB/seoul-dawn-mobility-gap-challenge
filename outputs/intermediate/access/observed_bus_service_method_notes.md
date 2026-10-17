# OA-21220 observed dawn bus service method notes

## Scope and grain

`observed_bus_service.csv` is limited actual-run evidence for direct-service
screening. Its grain is `route_id × stop_id × stop_sequence × hour`, where hour
is one of `03`, `04`, or `05`. Route and stop names are not joined, and the
OA-21220 stop sequence is preserved as supplied.

The five weekly source CSV files include dates outside September at their
edges. The build filters exactly 2026-09-01 through 2026-09-30 and reads
2,638,894 daily route-stop-sequence rows. The approved OA-21220 audit reports
zero duplicate business-key excess rows and zero exact duplicate rows for this
period; the output additionally verifies that its own four-column grain is
unique.

## Evidence rule and unknowns

A row is emitted only when at least one September cell contains a strictly
positive recorded run count for that route, stop, sequence, and hour.
`service_confirmed=true` therefore means only that direct service was recorded
at least once at that hourly grain. It does not establish an exact first arrival
or an end-to-end trip.

For each emitted row:

- `positive_service_days` counts September dates with a positive value.
- `positive_weekday_days` and `positive_weekend_days` split those dates by
  calendar Monday-Friday versus Saturday-Sunday. They are not holiday-adjusted.
- `observed_trip_count_sum` sums only nonblank positive values.
- `blank_cell_days` counts explicit blank hourly cells on present source rows.
- `missing_row_days` is 30 minus dates on which that source business key exists.
- `unknown_days` is `blank_cell_days + missing_row_days`.

Blank cells and missing daily rows remain unknown. They are never converted to
zero, `no_service`, or `no_gap`. There are 289,575 observed route-stop-sequence
hour combinations across the three hours; 217,551 have no positive cell and
are omitted from the compact evidence table. Their omission is not evidence of
service absence.

## Results

The compact table contains 72,024 positive-evidence combinations:

| Hour | Confirmed combinations | Unique routes | Unique stop IDs | Positive service-day observations | Recorded trip-count sum |
|---|---:|---:|---:|---:|---:|
| 03 | 3,628 | 210 | 2,519 | 85,957 | 171,663 |
| 04 | 18,886 | 680 | 8,536 | 475,086 | 1,305,555 |
| 05 | 49,510 | 1,129 | 16,932 | 1,289,642 | 4,556,575 |

These counts describe source records and are not unique vehicles, passengers,
beneficiaries, unmet demand, or policy effects.

## Interpretation limits and lineage

OA-21220 hourly aggregates cannot establish exact first arrival, travel time,
walking access, transfers, destination deadlines, or reachability. They do not
support service-gap ranking, demand weighting, beneficiary estimation,
15/30-minute schedule effects, short-route effects, or carbon effects.

Source lineage is OA-21220, provided by Seoul Metropolitan Government. Source
URL, retrieval time, license text, audit path, completeness checks, and hourly
summary metrics are recorded in `observed_bus_service_summary.json`.

Run from the repository root:

```text
.venv\Scripts\python.exe -m src.access.build_observed_bus_service
.venv\Scripts\python.exe -m pytest tests/access/test_observed_bus_service.py -q --basetemp=outputs/tmp/pytest_observed_bus
```

