# Transit supply/access audit method notes

## Permitted scope

The approved readiness mode is `separate_only` (`demand_ready=true`,
`transit_ready=true`, `join_ready=false`). Transit readiness means only a
technical inventory and the acquired planned-timetable cases. It does not mean
historical, citywide accessibility is ready.

No demand table is joined here. `service_gap_candidates.csv`, beneficiary
counts, demand-weighted rankings, carbon effects, 15/30-minute effects,
short-route effects, and before/after reachable areas are unsupported and are
not generated.

## OA-15334 denominator and usable cases

The local OA-15334 manifest records 1,999 completed unique requests from a
44,735-pair request universe: **4.46853694%**. This is request completion, not
usable timetable coverage. XML validation finds 1,963 valid `firstBusTm` items,
one of which has ARS ID `0`. The remaining 1,962 item rows represent **1,947
unique nonzero ARS-route pairs**. Fifteen pairs contain two valid timetable
items. For those pairs, the audit records the earliest clock time as the pair's
technical case and preserves every observed time in `observed_first_times`.

The 1,999 requests form a nonprobability subset. The 42,736 unrequested or
unfinished pairs, and all requested pairs without a usable timetable item, are
`unknown`; they are never treated as zero service or `no_gap`. The valid-pair
share of the original request universe is 4.35229686%, but it is not a
population coverage estimate.

## Fixed audit interpretation

`transit_coverage_audit.csv` contains one row for every one of the 1,947 valid
nonzero ARS-route pairs. `scenario=current` and `arrival_time` record the
acquired planned first-bus time at that stop. Because destination deadlines,
walking paths, transfer links, waiting assumptions, and a complete service
calendar are absent, `reachable` and `arrival_deadline` are blank and
`access_gap_status=unknown` for every row. The file does not assert actual
vehicle arrival or an end-to-end trip.

The selected pair cases include 1,041 first times from 03:00 inclusive to 06:00
exclusive: 1 in the 03 hour, 410 in the 04 hour, and 630 in the 05 hour. These
are descriptive counts inside the acquired nonprobability sample.

## Supply inventory and dates

- OA-1095 has 41,688 route-stop rows, 718 route IDs, 12,848 nonzero ARS IDs,
  and 41,023 unique nonzero route-ARS pairs in the 2026-09-02 snapshot.
- OA-21231 has 11,497 station-master rows in the 2026-10-16 snapshot.
- OA-21233 has 88,729 route-node rows in the 2026-10-16 snapshot.
- `data-go-15143847` has 296,720 saved timetable rows across the acquired query
  groups. The inventory separately reports weekday/weekend and direction, plus
  rows whose departure time is in 03:00-06:00. Public-holiday and always-day
  query groups returned zero rows in the local files; this is not proof of no
  service.

OA-1095 is a September 2 route-stop snapshot, while the bus masters, OA-15334
responses, and subway retrieval are October 16 snapshots. Their historical
equivalence for September is unverified. The subway request used a September
15 search datetime, but retrieval and source validity fields do not verify that
the observed schedule applied to every September analysis day. Actual bus and
train operation is not verified.

## Lineage, assumptions, and reproducibility

The fixed audit and first-bus distributions/coverage tables derive only from
OA-15334. The bus inventory derives from OA-1095, OA-21231, and OA-21233. The
subway inventory derives only from `data-go-15143847`. Row-level lineage for
OA-15334 includes the source JSONL path and line number. Dataset-level lineage
is also recorded in `access_summary.json`.

Unavailable walking, transfer, waiting, deadline, service-calendar,
short-route, and carbon inputs are externalized as inactive `null` assumptions
in `src/access/config/assumptions.json`; no default values are invented.

Run from the repository root:

```text
python -m src.access.build_supply_audit
python -m pytest tests/access -q --basetemp=outputs/tmp/pytest_access
```
